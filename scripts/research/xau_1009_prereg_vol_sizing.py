"""# Pre-registration: does forecast-based volatility sizing improve a simple gold position? (written 2026-10-09, before any run)

**Data.** `data/mt5/XAUUSD_M15.csv` only, same H1 rows, walk-forward months and purge as PREREG_range_decode_h1.md.
The 22 May - 6 Oct 2026 months are not used.

**Periods.** Non-overlapping 4-hour holding periods: test-window H1 rows whose hour is a multiple of 4 and whose next
4 hours are consecutive. P&L per period per oz = close(t+4) - close(t).
(These are 4-hour HOLDING periods cut on the UTC hour (hour % 4 == 0), pre-registered as such. They are NOT H4
candles: the gold market day starts at 17:00 New York, so H4 candle boundaries sit on a different hour grid.)

**Forecast.** Out-of-fold prediction of ln(next-4h range / ATR_price) from the BASELINE model only
(atr, volatility_ratio, volatility_regime, hour_of_day, session; same HistGradientBoostingRegressor settings).
Expected range $ = exp(forecast) x ATR_price.

**Three ways to hold gold long.**
- A, constant: 1 oz every period.
- B, forecast sizing: w = k / expected range $. k is fixed per fold from TRAINING rows only, so that the mean w over the
  training rows is 1 oz.
- C, naive sizing (comparator): w = k / ATR_price, k fixed the same way (no forecast model).
Rebalancing cost: $0.13 per oz changed (half the $0.26 round trip) for B and C; A pays none.

**Metric.** Per-period Sharpe ratio (mean / standard deviation of net P&L) and max drawdown in $/oz.

**Verdict rule.** "SIZING HELPS" only if the paired week-block bootstrap 95% interval (2,000 draws, seed 7) of
Sharpe(B) - Sharpe(A) lies above 0. Otherwise "NO MEASURED BENEFIT". Sharpe(B) - Sharpe(C) is reported as
descriptive (does the forecast beat simple ATR sizing). This is a risk-shape test only; long gold's average return in
2024-26 is drift, not an edge. No re-run with other models, horizons, costs or scaling.

Result: SIZING HELPS. Sharpe per 4h 0.0083 -> 0.0365, difference 95% CI [+0.005, +0.052]; plain 1/ATR sizing 0.0395.
Rule frozen and result logged in assistant_project.md SESSION LOG, 2026-10-09.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/research/xau_1009"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))
from data_ingestion.corpus_store import load as corpus_load  # noqa: E402
from research.resample import bucket_floor  # noqa: E402  (the H1 bucket authority)
from features.feature_pipeline import FeaturePipeline  # noqa: E402

N, HALF_COST = 4, 0.13
BASE = ["atr", "volatility_ratio", "volatility_regime", "hour_of_day", "session"]
path = ROOT / "data/mt5/XAUUSD_M15.csv"
corp = corpus_load(path, sequence_check=False)
raw = corp.frame(parse_dates=["timestamp"])
print("corpus", path, "rows", len(raw), raw.timestamp.iloc[0], "->", raw.timestamp.iloc[-1], flush=True)
m15, _ = FeaturePipeline(raw.copy()).run(); m15 = m15.reset_index(drop=True)
# CH-timeframe-ssot-v1: H1 bucket from the repo authority on the corpus market calendar (identical to a UTC
# hour floor on this fx_metals corpus: verified equal on all 47,275 rows), not a hand-rolled floor.
m15["hour"] = pd.to_datetime([corp.calendar.to_utc(bucket_floor(ts, "H1", corp.calendar))
                              for ts in m15["timestamp"].dt.to_pydatetime()])
g = m15.groupby("hour", sort=True)
H = g.tail(1).set_index("hour")[BASE].copy()
H["close"] = g["close"].last(); H["hi"] = g["high"].max(); H["lo"] = g["low"].min(); H["n15"] = g.size()
H = H[H["n15"] == 4].drop(columns="n15").sort_index().reset_index().rename(columns={"hour": "t"})
H["atr_price"] = H["atr"] * H["close"]
rng_next = pd.concat([H["hi"].shift(-k) for k in range(1, N + 1)], axis=1).max(axis=1) - \
           pd.concat([H["lo"].shift(-k) for k in range(1, N + 1)], axis=1).min(axis=1)
ok = (H["t"].shift(-N) - H["t"]) == pd.Timedelta(hours=N)
H["y"] = np.where(ok & (rng_next > 0) & (H["atr_price"] > 0), np.log(rng_next / H["atr_price"]), np.nan)
H["pnl"] = np.where(ok, H["close"].shift(-N) - H["close"], np.nan)
D = H[H["y"].notna()].reset_index(drop=True)
t = D["t"]; month = t.dt.to_period("M"); months = sorted(month.unique()); test_months = [m for m in months if m >= months[6]]
X = D[BASE].to_numpy(float); y = D["y"].to_numpy(float); ap = D["atr_price"].to_numpy(float)
mk = lambda: HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=100,
                                           l2_regularization=1.0, random_state=7)
wB = np.full(len(D), np.nan); wC = np.full(len(D), np.nan)
for mth in test_months:
    te = np.where(month == mth)[0]
    if len(te) == 0:
        continue
    tr = np.where(t < t.iloc[te[0]])[0]; tr = tr[: max(0, len(tr) - N)]
    if len(tr) < 500:
        continue
    m = mk().fit(X[tr], y[tr])
    exp_tr = np.exp(m.predict(X[tr])) * ap[tr]; exp_te = np.exp(m.predict(X[te])) * ap[te]
    kB = 1.0 / np.mean(1.0 / exp_tr); kC = 1.0 / np.mean(1.0 / ap[tr])          # mean training size = 1 oz
    wB[te] = kB / exp_te; wC[te] = kC / ap[te]
sel = (~np.isnan(wB)) & (t.dt.hour % 4 == 0).to_numpy() & (~np.isnan(D["pnl"].to_numpy()))
P = D[sel].reset_index(drop=True); b = wB[sel]; c = wC[sel]; pnl = P["pnl"].to_numpy(float)
print("periods", len(P), P.t.iloc[0], "->", P.t.iloc[-1], flush=True)


def net(w):
    turn = np.abs(np.diff(np.r_[w[0], w]))      # no cost on the very first period's open, same for all
    return w * pnl - HALF_COST * turn


nA = pnl.copy(); nB = net(b); nC = net(c)
sh = lambda x: x.mean() / x.std(ddof=1)
dd = lambda x: float((np.cumsum(x) - np.maximum.accumulate(np.r_[0, np.cumsum(x)])[1:]).min())
wk = P.t.dt.to_period("W").astype(str).to_numpy(); weeks = np.unique(wk); idx = {w_: np.where(wk == w_)[0] for w_ in weeks}
rng = np.random.default_rng(7); dBA, dBC = [], []
for _ in range(2000):
    ii = np.concatenate([idx[w_] for w_ in rng.choice(weeks, size=len(weeks), replace=True)])
    dBA.append(sh(nB[ii]) - sh(nA[ii])); dBC.append(sh(nB[ii]) - sh(nC[ii]))
ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
res = {"periods": len(P),
       "A": {"sharpe": float(sh(nA)), "mean": float(nA.mean()), "sd": float(nA.std(ddof=1)), "maxdd": dd(nA), "total": float(nA.sum()), "mean_size": 1.0},
       "B": {"sharpe": float(sh(nB)), "mean": float(nB.mean()), "sd": float(nB.std(ddof=1)), "maxdd": dd(nB), "total": float(nB.sum()), "mean_size": float(b.mean()), "cost_total": float((HALF_COST * np.abs(np.diff(np.r_[b[0], b]))).sum())},
       "C": {"sharpe": float(sh(nC)), "mean": float(nC.mean()), "sd": float(nC.std(ddof=1)), "maxdd": dd(nC), "total": float(nC.sum()), "mean_size": float(c.mean()), "cost_total": float((HALF_COST * np.abs(np.diff(np.r_[c[0], c]))).sum())},
       "dSharpe_BA": float(sh(nB) - sh(nA)), "dSharpe_BA_ci": ci(dBA), "dSharpe_BC": float(sh(nB) - sh(nC)), "dSharpe_BC_ci": ci(dBC)}
res["verdict"] = "SIZING HELPS" if res["dSharpe_BA_ci"][0] > 0 else "NO MEASURED BENEFIT"
for k in ("A", "B", "C"):
    print(k, {kk: round(v, 4) for kk, v in res[k].items()})
print("Sharpe B-A", round(res["dSharpe_BA"], 4), res["dSharpe_BA_ci"], "| B-C", round(res["dSharpe_BC"], 4), res["dSharpe_BC_ci"])
print("VERDICT:", res["verdict"])
(OUT / "vol_sizing_h1.json").write_text(json.dumps(res), encoding="utf-8")
