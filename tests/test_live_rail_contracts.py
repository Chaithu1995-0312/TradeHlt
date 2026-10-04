"""PR-1 contracts: types, LiveRailConfig _require, XOR, breaker, LongPort stub."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from inout.live_rail.config import LiveRailConfig
from inout.live_rail.longport_adapter import LongPortAdapter
from inout.live_rail.resilience import CircuitBreaker, ReconnectPolicy
from inout.live_rail.types import ClockBasis, DataVenue, NormalizedTick, OrderVenue, VenueName

_EXPERIMENTAL = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "experimental"
    / "spec"
    / "live_rail_tickdb_paper.json"
)


def _section(**overrides) -> dict:
    raw = json.loads(_EXPERIMENTAL.read_text(encoding="utf-8"))
    section = dict(raw["live_rail"])
    section.update(overrides)
    return section


def test_experimental_example_loads() -> None:
    cfg = LiveRailConfig.from_prod_config(_section())
    assert cfg.timeframe_seconds == 900
    assert cfg.data_venue is DataVenue.TICKDB
    assert cfg.order_venue is OrderVenue.PAPER
    assert cfg.dry_run is True
    assert cfg.order_manager.enabled is False
    cfg.assert_safe_to_start()


def test_missing_key_is_require_not_silent_default() -> None:
    section = _section()
    del section["symbol"]
    with pytest.raises(KeyError, match="symbol"):
        LiveRailConfig.from_prod_config(section)


def test_timeframe_seconds_must_not_be_declared_on_bar_builder() -> None:
    section = _section()
    section["bar_builder"] = dict(section["bar_builder"], timeframe_seconds=900)
    with pytest.raises(KeyError, match="timeframe_seconds"):
        LiveRailConfig.from_prod_config(section)


def test_emit_incomplete_on_stop_must_be_false() -> None:
    section = _section()
    section["bar_builder"] = dict(section["bar_builder"], emit_incomplete_on_stop=True)
    with pytest.raises(ValueError, match="emit_incomplete_on_stop"):
        LiveRailConfig.from_prod_config(section)


def test_report_maxsize_forbidden() -> None:
    section = _section()
    section["queues"] = dict(section["queues"], report_maxsize=8)
    with pytest.raises(KeyError, match="report_maxsize"):
        LiveRailConfig.from_prod_config(section)


def test_missing_section_fail_fast() -> None:
    with pytest.raises(RuntimeError, match="live_rail section missing"):
        LiveRailConfig.from_prod_config({})


def test_xor_hook_and_order_manager() -> None:
    cfg = LiveRailConfig.from_prod_config(
        _section(hook_submit_orders=True, order_manager={
            **_section()["order_manager"], "enabled": True,
        })
    )
    with pytest.raises(RuntimeError, match="XOR"):
        cfg.assert_safe_to_start()


def test_order_venue_mt5_refused() -> None:
    cfg = LiveRailConfig.from_prod_config(_section(order_venue="mt5"))
    with pytest.raises(RuntimeError, match="factory-unreachable"):
        cfg.assert_safe_to_start()


def test_binance_xauusd_refused() -> None:
    cfg = LiveRailConfig.from_prod_config(_section(data_venue="binance"))
    with pytest.raises(RuntimeError, match="XAUUSD"):
        cfg.assert_safe_to_start()


def test_longport_venue_refused() -> None:
    cfg = LiveRailConfig.from_prod_config(_section(data_venue="longport"))
    with pytest.raises(RuntimeError, match="LongPort"):
        cfg.assert_safe_to_start()


def test_live_auto_execute_refused() -> None:
    cfg = LiveRailConfig.from_prod_config(_section(dry_run=False, auto_execute=True))
    with pytest.raises(RuntimeError, match="auto-execute"):
        cfg.assert_safe_to_start()


def test_account_balance_source_must_be_paper() -> None:
    cfg = LiveRailConfig.from_prod_config(_section(account_balance_source="broker"))
    with pytest.raises(RuntimeError, match="paper"):
        cfg.assert_safe_to_start()


def test_normalized_tick_refuses_naive_ts() -> None:
    tick = NormalizedTick(
        ts=datetime(2026, 1, 2, 1, 0, 0),
        symbol="XAUUSD",
        bid=1.0,
        ask=1.1,
        last=1.05,
        size=1.0,
        seq=1,
        clock_basis=ClockBasis.BROKER_LOCAL,
        venue=VenueName.TICKDB,
        raw_kind="replay",
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        tick.validate()


def test_normalized_tick_refuses_crossed_book() -> None:
    tick = NormalizedTick(
        ts=datetime(2026, 1, 2, 1, 0, 0, tzinfo=timezone.utc),
        symbol="XAUUSD",
        bid=2.0,
        ask=1.0,
        last=1.5,
        size=1.0,
        seq=1,
        clock_basis=ClockBasis.BROKER_LOCAL,
        venue=VenueName.TICKDB,
        raw_kind="replay",
    )
    with pytest.raises(ValueError, match="crossed"):
        tick.validate()


def test_normalized_tick_spread_bps() -> None:
    tick = NormalizedTick(
        ts=datetime(2026, 1, 2, 1, 0, 0, tzinfo=timezone.utc),
        symbol="XAUUSD",
        bid=100.0,
        ask=100.1,
        last=100.05,
        size=1.0,
        seq=1,
        clock_basis=ClockBasis.BROKER_LOCAL,
        venue=VenueName.TICKDB,
        raw_kind="replay",
    )
    tick.validate()
    assert tick.spread_abs() == pytest.approx(0.1)
    assert tick.spread_bps() == pytest.approx(10_000.0 * 0.1 / 100.05)


def test_circuit_breaker_fail_closed() -> None:
    br = CircuitBreaker(fail_count_disable=2)
    assert br.is_open() is False
    br.record_failure()
    br.record_failure()
    assert br.is_open() is False
    br.record_failure()
    assert br.is_open() is True
    br.record_success()
    assert br.is_open() is False


def test_reconnect_policy_exhausts() -> None:
    import asyncio

    policy = ReconnectPolicy(base_delay_s=0.0, max_delay_s=0.0, max_attempts=2)

    async def _run() -> None:
        await policy.sleep(0)
        await policy.sleep(1)
        with pytest.raises(RuntimeError, match="fail-closed"):
            await policy.sleep(2)

    asyncio.run(_run())


def test_longport_stub_refuses_start() -> None:
    import asyncio

    adapter = LongPortAdapter()
    assert adapter.name is VenueName.LONGPORT
    with pytest.raises(NotImplementedError, match="stub"):
        asyncio.run(adapter.start())
