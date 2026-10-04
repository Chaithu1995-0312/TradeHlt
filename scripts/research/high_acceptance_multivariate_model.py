"""
high_acceptance_multivariate_model.py — Phase 3: multivariate model over the structural
characteristics of high-acceptance candles (research, ontology-free).

Phase 2 contrasted one structural characteristic at a time. Several top-ranked ones there
(atr_zscore / atr_local / range_to_atr -- all volatility-derived; ret_20 / ret_50 /
sma20_slope_5 -- all momentum-derived) could just be echoes of one or two underlying factors
rather than independent information. This script fits both a linear model (Ridge, interpretable
coefficients directly comparable to phase 2's effect sizes) and a gradient-boosted model
(checks whether nonlinear/interaction structure captures meaningfully more than the linear one)
jointly across all structural characteristics, on the same N=500 population phase 2 built.

CORRECTNESS NOTE (the reason for the chronological split below): horizon N=500 means candidates
i and i+1 share 499 of their 500 forward bars, so acceptance_score_atr_norm is extremely
autocorrelated across neighboring rows -- the 46,775 rows are NOT 46,775 independent
observations (same effective-sample-size issue this repo's F-086 finding flags elsewhere). A
random train/holdout split would leak near-duplicate neighboring rows across the split and
produce an inflated, meaningless holdout score. This script uses a single CHRONOLOGICAL split
(first 80% = train, last 20% = holdout) with a 500-row EMBARGO dropped from the end of train so
no train candidate's forward window overlaps a holdout candidate's own window.

Still descriptive/exploratory: no classification, no trading-meaning verdict, no promotion
authority -- reports fit quality, feature importance, and multicollinearity only.

PURE READ-ONLY over phase-2 artifacts. No production/src/config/spine change.

Outputs:
    results/research/high_acceptance/xauusd_m15_multivariate_summary.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import RidgeCV
from sklearn.metrics import r2_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "research" / "high_acceptance"
FEATURES_PARQUET = OUT_DIR / "xauusd_m15_structural_features.parquet"
OUT_SUMMARY_JSON = OUT_DIR / "xauusd_m15_multivariate_summary.json"

HORIZON = 500
TRAIN_FRAC = 0.8
EMBARGO_ROWS = HORIZON
SEED = 1337
CORR_FLAG_THRESHOLD = 0.7
RIDGE_ALPHAS = np.logspace(-3, 3, 25)

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
TARGET_COL = "acceptance_score_atr_norm"


def load_matrix() -> pd.DataFrame:
    df = pd.read_parquet(FEATURES_PARQUET).sort_values("candidate_index").reset_index(drop=True)
    for col in BOOLEAN_COLS:
        df[col] = df[col].astype(float)
    return df


def chronological_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    n = len(df)
    split_at = int(n * TRAIN_FRAC)
    holdout = df.iloc[split_at:].reset_index(drop=True)
    train_raw = df.iloc[:split_at]
    train = train_raw.iloc[: max(0, len(train_raw) - EMBARGO_ROWS)].reset_index(drop=True)

    last_train_idx = int(train["candidate_index"].iloc[-1])
    first_holdout_idx = int(holdout["candidate_index"].iloc[0])
    no_overlap = (last_train_idx + HORIZON) < first_holdout_idx

    info = {
        "n_total": n,
        "n_train_before_embargo": len(train_raw),
        "n_embargo_dropped": len(train_raw) - len(train),
        "n_train": len(train),
        "n_holdout": len(holdout),
        "last_train_candidate_index": last_train_idx,
        "first_holdout_candidate_index": first_holdout_idx,
        "embargo_gap_bars": first_holdout_idx - last_train_idx,
        "no_forward_window_overlap": bool(no_overlap),
    }
    if not no_overlap:
        raise AssertionError(f"embargo insufficient: {info}")
    return train, holdout, info


def drop_nan_rows(train: pd.DataFrame, holdout: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    cols = FEATURE_COLS + [TARGET_COL]
    n_train_before, n_holdout_before = len(train), len(holdout)
    train_clean = train.dropna(subset=cols).reset_index(drop=True)
    holdout_clean = holdout.dropna(subset=cols).reset_index(drop=True)
    info = {
        "train_rows_dropped_for_nan": n_train_before - len(train_clean),
        "holdout_rows_dropped_for_nan": n_holdout_before - len(holdout_clean),
        "n_train_final": len(train_clean),
        "n_holdout_final": len(holdout_clean),
    }
    return train_clean, holdout_clean, info


def multicollinearity_flags(train: pd.DataFrame) -> list[dict]:
    corr = train[FEATURE_COLS].corr(method="pearson")
    flags = []
    cols = FEATURE_COLS
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if pd.notna(r) and abs(r) > CORR_FLAG_THRESHOLD:
                flags.append({"a": cols[i], "b": cols[j], "pearson_r": float(r)})
    flags.sort(key=lambda f: abs(f["pearson_r"]), reverse=True)
    return flags


def fit_ridge(train: pd.DataFrame, holdout: pd.DataFrame) -> dict:
    scaler = StandardScaler().fit(train[FEATURE_COLS])
    x_train = scaler.transform(train[FEATURE_COLS])
    x_holdout = scaler.transform(holdout[FEATURE_COLS])
    y_train = train[TARGET_COL].to_numpy()
    y_holdout = holdout[TARGET_COL].to_numpy()

    model = RidgeCV(alphas=RIDGE_ALPHAS, cv=5).fit(x_train, y_train)
    pred = model.predict(x_holdout)
    r2 = float(r2_score(y_holdout, pred))
    rho, p = spearmanr(pred, y_holdout)

    coefs = sorted(
        (
            {"feature": f, "standardized_coef": float(c)}
            for f, c in zip(FEATURE_COLS, model.coef_)
        ),
        key=lambda r: abs(r["standardized_coef"]),
        reverse=True,
    )
    return {
        "alpha_selected": float(model.alpha_),
        "holdout_r2": r2,
        "holdout_spearman_r": float(rho),
        "holdout_spearman_p": float(p),
        "coefficients_ranked": coefs,
    }


def fit_gbm(train: pd.DataFrame, holdout: pd.DataFrame) -> dict:
    x_train = train[FEATURE_COLS].to_numpy()
    x_holdout = holdout[FEATURE_COLS].to_numpy()
    y_train = train[TARGET_COL].to_numpy()
    y_holdout = holdout[TARGET_COL].to_numpy()

    model = HistGradientBoostingRegressor(random_state=SEED).fit(x_train, y_train)
    pred = model.predict(x_holdout)
    r2 = float(r2_score(y_holdout, pred))
    rho, p = spearmanr(pred, y_holdout)

    perm = permutation_importance(
        model, x_holdout, y_holdout, n_repeats=20, random_state=SEED, scoring="r2"
    )
    importances = sorted(
        (
            {
                "feature": f,
                "perm_importance_mean": float(m),
                "perm_importance_std": float(s),
            }
            for f, m, s in zip(FEATURE_COLS, perm.importances_mean, perm.importances_std)
        ),
        key=lambda r: r["perm_importance_mean"],
        reverse=True,
    )
    return {
        "holdout_r2": r2,
        "holdout_spearman_r": float(rho),
        "holdout_spearman_p": float(p),
        "permutation_importance_ranked": importances,
    }


def main() -> None:
    df = load_matrix()
    train, holdout, split_info = chronological_split(df)
    train, holdout, nan_info = drop_nan_rows(train, holdout)

    corr_flags = multicollinearity_flags(train)
    ridge = fit_ridge(train, holdout)
    gbm = fit_gbm(train, holdout)

    summary = {
        "horizon": HORIZON,
        "split": split_info,
        "nan_handling": nan_info,
        "multicollinearity_flags_abs_r_gt_0.7": corr_flags,
        "ridge": ridge,
        "gradient_boosting": gbm,
        "gbm_minus_ridge_holdout_r2": gbm["holdout_r2"] - ridge["holdout_r2"],
        "note": (
            "Fit quality and feature importance only. No classification, no trading meaning, "
            "no ontology vocabulary, no promotion authority. Chronological split with a "
            f"{EMBARGO_ROWS}-row embargo prevents forward-window leakage across train/holdout."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str))

    print(f"train={split_info['n_train']} (embargo dropped {split_info['n_embargo_dropped']}) "
          f"holdout={split_info['n_holdout']} no_overlap={split_info['no_forward_window_overlap']}")
    print(f"ridge  holdout R2={ridge['holdout_r2']:.4f} spearman={ridge['holdout_spearman_r']:.4f}")
    print(f"gbm    holdout R2={gbm['holdout_r2']:.4f} spearman={gbm['holdout_spearman_r']:.4f}")
    print(f"gbm - ridge R2 = {summary['gbm_minus_ridge_holdout_r2']:.4f}")
    print(f"wrote: {OUT_SUMMARY_JSON}")


if __name__ == "__main__":
    sys.exit(main())
