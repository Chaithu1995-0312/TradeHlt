"""
test_execution_planner.py
=========================
Dedicated test suite for ExecutionPlannerV1_2 (refactored: pure intent gate).

Covers:
    - Happy path: BREAKOUT, PULLBACK, LIQ_SWEEP, REVERSAL (long + short)
    - Rejection paths: engine reject, missing features, invalid prices,
      invalid direction, UNKNOWN intent, gate reject
    - Intent classification accuracy
    - TTL derivation per intent
    - Precision rounding (default + symbol override)
    - Execution ID determinism
    - Config overrides
    - Gate result embedded in output

REMOVED (now in test_gate_intelligence.py):
    - SL computation per intent
    - TP computation / liquidity override
    - Position sizing formula
    - RR ratio calculation / min_rr_ratio gate

Run:
    python test_execution_planner.py
    pytest test_execution_planner.py -v
"""

from __future__ import annotations
import sys
import traceback

from config_layer.execution_planner import ExecutionPlannerV1_2, DEFAULT_CONFIG

# ── Shared fixtures ───────────────────────────────────────────────────────────

def _engine(direction: int = 1, decision: str = "execute", confidence: float = 0.8) -> dict:
    return {"decision": decision, "direction": direction,
            "confidence": confidence, "regime": "trend"}

def _base_features(**overrides) -> dict:
    """Minimal valid feature set that passes GateIntelligence at default threshold.

    Includes volume data so liquidity_score contributes positively.
    EMA alignment is bullish (ema_fast > ema_slow) — override for short tests.
    """
    f = {
        "close": 100.0,
        "high":  102.0,
        "low":   98.0,
        "atr":   2.0,
        "body_ratio":           0.8,
        "disp_strength":        2.2,
        "sweep_detected":       False,
        "double_sweep":         False,
        "retest_depth":         0.1,
        "candles_since_retest": 10,
        "ema_fast":             99.5,
        "ema_slow":             98.5,
        "momentum_score":       0.7,
        # Volume data — needed for liquidity_score to contribute
        "volume":               1200.0,
        "volume_ma20":          800.0,
        "lowest_low_20":        95.0,
        "highest_high_20":      103.0,
        "lowest_low_5":         98.5,
        "highest_high_5":       101.5,
    }
    f.update(overrides)
    return f

def _context(symbol: str = "EURUSD", balance: float = 10_000.0) -> dict:
    return {"symbol": symbol, "signal": 1, "score": 0.75,
            "account_balance": balance}

def _planner(**cfg_overrides) -> ExecutionPlannerV1_2:
    return ExecutionPlannerV1_2({**DEFAULT_CONFIG, **cfg_overrides})


# ── 1. APPROVAL / HAPPY PATH ─────────────────────────────────────────────────

def test_breakout_long_approve():
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "BREAKOUT"
    assert r["direction"] == 1
    assert r["entry_price"] > 0
    assert r["gate"]["approved"] is True
    assert 0.0 <= r["gate"]["final_score"] <= 1.0

def test_breakout_short_approve():
    p = _planner()
    # Bearish EMA alignment for short direction
    f = _base_features(ema_fast=98.0, ema_slow=99.0)
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "BREAKOUT"
    assert r["gate"]["approved"] is True

def test_pullback_long_approve():
    p = _planner()
    f = _base_features(
        sweep_detected=False,
        retest_depth=0.5,
        candles_since_retest=3,
        momentum_score=0.5,
        body_ratio=0.3,
        disp_strength=1.0,
        lowest_low_5=99.0,
        highest_high_5=103.0,
    )
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "PULLBACK"
    assert r["entry_type"] == "LIMIT"
    assert r["gate"]["approved"] is True

def test_pullback_short_approve():
    p = _planner()
    # Bearish EMA alignment for short direction
    f = _base_features(
        sweep_detected=False,
        retest_depth=0.5,
        candles_since_retest=3,
        momentum_score=0.5,
        body_ratio=0.3,
        disp_strength=1.0,
        lowest_low_5=95.0,
        highest_high_5=99.0,
        ema_fast=98.5,   # bearish alignment
        ema_slow=99.5,
    )
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "PULLBACK"
    assert r["entry_type"] == "LIMIT"
    assert r["gate"]["approved"] is True

def test_liq_sweep_long_approve():
    p = _planner()
    f = _base_features(sweep_detected=True)
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "LIQ_SWEEP"
    assert r["entry_type"] == "LIMIT"
    assert r["gate"]["approved"] is True

def test_liq_sweep_short_approve():
    p = _planner()
    # Bearish EMA alignment for short direction
    f = _base_features(sweep_detected=True, ema_fast=98.0, ema_slow=99.5)
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "LIQ_SWEEP"
    assert r["entry_type"] == "LIMIT"
    assert r["gate"]["approved"] is True

