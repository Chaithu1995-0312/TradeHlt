"""set2_consumer_scale_probe.py — OBSERVE-ONLY measurement of the Set-2 consumer unit contract.

Runs the XAUUSD M15 corpus through FeaturePipeline once per
`feature_pipeline.normalization_basis` and feeds the REAL consumers
(engine_runner.detect_regime / breakout_engine, GateIntelligence._vol_score,
EmaMomentumKernel.compute), reporting how degenerate each is under each basis
(F-061 / F-064 / F-109). Writes JSON under results/set2_consumer_scale/. Changes no config,
no code, no authority (§6.5): a distribution report, not a verdict.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from config_layer.production_config import get_prod_section               # noqa: E402
from core import engine_runner as er                                       # noqa: E402
from core.gate_intelligence import GateIntelligence                        # noqa: E402
from engines.ema_momentum_kernel import EmaMomentumKernel                  # noqa: E402
from features.feature_pipeline import FeaturePipeline                      # noqa: E402

DEFAULT_CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
OUT_DIR = ROOT / "results" / "set2_consumer_scale"


def _frac(mask) -> float:
    mask = np.asarray(mask)
    return float(mask.mean()) if mask.size else float("nan")


def measure(df: pd.DataFrame, cfg: dict, basis: str) -> dict:
    fp_cfg = {**cfg["feature_pipeline"], "normalization_basis": basis}
    out, _ = FeaturePipeline(df, cfg=fp_cfg).run()
    dual = dict(cfg["engine_runner"]["dual_engine"])
    rows = out.to_dict("records")
    n = len(rows)

    arms = {
        "legacy_regime": dual,
        "z_confirm_regime": {**dual, "regime_trend_confirmation": "trend_strength_z",
                             "regime_trend_strength_z_threshold": 1.5},
    }
    regimes = {k: {"trend": 0, "range": 0, "neutral": 0} for k in arms}
    for r in rows:
        for k, a in arms.items():
            regimes[k][er.detect_regime(r, a)] += 1
    regime_share = {k: {s: c / n for s, c in v.items()} for k, v in regimes.items()}

    bscore = np.array([er.breakout_engine(r, dual)["score"] for r in rows])

    vol = {}
    for gb in ("legacy_relative", "absolute"):
        gi = GateIntelligence({**cfg.get("gate_intelligence", {}), "gate_vol_atr_basis": gb})
        vs = np.array([gi._vol_score(r) for r in rows])
        vol[gb] = {"nonzero_frac": _frac(vs > 0), "mean": float(vs.mean()),
                   "pctl_5_25_50_75_95": [float(x) for x in np.percentile(vs, [5, 25, 50, 75, 95])],
                   "frac_ge_0.55": _frac(vs >= 0.55)}

    kernel = EmaMomentumKernel({"instrument": "XAUUSD"})
    ks = np.array([kernel.compute(r)["score"] for r in rows])
    mom = out["momentum_score"].to_numpy(np.float64)
    spr = out["ema_spread"].to_numpy(np.float64)
    return {
        "basis": basis,
        "rows": n,
        "median_abs_ema_spread": float(np.nanmedian(np.abs(spr))),
        "median_abs_momentum_score": float(np.nanmedian(np.abs(mom))),
        "tanh_saturated_gt_0.999": _frac(np.abs(np.tanh(mom)) > 0.999),
        "regime_share": regime_share,
        "breakout_score_pinned_1.0": _frac(bscore >= 1.0),
        "vol_score": vol,
        "kernel_score_std": float(ks.std()),
        "kernel_score_mean": float(ks.mean()),
        "kernel_pctl_5_25_50_75_95": [float(x) for x in np.percentile(ks, [5, 25, 50, 75, 95])],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--rows", type=int, default=0, help="first N rows only (0 = all)")
    ap.add_argument("--label", default="probe")
    a = ap.parse_args()

    df = pd.read_csv(a.csv)
    if a.rows:
        df = df.head(a.rows)
    print(f"CSV={a.csv} rows={len(df)}")
    cfg = {k: get_prod_section(k) for k in ("feature_pipeline", "engine_runner", "gate_intelligence")}
    result = {"csv": a.csv, "rows_in": len(df),
              "active_basis": cfg["feature_pipeline"]["normalization_basis"],
              "arms": [measure(df, cfg, b) for b in ("atr_relative", "atr_absolute")]}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / f"{a.label}.json"
    p.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
