"""
core/acceptance_controller.py — Adaptive Acceptance Control System

Maintains trade acceptance rate between 5%–15% using dynamic threshold
adjustment (integral control). Thresholds are injected into DecisionEngine
and FusionEngine each bar via EngineRunner.

Usage (in EngineRunner):
    ctrl = AcceptanceController(config)

    # Before decision step:
    thresholds = ctrl.get_thresholds()    # merge into config for DecisionEngine

    # After decision step:
    ctrl.update_metrics(engine_scores, fusion_score, accepted=True)
    ctrl.adjust_thresholds()

Constraints:
  - Stateless per bar, stateful per session.
  - Thresholds bounded: 0.50 <= theta <= 0.95.
  - Returns config defaults unchanged until min_history bars collected.
  - MUST NOT modify UltronRiskGate.
  - MUST NOT bypass ZoneGate.
"""

from __future__ import annotations

from collections import deque
from typing import Optional

import numpy as np

# Hard bounds on all thresholds
_THETA_MIN = 0.50
_THETA_MAX = 0.95

# Minimum samples before adaptive control engages
_MIN_HISTORY = 10

# Default config values (used when history is insufficient or config is missing)
_DEFAULTS = {
    "score_threshold":  0.45,
    "engine_threshold": 0.60,
    "fusion_threshold": 0.65,
}


def _clamp(v: float, lo: float = _THETA_MIN, hi: float = _THETA_MAX) -> float:
    return max(lo, min(hi, float(v)))


class AcceptanceController:
    """
    Adaptive threshold controller that nudges score_threshold up/down to
    keep acceptance rate inside [target_low, target_high].

    Integral control rule (applied once per bar via adjust_thresholds):
        error     = acceptance_rate - target_mid
        theta_new = clamp(theta_old + alpha * error, 0.5, 0.95)

    Threshold computation (called when history is sufficient):
        engine_threshold = mean(engine_scores) + k_sigma * std(engine_scores)
        fusion_threshold = np.percentile(fusion_scores, 85)
    """

    def __init__(self, config: Optional[dict] = None) -> None:
        cfg = config or {}

        # Integral control parameters
        self._alpha        = float(cfg.get("acceptance_alpha", 0.01))
        self._target_low   = float(cfg.get("acceptance_target_low",  0.05))
        self._target_high  = float(cfg.get("acceptance_target_high", 0.15))
        self._k_sigma      = float(cfg.get("acceptance_k_sigma",     1.0))
        self._window_size  = int(cfg.get("acceptance_window",        200))

        # Current theta (score_threshold fed to DecisionEngine)
        # Store raw config value separately so cold-path returns it unchanged
        self._cold_score_threshold = float(cfg.get("score_threshold", _DEFAULTS["score_threshold"]))
        self._theta = _clamp(self._cold_score_threshold)

        # Rolling history windows
        self._engine_scores:  deque[float] = deque(maxlen=self._window_size)
        self._fusion_scores:  deque[float] = deque(maxlen=self._window_size)
        self._accepted_flags: deque[bool]  = deque(maxlen=self._window_size)

        # Cached config defaults (returned when history is insufficient)
        # Use the raw (pre-clamp) score_threshold so config values < _THETA_MIN are preserved
        self._cfg_defaults = {
            "score_threshold":  self._cold_score_threshold,
            "engine_threshold": float(cfg.get("engine_threshold", _DEFAULTS["engine_threshold"])),
            "fusion_threshold": float(cfg.get("fusion_threshold", _DEFAULTS["fusion_threshold"])),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_metrics(
        self,
        engine_scores: dict,
        fusion_score:  float,
        accepted:      bool,
    ) -> None:
        """
        Record one bar's scores and acceptance outcome.
        engine_scores: {"crt": float, "gaussian": float, ...}
        """
        if engine_scores:
            values = [float(v) for v in engine_scores.values() if v is not None]
            if values:
                self._engine_scores.append(float(np.mean(values)))

        self._fusion_scores.append(float(fusion_score))
        self._accepted_flags.append(bool(accepted))

    def compute_thresholds(self) -> dict:
        """
        Compute statistically-derived thresholds from current history.
        Falls back to config defaults when history < _MIN_HISTORY.
        """
        if len(self._engine_scores) < _MIN_HISTORY:
            return dict(self._cfg_defaults)

        eng_arr    = np.array(self._engine_scores)
        fus_arr    = np.array(self._fusion_scores)

        engine_thr = _clamp(float(np.mean(eng_arr) + self._k_sigma * np.std(eng_arr)))
        fusion_thr = _clamp(float(np.percentile(fus_arr, 85)))

        return {
            "score_threshold":  round(self._theta,   4),
            "engine_threshold": round(engine_thr,    4),
            "fusion_threshold": round(fusion_thr,    4),
        }

    def adjust_thresholds(self) -> None:
        """
        Apply one integral control step to self._theta.
        Called once per bar, AFTER update_metrics().
        No-op if insufficient history.
        """
        if len(self._accepted_flags) < _MIN_HISTORY:
            return

        accept_rate = sum(self._accepted_flags) / len(self._accepted_flags)
        target_mid  = (self._target_low + self._target_high) / 2.0
        error       = accept_rate - target_mid

        self._theta = _clamp(self._theta + self._alpha * error)

    def get_thresholds(self) -> dict:
        """
        Return current thresholds for injection into DecisionEngine config.
        Always returns a valid dict — never raises.
        """
        return self.compute_thresholds()

    def acceptance_rate(self) -> Optional[float]:
        """Current rolling acceptance rate. None if no data yet."""
        if not self._accepted_flags:
            return None
        return sum(self._accepted_flags) / len(self._accepted_flags)

    def state(self) -> dict:
        """Return controller state for logging/debugging."""
        return {
            "theta":           round(self._theta, 4),
            "acceptance_rate": self.acceptance_rate(),
            "history_len":     len(self._accepted_flags),
            "target":          [self._target_low, self._target_high],
            "alpha":           self._alpha,
        }
