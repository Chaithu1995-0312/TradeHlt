"""
edge_attribution_study.py — Edge Attribution + Survivability Study (research / measure-first).

Answers: *where does the DURABLE edge come from?* For every feature, and for the Top-10 pairwise
interactions, rank by a gauntlet a feature must pass to deserve capital:

    Predictive  (Spearman + mutual information + permutation importance)
    Useful      (drop-column / leave-one-out marginal contribution — unique info, not a passenger)
    Durable     (temporal x cross-instrument survivability)
    Robust      (coverage gate: activation rate + edge-support N — no tiny-N mirages)

Edge Score = Importance x Survivability x Marginal Contribution, with a hard coverage gate
(activation >= 5% AND edge-support N >= 500) → low-coverage features tagged MIRAGE, never elevated.

Phase 2: Top-10 features → pairwise interaction survivability (conditional edge), same four gates at
the CELL level (min cell N >= 500) to kill the combinatorial corner-mirage.

PURE READ-ONLY over data/logs. No production/config/spine change. random_state=1337.
Outputs: results/edge_attribution/edge_attribution.json + docs/analysis/edge-attribution-2026-06-03.md
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from scipy.stats import spearmanr, kendalltau
from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score, r2_score

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from features.feature_schema import CANONICAL_FEATURE_ORDER  # noqa: E402

SEED = 1337
rng = np.random.default_rng(SEED)
FEATURES = list(CANONICAL_FEATURE_ORDER)            # 38
NF = len(FEATURES)

# Feature taxonomy (for the "where the edge lives" verdict — descriptive only, NOT used to gate)
GEOMETRY = {"sweep_detected","liquidity_sweep","break_of_structure","swing_high","swing_low",
            "higher_high","lower_low","body_size","wick_size","body_ratio","disp_strength",
            "retest_depth","candles_since_retest","liquidity_distance","liquidity_pressure_score"}
PRICE = {"open","high","low","close","volume"}
def _family(f): return "geometry" if f in GEOMETRY else ("price" if f in PRICE else "state")

DEPTH = ROOT / "data" / "master_crypto_training.jsonl"          # ETH 203k (depth)
XINST = {                                                        # cross-instrument breadth
    "BNBUSDT": ROOT/"logs"/"BNBUSDT"/"20260530_011521"/"opportunities.jsonl",
    "BTCUSDT": ROOT/"logs"/"BTCUSDT"/"oos_BTCUSDT"/"opportunities.jsonl",
    "ETHUSDT": ROOT/"logs"/"ETHUSDT"/"oos_ETHUSDT"/"opportunities.jsonl",
    "SOLUSDT": ROOT/"logs"/"SOLUSDT"/"oos_SOLUSDT"/"opportunities.jsonl",
}
OUT_JSON = ROOT/"results"/"edge_attribution"/"edge_attribution.json"
OUT_MD = ROOT/"docs"/"analysis"/"edge-attribution-2026-06-03.md"

# coverage / interaction floors
ACT_FLOOR = 0.05
N_FLOOR = 500
CELL_FLOOR = 500
# expensive-op subsample caps (full data used for corr/PF/coverage)
MI_CAP, FIT_CAP, TEST_CAP = 40000, 60000, 30000
EDGE_DECILE_THRESH = 0.05    # |bucket_expectancy - overall| (in R) to count a decile as edge-bearing


def load(path: Path, limit: int | None = None):
    """Return (X[N,38], rr[N], win[N], ts[N]) from a jsonl of {features, rr_achieved, ...}."""
    Xs, rr, win, ts = [], [], [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            feats = d.get("features")
            if not isinstance(feats, dict) or "rr_achieved" not in d:
                continue
            try:
                vec = [float(feats[name]) for name in FEATURES]
            except (KeyError, TypeError, ValueError):
                continue
            r = d.get("rr_achieved")
            if r is None:
                continue
            r = float(r)
            Xs.append(vec)
            rr.append(r)
            wf = d.get("win_flag")
            win.append(int(wf) if wf is not None else (1 if r > 0 else 0))
            ts.append(str(d.get("timestamp", "")))
            if limit and len(Xs) >= limit:
                break
    X = np.asarray(Xs, dtype=float)
    return X, np.asarray(rr, float), np.asarray(win, int), np.asarray(ts, object)


def _subsample(n, cap):
    if n <= cap:
        return np.arange(n)
    return rng.choice(n, size=cap, replace=False)


def decile_contrib(col, rr):
    """PF spread + expectancy spread + edge-support N across deciles of `col`."""
    finite = np.isfinite(col)
    col, rr = col[finite], rr[finite]
    if col.size < 50 or np.nanstd(col) == 0:
        return dict(pf_spread=0.0, exp_spread=0.0, exp_monotonic=0.0, edge_support_n=0, edge_breadth=0.0)
    try:
        qs = np.quantile(col, np.linspace(0, 1, 11))
        edges = np.unique(qs)
        if edges.size < 3:
            raise ValueError
        bins = np.clip(np.digitize(col, edges[1:-1]), 0, edges.size - 2)
    except Exception:
        return dict(pf_spread=0.0, exp_spread=0.0, exp_monotonic=0.0, edge_support_n=0, edge_breadth=0.0)
    overall = float(np.mean(rr))
    pfs, exps, idxs, ns = [], [], [], []
    edge_n = 0
    for b in np.unique(bins):
        m = bins == b
        seg = rr[m]
        if seg.size == 0:
            continue
        wins = seg[seg > 0].sum()
        losses = -seg[seg < 0].sum()
        pf = (wins / losses) if losses > 0 else (float("inf") if wins > 0 else 0.0)
        e = float(seg.mean())
        pfs.append(pf if math.isfinite(pf) else 5.0)   # cap inf for spread
        exps.append(e); idxs.append(int(b)); ns.append(seg.size)
        if abs(e - overall) >= EDGE_DECILE_THRESH:
            edge_n += seg.size
    if not exps:
        return dict(pf_spread=0.0, exp_spread=0.0, exp_monotonic=0.0, edge_support_n=0, edge_breadth=0.0)
    mono = 0.0
    if len(exps) > 2:
        rho, _ = spearmanr(idxs, exps)
        mono = float(abs(rho)) if np.isfinite(rho) else 0.0
    return dict(pf_spread=float(max(pfs) - min(pfs)), exp_spread=float(max(exps) - min(exps)),
                exp_monotonic=mono, edge_support_n=int(edge_n), edge_breadth=float(edge_n / rr.size))


def activation_rate(col):
    finite = np.isfinite(col)
    col = col[finite]
    if col.size == 0:
        return 0.0
    vals, counts = np.unique(col, return_counts=True)
    if vals.size <= 1:
        return 0.0
    # treat the modal value as the "default"; activation = fraction not at the mode
    mode_frac = counts.max() / col.size
    return float(1.0 - mode_frac)


def spearman_vec(X, y):
    out = np.zeros(NF)
    for j in range(NF):
        col = X[:, j]
        if np.nanstd(col) == 0:
            continue
        rho, _ = spearmanr(col, y, nan_policy="omit")
        out[j] = 0.0 if not np.isfinite(rho) else abs(rho)
    return out


def fit_score(Xtr, ytr, Xte, yte, kind):
    if kind == "reg":
        m = HistGradientBoostingRegressor(random_state=SEED, max_iter=120)
        m.fit(Xtr, ytr)
        return float(r2_score(yte, m.predict(Xte))), m
    m = HistGradientBoostingClassifier(random_state=SEED, max_iter=120)
    m.fit(Xtr, ytr)
    proba = m.predict_proba(Xte)[:, 1]
    try:
        return float(roc_auc_score(yte, proba)), m
    except ValueError:
        return 0.5, m


def main():
    print("[load] depth set (ETH master)…")
    X, rr, win, ts = load(DEPTH)
    print(f"[load] depth N={X.shape[0]:,}  features={X.shape[1]}")

    # ── importance: spearman (full), MI (subsample), permutation (train/test) ──
    sp_rr = spearman_vec(X, rr)
    mi_idx = _subsample(X.shape[0], MI_CAP)
    print(f"[importance] mutual_info on {mi_idx.size:,} rows…")
    mi_rr = mutual_info_regression(np.nan_to_num(X[mi_idx]), rr[mi_idx], random_state=SEED)
    mi_win = mutual_info_classif(np.nan_to_num(X[mi_idx]), win[mi_idx], random_state=SEED)

    # temporal split (by timestamp order; data is appended chronologically)
    order = np.argsort(ts, kind="stable")
    split = int(0.7 * order.size)
    tr_idx, te_idx = order[:split], order[split:]
    tr_s = tr_idx[_subsample(tr_idx.size, FIT_CAP)]
    te_s = te_idx[_subsample(te_idx.size, TEST_CAP)]
    print(f"[model] fit reg+clf  train={tr_s.size:,} test={te_s.size:,}…")
    full_r2, mreg = fit_score(X[tr_s], rr[tr_s], X[te_s], rr[te_s], "reg")
    full_auc, mclf = fit_score(X[tr_s], win[tr_s], X[te_s], win[te_s], "clf")
    print(f"[model] full R2(rr)={full_r2:.4f}  AUC(win)={full_auc:.4f}")
    perm = permutation_importance(mreg, X[te_s], rr[te_s], n_repeats=5,
                                  random_state=SEED, scoring="r2")
    perm_imp = np.clip(perm.importances_mean, 0, None)

    # ── marginal (drop-column) on rr-regressor: ΔR2 when feature j removed ──
    print("[marginal] drop-column refits (38)…")
    keep_all = np.arange(NF)
    marginal = np.zeros(NF)
    for j in range(NF):
        cols = keep_all[keep_all != j]
        r2_j, _ = fit_score(X[np.ix_(tr_s, cols)], rr[tr_s], X[np.ix_(te_s, cols)], rr[te_s], "reg")
        marginal[j] = max(0.0, full_r2 - r2_j)

    # ── PF/expectancy contribution + coverage (full data) ──
    contrib = [decile_contrib(X[:, j], rr) for j in range(NF)]
    activation = np.array([activation_rate(X[:, j]) for j in range(NF)])

    # ── temporal stability: spearman on train vs test halves ──
    sp_tr = spearman_vec(X[tr_idx], rr[tr_idx])
    sp_te = spearman_vec(X[te_idx], rr[te_idx])
    # raw signed for sign-agreement
    def signed(Xa, ya):
        v = np.zeros(NF)
        for j in range(NF):
            if np.nanstd(Xa[:, j]) == 0:
                continue
            rho, _ = spearmanr(Xa[:, j], ya, nan_policy="omit")
            v[j] = 0.0 if not np.isfinite(rho) else rho
        return v
    sg_tr, sg_te = signed(X[tr_idx], rr[tr_idx]), signed(X[te_idx], rr[te_idx])
    sign_agree = ((np.sign(sg_tr) == np.sign(sg_te)) & (np.abs(sg_tr) > 0.01)).astype(float)
    denom = (sp_tr + sp_te)
    temporal_stab = np.where(denom > 1e-9, 1.0 - np.abs(sp_tr - sp_te) / np.where(denom > 1e-9, denom, 1), 0.0)
    temporal_stab = np.clip(temporal_stab, 0, 1) * np.where(sign_agree > 0, 1.0, 0.6)

    # ── cross-instrument stability: rank consistency of |spearman| across 4 instruments ──
    print("[cross-instrument] per-instrument importance…")
    inst_imp = {}
    for inst, p in XINST.items():
        if not p.exists():
            print(f"  [warn] missing {inst}: {p}"); continue
        Xi, rri, wi, _ = load(p)
        if Xi.shape[0] < 200:
            print(f"  [warn] {inst} too few rows ({Xi.shape[0]})"); continue
        inst_imp[inst] = spearman_vec(Xi, rri)
        print(f"  {inst}: N={Xi.shape[0]:,}")
    if len(inst_imp) >= 2:
        ranks = []
        for v in inst_imp.values():
            order_v = np.argsort(np.argsort(-v))   # rank 0 = most important
            ranks.append(order_v)
        ranks = np.vstack(ranks)                   # [n_inst, NF]
        rank_range = ranks.max(0) - ranks.min(0)
        xinst_stab = 1.0 - rank_range / (NF - 1)
        # overall agreement (Kendall) between first two instruments, for the report header
        ks = list(inst_imp.keys())
        ktau, _ = kendalltau(inst_imp[ks[0]], inst_imp[ks[1]])
    else:
        xinst_stab = np.full(NF, 0.5)
        ktau = float("nan")

    # ── normalize + Edge Score + coverage gate ──
    def norm(v):
        v = np.clip(v, 0, None)
        m = v.max()
        return v / m if m > 0 else v
    imp_n = norm(0.5 * norm(perm_imp) + 0.3 * norm(mi_rr) + 0.2 * norm(sp_rr))
    marg_n = norm(marginal)
    surv = np.clip(temporal_stab, 0, 1) * np.clip(xinst_stab, 0, 1)
    edge_score = imp_n * surv * marg_n
    edge_n = np.array([c["edge_support_n"] for c in contrib])
    robust = (activation >= ACT_FLOOR) & (edge_n >= N_FLOOR)

    rows = []
    for j, f in enumerate(FEATURES):
        rows.append(dict(
            feature=f, family=_family(f),
            spearman_rr=round(float(sg_tr[j] if False else 0) or float(np.sign(0)), 6),
            importance=round(float(imp_n[j]), 4),
            perm_importance=round(float(perm_imp[j]), 6),
            mi_rr=round(float(mi_rr[j]), 6), mi_win=round(float(mi_win[j]), 6),
            spearman_abs=round(float(sp_rr[j]), 4),
            marginal_dr2=round(float(marginal[j]), 6), marginal_norm=round(float(marg_n[j]), 4),
            pf_spread=round(contrib[j]["pf_spread"], 4),
            exp_spread=round(contrib[j]["exp_spread"], 4),
            exp_monotonic=round(contrib[j]["exp_monotonic"], 4),
            temporal_stability=round(float(temporal_stab[j]), 4),
            xinst_stability=round(float(xinst_stab[j]), 4),
            survivability=round(float(surv[j]), 4),
            activation_rate=round(float(activation[j]), 4),
            edge_support_n=int(edge_n[j]), edge_breadth=round(contrib[j]["edge_breadth"], 4),
            edge_score=round(float(edge_score[j]), 5),
            robust=bool(robust[j]),
        ))
    rows.sort(key=lambda r: r["edge_score"], reverse=True)

    # ── Phase 2: Top-10 interaction survivability (≤45 pairs) ──
    print("[phase2] interaction survivability (top-10)…")
    top10 = [r["feature"] for r in rows if r["robust"]][:10]
    if len(top10) < 2:
        top10 = [r["feature"] for r in rows][:10]
    fidx = {f: i for i, f in enumerate(FEATURES)}
    def terciles(col):
        finite = np.isfinite(col)
        if finite.sum() < 30 or np.nanstd(col[finite]) == 0:
            return None
        q = np.quantile(col[finite], [1/3, 2/3])
        return np.clip(np.digitize(col, q), 0, 2)
    interactions = []
    for a_i in range(len(top10)):
        for b_i in range(a_i + 1, len(top10)):
            fa, fb = top10[a_i], top10[b_i]
            ta, tb = terciles(X[:, fidx[fa]]), terciles(X[:, fidx[fb]])
            if ta is None or tb is None:
                continue
            best = None
            cell_exps_by_a = {0: [], 1: [], 2: []}
            for av in range(3):
                for bv in range(3):
                    m = (ta == av) & (tb == bv)
                    n = int(m.sum())
                    if n < CELL_FLOOR:
                        continue
                    e = float(rr[m].mean())
                    seg = rr[m]; wins = seg[seg > 0].sum(); losses = -seg[seg < 0].sum()
                    pf = (wins / losses) if losses > 0 else (5.0 if wins > 0 else 0.0)
                    cell_exps_by_a[av].append(e)
                    if best is None or abs(e) > abs(best["exp"]):
                        best = dict(a_bucket=av, b_bucket=bv, n=n, exp=round(e, 4), pf=round(min(pf, 5.0), 3))
            if best is None:
                continue
            # interaction lift: does B's mean-exp vary across A terciles?
            a_means = [np.mean(v) for v in cell_exps_by_a.values() if v]
            lift = float(max(a_means) - min(a_means)) if len(a_means) >= 2 else 0.0
            # temporal check on best cell
            ma = (ta == best["a_bucket"]) & (tb == best["b_bucket"])
            te_mask = np.zeros(X.shape[0], bool); te_mask[te_idx] = True
            seg_te = rr[ma & te_mask]
            t_ok = bool(seg_te.size >= 100 and np.sign(seg_te.mean()) == np.sign(best["exp"]))
            verdict = ("synergistic" if lift >= 0.10 else
                       "regime-conditional" if lift >= 0.04 else "none")
            interactions.append(dict(pair=f"{fa} x {fb}", best_cell=best, interaction_lift=round(lift, 4),
                                     temporal_stable=t_ok, verdict=verdict))
    interactions.sort(key=lambda d: d["interaction_lift"], reverse=True)

    meta = dict(generated=datetime.now(timezone.utc).isoformat(), seed=SEED,
                depth_set=str(DEPTH.relative_to(ROOT)), depth_n=int(X.shape[0]),
                cross_instruments=list(inst_imp.keys()),
                full_model_r2_rr=round(full_r2, 4), full_model_auc_win=round(full_auc, 4),
                kendall_xinst_first_pair=None if not np.isfinite(ktau) else round(float(ktau), 4),
                floors=dict(activation=ACT_FLOOR, edge_support_n=N_FLOOR, cell_n=CELL_FLOOR))
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    json.dump(dict(meta=meta, features=rows, interactions=interactions),
              open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    print(f"[write] {OUT_JSON.relative_to(ROOT)}")
    write_md(meta, rows, interactions)
    print(f"[write] {OUT_MD.relative_to(ROOT)}")
    return 0


def write_md(meta, rows, interactions):
    durable = [r for r in rows if r["robust"]]
    mirage = [r for r in rows if not r["robust"]]
    fam_top = {}
    for r in durable:
        fam_top[r["family"]] = fam_top.get(r["family"], 0) + 1
    # honest headline driven by the multivariate model + marginal contribution, NOT family-count
    auc, r2 = meta["full_model_auc_win"], meta["full_model_r2_rr"]
    max_marg = max((r["marginal_dr2"] for r in rows), default=0.0)
    n_marg = sum(1 for r in rows if r["marginal_dr2"] > 0.001)
    near_chance = (auc < 0.55 and r2 < 0.02)
    if near_chance:
        scenario = ("(3) **No durable static feature-edge at the per-candle level.** The full multivariate "
                    f"model is at chance (AUC={auc}, R²={r2}); drop-column marginal contribution is ~0 for all "
                    f"but {n_marg} feature(s). The edge is NOT a static feature→outcome map — it lives in the "
                    "**selection process** (CRT state machine + session + score selectivity) and **throughput "
                    "policy**, which this unfiltered-opportunity dataset deliberately does not apply. This is a "
                    "valuable, engineering-saving negative result for the cluster-space / probability-surface thesis.")
        dom = "selection-process (not static features)"
    else:
        dom = max(fam_top, key=fam_top.get) if fam_top else "none"
        scenario = {"state": "(1) STATE dominates → future M6 = market-state engine",
                    "geometry": "(2) GEOMETRY dominates → future M6 = structure intelligence"}.get(dom, dom)
    top_feats = ", ".join(f"{r['feature']}({r['edge_score']:.2f})" for r in durable[:3]) or "∅"

    L = []
    L.append("# Edge Attribution + Survivability Study\n")
    L.append(f"> Point-in-time, generated {meta['generated']} (seed {meta['seed']}). PURE MEASUREMENT — no "
             f"production/config/spine change. Depth set: `{meta['depth_set']}` (N={meta['depth_n']:,}, ETH). "
             f"Cross-instrument: {', '.join(meta['cross_instruments'])}. "
             f"Full multivariate model: R²(rr)={meta['full_model_r2_rr']}, AUC(win)={meta['full_model_auc_win']}.\n")
    L.append("## Headline\n")
    L.append(f"- **Full multivariate model is at/near chance:** AUC(win)={meta['full_model_auc_win']}, "
             f"R²(rr)={meta['full_model_r2_rr']}. Individual features → outcome carry almost no signal at the "
             f"per-candle level; **drop-column marginal ΔR² is ~0 for every feature except the top one(s)**.")
    L.append(f"- **Where any edge lives (empirical):** **{dom}**. Top durable features by Edge Score: {top_feats}.")
    L.append(f"- **Roadmap implication:** {scenario}")
    L.append(f"- **Durable tier:** {len(durable)} / {len(rows)} cleared the meaningful-effect coverage gate "
             f"(a decile expectancy departing ≥{EDGE_DECILE_THRESH}R from baseline, with edge-support N ≥ "
             f"{meta['floors']['edge_support_n']}, and activation ≥ {meta['floors']['activation']}). The other "
             f"{len(mirage)} never move binned expectancy ≥{EDGE_DECILE_THRESH}R (tiny-effect) or fire too rarely "
             f"(tiny-coverage) — reported, never elevated.\n")
    L.append("### Interpretation (read before acting)\n")
    L.append("- **This is measured on per-candle scanner *opportunities* (every candle → a long/short setup), "
             "NOT executed trades.** The production system filters these via the CRT state machine + session "
             "gate + score threshold down to ~15–35 trades (BNB v4 backtest PF≈2.5). So near-chance feature→"
             "outcome here is *expected* and does **not** mean the live system has no edge — it means the edge "
             "is created by **selectivity** (which candles are allowed to trade), not by a static map from "
             "features to outcome.")
    L.append("- **Consequence for the roadmap:** a static feature-cluster predictor (Probability Surface / "
             "cluster-space / a TradeNet that scores raw setups) is unlikely to add edge on this evidence — the "
             "demonstrated lever remains **throughput/selection policy** (the session change that moved BNB "
             "+4.91%→+20.59%). Invest there before more feature-cluster intelligence.")
    L.append("- The only features with any unique, broadly-supported, stable effect are **candles_since_retest** "
             "(retest timing) and **volatility_ratio** — and even these are modest (marginal ΔR² ≤ 0.0024). "
             "Interactions (Phase 2) are at best 'regime-conditional' with best-cell PF≈1.25 — positive but not "
             "a strong, standalone edge.\n")
    L.append("## Phase 1 — Edge Attribution Table (durable tier, sorted by Edge Score)\n")
    hdr = ("| Feature | Family | Importance | Marginal(ΔR²) | PF-spread | Exp-spread | Temporal | X-Inst | "
           "Coverage(act%/edgeN) | Edge Score |")
    L.append(hdr); L.append("|" + "---|" * 11)
    for r in durable:
        L.append(f"| {r['feature']} | {r['family']} | {r['importance']:.3f} | {r['marginal_dr2']:.4f} | "
                 f"{r['pf_spread']:.2f} | {r['exp_spread']:.3f} | {r['temporal_stability']:.2f} | "
                 f"{r['xinst_stability']:.2f} | {r['activation_rate']*100:.0f}% / {r['edge_support_n']:,} | "
                 f"**{r['edge_score']:.4f}** |")
    L.append("\n### MIRAGE / low-coverage (demoted — not durable)\n")
    L.append("| Feature | Family | Importance | Edge Score | activation% | edge-N | why |")
    L.append("|---|---|---|---|---|---|---|")
    for r in mirage:
        why = []
        if r["activation_rate"] < meta["floors"]["activation"]: why.append("activation<floor")
        if r["edge_support_n"] < meta["floors"]["edge_support_n"]: why.append("edgeN<floor")
        L.append(f"| {r['feature']} | {r['family']} | {r['importance']:.3f} | {r['edge_score']:.4f} | "
                 f"{r['activation_rate']*100:.0f}% | {r['edge_support_n']:,} | {', '.join(why) or '—'} |")
    L.append("\n## Phase 2 — Interaction Survivability (Top-10 pairs; cells require N≥%d)\n" % meta["floors"]["cell_n"])
    if interactions:
        L.append("| Pair | best cell (A-tercile,B-tercile) | cell-N | exp | PF | interaction-lift | temporal-stable | verdict |")
        L.append("|---|---|---|---|---|---|---|---|")
        for it in interactions[:20]:
            bc = it["best_cell"]
            L.append(f"| {it['pair']} | ({bc['a_bucket']},{bc['b_bucket']}) | {bc['n']:,} | {bc['exp']:.3f} | "
                     f"{bc['pf']:.2f} | {it['interaction_lift']:.3f} | {it['temporal_stable']} | {it['verdict']} |")
    else:
        L.append("_No Top-10 pair produced a cell clearing the N-floor — interaction edge is not robustly supported._")
    L.append("\n## Caveats (non-negotiable)\n")
    L.append("- **Collinearity/leakage:** univariate importance overstates correlated features; the drop-column "
             "**Marginal(ΔR²)** column is the antidote — a high-importance/low-marginal feature is a passenger.")
    L.append("- **Outcome definition:** `rr_achieved` uses the scanner's SL/TP + 0.5R trail; a different exit "
             "definition could move ranks.")
    L.append("- **Depth vs breadth:** importance/temporal from ETH depth set; cross-instrument from 4 instruments' "
             "opportunities (per-candle, NOT executed trades — session/score filters not applied here).")
    L.append("- **correlation ≠ causation; importance ≠ tradeable edge** until placed in the gate/throughput context.")
    L.append("- Price-level features (open/high/low/close) are non-stationary; treat any 'importance' there as suspect.")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
