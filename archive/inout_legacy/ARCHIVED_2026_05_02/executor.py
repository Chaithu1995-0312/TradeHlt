"""
inout/executor.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — Broker Execution Layer

Translates ActionInstructions from the state machine into
broker API calls (Binance Futures in Phase 2).

Phase 1 (NOW):
    - STUB implementation: logs all orders, returns simulated fills
    - Full interface defined so Phase 2 can drop in real Binance client
    - Slippage estimation built in for realistic P&L accounting

Phase 2 (LATER):
    - Replace _place_market_order() with python-binance or ccxt call
    - Replace _update_sl_order() with Binance STOP_MARKET order API
    - Maintain same interface — zero changes to controller/state machine

Design principles
-----------------
    - Executor owns NO state. It fires orders and returns fill results.
    - All results returned as dict — caller (controller) writes to DB.
    - Failure never raises — returns {"status": "error", "reason": str}
    - Every call logged to audit trail via controller
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .config import INOUTConfig
from .state_machine import ActionInstruction, ActionType

logger = logging.getLogger("INOUT.EXECUTOR")


# ── Fill result ───────────────────────────────────────────────────────────────

@dataclass
class FillResult:
    """
    Returned by every executor method.
    Controller uses this to update DB and state.
    """
    success: bool
    order_id: str
    fill_price: float
    fill_qty: float
    status: str             # "filled" | "partial" | "rejected" | "error"
    reason: str = ""
    raw_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "fill_price": self.fill_price,
            "fill_qty": self.fill_qty,
            "status": self.status,
            "reason": self.reason,
        }


# ── Executor ──────────────────────────────────────────────────────────────────

class INOUTExecutor:
    """
    Broker execution interface for INOUT strategy.

    Phase 1: stub implementation (dry-run mode).
    Phase 2: replace _place_market_order() / _update_sl_order()
             with real Binance Futures API calls.

    Usage (called only by INOUTController — never by scanner or state machine):
        executor = INOUTExecutor(cfg)

        # On signal approval:
        fill = executor.open_position(symbol, direction, qty, sl, tp1, tp2)

        # On Tier 1 hit:
        fill = executor.exit_partial(symbol, direction, qty, reason="TP1")
        executor.update_stop_loss(symbol, direction, new_sl)

        # On runner trail update:
        executor.update_stop_loss(symbol, direction, new_trail_sl)

        # On full exit:
        fill = executor.exit_full(symbol, direction, qty, reason="TIMEOUT")
    """

    def __init__(self, cfg: INOUTConfig) -> None:
        self._cfg = cfg
        self._dry_run = True   # Phase 1: always dry-run
        # Phase 2: set self._dry_run = False, inject Binance client
        # self._client = BinanceClient(api_key=..., secret=...)

    # ── Entry ─────────────────────────────────────────────────────────────────

    def open_position(
        self,
        symbol: str,
        direction: str,
        qty: float,
        stop_loss: float,
        tp1_price: float,
        tp2_price: float,
        entry_hint: float | None = None,
    ) -> FillResult:
        """
        Place market entry order with initial SL.
        TP prices stored in DB, not as exchange orders (to allow partial exits).

        Phase 2: Place MARKET order + STOP_MARKET protective SL.
        """
        logger.info(
            "INOUT.EXEC: OPEN %s %s qty=%.6f entry~%.5f sl=%.5f tp1=%.5f tp2=%.5f",
            symbol, direction, qty, entry_hint or 0, stop_loss, tp1_price, tp2_price,
        )

        if self._dry_run:
            # Simulate market fill with 0.03% slippage
            slippage = 0.0003
            fill_price = entry_hint or 0.0
            if fill_price > 0:
                fill_price *= (1 + slippage) if direction == "LONG" else (1 - slippage)
            return FillResult(
                success=True,
                order_id=_gen_order_id("OPEN"),
                fill_price=fill_price,
                fill_qty=qty,
                status="filled",
                reason="dry_run",
            )

        # ── Phase 2: real Binance execution (stub) ─────────────────────────────
        # side = "BUY" if direction == "LONG" else "SELL"
        # response = self._client.futures_create_order(
        #     symbol=symbol, side=side, type="MARKET", quantity=qty
        # )
        # fill_price = float(response["avgPrice"])
        # self._place_sl_order(symbol, direction, qty, stop_loss)
        # return FillResult(success=True, order_id=response["orderId"], ...)
        raise NotImplementedError("Phase 2: implement Binance execution")

    # ── Partial exit ──────────────────────────────────────────────────────────

    def exit_partial(
        self,
        symbol: str,
        direction: str,
        qty: float,
        reason: str,
        target_price: float | None = None,
    ) -> FillResult:
        """
        Exit a fraction of the position at market.
        Called on Tier 1 or Tier 2 events.

        Phase 2: reduce_only MARKET order on Binance.
        """
        logger.info(
            "INOUT.EXEC: PARTIAL EXIT %s %s qty=%.6f reason=%s target=%.5f",
            symbol, direction, qty, reason, target_price or 0,
        )

        if self._dry_run:
            slippage = 0.0003
            fill_price = target_price or 0.0
            if fill_price > 0:
                fill_price *= (1 - slippage) if direction == "LONG" else (1 + slippage)
            return FillResult(
                success=True,
                order_id=_gen_order_id("PARTIAL"),
                fill_price=fill_price,
                fill_qty=qty,
                status="filled",
                reason=f"dry_run:{reason}",
            )

        # Phase 2:
        # side = "SELL" if direction == "LONG" else "BUY"
        # response = self._client.futures_create_order(
        #     symbol=symbol, side=side, type="MARKET",
        #     quantity=qty, reduceOnly=True
        # )
        raise NotImplementedError("Phase 2: implement Binance partial exit")

    # ── Full exit ─────────────────────────────────────────────────────────────

    def exit_full(
        self,
        symbol: str,
        direction: str,
        qty: float,
        reason: str,
        target_price: float | None = None,
    ) -> FillResult:
        """
        Close entire remaining position at market.
        Called on SL hit, time-stop, or runner trail hit.
        Also cancels any open SL orders on the exchange.

        Phase 2: reduce_only MARKET + cancel open STOP_MARKET.
        """
        logger.info(
            "INOUT.EXEC: FULL EXIT %s %s qty=%.6f reason=%s target=%.5f",
            symbol, direction, qty, reason, target_price or 0,
        )

        if self._dry_run:
            slippage = 0.001  # 0.1% — higher slippage on forced exits
            fill_price = target_price or 0.0
            if fill_price > 0:
                fill_price *= (1 - slippage) if direction == "LONG" else (1 + slippage)
            return FillResult(
                success=True,
                order_id=_gen_order_id("EXIT"),
                fill_price=fill_price,
                fill_qty=qty,
                status="filled",
                reason=f"dry_run:{reason}",
            )

        raise NotImplementedError("Phase 2: implement Binance full exit")

    # ── SL management ─────────────────────────────────────────────────────────

    def update_stop_loss(
        self,
        symbol: str,
        direction: str,
        new_sl: float,
        existing_sl_order_id: str | None = None,
    ) -> bool:
        """
        Update the broker-side stop-loss order.
        Called on: Tier 1 → move to breakeven; runner trail update.

        Phase 2: cancel existing STOP_MARKET, place new one.
        Returns True on success.
        """
        logger.info(
            "INOUT.EXEC: UPDATE SL %s %s new_sl=%.5f",
            symbol, direction, new_sl,
        )

        if self._dry_run:
            return True

        # Phase 2:
        # if existing_sl_order_id:
        #     self._client.futures_cancel_order(symbol=symbol, orderId=existing_sl_order_id)
        # self._place_sl_order(symbol, direction, remaining_qty, new_sl)
        raise NotImplementedError("Phase 2: implement Binance SL update")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_dry_run(self) -> bool:
        return self._dry_run

    def enable_live(self) -> None:
        """
        Phase 2: call this after injecting real Binance client.
        Switches from dry-run to live execution.
        """
        self._dry_run = False
        logger.warning(
            "INOUT.EXEC: LIVE MODE ENABLED — real orders will be placed"
        )


def _gen_order_id(prefix: str) -> str:
    return f"INOUT_{prefix}_{uuid.uuid4().hex[:8].upper()}"
