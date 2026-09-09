"""Live portfolio adapter around UltronRiskGate. Not a second risk engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from core.ultron_risk_gate import UltronRiskGate
from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")


@dataclass
class LivePosition:
    symbol: str
    direction: int
    qty: float
    entry: float
    stop_loss: float
    take_profit_1: float
    risk_pct: float
    ticket: int
    opened_at: datetime
    unrealized_pct: float = 0.0


@dataclass
class LivePortfolioState:
    account_balance: float
    total_open_risk_pct: float
    trades_today: int
    daily_loss_pct: float
    open_positions: int
    positions: dict[str, LivePosition] = field(default_factory=dict)
    realized_pnl: float = 0.0
    equity: float = 0.0
    asof: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_ultron_dict(self) -> dict[str, Any]:
        return {
            "account_balance": float(self.account_balance),
            "total_open_risk_pct": float(self.total_open_risk_pct),
            "trades_today": int(self.trades_today),
            "daily_loss_pct": float(self.daily_loss_pct),
            "open_positions": int(self.open_positions),
            "positions": {k: True for k in self.positions},
        }


class UltronLiveAdapter:
    """Read-only preflight. Live size path is UltronRiskGateWrapper inside the hook."""

    def __init__(self, gate: UltronRiskGate, paper_balance: float) -> None:
        self._gate = gate
        self._state = LivePortfolioState(
            account_balance=float(paper_balance),
            total_open_risk_pct=0.0,
            trades_today=0,
            daily_loss_pct=0.0,
            open_positions=0,
            equity=float(paper_balance),
        )
        self._day: date | None = None

    def state(self) -> LivePortfolioState:
        return self._state

    def _roll_day(self) -> None:
        today = datetime.now(timezone.utc).date()
        if self._day is None:
            self._day = today
            return
        if self._day == today:
            return
        self._state.trades_today = 0
        self._state.daily_loss_pct = 0.0
        self._day = today

    def preflight(self, symbol: str) -> dict[str, Any]:
        """READ-ONLY. Does not call evaluate() (Check 4 writes the KS file)."""
        self._roll_day()
        if self._gate.is_tripped():
            logger.warning("UltronLiveAdapter.preflight REJECT kill_switch_active")
            return {
                "decision": "reject",
                "risk_reason": "kill_switch_active",
                "final_position_size": 0.0,
            }
        max_trades = int(self._gate.config["max_trades_per_day"])
        if self._state.trades_today >= max_trades:
            return {
                "decision": "reject",
                "risk_reason": "daily_limit",
                "final_position_size": 0.0,
            }
        if symbol in self._state.positions:
            return {
                "decision": "reject",
                "risk_reason": "position_already_open",
                "final_position_size": 0.0,
            }
        return {"decision": "pass", "risk_reason": "ok"}

    def mark_to_market(self, symbol: str, last: float) -> None:
        pos = self._state.positions.get(symbol)
        if pos is None or pos.qty <= 0:
            return
        sl_dist = abs(pos.entry - pos.stop_loss)
        if sl_dist <= 0:
            return
        signed = (last - pos.entry) * pos.direction
        pos.unrealized_pct = 100.0 * signed / self._state.account_balance
        self._state.equity = self._state.account_balance + signed * pos.qty
        self._state.asof = datetime.now(timezone.utc)

    def register_fill(self, pos: LivePosition, allowed_risk_pct: float) -> None:
        self._state.positions[pos.symbol] = pos
        self._state.open_positions = len(self._state.positions)
        self._state.total_open_risk_pct += float(allowed_risk_pct)
        self._state.trades_today += 1
