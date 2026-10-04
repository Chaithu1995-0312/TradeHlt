"""
Fixtures for the mt5_analytics torture suite (Phase 2a).

Ensures the repo root is importable (so `import mt5_analytics` resolves) and provides a
synthetic MT5 deal factory mirroring the fields the reconstructor consumes. Synthetic
fixtures let the kernel be tested deterministically with NO live MT5 terminal.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

# MT5 deal entry / type constants re-exported for test readability.
from mt5_analytics.engines.position_reconstructor import (  # noqa: E402
    DEAL_ENTRY_IN,
    DEAL_ENTRY_INOUT,
    DEAL_ENTRY_OUT,
    DEAL_TYPE_BUY,
    DEAL_TYPE_SELL,
)
from mt5_analytics.engines.features._bars import Bar  # noqa: E402

BASE_TIME = 1_700_000_000  # arbitrary, fixed epoch seconds
M15 = 900                  # seconds per M15 bar


def make_bar(t: int, o: float, h: float, low: float, c: float, v: float = 0.0) -> Bar:
    """Build one Bar (index is assigned later by build_window)."""
    return Bar(index=0, time=t, open=o, high=h, low=low, close=c, volume=v)


def flat_bars(n: int, *, start_t: int, price: float, spread: float = 0.0) -> list[Bar]:
    """`n` warmup bars at `price` (optional high/low spread for a non-zero ATR)."""
    return [
        make_bar(start_t + i * M15, price, price + spread, price - spread, price)
        for i in range(n)
    ]


def make_deal(
    position_id: int,
    ticket: int,
    *,
    entry: int,
    deal_type: int,
    volume: float,
    price: float,
    t: int,
    profit: float = 0.0,
    swap: float = 0.0,
    commission: float = 0.0,
    symbol: str = "EURUSD",
) -> dict:
    """Build one synthetic MT5 deal dict (same keys the reconstructor reads)."""
    return {
        "position_id": position_id,
        "ticket": ticket,
        "symbol": symbol,
        "type": deal_type,
        "entry": entry,
        "volume": volume,
        "price": price,
        "profit": profit,
        "swap": swap,
        "commission": commission,
        "time": t,
    }


@pytest.fixture
def deal():
    """Expose the deal factory + constants as a convenience namespace."""
    class _DealNS:
        make = staticmethod(make_deal)
        IN = DEAL_ENTRY_IN
        OUT = DEAL_ENTRY_OUT
        INOUT = DEAL_ENTRY_INOUT
        BUY = DEAL_TYPE_BUY
        SELL = DEAL_TYPE_SELL
        base = BASE_TIME

    return _DealNS()
