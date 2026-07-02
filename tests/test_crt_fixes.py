# tests/test_crt_fixes.py
"""
Unit + integration tests for the five CRT pipeline fixes.

FIX 1 — Dynamic Threshold           (decision_engine.DynamicThreshold)
FIX 2 — Score Normalization          (fusion_engine.ScoreNormalizer)
FIX 3 — Dead Engine Neutralization   (fusion_engine.EngineHealthTracker)
FIX 4 — Minimum Acceptance Fallback  (decision_engine.DecisionEngine.decide_batch)
FIX 5 — Logging Fields               (fusion_engine.FusionResult, decision_engine.DecisionResult)
"""

import random
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "core"))

from decision_engine import (
    DecisionEngine,
    DecisionResult,
    DynamicThreshold,
)
from fusion_engine import EngineHealthTracker, FusionResult, ScoreNormalizer

# Canonical DynamicThreshold knobs (formerly module constants in dynamic_threshold.py;
# now config-first BEHAVIORAL knobs read fail-fast from decision_engine.threshold_*).
# Tests pass them explicitly — there are intentionally no silent defaults.
_TEST_PERCENTILE = 85
_TEST_T_MIN      = 0.45
_TEST_T_MAX      = 0.65


def _make_dyn_threshold(**kw) -> DynamicThreshold:
    """Construct a DynamicThreshold with the canonical knobs (fail-fast: required)."""
    return DynamicThreshold(
        percentile=_TEST_PERCENTILE, t_min=_TEST_T_MIN, t_max=_TEST_T_MAX, **kw
    )


# ─── minimal config so DecisionEngine doesn't raise ──────────────────────────
_CFG = {
    "score_threshold":          0.45,
    "p_win_threshold":          0.40,
    "rr_threshold":             1.20,
    "weak_link_weight":         0.30,
    "weak_component_threshold": 0.55,
    "threshold_percentile":     _TEST_PERCENTILE,
    "threshold_min":            _TEST_T_MIN,
    "threshold_max":            _TEST_T_MAX,
}


# ═════════════════════════════════════════════════════════════════
# FIX 2 — ScoreNormalizer
# ═════════════════════════════════════════════════════════════════

class TestScoreNormalizer:
    def test_single_value_returns_neutral(self):
        sn = ScoreNormalizer()
        assert sn.push_and_normalize(0.42) == 0.5

    def test_constant_input_returns_neutral(self):
        sn = ScoreNormalizer()
        results = [sn.push_and_normalize(0.5) for _ in range(20)]
        assert all(r == 0.5 for r in results)

    def test_min_maps_to_zero(self):
        sn = ScoreNormalizer()
        sn.push_and_normalize(0.55)   # max
        v = sn.push_and_normalize(0.33)  # min
        assert abs(v - 0.0) < 1e-9

    def test_max_maps_to_one(self):
        sn = ScoreNormalizer()
        sn.push_and_normalize(0.33)
        v = sn.push_and_normalize(0.55)
        assert abs(v - 1.0) < 1e-9

    def test_output_clamped_to_unit_interval(self):
        sn = ScoreNormalizer()
        for s in [random.uniform(0.2, 0.8) for _ in range(200)]:
            v = sn.push_and_normalize(s)
            assert 0.0 <= v <= 1.0

    def test_no_division_by_zero_for_zero_inputs(self):
        sn = ScoreNormalizer()
        for _ in range(10):
            v = sn.push_and_normalize(0.0)
        assert v == 0.5


# ═════════════════════════════════════════════════════════════════
# FIX 3 — EngineHealthTracker
# ═════════════════════════════════════════════════════════════════

