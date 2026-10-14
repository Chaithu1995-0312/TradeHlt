"""# Pre-registration: decode all features into an H1 direction algorithm (written 2026-10-09, before any model is trained)

**Question.** Do the 67 usable canonical features, taken together, carry information about the next-4-hour
direction of gold that survives walk-forward testing, and if so can a short readable rule exploit it after cost?

**Data.** `data/mt5/XAUUSD_M15.csv` ONLY (2-year file, UTC via corpus loader, 47,197 bars after warm-up).
The 22 May - 6 Oct 2026 months are NOT used (already spent by two earlier pre-registered tests).
Features come from `FeaturePipeline.run()` (current working-tree schema v9.0, 79 columns).

**Rows.** One row per H1 bar (repo `research.resample` H1, fx_metals calendar). Features = the value on the LAST
M15 bar of that hour (so everything is known at the H1 close). Skip an hour if its 4 M15 children are not all present.

**Excluded as price-scale / level columns (12):** open, high, low, close, volume, ema_fast, ema_slow, macd_line,
macd_signal, macd_hist_raw, body_size, candle_range. Remaining 67 are all used; none is selected by looking at results.

**Label.** up = H1 close at t+4 bars > close at t; down = lower; ties dropped. Dropped if the 4 following H1 bars are
not exactly consecutive hours (weekend/holiday gaps).

**Walk-forward.** Expanding window, calendar-month test blocks. First test block = first month with >= 6 months of
earlier data. Training rows exclude the last 4 H1 bars before each test block (label purge). Nothing is tuned
on a test block; all settings below are fixed here.

**Models (fixed, no tuning).**
- Ceiling: `HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=100,
  l2_regularization=1.0, random_state=7)` on all 67 features.
- Readable: `DecisionTreeClassifier(max_depth=3, min_samples_leaf=200, random_state=7)` on all 67 features.

**Metrics.**
1. Pooled out-of-fold AUC of the boosted model; 95% interval by block bootstrap over calendar weeks (2,000 draws, seed 7).
   Also per-block AUC and the share of blocks above 0.5.
2. Trading readout of the TREE (the readable algorithm): long if P(up) > 0.55, short if P(up) < 0.45, else flat;
   hold 4 H1 bars; one position at a time; cost $0.26/oz round trip. Net $/oz per trade with a 95% bootstrap
   interval over trades. Same readout for the boosted model, descriptive only.
3. Base rate of up labels and the "always long" net $/oz, for context.

**Verdict rule.** "ALGORITHM FOUND (candidate)" only if BOTH: (a) boosted pooled AUC interval lower bound > 0.50; and
(b) tree trades n >= 100, mean net $/oz > 0, and its 95% interval lower bound > 0.
Otherwise "NOT FOUND". Sub-label: (a) fails -> "no measurable information at the ceiling"; (a) passes but (b) fails ->
"information, not tradable by this rule".
If FOUND, the rule is only a CANDIDATE: it must then be registered in writing and tested once on data after 2026-10-06,
which does not exist yet. No claim and no authority before that.

**Descriptive extras (not part of the verdict).** Correlation clusters of the 67 features (|Spearman| > 0.9);
permutation importance of the boosted model on the pooled test blocks, shown only if (a) passes; sensitivity AUC for
horizons 1 and 12 H1 bars. No re-run with other features, depth, horizon, thresholds or models on this data.

Result: NOT FOUND. Boosted out-of-fold AUC 0.4957, 95% CI [0.480, 0.511].
Rule frozen and result logged in assistant_project.md SESSION LOG, 2026-10-09.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.tree import DecisionTreeClassifier, export_text

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/research/xau_1009"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))
from data_ingestion.corpus_store import load as corpus_load  # noqa: E402
from research.resample import bucket_floor  # noqa: E402  (the H1 bucket authority)
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features import feature_schema as FS  # noqa: E402

N, COST = 4, 0.26
EXCLUDE = ["open", "high", "low", "close", "volume", "ema_fast", "ema_slow", "macd_line", "macd_signal",
           "macd_hist_raw", "body_size", "candle_range"]
FEATS = [f for f in FS.CANONICAL_FEATURES if f not in EXCLUDE]
print("features used", len(FEATS), flush=True)

path = ROOT / "data/mt5/XAUUSD_M15.csv"
corp = corpus_load(path, sequence_check=False)
raw = corp.frame(parse_dates=["timestamp"])
print("corpus", path, "rows", len(raw), raw.timestamp.iloc[0], "->", raw.timestamp.iloc[-1], flush=True)
m15, _ = FeaturePipeline(raw.copy()).run()
m15 = m15.reset_index(drop=True)
missing = [f for f in FEATS if f not in m15.columns]
print("missing columns:", missing, "| M15 bars", len(m15), flush=True)
# CH-timeframe-ssot-v1: H1 bucket from the repo authority on the corpus market calendar (identical to a UTC
# hour floor on this fx_metals corpus: verified equal on all 47,275 rows), not a hand-rolled floor.
m15["hour"] = pd.to_datetime([corp.calendar.to_utc(bucket_floor(ts, "H1", corp.calendar))
                              for ts in m15["timestamp"].dt.to_pydatetime()])
g = m15.groupby("hour", sort=True)
cnt = g.size()
last = g.tail(1).set_index("hour")                           # last M15 bar of each hour
agg = pd.DataFrame({"close": g["close"].last()})
H = last[FEATS].copy(); H["close"] = agg["close"]; H["n15"] = cnt
H = H[H["n15"] == 4].drop(columns="n15").sort_index()
H = H.reset_index().rename(columns={"hour": "t"})
H["ok_next"] = (H["t"].shift(-N) - H["t"]) == pd.Timedelta(hours=N)
H["future"] = H["close"].shift(-N)


def label(horizon):
    ok = (H["t"].shift(-horizon) - H["t"]) == pd.Timedelta(hours=horizon)
    fut = H["close"].shift(-horizon)
    y = np.where(ok & (fut > H["close"]), 1.0, np.where(ok & (fut < H["close"]), 0.0, np.nan))
    return y


H["y"] = label(N)
D = H[H["y"].notna()].reset_index(drop=True)
print("H1 rows with a label", len(D), "up share", round(float(D.y.mean()), 4), D.t.iloc[0], "->", D.t.iloc[-1], flush=True)
X = D[FEATS].to_numpy(float); y = D["y"].to_numpy(int); t = D["t"]
month = t.dt.to_period("M")
months = sorted(month.unique())
first_test = months[6]
test_months = [m for m in months if m >= first_test]
print("test blocks", len(test_months), first_test, "->", test_months[-1], flush=True)


def wf(make, y_all, horizon=N, pos=None):
    pred = np.full(len(D), np.nan)
    per_block = []
    for mth in test_months:
        te = np.where(month == mth)[0]
        if len(te) == 0:
            continue
        tr = np.where(t < t.iloc[te[0]])[0]
        tr = tr[: max(0, len(tr) - horizon)] if len(tr) else tr           # purge last `horizon` rows
        if len(tr) < 500:
            continue
        mdl = make(); mdl.fit(X[tr], y_all[tr])
        p = mdl.predict_proba(X[te])[:, 1]; pred[te] = p
        if len(set(y_all[te])) == 2:
            per_block.append((str(mth), float(roc_auc_score(y_all[te], p)), len(te)))
    return pred, per_block


def block_boot_auc(pred, yy, seed=7, draws=2000):
    ok = ~np.isnan(pred)
    wk = t[ok].dt.to_period("W").astype(str).to_numpy(); p, yv = pred[ok], yy[ok]
    weeks = np.unique(wk); idx = {w: np.where(wk == w)[0] for w in weeks}
    rng = np.random.default_rng(seed); vals = []
    for _ in range(draws):
        pick = rng.choice(weeks, size=len(weeks), replace=True)
        ii = np.concatenate([idx[w] for w in pick])
        if len(set(yv[ii])) == 2:
            vals.append(roc_auc_score(yv[ii], p[ii]))
    return float(roc_auc_score(yv, p)), [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))], int(ok.sum())


def trade_readout(pred, hi=0.55, lo=0.45, seed=7):
    close = D["close"].to_numpy(float); fut = D["future"].to_numpy(float)
    trades, busy = [], -1
    for i in range(len(D)):
        if i <= busy or np.isnan(pred[i]):
            continue
        side = 1 if pred[i] > hi else (-1 if pred[i] < lo else 0)
        if side == 0:
            continue
        net = side * (fut[i] - close[i]) - COST
        trades.append((i, side, net)); busy = i + N - 1
    if not trades:
        return {"n": 0}
    r = np.array([x[2] for x in trades]); rng = np.random.default_rng(seed)
    boots = rng.choice(r, size=(10000, len(r)), replace=True).mean(axis=1)
    return {"n": len(r), "mean_net_usd_oz": float(r.mean()), "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "win_rate": float((r > 0).mean()), "long_share": float(np.mean([x[1] > 0 for x in trades])), "total_net_usd_oz": float(r.sum())}


mk_boost = lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=100,
                                                  l2_regularization=1.0, random_state=7)
mk_tree = lambda: DecisionTreeClassifier(max_depth=3, min_samples_leaf=200, random_state=7)
pb, blocks_b = wf(mk_boost, y); pt, blocks_t = wf(mk_tree, y)
auc_b, ci_b, n_oof = block_boot_auc(pb, y); auc_t, ci_t, _ = block_boot_auc(pt, y)
print(f"BOOSTED pooled OOF AUC {auc_b:.4f} CI {ci_b} n={n_oof} | blocks>0.5: {sum(b[1] > 0.5 for b in blocks_b)}/{len(blocks_b)}", flush=True)
print(f"TREE    pooled OOF AUC {auc_t:.4f} CI {ci_t}", flush=True)
tr_tree = trade_readout(pt); tr_boost = trade_readout(pb)
print("tree trades ", json.dumps(tr_tree)); print("boost trades", json.dumps(tr_boost), flush=True)
close = D["close"].to_numpy(float); fut = D["future"].to_numpy(float)
inwin = ~np.isnan(pb)
always_long = float(np.mean(fut[inwin] - close[inwin]) - COST)
print("up share in test window", round(float(y[inwin].mean()), 4), "| always-long mean net $/oz (overlapping bars)", round(always_long, 3), flush=True)

a_pass = ci_b[0] > 0.5
b_pass = tr_tree["n"] >= 100 and tr_tree["mean_net_usd_oz"] > 0 and tr_tree["ci95"][0] > 0
verdict = "ALGORITHM FOUND (candidate)" if (a_pass and b_pass) else (
    "NOT FOUND: information, not tradable by this rule" if a_pass else "NOT FOUND: no measurable information at the ceiling")
print("VERDICT:", verdict, "| (a)", a_pass, "(b)", b_pass, flush=True)

# descriptive extras
sens = {}
for hz in (1, 12):
    yz = label(hz); ok = ~np.isnan(yz[: len(H)])
    # recompute on the rows of D that have this label (same walk-forward settings)
    Hz = H.copy(); Hz["y"] = yz; Dz = Hz[Hz["y"].notna()].reset_index(drop=True)
    Xz = Dz[FEATS].to_numpy(float); yzv = Dz["y"].to_numpy(int); tz = Dz["t"]; mz = tz.dt.to_period("M")
    pz = np.full(len(Dz), np.nan)
    for mth in test_months:
        te = np.where(mz == mth)[0]
        if len(te) == 0:
            continue
        tr = np.where(tz < tz.iloc[te[0]])[0]; tr = tr[: max(0, len(tr) - hz)]
        if len(tr) < 500:
            continue
        mdl = mk_boost(); mdl.fit(Xz[tr], yzv[tr]); pz[te] = mdl.predict_proba(Xz[te])[:, 1]
    okz = ~np.isnan(pz)
    sens[hz] = float(roc_auc_score(yzv[okz], pz[okz]))
print("sensitivity AUC (boosted, descriptive):", sens, flush=True)

corr = pd.DataFrame(X, columns=FEATS).corr(method="spearman").abs()
seen, clusters = set(), []
for f in FEATS:
    if f in seen:
        continue
    grp = [g2 for g2 in FEATS if corr.loc[f, g2] > 0.9]
    if len(grp) > 1:
        clusters.append(grp); seen.update(grp)
print("correlation clusters |rho|>0.9:", clusters, flush=True)

imp = None
if a_pass:
    ok = ~np.isnan(pb)
    final = mk_boost().fit(X[ok][: int(ok.sum() * 0.7)], y[ok][: int(ok.sum() * 0.7)])
    pi = permutation_importance(final, X[ok][int(ok.sum() * 0.7):], y[ok][int(ok.sum() * 0.7):], scoring="roc_auc", n_repeats=10, random_state=7)
    imp = sorted(zip(FEATS, pi.importances_mean), key=lambda z: -z[1])[:15]
    print("top permutation importance:", [(f, round(float(v), 4)) for f, v in imp])
tree_text = export_text(mk_tree().fit(X[: int(len(X) * 0.5)], y[: int(len(X) * 0.5)]), feature_names=FEATS)
print("(illustrative tree on first half only, NOT the verdict model)\n" + tree_text)
(OUT / "feature_decode_h1.json").write_text(json.dumps({
    "n_features": len(FEATS), "rows": len(D), "up_share": float(D.y.mean()), "test_blocks": len(blocks_b),
    "boost": {"auc": auc_b, "ci95": ci_b, "n_oof": n_oof, "blocks": blocks_b}, "tree": {"auc": auc_t, "ci95": ci_t},
    "tree_trades": tr_tree, "boost_trades": tr_boost, "always_long_net": always_long, "verdict": verdict, "a_pass": bool(a_pass), "b_pass": bool(b_pass),
    "sensitivity_auc": sens, "clusters": clusters, "importance": imp}, default=str), encoding="utf-8")
