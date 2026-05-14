"""
Tests for GateIntelligence and compute_crt_levels.

Groups
------
A) Determinism  — same input → identical output across calls and instances
B) Threshold    — approve/reject boundary behaviour
C) Components   — each score responds correctly to its driving features
"""

from __future__ import annotations

import itertools

import pytest

from core.gate_intelligence import GateIntelligence, compute_crt_levels


# ── Fixtures ──────────────────────────────────────────────────────────────────

_BASE_CONFIG: dict = {
    "gate_weight_intent":      0.35,
    "gate_weight_vol":         0.20,
    "gate_weight_liquidity":   0.20,
    "gate_weight_structure":   0.25,
    "gate_approval_threshold": 0.55,
}


def _gate(overrides: dict | None = None) -> GateIntelligence:
    return GateIntelligence({**_BASE_CONFIG, **(overrides or {})})


def _breakout_features() -> dict:
    """Clean BREAKOUT signal with moderate liquidity — score near threshold."""
    return {
        "close":              100.0,
        "high":               102.0,
        "low":                98.0,
        "atr":                2.0,
        "body_ratio":         0.85,
        "disp_strength":      2.5,
        "sweep_detected":     False,
        "double_sweep":       False,
        "retest_depth":       0.1,
        "candles_since_retest": 12,
        "ema_fast":           100.5,
        "ema_slow":           99.0,
        "momentum_score":     0.6,
        "volume":             1200.0,
        "volume_ma20":        800.0,
        "highest_high_20":    103.0,
        "lowest_low_20":      96.0,
        "highest_high_5":     101.5,
        "lowest_low_5":       98.5,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP A — Determinism
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterminism:

    def test_decide_same_output_multiple_calls(self):
        """Five consecutive calls with identical input must return identical output."""
        g = _gate()
        f = _breakout_features()
        results = [g.decide(f, "BREAKOUT", 1) for _ in range(5)]
        for r in results[1:]:
            assert r["final_score"]  == results[0]["final_score"]
            assert r["approved"]     == results[0]["approved"]
            assert r["components"]   == results[0]["components"]

    def test_decide_independent_instances_same_result(self):
        """Two separate GateIntelligence instances with same config must agree."""
        f = _breakout_features()
        r1 = _gate().decide(f, "BREAKOUT", 1)
        r2 = _gate().decide(f, "BREAKOUT", 1)
        assert r1["final_score"] == r2["final_score"]
        assert r1["components"]  == r2["components"]
        assert r1["approved"]    == r2["approved"]

    def test_compute_crt_levels_deterministic(self):
        """Same kwargs must return identical dict on repeated calls."""
        kwargs = dict(entry=100.0, direction=1, low=98.0, high=102.0, atr=2.0)
        assert compute_crt_levels(**kwargs) == compute_crt_levels(**kwargs)

    def test_compute_crt_levels_long_formula(self):
        """LONG: sl=low-0.2*atr, risk_dist=abs(entry-sl), tp1=+1R, tp2=+2R, rr=1."""
        r = compute_crt_levels(entry=100.0, direction=1, low=98.0, high=102.0, atr=2.0)
        expected_sl        = 98.0 - 0.2 * 2.0          # 97.6
        expected_risk_dist = abs(100.0 - expected_sl)   # 2.4
        assert r["sl"]        == pytest.approx(expected_sl)
        assert r["risk_dist"] == pytest.approx(expected_risk_dist)
        assert r["tp1"]       == pytest.approx(100.0 + 1.0 * expected_risk_dist)
        assert r["tp2"]       == pytest.approx(100.0 + 2.0 * expected_risk_dist)
        assert r["rr"]        == 1.0

    def test_compute_crt_levels_short_formula(self):
        """SHORT: sl=high+0.2*atr, tp1 below entry, tp2 further below."""
        r = compute_crt_levels(entry=100.0, direction=-1, low=98.0, high=102.0, atr=2.0)
        expected_sl        = 102.0 + 0.2 * 2.0
        expected_risk_dist = abs(100.0 - expected_sl)
        assert r["sl"]        == pytest.approx(expected_sl)
        assert r["tp1"]       == pytest.approx(100.0 - 1.0 * expected_risk_dist)
        assert r["tp2"]       == pytest.approx(100.0 - 2.0 * expected_risk_dist)
        assert r["rr"]        == 1.0

    def test_compute_crt_levels_custom_buffer(self):
        """sl_atr_buffer parameter is applied correctly."""
        r = compute_crt_levels(entry=100.0, direction=1, low=98.0, high=102.0, atr=2.0,
                                sl_atr_buffer=0.5)
        assert r["sl"] == pytest.approx(98.0 - 0.5 * 2.0)


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP B — Threshold
# ═══════════════════════════════════════════════════════════════════════════════

class TestThreshold:

    def test_strong_liq_sweep_approves_at_default_threshold(self):
        """High-quality LIQ_SWEEP (double sweep + volume spike) must be approved."""
        f = {
            **_breakout_features(),
            "sweep_detected": True,
            "double_sweep":   True,
            "volume":         2000.0,  # 2.5× average → high vol_score
            "volume_ma20":    800.0,
            "ema_fast":       100.5,
            "ema_slow":       99.0,
            "disp_strength":  2.8,
        }
        r = _gate().decide(f, "LIQ_SWEEP", 1)
        assert r["approved"] is True
        assert r["final_score"] >= 0.55

    def test_weak_features_rejected_at_high_threshold(self):
        """Weak features must be rejected when threshold is raised to 0.9."""
        f = {
            **_breakout_features(),
            "body_ratio":     0.05,
            "disp_strength":  0.1,
            "sweep_detected": False,
            "double_sweep":   False,
            "volume":         10.0,
            "volume_ma20":    1000.0,
            "ema_fast":       100.0,
            "ema_slow":       100.0,  # no alignment
        }
        r = _gate({"gate_approval_threshold": 0.9}).decide(f, "UNKNOWN", 1)
        assert r["approved"] is False
        assert r["final_score"] < 0.9

    def test_threshold_099_rejects_average_breakout(self):
        """threshold=0.99 must reject even a clean BREAKOUT signal."""
        r = _gate({"gate_approval_threshold": 0.99}).decide(_breakout_features(), "BREAKOUT", 1)
        assert r["approved"] is False

    def test_threshold_zero_always_approves(self):
        """threshold=0.0 must approve regardless of features or intent."""
        r = _gate({"gate_approval_threshold": 0.0}).decide(_breakout_features(), "UNKNOWN", 1)
        assert r["approved"] is True

    def test_rejection_reason_contains_keyword_and_threshold(self):
        """Rejection reason must include 'rejected' and the threshold value."""
        r = _gate({"gate_approval_threshold": 0.99}).decide(_breakout_features(), "BREAKOUT", 1)
        assert r["approved"] is False
        assert "rejected" in r["reason"]
        assert "0.99" in r["reason"]

    def test_approval_reason_contains_approved_keyword(self):
        """Approval reason must include 'approved'."""
        r = _gate({"gate_approval_threshold": 0.0}).decide(_breakout_features(), "BREAKOUT", 1)
        assert "approved" in r["reason"]

    def test_compute_crt_levels_raises_on_zero_atr(self):
        """ValueError must be raised when atr=0."""
        with pytest.raises(ValueError, match="atr must be > 0"):
            compute_crt_levels(entry=100.0, direction=1, low=98.0, high=102.0, atr=0.0)

    def test_compute_crt_levels_raises_on_bad_direction(self):
        """ValueError must be raised when direction is not 1 or -1."""
        with pytest.raises(ValueError, match="direction must be 1 or -1"):
            compute_crt_levels(entry=100.0, direction=0, low=98.0, high=102.0, atr=2.0)

    def test_compute_crt_levels_raises_on_negative_atr(self):
        """ValueError must be raised when atr is negative."""
        with pytest.raises(ValueError, match="atr must be > 0"):
            compute_crt_levels(entry=100.0, direction=1, low=98.0, high=102.0, atr=-1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP C — Component contribution and weight sensitivity
# ═══════════════════════════════════════════════════════════════════════════════

class TestComponents:

    # ── intent_score ──────────────────────────────────────────────────────────

    def test_intent_breakout_increases_with_body_and_disp(self):
        g = _gate()
        f_weak   = {**_breakout_features(), "body_ratio": 0.1, "disp_strength": 0.5}
        f_strong = {**_breakout_features(), "body_ratio": 1.0, "disp_strength": 3.0}
        r_w = g.decide(f_weak,   "BREAKOUT", 1)
        r_s = g.decide(f_strong, "BREAKOUT", 1)
        assert r_s["components"]["intent_score"] > r_w["components"]["intent_score"]

    def test_intent_unknown_is_always_zero(self):
        r = _gate().decide(_breakout_features(), "UNKNOWN", 1)
        assert r["components"]["intent_score"] == 0.0

    def test_intent_liq_sweep_double_beats_single(self):
        g = _gate()
        f_single = {**_breakout_features(), "sweep_detected": True,  "double_sweep": False}
        f_double = {**_breakout_features(), "sweep_detected": True,  "double_sweep": True}
        r_s = g.decide(f_single, "LIQ_SWEEP", 1)
        r_d = g.decide(f_double, "LIQ_SWEEP", 1)
        assert r_d["components"]["intent_score"] > r_s["components"]["intent_score"]

    def test_intent_liq_sweep_no_sweeps_is_zero(self):
        f = {**_breakout_features(), "sweep_detected": False, "double_sweep": False}
        r = _gate().decide(f, "LIQ_SWEEP", 1)
        assert r["components"]["intent_score"] == 0.0

    def test_intent_pullback_perfect_depth_scores_highest(self):
        """retest_depth=0.5 (peak of triangular function) should outscore 0.1."""
        g = _gate()
        f_far  = {**_breakout_features(), "retest_depth": 0.1,  "candles_since_retest": 1}
        f_peak = {**_breakout_features(), "retest_depth": 0.5,  "candles_since_retest": 1}
        r_far  = g.decide(f_far,  "PULLBACK", 1)
        r_peak = g.decide(f_peak, "PULLBACK", 1)
        assert r_peak["components"]["intent_score"] > r_far["components"]["intent_score"]

    def test_intent_reversal_low_momentum_scores_high(self):
        """Reversal with near-zero momentum should score higher than strong momentum."""
        g = _gate()
        f_strong = {**_breakout_features(), "momentum_score": 0.95}
        f_weak   = {**_breakout_features(), "momentum_score": 0.05}
        r_s = g.decide(f_strong, "REVERSAL", 1)
        r_w = g.decide(f_weak,   "REVERSAL", 1)
        assert r_w["components"]["intent_score"] > r_s["components"]["intent_score"]

    # ── vol_score ─────────────────────────────────────────────────────────────

    def test_vol_score_is_1_when_range_equals_atr(self):
        """bar_range == atr → ratio = 1.0 → vol_score = 1.0."""
        f = {**_breakout_features(), "high": 101.0, "low": 99.0, "atr": 2.0}
        r = _gate().decide(f, "BREAKOUT", 1)
        assert r["components"]["vol_score"] == pytest.approx(1.0)

    def test_vol_score_zero_on_zero_atr(self):
        """atr=0 must produce vol_score=0.0 without division error."""
        f = {**_breakout_features(), "atr": 0.0}
        r = _gate().decide(f, "BREAKOUT", 1)
        assert r["components"]["vol_score"] == 0.0

    def test_vol_score_decreases_as_range_exceeds_3x_atr(self):
        """bar_range=3×atr → ratio=3 → score=0. bar_range=1×atr → score=1."""
        g = _gate()
        f_normal = {**_breakout_features(), "high": 101.0, "low": 99.0, "atr": 2.0}
        f_wide   = {**_breakout_features(), "high": 106.0, "low": 100.0, "atr": 2.0}
        r_n = g.decide(f_normal, "BREAKOUT", 1)
        r_w = g.decide(f_wide,   "BREAKOUT", 1)
        assert r_n["components"]["vol_score"] > r_w["components"]["vol_score"]

    # ── structure_score ───────────────────────────────────────────────────────

    def test_structure_ema_aligned_long_beats_misaligned(self):
        g = _gate()
        f_ok  = {**_breakout_features(), "ema_fast": 101.0, "ema_slow": 99.0}
        f_bad = {**_breakout_features(), "ema_fast": 99.0,  "ema_slow": 101.0}
        r_ok  = g.decide(f_ok,  "BREAKOUT", 1)
        r_bad = g.decide(f_bad, "BREAKOUT", 1)
        assert r_ok["components"]["structure_score"] > r_bad["components"]["structure_score"]

    def test_structure_ema_aligned_short(self):
        """SHORT aligned = ema_fast < ema_slow."""
        g = _gate()
        f_ok  = {**_breakout_features(), "ema_fast": 99.0,  "ema_slow": 101.0}
        f_bad = {**_breakout_features(), "ema_fast": 101.0, "ema_slow": 99.0}
        r_ok  = g.decide(f_ok,  "BREAKOUT", -1)
        r_bad = g.decide(f_bad, "BREAKOUT", -1)
        assert r_ok["components"]["structure_score"] > r_bad["components"]["structure_score"]

    # ── Weight sensitivity ────────────────────────────────────────────────────

    def test_weight_intent_zero_removes_intent_contribution(self):
        """With gate_weight_intent=0 the final_score must be the same for BREAKOUT and UNKNOWN."""
        cfg = {
            **_BASE_CONFIG,
            "gate_weight_intent":   0.0,
            "gate_weight_vol":      0.34,
            "gate_weight_liquidity": 0.33,
            "gate_weight_structure": 0.33,
        }
        g = _gate(cfg)
        f = _breakout_features()
        r_b = g.decide(f, "BREAKOUT", 1)
        r_u = g.decide(f, "UNKNOWN",  1)
        assert r_b["final_score"] == r_u["final_score"]

    def test_all_weights_zero_produces_score_zero(self):
        """All weights=0 must yield final_score=0 regardless of features."""
        cfg = {
            **_BASE_CONFIG,
            "gate_weight_intent":    0.0,
            "gate_weight_vol":       0.0,
            "gate_weight_liquidity": 0.0,
            "gate_weight_structure": 0.0,
            "gate_approval_threshold": 0.01,
        }
        r = _gate(cfg).decide(_breakout_features(), "BREAKOUT", 1)
        assert r["final_score"] == 0.0
        assert r["approved"] is False

    # ── Bounds ────────────────────────────────────────────────────────────────

    def test_final_score_bounded_0_to_1_all_intents_and_directions(self):
        """final_score must be in [0.0, 1.0] for every intent×direction combination."""
        g = _gate()
        intents    = ["BREAKOUT", "PULLBACK", "LIQ_SWEEP", "REVERSAL", "UNKNOWN"]
        directions = [1, -1]
        for intent, direction in itertools.product(intents, directions):
            r = g.decide(_breakout_features(), intent, direction)
            assert 0.0 <= r["final_score"] <= 1.0, (
                f"Out of bounds for {intent}/{direction}: {r['final_score']}"
            )

    def test_components_all_bounded_0_to_1(self):
        """Every component score must be in [0.0, 1.0]."""
        r = _gate().decide(_breakout_features(), "BREAKOUT", 1)
        for k, v in r["components"].items():
            assert 0.0 <= v <= 1.0, f"{k} = {v} out of bounds"

    def test_final_score_missing_optional_features(self):
        """Gate must not crash when optional feature keys are absent."""
        f = {
            "close": 100.0, "high": 102.0, "low": 98.0, "atr": 2.0,
            "body_ratio": 0.7, "disp_strength": 2.0,
            "sweep_detected": False, "double_sweep": False,
            "retest_depth": 0.5, "candles_since_retest": 3,
            "ema_fast": 100.5, "ema_slow": 99.0, "momentum_score": 0.3,
            # Intentionally omitting volume, volume_ma20, highest_high_*, lowest_low_*
        }
        r = _gate().decide(f, "PULLBACK", 1)
        assert 0.0 <= r["final_score"] <= 1.0

    # ── Return structure ──────────────────────────────────────────────────────

    def test_decide_result_has_required_keys(self):
        r = _gate().decide(_breakout_features(), "BREAKOUT", 1)
        assert {"approved", "final_score", "components", "reason"} <= r.keys()
        assert {"intent_score", "vol_score", "liquidity_score", "structure_score"} <= r["components"].keys()

    def test_approved_is_bool(self):
        r = _gate().decide(_breakout_features(), "BREAKOUT", 1)
        assert isinstance(r["approved"], bool)

    def test_final_score_is_float(self):
        r = _gate().decide(_breakout_features(), "BREAKOUT", 1)
        assert isinstance(r["final_score"], float)
