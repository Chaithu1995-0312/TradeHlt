"""
tests/test_ultron_gate.py
==========================
Unit + integration tests for RegimeGovernor / UltronGovernor (src/core/regime_governor.py).
Canonical name: RegimeGovernor. UltronGovernor is the backward-compat class name.

Run:
    pytest tests/test_ultron_gate.py -v
    pytest tests/test_ultron_gate.py tests/test_engine_runner_dual_gate.py -v

Coverage:
    FIX 1 — soft penalty application and clamping
    FIX 2 — regime-based percentile gate
    FIX 3 — daily quota enforcement
    FIX 4 — rejection reason labels
    FIX 5 — mandatory structured logging
    Integration — 100 mixed signals across 10 days
    Backward-compat — existing engine_runner_dual_gate scenarios
"""
from __future__ import annotations

import logging
import sys
import os
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.regime_governor import UltronGovernor


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

DAY1 = date(2025, 1, 2)
DAY2 = date(2025, 1, 3)
DAY3 = date(2025, 1, 6)   # skip weekend

DUMMY_CFG = {"neutral_min_score": 0.32}


def fresh() -> UltronGovernor:
    return UltronGovernor()


def _dual(
    b_score: float = 0.0, b_dir: int = 0,
    t_score: float = 0.0, t_dir: int = 0,
) -> dict:
    return {
        "breakout": {"engine": "breakout", "score": b_score, "direction": b_dir},
        "trap":     {"engine": "trap",     "score": t_score, "direction": t_dir},
    }


def _high_trend() -> dict:
    """High-scoring trend signal that should always pass during warmup."""
    return _dual(b_score=0.90, b_dir=1)


def _high_range() -> dict:
    """High-scoring range signal that should always pass during warmup."""
    return _dual(t_score=0.90, t_dir=1)


# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 — Penalty application
# ─────────────────────────────────────────────────────────────────────────────

class TestPenaltyApplication:

    def test_range_regime_applies_015_penalty(self):
        g = fresh()
        r = g.evaluate("range", _dual(t_score=0.70, t_dir=1), DUMMY_CFG, DAY1)
        assert r["original_score"]  == pytest.approx(0.70)
        assert r["adjusted_score"]  == pytest.approx(0.55)

    def test_trend_regime_zero_penalty(self):
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.60, b_dir=1), DUMMY_CFG, DAY1)
        assert r["original_score"]  == pytest.approx(0.60)
        assert r["adjusted_score"]  == pytest.approx(0.60)

    def test_neutral_regime_applies_015_penalty(self):
        g = fresh()
        r = g.evaluate("neutral", _dual(b_score=0.80, b_dir=1), DUMMY_CFG, DAY1)
        assert r["original_score"]  == pytest.approx(0.80)
        assert r["adjusted_score"]  == pytest.approx(0.65)

    def test_penalty_clamps_at_zero(self):
        """Score 0.10 in neutral (0.15 penalty) → clamped to 0.0."""
        g = fresh()
        r = g.evaluate("neutral", _dual(b_score=0.10, b_dir=1), DUMMY_CFG, DAY1)
        assert r["adjusted_score"] == pytest.approx(0.0)

    def test_penalty_clamps_at_one(self):
        """Score 1.0 in trend (0.0 penalty) stays 1.0."""
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=1.0, b_dir=1), DUMMY_CFG, DAY1)
        assert r["adjusted_score"] == pytest.approx(1.0)

    def test_direction_zero_adds_extra_010_penalty(self):
        """direction=0 → base 0.15 + dir 0.10 = 0.25 total."""
        g = fresh()
        # range regime (0.15) + direction=0 (+0.10) = 0.25; score=0.60 → adj=0.35
        r = g.evaluate("range", _dual(t_score=0.60, t_dir=0), DUMMY_CFG, DAY1)
        assert r["adjusted_score"] == pytest.approx(0.35)

    def test_trend_direction_zero_adds_010_only(self):
        """trend (0.00) + direction=0 (+0.10) = 0.10."""
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.80, b_dir=0), DUMMY_CFG, DAY1)
        assert r["adjusted_score"] == pytest.approx(0.70)

    def test_original_score_preserved_unchanged(self):
        """original_score must always equal the raw engine score."""
        g = fresh()
        r = g.evaluate("range", _dual(t_score=0.55, t_dir=1), DUMMY_CFG, DAY1)
        assert r["original_score"] == pytest.approx(0.55)


