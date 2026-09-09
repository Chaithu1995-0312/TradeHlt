"""Objective activation gate is OFF by default; ON denies non-EXISTS."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config_layer.crt_engine_v2 import Candle, CRTConfig, CRTEngine, CRTState, Direction, Range
from config_layer.htf_state import ObjectiveStatus


_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(i, o, h, l, c) -> Candle:
    return Candle(timestamp=_T0 + timedelta(minutes=15 * i), open=o, high=h, low=l, close=c)


def _engine_at_soft_conf() -> CRTEngine:
    eng = CRTEngine(CRTConfig())
    eng._parent_crt_enabled = True
    rng = Range(
        h_ref=110.0, l_ref=100.0, equilibrium=105.0,
        formed_at=_T0, htf_candle_id="HTF-1", session="LONDON",
    )
    eng.state.active_range = rng
    eng.state.current_state = CRTState.RETEST
    eng.state.direction = Direction.LONG
    eng.state.evaluating_soft_conf = True
    eng.state.retest_candle = _candle(10, 102.0, 103.0, 101.5, 102.2)
    eng.state.atr_abs = 2.0
    return eng


def test_gate_off_ignores_none_objective(monkeypatch):
    eng = _engine_at_soft_conf()
    eng._objective_gate_enabled = False
    monkeypatch.setattr(
        eng.risk, "approve_with_soft_conf", lambda *a, **k: (True, None, 0.80)
    )
    eng.process_candle(
        _candle(11, 102.3, 102.8, 102.0, 102.5),
        "HTF-1",
        parent_state=Direction.LONG,
        parent_objective=ObjectiveStatus.NONE,
    )
    assert not any(
        "objective" in str(getattr(e, "reason", "")).lower()
        for e in eng.state.event_log
    )


def test_gate_on_denies_none_objective(monkeypatch):
    eng = _engine_at_soft_conf()
    eng._objective_gate_enabled = True
    eng._objective_gate_mode = "allow_exists_only"
    monkeypatch.setattr(
        eng.risk, "approve_with_soft_conf", lambda *a, **k: (True, None, 0.80)
    )
    out = eng.process_candle(
        _candle(11, 102.3, 102.8, 102.0, 102.5),
        "HTF-1",
        parent_state=Direction.LONG,
        parent_objective=ObjectiveStatus.NONE,
    )
    assert out["action"] == "FILTER_REJECTED"
    reasons = [str(getattr(e, "reason", "")) for e in eng.state.event_log]
    assert any("Against parent-timeframe objective (NONE)" in r for r in reasons)


def test_gate_on_allows_exists(monkeypatch):
    eng = _engine_at_soft_conf()
    eng._objective_gate_enabled = True
    eng._objective_gate_mode = "allow_exists_only"
    monkeypatch.setattr(
        eng.risk, "approve_with_soft_conf", lambda *a, **k: (True, None, 0.80)
    )
    eng.process_candle(
        _candle(11, 102.3, 102.8, 102.0, 102.5),
        "HTF-1",
        parent_state=Direction.LONG,
        parent_objective=ObjectiveStatus.EXISTS,
    )
    assert not any(
        "objective" in str(getattr(e, "reason", "")).lower()
        for e in eng.state.event_log
    )


def test_active_config_objective_gate_defaults_off():
    eng = CRTEngine(CRTConfig())
    assert eng._objective_gate_enabled is False
