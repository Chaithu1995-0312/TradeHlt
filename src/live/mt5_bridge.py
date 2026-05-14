"""
mt5_bridge.py
================================================================================
MT5Bridge — MetaTrader 5 order execution bridge.

Optional dependency: MetaTrader5. If unavailable, dry-run mode is enforced
automatically (fail-open per CONVENTIONS.md). MT5 orders are a side-effect;
never block the decision pipeline on MT5 availability.

Supported operations
--------------------
  send_order      — market order with SL and TP
  close_position  — close an open position by ticket number
  get_account_info — account balance/equity/margin snapshot

Config section: live_integration.mt5 in production JSON.

MT5 deviation: max price deviation in points for market orders (default 20).
MT5 magic:     unique EA identifier to distinguish our orders (default 20260501).
================================================================================
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.production_config import get_prod_section   # type: ignore
from utils.logging_config import get_flow_logger               # type: ignore

logger = get_flow_logger("LIVE_HOOK")

try:
    import MetaTrader5 as _mt5  # type: ignore[import]
    _MT5_AVAILABLE = True
except ImportError:
    _mt5 = None  # type: ignore[assignment]
    _MT5_AVAILABLE = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MT5Bridge:
    """
    Submits orders to MetaTrader 5 via the MetaTrader5 Python package.

    Fail-open: if MetaTrader5 is not installed or MT5 terminal is not running,
    all operations log a WARNING and return None/False without raising.
    dry_run=True logs the intended order without placing it — safe for UAT.

    Config keys (live_integration.mt5)
    ------------------------------------
    enabled       bool   — master on/off switch (default True)
    dry_run       bool   — log only, no actual orders (default True in prod until live)
    magic         int    — EA magic number to tag our orders (default 20260501)
    deviation     int    — max price deviation in points (default 20)
    slippage      int    — slippage tolerance in points (default 3)
    lot_min       float  — minimum lot size (default 0.01)
    lot_max       float  — maximum lot size (default 5.0)
    """

    # MT5 order type constants (mirrored here so tests run without MT5 installed)
    _ORDER_BUY  = 0   # mt5.ORDER_TYPE_BUY
    _ORDER_SELL = 1   # mt5.ORDER_TYPE_SELL

    def __init__(
        self,
        enabled: bool = True,
        dry_run: bool = True,
        magic: int = 20260501,
        deviation: int = 20,
        slippage: int = 3,
        lot_min: float = 0.01,
        lot_max: float = 5.0,
    ) -> None:
        self._enabled   = enabled
        self._dry_run   = dry_run or not _MT5_AVAILABLE
        self._magic     = magic
        self._deviation = deviation
        self._slippage  = slippage
        self._lot_min   = lot_min
        self._lot_max   = lot_max
        self._connected = False

        if not _MT5_AVAILABLE:
            logger.warning(
                "MT5Bridge: MetaTrader5 package not installed — dry_run enforced."
            )

    @classmethod
    def from_prod_config(cls) -> "MT5Bridge":
        cfg = ((get_prod_section("live_integration") or {})
               .get("mt5", {}))
        return cls(
            enabled   = bool(cfg.get("enabled",   True)),
            dry_run   = bool(cfg.get("dry_run",   True)),
            magic     = int(cfg.get("magic",       20260501)),
            deviation = int(cfg.get("deviation",   20)),
            slippage  = int(cfg.get("slippage",    3)),
            lot_min   = float(cfg.get("lot_min",   0.01)),
            lot_max   = float(cfg.get("lot_max",   5.0)),
        )

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Initialize MT5 connection. Returns True on success."""
        if not self._enabled:
            self._connected = False
            return False
        if self._dry_run:
            self._connected = True
            return True
        if not _MT5_AVAILABLE:
            return False
        try:
            if _mt5.initialize():
                self._connected = True
                logger.info("MT5Bridge: connected to MetaTrader 5 terminal.")
                return True
            logger.warning("MT5Bridge: mt5.initialize() failed — %s", _mt5.last_error())
            return False
        except Exception as exc:
            logger.warning("MT5Bridge: connection error: %s", exc)
            return False

    def disconnect(self) -> None:
        if _MT5_AVAILABLE and not self._dry_run:
            try:
                _mt5.shutdown()
            except Exception:
                pass
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # ── Order management ───────────────────────────────────────────────────────

    def send_order(
        self,
        symbol: str,
        action: str,          # "BUY" | "SELL"
        lot_size: float,
        sl_price: float,
        tp_price: float,
        comment: str = "tradelatest",
    ) -> Optional[int]:
        """
        Place a market order.

        Parameters
        ----------
        symbol    MT5 symbol string (e.g. "EURUSD")
        action    "BUY" or "SELL"
        lot_size  Position size in lots (clamped to [lot_min, lot_max])
        sl_price  Stop-loss price
        tp_price  Take-profit price
        comment   Order comment (visible in MT5 trade history)

        Returns
        -------
        int ticket number on success, None on failure.
        """
        if not self._enabled:
            logger.debug("MT5Bridge: disabled — order not sent.")
            return None

        lot_size = max(self._lot_min, min(self._lot_max, round(lot_size, 2)))
        order_type = self._ORDER_BUY if action.upper() == "BUY" else self._ORDER_SELL

        logger.info(
            "MT5Bridge: %s %s lot=%.2f sl=%.5f tp=%.5f %s",
            "DRY-RUN" if self._dry_run else "ORDER",
            symbol, lot_size, sl_price, tp_price, action,
        )

        if self._dry_run or not _MT5_AVAILABLE:
            return -1  # sentinel dry-run ticket

        try:
            tick = _mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning("MT5Bridge: no tick for symbol %s", symbol)
                return None

            price = tick.ask if order_type == self._ORDER_BUY else tick.bid
            request = {
                "action":    _mt5.TRADE_ACTION_DEAL,
                "symbol":    symbol,
                "volume":    lot_size,
                "type":      order_type,
                "price":     price,
                "sl":        sl_price,
                "tp":        tp_price,
                "deviation": self._deviation,
                "magic":     self._magic,
                "comment":   comment,
                "type_time": _mt5.ORDER_TIME_GTC,
                "type_filling": _mt5.ORDER_FILLING_IOC,
            }
            result = _mt5.order_send(request)
            if result is None or result.retcode != _mt5.TRADE_RETCODE_DONE:
                logger.warning(
                    "MT5Bridge: order failed — retcode=%s comment=%s",
                    getattr(result, "retcode", "None"),
                    getattr(result, "comment", ""),
                )
                return None
            ticket = result.order
            logger.info("MT5Bridge: order placed — ticket=%d", ticket)
            return ticket
        except Exception as exc:
            logger.warning("MT5Bridge: send_order error: %s", exc)
            return None

    def close_position(self, ticket: int, symbol: str, lot_size: float) -> bool:
        """
        Close an open position by ticket.

        Returns True on success (or dry-run). False on failure.
        """
        if not self._enabled:
            return False

        logger.info(
            "MT5Bridge: %s close ticket=%d symbol=%s lot=%.2f",
            "DRY-RUN" if self._dry_run else "CLOSE",
            ticket, symbol, lot_size,
        )

        if self._dry_run or not _MT5_AVAILABLE:
            return True

        try:
            pos = _mt5.positions_get(ticket=ticket)
            if not pos:
                logger.warning("MT5Bridge: position ticket=%d not found.", ticket)
                return False

            p = pos[0]
            close_type = self._ORDER_SELL if p.type == self._ORDER_BUY else self._ORDER_BUY
            tick = _mt5.symbol_info_tick(p.symbol)
            price = tick.bid if close_type == self._ORDER_SELL else tick.ask

            request = {
                "action":    _mt5.TRADE_ACTION_DEAL,
                "symbol":    p.symbol,
                "volume":    p.volume,
                "type":      close_type,
                "position":  ticket,
                "price":     price,
                "deviation": self._deviation,
                "magic":     self._magic,
                "comment":   "close:tradelatest",
                "type_time": _mt5.ORDER_TIME_GTC,
                "type_filling": _mt5.ORDER_FILLING_IOC,
            }
            result = _mt5.order_send(request)
            if result is None or result.retcode != _mt5.TRADE_RETCODE_DONE:
                logger.warning(
                    "MT5Bridge: close failed — retcode=%s",
                    getattr(result, "retcode", "None"),
                )
                return False
            logger.info("MT5Bridge: position closed — ticket=%d", ticket)
            return True
        except Exception as exc:
            logger.warning("MT5Bridge: close_position error: %s", exc)
            return False

    def get_account_info(self) -> dict:
        """Return account snapshot. Returns empty dict on error."""
        if self._dry_run or not _MT5_AVAILABLE:
            return {"balance": 0.0, "equity": 0.0, "margin": 0.0, "dry_run": True}
        try:
            info = _mt5.account_info()
            if info is None:
                return {}
            return {
                "balance": info.balance,
                "equity":  info.equity,
                "margin":  info.margin,
                "profit":  info.profit,
                "currency": info.currency,
            }
        except Exception as exc:
            logger.warning("MT5Bridge: get_account_info error: %s", exc)
            return {}
