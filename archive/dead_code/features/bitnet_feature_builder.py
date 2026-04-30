# ARCHIVED 2026-04-28 — Dead Code Pass
# Reason: superseded by features/feature_pipeline.py; zero importers in active src/.
# Original: src/features/bitnet_feature_builder.py
# Action required on original: remove src/features/bitnet_feature_builder.py
"""
BitNet Feature Builder
Converts CRT trade, candle and state objects to canonical feature schema.

STRICT CONTRACT: Output dict ALWAYS contains EXACTLY ALL CANONICAL_FEATURES.
No missing keys. No extra keys. All values float.
"""
import logging
import numpy as np

from features.feature_schema import CANONICAL_FEATURES, SESSION_MAP, TREND_MAP

logger = logging.getLogger(__name__)


def build_bitnet_features(trade: dict, candle: dict, state: dict) -> dict:
    features = {}

    features["open"]     = float(candle.get("open", 0.0))
    features["high"]     = float(candle.get("high", 0.0))
    features["low"]      = float(candle.get("low", 0.0))
    features["close"]    = float(candle.get("close", 0.0))
    features["volume"]   = float(candle.get("volume", 0.0))
    features["volume_ratio"]       = float(candle.get("volume_ratio", 0.0))
    features["double_sweep"]       = float(state.get("double_sweep", 0.0))
    features["ema_fast"]           = float(candle.get("ema_fast", 0.0))
    features["ema_slow"]           = float(candle.get("ema_slow", 0.0))
    features["ema_spread"]         = features["ema_fast"] - features["ema_slow"]
    trend_bias = state.get("trend_bias", "neutral")
    features["trend_bias"]         = TREND_MAP.get(str(trend_bias).lower(), 0.0)
    features["trend_strength"]     = float(state.get("trend_strength", 0.0))
    features["momentum_score"]     = float(state.get("momentum_score", 0.0))
    features["atr"]                = float(candle.get("atr", 0.0))
    features["volatility_ratio"]   = float(state.get("volatility_ratio", 0.0))
    features["rsi_14"]             = float(candle.get("rsi_14", 0.0))
    features["macd_line"]          = float(candle.get("macd_line", 0.0))
    features["macd_signal"]        = float(candle.get("macd_signal", 0.0))
    features["macd_hist"]          = float(candle.get("macd_hist", 0.0))
    features["sweep_detected"]     = float(state.get("sweep_detected", 0.0))
    features["liquidity_sweep"]    = float(state.get("liquidity_sweep", 0.0))
    features["break_of_structure"] = float(state.get("break_of_structure", 0.0))
    features["swing_high"]         = float(state.get("swing_high", 0.0))
    features["swing_low"]          = float(state.get("swing_low", 0.0))
    features["higher_high"]        = float(state.get("higher_high", 0.0))
    features["lower_low"]          = float(state.get("lower_low", 0.0))
    body_size = abs(features["close"] - features["open"])
    wick_size = (features["high"] - features["low"]) - body_size
    features["body_size"]          = body_size
    features["wick_size"]          = wick_size
    features["body_ratio"]         = body_size / wick_size if wick_size > 1e-8 else 0.0
    features["volatility_regime"]  = float(state.get("volatility_regime", 0.0))
    session = str(candle.get("session", "unknown")).lower()
    features["session"]            = SESSION_MAP.get(session, 0.0)
    features["hour_of_day"]        = float(candle.get("hour_of_day", 0.0))
    features["disp_strength"]      = float(state.get("disp_strength", 0.0))
    features["retest_depth"]       = float(state.get("retest_depth", 0.0))
    features["candles_since_retest"] = float(state.get("candles_since_retest", 0.0))

    for k, v in features.items():
        if np.isnan(v) or np.isinf(v):
            logger.warning("NaN/inf detected in %s → setting to 0.0", k)
            features[k] = 0.0

    output_keys = set(features.keys())
    canonical_keys = set(CANONICAL_FEATURES)
    if output_keys != canonical_keys:
        missing = canonical_keys - output_keys
        extra   = output_keys - canonical_keys
        raise AssertionError(f"Feature schema mismatch!\nMissing: {missing}\nExtra: {extra}")

    return features
