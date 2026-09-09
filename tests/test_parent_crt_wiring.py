"""F-075 caller wiring: BacktestRunner threads ParentCRTFeed.bias into process_candle.

The engine gate itself already existed (crt_engine_v2 parent-bias elif). These
tests prove (1) the backtest loop actually constructs the feed and passes bias,
(2) an opposing parent_state at the soft-confirm EXECUTION filter is now a
reachable FILTER_REJECTED (PARENT_BIAS), (3) Direction.NONE / disabled feed
does not veto.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

from config_layer.crt_engine_v2 import (
    Candle, CRTConfig, CRTEngine, CRTState, Direction, Range,
)
from runtime.backtest_v2 import BacktestRunner

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(i: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(timestamp=_T0 + timedelta(minutes=15 * i), open=o, high=h, low=l, close=c)


def test_backtest_run_constructs_feed_and_threads_parent_state():
    src = inspect.getsource(BacktestRunner.run)
    assert "ParentCRTFeed.from_prod_config" in src
    assert "parent_state=parent_state" in src
    assert "parent_feed.bias" in src
    assert "parent_feed.push(candle)" in src


def _engine_at_soft_conf_long_discount() -> tuple[CRTEngine, Candle]:
    """Plant RETEST + evaluating_soft_conf + LONG in discount. Zone check passes."""
    eng = CRTEngine(CRTConfig())
    eng._parent_crt_enabled = True
    rng = Range(
        h_ref=110.0, l_ref=100.0, equilibrium=105.0,
        formed_at=_T0, htf_candle_id="HTF-1", session="LONDON",
    )
    retest = _candle(10, 102.0, 103.0, 101.5, 102.2)  # close 102.2 < mid 105
    eng.state.active_range = rng
    eng.state.current_state = CRTState.RETEST
    eng.state.direction = Direction.LONG
    eng.state.evaluating_soft_conf = True
    eng.state.retest_candle = retest
    eng.state.atr_abs = 2.0
    return eng, retest


def test_opposing_parent_bias_rejects_at_execution_filter(monkeypatch):
    eng, retest = _engine_at_soft_conf_long_discount()
    monkeypatch.setattr(
        eng.risk, "approve_with_soft_conf",
        lambda *a, **k: (True, None, 0.80),
    )
    out = eng.process_candle(
        _candle(11, 102.3, 102.8, 102.0, 102.5),
        "HTF-1",
        parent_state=Direction.SHORT,
    )
    assert out["action"] == "FILTER_REJECTED"
    reasons = [getattr(e, "reason", "") for e in eng.state.event_log]
    assert any("Against parent-timeframe bias (SHORT)" in str(r) for r in reasons)


def test_agreeing_parent_bias_does_not_parent_veto(monkeypatch):
    eng, retest = _engine_at_soft_conf_long_discount()
    monkeypatch.setattr(
        eng.risk, "approve_with_soft_conf",
        lambda *a, **k: (True, None, 0.80),
    )
    out = eng.process_candle(
        _candle(11, 102.3, 102.8, 102.0, 102.5),
        "HTF-1",
        parent_state=Direction.LONG,
    )
    assert not any(
        "parent-timeframe bias" in str(getattr(e, "reason", ""))
        for e in eng.state.event_log
    )


def test_none_parent_state_does_not_parent_veto(monkeypatch):
    eng, retest = _engine_at_soft_conf_long_discount()
    monkeypatch.setattr(
        eng.risk, "approve_with_soft_conf",
        lambda *a, **k: (True, None, 0.80),
    )
    eng.process_candle(
        _candle(11, 102.3, 102.8, 102.0, 102.5),
        "HTF-1",
        parent_state=None,
    )
    assert not any(
        "parent-timeframe bias" in str(getattr(e, "reason", ""))
        for e in eng.state.event_log
    )
