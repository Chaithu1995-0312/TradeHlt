"""
src/core/ultron_gate.py
========================
CANONICAL NAMING (use these names in all new code and comments):

  RegimeGovernor   (THIS FILE, canonical name)   — SIGNAL-QUALITY FILTER
                                           Step 6 inside EngineRunner.run().
                                           Soft penalty + per-regime percentile gate + daily quota cap.
                                           Controls WHICH signals are quality-high enough per regime.
                                           Config key: engine_runner.ultron_gate_enabled

  UltronRiskGate   (ultron_risk_gate.py)  — CAPITAL PROTECTION LAYER
                                           Runs AFTER ExecutionPlannerV1_2.plan().
                                           Validates position sizing, drawdown, and exposure limits.
                                           Called externally by live_engine_hook.py.

  UltronRiskGateWrapper (ultron_risk_gate_wrapper.py) — EXTERNAL REGIME PRE-SCALER
                                           Utility that pre-scales risk_percent by regime factor
                                           BEFORE passing to UltronRiskGate. External to EngineRunner.

BACKWARD COMPATIBILITY:
  UltronGovernor = class name retained for test compatibility.
  RegimeGovernor = canonical alias (exported below, use this in new code).
  tests/test_ultron_gate.py imports UltronGovernor directly — do not rename the class.

RegimeGovernor — controlled signal-quality filter replacing the hard-rejection
dual-engine regime gate in engine_runner.py.

Converts:
  if direction == 0: return REJECT
  if b_score < neutral_min and t_score < neutral_min: return REJECT

Into a three-layer soft filter:
  1. Soft penalty per regime   (REGIME_PENALTY + DIRECTION_PENALTY)
  2. Percentile gate           (rolling 100-score window per regime)
  3. Daily quota cap           (MAX_TRADES_PER_BATCH = 3)

Returns a gate_result dict that is fully compatible with engine_runner.py:
  keys: allow, reason, reject_stage, selected, original_score,
        adjusted_score, quota_rank.

Design principles:
  - Deterministic: no randomness, same inputs → same output.
  - No external dependencies (only stdlib).
  - _regime_governor_legacy() in engine_runner.py retained for backtest/training path.
  - UltronRiskGate (capital protection layer) is NOT touched.
  - FusionEngine, DecisionEngine, upstream scoring are NOT touched.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import date
from typing import Deque, Dict, Optional

logger = logging.getLogger("ULTRON_GATE")


class UltronGovernor:
    """
    Regime-aware, percentile-based risk governor.

    FIX 1 — Soft penalty instead of hard reject:
        Penalty is subtracted from the selected engine's raw score.
        Result is clamped to [0, 1]. No signal is dropped immediately.

        REGIME_PENALTY:
            trend:   0.00  (trending regime → full speed)
            range:   0.15  (compressed market → harder to trade)
            neutral: 0.15  (uncertain → moderate reduction)

        DIRECTION_PENALTY:
            +0.10 when selected engine direction == 0 (no clear bias)

    FIX 2 — Regime-based acceptance bands (percentile gate):
        A rolling window of the last 100 adjusted scores per regime is
        maintained. Only signals in the top percentile are accepted.

        REGIME_ACCEPT_PERCENTILE:
            trend:   0.75  → top 25%
            range:   0.90  → top 10%
            neutral: 0.92  → top  8%

        Warmup fallback (window < WINDOW_MIN_SAMPLES):
            flat threshold of FALLBACK_THRESHOLD = 0.45

    FIX 3 — Daily quota cap:
        MAX_TRADES_PER_BATCH = 3 approvals per trading day.
        Resets at date boundary (deterministic, no randomness).

    FIX 4 — Rejection reasons (no silent changes):
        "ultron_penalty" — filtered by percentile gate
        "ultron_quota"   — filtered by daily cap

    FIX 5 — Mandatory structured logging:
        Every evaluate() call emits a structured INFO log entry with:
        regime, original_score, adjusted_score, allow, reason,
        reject_stage, quota_rank, window_n.
    """

    # ── Tunable constants ─────────────────────────────────────────────────────

    MAX_TRADES_PER_BATCH: int = 3

    REGIME_PENALTY: Dict[str, float] = {
        "trend":   0.00,
        "range":   0.15,
        "neutral": 0.15,
    }

    REGIME_ACCEPT_PERCENTILE: Dict[str, float] = {
        "trend":   0.75,   # top 25%  (TREND band)
        "range":   0.90,   # top 10%  (RANGE band)
        "neutral": 0.92,   # top  8%  (NEUTRAL band)
    }

    DIRECTION_PENALTY:  float = 0.10
    FALLBACK_THRESHOLD: float = 0.45
    WINDOW_MIN_SAMPLES: int   = 10
    WINDOW_MAXLEN:      int   = 100

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._log: logging.Logger = logging.getLogger("ULTRON_GATE")

        # Rolling score windows keyed by regime
        self._windows: Dict[str, Deque[float]] = {
            k: deque(maxlen=self.WINDOW_MAXLEN)
            for k in ("trend", "range", "neutral")
        }

        # Daily quota state
        self._current_date: Optional[date] = None
        self._daily_count:  int = 0

        # Lifetime statistics (for report())
        self._total_evaluated: int = 0
        self._total_passed:    int = 0
        self._total_penalty:   int = 0
        self._total_quota:     int = 0

    # ── Public interface ──────────────────────────────────────────────────────

    def evaluate(
        self,
        regime:       str,
        dual_results: dict,
        cfg:          dict,
        candle_date:  date,
    ) -> dict:
        """
        Evaluate one signal through the three-layer governor.

        Parameters
        ----------
        regime       : "trend" | "range" | "neutral"
        dual_results : {"breakout": {...}, "trap": {...}}
        cfg          : dual_engine config dict (supplies neutral_min_score)
        candle_date  : trading day date for daily quota boundary

        Returns
        -------
        gate_result dict, compatible with engine_runner.py downstream code:
            allow          : bool
            reason         : str  — engine reason or "ultron_penalty" / "ultron_quota"
            reject_stage   : str  — "ultron_penalty" | "ultron_quota" | ""
            selected       : dict | None   — winning engine dict
            original_score : float         — raw engine score before penalty
            adjusted_score : float         — score after penalty, clamped [0,1]
            quota_rank     : int           — 1-based daily approval count (0 if filtered)
        """
        self._total_evaluated += 1

        # ── FIX 3: Date boundary reset ────────────────────────────────────────
        if candle_date != self._current_date:
            self._current_date = candle_date
            self._daily_count  = 0

        breakout = dual_results.get("breakout", {})
        trap     = dual_results.get("trap",     {})

        # ── Engine selection (existing regime rules preserved) ────────────────
        if regime == "trend":
            selected    = dict(breakout)
            gate_reason = "regime_trend"
            raw_score   = float(breakout.get("score", 0.0))

        elif regime == "range":
            selected    = dict(trap)
            gate_reason = "regime_range"
            raw_score   = float(trap.get("score", 0.0))

        else:  # neutral
            b_score = float(breakout.get("score", 0.0))
            t_score = float(trap.get("score", 0.0))
            b_dir   = int(breakout.get("direction", 0))
            t_dir   = int(trap.get("direction", 0))

            # FIX 1: neutral_low_confidence → no hard reject.
            # Pick the higher-scoring engine; the penalty + percentile gate
            # will filter it if confidence is genuinely too low.
            if b_score >= t_score:
                selected = {
                    "engine":    "breakout",
                    "score":     b_score,
                    "direction": b_dir,
                }
            else:
                selected = {
                    "engine":    "trap",
                    "score":     t_score,
                    "direction": t_dir,
                }
            raw_score   = max(b_score, t_score)
            gate_reason = "regime_neutral_resolved"

        # ── FIX 1: Soft penalty (regime + direction) ──────────────────────────
        direction = int((selected or {}).get("direction", 0))
        base_pen  = self.REGIME_PENALTY.get(regime, 0.15)
        dir_pen   = self.DIRECTION_PENALTY if direction == 0 else 0.0
        total_pen = base_pen + dir_pen
        adj_score = max(0.0, min(1.0, raw_score - total_pen))

        # ── FIX 2: Percentile gate ────────────────────────────────────────────
        # Record BEFORE evaluating so this signal participates in future
        # percentile calculations (deterministic, no look-ahead).
        window = self._windows.get(regime, self._windows["neutral"])
        window.append(adj_score)
        n = len(window)

        if n < self.WINDOW_MIN_SAMPLES:
            # Warmup: use flat fallback threshold
            passes_gate = adj_score >= self.FALLBACK_THRESHOLD
        else:
            pct       = self.REGIME_ACCEPT_PERCENTILE.get(regime, 0.90)
            idx       = min(int(pct * n), n - 1)
            threshold = sorted(window)[idx]
            passes_gate = adj_score >= threshold

        if not passes_gate:
            self._total_penalty += 1
            result = self._build(
                allow=False, reason="ultron_penalty",
                selected=selected, raw=raw_score, adj=adj_score, rank=0,
            )
            self._log_decision(result, regime, n)
            return result

        # ── FIX 3: Daily quota cap ────────────────────────────────────────────
        if self._daily_count >= self.MAX_TRADES_PER_BATCH:
            self._total_quota += 1
            result = self._build(
                allow=False, reason="ultron_quota",
                selected=selected, raw=raw_score, adj=adj_score, rank=0,
            )
            self._log_decision(result, regime, n)
            return result

        # ── PASS ──────────────────────────────────────────────────────────────
        self._daily_count  += 1
        self._total_passed += 1
        result = self._build(
            allow=True, reason=gate_reason,
            selected=selected, raw=raw_score, adj=adj_score,
            rank=self._daily_count,
        )
        self._log_decision(result, regime, n)
        return result

    def reset(self) -> None:
        """Reset all state. Call between independent backtest runs."""
        for w in self._windows.values():
            w.clear()
        self._current_date    = None
        self._daily_count     = 0
        self._total_evaluated = 0
        self._total_passed    = 0
        self._total_penalty   = 0
        self._total_quota     = 0

    def report(self) -> str:
        """One-line lifetime summary for logging."""
        rate = (
            self._total_passed / self._total_evaluated * 100
            if self._total_evaluated else 0.0
        )
        return (
            f"RegimeGovernor | evaluated={self._total_evaluated} "
            f"passed={self._total_passed} ({rate:.1f}%) "
            f"filtered_penalty={self._total_penalty} "
            f"filtered_quota={self._total_quota}"
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build(
        self,
        allow:    bool,
        reason:   str,
        selected: Optional[dict],
        raw:      float,
        adj:      float,
        rank:     int,
    ) -> dict:
        return {
            "allow":          allow,
            "reason":         reason,
            "reject_stage":   "" if allow else reason,
            "selected":       selected,
            "original_score": raw,
            "adjusted_score": adj,
            "quota_rank":     rank,
        }

    def _log_decision(self, result: dict, regime: str, n_samples: int) -> None:
        """FIX 5: Mandatory structured log on every evaluation."""
        self._log.info(
            "RegimeGov | regime=%s original_score=%.4f adjusted_score=%.4f "
            "allow=%s reason=%r reject_stage=%r quota_rank=%d window_n=%d",
            regime,
            result["original_score"],
            result["adjusted_score"],
            result["allow"],
            result["reason"],
            result["reject_stage"],
            result["quota_rank"],
            n_samples,
        )


# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL ALIAS — RegimeGovernor is the preferred name in all new code.
# UltronGovernor is kept for backward compatibility:
#   tests/test_ultron_gate.py imports UltronGovernor directly.
# Both names resolve to the same class; behaviour is identical.
# ─────────────────────────────────────────────────────────────────────────────
RegimeGovernor = UltronGovernor
