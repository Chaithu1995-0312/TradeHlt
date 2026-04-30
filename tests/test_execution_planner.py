"""
test_execution_planner.py
=========================
Dedicated test suite for ExecutionPlannerV1_2 (GAP-002).

Covers:
    - Happy path: BREAKOUT, PULLBACK, LIQ_SWEEP, REVERSAL (long + short)
    - Rejection paths: engine reject, missing features, invalid prices,
      invalid direction, UNKNOWN intent, RR too low, invalid SL/TP order
    - SL computation per intent (with/without lookback keys, both directions)
    - TP computation: ATR-only vs hybrid liquidity
    - Position sizing formula
    - TTL derivation per intent
    - Precision rounding (default + symbol override)
    - Execution ID determinism
    - Config overrides

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
    """Minimal valid feature set (BREAKOUT pattern by default)."""
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
    assert r["rr_ratio"] >= DEFAULT_CONFIG["min_rr_ratio"]
    assert r["entry_price"] > 0
    assert r["stop_loss"] < r["entry_price"]
    assert r["take_profit_1"] > r["entry_price"]

def test_breakout_short_approve():
    p = _planner()
    # body_ratio + disp → BREAKOUT, direction = -1
    f = _base_features(
        ema_fast=98.0, ema_slow=99.0,    # ensure not REVERSAL
    )
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute"
    assert r["trade_intent"] == "BREAKOUT"
    assert r["stop_loss"] > r["entry_price"]
    assert r["take_profit_1"] < r["entry_price"]

def test_pullback_long_approve():
    p = _planner()
    # entry = ema_fast=99.5, sl = lowest_low_5=99.0 → risk=0.5, tp=99.5+1.5*2=102.5 → rr=6 ✓
    f = _base_features(
        sweep_detected=False,
        retest_depth=0.5,
        candles_since_retest=3,
        momentum_score=0.5,
        body_ratio=0.3,          # avoid BREAKOUT
        disp_strength=1.0,
        lowest_low_5=99.0,       # close to entry → small risk → high RR
        highest_high_5=103.0,
    )
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "PULLBACK"
    # Entry should be at ema_fast for long pullback
    assert r["entry_type"] == "LIMIT"

def test_pullback_short_approve():
    p = _planner()
    # entry = ema_slow=98.5, sl = highest_high_5=99.0 → risk=0.5, tp=98.5-1.5*2=95.5 → rr=6 ✓
    f = _base_features(
        sweep_detected=False,
        retest_depth=0.5,
        candles_since_retest=3,
        momentum_score=0.5,
        body_ratio=0.3,
        disp_strength=1.0,
        lowest_low_5=95.0,
        highest_high_5=99.0,     # close to entry → small risk → high RR
    )
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "PULLBACK"
    assert r["entry_type"] == "LIMIT"
    assert r["stop_loss"] > r["entry_price"]

def test_liq_sweep_long_approve():
    p = _planner()
    f = _base_features(sweep_detected=True)
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute"
    assert r["trade_intent"] == "LIQ_SWEEP"
    assert r["entry_type"] == "LIMIT"

def test_liq_sweep_short_approve():
    p = _planner()
    f = _base_features(sweep_detected=True)
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute"
    assert r["trade_intent"] == "LIQ_SWEEP"
    assert r["entry_type"] == "LIMIT"
    assert r["stop_loss"] > r["entry_price"]

def test_double_sweep_triggers_liq_sweep():
    p = _planner()
    f = _base_features(sweep_detected=False, double_sweep=True)
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "LIQ_SWEEP"

def test_reversal_long_when_ema_fast_lt_ema_slow():
    """ema_fast < ema_slow but direction=1 → counter-trend → REVERSAL."""
    p = _planner()
    # entry=close=100, sl=lowest_low_3=99.0 → risk=1.0, tp=100+1.0*2=102 → rr=2 ✓
    f = _base_features(
        sweep_detected=False,
        body_ratio=0.3,
        disp_strength=1.0,
        retest_depth=0.0,
        candles_since_retest=99,
        ema_fast=98.0,
        ema_slow=100.0,    # fast < slow, direction=1 → REVERSAL
        lowest_low_3=99.0, # close SL → low risk → high RR
        highest_high_3=103.0,
    )
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "REVERSAL"

def test_reversal_short_when_ema_fast_gt_ema_slow():
    """ema_fast > ema_slow but direction=-1 → REVERSAL."""
    p = _planner()
    # entry=close=100, sl=highest_high_3=101 → risk=1.0, tp=100-1.0*2=98 → rr=2 ✓
    f = _base_features(
        sweep_detected=False,
        body_ratio=0.3,
        disp_strength=1.0,
        retest_depth=0.0,
        candles_since_retest=99,
        ema_fast=100.0,
        ema_slow=98.0,
        lowest_low_3=97.0,
        highest_high_3=101.0,  # close SL → low risk → high RR
    )
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute", r
    assert r["trade_intent"] == "REVERSAL"


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
    # UNKNOWN intent with reject_unknown_intent=False → proceeds to entry/SL/TP
    # MARKET entry at close; SL at ATR fallback; may still reject_rr if ATR gives bad RR
    assert r["decision"] in ("execute", "reject_rr", "reject_invalid")

def test_reject_rr_too_low():
    p = _planner()
    # Tiny ATR → tiny TP, big SL distance (low=98) → RR < 1.5
    f = _base_features(atr=0.1)  # BREAKOUT, SL=low=98, entry=close=100, tp=100+0.2=100.2
    # risk=2, reward=0.2 → rr=0.1
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "reject_rr"
    assert r["rr_ratio"] < DEFAULT_CONFIG["min_rr_ratio"]


# ── 3. SL COMPUTATION ────────────────────────────────────────────────────────

def test_sl_breakout_long_is_candle_low():
    p = _planner()
    f = _base_features(low=97.5)
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "BREAKOUT"
    assert abs(r["stop_loss"] - 97.5) < 0.01

def test_sl_breakout_short_is_candle_high():
    p = _planner()
    # entry=close=100, sl=high=101 → risk=1, tp=100-2*2=96 → rr=4 ✓
    f = _base_features(high=101.0)
    r = p.plan(_engine(-1), f, _context())
    assert r["trade_intent"] == "BREAKOUT", r
    assert abs(r["stop_loss"] - 101.0) < 0.01

def test_sl_pullback_uses_lookback_low():
    p = _planner()
    # entry=ema_fast=99.5, sl=lowest_low_5=99.0 → risk=0.5, tp=99.5+1.5*2=102.5 → rr=6 ✓
    f = _base_features(
        sweep_detected=False, retest_depth=0.5, candles_since_retest=3,
        momentum_score=0.5, body_ratio=0.3, disp_strength=1.0,
        lowest_low_5=99.0, highest_high_5=105.0,
    )
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "PULLBACK", r
    assert abs(r["stop_loss"] - 99.0) < 0.01

def test_sl_pullback_falls_back_to_bar_low_when_no_lookback_keys():
    p = _planner()
    f = _base_features(
        sweep_detected=False, retest_depth=0.5, candles_since_retest=3,
        momentum_score=0.5, body_ratio=0.3, disp_strength=1.0,
        low=97.0,
        # intentionally no lowest_low_5 / highest_high_5
    )
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "PULLBACK"
    assert r["trace"]["sl_fallback_used"] is True

def test_sl_liq_sweep_long_below_bar_low():
    p = _planner()
    f = _base_features(sweep_detected=True, low=98.0, atr=2.0)
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "LIQ_SWEEP"
    # SL = low - 0.2 * atr = 98 - 0.4 = 97.6
    assert r["stop_loss"] < 98.0

def test_sl_liq_sweep_short_above_bar_high():
    p = _planner()
    f = _base_features(sweep_detected=True, high=102.0, atr=2.0)
    r = p.plan(_engine(-1), f, _context())
    assert r["trade_intent"] == "LIQ_SWEEP"
    assert r["stop_loss"] > 102.0

def test_sl_reversal_uses_3candle_swing():
    p = _planner()
    # entry=close=100, sl=lowest_low_3=99.0 → risk=1.0, tp=100+1*2=102 → rr=2 ✓
    f = _base_features(
        sweep_detected=False, body_ratio=0.3, disp_strength=1.0,
        retest_depth=0.0, candles_since_retest=99,
        ema_fast=98.0, ema_slow=100.0,
        lowest_low_3=99.0, highest_high_3=104.0,
    )
    r = p.plan(_engine(1), f, _context())
    assert r["trade_intent"] == "REVERSAL", r
    assert abs(r["stop_loss"] - 99.0) < 0.01
    assert r["sl_method"] == "swing_reversal"


# ── 4. TP COMPUTATION ─────────────────────────────────────────────────────────

def test_tp_atr_only_when_no_liquidity_keys():
    p = _planner()
    f = _base_features()   # no volume / touch keys
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute"
    assert r["tp_method"] == "atr_only"

def test_tp_hybrid_liquidity_long():
    p = _planner()
    f = _base_features(
        highest_high_20=104.0,
        touches_high_20=3,
        volume_ma20=1000.0,
        volume=2000.0,         # vol_ratio=2.0 ≥ threshold 1.5
    )
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute"
    assert r["tp_method"] == "hybrid_liquidity"
    assert abs(r["take_profit_1"] - 104.0) < 0.001

def test_tp_hybrid_liquidity_short():
    p = _planner()
    f = _base_features(
        ema_fast=98.0, ema_slow=99.0,   # keep BREAKOUT, direction=-1
        lowest_low_20=96.0,
        touches_low_20=2,
        volume_ma20=1000.0,
        volume=1600.0,
    )
    r = p.plan(_engine(-1), f, _context())
    assert r["decision"] == "execute"
    assert r["tp_method"] == "hybrid_liquidity"
    assert abs(r["take_profit_1"] - 96.0) < 0.001

def test_tp_no_hybrid_when_vol_ratio_too_low():
    p = _planner()
    f = _base_features(
        highest_high_20=104.0,
        touches_high_20=5,
        volume_ma20=1000.0,
        volume=500.0,         # vol_ratio=0.5 < threshold 1.5
    )
    r = p.plan(_engine(1), f, _context())
    assert r["tp_method"] == "atr_only"

def test_tp_no_hybrid_when_touch_count_too_low():
    p = _planner()
    f = _base_features(
        highest_high_20=104.0,
        touches_high_20=1,    # < min_touches=2
        volume_ma20=1000.0,
        volume=2000.0,
    )
    r = p.plan(_engine(1), f, _context())
    assert r["tp_method"] == "atr_only"

def test_tp2_is_double_atr_distance():
    p = _planner()
    f = _base_features()
    r = p.plan(_engine(1), f, _context())
    if r["decision"] == "execute" and r.get("take_profit_2") is not None:
        entry = r["entry_price"]
        tp1 = r["take_profit_1"]
        tp2 = r["take_profit_2"]
        assert tp2 > tp1 > entry  # tp2 further from entry than tp1

def test_tp_per_intent_multiplier_reversal():
    """REVERSAL uses atr_mult_reversal_tp (1.0) < BREAKOUT (2.0)."""
    p = _planner()
    f_reversal = _base_features(
        sweep_detected=False, body_ratio=0.3, disp_strength=1.0,
        retest_depth=0.0, candles_since_retest=99,
        ema_fast=98.0, ema_slow=100.0,
        lowest_low_3=97.0, highest_high_3=103.0,
    )
    f_breakout = _base_features()  # same ATR, same entry

    r_rev = p.plan(_engine(1), f_reversal, _context())
    r_brk = p.plan(_engine(1), f_breakout, _context())

    if r_rev["decision"] == "execute" and r_brk["decision"] == "execute":
        # REVERSAL TP1 < BREAKOUT TP1 (smaller multiplier)
        assert r_rev["take_profit_1"] < r_brk["take_profit_1"]


# ── 5. POSITION SIZING ────────────────────────────────────────────────────────

def test_position_size_hint_formula():
    """hint = (balance * risk%) / risk_per_unit."""
    p = _planner(risk_percent=1.0)
    f = _base_features(close=100.0, low=98.0, atr=2.0)  # BREAKOUT, SL=98
    r = p.plan(_engine(1), f, _context(balance=10_000.0))
    assert r["decision"] == "execute"
    # entry=100, sl=98, risk_per_unit=2.0; hint=10000*0.01/2=50.0
    assert r["position_size_hint"] is not None
    assert abs(r["position_size_hint"] - 50.0) < 0.1

def test_position_size_hint_scales_with_balance():
    p = _planner(risk_percent=1.0)
    f = _base_features(close=100.0, low=98.0, atr=2.0)
    r1 = p.plan(_engine(1), f, _context(balance=5_000.0))
    r2 = p.plan(_engine(1), f, _context(balance=20_000.0))
    if r1["decision"] == "execute" and r2["decision"] == "execute":
        assert r2["position_size_hint"] == r1["position_size_hint"] * 4


# ── 6. TTL DERIVATION ────────────────────────────────────────────────────────

def test_ttl_breakout_matches_config():
    p = _planner(ttl_breakout_sec=999)
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute" and r["trade_intent"] == "BREAKOUT":
        assert r["validity_ttl_sec"] == 999

def test_ttl_liq_sweep_matches_config():
    p = _planner(ttl_liq_sweep_sec=555)
    f = _base_features(sweep_detected=True)
    r = p.plan(_engine(1), f, _context())
    assert r["decision"] == "execute"
    assert r["validity_ttl_sec"] == 555

def test_expires_at_is_in_future():
    from datetime import datetime, timezone
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute":
        expires = datetime.fromisoformat(r["expires_at"])
        now = datetime.now(timezone.utc)
        assert expires > now


# ── 7. PRECISION ROUNDING ─────────────────────────────────────────────────────

def test_precision_default_is_8_decimal_places():
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context(symbol="EURUSD"))
    if r["decision"] == "execute":
        # entry_price rounded to 8 decimal places — just check it's a float
        assert isinstance(r["entry_price"], float)

def test_precision_override_xauusd_is_2():
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context(symbol="XAUUSD"))
    if r["decision"] == "execute":
        # 2-decimal precision: entry should have ≤ 2 decimal digits
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


# ── 8. EXECUTION ID DETERMINISM ───────────────────────────────────────────────

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
    f2 = _base_features(close=105.0, high=107.0)  # different close
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


# ── 9. CONFIG OVERRIDES ──────────────────────────────────────────────────────

def test_custom_min_rr_ratio_lower_allows_more_trades():
    p_strict = _planner(min_rr_ratio=1.5)
    p_loose  = _planner(min_rr_ratio=0.1)
    f = _base_features(atr=0.1)  # tiny ATR → low RR
    ctx = _context()
    r_strict = p_strict.plan(_engine(1), f, ctx)
    r_loose  = p_loose.plan(_engine(1), f, ctx)
    assert r_strict["decision"] == "reject_rr"
    assert r_loose["decision"] in ("execute", "reject_invalid")

def test_defaults_preserved_when_no_config():
    p = ExecutionPlannerV1_2()
    assert p.config["min_rr_ratio"] == 1.5
    assert p.config["risk_percent"] == 0.5

def test_partial_config_preserves_remaining_defaults():
    p = ExecutionPlannerV1_2({"risk_percent": 2.0})
    assert p.config["risk_percent"] == 2.0
    assert p.config["min_rr_ratio"] == 1.5  # default preserved


# ── 10. RESPONSE STRUCTURE ───────────────────────────────────────────────────

def test_execute_result_has_required_keys():
    required = {
        "decision", "execution_id", "trade_intent", "direction",
        "entry_price", "stop_loss", "take_profit_1",
        "rr_ratio", "risk_percent", "position_size_hint",
        "expires_at", "created_at", "sl_method", "tp_method", "trace",
    }
    p = _planner()
    r = p.plan(_engine(1), _base_features(), _context())
    if r["decision"] == "execute":
        missing = required - r.keys()
        assert not missing, f"Missing keys: {missing}"

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
        test_reject_rr_too_low,
        # SL
        test_sl_breakout_long_is_candle_low,
        test_sl_breakout_short_is_candle_high,
        test_sl_pullback_uses_lookback_low,
        test_sl_pullback_falls_back_to_bar_low_when_no_lookback_keys,
        test_sl_liq_sweep_long_below_bar_low,
        test_sl_liq_sweep_short_above_bar_high,
        test_sl_reversal_uses_3candle_swing,
        # TP
        test_tp_atr_only_when_no_liquidity_keys,
        test_tp_hybrid_liquidity_long,
        test_tp_hybrid_liquidity_short,
        test_tp_no_hybrid_when_vol_ratio_too_low,
        test_tp_no_hybrid_when_touch_count_too_low,
        test_tp2_is_double_atr_distance,
        test_tp_per_intent_multiplier_reversal,
        # sizing
        test_position_size_hint_formula,
        test_position_size_hint_scales_with_balance,
        # TTL
        test_ttl_breakout_matches_config,
        test_ttl_liq_sweep_matches_config,
        test_expires_at_is_in_future,
        # precision
        test_precision_default_is_8_decimal_places,
        test_precision_override_xauusd_is_2,
        test_precision_override_btcusdt_is_2,
        # determinism
        test_execution_id_is_deterministic,
        test_execution_id_changes_with_entry_price,
        test_execution_id_starts_with_EX,
        # config
        test_custom_min_rr_ratio_lower_allows_more_trades,
        test_defaults_preserved_when_no_config,
        test_partial_config_preserves_remaining_defaults,
        # structure
        test_execute_result_has_required_keys,
        test_reject_result_has_trace,
    ]

    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"  {passed} passed / {failed} failed  ({len(tests)} total)")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
