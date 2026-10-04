"""calendar_periods.py — W1 (ISO week) and MN1 (calendar month) parent-candle aggregation.

CH-htfcrt-parent-candle-smc-v1 (2026-08-15): `research.resample.resample()` extends cleanly
to D1 (a degenerate 24-hour bucket, still hour-grid, still 00:00-of-day aligned — see the
comment on `resample._RULE_HOURS`), but W1 and MN1 are NOT fixed-hour buckets: a week can
start on any day-of-month and a month can start on any day-of-week, so `resample`'s
`ts.replace(hour=..., minute=0, ...)` floor — which can only move `ts` WITHIN its own
calendar day — cannot express either. This module is therefore a separate, calendar-KEY
aggregator, following the exact pattern already proven in
`research.weekly_sweep.weekly_range` (grouping by `isocalendar()` / month, lock-on-close,
`None`/dropped on an unclosed trailing period) rather than trying to force W1/MN1 into the
hour-grid design.

ASSOCIATIVITY CARVE-OUT (read before adding a W1->MN1 chain). `resample.py`'s central
determinism guarantee — `resample(resample(x,"H1"),"H4") == resample(x,"H4")` — holds because
every coarser rung's bucket boundaries are a strict SUPERSET of the finer rung's (H1 ⊆ H4 ⊆
D1, all anchored at 00:00). That containment FAILS between W1 and MN1: an ISO week routinely
straddles a month boundary (e.g. the week containing both the last days of January and the
first days of February), so a week is not a subset of any single month. Consequently:

    aggregate_calendar(aggregate_calendar(m15, "W1"), "MN1") != aggregate_calendar(m15, "MN1")

is a REAL, PERMANENT inequality, not a bug to fix. The rule enforced by this module: **MN1 is
always aggregated directly from the base (M15/D1) stream, never by re-grouping W1 parents.**
`aggregate_calendar` deliberately has no "resample of resample" chaining API to make that
mistake structurally harder to reach for.

CAUSALITY (identical discipline to `resample.py`): a period is emitted only when the first
bar of the NEXT period arrives; the trailing partial period is dropped unconditionally. No
period is ever fabricated — whatever bars exist in the window are aggregated, exactly as
`resample._emit` does for the hour-grid rules.

Pure, no I/O, no config reads, no spine import — the `research.weekly_sweep` isolation
precedent, extended to plain OHLC aggregation rather than sweep-geometry.

LAYERING (why the hour-grid rules are ALSO duplicated here, not imported from
`research.resample`): the established one-way dependency direction in this repo is
`src/research/ -> src/features/` (verified: every existing cross-import goes that direction;
searching `from research.` under `src/features/` returns nothing prior to this module). `features/`
is production code the live CRT spine (`config_layer.parent_crt`, Phase 2 of this program)
depends on; `research/` is the isolated, behavior-agnostic measurement harness. A production
feature module importing a research module would run that direction backwards — the same class
of defect the 2026-07-18 backwards-dependency audit fixed elsewhere in this repo (project
memory: `project_backwards_dep_refactor`). So `HOUR_GRID_HOURS` below is a deliberate,
cross-referenced DUPLICATE of `research.resample._RULE_HOURS`, not a shared import — if one
changes, check the other (both are 3-entry dicts; a mismatch is easy to spot on review, and
`tests/test_calendar_periods.py` cross-checks the two tables' floors agree on shared rules).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:  # avoid pulling the heavy crt_engine_v2 import at runtime
    from config_layer.crt_engine_v2 import Candle

# Duplicate of research.resample._RULE_HOURS — see the LAYERING note above. Same floor
# formula (`_bucket_start` there / `_hour_grid_start` here): floored_hour = (h // n) * n.
HOUR_GRID_HOURS = {"H1": 1, "H4": 4, "D1": 24}

CALENDAR_RULES = ("W1", "MN1")


def _iso_week_key(ts: datetime) -> tuple[int, int]:
    iso = ts.isocalendar()
    return (iso[0], iso[1])


def _month_key(ts: datetime) -> tuple[int, int]:
    return (ts.year, ts.month)


def _iso_week_start(year: int, week: int) -> datetime:
    """Monday 00:00 of the given ISO (year, week) — the W1 bucket's canonical timestamp."""
    d = date.fromisocalendar(year, week, 1)   # 1 = Monday
    return datetime(d.year, d.month, d.day)


def _month_start(year: int, month: int) -> datetime:
    """1st of the month, 00:00 — the MN1 bucket's canonical timestamp."""
    return datetime(year, month, 1)


