"""
feature_monitor.py
==================
Feature Drift + Distribution Tracking Layer.

Tracks the rolling distribution of canonical features in real-time,
detects anomalous trades via Z-score, and exposes distribution stats
for debugging and training quality control.

Integrates transparently into canonical pipeline â€” no direct callers needed.

USAGE
-----
Standalone:
    from feature_monitor import FeatureMonitor
    monitor = FeatureMonitor(window_size=500)
    monitor.update({"retest_depth": 0.35, "body_ratio": 0.55, "disp_strength": 0.21})
    if monitor.detect_drift(features):
        print("Drift detected!")
    print(monitor.summary())

Via canonical pipeline (recommended):
    from feature_pipeline import FeaturePipeline
    pipeline = FeaturePipeline(df)
    # monitor is updated automatically on every from_trade() call
    print(adapter.monitor.summary())
    if adapter.monitor.detect_drift(features):
        skip_trade()

DRIFT THRESHOLDS
----------------
  Z > 3.0  â†’ HARD drift  (strongly out-of-distribution â€” consider rejecting)
  Z > 2.5  â†’ SOFT drift  (default threshold â€” warning)

NOTES
-----
  - Requires at least 30 samples before drift detection activates.
  - Uses Z-score (standard deviations from rolling mean).
  - Zero-variance features are protected against divide-by-zero.
  - Window is a fixed-size deque (FIFO) â€” memory is bounded.
"""

from __future__ import annotations

import json
import logging
import math
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("FeatureMonitor")

# Canonical feature order (must match canonical 3-feature order)
_CANONICAL = ["retest_depth", "body_ratio", "disp_strength"]

# Minimum samples before drift detection fires
_MIN_SAMPLES_FOR_DRIFT = 30

# Default soft-drift Z-score threshold
DEFAULT_DRIFT_THRESHOLD = 2.5


