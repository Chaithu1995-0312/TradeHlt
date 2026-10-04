"""
high_acceptance_normalization_control.py — Phase 3.5 Study 0: is the volatility signal real, or
a property of the metric's denominator? (research, ontology-free)

WHY THIS EXISTS. Phases 2 and 3 all scored against the SAME ATR-normalized target
(acceptance_score_atr_norm = (future_min_low - high) / atr). So the phase-2 univariate contrast,
the phase-3 Ridge coefficient and the phase-3 GBM permutation importance are ONE measurement
repeated three times, not three independent confirmations -- and `atr_zscore` topping all three
is therefore much weaker evidence than it looks. A planning-time check found the sign reverses
when the denominator changes:

    spearman(atr_zscore, acceptance_score_atr_norm) = +0.218   <- the phase-3 headline
    spearman(atr_zscore, acceptance_score RAW)      = -0.052   <- same predictor, no denominator

with spearman(atr_local, raw score) = -0.486 (volatile markets travel further, so the excursion
below the high is DEEPER -- the mundane relationship) and spearman(atr_now, atr_500_later) =
+0.64 (current ATR mean-reverts over the horizon). Dividing by a currently-elevated ATR that then
mean-reverts can therefore manufacture the positive association on its own.

This script settles it by running the identical analysis against THREE targets:

    raw          acceptance_score                (price units, no denominator)
    atr_norm     acceptance_score_atr_norm       (the existing phase-2/3 target)
    stable_norm  acceptance_score_stable_norm    (divided by a forward-blind LONG-RUN median ATR,
                                                  which does not track the candidate bar's own
                                                  transient volatility)

A feature whose sign or rank survives all three is denominator-independent. One that does not is
reported as denominator-dependent -- and that is the finding, not a footnote.

Reuses the phase-3 chronological split + 500-row embargo verbatim (adjacent candidates share 499
of 500 forward bars, so a random split would leak).

Still descriptive: no classification, no trading meaning, no promotion authority.

PURE READ-ONLY over phase-1/2 artifacts. No production/src/config/spine change.

Outputs:
    results/research/high_acceptance/xauusd_m15_normalization_control.json
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
RAW_PARQUET = OUT_DIR / "xauusd_m15.parquet"
FEATURES_PARQUET = OUT_DIR / "xauusd_m15_structural_features.parquet"
OUT_JSON = OUT_DIR / "xauusd_m15_normalization_control.json"

HORIZON = 500
TRAIN_FRAC = 0.8
EMBARGO_ROWS = HORIZON
SEED = 1337
RIDGE_ALPHAS = np.logspace(-3, 3, 25)

# Long-run, forward-blind denominator. Deliberately long (2000 bars ~ 3 weeks of M15) so it
# reflects the instrument's standing volatility scale rather than the candidate bar's transient
# one -- that transience is exactly the suspected artifact.
STABLE_ATR_WINDOW = 2000
STABLE_ATR_MIN_PERIODS = 500

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

TARGETS = ["acceptance_score", "acceptance_score_atr_norm", "acceptance_score_stable_norm"]
TARGET_LABELS = {
    "acceptance_score": "raw (price units, no denominator)",
    "acceptance_score_atr_norm": "atr_norm (existing phase-2/3 target)",
    "acceptance_score_stable_norm": f"stable_norm (median ATR over prior {STABLE_ATR_WINDOW} bars)",
}


def local_atr(raw: pd.DataFrame) -> pd.Series:
    high, low, close = raw["high"], raw["low"], raw["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(14, min_periods=14).mean()


def load_with_stable_target() -> pd.DataFrame:
    df = pd.read_parquet(FEATURES_PARQUET).sort_values("candidate_index").reset_index(drop=True)
    raw = pd.read_parquet(RAW_PARQUET)

    atr = local_atr(raw)
    # Forward-blind by construction: rolling() only ever looks backward.
    stable = atr.rolling(STABLE_ATR_WINDOW, min_periods=STABLE_ATR_MIN_PERIODS).median()
    stable_at_candidate = stable.reindex(df["candidate_index"].to_numpy()).to_numpy()

    with np.errstate(divide="ignore", invalid="ignore"):
        df["acceptance_score_stable_norm"] = np.where(
            stable_at_candidate > 0, df["acceptance_score"] / stable_at_candidate, np.nan
        )
    df["_stable_denominator"] = stable_at_candidate
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
    if not (last_train_idx + HORIZON) < first_holdout_idx:
        raise AssertionError("embargo insufficient — forward windows overlap across the split")
    return train, holdout, {
        "n_total": n,
        "n_train": len(train),
        "n_holdout": len(holdout),
        "n_embargo_dropped": len(train_raw) - len(train),
        "embargo_gap_bars": first_holdout_idx - last_train_idx,
        "no_forward_window_overlap": True,
    }


def pooled_spearman(df: pd.DataFrame, target: str) -> dict:
    out = {}
    for col in FEATURE_COLS:
        sub = df[[col, target]].dropna()
        if len(sub) < 3:
            out[col] = {"n": len(sub), "spearman_r": None, "p": None}
            continue
        r, p = spearmanr(sub[col], sub[target])
        out[col] = {"n": int(len(sub)), "spearman_r": float(r), "p": float(p)}
    return out


def fit_models(train: pd.DataFrame, holdout: pd.DataFrame, target: str) -> dict:
    cols = FEATURE_COLS + [target]
    tr = train.dropna(subset=cols)
    ho = holdout.dropna(subset=cols)

    scaler = StandardScaler().fit(tr[FEATURE_COLS])
    x_tr, x_ho = scaler.transform(tr[FEATURE_COLS]), scaler.transform(ho[FEATURE_COLS])
    y_tr, y_ho = tr[target].to_numpy(), ho[target].to_numpy()

    ridge = RidgeCV(alphas=RIDGE_ALPHAS, cv=5).fit(x_tr, y_tr)
    r_pred = ridge.predict(x_ho)
    r_rho, _ = spearmanr(r_pred, y_ho)
    ridge_coefs = sorted(
        ({"feature": f, "standardized_coef": float(c)} for f, c in zip(FEATURE_COLS, ridge.coef_)),
        key=lambda r: abs(r["standardized_coef"]),
        reverse=True,
    )

    gbm = HistGradientBoostingRegressor(random_state=SEED).fit(tr[FEATURE_COLS].to_numpy(), y_tr)
    g_pred = gbm.predict(ho[FEATURE_COLS].to_numpy())
    g_rho, _ = spearmanr(g_pred, y_ho)
    perm = permutation_importance(
        gbm, ho[FEATURE_COLS].to_numpy(), y_ho, n_repeats=20, random_state=SEED, scoring="r2"
    )
    gbm_imp = sorted(
        (
            {"feature": f, "perm_importance_mean": float(m)}
            for f, m in zip(FEATURE_COLS, perm.importances_mean)
        ),
        key=lambda r: r["perm_importance_mean"],
        reverse=True,
    )

    return {
        "n_train": int(len(tr)),
        "n_holdout": int(len(ho)),
        "ridge": {
            "alpha_selected": float(ridge.alpha_),
            "holdout_r2": float(r2_score(y_ho, r_pred)),
            "holdout_spearman_r": float(r_rho),
            "coefficients_ranked": ridge_coefs,
        },
        "gradient_boosting": {
            "holdout_r2": float(r2_score(y_ho, g_pred)),
            "holdout_spearman_r": float(g_rho),
            "permutation_importance_ranked": gbm_imp,
        },
    }


def stability_table(per_target: dict) -> list[dict]:
    """Per feature: does the pooled-Spearman sign and the Ridge-coef sign hold across denominators?"""
    rows = []
    for col in FEATURE_COLS:
        sp = {t: per_target[t]["pooled_spearman"][col]["spearman_r"] for t in TARGETS}
        ridge_map = {
            t: {c["feature"]: c["standardized_coef"] for c in per_target[t]["models"]["ridge"]["coefficients_ranked"]}
            for t in TARGETS
        }
        rc = {t: ridge_map[t][col] for t in TARGETS}

        sp_signs = {np.sign(v) for v in sp.values() if v is not None and not np.isnan(v)}
        rc_signs = {np.sign(v) for v in rc.values() if v is not None and not np.isnan(v)}
        rows.append({
            "feature": col,
            "spearman_by_target": {t: (None if sp[t] is None else round(sp[t], 4)) for t in TARGETS},
            "ridge_coef_by_target": {t: round(rc[t], 4) for t in TARGETS},
            "spearman_sign_stable": len(sp_signs) <= 1,
            "ridge_sign_stable": len(rc_signs) <= 1,
            "sign_stable_across_denominators": len(sp_signs) <= 1 and len(rc_signs) <= 1,
            "max_abs_spearman": max((abs(v) for v in sp.values() if v is not None), default=None),
        })
    rows.sort(key=lambda r: (r["max_abs_spearman"] or 0), reverse=True)
    return rows


def main() -> None:
    df = load_with_stable_target()
    train, holdout, split_info = chronological_split(df)

    per_target = {}
    for t in TARGETS:
        per_target[t] = {
            "label": TARGET_LABELS[t],
            "pooled_spearman": pooled_spearman(df, t),
            "models": fit_models(train, holdout, t),
        }

    stability = stability_table(per_target)
    unstable = [r["feature"] for r in stability if not r["sign_stable_across_denominators"]]

    summary = {
        "horizon": HORIZON,
        "split": split_info,
        "stable_denominator": {
            "window_bars": STABLE_ATR_WINDOW,
            "min_periods": STABLE_ATR_MIN_PERIODS,
            "construction": "rolling median of ATR(14) over the PRIOR window — backward-only, forward-blind",
        },
        "targets": {t: TARGET_LABELS[t] for t in TARGETS},
        "per_target": per_target,
        "sign_stability_ranked": stability,
        "denominator_dependent_features": unstable,
        "note": (
            "Fit quality, correlation and feature ranking only. A feature listed in "
            "denominator_dependent_features changes sign when the metric's denominator changes, "
            "and any claim resting on it is a claim about the measurement, not the market. "
            "No classification, no trading meaning, no promotion authority."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2, default=str))

    print(f"split: train={split_info['n_train']} holdout={split_info['n_holdout']} "
          f"(embargo {split_info['n_embargo_dropped']})")
    for t in TARGETS:
        m = per_target[t]["models"]
        sp = per_target[t]["pooled_spearman"]["atr_zscore"]["spearman_r"]
        print(f"\n{t}  [{TARGET_LABELS[t]}]")
        print(f"  pooled spearman(atr_zscore) = {sp:+.4f}")
        print(f"  ridge  holdout R2={m['ridge']['holdout_r2']:+.4f} "
              f"spearman={m['ridge']['holdout_spearman_r']:+.4f} "
              f"| top coef: {m['ridge']['coefficients_ranked'][0]['feature']} "
              f"({m['ridge']['coefficients_ranked'][0]['standardized_coef']:+.3f})")
        print(f"  gbm    holdout R2={m['gradient_boosting']['holdout_r2']:+.4f} "
              f"spearman={m['gradient_boosting']['holdout_spearman_r']:+.4f} "
              f"| top perm: {m['gradient_boosting']['permutation_importance_ranked'][0]['feature']}")
    print(f"\ndenominator-dependent features ({len(unstable)}): {unstable}")
    print(f"wrote: {OUT_JSON}")


if __name__ == "__main__":
    sys.exit(main())
