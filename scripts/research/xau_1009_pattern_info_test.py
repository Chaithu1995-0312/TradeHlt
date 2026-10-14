"""Does selecting a pattern add information beyond a baseline? XAUUSD M15, same trade rule as pattern_pay_test.py.
Two-sided tests against two baselines:
  B0 unconditional: random bars, same n.
  B1 matched: random bars drawn from the SAME strata as the pattern bars
      (UTC hour x bar range/ATR quintile x bar colour) -- so a pattern only counts if it says more than
      "a big green bar at 14:00" already says.
Metrics: delta net R and delta win rate vs baseline. Benjamini-Hochberg across all tests.
Also a block check: pattern bars within 16 bars of each other overlap; effective n reported.

Exploratory. Result: 0 of 22 tests survive Benjamini-Hochberg vs the matched baseline; hammer long worse than matched (p 0.045).
Rule frozen and result logged in assistant_project.md SESSION LOG, 2026-10-09.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/research/xau_1009"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools/xau_chart"))
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from data_ingestion.corpus_store import load as corpus_load  # noqa: E402
class ZS:  # the four constants of tools/xau_chart/zone_study.py (untracked), same values
    STOP, TGT, H, COST = 1.0, 2.0, 16, 0.26

path = ROOT / "data/mt5/XAUUSD_M15.csv"
raw = corpus_load(path, sequence_check=False).frame(parse_dates=["timestamp"])
print("corpus", path, "rows", len(raw), flush=True)
df, _ = FeaturePipeline(raw.copy()).run()
df = df.reset_index(drop=True)
print("bars", len(df), df.timestamp.iloc[0], "->", df.timestamp.iloc[-1], flush=True)

o = df["open"].to_numpy(float); c = df["close"].to_numpy(float)
hi = df["high"].to_numpy(float); lo = df["low"].to_numpy(float)
atr = df["atr"].to_numpy(float) * c
n = len(c)
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
WIN = {"long": (RL >= 2.0).astype(float), "short": (RS >= 2.0).astype(float)}
valid = ~np.isnan(RL) & ~np.isnan(RS)

hour = df["timestamp"].dt.hour.to_numpy()
rr = (hi - lo) / np.where(atr > 0, atr, np.nan)
q = np.nanquantile(rr[valid], [0.2, 0.4, 0.6, 0.8])
rbin = np.digitize(rr, q)
colour = (c >= o).astype(int)
stratum = hour * 100 + rbin * 10 + colour
pools = {}
for s in np.unique(stratum[valid]):
    pools[s] = np.where(valid & (stratum == s))[0]

rng = np.random.default_rng(20261009)
DRAWS = 2000
FLAGS = ["pin_lower", "pin_upper", "hammer", "shooting_star", "doji_material", "dragonfly_doji", "gravestone_doji",
         "engulfing_bull", "engulfing_bear", "inside_bar", "morning_star"]
INTENT = {"hammer": "long", "pin_lower": "long", "engulfing_bull": "long", "dragonfly_doji": "long", "morning_star": "long",
          "shooting_star": "short", "pin_upper": "short", "engulfing_bear": "short", "gravestone_doji": "short"}


def two_sided(obs, null):
    null = np.asarray(null); mu = null.mean()
    return float((np.sum(np.abs(null - mu) >= abs(obs - mu)) + 1) / (len(null) + 1))


def eff_n(idx):
    """Clusters: pattern bars closer than the 16-bar horizon share outcome path; count clusters."""
    if len(idx) == 0:
        return 0
    return int(1 + np.sum(np.diff(idx) > ZS.H))


rows = []
for col in FLAGS:
    flag = (np.nan_to_num(df[col].to_numpy(float)) > 0.5) & valid
    idx = np.where(flag)[0]
    k = len(idx)
    # matched draws: for each pattern bar, a random bar from its stratum
    strata_of = stratum[idx]
    matched = np.empty((DRAWS, k), dtype=int)
    for s in np.unique(strata_of):
        pos = np.where(strata_of == s)[0]
        matched[:, pos] = rng.choice(pools[s], size=(DRAWS, len(pos)), replace=True)
    uncond = rng.choice(np.where(valid)[0], size=(DRAWS, k), replace=True)
    for side in ("long", "short"):
        net, win = NET[side], WIN[side]
        obsR, obsW = float(net[idx].mean()), float(win[idx].mean())
        nb0R = net[uncond].mean(axis=1); nb1R = net[matched].mean(axis=1); nb1W = win[matched].mean(axis=1)
        rows.append({"pattern": col, "side": side, "card_side": INTENT.get(col) == side or col not in INTENT,
                     "n": k, "eff_n": eff_n(idx),
                     "R": obsR, "win": obsW,
                     "R_uncond": float(nb0R.mean()), "p_uncond": two_sided(obsR, nb0R),
                     "R_matched": float(nb1R.mean()), "dR_matched": obsR - float(nb1R.mean()), "p_matched": two_sided(obsR, nb1R),
                     "win_matched": float(nb1W.mean()), "dWin_matched": obsW - float(nb1W.mean()), "p_win_matched": two_sided(obsW, nb1W)})

# Benjamini-Hochberg on matched-R p values, all rows and card-side only
def bh(ps, alpha=0.05):
    ps = np.asarray(ps); m = len(ps); order = np.argsort(ps)
    thr = alpha * (np.arange(1, m + 1)) / m
    passed = ps[order] <= thr
    kmax = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    out = np.zeros(m, bool); out[order[:kmax]] = True
    return out


for key in ("p_matched", "p_uncond", "p_win_matched"):
    sig = bh([r[key] for r in rows])
    for r, s in zip(rows, sig):
        r["bh_" + key] = bool(s)

for r in rows:
    print(f"{r['pattern']:15s} {r['side']:5s} {'*' if r['card_side'] else ' '} n={r['n']:5d} eff={r['eff_n']:5d} "
          f"R={r['R']:+.3f} | uncond {r['R_uncond']:+.3f} p={r['p_uncond']:.3f} | matched {r['R_matched']:+.3f} dR={r['dR_matched']:+.3f} p={r['p_matched']:.3f} "
          f"| win {r['win']:.3f} vs {r['win_matched']:.3f} p={r['p_win_matched']:.3f} | BH R:{int(r['bh_p_matched'])} W:{int(r['bh_p_win_matched'])}", flush=True)
print("strata", len(pools), "range quintile cuts (range/ATR)", [round(x, 3) for x in q])
(OUT / "pattern_info.json").write_text(json.dumps({"corpus": {"path": str(path), "rows": len(raw), "bars": n},
    "params": {"stop_atr": ZS.STOP, "target_atr": ZS.TGT, "horizon": ZS.H, "cost": ZS.COST, "draws": DRAWS,
               "strata": "UTC hour x range/ATR quintile x bar colour", "range_cuts": [float(x) for x in q]}, "rows": rows}), encoding="utf-8")
