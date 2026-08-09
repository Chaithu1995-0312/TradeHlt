"""Program 3 — deterministic M15 -> H1/H4 resampler tests.

The resampler's single most important property is DETERMINISM + CAUSALITY: it produces
input data for the audited research spine, so a boundary/lookahead bug here would silently
corrupt every HTF qualification verdict. These tests pin:

  * golden aggregation (open=first, high=max, low=min, close=last, volume=sum)
  * associativity (M15->H1->H4 == M15->H4, byte-identical) — catches boundary bugs
  * SHA-256 determinism of the written CSV across independent runs
  * weekend gap: Friday->Monday never merges and emits no synthetic bars
  * intra-hour gap: aggregate only observed children, never fabricate
  * trailing partial bucket dropped unconditionally
  * OHLC integrity + volume conservation + timestamp/index monotonicity
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle          # noqa: E402
from research.resample import resample, write_csv, CSV_HEADER  # noqa: E402


# ── helpers ─────────────────────────────────────────────────────────────────────
def _c(ts: datetime, o, h, l, c, v, idx=0) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, index=idx)


def _m15_series(start: datetime, n: int, *, base=100.0) -> list[Candle]:
    """A deterministic zig-zag M15 series with distinct, well-formed OHLC per bar."""
    out = []
    prev = base
    for i in range(n):
        o = prev
        cl = o + (0.4 if i % 3 else -0.3)
        hi = max(o, cl) + 0.2 + 0.001 * i      # distinct highs so max() is meaningful
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


# ── golden aggregation ────────────────────────────────────────────────────────────
def test_h1_golden_bucket():
    # Three hours of M15: hours 00 & 01 emit; hour 02 is the trailing bucket -> dropped.
    base = datetime(2026, 1, 1, 0, 0, 0)
    m15 = _m15_series(base, 12)          # hours 00,01,02 each 4 bars; 02 is trailing
    h1 = resample(m15, "H1")
    assert len(h1) == 2                  # only the 2 buckets a later candle closed
    assert h1[0].timestamp == datetime(2026, 1, 1, 0, 0, 0)
    assert h1[1].timestamp == datetime(2026, 1, 1, 1, 0, 0)
    _assert_ohlc_valid(h1[0], m15[0:4])
    _assert_ohlc_valid(h1[1], m15[4:8])
    assert h1[0].volume == pytest.approx(sum(c.volume for c in m15[0:4]))


def test_index_is_emit_position_and_monotonic():
    m15 = _m15_series(datetime(2026, 1, 1), 12)   # 3 hours, last dropped if partial -> here 3 complete? 12 bars = hours 00,01,02 each 4 -> 3 complete, but trailing (02) dropped
    h1 = resample(m15, "H1")
    assert [c.index for c in h1] == list(range(len(h1)))
    ts = [c.timestamp for c in h1]
    assert ts == sorted(ts) and len(set(ts)) == len(ts)   # strictly increasing


# ── the trailing-drop invariant ────────────────────────────────────────────────────
def test_trailing_partial_bucket_dropped_unconditionally():
    base = datetime(2026, 1, 1, 0, 0, 0)
    # Hour 00 complete (4 bars) + hour 01 partial (2 bars) -> only hour 00 emitted.
    m15 = _m15_series(base, 6)
    h1 = resample(m15, "H1")
    assert len(h1) == 1
    assert h1[0].timestamp == base


def test_even_a_complete_final_bucket_is_dropped_when_untriggered():
    # Exactly one hour of data: the bucket is complete but no NEXT candle triggers it.
    m15 = _m15_series(datetime(2026, 1, 1), 4)
    assert resample(m15, "H1") == []     # conservative + deterministic


# ── associativity (byte-identical) ─────────────────────────────────────────────────
def test_associativity_m15_h1_h4_equals_m15_h4():
    # 40 hours of M15 (160 bars) so several full H4 buckets exist.
    m15 = _m15_series(datetime(2026, 1, 1, 0, 0, 0), 160)
    direct = resample(m15, "H4")
    chained = resample(resample(m15, "H1"), "H4")
    assert len(direct) == len(chained) and len(direct) > 0
    # Object equality (frozen dataclass) == byte-identical fields incl. volume.
    assert direct == chained


def test_associativity_holds_in_written_csv_bytes(tmp_path):
    m15 = _m15_series(datetime(2026, 1, 1), 160)
    d = tmp_path / "direct.csv"
    ch = tmp_path / "chained.csv"
    write_csv(resample(m15, "H4"), d)
    write_csv(resample(resample(m15, "H1"), "H4"), ch)
    assert d.read_bytes() == ch.read_bytes()


# ── SHA-256 determinism ─────────────────────────────────────────────────────────────
def test_written_csv_is_sha256_identical_across_runs(tmp_path):
    m15 = _m15_series(datetime(2026, 1, 1), 100)
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    write_csv(resample(m15, "H1"), a)
    write_csv(resample(m15, "H1"), b)
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()


def test_csv_header_is_canonical(tmp_path):
    m15 = _m15_series(datetime(2026, 1, 1), 12)
    p = tmp_path / "h.csv"
    write_csv(resample(m15, "H1"), p)
    assert p.read_text(encoding="utf-8").splitlines()[0] == CSV_HEADER


# ── weekend gap: no merge, no synthetic bars ────────────────────────────────────────
def test_weekend_gap_no_merge_no_synthetic():
    # Friday 21:00-21:45 (one full hour), then a multi-day jump to Monday 22:00.
    fri = datetime(2026, 1, 2, 21, 0, 0)        # 2026-01-02 is a Friday
    mon = datetime(2026, 1, 5, 22, 0, 0)        # 2026-01-05 is a Monday
    friday = _m15_series(fri, 4)                # hour 21 complete
    monday = _m15_series(mon, 4)                # hour 22 complete (triggers Friday flush)
    h1 = resample(friday + monday, "H1")
    # Friday's 21:00 bucket emits (Monday's first bar triggers it); Monday's is trailing -> dropped.
    assert len(h1) == 1
    assert h1[0].timestamp == datetime(2026, 1, 2, 21, 0, 0)
    # No synthetic buckets were invented for the empty Sat/Sun span.
    assert all(c.timestamp <= datetime(2026, 1, 2, 21, 0, 0) for c in h1)


# ── intra-hour gap: aggregate observed children only ────────────────────────────────
def test_intrahour_gap_aggregates_observed_children_only():
    base = datetime(2026, 1, 1, 0, 0, 0)
    # Hour 00 has only 2 of 4 M15 bars (00:00, 00:45 missing 00:15/00:30), then hour 01 triggers flush.
    c0 = _c(base, 100.0, 101.0, 99.0, 100.5, 5.0)
    c1 = _c(base + timedelta(minutes=45), 100.5, 102.0, 100.0, 101.5, 7.0)
    trigger = _c(base + timedelta(hours=1), 101.5, 101.6, 101.4, 101.5, 1.0)
    h1 = resample([c0, c1, trigger], "H1")
    assert len(h1) == 1
    assert h1[0].volume == pytest.approx(12.0)   # only the 2 observed children, none fabricated
    _assert_ohlc_valid(h1[0], [c0, c1])


# ── volume conservation ─────────────────────────────────────────────────────────────
def test_volume_conserved_excluding_dropped_tail():
    m15 = _m15_series(datetime(2026, 1, 1), 9)   # hours 00,01 complete (8 bars) + 1 trailing bar dropped
    h1 = resample(m15, "H1")
    emitted_vol = sum(c.volume for c in h1)
    # children of the two emitted buckets are exactly m15[0:8]
    assert emitted_vol == pytest.approx(sum(c.volume for c in m15[0:8]))


def test_unsupported_rule_raises():
    with pytest.raises(ValueError):
        resample(_m15_series(datetime(2026, 1, 1), 8), "H2")