# ─────────────────────────────────────────────────────────────────────────────
# FIX 2 — Percentile gate
# ─────────────────────────────────────────────────────────────────────────────

class TestPercentileGate:

    def _seed(self, gov: UltronGovernor, regime: str, scores: list, day: date = DAY1) -> None:
        """Push a batch of raw scores into the window, routing to the right engine."""
        for s in scores:
            if regime == "range":
                # range selects trap engine; must populate t_score
                gov.evaluate(regime, _dual(t_score=s, t_dir=1), DUMMY_CFG, day)
            else:
                gov.evaluate(regime, _dual(b_score=s, b_dir=1), DUMMY_CFG, day)

    def test_fallback_during_warmup_passes_above_045(self):
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.50, b_dir=1), DUMMY_CFG, DAY1)
        assert r["allow"] is True      # 0.50 - 0.00 = 0.50 > 0.45

    def test_fallback_during_warmup_rejects_below_045(self):
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.40, b_dir=1), DUMMY_CFG, DAY1)
        assert r["allow"] is False
        assert r["reject_stage"] == "ultron_penalty"

    def test_percentile_threshold_computed_after_window_fills(self):
        """After seeding 20 trend scores at 0.50, a score of 0.50 sits at the
        75th percentile exactly — should pass."""
        g = fresh()
        # Seed 20 identical scores; after penalty, all are 0.50 (no trend penalty)
        self._seed(g, "trend", [0.50] * 20, day=DAY1)
        r = g.evaluate("trend", _dual(b_score=0.50, b_dir=1), DUMMY_CFG, DAY2)
        # sorted([0.50]*21), idx=int(0.75*21)=15, threshold=0.50; 0.50>=0.50 → pass
        assert r["allow"] is True

    def test_range_rejects_low_adj_score_after_window_builds(self):
        """Seed 20 range signals at 0.70 (adj=0.55 after 0.15 penalty).
        A new signal at 0.50 (adj=0.35) should fall below the 90th percentile."""
        g = fresh()
        self._seed(g, "range", [0.70] * 20, day=DAY1)
        r = g.evaluate("range", _dual(t_score=0.50, t_dir=1), DUMMY_CFG, DAY2)
        # Window 90th pct ≈ 0.55; new adj=0.35 < 0.55 → filtered
        assert r["allow"] is False
        assert r["reject_stage"] == "ultron_penalty"

    def test_high_score_passes_after_window_builds(self):
        """A very high score should sit above any realistic window percentile."""
        g = fresh()
        self._seed(g, "neutral", [0.40] * 20, day=DAY1)
        # adj = 0.90 - 0.15 = 0.75; well above 92nd pct of window [0.25]*21
        r = g.evaluate("neutral", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY2)
        assert r["allow"] is True

    def test_window_bounded_at_100(self):
        g = fresh()
        for i in range(150):
            g.evaluate("trend", _dual(b_score=0.80, b_dir=1), DUMMY_CFG, DAY1)
        assert len(g._windows["trend"]) == g.WINDOW_MAXLEN

    def test_different_regimes_have_independent_windows(self):
        """Seeding range window must not affect trend window."""
        g = fresh()
        self._seed(g, "range", [0.90] * 20, day=DAY1)
        # trend window is still empty → warmup fallback 0.45 applies
        r = g.evaluate("trend", _dual(b_score=0.50, b_dir=1), DUMMY_CFG, DAY2)
        # 0.50 > 0.45 → should pass during warmup
        assert r["allow"] is True


# ─────────────────────────────────────────────────────────────────────────────
# FIX 3 — Daily quota
# ─────────────────────────────────────────────────────────────────────────────

class TestDailyQuota:

    def _pass_signal(self, regime: str = "trend") -> dict:
        """Signal that reliably passes warmup percentile (adj > 0.45)."""
        return _dual(b_score=0.90, b_dir=1)

    def test_max_three_pass_per_day(self):
        g = fresh()
        results = [
            g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY1)
            for _ in range(5)
        ]
        passed   = [r for r in results if r["allow"]]
        filtered = [r for r in results if not r["allow"]]
        assert len(passed)   == UltronGovernor.MAX_TRADES_PER_BATCH
        assert len(filtered) == 5 - UltronGovernor.MAX_TRADES_PER_BATCH

    def test_quota_filtered_reason_is_ultron_quota(self):
        g = fresh()
        for _ in range(UltronGovernor.MAX_TRADES_PER_BATCH):
            g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY1)
        r = g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY1)
        assert r["allow"]        is False
        assert r["reason"]       == "ultron_quota"
        assert r["reject_stage"] == "ultron_quota"

    def test_quota_resets_on_new_date(self):
        g = fresh()
        for _ in range(UltronGovernor.MAX_TRADES_PER_BATCH):
            g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY1)
        # DAY1 exhausted — DAY2 should allow fresh 3
        r = g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY2)
        assert r["allow"]      is True
        assert r["quota_rank"] == 1

    def test_quota_rank_increments_correctly(self):
        g = fresh()
        ranks = []
        for _ in range(UltronGovernor.MAX_TRADES_PER_BATCH):
            r = g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY1)
            ranks.append(r["quota_rank"])
        assert ranks == [1, 2, 3]

    def test_filtered_decisions_have_quota_rank_zero(self):
        g = fresh()
        for _ in range(UltronGovernor.MAX_TRADES_PER_BATCH):
            g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY1)
        r = g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY1)
        assert r["quota_rank"] == 0

    def test_pass_quota_rank_is_nonzero(self):
        g = fresh()
        r = g.evaluate("trend", self._pass_signal(), DUMMY_CFG, DAY1)
        assert r["allow"] is True
        assert r["quota_rank"] >= 1

    def test_multi_day_quota_independence(self):
        """Each day is independently capped at MAX_TRADES_PER_BATCH."""
        g = fresh()
        for day_offset in range(3):
            d = DAY1 + timedelta(days=day_offset)
            passed = 0
            for _ in range(5):
                r = g.evaluate("trend", self._pass_signal(), DUMMY_CFG, d)
                if r["allow"]:
                    passed += 1
            assert passed == UltronGovernor.MAX_TRADES_PER_BATCH


# ─────────────────────────────────────────────────────────────────────────────
# FIX 4 — Result schema and rejection labels
# ─────────────────────────────────────────────────────────────────────────────

class TestResultSchema:

    def test_pass_result_fields(self):
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        assert r["allow"]          is True
        assert r["reject_stage"]   == ""
        assert r["quota_rank"]     >= 1
        assert 0.0 <= r["adjusted_score"] <= 1.0
        assert "selected" in r
        assert "original_score" in r

    def test_penalty_filtered_result_fields(self):
        g = fresh()
        # Score guaranteed to produce adjusted < 0.45 during warmup
        r = g.evaluate("neutral", _dual(b_score=0.10, b_dir=1), DUMMY_CFG, DAY1)
        assert r["allow"]          is False
        assert r["reason"]         == "ultron_penalty"
        assert r["reject_stage"]   == "ultron_penalty"
        assert r["quota_rank"]     == 0

    def test_quota_filtered_result_fields(self):
        g = fresh()
        for _ in range(UltronGovernor.MAX_TRADES_PER_BATCH):
            g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        r = g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        assert r["allow"]          is False
        assert r["reason"]         == "ultron_quota"
        assert r["reject_stage"]   == "ultron_quota"
        assert r["quota_rank"]     == 0

    def test_pass_reject_stage_is_empty_string(self):
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        assert r["reject_stage"] == ""

    def test_selected_populated_on_pass(self):
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        assert r["selected"] is not None
        assert "engine" in r["selected"]

    def test_selected_populated_on_filter(self):
        """selected is populated even on filtered decisions."""
        g = fresh()
        r = g.evaluate("neutral", _dual(b_score=0.05, b_dir=0), DUMMY_CFG, DAY1)
        assert r["selected"] is not None

    def test_reason_on_pass_is_gate_reason(self):
        """Passed results use regime-specific gate reason, not penalty/quota."""
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        assert r["reason"] in (
            "regime_trend", "regime_range", "regime_neutral_resolved"
        )

    def test_engine_runner_compat_keys_present(self):
        """All keys consumed by engine_runner.py must be present."""
        g = fresh()
        r = g.evaluate("range", _dual(t_score=0.80, t_dir=-1), DUMMY_CFG, DAY1)
        for key in ("allow", "reason", "selected"):
            assert key in r, f"Missing engine_runner key: {key!r}"


# ─────────────────────────────────────────────────────────────────────────────
# FIX 5 — Mandatory structured logging
# ─────────────────────────────────────────────────────────────────────────────

class TestLogging:

    def test_every_evaluate_emits_log_record(self, caplog):
        g = fresh()
        with caplog.at_level(logging.INFO, logger="ULTRON_GATE"):
            g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        assert any("RegimeGov" in r.message for r in caplog.records)

    def test_log_contains_required_fields(self, caplog):
        g = fresh()
        with caplog.at_level(logging.INFO, logger="ULTRON_GATE"):
            g.evaluate("range", _dual(t_score=0.70, t_dir=1), DUMMY_CFG, DAY1)
        log_text = " ".join(r.message for r in caplog.records)
        for field in ("regime=", "original_score=", "adjusted_score=",
                      "allow=", "reason=", "reject_stage=",
                      "quota_rank=", "window_n="):
            assert field in log_text, f"Log missing field: {field!r}"

    def test_filtered_decision_also_logs(self, caplog):
        g = fresh()
        with caplog.at_level(logging.INFO, logger="ULTRON_GATE"):
            g.evaluate("neutral", _dual(b_score=0.05, b_dir=0), DUMMY_CFG, DAY1)
        assert any("RegimeGov" in r.message for r in caplog.records)


# ─────────────────────────────────────────────────────────────────────────────
# Reset and report
# ─────────────────────────────────────────────────────────────────────────────

class TestResetAndReport:

    def test_reset_clears_all_windows(self):
        g = fresh()
        for _ in range(20):
            g.evaluate("trend", _dual(b_score=0.80, b_dir=1), DUMMY_CFG, DAY1)
        g.reset()
        for w in g._windows.values():
            assert len(w) == 0

    def test_reset_clears_daily_quota(self):
        g = fresh()
        for _ in range(UltronGovernor.MAX_TRADES_PER_BATCH):
            g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        g.reset()
        r = g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        assert r["allow"] is True

    def test_report_returns_string(self):
        g = fresh()
        g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        s = g.report()
        assert isinstance(s, str)
        assert "RegimeGovernor" in s

    def test_report_reflects_pass_count(self):
        g = fresh()
        for _ in range(2):
            g.evaluate("trend", _dual(b_score=0.90, b_dir=1), DUMMY_CFG, DAY1)
        assert "passed=2" in g.report()

    def test_report_reflects_evaluated_count(self):
        g = fresh()
        for _ in range(5):
            g.evaluate("trend", _dual(b_score=0.30, b_dir=1), DUMMY_CFG, DAY1)
        assert "evaluated=5" in g.report()


# ─────────────────────────────────────────────────────────────────────────────
# Engine selection logic (regime rules preserved)
# ─────────────────────────────────────────────────────────────────────────────

class TestEngineSelection:

    def test_trend_selects_breakout(self):
        g = fresh()
        r = g.evaluate("trend", _dual(b_score=0.90, b_dir=1, t_score=0.50, t_dir=-1),
                        DUMMY_CFG, DAY1)
        assert r["selected"]["engine"] == "breakout"

    def test_range_selects_trap(self):
        g = fresh()
        r = g.evaluate("range", _dual(b_score=0.50, b_dir=1, t_score=0.90, t_dir=-1),
                        DUMMY_CFG, DAY1)
        assert r["selected"]["engine"] == "trap"

    def test_neutral_selects_higher_score(self):
        g = fresh()
        # breakout=0.40, trap=0.60 → trap wins
        r = g.evaluate("neutral", _dual(b_score=0.40, b_dir=1, t_score=0.60, t_dir=-1),
                        DUMMY_CFG, DAY1)
        assert r["selected"]["engine"] == "trap"

    def test_neutral_tie_selects_breakout(self):
        g = fresh()
        r = g.evaluate("neutral", _dual(b_score=0.50, b_dir=1, t_score=0.50, t_dir=-1),
                        DUMMY_CFG, DAY1)
        assert r["selected"]["engine"] == "breakout"   # b_score >= t_score → breakout


# ─────────────────────────────────────────────────────────────────────────────
# Integration test — 100 mixed signals over 10 days
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegration:
    """
    100 deterministic signals × 10 trading days.
    Mixed regimes; scores ∈ [0.50, 0.89].

    Invariants:
        pass_count  > 0
        pass_count <= MAX_TRADES_PER_BATCH × num_days
        FILTERED decisions → non-empty reject_stage
        PASS decisions     → reject_stage == ""
        quota_rank >= 1 on all PASS decisions
    """

    REGIMES = ["trend", "range", "neutral"]

    def _signals(self):
        """100 deterministic signals: 10 days × 10 signals, cycling regimes."""
        signals = []
        base = date(2025, 1, 2)
        for i in range(100):
            day_offset = i // 10
            d          = base + timedelta(days=day_offset)
            score      = 0.50 + (i % 40) * 0.01          # [0.50 .. 0.89]
            regime     = self.REGIMES[i % 3]
            signals.append((regime, score, d))
        return signals

    def test_pass_count_positive(self):
        g = fresh()
        results = [
            g.evaluate(regime, _dual(b_score=s, b_dir=1, t_score=s, t_dir=1),
                        DUMMY_CFG, d)
            for regime, s, d in self._signals()
        ]
        assert sum(1 for r in results if r["allow"]) > 0

    def test_pass_count_bounded_by_quota(self):
        g = fresh()
        signals = self._signals()
        results = [
            g.evaluate(regime, _dual(b_score=s, b_dir=1, t_score=s, t_dir=1),
                        DUMMY_CFG, d)
            for regime, s, d in signals
        ]
        pass_count = sum(1 for r in results if r["allow"])
        num_days   = len({d for _, _, d in signals})
        assert pass_count <= UltronGovernor.MAX_TRADES_PER_BATCH * num_days

    def test_reject_stage_consistent(self):
        g = fresh()
        results = [
            g.evaluate(regime, _dual(b_score=s, b_dir=1, t_score=s, t_dir=1),
                        DUMMY_CFG, d)
            for regime, s, d in self._signals()
        ]
        for r in results:
            if r["allow"]:
                assert r["reject_stage"] == "", \
                    f"PASS decision has non-empty reject_stage: {r}"
            else:
                assert r["reject_stage"] in ("ultron_penalty", "ultron_quota"), \
                    f"FILTERED decision has unexpected reject_stage: {r['reject_stage']!r}"

    def test_quota_rank_positive_on_pass(self):
        g = fresh()
        results = [
            g.evaluate(regime, _dual(b_score=s, b_dir=1, t_score=s, t_dir=1),
                        DUMMY_CFG, d)
            for regime, s, d in self._signals()
        ]
        for r in results:
            if r["allow"]:
                assert r["quota_rank"] >= 1

    def test_report_reflects_totals(self):
        g = fresh()
        results = [
            g.evaluate(regime, _dual(b_score=s, b_dir=1, t_score=s, t_dir=1),
                        DUMMY_CFG, d)
            for regime, s, d in self._signals()
        ]
        pass_count = sum(1 for r in results if r["allow"])
        report     = g.report()
        assert f"passed={pass_count}" in report
        assert "evaluated=100" in report


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat — existing engine_runner_dual_gate scenarios
# ─────────────────────────────────────────────────────────────────────────────

class TestBackwardCompat:
    """
    Verify that scenarios tested by test_engine_runner_dual_gate.py still
    produce the expected outcome when routed through UltronGovernor.
    """

    def test_trend_high_score_passes(self):
        """trend + high breakout score → allow=True (existing test: "Approved")."""
        g = fresh()
        dual = {
            "breakout": {"engine": "breakout", "score": 0.85, "direction": 1,
                         "reason": "trend_follow",
                         "meta": {"trend_bias": 1.0, "momentum": 0.8, "ema_spread": 0.9}},
            "trap":     {"engine": "trap",     "score": 0.0,  "direction": 0,
                         "reason": "no_sweep", "meta": {}},
        }
        r = g.evaluate("trend", dual, DUMMY_CFG, DAY1)
        assert r["allow"] is True
        assert r["selected"]["engine"] == "breakout"

    def test_range_high_trap_score_passes(self):
        """range + high trap score → allow=True (existing test: "Approved")."""
        g = fresh()
        dual = {
            "breakout": {"engine": "breakout", "score": 0.05, "direction": 0,
                         "reason": "weak_breakout", "meta": {}},
            "trap":     {"engine": "trap",     "score": 0.90, "direction": 1,
                         "reason": "liquidity_trap",
                         "meta": {"sweep_detected": 1, "disp_strength": 0.9, "trend_bias": -1.0}},
        }
        r = g.evaluate("range", dual, DUMMY_CFG, DAY1)
        assert r["allow"] is True
        assert r["selected"]["engine"] == "trap"

    def test_neutral_near_zero_scores_rejected(self):
        """
        neutral + near-zero b_score and t_score → allow=False.
        Previously: hard "neutral_low_confidence".
        Now: "ultron_penalty" (same REJECT outcome, different reason label).
        """
        g = fresh()
        dual = {
            "breakout": {"engine": "breakout", "score": 0.02, "direction": 0,
                         "reason": "weak_breakout", "meta": {}},
            "trap":     {"engine": "trap",     "score": 0.0,  "direction": 0,
                         "reason": "no_sweep",     "meta": {}},
        }
        r = g.evaluate("neutral", dual, DUMMY_CFG, DAY1)
        assert r["allow"] is False
        # Rejection reason now starts with "ultron_" not "neutral_low_confidence"
        assert r["reason"] in ("ultron_penalty", "ultron_quota")


# ─────────────────────────────────────────────────────────────────────────────
# Standalone runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [
        # FIX 1
        TestPenaltyApplication().test_range_regime_applies_015_penalty,
        TestPenaltyApplication().test_trend_regime_zero_penalty,
        TestPenaltyApplication().test_neutral_regime_applies_015_penalty,
        TestPenaltyApplication().test_penalty_clamps_at_zero,
        TestPenaltyApplication().test_penalty_clamps_at_one,
        TestPenaltyApplication().test_direction_zero_adds_extra_010_penalty,
        TestPenaltyApplication().test_original_score_preserved_unchanged,
        # FIX 2
        TestPercentileGate().test_fallback_during_warmup_passes_above_045,
        TestPercentileGate().test_fallback_during_warmup_rejects_below_045,
        TestPercentileGate().test_window_bounded_at_100,
        # FIX 3
        TestDailyQuota().test_max_three_pass_per_day,
        TestDailyQuota().test_quota_resets_on_new_date,
        TestDailyQuota().test_quota_rank_increments_correctly,
        TestDailyQuota().test_filtered_decisions_have_quota_rank_zero,
        TestDailyQuota().test_multi_day_quota_independence,
        # FIX 4
        TestResultSchema().test_pass_result_fields,
        TestResultSchema().test_penalty_filtered_result_fields,
        TestResultSchema().test_quota_filtered_result_fields,
        TestResultSchema().test_engine_runner_compat_keys_present,
        # Engine selection
        TestEngineSelection().test_trend_selects_breakout,
        TestEngineSelection().test_range_selects_trap,
        TestEngineSelection().test_neutral_selects_higher_score,
        # Reset/report
        TestResetAndReport().test_reset_clears_all_windows,
        TestResetAndReport().test_reset_clears_daily_quota,
        TestResetAndReport().test_report_returns_string,
        # Integration
        TestIntegration().test_pass_count_positive,
        TestIntegration().test_pass_count_bounded_by_quota,
        TestIntegration().test_reject_stage_consistent,
        # Backward-compat
        TestBackwardCompat().test_trend_high_score_passes,
        TestBackwardCompat().test_range_high_trap_score_passes,
        TestBackwardCompat().test_neutral_near_zero_scores_rejected,
    ]

    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__qualname__}")
            passed += 1
        except Exception:
            print(f"  FAIL  {fn.__qualname__}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"  {passed} passed / {failed} failed  ({len(tests)} total)")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
