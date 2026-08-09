"""
test_feature_pipeline.py
========================
Unit tests for FeaturePipeline and the canonical feature contract.

Categories
----------
1. schema_completeness  — all 32 feature columns exist in output DataFrame
2. vector_size          — vectors.shape == (N, 32)
3. no_nan               — zero NaN in feature matrix
4. deterministic        — running pipeline twice gives identical vectors
5. zero_volume_forex    — volume_ratio == 1.0 when volume is 0
6. swing_structure      — liquidity_sweep and break_of_structure are in {-1, 0, 1}
7. strict_validator     — validate_features raises on missing/extra keys
8. order_integrity      — vector indices align exactly with CANONICAL_FEATURES
"""

import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import FeaturePipeline, build_features, build_feature_vector
from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP
from features.schema_validator import validate_features


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_synthetic_ohlcv(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data with realistic price movement."""
    rng = np.random.default_rng(seed)

    timestamps = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 1.1000 + np.cumsum(rng.normal(0, 0.0002, n))

    # Ensure OHLCV constraints: low ≤ open,close ≤ high
    wick = np.abs(rng.normal(0, 0.0003, n))
    body = rng.normal(0, 0.0002, n)

    open_  = close - body
    high   = np.maximum(open_, close) + wick
    low    = np.minimum(open_, close) - wick
    volume = rng.uniform(100, 2000, n)

    return pd.DataFrame({
        "timestamp": timestamps,
        "open":      open_,
        "high":      high,
        "low":       low,
        "close":     close,
        "volume":    volume,
    })


def _make_zero_volume_ohlcv(n: int = 500) -> pd.DataFrame:
    """Synthetic OHLCV with volume = 0 (Forex scenario)."""
    df = _make_synthetic_ohlcv(n)
    df["volume"] = 0.0
    return df


@pytest.fixture
def enriched_output():
    df = _make_synthetic_ohlcv(500)
    pipeline = FeaturePipeline(df)
    return pipeline.run()


# ---------------------------------------------------------------------------
# Test 1 — Schema completeness
# ---------------------------------------------------------------------------

def test_schema_completeness(enriched_output):
    """All 32 features in CANONICAL_FEATURES must be present in the output DataFrame."""
    df, _vectors = enriched_output
    missing = [col for col in CANONICAL_FEATURES if col not in df.columns]
    assert not missing, f"Missing columns in output DataFrame: {missing}"


# ---------------------------------------------------------------------------
# Test 2 — Vector size
# ---------------------------------------------------------------------------

def test_vector_size(enriched_output):
    """Feature vector must have exactly 32 columns."""
    _df, vectors = enriched_output
    assert vectors.ndim == 2, "vectors must be 2-dimensional"
    assert vectors.shape[1] == len(CANONICAL_FEATURES), (
        f"Expected vector width {len(CANONICAL_FEATURES)}, got {vectors.shape[1]}"
    )


def test_vector_row_count_matches_df(enriched_output):
    """Number of vector rows must equal number of DataFrame rows."""
    df, vectors = enriched_output
    assert vectors.shape[0] == len(df), (
        f"Row count mismatch: vectors={vectors.shape[0]}, df={len(df)}"
    )


# ---------------------------------------------------------------------------
# Test 3 — No NaN
# ---------------------------------------------------------------------------

def test_no_nan_in_vectors(enriched_output):
    """Feature matrix must contain zero NaN values."""
    _df, vectors = enriched_output
    nan_mask = np.isnan(vectors)
    assert not nan_mask.any(), (
        f"NaN found at positions: {np.argwhere(nan_mask).tolist()[:10]}"
    )


def test_no_nan_in_dataframe(enriched_output):
    """Output DataFrame must have no NaN in any CANONICAL_FEATURES column."""
    df, _vectors = enriched_output
    for col in CANONICAL_FEATURES:
        nan_count = df[col].isna().sum()
        assert nan_count == 0, f"Column '{col}' has {nan_count} NaN(s)"


# ---------------------------------------------------------------------------
# Test 4 — Deterministic ordering
# ---------------------------------------------------------------------------

def test_deterministic_same_seed():
    """Running pipeline twice on identical data must produce identical vectors."""
    df1 = _make_synthetic_ohlcv(500, seed=99)
    df2 = _make_synthetic_ohlcv(500, seed=99)

    _, vectors1 = FeaturePipeline(df1).run()
    _, vectors2 = FeaturePipeline(df2).run()

    np.testing.assert_array_equal(
        vectors1, vectors2,
        err_msg="Pipeline is not deterministic: vectors differ on identical input"
    )


def test_deterministic_feature_order():
    """Column order in vectors must match CANONICAL_FEATURES exactly."""
    df = _make_synthetic_ohlcv(500)
    pipeline = FeaturePipeline(df)
    enriched_df, vectors = pipeline.run()

    # Re-extract manually and compare
    manual = enriched_df[list(CANONICAL_FEATURES)].astype(np.float32).values
    np.testing.assert_array_equal(
        vectors, manual,
        err_msg="build_feature_vector() column order does not match CANONICAL_FEATURES"
    )


# ---------------------------------------------------------------------------
# Test 5 — Zero volume / Forex safe
# ---------------------------------------------------------------------------

def test_zero_volume_ratio():
    """Phase-1 identity: all-zero source volume is preserved (FEAT-VOLUME).

    volume_ratio binds to source volume → sentinel 1.0 when ma20 is 0.
    Price-range proxy is emitted under volume_range_proxy (not under volume).
    """
    df = _make_zero_volume_ohlcv(500)
    pipeline = FeaturePipeline(df)
    enriched_df, _vectors = pipeline.run()

    import numpy as np
    # Source volume identity preserved
    assert (enriched_df["volume"].fillna(0.0) == 0.0).all()
    # Explicit proxy identity
    assert "volume_range_proxy" in enriched_df.columns
    proxy = enriched_df["volume_range_proxy"]
    assert (proxy == (enriched_df["high"] - enriched_df["low"])).all()
    assert (proxy > 0).any(), "expected non-zero price-range proxy on synthetic data"
    # volume_ratio stays on source path
    ratio_col = enriched_df["volume_ratio"].dropna()
    assert len(ratio_col) > 0
    assert (ratio_col == 1.0).all(), "source-volume ratio sentinel must be 1.0 when volume dead"
    assert not np.isinf(ratio_col).any()
    # Proxy ratio under distinct name
    assert "volume_range_proxy_ratio" in enriched_df.columns
    pr = enriched_df["volume_range_proxy_ratio"].dropna()
    assert (pr > 0).all()


def test_zero_volume_no_spike():
    """All-zero source volume: volume_spike remains binary {0,1} on source ratio path.

    Schema v3.0: volume_spike is a canonical feature (Part 2 — promote_volume_spike).
    """
    df = _make_zero_volume_ohlcv(500)
    pipeline = FeaturePipeline(df)
    enriched_df, _ = pipeline.run()

    spike = enriched_df["volume_spike"]
    assert spike.dtype == "int8", f"volume_spike must be int8, got {spike.dtype}"
    assert not spike.isna().any(), "volume_spike must not contain NaN"
    unique_vals = set(spike.unique())
    assert unique_vals.issubset({0, 1}), (
        f"volume_spike must be binary {{0,1}}, got {unique_vals}"
    )
    # No same-name proxy substitution
    assert (enriched_df["volume"].fillna(0.0) == 0.0).all()


def test_missing_volume_column():
    """DataFrame without a 'volume' column is a fatal schema violation.

    Strict-schema enforcement (no silent auto-fill): the pipeline must raise
    rather than synthesize the missing column.
    """
    df = _make_synthetic_ohlcv(500).drop(columns=["volume"])
    with pytest.raises(ValueError, match="missing required columns: volume"):
        FeaturePipeline(df).run()


# ---------------------------------------------------------------------------
# Test 6 — Swing / structure / liquidity
# ---------------------------------------------------------------------------

def test_break_of_structure_valid_values(enriched_output):
    """break_of_structure must only contain values {-1, 0, 1}."""
    df, _ = enriched_output
    valid = {-1, 0, 1}
    unique = set(df["break_of_structure"].unique())
    assert unique.issubset(valid), (
        f"break_of_structure contains unexpected values: {unique - valid}"
    )


def test_liquidity_sweep_valid_values(enriched_output):
    """liquidity_sweep must only contain values {-1, 0, 1}."""
    df, _ = enriched_output
    valid = {-1, 0, 1}
    unique = set(df["liquidity_sweep"].unique())
    assert unique.issubset(valid), (
        f"liquidity_sweep contains unexpected values: {unique - valid}"
    )


def test_higher_high_lower_low_binary(enriched_output):
    """higher_high and lower_low must be binary (0 or 1)."""
    df, _ = enriched_output
    for col in ("higher_high", "lower_low"):
        unique = set(df[col].unique())
        assert unique.issubset({0, 1}), (
            f"'{col}' contains non-binary values: {unique}"
        )


def test_swing_high_implies_higher_high_possible(enriched_output):
    """At least one higher_high should exist in a trending synthetic series."""
    df, _ = enriched_output
    assert df["higher_high"].sum() > 0, (
        "No higher_high detected — swing logic may be broken"
    )


def test_retest_flag_uses_recent_sweep_not_bos():
    """Retest should trigger from recent sweep even when BOS is zero."""
    seed_df = _make_synthetic_ohlcv(10)
    pipeline = FeaturePipeline(seed_df)

    pipeline.df = pd.DataFrame({
        "liquidity_sweep": [0, 1, 0],
        "break_of_structure": [0, 0, 0],
        "body_size": [0.8, 0.8, 0.8],
        "candle_range": [1.0, 1.0, 1.0],
        "atr": [0.01, 0.01, 0.01],
        "close": [100.0, 100.0, 100.0],
        "ema_fast": [100.0, 100.0, 100.0],
    })

    pipeline.compute_canonical_structure_features()
    out = pipeline.df

    assert int(out.loc[2, "retest_flag"]) == 1, "Expected retest after prior sweep"
    assert int(out["break_of_structure"].sum()) == 0, "BOS must remain unused in this test"
    assert int(out["displacement_flag"].sum()) > 0, "Displacement should be candle-based"


def test_disp_strength_nonzero_without_bos():
    """disp_strength should not require BOS."""
    seed_df = _make_synthetic_ohlcv(10)
    pipeline = FeaturePipeline(seed_df)

    pipeline.df = pd.DataFrame({
        "break_of_structure": [0, 0, 0],
        "body_size": [0.2, 0.4, 0.6],
        "atr": [0.01, 0.01, 0.01],
        "close": [100.0, 100.0, 100.0],
        "retest_flag": [0, 0, 0],
        "ema_fast": [100.0, 100.0, 100.0],
    })

    pipeline.compute_canonical_temporal_features()
    out = pipeline.df

    assert float(out["disp_strength"].max()) > 0.0, "disp_strength should activate from candle strength"


# ---------------------------------------------------------------------------
# Test 7 — Input validation
# ---------------------------------------------------------------------------

def test_missing_required_column():
    """Pipeline must raise ValueError when a required column is absent."""
    df = _make_synthetic_ohlcv(500).drop(columns=["close"])
    with pytest.raises(ValueError, match="missing required columns"):
        FeaturePipeline(df)


def test_vector_dtype_float32(enriched_output):
    """Feature vectors must be float32."""
    _, vectors = enriched_output
    assert vectors.dtype == np.float32, (
        f"Expected float32, got {vectors.dtype}"
    )


# ---------------------------------------------------------------------------
# Test 8 — Warmup handling
# ---------------------------------------------------------------------------

def test_warmup_rows_dropped():
    """After warmup (ma_200 needs ≥200 bars), output must be shorter than input."""
    n = 500
    df = _make_synthetic_ohlcv(n)
    enriched_df, _ = FeaturePipeline(df).run()
    assert len(enriched_df) < n, (
        "Warmup rows were not dropped — finalize() may not be working"
    )


# ---------------------------------------------------------------------------
# Test 9 — Volatility regime
# ---------------------------------------------------------------------------

def test_volatility_regime_values(enriched_output):
    """volatility_regime must be in {0, 1, 2}."""
    df, _ = enriched_output
    unique = set(df["volatility_regime"].unique())
    assert unique.issubset({0, 1, 2}), (
        f"volatility_regime contains unexpected values: {unique}"
    )


# ---------------------------------------------------------------------------
# Test 10 — Session encoding
# ---------------------------------------------------------------------------

def test_session_encoding(enriched_output):
    """FM-052 v4.0: session is a 5-value WINDOW classification, and the pipeline must agree with
    `session_classifier` — the single owner — rather than re-deriving the table here.

    v3.0 asserted `issubset({0, 1, 2})` against a 3-value hour partition. The hour->session table
    itself is pinned once, in tests/test_session_classifier.py; duplicating it here is how the
    encodings drifted apart in the first place (feature_schema.SESSION_MAP vs the pipeline).
    """
    from features.session_classifier import SessionOrdinal, classify_session_feature

    df, _ = enriched_output
    unique = set(int(v) for v in df["session"].unique())
    assert unique.issubset({int(s) for s in SessionOrdinal}), (
        f"session contains values outside the FM-052 domain: {unique}"
    )
    # every emitted value must equal what the owning classifier says for that bar's hour
    sample = df[["hour_of_day", "session"]].drop_duplicates().head(50)
    for _, row in sample.iterrows():
        assert int(row["session"]) == classify_session_feature(int(row["hour_of_day"])), (
            f"pipeline disagrees with session_classifier at hour {int(row['hour_of_day'])}"
        )


# ---------------------------------------------------------------------------
# Test 11 — Normalized features mean/std
# ---------------------------------------------------------------------------

def test_normalized_features_mean_std():
    df = _make_synthetic_ohlcv(500)
    enriched_df, _ = FeaturePipeline(df).run()

    # Only columns in NORMALIZE_COLS are z-score normalized — atr_14 is NOT.
    cols = [
        "price_vs_ma20",
        "price_vs_ma50",
        "bb_width",
        # v4.0: `macd_hist_z` is the normalized column. `macd_hist_raw` is deliberately NOT here —
        # it is the un-normalized macd_line - macd_signal, and asserting z-score properties on it
        # would re-assert the exact conflation the split removed.
        "macd_hist_z",
        "trend_strength",
    ]

    for col in cols:
        mean = enriched_df[col].mean()
        std  = enriched_df[col].std()
        assert abs(mean) < 0.5, f"{col} mean too far from 0: {mean}"
        assert std > 0.1,       f"{col} std too small: {std}"


# ===========================================================================
# STRICT SCHEMA VALIDATOR TESTS  (NEW — required by feature contract)
# ===========================================================================

def _make_canonical_features() -> dict:
    """Return a valid dict with all 32 canonical features set to 0.0."""
    return {f: 0.0 for f in CANONICAL_FEATURES}


# ---------------------------------------------------------------------------
# Strict Test 1 — EXACT MATCH must pass validation
# ---------------------------------------------------------------------------

def test_validator_exact_match():
    """
    ✅ validate_features must NOT raise when features exactly match schema.
    """
    features = _make_canonical_features()
    # Should not raise
    validate_features(features, CANONICAL_FEATURES)


# ---------------------------------------------------------------------------
# Strict Test 2 — MISSING FEATURE must raise ValueError
# ---------------------------------------------------------------------------

def test_validator_missing_feature():
    """
    ❌ validate_features MUST raise ValueError when any feature is missing.
    """
    features = _make_canonical_features()
    del features["atr"]  # remove one canonical feature

    with pytest.raises(ValueError) as exc_info:
        validate_features(features, CANONICAL_FEATURES)

    # Verify the error contains structured info
    err = exc_info.value.args[0]
    assert isinstance(err, dict), "ValueError must carry a dict payload"
    assert err["error"] == "FEATURE_SCHEMA_VIOLATION"
    assert "atr" in err["missing"], f"Expected 'atr' in missing, got: {err['missing']}"
    assert err["extra"] == [], f"Expected empty extra, got: {err['extra']}"


# ---------------------------------------------------------------------------
# Strict Test 3 — EXTRA FEATURE must raise ValueError
# ---------------------------------------------------------------------------

def test_validator_extra_feature():
    """
    ❌ validate_features MUST raise ValueError when any extra key is present.
    """
    features = _make_canonical_features()
    features["rsi"] = 50.0  # inject a non-canonical key

    with pytest.raises(ValueError) as exc_info:
        validate_features(features, CANONICAL_FEATURES)

    err = exc_info.value.args[0]
    assert isinstance(err, dict), "ValueError must carry a dict payload"
    assert err["error"] == "FEATURE_SCHEMA_VIOLATION"
    assert "rsi" in err["extra"], f"Expected 'rsi' in extra, got: {err['extra']}"
    assert err["missing"] == [], f"Expected empty missing, got: {err['missing']}"


# ---------------------------------------------------------------------------
# Strict Test 4 — ORDER INTEGRITY: vector indices align with CANONICAL_FEATURES
# ---------------------------------------------------------------------------

def test_validator_order_integrity():
    """
    ❌ Vector produced by build_feature_vector must align exactly with
    CANONICAL_FEATURES by index — no reordering allowed.
    """
    # Build a feature dict where each value is its index in the schema
    features = {f: float(i) for i, f in enumerate(CANONICAL_FEATURES)}

    # Validate passes (exact match)
    validate_features(features, CANONICAL_FEATURES)

    # Build vector
    vector = build_feature_vector(features)

    # Verify: vector[i] == i for all positions
    for i, (feat_name, val) in enumerate(zip(CANONICAL_FEATURES, vector)):
        expected = float(i)
        assert val == expected, (
            f"Order integrity FAIL at index {i}: "
            f"feature '{feat_name}' expected value {expected}, got {val}. "
            f"build_feature_vector() order does not match CANONICAL_FEATURES."
        )

    # Cross-check with FEATURE_INDEX_MAP
    for feat_name in CANONICAL_FEATURES:
        idx = FEATURE_INDEX_MAP[feat_name]
        assert vector[idx] == float(idx), (
            f"FEATURE_INDEX_MAP['{feat_name}'] = {idx} but vector[{idx}] = {vector[idx]}"
        )


# ---------------------------------------------------------------------------
# Strict Test 5 — CANONICAL_FEATURES is immutable (tuple)
# ---------------------------------------------------------------------------

def test_canonical_features_is_tuple():
    """CANONICAL_FEATURES must be a tuple to prevent accidental mutation."""
    assert isinstance(CANONICAL_FEATURES, tuple), (
        f"CANONICAL_FEATURES must be tuple, got {type(CANONICAL_FEATURES).__name__}"
    )


# ---------------------------------------------------------------------------
# Strict Test 6 — FEATURE_INDEX_MAP covers all features
# ---------------------------------------------------------------------------

def test_feature_index_map_completeness():
    """FEATURE_INDEX_MAP must contain all features with correct indices."""
    assert len(FEATURE_INDEX_MAP) == len(CANONICAL_FEATURES), (
        f"FEATURE_INDEX_MAP has {len(FEATURE_INDEX_MAP)} entries, "
        f"expected {len(CANONICAL_FEATURES)}"
    )
    for i, name in enumerate(CANONICAL_FEATURES):
        assert name in FEATURE_INDEX_MAP, f"'{name}' missing from FEATURE_INDEX_MAP"
        assert FEATURE_INDEX_MAP[name] == i, (
            f"FEATURE_INDEX_MAP['{name}'] = {FEATURE_INDEX_MAP[name]}, expected {i}"
        )


# ===========================================================================
# GAP-012 — FeatureMonitor integration tests
# ===========================================================================

def test_pipeline_monitor_populated_after_run():
    """GAP-012: FeaturePipeline.monitor must have samples after run()."""
    df = _make_synthetic_ohlcv(500)
    pipeline = FeaturePipeline(df)
    assert len(pipeline.monitor) == 0, "Monitor should be empty before run()"
    pipeline.run()
    assert len(pipeline.monitor) > 0, "Monitor must be populated after run()"


def test_pipeline_monitor_injected_instance_is_shared():
    """GAP-012: injected monitor accumulates across multiple run() calls."""
    from features.feature_monitor import FeatureMonitor
    shared = FeatureMonitor(window_size=1000)

    df1 = _make_synthetic_ohlcv(300, seed=1)
    df2 = _make_synthetic_ohlcv(300, seed=2)

    FeaturePipeline(df1, monitor=shared).run()
    count_after_first = len(shared)
    FeaturePipeline(df2, monitor=shared).run()
    count_after_second = len(shared)

    assert count_after_second > count_after_first, (
        "Shared monitor must accumulate samples across pipeline runs"
    )


def test_pipeline_monitor_no_drift_on_clean_data():
    """GAP-012: clean synthetic data should not trigger drift on most rows."""
    from features.feature_monitor import FeatureMonitor
    df = _make_synthetic_ohlcv(500)
    pipeline = FeaturePipeline(df)
    pipeline.run()

    # After a full run, the monitor should have samples and no extreme drift
    stats = pipeline.monitor.stats()
    assert stats.get("n_samples", 0) > 0
    # Soft-drift rate (Z>2.5) can reach ~10% due to retest_depth's skewed
    # distribution (77% zeros). Assert on hard-drift rate (Z>3.0) instead —
    # that is the signal actually used to block trades.
    from features.feature_monitor import DEFAULT_DRIFT_THRESHOLD
    n_samples = stats.get("n_samples", 0)
    hard_drift = sum(
        1 for _, row in pipeline.df[["retest_depth", "body_ratio", "disp_strength"]].iterrows()
        if pipeline.monitor.detect_drift_severity(row.to_dict()) == "hard"
    ) if n_samples > 0 else 0
    hard_drift_rate = hard_drift / max(stats.get("n_total", 1), 1)
    assert hard_drift_rate < 0.05, (
        f"Hard-drift rate {hard_drift_rate:.1%} too high on clean synthetic data — "
        "monitor hard-threshold (Z>3.0) may be miscalibrated"
    )


def test_pipeline_monitor_detects_extreme_drift():
    """GAP-012: monitor must fire on extreme out-of-distribution features."""
    from features.feature_monitor import FeatureMonitor

    monitor = FeatureMonitor(window_size=200)
    # Feed 50 normal samples directly
    import random
    random.seed(0)
    for _ in range(50):
        monitor.update({
            "retest_depth":  random.uniform(0.2, 0.6),
            "body_ratio":    random.uniform(0.4, 0.8),
            "disp_strength": random.uniform(0.1, 0.4),
        })

    extreme = {"retest_depth": 0.99, "body_ratio": 0.99, "disp_strength": 0.99}
    severity = monitor.detect_drift_severity(extreme)
    assert severity in ("soft", "hard"), (
        f"Expected soft/hard drift for extreme features, got '{severity}'"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
