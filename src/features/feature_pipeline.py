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
    - Zero volume (Forex): when all volume values are zero the pipeline
      substitutes intrabar range (high-low) as a tick-activity proxy so
      both `volume` and `volume_ratio` carry real variance.
    - Flat market (ATR ≈ 0): bb_position has a 1e-9 denominator guard.
      ATR-gated features (ema_spread, momentum_score, disp_strength,
      retest_depth) emit NaN during the 14-bar ATR warmup; finalize()
      drops those rows cleanly.
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
from data_ingestion.ohlcv_schema import require_ohlcv_columns, validate_ohlcv_frame
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
        # Phase 1 — all six OHLCV columns must physically exist. No defaults,
        # no auto-generated volume column.
        require_ohlcv_columns(self.df.columns, source="FeaturePipeline")

        # Coerce numeric columns (unparseable cells become NaN, caught below).
        for col in ["open", "high", "low", "close", "volume"]:
            self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

        # Phase 2 — value integrity: no NaN/non-numeric, volume >= 0, candles
        # high/low-consistent. An all-zero (but numeric) volume column is valid
        # data and is later handled by compute_volume_features()'s proxy.
        validate_ohlcv_frame(self.df, source="FeaturePipeline")

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
    # VOLUME FEATURES
    # FX data often carries zero tick-volume. When detected, substitute the
    # intrabar price range (high - low) as a tick-activity proxy so that both
    # `volume` and `volume_ratio` carry genuine variance for model training.
    # ------------------------------------------------------------------
    def compute_volume_features(self) -> None:
        df = self.df

        raw_vol = df["volume"]
        # Detect FX "dead volume": all zeros or all NaN after numeric coercion
        vol_is_dead = (raw_vol.fillna(0.0).max() == 0)

        if vol_is_dead:
            logger.info(
                "compute_volume_features: volume column is all-zero — "
                "substituting intrabar range (high-low) as tick-activity proxy."
            )
            proxy = df["high"] - df["low"]
            proxy_ma20 = proxy.rolling(20).mean()
            df["volume"] = proxy
            df["volume_ma20"] = proxy_ma20
            df["volume_ratio"] = np.where(
                proxy_ma20 > 0,
                proxy / proxy_ma20,
                1.0
            )
        else:
            df["volume_ma20"] = raw_vol.rolling(20).mean()
            df["volume_ratio"] = np.where(
                df["volume_ma20"] > 0,
                raw_vol / df["volume_ma20"],
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

        # ── RSI(14) ───────────────────────────────────────────────────
        # Standard Wilder formula: RS = avg_gain / avg_loss, RSI = 100 − 100/(1+RS).
        # Correct range is strictly [0, 100]; clip guards the 1e-9 denominator edge.
        # Prior bug: formula 100*(gain−loss)/(gain+loss) produced [−100, 100] with
        # mean≈0 and std≈52 — confirmed in gaussian_v5_tradenet scaler statistics.
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df["rsi_14"] = (100.0 - (100.0 / (1.0 + rs))).clip(0.0, 100.0)

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

        # [F-029 / Program B measurement hook, 2026-06-15] volatility_regime buckets ATR by its
        # GLOBAL percentile rank — a whole-column statistic, so the same bar's regime depends on the
        # slice length (a cross-length / walk-forward inconsistency). Unlike F1's swing lookahead
        # (already measured byte-identical-benign), this column IS decision-reachable (s05_grid.py
        # blocks LONG in the TRENDING regime). MEASURE-ONLY A/B/C hook: default (env unset) keeps the
        # current GLOBAL rank (production behavior, no hash change); TRUST_VOLREGIME_CAUSAL selects a
        # causal variant for comparison. See docs/analysis/backtest-trust-audit-2026-06-10 §4f /
        # docs/current-findings.md F-029.
        import os as _os
        _vr_mode = _os.environ.get("TRUST_VOLREGIME_CAUSAL", "").strip().lower()
        if _vr_mode == "expanding":        # B — time-causal expanding percentile (no future leak)
            atr_pct = df["atr_14"].expanding(min_periods=1).rank(pct=True)
        elif _vr_mode == "rolling":        # C — trailing-window percentile (regime-adaptive)
            atr_pct = df["atr_14"].rolling(200, min_periods=1).rank(pct=True)
        else:                              # A — current GLOBAL rank (default; production behavior)
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

        # Bullish pivot: this bar's HIGH is the rolling maximum
        df["swing_high"] = (df["high"] == roll_high).astype(np.int8)
        # Bearish pivot: this bar's LOW is the rolling minimum — must use LOW/roll_low
        df["swing_low"]  = (df["low"]  == roll_low).astype(np.int8)

        # Guard against copy-paste regression: the two flags must differ
        if df["swing_high"].equals(df["swing_low"]):
            raise AssertionError(
                "compute_structure_liquidity: swing_high and swing_low are "
                "bit-for-bit identical — column reference bug detected."
            )

        df["last_swing_high_price"] = df["high"].where(df["swing_high"] == 1).ffill()
        df["last_swing_low_price"]  = df["low"].where(df["swing_low"]  == 1).ffill()

        # [trust-layer F1/WS4A measurement hook, 2026-06-10] center=True swing detection
        # confirms a pivot at bar t using bars up to t+SWING_WINDOW (a future-bar peek).
        # When TRUST_SWING_CAUSAL=1, delay pivot availability by SWING_WINDOW bars so the
        # decision-bar reference is causal (no lookahead). MEASURE-ONLY: default off, no
        # production-config/hash change. See docs/analysis/backtest-trust-audit-2026-06-10.
        import os as _os
        if _os.environ.get("TRUST_SWING_CAUSAL") == "1":
            _s = SWING_WINDOW
            df["swing_high"] = df["swing_high"].shift(_s).fillna(0).astype(np.int8)
            df["swing_low"]  = df["swing_low"].shift(_s).fillna(0).astype(np.int8)
            df["last_swing_high_price"] = df["last_swing_high_price"].shift(_s)
            df["last_swing_low_price"]  = df["last_swing_low_price"].shift(_s)

        ref_high = df["last_swing_high_price"].shift(1)
        ref_low  = df["last_swing_low_price"].shift(1)

        # Bullish structure: current HIGH exceeds previous swing high
        df["higher_high"] = (df["high"] > ref_high).astype(np.int8)
        # Bearish structure: current LOW undercuts previous swing low — must use LOW/ref_low
        df["lower_low"]   = (df["low"]  < ref_low).astype(np.int8)

        # Guard against copy-paste regression
        if df["higher_high"].equals(df["lower_low"]):
            raise AssertionError(
                "compute_structure_liquidity: higher_high and lower_low are "
                "bit-for-bit identical — column reference bug detected."
            )

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

        # Use np.nan (not 0.0) when ATR is unavailable so finalize() drops the
        # warmup rows instead of silently injecting 0.0 into training samples.
        df["ema_spread"] = np.where(
            df["atr"] > 0,
            (df["ema_fast"] - df["ema_slow"]) / df["atr"],
            np.nan
        ).astype(np.float32)

        df["momentum_score"] = np.where(
            df["atr"] > 0,
            df["close"].diff() / df["atr"],
            np.nan
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
        # Use a 10-bar rolling window so retests up to 10 bars after the sweep are
        # captured (was 1-bar .shift(1) which forced candles_since_retest=1 always).
        _RETEST_LOOKBACK = 10
        recent_sweep = (
            (df["liquidity_sweep"] != 0)
            .rolling(window=_RETEST_LOOKBACK, min_periods=1)
            .max()
            .astype(bool)
        )
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

        # np.nan fallbacks — finalize() drops these rows; 0.0 would silently
        # inject invalid samples during the ATR warmup period.
        df["disp_strength"] = np.where(
            (df["atr"] > 0) & (df["close"] > 0),
            df["body_size"] / (df["atr"] * df["close"]),
            np.nan,
        ).astype(np.float32)
        df["disp_strength"] = df["disp_strength"].clip(lower=0.0, upper=3.0).astype(np.float32)

        # retest_depth is only defined when retest_flag == 1; on every other bar
        # the feature is semantically "no retest", which we encode as 0.0 (NOT NaN).
        # NaN would propagate into finalize()'s dropna(subset=CANONICAL_FEATURES)
        # and silently delete ~52% of bars — breaking the timestamp → row-index map
        # the backtest loop uses (see backtest_v2.py:1500-1530). ATR-warmup rows are
        # still cleanly dropped via the NaN fallbacks in disp_strength / ema_spread
        # / momentum_score, so no invalid warm-up samples leak through.
        df["retest_depth"] = np.where(
            (df["retest_flag"] == 1) & (df["atr"] > 0) & (df["close"] > 0),
            (df["close"] - df["ema_fast"]).abs() / (df["atr"] * df["close"]),
            0.0,
        ).astype(np.float32)
        df["retest_depth"] = df["retest_depth"].clip(lower=0.0, upper=1.0).astype(np.float32)

        # Count bars since the last liquidity sweep (the event that SET UP the
        # retest), not since the retest_flag itself.  Previously this used
        # retest_flag.cumsum(), which made cumcount()=0 at every retest candle
        # (the retest_flag candle IS the first candle of its group) — giving
        # zero variance in training data.  Grouping by sweep events instead
        # yields N=2–5 at a typical retest candle, producing a meaningful signal.
        # Guard: `liquidity_sweep` may be absent in minimal test DataFrames or
        # partial pipeline runs; fall back to retest_flag grouping in that case.
        if "liquidity_sweep" in df.columns:
            sweep_groups = (df["liquidity_sweep"] != 0).astype(int).cumsum()
        else:
            sweep_groups = df["retest_flag"].eq(1).cumsum()
        bars_since_sweep = df.groupby(sweep_groups).cumcount()
        df["candles_since_retest"] = np.where(
            sweep_groups > 0,
            bars_since_sweep,
            0,
        ).astype(np.int16)

    def compute_liquidity_distance(self) -> None:
        """
        Compute ATR-normalised distance to nearest liquidity level.

        No lookahead: all reference levels use .shift(1) so they reflect
        the state BEFORE the current bar opens.

        Populates:
          liquidity_distance       — abs(close - nearest_level) / (atr * close);
                                     NaN when atr=0 or no level available
          liquidity_pressure_score — exp(-0.5 * liquidity_distance), clipped [0, 1];
                                     higher = price is closer to a sweep zone

        Live safety note:
          Reference levels (last_swing_high_price, last_swing_low_price) are
          computed in compute_structure_liquidity() using center=True rolling windows
          which introduce lookahead for live inference. For backtesting this is
          acceptable. For live mode, swap to a trailing-window swing detector.
          This method itself is safe because it reads the SHIFTED reference prices.
        """
        df = self.df

        # Reference levels (all trailing — no lookahead)
        ref_high = df["last_swing_high_price"].shift(1)
        ref_low  = df["last_swing_low_price"].shift(1)

        # Last BOS level: carry forward the price level at which BOS occurred.
        bos_level = pd.Series(np.nan, index=df.index)
        bos_bullish = df["break_of_structure"] == 1
        bos_bearish = df["break_of_structure"] == -1
        bos_level.loc[bos_bullish] = ref_high.loc[bos_bullish]
        bos_level.loc[bos_bearish] = ref_low.loc[bos_bearish]
        bos_level = bos_level.ffill()

        # ATR in absolute price units (atr column is close-relative; multiply back).
        # Guard: atr_safe is NaN when atr is 0 or NaN — produces NaN distance.
        atr_abs  = df["atr"] * df["close"]
        atr_safe = atr_abs.where(atr_abs > 0, np.nan)

        # Candidate distances (non-negative, ATR-normalised)
        dist_high = (df["close"] - ref_high).abs() / atr_safe
        dist_low  = (df["close"] - ref_low).abs()  / atr_safe
        dist_bos  = (df["close"] - bos_level).abs() / atr_safe

        # Nearest of the three candidates
        nearest = pd.concat([dist_high, dist_low, dist_bos], axis=1).min(axis=1)
        df["liquidity_distance"] = nearest.clip(lower=0.0).astype(np.float32)

        # Pressure score: exp(-0.5 × distance) → high score when price near liquidity
        df["liquidity_pressure_score"] = (
            np.exp(-0.5 * df["liquidity_distance"].fillna(10.0))
        ).clip(0.0, 1.0).astype(np.float32)

        self.df = df

    def promote_volume_spike(self) -> None:
        """
        Replace fixed-threshold volume_spike with adaptive 75th-percentile threshold.

        Rationale: fixed 1.5× threshold is not forex-safe across instruments with
        different volume characteristics. Adaptive percentile adjusts to the
        instrument's own distribution.

        Overwrites the 'volume_spike' column (computed earlier in
        compute_volume_features() with a fixed threshold).

        Falls back to fixed 1.5× threshold when rolling window has < 20 samples.
        No lookahead: rolling window uses trailing only (no center=True).
        """
        df = self.df

        _ADAPTIVE_WINDOW     = 50
        _FIXED_FALLBACK      = 1.5
        _MIN_SAMPLES         = 20
        _PERCENTILE          = 75

        vol_ratio = df["volume_ratio"]
        rolling_thresh = vol_ratio.rolling(
            window=_ADAPTIVE_WINDOW, min_periods=_MIN_SAMPLES
        ).quantile(_PERCENTILE / 100.0)

        # Where rolling threshold is available use adaptive; else use fixed fallback
        threshold = rolling_thresh.where(rolling_thresh.notna(), _FIXED_FALLBACK)
        df["volume_spike"] = (vol_ratio > threshold).astype(np.int8)

        self.df = df

    def compute_canonical_session(self) -> None:
        """Ensure session is int-encoded properly."""
        df = self.df
        df["session"] = df["session"].astype(np.int8)

    # ------------------------------------------------------------------
    # FINAL CLEANUP
    # ------------------------------------------------------------------
    def finalize(self) -> pd.DataFrame:
        n_before = len(self.df)
        df = self.df
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna(subset=list(CANONICAL_FEATURES)).reset_index(drop=True)
        n_after    = len(df)
        drop_count = n_before - n_after
        drop_pct   = 100.0 * drop_count / max(n_before, 1)

        # Structured telemetry — trendable; catches gradual degradation across runs.
        _fp_log = logging.getLogger("FeaturePipeline")
        _fp_log.info(
            "finalize | rows_before=%d rows_after=%d drop=%d drop_pct=%.2f%%",
            n_before, n_after, drop_count, drop_pct,
            extra={
                "event":       "FEATURE_FINALIZE",
                "rows_before": n_before,
                "rows_after":  n_after,
                "drop_count":  drop_count,
                "drop_pct":    round(drop_pct, 2),
            },
        )

        # Survivorship guard (absolute budget, not survival ratio).
        # Ratio permits ~5k silent loss on 100k datasets; absolute budget does not.
        # Warm-up budget = ma_200(200) + z-score(50) + swing edges(4) = ~300 rows max.
        # Beyond that, any large drop indicates an unintended NaN in CANONICAL_FEATURES.
        _warmup_budget = 300
        _allowed_drop  = max(_warmup_budget, int(n_before * 0.02))  # 2% OR warmup, whichever larger
        if drop_count > _allowed_drop:
            _fp_log.error(
                "finalize(): drop count %d exceeds allowed budget %d (%.1f%% of input). "
                "Likely unintended NaN in CANONICAL_FEATURES. Check recent feature additions.",
                drop_count, _allowed_drop, drop_pct,
            )

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
            "liquidity_distance",       # v3.0
            "volume_spike",             # v3.0
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
        self.compute_liquidity_distance()     # v3.0: index 35 + 36 (after structure)
        self.promote_volume_spike()           # v3.0: index 37 (adaptive percentile)
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
