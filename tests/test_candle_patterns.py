"""CH-candle-pattern-observations-v8 (schema v8.0): candle-pattern observations FM-103..FM-119.

Pins the corrected-spec definitions (inclusive comparisons, current bar excluded from the swing
extreme, zero-range = undefined, gap-safe two-bar patterns, price-unit ATR gate) and binds the
pipeline's vectorized mirror to the scalar identities."""
import numpy as np
import pandas as pd
import pytest

from features import candle_patterns as cp
from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM, SCHEMA_VERSION
from features.registry import FORMULA_REGISTRY, validate_registry

P = cp.CandlePatternParams(
    size_gate_atr_k=0.5, swing_lookback=5, pin_wick_min=0.60, pin_body_max=0.25,
    pin_opposite_wick_max=0.15, probe_wick_body_multiple=2.0, probe_opposite_wick_max=0.10,
    doji_body_max=0.10, doji_wick_asymmetry_max=0.20, doji_extreme_body_max=0.05,
    doji_extreme_wick_min=0.75, engulfing_strength_cap=3.0, compression_ratio_cap=10.0,
    morning_star_body_min=0.6, morning_star_mid_max=0.25,
)
ATR = 1.0   # price units


def test_schema_v8_layout():
    assert SCHEMA_VERSION == "9.0" and CANONICAL_FEATURE_DIM == 79
    assert tuple(CANONICAL_FEATURES[54:71]) == cp.PATTERN_COLUMNS
    assert CANONICAL_FEATURES[71] == "morning_star"
    assert all(f"features.candle_patterns.{n}" in FORMULA_REGISTRY for n in cp.PATTERN_COLUMNS)
    assert validate_registry() == []


def test_params_strict():
    with pytest.raises(KeyError):
        cp.CandlePatternParams.from_cfg({"size_gate_atr_k": 0.5})


def test_shares_sum_to_one_and_zero_range_undefined():
    b, u, d = cp.wick_ratios(10.0, 12.0, 9.0, 11.0)
    assert b + u + d == pytest.approx(1.0)
    assert cp.wick_ratios(5.0, 5.0, 5.0, 5.0) == (0.0, 0.0, 0.0)
    assert not cp.size_gate(5.0, 5.0, ATR, P)
    assert not cp.size_gate(12.0, 9.0, float("nan"), P)


def test_pins():
    # range 1.0, lower wick 0.7, body 0.2, upper 0.1
    assert cp.pin_lower(10.7, 10.8, 9.8, 10.5, ATR, P)
    assert not cp.pin_upper(10.7, 10.8, 9.8, 10.5, ATR, P)
    assert cp.pin_upper(9.9, 10.8, 9.8, 10.1, ATR, P)
    # same shape, too small vs ATR -> gate false
    assert not cp.pin_lower(10.7, 10.8, 9.8, 10.5, 10.0, P)


def test_hammer_needs_prior_low_excluding_current_bar():
    o, h, l, c = 10.0, 10.05, 9.0, 10.04   # lower wick 1.0 >= 2*body 0.04, upper 0.01
    assert cp.hammer(o, h, l, c, prior_low_min=9.0, atr_absolute=ATR, p=P)       # equal -> inclusive
    assert not cp.hammer(o, h, l, c, prior_low_min=8.9, atr_absolute=ATR, p=P)   # not a fresh low
    assert not cp.hammer(o, h, l, c, prior_low_min=float("nan"), atr_absolute=ATR, p=P)
    # Card 03 also asks for a downtrend. The identity has no trend input; the same bar fires
    # from OHLC, the prior 5-bar low, and ATR alone.
    assert "trend" not in cp.hammer.__code__.co_varnames


def test_shooting_star_needs_prior_high_excluding_current_bar():
    # upper wick 0.96 >= 2*body 0.04, lower-wick share 0.04/1.04 <= 0.10, range 1.04 >= 0.5 ATR
    o, h, l, c = 10.0, 11.0, 9.96, 10.04
    assert cp.shooting_star(o, h, l, c, prior_high_max=11.0, atr_absolute=ATR, p=P)
    assert not cp.shooting_star(o, h, l, c, prior_high_max=11.01, atr_absolute=ATR, p=P)
    assert not cp.shooting_star(o, h, l, c, prior_high_max=float("nan"), atr_absolute=ATR, p=P)


def test_doji_size_gate_rejects_a_quiet_bar():
    # Balanced tiny body, range 0.30 < 0.5 ATR -> material doji stays off.
    assert not cp.doji_material(10.0, 10.15, 9.85, 10.01, ATR, P)
    # Same shares, range 1.20, clears the gate.
    assert cp.doji_material(10.0, 10.60, 9.40, 10.04, ATR, P)


def test_engulfing_covers_the_previous_body():
    # Previous body 10.5->10.0, current body 10.0->10.6. A previous wick up to 12 never
    # enters the call: the identity compares opens and closes.
    assert cp.engulfing_bull(10.0, 10.6, 10.5, 10.0, contiguous=True)
    assert set(cp.engulfing_bull.__code__.co_varnames) >= {"open_", "close", "prev_open", "prev_close"}
    assert "high" not in cp.engulfing_bull.__code__.co_varnames


def test_card_names_without_an_identity_stay_out_of_the_vector():
    names = set(CANONICAL_FEATURES)
    assert "pin_bar" not in names
    for absent in ("evening_star", "wait_for_next_candle", "reward_risk_bracket"):
        assert absent not in names
    assert {"morning_star", "higher_low", "lower_high", "sideways"} <= names
    assert {"hammer", "shooting_star", "doji_material", "engulfing_bull", "engulfing_bear",
            "pin_lower", "pin_upper", "inside_bar"} <= names


