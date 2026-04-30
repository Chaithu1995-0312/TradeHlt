"""
core/convergence_controller.py — Convergence Layer for FusionEngine

Architecture (Option B — Layered):
  scores → FusionEngine (weighted aggregation)
         → ConvergenceController (stability layer)

The controller does NOT re-aggregate engine scores.  When FusionEngine passes
a pre-computed `weighted_score`, that value is used as `base_avg`; the
controller's job is purely to apply a stability penalty and adaptive threshold:

  1. BitNet dampening      — zone_gate score ** 4  (only if score > 0.5)
  2. Sigmoid calibration   — 1/(1+exp(-k*(s-t))) on all 4 scores
  3. Disagreement penalty  — variance-based penalty applied to weighted_score
  4. Entropy tracking      — informational; logged per bar
  5. Adaptive threshold    — rolling 500-bar window controls accept/reject gate

When `weighted_score` is not supplied (legacy / standalone use), falls back to
the flat average of calibrated scores so existing callers are unaffected.

Usage (injected into FusionEngine):
    ctrl = ConvergenceController(window_size=500)
    result = ctrl.apply(
        {"crt": 0.7, "gaussian": 0.6, "zone_gate": 0.9, "rr": 0.65},
        weighted_score=0.71,   # pre-computed by FusionEngine
    )
    ctrl.record_outcome(accepted=result["accepted"])
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

import numpy as np

# Minimum history before adaptive threshold kicks in
_WARMUP_BARS = 10

# Adaptive threshold bounds
_THRESH_MIN = 0.30
_THRESH_MAX = 0.90
_THRESH_STEP = 0.02

# Accept-rate targets for adaptive threshold
_ACCEPT_RATE_HIGH = 0.30   # if above this → increase threshold
_ACCEPT_RATE_LOW  = 0.10   # if below this → decrease threshold

# Sigmoid calibration defaults
_SIG_K = 8.0
_SIG_T = 0.6


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class ConvergenceController:
    """
    Applied inside FusionEngine.compute() after per-engine scores are extracted.

    Transformations (in order):
      1. BitNet dampening:       zone_gate_score = score**4   IF score > 0.5
      2. Sigmoid calibration:    s = 1/(1+exp(-k*(s-t)))      on all 4 scores
      3. Disagreement penalty:   final *= (1 - sigmoid(variance_of_calibrated_scores))
      4. Entropy:                -sum(p*log(p+eps)) over calibrated score distribution
      5. Adaptive threshold:     rolling window adjusts threshold by _THRESH_STEP
      6. Decision:               accepted = final_score > threshold

    Cold-start guard: if fewer than _WARMUP_BARS outcomes recorded,
    returns raw average with variance=0, entropy=0, threshold=initial_threshold.
    """

    def __init__(
        self,
        window_size:       int   = 500,
        initial_threshold: float = 0.50,
    ) -> None:
        self._window_size = window_size
        self._threshold   = _clamp(initial_threshold, _THRESH_MIN, _THRESH_MAX)
        # Rolling window of bool outcomes for accept_rate computation
        self._outcome_window: deque[bool] = deque(maxlen=window_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_warm(self) -> bool:
        """True once enough outcomes have been recorded for stable statistics."""
        return len(self._outcome_window) >= _WARMUP_BARS

    @property
    def threshold(self) -> float:
        return self._threshold

    def calibrate_score(self, s: float, k: float = _SIG_K, t: float = _SIG_T) -> float:
        """Sigmoid calibration: 1/(1+exp(-k*(s-t))). Output clamped to [0,1]."""
        try:
            return _clamp(1.0 / (1.0 + math.exp(-k * (s - t))))
        except OverflowError:
            return 0.0 if s < t else 1.0

    def apply(
        self,
        scores: dict,
        debug: bool = False,
        weighted_score: Optional[float] = None,
    ) -> dict:
        """
        Parameters
        ----------
        scores         : dict with keys "crt", "gaussian", "zone_gate", "rr"
                         Missing keys default to 0.5 (neutral).
        debug          : if True, include raw_scores breakdown in result.
        weighted_score : pre-computed weighted fusion score from FusionEngine.
                         When provided this is used as base_avg (layered mode),
                         so the controller applies stability penalty on top of
                         the already-weighted value rather than re-averaging.
                         When None, falls back to flat average (legacy mode).

        Returns
        -------
        dict with keys:
          final_score, scores (calibrated), missing_engines,
          variance, entropy, threshold, accepted,
          and optionally debug (dict of intermediate values).
        """
        # --- Extract raw scores (default 0.5 for missing engines) ---
        raw = {
            "crt":       float(scores.get("crt",       0.5)),
            "gaussian":  float(scores.get("gaussian",  0.5)),
            "zone_gate": float(scores.get("zone_gate", 0.5)),
            "rr":        float(scores.get("rr",        0.5)),
        }
        missing = [k for k in ("crt", "gaussian", "zone_gate", "rr") if k not in scores]

        # Cold-start: skip transformations, honour weighted_score if supplied
        if not self.is_warm:
            base = float(weighted_score) if weighted_score is not None else sum(raw.values()) / 4.0
            base = _clamp(base)
            return {
                "final_score":    round(base, 4),
                "scores":         raw,
                "missing_engines": missing,
                "variance":       0.0,
                "entropy":        0.0,
                "threshold":      self._threshold,
                "accepted":       base > self._threshold,
                **({"debug": {"cold_start": True, "raw": raw, "weighted_score": weighted_score}} if debug else {}),
            }

        # --- Step 1: BitNet dampening on zone_gate only ---
        zg = raw["zone_gate"]
        dampened_zg = (zg ** 4) if zg > 0.5 else zg

        working = {
            "crt":       raw["crt"],
            "gaussian":  raw["gaussian"],
            "zone_gate": dampened_zg,
            "rr":        raw["rr"],
        }

        # --- Step 2: Sigmoid calibration on all 4 scores ---
        calibrated = {k: self.calibrate_score(v) for k, v in working.items()}

        cal_values = list(calibrated.values())

        # --- Step 3: Disagreement penalty ---
        variance = float(np.var(cal_values))
        # Penalty = sigmoid(variance) — reuse calibrate with k=8, t=0.5
        penalty  = self.calibrate_score(variance, k=8.0, t=0.5)
        # Layered mode: use pre-weighted fusion score as base instead of re-averaging.
        # Falls back to flat average of calibrated scores when no weighted_score supplied.
        base_avg = (
            _clamp(float(weighted_score))
            if weighted_score is not None
            else sum(cal_values) / 4.0
        )
        final    = _clamp(base_avg * (1.0 - penalty))

        # --- Step 4: Entropy ---
        total    = sum(cal_values) + 1e-9
        probs    = [v / total for v in cal_values]
        entropy  = float(-sum(p * math.log(p + 1e-9) for p in probs))

        # --- Step 5: Adaptive threshold update ---
        if len(self._outcome_window) > 0:
            accept_rate = sum(self._outcome_window) / len(self._outcome_window)
            if accept_rate > _ACCEPT_RATE_HIGH:
                self._threshold = _clamp(self._threshold + _THRESH_STEP, _THRESH_MIN, _THRESH_MAX)
            elif accept_rate < _ACCEPT_RATE_LOW:
                self._threshold = _clamp(self._threshold - _THRESH_STEP, _THRESH_MIN, _THRESH_MAX)

        # --- Step 6: Accept decision ---
        accepted = final > self._threshold

        result: dict = {
            "final_score":     round(final, 4),
            "scores":          calibrated,
            "missing_engines": missing,
            "variance":        round(variance, 6),
            "entropy":         round(entropy, 6),
            "threshold":       round(self._threshold, 4),
            "accepted":        accepted,
        }

        if debug:
            result["debug"] = {
                "raw":            raw,
                "dampened_zg":    round(dampened_zg, 4),
                "calibrated":     calibrated,
                "weighted_score": weighted_score,
                "base_avg":       round(base_avg, 4),
                "penalty":        round(penalty, 4),
                "variance":       round(variance, 6),
                "entropy":        round(entropy, 6),
            }

        return result

    def record_outcome(self, accepted: bool) -> None:
        """
        Update the rolling outcome window after a bar decision.
        Must be called once per bar, AFTER apply() is called.
        """
        self._outcome_window.append(bool(accepted))

    def accept_rate(self) -> Optional[float]:
        """Current rolling accept rate. None if no outcomes recorded yet."""
        if not self._outcome_window:
            return None
        return sum(self._outcome_window) / len(self._outcome_window)
