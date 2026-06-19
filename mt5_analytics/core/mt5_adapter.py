"""
mt5_adapter — the ONLY place the analytics layer touches MetaTrader 5, READ-ONLY.

Exposes exactly five read calls — `history_deals_get`, `history_orders_get`,
`positions_get`, `account_info`, `copy_rates_range`. It deliberately exposes **no**
`order_send` / `position_*` mutation: the analytics layer is fail-closed w.r.t.
execution (it cannot send orders, modify positions, or change SL/TP).

Import-guard + connection lifecycle mirror `src/inout/mt5_candle_fetcher.py`: fail-soft
import at module load, fail-fast at use. Use as a context manager so initialize/shutdown
are paired:

    with MT5Adapter() as mt5a:
        deals = mt5a.history_deals_get(from_dt, to_dt)
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Sequence

logger = logging.getLogger("mt5_analytics.mt5_adapter")

# Optional dependency: fail-soft import, fail-fast at construction/connect.
try:
    import MetaTrader5 as mt5  # type: ignore
    _MT5_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when the wheel is absent
    mt5 = None  # type: ignore
    _MT5_AVAILABLE = False


def _as_dicts(raw: Any) -> list[dict]:
    """Normalize MT5 namedtuple results to plain dicts (None/empty -> [])."""
    if not raw:
        return []
    out: list[dict] = []
    for item in raw:
        if hasattr(item, "_asdict"):
            out.append(dict(item._asdict()))
        elif isinstance(item, dict):
            out.append(item)
    return out


# ── server↔UTC offset (pure, CI-testable) ──────────────────────────────────────
# MT5 reports deal/candle `time` as the trade SERVER's wall clock expressed as a Unix
# epoch (e.g. MetaQuotes-Demo = EET/EEST, UTC+2/+3), NOT true UTC. We detect the offset
# once and normalize EVERY timestamp to true UTC below the feature layer, so deal↔candle
# alignment (hence reconstruction / MFE / duration) is unchanged while session/hour
# features become correct. `server = UTC + offset` ⇒ add offset to query bounds, subtract
# from returned times.
def detect_offset_seconds(
    server_epoch: int, utc_now_epoch: int, *, round_to: int = 1800, max_abs: int = 18 * 3600
) -> "int | None":
    """Offset (server − UTC) in seconds from a live server timestamp vs real UTC now.

    Rounded to `round_to` (default 30 min). Returns None when the gap exceeds `max_abs`
    (a stale tick on a closed market) — the caller then falls back to 0 / config.
    """
    raw = int(server_epoch) - int(utc_now_epoch)
    if abs(raw) > max_abs:
        return None
    return int(round(raw / round_to) * round_to)


class MT5Adapter:
    """Read-only, context-managed wrapper over a running MT5 terminal (UTC-normalized)."""

    _DETECT_SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD")
    # mt5.initialize()/shutdown() are PROCESS-GLOBAL, so nested `with MT5Adapter()` blocks
    # (e.g. a harness adapter that also calls rebuild.run, which opens its own) must be
    # reference-counted: initialize once on the outermost enter, shutdown only on last exit.
    _refcount = 0

    def __init__(self, *, server_utc_offset_hours: "float | None" = None) -> None:
        if not _MT5_AVAILABLE or mt5 is None:
            raise RuntimeError(
                "MetaTrader5 package not installed. Run: pip install MetaTrader5"
            )
        self._connected = False
        self._override = server_utc_offset_hours
        self.server_utc_offset = 0   # seconds; set on __enter__

    # ── lifecycle ──────────────────────────────────────────────────────────────
    def __enter__(self) -> "MT5Adapter":
        if MT5Adapter._refcount == 0:
            if not mt5.initialize():
                raise RuntimeError(
                    f"MT5 initialize() failed: {mt5.last_error()}. "
                    "Is the MetaTrader 5 terminal running and logged in?"
                )
        MT5Adapter._refcount += 1
        self._connected = True
        self.server_utc_offset = self._resolve_offset()
        logger.info("MT5 server-UTC offset = %+d s (%.1f h)",
                   self.server_utc_offset, self.server_utc_offset / 3600.0)
        return self

    def _resolve_offset(self) -> int:
        if self._override is not None:
            return int(round(float(self._override) * 3600))
        now = int(_dt.datetime.now(_dt.timezone.utc).timestamp())
        for sym in self._DETECT_SYMBOLS:
            tick = mt5.symbol_info_tick(sym)
            t = getattr(tick, "time", 0) if tick else 0
            if t:
                off = detect_offset_seconds(int(t), now)
                if off is not None:
                    return off
        logger.warning("MT5 offset auto-detect failed (stale/closed market) -> 0")
        return 0

    def _shift(self, d: _dt.datetime) -> _dt.datetime:
        """UTC datetime -> server-time datetime for an MT5 query bound."""
        return d + _dt.timedelta(seconds=self.server_utc_offset)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._connected:
            MT5Adapter._refcount = max(0, MT5Adapter._refcount - 1)
            if MT5Adapter._refcount == 0:
                mt5.shutdown()
            self._connected = False

    # ── read-only API ──────────────────────────────────────────────────────────
    def history_deals_get(
        self, date_from: _dt.datetime, date_to: _dt.datetime
    ) -> list[dict]:
        """Closed deals in UTC [date_from, date_to]; `time` normalized to true UTC epoch."""
        off = self.server_utc_offset
        deals = _as_dicts(mt5.history_deals_get(self._shift(date_from), self._shift(date_to)))
        for d in deals:
            if d.get("time"):
                d["time"] = int(d["time"]) - off
        return deals

    def history_orders_get(
        self, date_from: _dt.datetime, date_to: _dt.datetime
    ) -> list[dict]:
        """Historical orders in UTC [date_from, date_to]; time fields normalized to UTC."""
        off = self.server_utc_offset
        orders = _as_dicts(mt5.history_orders_get(self._shift(date_from), self._shift(date_to)))
        for o in orders:
            for k in ("time_setup", "time_done"):
                if o.get(k):
                    o[k] = int(o[k]) - off
        return orders

    def positions_get(self, symbol: "str | None" = None) -> list[dict]:
        """Snapshot of currently OPEN positions (read-only operational awareness)."""
        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return _as_dicts(raw)

    def open_position_ids(self) -> frozenset[int]:
        """The set of position_ids currently open — feeds the completion guard."""
        return frozenset(int(p["identifier"]) for p in self.positions_get()
                         if "identifier" in p)

    def account_info(self) -> dict:
        """Ephemeral account snapshot (balance/equity/margin) — never persisted as truth."""
        info = mt5.account_info()
        return dict(info._asdict()) if info is not None else {}

    def copy_rates_range(
        self, symbol: str, timeframe: Any, date_from: _dt.datetime, date_to: _dt.datetime
    ) -> list[dict]:
        """OHLCV bars for UTC [date_from, date_to] as dicts; `time` normalized to UTC epoch."""
        off = self.server_utc_offset
        rates = mt5.copy_rates_range(symbol, timeframe, self._shift(date_from), self._shift(date_to))
        if rates is None:
            return []
        return [
            {
                "time": int(r["time"]) - off,
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "tick_volume": float(r["tick_volume"]),
            }
            for r in rates
        ]
