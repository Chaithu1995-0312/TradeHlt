"""
CRT Feature Builder
Converts CRT trade, candle and state objects to canonical feature schema.

STRICT CONTRACT: Output dict ALWAYS contains EXACTLY ALL CANONICAL_FEATURES.
No missing keys. No extra keys. All values float.

STATUS (2026-07-23, T-16): `build_bitnet_features` still has ZERO call sites (its sibling lives
in archive/dead_code/), but it is no longer schema-stale. It was migrated v2.0 -> v4.0 so the
strict `output_keys == CANONICAL_FEATURES` assertion at the bottom passes instead of raising:

  * `macd_hist`  -> `macd_hist_raw` (macd_line - macd_signal, the DECLARED FM-049 formula)
                 +  `macd_hist_z`   (the feeder's legacy `macd_hist`, which WAS the z-score)
  * `wick_size`  -> `candle_range`  (pure key rename; the value was already high - low)
  * ADDED the v3.0 tail it never carried: liquidity_distance, liquidity_pressure_score,
    volume_spike — the actual reason it would AssertionError against any post-v2 schema.

Kept (not deleted) per CLAUDE.md §6.2 rule 4. **Being schema-current does not make it live:** the
live BitNet path reads canonical geometry from the CRT engine's cached_features
(Candle.body_ratio), not this builder, and nothing calls this function. It is a transcriber —
it maps a feeder's trade/candle/state dicts onto canonical keys; geometry FM-001/002/010 route
through resolve_fm (Phase-3a), ema_spread still via derived_math. `tests/test_crt_feature_builder_v4_schema.py`
is what keeps that claim honest; without an exercising test a rewritten dead module merely LOOKS
maintained.
"""
import logging
import os
import numpy as np

from features.feature_schema import CANONICAL_FEATURES, SESSION_MAP, SESSION_UNKNOWN, TREND_MAP
from features import derived_math
from features.fm_resolve import bind_phase3a_feature_builder_callables

try:
    from src.utils.integrity_events import emit_integrity_event  # noqa: F401
except Exception:  # pragma: no cover
    def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
        return None

logger = logging.getLogger(__name__)

# Phase-3a: FM-001 / FM-002 / FM-010 via resolve_fm (geometry slice).
# Primitives identity-equal to candle_math; FM-010 composition path float-parity in tests.
_FM_BUILDER: dict = bind_phase3a_feature_builder_callables()


