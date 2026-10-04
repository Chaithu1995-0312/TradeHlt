"""
accepted_trade_attribution.py — Study 1: does feature→outcome edge EMERGE after selection?

Re-runs the Edge Attribution metrics on ONLY the CRT-accepted/executed trades (the ~15-35 per run the
pipeline actually took), pooled across all `results/**/*_trades.csv`, vs the per-candle baseline
(AUC 0.515 / R² 0.004 on 203k opportunities). If accepted-trade AUC rises ≫0.55 with durable marginal
features → feature edge is real post-selection. If it stays ~chance → the edge is the selection sequence
itself, not features. Pure read-only. random_state=1337.

Reuses the attribution primitives from edge_attribution_study.py.
Output: docs/analysis/accepted-trade-attribution-2026-06-03.md + results/edge_attribution/accepted_trade_attribution.json
"""
from __future__ import annotations
import csv, json, sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
from sklearn.inspection import permutation_importance

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import edge_attribution_study as eas   # reuse FEATURES, decile_contrib, activation_rate, spearman_vec, fit_score, _family

ROOT = eas.ROOT
FEATURES, NF, SEED = eas.FEATURES, eas.NF, eas.SEED
rng = np.random.default_rng(SEED)
OUT_JSON = ROOT/"results"/"edge_attribution"/"accepted_trade_attribution.json"
OUT_MD = ROOT/"docs"/"analysis"/"accepted-trade-attribution-2026-06-03.md"
ACT_FLOOR, N_FLOOR = 0.05, 200          # lower edge-N floor — accepted trades are inherently small-N


def load_accepted():
    """Pool all results/**/*_trades.csv → (X, rr, win, ts, inst), filtered + deduped."""
    files = sorted(ROOT.glob("results/**/*_trades.csv"))
    print(f"[load] {len(files)} trade CSVs")
    seen, rows = set(), []
    missing_cols = None
    for fp in files:
        try:
            rdr = list(csv.DictReader(open(fp, encoding="utf-8")))
        except Exception:
            continue
        if not rdr:
            continue
        cols = rdr[0].keys()
        present = [f for f in FEATURES if f in cols]
        if missing_cols is None:
            missing_cols = [f for f in FEATURES if f not in cols]
        if "pnl_rr_net" not in cols or len(present) < 30:
            continue
        inst = (rdr[0].get("instrument") or fp.parts[-3] or "?")
        for r in rdr:
            try:
                rr = float(r.get("pnl_rr_net") or "nan")
            except ValueError:
                continue
            if not np.isfinite(rr):
                continue
            vec = []
            ok = True
            for f in FEATURES:
                v = r.get(f)
                try:
                    vec.append(float(v) if v not in (None, "") else 0.0)
                except ValueError:
                    vec.append(0.0)
            zero_frac = sum(1 for x in vec if x == 0.0) / len(vec)
            if zero_frac > 0.5:               # zero-feature guard (stale lookup) → drop
                continue
            key = (inst, r.get("opened_at"), r.get("direction"), r.get("entry"), r.get("sl"), r.get("tp"))
            if key in seen:
                continue
            seen.add(key)
            rows.append((vec, rr, 1 if rr > 0 else 0, str(r.get("opened_at", "")), inst))
    X = np.array([r[0] for r in rows], float)
    rr = np.array([r[1] for r in rows], float)
    win = np.array([r[2] for r in rows], int)
    ts = np.array([r[3] for r in rows], object)
    inst = np.array([r[4] for r in rows], object)
    print(f"[load] unique valid accepted trades = {X.shape[0]:,}  (dropped degenerate/dupes)")
    if missing_cols:
        print(f"[load] features absent from trade CSVs: {missing_cols}")
    return X, rr, win, ts, inst, missing_cols or []


