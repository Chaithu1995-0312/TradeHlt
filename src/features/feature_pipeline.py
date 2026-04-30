"""
feature_pipeline.py
====================
Production-grade feature engineering pipeline for M15 OHLCV data.

Produces a deterministic 32-length BitNet feature vector aligned to
CANONICAL_FEATURES from features.feature_schema.py (the single source of truth).

Only pandas + numpy are used (no TA-lib or other external TA libraries).

Pipeline contract
-----------------
    build_features(row)        → Dict[str, float]   (32 canonical keys)
    validate_features(f, schema)                     (fail-fast — no return)
    build_feature_vector(f)    → List[float]         (32 values, strict order)

Batch usage
-----------
    pipeline = FeaturePipeline(df)
    enriched_df, vectors = pipeline.run()
    # Drift report available after run():
    print(pipeline.monitor.summary())

Edge Cases:
    - Zero volume (Forex): volume_ratio is set to 1.0 when volume_ma20 == 0.
    - Flat market (ATR ≈ 0): bb_position has a 1e-9 denominator guard.
    - Warmup NaNs: finalize() drops all NaN rows. With ma_200 the warmup is ≥ 200
      bars; callers must ensure sufficient history.

Failure Modes:
    - Feature drift: pipeline is stateless. If market regime shifts, retrain.
    - Lookahead bias: swing reference prices use .shift(1) so current-bar data
      never influences the same bar's BOS/sweep decision.
    - Swing detection uses center=True rolling — valid for historical backtesting.
      For live inference, replace with a trailing-only swing detector.
"""

import math
import logging
from typing import Optional

import pandas as pd
import numpy as np

from features.feature_schema import CANONICAL_FEATURES
from features.schema_validator import validate_features, validate_feature_values, validate_vector
from features.feature_monitor import FeatureMonitor
from utils.logging_config import get_flow_logger

logger = get_flow_logger("FEATURE_PIPELINE")

SWING_WINDOW = 2  # ±2 candles for swing detection

# Columns subject to rolling z-score normalization (MUST NOT include
# categoricals, RSI, volume_ratio, or placeholder scalars)
NORMALIZE_COLS = [
    "price_vs_ma20",
    "price_vs_ma50",
    "bb_width",
    "macd_hist",
    "trend_strength",
]


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE FUNCTIONS (canonical pipeline contract)
# ─────────────────────────────────────────────────────────────────────────────

def build_features(row: "pd.Series") -> dict:
    """
    Compute all 32 canonical features from a single enriched DataFrame row.

    The row MUST come from a DataFrame that has been processed by
    FeaturePipeline.run() — i.e., all intermediate columns must be present.

    CANONICAL_FEATURES (32 keys) is the SINGLE SOURCE OF TRUTH.
    This function returns EXACTLY those keys — no more, no less.

    Args:
        row: a single pandas Series from the enriched DataFrame

    Returns:
        dict with EXACTLY the 32 canonical keys from CANONICAL_FEATURES

    Raises:
        ValueError: if any required column is missing from row
        ValueError: if any computed feature is NaN or infinite
    """
    required_cols = list(CANONICAL_FEATURES)
    missing_cols = [c for c in required_cols if c not in row.index]
    if missing_cols:
        raise ValueError(
            f"build_features: row is missing required columns: {missing_cols}. "
            "Ensure FeaturePipeline.run() has been called on the DataFrame first."
        )

    # Build dict with all 32 canonical features — exact keys, float values
    features = {col: float(row[col]) for col in CANONICAL_FEATURES}

    # NaN guard — fail fast rather than poisoning the model
    for k, v in features.items():
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            raise ValueError(
                f"build_features: feature '{k}' = {v} is invalid (NaN/inf/None). "
                "Check input data quality or warmup period."
            )

    return features

def build_feature_vector(features: dict) -> list:
    """
    Convert a canonical feature dict to a deterministically-ordered list.

    Order is defined by CANONICAL_FEATURES (imported from features.feature_schema).
    This is the ONLY place where dict → vector conversion happens.

    Args:
        features: canonical feature dict (MUST pass validate_features first)

    Returns:
        list of 32 floats in canonical order
    """
    return [features[f] for f in CANONICAL_FEATURES]