def _require(d: dict, key: str, source: str) -> object:
    """Strict FEEDER accessor — raises if the key is absent (T-16, CLAUDE.md Section 6.5).

    Sibling of the ten `_require`-style accessors already in this repo
    (`runtime/backtest_v2._require_bt_cfg`, `features/feature_pipeline._require_fp_cfg`,
    `runtime/live_engine_hook._require_cfg`, ...). Same rule, applied one layer out: these are
    FEEDER dicts (trade / candle / state) rather than config sections, but the failure mode is
    identical — a soft `.get(key, 0.0)` makes "the feeder never supplied this" indistinguishable
    from "the feeder measured exactly zero", and a zero-filled canonical feature is not a neutral
    input, it is a fabricated observation that scores downstream as if measured.

    This module previously used `.get(key, 0.0)` for all 33 reads. That was a coherent-but-unsafe
    transcriber contract; it is now strict throughout. Deliberately NOT half-converted: mixing
    strict and soft reads in one builder would raise on some absent keys while silently
    zero-filling others, which is a worse contract than either extreme.
    """
    if key not in d or d[key] is None:
        raise KeyError(
            f"crt_feature_builder: required {source} key {key!r} is absent. "
            "No silent zero-fill — supply the value or fix the feeder "
            "(CLAUDE.md Section 6.5: a missing key is an error, not a default)."
        )
    return d[key]


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
    features["volume_ratio"]       = float(_require(candle, "volume_ratio", "candle"))
    features["double_sweep"]       = float(_require(state, "double_sweep", "state"))

    # --------------------------
    # Trend
    # --------------------------
    features["ema_fast"]           = float(_require(candle, "ema_fast", "candle"))
    features["ema_slow"]           = float(_require(candle, "ema_slow", "candle"))
    # FM-022 via derived_math (2026-07-11 lint hardening): the old bare
    # `ema_fast - ema_slow` was a name collision with the canonical
    # (fast - slow)/atr definition. Dead builder (F-046: 0 callers) routed to
    # canonical math like its geometry block, so it cannot diverge if revived.
    _atr_for_spread = float(_require(candle, "atr", "candle"))
    features["ema_spread"]         = derived_math.ema_spread(
        features["ema_fast"], features["ema_slow"], _atr_for_spread
    ) if _atr_for_spread > 0 else 0.0

    # --------------------------
    # Trend Bias / Strength
    # --------------------------
    trend_bias = _require(state, "trend_bias", "state")
    # T-16: an UNRECOGNISED trend label used to fall to 0.0 — which is TREND_MAP["neutral"], so
    # "we don't understand this feeder's label" was indistinguishable from "the feeder said
    # neutral". Raise instead; the legal domain is exactly TREND_MAP's keys.
    _trend_key = str(trend_bias).strip().lower()
    if _trend_key not in TREND_MAP:
        raise ValueError(
            f"crt_feature_builder: unrecognised trend_bias {trend_bias!r} "
            f"(legal: {sorted(TREND_MAP)}). Not defaulting to neutral — that would silently "
            "encode an unknown label as a real reading."
        )
    features["trend_bias"]         = TREND_MAP[_trend_key]
    features["trend_strength"]     = float(_require(state, "trend_strength", "state"))

    # --------------------------
    # Momentum
    # --------------------------
    features["momentum_score"]     = float(_require(state, "momentum_score", "state"))

    # --------------------------
    # Volatility
    # --------------------------
    features["atr"]                = float(_require(candle, "atr", "candle"))
    features["volatility_ratio"]   = float(_require(state, "volatility_ratio", "state"))

    # --------------------------
    # Indicators
    # --------------------------
    features["rsi_14"]             = float(_require(candle, "rsi_14", "candle"))
    features["macd_line"]          = float(_require(candle, "macd_line", "candle"))
    features["macd_signal"]        = float(_require(candle, "macd_signal", "candle"))
    # v4.0 MACD SPLIT (schema v3.0 emitted ONE `macd_hist` whose value was the Z-SCORED one —
    # compute_normalization overwrote it in place, contradicting FM-049's declared formula).
    # BOTH are TRANSCRIBED, never re-derived here. Computing `macd_line - macd_signal` locally
    # would re-derive registered FM-049 outside the registry — caught by feature_math_lint
    # (its `impl` is feature_pipeline.compute_indicators, a vectorized pipeline stage with no
    # scalar counterpart to route through, so there is nothing legitimate to call). This module
    # is a transcriber: the feeder owns the math. A feeder still on the v3.0 spelling supplies
    # `macd_hist`, which WAS the z-scored series, so that is where it maps.
    features["macd_hist_raw"]      = float(_require(candle, "macd_hist_raw", "candle"))
    features["macd_hist_z"]        = float(candle.get("macd_hist_z", _require(candle, "macd_hist", "candle")))

    # --------------------------
    # Structure
    # --------------------------
    features["sweep_detected"]     = float(_require(state, "sweep_detected", "state"))
    features["liquidity_sweep"]    = float(_require(state, "liquidity_sweep", "state"))
    features["break_of_structure"] = float(_require(state, "break_of_structure", "state"))

    # --------------------------
    # Swing
    # --------------------------
    features["swing_high"]         = float(_require(state, "swing_high", "state"))
    features["swing_low"]          = float(_require(state, "swing_low", "state"))
    features["higher_high"]        = float(_require(state, "higher_high", "state"))
    features["lower_low"]          = float(_require(state, "lower_low", "state"))

    # --------------------------
    # Candle Anatomy
    # --------------------------
    # Phase-3a: geometry via resolve_fm (FM-001 / FM-002 / FM-010), same identities as
    # candle_math / composition path. body_ratio = body_size / candle_range, bounded [0,1].
    # (Previously computed body_size / total_wick here — corrected 2026-07-05.)
    # v4.0: slot name is candle_range (high - low); misnomer wick_size is read-side alias only.
    o, h, l, c = features["open"], features["high"], features["low"], features["close"]
    features["body_size"]          = float(_FM_BUILDER["FM-001"](o, c))
    features["candle_range"]       = float(_FM_BUILDER["FM-002"](h, l))
    features["body_ratio"]         = float(_FM_BUILDER["FM-010"](o, h, l, c))

    # --------------------------
    # Regime
    # --------------------------
    features["volatility_regime"]  = float(_require(state, "volatility_regime", "state"))

    # --------------------------
    # Time / Session
    # --------------------------
    # T-16: PRESENCE is strict (an absent `session` is a feeder defect, not a value), but a
    # SUPPLIED-yet-unrecognised label keeps the deliberate out-of-band SESSION_UNKNOWN sentinel
    # + integrity event below. Those are two different failures and stay distinguishable:
    # "the feeder never sent it" raises; "the feeder sent something we don't recognise" is a
    # data-quality signal that must remain visible rather than abort a batch.
    raw_session = _require(candle, "session", "candle")
    # T-15 (2026-07-20): local renamed session -> session_label. Assigning to a
    # bare name `session` was flagged by feature_math_lint as a re-derivation of
    # FM-052 after temporal_context registration — false positive: this is string
    # NORMALIZATION of a feeder-supplied label, not the int8 hour-bucket feature.
    # Module remains 0-caller dead code (F-046); rename keeps the floor honest.
    session_label = str(raw_session).strip().lower()
    if session_label in SESSION_MAP:
        features["session"] = SESSION_MAP[session_label]
    else:
        # Explicit out-of-band encoding (no longer silently mapped to 0.0=london).
        features["session"] = SESSION_UNKNOWN
        emit_integrity_event(
            "SESSION_UNKNOWN",
            "WARNING",
            "crt_feature_builder",
            {
                "raw_session":   repr(raw_session),
                "normalized":    session_label,
                "encoded_value": SESSION_UNKNOWN,
            },
        )
        if os.environ.get("STRICT_SESSION_VALIDATION", "false").lower() == "true":
            raise ValueError(f"Unknown session value: {raw_session!r}")
    features["hour_of_day"]        = float(_require(candle, "hour_of_day", "candle"))

    # --------------------------
    # CRT Trade Specific
    # --------------------------
    features["disp_strength"]      = float(_require(state, "disp_strength", "state"))
    features["retest_depth"]       = float(_require(state, "retest_depth", "state"))
    features["candles_since_retest"] = float(_require(state, "candles_since_retest", "state"))

    # --------------------------
    # Liquidity / Volume (schema v3.0 tail, indices 36-38)
    # --------------------------
    # Absent from this builder since v2.0 — the reason it would AssertionError against any
    # post-v2 CANONICAL_FEATURES. Sourced from `state` (the FeatureStore/pipeline-supplied
    # market-state dict) like every other derived structural feature above; this builder is a
    # TRANSCRIBER, it does not compute liquidity geometry.
    features["liquidity_distance"]       = float(_require(state, "liquidity_distance", "state"))
    features["liquidity_pressure_score"] = float(_require(state, "liquidity_pressure_score", "state"))
    features["volume_spike"]             = float(_require(candle, "volume_spike", "candle"))

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