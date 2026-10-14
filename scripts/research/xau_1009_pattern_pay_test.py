"""Does it pay? per candle pattern (FM-103..119 + morning_star), XAUUSD M15 2-year corpus.
Same trade rule as tools/xau_chart/zone_edge.py (stop 1 ATR, target 2 ATR, 16 bars, $0.26 cost, enter at the
signal bar's close). Observation only. Adds a same-n random-bar control and a first/second-half split.

Exploratory. Result: 0 of 9 directional patterns beat random bars on their named side; smallest p 0.052 of 22.
Rule frozen and result logged in assistant_project.md SESSION LOG, 2026-10-09.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/research/xau_1009"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools/xau_chart"))
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features import candle_patterns as CP  # noqa: E402
from data_ingestion.corpus_store import load as corpus_load  # noqa: E402
class ZS:  # the four constants of tools/xau_chart/zone_study.py (untracked), same values
    STOP, TGT, H, COST = 1.0, 2.0, 16, 0.26

path = ROOT / "data/mt5/XAUUSD_M15.csv"
raw = corpus_load(path, sequence_check=False).frame(parse_dates=["timestamp"])
print("corpus", path, "rows", len(raw), "first", raw.timestamp.iloc[0], "last", raw.timestamp.iloc[-1], flush=True)
enriched, _ = FeaturePipeline(raw.copy()).run()
cols = list(CP.PATTERN_COLUMNS) + ["morning_star"]
missing = [c for c in cols if c not in enriched.columns]
print("missing pattern cols:", missing, flush=True)
df = enriched.reset_index(drop=True)
print("bars after warmup", len(df), "first", df.timestamp.iloc[0], "last", df.timestamp.iloc[-1], flush=True)

c = df["close"].to_numpy(float); atr = df["atr"].to_numpy(float) * c
hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
n = len(c); half = n // 2
cost_r = ZS.COST / np.where(atr > 0, atr, np.nan)


def trade_r(i, sgn):
    a, e = atr[i], c[i]
    for j in range(i + 1, i + ZS.H + 1):
        if (lo[j] <= e - ZS.STOP * a) if sgn > 0 else (hi[j] >= e + ZS.STOP * a):
            return -1.0
        if (hi[j] >= e + ZS.TGT * a) if sgn > 0 else (lo[j] <= e - ZS.TGT * a):
            return ZS.TGT / ZS.STOP
    return sgn * (c[i + ZS.H] - e) / (ZS.STOP * a)


RL = np.full(n, np.nan); RS = np.full(n, np.nan)
for i in range(n):
    if atr[i] > 0 and i + ZS.H < n:
        RL[i], RS[i] = trade_r(i, 1), trade_r(i, -1)
NET = {"long": RL - cost_r, "short": RS - cost_r}
GROSS = {"long": RL, "short": RS}
rng = np.random.default_rng(20261008)


def summarize(mask, side):
    m = mask & ~np.isnan(NET[side])
    k = int(m.sum())
    if k == 0:
        return None
    idx = np.where(m)[0]
    net = NET[side][idx]; gross = GROSS[side][idx]
    valid = np.where(~np.isnan(NET[side]))[0]
    draws = [np.nanmean(NET[side][rng.choice(valid, size=k, replace=False)]) for _ in range(2000)]
    p = float((np.sum(np.array(draws) >= net.mean()) + 1) / (len(draws) + 1))      # one-sided: pattern better than luck
    h1 = net[idx < half]; h2 = net[idx >= half]
    return {"n": k, "win": float((gross >= 2.0).mean()), "R": float(net.mean()), "R_gross": float(gross.mean()),
            "p_vs_random": p, "R_h1": float(h1.mean()) if len(h1) else None, "n_h1": int(len(h1)),
            "R_h2": float(h2.mean()) if len(h2) else None, "n_h2": int(len(h2))}


INTENT = {"hammer": "long", "pin_lower": "long", "engulfing_bull": "long", "dragonfly_doji": "long", "morning_star": "long",
          "shooting_star": "short", "pin_upper": "short", "engulfing_bear": "short", "gravestone_doji": "short"}
out = {"corpus": {"path": str(path), "rows": len(raw), "bars": n, "first": str(df.timestamp.iloc[0]), "last": str(df.timestamp.iloc[-1])},
       "params": {"stop_atr": ZS.STOP, "target_atr": ZS.TGT, "horizon_bars": ZS.H, "cost": ZS.COST},
       "base": {s: summarize(np.ones(n, bool), s) for s in ("long", "short")}, "patterns": {}}
for col in cols:
    if col in missing:
        continue
    v = df[col].to_numpy(float)
    if col in ("upper_wick_ratio", "lower_wick_ratio", "compression_ratio", "rejection_intensity_signed",
               "rejection_intensity_lower", "rejection_intensity_upper", "engulfing_strength"):
        continue                      # continuous measures: not on/off flags; out of scope for this table
    flag = np.nan_to_num(v) > 0.5
    out["patterns"][col] = {"intent": INTENT.get(col, "both"), "flag_count": int(flag.sum()),
                            "long": summarize(flag, "long"), "short": summarize(flag, "short")}
    r = out["patterns"][col]
    for s in ("long", "short"):
        x = r[s]
        print(f"{col:16s} {s:5s} flags={r['flag_count']:5d} ", "n/a" if x is None else
              f"n={x['n']:5d} win={x['win']:.3f} netR={x['R']:+.3f} grossR={x['R_gross']:+.3f} p={x['p_vs_random']:.3f} h1={x['R_h1']} h2={x['R_h2']}", flush=True)
print("base", json.dumps(out["base"]))
(OUT / "pattern_pay.json").write_text(json.dumps(out), encoding="utf-8")