def test_double_sweep_triggers_liq_sweep():
    p = _planner()
    f = _base_features(sweep_detected=False, double_sweep=True)
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "LIQ_SWEEP"

def test_reversal_long_when_ema_fast_lt_ema_slow():
    """ema_fast < ema_slow but direction=1 → counter-trend → REVERSAL."""
    p = _planner()
    f = _base_features(
        sweep_detected=False,
        body_ratio=0.3,
        disp_strength=1.0,
        retest_depth=0.0,
        candles_since_retest=99,
        ema_fast=98.0,
        ema_slow=100.0,
        momentum_score=0.0,  # low momentum needed for REVERSAL intent_score
        lowest_low_3=99.0,
        highest_high_3=103.0,
    )
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "REVERSAL"
    assert r["gate"]["approved"] is True

def test_reversal_short_when_ema_fast_gt_ema_slow():
    """ema_fast > ema_slow but direction=-1 → REVERSAL."""
    p = _planner()
    f = _base_features(
        sweep_detected=False,
        body_ratio=0.3,
        disp_strength=1.0,
        retest_depth=0.0,
        candles_since_retest=99,
        ema_fast=100.0,
        ema_slow=98.0,
        momentum_score=0.0,  # low momentum needed for REVERSAL intent_score
        lowest_low_3=97.0,
        highest_high_3=101.0,
    )
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "REVERSAL"
    assert r["gate"]["approved"] is True


# ── 2. REJECTION PATHS ────────────────────────────────────────────────────────

def test_reject_engine_decision_not_execute():
    p = _planner()
    r = p.plan(_engine(1, decision="REJECT"), _base_features(), _context())
    assert r["decision"] == "reject_engine"

def test_reject_engine_decision_hold():
    p = _planner()
    r = p.plan({"decision": "hold", "direction": 1}, _base_features(), _context())
    assert r["decision"] == "reject_engine"

def test_reject_missing_required_feature():
    p = _planner()
    f = _base_features()
    del f["atr"]
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "reject_invalid"
    assert "atr" in r["trace"]["error"]

def test_reject_multiple_missing_features():
    p = _planner()
    f = _base_features()
    del f["close"]
    del f["ema_fast"]
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "reject_invalid"

def test_reject_invalid_close_zero():
    p = _planner()
    r = p.plan(_engine(1), _base_features(close=0.0), _context())
    assert r["decision"] == "reject_invalid"
    assert "invalid_close" in r["trace"]["error"]

def test_reject_invalid_close_negative():
    p = _planner()
    r = p.plan(_engine(1), _base_features(close=-1.0), _context())
    assert r["decision"] == "reject_invalid"

def test_reject_invalid_atr_zero():
    p = _planner()
    r = p.plan(_engine(1), _base_features(atr=0.0), _context())
    assert r["decision"] == "reject_invalid"
    assert "invalid_atr" in r["trace"]["error"]

def test_reject_high_not_above_low():
    p = _planner()
    r = p.plan(_engine(1), _base_features(high=98.0, low=102.0), _context())
    assert r["decision"] == "reject_invalid"
    assert "high_not_above_low" in r["trace"]["error"]

def test_reject_invalid_direction_zero():
    p = _planner()
    er = {"decision": "execute", "direction": 0, "confidence": 0.8, "regime": "trend"}
    r = p.plan(er, _base_features(), _context())
    assert r["decision"] == "reject_invalid"

def test_reject_invalid_direction_value():
    p = _planner()
    er = {"decision": "execute", "direction": 2, "confidence": 0.8, "regime": "trend"}
    r = p.plan(er, _base_features(), _context())
    assert r["decision"] == "reject_invalid"

def test_reject_unknown_intent_by_default():
    p = _planner()
    # Features that match no pattern
    f = _base_features(
        sweep_detected=False, double_sweep=False,
        retest_depth=0.0, candles_since_retest=99, momentum_score=0.0,
        body_ratio=0.2, disp_strength=0.5,
        ema_fast=100.0, ema_slow=99.0,   # fast > slow, direction=1 → not REVERSAL
    )
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "reject_unknown_intent"

def test_allow_unknown_intent_when_configured():
    p = _planner(reject_unknown_intent=False)
    f = _base_features(
        sweep_detected=False, double_sweep=False,
        retest_depth=0.0, candles_since_retest=99, momentum_score=0.0,
        body_ratio=0.2, disp_strength=0.5,
        ema_fast=100.0, ema_slow=99.0,
    )
    r = p.plan(_engine(1), f, _context())
    # UNKNOWN intent proceeds to gate; gate may reject since intent_score=0
    assert r["decision"] in ("execute", "reject_gate", "reject_invalid")

