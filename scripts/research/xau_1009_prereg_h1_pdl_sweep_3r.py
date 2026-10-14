"""# Pre-registration: H1 sweep of prior-day low, closes back above, long, 3R (written 2026-10-09, before any run)

**Level.** PDL = low of the most recently CLOSED D1 parent candle, from the repo's own
`features.parent_candle.ParentCandleBuilder("D1", keep=2, calendar=<corpus calendar>)` (gold market
day, fx_metals, 17:00 New York), fed M15 candles in order. Only parents closed at or before the
signal bar's close count (no lookahead).

**Signal.** An H1 bar (repo `research.resample` H1, same calendar) with
`low < PDL` AND `close > PDL`. No candle-pattern flag is used.

**Trade.** Long. Entry = signal bar close. Stop = signal bar low (risk = entry - low > 0 by construction).
Target = entry + 3 x risk. Walk forward one H1 bar at a time:
- bar low <= stop -> stopped, -1R (a bar that also reaches the target counts as stopped);
- bar high >= target -> +3R;
- neither within 48 H1 bars (two trading days) -> exit at the close of bar 48, marked to market.
Cost $0.26/oz round trip: net R = gross R - 0.26 / risk. No minimum-risk filter.

**Positions.** Primary (verdict): one position at a time; a signal while a trade is open is skipped.
Secondary (reported only): every signal taken.

**Data.**
- Out-of-sample (the verdict): `data/mt5/XAUUSD_M15_2026-04-20_to_2026-10-06.csv`, signals with H1 bar
  start after 2026-05-21 20:45 UTC; earlier bars warm up the D1 builder only.
- In-sample (comparison only): `data/mt5/XAUUSD_M15.csv`.

**Comparator (reported, not the verdict).** Every H1 bar, long, stop at its own low, same 3R rule,
same 48-bar exit, one position at a time, same OOS window.

**Verdict rule.** Out-of-sample trades < 30 -> INSUFFICIENT, no claim. Otherwise PASS only if mean net R > 0
AND the 95% bootstrap interval (10,000 resamples, seed 7) of mean net R lies above 0. Anything else FAIL.
No re-run with a different level, stop, target, horizon or timeframe on these months.

Result: FAIL. Out-of-sample n=67, mean net -0.261R, 95% CI [-0.617, +0.126]; every H1 bar -0.289R.
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
from features.parent_candle import ParentCandleBuilder  # noqa: E402

COST, TGT, MAX_BARS = 0.26, 3.0, 48
CUTOFF = pd.Timestamp("2026-05-21 20:45:00")


def frames(path):
    corp = corpus_load(path, sequence_check=False)
    m = corp.frame(parse_dates=["timestamp"])
    print("corpus", path, "rows", len(m), m.timestamp.iloc[0], "->", m.timestamp.iloc[-1], flush=True)
    cs = [Candle(timestamp=r.timestamp.to_pydatetime(), open=float(r.open), high=float(r.high), low=float(r.low),
                 close=float(r.close), volume=float(r.volume), index=i) for i, r in enumerate(m.itertuples(index=False))]
    cal = corp.calendar
    h1 = resample(cs, "H1", calendar=cal)
    d1 = ParentCandleBuilder("D1", keep=2, calendar=cal)
    pdl = []; j = 0
    for b in h1:                                    # PDL as of the CLOSE of each H1 bar: push every M15 child up to it
        end = pd.Timestamp(b.timestamp) + pd.Timedelta(hours=1)
        while j < len(cs) and pd.Timestamp(cs[j].timestamp) < end:
            d1.push(cs[j]); j += 1
        pc = d1.parent_candle
        pdl.append(pc.low if pc is not None else np.nan)
    df = pd.DataFrame({"t": [pd.Timestamp(b.timestamp) for b in h1], "o": [b.open for b in h1], "h": [b.high for b in h1],
                       "l": [b.low for b in h1], "c": [b.close for b in h1], "pdl": pdl})
    print("  H1 bars", len(df), df.t.iloc[0], "->", df.t.iloc[-1], "| bars with a PDL", int(df.pdl.notna().sum()), flush=True)
    return df


def walk(df, i):
    e, stop = df.c.iloc[i], df.l.iloc[i]; risk = e - stop
    if risk <= 0:
        return None
    tgt = e + TGT * risk; n = len(df)
    for k in range(1, MAX_BARS + 1):
        j = i + k
        if j >= n:
            return "open"
        if df.l.iloc[j] <= stop:
            return {"R_gross": -1.0, "bars": k, "exit": "stop", "risk": risk}
        if df.h.iloc[j] >= tgt:
            return {"R_gross": TGT, "bars": k, "exit": "target", "risk": risk}
    j = i + MAX_BARS
    return {"R_gross": (df.c.iloc[j] - e) / risk, "bars": MAX_BARS, "exit": "time", "risk": risk}


def run(df, start_after, mask_fn):
    trades = []
    for i in range(len(df)):
        if start_after is not None and df.t.iloc[i] <= start_after:
            continue
        if not mask_fn(df, i):
            continue
        r = walk(df, i)
        if r is None or r == "open":
            continue
        r.update({"i": i, "t": str(df.t.iloc[i]), "entry": float(df.c.iloc[i]), "stop": float(df.l.iloc[i]),
                  "R_net": r["R_gross"] - COST / r["risk"], "exit_i": i + r["bars"]})
        trades.append(r)
    one, busy = [], -1
    for t in trades:
        if t["i"] > busy:
            one.append(t); busy = t["exit_i"]
    return trades, one


def sweep(df, i):
    p = df.pdl.iloc[i]
    return (not np.isnan(p)) and df.l.iloc[i] < p < df.c.iloc[i]


def every(df, i):
    return True


def summary(ts):
    if not ts:
        return {"n": 0}
    r = np.array([t["R_net"] for t in ts]); rng = np.random.default_rng(7)
    boots = rng.choice(r, size=(10000, len(r)), replace=True).mean(axis=1)
    return {"n": len(r), "mean_net_R": float(r.mean()), "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "total_net_R": float(r.sum()), "win_rate": float((r > 0).mean()),
            "exits": pd.Series([t["exit"] for t in ts]).value_counts().to_dict(),
            "mean_gross_R": float(np.mean([t["R_gross"] for t in ts])), "risk_med": float(np.median([t["risk"] for t in ts]))}


def verdict(s):
    if s["n"] < 30:
        return "INSUFFICIENT"
    return "PASS" if s["mean_net_R"] > 0 and s["ci95"][0] > 0 else "FAIL"


oos = frames(ROOT / "data/mt5/XAUUSD_M15_2026-04-20_to_2026-10-06.csv")
ins = frames(ROOT / "data/mt5/XAUUSD_M15.csv")
res = {}
for name, df, cut in (("oos", oos, CUTOFF), ("insample", ins, None)):
    sa, so = run(df, cut, sweep); ca, co = run(df, cut, every)
    res[name] = {"sweep_one": summary(so), "sweep_all": summary(sa), "every_bar_one": summary(co),
                 "signals_flagged": int(sum(1 for i in range(len(df)) if (cut is None or df.t.iloc[i] > cut) and sweep(df, i)))}
    if name == "oos":
        res[name]["trades"] = so
res["oos"]["verdict"] = verdict(res["oos"]["sweep_one"])
for k in ("oos", "insample"):
    print(k, "signals flagged", res[k]["signals_flagged"])
    for key in ("sweep_one", "sweep_all", "every_bar_one"):
        print(" ", key, json.dumps(res[k][key]), flush=True)
print("OOS VERDICT:", res["oos"]["verdict"])
for t in res["oos"]["trades"]:
    print("  ", t["t"], f"entry {t['entry']:.2f} stop {t['stop']:.2f} risk {t['risk']:.2f} -> {t['exit']} after {t['bars']} bars, net {t['R_net']:+.2f}R")
(OUT / "h1_pdl_sweep_3R.json").write_text(json.dumps(res, default=str), encoding="utf-8")
