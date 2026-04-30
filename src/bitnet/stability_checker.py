"""
bitnet/stability_checker.py
============================
Checks zone stability across temporal data splits.

A zone that only works in one time period is overfit.
A zone that works across multiple consecutive periods is robust.

Strategy
--------
  1. Split dataset into N temporal chunks (preserving time order)
  2. Evaluate zone metrics on each chunk independently
  3. Check consistency: std of avg_rr across chunks must be below threshold
  4. Check positive rate: avg_rr must be positive in >= MIN_POSITIVE_SPLITS chunks

Penalises
---------
  - High variance across splits (classic overfit signal)
  - Zones that are only positive in 1–2 of 5 time periods
  - Zones with too few trades per split to be statistically reliable

Anti-overfitting safeguards
---------------------------
  - σ lower bound enforced in search_engine (no needle-thin zones)
  - Minimum 10 trades per split before split counts towards stability
  - Stability score returned (0–1) allows ranking of stable zones
"""

from __future__ import annotations

import math
from typing import List, Tuple


class StabilityChecker:
    """
    Evaluates zone performance across temporal data splits.

    Class constants (override via subclass for custom thresholds):
      N_SPLITS              : number of temporal chunks
      MIN_TRADES_PER_SPLIT  : minimum trades in a split for it to count
      MAX_RR_STD            : maximum allowed std of avg_rr across valid splits
      MIN_POSITIVE_SPLITS   : minimum number of splits where avg_rr > 0
    """

    N_SPLITS             = 5
    MIN_TRADES_PER_SPLIT = 10
    MAX_RR_STD           = 0.80   # if std > this, zone is too volatile
    MIN_POSITIVE_SPLITS  = 3      # must profit in at least 3 of 5 splits

    @classmethod
    def check(
        cls,
        X:         List[List[float]],
        y_rr:      List[float],
        y_win:     List[int],
        candidate,
        n_splits:  int = None,
    ) -> Tuple[bool, float, List[dict]]:
        """
        Evaluate candidate zone stability across temporal splits.

        Parameters
        ----------
        X         : feature matrix (time-ordered)
        y_rr      : RR targets
        y_win     : win labels
        candidate : ZoneCandidate with mu, sigma, weights, threshold
        n_splits  : override number of splits (default: cls.N_SPLITS)

        Returns
        -------
        (stable: bool, stability_score: float, split_metrics: List[dict])

        stable           : True if zone passes all consistency checks
        stability_score  : 0–1, higher = more temporally consistent
        split_metrics    : per-split metric dicts for inspection/logging
        """
        # Lazy import to avoid circular dependency
        from bitnet.search_engine import _evaluate_subset

        n_splits = n_splits or cls.N_SPLITS
        n = len(X)

        # Dataset too small to split meaningfully — pass with neutral score
        if n < n_splits * cls.MIN_TRADES_PER_SPLIT:
            return True, 0.50, []

        chunk_size = n // n_splits
        split_metrics: List[dict] = []

        for i in range(n_splits):
            start = i * chunk_size
            end   = (i + 1) * chunk_size if i < n_splits - 1 else n

            m = _evaluate_subset(
                X[start:end],
                y_rr[start:end],
                y_win[start:end],
                candidate,
            )
            split_metrics.append(m)

        # Collect avg_rr values only from splits with enough trades
        rr_values = [
            m["avg_rr"]
            for m in split_metrics
            if m["trade_count"] >= cls.MIN_TRADES_PER_SPLIT
        ]

        if len(rr_values) < 2:
            # Insufficient data to assess stability — neutral pass
            return True, 0.40, split_metrics

        # ── Statistics ────────────────────────────────────────────────────
        mean_rr  = sum(rr_values) / len(rr_values)
        variance = sum((r - mean_rr) ** 2 for r in rr_values) / len(rr_values)
        std_rr   = math.sqrt(variance)

        n_positive = sum(1 for r in rr_values if r > 0)

        # ── Rejection checks ──────────────────────────────────────────────
        if std_rr > cls.MAX_RR_STD:
            # Too volatile across time periods
            stability_score = max(0.0, 1.0 - std_rr / (cls.MAX_RR_STD * 2))
            return False, round(stability_score, 4), split_metrics

        if n_positive < cls.MIN_POSITIVE_SPLITS:
            # Not consistently profitable across time periods
            stability_score = n_positive / cls.N_SPLITS
            return False, round(stability_score, 4), split_metrics

        # ── Stability score (0–1) ─────────────────────────────────────────
        # Reward: low variance + high positive split ratio
        # Penalise: high std, few positive splits
        consistency    = n_positive / len(rr_values)  # fraction of positive splits
        variance_score = max(0.0, 1.0 - std_rr / cls.MAX_RR_STD)
        stability_score = consistency * variance_score
        stability_score = round(min(1.0, max(0.0, stability_score)), 4)

        return True, stability_score, split_metrics

    @classmethod
    def stability_score_only(
        cls,
        X: List[List[float]],
        y_rr: List[float],
        y_win: List[int],
        candidate,
    ) -> float:
        """Convenience: returns only the stability score (0–1)."""
        _, score, _ = cls.check(X, y_rr, y_win, candidate)
        return score