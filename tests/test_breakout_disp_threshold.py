"""
test_breakout_disp_threshold.py — governance tests for the config-driven BREAKOUT disp gate.

Covers the deployment of `breakout_disp_threshold` (default 1.5; per-instrument override, BNBUSDT=1.3):
  - resolver semantics (global / override / case-insensitive / fallback)
  - config defaults are 1.5 (no-op migration)
  - both classifiers honor the threshold
  - ★ CROSS-COMPONENT CONSISTENCY INVARIANT: CRT engine and ExecutionPlanner resolve+apply the SAME
    threshold for a symbol → they can never diverge (the original two-hardcoded-copies bug class).
"""
from config_layer.production_config import resolve_breakout_disp_threshold
from config_layer.crt_engine_v2 import CRTConfig, Direction, ExecutionEngine
from config_layer.execution_planner import ExecutionPlannerV1_2
from config_layer.strict_config import ConfigKeyMissingError
from tests.helpers.planner_config import planner_test_config
import pytest
from tests.helpers.crt_config import crt_config_for_test


# A breakout-shaped feature vector whose disp (1.4) sits BETWEEN 1.3 and 1.5 → the decisive case:
# classified "breakout" at threshold 1.3, "reversal" at 1.5.
_FEATS = {
    "body_ratio": 0.80, "disp_strength": 1.40, "retest_depth": 0.90,
    "candles_since_sweep": 9, "momentum_score": 0.0,
    "sweep_detected": False, "double_sweep": False, "ema_fast": 1.0, "ema_slow": 2.0,
    # EPIC-84 A3b: the engine's strict intent contract keys (same quantities as above)
    "displacement_retrace": 0.90, "displacement_atr_ratio": 1.40,
}
_ENGINE_RESULT = {"decision": "execute", "selected_direction": 1}
# Staged candidate config block (what the v5 promotion would carry).
_CRT_SECTION = {"breakout_disp_threshold": 1.5,
                "breakout_disp_threshold_overrides": {"BNBUSDT": 1.3}}


def test_config_defaults_are_1_5_noop():
    """Migration is a no-op by default: both config defaults == historical hardcoded 1.5."""
    assert crt_config_for_test().breakout_disp_threshold == 1.5
    assert planner_test_config()["breakout_disp_threshold"] == 1.5  # fixture = former default


def test_resolver_global_override_caseinsensitive_fallback():
    assert resolve_breakout_disp_threshold(_CRT_SECTION, "BNBUSDT") == 1.3
    assert resolve_breakout_disp_threshold(_CRT_SECTION, "bnbusdt") == 1.3   # case-insensitive
    assert resolve_breakout_disp_threshold(_CRT_SECTION, "BTCUSDT") == 1.5   # global default
    # EPIC-84: no section / no global key fails closed (was: None -> caller kept its 1.5)
    with pytest.raises(ConfigKeyMissingError):
        resolve_breakout_disp_threshold(None, "BNBUSDT")
    with pytest.raises(ConfigKeyMissingError):
        resolve_breakout_disp_threshold({}, "BNBUSDT")


def test_crt_intent_honors_threshold_and_static_caller_unchanged():
    # EPIC-84: the threshold is a required argument (was: defaulted to 1.5)
    import pytest as _pt
    with _pt.raises(TypeError):
        ExecutionEngine._derive_trade_intent(_FEATS)
    assert ExecutionEngine._derive_trade_intent(_FEATS, 1.5, Direction.LONG) == "reversal"
    assert ExecutionEngine._derive_trade_intent(_FEATS, 1.3, Direction.LONG) == "breakout"


def test_planner_intent_honors_threshold():
    assert ExecutionPlannerV1_2(planner_test_config())._derive_intent(_FEATS, _ENGINE_RESULT)[0] == "REVERSAL"  # 1.5
    assert ExecutionPlannerV1_2(planner_test_config(breakout_disp_threshold=1.3))._derive_intent(
        _FEATS, _ENGINE_RESULT)[0] == "BREAKOUT"


def test_cross_component_consistency_invariant():
    """★ The CRT engine and the ExecutionPlanner MUST classify the same trade identically when fed the
    same per-symbol resolved threshold. Guards the named failure mode (backtest 1.3 / live 1.5)."""
    for symbol in ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"):
        thr = resolve_breakout_disp_threshold(_CRT_SECTION, symbol)
        crt_is_breakout = ExecutionEngine._derive_trade_intent(_FEATS, thr, Direction.LONG) == "breakout"
        planner_is_breakout = ExecutionPlannerV1_2(
            planner_test_config(breakout_disp_threshold=thr))._derive_intent(_FEATS, _ENGINE_RESULT)[0] == "BREAKOUT"
        assert crt_is_breakout == planner_is_breakout, f"{symbol}: CRT/Planner disagree at thr={thr}"
    # And the resolved values are exactly what we expect (BNB lowered, others default).
    assert resolve_breakout_disp_threshold(_CRT_SECTION, "BNBUSDT") == 1.3
    assert all(resolve_breakout_disp_threshold(_CRT_SECTION, s) == 1.5
               for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT"))