def test_doji_variants():
    assert cp.doji_material(10.0, 10.5, 9.5, 10.02, ATR, P)
    assert cp.dragonfly_doji(10.0, 10.01, 9.0, 10.0, ATR, P)
    assert cp.gravestone_doji(10.0, 11.0, 9.99, 10.0, ATR, P)
    assert not cp.doji_material(10.0, 10.01, 9.0, 10.0, ATR, P)   # dragonfly is not a balanced doji


def test_engulfing_inclusive_and_gap():
    # prev bearish 10.5 -> 10.0, current bullish 10.0 -> 10.6 (open == prev close: inclusive)
    assert cp.engulfing_bull(10.0, 10.6, 10.5, 10.0, contiguous=True)
    assert not cp.engulfing_bull(10.0, 10.6, 10.5, 10.0, contiguous=False)
    assert cp.engulfing_bear(10.5, 9.9, 10.0, 10.5, contiguous=True)
    assert cp.engulfing_strength(10.0, 10.6, 10.5, 10.0, True, P) == pytest.approx(1.2)
    assert cp.engulfing_strength(10.0, 10.6, 10.5, 10.0, False, P) == 0.0


def test_inside_bar_and_compression():
    assert cp.inside_bar(10.5, 10.0, 10.5, 9.9, contiguous=True)
    assert not cp.inside_bar(10.5, 10.0, 10.5, 9.9, contiguous=False)
    assert cp.compression_ratio(10.5, 10.0, 11.0, 10.0, True, P) == pytest.approx(0.5)
    assert cp.compression_ratio(10.5, 10.0, 11.0, 10.0, False, P) == 1.0
    assert cp.compression_ratio(10.5, 10.0, 10.0, 10.0, True, P) == 1.0      # flat mother bar


def test_contiguous_mask_marks_gaps():
    ts = pd.to_datetime(["2026-01-02 22:30", "2026-01-02 22:45", "2026-01-05 01:00", "2026-01-05 01:15"])
    assert cp.contiguous_mask(ts.to_numpy()).tolist() == [False, True, False, True]


def test_vectorized_mirror_equals_scalar_identities():
    rng = np.random.default_rng(7)
    n = 600
    c = 100 + np.cumsum(rng.normal(0, 0.5, n))
    o = np.r_[c[0], c[:-1]] + rng.normal(0, 0.1, n)
    h = np.maximum(o, c) + rng.exponential(0.3, n)
    l = np.minimum(o, c) - rng.exponential(0.3, n)
    o[50], h[50], l[50], c[50] = 100.0, 100.0, 100.0, 100.0          # zero-range bar
    atr = pd.Series(h - l).rolling(14).mean().to_numpy()               # NaN warmup
    contig = np.ones(n, bool)
    contig[0] = contig[200] = False                                    # a gap
    out = cp.compute_all(o, h, l, c, atr, contig, P)
    k = P.swing_lookback
    # argument shape per scalar identity (dispatched by name, so this test never binds a
    # registered feature name to a computed value itself)
    shapes = {"ohlc": ("upper_wick_ratio", "lower_wick_ratio"),
              "ohlc_atr": ("pin_lower", "pin_upper", "doji_material", "dragonfly_doji", "gravestone_doji",
                           "rejection_intensity_signed", "rejection_intensity_lower",
                           "rejection_intensity_upper"),
              "probe_low": ("hammer",), "probe_high": ("shooting_star",),
              "body_pair": ("engulfing_bull", "engulfing_bear"),
              "body_pair_p": ("engulfing_strength",),
              "range_pair": ("inside_bar",), "range_pair_p": ("compression_ratio",)}
    assert sorted(sum(shapes.values(), ())) == sorted(cp.PATTERN_COLUMNS)
    for i in range(n):
        pl = np.min(l[i - k:i]) if i >= k else float("nan")
        ph = np.max(h[i - k:i]) if i >= k else float("nan")
        po, ph1, pl1, pc = (o[i - 1], h[i - 1], l[i - 1], c[i - 1]) if i else (np.nan,) * 4
        args = {"ohlc": (o[i], h[i], l[i], c[i]),
                "ohlc_atr": (o[i], h[i], l[i], c[i], atr[i], P),
                "probe_low": (o[i], h[i], l[i], c[i], pl, atr[i], P),
                "probe_high": (o[i], h[i], l[i], c[i], ph, atr[i], P),
                "body_pair": (o[i], c[i], po, pc, contig[i]),
                "body_pair_p": (o[i], c[i], po, pc, contig[i], P),
                "range_pair": (h[i], l[i], ph1, pl1, contig[i]),
                "range_pair_p": (h[i], l[i], ph1, pl1, contig[i], P)}
        for shape, names in shapes.items():
            for fn_name in names:
                v = getattr(cp, fn_name)(*args[shape])
                assert out[fn_name][i] == np.float32(float(v)), (i, fn_name, out[fn_name][i], v)
        if i < 2:
            assert out["morning_star"][i] == np.float32(0.0)
            continue
        star = cp.morning_star(
            o[i - 2], h[i - 2], l[i - 2], c[i - 2],
            o[i - 1], h[i - 1], l[i - 1], c[i - 1],
            o[i], h[i], l[i], c[i],
            bool(contig[i - 1]), bool(contig[i]), P,
        )
        assert out["morning_star"][i] == np.float32(float(star)), (i, out["morning_star"][i], star)
    assert all(np.isfinite(out[name]).all() for name in cp.PATTERN_COLUMNS)
    assert np.isfinite(out["morning_star"]).all()
