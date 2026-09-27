"""K23 F3: sl_anchor gates the stop anchor. Default 'displacement' is the legacy stop."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from config_layer.crt_engine_v2 import (
    Candle, CRTEngine, CRTState, Direction, EngineState, ExecutionEngine, Range, SweepEvent,
)
from tests.helpers.crt_config import crt_config_for_test

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _c(o, h, l, c) -> Candle:
    return Candle(timestamp=_T0, open=o, high=h, low=l, close=c)


def _state(direction: Direction) -> EngineState:
    st = EngineState()
    st.active_range = Range(h_ref=120.0, l_ref=80.0, equilibrium=100.0,
                            formed_at=_T0, htf_candle_id="H", session="LONDON")
    st.direction = direction
    st.atr_abs = 2.0
    sweep_c = _c(85, 86, 70.0, 84) if direction == Direction.LONG else _c(115, 130.0, 114, 116)
    st.sweep_event = SweepEvent(direction=direction, price=80.0, candle=sweep_c)
    st.displacement_candle = _c(90, 96, 88.0, 95) if direction == Direction.LONG else _c(110, 112, 104, 105)
    st.retest_candle = _c(94, 95, 92, 93) if direction == Direction.LONG else _c(106, 108, 105, 106)
    st.current_state = CRTState.RETEST
    return st


def _sl(anchor, direction):
    cfg = crt_config_for_test()
    ex = ExecutionEngine(cfg, sl_anchor=anchor)
    trade = ex.build_trade(_state(direction), None)
    return cfg, trade


def test_default_is_legacy():
    assert ExecutionEngine(crt_config_for_test()).sl_anchor == "displacement"
    assert CRTEngine(crt_config_for_test()).executor.sl_anchor == "displacement"


def test_engine_kwarg_reaches_executor():
    assert CRTEngine(crt_config_for_test(), sl_anchor="sweep_extreme").executor.sl_anchor == "sweep_extreme"


@pytest.mark.parametrize("bad", ["", "swept", None])
def test_invalid_anchor_rejected(bad):
    with pytest.raises(ValueError):
        ExecutionEngine(crt_config_for_test(), sl_anchor=bad)


def test_long_sl_uses_sweep_low_when_gated():
    cfg = crt_config_for_test()
    ex = ExecutionEngine(cfg, sl_anchor="sweep_extreme")
    st = _state(Direction.LONG)
    ex.build_trade(st, None)
    assert ex.last_build_attempt is not None


def _computed_sl(anchor, direction):
    cfg = crt_config_for_test()
    ex = ExecutionEngine(cfg, sl_anchor=anchor)
    st = _state(direction)
    try:
        ex.build_trade(st, None)
    except Exception:
        pass
    return cfg, ex.last_build_attempt


def test_sl_values_differ_by_anchor():
    cfg, legacy = _computed_sl("displacement", Direction.LONG)
    _, gated = _computed_sl("sweep_extreme", Direction.LONG)
    buf = cfg.sl_atr_buffer * 2.0
    assert legacy.computed_sl == pytest.approx(88.0 - buf)
    assert gated.computed_sl == pytest.approx(70.0 - buf)


def test_short_sl_uses_sweep_high_when_gated():
    cfg, gated = _computed_sl("sweep_extreme", Direction.SHORT)
    assert gated.computed_sl == pytest.approx(130.0 + cfg.sl_atr_buffer * 2.0)


def test_backtest_config_default_and_validation(monkeypatch):
    import config_layer.production_config as pc
    from runtime.backtest_v2 import BacktestConfig

    def _cfg(**extra):
        base = dict(pc.get_prod_section("backtest"))
        base.pop("sl_anchor", None)
        base.update(extra)
        monkeypatch.setattr(pc, "get_prod_section", lambda n: base if n == "backtest" else {})
        return BacktestConfig.from_prod_config("XAUUSD", crt_config=crt_config_for_test())

    assert _cfg().sl_anchor == "displacement"
    assert _cfg(sl_anchor="sweep_extreme").sl_anchor == "sweep_extreme"
    with pytest.raises(ValueError, match="sl_anchor"):
        _cfg(sl_anchor="bogus")
