"""
strategy_result.py
================================================================================
StrategyResult — universal output contract for all 10 strategy modules.

Every strategy (S1..S10) implements BaseStrategy.compute() and returns one of
these. FusionEngine consumes a list of StrategyResults from active strategies.
================================================================================
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Optional

if TYPE_CHECKING:
    # Imported for type annotations only — avoids circular imports at runtime.
    # At runtime all annotations are strings (from __future__ import annotations).
    from strategies.strategy_intent import StrategyIntent  # noqa: F401

# ── Valid domain values ──────────────────────────────────────────────────────

VALID_INTENTS = frozenset(
    {"BREAKOUT", "PULLBACK", "REVERSAL", "LIQ_SWEEP", "TRAP", "NO_TRADE"}
)
VALID_SIGNALS = frozenset({"BUY", "SELL", "NO_TRADE"})
VALID_REGIMES = frozenset({"TRENDING", "RANGING", "VOLATILE", "BREAKOUT", "UNKNOWN"})
VALID_STRATEGY_IDS = frozenset(
    {"S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"}
)

_MAX_SL_INR = 25_000.0  # hard ceiling enforced by UltronRiskGate capital_management config


@dataclass
class StrategyResult:
    """
    Value object emitted by every strategy module.

    Fields
    ------
    score         Engine-specific scoring value, 0.0–1.0.
    intent        Trade geometry intent (BREAKOUT / PULLBACK / REVERSAL /
                  LIQ_SWEEP / TRAP / NO_TRADE).
    regime        Market condition at signal time.
    signal        Direction: BUY | SELL | NO_TRADE.
    confidence    Calibrated probability estimate, 0.0–1.0.
    entry         Planned entry price.
    sl            Stop-loss price.
    tp            Take-profit price.
    sl_inr        INR risk if SL is hit (must be <= INR 25,000).
    tp_inr        INR gain if TP is hit.
    roi_min       Conservative ROI estimate (%).
    roi_max       Optimistic ROI estimate (%).
    strategy_id   Originating strategy code (S1..S10).
    pair          Instrument symbol (e.g. EURUSD).
    timeframe     Candle timeframe (M1 / M5 / M15 / H1 / H4 / D1).
    ts            ISO-8601 UTC timestamp of the signal candle.
    """

    score:       float
    intent:      str
    regime:      str
    signal:      str
    confidence:  float
    entry:       float
    sl:          float
    tp:          float
    sl_inr:      float
    tp_inr:      float
    roi_min:     float
    roi_max:     float
    strategy_id: str
    pair:        str
    timeframe:   str
    ts:          str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Phase B additions (backward-compatible defaults) ─────────────────────
    # intent_obj: populated by StrategyIntentBuilder in _aggregate(); None until then.
    # capabilities: frozenset emitted by the strategy itself (frozenset is immutable,
    #   hashable, cannot be accidentally mutated after emit).
    #   Strategies that understand CRT transition path emit frozenset({"transition_path"}).
    #   All others use the default frozenset() — NO change to S02-S09 required.
    intent_obj:    Optional["StrategyIntent"] = field(default=None, repr=False)
    capabilities:  FrozenSet[str]             = field(default_factory=frozenset, repr=False)

    # ── Validation ───────────────────────────────────────────────────────────

    def validate(self) -> bool:
        """
        Validates all fields. Raises ValueError on first violation.

        Returns True when valid (callers can use: assert result.validate()).
        """
        errors: list[str] = []

        if not (0.0 <= self.score <= 1.0):
            errors.append(f"score={self.score!r} not in [0, 1]")

        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence={self.confidence!r} not in [0, 1]")

        if self.intent not in VALID_INTENTS:
            errors.append(f"intent={self.intent!r} not in {sorted(VALID_INTENTS)}")

        if self.signal not in VALID_SIGNALS:
            errors.append(f"signal={self.signal!r} not in {sorted(VALID_SIGNALS)}")

        if self.regime not in VALID_REGIMES:
            errors.append(f"regime={self.regime!r} not in {sorted(VALID_REGIMES)}")

        if self.strategy_id not in VALID_STRATEGY_IDS:
            errors.append(
                f"strategy_id={self.strategy_id!r} not in {sorted(VALID_STRATEGY_IDS)}"
            )

        if self.signal == "BUY" and self.entry > 0.0:
            if not (self.sl < self.entry < self.tp):
                errors.append(
                    f"BUY geometry violated: sl={self.sl} < entry={self.entry} < tp={self.tp}"
                )

        if self.signal == "SELL" and self.entry > 0.0:
            if not (self.tp < self.entry < self.sl):
                errors.append(
                    f"SELL geometry violated: tp={self.tp} < entry={self.entry} < sl={self.sl}"
                )

        if self.sl_inr > _MAX_SL_INR:
            errors.append(
                f"sl_inr={self.sl_inr:.2f} exceeds max allowed INR {_MAX_SL_INR:.0f}"
            )

        if self.roi_min > self.roi_max:
            errors.append(
                f"roi_min={self.roi_min} > roi_max={self.roi_max}"
            )

        if errors:
            raise ValueError(
                f"StrategyResult validation failed [{self.strategy_id}]:\n"
                + "\n".join(f"  • {e}" for e in errors)
            )

        return True

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Returns a plain dict safe for JSON serialisation and LLMLogger.

        Phase-B fields (intent_obj, capabilities) are excluded:
        - intent_obj contains a lazy Callable (_evidence_factory) — use
          result.intent_obj.to_dict() explicitly when serialising intents.
        - capabilities is a frozenset — internal-use only, not JSON-safe.
        """
        d = asdict(self)
        d.pop("intent_obj", None)
        d.pop("capabilities", None)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyResult":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    # ── Convenience constructors ─────────────────────────────────────────────

    @classmethod
    def no_trade(
        cls,
        strategy_id: str,
        pair: str,
        timeframe: str,
        regime: str = "UNKNOWN",
    ) -> "StrategyResult":
        """Standard NO_TRADE sentinel — every strategy uses this instead of None."""
        return cls(
            score=0.0,
            intent="NO_TRADE",
            regime=regime,
            signal="NO_TRADE",
            confidence=0.0,
            entry=0.0,
            sl=0.0,
            tp=0.0,
            sl_inr=0.0,
            tp_inr=0.0,
            roi_min=0.0,
            roi_max=0.0,
            strategy_id=strategy_id,
            pair=pair,
            timeframe=timeframe,
        )

    def is_actionable(self) -> bool:
        """True when the result carries a real BUY or SELL signal."""
        return self.signal in ("BUY", "SELL") and self.confidence > 0.0

    def __repr__(self) -> str:
        return (
            f"StrategyResult({self.strategy_id} | {self.signal} | "
            f"{self.pair} {self.timeframe} | conf={self.confidence:.2f} "
            f"| sl_inr=INR{self.sl_inr:.0f})"
        )
