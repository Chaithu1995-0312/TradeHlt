"""
timing_advisor.py
=================
Consumer-facing read API for the Pattern Timing Library (Phase 1, measure-only).

This is the single contract the two timing consumers read — kept DORMANT
(advisory-only, weight 0.0) until the 1c incremental-edge gate clears in Phase 2:

  (A) Early-invalidation / abnormality exit  ->  abnormality(...)   [PRIMARY]
  (B) Scanner ranking (capital efficiency)   ->  rank_score(...)    [SECONDARY]

Doctrine:
  - Fail-open: a missing/corrupt library or unknown cluster yields a NEUTRAL,
    zero-weight result. It can never block or trigger anything (LLM/advisory
    isolation invariant — same posture as the rest of the advisory layer).
  - Pure read: no I/O after load; deterministic.
  - This module is also the home of the cluster-key construction so the
    aggregator (scripts/analysis/build_pattern_library.py) and any live consumer
    bucket identically.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("TimingAdvisor")

# body_ratio tercile thresholds (body_ratio is a normalized feature in [0,1]).
_BODY_LO, _BODY_HI = 0.33, 0.66


def geometry_bucket(features: dict) -> str:
    br = float(features.get("body_ratio", 0.0) or 0.0)
    if br < _BODY_LO:
        return "body_lo"
    if br < _BODY_HI:
        return "body_mid"
    return "body_hi"


def cluster_key(direction: str, session: int, vol_regime: int, geo: str) -> str:
    return f"dir={direction}|sess={session}|vreg={vol_regime}|geo={geo}"


def cluster_key_from_features(direction: str, features: dict) -> str:
    return cluster_key(
        direction,
        int(float(features.get("session", -1))),
        int(float(features.get("volatility_regime", -1))),
        geometry_bucket(features),
    )


class TimingAdvisor:
    """Read-only view over a pattern_library_<instrument>.json artifact."""

    def __init__(self, library: Optional[dict]):
        self._lib = library or {}
        self._cells: Dict[str, dict] = self._lib.get("cells", {}) or {}
        # Precompute expectancy_per_candle range for rank normalization.
        epcs = [c["expectancy_per_candle"] for c in self._cells.values()
                if c.get("expectancy_per_candle") is not None]
        self._epc_min = min(epcs) if epcs else 0.0
        self._epc_max = max(epcs) if epcs else 0.0

    @classmethod
    def from_path(cls, path: "str | Path") -> "TimingAdvisor":
        """Load a library JSON; fail-open to an empty (neutral) advisor."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("TimingAdvisor: cannot load %s (%s); neutral mode", path, exc)
            data = {}
        return cls(data)

    @property
    def loaded(self) -> bool:
        return bool(self._cells)

    # ── (B) Ranking: capital-efficiency score in [0,1], neutral 0.0 ──────────
    def rank_score(self, key: str) -> float:
        cell = self._cells.get(key)
        if not cell or cell.get("expectancy_per_candle") is None:
            return 0.0
        span = self._epc_max - self._epc_min
        if span <= 0:
            return 0.0
        return round((cell["expectancy_per_candle"] - self._epc_min) / span, 4)

    # ── (A) Early-invalidation: abnormality advisory (weight 0.0) ────────────
    def abnormality(self, key: str, candles_since_entry: int,
                    reached_025R: bool,
                    *, win_rate_floor: float = 0.5) -> dict:
        """Advisory (non-binding) read of the cluster's win-rate-decay curve.

        Returns the empirical conditional win-rate for a live trade that has
        gone `candles_since_entry` bars without (or with) reaching +0.25R.
        `enabled` is always False in Phase 1 — advisory-only, weight 0.0.
        """
        neutral = {
            "advisory": "NEUTRAL", "flag_abnormal": False,
            "conditional_win_rate": None, "weight": 0.0,
            "enabled": False, "reason": "no_cluster",
        }
        cell = self._cells.get(key)
        if not cell:
            return neutral
        decay = cell.get("winrate_decay_on_025R", {})
        if reached_025R:
            return {**neutral, "reason": "reached_025R",
                    "conditional_win_rate": cell.get("win_rate")}
        # Pick the largest checkpoint <= candles_since_entry.
        ks = sorted(int(k) for k in decay)
        chosen = None
        for k in ks:
            if k <= candles_since_entry:
                chosen = k
        if chosen is None:
            return {**neutral, "reason": "too_early"}
        cwr = decay[str(chosen)].get("win_rate_if_not_by_k")
        return {
            "advisory": "ABNORMAL" if (cwr is not None and cwr < win_rate_floor) else "NORMAL",
            "flag_abnormal": bool(cwr is not None and cwr < win_rate_floor),
            "conditional_win_rate": cwr,
            "checkpoint_candle": chosen,
            "weight": 0.0,           # DORMANT — advisory only in Phase 1
            "enabled": False,
            "reason": "decay_curve",
        }
