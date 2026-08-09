"""crt_feature_builder schema-v4 floor (T-16).

`build_bitnet_features` has ZERO call sites and emitted the v2.0 35-key set, so it would have
AssertionError'd against any post-v2 CANONICAL_FEATURES if ever invoked. It was migrated to v4.0
(39 keys) rather than deleted, per CLAUDE.md 6.2 rule 4.

A rewritten dead module with no test merely LOOKS maintained — the next schema bump would
silently re-stale it, exactly as v3.0 did. These tests are the only thing that exercises the
function, so they are the whole justification for the rewrite over a deprecation banner.
"""
from __future__ import annotations

import math

import pytest

from features.crt_feature_builder import build_bitnet_features
from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM


def _inputs() -> tuple[dict, dict, dict]:
    """A COMPLETE, well-formed (trade, candle, state) triple.

    Must be exhaustive as of T-16: every read in the builder now goes through the strict
    `_require` accessor, so a sparse feeder dict raises instead of zero-filling. That is the
    point — a missing feature is a feeder defect, not a measurement of zero.
    """
    trade = {"entry": 2318.21, "sl": 2317.45, "tp": 2319.34}
    candle = {
        "open": 2318.24, "high": 2319.92, "low": 2317.81, "close": 2319.29, "volume": 1692.0,
        "volume_ratio": 1.1986, "ema_fast": 2319.94, "ema_slow": 2320.39, "atr": 0.00093,
        "rsi_14": 48.16, "macd_line": -0.5796, "macd_signal": -0.5832,
        # DELIBERATELY not equal to (macd_line - macd_signal) == 0.0036. If the builder ever
        # recomputes the difference locally instead of transcribing, the value it produces will
        # differ from this one and the pass-through test catches it. A "physically correct"
        # fixture here would make that test vacuous.
        "macd_hist_raw": 0.0099, "macd_hist": 0.1901,   # `macd_hist` = the v3.0 z-scored spelling
        "hour_of_day": 15.0, "session": "london", "volume_spike": 1.0,
    }
    state = {
        "trend_bias": "bullish", "trend_strength": 2.42, "momentum_score": 1155.82,
        "volatility_ratio": 0.9736, "volatility_regime": 1.0, "double_sweep": 0.0,
        "sweep_detected": 0.0, "liquidity_sweep": 0.0, "break_of_structure": -1.0,
        "swing_high": 0.0, "swing_low": 1.0, "higher_high": 0.0, "lower_low": 1.0,
        "disp_strength": 0.4845, "retest_depth": 0.3011, "candles_since_retest": 2.0,
        "liquidity_distance": 0.1384, "liquidity_pressure_score": 0.9331,
    }
    return trade, candle, state


def test_emits_exactly_the_canonical_key_set() -> None:
    """The strict assertion inside the builder must PASS, not raise. The load-bearing test."""
    features = build_bitnet_features(*_inputs())
    emitted = set(features) - {"_quality"}
    assert emitted == set(CANONICAL_FEATURES), (
        f"missing={sorted(set(CANONICAL_FEATURES) - emitted)} "
        f"extra={sorted(emitted - set(CANONICAL_FEATURES))}"
    )
    assert len(emitted) == CANONICAL_FEATURE_DIM


def test_all_values_are_finite_floats() -> None:
    """The NaN guard runs and nothing escapes as NaN/inf/None."""
    features = build_bitnet_features(*_inputs())
    bad = {k: v for k, v in features.items()
           if not isinstance(v, float) or math.isnan(v) or math.isinf(v)}
    assert not bad, f"non-finite or non-float values: {bad}"


def test_v4_macd_split_transcribes_two_distinct_quantities() -> None:
    """macd_hist_raw and macd_hist_z stay separate, and BOTH are transcribed, never re-derived.

    v3.0's single `macd_hist` column held the z-score while its name promised the difference —
    the defect the split exists to close. If these two ever collapse to one value, the split has
    been undone.

    The builder must NOT compute `macd_line - macd_signal` itself: that re-derives registered
    FM-049 outside the registry and feature_math_lint fails the build (it did, on the first
    attempt at this migration). A feeder on the v3.0 spelling supplies `macd_hist`, which was the
    z-scored series — that is the mapping asserted here.
    """
    _t, candle, _s = _inputs()
    features = build_bitnet_features(*_inputs())
    assert features["macd_hist_raw"] == pytest.approx(candle["macd_hist_raw"])
    assert features["macd_hist_z"] == pytest.approx(candle["macd_hist"])
    assert features["macd_hist_raw"] != pytest.approx(features["macd_hist_z"])


