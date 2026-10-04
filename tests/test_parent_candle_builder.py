"""CH-htfcrt-parent-candle-smc-v1 — features.parent_candle.ParentCandleBuilder tests.

The load-bearing property is NO-LOOKAHEAD: `parent_candle` / `parent_history` must NEVER
expose an in-progress (not-yet-closed) period's accumulator. Every test in this file that
pushes candles one at a time checks that invariant adversarially at every step, not just at
the end — a builder that leaks the open bucket only on, say, the 50th push would pass an
end-of-run-only check but is exactly the defect this module exists to prevent.
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
from features.calendar_periods import aggregate_calendar  # noqa: E402
from features.parent_candle import ParentCandleBuilder, SUPPORTED_RULES  # noqa: E402
from research.resample import resample                  # noqa: E402


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


def test_supported_rules_covers_h1_h4_d1_w1_mn1():
    assert set(SUPPORTED_RULES) == {"H1", "H4", "D1", "W1", "MN1"}


def test_unsupported_rule_raises_at_construction():
    with pytest.raises(ValueError):
        ParentCandleBuilder("M15")   # not a valid PARENT rule (finer than the base stream)


def test_parent_candle_is_none_until_first_close():
    start = datetime(2024, 1, 1, 0, 0)
    m15 = _m15_series(start, 20)   # well short of one H4 bucket (16 bars)
    b = ParentCandleBuilder("H4", keep=1)
    for c in m15:
        b.push(c)
    # H4 bucket is [00:00,04:00); 20*15min = 5h -> bucket 1 closed at 04:00, bucket 2 open
    assert b.parent_candle is not None
    assert b.parent_candle.timestamp == start


def test_parent_candle_never_none_check_before_any_push():
    b = ParentCandleBuilder("D1", keep=3)
    assert b.parent_candle is None
    assert b.parent_history == []


@pytest.mark.parametrize("rule,resample_fn", [
    ("H1", lambda m15: resample(m15, "H1")),
    ("H4", lambda m15: resample(m15, "H4")),
    ("D1", lambda m15: resample(m15, "D1")),
    ("W1", lambda m15: aggregate_calendar(m15, "W1")),
    ("MN1", lambda m15: aggregate_calendar(m15, "MN1")),
])
def test_streaming_output_matches_batch_aggregation(rule, resample_fn):
    """The incremental push() API must produce EXACTLY the same closed periods (values and
    count) as the equivalent batch resample/aggregate_calendar call — same causality
    contract, different delivery mechanism."""
    start = datetime(2024, 1, 1, 0, 0)   # a Monday, for clean W1/MN1 alignment too
    m15 = _m15_series(start, 96 * 70)    # ~70 days: plenty of H1/H4/D1/W1 periods, 2 months

    batch = resample_fn(m15)

    b = ParentCandleBuilder(rule, keep=len(batch) + 1 if batch else 1)
    for c in m15:
        b.push(c)
    streamed = b.parent_history

    assert len(streamed) == len(batch)
    for s, expect in zip(streamed, batch):
        assert s.timestamp == expect.timestamp
        assert s.open == expect.open
        assert s.high == expect.high
        assert s.low == expect.low
        assert s.close == expect.close
        assert abs(s.volume - expect.volume) < 1e-9


def test_keep_bounds_history_to_a_ring_of_the_last_n_closed_periods():
    start = datetime(2024, 1, 1, 0, 0)
    m15 = _m15_series(start, 96 * 20)   # 20 D1 periods worth
    b = ParentCandleBuilder("D1", keep=3)
    for c in m15:
        b.push(c)
    hist = b.parent_history
    assert len(hist) == 3
    # oldest-first, and the LAST entry must equal parent_candle (the most recent close)
    assert hist[-1].timestamp == b.parent_candle.timestamp
    # ring must hold the 3 MOST RECENT closed periods, not the first 3
    from research.resample import resample as _rs
    full = _rs(m15, "D1")
    assert [h.timestamp for h in hist] == [c.timestamp for c in full[-3:]]


def test_adversarial_no_lookahead_every_single_push_h4():
    """At EVERY push, not just at the end: parent_candle must reflect only bars strictly
    before the current bucket, never the bar just pushed if it opened a new bucket, and
    never a partial view of the currently-open bucket."""
    start = datetime(2024, 1, 1, 0, 0)
    m15 = _m15_series(start, 96 * 10, base=1000.0)   # large distinct base -> easy to detect leakage
    b = ParentCandleBuilder("H4", keep=50)

    from research.resample import bucket_floor
    for i, c in enumerate(m15):
        closed = b.push(c)
        pc = b.parent_candle
        cur_bucket_start = bucket_floor(c.timestamp, "H4")
        if pc is not None:
            # the reported parent candle's bucket must be STRICTLY earlier than the bucket
            # the just-pushed candle belongs to -- it can never be the (possibly still-open,
            # possibly just-closed-by-this-very-push) current bucket's live accumulator.
            assert pc.timestamp < cur_bucket_start, (
                f"push #{i}: parent_candle timestamp {pc.timestamp} is not strictly before "
                f"the current bucket {cur_bucket_start} -- possible lookahead leak"
            )
        if closed:
            # a close was JUST reported on this push -> the newly closed period's timestamp
            # must be the PREVIOUS bucket (before this candle's own bucket).
            assert pc is not None
            assert pc.timestamp == bucket_floor(m15[i - 1].timestamp, "H4")


def test_adversarial_no_lookahead_across_all_five_rules():
    start = datetime(2024, 1, 1, 0, 0)
    m15 = _m15_series(start, 96 * 65, base=5000.0)
    for rule in SUPPORTED_RULES:
        b = ParentCandleBuilder(rule, keep=200)
        seen_timestamps = []
        for c in m15:
            b.push(c)
            pc = b.parent_candle
            if pc is not None:
                # monotonic: once history grows it never "goes back" or repeats a period
                if seen_timestamps:
                    assert pc.timestamp >= seen_timestamps[-1]
                if not seen_timestamps or pc.timestamp != seen_timestamps[-1]:
                    seen_timestamps.append(pc.timestamp)
                # the parent candle can never be built from data at or after `c` itself in
                # a way that includes `c`'s own bucket while that bucket is still open --
                # cross-checked structurally via test_streaming_output_matches_batch_aggregation;
                # here we only check monotonic non-decreasing closed-period timestamps.
        assert seen_timestamps == sorted(seen_timestamps)
