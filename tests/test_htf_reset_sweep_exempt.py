"""K23 F4: htf_reset_exempt_sweep gates whether an HTF-window flip resets SWEEP.

Default False must reproduce the legacy rule exactly (byte-identical); True exempts SWEEP only,
leaving every other state's HTF reset, and every non-HTF reset, untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from config_layer.crt_engine_v2 import (
    Candle,
    CRTEngine,
    CRTState,
    Direction,
    EngineState,
    Range,
    ResetLogic,
)
from tests.helpers.crt_config import crt_config_for_test
from tests.helpers.crt_config import crt_engine_for_test, execution_engine_for_test, reset_logic_for_test  # noqa: F401

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_OLD, _NEW = "HTF-1", "HTF-2"


def _candle(close: float = 100.0) -> Candle:
    return Candle(timestamp=_T0, open=100.0, high=close + 1.0, low=close - 1.0, close=close)


def _state(current: CRTState) -> EngineState:
    st = EngineState()
    st.active_range = Range(
        h_ref=120.0, l_ref=80.0, equilibrium=100.0,
        formed_at=_T0, htf_candle_id=_OLD, session="LONDON",
    )
    st.direction = Direction.LONG
    st.current_state = current
    return st


def _reset(exempt: bool, current: CRTState, htf_id: str = _NEW) -> tuple[bool, str]:
    logic = reset_logic_for_test(crt_config_for_test(), htf_reset_exempt_sweep=exempt)
    return logic.should_reset(_state(current), _candle(), htf_id)


def test_default_is_legacy_false():
    assert reset_logic_for_test(crt_config_for_test()).htf_reset_exempt_sweep is False
    assert crt_engine_for_test(crt_config_for_test()).reset_lg.htf_reset_exempt_sweep is False


def test_engine_kwarg_reaches_reset_logic():
    eng = crt_engine_for_test(crt_config_for_test(), htf_reset_exempt_sweep=True)
    assert eng.reset_lg.htf_reset_exempt_sweep is True


def test_crtconfig_has_no_new_field():
    # The census pins every CRTConfig field; the flag deliberately lives outside it.
    from config_layer.state_identity import CRTConfig
    assert not hasattr(CRTConfig, "htf_reset_exempt_sweep")


def test_legacy_sweep_is_reset_on_htf_flip():
    fired, reason = _reset(False, CRTState.SWEEP)
    assert fired is True and reason.startswith("HTF changed")


def test_exempt_sweep_survives_htf_flip():
    assert _reset(True, CRTState.SWEEP) == (False, "")


@pytest.mark.parametrize("state", [CRTState.RANGE, CRTState.DISPLACEMENT, CRTState.SHADOW_PENDING])
def test_exempt_flag_does_not_touch_other_states(state):
    for flag in (False, True):
        fired, reason = _reset(flag, state)
        assert fired is True and reason.startswith("HTF changed")


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("state", [CRTState.EXPANSION, CRTState.RETEST])
def test_expansion_retest_always_exempt(flag, state):
    assert _reset(flag, state) == (False, "")


@pytest.mark.parametrize("flag", [False, True])
def test_no_flip_no_htf_reset(flag):
    assert _reset(flag, CRTState.SWEEP, htf_id=_OLD) == (False, "")


def _bt_cfg(monkeypatch, **extra):
    import config_layer.production_config as pc
    from runtime.backtest_v2 import BacktestConfig

    base = dict(pc.get_prod_section("backtest"))
    base.pop("htf_reset_exempt_sweep", None)
    base.update(extra)
    monkeypatch.setattr(pc, "get_prod_section", lambda name: base if name == "backtest" else {})
    return BacktestConfig.from_prod_config("XAUUSD", crt_config=crt_config_for_test(), pip_size=0.0001, scorer_mode="calibrated", allow_router_crt_config=False, strategy_id="")


def test_backtest_config_defaults_to_legacy(monkeypatch):
    assert _bt_cfg(monkeypatch).htf_reset_exempt_sweep is False


def test_backtest_config_reads_true(monkeypatch):
    assert _bt_cfg(monkeypatch, htf_reset_exempt_sweep=True).htf_reset_exempt_sweep is True


@pytest.mark.parametrize("bad", ["true", 1, None])
def test_backtest_config_rejects_non_bool(monkeypatch, bad):
    with pytest.raises(ValueError, match="JSON boolean"):
        _bt_cfg(monkeypatch, htf_reset_exempt_sweep=bad)
