"""Build IC-002 path-relative trajectories — one FeaturePipeline pass, then slice."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.ic002_entry_evolution.io_util import (
    DEFAULT_OUT,
    load_entries,
    load_prereg,
    resolve_ohlcv,
    save_batch,
    sha256_file,
    sha256_text,
)
from research.ic002_entry_evolution.schema import (
    D,
    N_GRID,
    TRAJECTORY_FEATURE_IDS,
    TrajectoryBatch,
    path_relative_row,
)

logger = logging.getLogger("ic002.build")


def _load_ohlcv_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # normalize column names
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for need in ("open", "high", "low", "close", "volume"):
        if need in df.columns:
            continue
        if need in cols:
            rename[cols[need]] = need
    if rename:
        df = df.rename(columns=rename)
    df["_src_idx"] = np.arange(len(df), dtype=np.int64)
    return df


def run_feature_matrix(ohlcv_path: Path) -> pd.DataFrame:
    """Single FeaturePipeline.run(); preserve _src_idx through finalize."""
    from features.feature_pipeline import FeaturePipeline

    df = _load_ohlcv_df(ohlcv_path)
    # FeaturePipeline copies df; ensure _src_idx is on the copy
    fp = FeaturePipeline(df)
    if "_src_idx" not in fp.df.columns:
        fp.df["_src_idx"] = np.arange(len(fp.df), dtype=np.int64)
    enriched, _ = fp.run()
    if "_src_idx" not in enriched.columns:
        raise RuntimeError(
            "FeaturePipeline.finalize dropped _src_idx; cannot align entry_index"
        )
    # map original bar index -> row in enriched
    enriched = enriched.reset_index(drop=True)
    return enriched


def _row_features(row: pd.Series, fids: tuple[str, ...]) -> list[float]:
    out: list[float] = []
    for f in fids:
        v = row.get(f, np.nan)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out.append(0.0)
        else:
            out.append(float(v))
    return out


def build_for_N(
    enriched: pd.DataFrame,
    src_to_row: dict[int, int],
    entries: list[dict],
    N: int,
    fids: tuple[str, ...] = TRAJECTORY_FEATURE_IDS,
) -> TrajectoryBatch:
    trade_ids: list[str] = []
    entry_indices: list[int] = []
    timestamps: list[str] = []
    families: list[str] = []
    directions: list[str] = []
    y_list: list[int] = []
    outcomes: list[str] = []
    Z_list: list[list[list[float]]] = []
    X0_list: list[list[float]] = []

    n_bars = len(enriched)
    skipped = 0

    for o in entries:
        ei = int(o["entry_index"])
        if ei not in src_to_row:
            skipped += 1
            continue
        r0 = src_to_row[ei]
        # need entry bar + N forward bars present in enriched
        last_src = ei + N
        if last_src not in src_to_row:
            skipped += 1
            continue
        # also require contiguous forward bars exist as src indices
        ok = True
        row_idx_path: list[int] = []
        for k in range(1, N + 1):
            sk = ei + k
            if sk not in src_to_row:
                ok = False
                break
            row_idx_path.append(src_to_row[sk])
        if not ok:
            skipped += 1
            continue

        x0 = _row_features(enriched.iloc[r0], fids)
        Z_steps: list[list[float]] = []
        for ri in row_idx_path:
            xk = _row_features(enriched.iloc[ri], fids)
            Z_steps.append(path_relative_row(xk, x0))

        outcome = str(o.get("outcome", ""))
        y = 1 if outcome == "TP_HIT" else 0

        trade_ids.append(str(o.get("trade_id", f"idx_{ei}")))
        entry_indices.append(ei)
        timestamps.append(str(o.get("entry_timestamp", "")))
        families.append(str(o.get("family", "")))
        directions.append(str(o.get("direction", "")))
        y_list.append(y)
        outcomes.append(outcome)
        Z_list.append(Z_steps)
        X0_list.append(x0)

    logger.info("N=%s built=%s skipped=%s", N, len(trade_ids), skipped)
    Z = np.asarray(Z_list, dtype=np.float64)
    X0 = np.asarray(X0_list, dtype=np.float64)
    if len(trade_ids) == 0:
        Z = np.zeros((0, N, D), dtype=np.float64)
        X0 = np.zeros((0, D), dtype=np.float64)
    return TrajectoryBatch(
        N=N,
        feature_ids=fids,
        trade_ids=trade_ids,
        entry_indices=entry_indices,
        timestamps=timestamps,
        families=families,
        directions=directions,
        y=y_list,
        outcomes=outcomes,
        Z=Z,
        X0=X0,
    )


def build_all(
    *,
    entries_path: Path | None = None,
    ohlcv_path: Path | None = None,
    out_dir: Path | None = None,
    n_grid: tuple[int, ...] = N_GRID,
) -> dict[str, Any]:
    prereg = load_prereg()
    ohlcv = ohlcv_path or resolve_ohlcv(prereg["population"].get("ohlcv_candidates"))
    out_dir = out_dir or DEFAULT_OUT
    entries = load_entries(entries_path)

    logger.info("OHLCV=%s entries=%s", ohlcv, len(entries))
    enriched = run_feature_matrix(ohlcv)
    src_to_row = {
        int(s): i for i, s in enumerate(enriched["_src_idx"].astype(int).tolist())
    }

    # missing feature check
    missing = [f for f in TRAJECTORY_FEATURE_IDS if f not in enriched.columns]
    if missing:
        raise RuntimeError(f"Enriched frame missing trajectory features: {missing}")

    entry_ids = sorted(str(o.get("trade_id", "")) for o in entries)
    manifest: dict[str, Any] = {
        "program": "H-IC002-001",
        "ohlcv_path": str(ohlcv),
        "ohlcv_sha256": sha256_file(ohlcv),
        "n_entries_source": len(entries),
        "entry_id_list_sha256": sha256_text("\n".join(entry_ids)),
        "feature_ids": list(TRAJECTORY_FEATURE_IDS),
        "N_grid": list(n_grid),
        "batches": {},
    }

    for N in n_grid:
        batch = build_for_N(enriched, src_to_row, entries, N)
        paths = save_batch(out_dir, batch)
        manifest["batches"][str(N)] = {
            "n_trajectories": len(batch.trade_ids),
            "n_pos": int(sum(batch.y)),
            **paths,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    import json

    (out_dir / "build_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest
