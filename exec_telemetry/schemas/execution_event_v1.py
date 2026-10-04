"""
execution_event_v1 — the frozen schema for one order-send execution event.

Same discipline as `DealRecord` / `PositionEpisode` / `FeatureRecord`: a typed, frozen value
object so the JSONL log never degrades into ad-hoc dicts → silent drift → broken reports. One
`ExecutionEvent` is captured per `order_send` at execution time (the only moment these facts
exist). Field evolution bumps SCHEMA_VERSION.

OPERATIONAL-ONLY: this carries execution-quality facts (slippage / latency / retcode), NEVER
profit / expectancy / R — those are the truth + insight engines' domain.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

SCHEMA_VERSION = "1.0"

# MT5 trade-server retcodes seen / expected in this repo (validation history). Anything else →
# "UNKNOWN_<code>". Shared by the producer (capture) and the report (histogram) so the names
# can never drift apart.
RETCODE_NAMES: dict[int, str] = {
    10004: "REQUOTE",
    10006: "REJECT",
    10009: "DONE",
    10013: "INVALID_REQUEST",
    10014: "INVALID_VOLUME",
    10015: "INVALID_PRICE",
    10016: "INVALID_STOPS",
    10018: "MARKET_CLOSED",
    10019: "NO_MONEY",
    10021: "PRICE_OFF",
    10027: "CLIENT_DISABLES_AT",   # AutoTrading toggle off
    10030: "INVALID_FILL",
    10031: "CONNECTION",
}


def retcode_name(code: "int | None") -> str:
    if code is None:
        return "NO_RESULT"
    return RETCODE_NAMES.get(int(code), f"UNKNOWN_{code}")


@dataclass(frozen=True)
class ExecutionEvent:
    """One order_send attempt's execution-time facts (self-describing per row)."""

    ts: str                    # ISO-8601 UTC (str, JSONL-safe — mirrors PositionEpisode.entry_time)
    broker_fingerprint: str    # sha256(company|server|login)
    company: str
    server: str
    login: int
    margin_mode: int           # on the row, not just the dir → row is self-describing out of partition
    symbol: str
    side: str                  # "buy" | "sell"
    requested_price: float     # pre-send tick (ask for buy, bid for sell)
    filled_price: float        # result.price (0.0 when the order did not fill)
    slippage_points: float     # signed (filled - requested) / point; 0.0 when not filled
    latency_ms: float          # send → return wall time
    retcode: int
    retcode_name: str
    filling_mode: str          # "FOK" | "IOC" | "RETURN"
    volume: float              # requested lot
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)
