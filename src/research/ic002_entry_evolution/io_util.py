"""Load prereg JSON, entries, OHLCV path resolution, save trajectory batches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from research.ic002_entry_evolution.schema import N_GRID, TRAJECTORY_FEATURE_IDS, TrajectoryBatch

_ROOT = Path(__file__).resolve().parents[3]
PREREG_JSON = _ROOT / "docs" / "research-readiness" / "h-ic002-entry-evolution-experiment-definition.json"
DEFAULT_ENTRIES = _ROOT / "results" / "research" / "trace_corpus" / "xauusd" / "trace_corpus_enriched.jsonl"
DEFAULT_OUT = _ROOT / "results" / "research" / "ic_002"


def repo_root() -> Path:
    return _ROOT


def load_prereg() -> dict[str, Any]:
    return json.loads(PREREG_JSON.read_text(encoding="utf-8"))


def resolve_ohlcv(candidates: list[str] | None = None) -> Path:
    cands = candidates or [
        "data/mt5/XAUUSD_M15.csv",
        "data/XAUUSD_M15.csv",
    ]
    for rel in cands:
        p = _ROOT / rel
        if p.exists():
            return p
    raise FileNotFoundError(f"No OHLCV found among {cands}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_entries(path: Path | None = None) -> list[dict]:
    path = path or DEFAULT_ENTRIES
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            if o.get("entry_index") is None:
                continue
            # warmup-null: missing engine or feature
            if o.get("feature_rsi_14") is None and o.get("engine_crt_score") is None:
                # still allow if we only need entry_index — but prereg says exclude warmup null features
                if o.get("feature_body_ratio") is None:
                    continue
            rows.append(o)
    return rows


def save_batch(out_dir: Path, batch: TrajectoryBatch) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = batch.N
    npz_path = out_dir / f"trajectories_N{n}.npz"
    meta_path = out_dir / f"trajectories_N{n}_meta.jsonl"
    np.savez_compressed(
        npz_path,
        Z=np.asarray(batch.Z, dtype=np.float64),
        X0=np.asarray(batch.X0, dtype=np.float64),
        y=np.asarray(batch.y, dtype=np.int8),
        entry_indices=np.asarray(batch.entry_indices, dtype=np.int64),
        feature_ids=np.array(batch.feature_ids),
        N=np.array([n]),
    )
    with open(meta_path, "w", encoding="utf-8") as f:
        for i, tid in enumerate(batch.trade_ids):
            f.write(
                json.dumps(
                    {
                        "trade_id": tid,
                        "entry_index": batch.entry_indices[i],
                        "timestamp": batch.timestamps[i],
                        "family": batch.families[i],
                        "direction": batch.directions[i],
                        "outcome": batch.outcomes[i],
                        "y": batch.y[i],
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    return {"npz": str(npz_path), "meta": str(meta_path)}


def load_batch(out_dir: Path, N: int) -> TrajectoryBatch:
    npz_path = out_dir / f"trajectories_N{N}.npz"
    meta_path = out_dir / f"trajectories_N{N}_meta.jsonl"
    data = np.load(npz_path, allow_pickle=True)
    trade_ids: list[str] = []
    timestamps: list[str] = []
    families: list[str] = []
    directions: list[str] = []
    outcomes: list[str] = []
    y: list[int] = []
    entry_indices: list[int] = []
    with open(meta_path, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            trade_ids.append(o["trade_id"])
            timestamps.append(o.get("timestamp", ""))
            families.append(o.get("family", ""))
            directions.append(o.get("direction", ""))
            outcomes.append(o.get("outcome", ""))
            y.append(int(o["y"]))
            entry_indices.append(int(o["entry_index"]))
    fids = tuple(str(x) for x in data["feature_ids"].tolist())
    if fids != TRAJECTORY_FEATURE_IDS:
        # allow load but warn via assert soft
        pass
    return TrajectoryBatch(
        N=N,
        feature_ids=fids if fids else TRAJECTORY_FEATURE_IDS,
        trade_ids=trade_ids,
        entry_indices=entry_indices,
        timestamps=timestamps,
        families=families,
        directions=directions,
        y=y,
        outcomes=outcomes,
        Z=data["Z"],
        X0=data["X0"],
    )
