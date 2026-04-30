# exposure_tracker.py — tracks open positions and portfolio risk
#
import logging
from typing import Optional

log = logging.getLogger(__name__)


class ExposureTracker:
    """
    Tracks open positions and computes total portfolio risk exposure.

    Position schema (dict):
        {
            "trade_id": str,
            "symbol": str,
            "risk": float,       ← fraction of capital at risk (e.g. 0.005 = 0.5%)
        }

    Usage:
        tracker = ExposureTracker()
        tracker.add_position({"trade_id": "t1", "symbol": "BTCUSDT", "risk": 0.005})
        print(tracker.total_risk())     # → 0.005
        tracker.remove_position("t1")
    """

    def __init__(self):
        self._positions: dict = {}  # trade_id → position dict

    def add_position(self, position: dict) -> None:
        """Add or update a position by trade_id."""
        trade_id = position.get("trade_id")
        if not trade_id:
            raise ValueError("Position must have a 'trade_id' field")
        self._positions[trade_id] = dict(position)
        log.debug(
            "ExposureTracker: added trade_id=%s symbol=%s risk=%.4f",
            trade_id, position.get("symbol", "?"), position.get("risk", 0.0),
        )

    def remove_position(self, trade_id: str) -> Optional[dict]:
        """Remove and return position by trade_id. Returns None if not found."""
        pos = self._positions.pop(trade_id, None)
        if pos:
            log.debug("ExposureTracker: removed trade_id=%s", trade_id)
        return pos

    def total_risk(self) -> float:
        """Total portfolio risk as fraction of capital."""
        return sum(p.get("risk", 0.0) for p in self._positions.values())

    def exposure_by_symbol(self) -> dict:
        """Risk exposure aggregated by symbol: {symbol: total_risk}."""
        out: dict = {}
        for p in self._positions.values():
            sym = p.get("symbol", "UNKNOWN")
            out[sym] = out.get(sym, 0.0) + p.get("risk", 0.0)
        return out

    def positions(self) -> list:
        """Return list of all open position dicts (copies)."""
        return [dict(p) for p in self._positions.values()]

    def position_count(self) -> int:
        """Number of open positions."""
        return len(self._positions)

    def clear(self) -> None:
        """Remove all positions (session reset)."""
        self._positions.clear()
        log.info("ExposureTracker: all positions cleared")