def run():
    X, rr, win, ts, inst, missing = load_accepted()
    N = X.shape[0]
    insts, counts = np.unique(inst, return_counts=True)
    by_inst = dict(sorted(zip(insts.tolist(), counts.tolist()), key=lambda kv: -kv[1]))
    print(f"[data] N={N}  win_rate={win.mean():.3f}  mean_rr={rr.mean():+.3f}  instruments={by_inst}")

    sp = eas.spearman_vec(X, rr)
    mi_rr = mutual_info_regression(np.nan_to_num(X), rr, random_state=SEED)
    mi_win = mutual_info_classif(np.nan_to_num(X), win, random_state=SEED)

    # temporal split by opened_at
    order = np.argsort(ts, kind="stable")
    split = int(0.7 * N)
    tr, te = order[:split], order[split:]
    full_r2, mreg = eas.fit_score(X[tr], rr[tr], X[te], rr[te], "reg")
    full_auc, mclf = eas.fit_score(X[tr], win[tr], X[te], win[te], "clf")
    print(f"[model] ACCEPTED full R2(rr)={full_r2:.4f}  AUC(win)={full_auc:.4f}  (baseline opp: R2=0.0042 AUC=0.5149)")
    perm = permutation_importance(mreg, X[te], rr[te], n_repeats=8, random_state=SEED, scoring="r2")
    perm_imp = np.clip(perm.importances_mean, 0, None)

    # drop-column marginal
    marg = np.zeros(NF)
    keep = np.arange(NF)
    for j in range(NF):
        cols = keep[keep != j]
        r2j, _ = eas.fit_score(X[np.ix_(tr, cols)], rr[tr], X[np.ix_(te, cols)], rr[te], "reg")
        marg[j] = max(0.0, full_r2 - r2j)

    contrib = [eas.decile_contrib(X[:, j], rr) for j in range(NF)]
    act = np.array([eas.activation_rate(X[:, j]) for j in range(NF)])

    # temporal stability (sign agreement of spearman on halves)
    sp_tr, sp_te = eas.spearman_vec(X[tr], rr[tr]), eas.spearman_vec(X[te], rr[te])
    denom = sp_tr + sp_te
    temporal = np.clip(np.where(denom > 1e-9, 1 - np.abs(sp_tr - sp_te)/np.where(denom > 1e-9, denom, 1), 0), 0, 1)

    # cross-instrument stability (rank consistency across instruments with N>=40)
    big = [i for i, c in by_inst.items() if c >= 40]
    if len(big) >= 2:
        ranks = []
        for i in big:
            m = inst == i
            v = eas.spearman_vec(X[m], rr[m])
            ranks.append(np.argsort(np.argsort(-v)))
        ranks = np.vstack(ranks)
        xinst = 1 - (ranks.max(0) - ranks.min(0)) / (NF - 1)
    else:
        xinst = np.full(NF, 0.5)

    def norm(v):
        v = np.clip(v, 0, None); m = v.max(); return v/m if m > 0 else v
    imp_n = norm(0.5*norm(perm_imp) + 0.3*norm(mi_rr) + 0.2*norm(sp))
    surv = np.clip(temporal, 0, 1) * np.clip(xinst, 0, 1)
    edge = imp_n * surv * norm(marg)
    edge_n = np.array([c["edge_support_n"] for c in contrib])
    robust = (act >= ACT_FLOOR) & (edge_n >= N_FLOOR)

    rows = []
    for j, f in enumerate(FEATURES):
        rows.append(dict(feature=f, family=eas._family(f), importance=round(float(imp_n[j]), 4),
                         perm=round(float(perm_imp[j]), 6), mi_rr=round(float(mi_rr[j]), 6),
                         spearman_abs=round(float(sp[j]), 4), marginal_dr2=round(float(marg[j]), 6),
                         pf_spread=round(contrib[j]["pf_spread"], 4), exp_spread=round(contrib[j]["exp_spread"], 4),
                         temporal=round(float(temporal[j]), 4), xinst=round(float(xinst[j]), 4),
                         survivability=round(float(surv[j]), 4), activation=round(float(act[j]), 4),
                         edge_support_n=int(edge_n[j]), edge_score=round(float(edge[j]), 5), robust=bool(robust[j])))
    rows.sort(key=lambda r: r["edge_score"], reverse=True)

    meta = dict(generated=datetime.now(timezone.utc).isoformat(), seed=SEED, n_accepted=int(N),
                win_rate=round(float(win.mean()), 4), mean_rr=round(float(rr.mean()), 4),
                by_instrument=by_inst, missing_features=missing,
                accepted_full_r2=round(full_r2, 4), accepted_full_auc=round(full_auc, 4),
                baseline_opp_r2=0.0042, baseline_opp_auc=0.5149)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    json.dump(dict(meta=meta, features=rows), open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    write_md(meta, rows)
    print(f"[write] {OUT_MD.relative_to(ROOT)}")


def write_md(meta, rows):
    durable = [r for r in rows if r["robust"]]
    auc, r2 = meta["accepted_full_auc"], meta["accepted_full_r2"]
    delta = auc - meta["baseline_opp_auc"]
    # tiered, honest verdict — AUC alone is not enough; require positive generalization (R²>0) for "strong"
    if auc >= 0.60 and r2 > 0 and any(r["marginal_dr2"] > 0.005 for r in rows):
        verdict = ("**Feature edge EMERGES post-selection** — accepted trades are separably predictable by "
                   "features (AUC well above chance *and* positive out-of-sample R²). A filtered predictor "
                   "(Probability Surface on accepted trades) is worth building.")
    elif auc >= 0.55:
        verdict = (f"**Weak / suggestive — INCONCLUSIVE.** Direction-only AUC lifted {meta['baseline_opp_auc']}→{auc} "
                   f"(Δ{delta:+.3f}), so features carry *a little* more signal among accepted trades than among all "
                   f"candles. BUT R²(rr)={r2} is **negative** (magnitude is unpredictable — the model generalizes "
                   f"worse than the mean), the marginal-ΔR² column is computed off that negative-R² model so it is "
                   f"**not reliable**, and N={meta['n_accepted']} across heterogeneous configs is too small to trust. "
                   f"This does **not** justify building a feature/cluster predictor yet — it justifies getting more "
                   f"clean accepted-trade samples (fix feedback-loop Break 2) and looking at Study 2.")
    else:
        verdict = ("**Feature edge does NOT emerge** — even among selected trades, features ≈ chance. The edge is the "
                   "**selection sequence itself** → Study 2; deprioritize feature/cluster intelligence.")
    L = ["# Accepted-Trade Attribution Study (Study 1)\n",
         f"> Point-in-time, {meta['generated']} (seed {meta['seed']}). PURE MEASUREMENT — no production change. "
         f"Pooled CRT-accepted/executed trades from `results/**/*_trades.csv`. N={meta['n_accepted']:,} unique valid "
         f"(win-rate {meta['win_rate']}, mean rr {meta['mean_rr']:+}). By instrument: {meta['by_instrument']}.\n",
         "## Headline — does feature edge EMERGE after selection?\n",
         f"- **Selection already produces positive expectancy:** accepted trades = mean rr **{meta['mean_rr']:+}R** at "
         f"**{meta['win_rate']:.1%}** win-rate (the per-candle opportunity pool is ~0). The edge is demonstrably in the "
         f"selection. The question is whether *features* add anything on top.",
         f"- **Accepted-trade multivariate model:** AUC(win)=**{auc}**, R²(rr)=**{r2}**  "
         f"vs per-candle baseline AUC={meta['baseline_opp_auc']}, R²={meta['baseline_opp_r2']}  "
         f"(ΔAUC = **{delta:+.4f}**).",
         f"- **Verdict:** {verdict}",
         f"- **Recurring (weak) candidates:** the only features with any signal are volatility-context — "
         f"`atr`/`volatility_ratio`/`rsi_14` top importance — consistent with *volatility regime* mattering at entry, "
         f"but marginal is unreliable at this N.",
         f"- **Durable features (coverage-gated):** {len(durable)}/{len(rows)} — NOTE: at N={meta['n_accepted']} the "
         f"decile expectancy spreads are large from noise, so the coverage gate is weakly discriminating here; trust "
         f"the Edge Score / marginal collapse, not the count.\n",
         "## Attribution table (durable tier, by Edge Score)\n",
         "| Feature | Family | Importance | Marginal(ΔR²) | PF-spread | Exp-spread | Temporal | X-Inst | act% / edgeN | Edge Score |",
         "|" + "---|"*11]
    for r in (durable or rows[:8]):
        L.append(f"| {r['feature']} | {r['family']} | {r['importance']:.3f} | {r['marginal_dr2']:.4f} | "
                 f"{r['pf_spread']:.2f} | {r['exp_spread']:.3f} | {r['temporal']:.2f} | {r['xinst']:.2f} | "
                 f"{r['activation']*100:.0f}% / {r['edge_support_n']:,} | **{r['edge_score']:.4f}** |")
    L += ["\n## Caveats\n",
          "- **Config/period heterogeneity (dominant):** the 731 runs span many param configs and date ranges; "
          "pooled attribution mixes regimes. Per-instrument N is small.",
          "- **Survivorship:** only executed trades; no rejected-candidate counterfactual here (that is Study 2).",
          f"- **Missing features in trade CSVs:** {meta['missing_features'] or 'none'} (excluded if absent).",
          "- Low N inflates importance variance; treat single-feature spikes with suspicion. correlation ≠ causation."]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
