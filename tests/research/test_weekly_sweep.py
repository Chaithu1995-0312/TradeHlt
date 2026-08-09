"""Tests for weekly_range.py — pure geometry, synthetic candles, no CSV dependency.

Covers: normal-week high/low sweep + reversal direction; no-sweep; holiday-shortened week
(both accept/reject branches of min_accumulation_bars); weekend/week-boundary non-leakage
(the core no-lookahead-across-weeks regression); the one-shot-per-boundary-per-week guard;
the range-lock-before-Tuesday-closes rule; the intraday-gap guard; and
`is_week_structurally_valid`.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                      # noqa: E402
from data_ingestion.session_autoderive import derive_weekly_mask   # noqa: E402
from research.weekly_sweep.weekly_range import (                   # noqa: E402
    _first_sweep_this_week,
    _has_unexpected_gap,
    current_week_range,
    detect_weekly_sweep,
    is_week_structurally_valid,
)

MONDAY = datetime(2024, 1, 1)   # a Monday
BARS_PER_DAY = 96               # M15 bars/day


def _c(ts, o, h, l, c, idx, v=10.0):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, index=idx)


def _build_week(start=MONDAY, mon_low=99.0, mon_high=101.0, days=5, bars_per_day=BARS_PER_DAY):
    """One Mon-Fri week. Monday+Tuesday touch both [mon_low, mon_high] boundaries once each
    (so the accumulation range is exactly [mon_low, mon_high]); Wed-Fri stay flat and safely
    INSIDE that range until a test overrides a specific bar to create a sweep."""
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
            elif day in (0, 1):
                o, h, l, c = mid, mid + 0.05, mid - 0.05, mid   # inside [mon_low, mon_high]
            else:
                o, h, l, c = mid, mid + 0.05, mid - 0.05, mid   # inside [mon_low, mon_high]
            bars.append(_c(ts, o, h, l, c, idx))
            idx += 1
    return bars


def _wed_index(b=10):
    return 2 * BARS_PER_DAY + b   # Wednesday = day 2


def _set_sweep(bars, idx, *, boundary, h_ref=101.0, l_ref=99.0):
    """Overwrite bars[idx] to be a boundary-cross-then-close-back-inside sweep bar."""
    ts = bars[idx].timestamp
    if boundary == "HIGH":
        bars[idx] = _c(ts, 100.0, h_ref + 0.5, 99.9, 100.5, idx)
    else:
        bars[idx] = _c(ts, 100.0, 100.1, l_ref - 0.5, 99.5, idx)
    return bars


# ── current_week_range: range-lock + accumulation geometry ─────────────────────────────────
def test_range_lock_before_tuesday_closes():
    bars = _build_week()
    window = bars[:BARS_PER_DAY]   # only Monday's bars — Tuesday hasn't closed yet
    assert current_week_range(window, min_accumulation_bars=1) is None


def test_normal_week_range_and_high_sweep_direction_short():
    bars = _build_week()
    i = _wed_index(10)
    _set_sweep(bars, i, boundary="HIGH")
    window = bars[:i + 1]
    wr = current_week_range(window, min_accumulation_bars=40)
    assert wr is not None
    assert wr.h_ref == 101.0 and wr.l_ref == 99.0
    ev = detect_weekly_sweep(window, wr)
    assert ev is not None
    assert ev.boundary == "HIGH"
    assert ev.direction == "short"


def test_normal_week_low_sweep_direction_long():
    bars = _build_week()
    i = _wed_index(10)
    _set_sweep(bars, i, boundary="LOW")
    window = bars[:i + 1]
    wr = current_week_range(window, min_accumulation_bars=40)
    ev = detect_weekly_sweep(window, wr)
    assert ev is not None
    assert ev.boundary == "LOW"
    assert ev.direction == "long"


def test_no_sweep_when_bars_stay_inside_range():
    bars = _build_week()
    wr = current_week_range(bars[:_wed_index(10) + 1], min_accumulation_bars=40)
    for day in (2, 3, 4):
        for b in range(BARS_PER_DAY):
            i = day * BARS_PER_DAY + b
            if i >= len(bars):
                continue
            window = bars[:i + 1]
            assert detect_weekly_sweep(window, wr) is None


# ── holiday-shortened week ───────────────────────────────────────────────────────────────
def _tuesday_only_week(start=MONDAY, mon_low=99.0, mon_high=101.0, bars_per_day=BARS_PER_DAY):
    """Monday holiday (0 bars); Tuesday has a full session."""
    bars = []
    idx = 0
    tuesday = start + timedelta(days=1)
    for b in range(bars_per_day):
        ts = tuesday + timedelta(minutes=15 * b)
        if b == 0:
            o, h, l, c = 100.0, mon_high, 100.0, 100.0
        elif b == 1:
            o, h, l, c = 100.0, 100.0, mon_low, 100.0
        else:
            o, h, l, c = 100.0, 100.2, 99.8, 100.0
        bars.append(_c(ts, o, h, l, c, idx))
        idx += 1
    return bars


def test_holiday_shortened_week_accepted_when_threshold_low():
    bars = _tuesday_only_week()
    wr = current_week_range(bars, min_accumulation_bars=40)
    assert wr is not None
    assert wr.n_accumulation_bars == BARS_PER_DAY
    assert wr.h_ref == 101.0 and wr.l_ref == 99.0


def test_holiday_shortened_week_rejected_when_threshold_high():
    bars = _tuesday_only_week()
    wr = current_week_range(bars, min_accumulation_bars=200)   # more than the 96 available
    assert wr is None


# ── weekend / week-boundary non-leakage (no-lookahead-across-weeks regression) ─────────────
def test_new_week_does_not_leak_prior_week_range():
    week1 = _build_week(start=MONDAY, mon_low=99.0, mon_high=101.0)
    week2_start = MONDAY + timedelta(days=7)
    week2 = _build_week(start=week2_start, mon_low=105.0, mon_high=107.0)
    for i, b in enumerate(week2):
        b.index = len(week1) + i
    combined = week1 + week2
    # window ends on week2's Tuesday (range locked), spanning across the Fri->Mon gap
    week2_tue_end = len(week1) + 2 * BARS_PER_DAY - 1
    window = combined[:week2_tue_end + 1]
    wr = current_week_range(window, min_accumulation_bars=40)
    assert wr is not None
    assert (wr.h_ref, wr.l_ref) == (107.0, 105.0)   # week2's own range, NOT week1's [99,101]


# ── one-shot-per-boundary-per-week guard ────────────────────────────────────────────────
def test_one_shot_per_boundary_guard():
    bars = _build_week()
    i1 = _wed_index(10)
    i2 = _wed_index(11)
    _set_sweep(bars, i1, boundary="HIGH")
    _set_sweep(bars, i2, boundary="HIGH")
    wr = current_week_range(bars[:i1 + 1], min_accumulation_bars=40)

    window_first = bars[:i1 + 1]
    assert _first_sweep_this_week(window_first, wr, "HIGH") is True

    window_second = bars[:i2 + 1]
    assert _first_sweep_this_week(window_second, wr, "HIGH") is False


# ── intraday-gap guard (closes the intraweek-data-outage blind spot) ────────────────────
def test_intraweek_gap_invalidates_the_week():
    bars = _build_week()
    # Remove a chunk of Monday bars mid-morning to create a multi-hour gap.
    del bars[10:20]   # 10 bars * 15min = 2.5h dropped
    for i, b in enumerate(bars):
        b.index = i
    window = bars[:_wed_index(10) + 1 - 10]   # account for the removed bars
    assert current_week_range(window, min_accumulation_bars=1,
                              max_intraweek_gap_minutes=30) is None
    # Without the gap guard, the same window still produces a range (bar count clears).
    assert current_week_range(window, min_accumulation_bars=1) is not None


def test_has_unexpected_gap_pure():
    bars = _build_week()[:5]
    assert _has_unexpected_gap(bars, max_intraweek_gap_minutes=30) is False
    gapped = [bars[0], bars[4]]   # 45 minutes apart
    assert _has_unexpected_gap(gapped, max_intraweek_gap_minutes=30) is True
    assert _has_unexpected_gap(gapped, max_intraweek_gap_minutes=60) is False


# ── is_week_structurally_valid ───────────────────────────────────────────────────────────
def test_week_structurally_valid_with_normal_mask():
    bars = _build_week()
    window = bars[:_wed_index(10) + 1]
    mask = derive_weekly_mask((b.timestamp for b in bars), presence_min=0.5)
    assert is_week_structurally_valid(window, mask, holidays=set()) is True


def test_week_structurally_invalid_with_empty_mask():
    bars = _build_week()
    window = bars[:_wed_index(10) + 1]
    assert is_week_structurally_valid(window, frozenset(), holidays=set()) is False


def test_week_structurally_invalid_with_no_accumulation_bars():
    bars = _build_week()
    window = bars[2 * BARS_PER_DAY:_wed_index(10) + 1]   # Wed-only window, no Mon/Tue bars
    mask = derive_weekly_mask((b.timestamp for b in bars), presence_min=0.5)
    assert is_week_structurally_valid(window, mask, holidays=set()) is False
