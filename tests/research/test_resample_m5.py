"""Program 9 — M5 base resampling: the minute-grid "M15" rule + full-ladder associativity.

The additive `_RULE_MINUTES` extension must (a) aggregate M5->M15 by the same
calendar-floor/trailing-drop contract as the hour rules, (b) keep the whole ladder
associative (M5->M15->H1 == M5->H1, M5->M15->H4 == M5->H4 — M15 boundaries are a subset
of H1 boundaries by 00:00 alignment), and (c) leave the pre-existing H1/H4 path
byte-identical (bucket_floor dispatches hour rules to the original `_bucket_start`).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                              # noqa: E402
from research.resample import _RULE_HOURS, _bucket_start, bucket_floor, resample  # noqa: E402


def _c(ts: datetime, o, h, l, c, v, idx=0) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, index=idx)


def _m5_series(start: datetime, n: int, *, base=100.0) -> list[Candle]:
    """Deterministic zig-zag M5 series with distinct, well-formed OHLC per bar."""
    out = []
    prev = base
    for i in range(n):
        o = prev
        cl = o + (0.4 if i % 3 else -0.3)
        hi = max(o, cl) + 0.2 + 0.001 * i
        lo = min(o, cl) - 0.2 - 0.001 * i
        out.append(_c(start + timedelta(minutes=5 * i), o, hi, lo, cl, 1.0 + 0.5 * i, i))
        prev = cl
    return out


def _assert_ohlc_valid(candle: Candle, children: list[Candle]):
    assert candle.high == max(c.high for c in children)
    assert candle.low == min(c.low for c in children)
    assert candle.open == children[0].open
    assert candle.close == children[-1].close


# ── golden M5->M15 aggregation ───────────────────────────────────────────────────────
def test_m15_golden_bucket():
    # Three M15 buckets of M5 (3 bars each); the third is trailing -> dropped.
    base = datetime(2026, 1, 1, 0, 0, 0)
    m5 = _m5_series(base, 9)
    m15 = resample(m5, "M15")
    assert len(m15) == 2
    assert m15[0].timestamp == datetime(2026, 1, 1, 0, 0, 0)
    assert m15[1].timestamp == datetime(2026, 1, 1, 0, 15, 0)
    _assert_ohlc_valid(m15[0], m5[0:3])
    _assert_ohlc_valid(m15[1], m5[3:6])
    assert m15[0].volume == pytest.approx(sum(c.volume for c in m5[0:3]))


def test_m15_buckets_align_to_quarter_hours():
    # Start mid-bucket (00:10): the first (partial) bucket floors to 00:00.
    base = datetime(2026, 1, 1, 0, 10, 0)
    m5 = _m5_series(base, 8)                    # 00:10 .. 00:45
    m15 = resample(m5, "M15")
    # buckets 00:00 (partial head), 00:15, 00:30 emit; 00:45 is trailing -> dropped
    assert [c.timestamp.minute for c in m15] == [0, 15, 30]
    assert all(c.timestamp.minute % 15 == 0 for c in m15)


def test_trailing_partial_m15_bucket_dropped():
    m5 = _m5_series(datetime(2026, 1, 1), 5)    # bucket 00:00 complete + 00:15 partial
    m15 = resample(m5, "M15")
    assert len(m15) == 1 and m15[0].timestamp == datetime(2026, 1, 1, 0, 0, 0)


# ── full-ladder associativity ────────────────────────────────────────────────────────
def test_associativity_m5_m15_h1_equals_m5_h1():
    m5 = _m5_series(datetime(2026, 1, 1), 480)  # 40 hours of M5
    direct = resample(m5, "H1")
    chained = resample(resample(m5, "M15"), "H1")
    assert len(direct) == len(chained) and len(direct) > 0
    assert direct == chained                     # frozen dataclass equality = byte-identical


def test_associativity_m5_m15_h4_equals_m5_h4():
    m5 = _m5_series(datetime(2026, 1, 1), 480)
    direct = resample(m5, "H4")
    chained = resample(resample(m5, "M15"), "H4")
    assert len(direct) == len(chained) and len(direct) > 0
    assert direct == chained


def test_associativity_full_chain_m5_m15_h1_h4():
    m5 = _m5_series(datetime(2026, 1, 1), 960)  # 80 hours -> several H4 buckets
    direct = resample(m5, "H4")
    chained = resample(resample(resample(m5, "M15"), "H1"), "H4")
    assert direct == chained and len(direct) > 0


# ── gap handling (never fabricate) ───────────────────────────────────────────────────
def test_weekend_gap_no_merge_no_synthetic_m15():
    fri = datetime(2026, 1, 2, 21, 0, 0)
    mon = datetime(2026, 1, 5, 22, 0, 0)
    m5 = _m5_series(fri, 3) + _m5_series(mon, 3)
    m15 = resample(m5, "M15")
    assert len(m15) == 1
    assert m15[0].timestamp == fri               # Monday's bucket is trailing -> dropped


# ── pre-existing hour path unchanged ─────────────────────────────────────────────────
def test_bucket_floor_matches_original_bucket_start_for_hours():
    ts = datetime(2026, 3, 15, 13, 40, 0)
    for rule in ("H1", "H4"):
        assert bucket_floor(ts, rule) == _bucket_start(ts, _RULE_HOURS[rule])


def test_unsupported_rule_still_raises():
    with pytest.raises(ValueError):
        resample(_m5_series(datetime(2026, 1, 1), 8), "M30")
    with pytest.raises(ValueError):
        bucket_floor(datetime(2026, 1, 1), "M1")
