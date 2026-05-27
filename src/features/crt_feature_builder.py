"""
CRT Feature Builder
Converts CRT trade, candle and state objects to canonical feature schema.

STRICT CONTRACT: Output dict ALWAYS contains EXACTLY ALL CANONICAL_FEATURES.
No missing keys. No extra keys. All values float.
"""
import logging
import os
import numpy as np

from features.feature_schema import CANONICAL_FEATURES, SESSION_MAP, SESSION_UNKNOWN, TREND_MAP

try:
    from src.utils.integrity_events import emit_integrity_event  # noqa: F401
except Exception:  # pragma: no cover
    def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
        return None

logger = logging.getLogger(__name__)


def build_bitnet_features(trade: dict, candle: dict, state: dict) -> dict:
    """
    Build full canonical feature vector for BitNet from trade, candle and state.

    Parameters
    ----------
    trade : dict
        CRT trade output: entry, sl, tp
    candle : dict
        Raw OHLCV + indicator data
    state : dict
        Market state features from FeatureStore / pipeline

    Returns
    -------
    dict
        Feature dict with ALL CANONICAL_FEATURES keys, all float values
    """
    features = {}

    # --------------------------
    # OHLCV (MANDATORY)
    # --------------------------
    features["open"]     = float(candle.get("open", 0.0))
    features["high"]     = float(candle.get("high", 0.0))
    features["low"]      = float(candle.get("low", 0.0))
    features["close"]    = float(candle.get("close", 0.0))
    features["volume"]   = float(candle.get("volume", 0.0))

    # --------------------------
    # Volume / Flow
    # --------------------------
    features["volume_ratio"]       = float(candle.get("volume_ratio", 0.0))
    features["double_sweep"]       = float(state.get("double_sweep", 0.0))

    # --------------------------
    # Trend
    # --------------------------
    features["ema_fast"]           = float(candle.get("ema_fast", 0.0))
    features["ema_slow"]           = float(candle.get("ema_slow", 0.0))
    features["ema_spread"]         = features["ema_fast"] - features["ema_slow"]

    # --------------------------
    # Trend Bias / Strength
    # --------------------------
    trend_bias = state.get("trend_bias", "neutral")
    features["trend_bias"]         = TREND_MAP.get(str(trend_bias).lower(), 0.0)
    features["trend_strength"]     = float(state.get("trend_strength", 0.0))

    # --------------------------
    # Momentum
    # --------------------------
    features["momentum_score"]     = float(state.get("momentum_score", 0.0))

    # --------------------------
    # Volatility
    # --------------------------
    features["atr"]                = float(candle.get("atr", 0.0))
    features["volatility_ratio"]   = float(state.get("volatility_ratio", 0.0))

    # --------------------------
    # Indicators
    # --------------------------
    features["rsi_14"]             = float(candle.get("rsi_14", 0.0))
    features["macd_line"]          = float(candle.get("macd_line", 0.0))
    features["macd_signal"]        = float(candle.get("macd_signal", 0.0))
    features["macd_hist"]          = float(candle.get("macd_hist", 0.0))

    # --------------------------
    # Structure
    # --------------------------
    features["sweep_detected"]     = float(state.get("sweep_detected", 0.0))
    features["liquidity_sweep"]    = float(state.get("liquidity_sweep", 0.0))
    features["break_of_structure"] = float(state.get("break_of_structure", 0.0))

    # --------------------------
    # Swing
    # --------------------------
    features["swing_high"]         = float(state.get("swing_high", 0.0))
    features["swing_low"]          = float(state.get("swing_low", 0.0))
    features["higher_high"]        = float(state.get("higher_high", 0.0))
    features["lower_low"]          = float(state.get("lower_low", 0.0))

    # --------------------------
    # Candle Anatomy
    # --------------------------
    body_size = abs(features["close"] - features["open"])
    wick_size = (features["high"] - features["low"]) - body_size
    features["body_size"]          = body_size
    features["wick_size"]          = wick_size
    features["body_ratio"]         = body_size / wick_size if wick_size > 1e-8 else 0.0

    # --------------------------
    # Regime
    # --------------------------
    features["volatility_regime"]  = float(state.get("volatility_regime", 0.0))

    # --------------------------
    # Time / Session
    # --------------------------
    raw_session = candle.get("session")
    session = str(raw_session if raw_session is not None else "unknown").strip().lower()
    if session in SESSION_MAP:
        features["session"] = SESSION_MAP[session]
    else:
        # Explicit out-of-band encoding (no longer silently mapped to 0.0=london).
        features["session"] = SESSION_UNKNOWN
        emit_integrity_event(
            "SESSION_UNKNOWN",
            "WARNING",
            "crt_feature_builder",
            {
                "raw_session":   repr(raw_session),
                "normalized":    session,
                "encoded_value": SESSION_UNKNOWN,
            },
        )
        if os.environ.get("STRICT_SESSION_VALIDATION", "false").lower() == "true":
            raise ValueError(f"Unknown session value: {raw_session!r}")
    features["hour_of_day"]        = float(candle.get("hour_of_day", 0.0))

    # --------------------------
    # CRT Trade Specific
    # --------------------------
    features["disp_strength"]      = float(state.get("disp_strength", 0.0))
    features["retest_depth"]       = float(state.get("retest_depth", 0.0))
    features["candles_since_retest"] = float(state.get("candles_since_retest", 0.0))

    # --------------------------
    # NaN Guard
    # --------------------------
    _nan_replaced = 0
    for k, v in features.items():
        if np.isnan(v) or np.isinf(v):
            logger.warning("NaN/inf detected in %s → setting to 0.0", k)
            features[k] = 0.0
            _nan_replaced += 1

    # --------------------------
    # STRICT SCHEMA VALIDATION
    # --------------------------
    output_keys = set(features.keys())
    canonical_keys = set(CANONICAL_FEATURES)

    if output_keys != canonical_keys:
        missing = canonical_keys - output_keys
        extra   = output_keys - canonical_keys
        raise AssertionError(f"Feature schema mismatch!\nMissing: {missing}\nExtra: {extra}")

    # Data-completeness signal: fraction of non-zero canonical features after NaN guard.
    # Stored as _quality so gate callers can abstain on thin/empty inputs.
    # BitNetRunner and other canonical-key consumers ignore this key safely.
    total = len(CANONICAL_FEATURES)
    non_zero = sum(1 for k in CANONICAL_FEATURES if features[k] != 0.0)
    features["_quality"] = round(non_zero / total, 4) if total else 0.0

    return features