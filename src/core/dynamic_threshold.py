"""
dynamic_threshold.py
═══════════════════════════════════════════════════════════════════════════════
Percentile-based adaptive threshold for the CRT decision engine.

Extracted from decision_engine.py. ``DecisionEngine`` imports this class;
new code should import it directly from here.

Public API
----------
  DynamicThreshold          — percentile-based threshold with sliding window
"""

from __future__ import annotations

from collections import deque

# Config-first (no silent defaults): the percentile + clamp bounds are BEHAVIORAL
# knobs supplied by the caller from configs/production → decision_engine
# (threshold_percentile / threshold_min / threshold_max). There is intentionally NO
# module-level default — a missing value must fail fast at the config boundary
# (DecisionEngine._require_decision_cfg), never be silently guessed here.


class DynamicThreshold:
    """
    Percentile-based threshold: threshold = percentile(scores, ``percentile``),
    clamped to [``t_min``, ``t_max``]. Returns the clamp midpoint until history exists.

    Parameters
    ----------
    window : int
        Maximum number of scores to retain in the sliding window (default 1000).
    percentile, t_min, t_max : required keyword-only BEHAVIORAL knobs
        Sourced from the ``decision_engine`` config section. Required (no defaults)
        so behaviour can never silently diverge from the active config.
    """

    def __init__(
        self,
        window: int = 1000,
        *,
        percentile: int,
        t_min: float,
        t_max: float,
    ) -> None:
        self._scores: deque[float] = deque(maxlen=window)
        self._percentile = int(percentile)
        self._t_min = float(t_min)
        self._t_max = float(t_max)

    def update(self, score: float) -> None:
        """Add a new score to the sliding window."""
        self._scores.append(score)

    def compute(self) -> float:
        """
        Return the current adaptive threshold.

        Returns the midpoint of [t_min, t_max] when the window is empty (no history).
        """
        if not self._scores:
            return (self._t_min + self._t_max) / 2.0
        sorted_scores = sorted(self._scores)
        n   = len(sorted_scores)
        idx = min(int(n * self._percentile / 100), n - 1)
        raw = sorted_scores[idx]
        return max(self._t_min, min(self._t_max, raw))

    @property
    def n_samples(self) -> int:
        """Number of scores currently in the window."""
        return len(self._scores)
