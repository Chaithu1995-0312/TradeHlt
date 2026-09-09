"""
high_acceptance_structural_scan.py — Phase 2: structural characteristics of the strongest
high-acceptance candles (research, ontology-free).

Answers: "what is numerically different about a candle (and its recent numeric context) when
its high strongly survives forward horizon N=500, vs when it gets reclaimed quickly?"

Still governed by the phase-1 framing: purely numerical/statistical, no CRT/SMC/ontology
vocabulary attached (no "swing high," "session," "displacement," etc. -- those concepts are
approximated here only as generic rolling-window/calendar arithmetic), and no trading-meaning
verdict -- this reports effect sizes and correlations, not a conclusion.

Reuses phase-1 outputs (results/research/high_acceptance/xauusd_m15.parquet +
xauusd_m15_candidates.parquet, filtered to N=500) rather than recomputing them.

Cohorts (per user decision): "strong" = top 1/5/10% by acceptance_score_atr_norm at N=500;
"weak" = bottom 50% by the same metric (the "reclaimed early" cohort) -- the sharpest available
contrast. A pooled Spearman correlation across the FULL N=500 population is reported alongside
the cohort contrast so a hard-cut artifact would be visible.

PURE READ-ONLY over phase-1 artifacts. No production/src/config/spine change. No new ontology
feature registered.

Outputs:
    results/research/high_acceptance/xauusd_m15_structural_features.parquet (+ .csv)
    results/research/high_acceptance/xauusd_m15_structural_summary.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu, spearmanr

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "research" / "high_acceptance"
RAW_PARQUET = OUT_DIR / "xauusd_m15.parquet"
CANDIDATES_PARQUET = OUT_DIR / "xauusd_m15_candidates.parquet"
OUT_PARQUET_FEATURES = OUT_DIR / "xauusd_m15_structural_features.parquet"
OUT_CSV_FEATURES = OUT_DIR / "xauusd_m15_structural_features.csv"
OUT_SUMMARY_JSON = OUT_DIR / "xauusd_m15_structural_summary.json"

HORIZON = 500
STRONG_PCTS = [1, 5, 10]
PRIMARY_STRONG_PCT = 10
WEAK_PCT = 50  # bottom 50%
VOLUME_ZSCORE_WINDOW = 100
ATR_ZSCORE_WINDOW = 200
NEW_HIGH_WINDOWS = [20, 50, 100]
PRIOR_HIGHER_HIGH_LOOKBACK = 500

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
CALENDAR_COLS = ["hour_of_day", "day_of_week"]


def load_inputs() -> pd.DataFrame:
    raw = pd.read_parquet(RAW_PARQUET)
    cand = pd.read_parquet(CANDIDATES_PARQUET)
    cand = cand[cand["N"] == HORIZON].reset_index(drop=True)
    df = cand.merge(
        raw[["open", "high", "low", "close", "volume"]],
        left_on="candidate_index",
        right_index=True,
        how="left",
    )
    return df.sort_values("candidate_index").reset_index(drop=True)


def add_local_atr(raw: pd.DataFrame) -> pd.Series:
    high, low, close = raw["high"], raw["low"], raw["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(14, min_periods=14).mean()


def build_structural_features(df: pd.DataFrame) -> pd.DataFrame:
    raw = pd.read_parquet(RAW_PARQUET)
    raw["atr_local"] = add_local_atr(raw)
    raw["sma20"] = raw["close"].rolling(20, min_periods=20).mean()
    high, low, close, open_ = raw["high"], raw["low"], raw["close"], raw["open"]

    rng = high - low
    body = (close - open_).abs()
    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low

    feat = pd.DataFrame(index=raw.index)
    feat["range"] = rng
    feat["body"] = body
    with np.errstate(divide="ignore", invalid="ignore"):
        feat["body_frac"] = np.where(rng > 0, body / rng, np.nan)
        feat["upper_wick_frac"] = np.where(rng > 0, upper_wick / rng, np.nan)
        feat["lower_wick_frac"] = np.where(rng > 0, lower_wick / rng, np.nan)
        feat["close_position_in_range"] = np.where(rng > 0, (close - low) / rng, np.nan)
    feat["direction_up"] = (close > open_)
    feat["volume_raw"] = raw["volume"]
    vol_roll = raw["volume"].rolling(VOLUME_ZSCORE_WINDOW, min_periods=VOLUME_ZSCORE_WINDOW)
    feat["volume_zscore"] = (raw["volume"] - vol_roll.mean()) / vol_roll.std()

    feat["atr_local"] = raw["atr_local"]
    atr_roll = raw["atr_local"].rolling(ATR_ZSCORE_WINDOW, min_periods=ATR_ZSCORE_WINDOW)
    feat["atr_zscore"] = (raw["atr_local"] - atr_roll.mean()) / atr_roll.std()
    with np.errstate(divide="ignore", invalid="ignore"):
        feat["range_to_atr"] = np.where(raw["atr_local"] > 0, rng / raw["atr_local"], np.nan)

    feat["ret_5"] = close.pct_change(5)
    feat["ret_20"] = close.pct_change(20)
    feat["ret_50"] = close.pct_change(50)
    with np.errstate(divide="ignore", invalid="ignore"):
        feat["dist_from_sma20"] = np.where(
            raw["atr_local"] > 0, (close - raw["sma20"]) / raw["atr_local"], np.nan
        )
        feat["sma20_slope_5"] = np.where(
            raw["atr_local"] > 0, (raw["sma20"] - raw["sma20"].shift(5)) / raw["atr_local"], np.nan
        )

    for w in NEW_HIGH_WINDOWS:
        rolling_max = high.rolling(w, min_periods=w).max()
        feat[f"is_new_high_{w}"] = high >= rolling_max

    bars_since = np.full(len(raw), np.nan)
    high_vals = high.to_numpy()
    for i in range(len(raw)):
        lo = max(0, i - PRIOR_HIGHER_HIGH_LOOKBACK)
        window = high_vals[lo:i]
        if len(window) == 0:
            continue
        higher = np.where(window > high_vals[i])[0]
        if len(higher):
            bars_since[i] = i - (lo + higher[-1])
    feat["bars_since_prior_higher_high"] = bars_since

    ts = raw["timestamp"]
    feat["hour_of_day"] = ts.dt.hour
    feat["day_of_week"] = ts.dt.dayofweek

    accepted_at_i = pd.Series(False, index=raw.index)
    for _, row in df.iterrows():
        accepted_at_i.iloc[int(row["candidate_index"])] = bool(row["acceptance_score"] > 0)
    feat["prior_candidate_accepted"] = accepted_at_i.shift(1).fillna(False)

    merged = df.merge(feat, left_on="candidate_index", right_index=True, how="left")
    return merged


def _cohens_d(a: pd.Series, b: pd.Series) -> float:
    a, b = a.dropna(), b.dropna()
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return float("nan")
    pooled_std = np.sqrt(((n1 - 1) * a.var() + (n2 - 1) * b.var()) / (n1 + n2 - 2))
    if pooled_std == 0 or np.isnan(pooled_std):
        return float("nan")
    return float((a.mean() - b.mean()) / pooled_std)


def cohort_contrast(strong: pd.DataFrame, weak: pd.DataFrame) -> dict:
    continuous = {}
    for col in CONTINUOUS_COLS:
        a, b = strong[col], weak[col]
        d = _cohens_d(a, b)
        try:
            _, p = mannwhitneyu(a.dropna(), b.dropna(), alternative="two-sided")
        except ValueError:
            p = float("nan")
        continuous[col] = {
            "strong_mean": float(a.mean()) if a.notna().any() else None,
            "weak_mean": float(b.mean()) if b.notna().any() else None,
            "cohens_d": d,
            "mannwhitney_p": float(p),
        }

    boolean = {}
    for col in BOOLEAN_COLS:
        a, b = strong[col].astype(bool), weak[col].astype(bool)
        rate_a, rate_b = float(a.mean()), float(b.mean())
        table = [[int(a.sum()), int((~a).sum())], [int(b.sum()), int((~b).sum())]]
        try:
            _, p = fisher_exact(table)
        except ValueError:
            p = float("nan")
        boolean[col] = {
            "strong_rate": rate_a,
            "weak_rate": rate_b,
            "rate_diff": rate_a - rate_b,
            "fisher_p": float(p),
        }

    ranked = []
    for col, stats in continuous.items():
        if stats["cohens_d"] is not None and not np.isnan(stats["cohens_d"]):
            ranked.append({"characteristic": col, "kind": "continuous", "effect_size": stats["cohens_d"]})
    for col, stats in boolean.items():
        ranked.append({"characteristic": col, "kind": "boolean", "effect_size": stats["rate_diff"]})
    ranked.sort(key=lambda r: abs(r["effect_size"]), reverse=True)

    calendar = {}
    for col in CALENDAR_COLS:
        buckets = sorted(set(strong[col].dropna().unique()) | set(weak[col].dropna().unique()))
        calendar[col] = [
            {
                "bucket": int(b),
                "strong_fraction": float((strong[col] == b).mean()),
                "weak_fraction": float((weak[col] == b).mean()),
            }
            for b in buckets
        ]

    return {
        "continuous": continuous,
        "boolean": boolean,
        "ranked_by_abs_effect_size": ranked,
        "calendar": calendar,
    }


def pooled_correlation(df: pd.DataFrame) -> dict:
    target = df["acceptance_score_atr_norm"]
    out = {}
    for col in CONTINUOUS_COLS:
        sub = df[[col]].join(target.rename("target")).dropna()
        if len(sub) < 3:
            out[col] = {"n": len(sub), "spearman_r": None, "p": None}
            continue
        r, p = spearmanr(sub[col], sub["target"])
        out[col] = {"n": len(sub), "spearman_r": float(r), "p": float(p)}
    for col in BOOLEAN_COLS:
        sub = df[[col]].astype({col: float}).join(target.rename("target")).dropna()
        if len(sub) < 3:
            out[col] = {"n": len(sub), "spearman_r": None, "p": None}
            continue
        r, p = spearmanr(sub[col], sub["target"])
        out[col] = {"n": len(sub), "spearman_r": float(r), "p": float(p)}
    return out


def main() -> None:
    df = load_inputs()
    feat = build_structural_features(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    feat.to_parquet(OUT_PARQUET_FEATURES, engine="pyarrow", index=False)
    feat.to_csv(OUT_CSV_FEATURES, index=False)

    score = feat["acceptance_score_atr_norm"]
    weak_threshold = np.percentile(score.dropna(), WEAK_PCT)
    weak = feat[score <= weak_threshold]

    cohorts_out = {}
    for pct in STRONG_PCTS:
        strong_threshold = np.percentile(score.dropna(), 100 - pct)
        strong = feat[score >= strong_threshold]
        cohorts_out[f"top_{pct}pct"] = {
            "n_strong": int(len(strong)),
            "n_weak": int(len(weak)),
            "strong_threshold_atr_norm": float(strong_threshold),
            "weak_threshold_atr_norm": float(weak_threshold),
            "contrast": cohort_contrast(strong, weak),
        }

    summary = {
        "horizon": HORIZON,
        "n_population": int(len(feat)),
        "primary_reporting_cohort": f"top_{PRIMARY_STRONG_PCT}pct",
        "cohorts": cohorts_out,
        "pooled_correlation_full_population": pooled_correlation(feat),
        "note": (
            "Effect sizes and correlations only. No classification, no trading meaning, no "
            "ontology vocabulary attached. is_new_high_* / bars_since_prior_higher_high are "
            "plain rolling-max arithmetic, not a registered ontology feature."
        ),
    }
    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str))

    print(f"N=500 population: {len(feat)}")
    for pct in STRONG_PCTS:
        print(f"  top {pct}% n={cohorts_out[f'top_{pct}pct']['n_strong']}")
    print(f"  bottom {WEAK_PCT}% n={len(weak)}")
    print(f"wrote: {OUT_PARQUET_FEATURES}")
    print(f"wrote: {OUT_CSV_FEATURES}")
    print(f"wrote: {OUT_SUMMARY_JSON}")


if __name__ == "__main__":
    sys.exit(main())
