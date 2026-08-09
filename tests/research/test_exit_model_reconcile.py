"""B0 — research forward-walk realism reconciled to intrabar truth.

Verifies the governing `intrabar_fixed` exit model (default) vs opt-in `trailing`, and
the versioned truth-standard provenance stamped into research artifacts.
"""
from dataclasses import dataclass
from datetime import datetime

import pytest

from research.config import ResearchConfig
from research.contracts import Signal
from research.measurement.forward_walk import forward_walk, horizon_excursion
from research.provenance import TRUTH_STANDARD_VERSION, provenance_block


@dataclass
class Bar:
    high: float
    low: float
    close: float
    index: int


def _long_signal() -> Signal:
    return Signal(instrument="TEST", timestamp=datetime(2026, 1, 1), entry_index=0,
                  direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)


# Scenario isolating the ratchet: price runs to +1.0 (ratchets a trailing stop up to
# 100.5), pulls back to 100.4 (below the trailed stop, above the fixed SL 99), then on
# the next bar wicks to 98.5 (below the fixed SL).
_BARS = [
    Bar(high=101.0, low=100.4, close=100.5, index=1),
    Bar(high=100.6, low=98.5, close=98.6, index=2),
]


def test_intrabar_fixed_is_default():
    # No exit_model arg must equal explicit intrabar_fixed.
    a = forward_walk(_long_signal(), _BARS)
    b = forward_walk(_long_signal(), _BARS, exit_model="intrabar_fixed")
    assert a == b


def test_fixed_holds_to_original_sl():
    out = forward_walk(_long_signal(), _BARS, exit_model="intrabar_fixed")
    assert out.outcome == "SL_HIT"
    assert out.rr_achieved == -1.0          # exits at fixed SL (99), not the ratchet
    assert out.duration_candles == 2        # survives bar 1, stops on bar 2


def test_trailing_ratchets_and_exits_early():
    out = forward_walk(_long_signal(), _BARS, exit_model="trailing")
    assert out.outcome == "SL_HIT"
    assert out.rr_achieved == pytest.approx(0.5)   # trailed stop locked +0.5R
    assert out.duration_candles == 1               # exits on bar 1's pullback


def test_bad_exit_model_raises():
    with pytest.raises(ValueError, match="exit_model"):
        forward_walk(_long_signal(), _BARS, exit_model="nonsense")


# ── measure-only close_only mode (forensics) ─────────────────────────────────
def test_close_only_holds_on_wick_only_sl_touch():
    # Bar wicks below SL (99) but closes above it → intrabar_fixed STOPS, close_only HOLDS.
    sig = _long_signal()
    bar = Bar(high=100.5, low=98.5, close=100.0, index=1)
    fixed = forward_walk(sig, [bar], exit_model="intrabar_fixed")
    close = forward_walk(sig, [bar], exit_model="close_only")
    assert fixed.outcome == "SL_HIT" and fixed.rr_achieved == -1.0
    assert close.outcome == "TIMEOUT"          # close 100 never crossed SL 99 → no exit


def test_close_only_exits_when_close_crosses():
    sig = _long_signal()
    # Close below SL → close_only stops at the fixed SL level.
    out = forward_walk(sig, [Bar(high=100.2, low=98.0, close=98.5, index=1)],
                       exit_model="close_only")
    assert out.outcome == "SL_HIT"
    assert out.rr_achieved == -1.0


# ── exit-agnostic horizon excursion (forensics Layer 2) ─────────────────────
def test_horizon_ignores_sl_and_records_full_mfe():
    # Bar 1 dips to SL (would be a -1R loss in forward_walk); bar 2 runs to +2.5R.
    # horizon_excursion ignores exits → mfe_r ≈ 2.5, reached_2r True, drawdown-first.
    sig = _long_signal()
    bars = [Bar(high=100.2, low=98.5, close=99.0, index=1),
            Bar(high=102.5, low=99.5, close=102.0, index=2)]
    e = horizon_excursion(sig, bars)
    assert e["mfe_r"] == 2.5 and e["reached_2r"] is True and e["reached_3r"] is False
    assert e["mae_r"] == -1.5
    assert e["bars_to_first_1r"] == 2
    assert e["favorable_first"] is False        # −0.5R adverse (bar 1) preceded +1R (bar 2)


def test_horizon_favorable_first_true():
    sig = _long_signal()
    bars = [Bar(high=101.5, low=100.0, close=101.0, index=1),   # +1.5R, no adverse
            Bar(high=101.0, low=98.0, close=98.5, index=2)]     # −2R later
    e = horizon_excursion(sig, bars)
    assert e["bars_to_first_1r"] == 1
    assert e["favorable_first"] is True


def test_horizon_short_direction():
    sig = Signal(instrument="T", timestamp=datetime(2026, 1, 1), entry_index=0,
                 direction="short", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)
    e = horizon_excursion(sig, [Bar(high=100.3, low=98.2, close=98.5, index=1)])
    assert e["mfe_r"] == 1.8 and e["reached_1_5r"] is True and e["reached_2r"] is False


def test_horizon_lookahead_guard():
    sig = Signal(instrument="T", timestamp=datetime(2026, 1, 1), entry_index=10,
                 direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)
    with pytest.raises(ValueError, match="lookahead"):
        horizon_excursion(sig, [Bar(high=101.0, low=99.0, close=100.5, index=10)])


# ── provenance / truth-standard stamp ────────────────────────────────────────
def test_config_carries_exit_model():
    cfg = ResearchConfig.from_file()
    assert cfg.exit_model == "intrabar_fixed"


def test_provenance_block_shape():
    p = provenance_block("intrabar_fixed", 12.0)
    assert p["truth_standard"] == {
        "version": TRUTH_STANDARD_VERSION,
        "exit_geometry": "intrabar_fixed",
        "slippage_model": "flat_12bps",
        "tie_break": "SL_before_TP",
    }
    assert p["research_cost_model_version"] and p["spine_cost_model_version"]