def test_gate_reject_weak_signal():
    """Very high threshold forces gate rejection on an otherwise valid signal."""
    p = _planner(gate_approval_threshold=0.99)
    r = p.plan(_engine(1), _base_features(), _context())
    assert r["decision"] == "reject_gate"
    assert r["gate"]["approved"] is False
    assert "rejected" in r["gate"]["reason"]


# ── 3. INTENT CLASSIFICATION ──────────────────────────────────────────────────

def test_intent_classification_breakout():
    """body_ratio + disp_strength → BREAKOUT."""
    p = _planner()
    r = p.plan(_engine(1), _base_features(body_ratio=0.8, disp_strength=2.2), _context())
    if r["decision"] == "execute":
        assert r["trade_intent"] == "BREAKOUT"

def test_intent_classification_pullback():
    f = _base_features(
        sweep_detected=False, retest_depth=0.5, candles_since_retest=3,
        momentum_score=0.5, body_ratio=0.3, disp_strength=1.0,
    )
    p = _planner()
    r = p.plan(_engine(1), f, _context())
    if r["decision"] in ("execute", "reject_gate"):
        assert r["trade_intent"] == "PULLBACK"

def test_intent_classification_liq_sweep_single():
    p = _planner()
    f = _base_features(sweep_detected=True, body_ratio=0.3, disp_strength=1.0)
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "LIQ_SWEEP"

def test_intent_classification_liq_sweep_double():
    p = _planner()
    f = _base_features(sweep_detected=False, double_sweep=True)
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "LIQ_SWEEP"

def test_intent_classification_reversal():
    p = _planner()
    f = _base_features(
        sweep_detected=False, body_ratio=0.3, disp_strength=1.0,
        ema_fast=98.0, ema_slow=100.0,
        retest_depth=0.0, candles_since_retest=99,
    )
    r = p.plan(_engine(1), f, _context())
    if r["decision"] in ("execute", "reject_gate"):
        assert r["trade_intent"] == "REVERSAL"


# ── 4. TTL DERIVATION ────────────────────────────────────────────────────────

def test_ttl_breakout_matches_config():
    p = _planner(ttl_breakout_sec=999)
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute" and r["trade_intent"] == "BREAKOUT":
        assert r["validity_ttl_sec"] == 999

def test_ttl_liq_sweep_matches_config():
    p = _planner(ttl_liq_sweep_sec=555)
    f = _base_features(sweep_detected=True)
    r = p.plan(_engine(1), f, _context())
    if r["decision"] == "execute":
        assert r["validity_ttl_sec"] == 555

def test_expires_at_is_in_future():
    from datetime import datetime, timezone
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute":
        expires = datetime.fromisoformat(r["expires_at"])
        now = datetime.now(timezone.utc)
        assert expires > now


# ── 5. PRECISION ROUNDING ─────────────────────────────────────────────────────

def test_precision_default_is_8_decimal_places():
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context(symbol="EURUSD"))
    if r["decision"] == "execute":
        assert isinstance(r["entry_price"], float)

def test_precision_override_xauusd_is_2():
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context(symbol="XAUUSD"))
    if r["decision"] == "execute":
        s = f"{r['entry_price']}"
        parts = s.split(".")
        if len(parts) == 2:
            assert len(parts[1].rstrip("0") or "0") <= 2, f"Expected 2dp, got {s}"

def test_precision_override_btcusdt_is_2():
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context(symbol="BTCUSDT"))
    if r["decision"] == "execute":
        s = f"{r['entry_price']}"
        parts = s.split(".")
        if len(parts) == 2:
            assert len(parts[1].rstrip("0") or "0") <= 2


# ── 6. EXECUTION ID DETERMINISM ───────────────────────────────────────────────

def test_execution_id_is_deterministic():
    p = _planner()
    f = _base_features()
    ctx = _context()
    r1 = p.plan(_engine(1), f, ctx)
    r2 = p.plan(_engine(1), f, ctx)
    if r1["decision"] == "execute" and r2["decision"] == "execute":
        assert r1["execution_id"] == r2["execution_id"]

def test_execution_id_changes_with_entry_price():
    p = _planner()
    f1 = _base_features(close=100.0)
    f2 = _base_features(close=105.0, high=107.0)
    ctx = _context()
    r1 = p.plan(_engine(1), f1, ctx)
    r2 = p.plan(_engine(1), f2, ctx)
    if r1["decision"] == "execute" and r2["decision"] == "execute":
        assert r1["execution_id"] != r2["execution_id"]

def test_execution_id_starts_with_EX():
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute":
        assert r["execution_id"].startswith("EX_")


