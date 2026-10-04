"""PR-1 BarBuilder: no-lookahead M15 close, extras sidecar, no synthetic bars."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data_ingestion.ohlcv_schema import REQUIRED_OHLCV_COLUMNS
from inout.live_rail.bar_builder import BarBuilder
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.types import ClockBasis, NormalizedTick, VenueName

_EXPERIMENTAL = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "experimental"
    / "spec"
    / "live_rail_tickdb_paper.json"
)


def _cfg() -> LiveRailConfig:
    raw = json.loads(_EXPERIMENTAL.read_text(encoding="utf-8"))
    return LiveRailConfig.from_prod_config(raw["live_rail"])


def _tick(ts: str, last: float, *, bid: float | None = None, ask: float | None = None,
          size: float = 1.0, symbol: str = "XAUUSD") -> NormalizedTick:
    px = last
    return NormalizedTick(
        ts=datetime.fromisoformat(ts),
        symbol=symbol,
        bid=bid if bid is not None else px - 0.05,
        ask=ask if ask is not None else px + 0.05,
        last=last,
        size=size,
        seq=None,
        clock_basis=ClockBasis.BROKER_LOCAL,
        venue=VenueName.TICKDB,
        raw_kind="replay",
    )


def test_same_period_does_not_emit() -> None:
    bb = BarBuilder(_cfg())
    assert bb.on_tick(_tick("2026-01-02T01:00:00+00:00", 2650.0)) is None
    assert bb.on_tick(_tick("2026-01-02T01:05:00+00:00", 2651.0)) is None


def test_period_boundary_emits_prior_bar() -> None:
    bb = BarBuilder(_cfg())
    assert bb.on_tick(_tick("2026-01-02T01:00:00+00:00", 2650.0, size=1.0)) is None
    assert bb.on_tick(_tick("2026-01-02T01:05:00+00:00", 2652.0, size=2.0)) is None
    closed = bb.on_tick(_tick("2026-01-02T01:15:00+00:00", 2649.0, size=1.5))
    assert closed is not None
    c = closed.candle
    assert c.timestamp == datetime.fromisoformat("2026-01-02T01:00:00+00:00")
    assert c.open == pytest.approx(2650.0)
    assert c.high == pytest.approx(2652.0)
    assert c.low == pytest.approx(2650.0)
    assert c.close == pytest.approx(2652.0)
    assert c.volume == pytest.approx(3.0)
    assert closed.n_ticks == 2
    assert closed.period_end == datetime.fromisoformat("2026-01-02T01:15:00+00:00")
    assert set(closed.extras) >= {"mid", "spread_abs", "spread_bps", "bid_at_close", "ask_at_close"}
    candle_fields = {"timestamp", "open", "high", "low", "close", "volume"}
    assert candle_fields == REQUIRED_OHLCV_COLUMNS


def test_gap_does_not_synthesize_bars() -> None:
    bb = BarBuilder(_cfg())
    assert bb.on_tick(_tick("2026-01-02T01:00:00+00:00", 2650.0)) is None
    closed = bb.on_tick(_tick("2026-01-02T01:45:00+00:00", 2660.0))
    assert closed is not None
    assert closed.candle.close == pytest.approx(2650.0)
    assert closed.candle.timestamp == datetime.fromisoformat("2026-01-02T01:00:00+00:00")
    assert closed.n_ticks == 1
    # One emit only — 01:15 and 01:30 were not synthesized.
    assert bb.on_tick(_tick("2026-01-02T02:00:00+00:00", 2670.0)) is not None


def test_time_reverse_fail_closed() -> None:
    bb = BarBuilder(_cfg())
    assert bb.on_tick(_tick("2026-01-02T01:15:00+00:00", 2650.0)) is None
    with pytest.raises(RuntimeError, match="time-reversed"):
        bb.on_tick(_tick("2026-01-02T01:00:00+00:00", 2640.0))


def test_symbol_mismatch_fail_closed() -> None:
    bb = BarBuilder(_cfg())
    with pytest.raises(ValueError, match="symbol"):
        bb.on_tick(_tick("2026-01-02T01:00:00+00:00", 2650.0, symbol="EURUSD"))


def test_no_lookahead_last_bar_not_emitted() -> None:
    bb = BarBuilder(_cfg())
    assert bb.on_tick(_tick("2026-01-02T01:00:00+00:00", 2650.0)) is None
    assert bb.on_tick(_tick("2026-01-02T01:14:00+00:00", 2651.0)) is None
    bb.drop_in_progress()
    assert bb.on_tick(_tick("2026-01-02T01:30:00+00:00", 2660.0)) is None


def test_tick_count_volume_mode() -> None:
    raw = json.loads(_EXPERIMENTAL.read_text(encoding="utf-8"))
    section = dict(raw["live_rail"])
    section["bar_builder"] = dict(section["bar_builder"], volume_mode="tick_count")
    bb = BarBuilder(LiveRailConfig.from_prod_config(section))
    assert bb.on_tick(_tick("2026-01-02T01:00:00+00:00", 2650.0, size=10.0)) is None
    assert bb.on_tick(_tick("2026-01-02T01:01:00+00:00", 2651.0, size=10.0)) is None
    closed = bb.on_tick(_tick("2026-01-02T01:15:00+00:00", 2652.0))
    assert closed is not None
    assert closed.candle.volume == pytest.approx(2.0)


def test_floor_respects_label_offset() -> None:
    """Broker-labeled +00:00 01:00 is period start (F-080), not converted to another zone."""
    bb = BarBuilder(_cfg())
    ts = datetime(2026, 1, 2, 1, 7, 0, tzinfo=timezone.utc)
    assert bb.on_tick(_tick(ts.isoformat(), 2650.0)) is None
    closed = bb.on_tick(_tick("2026-01-02T01:15:00+00:00", 2651.0))
    assert closed is not None
    assert closed.candle.timestamp.hour == 1
    assert closed.candle.timestamp.minute == 0
