"""
ultron_risk_gate.py
===================
CANONICAL NAMING:
  UltronRiskGate  (THIS FILE) = CAPITAL PROTECTION LAYER.
                    Validates position sizing, drawdown, and exposure limits.
                    Called externally by live_engine_hook.py AFTER
                    EngineRunner.run() + ExecutionPlannerV1_2.plan().

  RegimeGovernor  (regime_governor.py) = SIGNAL-QUALITY FILTER.
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
    - No external dependencies (only datetime, typing) + the sizing bridge.
    - Pure class with config injected at construction.
    - Hard-reject on any limit breach; no partial overrides.
    - Separation of concerns: position sizing is FINAL here, not in planner.
    - Sizing is risk-based in the DEPOSIT currency (INR) and emits broker LOTS via
      core.position_sizing.size_trade_lots (D11, 2026-09-30). Below the broker's
      minimum lot the trade is REJECTED ("size_below_min_lot") — never rounded up.
"""

from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from utils.logging_config import get_flow_logger
from config_layer.strict_config import (
    ConfigKeyMissingError,  # noqa: F401  (re-exported for callers/tests)
    missing_keys,
    missing_reason,
    require_all,
)
# D11 (2026-09-30): sizing no longer happens here. The ONE sizing bridge is
# core.position_sizing.size_trade_lots — Ultron's final size, the live hook's
# position_size_hint and the backtest CapitalCurve all call it, so the three rails
# cannot disagree in units. `final_position_size` therefore means LOTS, not ounces.
from core.position_sizing import (
    REASON_SIZE_BELOW_MIN_LOT,  # noqa: F401  (re-exported for callers/tests)
    SPEC_SECTION,
    floor_to_lot_step,
    instrument_spec,
    size_trade_lots,
)

logger = get_flow_logger("ULTRON_RISK_GATE")

# FRAG-1 fix: persisted kill-switch state file.
# Written atomically on first trip; cleared only by reset_kill_switch().
# Lives outside the registry dir so it survives config reloads.
_KS_STATE_PATH = Path("logs") / "kill_switch_state.json"

