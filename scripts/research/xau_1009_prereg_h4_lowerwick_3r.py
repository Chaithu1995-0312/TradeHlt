"""# Pre-registration — H4 lower-wick long, 1:3 (written 2026-10-09, before any run of this rule)

**Signal.** H4 XAUUSD bar (repo `research.resample` H4 on the corpus market calendar, fx_metals 17:00 New York)
where `pin_lower` OR `hammer` fires (repo `features.candle_patterns.compute_all`, active-config thresholds,
size gate on H4 SMA14 true range). One signal per bar even if both fire.

**Trade.** Long. Entry = signal bar close. Stop = signal bar low. Risk = entry − stop (skip if ≤ 0).
Target = entry + 3 × risk. Walk forward one H4 bar at a time:
- bar low ≤ stop → stopped at −1R (if the same bar also reaches the target, it counts as stopped);
- bar high ≥ target → +3R;
- neither within 30 bars → exit at the close of bar 30, marked to market.
Cost $0.26/oz round trip: net R = gross R − 0.26 / risk.

**Positions.** Primary: one position at a time (a signal while a trade is open is skipped).
Secondary (reported, not the verdict): every signal taken.

**Data.**
- Out-of-sample (the verdict): `data/mt5/XAUUSD_M15_2026-04-20_to_2026-10-06.csv`; only signals
  whose H4 bar opens after the 2-year file's last bar (2026-05-21 20:45 UTC). April–May bars are
  used for warm-up only.
- In-sample (comparison only): `data/mt5/XAUUSD_M15.csv`.

**Verdict rule.** If out-of-sample trades < 30: INSUFFICIENT, no claim either way.
Otherwise PASS only if mean net R > 0 AND the 95% bootstrap interval of mean net R lies above 0.
Anything else: FAIL. No re-run with a different exit, stop, pattern set or horizon on this data.

Result: INSUFFICIENT. Out-of-sample n=14, mean net -0.44R, 95% CI [-1.01, +0.42].
Rule frozen and result logged in assistant_project.md SESSION LOG, 2026-10-09.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/research/xau_1009"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))
from data_ingestion.corpus_store import load as corpus_load  # noqa: E402
from config_layer.crt_engine_v2 import Candle  # noqa: E402
from research.resample import resample  # noqa: E402
from features import candle_patterns as CP  # noqa: E402
from config_layer.production_config import get_prod_section  # noqa: E402

COST, TGT, MAX_BARS = 0.26, 3.0, 30
CUTOFF = pd.Timestamp("2026-05-21 20:45:00")       # last bar of the 2-year file, UTC
cfg = get_prod_section("feature_pipeline")
P = CP.CandlePatternParams.from_cfg(cfg["candle_patterns"]); PERIOD = int(cfg["atr_period"])


def h4_frame(path):
    corp = corpus_load(path, sequence_check=False)
    m = corp.frame(parse_dates=["timestamp"])
    print("corpus", path, "rows", len(m), m.timestamp.iloc[0], "->", m.timestamp.iloc[-1], flush=True)
    cs = [Candle(timestamp=r.timestamp.to_pydatetime(), open=float(r.open), high=float(r.high), low=float(r.low),
                 close=float(r.close), volume=float(r.volume), index=i) for i, r in enumerate(m.itertuples(index=False))]
    h4 = resample(cs, "H4", calendar=corp.calendar)
    df = pd.DataFrame({"t": [c.timestamp for c in h4], "o": [c.open for c in h4], "h": [c.high for c in h4],
                       "l": [c.low for c in h4], "c": [c.close for c in h4]})
    df["t"] = pd.to_datetime(df["t"]).dt.tz_localize(None) if getattr(pd.to_datetime(df["t"]).dt, "tz", None) else pd.to_datetime(df["t"])
    print("  H4 bars", len(df), df.t.iloc[0], "->", df.t.iloc[-1], flush=True)
    return df


def h4_patterns(df):
    """Candle-pattern flags computed on the H4 candles themselves (CH-timeframe-ssot-v1: the one place
    this script's H4 patterns come from, so analysis scripts reuse it instead of re-deriving them)."""
    o, h, l, c = (df[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    pc_ = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc_), np.abs(l - pc_)]), axis=0)
    atr = pd.Series(tr).rolling(PERIOD).mean().to_numpy()
    return CP.compute_all(o, h, l, c, atr, CP.contiguous_mask(df.t.to_numpy()), P), atr


