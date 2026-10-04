"""Layer-5 paper order I/O. Size is Ultron final_position_size only."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, runtime_checkable

from config_layer.strict_config import missing_keys, missing_reason
from core.ultron_live_adapter import LivePosition
from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")

#: Per-trade values this module reads from the Ultron result. Absence is not a
#: default: the trade is REJECTED with the keys named (EPIC-84 trade-time rule).
_ULTRON_KEYS = ("decision", "final_position_size")


@dataclass(frozen=True)
class FillReport:
    execution_id: str
    symbol: str
    side: str
    requested_qty: float
    filled_qty: float
    avg_price: float
    ticket: int
    status: str
    reason: str
    ts: datetime


@runtime_checkable
class VenueExecutor(Protocol):
    def send(
        self, *, symbol: str, side: str, qty: float, sl: float, tp: float, comment: str
    ) -> Optional[int]: ...
    def close(self, ticket: int, symbol: str, qty: float) -> bool: ...


class PaperVenueExecutor:
    """Deterministic full fill. TickDB / dry_run path."""

    def send(self, *, symbol: str, side: str, qty: float, sl: float, tp: float, comment: str) -> Optional[int]:
        logger.info(
            "PaperVenue: FILL %s %s qty=%.6f sl=%.5f tp=%.5f %s",
            side, symbol, qty, sl, tp, comment,
        )
        return -1

    def close(self, ticket: int, symbol: str, qty: float) -> bool:
        logger.info("PaperVenue: CLOSE ticket=%s %s qty=%.6f", ticket, symbol, qty)
        return True


class OrderManager:
    """Submits Ultron-approved size. Does not compute ATR size."""

    def __init__(
        self,
        executor: VenueExecutor,
        *,
        dry_run: bool,
        fill_timeout_s: float,
        allow_partial: bool,
        allow_lot_clamp: bool = False,
    ) -> None:
        self._ex = executor
        self._dry_run = dry_run
        self._timeout = fill_timeout_s
        self._allow_partial = allow_partial
        self._allow_lot_clamp = allow_lot_clamp
        self._working: dict[str, FillReport] = {}

    def submit(self, trade_plan: dict[str, Any], ultron_result: dict[str, Any]) -> FillReport:
        # EPIC-84 trade-time rule: a missing per-trade value REJECTS this trade with
        # the keys named; it never takes a code literal. The engine keeps running.
        missing = missing_keys(ultron_result, _ULTRON_KEYS)
        if missing:
            return self._reject(trade_plan, missing_reason("ultron_result", missing))
        if str(ultron_result["decision"]).lower() != "approve":
            return self._reject(trade_plan, "ultron_not_approved")
        raw_size = ultron_result["final_position_size"]
        # None is a declared value ("no size approved") — it is not a default.
        qty = 0.0 if raw_size is None else float(raw_size)
        if qty <= 0:
            return self._reject(trade_plan, "size_not_approved")
        if "execution_id" not in trade_plan:
            return self._reject(trade_plan, missing_reason("trade_plan", ["execution_id"]))
        sl = float(trade_plan["stop_loss"])
        tp = float(trade_plan["take_profit_1"])
        if sl == 0.0 or tp == 0.0:
            return self._reject(trade_plan, "MISSING_SL_TP")
        direction = int(trade_plan["direction"])
        if direction not in (1, -1):
            return self._reject(trade_plan, "direction_none")
        side = "BUY" if direction == 1 else "SELL"
        symbol = str(trade_plan["symbol"])
        t0 = time.monotonic()
        ticket = self._ex.send(
            symbol=symbol, side=side, qty=qty, sl=sl, tp=tp,
            comment=str(trade_plan["execution_id"]),
        )
        elapsed = time.monotonic() - t0
        if ticket is None:
            return self._reject(trade_plan, "venue_reject")
        if elapsed > self._timeout:
            logger.error("OrderManager: venue timeout %.2fs — fail-closed", elapsed)
            return self._reject(trade_plan, "venue_timeout")
        report = FillReport(
            execution_id=str(trade_plan["execution_id"]),
            symbol=symbol,
            side=side,
            requested_qty=qty,
            filled_qty=qty,
            avg_price=float(trade_plan["entry_price"]),
            ticket=int(ticket),
            status="FILLED",
            reason="ok",
            ts=datetime.now(timezone.utc),
        )
        self._working[report.execution_id] = report
        return report

    def to_position(
        self, trade_plan: dict[str, Any], fill: FillReport, risk_pct: float
    ) -> LivePosition:
        return LivePosition(
            symbol=fill.symbol,
            direction=int(trade_plan["direction"]),
            qty=fill.filled_qty,
            entry=fill.avg_price,
            stop_loss=float(trade_plan["stop_loss"]),
            take_profit_1=float(trade_plan["take_profit_1"]),
            risk_pct=risk_pct,
            ticket=fill.ticket,
            opened_at=fill.ts,
        )

    def _reject(self, trade_plan: dict[str, Any], reason: str) -> FillReport:
        """REJECT shape. When the payload itself is missing the identity fields (that is
        the condition being reported), they are echoed as empty — never substituted by a
        placeholder, so the report cannot be mistaken for a known trade."""
        return FillReport(
            execution_id=str(trade_plan["execution_id"]) if "execution_id" in trade_plan else "",
            symbol=str(trade_plan["symbol"]) if "symbol" in trade_plan else "",
            side="",
            requested_qty=0.0,
            filled_qty=0.0,
            avg_price=0.0,
            ticket=0,
            status="REJECTED",
            reason=reason,
            ts=datetime.now(timezone.utc),
        )
