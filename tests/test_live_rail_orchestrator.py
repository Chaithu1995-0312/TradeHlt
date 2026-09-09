"""PR-4c: TickDB drain, required feeder, XOR (OM=1, hook send=0)."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config_layer.crt_engine_v2 import Candle
from core.ultron_live_adapter import UltronLiveAdapter
from core.ultron_risk_gate import UltronRiskGate
from engines.live_engine import LiveEngineConfig
from inout.live_rail.bar_builder import BarBuilder
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.factory import build_port
from inout.live_rail.resilience import CircuitBreaker, ReconnectPolicy
from inout.live_rail.types import ClockBasis, ClosedBar, DataVenue, VenueName
from live.order_manager import OrderManager, PaperVenueExecutor
from runtime.live_engine_hook import HookedLiveEngine
from runtime.live_rail_feeder import LiveRailFeeder
from runtime.live_rail_orchestrator import LiveRailContext, LiveRailOrchestrator

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


def _cfg(tick_path: Path, **overrides) -> LiveRailConfig:
    section = _section()
    section["enabled"] = True
    tickdb = dict(section["tickdb"])
    tickdb["path"] = str(tick_path)
    tickdb["speed_mult"] = 0.0
    tickdb["require_clock_record"] = True
    section["tickdb"] = tickdb
    om = dict(section["order_manager"])
    om["enabled"] = True
    section["order_manager"] = om
    section.update(overrides)
    return LiveRailConfig.from_prod_config(section)


def _gate() -> UltronRiskGate:
    g = UltronRiskGate({
        "max_risk_per_trade_pct": 1.0,
        "max_portfolio_risk_pct": 5.0,
        "max_trades_per_day": 10,
        "max_daily_loss_pct": 3.0,
        "min_rr_ratio": 1.5,
        "disabled": False,
    })
    g._kill_switch_tripped = False
    g._load_ks_state = lambda: False  # type: ignore[method-assign]
    return g


class StubHook:
    def __init__(self, *, boom: bool = False, approve: bool = True) -> None:
        self._hook_submit_orders = False
        self.calls: list = []
        self.boom = boom
        self.approve = approve

    def process(self, trade_data, gaussian_model=None, scaler=None, **kwargs):
        self.calls.append(trade_data)
        if self.boom:
            raise KeyError("FEATURE_STORE missing")
        if not self.approve:
            return {"trade_plan": {}, "ultron": {"decision": "reject", "risk_reason": "no"}}
        return {
            "trade_plan": {
                "decision": "execute",
                "symbol": "XAUUSD",
                "direction": 1,
                "entry_price": 2000.0,
                "stop_loss": 1999.0,
                "take_profit_1": 2002.0,
                "execution_id": "e1",
            },
            "ultron": {
                "decision": "approve",
                "final_position_size": 0.1,
                "allowed_risk_pct": 0.5,
            },
        }


def _closed_bar(i: int) -> ClosedBar:
    ts = datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i)
    candle = Candle(
        timestamp=ts, open=2000.0, high=2001.0, low=1999.0, close=2000.5,
        volume=1.0, index=i,
    )
    return ClosedBar(
        candle=candle, extras={}, symbol="XAUUSD",
        clock_basis=ClockBasis.BROKER_LOCAL, venue=VenueName.TICKDB,
        n_ticks=1, period_start=ts, period_end=ts + timedelta(minutes=15),
    )


def _ctx(cfg: LiveRailConfig, hook, tmp_path: Path, port=None) -> LiveRailContext:
    ultron = _gate()
    return LiveRailContext(
        cfg=cfg,
        port=port,
        bars=BarBuilder(cfg),
        risk=UltronLiveAdapter(ultron, paper_balance=cfg.portfolio.paper_balance),
        orders=OrderManager(
            PaperVenueExecutor(),
            dry_run=True,
            fill_timeout_s=5.0,
            allow_partial=False,
        ),
        hook=hook,
        breaker=CircuitBreaker(fail_count_disable=10),
        ultron=ultron,
        feeder=LiveRailFeeder(symbol=cfg.symbol, timeframe=cfg.timeframe),
    )


def _write_ticks(path: Path, n_periods: int) -> None:
    lines = []
    base = datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc)
    seq = 1
    for i in range(n_periods):
        ts = base + timedelta(minutes=15 * i)
        lines.append(json.dumps({
            "ts": ts.isoformat(),
            "symbol": "XAUUSD",
            "bid": 2000.0,
            "ask": 2000.1,
            "last": 2000.05,
            "size": 1.0,
            "seq": seq,
            "clock_basis": "broker_local",
            "raw_kind": "replay",
        }))
        seq += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_from_config_refuses_without_env(tmp_path: Path, monkeypatch) -> None:
    ticks = tmp_path / "t.jsonl"
    ticks.write_text("{}\n", encoding="utf-8")
    cfg = _cfg(ticks)
    monkeypatch.delenv("LIVE_ENGINE_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="LIVE_ENGINE_ENABLED"):
        LiveRailOrchestrator.from_config(cfg)


def test_from_config_refuses_when_disabled(tmp_path: Path, monkeypatch) -> None:
    ticks = tmp_path / "t.jsonl"
    ticks.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("LIVE_ENGINE_ENABLED", "1")
    cfg = _cfg(ticks, enabled=False)
    with pytest.raises(RuntimeError, match="enabled=false"):
        LiveRailOrchestrator.from_config(cfg)


def test_factory_binance_returns_adapter(tmp_path: Path) -> None:
    ticks = tmp_path / "t.jsonl"
    ticks.write_text("{}\n", encoding="utf-8")
    cfg = _cfg(ticks, data_venue="binance", symbol="BTCUSDT", clock_basis="utc")
    from inout.live_rail.binance_ws_adapter import BinanceWsAdapter
    port = build_port(cfg, CircuitBreaker(10), ReconnectPolicy(1.0, 2.0, 3))
    assert isinstance(port, BinanceWsAdapter)


def test_context_requires_feeder() -> None:
    with pytest.raises(TypeError):
        LiveRailContext(  # type: ignore[call-arg]
            cfg=None, port=None, bars=None, risk=None, orders=None,
            hook=None, breaker=None, ultron=None,
        )


def test_drain_flushes_closed_bars(tmp_path: Path) -> None:
    ticks = tmp_path / "t.jsonl"
    # 01:00, 01:15, 01:30 → two closed bars; 01:30 in-progress dropped.
    _write_ticks(ticks, 3)
    cfg = _cfg(ticks)
    hook = StubHook()
    ctx = _ctx(cfg, hook, tmp_path, port=None)
    from inout.live_rail.tickdb_adapter import TickDBAdapter
    ctx.port = TickDBAdapter(cfg)
    orch = LiveRailOrchestrator(ctx, report_path=tmp_path / "live_rail.jsonl")
    rc = asyncio.run(orch.run_until_exhausted())
    assert rc == 0
    assert orch.closed_bars_seen == 2
    assert hook.calls == []  # warmup 78; 2 bars not ready


def test_warmup_skips_process(tmp_path: Path) -> None:
    ticks = tmp_path / "t.jsonl"
    _write_ticks(ticks, 1)
    cfg = _cfg(ticks)
    hook = StubHook()
    ctx = _ctx(cfg, hook, tmp_path)
    orch = LiveRailOrchestrator(ctx, report_path=tmp_path / "live_rail.jsonl")

    async def _run() -> None:
        await orch.ingest_closed_bar(_closed_bar(0))
        await orch.ingest_closed_bar(_closed_bar(1))
        await orch.run_until_bar_queue_empty()

    asyncio.run(_run())
    assert orch.closed_bars_seen == 2
    assert orch.process_calls == 0
    assert hook.calls == []


def test_ready_raise_is_feeder_reject_and_drain_completes(tmp_path: Path) -> None:
    ticks = tmp_path / "t.jsonl"
    _write_ticks(ticks, 3)
    cfg = _cfg(ticks)
    hook = StubHook()
    ctx = _ctx(cfg, hook, tmp_path)
    ctx.feeder.ready = lambda: (_ for _ in ()).throw(AssertionError("swing identical"))  # type: ignore[method-assign]
    from inout.live_rail.tickdb_adapter import TickDBAdapter
    ctx.port = TickDBAdapter(cfg)
    orch = LiveRailOrchestrator(ctx, report_path=tmp_path / "live_rail.jsonl")
    rc = asyncio.run(orch.run_until_exhausted())
    assert rc == 0
    assert orch.closed_bars_seen == 2
    assert orch.process_calls == 0
    # The feeder failed, so the hook was never even attempted.
    assert orch.process_attempts == 0
    log = (tmp_path / "live_rail.jsonl").read_text(encoding="utf-8")
    assert "FEEDER_REJECT" in log
    assert "ENGINE_ERROR" not in log, "a feeder failure must not be reported as an engine fault"
    assert "swing identical" in log


def test_hook_raise_is_engine_error_and_attempt_is_counted(tmp_path: Path) -> None:
    ticks = tmp_path / "t.jsonl"
    _write_ticks(ticks, 1)
    cfg = _cfg(ticks)
    hook = StubHook(boom=True)
    ctx = _ctx(cfg, hook, tmp_path)
    # Pretend feeder already warm.
    ctx.feeder.ready = lambda: True  # type: ignore[method-assign]
    ctx.feeder.as_trade_data = lambda bar, ps: {  # type: ignore[method-assign]
        "symbol": "XAUUSD", "timeframe": "M15", "timestamp": bar.candle.timestamp,
        "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1,
        "account_balance": 10000, "total_open_risk_pct": 0, "trades_today": 0,
        "daily_loss_pct": 0, "open_positions": 0, "positions": {},
    }
    orch = LiveRailOrchestrator(ctx, report_path=tmp_path / "live_rail.jsonl")

    async def _run() -> None:
        await orch.ingest_closed_bar(_closed_bar(0))
        await orch.run_until_bar_queue_empty()

    asyncio.run(_run())
    log = (tmp_path / "live_rail.jsonl").read_text(encoding="utf-8")
    rec = json.loads(log.strip().splitlines()[-1])
    # The distinction Phase 0 exists for: hook.process WAS called and raised.
    # Reporting this as FEATURE_REJECT is what made a real call look like a
    # feature-construction failure and left process_calls=0 unexplained.
    assert rec["kind"] == "ENGINE_ERROR"
    assert "FEEDER_REJECT" not in log
    assert rec["error_type"] == "KeyError"
    assert rec["raised_in"], "engine errors must name where they were raised"
    assert orch.process_attempts == 1, "the attempt happened even though it raised"
    assert orch.process_calls == 0, "process_calls counts returns, not attempts"


def test_xor_om_fill_hook_send_zero(tmp_path: Path) -> None:
    ticks = tmp_path / "t.jsonl"
    _write_ticks(ticks, 1)
    cfg = _cfg(ticks)
    assert cfg.hook_submit_orders is False
    assert cfg.order_manager.enabled is True
    hook = StubHook(approve=True)
    real_hook = HookedLiveEngine(LiveEngineConfig(enabled=False), hook_submit_orders=False)
    ctx = _ctx(cfg, hook, tmp_path)
    orch = LiveRailOrchestrator(ctx, report_path=tmp_path / "live_rail.jsonl")
    ctx.feeder.ready = lambda: True  # type: ignore[method-assign]
    ctx.feeder.push = lambda bar: None  # type: ignore[method-assign]
    ctx.feeder.as_trade_data = lambda bar, ps: {  # type: ignore[method-assign]
        "symbol": "XAUUSD", "timeframe": "M15", "timestamp": bar.candle.timestamp,
        "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1,
        "account_balance": 10000, "total_open_risk_pct": 0, "trades_today": 0,
        "daily_loss_pct": 0, "open_positions": 0, "positions": {},
    }
    mt5 = MagicMock()
    with patch("runtime.live_engine_hook._get_mt5", return_value=mt5):
        async def _run() -> None:
            await orch.ingest_closed_bar(_closed_bar(0))
            await orch.run_until_bar_queue_empty()
        asyncio.run(_run())
        # Stub process does not call _emit_live_io; also fire the real hook emit path.
        real_hook._emit_live_io(
            ultron_result={"decision": "approve", "final_position_size": 0.1},
            ks_blocked=False,
            trade_plan={"trade_intent": "BREAKOUT", "stop_loss": 1999.0, "take_profit_1": 2002.0},
            pair="XAUUSD", timeframe="M15", close=2000.0, confidence=0.5, orch_result=None,
        )
    assert orch.process_calls == 1
    log = (tmp_path / "live_rail.jsonl").read_text(encoding="utf-8")
    assert '"kind": "FILL"' in log
    assert mt5.send_order.call_count == 0
    assert ctx.orders._working  # paper fill recorded
