"""F-073 repair: missing caller of HookedLiveEngine.process. Paper TickDB only."""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config_layer.production_config import get_prod_section
from core.ultron_live_adapter import UltronLiveAdapter
from core.ultron_risk_gate import UltronRiskGate
from engines.live_engine import LiveEngineConfig
from inout.live_rail.bar_builder import BarBuilder
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.factory import build_port
from inout.live_rail.resilience import CircuitBreaker, ReconnectPolicy
from inout.live_rail.types import ClosedBar, DataVenue, MarketDataPort, OrderVenue
from live.order_manager import OrderManager, PaperVenueExecutor
from runtime.live_engine_hook import HookedLiveEngine
from runtime.live_rail_feeder import LiveRailFeeder
from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")


def _reject_record(kind: str, exc: BaseException) -> dict[str, Any]:
    """Audit record for a caught exception, naming where it was actually raised.

    ``raised_in`` is the deepest traceback frame, so an engine-side contract break
    reports the module that broke it rather than the orchestrator that caught it.
    """
    tb = exc.__traceback__
    raised_in = ""
    while tb is not None:
        raised_in = f"{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}"
        tb = tb.tb_next
    return {
        "kind": kind,
        "error": str(exc),
        "error_type": type(exc).__name__,
        "raised_in": raised_in,
    }

_REPORT_PATH = Path("logs") / "live_rail.jsonl"


@dataclass
class LiveRailContext:
    """DI for the orchestrator. Not the documented-but-absent LiveEngineContext."""

    cfg: LiveRailConfig
    port: Optional[MarketDataPort]
    bars: BarBuilder
    risk: UltronLiveAdapter
    orders: OrderManager
    hook: HookedLiveEngine
    breaker: CircuitBreaker
    ultron: UltronRiskGate
    feeder: LiveRailFeeder


