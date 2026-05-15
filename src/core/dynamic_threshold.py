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

# ── Constants (tuned via configs/production/v1_multi_2026_03.json → decision_engine) ──
_THRESHOLD_PERCENTILE: int   = 85     # percentile used for threshold computation
_THRESHOLD_MIN:        float = 0.45   # floor clamp
_THRESHOLD_MAX:        float = 0.65   # ceiling clamp


class DynamicThreshold:
    """
    Percentile-based threshold: threshold = percentile(scores, 85),
    clamped to [0.45, 0.65]. Returns 0.55 (midpoint) until history exists.

    Parameters
    ----------
    window : int
        Maximum number of scores to retain in the sliding window (default 1000).
    """

    def __init__(self, window: int = 1000) -> None:
        self._scores: deque[float] = deque(maxlen=window)

    def update(self, score: float) -> None:
        """Add a new score to the sliding window."""
        self._scores.append(score)

    def compute(self) -> float:
        """
        Return the current adaptive threshold.

        Returns the midpoint of [_THRESHOLD_MIN, _THRESHOLD_MAX] when the
        window is empty (no history yet).
        """
        if not self._scores:
            return (_THRESHOLD_MIN + _THRESHOLD_MAX) / 2.0
        sorted_scores = sorted(self._scores)
        n   = len(sorted_scores)
        idx = min(int(n * _THRESHOLD_PERCENTILE / 100), n - 1)
        raw = sorted_scores[idx]
        return max(_THRESHOLD_MIN, min(_THRESHOLD_MAX, raw))

    @property
    def n_samples(self) -> int:
        """Number of scores currently in the window."""
        return len(self._scores)
