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


class FeatureValidationError(ValueError):
    """Raised by FeatureStore.validate_or_raise() on schema mismatch."""


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
    Computes derived features that depend on history.

    FC1-A: structure/sweep/liquidity dims are re-derived from OHLCV history
    via delayed-confirmed (causal) publication so live matches batch production
    semantics (available_at=t+k). Feeder zeros or centered values are overwritten.
    """

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._history: Deque[FeatureFrame] = deque(maxlen=max_history)
        # T-7 (2026-07-19): this ring feeds causal_structure_at_bar's double_sweep window, so it
        # must never be SHORTER than that window or live would silently truncate a lookback the
        # batch path honors — the same split-brain T-7 closed one level up. Floor of 10 keeps
        # today's behavior byte-identical (config value is 5).
        # Function-local import: same deferred-edge convention as the causal_structure_at_bar
        # call site below (avoids a module-level core -> features -> config_layer chain).
        from features.feature_pipeline import resolve_double_sweep_window
        _ds_window = resolve_double_sweep_window()
        self._liquidity_sweep_history: Deque[int] = deque(maxlen=max(10, _ds_window))
        # OHLCV(+atr) ring for causal structure (FC1-A live contract)
        self._ohlcv_hist: Deque[Dict[str, float]] = deque(maxlen=max_history)

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
            FeatureFrame with every CANONICAL_FEATURES key and the integrity sentinel.
            (48 names under schema v5.0, F-076 — `_validate_schema` checks against the constant,
            never a literal; this docstring said "33" from the v2.0 era.)
        """
        raw = self._merge_inputs(ohlcv, auxiliary or {})
        self._ensure_required(raw)
        # FC1-A: publish delayed-confirmed structure from history (same as batch)
        self._apply_causal_structure(raw, ohlcv)
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

    def _apply_causal_structure(self, d: Dict, ohlcv: Dict[str, float]) -> None:
        """Overwrite structure dims with FC1-A delayed-confirmed values from OHLCV history."""
        atr = float(d.get("atr", 0.0) or 0.0)
        self._ohlcv_hist.append(
            {
                "high": float(ohlcv["high"]),
                "low": float(ohlcv["low"]),
                "close": float(ohlcv["close"]),
                "atr": atr,
            }
        )
        try:
            from features.causal_structure import causal_structure_at_bar

            highs = [r["high"] for r in self._ohlcv_hist]
            lows = [r["low"] for r in self._ohlcv_hist]
            closes = [r["close"] for r in self._ohlcv_hist]
            atrs = [r["atr"] for r in self._ohlcv_hist]
            struct = causal_structure_at_bar(
                highs, lows, closes, atrs,
                liquidity_sweep_history=list(self._liquidity_sweep_history),
            )
            # Only CANONICAL structure keys — skip internal _last_swing_* helpers
            for key, val in struct.items():
                if key.startswith("_"):
                    continue
                d[key] = val
        except Exception as exc:
            logger.warning("FeatureStore: causal structure failed (%s); leaving feeder values", exc)

    def _compute_derived(self, d: Dict, candle_idx: int) -> None:
        """Compute derived canonical features that are not supplied directly."""
        # double_sweep: prefer causal_structure result; still track history for callers
        if "liquidity_sweep" in d:
            try:
                val = int(d["liquidity_sweep"])
                self._liquidity_sweep_history.append(val)
            except (TypeError, ValueError):
                pass  # ignore non-numeric

        # If causal_structure already set double_sweep, keep it; else derive from history
        if "double_sweep" not in d or d.get("double_sweep") is None:
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

    def validate_or_raise(self, features: Dict) -> None:
        """
        Public contract enforcer — call before passing any feature dict to an engine.
        Raises FeatureValidationError (subclass of ValueError) on schema mismatch.
        """
        missing = [k for k in CANONICAL_FEATURES if k not in features]
        if missing:
            raise FeatureValidationError(
                f"FeatureStore: missing canonical keys: {missing}"
            )
        validate_features(features, CANONICAL_FEATURES)

    def _validate_schema(self, d: Dict) -> None:
        """Internal schema check used by process()."""
        missing = [k for k in CANONICAL_FEATURES if k not in d]
        if missing:
            raise ValueError(f"FeatureStore: missing canonical keys: {missing}")
        validate_features(d, CANONICAL_FEATURES)