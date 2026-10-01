"""Entry-chain floor (2026-10-01): the three defects traced from run_20260930_163142.

  retest_stop_guard   an EXPANSION whose bar CLOSE reaches the stop a trade built on that bar would
                      use ends the setup (ResetLogic deliberately lets EXPANSION outlive the HTF
                      flip, so the retrace/extension resets stop applying after the first flip).
  entry_semantics     "resting_order": the order fills at the RETEST close and the soft-confirmation
                      bars are walked for SL/TP; an unconfirmed setup is flattened at that bar's
                      close. "approval_bar_legacy" (default) is byte-for-byte today.
  ghost EXECUTION     build_trade refusing an approved setup used to leave the engine in EXECUTION
                      with no trade, no event and no reset; it is now a counted rejection + reset.

These drive a real `CRTEngine.process_candle()` on a seeded EXPANSION state (the pattern of
test_shadow_ttl_lifecycle.py). The only thing replaced is the soft-confirmation SCORE
(`engine.risk.approve_with_soft_conf`), so approval is controlled; the code under test
(guard, placement, flatten, confirm, reject) is the real one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytest

from config_layer.crt_engine_v2 import (
    Candle, CRTEngine, CRTState, Direction, EngineState, Range, SweepEvent,
)
from tests.helpers.crt_config import (
    bar_features_for_test, crt_config_for_test, crt_engine_for_test,
    execution_engine_for_test, retest_cache_for_test,
)

_T0 = datetime(2026, 1, 5, 7, 30)        # Monday 07:30 -> LONDON window (07:00-10:00)
_T_OFF = datetime(2026, 1, 5, 11, 0)     # outside every window -> OFF_SESSION


def _c(i: int, o: float, h: float, l: float, c: float, t0: datetime = _T0) -> Candle:
    return Candle(timestamp=t0 + timedelta(minutes=15 * i), open=o, high=h, low=l, close=c)


# Valid LONG geometry: the displacement sits just above the range low, so the stop (89.9) is far
# below the retest close and build_trade succeeds. Range is 90..110 (size 20).
_DISP_VALID = (90.6, 93.9, 90.3, 93.6)
# Ghost geometry: displacement sits ABOVE the retest close, so the stop (94.1) is above the entry
# and build_trade refuses with inverted_sl_long.
_DISP_INVERTED = (95.0, 98.0, 94.5, 97.5)


def _engine(entry_semantics="approval_bar_legacy", guard=False, disp=_DISP_VALID, t0=_T0,
            approve=None) -> CRTEngine:
    eng = crt_engine_for_test(
        crt_config_for_test(), entry_semantics=entry_semantics, retest_stop_guard=guard,
    )
    # ATR scaffolding: 15 flat bars around the scenario price keep ATR ~2.0.
    for k in range(15, 0, -1):
        eng.candle_buffer.append(_c(-k, 92.0, 93.0, 91.0, 92.0, t0))
    st = eng.state
    st.active_range = Range(h_ref=110.0, l_ref=90.0, equilibrium=100.0, formed_at=t0,
                            htf_candle_id="HTF-1", session="LONDON")
    st.current_state = CRTState.EXPANSION
    st.direction = Direction.LONG
    st.sweep_event = SweepEvent(direction=Direction.LONG, price=90.0,
                                candle=_c(-3, 90.5, 91.0, 88.5, 90.5, t0))
    st.displacement_candle = _c(-2, *disp, t0=t0)
    st.current_candle_index = 20
    st._expansion_entry_idx = 18
    eng.telemetry.on_candidate_opened("CAND-1", 18, t0.isoformat(), shadow=False)
    if approve is not None:
        eng.risk.approve_with_soft_conf = lambda state, candle: approve
    return eng


def _step(eng: CRTEngine, candle: Candle, htf: str = "HTF-2") -> dict:
    # "HTF-2" != the range clock "HTF-1": EXPANSION/RETEST are protected from the HTF flip, which
    # is exactly the situation the guard exists for (and keeps incidental retrace resets out).
    return eng.process_candle(candle, htf, bar_features=bar_features_for_test())


def _events(eng: CRTEngine, name: str) -> list:
    return [e for e in eng.state.event_log if e.event == name]


_RETEST_BAR = (92.3, 93.0, 91.2, 92.5)    # depth 2.5 above l_ref=90 -> a valid retest close
_BENIGN = (92.5, 92.9, 91.9, 92.3)        # touches neither the SL (89.9) nor TP1
_APPROVE = (True, None, 0.60)
_REJECT = (False, None, 0.10)


# ── stop_price: one authority ───────────────────────────────────────────────────────────────────

def _state(direction: Direction) -> EngineState:
    st = EngineState()
    st.active_range = Range(h_ref=120.0, l_ref=80.0, equilibrium=100.0, formed_at=_T0,
                            htf_candle_id="H", session="LONDON")
    st.direction = direction
    st.atr_abs = 2.0
    sweep_c = _c(0, 85, 86, 70.0, 84) if direction == Direction.LONG else _c(0, 115, 130.0, 114, 116)
    st.sweep_event = SweepEvent(direction=direction, price=80.0, candle=sweep_c)
    st.displacement_candle = (_c(0, 90, 96, 88.0, 95) if direction == Direction.LONG
                              else _c(0, 110, 112, 104, 105))
    st.retest_candle = _c(0, 94, 95, 92, 93) if direction == Direction.LONG else _c(0, 106, 108, 105, 106)
    st.current_state = CRTState.RETEST
    st.cached_features = retest_cache_for_test()
    return st


# Hand-computed from `_state` (atr 2.0, sl_atr_buffer 0.2 -> buffer 0.4), independent of the code
# under test: displacement anchor = displacement low/high -/+ buffer; sweep_extreme = swept wick.
@pytest.mark.parametrize("anchor,direction,expected", [
    ("displacement", Direction.LONG, 88.0 - 0.4),
    ("displacement", Direction.SHORT, 112.0 + 0.4),
    ("sweep_extreme", Direction.LONG, 70.0 - 0.4),
    ("sweep_extreme", Direction.SHORT, 130.0 + 0.4),
])
def test_stop_price_is_exactly_the_stop_build_trade_places(anchor, direction, expected):
    ex = execution_engine_for_test(crt_config_for_test(), sl_anchor=anchor)
    st = _state(direction)
    trade = ex.build_trade(st, None)
    assert trade is not None
    assert ex.stop_price(st) == trade.sl_price           # one authority: build_trade reads it
    assert ex.stop_price(st) == pytest.approx(expected)  # and it is the documented formula


def test_stop_price_is_none_when_it_cannot_be_derived():
    ex = execution_engine_for_test(crt_config_for_test(), sl_anchor="sweep_extreme")
    st = _state(Direction.LONG)
    st.sweep_event = None
    assert ex.stop_price(st) is None                       # sweep_extreme needs a sweep
    st = _state(Direction.LONG)
    st.displacement_candle = None
    assert ex.stop_price(st) is None
    st = _state(Direction.LONG)
    st.direction = Direction.NONE
    assert ex.stop_price(st) is None


def test_build_trade_refusal_reasons_are_unchanged():
    ex = execution_engine_for_test(crt_config_for_test(), sl_anchor="displacement")
    st = _state(Direction.LONG)
    st.displacement_candle = None
    assert ex.build_trade(st, None) is None
    assert ex.last_build_attempt.reason == "missing_displacement"
    st = _state(Direction.LONG)
    st.direction = Direction.NONE
    assert ex.build_trade(st, None) is None
    assert ex.last_build_attempt.reason == "invalid_direction"


# ── retest_stop_guard ───────────────────────────────────────────────────────────────────────────

_BREACH_BAR = (91.0, 91.4, 89.2, 89.5)    # CLOSE 89.5 is below the stop (~89.9)


def test_guard_on_a_close_beyond_the_stop_ends_the_expansion():
    eng = _engine(guard=True)
    res = _step(eng, _c(0, *_BREACH_BAR))
    assert res["action"] == "EXPANSION_STOP_BREACHED"
    assert eng.state.current_state == CRTState.RANGE
    resets = _events(eng, "RESET")
    assert resets and "stop_breached" in resets[-1].reason
    # the candidate lifecycle is closed with the truthful death reason
    assert eng.telemetry._candidate_records[-1]["death_reason"] == "STOP_BREACHED"


def test_guard_off_the_same_bar_leaves_the_expansion_alive():
    eng = _engine(guard=False)
    res = _step(eng, _c(0, *_BREACH_BAR))
    assert res["action"] != "EXPANSION_STOP_BREACHED"
    assert eng.state.current_state == CRTState.EXPANSION


def test_guard_on_does_not_block_a_retest_whose_stop_was_never_breached():
    eng = _engine(guard=True)
    res = _step(eng, _c(0, *_RETEST_BAR))
    assert res["action"] == "RETEST_CONFIRMED"
    assert eng.state.current_state == CRTState.RETEST


def test_guard_a_wick_below_the_stop_that_closes_above_it_does_not_fire():
    """Close-triggered, like the SEM-021 kill: a wick is not a breach."""
    eng = _engine(guard=True)
    res = _step(eng, _c(0, 91.5, 91.8, 88.9, 91.6))     # low 88.9 < stop ~89.9, close 91.6 above it
    assert res["action"] == "RETEST_CONFIRMED"           # the bar is a valid retest, not a breach
    assert eng.state.current_state == CRTState.RETEST


# ── entry_semantics: the contrast ───────────────────────────────────────────────────────────────

def test_legacy_opens_one_bar_after_the_retest_at_the_retest_close():
    eng = _engine("approval_bar_legacy", approve=_APPROVE)
    r1 = _step(eng, _c(0, *_RETEST_BAR))
    assert r1["action"] == "RETEST_CONFIRMED" and eng.state.active_trade is None
    r2 = _step(eng, _c(1, *_BENIGN))
    assert r2["action"] == "TRADE_OPENED"
    t = eng.state.active_trade
    assert t is not None and t.entry_price == pytest.approx(92.5)      # the PREVIOUS bar's close
    assert t.opened_at == _c(1, *_BENIGN).timestamp                    # opened a bar later


def test_resting_order_fills_at_the_retest_bar():
    eng = _engine("resting_order", approve=_APPROVE)
    r1 = _step(eng, _c(0, *_RETEST_BAR))
    assert r1["action"] == "TRADE_OPENED"
    t = eng.state.active_trade
    assert t is not None and t.status == "OPEN"
    assert t.entry_price == pytest.approx(92.5)
    assert t.opened_at == _c(0, *_RETEST_BAR).timestamp               # the retest bar itself
    assert eng.state.current_state == CRTState.RETEST
    assert eng.state.evaluating_soft_conf is True
    assert r1["candidate_id"] == "CAND-1"                             # row carries the lifecycle id
    opened = _events(eng, "TRADE_OPENED")
    assert len(opened) == 1 and opened[0].metadata["entry_semantics"] == "resting_order"
    assert opened[0].metadata["S_score"] is None


def test_resting_order_approval_confirms_without_a_second_open():
    eng = _engine("resting_order", approve=_APPROVE)
    _step(eng, _c(0, *_RETEST_BAR))
    r2 = _step(eng, _c(1, *_BENIGN))
    assert r2["action"] == "TRADE_CONFIRMED"
    assert eng.state.current_state == CRTState.EXECUTION
    assert eng.state.active_trade.status == "OPEN"
    assert len(_events(eng, "TRADE_OPENED")) == 1
    assert len(_events(eng, "TRADE_CONFIRMED")) == 1
    assert eng.telemetry._candidate_records[-1]["death_reason"] == "ACCEPTED"
    assert eng.telemetry._candidate_records[-1]["trade_id"] == eng.state.active_trade.id


def test_resting_order_stopped_on_a_soft_conf_bar_is_a_loss_not_a_skipped_bar(caplog):
    """The approval bar IS walked: a bar that takes out the stop closes the order, whatever the
    confirmation score would have said. No illegal RETEST->RESOLUTION hop is attempted."""
    eng = _engine("resting_order", approve=_APPROVE)
    _step(eng, _c(0, *_RETEST_BAR))
    with caplog.at_level(logging.WARNING, logger="CRT.StateMachine"):
        r2 = _step(eng, _c(1, 92.0, 92.2, 89.0, 89.4))               # low 89.0 <= stop 89.9
    assert r2["action"] == "TRADE_STOPPED"
    assert eng.state.active_trade.status == "STOPPED"
    assert eng.state.current_state == CRTState.RANGE
    assert not [r for r in caplog.records if "ILLEGAL" in r.getMessage()]


def test_resting_order_reaching_tp1_during_confirmation_runs_on_unconfirmed(caplog):
    """Documented limit (docs/topics/crt-spine.md): once a resting order has filled AND reached
    TP1, confirmation is no longer required -- the setup is closed out like any TP1 hit (state
    resets, runner leg keeps being managed) and is NOT flattened as unconfirmed. Confirmation
    here would never pass, so only the TP1 fill can explain the outcome."""
    eng = _engine("resting_order", approve=_REJECT)
    _step(eng, _c(0, *_RETEST_BAR))
    t = eng.state.active_trade
    assert t.tp1_price < 96.5 < t.tp2_price                          # the bar reaches TP1 only
    with caplog.at_level(logging.WARNING, logger="CRT.StateMachine"):
        r2 = _step(eng, _c(1, 92.6, 96.5, 92.0, 95.5))
    assert r2["action"] == "TRADE_TP1"
    assert t.status == "TP1" and t.partial_pnl > 0
    assert eng.state.current_state == CRTState.RANGE
    assert eng.state.evaluating_soft_conf is False
    assert not _events(eng, "TRADE_UNCONFIRMED")
    assert not [r for r in caplog.records if "ILLEGAL" in r.getMessage()]


def test_resting_order_flattened_at_close_when_confirmation_times_out():
    eng = _engine("resting_order", approve=_REJECT)
    _step(eng, _c(0, *_RETEST_BAR))
    actions = [_step(eng, _c(i, *_BENIGN))["action"] for i in (1, 2, 3)]
    assert actions[:2] == ["EVALUATING_SOFT_CONF"] * 2
    assert actions[2] == "TRADE_UNCONFIRMED"
    t = eng.state.active_trade
    assert t.status == "UNCONFIRMED"
    assert t.pnl == pytest.approx(92.3 - 92.5)                        # booked at the bar CLOSE
    assert eng.state.current_state == CRTState.RANGE
    assert len(_events(eng, "TRADE_UNCONFIRMED")) == 1


def test_resting_order_flattened_when_an_approved_setup_fails_the_session_filter():
    eng = _engine("resting_order", approve=_APPROVE, t0=_T_OFF)
    _step(eng, _c(0, *_RETEST_BAR, t0=_T_OFF))
    r2 = _step(eng, _c(1, *_BENIGN, t0=_T_OFF))
    assert r2["action"] == "TRADE_UNCONFIRMED"
    assert r2["reason"].startswith("off_session")
    assert eng.state.active_trade.status == "UNCONFIRMED"
    assert eng.state.current_state == CRTState.RANGE


def test_legacy_semantics_never_flatten_or_emit_new_actions():
    """Default-inert: the legacy session-filter rejection keeps its original action and event."""
    eng = _engine("approval_bar_legacy", approve=_APPROVE, t0=_T_OFF)
    _step(eng, _c(0, *_RETEST_BAR, t0=_T_OFF))
    r2 = _step(eng, _c(1, *_BENIGN, t0=_T_OFF))
    assert r2["action"] == "FILTER_REJECTED"
    assert eng.state.active_trade is None
    assert not _events(eng, "TRADE_UNCONFIRMED")


# ── ghost EXECUTION ─────────────────────────────────────────────────────────────────────────────

def test_legacy_a_refused_build_is_a_counted_rejection_not_a_silent_execution():
    eng = _engine("approval_bar_legacy", disp=_DISP_INVERTED, approve=_APPROVE)
    _step(eng, _c(0, *_RETEST_BAR))
    r2 = _step(eng, _c(1, *_BENIGN))
    assert r2["action"] == "TRADE_BUILD_REJECTED"
    assert r2["reason"] == "trade_build_rejected:inverted_sl_long"
    assert eng.state.current_state == CRTState.RANGE                   # was: stuck in EXECUTION
    assert eng.state.active_trade is None
    ev = _events(eng, "TRADE_BUILD_REJECTED")
    assert len(ev) == 1 and ev[0].metadata["build_reason"] == "inverted_sl_long"
    assert eng.telemetry._candidate_records[-1]["death_reason"] == "BUILD_REJECTED"


def test_resting_a_refused_build_is_rejected_at_the_retest_bar():
    eng = _engine("resting_order", disp=_DISP_INVERTED, approve=_APPROVE)
    r1 = _step(eng, _c(0, *_RETEST_BAR))
    assert r1["action"] == "TRADE_BUILD_REJECTED"
    assert eng.state.current_state == CRTState.RANGE
    assert eng.state.active_trade is None


# ── configuration contract ──────────────────────────────────────────────────────────────────────

def test_engine_validates_the_new_arguments():
    with pytest.raises(ValueError, match="entry_semantics"):
        crt_engine_for_test(crt_config_for_test(), entry_semantics="bogus")
    with pytest.raises(ValueError, match="retest_stop_guard"):
        crt_engine_for_test(crt_config_for_test(), retest_stop_guard="yes")


def test_resting_order_is_refused_with_the_mode_c_resolver():
    with pytest.raises(ValueError, match="resolver"):
        crt_engine_for_test(crt_config_for_test(), entry_semantics="resting_order", decider="resolver")


def test_setup_rejects_an_invalid_entry_semantics(monkeypatch):
    import config_layer.production_config as pc
    from config_layer.setup import Setup

    real = pc.get_prod_section
    active = (pc.get_active_version())

    def fake(name, version=None):
        sec = dict(real(name, version=version))
        if name == "setup":
            sec["entry_semantics"] = "bogus"
        return sec

    monkeypatch.setattr(pc, "get_prod_section", fake)
    with pytest.raises(ValueError, match="entry_semantics"):
        Setup.from_prod_config(active)


def test_runner_books_an_unconfirmed_order_at_the_bar_close():
    from runtime.backtest_v2 import _resolve_exit
    from config_layer.crt_engine_v2 import Trade

    t = Trade(id="T", direction=Direction.LONG, entry_price=92.5, sl_price=89.9,
              tp1_price=95.0, tp2_price=97.0)
    candle = _c(0, 92.0, 92.6, 91.8, 92.3)
    assert _resolve_exit("TRADE_UNCONFIRMED", t, "UNCONFIRMED", candle, True, 0.5) == (92.3, "UNCONFIRMED")
    exit_raw, reason = _resolve_exit("TRADE_UNCONFIRMED", t, "TP1", candle, True, 0.5)
    assert reason == "TP1_UNCONFIRMED" and exit_raw == pytest.approx(0.5 * 95.0 + 0.5 * 92.3)
