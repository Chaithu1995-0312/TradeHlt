"""# Pre-registration: do the features predict next-4-hour RANGE beyond a volatility baseline? (written 2026-10-09, before any run)

Same data, rows, features (67), walk-forward blocks, purge and boosted settings as PREREG_feature_decode_h1.md.
`data/mt5/XAUUSD_M15.csv` only; 22 May - 6 Oct 2026 stays unused.

**Target.** y = ln( (max high - min low over the next 4 consecutive H1 bars) / ATR_price ), where ATR_price = the
`atr` feature (close-relative) x close at the last M15 bar of the current hour. Rows dropped if the next 4 hours are
not consecutive.

**Models (fixed).** HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=100,
l2_regularization=1.0, random_state=7).
- Full: all 67 features.
- Baseline: only atr, volatility_ratio, volatility_regime, hour_of_day, session (the known drivers of range).

**Metric.** Pooled out-of-fold R^2 of each model; delta = R^2_full - R^2_baseline. 95% interval for delta by
paired block bootstrap over calendar weeks (2,000 draws, seed 7), on squared errors.

**Verdict rule.** "FEATURES ADD INFORMATION ON RANGE" only if the delta interval lower bound > 0. Otherwise
"NO ADDED INFORMATION" (recent volatility and time of day already contain it). Also report R^2 of the baseline against a
constant (is range predictable at all) - descriptive.

**Authority.** Information only (rung 1). No trading rule is derived or tested; consuming a range forecast (stops, size)
is a separate pre-registration. No re-run with other features, depth, horizon or baseline sets.

Result: NO ADDED INFORMATION. Baseline R^2 0.382; all-feature minus baseline -0.0055, 95% CI [-0.011, +0.001].
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
from features import feature_schema as FS  # noqa: E402

N = 4
EXCLUDE = ["open", "high", "low", "close", "volume", "ema_fast", "ema_slow", "macd_line", "macd_signal",
           "macd_hist_raw", "body_size", "candle_range"]
FEATS = [f for f in FS.CANONICAL_FEATURES if f not in EXCLUDE]
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
last = g.tail(1).set_index("hour")
H = last[FEATS].copy()
H["close"] = g["close"].last(); H["hi"] = g["high"].max(); H["lo"] = g["low"].min(); H["n15"] = g.size()
H = H[H["n15"] == 4].drop(columns="n15").sort_index().reset_index().rename(columns={"hour": "t"})
atr_price = H["atr"] * H["close"]
rng_next = pd.concat([H["hi"].shift(-k) for k in range(1, N + 1)], axis=1).max(axis=1) - \
           pd.concat([H["lo"].shift(-k) for k in range(1, N + 1)], axis=1).min(axis=1)
ok = (H["t"].shift(-N) - H["t"]) == pd.Timedelta(hours=N)
H["y"] = np.where(ok & (rng_next > 0) & (atr_price > 0), np.log(rng_next / atr_price), np.nan)
D = H[H["y"].notna()].reset_index(drop=True)
print("rows", len(D), "y mean", round(float(D.y.mean()), 3), "sd", round(float(D.y.std()), 3), flush=True)
t = D["t"]; month = t.dt.to_period("M"); months = sorted(month.unique()); test_months = [m for m in months if m >= months[6]]
y = D["y"].to_numpy(float)
mk = lambda: HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=100,
                                           l2_regularization=1.0, random_state=7)


def wf(cols):
    X = D[cols].to_numpy(float); pred = np.full(len(D), np.nan); const = np.full(len(D), np.nan)
    for mth in test_months:
        te = np.where(month == mth)[0]
        if len(te) == 0:
            continue
        tr = np.where(t < t.iloc[te[0]])[0]; tr = tr[: max(0, len(tr) - N)]
        if len(tr) < 500:
            continue
        m = mk().fit(X[tr], y[tr]); pred[te] = m.predict(X[te]); const[te] = y[tr].mean()
    return pred, const


pf, c0 = wf(FEATS); pb, _ = wf(BASE)
ok_ = ~np.isnan(pf) & ~np.isnan(pb)
yy = y[ok_]; ef = (yy - pf[ok_]) ** 2; eb = (yy - pb[ok_]) ** 2; e0 = (yy - c0[ok_]) ** 2
r2 = lambda e, e_ref: 1 - e.sum() / e_ref.sum()
R2_full, R2_base = r2(ef, e0), r2(eb, e0)
wk = t[ok_].dt.to_period("W").astype(str).to_numpy(); weeks = np.unique(wk); idx = {w: np.where(wk == w)[0] for w in weeks}
rng = np.random.default_rng(7); deltas, base_r2 = [], []
for _ in range(2000):
    ii = np.concatenate([idx[w] for w in rng.choice(weeks, size=len(weeks), replace=True)])
    deltas.append((1 - ef[ii].sum() / e0[ii].sum()) - (1 - eb[ii].sum() / e0[ii].sum()))
    base_r2.append(1 - eb[ii].sum() / e0[ii].sum())
d_ci = [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))]
b_ci = [float(np.percentile(base_r2, 2.5)), float(np.percentile(base_r2, 97.5))]
print(f"n_oof={int(ok_.sum())} blocks={len(test_months)}")
print(f"R2 baseline vs constant = {R2_base:.4f}  CI {b_ci}")
print(f"R2 full     vs constant = {R2_full:.4f}")
print(f"delta R2 (full - baseline) = {R2_full - R2_base:+.4f}  95% CI {d_ci}")
verdict = "FEATURES ADD INFORMATION ON RANGE" if d_ci[0] > 0 else "NO ADDED INFORMATION"
print("VERDICT:", verdict, flush=True)
(OUT / "range_decode_h1.json").write_text(json.dumps({"n_oof": int(ok_.sum()), "R2_base": R2_base, "R2_full": R2_full,
    "delta": R2_full - R2_base, "delta_ci95": d_ci, "base_ci95": b_ci, "verdict": verdict}), encoding="utf-8")