def run(df, start_after=None):
    o, h, l, c = (df[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    pat, atr = h4_patterns(df)
    sig = (pat["pin_lower"] > 0.5) | (pat["hammer"] > 0.5)
    n = len(c); trades = []
    for i in np.where(sig)[0]:
        if start_after is not None and df.t.iloc[i] <= start_after:
            continue
        e, stop = c[i], l[i]; risk = e - stop
        if risk <= 0:
            continue
        tgt = e + TGT * risk; res = None
        for k in range(1, MAX_BARS + 1):
            j = i + k
            if j >= n:
                break
            if l[j] <= stop:
                res = (-1.0, k, "stop"); break
            if h[j] >= tgt:
                res = (TGT, k, "target"); break
        if res is None:
            if i + MAX_BARS < n:
                res = ((c[i + MAX_BARS] - e) / risk, MAX_BARS, "time")
            else:
                trades.append({"i": int(i), "t": str(df.t.iloc[i]), "open": True}); continue
        g, k, why = res
        trades.append({"i": int(i), "t": str(df.t.iloc[i]), "entry": e, "stop": stop, "target": tgt, "risk": risk,
                       "R_gross": g, "R_net": g - COST / risk, "bars": k, "exit": why, "exit_i": int(i + k), "open": False})
    closed = [t for t in trades if not t["open"]]
    one = []; busy_until = -1
    for t in closed:
        if t["i"] > busy_until:
            one.append(t); busy_until = t["exit_i"]
    return closed, one, [t for t in trades if t["open"]]


def summary(ts, seed=7):
    if not ts:
        return {"n": 0}
    r = np.array([t["R_net"] for t in ts]); rng = np.random.default_rng(seed)
    boots = rng.choice(r, size=(10000, len(r)), replace=True).mean(axis=1)
    ex = pd.Series([t["exit"] for t in ts]).value_counts().to_dict()
    eq = np.cumsum(r); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    return {"n": len(r), "mean_net_R": float(r.mean()), "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "total_net_R": float(r.sum()), "win_rate": float((r > 0).mean()), "exits": ex,
            "mean_gross_R": float(np.mean([t["R_gross"] for t in ts])), "risk_med": float(np.median([t["risk"] for t in ts])),
            "max_drawdown_R": dd}


def verdict(s):
    if s["n"] < 30:
        return "INSUFFICIENT"
    return "PASS" if s["mean_net_R"] > 0 and s["ci95"][0] > 0 else "FAIL"


oos_df = h4_frame(ROOT / "data/mt5/XAUUSD_M15_2026-04-20_to_2026-10-06.csv")
ins_df = h4_frame(ROOT / "data/mt5/XAUUSD_M15.csv")
o_all, o_one, o_open = run(oos_df, start_after=CUTOFF)
i_all, i_one, i_open = run(ins_df)
out = {"prereg": "PREREG_h4_lowerwick_3R.md", "cutoff_utc": str(CUTOFF),
       "oos": {"one_position": summary(o_one), "all_signals": summary(o_all), "still_open": len(o_open), "trades": o_one},
       "insample": {"one_position": summary(i_one), "all_signals": summary(i_all), "still_open": len(i_open)}}
out["oos"]["verdict"] = verdict(out["oos"]["one_position"])
out["insample"]["verdict_if_it_were_the_test"] = verdict(out["insample"]["one_position"])
for k in ("oos", "insample"):
    print(k, "one-position", json.dumps(out[k]["one_position"]), flush=True)
    print(k, "all-signals ", json.dumps(out[k]["all_signals"]), flush=True)
print("OOS VERDICT:", out["oos"]["verdict"], "| still open at end:", len(o_open))
for t in o_one:
    print("  ", t["t"], f"entry {t['entry']:.2f} stop {t['stop']:.2f} risk {t['risk']:.2f} -> {t['exit']} after {t['bars']} bars, net {t['R_net']:+.2f}R")
(OUT / "h4_lowerwick_3R.json").write_text(json.dumps(out, default=str), encoding="utf-8")