class LiveRailOrchestrator:
    """Missing F-073 caller. Does not replace EngineRunner. Does not size."""

    def __init__(self, ctx: LiveRailContext, *, report_path: Path | None = None) -> None:
        if ctx.feeder is None:
            raise TypeError("LiveRailContext.feeder is required (no hasattr fallback)")
        self._ctx = ctx
        self._tick_q: asyncio.Queue = asyncio.Queue(maxsize=ctx.cfg.queues.tick_maxsize)
        self._bar_q: asyncio.Queue = asyncio.Queue(maxsize=ctx.cfg.queues.bar_maxsize)
        self._stop = asyncio.Event()
        self._report_path = Path(report_path) if report_path is not None else _REPORT_PATH
        self.closed_bars_seen = 0
        # process_attempts increments BEFORE hook.process(); process_calls only on return.
        # Keeping them separate is what distinguishes "never reached" from "raised inside".
        self.process_attempts = 0
        self.process_calls = 0

    @classmethod
    def from_config(
        cls,
        cfg: LiveRailConfig,
        *,
        report_path: Path | None = None,
        port: Optional[MarketDataPort] = None,
    ) -> "LiveRailOrchestrator":
        """``port`` overrides the configured venue (file-backed replay ports only).

        It exists so a certification run can substitute a historical-corpus port
        without a caller reaching into the private context.
        """
        cfg.assert_safe_to_start()
        if not cfg.enabled:
            raise RuntimeError("live_rail.enabled=false — refuse to start")
        if os.environ.get("LIVE_ENGINE_ENABLED", "0") != "1":
            raise RuntimeError(
                "LIVE_ENGINE_ENABLED is not '1' — refuse to start "
                "(fail-closed; matches LiveEngineConfig.from_env)"
            )
        policy = ReconnectPolicy(
            base_delay_s=cfg.reconnect.base_delay_s,
            max_delay_s=cfg.reconnect.max_delay_s,
            max_attempts=cfg.reconnect.max_attempts,
        )
        breaker = CircuitBreaker(fail_count_disable=cfg.reconnect.fail_count_disable)
        if port is None:
            port = build_port(cfg, breaker, policy)
        ultron = UltronRiskGate(get_prod_section("ultron_risk_gate"))
        risk = UltronLiveAdapter(ultron, paper_balance=cfg.portfolio.paper_balance)
        if cfg.order_venue is not OrderVenue.PAPER:
            raise RuntimeError("factory refused non-paper order_venue")
        orders = OrderManager(
            PaperVenueExecutor(),
            dry_run=cfg.dry_run,
            fill_timeout_s=cfg.order_manager.fill_timeout_s,
            allow_partial=cfg.order_manager.allow_partial,
            allow_lot_clamp=cfg.order_manager.allow_lot_clamp,
        )
        hook = HookedLiveEngine(
            LiveEngineConfig(enabled=False),
            hook_submit_orders=cfg.hook_submit_orders,
            ultron_gate=ultron,
        )
        feeder = LiveRailFeeder(symbol=cfg.symbol, timeframe=cfg.timeframe)
        ctx = LiveRailContext(
            cfg=cfg,
            port=port,
            bars=BarBuilder(cfg),
            risk=risk,
            orders=orders,
            hook=hook,
            breaker=breaker,
            ultron=ultron,
            feeder=feeder,
        )
        return cls(ctx, report_path=report_path)

    @classmethod
    def from_prod_config(cls) -> "LiveRailOrchestrator":
        return cls.from_config(LiveRailConfig.from_prod_config())

    async def ingest_closed_bar(self, bar: ClosedBar) -> None:
        bar.validate()
        await self._bar_q.put(bar)

    async def run_until_exhausted(self) -> int:
        if self._ctx.port is None:
            raise RuntimeError("run_until_exhausted requires a tick port")
        await self._ctx.port.start()
        try:
            t_pump = asyncio.create_task(self._pump_ticks())
            t_bars = asyncio.create_task(self._pump_bars())
            t_cons = asyncio.create_task(self._consume_bars())
            await t_pump
            await self._tick_q.join()
            t_bars.cancel()
            try:
                await t_bars
            except asyncio.CancelledError:
                pass
            await self._bar_q.join()
            t_cons.cancel()
            try:
                await t_cons
            except asyncio.CancelledError:
                pass
            return 0
        finally:
            await self._ctx.port.stop()

    async def run_bars(self, bars) -> int:
        """Arm A: inject already-closed bars. No tick port, no BarBuilder.

        The consumer starts FIRST so ``ingest_closed_bar`` back-pressures on the
        queue bound instead of dead-locking on a corpus larger than ``bar_maxsize``.
        """
        t_cons = asyncio.create_task(self._consume_bars())
        try:
            for bar in bars:
                await self.ingest_closed_bar(bar)
            await self._bar_q.join()
        finally:
            t_cons.cancel()
            try:
                await t_cons
            except asyncio.CancelledError:
                pass
        return 0

    async def run_until_bar_queue_empty(self) -> int:
        """Alternative B helper: consume ingest_closed_bar items then stop."""
        t_cons = asyncio.create_task(self._consume_bars())
        await self._bar_q.join()
        t_cons.cancel()
        try:
            await t_cons
        except asyncio.CancelledError:
            pass
        return 0

    async def _pump_ticks(self) -> None:
        assert self._ctx.port is not None
        async for tick in self._ctx.port.ticks():
            if self._stop.is_set() or self._ctx.breaker.is_open():
                return
            await self._tick_q.put(tick)

    async def _pump_bars(self) -> None:
        try:
            while not self._stop.is_set():
                tick = await self._tick_q.get()
                try:
                    closed = self._ctx.bars.on_tick(tick)
                    self._ctx.risk.mark_to_market(tick.symbol, tick.last)
                    if closed is not None:
                        await self._bar_q.put(closed)
                finally:
                    self._tick_q.task_done()
        except asyncio.CancelledError:
            self._ctx.bars.drop_in_progress()
            raise

    async def _consume_bars(self) -> None:
        try:
            while not self._stop.is_set():
                bar: ClosedBar = await self._bar_q.get()
                try:
                    await self._on_closed_bar(bar)
                finally:
                    self._bar_q.task_done()
        except asyncio.CancelledError:
            raise

    async def _on_closed_bar(self, bar: ClosedBar) -> None:
        cfg = self._ctx.cfg
        self.closed_bars_seen += 1
        feeder = self._ctx.feeder
        feeder.push(bar)
        # ready() runs FeaturePipeline — a raise here must NOT kill _consume_bars
        # (that left bar_q.join() waiting forever on the paper TickDB drain).
        try:
            is_ready = feeder.ready()
        except Exception as exc:
            self._audit(_reject_record("FEEDER_REJECT", exc))
            return
        if not is_ready:
            return
        pre = self._ctx.risk.preflight(bar.symbol)
        if pre["decision"] == "reject":
            self._audit({"kind": "PREFLIGHT_REJECT", "reason": pre["risk_reason"]})
            return
        trade_data = feeder.as_trade_data(bar, self._ctx.risk.state())
        self.process_attempts += 1
        try:
            result = self._ctx.hook.process(
                trade_data, gaussian_model=None, scaler=None,
                candle_idx=int(bar.candle.index), timeframe=cfg.timeframe,
            )
            self.process_calls += 1
        except Exception as exc:
            # NOT a feeder failure: as_trade_data already passed its 48-key check above.
            # Collapsing both into one kind is what made an in-engine raise look like a
            # feature-construction failure.
            self._audit(_reject_record("ENGINE_ERROR", exc))
            return
        ultron = result.get("ultron") or {}
        decision = str(ultron.get("decision", "")).lower()
        plan = result.get("trade_plan") or {}
        if (
            decision == "approve"
            and cfg.order_manager.enabled
            and not cfg.hook_submit_orders
            and cfg.order_venue is OrderVenue.PAPER
        ):
            if not cfg.dry_run and not cfg.auto_execute:
                self._audit({"kind": "HUMAN_GATE", "execution_id": plan.get("execution_id")})
                return
            fill = await asyncio.to_thread(self._ctx.orders.submit, plan, ultron)
            rec = {"kind": "FILL"}
            rec.update(fill.__dict__)
            self._audit(rec)
            if fill.status == "FILLED":
                risk_pct = float(ultron.get("allowed_risk_pct", 0.0))
                pos = self._ctx.orders.to_position(plan, fill, risk_pct)
                self._ctx.risk.register_fill(pos, risk_pct)
        else:
            self._audit({
                "kind": "NO_ORDER",
                "decision": decision,
                "reason": ultron.get("risk_reason"),
            })

    def _audit(self, rec: dict[str, Any]) -> None:
        rec.setdefault("ts", datetime.now(timezone.utc).isoformat())
        self._report_path.parent.mkdir(parents=True, exist_ok=True)
        with self._report_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")


def summarize_audit(report_path: Path) -> dict[str, int]:
    """Tally audit records by kind. Reporting only -- no decision reads this."""
    counts: dict[str, int] = {}
    if not report_path.is_file():
        return counts
    with report_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            kind = str(json.loads(line).get("kind", "UNKNOWN"))
            counts[kind] = counts.get(kind, 0) + 1
    return counts
