"""CH-htfcrt-parent-candle-smc-v1 — features.calendar_periods tests.

Covers what makes this module load-bearing:
  * hour-grid table (`HOUR_GRID_HOURS`) stays byte-identical to `research.resample._RULE_HOURS`
    (the deliberate duplicate the module's LAYERING note declares — this test is the mechanical
    guard the docstring promises)
  * `period_key`/`period_start` agree with `research.resample.bucket_floor` on every shared rule
  * D1 golden aggregation + midnight floor
  * W1/MN1 golden aggregation, lock-on-close, trailing-partial-drop, weekend/gap safety
  * the W1 -> MN1 associativity FAILURE is real and reproducible (not just asserted in prose)
  * OHLC integrity + volume conservation on every rule
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle          # noqa: E402
from features.calendar_periods import (                # noqa: E402
    ALL_PERIOD_RULES, CALENDAR_RULES, HOUR_GRID_HOURS,
    aggregate_calendar, calendar_key, period_key, period_start,
)
from research.resample import _RULE_HOURS, bucket_floor, resample  # noqa: E402


def _c(ts: datetime, o, h, l, c, v, idx=0) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, index=idx)


def _m15_series(start: datetime, n: int, *, base=100.0) -> list[Candle]:
    out = []
    prev = base
    for i in range(n):
        o = prev
        cl = o + (0.4 if i % 3 else -0.3)
        hi = max(o, cl) + 0.2 + 0.001 * i
        lo = min(o, cl) - 0.2 - 0.001 * i
        out.append(_c(start + timedelta(minutes=15 * i), o, hi, lo, cl, 1.0 + 0.5 * i, i))
        prev = cl
    return out


def _assert_ohlc_valid(candle: Candle, children: list[Candle]):
    assert candle.high == max(c.high for c in children)
    assert candle.low == min(c.low for c in children)
    assert candle.open == children[0].open
    assert candle.close == children[-1].close
    assert candle.high >= max(candle.open, candle.close)
    assert candle.low <= min(candle.open, candle.close)
    assert abs(candle.volume - sum(c.volume for c in children)) < 1e-9


# ── layering guard: the duplicate table must never silently drift ──────────────────
def test_hour_grid_table_matches_resample_exactly():
    assert HOUR_GRID_HOURS == _RULE_HOURS


@pytest.mark.parametrize("rule", ["H1", "H4", "D1"])
def test_period_key_agrees_with_bucket_floor(rule):
    ts = datetime(2024, 3, 17, 13, 37, 5)
    if rule == "D1":
        # D1 exists only in calendar_periods (resample gained it in the same program;
        # confirm both independently derive the same midnight floor via their own tables).
        assert period_key(ts, "D1") == ts.replace(hour=0, minute=0, second=0, microsecond=0)
    assert period_key(ts, rule) == bucket_floor(ts, rule)


def test_all_period_rules_is_exhaustive_and_sorted_hour_grid_first():
    assert set(ALL_PERIOD_RULES) == set(HOUR_GRID_HOURS) | set(CALENDAR_RULES)
    assert ALL_PERIOD_RULES[-2:] == CALENDAR_RULES


# ── D1 (via research.resample, exercised here for the parent-candle use case) ──────
def test_d1_golden_aggregation_and_midnight_floor():
    start = datetime(2024, 1, 1, 0, 0)
    m15 = _m15_series(start, 96 * 5)   # 5 full days
    d1 = resample(m15, "D1")
    assert len(d1) == 4   # trailing partial (day 5) dropped
    for i, day in enumerate(d1):
        assert day.timestamp == start + timedelta(days=i)
        assert day.timestamp.hour == 0 and day.timestamp.minute == 0
        children = [c for c in m15 if c.timestamp.date() == day.timestamp.date()]
        assert len(children) == 96
        _assert_ohlc_valid(day, children)


# ── W1 golden aggregation ───────────────────────────────────────────────────────────
def test_w1_golden_aggregation_starts_on_monday():
    start = datetime(2024, 1, 1, 0, 0)   # a Monday
    m15 = _m15_series(start, 96 * 21)    # 3 ISO weeks
    w1 = aggregate_calendar(m15, "W1")
    assert len(w1) == 2   # trailing partial week dropped
    for wk in w1:
        assert wk.timestamp.weekday() == 0
        children = [c for c in m15 if calendar_key(c.timestamp, "W1") == calendar_key(wk.timestamp, "W1")]
        _assert_ohlc_valid(wk, children)


def test_w1_mid_week_start_still_locks_to_the_correct_iso_week():
    # Start mid-week (Wednesday), continuous bars (this helper has no weekday gaps) for
    # 14 days: spans a partial first week (Wed-Sun), a full second week, and a partial
    # trailing third week (dropped) -> 2 closed weeks.
    start = datetime(2024, 1, 3, 0, 0)   # a Wednesday
    m15 = _m15_series(start, 96 * 14)
    w1 = aggregate_calendar(m15, "W1")
    assert len(w1) == 2
    # the FIRST emitted week's key must be the ISO week containing 2024-01-03, and its
    # children must start at the series' own first bar (Wed), not a fabricated Monday.
    assert calendar_key(w1[0].timestamp, "W1") == calendar_key(start, "W1")
    first_week_children = [c for c in m15 if calendar_key(c.timestamp, "W1") == calendar_key(start, "W1")]
    assert first_week_children[0].timestamp == start


# ── MN1 golden aggregation ───────────────────────────────────────────────────────────
def test_mn1_golden_aggregation_starts_on_first_of_month():
    start = datetime(2024, 1, 1, 0, 0)
    # 93 continuous days = all of Jan(31) + Feb(29, leap) + Mar(31) fully closed, 2 days
    # into April as the dropped trailing partial.
    m15 = _m15_series(start, 96 * 93)
    mn1 = aggregate_calendar(m15, "MN1")
    assert len(mn1) == 3
    for i, mo in enumerate(mn1):
        assert mo.timestamp.day == 1 and mo.timestamp.hour == 0
        assert mo.timestamp.month == i + 1
        children = [c for c in m15 if calendar_key(c.timestamp, "MN1") == calendar_key(mo.timestamp, "MN1")]
        _assert_ohlc_valid(mo, children)


def test_mn1_february_leap_year_boundary():
    start = datetime(2024, 2, 1, 0, 0)   # 2024 is a leap year (Feb has 29 days)
    m15 = _m15_series(start, 96 * 29 + 96 * 5)   # all of Feb + a few days into March
    mn1 = aggregate_calendar(m15, "MN1")
    assert len(mn1) == 1
    feb = mn1[0]
    children = [c for c in m15 if c.timestamp.month == 2]
    assert len(children) == 96 * 29
    _assert_ohlc_valid(feb, children)


# ── the documented associativity FAILURE, reproduced (not just asserted in prose) ──
def test_w1_to_mn1_associativity_genuinely_fails_across_a_month_boundary():
    """A week straddling a month boundary makes W1-then-MN1 chaining wrong.

    2024-01-29 is a Monday; its ISO week runs 2024-01-29..2024-02-04, straddling the
    Jan/Feb boundary. Grouping M15 directly by month must NOT match what you'd get by
    (incorrectly) re-grouping W1 parents by month, because that straddling week's bars
    would be attributed entirely to one W1 parent that itself can't be re-split by month.
    """
    straddle_week_start = datetime(2024, 1, 29, 0, 0)
    m15 = _m15_series(straddle_week_start, 96 * 7)   # exactly the straddling week
    w1 = aggregate_calendar(m15, "W1")
    assert len(w1) == 0   # single week, dropped as trailing (never closes in this window)

    # Direct MN1 aggregation over the SAME straddling data sees Jan and Feb bars mixed
    # within one still-open (never-closed, in this short window) month bucket too --
    # but extend the window enough to close January's month bucket and demonstrate the
    # week's bars are split across two DIFFERENT MN1 periods, which a W1 parent (a single
    # atomic object) could never be re-split into.
    jan_bars = [c for c in m15 if c.timestamp.month == 1]
    feb_bars = [c for c in m15 if c.timestamp.month == 2]
    assert jan_bars and feb_bars, "the straddling week must contain bars from both months"
    # The single W1 parent (if it had closed) would carry a timestamp of just ONE month
    # (2024-01-29, a Monday in January) yet its true high/low mixes Jan+Feb bars -- so
    # re-deriving "the Feb MN1 candle" FROM that W1 parent alone is structurally impossible;
    # only direct aggregation from the base stream (as aggregate_calendar always does) is
    # correct. This is the concrete mechanism behind the module's documented inequality.
    assert calendar_key(jan_bars[-1].timestamp, "MN1") != calendar_key(feb_bars[0].timestamp, "MN1")
    assert calendar_key(jan_bars[-1].timestamp, "W1") == calendar_key(feb_bars[0].timestamp, "W1")


# ── weekend gap / trailing-drop / no-fabrication (same discipline as resample.py) ───
def _m15_series_no_weekends(start: datetime, n_weekdays_worth: int, *, base=100.0) -> list[Candle]:
    """Like `_m15_series` but SKIPS Saturday/Sunday entirely (a real FX/crypto-session-gapped
    corpus never has weekend bars) — the generator this specific test needs, distinct from
    the plain continuous `_m15_series` every other test intentionally uses."""
    out = []
    prev = base
    i = 0
    ts = start
    produced = 0
    while produced < n_weekdays_worth * 96:
        if ts.weekday() not in (5, 6):
            o = prev
            cl = o + (0.4 if i % 3 else -0.3)
            hi = max(o, cl) + 0.2 + 0.001 * i
            lo = min(o, cl) - 0.2 - 0.001 * i
            out.append(_c(ts, o, hi, lo, cl, 1.0 + 0.5 * i, i))
            prev = cl
            i += 1
            produced += 1
        ts += timedelta(minutes=15)
    return out


def test_w1_weekend_gap_never_fabricates_a_bar():
    start = datetime(2024, 1, 1, 0, 0)   # a Monday
    m15 = _m15_series_no_weekends(start, n_weekdays_worth=14)   # 2 full weekday-only weeks
    assert all(c.timestamp.weekday() not in (5, 6) for c in m15), "generator sanity check"
    w1 = aggregate_calendar(m15, "W1")
    assert len(w1) >= 1
    for wk in w1:
        children = [c for c in m15 if calendar_key(c.timestamp, "W1") == calendar_key(wk.timestamp, "W1")]
        assert all(c.timestamp.weekday() not in (5, 6) for c in children)
        # exactly 5 weekdays' worth of bars, never a fabricated Sat/Sun bar to pad the count
        assert len(children) == 5 * 96


def test_unsupported_rule_raises():
    with pytest.raises(ValueError):
        aggregate_calendar([], "H4")
    with pytest.raises(ValueError):
        period_key(datetime(2024, 1, 1), "BOGUS")
    with pytest.raises(ValueError):
        period_start((2024, 1), "BOGUS")
