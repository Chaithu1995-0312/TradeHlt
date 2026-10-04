"""Forward test of the zone-start features on the 2-year XAUUSD corpus.

AUC said which features look different at the first bar of a profitable zone. This asks the trading
question instead: if you enter on EVERY bar whose feature sits in a given decile, how often does the
same 2xATR-target / 1xATR-stop / 16-bar trade win, and what is the average R after cost?
Break-even at 2:1 with no cost is a 33.3% win rate. Halves are reported to show stability.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(HERE))
from features.feature_pipeline import FeaturePipeline  # noqa: E402
import zone_study as ZS  # noqa: E402

FEATS = ["momentum_score", "disp_strength", "volatility_ratio", "body_ratio", "body_size", "candle_range",
         "break_of_structure", "rsi_14", "macd_hist_z", "volume_ratio", "lower_low", "higher_high"]

path = ROOT / "data/mt5/XAUUSD_M15.csv"
from data_ingestion.corpus_store import load as _corpus_load  # CH-corpus-ssot: the corpus SSOT
raw = _corpus_load(path).frame(parse_dates=["timestamp"])
print("corpus", path, "rows", len(raw), flush=True)
cache = HERE / "zone_full_enriched.parquet"
if cache.exists():
    df = pd.read_parquet(cache)
else:
    enriched, _ = FeaturePipeline(raw.copy()).run()
    df = enriched[["timestamp", "open", "high", "low", "close", "atr"] + FEATS].reset_index(drop=True)
    try:
        df.to_parquet(cache)
    except Exception as e:  # parquet engine optional
        print("cache skipped:", e)
c = df["close"].to_numpy(float)
atr_abs = df["atr"].to_numpy(float) * c
hi_, lo_ = df["high"].to_numpy(float), df["low"].to_numpy(float)
lw, sw = ZS.win_labels(df["open"].to_numpy(float), hi_, lo_, c, atr_abs)
cost_r = ZS.COST / np.where(atr_abs > 0, atr_abs, np.nan)        # cost in R (stop = 1 ATR)


def trade_r(i, sgn):
    """Gross R of one trade: +TGT on target, -STOP on stop (same bar = stop), else the close of the
    last bar in the horizon marked to market (a timeout is NOT a full loss)."""
    a, e = atr_abs[i], c[i]
    for j in range(i + 1, i + ZS.H + 1):
        if (lo_[j] <= e - ZS.STOP * a) if sgn > 0 else (hi_[j] >= e + ZS.STOP * a):
            return -ZS.STOP / ZS.STOP
        if (hi_[j] >= e + ZS.TGT * a) if sgn > 0 else (lo_[j] <= e - ZS.TGT * a):
            return ZS.TGT / ZS.STOP
    return sgn * (c[i + ZS.H] - e) / (ZS.STOP * a)


R_L = np.full(len(c), np.nan); R_S = np.full(len(c), np.nan)
for i in range(len(c)):
    if atr_abs[i] > 0 and i + ZS.H < len(c):
        R_L[i], R_S[i] = trade_r(i, 1), trade_r(i, -1)
RS = {"long": R_L, "short": R_S}
timeouts = {s: float(np.nanmean((RS[s] != 2.0) & (RS[s] != -1.0))) for s in RS}
print("share of trades that time out:", timeouts, flush=True)
n = len(df); half = n // 2
out = {"corpus": {"path": str(path), "rows": len(raw), "bars": n, "first": str(df.timestamp.iloc[0]), "last": str(df.timestamp.iloc[-1])},
       "params": {"stop_atr": ZS.STOP, "target_atr": ZS.TGT, "horizon_bars": ZS.H, "cost": ZS.COST},
       "base": {}, "features": {}}


def stats(mask, win):
    side = "long" if win is lw else "short"
    m = mask & ~np.isnan(win) & ~np.isnan(RS[side])
    if m.sum() == 0:
        return None
    gross = RS[side][m]
    net = gross - cost_r[m]
    return {"n": int(m.sum()), "win": float(win[m].mean()), "R": float(np.nanmean(net)), "R_gross": float(np.nanmean(gross))}


out["timeout_share"] = timeouts
for side, win in (("long", lw), ("short", sw)):
    allm = np.ones(n, bool)
    out["base"][side] = {"all": stats(allm, win), "h1": stats(allm & (np.arange(n) < half), win), "h2": stats(allm & (np.arange(n) >= half), win)}
for f in FEATS:
    v = df[f].to_numpy(float)
    ok = ~np.isnan(v)
    uniq = np.unique(v[ok])
    if len(uniq) <= 12:     # discrete feature: one row per value
        bins = [(float(u), float(u)) for u in uniq]
        masks = [ok & (v == u) for u in uniq]
    else:
        qs = np.nanquantile(v, np.linspace(0, 1, 11))
        bins = [(float(qs[k]), float(qs[k + 1])) for k in range(10)]
        masks = [ok & (v >= qs[k]) & ((v < qs[k + 1]) if k < 9 else (v <= qs[k + 1])) for k in range(10)]
    rows = []
    for (lo, hi), m in zip(bins, masks):
        row = {"lo": lo, "hi": hi}
        for side, win in (("long", lw), ("short", sw)):
            row[side] = {"all": stats(m, win), "h1": stats(m & (np.arange(n) < half), win), "h2": stats(m & (np.arange(n) >= half), win)}
        rows.append(row)
    out["features"][f] = rows
    best = max(rows, key=lambda r: max(r["long"]["all"]["R"] if r["long"]["all"] else -9, r["short"]["all"]["R"] if r["short"]["all"] else -9))
    print(f, "best bin", round(best["lo"], 3), round(best["hi"], 3),
          "long", {k: round(x, 3) for k, x in best["long"]["all"].items()}, "short", {k: round(x, 3) for k, x in best["short"]["all"].items()}, flush=True)
print("base", json.dumps(out["base"]))
(HERE / "zone_edge.json").write_text(json.dumps(out), encoding="utf-8")