class TestEngineHealthTracker:
    def test_zero_only_engine_is_dead(self):
        eht = EngineHealthTracker()
        for _ in range(10):
            eht.push(0.0)
        assert eht.is_dead() is True

    def test_mixed_engine_is_not_dead(self):
        eht = EngineHealthTracker()
        for v in [0.0, 0.5, 0.0]:
            eht.push(v)
        assert eht.is_dead() is False

    def test_insufficient_samples_not_dead(self):
        eht = EngineHealthTracker()
        eht.push(0.0)
        assert eht.is_dead() is False

    def test_window_eviction_reactivates(self):
        eht = EngineHealthTracker(window=5)
        for _ in range(5):
            eht.push(0.0)
        assert eht.is_dead() is True
        for _ in range(5):
            eht.push(0.7)
        assert eht.is_dead() is False

    def test_constant_nonzero_not_dead(self):
        eht = EngineHealthTracker()
        for _ in range(20):
            eht.push(0.5)
        assert eht.is_dead() is False


# ═════════════════════════════════════════════════════════════════
# FIX 1 — DynamicThreshold
# ═════════════════════════════════════════════════════════════════

class TestDynamicThreshold:
    def test_cold_start_returns_midpoint(self):
        dt = _make_dyn_threshold()
        assert dt.compute() == (_TEST_T_MIN + _TEST_T_MAX) / 2.0

    def test_threshold_within_clamp(self):
        dt = _make_dyn_threshold()
        for s in [i / 10.0 for i in range(1, 11)]:
            dt.update(s)
        assert _TEST_T_MIN <= dt.compute() <= _TEST_T_MAX

    def test_all_low_scores_clamp_to_min(self):
        dt = _make_dyn_threshold()
        for _ in range(100):
            dt.update(0.10)
        assert dt.compute() == _TEST_T_MIN

    def test_all_high_scores_clamp_to_max(self):
        dt = _make_dyn_threshold()
        for _ in range(100):
            dt.update(0.95)
        assert dt.compute() == _TEST_T_MAX

    def test_n_samples_tracks_updates(self):
        dt = _make_dyn_threshold(window=50)
        for i in range(30):
            dt.update(float(i) / 100)
        assert dt.n_samples == 30


# ═════════════════════════════════════════════════════════════════
# FIX 4 — DecisionEngine.decide_batch (minimum acceptance fallback)
# ═════════════════════════════════════════════════════════════════

class TestDecisionEngineBatch:
    def _make_signal(self, score: float) -> dict:
        return {
            "score":     score,
            "p_win":     0.6,
            "zone_gate": {"valid": True},
            "fusion":    {"normalized_score": score, "rr": 2.0, "weak_component": 0.1},
            "config":    _CFG,
        }

    def test_fallback_fires_when_zero_accepted(self):
        de = DecisionEngine(config=_CFG, fallback_n=2)
        # Force threshold to max so no normal signal passes
        for _ in range(1000):
            de._dynamic_threshold.update(0.65)
        signals = [self._make_signal(0.01) for _ in range(5)]
        results = de.decide_batch(signals)
        accepted = [r for r in results if r["decision"] == "execute"]
        assert len(accepted) == 2
        assert all(r["reject_stage"] == "fallback_top_n" for r in accepted)

    def test_batch_empty_returns_empty(self):
        de = DecisionEngine(config=_CFG)
        assert de.decide_batch([]) == []

    def test_normal_signals_pass_without_fallback(self):
        de = DecisionEngine(config=_CFG)
        # Force threshold low so high scores pass normally
        for _ in range(100):
            de._dynamic_threshold.update(0.01)
        signals = [self._make_signal(0.9) for _ in range(5)]
        results = de.decide_batch(signals)
        accepted = [r for r in results if r["decision"] == "execute"]
        assert len(accepted) > 0
        assert all(r["reject_stage"] != "fallback_top_n" for r in accepted)


# ═════════════════════════════════════════════════════════════════
# FIX 3 — Dead zone_gate bypass in evaluate()
# ═════════════════════════════════════════════════════════════════

