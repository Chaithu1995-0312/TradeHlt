"""
high_acceptance_regime_stability.py — Phase 3.5 Study 0.6: regime stability + walk-forward
decomposition of the surviving rank signal (research, ontology-free).

QUESTION. Study 0 left exactly one survivor: a denominator-independent Ridge holdout rank
correlation of +0.21..+0.25. Study 0.5 showed it is REDUNDANT rather than concentrated -- on the
raw target, volatility SOLO reproduces 97% of the full model, volume SOLO 93%, candle_geometry
SOLO 79%, yet leaving any single group OUT costs at most 0.015. Three different groups each
carry nearly all of it and none is necessary: the signature of several proxies for one shared
quantity. This script asks whether that quantity is a regime effect, and whether the rank
correlation is per-bar discrimination at all.

THREE DIAGNOSTICS. No new features, no new model families, no clustering -- the same Ridge over
the same phase-2 features throughout.

  (A) WALK-FORWARD. K sequential rolling-origin folds, each with the same 500-row embargo.
      Per-fold holdout Spearman answers: is the signal steady over time, or produced by a few
      periods? (stdev across folds, sign consistency, min/max)

  (B) REGIME STRATIFICATION. Label every bar Compressed/Normal/Expanded by TRAILING ATR terciles
      -- construction mirrors src/interpreters/regime_observer.py:43-48 (atr_period=14,
      tercile_window=480, cuts at 33.33/66.67, backward-only so no lookahead), reimplemented
      inline to keep this chain standalone. Then compute holdout Spearman WITHIN each regime. If
      the signal lives in one tercile it is a regime effect, not a general property.

  (C) DECORRELATION (the decisive one). Adjacent candidates share 499 of 500 forward bars, so
      both the prediction and the target are slowly-varying series. A high global Spearman can
      therefore be produced entirely by the two series drifting together, with zero ability to
      rank two nearby bars against each other. Three measurements separate these:
          global        Spearman over all holdout rows            (co-drift + local skill)
          within_block  Spearman inside consecutive 500-row blocks, averaged
                        (local skill ONLY -- cross-block drift removed)
          subsampled    Spearman over every 500th row
                        (near-independent observations; small n, wide CI)
      global >> within_block  =>  the signal is CO-DRIFT with a slow latent variable, not per-bar
      discrimination. within_block ~= global => genuine local ranking skill.

Still descriptive: no classification, no trading meaning, no promotion authority.

PURE READ-ONLY over phase-1/2 artifacts. No production/src/config/spine change.

Outputs:
    results/research/high_acceptance/xauusd_m15_regime_stability.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "research" / "high_acceptance"
RAW_PARQUET = OUT_DIR / "xauusd_m15.parquet"
FEATURES_PARQUET = OUT_DIR / "xauusd_m15_structural_features.parquet"
OUT_JSON = OUT_DIR / "xauusd_m15_regime_stability.json"

HORIZON = 500
EMBARGO_ROWS = HORIZON
RIDGE_ALPHAS = np.logspace(-3, 3, 25)
N_FOLDS = 8
MIN_TRAIN_ROWS = 6000
STABLE_ATR_WINDOW = 2000
STABLE_ATR_MIN_PERIODS = 500

# Mirrors src/interpreters/regime_observer.py:43-48 (backward-only, no lookahead).
ATR_PERIOD = 14
TERCILE_WINDOW = 480
LOWER_PCT, UPPER_PCT = 33.33, 66.67

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
PRIMARY_TARGET = "acceptance_score"


def local_atr(raw: pd.DataFrame) -> pd.Series:
    high, low, close = raw["high"], raw["low"], raw["close"]
    prev = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean()


def trailing_tercile_regime(atr: pd.Series) -> pd.Series:
    """Compressed/Normal/Expanded by trailing ATR terciles. Backward-only: bar i uses [i-479, i]."""
    lower = atr.rolling(TERCILE_WINDOW, min_periods=TERCILE_WINDOW).quantile(LOWER_PCT / 100.0)
    upper = atr.rolling(TERCILE_WINDOW, min_periods=TERCILE_WINDOW).quantile(UPPER_PCT / 100.0)
    out = pd.Series(pd.NA, index=atr.index, dtype="object")
    out[atr <= lower] = "COMPRESSED"
    out[(atr > lower) & (atr < upper)] = "NORMAL"
    out[atr >= upper] = "EXPANDED"
    out[lower.isna() | upper.isna()] = pd.NA
    return out


def load_frame() -> pd.DataFrame:
    df = pd.read_parquet(FEATURES_PARQUET).sort_values("candidate_index").reset_index(drop=True)
    raw = pd.read_parquet(RAW_PARQUET)
    atr = local_atr(raw)

    stable = atr.rolling(STABLE_ATR_WINDOW, min_periods=STABLE_ATR_MIN_PERIODS).median()
    denom = stable.reindex(df["candidate_index"].to_numpy()).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        df["acceptance_score_stable_norm"] = np.where(denom > 0, df["acceptance_score"] / denom, np.nan)

    regime = trailing_tercile_regime(atr)
    df["regime"] = regime.reindex(df["candidate_index"].to_numpy()).to_numpy()
    for col in BOOLEAN_COLS:
        df[col] = df[col].astype(float)
    return df


def _fit_predict(tr: pd.DataFrame, ho: pd.DataFrame, target: str) -> np.ndarray:
    scaler = StandardScaler().fit(tr[FEATURE_COLS])
    model = RidgeCV(alphas=RIDGE_ALPHAS, cv=5).fit(scaler.transform(tr[FEATURE_COLS]), tr[target])
    return model.predict(scaler.transform(ho[FEATURE_COLS]))


def _rho(a, b) -> float | None:
    if len(a) < 3:
        return None
    r, _ = spearmanr(a, b)
    return None if np.isnan(r) else float(r)


def decorrelation_probe(pred: np.ndarray, actual: np.ndarray, block: int = HORIZON) -> dict:
    """Global vs within-block vs subsampled rank correlation. See module docstring (C)."""
    global_rho = _rho(pred, actual)

    block_rhos, block_ns = [], []
    for start in range(0, len(pred), block):
        p, a = pred[start:start + block], actual[start:start + block]
        r = _rho(p, a)
        if r is not None:
            block_rhos.append(r)
            block_ns.append(len(p))
    within = float(np.average(block_rhos, weights=block_ns)) if block_rhos else None

    sub_rho = _rho(pred[::block], actual[::block])

    ratio = (within / global_rho) if (within is not None and global_rho) else None
    return {
        "global_spearman": global_rho,
        "within_block_spearman_weighted_mean": within,
        "within_block_n_blocks": len(block_rhos),
        "within_block_spearman_median": float(np.median(block_rhos)) if block_rhos else None,
        "within_block_positive_fraction": (
            float(np.mean([r > 0 for r in block_rhos])) if block_rhos else None
        ),
        "subsampled_spearman": sub_rho,
        "subsampled_n": int(len(pred[::block])),
        "within_over_global_ratio": ratio,
        "interpretation": (
            "global >> within_block => co-drift with a slow latent variable, not per-bar "
            "discrimination; within_block ~= global => genuine local ranking skill"
        ),
    }


def walk_forward(df: pd.DataFrame, target: str) -> dict:
    cols = FEATURE_COLS + [target]
    d = df.dropna(subset=cols).reset_index(drop=True)
    n = len(d)
    fold_size = (n - MIN_TRAIN_ROWS) // N_FOLDS
    folds, all_pred, all_actual = [], [], []

    for k in range(N_FOLDS):
        test_start = MIN_TRAIN_ROWS + k * fold_size
        test_end = test_start + fold_size if k < N_FOLDS - 1 else n
        train_end = test_start - EMBARGO_ROWS
        if train_end < MIN_TRAIN_ROWS // 2 or test_end - test_start < 50:
            continue
        tr, ho = d.iloc[:train_end], d.iloc[test_start:test_end]
        pred = _fit_predict(tr, ho, target)
        actual = ho[target].to_numpy()
        all_pred.append(pred)
        all_actual.append(actual)
        folds.append({
            "fold": k,
            "n_train": int(len(tr)),
            "n_test": int(len(ho)),
            "test_start_ts": str(ho["candidate_ts"].iloc[0]),
            "test_end_ts": str(ho["candidate_ts"].iloc[-1]),
            "holdout_spearman_r": _rho(pred, actual),
            "decorrelation": decorrelation_probe(pred, actual),
        })

    rhos = [f["holdout_spearman_r"] for f in folds if f["holdout_spearman_r"] is not None]
    wb = [
        f["decorrelation"]["within_block_spearman_weighted_mean"]
        for f in folds
        if f["decorrelation"]["within_block_spearman_weighted_mean"] is not None
    ]
    return {
        "n_folds_run": len(folds),
        "folds": folds,
        "across_folds": {
            "mean_spearman": float(np.mean(rhos)) if rhos else None,
            "std_spearman": float(np.std(rhos)) if rhos else None,
            "min_spearman": float(np.min(rhos)) if rhos else None,
            "max_spearman": float(np.max(rhos)) if rhos else None,
            "positive_fold_fraction": float(np.mean([r > 0 for r in rhos])) if rhos else None,
            "mean_within_block_spearman": float(np.mean(wb)) if wb else None,
        },
    }


def regime_stratified(df: pd.DataFrame, target: str) -> dict:
    """Single chronological split (phase-3 geometry), holdout Spearman within each ATR tercile."""
    cols = FEATURE_COLS + [target]
    d = df.dropna(subset=cols).reset_index(drop=True)
    at = int(len(d) * 0.8)
    ho = d.iloc[at:].reset_index(drop=True)
    tr = d.iloc[: at - EMBARGO_ROWS]
    pred = _fit_predict(tr, ho, target)
    actual = ho[target].to_numpy()

    out = {"overall_spearman": _rho(pred, actual), "by_regime": {}}
    for label in ["COMPRESSED", "NORMAL", "EXPANDED"]:
        mask = (ho["regime"] == label).to_numpy()
        out["by_regime"][label] = {
            "n": int(mask.sum()),
            "spearman_r": _rho(pred[mask], actual[mask]),
            "within_block_spearman": (
                decorrelation_probe(pred[mask], actual[mask])["within_block_spearman_weighted_mean"]
                if mask.sum() > HORIZON else None
            ),
        }
    n_unlabelled = int(ho["regime"].isna().sum())
    out["n_unlabelled_regime"] = n_unlabelled
    return out


def main() -> None:
    df = load_frame()
    per_target = {}
    for t in TARGETS:
        per_target[t] = {
            "walk_forward": walk_forward(df, t),
            "regime_stratified": regime_stratified(df, t),
        }

    summary = {
        "horizon": HORIZON,
        "primary_target": PRIMARY_TARGET,
        "regime_construction": {
            "atr_period": ATR_PERIOD,
            "tercile_window": TERCILE_WINDOW,
            "cuts_pct": [LOWER_PCT, UPPER_PCT],
            "source": "mirrors src/interpreters/regime_observer.py:43-48, backward-only",
        },
        "walk_forward_config": {"n_folds": N_FOLDS, "min_train_rows": MIN_TRAIN_ROWS,
                                "embargo_rows": EMBARGO_ROWS},
        "per_target": per_target,
        "note": (
            "Same Ridge, same phase-2 features throughout. No new features, no new model "
            "families, no clustering. Descriptive only: no classification, no trading meaning, "
            "no promotion authority."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2, default=str))

    for t in TARGETS:
        star = "  <-- PRIMARY" if t == PRIMARY_TARGET else ""
        wf, rs = per_target[t]["walk_forward"], per_target[t]["regime_stratified"]
        a = wf["across_folds"]
        print(f"\n=== {t}{star}")
        print(f"  walk-forward ({wf['n_folds_run']} folds): mean rho={a['mean_spearman']:+.4f} "
              f"sd={a['std_spearman']:.4f} range=[{a['min_spearman']:+.4f}, {a['max_spearman']:+.4f}] "
              f"positive={a['positive_fold_fraction']:.2f}")
        print(f"  mean WITHIN-BLOCK rho across folds = {a['mean_within_block_spearman']:+.4f}"
              f"   (vs global {a['mean_spearman']:+.4f})")
        print(f"  regime-stratified (single split, overall {rs['overall_spearman']:+.4f}):")
        for lab, v in rs["by_regime"].items():
            wb = v["within_block_spearman"]
            print(f"    {lab:11s} n={v['n']:6d} rho={v['spearman_r']:+.4f} "
                  f"within_block={'n/a' if wb is None else f'{wb:+.4f}'}")
    print(f"\nwrote: {OUT_JSON}")


if __name__ == "__main__":
    sys.exit(main())