def calendar_key(ts: datetime, rule: str) -> tuple[int, int]:
    """The (bucket-defining) calendar key for `ts` under `rule` ∈ {"W1", "MN1"}."""
    if rule == "W1":
        return _iso_week_key(ts)
    if rule == "MN1":
        return _month_key(ts)
    raise ValueError(f"calendar_key: unsupported rule '{rule}' (expected one of {CALENDAR_RULES})")


def bucket_start(key: tuple[int, int], rule: str) -> datetime:
    if rule == "W1":
        return _iso_week_start(*key)
    return _month_start(*key)


def _hour_grid_start(ts: datetime, hours: int) -> datetime:
    """Floor `ts` to its hour-grid bucket start — duplicate of `resample._bucket_start`
    (see the module LAYERING note)."""
    floored_hour = (ts.hour // hours) * hours
    return ts.replace(hour=floored_hour, minute=0, second=0, microsecond=0)


#: every rule this module accepts, hour-grid + calendar, for a single dispatch surface.
ALL_PERIOD_RULES = tuple(sorted(HOUR_GRID_HOURS)) + CALENDAR_RULES


def period_key(ts: datetime, rule: str):
    """Unified bucket key for ANY supported rule (hour-grid or calendar).

    Hour-grid rules (H1/H4/D1): the key IS the bucket-start timestamp (matching
    `research.resample.bucket_floor`'s convention). Calendar rules (W1/MN1): the key is the
    `(year, week|month)` tuple from `calendar_key`. `period_start` converts either key back to
    a canonical bucket-start timestamp — for hour-grid rules that is the identity function.
    """
    if rule in HOUR_GRID_HOURS:
        return _hour_grid_start(ts, HOUR_GRID_HOURS[rule])
    if rule in CALENDAR_RULES:
        return calendar_key(ts, rule)
    raise ValueError(f"period_key: unsupported rule '{rule}' (expected one of {ALL_PERIOD_RULES})")


def period_start(key, rule: str) -> datetime:
    """Inverse of `period_key`: the canonical bucket-start timestamp for `key` under `rule`."""
    if rule in HOUR_GRID_HOURS:
        return key   # hour-grid: the key already IS the bucket-start timestamp
    if rule in CALENDAR_RULES:
        return bucket_start(key, rule)
    raise ValueError(f"period_start: unsupported rule '{rule}' (expected one of {ALL_PERIOD_RULES})")


def _emit(children: "Sequence[Candle]", key: tuple[int, int], rule: str, index: int) -> "Candle":
    """Aggregate a non-empty list of child candles into one calendar-period parent candle.

    Identical aggregation contract to `resample._emit`: open=first.open, high=max, low=min,
    close=last.close, volume=Decimal-exact sum (grouping-invariant), timestamp=period start.
    """
    from config_layer.crt_engine_v2 import Candle

    ordered = list(children)
    vol = sum((Decimal(str(c.volume)) for c in ordered), Decimal(0))
    return Candle(
        timestamp=bucket_start(key, rule),
        open=ordered[0].open,
        high=max(c.high for c in ordered),
        low=min(c.low for c in ordered),
        close=ordered[-1].close,
        volume=float(vol),
        index=index,
    )


def aggregate_calendar(candles: "Sequence[Candle]", rule: str) -> "list[Candle]":
    """Aggregate chronologically-ordered `candles` into `rule` ∈ {"W1", "MN1"} parent candles.

    Input MUST be time-ordered (same contract as `resample.resample`). Emits a period only
    when a later period's first candle has arrived; drops the trailing partial period
    unconditionally — never fabricates a period, never flushes an in-progress one. Returns a
    fresh list whose `index` is the emitted-series position (0..len-1).

    Deliberately NOT chainable onto another calendar aggregation's output — see the module
    docstring's associativity carve-out. Always call this on the base M15 (or a resampled
    hour-grid, e.g. D1) stream, never on a prior `aggregate_calendar(..., "W1")` result.
    """
    if rule not in CALENDAR_RULES:
        raise ValueError(f"aggregate_calendar: unsupported rule '{rule}' (expected one of {CALENDAR_RULES})")

    out: "list[Candle]" = []
    cur_key: tuple[int, int] | None = None
    cur_children: "list[Candle]" = []

    for c in candles:
        key = calendar_key(c.timestamp, rule)
        if cur_key is None:
            cur_key = key
        elif key != cur_key:
            out.append(_emit(cur_children, cur_key, rule, len(out)))
            cur_key = key
            cur_children = []
        cur_children.append(c)

    # Trailing (cur_key) period intentionally NOT flushed — no later candle proves it closed.
    return out
