"""Train, save and register a Gaussian model from one BacktestRunner *_trades.csv.

Thin wrapper over training.trainer / core.model_registry (no new model logic).
The sample-count floor (MIN_GAUSSIAN_SAMPLES) is lowered at runtime only, by explicit
operator request via --min-samples; src/ is not modified.

    python scripts/training/gaussian_from_backtest.py \
        --trades results/gaussian_training/backtest/<run>/XAUUSD_trades.csv \
        --csv data/XAUUSD_M15.csv --version <label> --min-samples 5 --register --promote
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.dataset_builder import GAUSSIAN_FEATURE_SCHEMA, extract_feature_vector, rr_to_class  # noqa: E402
from features import feature_pipeline as fp  # noqa: E402
from training import trainer  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_definition() -> dict:
    """Feature-definition identity: parameters + pipeline source hash (not just names)."""
    d = {
        "structure_mode": fp.STRUCTURE_MODE_CAUSAL,
        "swing_window": fp.SWING_WINDOW,
        "swing_confirm_bars": fp.SWING_CONFIRM_BARS,
        "vol_regime_window": fp.VOL_REGIME_WINDOW,
        "vol_regime_pcts": [fp.VOL_REGIME_LOW_PCT, fp.VOL_REGIME_HIGH_PCT],
        "vol_regime": "ATR(14) mid-rank vs previous window bars, current excluded, same timeframe",
        "ordered_features": list(GAUSSIAN_FEATURE_SCHEMA),
        "feature_pipeline_py_sha256": _sha(ROOT / "src/features/feature_pipeline.py"),
    }
    d["definition_hash"] = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", required=True)
    ap.add_argument("--csv", required=True, help="OHLCV csv used by the backtest (provenance)")
    ap.add_argument("--version", required=True)
    ap.add_argument("--min-samples", type=int, default=trainer.MIN_GAUSSIAN_SAMPLES)
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--promote", action="store_true")
    a = ap.parse_args()

    rows = sorted(csv.DictReader(open(a.trades, encoding="utf-8-sig")), key=lambda r: r["opened_at"])
    X = [extract_feature_vector(r) for r in rows]          # strict: raises on missing/unmapped
    y = [float(r["pnl_rr_net"]) for r in rows]
    assert all(len(x) == len(GAUSSIAN_FEATURE_SCHEMA) for x in X)
    assert [r["opened_at"] for r in rows] == sorted(r["opened_at"] for r in rows)

    trainer.MIN_GAUSSIAN_SAMPLES = a.min_samples
    model, scaler, metrics = trainer.train_gaussian(X, y)
    n_tr = metrics["n_train"]
    cls_tr = Counter(rr_to_class(v) for v in y[:n_tr])
    cls_val = Counter(rr_to_class(v) for v in y[n_tr:])
    # leakage check: scaler stats equal training-only stats
    import statistics as st
    j = 0
    assert abs(scaler._mean[j] - st.fmean(x[j] for x in X[:n_tr])) < 1e-9

    fdef = feature_definition()
    prov = {
        "trades_csv": a.trades, "trades_csv_sha256": _sha(Path(a.trades)),
        "ohlcv_csv": a.csv, "ohlcv_csv_sha256": _sha(Path(a.csv)),
        "instrument_timeframe": "XAUUSD M15",
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
        "train_range": [rows[0]["opened_at"], rows[n_tr - 1]["opened_at"]],
        "val_range": [rows[n_tr]["opened_at"], rows[-1]["opened_at"]] if n_tr < len(rows) else None,
        "n_total": len(rows), "class_counts_train": dict(cls_tr), "class_counts_val": dict(cls_val),
        "split": "temporal 70/30, scaler and model fit on train only",
        "min_samples_override": a.min_samples,
        "caveat": "EXPERIMENTAL: operator-approved sample-count override; <=6 train rows, classes 2/3 absent",
    }
    name = f"gaussian_{a.version}.json"
    path = trainer.save_gaussian_model(model, scaler, metrics, name=name,
                                       feature_schema=list(GAUSSIAN_FEATURE_SCHEMA))
    bundle = json.loads(path.read_text())
    bundle["feature_definition"] = fdef
    bundle["provenance"] = prov
    path.write_text(json.dumps(bundle, indent=2))
    out = {"artifact": str(path), "sha256": _sha(path), "metrics": metrics, "provenance": prov,
           "definition_hash": fdef["definition_hash"], "schema_checksum": bundle["schema_checksum"]}

    if a.register:
        from core import model_registry as mr
        reg_path = ROOT / "models/gaussian_registry.json"
        backup = ROOT / f"models/gaussian_registry.pre_{a.version}.json"
        if reg_path.exists() and not backup.exists():
            shutil.copy2(reg_path, backup)
        mr.register_gaussian(a.version, name, list(GAUSSIAN_FEATURE_SCHEMA), metrics)
        reg = json.loads(reg_path.read_text())
        reg[a.version]["feature_definition_hash"] = fdef["definition_hash"]
        reg[a.version]["artifact_sha256"] = out["sha256"]
        reg[a.version]["experimental"] = True
        reg_path.write_text(json.dumps(reg, indent=2))
        if a.promote:
            ok, why = mr._gaussian_registry.promote_gaussian(a.version, force=True)  # v1 is a dangling entry
            out["promote"] = [ok, why]
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
