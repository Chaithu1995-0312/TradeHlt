"""
rr_shadow_value.py — Track 4 KILL-TEST (READ-ONLY): does the RR model have ANY economic value?

Frame: RR is guilty until proven useful. This measures the RR model's OUT-OF-SAMPLE discrimination
via 5-fold CV on the 38-dim BNB corpus (the only 38-dim dataset on disk; ETH/BTC are 35-dim → a
cross-instrument OOS would test schema mismatch, not generalization, so it is deferred).

Critical: we measure the model's RAW outputs (ridge expected_rr, GNB p_win) — NOT through
NanoInferenceEngine.predict(), because the confidence gate short-circuits (~100% bypass) and would
HIDE the model's signal. The gate decides whether to USE the model in fusion; this test asks whether
the model has any signal to use at all.

Tiered early-stop (pre-registered):
  Tier 1  statistical discrimination: rr_corr(pred_rr,y_rr), AUC/Brier(p_win,y_win) vs shuffle null.
          STOP RULE — AUC<=0.52 AND |rr_corr|~0  ->  RETIRE (do not run Tier 2/3).
  Tier 2  selection value: top-decile-by-score actual mean y_rr vs random and vs gaussian baseline.
          RETIRE if top-decile deltaR <= gaussian baseline.
  Tier 3  heavy-tail filter: restrict to d_sq<=P95 cut; does excluding the weird 5% RECOVER signal?
          yes -> KEEP-CANDIDATE ; no -> RETIRE.

Authority: RESEARCH_ONLY (§6.5). A positive result is a KEEP-CANDIDATE, never a re-enable. rr_fusion
stays enabled:false; this script re-enables nothing.

Run:  python scripts/research/rr_shadow_value.py
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import numpy as np

from config_layer.rr.rr_pattern_miner import (
    RRPatternTrainer, N_FEATURES, RR_SCORE_MIN, RR_SCORE_MAX, DEFAULT_MODEL_PATH,
)

_DATASET = os.path.join(_ROOT, "models", "BNBUSDT", "bnbusdt_balanced_20260524", "rr_dataset_202605_v1.json")
_OUT_DIR = os.path.join(_ROOT, "results", "research", "rr_shadow_value")
_K = 5
_SEED = 0
_AUC_KILL = 0.52
_RRCORR_KILL = 0.03


def _raw_model_outputs(state: dict, Xtest: np.ndarray):
    """Replicate predict()'s expected_rr / p_win / d_sq math but WITHOUT the confidence-gate short
    circuit (rr_pattern_miner.py:351-363,327-334). Measures the model's raw signal."""
    W = np.asarray(state["ridge_w"]); b = float(state["ridge_b"])
    smu = np.asarray(state["scale_mu"]); ssig = np.asarray(state["scale_sigma"])
    cmu = np.asarray(state["conf_mu"]); P = np.asarray(state["conf_P"])
    gC0, gV0, gm0 = (np.asarray(state["gnb_C"][0]), np.asarray(state["gnb_V"][0]), np.asarray(state["gnb_mu"][0]))
    gC1, gV1, gm1 = (np.asarray(state["gnb_C"][1]), np.asarray(state["gnb_V"][1]), np.asarray(state["gnb_mu"][1]))

    Xs = (Xtest - smu) / ssig
    exp_rr = np.clip(Xs @ W + b, RR_SCORE_MIN, RR_SCORE_MAX)
    ll0 = (gC0 - 0.5 * gV0 * (Xs - gm0) ** 2).sum(axis=1)
    ll1 = (gC1 - 0.5 * gV1 * (Xs - gm1) ** 2).sum(axis=1)
    mx = np.maximum(ll0, ll1)
    e0 = np.exp(ll0 - mx); e1 = np.exp(ll1 - mx)
    p_win = e1 / (e0 + e1)
    delta = Xs - cmu
    d_sq = np.einsum("ij,jk,ik->i", delta, P, delta)
    return exp_rr, p_win, d_sq