class TestDeadZoneGatBypass:
    def test_dead_zone_gate_does_not_block(self):
        de = DecisionEngine(config=_CFG)
        # Force low threshold so score check passes
        for _ in range(100):
            de._dynamic_threshold.update(0.01)
        result = de.evaluate(
            score     = 0.8,
            p_win     = 0.6,
            zone_gate = {"valid": False},
            fusion    = {
                "normalized_score": 0.8,
                "zone_gate_dead":   True,   # FIX 3 signal
                "rr":               2.0,
                "weak_component":   0.1,
            },
            config    = _CFG,
        )
        assert result["decision"] == "execute", (
            f"Dead zone_gate should be bypassed, got: {result}"
        )

    def test_live_invalid_zone_gate_still_blocks(self):
        de = DecisionEngine(config=_CFG)
        result = de.evaluate(
            score     = 0.9,
            p_win     = 0.6,
            zone_gate = {"valid": False},
            fusion    = {
                "normalized_score": 0.9,
                "zone_gate_dead":   False,   # engine alive but gate invalid
                "rr":               2.0,
                "weak_component":   0.1,
            },
            config    = _CFG,
        )
        assert result["decision"] == "reject"
        assert result["reason"] == "zone_gate_invalid"


# ═════════════════════════════════════════════════════════════════
# FIX 5 — Logging fields mandatory in all outputs
# ═════════════════════════════════════════════════════════════════

class TestLoggingFields:
    def test_fusion_result_has_logging_fields(self):
        r = FusionResult(
            final_score=0.5, gaussian=0.5, neural=None, llm=None,
            llm_fired=False, action="REJECT", risk_mult=0.0,
            normalized_score=0.72, threshold_used=0.55, reject_stage="score_below_tier_half",
        )
        d = r.to_dict()
        assert "normalized_score" in d
        assert "threshold_used"   in d
        assert "reject_stage"     in d

    def test_decision_result_has_logging_fields(self):
        r = DecisionResult(
            decision="execute", reason="all_conditions_met",
            confidence=0.7, threshold_used=0.52, reject_stage="passed",
        )
        d = r.to_dict()
        assert "threshold_used" in d
        assert "reject_stage"   in d
        assert d["threshold_used"] == 0.52
        assert d["reject_stage"]   == "passed"

    def test_evaluate_always_includes_threshold_used(self):
        de = DecisionEngine(config=_CFG)
        result = de.evaluate(
            score=0.8, p_win=0.6,
            zone_gate={"valid": True},
            fusion={"normalized_score": 0.8, "rr": 2.0, "weak_component": 0.1},
            config=_CFG,
        )
        assert "threshold_used" in result
        assert "reject_stage"   in result


# ═════════════════════════════════════════════════════════════════
# INTEGRATION — full pipeline: compressed scores → ACCEPT > 0
# ═════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_compressed_scores_yield_accepts(self):
        """
        Simulate compressed fusion scores [0.33, 0.55].
        After ScoreNormalizer + DynamicThreshold: ACCEPT > 0.
        """
        rng = random.Random(42)
        raw_scores = [rng.uniform(0.33, 0.55) for _ in range(200)]

        sn = ScoreNormalizer()
        de = DecisionEngine(config=_CFG)

        normalised = [sn.push_and_normalize(s) for s in raw_scores]
        assert min(normalised) < 0.10
        assert max(normalised) > 0.90

        accepted = 0
        for n in normalised:
            result = de.evaluate(
                score     = n,
                p_win     = 0.6,
                zone_gate = {"valid": True},
                fusion    = {"normalized_score": n, "rr": 2.0, "weak_component": 0.1},
                config    = _CFG,
            )
            if result["decision"] == "execute":
                accepted += 1

        assert accepted > 0, f"ACCEPT count must be > 0, got {accepted}"

        # Safety: max_score >= threshold — threshold was reachable
        threshold = de.current_threshold
        assert max(normalised) >= threshold

    def test_no_silent_failures_on_extreme_inputs(self):
        sn = ScoreNormalizer()
        de = DecisionEngine(config=_CFG)
        for v in [0.0, 0.0, 0.0, 1.0, 1.0]:
            n = sn.push_and_normalize(v)
            de.evaluate(
                score=n, p_win=0.6,
                zone_gate={"valid": True},
                fusion={"normalized_score": n, "rr": 2.0, "weak_component": 0.1},
                config=_CFG,
            )
