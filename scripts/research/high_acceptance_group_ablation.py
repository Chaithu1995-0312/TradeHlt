"""
high_acceptance_group_ablation.py — Phase 3.5 Study 0.5: feature-group ablation on the Ridge
model (research, ontology-free).

QUESTION. Study 0 showed the only thing that survived a denominator swap is the Ridge holdout
rank-correlation (+0.251 raw / +0.249 atr_norm / +0.207 stable_norm), while 16 of 22 features
are denominator-dependent and the 6 sign-stable ones are all tiny (|rho| <= 0.042). So what
carries the surviving rank signal?

METHOD. No new features, no new models, no clustering. The existing 22 phase-2 features are
partitioned into 6 semantic groups, and the existing Ridge is refit under two ablations:

    LOGO  leave-one-group-out : all features EXCEPT group G  -> how much is lost without G
    SOLO  only-one-group      : ONLY group G                 -> how much G carries alone

Run against all three Study-0 targets so the ablation conclusion is itself checked for
denominator independence. Split + 500-row embargo reused verbatim from phase 3.

READING THE RESULT.
    concentrated -> one group's SOLO ~= the full model and its LOGO collapses
    distributed  -> every SOLO is a fraction of full, every LOGO barely moves
                    (redundancy: groups substitute for each other)

Still descriptive: no classification, no trading meaning, no promotion authority.

PURE READ-ONLY over phase-1/2 artifacts. No production/src/config/spine change.

Outputs:
    results/research/high_acceptance/xauusd_m15_group_ablation.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.metrics import r2_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "research" / "high_acceptance"
RAW_PARQUET = OUT_DIR / "xauusd_m15.parquet"
FEATURES_PARQUET = OUT_DIR / "xauusd_m15_structural_features.parquet"
OUT_JSON = OUT_DIR / "xauusd_m15_group_ablation.json"

HORIZON = 500
TRAIN_FRAC = 0.8
EMBARGO_ROWS = HORIZON
RIDGE_ALPHAS = np.logspace(-3, 3, 25)
STABLE_ATR_WINDOW = 2000
STABLE_ATR_MIN_PERIODS = 500

FEATURE_GROUPS: dict[str, list[str]] = {
    "volatility": ["atr_local", "atr_zscore", "range_to_atr"],
    "candle_geometry": [
        "range", "body", "body_frac", "upper_wick_frac", "lower_wick_frac",
        "close_position_in_range", "direction_up",
    ],
    "volume": ["volume_raw", "volume_zscore"],
    "momentum": ["ret_5", "ret_20", "ret_50", "dist_from_sma20", "sma20_slope_5"],
    "local_extremum": [
        "is_new_high_20", "is_new_high_50", "is_new_high_100", "bars_since_prior_higher_high",
    ],
    "persistence": ["prior_candidate_accepted"],
}
ALL_FEATURES = [f for g in FEATURE_GROUPS.values() for f in g]
BOOLEAN_COLS = [
    "direction_up", "is_new_high_20", "is_new_high_50", "is_new_high_100",
    "prior_candidate_accepted",
]
TARGETS = ["acceptance_score", "acceptance_score_atr_norm", "acceptance_score_stable_norm"]
PRIMARY_TARGET = "acceptance_score"  # raw price units — Study 0 showed the others are artifact-prone


def local_atr(raw: pd.DataFrame) -> pd.Series:
    high, low, close = raw["high"], raw["low"], raw["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(14, min_periods=14).mean()


def load_frame() -> pd.DataFrame:
    df = pd.read_parquet(FEATURES_PARQUET).sort_values("candidate_index").reset_index(drop=True)
    raw = pd.read_parquet(RAW_PARQUET)
    stable = local_atr(raw).rolling(
        STABLE_ATR_WINDOW, min_periods=STABLE_ATR_MIN_PERIODS
    ).median()
    denom = stable.reindex(df["candidate_index"].to_numpy()).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        df["acceptance_score_stable_norm"] = np.where(
            denom > 0, df["acceptance_score"] / denom, np.nan
        )
    for col in BOOLEAN_COLS:
        df[col] = df[col].astype(float)
    return df


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(df)
    at = int(n * TRAIN_FRAC)
    holdout = df.iloc[at:].reset_index(drop=True)
    train_raw = df.iloc[:at]
    train = train_raw.iloc[: len(train_raw) - EMBARGO_ROWS].reset_index(drop=True)
    if not int(train["candidate_index"].iloc[-1]) + HORIZON < int(holdout["candidate_index"].iloc[0]):
        raise AssertionError("embargo insufficient — forward windows overlap the split")
    return train, holdout


def fit_ridge(train: pd.DataFrame, holdout: pd.DataFrame, feats: list[str], target: str) -> dict:
    cols = feats + [target]
    tr, ho = train.dropna(subset=cols), holdout.dropna(subset=cols)
    scaler = StandardScaler().fit(tr[feats])
    model = RidgeCV(alphas=RIDGE_ALPHAS, cv=5).fit(scaler.transform(tr[feats]), tr[target])
    pred = model.predict(scaler.transform(ho[feats]))
    rho, p = spearmanr(pred, ho[target])
    return {
        "n_features": len(feats),
        "holdout_spearman_r": float(rho),
        "holdout_spearman_p": float(p),
        "holdout_r2": float(r2_score(ho[target], pred)),
    }


def ablate(train: pd.DataFrame, holdout: pd.DataFrame, target: str) -> dict:
    full = fit_ridge(train, holdout, ALL_FEATURES, target)
    logo, solo = {}, {}
    for name, feats in FEATURE_GROUPS.items():
        rest = [f for f in ALL_FEATURES if f not in feats]
        r_logo = fit_ridge(train, holdout, rest, target)
        r_solo = fit_ridge(train, holdout, feats, target)
        r_logo["delta_vs_full_spearman"] = r_logo["holdout_spearman_r"] - full["holdout_spearman_r"]
        r_solo["frac_of_full_spearman"] = (
            r_solo["holdout_spearman_r"] / full["holdout_spearman_r"]
            if full["holdout_spearman_r"] else None
        )
        logo[name], solo[name] = r_logo, r_solo

    worst_logo = min(logo.items(), key=lambda kv: kv[1]["delta_vs_full_spearman"])
    best_solo = max(solo.items(), key=lambda kv: kv[1]["holdout_spearman_r"])
    return {
        "full_model": full,
        "leave_one_group_out": logo,
        "solo_group": solo,
        "largest_logo_drop": {"group": worst_logo[0], "delta": worst_logo[1]["delta_vs_full_spearman"]},
        "best_solo_group": {
            "group": best_solo[0],
            "spearman": best_solo[1]["holdout_spearman_r"],
            "frac_of_full": best_solo[1]["frac_of_full_spearman"],
        },
    }


def verdict(res: dict) -> dict:
    """Concentrated vs distributed, on pre-stated numeric criteria."""
    full = res["full_model"]["holdout_spearman_r"]
    max_drop = -res["largest_logo_drop"]["delta"]          # positive magnitude of worst loss
    best_solo_frac = res["best_solo_group"]["frac_of_full"] or 0.0
    if best_solo_frac >= 0.80 and max_drop >= 0.5 * abs(full):
        label = "CONCENTRATED"
    elif best_solo_frac < 0.80 and max_drop < 0.25 * abs(full):
        label = "DISTRIBUTED_REDUNDANT"
    else:
        label = "MIXED"
    return {
        "label": label,
        "full_spearman": full,
        "largest_logo_drop_magnitude": max_drop,
        "best_solo_fraction_of_full": best_solo_frac,
        "criteria": (
            "CONCENTRATED if best SOLO >= 80% of full AND worst LOGO loses >= 50% of full; "
            "DISTRIBUTED_REDUNDANT if best SOLO < 80% AND worst LOGO loses < 25%; else MIXED"
        ),
    }


def main() -> None:
    df = load_frame()
    train, holdout = split(df)

    per_target = {}
    for t in TARGETS:
        res = ablate(train, holdout, t)
        res["verdict"] = verdict(res)
        per_target[t] = res

    summary = {
        "horizon": HORIZON,
        "primary_target": PRIMARY_TARGET,
        "feature_groups": FEATURE_GROUPS,
        "n_train": int(len(train)),
        "n_holdout": int(len(holdout)),
        "per_target": per_target,
        "note": (
            "Ablation of the EXISTING Ridge over the EXISTING phase-2 features. No new features, "
            "no new model families, no clustering. Descriptive only: no classification, no "
            "trading meaning, no promotion authority."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2, default=str))

    for t in TARGETS:
        r = per_target[t]
        star = "  <-- PRIMARY" if t == PRIMARY_TARGET else ""
        print(f"\n=== {t}{star}")
        print(f"  full model holdout spearman = {r['full_model']['holdout_spearman_r']:+.4f}")
        print(f"  {'group':18s} {'SOLO rho':>10s} {'frac_full':>10s} {'LOGO rho':>10s} {'delta':>9s}")
        for g in FEATURE_GROUPS:
            s, l = r["solo_group"][g], r["leave_one_group_out"][g]
            print(f"  {g:18s} {s['holdout_spearman_r']:+10.4f} "
                  f"{(s['frac_of_full_spearman'] or 0):10.2f} "
                  f"{l['holdout_spearman_r']:+10.4f} {l['delta_vs_full_spearman']:+9.4f}")
        print(f"  VERDICT: {r['verdict']['label']}")
    print(f"\nwrote: {OUT_JSON}")


if __name__ == "__main__":
    sys.exit(main())
