"""PR-1 TickDB adapter: replay, SEQ_GAP, clock, naive ts. Zero network."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from data_ingestion.ohlcv_schema import ClockProvenanceError
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.tickdb_adapter import TickDBAdapter
from inout.live_rail.types import ClockBasis, VenueName

_EXPERIMENTAL = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "experimental"
    / "spec"
    / "live_rail_tickdb_paper.json"
)
_SAMPLE = (
    Path(__file__).resolve().parent / "fixtures" / "ticks" / "xauusd_m15_sample.jsonl"
)


def _cfg_for(path: Path, **overrides) -> LiveRailConfig:
    raw = json.loads(_EXPERIMENTAL.read_text(encoding="utf-8"))
    section = dict(raw["live_rail"])
    tickdb = dict(section["tickdb"])
    tickdb["path"] = str(path)
    tickdb["speed_mult"] = 0.0
    tickdb["require_clock_record"] = True
    tickdb.update(overrides.pop("tickdb", {}))
    section["tickdb"] = tickdb
    section.update(overrides)
    return LiveRailConfig.from_prod_config(section)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _collect(adapter: TickDBAdapter) -> list:
    return [t async for t in adapter.ticks()]


def test_tickdb_replays_sample_via_tmp(tmp_path: Path) -> None:
    dest = tmp_path / "ticks.jsonl"
    dest.write_text(_SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    adapter = TickDBAdapter(_cfg_for(dest))
    asyncio.run(adapter.start())
    ticks = asyncio.run(_collect(adapter))
    asyncio.run(adapter.stop())
    assert len(ticks) == 3
    assert ticks[0].symbol == "XAUUSD"
    assert ticks[0].seq == 1
    assert ticks[0].venue is VenueName.TICKDB
    assert ticks[0].clock_basis is ClockBasis.BROKER_LOCAL
    assert ticks[0].ts.tzinfo is not None
    assert ticks[2].last == pytest.approx(2650.55)


def test_tickdb_seq_gap_fail_closed(tmp_path: Path) -> None:
    dest = tmp_path / "gap.jsonl"
    _write_lines(dest, [
        '{"ts":"2026-01-02T01:00:00+00:00","symbol":"XAUUSD","bid":1,"ask":1.1,"last":1.05,"size":1,"seq":1,"clock_basis":"broker_local"}',
        '{"ts":"2026-01-02T01:00:01+00:00","symbol":"XAUUSD","bid":1,"ask":1.1,"last":1.05,"size":1,"seq":3,"clock_basis":"broker_local"}',
    ])
    adapter = TickDBAdapter(_cfg_for(dest))
    asyncio.run(adapter.start())
    with pytest.raises(RuntimeError, match="SEQ_GAP"):
        asyncio.run(_collect(adapter))


def test_tickdb_time_reverse_fail_closed(tmp_path: Path) -> None:
    dest = tmp_path / "rev.jsonl"
    _write_lines(dest, [
        '{"ts":"2026-01-02T01:00:01+00:00","symbol":"XAUUSD","bid":1,"ask":1.1,"last":1.05,"size":1,"seq":1,"clock_basis":"broker_local"}',
        '{"ts":"2026-01-02T01:00:00+00:00","symbol":"XAUUSD","bid":1,"ask":1.1,"last":1.05,"size":1,"seq":2,"clock_basis":"broker_local"}',
    ])
    adapter = TickDBAdapter(_cfg_for(dest))
    asyncio.run(adapter.start())
    with pytest.raises(RuntimeError, match="time-reversed"):
        asyncio.run(_collect(adapter))


def test_tickdb_naive_ts_refused(tmp_path: Path) -> None:
    dest = tmp_path / "naive.jsonl"
    _write_lines(dest, [
        '{"ts":"2026-01-02T01:00:00","symbol":"XAUUSD","bid":1,"ask":1.1,"last":1.05,"size":1,"seq":1,"clock_basis":"broker_local"}',
    ])
    adapter = TickDBAdapter(_cfg_for(dest))
    asyncio.run(adapter.start())
    with pytest.raises(ValueError, match="naive"):
        asyncio.run(_collect(adapter))


def test_tickdb_clock_basis_mismatch(tmp_path: Path) -> None:
    dest = tmp_path / "clk.jsonl"
    _write_lines(dest, [
        '{"ts":"2026-01-02T01:00:00+00:00","symbol":"XAUUSD","bid":1,"ask":1.1,"last":1.05,"size":1,"seq":1,"clock_basis":"utc"}',
    ])
    adapter = TickDBAdapter(_cfg_for(dest))
    asyncio.run(adapter.start())
    with pytest.raises(ClockProvenanceError, match="clock_basis"):
        asyncio.run(_collect(adapter))


def test_tickdb_utc_label_on_xauusd_refused_at_start(tmp_path: Path) -> None:
    dest = tmp_path / "utc.jsonl"
    dest.write_text("{}\n", encoding="utf-8")
    adapter = TickDBAdapter(_cfg_for(dest, clock_basis="utc"))
    with pytest.raises(RuntimeError, match="clock_basis=utc"):
        asyncio.run(adapter.start())


def test_tickdb_missing_file() -> None:
    adapter = TickDBAdapter(_cfg_for(Path("does/not/exist.jsonl"), tickdb={"require_clock_record": False}))
    with pytest.raises(FileNotFoundError):
        asyncio.run(adapter.start())


def test_tickdb_require_clock_on_unreviewed_committed_file() -> None:
    adapter = TickDBAdapter(_cfg_for(_SAMPLE))
    with pytest.raises(ClockProvenanceError):
        asyncio.run(adapter.start())
