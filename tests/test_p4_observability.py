# -*- coding: utf-8 -*-
"""
test_p4_observability.py
========================
Regression tests encoding the P4/P5 observability bugs found during
the architecture study (2026-05-22).

Two bugs identified and fixed in p4_execution_intent_attribution.py:

Bug 1 — candles_since_retest sentinel (P5):
  SYMPTOM:  All groups reported candles_since_retest = 99.
  CAUSE:    feats.get("candles_since_retest", 99) where feats=state.cached_features.
            The key is ABSENT from cached_features (it is computed dynamically in
            scoring as state.current_candle_index - state.retest_candle_index).
            The .get() default always fired.
  FIX:      Derive from engine state indices directly; return None if either
            index is missing (not 0 — avoids silent missing→0 encoding).
  RESULT:   All groups show candles_since_retest = 1 (flat → DISCARD feature).

Bug 2 — mean=0.0 → 'n/a' falsy evaluation:
  SYMPTOM:  double_sweep showed 'n/a' instead of '0.000' in feature comparison
            tables.  Same for any feature whose group-mean was exactly 0.0.
  CAUSE:    _fmt(e_s['mean'] or 'n/a') — Python falsy: 0.0 or 'n/a' = 'n/a'.
            This converted valid negative evidence (double_sweep=False → int=0
            → mean=0.0) into missing evidence ('n/a').
  FIX:      Explicit None guard: _safe(v) = 'n/a' if v is None else _fmt(v).
  RESULT:   double_sweep shows '0.000' (correct); genuinely absent features
            (momentum_score, volume_ratio etc.) still show 'n/a'.

These tests encode the fixed logic as standalone pure-function assertions.
No external dependencies, no backtest required.

References:
  scripts/analysis/p4_execution_intent_attribution.py — _capture_state(), display
  src/config_layer/crt_engine_v2.py — EngineState (current_candle_index,
                                       retest_candle_index, cached_features)
"""

import pytest


# ---------------------------------------------------------------------------
# candles_since_retest derivation logic
# ---------------------------------------------------------------------------

def _derive_csr(current_candle_index, retest_candle_index):
    """
    Corrected candles_since_retest derivation.

    Returns None if either index is missing (avoids silent missing→0 encoding).
    Returns max(0, cur - ret) otherwise (non-negative: current is always >= retest).
    """
    if current_candle_index is None or retest_candle_index is None:
        return None
    return max(0, current_candle_index - retest_candle_index)


class TestCanglesSinceRetest:
    """Bug 1: candles_since_retest derivation must not produce the sentinel 99."""

    OLD_SENTINEL = 99   # the value produced by the buggy .get() default

    def test_one_candle_after_retest(self):
        assert _derive_csr(10, 9) == 1

    def test_fifteen_candles_after_retest(self):
        assert _derive_csr(25, 10) == 15

    def test_zero_candles_same_bar(self):
        """Retest fires on the bar it is evaluated — result is 0, not None."""
        assert _derive_csr(5, 5) == 0

    def test_none_when_current_index_missing(self):
        """If engine state doesn't have the attribute, must return None, not 0."""
        assert _derive_csr(None, 5) is None

    def test_none_when_retest_index_missing(self):
        assert _derive_csr(10, None) is None

    def test_none_when_both_missing(self):
        assert _derive_csr(None, None) is None

    def test_result_is_never_old_sentinel_for_normal_pairs(self):
        """
        Regression: the old .get(key, 99) default produced 99 for EVERY call
        because the key was always absent from cached_features.

        Verify that ordinary index pairs do not accidentally equal 99.
        (Edge case: if cur - ret == 99 that is coincidentally valid, not buggy.)
        """
        normal_pairs = [
            (10, 9),    # 1 candle
            (25, 10),   # 15 candles
            (100, 99),  # 1 candle — valid but coincidence, not sentinel
            (200, 150), # 50 candles
        ]
        for cur, ret in normal_pairs:
            result = _derive_csr(cur, ret)
            # Only flag as problematic if the derivation itself equals old sentinel
            # AND the inputs don't legitimately produce 99
            if cur - ret != self.OLD_SENTINEL:
                assert result != self.OLD_SENTINEL, (
                    f"_derive_csr({cur}, {ret}) = {result} = old sentinel {self.OLD_SENTINEL} "
                    f"despite (cur - ret) = {cur - ret}. Likely a sentinel constant leaked."
                )

    def test_missing_key_from_dict_yields_none(self):
        """
        Core of Bug 1: feats.get("candles_since_retest", 99) always returned 99
        because the key is absent from state.cached_features.

        The correct pattern is to derive from engine state, not from cached_features.
        This test demonstrates the fallback logic.
        """
        cached_features = {
            "retest_depth": 0.35, "body_ratio": 0.4, "disp_strength": 0.8,
            "retest_index": 5, "session": 1, "double_sweep": False,
        }
        # The key is absent — .get() with sentinel is the WRONG approach
        buggy_result  = cached_features.get("candles_since_retest", 99)
        assert buggy_result == 99, "Key should be absent; demonstrates the original bug"

        # The correct approach: derive from engine indices
        correct_result = _derive_csr(current_candle_index=10, retest_candle_index=9)
        assert correct_result == 1
        assert correct_result != 99


# ---------------------------------------------------------------------------
# _safe() formatter — Bug 2: mean=0.0 → 'n/a' falsy evaluation
# ---------------------------------------------------------------------------

def _safe(v, decimals: int = 3) -> str:
    """
    Corrected formatter.

    None   → 'n/a'   (genuinely absent feature)
    0.0    → '0.000' (valid zero evidence — NOT 'n/a')
    False  → '0.000' (int(False)=0; double_sweep=False case)
    1.234  → '1.234'
    """
    if v is None:
        return "n/a"
    return f"{v:.{decimals}f}"


