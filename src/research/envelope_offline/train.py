"""Narrow multi-head Envelope offline trainer — ENV_OFFLINE_TRAIN_V1.

Trains independent HistGradientBoostingRegressor heads on TN_ENV_CLEAN_L2 labels.
Research artifacts only.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from features.feature_schema import SCHEMA_HASH
from research.clean_labels.builder import LEGACY_FEATURE_NAMES

CHARTER_ID = "ENV_OFFLINE_TRAIN_V1"
REQUIRED_PROTOCOL = "TN_ENV_CLEAN_L2"
HEADS = (
    "y_mfe_r",
    "y_mae_r_heat",
    "y_holding_bars",
    "y_time_to_mfe",
)
HEAD_KEYS = {
    "y_mfe_r": "mfe_r",
    "y_mae_r_heat": "mae_r_heat",
    "y_holding_bars": "holding_bars",
    "y_time_to_mfe": "time_to_mfe",
}
IC_RETAIN_FLOOR = 0.10
OVERFIT_GAP = 0.15
SEED = 42


@dataclass
class TrainConfig:
    dataset_path: str
    out_dir: str
    instrument: str = "BNBUSDT"
    max_rows: int | None = None
    train_frac: float = 0.60
    val_frac: float = 0.20
    # test = remainder
    seed: int = SEED
    max_depth: int = 6
    max_iter: int = 100
    learning_rate: float = 0.08
    min_samples_leaf: int = 40


@dataclass
class HeadMetrics:
    n_train: int
    n_val: int
    n_test: int
    y_mean_test: float
    y_std_test: float
    train_ic: float | None
    val_ic: float | None
    test_ic: float | None
    test_rmse: float | None
    test_r2: float | None
    val_test_ic_gap: float | None
    long_test_ic: float | None
    short_test_ic: float | None
    tag: str


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    m = np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < 30:
        return None
    aa, bb = a[m], b[m]
    ra = aa.argsort().argsort().astype(float)
    rb = bb.argsort().argsort().astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    if den <= 0:
        return None
    return float((ra * rb).sum() / den)


def _rmse(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y - p) ** 2)))


def _r2(y: np.ndarray, p: np.ndarray) -> float | None:
    ss_res = float(np.sum((y - p) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot <= 0:
        return None
    return float(1.0 - ss_res / ss_tot)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_l2_matrix(
    dataset_path: Path,
    max_rows: int | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray], np.ndarray, np.ndarray, dict]:
    """Load features + envelope heads; enforce protocol via sidecar meta if present."""
    meta_path = dataset_path.parent / "dataset_meta.json"
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        pid = meta.get("protocol_id")
        if pid != REQUIRED_PROTOCOL:
            raise ValueError(
                f"ENV_OFFLINE_TRAIN_V1 requires {REQUIRED_PROTOCOL}, got protocol_id={pid!r}"
            )

    X_rows: list[list[float]] = []
    ys: dict[str, list[float]] = {h: [] for h in HEADS}
    entry_index: list[float] = []
    side_long: list[float] = []
    n = 0
    with dataset_path.open(encoding="utf-8") as fh:
        for line in fh:
            if max_rows is not None and n >= max_rows:
                break
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            vec = r.get("feature_vector")
            if not isinstance(vec, list) or len(vec) != 38:
                continue
            # require finite primary heads except time_to_mfe may be nan
            ok = True
            vals: dict[str, float] = {}
            for h in HEADS:
                v = r.get(h)
                if h == "y_time_to_mfe" and v is None:
                    vals[h] = float("nan")
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    ok = False
                    break
                if h != "y_time_to_mfe" and not math.isfinite(fv):
                    ok = False
                    break
                vals[h] = fv
            if not ok:
                continue
            X_rows.append([float(x) for x in vec])
            for h in HEADS:
                ys[h].append(vals[h])
            entry_index.append(float(r.get("entry_index", n)))
            side_long.append(1.0 if str(r.get("side", "")).lower() == "long" else 0.0)
            n += 1

    if n < 500:
        raise ValueError(f"too few rows for offline train: n={n}")

    X = np.asarray(X_rows, dtype=np.float64)
    Y = {h: np.asarray(ys[h], dtype=np.float64) for h in HEADS}
    return (
        X,
        Y,
        np.asarray(entry_index, dtype=np.float64),
        np.asarray(side_long, dtype=np.float64),
        meta,
    )


def time_split(
    entry_index: np.ndarray,
    train_frac: float,
    val_frac: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(entry_index, kind="mergesort")
    n = len(order)
    n_tr = int(n * train_frac)
    n_va = int(n * val_frac)
    if n_tr < 200 or n_va < 100 or (n - n_tr - n_va) < 100:
        raise ValueError(f"split too small: n={n} tr={n_tr} va={n_va}")
    tr = order[:n_tr]
    va = order[n_tr : n_tr + n_va]
    te = order[n_tr + n_va :]
    return tr, va, te


def _tag_head(test_ic: float | None, val_ic: float | None) -> str:
    if test_ic is None:
        return "INDETERMINATE"
    if test_ic <= 0:
        return "SIGNAL_FAIL"
    gap = None
    if val_ic is not None:
        gap = val_ic - test_ic
        if gap > OVERFIT_GAP and test_ic < 0.05:
            return "SIGNAL_FAIL"
    if test_ic > IC_RETAIN_FLOOR:
        return "SIGNAL_RETAINED"
    return "SIGNAL_WEAK"


def _fit_head(
    Xtr: np.ndarray,
    ytr: np.ndarray,
    cfg: TrainConfig,
):
    from sklearn.ensemble import HistGradientBoostingRegressor

    # drop non-finite train rows (time_to_mfe)
    m = np.isfinite(ytr)
    model = HistGradientBoostingRegressor(
        max_depth=cfg.max_depth,
        max_iter=cfg.max_iter,
        learning_rate=cfg.learning_rate,
        min_samples_leaf=cfg.min_samples_leaf,
        random_state=cfg.seed,
    )
    model.fit(Xtr[m], ytr[m])
    return model


def run_offline_train(cfg: TrainConfig) -> dict[str, Any]:
    dataset_path = Path(cfg.dataset_path)
    out_dir = Path(cfg.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    X, Y, entry_index, side_long, ds_meta = load_l2_matrix(dataset_path, cfg.max_rows)
    tr, va, te = time_split(entry_index, cfg.train_frac, cfg.val_frac)

    head_metrics: dict[str, Any] = {}
    head_paths: dict[str, str] = {}
    tags: list[str] = []

    for h in HEADS:
        key = HEAD_KEYS[h]
        y = Y[h]
        model = _fit_head(X[tr], y[tr], cfg)

        def _pred(idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            m = np.isfinite(y[idx])
            ii = idx[m]
            return y[ii], model.predict(X[ii])

        y_tr, p_tr = _pred(tr)
        y_va, p_va = _pred(va)
        y_te, p_te = _pred(te)

        train_ic = _spearman(y_tr, p_tr)
        val_ic = _spearman(y_va, p_va)
        test_ic = _spearman(y_te, p_te)
        test_rmse = _rmse(y_te, p_te) if len(y_te) else None
        test_r2 = _r2(y_te, p_te) if len(y_te) else None
        gap = None if val_ic is None or test_ic is None else float(val_ic - test_ic)

        # side slices on test
        te_m = te[np.isfinite(y[te])]
        long_m = te_m[side_long[te_m] == 1]
        short_m = te_m[side_long[te_m] == 0]
        long_ic = (
            _spearman(y[long_m], model.predict(X[long_m])) if len(long_m) >= 30 else None
        )
        short_ic = (
            _spearman(y[short_m], model.predict(X[short_m])) if len(short_m) >= 30 else None
        )

        tag = _tag_head(test_ic, val_ic)
        tags.append(tag)
        hm = HeadMetrics(
            n_train=int(np.isfinite(y[tr]).sum()),
            n_val=int(np.isfinite(y[va]).sum()),
            n_test=int(np.isfinite(y[te]).sum()),
            y_mean_test=float(np.nanmean(y[te])),
            y_std_test=float(np.nanstd(y[te])),
            train_ic=None if train_ic is None else round(train_ic, 4),
            val_ic=None if val_ic is None else round(val_ic, 4),
            test_ic=None if test_ic is None else round(test_ic, 4),
            test_rmse=None if test_rmse is None else round(test_rmse, 4),
            test_r2=None if test_r2 is None else round(test_r2, 4),
            val_test_ic_gap=None if gap is None else round(gap, 4),
            long_test_ic=None if long_ic is None else round(long_ic, 4),
            short_test_ic=None if short_ic is None else round(short_ic, 4),
            tag=tag,
        )
        head_metrics[key] = asdict(hm)

        art = out_dir / f"head_{key}.joblib"
        joblib.dump(
            {
                "model": model,
                "head": h,
                "key": key,
                "feature_names": list(LEGACY_FEATURE_NAMES),
                "charter_id": CHARTER_ID,
                "protocol_id": REQUIRED_PROTOCOL,
            },
            art,
        )
        head_paths[key] = str(art)

    # rollup from head tags
    head_tags = [head_metrics[HEAD_KEYS[h]]["tag"] for h in HEADS]
    if any(t == "SIGNAL_FAIL" for t in head_tags):
        rollup = "SIGNAL_FAIL"
    elif all(t == "SIGNAL_RETAINED" for t in head_tags):
        rollup = "SIGNAL_RETAINED"
    else:
        rollup = "SIGNAL_WEAK"

    dataset_sha = _file_sha256(dataset_path)
    bundle = {
        "charter_id": CHARTER_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "TRAIN_COMPLETE",
        "signal_rollup": rollup,
        "instrument": cfg.instrument,
        "required_protocol": REQUIRED_PROTOCOL,
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_sha,
        "dataset_protocol_id": ds_meta.get("protocol_id"),
        "dataset_protocol_hash": ds_meta.get("protocol_hash"),
        "schema_hash": SCHEMA_HASH,
        "pit_status": ds_meta.get("pit_status", "PIT_UNCLEAN_STORED_FEATURES"),
        "n_rows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "split": {
            "train_frac": cfg.train_frac,
            "val_frac": cfg.val_frac,
            "n_train": int(len(tr)),
            "n_val": int(len(va)),
            "n_test": int(len(te)),
            "order": "entry_index_ascending",
        },
        "hyperparams": {
            "model": "HistGradientBoostingRegressor",
            "max_depth": cfg.max_depth,
            "max_iter": cfg.max_iter,
            "learning_rate": cfg.learning_rate,
            "min_samples_leaf": cfg.min_samples_leaf,
            "random_state": cfg.seed,
        },
        "heads": head_metrics,
        "head_artifacts": head_paths,
        "ic_retain_floor": IC_RETAIN_FLOOR,
        "authority": {
            "production": False,
            "registry_promote": False,
            "spine_wire": False,
            "fusion": False,
            "planner": False,
            "tradenet_outcome_train": False,
        },
        "feature_names": list(LEGACY_FEATURE_NAMES),
    }

    bundle_path = out_dir / "envelope_bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    report = _render_report(bundle)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    return bundle


def predict_envelope_from_bundle(
    bundle_dir: Path,
    feature_vector: list[float] | np.ndarray,
) -> dict[str, float]:
    """Research-only multi-head predict. Not for EngineRunner."""
    bundle = json.loads((bundle_dir / "envelope_bundle.json").read_text(encoding="utf-8"))
    x = np.asarray(feature_vector, dtype=np.float64).reshape(1, -1)
    if x.shape[1] != 38:
        raise ValueError(f"expected 38 features, got {x.shape[1]}")
    out: dict[str, float] = {}
    for key, path in bundle["head_artifacts"].items():
        payload = joblib.load(path)
        out[key] = float(payload["model"].predict(x)[0])
    return out


def _render_report(b: dict) -> str:
    lines = [
        f"# Envelope Offline Train — {b['charter_id']}",
        "",
        f"| Field | Value |",
        f"|-------|--------|",
        f"| created | {b['created_utc']} |",
        f"| instrument | {b['instrument']} |",
        f"| protocol | {b['dataset_protocol_id']} |",
        f"| protocol_hash | `{b.get('dataset_protocol_hash', '')}` |",
        f"| n_rows | {b['n_rows']} |",
        f"| status | **{b['status']}** |",
        f"| signal_rollup | **{b['signal_rollup']}** |",
        f"| authority | research offline only |",
        "",
        "## Test metrics (primary = Spearman IC)",
        "",
        "| Head | test IC | val IC | gap | RMSE | R² | long IC | short IC | Tag |",
        "|------|---------|--------|-----|------|----|---------|----------|-----|",
    ]
    for key, h in b["heads"].items():
        lines.append(
            f"| `{key}` | {h['test_ic']} | {h['val_ic']} | {h['val_test_ic_gap']} | "
            f"{h['test_rmse']} | {h['test_r2']} | {h['long_test_ic']} | {h['short_test_ic']} | "
            f"**{h['tag']}** |"
        )
    lines += [
        "",
        f"IC retain floor: {b['ic_retain_floor']}",
        "",
        "## Explicit non-claims",
        "",
        "- No production KEEP",
        "- No Fusion / planner / neural_fn",
        "- No TradeNet outcome training",
        "- PIT unclean features inherited — GATE-P forbidden",
        "",
        f"Artifacts under run directory; dataset_sha256=`{b['dataset_sha256'][:16]}…`",
        "",
    ]
    return "\n".join(lines)