class FeatureMonitor:
    """
    Rolling-window drift detector and distribution tracker.

    Parameters
    ----------
    window_size : int
        Maximum number of samples to retain in the rolling window (FIFO).
        Older samples are discarded automatically.
    """

    def __init__(
        self,
        window_size: int = 500,
        soft_threshold: float = 2.5,
        hard_threshold: float = 3.0,
    ) -> None:
        self.window_size = window_size
        # Governed drift Z-thresholds (config: feature_monitor.soft_drift_z /
        # hard_drift_z). Stored so detect_drift_severity() honors config rather than
        # its own hardcoded defaults. Defaults here equal the historical literals.
        self.soft_threshold = soft_threshold
        self.hard_threshold = hard_threshold
        self._buffer: deque[List[float]] = deque(maxlen=window_size)
        self._n_drift_detected: int = 0
        self._n_total: int = 0

    # ------------------------------------------------------------------
    def update(self, features: Dict[str, float]) -> None:
        """
        Add a canonical feature dict to the rolling window.

        Args:
            features: dict with keys retest_depth, body_ratio, disp_strength
        """
        row = [
            features.get("retest_depth",  0.0),
            features.get("body_ratio",    0.0),
            features.get("disp_strength", 0.0),
        ]
        self._buffer.append(row)
        self._n_total += 1

    # ------------------------------------------------------------------
    def _compute_stats(self) -> Optional[Tuple[List[float], List[float]]]:
        """
        Compute (mean, std) per feature from the rolling buffer.

        Returns None if the buffer has fewer than _MIN_SAMPLES_FOR_DRIFT samples.
        Std of 0.0 is replaced with 1.0 to prevent divide-by-zero.
        """
        n = len(self._buffer)
        if n < _MIN_SAMPLES_FOR_DRIFT:
            return None

        k = 3  # number of features
        sums   = [0.0] * k
        sums_sq = [0.0] * k

        for row in self._buffer:
            for i in range(k):
                sums[i]    += row[i]
                sums_sq[i] += row[i] * row[i]

        mean = [sums[i] / n for i in range(k)]
        var  = [max(0.0, sums_sq[i] / n - mean[i] ** 2) for i in range(k)]
        std  = [math.sqrt(v) if v > 0.0 else 1.0 for v in var]

        return mean, std

    # ------------------------------------------------------------------
    def detect_drift(
        self,
        features: Dict[str, float],
        threshold: float = DEFAULT_DRIFT_THRESHOLD,
    ) -> bool:
        """
        Return True if any canonical feature is a Z-score outlier.

        Args:
            features:  canonical feature dict
            threshold: Z-score threshold (default 2.5 = soft drift)

        Returns:
            True if drift detected, False otherwise or if too few samples.
        """
        stats = self._compute_stats()
        if stats is None:
            return False  # Not enough data yet

        mean, std = stats
        vals = [
            features.get("retest_depth",  0.0),
            features.get("body_ratio",    0.0),
            features.get("disp_strength", 0.0),
        ]

        for i in range(3):
            z = abs(vals[i] - mean[i]) / std[i]
            if z > threshold:
                self._n_drift_detected += 1
                log.debug(
                    "[FeatureMonitor] Drift on %s: value=%.4f mean=%.4f std=%.4f z=%.2f",
                    _CANONICAL[i], vals[i], mean[i], std[i], z,
                )
                return True

        return False

    # ------------------------------------------------------------------
    def detect_drift_severity(
        self,
        features: Dict[str, float],
        soft_threshold: float | None = None,
        hard_threshold: float | None = None,
    ) -> str:
        """
        Return drift severity: 'none', 'soft', or 'hard'.

        Thresholds default to the instance values (set from config at construction:
        feature_monitor.soft_drift_z / hard_drift_z); pass explicitly to override.

        Args:
            features:       canonical feature dict
            soft_threshold: Z-score for soft drift (default: instance soft_threshold)
            hard_threshold: Z-score for hard drift (default: instance hard_threshold)

        Returns:
            'hard'  â€” strongly out-of-distribution (consider rejecting trade)
            'soft'  â€” mildly out-of-distribution (reduce confidence)
            'none'  â€” within expected distribution
        """
        if soft_threshold is None:
            soft_threshold = self.soft_threshold
        if hard_threshold is None:
            hard_threshold = self.hard_threshold

        stats = self._compute_stats()
        if stats is None:
            return "none"

        mean, std = stats
        vals = [
            features.get("retest_depth",  0.0),
            features.get("body_ratio",    0.0),
            features.get("disp_strength", 0.0),
        ]

        max_z = 0.0
        for i in range(3):
            z = abs(vals[i] - mean[i]) / std[i]
            if z > max_z:
                max_z = z

        if max_z > hard_threshold:
            return "hard"
        if max_z > soft_threshold:
            return "soft"
        return "none"

    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        """
        Return distribution statistics for the current rolling window.

        Returns:
            dict with keys: mean, std, min, max (each a list of 3 floats),
            plus n_samples, n_total, n_drift_detected.
            Returns empty dict if fewer than _MIN_SAMPLES_FOR_DRIFT samples.
        """
        n = len(self._buffer)
        if n < _MIN_SAMPLES_FOR_DRIFT:
            return {
                "n_samples": n,
                "n_total": self._n_total,
                "n_drift_detected": self._n_drift_detected,
                "status": f"insufficient_data (need {_MIN_SAMPLES_FOR_DRIFT})",
            }

        k = 3
        buf_list = list(self._buffer)

        minimums = [min(row[i] for row in buf_list) for i in range(k)]
        maximums = [max(row[i] for row in buf_list) for i in range(k)]

        stats_result = self._compute_stats()
        if stats_result is None:
            return {}
        mean, std = stats_result

        return {
            "features":          _CANONICAL,
            "mean":              [round(v, 6) for v in mean],
            "std":               [round(v, 6) for v in std],
            "min":               [round(v, 6) for v in minimums],
            "max":               [round(v, 6) for v in maximums],
            "n_samples":         n,
            "window_size":       self.window_size,
            "n_total":           self._n_total,
            "n_drift_detected":  self._n_drift_detected,
        }

    # ------------------------------------------------------------------
    def summary(self) -> str:
        """Return a JSON-formatted distribution summary string."""
        return json.dumps(self.stats(), indent=2)

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Clear the rolling buffer and reset counters."""
        self._buffer.clear()
        self._n_drift_detected = 0
        self._n_total = 0

    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return (
            f"FeatureMonitor(window_size={self.window_size}, "
            f"n={len(self._buffer)}, "
            f"n_drift={self._n_drift_detected})"
        )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Self-test
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == "__main__":
    import random
    random.seed(42)

    monitor = FeatureMonitor(window_size=200)

    # Feed 50 normal samples (synthetic fixture noise — bind to intermediates so the
    # governed keys receive TRANSPORTED values; the demo synthesizes inputs, not
    # feature math — feature_math_lint 2026-07-11 hardening)
    for _ in range(50):
        _rd = random.uniform(0.2, 0.6)
        _br = random.uniform(0.4, 0.8)
        _ds = random.uniform(0.1, 0.4)
        monitor.update({
            "retest_depth":  _rd,
            "body_ratio":    _br,
            "disp_strength": _ds,
        })

    print("After 50 normal samples:")
    print(monitor.summary())
    assert len(monitor) == 50

    # Normal trade â€” should NOT trigger drift
    normal = {"retest_depth": 0.40, "body_ratio": 0.60, "disp_strength": 0.25}
    is_drift = monitor.detect_drift(normal)
    assert not is_drift, "Normal trade should not trigger drift"
    print(f"\nNormal trade drift={is_drift} âœ“")

    # Extreme trade â€” should trigger drift
    extreme = {"retest_depth": 0.99, "body_ratio": 0.99, "disp_strength": 0.99}
    is_drift = monitor.detect_drift(extreme)
    assert is_drift, "Extreme trade should trigger drift"
    severity = monitor.detect_drift_severity(extreme)
    print(f"Extreme trade drift={is_drift} severity={severity} âœ“")

    # Severity check
    assert severity in ("soft", "hard"), severity

    # Reset
    monitor.reset()
    assert len(monitor) == 0
    print("\nReset âœ“")

    print("\nAll feature_monitor.py self-tests PASSED.")