class TestSafeFormatter:
    """Bug 2: _safe() must distinguish None (absent) from 0.0 (valid zero)."""

    def test_none_yields_na(self):
        """None represents a genuinely absent feature — must show 'n/a'."""
        assert _safe(None)         == "n/a"
        assert _safe(None, decimals=4) == "n/a"

    def test_zero_float_yields_numeric(self):
        """
        0.0 is valid negative evidence (e.g., double_sweep mean over 4 executed
        trades where no trade had a double sweep).  Must NOT show 'n/a'.

        This was the core of Bug 2: `0.0 or 'n/a'` → `'n/a'` in Python.
        """
        assert _safe(0.0)  == "0.000", \
            "_safe(0.0) must return '0.000', not 'n/a' — falsy regression"
        assert _safe(0.0, decimals=4) == "0.0000"

    def test_zero_int_yields_numeric(self):
        """int(0) is also falsy — must not produce 'n/a'."""
        assert _safe(0) == "0.000"

    def test_false_yields_numeric(self):
        """
        double_sweep is stored as bool in cached_features.
        int(False) = 0, mean over group = 0.0 → must show '0.000', not 'n/a'.
        """
        assert _safe(False) == "0.000"

    def test_positive_value_formatted_correctly(self):
        assert _safe(1.234567) == "1.235"   # rounded to 3 decimals
        assert _safe(1.234567, decimals=4) == "1.2346"

    def test_negative_value_formatted_correctly(self):
        assert _safe(-0.375) == "-0.375"

    def test_buggy_pattern_documents_original_failure(self):
        """
        Demonstrates that `v or 'n/a'` is the WRONG pattern.
        This test exists as a negative example — it should always pass because
        we are verifying the known bug behavior.
        """
        v = 0.0
        # Buggy pattern used in original P4 script:
        buggy_result = v or "n/a"
        assert buggy_result == "n/a", \
            "Demonstrates the original falsy bug: 0.0 or 'n/a' = 'n/a'"

        # Correct pattern:
        correct_result = _safe(v)
        assert correct_result == "0.000", \
            "Correct pattern: None check first, then format"

        assert buggy_result != correct_result, \
            "The two patterns must differ on v=0.0 (that's the bug)"


# ---------------------------------------------------------------------------
# Intent lift computation
# ---------------------------------------------------------------------------

def _intent_lift(intent: str, all_setups: list, executed: list) -> float:
    """
    lift(intent) = executed_count(intent) / candidate_count(intent)

    Returns 0.0 if there are no candidates (avoids ZeroDivisionError).
    """
    candidates = sum(1 for r in all_setups if r.get("intent") == intent)
    exec_cnt   = sum(1 for r in executed   if r.get("intent") == intent)
    return exec_cnt / candidates if candidates > 0 else 0.0


class TestIntentLift:
    """Intent lift correctly computes executed_count / candidate_count."""

    # Simulated ETHUSDT baseline: 14 RETEST candidates → 4 executed
    # Actual P4 result: breakout=4 candidates/0 executed, reversal=10/4
    ALL_SETUPS = [{"intent": "breakout"}] * 4 + [{"intent": "reversal"}] * 10
    EXECUTED   = [{"intent": "reversal"}] * 4

    def test_breakout_lift_zero(self):
        """Breakout: 4 candidates, 0 executed → lift = 0.00."""
        assert _intent_lift("breakout", self.ALL_SETUPS, self.EXECUTED) == pytest.approx(0.00)

    def test_reversal_lift_forty_pct(self):
        """Reversal: 10 candidates, 4 executed → lift = 0.40."""
        assert _intent_lift("reversal", self.ALL_SETUPS, self.EXECUTED) == pytest.approx(0.40)

    def test_perfect_lift_all_executed(self):
        """All candidates for an intent executed → lift = 1.00."""
        setups   = [{"intent": "liq_sweep"}] * 3
        executed = [{"intent": "liq_sweep"}] * 3
        assert _intent_lift("liq_sweep", setups, executed) == pytest.approx(1.00)

    def test_zero_candidates_returns_zero_not_error(self):
        """
        An intent not present in the candidate set must return 0.0,
        not raise ZeroDivisionError.
        """
        setups   = [{"intent": "reversal"}] * 5
        executed = [{"intent": "reversal"}] * 2
        assert _intent_lift("breakout", setups, executed) == 0.0

    def test_lift_bounded_between_zero_and_one(self):
        """lift must be in [0, 1] for any valid input (count-based)."""
        for intent in ("breakout", "reversal"):
            lift = _intent_lift(intent, self.ALL_SETUPS, self.EXECUTED)
            assert 0.0 <= lift <= 1.0, f"lift({intent}) = {lift} out of [0, 1]"

    def test_empty_all_setups_returns_zero(self):
        """No setups at all → lift = 0.0 for any intent."""
        assert _intent_lift("reversal", [], []) == 0.0

    def test_lift_uses_candidate_count_not_rate(self):
        """
        lift = executed / candidates.

        This is a count ratio, not a "rate / rate" computation.
        Verify with a case that would differ under rate/rate:

          candidates for reversal = 10, total = 14  → candidate_rate = 0.714
          executed   for reversal = 4,  total = 4   → executed_rate  = 1.000
          rate/rate lift = 1.000 / 0.714 = 1.40  (wrong — exceeds 1.0)
          count lift     = 4 / 10 = 0.40          (correct)
        """
        lift = _intent_lift("reversal", self.ALL_SETUPS, self.EXECUTED)
        assert lift == pytest.approx(0.40), (
            "lift must be count-based (executed / candidates), not rate/rate"
        )
        assert lift <= 1.0, "count-based lift cannot exceed 1.0"
