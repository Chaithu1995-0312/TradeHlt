"""TradePlan, TRS-05 stop, TRS-06 target. Prices are compared with ExecutionEngine, not recomputed here as the oracle only."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from config_layer.crt_engine_v2 import Candle, EngineState, ExecutionEngine, Range, SweepEvent
from config_layer.state_identity import Direction
from semantics.market.levels import range_levels
from semantics.trading.entry import resting_entry
from semantics.trading.plan import trade_plan
from semantics.trading.stop import place_stop
from semantics.trading.target import fixed_r_target, intent_r_multiple, structural_tp2_target
from semantics.trading.thesis import form_thesis
from semantics.types import Bias, LevelStatus, OhlcBar
from tests.helpers.crt_config import crt_config_for_test, retest_cache_for_test

_T0 = datetime(2024, 1, 1)


def _candle(index, open_, high, low, close):
    return Candle(_T0 + timedelta(minutes=15 * index), open_, high, low, close, index=index)


def _ohlc(index, open_, high, low, close):
    return OhlcBar(open_, high, low, close, index)


def _state(direction, *, h_ref, l_ref, entry=110.0, disp_low=99.0, disp_high=120.0, sweep_low=90.0, sweep_high=130.0, features=None):
    disp = _candle(5, 102.0, disp_high, disp_low, 110.0 if direction is Direction.LONG else 90.0)
    sweep_candle = _candle(2, 103.0, sweep_high, sweep_low, 102.0)
    retest = _candle(8, entry, entry + 1.0, entry - 1.0, entry)
    sweep = SweepEvent(direction, 100.0, sweep_candle, candle_index=2)
    return EngineState(
        active_range=Range(h_ref, l_ref, (h_ref + l_ref) / 2.0, _T0, "h1"),
        sweep_event=sweep,
        direction=direction,
        atr_abs=2.0,
        displacement_candle=disp,
        retest_candle=retest,
        cached_features=retest_cache_for_test() if features is None else features,
    )


def _long_thesis():
    _upper, lower = range_levels(
        120.0, 100.0, founding="m15_structural_range", formed_at=0, available_at=0,
        timeframe="M15", clock="htf_period",
    )
    thesis = form_thesis(
        _ohlc(2, 103.0, 104.0, 99.0, 102.0), lower, _ohlc(5, 102.0, 112.0, 101.0, 110.0),
        retrace_fraction=0.5, extension_fib=1.618, clock="htf_period",
    )
    assert thesis is not None and thesis.direction is Bias.LONG
    return thesis


def _short_thesis():
    upper, _lower = range_levels(
        100.0, 80.0, founding="m15_structural_range", formed_at=0, available_at=0,
        timeframe="M15", clock="htf_period",
    )
    thesis = form_thesis(
        _ohlc(2, 99.0, 101.0, 90.0, 98.0), upper, _ohlc(5, 99.0, 100.0, 80.0, 90.0),
        retrace_fraction=0.5, extension_fib=1.618, clock="htf_period",
    )
    assert thesis is not None and thesis.direction is Bias.SHORT
    return thesis


def test_plan_requires_invalidation_and_stop_and_rejects_an_inverted_stop():
    thesis = _long_thesis()
    cfg = crt_config_for_test()
    state = _state(Direction.LONG, h_ref=140.0, l_ref=90.0)
    stop = place_stop(cfg, state, sl_anchor="displacement", target_policy="fixed_r", plan_bar=8)
    assert stop is not None
    entry = resting_entry(_ohlc(8, 109.0, 111.0, 108.0, 110.0))
    plan = trade_plan(thesis, entry, stop)
    assert plan is not None
    assert plan.R == abs(entry.price - stop.price)
    assert plan.concept_id == thesis.concept_id
    assert plan.available_at >= max(thesis.available_at, entry.available_at, stop.available_at)
    equal = resting_entry(_ohlc(8, stop.price, stop.price, stop.price, stop.price))
    assert trade_plan(thesis, equal, stop) is None
    below = resting_entry(_ohlc(8, stop.price - 1.0, stop.price, stop.price - 1.0, stop.price - 1.0))
    assert trade_plan(thesis, below, stop) is None
    import dataclasses
    with pytest.raises(ValueError, match="I-11"):
        trade_plan(dataclasses.replace(thesis, invalidation=None), entry, stop)
    with pytest.raises(ValueError, match="I-11"):
        trade_plan(thesis, entry, None)

    short = _short_thesis()
    short_state = _state(Direction.SHORT, h_ref=140.0, l_ref=70.0, entry=110.0)
    short_stop = place_stop(cfg, short_state, sl_anchor="displacement", target_policy="fixed_r", plan_bar=8)
    assert short_stop is not None and short_stop.price > 110.0
    short_entry = resting_entry(_ohlc(8, 109.0, 111.0, 108.0, 110.0))
    assert trade_plan(short, short_entry, short_stop) is not None
    assert trade_plan(short, resting_entry(_ohlc(8, short_stop.price, short_stop.price, short_stop.price, short_stop.price)), short_stop) is None
    above = short_stop.price + 1.0
    assert trade_plan(short, resting_entry(_ohlc(8, above, above, above, above)), short_stop) is None


def test_stop_matches_execution_engine_for_both_anchors():
    cfg = crt_config_for_test()
    state = _state(Direction.LONG, h_ref=140.0, l_ref=90.0)
    for anchor in ("displacement", "sweep_extreme"):
        engine = ExecutionEngine(cfg, sl_anchor=anchor, target_policy="fixed_r")
        placed = place_stop(cfg, state, sl_anchor=anchor, target_policy="fixed_r", plan_bar=8)
        assert placed is not None
        assert placed.price == engine.stop_price(state)
        assert placed.buffer_atr == cfg.sl_atr_buffer
        assert placed.anchor == anchor
        assert placed.available_at >= state.displacement_candle.index
        assert placed.available_at >= state.sweep_event.candle.index
    displacement = place_stop(cfg, state, sl_anchor="displacement", target_policy="fixed_r", plan_bar=8)
    extreme = place_stop(cfg, state, sl_anchor="sweep_extreme", target_policy="fixed_r", plan_bar=8)
    assert displacement.price != extreme.price
    bare = EngineState(direction=Direction.LONG, atr_abs=2.0)
    assert place_stop(cfg, bare, sl_anchor="displacement", target_policy="fixed_r", plan_bar=1) is None
    assert ExecutionEngine(cfg, sl_anchor="displacement", target_policy="fixed_r").stop_price(bare) is None


def _edges(h_ref, l_ref):
    return range_levels(
        h_ref, l_ref, founding="m15_structural_range", formed_at=0, available_at=0,
        timeframe="M15", clock="htf_period",
    )


def test_targets_match_build_trade_and_intent_picks_the_multiple():
    cfg = crt_config_for_test()
    state = _state(Direction.LONG, h_ref=140.0, l_ref=90.0)
    engine = ExecutionEngine(cfg, sl_anchor="displacement", target_policy="fixed_r")
    trade = engine.build_trade(state)
    assert trade is not None
    intent, multiple = intent_r_multiple(cfg, state.cached_features, Bias.LONG)
    assert intent == ExecutionEngine._derive_trade_intent(
        state.cached_features, cfg.breakout_disp_threshold, Direction.LONG,
    )
    assert multiple == getattr(cfg, f"tp1_atr_multiplier_{intent}")
    tp1 = fixed_r_target(
        trade.entry_price, trade.sl_price, ordinal=1, r_multiple=multiple,
        direction=Bias.LONG, plan_bar=8, intent=intent,
    )
    tp2 = fixed_r_target(
        trade.entry_price, trade.sl_price, ordinal=2, r_multiple=cfg.tp2_atr_multiplier,
        direction=Bias.LONG, plan_bar=8, target_policy="fixed_r",
    )
    assert tp1.price == trade.tp1_price
    assert tp2.price == trade.tp2_price
    assert tp1.available_at >= 8

    swept = retest_cache_for_test(sweep_detected=True)
    sweep_state = _state(Direction.LONG, h_ref=140.0, l_ref=90.0, features=swept)
    sweep_trade = ExecutionEngine(cfg, sl_anchor="displacement", target_policy="fixed_r").build_trade(sweep_state)
    sweep_intent, sweep_multiple = intent_r_multiple(cfg, swept, Bias.LONG)
    assert sweep_intent != intent
    assert sweep_multiple == getattr(cfg, f"tp1_atr_multiplier_{sweep_intent}")
    assert fixed_r_target(
        sweep_trade.entry_price, sweep_trade.sl_price, ordinal=1, r_multiple=sweep_multiple,
        direction=Bias.LONG, plan_bar=8, intent=sweep_intent,
    ).price == sweep_trade.tp1_price


def test_structural_tp2_identity_ignores_the_nominal_multiple():
    upper, lower = _edges(120.0, 80.0)
    first, first_reason = structural_tp2_target(
        100.0, 90.0, upper, lower, direction=Bias.LONG, r_multiple=1.0, plan_bar=8,
    )
    second, second_reason = structural_tp2_target(
        100.0, 90.0, upper, lower, direction=Bias.LONG, r_multiple=3.0, plan_bar=8,
    )
    assert first_reason is None and second_reason is None
    assert first is not None and second is not None
    assert first.price == second.price == upper.price
    assert first.parameterization_id == second.parameterization_id
    assert upper.status is LevelStatus.ACTIVE


def test_structural_tp2_matches_build_trade_including_both_rejections():
    cfg = crt_config_for_test()
    base = _state(Direction.LONG, h_ref=140.0, l_ref=90.0)
    probe = ExecutionEngine(cfg, sl_anchor="displacement", target_policy="fixed_r")
    reference = probe.build_trade(base)
    assert reference is not None
    entry = reference.entry_price
    risk = abs(entry - reference.sl_price)
    cases = (
        ("accept", entry + risk + 5.0, None),
        ("exact", entry + risk, None),
        ("too_close", entry + risk * 0.5, "structural_tp2_too_close"),
        ("inverted", entry - 1.0, "structural_tp2_inverted"),
    )
    for _name, h_ref, expected in cases:
        state = _state(Direction.LONG, h_ref=h_ref, l_ref=90.0)
        engine = ExecutionEngine(cfg, sl_anchor="displacement", target_policy="structural_tp2")
        sl = engine.stop_price(state)
        built = engine.build_trade(state)
        upper, lower = _edges(h_ref, 90.0)
        before = upper.status
        target, reason = structural_tp2_target(
            state.retest_candle.close, sl, upper, lower,
            direction=Bias.LONG, r_multiple=cfg.tp2_atr_multiplier, plan_bar=8,
        )
        assert upper.status is before
        assert lower.status is LevelStatus.ACTIVE
        if expected is None:
            assert built is not None and target is not None and reason is None
            assert target.price == built.tp2_price
            assert target.available_at >= upper.available_at
        else:
            assert built is None
            assert engine.last_build_attempt.reason == expected
            assert target is None and reason == expected

    short_base = _state(Direction.SHORT, h_ref=140.0, l_ref=70.0)
    short_ref = ExecutionEngine(cfg, sl_anchor="displacement", target_policy="fixed_r").build_trade(short_base)
    assert short_ref is not None
    short_entry = short_ref.entry_price
    short_risk = abs(short_entry - short_ref.sl_price)
    short_cases = (
        (short_entry - short_risk - 5.0, None),
        (short_entry - short_risk, None),
        (short_entry - short_risk * 0.5, "structural_tp2_too_close"),
        (short_entry + 1.0, "structural_tp2_inverted"),
    )
    for l_ref, expected in short_cases:
        state = _state(Direction.SHORT, h_ref=150.0, l_ref=l_ref)
        engine = ExecutionEngine(cfg, sl_anchor="displacement", target_policy="structural_tp2")
        sl = engine.stop_price(state)
        built = engine.build_trade(state)
        upper, lower = _edges(150.0, l_ref)
        target, reason = structural_tp2_target(
            state.retest_candle.close, sl, upper, lower,
            direction=Bias.SHORT, r_multiple=cfg.tp2_atr_multiplier, plan_bar=8,
        )
        assert lower.status is LevelStatus.ACTIVE
        if expected is None:
            assert built is not None and target is not None
            assert target.price == built.tp2_price
        else:
            assert built is None and reason == engine.last_build_attempt.reason == expected
