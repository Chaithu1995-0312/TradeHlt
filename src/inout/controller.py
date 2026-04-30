"""
inout/controller.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — Trade Controller

Orchestrates the full INOUT pipeline per signal:

    INOUTScanner (signal)
        → INOUTController.on_signal()
            → guard rails (dedup, max trades, exposure)
            → UltronRiskGate.evaluate()         ← READ ONLY, not modified
            → INOUTDatabase.create_trade()       ← atomic DB write first
            → INOUTExecutor.open_position()      ← broker AFTER DB write
            → INOUTDatabase.transition(ACTIVE)
        → INOUTController.on_price_tick()
            → INOUTStateMachine.evaluate()
            → execute action instruction
            → INOUTDatabase.transition()

Architecture boundaries (HARD):
    - UltronRiskGate: imported, never modified
    - EngineRunner:   NOT imported (INOUT is parallel, not downstream)
    - ExecutionPlannerV1_2: NOT used (INOUT has its own plan builder)
    - live_engine_hook.py: NOT touched

Guard rails enforced here:
    - max_concurrent_trades
    - max_total_exposure_pct
    - dedup_window_seconds (no duplicate signal per symbol)
    - no new signal while same symbol has open trade

Extension points:
    Phase 2: on_signal() calls probability engine before Ultron
    Phase 3: on_signal() calls Gemini for regime context
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import INOUTConfig
from .db import INOUTDatabase
from .executor import INOUTExecutor, FillResult
from .scanner import INOUTSignal
from .state_machine import ActionInstruction, ActionType, INOUTStateMachine

# ── Ultron import (READ ONLY — never modify) ──────────────────────────────────
try:
    from core.ultron_risk_gate import UltronRiskGate
    _ULTRON_AVAILABLE = True
except ImportError:
    _ULTRON_AVAILABLE = False

logger = logging.getLogger("INOUT.CONTROLLER")


class INOUTController:
    """
    Central coordinator for the INOUT strategy.

    One instance per runner process. Thread-safe via DB WAL.

    Usage
    -----
        cfg  = INOUTConfig.load()
        db   = INOUTDatabase(cfg)
        exec = INOUTExecutor(cfg)
        sm   = INOUTStateMachine(cfg)
        ctrl = INOUTController(cfg, db, exec, sm)

        # Feed signals from scanner:
        ctrl.on_signal(signal)

        # Feed price ticks (call every candle close):
        ctrl.on_price_tick(symbol="BTCUSDT", price=51234.0, atr=120.0)

        # On boot — resurrect any unclosed trades:
        ctrl.resurrect()
    """

    def __init__(
        self,
        cfg: INOUTConfig,
        db: INOUTDatabase,
        executor: INOUTExecutor,
        state_machine: INOUTStateMachine,
        ultron_config: dict[str, Any] | None = None,
    ) -> None:
        self._cfg = cfg
        self._db = db
        self._exec = executor
        self._sm = state_machine

        # Ultron (risk gate) — READ ONLY
        self._ultron: UltronRiskGate | None = None
        if _ULTRON_AVAILABLE:
            ultron_cfg = ultron_config or {}
            self._ultron = UltronRiskGate(ultron_cfg)
            logger.info("INOUT.CTRL: UltronRiskGate loaded")
        else:
            logger.warning(
                "INOUT.CTRL: UltronRiskGate not available — risk checks will use internal guard rails only"
            )

        # In-memory dedup tracker: symbol → last signal timestamp (epoch sec)
        self._dedup: dict[str, float] = {}

        # Portfolio state for Ultron (reset on init, maintained across ticks)
        self._portfolio_state: dict[str, Any] = {
            "account_balance": 10000.0,
            "total_open_risk_pct": 0.0,
            "trades_today": 0,
            "daily_loss_pct": 0.0,
            "open_positions": 0,
        }

    # ── Signal entry point ────────────────────────────────────────────────────

    def on_signal(self, signal: INOUTSignal) -> dict[str, Any]:
        """
        Process an INOUTSignal from the scanner.

        Returns dict with outcome:
            {"accepted": True/False, "trade_id": str | None, "reason": str}

        ATOMIC ORDER:
            1. Guard rails
            2. Build trade plan
            3. Ultron risk check
            4. DB write (BEFORE broker)
            5. Broker open
            6. DB transition to ACTIVE
        """
        symbol = signal.symbol
        direction = signal.direction

        logger.info(
            "INOUT.CTRL: signal received %s %s score=%.3f",
            symbol, direction, signal.composite_score,
        )

        # ── Step 1: Guard rails ───────────────────────────────────────────────
        guard_result = self._apply_guard_rails(signal)
        if not guard_result["ok"]:
            logger.info("INOUT.CTRL: signal REJECTED (guard) %s: %s", symbol, guard_result["reason"])
            return {"accepted": False, "trade_id": None, "reason": guard_result["reason"]}

        # ── Step 2: Build trade plan ──────────────────────────────────────────
        plan = self._build_trade_plan(signal)
        if plan is None:
            return {"accepted": False, "trade_id": None, "reason": "plan_build_failed"}

        # ── Step 3: Ultron risk check ─────────────────────────────────────────
        risk_result = self._check_ultron(plan)
        if risk_result["decision"] != "approve":
            logger.info(
                "INOUT.CTRL: signal REJECTED (Ultron) %s: %s",
                symbol, risk_result.get("risk_reason", "ultron_reject"),
            )
            return {
                "accepted": False,
                "trade_id": None,
                "reason": f"ultron:{risk_result.get('risk_reason', 'reject')}",
            }

        final_size = float(risk_result.get("final_position_size", plan["position_size"]))

        # ── Step 4: DB write FIRST (resurrection safety) ──────────────────────
        time_stop_at = datetime.now(timezone.utc) + timedelta(
            minutes=float(self._cfg.time("max_time_min", 15))
        )
        trade_id = self._db.create_trade(
            symbol=symbol,
            direction=direction,
            entry_price=plan["entry_price"],
            stop_loss=plan["stop_loss"],
            tp1_price=plan["tp1_price"],
            tp2_price=plan["tp2_price"],
            position_size=final_size,
            risk_pct=plan["risk_pct"],
            rr_ratio=plan["rr_ratio"],
            signal_score=signal.composite_score,
            signal_meta=signal.to_dict(),
            time_stop_at=time_stop_at,
        )

        # ── Step 4b: Store probability snapshot (Phase 2 — no-op if engine not wired)
        if getattr(signal, "prob_result", None) is not None:
            self._db.update_prob_snapshot(trade_id, signal.prob_result)

        # ── Step 5: Broker open ───────────────────────────────────────────────
        fill = self._exec.open_position(
            symbol=symbol,
            direction=direction,
            qty=final_size,
            stop_loss=plan["stop_loss"],
            tp1_price=plan["tp1_price"],
            tp2_price=plan["tp2_price"],
            entry_hint=plan["entry_price"],
        )

        if not fill.success:
            self._db.transition(trade_id, "FAILED", {"reason": fill.reason})
            logger.error("INOUT.CTRL: broker fill FAILED trade=%s reason=%s", trade_id, fill.reason)
            return {"accepted": False, "trade_id": trade_id, "reason": f"broker:{fill.reason}"}

        # ── Step 6: Transition to ACTIVE ──────────────────────────────────────
        self._db.transition(trade_id, "ACTIVE", {"fill_price": fill.fill_price})
        self._update_portfolio_state_on_open(plan["risk_pct"])
        self._dedup[symbol] = time.time()

        logger.info(
            "INOUT.CTRL: trade ACTIVATED %s %s fill=%.5f sl=%.5f tp1=%.5f tp2=%.5f size=%.6f",
            trade_id, symbol, fill.fill_price,
            plan["stop_loss"], plan["tp1_price"], plan["tp2_price"], final_size,
        )
        return {"accepted": True, "trade_id": trade_id, "reason": "ok", "fill": fill.to_dict()}

    # ── Price tick handler ────────────────────────────────────────────────────

    def on_price_tick(
        self,
        symbol: str,
        price: float,
        current_time: datetime | None = None,
        atr: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Called on every new candle close for each monitored symbol.
        Evaluates all open trades for that symbol and executes any actions.

        Returns list of action results (one per trade acted upon).
        """
        open_trades = self._db.get_active_by_symbol(symbol)
        if not open_trades:
            return []

        results = []
        for trade in open_trades:
            instruction = self._sm.evaluate(
                trade=trade,
                current_price=price,
                current_time=current_time,
                current_atr=atr,
            )
            if instruction.action != ActionType.NONE:
                result = self._execute_instruction(instruction, trade, price)
                results.append(result)

        return results

    # ── System boot resurrection ──────────────────────────────────────────────

    def resurrect(self) -> int:
        """
        Called on system boot. Re-establishes monitoring for any
        trades that were not cleanly closed before shutdown.

        Returns number of trades resurrected.
        """
        unclosed = self._db.get_unclosed_trades()
        count = len(unclosed)
        if count == 0:
            logger.info("INOUT.CTRL: resurrect — no unclosed trades")
            return 0

        logger.warning(
            "INOUT.CTRL: resurrect — found %d unclosed trade(s)", count
        )
        for trade in unclosed:
            logger.info(
                "INOUT.CTRL: resurrecting trade=%s %s %s state=%s",
                trade["trade_id"], trade["symbol"], trade["direction"], trade["state"],
            )
            # Phase 2: re-verify broker position, re-place any missing SL orders
            # For now: log and re-add to active monitoring

        return count

    # ── Portfolio state update ────────────────────────────────────────────────

    def update_portfolio_state(self, state: dict[str, Any]) -> None:
        """
        Called by runner to sync live portfolio state before signal evaluation.
        Phase 2: pull directly from Binance account info API.
        """
        self._portfolio_state.update(state)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _apply_guard_rails(self, signal: INOUTSignal) -> dict[str, Any]:
        symbol = signal.symbol

        # Rule 1: no duplicate signals for same symbol within dedup window
        dedup_sec = float(self._cfg.risk("dedup_window_seconds", 300))
        last = self._dedup.get(symbol, 0.0)
        if time.time() - last < dedup_sec:
            return {"ok": False, "reason": f"dedup_cooldown:{symbol}"}

        # Rule 2: no new trade if same symbol already has an open trade
        if self._db.get_active_by_symbol(symbol):
            return {"ok": False, "reason": f"symbol_already_open:{symbol}"}

        # Rule 3: max concurrent trades
        max_concurrent = int(self._cfg.risk("max_concurrent_trades", 3))
        open_count = self._db.count_open_trades()
        if open_count >= max_concurrent:
            return {"ok": False, "reason": f"max_concurrent:{open_count}/{max_concurrent}"}

        # Rule 4: max total exposure
        max_exposure = float(self._cfg.risk("max_total_exposure_pct", 3.0))
        current_exposure = self._db.open_risk_pct()
        risk_per_trade = float(self._cfg.risk("risk_per_trade_pct", 0.5))
        if current_exposure + risk_per_trade > max_exposure:
            return {"ok": False, "reason": f"max_exposure:{current_exposure:.2f}+{risk_per_trade:.2f}>{max_exposure:.2f}"}

        return {"ok": True, "reason": "ok"}

    def _build_trade_plan(self, signal: INOUTSignal) -> dict[str, Any] | None:
        """
        Build entry/SL/TP/RR plan from INOUTSignal.
        INOUT uses its own plan builder — NOT ExecutionPlannerV1_2.
        """
        direction = signal.direction
        entry = signal.trigger_price
        atr = signal.atr

        if atr <= 0 or entry <= 0:
            logger.error("INOUT.CTRL: invalid atr=%.5f or entry=%.5f", atr, entry)
            return None

        # ── SL: structure-based ───────────────────────────────────────────────
        sl_struct_lookback = int(self._cfg.exit("sl_structure_lookback", 5))
        sl_atr_buffer = float(self._cfg.exit("sl_atr_buffer_mult", 0.2))

        # For Phase 1 use candle high/low as structure proxy
        if direction == "LONG":
            sl = round(signal.candle_low - atr * sl_atr_buffer, 5)
        else:
            sl = round(signal.candle_high + atr * sl_atr_buffer, 5)

        sl_distance = abs(entry - sl)
        if sl_distance == 0:
            logger.error("INOUT.CTRL: zero SL distance — rejecting")
            return None

        # ── TP1: 1R (Tier 1) ─────────────────────────────────────────────────
        tp1_rr = float(self._cfg.exit("tp1_rr", 1.0))
        if direction == "LONG":
            tp1 = round(entry + sl_distance * tp1_rr, 5)
        else:
            tp1 = round(entry - sl_distance * tp1_rr, 5)

        # ── TP2: 2R (Tier 2 — CRT extension proxy) ────────────────────────────
        tp2_rr = float(self._cfg.exit("tp2_rr", 2.0))
        if direction == "LONG":
            tp2 = round(entry + sl_distance * tp2_rr, 5)
        else:
            tp2 = round(entry - sl_distance * tp2_rr, 5)

        rr_ratio = tp2_rr  # Use Tier 2 as the RR ratio passed to Ultron

        # ── Position size hint ────────────────────────────────────────────────
        risk_pct = float(self._cfg.risk("risk_per_trade_pct", 0.5))
        balance = float(self._portfolio_state.get("account_balance", 10000.0))
        risk_usd = balance * (risk_pct / 100.0)
        position_size = round(risk_usd / sl_distance, 6) if sl_distance > 0 else 0.0

        plan = {
            "symbol": signal.symbol,
            "direction": direction,
            "entry_price": entry,
            "stop_loss": sl,
            "tp1_price": tp1,
            "tp2_price": tp2,
            "rr_ratio": rr_ratio,
            "risk_pct": risk_pct,
            "position_size": position_size,
            "atr": atr,
        }

        logger.debug(
            "INOUT.CTRL: plan built %s entry=%.5f sl=%.5f tp1=%.5f tp2=%.5f rr=%.2f size=%.6f",
            signal.symbol, entry, sl, tp1, tp2, rr_ratio, position_size,
        )
        return plan

    def _check_ultron(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Pass plan through UltronRiskGate (READ ONLY)."""
        if self._ultron is None:
            # No Ultron available — use internal guard only (already applied)
            logger.warning("INOUT.CTRL: Ultron unavailable — using guard-rail-only approval")
            return {
                "decision": "approve",
                "final_position_size": plan["position_size"],
                "risk_reason": "no_ultron",
            }

        trade_dict = {
            "execution_id": f"INOUT_{uuid.uuid4().hex[:8]}",
            "entry_price": plan["entry_price"],
            "stop_loss": plan["stop_loss"],
            "rr_ratio": plan["rr_ratio"],
            "risk_percent": plan["risk_pct"],
            "position_size": plan["position_size"],
            "position_size_hint": plan["position_size"],
            "expires_at": None,  # INOUT manages its own time-stop
        }
        return self._ultron.evaluate(trade_dict, self._portfolio_state)

    def _execute_instruction(
        self,
        instruction: ActionInstruction,
        trade: dict[str, Any],
        current_price: float,
    ) -> dict[str, Any]:
        """
        Translate ActionInstruction into DB + broker calls.
        Order: DB state write FIRST, broker second (resurrection safety).
        """
        trade_id = instruction.trade_id
        symbol = instruction.symbol
        direction = instruction.direction
        action = instruction.action

        result: dict[str, Any] = {"trade_id": trade_id, "action": action.value, "success": False}

        if action == ActionType.EXIT_PARTIAL:
            orig_size = float(trade.get("position_size", 0.0))
            exit_qty = round(orig_size * instruction.fraction, 6)

            # DB first
            if instruction.new_state:
                self._db.transition(trade_id, instruction.new_state, {
                    "reason": instruction.exit_reason
                })

            # Broker
            fill = self._exec.exit_partial(
                symbol=symbol,
                direction=direction,
                qty=exit_qty,
                reason=instruction.exit_reason,
                target_price=instruction.target_price,
            )

            # Log exit
            pnl_rr = self._compute_pnl_rr(
                trade, fill.fill_price, exit_qty, instruction.exit_tier or 0
            )
            self._db.record_exit(
                trade_id=trade_id,
                tier=instruction.exit_tier or 0,
                fraction=instruction.fraction,
                fill_price=fill.fill_price,
                exit_reason=instruction.exit_reason,
                target_price=instruction.target_price,
                pnl_rr=pnl_rr,
            )

            # Update SL to breakeven / new level
            if instruction.new_sl is not None:
                self._exec.update_stop_loss(symbol, direction, instruction.new_sl)
                self._db_update_sl(trade_id, instruction.new_sl)

            result.update({"success": fill.success, "fill": fill.to_dict(), "pnl_rr": pnl_rr})
            logger.info(
                "INOUT.CTRL: PARTIAL EXIT %s tier=%d fill=%.5f pnl_rr=%.3f",
                trade_id, instruction.exit_tier or 0, fill.fill_price, pnl_rr or 0,
            )

        elif action == ActionType.EXIT_FULL:
            orig_size = float(trade.get("position_size", 0.0))
            exit_qty = round(orig_size * instruction.fraction, 6)

            # DB first
            if instruction.new_state:
                self._db.transition(trade_id, instruction.new_state, {
                    "reason": instruction.exit_reason
                })

            # Broker
            fill = self._exec.exit_full(
                symbol=symbol,
                direction=direction,
                qty=exit_qty,
                reason=instruction.exit_reason,
                target_price=instruction.target_price or current_price,
            )

            pnl_rr = self._compute_pnl_rr(
                trade, fill.fill_price, exit_qty, instruction.exit_tier or 99
            )
            self._db.record_exit(
                trade_id=trade_id,
                tier=instruction.exit_tier or 99,
                fraction=instruction.fraction,
                fill_price=fill.fill_price,
                exit_reason=instruction.exit_reason,
                target_price=instruction.target_price,
                pnl_rr=pnl_rr,
            )
            self._db.update_total_pnl(trade_id, pnl_rr or 0.0)
            self._update_portfolio_state_on_close(float(trade.get("risk_pct", 0.5)))

            result.update({"success": fill.success, "fill": fill.to_dict(), "pnl_rr": pnl_rr})
            logger.info(
                "INOUT.CTRL: FULL EXIT %s reason=%s fill=%.5f pnl_rr=%.3f",
                trade_id, instruction.exit_reason, fill.fill_price, pnl_rr or 0,
            )

        elif action == ActionType.UPDATE_TRAIL:
            if instruction.new_sl is not None:
                self._exec.update_stop_loss(symbol, direction, instruction.new_sl)
                self._db.update_runner_trail(trade_id, instruction.new_sl)
                result.update({"success": True, "new_sl": instruction.new_sl})

        elif action == ActionType.MOVE_SL:
            if instruction.new_sl is not None:
                self._exec.update_stop_loss(symbol, direction, instruction.new_sl)
                self._db_update_sl(trade_id, instruction.new_sl)
                result.update({"success": True, "new_sl": instruction.new_sl})

        return result

    def _compute_pnl_rr(
        self,
        trade: dict[str, Any],
        fill_price: float,
        qty: float,
        tier: int,
    ) -> float | None:
        try:
            entry = float(trade["entry_price"])
            sl = float(trade["stop_loss"])
            sl_dist = abs(entry - sl)
            if sl_dist == 0:
                return None
            direction = trade["direction"]
            if direction == "LONG":
                pnl_per_unit = fill_price - entry
            else:
                pnl_per_unit = entry - fill_price
            return round(pnl_per_unit / sl_dist, 4)
        except (KeyError, TypeError, ZeroDivisionError):
            return None

    def _db_update_sl(self, trade_id: str, new_sl: float) -> None:
        """Update stop_loss column directly for resurrection accuracy."""
        try:
            with self._db._conn() as conn:
                conn.execute(
                    "UPDATE inout_trades SET stop_loss = ? WHERE trade_id = ?",
                    (new_sl, trade_id),
                )
        except Exception as exc:
            logger.warning("INOUT.CTRL: failed to update SL in DB: %s", exc)

    def _update_portfolio_state_on_open(self, risk_pct: float) -> None:
        self._portfolio_state["open_positions"] = (
            int(self._portfolio_state.get("open_positions", 0)) + 1
        )
        self._portfolio_state["total_open_risk_pct"] = round(
            float(self._portfolio_state.get("total_open_risk_pct", 0.0)) + risk_pct, 4
        )
        self._portfolio_state["trades_today"] = (
            int(self._portfolio_state.get("trades_today", 0)) + 1
        )

    def _update_portfolio_state_on_close(self, risk_pct: float) -> None:
        self._portfolio_state["open_positions"] = max(
            0, int(self._portfolio_state.get("open_positions", 0)) - 1
        )
        self._portfolio_state["total_open_risk_pct"] = max(
            0.0,
            round(float(self._portfolio_state.get("total_open_risk_pct", 0.0)) - risk_pct, 4),
        )