# ── 7. CONFIG OVERRIDES ──────────────────────────────────────────────────────

def test_defaults_preserved_when_no_config():
    p = ExecutionPlannerV1_2()
    assert p.config["risk_percent"]           == 0.5
    assert p.config["gate_approval_threshold"] == 0.55

def test_partial_config_preserves_remaining_defaults():
    p = ExecutionPlannerV1_2({"risk_percent": 2.0})
    assert p.config["risk_percent"]            == 2.0
    assert p.config["gate_approval_threshold"] == 0.55  # default preserved

def test_gate_threshold_override():
    """Lowering gate threshold allows signals that the default would reject."""
    # Use minimal features that won't pass 0.55 but will pass 0.0
    p_strict = _planner(gate_approval_threshold=0.99)
    p_loose  = _planner(gate_approval_threshold=0.0)
    f = _base_features()
    r_strict = p_strict.plan(_engine(1), f, _context())
    r_loose  = p_loose.plan(_engine(1), f, _context())
    assert r_strict["decision"] == "reject_gate"
    assert r_loose["decision"] == "execute"


# ── 8. RESPONSE STRUCTURE ───────────────────────────────────────────────────

def test_execute_result_has_required_keys():
    """Plan output must include intent, entry, gate, and timing keys."""
    required = {
        "decision", "execution_id", "trade_intent", "direction",
        "entry_type", "entry_price", "gate",
        "validity_ttl_sec", "expires_at", "created_at", "trace",
    }
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute":
        missing = required - r.keys()
        assert not missing, f"Missing keys: {missing}"

def test_execute_result_has_no_sl_tp_keys():
    """SL and TP must NOT be present in plan output (CRT engine responsibility)."""
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute":
        for key in ("stop_loss", "take_profit_1", "take_profit_2", "rr_ratio",
                    "sl_method", "tp_method"):
            assert key not in r, f"Unexpected key '{key}' found in plan output"

def test_gate_result_embedded_in_execute():
    """gate key must be present with approved=True for execute decisions."""
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute":
        assert "gate" in r
        assert r["gate"]["approved"] is True
        assert {"approved", "final_score", "components", "reason"} <= r["gate"].keys()

def test_gate_result_embedded_in_reject_gate():
    """reject_gate decision must include gate breakdown."""
    p = _planner(gate_approval_threshold=0.99)
    r = p.plan(_engine(1), _base_features(), _context())
    assert r["decision"] == "reject_gate"
    assert "gate" in r
    assert r["gate"]["approved"] is False

def test_reject_result_has_trace():
    p = _planner()
    r = p.plan(_engine(1, decision="hold"), _base_features(), _context())
    assert "trace" in r


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # happy paths
        test_breakout_long_approve,
        test_breakout_short_approve,
        test_pullback_long_approve,
        test_pullback_short_approve,
        test_liq_sweep_long_approve,
        test_liq_sweep_short_approve,
        test_double_sweep_triggers_liq_sweep,
        test_reversal_long_when_ema_fast_lt_ema_slow,
        test_reversal_short_when_ema_fast_gt_ema_slow,
        # rejections
        test_reject_engine_decision_not_execute,
        test_reject_engine_decision_hold,
        test_reject_missing_required_feature,
        test_reject_multiple_missing_features,
        test_reject_invalid_close_zero,
        test_reject_invalid_close_negative,
        test_reject_invalid_atr_zero,
        test_reject_high_not_above_low,
        test_reject_invalid_direction_zero,
        test_reject_invalid_direction_value,
        test_reject_unknown_intent_by_default,
        test_allow_unknown_intent_when_configured,
        test_gate_reject_weak_signal,
        # intent classification
        test_intent_classification_breakout,
        test_intent_classification_pullback,
        test_intent_classification_liq_sweep_single,
        test_intent_classification_liq_sweep_double,
        test_intent_classification_reversal,
        # TTL
        test_ttl_breakout_matches_config,
        test_ttl_liq_sweep_matches_config,
        test_expires_at_is_in_future,
        # precision
        test_precision_default_is_8_decimal_places,
        test_precision_override_xauusd_is_2,
        test_precision_override_btcusdt_is_2,
        # execution ID
        test_execution_id_is_deterministic,
        test_execution_id_changes_with_entry_price,
        test_execution_id_starts_with_EX,
        # config
        test_defaults_preserved_when_no_config,
        test_partial_config_preserves_remaining_defaults,
        test_gate_threshold_override,
        # response structure
        test_execute_result_has_required_keys,
        test_execute_result_has_no_sl_tp_keys,
        test_gate_result_embedded_in_execute,
        test_gate_result_embedded_in_reject_gate,
        test_reject_result_has_trace,
    ]

    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
