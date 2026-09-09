"""B. Number-trace / provenance — substitute the wrong operand and require a detectable mismatch.

Semantic invariant: SL = extreme ± sl_atr_buffer * state.atr_abs, where atr_abs is
whatever is sitting on the state at build_trade time (soft-conf bar in production).
Ordinary tests check a single happy-path number, not adversarial substitutions.
"""
from __future__ import annotations

import pytest

from config_layer.state_identity import CRTConfig

from tests.Grok._fixtures import engine_ready_long, engine_ready_short, executor


def _short_sl(disp_high: float, atr: float, buf: float) -> float:
    return disp_high + buf * atr


def _long_sl(disp_low: float, atr: float, buf: float) -> float:
    return disp_low - buf * atr


def test_traced_short_sl_reproduces_from_named_operands():
    """Invariant: the A3 SHORT proof arithmetic is recoverable from operands.

    Source: ExecutionEngine.build_trade + operands.csv of 20260813T124158Z
    """
    sl = _short_sl(4146.75, 9.562142857142915, 0.2)
    assert sl == pytest.approx(4148.662428571429)
    st = engine_ready_short()
    # engine rejects (inverted) so we recompute the would-be sl
    would = _short_sl(st.displacement_candle.high, st.atr_abs, 0.2)
    assert would == pytest.approx(4148.6624286, abs=1e-6)
    assert would < st.retest_candle.close


def test_substitute_retest_atr_changes_sl():
    """Wrong ATR: RETEST-bar atr_abs ≠ soft-conf atr_abs.

    Source: operands.csv (10.473571 @ 19:00 vs 9.562143 @ 19:15)
    Failure mode: copying feat_atr or RETEST atr_abs into the SL formula.
    Why ordinary tests miss it: they only store one ATR.
    """
    soft = 9.562142857142915
    retest = 10.473571428571502
    buf = 0.2
    sl_soft = _short_sl(4146.75, soft, buf)
    sl_retest = _short_sl(4146.75, retest, buf)
    assert sl_soft != pytest.approx(sl_retest)
    assert abs(sl_retest - sl_soft) == pytest.approx(buf * (retest - soft))


def test_substitute_wrong_candle_extreme_changes_sl_and_guard():
    """Wrong candle: using the confirming/RETEST high instead of displacement high.

    SHORT RETEST high=4159.55 vs disp_high=4146.75 — the guard would flip.
    """
    buf, atr = 0.2, 9.562143
    entry = 4154.55
    sl_correct = _short_sl(4146.75, atr, buf)
    sl_wrong = _short_sl(4159.55, atr, buf)
    assert sl_correct < entry          # inverted (true reject)
    assert sl_wrong > entry            # would have PASSED the SHORT guard
    assert sl_wrong != pytest.approx(sl_correct)


def test_substitute_wrong_config_buffer_changes_sl():
    """Wrong config: sl_atr_buffer 1.0 vs 0.2."""
    sl_prod = _short_sl(4146.75, 9.562143, 0.2)
    sl_alt = _short_sl(4146.75, 9.562143, 1.0)
    assert sl_alt - sl_prod == pytest.approx(0.8 * 9.562143)


def test_build_trade_sl_scales_with_state_atr_abs():
    """Class C: SL uses `state.atr_abs` on the call (crt_engine_v2.py:2201).

    The live path writes that field on the soft-conf bar. This pins the
    implemented operand, not a claim about which bar *ought* to own it.
    """
    st = engine_ready_short(entry=4140.0, atr_abs=9.562143)
    from datetime import datetime
    from tests.Grok._fixtures import candle

    st.retest_candle = candle(datetime(2026, 7, 22, 19, 0, 0), 4141, 4142, 4139, 4140.0, idx=72)
    trade_a = executor().build_trade(st)
    assert trade_a is not None
    st.atr_abs = 50.0
    trade_b = executor().build_trade(st)
    assert trade_b is not None
    assert trade_b.sl_price - trade_a.sl_price == pytest.approx(0.2 * (50.0 - 9.562143))


def test_substitute_wrong_engine_result_is_detectable_by_recompute():
    """A forged engine SL must fail a 5dp parity check against the operands.

    This is the check the episode-trace proofs run. Here we *deliberately*
    perturb the engine result and require the auditor to reject it.
    """
    sl_trace = _short_sl(4146.75, 9.562142857142915, 0.2)
    sl_forged = sl_trace * 1.001
    delta = abs(sl_forged - sl_trace)
    assert delta > 5e-6, "perturbation too small to be a useful mismatch"
    # 5 decimal places (trace contract)
    assert round(sl_forged, 5) != round(sl_trace, 5)


def test_future_bar_close_must_not_be_the_entry_operand():
    """Entry is retest_candle.close, not the soft-conf (next) bar close.

    Source: build_trade  `entry = state.retest_candle.close`
    Trace: entry 4154.55 @ 19:00; soft-conf close 4149.24 @ 19:15 (bars.csv)
    """
    st = engine_ready_short()
    assert st.retest_candle.close == pytest.approx(4154.55)
    future_close = 4149.24
    assert future_close != pytest.approx(st.retest_candle.close)
    # substituting the future close would change the inverted-SL verdict distance
    sl = _short_sl(st.displacement_candle.high, st.atr_abs, 0.2)
    assert sl < st.retest_candle.close
    # future close 4149.24 is still > sl 4148.66 — still inverted — but the
    # *entry operand* is different. A provenance-aware trace must not collapse them.


def test_stale_config_buffer_on_executor_is_the_one_that_binds():
    """Wrong config object: ExecutionEngine holds its own CRTConfig.

    Source: ExecutionEngine.__init__ stores config; build_trade reads self.config.
    """
    st = engine_ready_short(entry=4140.0)
    from datetime import datetime
    from tests.Grok._fixtures import candle

    st.retest_candle = candle(datetime(2026, 7, 22, 19, 0, 0), 4141, 4142, 4139, 4140.0, idx=72)
    t0 = executor(CRTConfig(sl_atr_buffer=0.2)).build_trade(st)
    t1 = executor(CRTConfig(sl_atr_buffer=1.0)).build_trade(st)
    assert t0 is not None and t1 is not None
    assert t1.sl_price - t0.sl_price == pytest.approx((1.0 - 0.2) * st.atr_abs)


def test_long_operands_are_not_reusable_on_the_short_formula():
    """Wrong state: applying SHORT formula to LONG operands is a detectable mismatch."""
    st = engine_ready_long()
    short_formula = _short_sl(st.displacement_candle.high, st.atr_abs, 0.2)
    long_formula = _long_sl(st.displacement_candle.low, st.atr_abs, 0.2)
    assert short_formula != pytest.approx(long_formula)
    assert long_formula == pytest.approx(4045.065714, abs=1e-6)
