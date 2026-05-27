"""
strategy_intent.py
================================================================================
StrategyIntent — typed hypothesis contract produced by StrategyIntentBuilder
for every non-NO_TRADE StrategyResult.

Design goals:
  - All strategies produce a StrategyIntent, not just S01.
    Replay learns from ALL strategies' hypotheses, preventing S01 dominance.
  - Evidence is lazy (Callable), materialised only on .evidence access or
    to_dict() — prevents ~90 strategies × evidence strings × every candle.
  - InvalidationRule is machine-executable — no NLP parsing required.
  - source_path_hash encodes the CRT path (from_state:to_state:sweep_type:disp)
    so replay can group patterns even when state names are identical.

Architecture invariant:
  StrategyOrchestrator MUST NEVER mutate CRT state.
  CRT MUST NEVER know strategy outcome.
================================================================================
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class InvalidationRule:
    """Machine-executable invalidation condition.

    Evaluated every candle after hypothesis is formed.  No NLP parsing required.

    Example:
        InvalidationRule("close", "<", 1.2345, "price closed below entry - 1×ATR")
    """
    field:       str    # feature name, e.g. "disp_strength", "retest_depth", "close"
    op:          str    # "<" | ">" | ">=" | "<=" | "=="
    value:       float  # comparison threshold
    description: str = ""

    def is_violated(self, features: dict) -> bool:
        """Return True when this rule's condition is met (hypothesis invalidated)."""
        v = features.get(self.field)
        if v is None:
            return False
        try:
            v = float(v)
        except (TypeError, ValueError):
            return False
        return {
            "<":  v < self.value,
            ">":  v > self.value,
            ">=": v >= self.value,
            "<=": v <= self.value,
            "==": v == self.value,
        }.get(self.op, False)

    def to_dict(self) -> dict:
        return {
            "field":       self.field,
            "op":          self.op,
            "value":       self.value,
            "description": self.description,
        }


@dataclass
class StrategyIntent:
    """
    Typed hypothesis emitted by StrategyIntentBuilder for each non-NO_TRADE result.

    Fields
    ------
    strategy_id       Originating strategy code (S1..S10).
    strategy_family   Family label for family-level replay expectancy (sparse-sample
                      safety): "CRT" | "ZONE" | "BITNET" | "MOMENTUM" | etc.
    direction         1=BUY, -1=SELL, 0=NEUTRAL.
    confidence        [0.0, 1.0] — copied from StrategyResult.
    invalidation      Machine-executable exit conditions (geometry-based).
    expected_rr       abs((tp-entry)/(entry-sl)).
    ttl               Candles before hypothesis expires (default 3).
    source_path_hash  SHA-256[:16] of "from:to:sweep_type:disp_strength" path —
                      includes sweep_type + disp_strength to prevent state-name
                      collisions (RANGE→SWEEP is different for TYPE-A vs TYPE-B).
    _evidence_factory Lazy callable — materialised only on .evidence access or
                      to_dict().  Prevents unbounded per-candle allocation.
    """
    strategy_id:      str
    strategy_family:  str                        # "CRT" | "ZONE" | "BITNET" | etc.
    direction:        int                        # 1=BUY, -1=SELL, 0=NEUTRAL
    confidence:       float                      # [0.0, 1.0]
    invalidation:     List[InvalidationRule]     # machine-executable exit conditions
    expected_rr:      float                      # abs((tp-entry)/(entry-sl))
    ttl:              int                        # candles before hypothesis expires
    source_path_hash: str = ""                   # SHA-256[:16] of enriched CRT path

    # Lazy evidence factory — evaluated only when the intent is selected for replay,
    # logging, or serialisation.  Not repr'd to keep debug output clean.
    _evidence_factory: Optional[Callable[[], List[str]]] = field(
        default=None, repr=False
    )

    @property
    def evidence(self) -> List[str]:
        """Materialise evidence on first access only."""
        return self._evidence_factory() if self._evidence_factory else []

    def is_valid(self, candles_elapsed: int) -> bool:
        """True while the hypothesis has not yet expired."""
        return self.ttl == 0 or candles_elapsed < self.ttl

    def check_invalidation(self, features: dict) -> Optional[InvalidationRule]:
        """Return the first violated rule, or None if hypothesis is still live."""
        return next(
            (r for r in self.invalidation if r.is_violated(features)), None
        )

    def to_dict(self) -> dict:
        """Serialise to JSON-safe dict.  Materialises evidence at call time."""
        return {
            "strategy_id":      self.strategy_id,
            "strategy_family":  self.strategy_family,
            "direction":        self.direction,
            "confidence":       self.confidence,
            "invalidation":     [r.to_dict() for r in self.invalidation],
            "expected_rr":      self.expected_rr,
            "ttl":              self.ttl,
            "source_path_hash": self.source_path_hash,
            "evidence":         self.evidence,  # materialised here
        }