# ─────────────────────────────────────────────────────────────────────────────
# BATCH PIPELINE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class FeaturePipeline:
    """
    Full feature engineering pipeline for batch DataFrame processing.

    Usage
    -----
    >>> pipeline = FeaturePipeline(df)
    >>> enriched_df, vectors = pipeline.run()
    >>> print(pipeline.monitor.summary())   # drift report after run()

    The enriched DataFrame can then be used row-by-row with build_features().
    A FeatureMonitor is attached automatically and updated with every row
    produced by run() so that drift statistics accumulate across batches when
    the same pipeline instance is reused (e.g. incremental live data ingestion).
    """

    def __init__(self, df: pd.DataFrame, monitor: Optional[FeatureMonitor] = None):
        self.df = df.copy()
        # Drift monitor: injected or created fresh (window_size=500 default).
        # Pass an existing monitor to accumulate statistics across multiple run() calls.
        self.monitor: FeatureMonitor = monitor if monitor is not None else FeatureMonitor()
        self._validate_input()

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------
    def _validate_input(self) -> None:
        required = ["timestamp", "open", "high", "low", "close"]
        missing = [c for c in required if c not in self.df.columns]
        if missing:
            raise ValueError(f"FeaturePipeline: missing required columns: {missing}")

        if "volume" not in self.df.columns:
            self.df["volume"] = 0.0  # Forex safe fallback

        # Coerce numeric columns
        for col in ["open", "high", "low", "close", "volume"]:
            self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

    # ------------------------------------------------------------------
    # PRICE FEATURES
    # ------------------------------------------------------------------
    def compute_price_features(self) -> None:
        df = self.df

        df["prev_close"] = df["close"].shift(1)
        df["delta_close"] = df["close"] - df["prev_close"]

        df["candle_body"] = df["close"] - df["open"]
        df["upper_wick"] = df["high"] - np.maximum(df["open"], df["close"])
        df["lower_wick"] = np.minimum(df["open"], df["close"]) - df["low"]

        df["direction"] = np.where(
            df["close"] > df["open"], 1,
            np.where(df["close"] < df["open"], -1, 0)
        ).astype(np.int8)

        self.df = df

    # ------------------------------------------------------------------
    # VOLUME FEATURES  (Forex-safe: zero volume → ratio = 1.0)
    # ------------------------------------------------------------------
    def compute_volume_features(self) -> None:
        df = self.df

        df["volume_ma20"] = df["volume"].rolling(20).mean()

        df["volume_ratio"] = np.where(
            df["volume_ma20"] > 0,
            df["volume"] / df["volume_ma20"],
            1.0
        )

        df["volume_spike"] = (df["volume_ratio"] > 1.5).astype(np.int8)

        self.df = df

    # ------------------------------------------------------------------
    # INDICATORS  (pure pandas / numpy — no TA-lib)
    # ------------------------------------------------------------------
    def compute_indicators(self) -> None:
        df = self.df

        # ── Moving Averages ───────────────────────────────────────────
        df["ma_20"] = df["close"].rolling(20).mean()
        df["ma_50"] = df["close"].rolling(50).mean()
        df["ma_200"] = df["close"].rolling(200).mean()

        # ── RSI(14) — kept as intermediate, NOT in canonical output ──
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

        df["rsi_state"] = np.where(
            df["rsi_14"] > 70, 1,
            np.where(df["rsi_14"] < 30, -1, 0)
        ).astype(np.int8)

        # ── ATR(14) ───────────────────────────────────────────────────
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"]  - df["close"].shift(1)).abs()
        df["true_range"] = np.maximum(tr1, np.maximum(tr2, tr3))
        df["atr_14_raw"] = df["true_range"].rolling(14).mean()
        df["atr_14"] = df["atr_14_raw"]

        # ── Bollinger Bands (20, ±2σ) ─────────────────────────────────
        bb_ma = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std(ddof=1)
        df["bb_upper"] = bb_ma + 2.0 * bb_std
        df["bb_lower"] = bb_ma - 2.0 * bb_std
        df["bb_width"] = df["bb_upper"] - df["bb_lower"]
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_width"] + 1e-9)

        # ── MACD (12, 26, 9) ──────────────────────────────────────────
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd_line"] = ema12 - ema26
        df["macd_signal"] = df["macd_line"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd_line"] - df["macd_signal"]

        self.df = df

    # ------------------------------------------------------------------
    # TREND FEATURES
    # ------------------------------------------------------------------
    def compute_trend_features(self) -> None:
        df = self.df

        df["price_vs_ma20"] = df["close"] - df["ma_20"]
        df["price_vs_ma50"] = df["close"] - df["ma_50"]
        df["ma_slope_20"] = df["ma_20"].diff()
        df["trend_strength"] = df["ma_slope_20"].rolling(10).mean()

        self.df = df

    # ------------------------------------------------------------------
    # VOLATILITY REGIME
    # ------------------------------------------------------------------
    def compute_volatility_regime(self) -> None:
        df = self.df

        atr_pct = df["atr_14"].rank(pct=True, method="average")

        df["volatility_regime"] = np.select(
            [atr_pct < 0.33, atr_pct < 0.66],
            [0, 1],
            default=2
        ).astype(np.int8)

        self.df = df

    # ------------------------------------------------------------------
    # CONTEXT FEATURES
    # ------------------------------------------------------------------
    def compute_context(self) -> None:
        df = self.df

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour_of_day"] = df["timestamp"].dt.hour.astype(np.int8)
        df["day_of_week"] = df["timestamp"].dt.dayofweek.astype(np.int8)

        # Session encoding: Asia=0, London=1, NY=2
        hour = df["hour_of_day"]
        df["session"] = np.where(
            hour < 8, 0,
            np.where(hour < 16, 1, 2)
        ).astype(np.int8)

        self.df = df

    # ------------------------------------------------------------------
    # STRUCTURE + LIQUIDITY  (swing detection, BOS, trap logic)
    # ------------------------------------------------------------------
    def compute_structure_liquidity(self) -> None:
        df = self.df
        w = 2 * SWING_WINDOW + 1

        # ── Swing highs / lows ────────────────────────────────────────
        roll_high = df["high"].rolling(w, center=True, min_periods=w).max()
        roll_low  = df["low"].rolling(w, center=True, min_periods=w).min()

        df["swing_high"] = (df["high"] == roll_high).astype(np.int8)
        df["swing_low"]  = (df["low"]  == roll_low).astype(np.int8)

        df["last_swing_high_price"] = df["high"].where(df["swing_high"] == 1).ffill()
        df["last_swing_low_price"]  = df["low"].where(df["swing_low"]  == 1).ffill()

        ref_high = df["last_swing_high_price"].shift(1)
        ref_low  = df["last_swing_low_price"].shift(1)

        df["higher_high"] = (df["high"] > ref_high).astype(np.int8)
        df["lower_low"]   = (df["low"]  < ref_low).astype(np.int8)

        df["break_of_structure"] = np.where(
            df["close"] > ref_high,  1,
            np.where(df["close"] < ref_low, -1, 0)
        ).astype(np.int8)

        sweep_high = (df["high"] > ref_high) & (df["close"] <= ref_high)
        sweep_low  = (df["low"]  < ref_low)  & (df["close"] >= ref_low)

        df["liquidity_sweep"] = np.where(
            sweep_high,  1,
            np.where(sweep_low, -1, 0)
        ).astype(np.int8)

        self.df = df

    # ------------------------------------------------------------------
    # NORMALIZATION  (rolling z-score, 50-bar window)
    # ------------------------------------------------------------------
    def compute_normalization(self) -> None:
        df = self.df
        for col in NORMALIZE_COLS:
            if col not in df.columns:
                raise ValueError(
                    f"compute_normalization: column '{col}' not found. "
                    "Ensure indicators and trend features are computed first."
                )
            rolling_mean = df[col].rolling(50).mean()
            rolling_std  = df[col].rolling(50).std(ddof=1)
            df[col] = (df[col] - rolling_mean) / (rolling_std + 1e-9)
        self.df = df

    # ------------------------------------------------------------------
    # CANONICAL FEATURE COMPUTATION
    # ------------------------------------------------------------------

    def compute_canonical_price_features(self) -> None:
        """Compute body_ratio, wick_size, body_size, price_position from OHLC."""
        df = self.df

        df["body_size"] = (df["close"] - df["open"]).abs()
        df["wick_size"] = df["high"] - df["low"]

        df["body_ratio"] = np.where(
            df["wick_size"] > 0,
            df["body_size"] / df["wick_size"],
            0.0
        ).astype(np.float32)

        df["price_position"] = np.where(
            df["wick_size"] > 0,
            (df["close"] - df["low"]) / df["wick_size"],
            0.5
        ).astype(np.float32)

    def compute_canonical_volatility_features(self) -> None:
        """Compute atr, range_size, volatility_ratio."""
        df = self.df

        df["atr"] = np.where(
            df["close"] > 0,
            df["atr_14_raw"] / df["close"],
            0.0
        ).astype(np.float32)

        range_high = df["high"].rolling(20).max()
        range_low = df["low"].rolling(20).min()
        df["range_size"] = np.where(
            df["close"] > 0,
            (range_high - range_low) / df["close"],
            0.0
        ).astype(np.float32)

        df["volatility_ratio"] = np.where(
            (df["atr"] > 0) & (df["close"] > 0),
            (df["high"] - df["low"]) / (df["atr"] * df["close"]),
            1.0
        ).astype(np.float32)

    def compute_canonical_ema_features(self) -> None:
        """Compute ema_fast, ema_slow, ema_spread, momentum_score."""
        df = self.df

        df["ema_fast"] = df["close"].ewm(span=9, adjust=False).mean().astype(np.float32)
        df["ema_slow"] = df["close"].ewm(span=21, adjust=False).mean().astype(np.float32)

        df["ema_spread"] = np.where(
            df["atr"] > 0,
            (df["ema_fast"] - df["ema_slow"]) / df["atr"],
            0.0
        ).astype(np.float32)

        df["momentum_score"] = np.where(
            df["atr"] > 0,
            df["close"].diff() / df["atr"],
            0.0
        ).astype(np.float32)

    def compute_canonical_trend_features(self) -> None:
        """Compute trend_bias from EMA fast/slow state."""
        df = self.df
        df["trend_bias"] = np.where(
            df["ema_fast"] > df["ema_slow"], 1,
            np.where(df["ema_fast"] < df["ema_slow"], -1, 0)
        ).astype(np.float32)

    def compute_canonical_structure_features(self) -> None:
        """Compute sweep_detected, displacement_flag, retest_flag, double_sweep."""
        df = self.df

        df["sweep_detected"] = (df["liquidity_sweep"] != 0).astype(np.int8)
        # Trap-first displacement marker: strong candle body vs total wick/range.
        strong_body = df["body_size"] > (df["wick_size"] * 0.6)
        df["displacement_flag"] = np.where(
            strong_body & (df["atr"] > 0),
            1,
            0,
        ).astype(np.int8)

        # Retest: after a sweep, price returns close to fast EMA within ATR-based band.
        recent_sweep = (df["liquidity_sweep"] != 0).shift(1).fillna(False)
        near_fast_ema = (df["close"] - df["ema_fast"]).abs() <= (1.0 * df["atr"] * df["close"])
        df["retest_flag"] = (recent_sweep & near_fast_ema).astype(np.int8)

        # Double sweep: both sweep directions seen in a short recent window.
        window = 5
        seen_up = (
            (df["liquidity_sweep"] > 0)
            .rolling(window=window, min_periods=1)
            .max()
            .astype(bool)
        )
        seen_down = (
            (df["liquidity_sweep"] < 0)
            .rolling(window=window, min_periods=1)
            .max()
            .astype(bool)
        )
        df["double_sweep"] = (seen_up & seen_down).astype(np.int8)

    def compute_canonical_temporal_features(self) -> None:
        """Compute candles_since_retest, retest_depth, disp_strength."""
        df = self.df

        df["disp_strength"] = np.where(
            (df["atr"] > 0) & (df["close"] > 0),
            df["body_size"] / (df["atr"] * df["close"]),
            0.0,
        ).astype(np.float32)
        df["disp_strength"] = df["disp_strength"].clip(lower=0.0, upper=3.0).astype(np.float32)

        df["retest_depth"] = np.where(
            (df["retest_flag"] == 1) & (df["atr"] > 0) & (df["close"] > 0),
            (df["close"] - df["ema_fast"]).abs() / (df["atr"] * df["close"]),
            0.0,
        ).astype(np.float32)
        df["retest_depth"] = df["retest_depth"].clip(lower=0.0, upper=1.0).astype(np.float32)

        retest_groups = df["retest_flag"].eq(1).cumsum()
        bars_since = df.groupby(retest_groups).cumcount()
        df["candles_since_retest"] = np.where(
            retest_groups > 0,
            bars_since,
            0,
        ).astype(np.int16)

    def compute_canonical_session(self) -> None:
        """Ensure session is int-encoded properly."""
        df = self.df
        df["session"] = df["session"].astype(np.int8)

    # ------------------------------------------------------------------
    # FINAL CLEANUP
    # ------------------------------------------------------------------
    def finalize(self) -> pd.DataFrame:
        df = self.df
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna(subset=list(CANONICAL_FEATURES)).reset_index(drop=True)
        self.df = df
        return df

    def log_critical_feature_health(self) -> None:
        """Log zero-rate, NaN-rate, and range stats for critical canonical features."""
        df = self.df
        critical = [
            "retest_depth",
            "disp_strength",
            "trend_bias",
            "momentum_score",
            "ema_spread",
            "atr",
        ]
        for col in critical:
            if col not in df.columns:
                logger.warning("Feature health check skipped missing column: %s", col)
                continue

            s = pd.to_numeric(df[col], errors="coerce")
            nan_rate = float(s.isna().mean())
            zero_rate = float(s.abs().lt(1e-12).mean())
            logger.info(
                "FeatureHealth %s | zero_rate=%.2f%% nan_rate=%.2f%% min=%.6g max=%.6g mean=%.6g",
                col,
                zero_rate * 100.0,
                nan_rate * 100.0,
                float(s.min(skipna=True)),
                float(s.max(skipna=True)),
                float(s.mean(skipna=True)),
            )

    # ------------------------------------------------------------------
    # BATCH FEATURE VECTOR (DataFrame → numpy array)
    # ------------------------------------------------------------------
    def build_feature_vector(self) -> np.ndarray:
        """
        Build the (N, 32) feature matrix from the enriched DataFrame.

        Uses CANONICAL_FEATURES from features.feature_schema — NOT a local list.
        """
        df = self.df

        # Assertion 1: all canonical columns present
        missing = [c for c in CANONICAL_FEATURES if c not in df.columns]
        if missing:
            raise ValueError(
                f"FeaturePipeline.build_feature_vector: missing columns: {missing}"
            )

        vectors = df[list(CANONICAL_FEATURES)].astype(np.float32).values

        # Assertion 2: correct shape
        expected_width = len(CANONICAL_FEATURES)
        if vectors.shape[1] != expected_width:
            raise ValueError(
                f"FeaturePipeline: vector width mismatch — "
                f"expected {expected_width}, got {vectors.shape[1]}"
            )

        # Assertion 3: no NaN
        nan_count = np.isnan(vectors).sum()
        if nan_count > 0:
            raise ValueError(
                f"FeaturePipeline: feature vector contains {nan_count} NaN value(s). "
                "Check warmup period or input data quality."
            )

        return vectors

    # ------------------------------------------------------------------
    # FULL PIPELINE (CANONICAL)
    # ------------------------------------------------------------------
    def run(self) -> tuple:
        """
        Execute the full pipeline in canonical feature order.

        Returns
        -------
        df : pd.DataFrame
            Enriched, NaN-free DataFrame with all 32 canonical features.
        vectors : np.ndarray, shape (N, 32), dtype float32
            Feature matrix in canonical CANONICAL_FEATURES order.
        """
        # Base computations (OHLCV + indicators)
        self.compute_price_features()
        self.compute_volume_features()
        self.compute_indicators()
        self.compute_trend_features()
        self.compute_volatility_regime()
        self.compute_context()
        self.compute_structure_liquidity()
        self.compute_normalization()

        # Canonical feature computation (MUST run after base)
        self.compute_canonical_price_features()
        self.compute_canonical_volatility_features()
        self.compute_canonical_ema_features()
        self.compute_canonical_trend_features()
        self.compute_canonical_structure_features()
        self.compute_canonical_temporal_features()
        self.compute_canonical_session()

        # Finalize and build vectors
        df = self.finalize()
        self.log_critical_feature_health()
        vectors = self.build_feature_vector()

        # ── FeatureMonitor: update rolling window, log drift summary ─────────
        # Monitor tracks the 3 primary CRT features (retest_depth, body_ratio,
        # disp_strength) that are most predictive of distribution shift.
        _drift_cols = {"retest_depth", "body_ratio", "disp_strength"}
        _available  = _drift_cols.intersection(df.columns)
        if _available == _drift_cols:
            n_drift = 0
            for _, row in df[list(_drift_cols)].iterrows():
                feat = row.to_dict()
                self.monitor.update(feat)
                if self.monitor.detect_drift(feat):
                    n_drift += 1
            if n_drift > 0:
                logger.warning(
                    "FeatureMonitor: %d/%d rows flagged as drift in this batch "
                    "(Z > %.1f on retest_depth/body_ratio/disp_strength).",
                    n_drift, len(df), 2.5,
                )
            else:
                logger.info(
                    "FeatureMonitor: batch clean — 0/%d rows flagged for drift.", len(df)
                )
            logger.debug("FeatureMonitor stats: %s", self.monitor.summary())
        else:
            logger.warning(
                "FeatureMonitor: skipped — missing columns %s.",
                _drift_cols - _available,
            )

        return df, vectors
