# ARCHIVED 2026-04-28 — Dead Code Pass
# Reason: zero importers in active src/; journal subpackage has no production callers.
# Original: src/journal/schema.py
# Action required on original: remove src/journal/schema.py
# schema.py — TradeRecord dataclass
from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class TradeRecord:
    """Complete trade record capturing decision context + outcome."""
    trade_id: str
    timestamp: str
    symbol: str
    regime: str = ""
    config_profile: str = ""
    confidence: float = 0.0
    rr: float = 0.0
    zone: float = 0.0
    allocated_risk: float = 0.0
    portfolio_exposure_before: float = 0.0
    engine_action: str = ""
    override_action: str = ""
    result: str = ""
    pnl: float = 0.0
    duration_candles: int = 0
    drawdown_at_entry: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "TradeRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
