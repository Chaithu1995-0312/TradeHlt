"""Bar-by-bar H4 walk: for every H4 bar, enter at its close; stop just beyond the bar
(long: its low, short: its high). Walk forward one H4 bar at a time until the stop is touched
(or MAX_BARS). Record the best price reached BEFORE the stop: in $, in multiples of the stop
distance (R), and how many bars after entry it printed. The bar that touches the stop does not
count toward the best price (OHLC cannot say whether its high came before its low).
No random bars: every bar is a row; pattern groups are subsets of the same rows.

Exploratory. Result: 1 of 13 card-side pairs outside its 95% range vs same-stop bars (pin_lower long), about chance level.
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

MAX_BARS = 30          # 30 H4 bars ~ one trading week
COST = 0.26            # $/oz round trip, same figure the MT5 page used

path = ROOT / "data/mt5/XAUUSD_M15.csv"
corp = corpus_load(path, sequence_check=False)
m15 = corp.frame(parse_dates=["timestamp"])
print("corpus", path, "rows", len(m15), m15.timestamp.iloc[0], "->", m15.timestamp.iloc[-1], flush=True)
cal = corp.calendar
print("calendar", cal, flush=True)
candles = [Candle(timestamp=r.timestamp.to_pydatetime(), open=float(r.open), high=float(r.high), low=float(r.low),
                  close=float(r.close), volume=float(r.volume), index=i) for i, r in enumerate(m15.itertuples(index=False))]
h4 = resample(candles, "H4", calendar=cal)
df = pd.DataFrame({"t": [c.timestamp for c in h4], "o": [c.open for c in h4], "h": [c.high for c in h4],
                   "l": [c.low for c in h4], "c": [c.close for c in h4]})
print("H4 bars", len(df), df.t.iloc[0], "->", df.t.iloc[-1], flush=True)

cfg = get_prod_section("feature_pipeline")
p = CP.CandlePatternParams.from_cfg(cfg["candle_patterns"])
period = int(cfg["atr_period"])
o, h, l, c = (df[k].to_numpy(float) for k in ("o", "h", "l", "c"))
prev_c = np.r_[np.nan, c[:-1]]
tr = np.nanmax(np.vstack([h - l, np.abs(h - prev_c), np.abs(l - prev_c)]), axis=0)
atr = pd.Series(tr).rolling(period).mean().to_numpy()          # price-unit ATR (FM-074 basis), H4
contig = CP.contiguous_mask(df.t.to_numpy())
pat = CP.compute_all(o, h, l, c, atr, contig, p)
FLAGS = ["hammer", "pin_lower", "engulfing_bull", "dragonfly_doji", "morning_star",
         "shooting_star", "pin_upper", "engulfing_bear", "gravestone_doji", "doji_material", "inside_bar"]
CARD = {"hammer": "long", "pin_lower": "long", "engulfing_bull": "long", "dragonfly_doji": "long", "morning_star": "long",
        "shooting_star": "short", "pin_upper": "short", "engulfing_bear": "short", "gravestone_doji": "short"}
n = len(df)


def walk(i, side):
    e = c[i]
    stop = l[i] if side == "long" else h[i]
    risk = (e - stop) if side == "long" else (stop - e)
    best, best_k, stopped, stop_k = e, 0, False, None
    for k in range(1, MAX_BARS + 1):
        j = i + k
        if j >= n:
            return None                      # not enough future bars: drop, do not guess
        if (l[j] <= stop) if side == "long" else (h[j] >= stop):
            stopped, stop_k = True, k
            break
        px = h[j] if side == "long" else l[j]
        if (px > best) if side == "long" else (px < best):
            best, best_k = px, k
    gain = (best - e) if side == "long" else (e - best)
    return {"risk": risk, "gain": gain, "R": gain / risk if risk > 0 else np.nan, "peak_k": best_k,
            "stopped": stopped, "stop_k": stop_k}


rows = {"long": [], "short": []}
for side in rows:
    for i in range(n):
        if np.isnan(atr[i]):
            rows[side].append(None); continue
        rows[side].append(walk(i, side))


def summarize(idx, side):
    rs = [rows[side][i] for i in idx if rows[side][i] is not None]
    if not rs:
        return None
    risk = np.array([r["risk"] for r in rs]); gain = np.array([r["gain"] for r in rs])
    R = np.array([r["R"] for r in rs]); peak = np.array([r["peak_k"] for r in rs])
    stopped = np.array([r["stopped"] for r in rs]); stop_k = np.array([r["stop_k"] or 0 for r in rs])
    okR = R[~np.isnan(R)]
    need = (risk + COST)                     # reach 1R AND cover cost
    return {"n": len(rs), "zero_risk": int((risk <= 0).sum()),
            "risk_med": float(np.median(risk)), "gain_med": float(np.median(gain)), "gain_mean": float(gain.mean()),
            "R_med": float(np.median(okR)), "R_p75": float(np.percentile(okR, 75)),
            "hit_1R": float((okR >= 1).mean()), "hit_2R": float((okR >= 2).mean()), "hit_3R": float((okR >= 3).mean()),
            "hit_1R_net": float((gain >= need).mean()),
            "no_progress": float((gain <= 0).mean()),
            "peak_bars_med": float(np.median(peak[gain > 0])) if (gain > 0).any() else None,
            "stopped": float(stopped.mean()),
            "stop_bars_med": float(np.median(stop_k[stopped])) if stopped.any() else None}


valid_idx = [i for i in range(n) if not np.isnan(atr[i])]
out = {"corpus": {"path": str(path), "m15_rows": len(m15), "h4_bars": n, "first": str(df.t.iloc[0]), "last": str(df.t.iloc[-1]),
                  "calendar": str(cal)},
       "rules": {"entry": "close of the bar", "stop_long": "bar low", "stop_short": "bar high", "max_bars": MAX_BARS,
                 "cost": COST, "atr": f"SMA{period} true range on H4 (size gate only)"},
       "all": {s: summarize(valid_idx, s) for s in ("long", "short")}, "patterns": {}}
for f in FLAGS:
    idx = [i for i in valid_idx if pat[f][i] > 0.5]
    out["patterns"][f] = {"card_side": CARD.get(f, "both"), "count": len(idx),
                          "long": summarize(idx, "long"), "short": summarize(idx, "short")}


def show(name, s, side):
    if s is None:
        print(f"{name:16s} {side:5s} none"); return
    print(f"{name:16s} {side:5s} n={s['n']:5d} risk${s['risk_med']:6.2f} gain${s['gain_med']:6.2f} R_med={s['R_med']:5.2f} "
          f">=1R {s['hit_1R']:.2f} >=2R {s['hit_2R']:.2f} >=3R {s['hit_3R']:.2f} 1R+cost {s['hit_1R_net']:.2f} "
          f"none {s['no_progress']:.2f} peak@{s['peak_bars_med']} stopped {s['stopped']:.2f} stop@{s['stop_bars_med']}", flush=True)


for s in ("long", "short"):
    show("ALL BARS", out["all"][s], s)
for f, v in out["patterns"].items():
    for s in ("long", "short"):
        show(f + ("*" if v["card_side"] in (s, "both") else ""), v[s], s)
(OUT / "h4_walk.json").write_text(json.dumps(out), encoding="utf-8")


# ---- same-stop-size comparison (no random bars: every bar of the same stop size) ----
def wilson(k, m, z=1.96):
    if m == 0:
        return (None, None)
    ph = k / m; d = 1 + z * z / m; ctr = (ph + z * z / (2 * m)) / d; hw = z * np.sqrt(ph * (1 - ph) / m + z * z / (4 * m * m)) / d
    return (ctr - hw, ctr + hw)


def ambiguous(i, side, r):
    """Stop bar whose own extreme also reached +1R: order inside the bar unknown."""
    if r is None or not r["stopped"] or r["risk"] <= 0:
        return False
    j = i + r["stop_k"]; e = c[i]
    return (h[j] - e >= r["risk"]) if side == "long" else (e - l[j] >= r["risk"])


comp = {}
for side in ("long", "short"):
    ix = [i for i in valid_idx if rows[side][i] is not None and rows[side][i]["risk"] > 0]
    ratio = np.array([rows[side][i]["risk"] / atr[i] for i in ix])
    hit = np.array([rows[side][i]["R"] >= 1 for i in ix])
    edges = np.quantile(ratio, np.linspace(0, 1, 11)); edges[0] -= 1e-9; edges[-1] += 1e-9
    b = np.clip(np.digitize(ratio, edges) - 1, 0, 9)
    rate = np.array([hit[b == k].mean() for k in range(10)])
    pos = {i: k for k, i in enumerate(ix)}
    comp[side] = {"bucket_edges_atr": [float(x) for x in edges], "bucket_hit_1R": [float(x) for x in rate],
                  "ambiguous_all": float(np.mean([ambiguous(i, side, rows[side][i]) for i in ix]))}
    print(side, "hit>=1R by stop-size decile (stop/ATR):", [f"{edges[k]:.2f}-{edges[k+1]:.2f}:{rate[k]:.2f}" for k in range(10)])
    print(side, "ambiguous stop-bar share (all bars):", round(comp[side]["ambiguous_all"], 3))
    for f in FLAGS:
        sel = [pos[i] for i in valid_idx if pat[f][i] > 0.5 and i in pos]
        if not sel:
            continue
        obs = hit[sel].mean(); exp = rate[b[sel]].mean(); lo95, hi95 = wilson(int(hit[sel].sum()), len(sel))
        amb = np.mean([ambiguous(ix[s], side, rows[side][ix[s]]) for s in sel])
        out["patterns"][f][side + "_vs_same_stop"] = {"n": len(sel), "observed": float(obs), "expected_same_stop": float(exp),
                                                     "diff": float(obs - exp), "ci95": [lo95, hi95], "ambiguous": float(amb),
                                                     "stop_atr_med": float(np.median(ratio[sel]))}
        card = CARD.get(f, "both") in (side, "both")
        print(f"  {f:16s}{'*' if card else ' '} n={len(sel):4d} stop/ATR med {np.median(ratio[sel]):.2f}  observed {obs:.2f} "
              f"[{lo95:.2f}-{hi95:.2f}]  same-stop all bars {exp:.2f}  diff {obs-exp:+.2f}  ambiguous {amb:.2f}")
out["same_stop"] = comp
(OUT / "h4_walk.json").write_text(json.dumps(out), encoding="utf-8")
