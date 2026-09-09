"""
high_acceptance_activity_conditioning.py — Phase 3.5 Studies A/B/C: condition on the activity
state instead of predicting through it (research, ontology-free).

WHY. Study 0.5 showed volatility / volume / candle-geometry are not three predictors but three
noisy sensors of one hidden variable (each SOLO reproduces 79-97% of the full model, none is
necessary). Study 0.6 showed the model's apparent skill collapses ~80% when cross-period drift is
removed (global +0.216 -> within-500-bar-block +0.040, NEGATIVE in two of three regimes). So the
model was estimating a slow ACTIVITY STATE, not discriminating between candles.

This script removes that dominant latent by stratifying on it, then asks what is left.

  STUDY A  Inside a fixed activity quintile, does ANY candle feature matter?
           Per-feature Spearman within each quintile, Benjamini-Hochberg FDR over all
           22 features x 5 quintiles = 110 tests (without it, ~5 "significant" results are
           expected by chance alone), plus a Ridge refit WITHIN each quintile and the
           within-block variant of both.

  STUDY B  Within activity state, does RECLAIM SPEED differ? Uses bars_until_first_reclaim
           (phase-1 survival_bars at N=500) rather than the acceptance score, because acceptance
           itself is far too sparse (30 events). Censoring is negligible and reported: only the
           handful never reclaimed inside 500 bars are right-censored.

  STUDY C  The 30 true acceptance events: what activity state were they born in? Frequency
           table vs the uniform expectation, with an exact test. If they concentrate in one
           state, that state is the parent variable.

ACTIVITY INDEX. Built ONLY from proxies already identified — no new features engineered. Primary
construction is the mean of TRAILING z-scores (window 480, matching Study 0.6's tercile window)
of atr_local, volume_raw and range; quintiles are assigned by TRAILING percentile rank over 2000
bars. Both steps are backward-only, so the stratification carries no lookahead. A PC1 index over
the same three sensor groups is computed as a cross-check and their rank agreement is reported —
if the two disagree the stratification is not measuring a single coherent state.

No new model families, no clustering, no new candle features.

Still descriptive: no classification, no trading meaning, no promotion authority.

PURE READ-ONLY over phase-1/2 artifacts. No production/src/config/spine change.

Outputs:
    results/research/high_acceptance/xauusd_m15_activity_conditioning.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chisquare, kruskal, spearmanr
from sklearn.decomposition import PCA
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "research" / "high_acceptance"
RAW_PARQUET = OUT_DIR / "xauusd_m15.parquet"
CANDIDATES_PARQUET = OUT_DIR / "xauusd_m15_candidates.parquet"
FEATURES_PARQUET = OUT_DIR / "xauusd_m15_structural_features.parquet"
OUT_JSON = OUT_DIR / "xauusd_m15_activity_conditioning.json"

HORIZON = 500
TRAIN_FRAC = 0.8
EMBARGO_ROWS = HORIZON
RIDGE_ALPHAS = np.logspace(-3, 3, 25)
Z_WINDOW = 480          # matches Study 0.6 / regime_observer tercile window
PCTL_WINDOW = 2000      # trailing window for quintile assignment
N_QUANTILES = 5
FDR_ALPHA = 0.05

SENSOR_COLS = ["atr_local", "volume_raw", "range"]          # the three redundant sensors
SENSOR_GROUP_COLS = [                                        # full sensor set, for the PC1 check
    "atr_local", "atr_zscore", "range_to_atr", "volume_raw", "volume_zscore",
    "range", "body",
]

CONTINUOUS_COLS = [
    "range", "body", "body_frac", "upper_wick_frac", "lower_wick_frac",
    "close_position_in_range", "volume_raw", "volume_zscore",
    "atr_local", "atr_zscore", "range_to_atr",
    "ret_5", "ret_20", "ret_50", "dist_from_sma20", "sma20_slope_5",
    "bars_since_prior_higher_high",
]
BOOLEAN_COLS = [
    "direction_up", "is_new_high_20", "is_new_high_50", "is_new_high_100",
    "prior_candidate_accepted",
]
FEATURE_COLS = CONTINUOUS_COLS + BOOLEAN_COLS
TARGET = "acceptance_score"      # raw price units — Study 0 showed the normalized ones are artifact-prone


# --------------------------------------------------------------------------- activity state

def build_activity_index(df: pd.DataFrame) -> pd.DataFrame:
    """Trailing-z mean of the three sensors, then trailing-percentile quintiles. No lookahead."""
    z_parts = []
    for col in SENSOR_COLS:
        s = df[col]
        roll = s.rolling(Z_WINDOW, min_periods=Z_WINDOW)
        z_parts.append((s - roll.mean()) / roll.std())
    df["activity_index"] = pd.concat(z_parts, axis=1).mean(axis=1)

    # Trailing percentile rank of the index within its own prior PCTL_WINDOW bars.
    df["activity_pctl"] = (
        df["activity_index"]
        .rolling(PCTL_WINDOW, min_periods=PCTL_WINDOW // 4)
        .apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)
    )
    df["activity_q"] = pd.cut(
        df["activity_pctl"], bins=np.linspace(0, 1, N_QUANTILES + 1),
        labels=[f"Q{i}" for i in range(1, N_QUANTILES + 1)], include_lowest=True,
    ).astype("object")
    return df


def pc1_crosscheck(df: pd.DataFrame) -> dict:
    """PC1 over the full sensor set, as an independent estimate of the same latent."""
    sub = df[SENSOR_GROUP_COLS].dropna()
    x = StandardScaler().fit_transform(sub)
    pca = PCA(n_components=3).fit(x)
    pc1 = pca.transform(x)[:, 0]
    joined = df.loc[sub.index, ["activity_index"]].assign(pc1=pc1).dropna()
    r, _ = spearmanr(joined["activity_index"], joined["pc1"])
    return {
        "explained_variance_ratio_pc1": float(pca.explained_variance_ratio_[0]),
        "explained_variance_ratio_first3": [float(v) for v in pca.explained_variance_ratio_],
        "spearman_index_vs_pc1": float(abs(r)),
        "n": int(len(joined)),
        "note": (
            "High PC1 variance share + high |rank agreement| => the sensors do describe one "
            "coherent latent and the quintiles are measuring it."
        ),
    }


# --------------------------------------------------------------------------- helpers

def benjamini_hochberg(pvals: list[float], alpha: float = FDR_ALPHA) -> list[bool]:
    n = len(pvals)
    order = np.argsort(pvals)
    passed = np.zeros(n, dtype=bool)
    thresholds = (np.arange(1, n + 1) / n) * alpha
    sorted_p = np.array(pvals)[order]
    below = sorted_p <= thresholds
    if below.any():
        cutoff = np.max(np.where(below)[0])
        passed[order[: cutoff + 1]] = True
    return passed.tolist()


def _rho(a, b):
    if len(a) < 3:
        return None, None
    r, p = spearmanr(a, b)
    return (None, None) if np.isnan(r) else (float(r), float(p))


def within_block_rho(pred: np.ndarray, actual: np.ndarray, block: int = HORIZON):
    rhos, ns = [], []
    for s in range(0, len(pred), block):
        r, _ = _rho(pred[s:s + block], actual[s:s + block])
        if r is not None:
            rhos.append(r)
            ns.append(len(pred[s:s + block]))
    return float(np.average(rhos, weights=ns)) if rhos else None


# --------------------------------------------------------------------------- Study A

def study_a(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=FEATURE_COLS + [TARGET, "activity_q"]).reset_index(drop=True)

    tests = []
    for q in [f"Q{i}" for i in range(1, N_QUANTILES + 1)]:
        sub = d[d["activity_q"] == q]
        for col in FEATURE_COLS:
            r, p = _rho(sub[col], sub[TARGET])
            if r is None:
                continue
            tests.append({"quantile": q, "feature": col, "n": int(len(sub)),
                          "spearman_r": r, "p": p})
    passed = benjamini_hochberg([t["p"] for t in tests])
    for t, ok in zip(tests, passed):
        t["survives_bh_fdr"] = bool(ok)
    tests.sort(key=lambda t: abs(t["spearman_r"]), reverse=True)
    survivors = [t for t in tests if t["survives_bh_fdr"]]

    # Ridge refit WITHIN each quintile: chronological split + embargo inside the quintile.
    per_q_model = {}
    for q in [f"Q{i}" for i in range(1, N_QUANTILES + 1)]:
        sub = d[d["activity_q"] == q].sort_values("candidate_index").reset_index(drop=True)
        at = int(len(sub) * TRAIN_FRAC)
        tr, ho = sub.iloc[: max(0, at - EMBARGO_ROWS)], sub.iloc[at:]
        if len(tr) < 500 or len(ho) < 200:
            per_q_model[q] = {"n_train": len(tr), "n_holdout": len(ho), "skipped": True}
            continue
        scaler = StandardScaler().fit(tr[FEATURE_COLS])
        model = RidgeCV(alphas=RIDGE_ALPHAS, cv=5).fit(scaler.transform(tr[FEATURE_COLS]), tr[TARGET])
        pred = model.predict(scaler.transform(ho[FEATURE_COLS]))
        actual = ho[TARGET].to_numpy()
        r, p = _rho(pred, actual)
        per_q_model[q] = {
            "n_train": int(len(tr)), "n_holdout": int(len(ho)),
            "holdout_spearman_r": r, "holdout_spearman_p": p,
            "within_block_spearman": within_block_rho(pred, actual),
        }

    return {
        "n_tests": len(tests),
        "bh_alpha": FDR_ALPHA,
        "n_surviving_bh_fdr": len(survivors),
        "surviving_tests": survivors[:40],
        "top_20_by_abs_rho": tests[:20],
        "within_quantile_ridge": per_q_model,
        "reading": (
            "If n_surviving_bh_fdr is ~0 and the within-quantile Ridge holdout rho collapses "
            "toward 0, then holding the activity state fixed leaves no candle-level signal."
        ),
    }


# --------------------------------------------------------------------------- Study B

def study_b(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["activity_q", "survival_bars"]).reset_index(drop=True)
    groups, table = [], {}
    for q in [f"Q{i}" for i in range(1, N_QUANTILES + 1)]:
        v = d.loc[d["activity_q"] == q, "survival_bars"].to_numpy(dtype=float)
        if len(v) == 0:
            continue
        groups.append(v)
        table[q] = {
            "n": int(len(v)),
            "mean_bars_until_first_reclaim": float(np.mean(v)),
            "median": float(np.median(v)),
            "p10": float(np.percentile(v, 10)),
            "p25": float(np.percentile(v, 25)),
            "p75": float(np.percentile(v, 75)),
            "p90": float(np.percentile(v, 90)),
            "n_censored_at_horizon": int((v >= HORIZON).sum()),
        }
    stat, p = kruskal(*groups) if len(groups) > 1 else (float("nan"), float("nan"))
    q_keys = list(table.keys())
    return {
        "target": "survival_bars at N=500 (bars until first reclaim; right-censored at 500)",
        "by_activity_quantile": table,
        "kruskal_wallis": {"H": float(stat), "p": float(p)},
        "monotone_in_activity": (
            [table[q]["median"] for q in q_keys] == sorted([table[q]["median"] for q in q_keys])
            or [table[q]["median"] for q in q_keys] == sorted([table[q]["median"] for q in q_keys], reverse=True)
        ),
        "caveat": (
            "Higher activity mechanically implies larger moves in BOTH directions, so a faster "
            "reclaim in high-activity states is expected, not a discovery. Reported as observed."
        ),
    }


# --------------------------------------------------------------------------- Study C

def study_c(df: pd.DataFrame, persistent: pd.Series) -> dict:
    d = df.copy()
    d["persistent_score"] = d["candidate_index"].map(persistent).fillna(0).astype(int)
    events = d[d["persistent_score"] >= 1].dropna(subset=["activity_q"])
    population = d.dropna(subset=["activity_q"])

    q_labels = [f"Q{i}" for i in range(1, N_QUANTILES + 1)]
    obs = np.array([int((events["activity_q"] == q).sum()) for q in q_labels], dtype=float)
    pop_frac = np.array([float((population["activity_q"] == q).mean()) for q in q_labels])
    exp = pop_frac * obs.sum()

    chi = chisquare(obs, f_exp=exp) if obs.sum() > 0 and (exp > 0).all() else None
    return {
        "n_events_total": int((d["persistent_score"] >= 1).sum()),
        "n_events_with_activity_label": int(len(events)),
        "quantile_counts": {q: int(o) for q, o in zip(q_labels, obs)},
        "expected_if_uniform_over_population": {q: round(float(e), 2) for q, e in zip(q_labels, exp)},
        "population_fraction": {q: round(float(f), 4) for q, f in zip(q_labels, pop_frac)},
        "chi_square": (None if chi is None else {"stat": float(chi.statistic), "p": float(chi.pvalue)}),
        "events": events[
            ["candidate_ts", "candidate_index", "persistent_score", "activity_index",
             "activity_pctl", "activity_q", "acceptance_score", "survival_bars"]
        ].assign(candidate_ts=lambda x: x["candidate_ts"].astype(str)).to_dict("records"),
        "caveat": (
            "n=30 total. Descriptive census plus one omnibus test; chi-square is approximate at "
            "these counts and no per-cell claim is made."
        ),
    }


# --------------------------------------------------------------------------- main

def persistent_scores() -> pd.Series:
    c = pd.read_parquet(CANDIDATES_PARQUET)
    piv = c.pivot_table(index="candidate_index", columns="N", values="acceptance_score",
                        aggfunc="first").dropna()
    return (piv > 0).sum(axis=1)


def main() -> None:
    df = pd.read_parquet(FEATURES_PARQUET).sort_values("candidate_index").reset_index(drop=True)
    for col in BOOLEAN_COLS:
        df[col] = df[col].astype(float)
    df = build_activity_index(df)

    summary = {
        "horizon": HORIZON,
        "target": TARGET,
        "activity_index": {
            "sensors": SENSOR_COLS,
            "z_window": Z_WINDOW,
            "percentile_window": PCTL_WINDOW,
            "n_quantiles": N_QUANTILES,
            "construction": "trailing z-mean of sensors, trailing percentile rank -> quintile; backward-only",
            "pc1_crosscheck": pc1_crosscheck(df),
            "labelled_rows": int(df["activity_q"].notna().sum()),
        },
        "study_a_within_state_features": study_a(df),
        "study_b_reclaim_speed": study_b(df),
        "study_c_event_birth_state": study_c(df, persistent_scores()),
        "note": (
            "Conditioning study. No new candle features, no new model families, no clustering. "
            "Descriptive only: no classification, no trading meaning, no promotion authority."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2, default=str))

    ai = summary["activity_index"]
    print(f"activity index: labelled {ai['labelled_rows']} rows | "
          f"PC1 var={ai['pc1_crosscheck']['explained_variance_ratio_pc1']:.3f} "
          f"agreement={ai['pc1_crosscheck']['spearman_index_vs_pc1']:.3f}")

    a = summary["study_a_within_state_features"]
    print(f"\nSTUDY A: {a['n_tests']} tests, {a['n_surviving_bh_fdr']} survive BH-FDR @ {FDR_ALPHA}")
    print("  within-quantile Ridge holdout rho:")
    for q, m in a["within_quantile_ridge"].items():
        if m.get("skipped"):
            print(f"    {q} skipped (n_train={m['n_train']})")
        else:
            wb = m["within_block_spearman"]
            print(f"    {q} n_ho={m['n_holdout']:5d} rho={m['holdout_spearman_r']:+.4f} "
                  f"within_block={'n/a' if wb is None else f'{wb:+.4f}'}")
    print("  top 5 |rho| within-state feature tests:")
    for t in a["top_20_by_abs_rho"][:5]:
        print(f"    {t['quantile']} {t['feature']:28s} rho={t['spearman_r']:+.4f} "
              f"p={t['p']:.2e} bh={t['survives_bh_fdr']}")

    b = summary["study_b_reclaim_speed"]
    print(f"\nSTUDY B: bars until first reclaim by activity quintile "
          f"(Kruskal H={b['kruskal_wallis']['H']:.1f} p={b['kruskal_wallis']['p']:.2e})")
    for q, v in b["by_activity_quantile"].items():
        print(f"    {q} n={v['n']:6d} median={v['median']:6.1f} mean={v['mean_bars_until_first_reclaim']:7.2f} "
              f"p90={v['p90']:6.1f} censored={v['n_censored_at_horizon']}")

    c = summary["study_c_event_birth_state"]
    print(f"\nSTUDY C: {c['n_events_with_activity_label']} of {c['n_events_total']} events labelled")
    print(f"    observed {c['quantile_counts']}")
    print(f"    expected {c['expected_if_uniform_over_population']}")
    if c["chi_square"]:
        print(f"    chi2={c['chi_square']['stat']:.2f} p={c['chi_square']['p']:.4f}")
    print(f"\nwrote: {OUT_JSON}")


if __name__ == "__main__":
    sys.exit(main())