def test_macd_hist_raw_is_not_locally_derived() -> None:
    """Ownership guard: a feeder without `macd_hist_raw` RAISES, never computes the diff itself.

    Post-T-16 this is the sharper form of the guard: if someone 'helpfully' reinstates
    `macd_line - macd_signal`, the absent key stops raising and this test goes red — which is
    also what feature_math_lint::test_floor_is_green catches from the other direction.
    """
    trade, candle, state = _inputs()
    candle = {k: v for k, v in candle.items() if k != "macd_hist_raw"}
    with pytest.raises(KeyError, match="macd_hist_raw"):
        build_bitnet_features(trade, candle, state)


def test_supplied_macd_hist_raw_passes_through_unchanged() -> None:
    """The value is transcribed verbatim — not recomputed from the two legs."""
    _t, candle, _s = _inputs()
    features = build_bitnet_features(*_inputs())
    assert features["macd_hist_raw"] == pytest.approx(candle["macd_hist_raw"])
    # and it is NOT the locally-derivable difference
    assert features["macd_hist_raw"] != pytest.approx(
        candle["macd_line"] - candle["macd_signal"]
    )


def test_candle_range_is_high_minus_low_not_a_wick() -> None:
    """v4.0 rename: the slot formerly called `wick_size` always held the full range (FM-002)."""
    _t, candle, _s = _inputs()
    features = build_bitnet_features(*_inputs())
    assert features["candle_range"] == pytest.approx(candle["high"] - candle["low"])
    assert "wick_size" not in features


def test_body_ratio_is_body_over_range_and_bounded() -> None:
    """Canonical FM-010, not the body/total_wick identity — bounded [0,1]."""
    _t, candle, _s = _inputs()
    features = build_bitnet_features(*_inputs())
    expected = abs(candle["close"] - candle["open"]) / (candle["high"] - candle["low"])
    assert features["body_ratio"] == pytest.approx(expected)
    assert 0.0 <= features["body_ratio"] <= 1.0


def test_sparse_state_raises_instead_of_zero_filling() -> None:
    """T-16 contract reversal: a sparse feeder is an ERROR, not a zero-filled vector.

    Before T-16 this module answered a missing key with 0.0, making "the feeder never supplied
    this" indistinguishable from "the feeder measured exactly zero" across 33 reads. A
    zero-filled canonical feature is a fabricated observation, so it now raises.
    """
    trade, candle, _state = _inputs()
    with pytest.raises(KeyError):
        build_bitnet_features(trade, candle, {})


@pytest.mark.parametrize("missing", ["volume_ratio", "ema_fast", "atr", "rsi_14", "session"])
def test_each_missing_candle_key_raises_and_names_itself(missing) -> None:
    """Every strict read names the offending key — a raise you cannot act on is barely better
    than a silent default."""
    trade, candle, state = _inputs()
    candle = {k: v for k, v in candle.items() if k != missing}
    with pytest.raises(KeyError, match=missing):
        build_bitnet_features(trade, candle, state)


@pytest.mark.parametrize("missing", ["trend_bias", "momentum_score", "liquidity_distance"])
def test_each_missing_state_key_raises_and_names_itself(missing) -> None:
    trade, candle, state = _inputs()
    state = {k: v for k, v in state.items() if k != missing}
    with pytest.raises(KeyError, match=missing):
        build_bitnet_features(trade, candle, state)


def test_unrecognised_trend_bias_raises_rather_than_encoding_neutral() -> None:
    """An unknown label used to map to 0.0 == TREND_MAP['neutral'], so 'not understood' and
    'neutral' were the same number. They must not be."""
    trade, candle, state = _inputs()
    state = {**state, "trend_bias": "sideways-ish"}
    with pytest.raises(ValueError, match="trend_bias"):
        build_bitnet_features(trade, candle, state)


def test_none_valued_key_is_treated_as_absent() -> None:
    """A key present with value None is a feeder defect too — float(None) would TypeError."""
    trade, candle, state = _inputs()
    state = {**state, "momentum_score": None}
    with pytest.raises(KeyError, match="momentum_score"):
        build_bitnet_features(trade, candle, state)
