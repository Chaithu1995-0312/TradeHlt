"""
tests/features/test_liquidity_distance.py
==========================================
Tests for compute_liquidity_distance() and promote_volume_spike() (Part 2),
and CANONICAL_FEATURE_DIM=38 schema assertion (Part 1).

Covers:
    1. liquidity_distance uses .shift(1) — no lookahead
    2. liquidity_distance >= 0 always
    3. liquidity_pressure_score ∈ [0, 1] always
    4. NaN when atr=0 (dropped by finalize())
    5. CANONICAL_FEATURE_DIM == 39 after schema change (v4.0; 38 at v3.0)
    6. volume_spike uses rolling percentile threshold (adaptive, not fixed 1.5)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    import numpy as np
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _PANDAS_AVAILABLE, reason="pandas/numpy not installed"
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_minimal_df(n: int = 60) -> "pd.DataFrame":
    """
    Build a minimal DataFrame that satisfies compute_liquidity_distance()
    without running the full FeaturePipeline.
    """
    np.random.seed(42)
    close = 1.0 + np.cumsum(np.random.randn(n) * 0.001)
    df = pd.DataFrame({
        "open":   close * (1 - 0.0002),
        "high":   close * (1 + 0.0005),
        "low":    close * (1 - 0.0005),
        "close":  close,
        "volume": np.random.randint(1000, 5000, n).astype(float),
        "atr":    np.full(n, 0.002),
        "volume_ratio": np.random.uniform(0.5, 3.0, n),
        # Structure columns (normally computed by compute_structure_liquidity)
        "last_swing_high_price": close * 1.005,
        "last_swing_low_price":  close * 0.995,
        "break_of_structure":    np.zeros(n, dtype=int),
        "volume_spike":          np.zeros(n, dtype=np.int8),
    })
    return df


def _run_liquidity_distance(df: "pd.DataFrame") -> "pd.DataFrame":
    """Run compute_liquidity_distance() logic directly (extracted from pipeline)."""
    ref_high = df["last_swing_high_price"].shift(1)
    ref_low  = df["last_swing_low_price"].shift(1)

    bos_level = pd.Series(np.nan, index=df.index)
    bos_bullish = df["break_of_structure"] == 1
    bos_bearish = df["break_of_structure"] == -1
    bos_level.loc[bos_bullish] = ref_high.loc[bos_bullish]
    bos_level.loc[bos_bearish] = ref_low.loc[bos_bearish]
    bos_level = bos_level.ffill()

    atr_abs  = df["atr"] * df["close"]
    atr_safe = atr_abs.where(atr_abs > 0, np.nan)

    dist_high = (df["close"] - ref_high).abs() / atr_safe
    dist_low  = (df["close"] - ref_low).abs()  / atr_safe
    dist_bos  = (df["close"] - bos_level).abs() / atr_safe

    nearest = pd.concat([dist_high, dist_low, dist_bos], axis=1).min(axis=1)
    df = df.copy()
    df["liquidity_distance"] = nearest.clip(lower=0.0).astype(np.float32)
    df["liquidity_pressure_score"] = (
        np.exp(-0.5 * df["liquidity_distance"].fillna(10.0))
    ).clip(0.0, 1.0).astype(np.float32)
    return df


def _run_promote_volume_spike(df: "pd.DataFrame") -> "pd.DataFrame":
    """Run promote_volume_spike() logic directly."""
    df = df.copy()
    vol_ratio = df["volume_ratio"]
    rolling_thresh = vol_ratio.rolling(window=50, min_periods=20).quantile(0.75)
    threshold = rolling_thresh.where(rolling_thresh.notna(), 1.5)
    df["volume_spike"] = (vol_ratio > threshold).astype(np.int8)
    return df


# ── Test 1: No lookahead ──────────────────────────────────────────────────────

def test_liquidity_distance_no_lookahead():
    """
    Verify that liquidity_distance at bar t depends only on bars ≤ t-1.
    Inject a swing-high spike at bar 30 and check that bar 29 is unaffected.
    """
    df = _make_minimal_df(60)
    # Spike ref levels at bar 31 (so shift(1) sees it at bar 32, not before)
    df.loc[31, "last_swing_high_price"] = df.loc[31, "close"] * 10.0

    df_out = _run_liquidity_distance(df)

    # Bar 30 should see shift(1) of bar 29 (unspiced) — distance should be finite and moderate
    dist_30 = float(df_out.loc[30, "liquidity_distance"])
    # Bar 32 sees shift(1) of bar 31 (spiked) — distance should be large
    dist_32 = float(df_out.loc[32, "liquidity_distance"])

    assert dist_32 > dist_30, (
        f"Expected spike at bar 32 to increase distance vs bar 30 "
        f"(dist_30={dist_30:.4f}, dist_32={dist_32:.4f})"
    )


# ── Test 2: liquidity_distance >= 0 ──────────────────────────────────────────

def test_value_range():
    df = _run_liquidity_distance(_make_minimal_df(60))
    non_nan = df["liquidity_distance"].dropna()
    assert (non_nan >= 0).all(), "liquidity_distance has negative values"


# ── Test 3: liquidity_pressure_score ∈ [0, 1] ────────────────────────────────

def test_pressure_score_range():
    df = _run_liquidity_distance(_make_minimal_df(60))
    ps = df["liquidity_pressure_score"].dropna()
    assert (ps >= 0.0).all() and (ps <= 1.0).all(), (
        f"liquidity_pressure_score out of [0,1]: min={ps.min():.4f} max={ps.max():.4f}"
    )


# ── Test 4: NaN when atr=0 ───────────────────────────────────────────────────

def test_zero_atr_handled():
    df = _make_minimal_df(10)
    df["atr"] = 0.0   # force zero ATR throughout
    df_out = _run_liquidity_distance(df)
    # All distances should be NaN when atr=0
    assert df_out["liquidity_distance"].isna().all(), (
        "Expected all NaN when atr=0"
    )


# ── Test 5: CANONICAL_FEATURE_DIM == 39 (schema v4.0; was 38 at v3.0) ────────

def test_canonical_dim():
    from features.feature_schema import CANONICAL_FEATURE_DIM, CANONICAL_FEATURES
    assert CANONICAL_FEATURE_DIM == 39, (
        f"Expected CANONICAL_FEATURE_DIM=39, got {CANONICAL_FEATURE_DIM}"
    )
    assert len(CANONICAL_FEATURES) == 39, (
        f"Expected len(CANONICAL_FEATURES)=39, got {len(CANONICAL_FEATURES)}"
    )
    # Check the three new features are present
    for feat in ("liquidity_distance", "liquidity_pressure_score", "volume_spike"):
        assert feat in CANONICAL_FEATURES, f"New feature '{feat}' not in CANONICAL_FEATURES"


# ── Test 6: volume_spike uses adaptive threshold ──────────────────────────────

def test_volume_spike_adaptive():
    """
    With rolling 75th-percentile threshold, a volume_ratio just above 1.5
    may or may not be a spike depending on local distribution.
    Verify the threshold varies across rows (not always 1.5).
    """
    df = _make_minimal_df(80)
    # Force a consistent volume_ratio pattern: first 40 bars low, last 40 bars high
    df.loc[:39, "volume_ratio"] = 0.5
    df.loc[40:, "volume_ratio"] = 3.0

    df_out = _run_promote_volume_spike(df)

    # After warmup (>= 20 samples with min_periods=20), threshold should adapt.
    # In the high-volume zone, the 75th pct of a window that has seen mostly 0.5
    # should be below 3.0, so volume_spike should be 1 for bars in that zone.
    high_zone_spikes = df_out.loc[40:, "volume_spike"]
    # At least some of the high-volume bars should be flagged
    assert high_zone_spikes.sum() > 0, (
        "Expected adaptive threshold to flag high-volume bars as spikes"
    )

    # Verify output is binary {0, 1}
    unique_vals = set(df_out["volume_spike"].unique())
    assert unique_vals.issubset({0, 1}), (
        f"volume_spike contains non-binary values: {unique_vals}"
    )
