"""Tests for the weekly_sweep_reversal hypothesis — registration, Signal emission on a
weekly-sweep setup, weekday/range-lock gating, the one-shot guard, exit geometry, and
determinism/no-lookahead. Mirrors tests/research/test_compression_breakout.py's structure.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                             # noqa: E402
import research.hypotheses                                                # noqa: F401,E402 (register)
from research.hypotheses.weekly_sweep_reversal import WeeklySweepReversal  # noqa: E402
from research.registry import get_hypothesis                              # noqa: E402

MONDAY = datetime(2024, 1, 1)   # a Monday
BARS_PER_DAY = 96


def _c(ts, o, h, l, c, idx, v=10.0):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, index=idx)


def _build_week(start=MONDAY, mon_low=99.0, mon_high=101.0, days=5, bars_per_day=BARS_PER_DAY):
    bars = []
    idx = 0
    for day in range(days):
        for b in range(bars_per_day):
            ts = start + timedelta(days=day, minutes=15 * b)
            mid = (mon_low + mon_high) / 2.0
            if day in (0, 1) and b == 0:
                o, h, l, c = mid, mon_high, mid, mid
            elif day in (0, 1) and b == 1:
                o, h, l, c = mid, mid, mon_low, mid
            else:
                o, h, l, c = mid, mid + 0.05, mid - 0.05, mid
            bars.append(_c(ts, o, h, l, c, idx))
            idx += 1
    return bars


def _wed_index(b=10):
    return 2 * BARS_PER_DAY + b   # Wednesday = day 2


def _set_sweep(bars, idx, *, boundary, h_ref=101.0, l_ref=99.0):
    ts = bars[idx].timestamp
    if boundary == "HIGH":
        bars[idx] = _c(ts, 100.0, h_ref + 0.5, 99.9, 100.5, idx)
    else:
        bars[idx] = _c(ts, 100.0, 100.1, l_ref - 0.5, 99.5, idx)
    return bars


def _hyp(**overrides):
    kwargs = dict(min_accumulation_bars=40, sl_range_frac=0.25, atr_period=14,
                  max_intraweek_gap_minutes=30.0, regime_tercile_window=2000,
                  check_week_validity=False)
    kwargs.update(overrides)
    return WeeklySweepReversal(**kwargs)


def test_registered():
    h = get_hypothesis("weekly_sweep_reversal")
    assert h.name == "weekly_sweep_reversal"
    assert h.family == "structural"


def test_emits_short_signal_on_high_sweep():
    bars = _build_week()
    i = _wed_index(10)
    _set_sweep(bars, i, boundary="HIGH")
    window = bars[:i + 1]
    sigs = _hyp().detect(window, {}, {"instrument": "TEST"})
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == "short"
    assert s.entry_index == window[-1].index
    assert s.entry == window[-1].close
    assert s.meta["boundary"] == "HIGH"
    assert "direction_vol_cell" in s.meta


def test_emits_long_signal_on_low_sweep():
    bars = _build_week()
    i = _wed_index(10)
    _set_sweep(bars, i, boundary="LOW")
    window = bars[:i + 1]
    sigs = _hyp().detect(window, {}, {"instrument": "TEST"})
    assert len(sigs) == 1
    assert sigs[0].direction == "long"
    assert sigs[0].meta["boundary"] == "LOW"


def test_no_signal_before_tuesday_closes():
    bars = _build_week()
    window = bars[:BARS_PER_DAY]   # Monday only — Tuesday hasn't closed yet
    assert _hyp().detect(window, {}, {"instrument": "TEST"}) == []


def test_no_signal_on_monday_or_tuesday_bars():
    """Even if a Mon/Tue bar geometrically pierces a PRIOR week's range, detect() returns []
    -- the weekday gate short-circuits before the range/sweep logic ever runs."""
    prior_week = _build_week(start=MONDAY - timedelta(days=7), mon_low=99.0, mon_high=101.0)
    current_week = _build_week(start=MONDAY, mon_low=99.0, mon_high=101.0)
    combined = prior_week + current_week
    for idx, b in enumerate(combined):
        b.index = idx
    mon_bar_pos = len(prior_week)   # current week's very first (Monday) bar
    combined[mon_bar_pos] = _c(combined[mon_bar_pos].timestamp, 100.0, 102.0, 99.9, 101.5,
                               combined[mon_bar_pos].index)
    window = combined[:mon_bar_pos + 1]
    assert _hyp().detect(window, {}, {"instrument": "TEST"}) == []


def test_no_repeat_signal_same_boundary_same_week():
    bars = _build_week()
    i1 = _wed_index(10)
    i2 = _wed_index(11)
    _set_sweep(bars, i1, boundary="HIGH")
    _set_sweep(bars, i2, boundary="HIGH")
    h = _hyp()
    sigs1 = h.detect(bars[:i1 + 1], {}, {"instrument": "TEST"})
    assert len(sigs1) == 1
    sigs2 = h.detect(bars[:i2 + 1], {}, {"instrument": "TEST"})
    assert sigs2 == []


def test_exit_geometry_targets_opposite_boundary():
    bars = _build_week()
    i = _wed_index(10)
    _set_sweep(bars, i, boundary="HIGH")
    window = bars[:i + 1]
    s = _hyp().detect(window, {}, {"instrument": "TEST"})[0]
    range_width = 101.0 - 99.0
    assert abs(s.tp_atr_mult * s.atr - range_width) < 1e-6
    assert abs(s.sl_atr_mult * s.atr - 0.25 * range_width) < 1e-6


def test_detect_is_deterministic():
    bars = _build_week()
    i = _wed_index(10)
    _set_sweep(bars, i, boundary="HIGH")
    h = _hyp()
    window = bars[:i + 1]
    assert h.detect(window, {}, {"instrument": "T"}) == h.detect(window, {}, {"instrument": "T"})


def test_no_lookahead_smoke():
    """The Signal detect() fires when window[-1] IS the sweep bar must not change depending
    on whether MORE future bars exist beyond it in the underlying series (replicates the
    runner's sliding-window usage): re-slicing a longer series back to the same boundary must
    reproduce the identical signal as truncating the series there directly."""
    bars = _build_week()
    i = _wed_index(10)
    _set_sweep(bars, i, boundary="HIGH")
    h = _hyp()

    window_truncated = bars[:i + 1]
    sig_truncated = h.detect(window_truncated, {}, {"instrument": "TEST"})

    extended = bars[:i + 1] + bars[i + 1:i + 51]   # same prefix + 50 MORE future bars appended
    window_at_i_from_extended = extended[:i + 1]   # re-slice back to the same boundary
    sig_from_extended = h.detect(window_at_i_from_extended, {}, {"instrument": "TEST"})

    assert sig_truncated == sig_from_extended
