#!/usr/bin/env python3
"""
semantic_layer_validation.py
=============================
Read-only STATISTICS ENGINE for the seven-day semantic-layer validation study (XAUUSD M15).

Runs the STANDARD production path -- `FeaturePipeline.run()` INCLUDING `finalize()` -- over the
complete dataset, slices a window of N consecutive trading days, and emits per-feature
statistics, categorical transition/run-length tables, a mechanical contradiction scan,
co-occurrence tables, and RULE-SELECTED representative examples.

This script MEASURES. It makes no judgments -- the validation report interprets its output.
Every example it selects is chosen by an explicit rule (argmax / nearest-median / nearest-
threshold / predicate-trip), never hand-picked, so the report cannot cherry-pick anecdotes.

Two independent verification paths are built in:
  * every primitive-geometry identity is re-derived from raw OHLCV via the immutable
    `candle_math` scalars and compared to the production columns;
  * every contradiction predicate is re-derived from raw OHLCV + reference columns, independent
    of the pipeline's own emitted flag columns.

Usage:
    PYTHONPATH=src python scripts/analysis/semantic_layer_validation.py
    PYTHONPATH=src python scripts/analysis/semantic_layer_validation.py \\
        --start 2024-05-23 --trading-days 7
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from features import candle_math
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES

# ── Feature taxonomy for the audit (which statistics apply to which feature) ────────────────
BINARY_FEATURES = [
    "double_sweep", "sweep_detected", "swing_high", "swing_low",
    "higher_high", "lower_low", "volume_spike",
]
CATEGORICAL_FEATURES = {
    "break_of_structure": {-1: "BearishBreak", 0: "NoBreak", 1: "BullishBreak"},
    "liquidity_sweep": {-1: "SellSideSweep", 0: "NoSweep", 1: "BuySideSweep"},
    "trend_bias": {-1.0: "Bearish", 0.0: "Neutral", 1.0: "Bullish"},
    "volatility_regime": {0: "LowVolatility", 1: "MediumVolatility", 2: "HighVolatility"},
    "session": {0: "ASIA", 1: "LONDON", 2: "NEWYORK", 3: "OVERLAP", 4: "CLOSED"},
}
# Non-canonical but production-computed -- the missing-semantics evidence base.
NON_CANONICAL_EVIDENCE = ["upper_wick", "lower_wick", "price_position", "candle_body",
                          "true_range", "atr_14", "retest_flag", "displacement_flag"]

SEMANTIC_FAMILIES = {
    "Primitive Geometry": ["open", "high", "low", "close", "volume"],
    "Candle Geometry": ["body_size", "candle_range", "body_ratio"],
    "Trend": ["ema_fast", "ema_slow", "ema_spread", "trend_bias", "trend_strength"],
    "Momentum": ["momentum_score", "rsi_14", "macd_line", "macd_signal",
                 "macd_hist_raw", "macd_hist_z"],
    "Volatility": ["atr", "volatility_ratio", "volatility_regime"],
    "Market Structure": ["swing_high", "swing_low", "higher_high", "lower_low",
                         "break_of_structure"],
    "Liquidity": ["liquidity_sweep", "sweep_detected", "double_sweep",
                  "liquidity_distance", "liquidity_pressure_score"],
    "Retest": ["retest_depth", "candles_since_retest", "disp_strength"],
    "Volume": ["volume_ratio", "volume_spike"],
    "Temporal Context": ["session", "hour_of_day"],
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _native(v):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        v = float(v)
        return None if (v != v or np.isinf(v)) else v
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return str(v)


# ── Statistics ─────────────────────────────────────────────────────────────────────────────

def _distribution(s: pd.Series) -> dict:
    clean = pd.to_numeric(s, errors="coerce").dropna()
    if clean.empty:
        return {"n": 0}
    return {
        "n": int(len(clean)),
        "min": _native(clean.min()), "max": _native(clean.max()),
        "mean": _native(clean.mean()), "median": _native(clean.median()),
        "std": _native(clean.std(ddof=1)),
        "deciles": {f"p{p}": _native(clean.quantile(p / 100.0))
                    for p in (10, 20, 30, 40, 50, 60, 70, 80, 90)},
        "zero_rate_pct": _native(100.0 * (clean.abs() < 1e-12).mean()),
    }


def _run_lengths(s: pd.Series) -> dict:
    """Consecutive run lengths per state value."""
    runs: dict = {}
    if len(s) == 0:
        return runs
    cur_val, cur_len = s.iloc[0], 1
    for v in s.iloc[1:]:
        if v == cur_val:
            cur_len += 1
        else:
            runs.setdefault(_native(cur_val), []).append(cur_len)
            cur_val, cur_len = v, 1
    runs.setdefault(_native(cur_val), []).append(cur_len)
    return {str(k): {"count": len(v), "mean": _native(float(np.mean(v))),
                     "median": _native(float(np.median(v))), "max": int(max(v))}
            for k, v in runs.items()}


def _transition_matrix(s: pd.Series) -> dict:
    prev, cur = s.iloc[:-1].values, s.iloc[1:].values
    out: dict = {}
    for a, b in zip(prev, cur):
        out.setdefault(str(_native(a)), {}).setdefault(str(_native(b)), 0)
        out[str(_native(a))][str(_native(b))] += 1
    return out


def _feature_stats(w: pd.DataFrame, name: str) -> dict:
    s = w[name]
    entry = {"feature": name, "total_observations": int(len(s)),
             "distribution": _distribution(s)}
    if name in BINARY_FEATURES or name in ("volume_spike",):
        act = int((pd.to_numeric(s, errors="coerce") != 0).sum())
        entry["activations"] = act
        entry["active_pct"] = _native(100.0 * act / len(s))
    if name in CATEGORICAL_FEATURES:
        vc = s.value_counts().sort_index()
        entry["state_frequency"] = {
            str(_native(k)): {"label": CATEGORICAL_FEATURES[name].get(k, str(k)),
                              "count": int(v), "pct": _native(100.0 * v / len(s))}
            for k, v in vc.items()}
        entry["transition_matrix"] = _transition_matrix(s)
        entry["run_lengths"] = _run_lengths(s)
    if name in BINARY_FEATURES:
        entry["run_lengths"] = _run_lengths(s)
    return entry


# ── Independent verification ───────────────────────────────────────────────────────────────

def _verify_geometry(w: pd.DataFrame) -> dict:
    """Re-derive every geometry identity from raw OHLCV via the immutable candle_math scalars."""
    mismatches = []
    for idx, r in w.iterrows():
        o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
        for qty, scalar_val, col in (
            ("body_size", candle_math.body_size(o, c), "body_size"),
            ("candle_range", candle_math.candle_range(h, l), "candle_range"),
            ("body_ratio", candle_math.body_ratio(o, h, l, c), "body_ratio"),
            ("upper_wick", candle_math.upper_wick(o, h, c), "upper_wick"),
            ("lower_wick", candle_math.lower_wick(o, l, c), "lower_wick"),
        ):
            pv = float(r[col])
            if abs(float(scalar_val) - pv) > max(1e-6, 1e-6 * abs(pv)):
                mismatches.append({"timestamp": _native(r["timestamp"]), "quantity": qty,
                                   "scalar": _native(scalar_val), "production": _native(pv)})
    return {"bars_checked": int(len(w)), "identities_per_bar": 5,
            "total_checks": int(len(w) * 5), "mismatches": mismatches,
            "all_match": len(mismatches) == 0}


def _bar_evidence(r: pd.Series, extra: tuple = ()) -> dict:
    d = {"timestamp": _native(r["timestamp"]),
         "open": _native(r["open"]), "high": _native(r["high"]),
         "low": _native(r["low"]), "close": _native(r["close"]),
         "volume": _native(r["volume"]),
         "body_size": _native(r["body_size"]), "candle_range": _native(r["candle_range"]),
         "body_ratio": _native(r["body_ratio"]),
         "upper_wick": _native(r["upper_wick"]), "lower_wick": _native(r["lower_wick"])}
    for c in extra:
        if c in r.index:
            d[c] = _native(r[c])
    return d


def _contradiction_scan(w: pd.DataFrame, cfg: dict) -> dict:
    """Definitional invariants (expect 0) + semantic-mismatch predicates (firing = finding).

    Every predicate is re-derived from RAW OHLCV + reference columns wherever possible, i.e.
    independently of the pipeline's own emitted flag column, so a flag bug cannot hide itself.
    """
    ref_high, ref_low = w["ref_high"], w["ref_low"]
    disp_mult = cfg["displacement_strong_body_mult"]

    # Independent re-derivation straight from OHLCV + references (feature_pipeline.py:746-757)
    d_sweep_high = (w["high"] > ref_high) & (w["close"] <= ref_high)
    d_sweep_low = (w["low"] < ref_low) & (w["close"] >= ref_low)
    d_sweep = np.where(d_sweep_high, 1, np.where(d_sweep_low, -1, 0))
    d_bos = np.where(w["close"] > ref_high, 1, np.where(w["close"] < ref_low, -1, 0))
    d_trend_bias = np.sign(w["ema_fast"] - w["ema_slow"])
    d_displacement = ((w["body_ratio"] > disp_mult) & (w["atr"] > 0)).astype(int)

    invariants = [
        ("trend_bias == sign(ema_fast - ema_slow)",
         w["trend_bias"] != d_trend_bias, "feature_pipeline.py:909-915"),
        ("sweep_detected == (liquidity_sweep != 0)",
         w["sweep_detected"] != (w["liquidity_sweep"] != 0).astype(int),
         "feature_pipeline.py:921"),
        ("retest_depth > 0 implies retest_flag == 1",
         (w["retest_depth"] > 0) & (w["retest_flag"] == 0), "feature_pipeline.py:997-1006"),
        ("body_ratio within [0, 1]",
         (w["body_ratio"] < 0) | (w["body_ratio"] > 1), "candle_math.py:50-61"),
        ("displacement_flag == (body_ratio > mult AND atr > 0)",
         w["displacement_flag"] != d_displacement, "feature_pipeline.py:923-932"),
        ("liquidity_sweep matches independent OHLCV re-derivation",
         w["liquidity_sweep"] != d_sweep, "feature_pipeline.py:751-757"),
        ("break_of_structure matches independent OHLCV re-derivation",
         w["break_of_structure"] != d_bos, "feature_pipeline.py:746-749"),
    ]
    inv_out = []
    for desc, mask, ref in invariants:
        mask = mask.fillna(False) if hasattr(mask, "fillna") else mask
        n = int(np.sum(mask))
        inv_out.append({
            "invariant": desc, "source": ref, "violations": n, "clean": n == 0,
            "examples": [_bar_evidence(r, ("liquidity_sweep", "break_of_structure",
                                           "trend_bias", "retest_flag", "retest_depth",
                                           "displacement_flag", "ref_high", "ref_low"))
                         for _, r in w[mask].head(5).iterrows()] if n else [],
        })

    rng_p90 = w["candle_range"].quantile(0.90)
    rng_p10 = w["candle_range"].quantile(0.10)
    disp_med = w["disp_strength"].median()

    predicates = [
        (f"volatility_regime==LOW while candle_range in top decile (>{rng_p90:.2f})",
         (w["volatility_regime"] == 0) & (w["candle_range"] > rng_p90)),
        (f"volatility_regime==HIGH while candle_range in bottom decile (<{rng_p10:.2f})",
         (w["volatility_regime"] == 2) & (w["candle_range"] < rng_p10)),
        (f"strong bullish body (body_ratio>0.6) but disp_strength below median ({disp_med:.3f})",
         (w["body_ratio"] > 0.6) & (w["close"] > w["open"]) & (w["disp_strength"] < disp_med)),
        ("trend_bias==Bullish while break_of_structure==BearishBreak",
         (w["trend_bias"] == 1) & (w["break_of_structure"] == -1)),
        ("trend_bias==Bearish while break_of_structure==BullishBreak",
         (w["trend_bias"] == -1) & (w["break_of_structure"] == 1)),
        ("doji (body_ratio<0.1) carrying break_of_structure != 0",
         (w["body_ratio"] < 0.1) & (w["break_of_structure"] != 0)),
        ("liquidity_sweep != 0 AND break_of_structure != 0 on the same bar",
         (w["liquidity_sweep"] != 0) & (w["break_of_structure"] != 0)),
    ]
    pred_out = []
    for desc, mask in predicates:
        mask = mask.fillna(False)
        n = int(mask.sum())
        pred_out.append({
            "predicate": desc, "occurrences": n,
            "pct_of_window": _native(100.0 * n / len(w)),
            "examples": [_bar_evidence(r, ("volatility_regime", "trend_bias",
                                           "break_of_structure", "liquidity_sweep",
                                           "disp_strength", "atr", "ref_high", "ref_low"))
                         for _, r in w[mask].head(6).iterrows()],
        })
    return {"definitional_invariants": inv_out, "semantic_mismatch_predicates": pred_out}


def _latching_analysis(w: pd.DataFrame, col: str) -> dict:
    """Is this feature an EVENT (fires once) or a LEVEL STATE (re-fires while a condition holds)?"""
    s = w[col]
    nz = (s != 0)
    fresh = nz & (s != s.shift(1))
    runs = []
    cur = 0
    for v in s:
        if v != 0:
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return {
        "feature": col,
        "nonzero_bars": int(nz.sum()),
        "nonzero_pct": _native(100.0 * nz.sum() / len(w)),
        "fresh_transitions": int(fresh.sum()),
        "fresh_pct_of_nonzero": _native(100.0 * fresh.sum() / max(1, nz.sum())),
        "latched_continuations": int(nz.sum() - fresh.sum()),
        "latched_pct_of_nonzero": _native(100.0 * (nz.sum() - fresh.sum()) / max(1, nz.sum())),
        "run_count": len(runs),
        "run_mean": _native(float(np.mean(runs))) if runs else None,
        "run_median": _native(float(np.median(runs))) if runs else None,
        "run_max": int(max(runs)) if runs else None,
    }


def _cooccurrence(w: pd.DataFrame) -> dict:
    n = len(w)

    def pair(a_desc, a, b_desc, b):
        a, b = a.fillna(False), b.fillna(False)
        both = int((a & b).sum())
        return {"a": a_desc, "b": b_desc,
                "a_count": int(a.sum()), "b_count": int(b.sum()), "both": both,
                "both_pct_of_window": _native(100.0 * both / n),
                "p_b_given_a_pct": _native(100.0 * both / max(1, int(a.sum()))),
                "p_b_baseline_pct": _native(100.0 * int(b.sum()) / n)}

    return {
        "bos_x_displacement": pair("break_of_structure != 0", w["break_of_structure"] != 0,
                                   "displacement_flag == 1", w["displacement_flag"] == 1),
        "sweep_x_retest": pair("sweep_detected == 1", w["sweep_detected"] == 1,
                               "retest_flag == 1", w["retest_flag"] == 1),
        "sweep_x_bos": pair("liquidity_sweep != 0", w["liquidity_sweep"] != 0,
                            "break_of_structure != 0", w["break_of_structure"] != 0),
        "volume_spike_x_displacement": pair("volume_spike == 1", w["volume_spike"] == 1,
                                            "displacement_flag == 1", w["displacement_flag"] == 1),
        "highvol_regime_x_top_decile_range": pair(
            "volatility_regime == 2", w["volatility_regime"] == 2,
            "candle_range in top decile", w["candle_range"] > w["candle_range"].quantile(0.90)),
        "double_sweep_x_bos": pair("double_sweep == 1", w["double_sweep"] == 1,
                                   "break_of_structure != 0", w["break_of_structure"] != 0),
    }


def _wick_analysis(w: pd.DataFrame) -> dict:
    rng = w["candle_range"].replace(0, np.nan)
    dom = w[["upper_wick", "lower_wick"]].max(axis=1) / rng
    asym = (w["upper_wick"] - w["lower_wick"]) / rng
    return {
        "dominant_wick_fraction_of_range": _distribution(dom),
        "wick_asymmetry_upper_minus_lower_over_range": _distribution(asym),
        "bars_single_wick_gt_50pct_range": int((dom > 0.5).sum()),
        "pct_single_wick_gt_50pct_range": _native(100.0 * (dom > 0.5).sum() / len(w)),
        "bars_single_wick_gt_70pct_range": int((dom > 0.7).sum()),
        "pct_single_wick_gt_70pct_range": _native(100.0 * (dom > 0.7).sum() / len(w)),
        "note": "upper_wick / lower_wick are production-computed but absent from "
                "CANONICAL_FEATURES; this quantifies what the 39-dim vector cannot express.",
    }


def _rule_selected_examples(w: pd.DataFrame, name: str, cfg: dict) -> dict:
    """Examples chosen by EXPLICIT RULE, never hand-picked."""
    s = pd.to_numeric(w[name], errors="coerce")
    ex = {}
    extra = ("atr", "disp_strength", "trend_bias", "break_of_structure", "liquidity_sweep",
             "volatility_regime", "retest_flag", "retest_depth", "volume_ratio", "rsi_14")
    if s.notna().any():
        ex["best_rule"] = "argmax of the feature's own value"
        ex["best"] = _bar_evidence(w.loc[s.idxmax()], extra + (name,))
        med = s.median()
        ex["typical_rule"] = f"bar nearest the median ({med:.6g})"
        ex["typical"] = _bar_evidence(w.loc[(s - med).abs().idxmin()], extra + (name,))
        if name in BINARY_FEATURES or name in CATEGORICAL_FEATURES:
            chg = w.index[s != s.shift(1)]
            if len(chg) > 1:
                ex["borderline_rule"] = "first state transition in the window"
                ex["borderline"] = _bar_evidence(w.loc[chg[1]], extra + (name,))
        else:
            ex["borderline_rule"] = "bar nearest the 90th percentile (upper activation edge)"
            ex["borderline"] = _bar_evidence(
                w.loc[(s - s.quantile(0.90)).abs().idxmin()], extra + (name,))
    return ex


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--start", default="2024-05-23",
                    help="First trading day of the window (YYYY-MM-DD). Default 2024-05-23 "
                         "(first FULL trading day after the 78-row warmup).")
    ap.add_argument("--trading-days", type=int, default=7)
    ap.add_argument("--output-dir", default="results/feature_trace")
    args = ap.parse_args()

    csv_path = Path(args.csv) if Path(args.csv).is_absolute() else ROOT / args.csv
    raw = pd.read_csv(csv_path)
    csv_sha = _sha256(csv_path)

    from config_layer.production_config import get_active_version, get_prod_section
    prod_version = get_active_version()
    fp_cfg = get_prod_section("feature_pipeline")

    # ── STANDARD production path ──
    pipe = FeaturePipeline(raw.copy(), cfg=fp_cfg)
    df, _vectors = pipe.run()
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["ref_high"] = df["last_swing_high_price"].shift(1)
    df["ref_low"] = df["last_swing_low_price"].shift(1)

    # Select exactly N consecutive TRADING days (days present in the data) from --start.
    all_days = sorted({d for d in df["timestamp"].dt.date})
    start_date = pd.to_datetime(args.start).date()
    later = [d for d in all_days if d >= start_date]
    if len(later) < args.trading_days:
        print(f"ERROR: only {len(later)} trading days available from {start_date}", file=sys.stderr)
        return 1
    chosen_days = later[:args.trading_days]
    w = df[df["timestamp"].dt.date.isin(chosen_days)].copy().reset_index(drop=True)

    if len(set(w["timestamp"].dt.date)) != args.trading_days:
        print(f"ERROR: window does not contain exactly {args.trading_days} trading days",
              file=sys.stderr)
        return 1

    bars_per_day = {str(d): int(n) for d, n in w.groupby(w["timestamp"].dt.date).size().items()}

    payload = {
        "generator": "scripts/analysis/semantic_layer_validation.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(csv_path), "source_csv_sha256": csv_sha,
        "prod_config_version": prod_version,
        "production_path": "FeaturePipeline.run() INCLUDING finalize()",
        "raw_rows": int(len(raw)), "finalized_rows": int(len(df)),
        "warmup_rows_dropped": int(len(raw) - len(df)),
        "window": {
            "start_timestamp": _native(w["timestamp"].min()),
            "end_timestamp": _native(w["timestamp"].max()),
            "total_bars": int(len(w)),
            "trading_days": args.trading_days,
            "bars_per_day": bars_per_day,
        },
        "canonical_feature_count": len(CANONICAL_FEATURES),
        "geometry_verification": _verify_geometry(w),
        "feature_statistics": {n: _feature_stats(w, n) for n in CANONICAL_FEATURES},
        "non_canonical_evidence_statistics": {
            n: _distribution(w[n]) for n in NON_CANONICAL_EVIDENCE if n in w.columns},
        "contradiction_scan": _contradiction_scan(w, fp_cfg),
        "latching_analysis": {c: _latching_analysis(w, c)
                              for c in ("break_of_structure", "liquidity_sweep", "trend_bias",
                                        "higher_high", "lower_low", "retest_flag")},
        "cooccurrence": _cooccurrence(w),
        "wick_analysis": _wick_analysis(w),
        "semantic_families": SEMANTIC_FAMILIES,
        "rule_selected_examples": {n: _rule_selected_examples(w, n, fp_cfg)
                                   for n in CANONICAL_FEATURES},
        "config_thresholds_cited": {
            k: _native(fp_cfg[k]) for k in
            ("displacement_strong_body_mult", "retest_lookback", "retest_atr_band_mult",
             "double_sweep_window", "swing_window", "volatility_percentile_window",
             "volatility_tercile_low", "volatility_tercile_high", "zscore_window",
             "volume_spike_percentile", "volume_spike_fixed_fallback",
             "volume_spike_adaptive_window", "volume_spike_min_samples",
             "rsi_period", "atr_period", "ema_fast_span", "ema_slow_span")
            if k in fp_cfg},
    }

    out_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"semantic_layer_validation_{args.trading_days}day_stats"
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Flat per-bar CSV of the window for independent inspection.
    keep = ["timestamp"] + list(CANONICAL_FEATURES) + \
           [c for c in NON_CANONICAL_EVIDENCE if c in w.columns] + ["ref_high", "ref_low"]
    w[keep].to_csv(out_dir / f"semantic_layer_validation_{args.trading_days}day_bars.csv",
                   index=False)

    geo = payload["geometry_verification"]
    inv_bad = [i for i in payload["contradiction_scan"]["definitional_invariants"] if not i["clean"]]
    print(f"Wrote {json_path}")
    print(f"Window: {payload['window']['start_timestamp']} -> {payload['window']['end_timestamp']}")
    print(f"Bars: {payload['window']['total_bars']} across {args.trading_days} trading days "
          f"{list(bars_per_day.values())}")
    geo_status = "ALL MATCH" if geo["all_match"] else f"{len(geo['mismatches'])} MISMATCHES"
    print(f"Geometry verification: {geo['total_checks']} checks, {geo_status}")
    print(f"Definitional invariants: {len(payload['contradiction_scan']['definitional_invariants']) - len(inv_bad)}"
          f"/{len(payload['contradiction_scan']['definitional_invariants'])} clean")
    for i in inv_bad:
        print(f"   FIRES ({i['violations']}): {i['invariant']}")
    for p in payload["contradiction_scan"]["semantic_mismatch_predicates"]:
        print(f"   {p['occurrences']:>4} ({p['pct_of_window']:5.2f}%)  {p['predicate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