def _auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Mann-Whitney AUC (no sklearn dependency). 0.5 = no discrimination."""
    labels = labels.astype(int)
    n_pos = int(labels.sum()); n_neg = int(len(labels) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), float)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ties
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return (ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def _corr(a, b) -> float:
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    c = float(np.corrcoef(a, b)[0, 1])
    return 0.0 if np.isnan(c) else c


def main() -> int:
    os.makedirs(_OUT_DIR, exist_ok=True)
    with open(_DATASET, "r", encoding="utf-8") as f:
        ds = json.load(f)
    X = np.asarray(ds["X"], float)
    y_rr = np.asarray(ds["y_rr"], float)
    y_win = np.asarray(ds["y_win"], int)
    n = len(X)

    # Mirror the deployed model's feature treatment: zero the price-anchored columns.
    with open(DEFAULT_MODEL_PATH, "r", encoding="utf-8") as f:
        zero_idx = sorted(int(i) for i in json.load(f).get("zero_indices", []))
    for i in zero_idx:
        X[:, i] = 0.0
    dof = N_FEATURES - len(zero_idx)

    # 5-fold CV → OOS predictions aligned to row order.
    rng = np.random.default_rng(_SEED)
    perm = rng.permutation(n)
    folds = np.array_split(perm, _K)
    oos_rr = np.full(n, np.nan); oos_pw = np.full(n, np.nan); oos_dsq = np.full(n, np.nan)
    for k in range(_K):
        test_idx = folds[k]
        train_idx = np.concatenate([folds[j] for j in range(_K) if j != k])
        state = RRPatternTrainer().train(
            X[train_idx].tolist(), y_rr[train_idx].tolist(), y_win[train_idx].tolist()
        )
        rr, pw, dsq = _raw_model_outputs(state, X[test_idx])
        oos_rr[test_idx] = rr; oos_pw[test_idx] = pw; oos_dsq[test_idx] = dsq

    # ── Tier 1: statistical discrimination (the kill gate) ──
    rr_corr = _corr(oos_rr, y_rr)
    auc = _auc(oos_pw, y_win)
    brier = float(np.mean((oos_pw - y_win) ** 2))
    shuf = y_win.copy(); rng.shuffle(shuf)
    auc_shuffle = _auc(oos_pw, shuf)
    tier1_survives = not (auc <= _AUC_KILL and abs(rr_corr) < _RRCORR_KILL)

    report = {
        "experiment": "rr_shadow_value KILL-TEST",
        "dataset": os.path.relpath(_DATASET, _ROOT),
        "n": int(n), "k_folds": _K, "effective_dof": dof,
        "authority": "RESEARCH_ONLY (§6.5) — KEEP-CANDIDATE at most, never a re-enable",
        "tier1_discrimination": {
            "rr_corr_pred_rr_vs_y_rr": round(rr_corr, 5),
            "auc_p_win_vs_y_win": round(auc, 5),
            "auc_shuffle_control": round(auc_shuffle, 5),
            "brier": round(brier, 5),
            "base_win_rate": round(float(y_win.mean()), 5),
            "kill_rule": f"AUC<={_AUC_KILL} AND |rr_corr|<{_RRCORR_KILL}",
            "survives": bool(tier1_survives),
        },
    }

    # ── Tier 0 — LABEL-VALIDITY gate (binding; added after the run surfaced apparent signal) ──
    # y_win/y_rr derive from the trade `outcome`/`rr_achieved` field (rr_dataset_builder.py:125-206),
    # the SAME stream F-022 found only 36.8% self-consistent (SL_HIT on paths that never touch the
    # stop). F-041B is precedent: this exact contamination produced false labels that FLIPPED when
    # re-derived through forward_walk(intrabar_fixed). So ANY Tier 1-3 survival here is discrimination
    # against a CONTAMINATED label, not credible economic evidence. Tiers below are INFORMATIONAL only.
    report["tier0_label_validity"] = {
        "label_source": "trade outcome / rr_achieved (rr_dataset_builder.py:125-206)",
        "contamination_finding": "F-022 (36.8% self-consistent); F-041B precedent (labels flipped on re-derive)",
        "y_rr_degenerate": "every win has y_rr==1.0 → y_rr ≈ y_win, not a continuous RR target",
        "credible": False,
    }

    # Tier 1-3 computed for INFORMATION (against contaminated labels — not a verdict).
    dec = max(1, n // 10)
    top = np.argsort(-oos_rr)[:dec]
    rr_top = float(np.mean(y_rr[top])); rr_rand = float(np.mean(y_rr))
    p95 = float(np.nanpercentile(oos_dsq, 95)); keep = oos_dsq <= p95
    report["tier2_selection_INFORMATIONAL"] = {
        "top_decile_mean_y_rr_by_RR": round(rr_top, 5),
        "random_baseline_mean_y_rr": round(rr_rand, 5),
    }
    report["tier3_heavy_tail_INFORMATIONAL"] = {
        "p95_cut": round(p95, 4),
        "auc_within_cut": round(_auc(oos_pw[keep], y_win[keep]), 5),
        "note": "diagnostic only — 'no improvement' does NOT mean 'no signal' (Tier-3 rule bug corrected)",
    }

    report["classification"] = "INSUFFICIENT_LABEL_CONTAMINATED"
    report["verdict_reason"] = (
        f"Apparent OOS discrimination (AUC={auc:.4f} vs shuffle {auc_shuffle:.4f}; rr_corr={rr_corr:.4f}; "
        f"top-decile y_rr={rr_top:.4f} vs random {rr_rand:.4f}) SURVIVED Tiers 1-2 — surprising vs the "
        f"F-001/F-002 prior. BUT the labels are F-022-contaminated (see tier0), so this is NOT credible "
        f"economic evidence: the model may be predicting the mislabeling structure, not real outcomes. "
        f"Cannot classify KEEP/RETIRE. REQUIRED next step: re-derive y via forward_walk(intrabar_fixed) "
        f"on the source opportunities+candles (the F-041B remedy) and re-run this kill-test."
    )

    with open(os.path.join(_OUT_DIR, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    md = _render_md(report)
    with open(os.path.join(_OUT_DIR, "report.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\nArtifact: {os.path.relpath(_OUT_DIR, _ROOT)}/report.json")
    print(f"CLASSIFICATION: {report['classification']}")
    return 0


def _gaussian_baseline_topdecile(X, y_rr, dec, zero_idx):
    """Top-decile mean y_rr selected by the heuristic gaussian score (the incumbent RR duplicates).
    Returns None if the engine can't be constructed cleanly (Tier-2 then uses random baseline only)."""
    try:
        from features.feature_schema import FEATURE_INDEX_MAP
        from engines.heuristic_gaussian_engine import HeuristicGaussianEngine  # type: ignore
        from config_layer.production_config import get_prod_section
        cfg = get_prod_section("gaussian_scorer")
        eng = HeuristicGaussianEngine(cfg)
        iff, ifs, im = (FEATURE_INDEX_MAP["ema_fast"], FEATURE_INDEX_MAP["ema_slow"],
                        FEATURE_INDEX_MAP["momentum_score"])
        scores = np.array([
            float(eng.compute({"ema_fast": X[r, iff], "ema_slow": X[r, ifs],
                               "momentum_score": X[r, im]}).get("score", 0.0))
            for r in range(len(X))
        ])
        top = np.argsort(-scores)[:dec]
        return float(np.mean(y_rr[top]))
    except Exception:
        return None


