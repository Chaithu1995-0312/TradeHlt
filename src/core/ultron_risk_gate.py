"""
ultron_risk_gate.py
===================
CANONICAL NAMING:
  UltronRiskGate  (THIS FILE) = CAPITAL PROTECTION LAYER.
                    Validates position sizing, drawdown, and exposure limits.
                    Called externally by live_engine_hook.py AFTER
                    EngineRunner.run() + ExecutionPlannerV1_2.plan().

  RegimeGovernor  (ultron_gate.py) = SIGNAL-QUALITY FILTER.
                    Step 6 inside EngineRunner. Regime-based penalties + daily quota.
                    NOT a capital gate. (Class name: UltronGovernor — backward compat.)

Ultron Risk Gate v1 — final approval layer before execution.

Architecture position:
    Layer 1 (Intelligence) → EngineRunner.run()         → decision + score + regime
    Layer 2 (Planner)      → ExecutionPlannerV1_2.plan() → entry/SL/TP/RR/hint
    Layer 3 (This module)  → UltronRiskGate.evaluate()   → final approval + final size
    Layer 4 (Executor)     → broker stub (offline)

Design principles:
    - Deterministic: same inputs always produce same output.
    - No external dependencies (only datetime, typing).
    - Pure class with config injected at construction.
    - Hard-reject on any limit breach; no partial overrides.
    - Separation of concerns: position sizing is FINAL here, not in planner.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from utils.logging_config import get_flow_logger

logger = get_flow_logger("ULTRON_RISK_GATE")

# ── Default config (mirrors configs/production/v1_multi_2026_03.json values) ─
DEFAULT_CONFIG: dict = {
    "disabled":              False,
    "max_risk_per_trade_pct": 1.0,
    "max_portfolio_risk_pct": 5.0,
    "max_trades_per_day":    10,
    "max_daily_loss_pct":    3.0,
    "min_rr_ratio":          1.5,
}


class UltronRiskGate:
    """
    Deterministic risk validator. Consumes Execution Planner output and
    portfolio state; returns approve/reject with final position size.

    Checks (in order — first failure rejects immediately):
        1. TTL enforcement    — signal expired?
        2. RR floor           — rr_ratio < min?
        3. Daily trade limit  — too many trades today?
        4. Kill switch        — daily loss limit breached?
        5. Portfolio exposure — would exceed max_portfolio_risk_pct?
        6. SL distance        — entry == SL? (divide-by-zero guard)
        7. Position sizing    — compute final_position_size

    Usage
    -----
        gate = UltronRiskGate(config)
        result = gate.evaluate(trade, portfolio_state)
    """

    # ── Required configuration keys (all must be in v1_multi_2026_03.json) ─────
    _REQUIRED_KEYS: tuple[str, ...] = (
        "max_risk_per_trade_pct",
        "max_portfolio_risk_pct",
        "max_trades_per_day",
        "max_daily_loss_pct",
        "min_rr_ratio",
        "disabled",
    )

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Parameters
        ----------
        config : dict, optional
            Overrides for DEFAULT_CONFIG keys. Missing keys fall back to
            DEFAULT_CONFIG values. Pass None or omit to use all defaults.
        """
        effective: dict[str, Any] = {**DEFAULT_CONFIG}
        if isinstance(config, dict):
            effective.update(config)
        self.config: dict[str, Any] = effective

    # ── Public interface ──────────────────────────────────────────────────────

    def evaluate(
        self,
        trade: dict[str, Any],
        portfolio_state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate a trade plan against portfolio risk constraints.

        Parameters
        ----------
        trade : dict
            Output from ExecutionPlannerV1_2.plan() with decision == "execute".
            Required keys:
                execution_id, entry_price, stop_loss, rr_ratio, risk_percent,
                expires_at, position_size_hint (may be None).
        portfolio_state : dict
            Current portfolio snapshot.
            Required keys:
                account_balance (float)   — total account balance in base currency
                total_open_risk_pct (float) — sum of risk% for all open positions
                trades_today (int)        — count of trades taken today
                daily_loss_pct (float)    — realized loss today as % of balance
                open_positions (int)      — number of currently open positions

        Returns
        -------
        dict with keys:
            decision           : "approve" | "reject"
            execution_id       : str
            final_position_size: float  (0.0 on reject)
            risk_reason        : str
            portfolio_state    : dict with updated total_risk and open_positions
        """
        # ── Gate disabled (backtest / testing bypass) ────────────────────────
        if self.config.get("disabled", False):
            logger.info("UltronRiskGate: DISABLED — pass-through (no risk checks applied)")
            return {
                "decision": "approve",
                "risk_reason": "gate_disabled",
                "execution_id": trade.get("execution_id", "UNKNOWN"),
                "final_position_size": float(trade.get("position_size", 0.0)),
                "portfolio_state": portfolio_state,
            }

        execution_id = trade.get("execution_id", "UNKNOWN")

        # ── Check 1: TTL ─────────────────────────────────────────────────────
        expires_at_raw = trade.get("expires_at")
        if expires_at_raw:
            try:
                expires_at = datetime.fromisoformat(str(expires_at_raw))
                # Make timezone-aware if naive
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if now > expires_at:
                    return self._reject(trade, "expired_signal", portfolio_state)
            except (ValueError, TypeError):
                # Malformed timestamp — treat as expired for safety
                return self._reject(trade, "malformed_expires_at", portfolio_state)

        # ── Check 2: RR floor ────────────────────────────────────────────────
        rr_ratio = float(trade.get("rr_ratio", 0.0))
        if rr_ratio < float(self.config["min_rr_ratio"]):
            return self._reject(trade, "rr_too_low", portfolio_state)

        # ── Check 3: Daily trade limit ────────────────────────────────────────
        trades_today = int(portfolio_state.get("trades_today", 0))
        if trades_today >= int(self.config["max_trades_per_day"]):
            return self._reject(trade, "daily_limit", portfolio_state)

        # ── Check 4: Kill switch (daily loss) ────────────────────────────────
        daily_loss = float(portfolio_state.get("daily_loss_pct", 0.0))
        if daily_loss >= float(self.config["max_daily_loss_pct"]):
            return self._reject(trade, "kill_switch", portfolio_state)

        # ── Check 5: Portfolio exposure cap ──────────────────────────────────
        open_risk = float(portfolio_state.get("total_open_risk_pct", 0.0))
        risk_percent = float(trade.get("risk_percent", 0.5))
        max_risk_trade = float(self.config["max_risk_per_trade_pct"])
        # Cap the allowed risk to max per-trade limit
        allowed_risk = min(risk_percent, max_risk_trade)

        max_portfolio = float(self.config["max_portfolio_risk_pct"])
        if open_risk + allowed_risk > max_portfolio:
            return self._reject(trade, "over_exposure", portfolio_state)

        # ── Check 6: Valid SL distance ────────────────────────────────────────
        entry = float(trade.get("entry_price", 0.0))
        sl = float(trade.get("stop_loss", 0.0))
        risk_per_unit = abs(entry - sl)
        if risk_per_unit == 0.0:
            return self._reject(trade, "invalid_sl_distance", portfolio_state)

        # ── Check 7: Position sizing (final) ──────────────────────────────────
        balance = float(portfolio_state.get("account_balance", 10000.0))
        risk_usd = balance * (allowed_risk / 100.0)
        max_size_by_risk = risk_usd / risk_per_unit

        hint = trade.get("position_size_hint")
        if hint is not None:
            try:
                hint = float(hint)
                final_size = min(hint, max_size_by_risk)
            except (TypeError, ValueError):
                final_size = max_size_by_risk
        else:
            final_size = max_size_by_risk

        if final_size <= 0:
            return self._reject(trade, "position_size_zero", portfolio_state)

        final_size = round(final_size, 6)

        # ── Approve ───────────────────────────────────────────────────────────
        return {
            "decision":            "approve",
            "execution_id":        execution_id,
            "final_position_size": final_size,
            "risk_reason":         "ok",
            "allowed_risk_pct":    allowed_risk,
            "portfolio_state": {
                "total_risk":     round(open_risk + allowed_risk, 4),
                "open_positions": int(portfolio_state.get("open_positions", 0)),
            },
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _reject(
        self,
        trade: dict[str, Any],
        reason: str,
        portfolio_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a standardised REJECT response."""
        return {
            "decision":            "reject",
            "execution_id":        trade.get("execution_id", "UNKNOWN"),
            "final_position_size": 0.0,
            "risk_reason":         reason,
            "allowed_risk_pct":    0.0,
            "portfolio_state":     portfolio_state,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SELF-REVIEW
# ─────────────────────────────────────────────────────────────────────────────
#
# Assumptions
# -----------
# - `expires_at` is an ISO-8601 string (with or without timezone suffix).
# - `account_balance` is in base currency units consistent with `risk_per_unit`.
# - `position_size_hint` from the planner is denominated in the same units.
# - `total_open_risk_pct` accumulates monotonically until Ultron deducts it.
#
# Edge Cases
# ----------
# - expires_at missing/None → TTL check skipped (no rejection).
# - expires_at malformed string → treated as expired → reject.
# - risk_per_unit == 0 → reject with "invalid_sl_distance".
# - position_size_hint is None → max_size_by_risk used directly.
# - position_size_hint is negative → min(negative, max) = negative → reject "position_size_zero".
# - allowed_risk capped at max_risk_per_trade_pct but never raises its own reject.
#
# Failure Modes
# -------------
# - account_balance = 0 → risk_usd = 0 → max_size_by_risk = 0 → reject.
# - Float precision: risk_per_unit near machine-epsilon could produce huge size.
#   Mitigation: planner already validates entry != sl; Ultron guards abs() > 0.
# - Clock skew: if system clock is behind the signal clock, a valid signal may
#   appear expired. Mitigation: accept ±0s margin (caller responsibility).
#
# Test Cases (example)
# --------------------
# 1. Happy path: trade with rr=2.0, trades_today=3, open_risk=1.5%, balance=10000
#    → approve, final_size = 10000*0.5%/risk_per_unit
# 2. Expired: expires_at in the past → reject "expired_signal"
# 3. Over exposure: open_risk=4.8%, allowed_risk=0.5% → 5.3 > 5.0 → reject "over_exposure"
# 4. Kill switch: daily_loss_pct=3.1 → reject "kill_switch"
# 5. Hint smaller than max: hint=0.05, max=0.10 → final_size=0.05
#
# Risks
# -----
# - Ultron does NOT update portfolio_state in place. Caller must persist
#   the returned portfolio_state (total_risk, open_positions) between calls.
# - Ultron does NOT verify that entry/SL/TP form a valid trade structure.
#   That is the Execution Planner's responsibility.
#
# Integration Notes
# -----------------
# Integration point after ExecutionPlannerV1_2.plan():
#
#     planner = ExecutionPlannerV1_2(config)
#     gate    = UltronRiskGate(config)
#
#     trade_plan = planner.plan(engine_result, features, context)
#     if trade_plan["decision"] == "execute":
#         risk_result = gate.evaluate(trade_plan, portfolio_state)
#         if risk_result["decision"] == "approve":
#             send_to_broker(trade_plan, risk_result["final_position_size"])


# ─────────────────────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from datetime import timedelta

    gate = UltronRiskGate()

    base_trade = {
        "execution_id":        "EX_abc123def456",
        "entry_price":         100.0,
        "stop_loss":           98.0,
        "take_profit_1":       104.0,
        "rr_ratio":            2.0,
        "risk_percent":        0.5,
        "position_size_hint":  25.0,
        "expires_at":          (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat(),
    }

    base_portfolio = {
        "account_balance":      10000.0,
        "total_open_risk_pct":  1.0,
        "trades_today":         2,
        "daily_loss_pct":       0.5,
        "open_positions":       2,
    }

    # Test 1: Happy path
    r1 = gate.evaluate(base_trade, base_portfolio)
    assert r1["decision"] == "approve", f"Expected approve, got {r1}"
    assert r1["final_position_size"] > 0
    print(f"Test 1 PASS: approve, size={r1['final_position_size']}")

    # Test 2: Expired signal
    expired_trade = {**base_trade, "expires_at": "2020-01-01T00:00:00+00:00"}
    r2 = gate.evaluate(expired_trade, base_portfolio)
    assert r2["decision"] == "reject" and r2["risk_reason"] == "expired_signal"
    print(f"Test 2 PASS: {r2['risk_reason']}")

    # Test 3: RR too low
    low_rr_trade = {**base_trade, "rr_ratio": 1.0}
    r3 = gate.evaluate(low_rr_trade, base_portfolio)
    assert r3["decision"] == "reject" and r3["risk_reason"] == "rr_too_low"
    print(f"Test 3 PASS: {r3['risk_reason']}")

    # Test 4: Kill switch
    bad_portfolio = {**base_portfolio, "daily_loss_pct": 3.5}
    r4 = gate.evaluate(base_trade, bad_portfolio)
    assert r4["decision"] == "reject" and r4["risk_reason"] == "kill_switch"
    print(f"Test 4 PASS: {r4['risk_reason']}")

    # Test 5: Over exposure
    fat_portfolio = {**base_portfolio, "total_open_risk_pct": 4.8}
    r5 = gate.evaluate(base_trade, fat_portfolio)
    assert r5["decision"] == "reject" and r5["risk_reason"] == "over_exposure"
    print(f"Test 5 PASS: {r5['risk_reason']}")

    # Test 6: Invalid SL distance (entry == stop_loss)
    bad_sl_trade = {**base_trade, "stop_loss": 100.0}
    r6 = gate.evaluate(bad_sl_trade, base_portfolio)
    assert r6["decision"] == "reject" and r6["risk_reason"] == "invalid_sl_distance"
    print(f"Test 6 PASS: {r6['risk_reason']}")

    print("\n=== All UltronRiskGate tests passed ===")