# EPIC-84 STORY-84.2: the module-level DEFAULT_CONFIG and its merge are gone. Every key in
# ``UltronRiskGate._REQUIRED_KEYS`` must be declared in the ``ultron_risk_gate`` config section;
# a missing key raises ``ConfigKeyMissingError`` at construction. Per-trade / portfolio payload
# values listed in ``_REQUIRED_TRADE_KEYS`` / ``_REQUIRED_PORTFOLIO_KEYS`` that are absent at
# trade time REJECT that one trade with reason ``config_key_missing:<payload>.<key>`` (the
# engine keeps running) instead of substituting a literal (was: risk_percent 0.5,
# account_balance 10000.0, rr_ratio/entry/stop 0.0, counters 0).


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
        7. Position sizing    — compute final_position_size in BROKER LOTS
                                (risk-INR -> USD -> units -> lots; below the broker
                                minimum lot REJECTS with "size_below_min_lot")

    Usage
    -----
        gate = UltronRiskGate(config)
        result = gate.evaluate(trade, portfolio_state)
    """

    # ── Required configuration keys (ultron_risk_gate section; no defaults) ──
    _REQUIRED_KEYS: tuple[str, ...] = (
        "disabled",
        "max_risk_per_trade_pct",
        "max_portfolio_risk_pct",
        "max_trades_per_day",
        "max_daily_loss_pct",
        "min_rr_ratio",
        # Execution cost tax (audit fix 2026-05-14): 0.0 / 0.0 disables the tax.
        "spread_pips",
        "slippage_pips",
        "pip_size",
        # FRAG-6 minimum SL distance: 0.0 disables the guard.
        "min_sl_pips",
    )

    # ── Per-trade payload values: absent at trade time -> REJECT (never a literal) ──
    _REQUIRED_TRADE_KEYS: tuple[str, ...] = (
        "rr_ratio",
        "entry_price",
        "stop_loss",
        "risk_percent",
    )
    _REQUIRED_PORTFOLIO_KEYS: tuple[str, ...] = (
        "account_balance",
        "total_open_risk_pct",
        "trades_today",
        "daily_loss_pct",
        "open_positions",
    )

    def __init__(
        self,
        config: dict[str, Any],
        *,
        instrument_specs: dict[str, Any] | None = None,
        usd_inr_rate: float | None = None,
    ) -> None:
        """
        Parameters
        ----------
        config : dict
            The ``ultron_risk_gate`` config section. Every key in ``_REQUIRED_KEYS``
            must be present; a missing key raises ``ConfigKeyMissingError`` naming it.
        instrument_specs : dict | None
            The TOP-LEVEL ``instrument_specs`` section (broker contract facts:
            contract_size / lot_step / lot_min / lot_max). Required to size anything:
            absent/unresolved -> each trade REJECTS with
            ``config_key_missing:instrument_specs...`` (never a literal size).
        usd_inr_rate : float | None
            The declared ``capital_management.usd_to_inr_rate``. REQUIRED here rather
            than re-declared in this section. Absent -> per-trade REJECT.

        Construction deliberately does NOT require the two sizing inputs: callers that
        only exercise non-sizing checks (RR floor, TTL, kill switch, exposure) keep
        working unchanged, and the sizing step fails closed on its own.
        """
        require_all(
            config, self._REQUIRED_KEYS,
            section_name="ultron_risk_gate", consumer="UltronRiskGate",
        )
        self.config: dict[str, Any] = dict(config)
        # D11 sizing context (top-level instrument_specs + capital_management rate).
        # Kept as a plain dict / float; validated per trade so a config regression
        # REJECTS the trade instead of taking down the engine (STORY-84.2 shape).
        self._instrument_specs: dict[str, Any] = (
            dict(instrument_specs) if isinstance(instrument_specs, dict) else {}
        )
        self._usd_inr_rate: float | None = (
            None if usd_inr_rate is None else float(usd_inr_rate)
        )
        # FRAG-1 fix: load persisted kill-switch state from disk so the gate
        # cannot be bypassed across instantiations by resetting daily_loss_pct.
        self._kill_switch_tripped: bool = self._load_ks_state()

    # ── Kill-switch state persistence (FRAG-1 fix) ───────────────────────────

    def _load_ks_state(self) -> bool:
        """Read persisted kill-switch flag from disk.  Fail-open: returns False."""
        try:
            if _KS_STATE_PATH.exists():
                state = json.loads(_KS_STATE_PATH.read_text(encoding="utf-8"))
                return bool(state.get("tripped", False))
        except Exception:
            pass
        return False

    def _save_ks_state(self, tripped: bool, reason: str = "") -> None:
        """Atomically persist kill-switch state.  Fail-open: never raises."""
        try:
            _KS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "tripped":    tripped,
                "reason":     reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            tmp = _KS_STATE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            os.replace(tmp, _KS_STATE_PATH)
        except Exception as exc:
            logger.warning("UltronRiskGate: kill-switch state persistence failed: %s", exc)

    def is_tripped(self) -> bool:
        """Read-only kill-switch view. Does not call evaluate() and does not write the file."""
        return bool(self._kill_switch_tripped) or bool(self._load_ks_state())

    def reset_kill_switch(self) -> None:
        """
        Clear the persisted kill-switch state — operator admin action.

        Call this at the start of a new trading day or after manual review
        confirms the risk condition has been resolved.  The gate will resume
        approving trades on the next evaluate() call after reset.
        """
        self._kill_switch_tripped = False
        self._save_ks_state(False, reason="reset_by_operator")
        logger.warning("UltronRiskGate: kill switch reset by operator call.")

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
            final_position_size: float  (BROKER LOTS; 0.0 on reject)
            risk_reason        : str
            portfolio_state    : dict with updated total_risk and open_positions
        """
        # ── Gate disabled (backtest / testing bypass) ────────────────────────
        if self.config["disabled"]:
            logger.info("UltronRiskGate: DISABLED — pass-through (no risk checks applied)")
            # The pass-through size is a per-trade value: absent -> REJECT, never 0.0.
            _missing_size = missing_keys(trade, ("position_size",))
            if _missing_size:
                return self._reject(trade, missing_reason("trade", _missing_size), portfolio_state)
            return {
                "decision": "approve",
                "risk_reason": "gate_disabled",
                "execution_id": trade.get("execution_id", "UNKNOWN"),
                "final_position_size": float(trade["position_size"]),
                "portfolio_state": portfolio_state,
            }

        execution_id = trade.get("execution_id", "UNKNOWN")

        # ── Check 0: Persisted kill-switch state (FRAG-1 fix) ────────────────
        # Guards against callers that reset daily_loss_pct between calls to
        # bypass the stateless Check 4.  The flag is cleared only via
        # reset_kill_switch() — an explicit operator action.
        if self._kill_switch_tripped:
            logger.warning(
                "UltronRiskGate: kill switch ACTIVE (persisted) — "
                "blocking execution_id=%s. Call reset_kill_switch() to re-enable.",
                execution_id,
            )
            return self._reject(trade, "kill_switch_active", portfolio_state)

        # ── Check 0b: per-trade payload completeness (EPIC-84 STORY-84.2) ────
        # A value the trade or portfolio snapshot must carry is never substituted by a
        # literal: the trade is REJECTED with a named reason; the engine keeps running.
        _missing_trade = missing_keys(trade, self._REQUIRED_TRADE_KEYS)
        if _missing_trade:
            return self._reject(trade, missing_reason("trade", _missing_trade), portfolio_state)
        _missing_ps = missing_keys(portfolio_state, self._REQUIRED_PORTFOLIO_KEYS)
        if _missing_ps:
            return self._reject(
                trade, missing_reason("portfolio_state", _missing_ps), portfolio_state,
            )

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

        # ── Check 2: RR floor (with spread+slippage tax) ────────────────────
        rr_ratio   = float(trade["rr_ratio"])
        min_rr     = float(self.config["min_rr_ratio"])
        # Execution cost tax: deduct spread+slippage as a fraction of sl_distance.
        # Only applied when both pip_size > 0 and cost pips > 0.
        spread_pips   = float(self.config["spread_pips"])
        slippage_pips = float(self.config["slippage_pips"])
        pip_size      = float(self.config["pip_size"])
        total_cost_pips = spread_pips + slippage_pips
        if total_cost_pips > 0 and pip_size > 0:
            entry = float(trade["entry_price"])
            sl    = float(trade["stop_loss"])
            sl_distance = abs(entry - sl)
            if sl_distance > 0:
                cost_as_rr_fraction = (total_cost_pips * pip_size) / sl_distance
                rr_ratio = max(0.0, rr_ratio - cost_as_rr_fraction)
        if rr_ratio < min_rr:
            return self._reject(trade, "rr_too_low_after_costs", portfolio_state)

        # ── Check 2.5: Per-symbol duplicate position guard (FRAG-2) ──────────
        # Only enforced when the caller populates portfolio_state["positions"].
        # Legacy callers that omit "positions" are unaffected (empty dict = skip).
        instrument = trade.get("symbol", trade.get("instrument", ""))
        if instrument:
            open_pos_map = portfolio_state.get("positions", {})
            if open_pos_map.get(instrument):
                logger.warning(
                    "UltronRiskGate: position already open for %s — "
                    "rejecting duplicate (FRAG-2).", instrument,
                )
                return self._reject(trade, "position_already_open", portfolio_state)

        # ── Check 3: Daily trade limit ────────────────────────────────────────
        trades_today = int(portfolio_state["trades_today"])
        if trades_today >= int(self.config["max_trades_per_day"]):
            return self._reject(trade, "daily_limit", portfolio_state)

        # ── Check 4: Kill switch (daily loss) ────────────────────────────────
        daily_loss = float(portfolio_state["daily_loss_pct"])
        if daily_loss >= float(self.config["max_daily_loss_pct"]):
            # FRAG-1: persist flag so subsequent calls are blocked even if the
            # caller resets daily_loss_pct to 0.  Cleared only by reset_kill_switch().
            self._kill_switch_tripped = True
            self._save_ks_state(
                True,
                reason=(
                    f"daily_loss_pct={daily_loss:.2f}% >= "
                    f"max_daily_loss_pct={self.config['max_daily_loss_pct']}%"
                ),
            )
            logger.error(
                "UltronRiskGate: kill switch TRIPPED — daily_loss=%.2f%% >= limit=%.2f%%. "
                "State persisted to %s. Call reset_kill_switch() to re-enable.",
                daily_loss, float(self.config["max_daily_loss_pct"]), _KS_STATE_PATH,
            )
            return self._reject(trade, "kill_switch", portfolio_state)

        # ── Check 5: Portfolio exposure cap ──────────────────────────────────
        open_risk = float(portfolio_state["total_open_risk_pct"])
        risk_percent = float(trade["risk_percent"])
        max_risk_trade = float(self.config["max_risk_per_trade_pct"])
        # Cap the allowed risk to max per-trade limit
        allowed_risk = min(risk_percent, max_risk_trade)

        max_portfolio = float(self.config["max_portfolio_risk_pct"])
        if open_risk + allowed_risk > max_portfolio:
            return self._reject(trade, "over_exposure", portfolio_state)

        # ── Check 6: Valid SL distance ────────────────────────────────────────
        entry = float(trade["entry_price"])
        sl = float(trade["stop_loss"])
        risk_per_unit = abs(entry - sl)
        if risk_per_unit == 0.0:
            return self._reject(trade, "invalid_sl_distance", portfolio_state)

        # ── Check 6b: Minimum SL distance enforcement (FRAG-6) ───────────────
        # Prevents trades where the SL is so tight that spread + slippage
        # would consume the entire risk distance.  Only enforced when
        # min_sl_pips > 0 and pip_size > 0 (0.0 = disabled, backtest default).
        min_sl_pips = float(self.config["min_sl_pips"])
        if min_sl_pips > 0 and pip_size > 0:
            sl_pips = risk_per_unit / pip_size
            # Effective minimum: the larger of min_sl_pips and 2× spread
            min_from_spread = spread_pips * 2.0
            effective_min_sl_pips = max(min_sl_pips, min_from_spread)
            if sl_pips < effective_min_sl_pips:
                logger.warning(
                    "UltronRiskGate: SL too tight — sl_pips=%.2f < effective_min=%.2f "
                    "(min_sl_pips=%.2f, spread×2=%.2f). Rejecting (FRAG-6).",
                    sl_pips, effective_min_sl_pips, min_sl_pips, min_from_spread,
                )
                return self._reject(trade, "sl_distance_too_tight", portfolio_state)

        # ── Check 7: Position sizing (final, in BROKER LOTS) ──────────────────
        # D11 (2026-09-30): the risk budget is in the DEPOSIT currency (INR). It is
        # converted USD-side, turned into instrument units and then into LOTS by the
        # ONE shared bridge — the same function the live hook's position_size_hint and
        # the backtest CapitalCurve call. A budget that cannot buy the broker's
        # minimum lot REJECTS this trade; it is never rounded up.
        balance = float(portfolio_state["account_balance"])   # INR (deposit currency)
        risk_capital_inr = balance * (allowed_risk / 100.0)
        if risk_capital_inr <= 0:
            return self._reject(trade, "position_size_zero", portfolio_state)

        # `missing_keys` only checks key PRESENCE — self._usd_inr_rate/_instrument_specs
        # are always present as attributes (possibly None/{}), so it would never catch
        # an unconfigured gate and Check 7 would crash on float(None) below instead of
        # rejecting. Check the actual sizing-context values directly.
        missing_sizing = [
            name for name, value in (
                ("usd_inr_rate", self._usd_inr_rate),
                ("instrument_specs", self._instrument_specs),
            ) if not value
        ]
        if missing_sizing:
            return self._reject(
                trade, missing_reason("sizing", missing_sizing), portfolio_state,
            )
        instrument = str(trade.get("symbol", trade.get("instrument", "")))
        try:
            spec = instrument_spec(
                self._instrument_specs, instrument, consumer="UltronRiskGate",
            )
        except (ConfigKeyMissingError, TypeError) as exc:
            # An undeclared instrument fails CLOSED: a size is never guessed from a
            # missing contract spec (F-110). Reason names the exact key.
            logger.error(
                "UltronRiskGate: no declared broker contract spec for %r — rejecting "
                "(sizing is never guessed). %s", instrument, exc,
            )
            keys = list(getattr(exc, "missing", ()) or ()) or [instrument or "<instrument>"]
            return self._reject(trade, missing_reason(SPEC_SECTION, keys), portfolio_state)

        lots, size_reason = size_trade_lots(
            risk_capital_inr,
            float(self._usd_inr_rate),
            risk_per_unit,
            float(spec["contract_size"]),
            float(spec["lot_step"]),
            float(spec["lot_min"]),
            float(spec["lot_max"]),
        )
        if lots is None:
            logger.warning(
                "UltronRiskGate: sizing REJECT (%s) — execution_id=%s instrument=%s "
                "risk=%.2f INR (=%.4f USD) stop_distance=%.6f contract_size=%s "
                "lot_min=%s. Below the broker minimum lot is never rounded up.",
                size_reason, execution_id, instrument, risk_capital_inr,
                risk_capital_inr / float(self._usd_inr_rate), risk_per_unit,
                spec["contract_size"], spec["lot_min"],
            )
            return self._reject(
                trade, size_reason or REASON_SIZE_BELOW_MIN_LOT, portfolio_state,
            )

        # A caller-supplied hint is a CEILING — it may only REDUCE the size — and it is
        # denominated in LOTS by the same bridge (live hook: position_size_hint). It is
        # floored onto the broker's step grid here so a sub-step hint can never be
        # rounded UP by the venue's own lot rounding.
        final_size = lots
        hint = trade.get("position_size_hint")
        if hint is not None:
            try:
                hint = float(hint)
            except (TypeError, ValueError):
                hint = None
            if hint is not None:
                if hint <= 0:
                    return self._reject(trade, "position_size_zero", portfolio_state)
                hint_lots = floor_to_lot_step(hint, float(spec["lot_step"]))
                if hint_lots < float(spec["lot_min"]):
                    return self._reject(
                        trade, REASON_SIZE_BELOW_MIN_LOT, portfolio_state,
                    )
                final_size = min(hint_lots, lots)

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
                "open_positions": int(portfolio_state["open_positions"]),
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
# - `account_balance` is the account's DEPOSIT currency (INR) — NOT the instrument's.
# - `position_size_hint` from the planner is denominated in LOTS, by the same bridge
#   (core.position_sizing.size_trade_lots); it can only REDUCE the risk-derived size.
# - `instrument_specs` (top-level) and `capital_management.usd_to_inr_rate` are the
#   only brokers/currency facts the sizing step needs, injected at construction.
# - `total_open_risk_pct` accumulates monotonically until Ultron deducts it.
#
# Edge Cases
# ----------
# - expires_at missing/None → TTL check skipped (no rejection).
# - expires_at malformed string → treated as expired → reject.
# - risk_per_unit == 0 → reject with "invalid_sl_distance".
# - position_size_hint is None → the risk-derived lot size is used directly.
# - position_size_hint <= 0 → reject "position_size_zero" (unchanged semantics).
# - position_size_hint > 0 but below lot_min → reject "size_below_min_lot".
# - instrument not declared in instrument_specs → reject
#   "config_key_missing:instrument_specs.<SYM>" (fail closed, never guessed).
# - usd_inr_rate / instrument_specs not injected → reject "config_key_missing:sizing.*".
# - allowed_risk capped at max_risk_per_trade_pct but never raises its own reject.
#
# Failure Modes
# -------------
# - account_balance = 0 → risk_capital_inr = 0 → reject "position_size_zero".
# - Risk budget below the cheapest broker lot → reject "size_below_min_lot"
#   (measured XAUUSD case: 0.5% of INR 1L with a stop wider than ~5.95 USD).
# - Float precision: risk_per_unit near machine-epsilon could produce a huge unit
#   count, but lots are clamped to the declared lot_max.
# - Clock skew: if system clock is behind the signal clock, a valid signal may
#   appear expired. Mitigation: accept ±0s margin (caller responsibility).
#
# Test Cases (example)
# --------------------
# 1. Happy path: XAUUSD, balance=100000 INR (1 lakh), risk=0.5%, entry-sl=5.0351,
#    rate=84, contract_size=100, step/min=0.01, max=10
#    → risk 500 INR = 5.9524 USD → 1.1822 oz → 0.01 lots → approve size=0.01
# 2. Expired: expires_at in the past → reject "expired_signal"
# 3. Over exposure: open_risk=4.8%, allowed_risk=0.5% → 5.3 > 5.0 → reject "over_exposure"
# 4. Kill switch: daily_loss_pct=3.1 → reject "kill_switch"
# 5. Hint smaller than the risk size: hint=0.01 lot < 0.02 lot → final_size=0.01
# 6. Wide stop: same budget with entry-sl=12.0 → 0.0049 lots → reject
#    "size_below_min_lot" (never rounded up to 0.01)
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

    # Explicit config: the values of the active ultron_risk_gate section (no defaults).
    gate = UltronRiskGate({
        "disabled": False, "max_risk_per_trade_pct": 1.0, "max_portfolio_risk_pct": 5.0,
        "max_trades_per_day": 10, "max_daily_loss_pct": 3.0, "min_rr_ratio": 1.5,
        "spread_pips": 0.0, "slippage_pips": 0.0, "pip_size": 0.0001, "min_sl_pips": 0.0,
    },
        # D11: the top-level instrument_specs section + the REUSED
        # capital_management.usd_to_inr_rate (never re-declared in this section).
        instrument_specs={
            "XAUUSD": {
                "contract_size": 100.0, "lot_step": 0.01, "lot_min": 0.01, "lot_max": 10.0,
            },
        },
        usd_inr_rate=84.0,
    )

    base_trade = {
        "execution_id":        "EX_abc123def456",
        "symbol":              "XAUUSD",
        "entry_price":         2600.0,
        "stop_loss":           2594.9649,   # risk distance 5.0351 USD/oz
        "take_profit_1":       2610.0702,
        "rr_ratio":            2.0,
        "risk_percent":        0.5,
        "position_size_hint":  None,
        "expires_at":          (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat(),
    }

    base_portfolio = {
        "account_balance":      100000.0,   # INR — the DEPOSIT currency (1 lakh)
        "total_open_risk_pct":  1.0,
        "trades_today":         2,
        "daily_loss_pct":       0.5,
        "open_positions":       2,
    }

    # The kill switch PERSISTS to disk (logs/kill_switch_state.json). Clear it first so
    # this harness is re-runnable: a previous run's trip would otherwise block Test 1.
    gate.reset_kill_switch()

    # Test 1: Happy path — 0.5% of 1 lakh = 500 INR = 5.9524 USD over a 5.0351 stop
    #         = 1.1822 oz = 0.011822 lots → floored to 0.01 lots.
    r1 = gate.evaluate(base_trade, base_portfolio)
    assert r1["decision"] == "approve", f"Expected approve, got {r1}"
    assert abs(r1["final_position_size"] - 0.01) < 1e-9, r1
    print(f"Test 1 PASS: approve, size={r1['final_position_size']} LOTS")

    # Test 2: Expired signal
    expired_trade = {**base_trade, "expires_at": "2020-01-01T00:00:00+00:00"}
    r2 = gate.evaluate(expired_trade, base_portfolio)
    assert r2["decision"] == "reject" and r2["risk_reason"] == "expired_signal"
    print(f"Test 2 PASS: {r2['risk_reason']}")

    # Test 3: RR too low
    low_rr_trade = {**base_trade, "rr_ratio": 1.0}
    r3 = gate.evaluate(low_rr_trade, base_portfolio)
    assert r3["decision"] == "reject" and r3["risk_reason"] == "rr_too_low_after_costs"
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
    bad_sl_trade = {**base_trade, "stop_loss": 2600.0}
    r6 = gate.evaluate(bad_sl_trade, base_portfolio)
    assert r6["decision"] == "reject" and r6["risk_reason"] == "invalid_sl_distance"
    print(f"Test 6 PASS: {r6['risk_reason']}")

    # Test 7: Risk budget below the broker minimum lot → REJECT, never rounded up.
    #         500 INR = 5.9524 USD over a 12.0 stop = 0.00496 lots < lot_min 0.01.
    wide_stop_trade = {**base_trade, "stop_loss": 2588.0}
    r7 = gate.evaluate(wide_stop_trade, base_portfolio)
    assert r7["decision"] == "reject" and r7["risk_reason"] == "size_below_min_lot", r7
    print(f"Test 7 PASS: {r7['risk_reason']}")

    # Test 8: An instrument with no declared broker spec fails CLOSED (never guessed).
    undeclared_trade = {**base_trade, "symbol": "EURUSD"}
    r8 = gate.evaluate(undeclared_trade, base_portfolio)
    assert r8["decision"] == "reject"
    assert r8["risk_reason"] == "config_key_missing:instrument_specs.EURUSD", r8
    print(f"Test 8 PASS: {r8['risk_reason']}")

    print("\n=== All UltronRiskGate tests passed ===")