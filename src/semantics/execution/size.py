"""DEX-01 position size. quantity = risk_fraction * equity / R.

risk_fraction is a FRACTION (0.01 = 1 percent). A percent passed by mistake would size the
position 100x too large, so anything outside (0, 1) raises (F-111).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from semantics.identity import parameterization_id
from semantics.trading.plan import TradePlan

POSITION_SIZE = "DEX-01"
INITIAL_CAPITAL = "initial_capital"
CURRENT_EQUITY = "current_equity"
EQUITY_BASES = (INITIAL_CAPITAL, CURRENT_EQUITY)


@dataclass(frozen=True)
class PositionSize:
    """DEX-01. risk_fraction and equity_basis are the identity; equity is the value used."""

    concept_id: str
    parameterization_id: str
    available_at: int
    quantity: float
    risk_fraction: float
    equity: float
    equity_basis: str


def _check_fraction(risk_fraction: float) -> float:
    value = float(risk_fraction)
    if not 0.0 < value < 1.0:
        raise ValueError(f"DEX-01 risk_fraction {risk_fraction!r} must be a fraction in (0, 1), never a percent")
    return value


def position_size(
    plan: TradePlan,
    *,
    risk_fraction: float,
    equity: float,
    equity_basis: str,
) -> Optional[PositionSize]:
    """None when R is 0. equity is realised equity as of the plan bar (never open P&L)."""
    fraction = _check_fraction(risk_fraction)
    if equity_basis not in EQUITY_BASES:
        raise ValueError(f"DEX-01 equity_basis {equity_basis!r} is outside {EQUITY_BASES}")
    if not float(equity) > 0.0:
        raise ValueError(f"DEX-01 equity {equity!r} must be positive")
    risk = plan.R
    if risk <= 0:
        return None
    pid = parameterization_id(
        POSITION_SIZE, {"risk_fraction": fraction, "equity_basis": equity_basis},
        ("risk_fraction", "equity_basis"),
    )
    quantity = fraction * float(equity) / risk
    return PositionSize(
        POSITION_SIZE, pid, plan.available_at, quantity, fraction, float(equity), equity_basis,
    )