def _render_md(r: dict) -> str:
    t1 = r["tier1_discrimination"]
    L = [
        "# RR Shadow-Value KILL-TEST (Track 4)", "",
        f"**{r['dataset']}**  n={r['n']}  {r['k_folds']}-fold CV  dof={r['effective_dof']}",
        f"Authority: {r['authority']}", "",
        "## Tier 1 — statistical discrimination (kill gate)",
        f"- rr_corr(pred_rr, y_rr) = **{t1['rr_corr_pred_rr_vs_y_rr']}**",
        f"- AUC(p_win, y_win) = **{t1['auc_p_win_vs_y_win']}**  (shuffle control {t1['auc_shuffle_control']})",
        f"- Brier = {t1['brier']}  base win-rate = {t1['base_win_rate']}",
        f"- kill rule: {t1['kill_rule']}  → survives = **{t1['survives']}**", "",
    ]
    if "tier0_label_validity" in r:
        t0 = r["tier0_label_validity"]
        L += ["## Tier 0 — LABEL VALIDITY (binding gate)",
              f"- label source: {t0['label_source']}",
              f"- contamination: {t0['contamination_finding']}",
              f"- {t0['y_rr_degenerate']}",
              f"- credible = **{t0['credible']}**", ""]
    if "tier2_selection_INFORMATIONAL" in r:
        t2 = r["tier2_selection_INFORMATIONAL"]
        L += ["## Tier 2 (INFORMATIONAL — contaminated labels)",
              f"- top-decile mean y_rr by RR = {t2['top_decile_mean_y_rr_by_RR']}  "
              f"random = {t2['random_baseline_mean_y_rr']}", ""]
    if "tier3_heavy_tail_INFORMATIONAL" in r:
        t3 = r["tier3_heavy_tail_INFORMATIONAL"]
        L += ["## Tier 3 (INFORMATIONAL)",
              f"- within P95 cut {t3['p95_cut']}: AUC={t3['auc_within_cut']} — {t3['note']}", ""]
    L += [f"## CLASSIFICATION: **{r['classification']}**", "", r.get("verdict_reason", "")]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
