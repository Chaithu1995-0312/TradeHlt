"""Adverse-fill floor for `forward_walk` — SEM-016 ADVERSE_STOP_FILL_EXCURSION.

`forward_walk` is consumed by ~30 modules and is the governing outcome truth for
every research result in the repo. Two things must hold forever:

  1. the DEFAULT path (`adverse_fill=None`) is bit-identical to the historical
     behaviour — a fixed-stop SL_HIT is exactly -1.000R;
  2. when supplied, the model charges gap and slippage on the STOP side only, and
     never improves a take-profit.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from research.contracts import Signal  # noqa: E402
from research.measurement.forward_walk import (  # noqa: E402
    AdverseFill,
    forward_walk,
)


class Bar:
    """Minimal bar. `open` is optional so the no-`open` guard can be exercised."""

    def __init__(self, index, high, low, close, open_=None):
        self.index, self.high, self.low, self.close = index, high, low, close
        if open_ is not None:
            self.open = open_


def _sig(direction="long", entry=100.0, atr=10.0):
    return Signal(
        instrument="TEST", timestamp=datetime(2020, 1, 1), entry_index=0,
        direction=direction, entry=entry, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=atr,
    )


# ── 1. default path is the historical behaviour ──────────────────────────────

def test_default_fixed_stop_is_exactly_minus_one_r():
    """The defect SEM-016 describes — pinned so the default cannot drift."""
    # long entry 100, sl 90; bar trades down to 85 but we fill at 90 exactly
    out = forward_walk(_sig(), [Bar(1, 101.0, 85.0, 95.0, open_=99.0)], max_forward=5)
    assert out.outcome == "SL_HIT"
    assert out.rr_achieved == pytest.approx(-1.0, abs=1e-12)


def test_default_ignores_a_gap_open_entirely():
    """Even a bar opening far below the stop still books exactly -1R by default."""
    out = forward_walk(_sig(), [Bar(1, 80.0, 70.0, 75.0, open_=80.0)], max_forward=5)
    assert out.outcome == "SL_HIT"
    assert out.rr_achieved == pytest.approx(-1.0, abs=1e-12)


def test_default_works_without_an_open_attribute():
    """Historical callers pass bars carrying only high/low/close/index."""
    out = forward_walk(_sig(), [Bar(1, 101.0, 85.0, 95.0)], max_forward=5)
    assert out.rr_achieved == pytest.approx(-1.0, abs=1e-12)


# ── 2. gap-through fills at the open ─────────────────────────────────────────

def test_long_gap_open_below_stop_fills_at_open():
    af = AdverseFill(stop_slippage=0.5)
    # sl = 90; bar OPENS at 80 -> price never traded at 90, fill is 80 -> -2R
    out = forward_walk(_sig(), [Bar(1, 82.0, 70.0, 75.0, open_=80.0)], max_forward=5,
                       adverse_fill=af)
    assert out.outcome == "SL_HIT"
    assert out.rr_achieved == pytest.approx(-2.0, abs=1e-12)


def test_short_gap_open_above_stop_fills_at_open():
    af = AdverseFill(stop_slippage=0.5)
    # short entry 100, sl 110; bar OPENS at 120 -> fill 120 -> -2R
    out = forward_walk(_sig("short"), [Bar(1, 130.0, 118.0, 125.0, open_=120.0)],
                       max_forward=5, adverse_fill=af)
    assert out.outcome == "SL_HIT"
    assert out.rr_achieved == pytest.approx(-2.0, abs=1e-12)


def test_intrabar_stop_pays_slippage_not_the_open():
    af = AdverseFill(stop_slippage=0.5)
    # opens at 99 (above sl 90), trades down through it -> fill 90 - 0.5 = 89.5
    out = forward_walk(_sig(), [Bar(1, 101.0, 85.0, 95.0, open_=99.0)], max_forward=5,
                       adverse_fill=af)
    assert out.rr_achieved == pytest.approx(-1.05, abs=1e-12)


def test_adverse_fill_is_never_better_than_minus_one_r():
    """Directional invariant: the correction only ever makes a stop exit worse."""
    af = AdverseFill(stop_slippage=0.25)
    for direction, bar in (
        ("long", Bar(1, 101.0, 85.0, 95.0, open_=99.0)),
        ("long", Bar(1, 82.0, 70.0, 75.0, open_=80.0)),
        ("short", Bar(1, 115.0, 99.0, 112.0, open_=101.0)),
        ("short", Bar(1, 130.0, 118.0, 125.0, open_=120.0)),
    ):
        out = forward_walk(_sig(direction), [bar], max_forward=5, adverse_fill=af)
        assert out.outcome == "SL_HIT"
        assert out.rr_achieved <= -1.0


# ── 3. the take-profit side is untouched ─────────────────────────────────────

def test_take_profit_is_unaffected_by_adverse_fill():
    """A resting limit order does not fill better than its level."""
    af = AdverseFill(stop_slippage=5.0)
    bar = [Bar(1, 130.0, 99.0, 125.0, open_=101.0)]      # long tp = 120
    base = forward_walk(_sig(), bar, max_forward=5)
    adv = forward_walk(_sig(), bar, max_forward=5, adverse_fill=af)
    assert base.outcome == adv.outcome == "TP_HIT"
    assert adv.rr_achieved == pytest.approx(base.rr_achieved) == pytest.approx(2.0)


def test_timeout_is_unaffected_by_adverse_fill():
    af = AdverseFill(stop_slippage=5.0)
    bar = [Bar(1, 101.0, 99.0, 100.5, open_=100.0)]
    base = forward_walk(_sig(), bar, max_forward=5)
    adv = forward_walk(_sig(), bar, max_forward=5, adverse_fill=af)
    assert base.outcome == adv.outcome == "TIMEOUT"
    assert adv.rr_achieved == pytest.approx(base.rr_achieved)


# ── 4. fail closed, never silently skip ──────────────────────────────────────

def test_gap_modelling_without_open_fails_closed():
    """Silently skipping the gap branch would reintroduce the optimism."""
    with pytest.raises(ValueError, match=r"\.open"):
        forward_walk(_sig(), [Bar(1, 101.0, 85.0, 95.0)], max_forward=5,
                     adverse_fill=AdverseFill(stop_slippage=0.5))


def test_slippage_only_mode_works_without_open():
    out = forward_walk(_sig(), [Bar(1, 101.0, 85.0, 95.0)], max_forward=5,
                       adverse_fill=AdverseFill(stop_slippage=0.5, model_gaps=False))
    assert out.rr_achieved == pytest.approx(-1.05, abs=1e-12)


def test_negative_slippage_rejected():
    with pytest.raises(ValueError, match="stop_slippage"):
        AdverseFill(stop_slippage=-0.1)


def test_zero_slippage_no_gap_reproduces_the_default():
    af = AdverseFill(stop_slippage=0.0)
    bar = [Bar(1, 101.0, 85.0, 95.0, open_=99.0)]
    assert forward_walk(_sig(), bar, max_forward=5, adverse_fill=af).rr_achieved == pytest.approx(
        forward_walk(_sig(), bar, max_forward=5).rr_achieved
    )
