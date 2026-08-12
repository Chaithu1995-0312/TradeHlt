"""
CRT Feature Builder
Converts CRT trade, candle and state objects to canonical feature schema.

STRICT CONTRACT: Output dict ALWAYS contains EXACTLY ALL CANONICAL_FEATURES.
No missing keys. No extra keys. All values float.

STATUS (2026-07-05): `build_bitnet_features` currently has ZERO call sites (its sibling
lives in archive/dead_code/). It is also stale vs schema v3.0 — it emits the 35 v2.0 keys
and would AssertionError against the 38-key CANONICAL_FEATURES if invoked. Kept (not deleted)
per CLAUDE.md §6.2 rule 4; the live BitNet path reads canonical geometry from the CRT engine's
cached_features (Candle.body_ratio), not this builder. Candle geometry here now routes through
features.candle_math so it can no longer diverge if a caller is reintroduced.
"""
import logging
import os
import numpy as np

from features.feature_schema import CANONICAL_FEATURES, SESSION_MAP, SESSION_UNKNOWN, TREND_MAP
from features import candle_math
from features import derived_math

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
    features["open"]     = float(candle["open"])
    features["high"]     = float(candle["high"])
    features["low"]      = float(candle["low"])
    features["close"]    = float(candle["close"])
    features["volume"]   = float(candle["volume"])

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
    # FM-022 via derived_math (2026-07-11 lint hardening): the old bare
    # `ema_fast - ema_slow` was a name collision with the canonical
    # (fast - slow)/atr definition. Dead builder (F-046: 0 callers) routed to
    # canonical math like its geometry block, so it cannot diverge if revived.
    _atr_for_spread = float(candle.get("atr", 0.0))
    features["ema_spread"]         = derived_math.ema_spread(
        features["ema_fast"], features["ema_slow"], _atr_for_spread
    ) if _atr_for_spread > 0 else 0.0

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
    # Canonical geometry via candle_math (single source of truth). `wick_size` is the
    # full candle range (high - low); body_ratio = body_size / candle_range, bounded [0,1].
    # (Previously computed body_size / total_wick here — an unbounded, non-canonical
    #  definition that disagreed with the CRT Candle property + batch pipeline. Corrected
    #  2026-07-05; this builder is currently uncalled, so the fix is behavior-inert.)
    o, h, l, c = features["open"], features["high"], features["low"], features["close"]
    features["body_size"]          = candle_math.body_size(o, c)
    features["wick_size"]          = candle_math.candle_range(h, l)
    features["body_ratio"]         = candle_math.body_ratio(o, h, l, c)

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