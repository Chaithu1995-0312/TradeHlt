# -*- coding: utf-8 -*-
"""
test_finalize_survivorship.py
=============================
Regression tests for the Phase 0 FeaturePipeline survivorship fix.

Root cause that prompted these tests:
  FeaturePipeline.compute_canonical_temporal_features() wrote np.nan to
  retest_depth on every bar where retest_flag != 1.  retest_depth is a
  member of CANONICAL_FEATURES, so finalize()'s dropna(subset=...) silently
  deleted ~52% of bars (54,278 of 105,206 on ETHUSDT M15), breaking the
  timestamp→row-index lookup map used by BacktestRunner.

Fix (committed, Phase 0):
  np.nan → 0.0 on non-retest bars.

These tests encode the post-fix contract so a regression would be caught
in CI before reaching production.

References:
  src/features/feature_pipeline.py — compute_canonical_temporal_features()
  src/features/feature_pipeline.py — finalize()
  src/features/feature_schema.py   — CANONICAL_FEATURES
"""

import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import FeaturePipeline


# ---------------------------------------------------------------------------
# Shared OHLCV generator (self-contained to keep this file independent)
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 2000, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic OHLCV data with realistic price movement.
    Uses n=2000 by default so warmup rows (~300 max) stay well under the
    2% survivorship budget.
    """
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 1.1000 + np.cumsum(rng.normal(0, 0.0002, n))
    wick  = np.abs(rng.normal(0, 0.0003, n))
    body  = rng.normal(0, 0.0002, n)
    open_ = close - body
    high  = np.maximum(open_, close) + wick
    low   = np.minimum(open_, close) - wick
    volume = rng.uniform(100, 2000, n)
    return pd.DataFrame({
        "timestamp": timestamps,
        "open":      open_.astype(np.float64),
        "high":      high.astype(np.float64),
        "low":       low.astype(np.float64),
        "close":     close.astype(np.float64),
        "volume":    volume.astype(np.float64),
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFinalizeSurvivorship:
    """Drop budget and retest_depth correctness after the Phase 0 fix."""

    def test_finalize_drop_pct_within_budget(self):
        """
        finalize() must not drop more than max(300, 2% of input) rows.

        Budget formula mirrors the survivorship guard in finalize() itself
        (feature_pipeline.py).  This test catches a regression to the
        pre-fix state where ~52% of rows were silently deleted.
        """
        df = _make_ohlcv(n=2000, seed=42)
        enriched, _ = FeaturePipeline(df).run()

        n_before   = len(df)
        n_after    = len(enriched)
        drop_count = n_before - n_after
        budget     = max(300, int(n_before * 0.02))   # mirrors finalize() guard

        assert drop_count <= budget, (
            f"finalize() dropped {drop_count}/{n_before} rows "
            f"(budget={budget}, {100*drop_count/n_before:.1f}%). "
            f"Likely NaN in CANONICAL_FEATURES — check retest_depth or recent "
            f"feature additions."
        )

    def test_retest_depth_has_no_nan(self):
        """
        retest_depth must be 0.0 (not NaN) on non-retest bars after the fix.

        Pre-fix: np.where(..., computed_value, np.nan) → NaN on ~52% of bars.
        Post-fix: np.where(..., computed_value, 0.0)   → 0.0 on non-retest bars.
        """
        df = _make_ohlcv(n=1000, seed=42)
        enriched, _ = FeaturePipeline(df).run()

        assert "retest_depth" in enriched.columns, (
            "retest_depth column missing from enriched DataFrame"
        )
        nan_count = enriched["retest_depth"].isna().sum()
        assert nan_count == 0, (
            f"retest_depth contains {nan_count} NaN values — Phase 0 fix regressed. "
            f"Check compute_canonical_temporal_features() in feature_pipeline.py."
        )

    def test_retest_depth_non_negative(self):
        """retest_depth is clipped [0, 1] so all values must be >= 0."""
        df = _make_ohlcv(n=1000, seed=7)
        enriched, _ = FeaturePipeline(df).run()
        assert (enriched["retest_depth"] >= 0.0).all(), (
            "retest_depth contains negative values — clip(0, 1) not applied"
        )

    def test_non_retest_bars_have_zero_retest_depth(self):
        """
        On bars where retest_flag != 1, retest_depth must be exactly 0.0.

        This is the direct contract of the np.where fix:
          np.where(retest_flag == 1, computed_value, 0.0)
        """
        df = _make_ohlcv(n=1000, seed=42)
        enriched, _ = FeaturePipeline(df).run()

        if "retest_flag" not in enriched.columns:
            pytest.skip("retest_flag column not present in enriched output — skipping")

        non_retest_mask = enriched["retest_flag"] != 1
        non_retest_df   = enriched[non_retest_mask]

        if len(non_retest_df) == 0:
            pytest.skip("No non-retest bars in synthetic data — skipping")

        wrong = (non_retest_df["retest_depth"] != 0.0).sum()
        assert wrong == 0, (
            f"{wrong} non-retest bars have retest_depth != 0.0. "
            f"The np.where fallback must be 0.0, not NaN or any other value."
        )

    def test_feature_vectors_no_nan(self):
        """
        The feature matrix (N, K) produced by FeaturePipeline.run() must
        contain no NaN values — these would produce silent zero-feature trades.
        """
        df = _make_ohlcv(n=1000, seed=99)
        _, vectors = FeaturePipeline(df).run()

        nan_count = np.isnan(vectors).sum()
        assert nan_count == 0, (
            f"Feature matrix contains {nan_count} NaN values. "
            f"All NaN should have been eliminated by finalize()."
        )

    def test_enriched_row_count_exceeds_warmup_floor(self):
        """
        After finalize(), the enriched DataFrame must contain significantly
        more rows than just the warmup period.

        Warmup maximum: ~300 rows (ma_200 + z-score + swing edges).
        A 1000-row input should produce ≥ 700 enriched rows.
        This test fails loudly if the 52%-drop regression recurs.
        """
        df = _make_ohlcv(n=1000, seed=42)
        enriched, _ = FeaturePipeline(df).run()

        n_input  = len(df)
        n_output = len(enriched)
        assert n_output >= n_input * 0.70, (
            f"Only {n_output}/{n_input} rows survived finalize() "
            f"({100*n_output/n_input:.1f}%). Expected ≥ 70%. "
            f"Check retest_depth NaN regression."
        )
