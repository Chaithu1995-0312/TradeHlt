"""
core/feature_store.py
Canonical feature store – single source of truth for all feature dictionaries.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Deque

from features.feature_schema import CANONICAL_FEATURES
from features.schema_validator import validate_features

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeatureFrame:
    """Immutable feature snapshot at a given candle index."""
    candle_idx: int
    timestamp: Any          # datetime or int (Unix timestamp)
    features: Dict[str, float]
    integrity: str = "real"

    def to_dict(self) -> Dict:
        """Convert to JSON‑serialisable dict for logging."""
        ts = self.timestamp
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        return {
            "candle_idx": self.candle_idx,
            "timestamp": ts,
            "features": self.features,
            "_data_integrity": self.integrity,
        }


class FeatureStore:
    """
    Validates and stores canonical feature frames.
    Injects the data integrity sentinel at the pipeline boundary.
    Computes derived features that depend on history (e.g., double_sweep).
    """

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._history: Deque[FeatureFrame] = deque(maxlen=max_history)
        self._liquidity_sweep_history: Deque[int] = deque(maxlen=10)

    def process(
        self,
        candle_idx: int,
        timestamp: Any,
        ohlcv: Dict[str, float],
        auxiliary: Optional[Dict[str, float]] = None,
    ) -> FeatureFrame:
        """
        Main entry point.

        Args:
            candle_idx: 0‑based index of the candle.
            timestamp: datetime or numeric timestamp.
            ohlcv: must contain 'open', 'high', 'low', 'close', 'volume'.
            auxiliary: any pre‑computed features (e.g., atr, ema_fast, etc.).

        Returns:
            FeatureFrame with all 33 canonical features and integrity sentinel.
        """
        raw = self._merge_inputs(ohlcv, auxiliary or {})
        self._ensure_required(raw)
        self._compute_derived(raw, candle_idx)
        self._validate_schema(raw)
        raw["_data_integrity"] = "real"
        if "volume_ratio" not in raw:
            raw["volume_ratio"] = 1.0
        if "double_sweep" not in raw:
            raw["double_sweep"] = 0
        frame = FeatureFrame(
            candle_idx=candle_idx,
            timestamp=timestamp,
            features=raw,
            integrity="real",
        )
        self._history.append(frame)
        return frame

    def get_history(self, lookback: int) -> List[FeatureFrame]:
        """Return last N frames (most recent last)."""
        return list(self._history)[-lookback:]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _merge_inputs(self, ohlcv: Dict, auxiliary: Dict) -> Dict:
        merged = ohlcv.copy()
        for k, v in auxiliary.items():
            if k not in merged:
                merged[k] = v
        return merged

    def _ensure_required(self, d: Dict) -> None:
        """Check that raw required fields are present."""
        required = {"open", "high", "low", "close", "volume", "atr", "ema_fast", "ema_slow", "session"}
        missing = required - set(d.keys())
        if missing:
            raise ValueError(f"FeatureStore: missing required fields: {missing}")

    def _compute_derived(self, d: Dict, candle_idx: int) -> None:
        """Compute derived canonical features that are not supplied directly."""
        # double_sweep: both positive and negative liquidity_sweep in recent history
        if "liquidity_sweep" in d:
            try:
                val = int(d["liquidity_sweep"])
                self._liquidity_sweep_history.append(val)
            except (TypeError, ValueError):
                pass  # ignore non-numeric

        # Only compute if we have at least one numeric value
        if self._liquidity_sweep_history:
            has_pos = any(v > 0 for v in self._liquidity_sweep_history if isinstance(v, (int, float)))
            has_neg = any(v < 0 for v in self._liquidity_sweep_history if isinstance(v, (int, float)))
            d["double_sweep"] = 1 if (has_pos and has_neg) else 0
        else:
            d["double_sweep"] = 0

    # Ensure volume_ratio is present
        if "volume_ratio" not in d:
            d["volume_ratio"] = 1.0
            logger.warning("volume_ratio missing, set to 1.0")

    def _validate_schema(self, d: Dict) -> None:
        """Ensure all canonical keys are present and types are correct."""
        missing = [k for k in CANONICAL_FEATURES if k not in d]
        if missing:
            raise ValueError(f"FeatureStore: missing canonical keys: {missing}")
        # Reuse existing validator (type checks, etc.)
        validate_features(d, CANONICAL_FEATURES)