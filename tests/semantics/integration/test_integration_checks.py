"""Verdict logic of the Semantic OS integration comparators on synthetic observed bars.

Range 100..120. Sweep bar 2 pierces 100 (LONG), wick 99. Displacement bar 3: 102 -> 110.
R1-A: the move starts at MKT-E01 sweep_extreme (the wick 99) -> 110, so the invalidation is 104.5
(strict) and the extension 116.798 — the same extension the engine computes. The engine retrace
still uses the body 102 -> 110 (recorded TRS-03 divergence).
"""

from __future__ import annotations

import copy

import pytest

from semantics.integration.checks import (
    AGREE, EXPECTED_DIVERGENCE, NOT_CHECKABLE, UNEXPLAINED, CheckContext, attribute,
    check_displacements, check_positions, check_sweeps, check_terminations, check_thesis_lifecycle,
    check_trade_plans,
)
from semantics.integration.observe import replay_gate
from semantics.integration.report import d_levels, summarize
from semantics.registry import load_concept_contracts, load_representation_shards

RANGE = {"h_ref": 120.0, "l_ref": 100.0, "size": 20.0, "session": "LONDON", "htf_candle_id": "H1"}
SWEEP_EV = {"price": 99.0, "direction": "LONG", "candle_index": 2, "double_confirmed": False}
SWEEP_C = {"index": 2, "timestamp": "t2", "open": 103.0, "high": 104.0, "low": 99.0, "close": 102.0}
DISP_C = {"index": 3, "timestamp": "t3", "open": 102.0, "high": 112.0, "low": 101.0, "close": 110.0}


def candle(i, o, h, l, c):
    return {"index": i, "timestamp": f"t{i}", "open": o, "high": h, "low": l, "close": c}


def facts(state, **kw):
    base = {"current_state": state, "active_range": RANGE, "range_clock_id": "H1", "sweep_event": None,
            "sweep_candle": None, "displacement_candle": None, "displacement_candle_index": None,
            "retest_candle_index": None, "trade": None, "atr": 5.0}
    base.update(kw)
    return base


def rec(i, c, before, after, events=(), htf="H1"):
    return {"bar": i, "candle": c, "htf_candle_id": htf, "before": before, "after": after,
            "action": {}, "events": list(events)}


SWEPT = dict(sweep_event=SWEEP_EV, sweep_candle=SWEEP_C)
DISPLACED = dict(SWEPT, displacement_candle=DISP_C, displacement_candle_index=3)


def setup_bars():
    return [
        rec(1, candle(1, 105, 108, 103, 106), facts("RANGE"), facts("RANGE")),
        rec(2, SWEEP_C, facts("RANGE"), facts("SWEEP", **SWEPT)),
        rec(3, DISP_C, facts("SWEEP", **SWEPT), facts("DISPLACEMENT", **DISPLACED)),
    ]


def ctx(bars, events=()):
    return CheckContext(bars, list(events))


def test_c1_every_reset_reason_must_map():
    rows = check_terminations(ctx([], [{"event": "RESET", "reason": "off_session_filter", "candle_index": 5},
                                      {"event": "RESET", "reason": "no such reason", "candle_index": 6}]))
    assert [r.verdict for r in rows] == [AGREE, UNEXPLAINED]


def test_c2_sweep_agree_unexplained_and_missed():
    rows = check_sweeps(ctx(setup_bars()))
    assert [(r.bar, r.verdict) for r in rows] == [(2, AGREE)]
    fake = setup_bars()
    fake[1]["candle"] = candle(2, 103, 104, 100.5, 102)        # never pierces 100
    assert check_sweeps(ctx(fake))[0].verdict == UNEXPLAINED
    missed = setup_bars()
    missed[1]["after"] = facts("RANGE")                        # GP-04 true, engine stays in RANGE
    row = check_sweeps(ctx(missed))[0]
    assert row.verdict == UNEXPLAINED and "stayed in RANGE" in row.note


def test_c2_a_two_sided_bar_reports_the_side_the_engine_dropped():
    bars = setup_bars()
    bars[1]["candle"] = candle(2, 110, 121, 99, 110)           # pierces both edges, closes inside
    bars[1]["after"] = facts("SWEEP", sweep_event=dict(SWEEP_EV, direction="SHORT"), sweep_candle=SWEEP_C)
    verdicts = [(r.engine, r.contract, r.verdict) for r in check_sweeps(ctx(bars))]
    assert ("UPPER", ["LOWER", "UPPER"], AGREE) in verdicts and ("UPPER", "LOWER", UNEXPLAINED) in verdicts


def test_c3_displacement_must_be_gp06_against_the_sweep_extreme():
    rows, setups = check_displacements(ctx(setup_bars()))
    assert {(r.concept_id, r.verdict) for r in rows} == {("MKT-E04", AGREE), ("TRS-01", AGREE)}
    assert setups[0].thesis is not None and setups[0].thesis.move_start == 99.0   # R1-A: the wick
    bad = setup_bars()
    bad[2]["candle"] = candle(3, 110, 112, 101, 102)           # bearish bar for a LONG
    rows, _ = check_displacements(ctx(bad))
    assert any(r.concept_id == "MKT-E04" and r.verdict == UNEXPLAINED for r in rows)


def _lifecycle(after_bar, events=(), htf="H1"):
    bars = setup_bars() + [after_bar if isinstance(after_bar, dict) else None]
    bars[-1]["events"] = list(events)
    bars[-1]["htf_candle_id"] = htf
    _rows, setups = check_displacements(ctx(bars))
    return check_thesis_lifecycle(ctx(bars), setups)


def test_c4_extension_is_measured_from_the_wick_like_the_engine():
    below = _lifecycle(rec(4, candle(4, 110, 117, 109, 116.5), facts("EXPANSION", **DISPLACED),
                           facts("EXPANSION", **DISPLACED)))
    assert below == []                                          # 116.5 < 116.798: neither side spent
    hit = _lifecycle(rec(4, candle(4, 110, 117.5, 109, 117.0), facts("EXPANSION", **DISPLACED),
                         facts("RANGE")), [{"event": "RESET", "reason": "1.618 extension hit @ 116.79800"}])
    assert hit[0].concept_id == "MKT-E11" and hit[0].verdict == AGREE


def test_c4_retrace_difference_is_the_recorded_trs03_divergence():
    reset = [{"event": "RESET", "reason": "50% retrace hit (retrace=0.562)"}]
    rows = _lifecycle(rec(4, candle(4, 108, 109, 105.2, 105.5), facts("EXPANSION", **DISPLACED),
                          facts("RANGE")), reset)
    assert rows[0].verdict == EXPECTED_DIVERGENCE
    assert rows[0].divergence_ref == attribute(load_concept_contracts()["concepts"], "TRS-03",
                                               "ResetLogic.should_reset retrace")
    both = _lifecycle(rec(4, candle(4, 108, 109, 103.5, 104.0), facts("EXPANSION", **DISPLACED),
                          facts("RANGE")), [{"event": "RESET", "reason": "50% retrace hit (retrace=0.750)"}])
    assert both[0].verdict == AGREE


def test_c4_r1b_rollover_expires_only_before_extension():
    # still DISPLACED at the flip, engine resets: both EXPIRED
    agree = _lifecycle(rec(4, candle(4, 110, 111, 108, 109), facts("DISPLACEMENT", **DISPLACED), facts("RANGE")),
                       [{"event": "RESET", "reason": "HTF changed: H1 -> H2"}], htf="H2")
    assert agree[0].concept_id == "MKT-E12" and agree[0].verdict == AGREE
    # still DISPLACED at the flip, engine keeps it: unexplained
    kept = _lifecycle(rec(4, candle(4, 110, 111, 108, 109), facts("DISPLACEMENT", **DISPLACED),
                          facts("DISPLACEMENT", **DISPLACED)), htf="H2")
    assert kept[0].concept_id == "MKT-E12" and kept[0].verdict == UNEXPLAINED
    # EXTENDED before the flip: the thesis survives; no row
    bars = setup_bars() + [
        rec(4, candle(4, 110, 112, 109, 111), facts("DISPLACEMENT", **DISPLACED), facts("EXPANSION", **DISPLACED)),
        rec(5, candle(5, 111, 112, 109, 110), facts("EXPANSION", **DISPLACED), facts("EXPANSION", **DISPLACED), htf="H2"),
    ]
    _rows, setups = check_displacements(ctx(bars))
    assert check_thesis_lifecycle(ctx(bars), setups) == []


def test_c4_post_flip_invalidation_the_engine_skips_is_the_recorded_divergence():
    bars = setup_bars() + [
        rec(4, candle(4, 110, 112, 109, 111), facts("DISPLACEMENT", **DISPLACED), facts("EXPANSION", **DISPLACED)),
        rec(5, candle(5, 111, 112, 109, 110), facts("EXPANSION", **DISPLACED), facts("EXPANSION", **DISPLACED), htf="H2"),
        rec(6, candle(6, 106, 106.5, 103, 103.5), facts("EXPANSION", **DISPLACED), facts("EXPANSION", **DISPLACED), htf="H2"),
    ]
    _rows, setups = check_displacements(ctx(bars))
    rows = check_thesis_lifecycle(ctx(bars), setups)
    assert len(rows) == 1 and rows[0].concept_id == "TRS-03" and rows[0].verdict == EXPECTED_DIVERGENCE
    assert "HTF protection" in rows[0].divergence_ref


def _trade_bars(*, tp1=117.6, exit_status="STOPPED"):
    trade = {"id": "CRT-0001", "entry_price": 108.0, "sl_price": 100.0, "tp1_price": tp1, "tp2_price": 124.0,
             "status": "OPEN", "pnl": 0.0, "partial_pnl": 0.0, "open_candle_index": 6,
             "displacement_origin": 102.0, "risk_pct": 0.01, "direction": "LONG"}
    live = dict(DISPLACED, retest_candle_index=5)
    closed = dict(trade, status=exit_status)
    return setup_bars() + [
        rec(4, candle(4, 110, 111, 107, 109), facts("EXPANSION", **live), facts("EXPANSION", **live)),
        rec(5, candle(5, 109, 109.5, 107.5, 108), facts("EXPANSION", **live), facts("RETEST", **live)),
        rec(6, candle(6, 108, 109, 107.8, 108.5), facts("RETEST", **live), facts("EXECUTION", **dict(live, trade=trade))),
        rec(7, candle(7, 108, 108.2, 99.0, 103.0), facts("EXECUTION", **dict(live, trade=trade)),
            facts("EXECUTION", **dict(live, trade=closed))),
    ]


def test_c5_trade_plan_entry_stop_targets():
    rows = check_trade_plans(ctx(_trade_bars()))
    got = {(r.concept_id, r.verdict) for r in rows}
    assert ("TRS-04", AGREE) in got and ("TRS-04", EXPECTED_DIVERGENCE) in got
    assert ("TRS-05", AGREE) in got and all(r.verdict != UNEXPLAINED for r in rows)
    off = check_trade_plans(ctx(_trade_bars(tp1=119.0)))
    assert any(r.concept_id == "TRS-06" and r.verdict == UNEXPLAINED for r in off)


def test_c5_c6_say_so_when_there_is_no_trade():
    assert {r.verdict for r in check_trade_plans(ctx(setup_bars()))} == {NOT_CHECKABLE}
    _rows, setups = check_displacements(ctx(setup_bars()))
    assert {r.verdict for r in check_positions(ctx(setup_bars()), setups)} == {NOT_CHECKABLE}


def test_c6_position_exit_matches_the_contract_replay():
    bars = _trade_bars()
    _rows, setups = check_displacements(ctx(bars))
    rows = check_positions(ctx(bars), setups)
    assert rows[0].verdict == AGREE and rows[0].contract == {"exit": "STOP", "bar": 7}
    wrong = _trade_bars(exit_status="TP2")
    _rows, setups = check_displacements(ctx(wrong))
    assert check_positions(ctx(wrong), setups)[0].verdict == UNEXPLAINED


# ── C7 feature slots ──────────────────────────────────────────────────────────────────────
# Slots are built the way the pipeline builds them (causal twin: latest swing level only, inclusive
# tie, no consumption); the contract side walks the MKT-L01 lifecycle. k=2, W=5 (active config).
# BASE: swing high 110 at bar 3 (available 5), swing low 95 at bar 6 (available 8).
_BASE = [(100, 101, 99, 100), (100, 102, 99, 101), (101, 104, 100, 103), (103, 110, 102, 108),
         (108, 109, 104, 105), (105, 106, 97, 98), (98, 99, 95, 96), (96, 100, 96, 99),
         (99, 103, 97, 102)]
# 9 closes ON 110 (inclusive tie), 10 closes beyond 110 (BROKEN), 11 re-fires on the BROKEN level,
# 12 sweeps 95, 13 closes below 95.
_TIE = _BASE + [(102, 111, 101, 110), (110, 112, 108, 111), (111, 113, 109, 109.5),
                (109, 110, 94, 96), (96, 97, 93, 94)]
# 9 sweeps both 110 and 95 (two-sided), 10 re-fires on the now-SWEPT 110.
_TWO_SIDED = _BASE + [(100, 111, 94, 100), (100, 110.5, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)]
# a newer, lower swing high 103 (bar 8, available 10); 11 sweeps the OLDER 110 and closes beyond 103.
_OLDER = _BASE + [(102, 102.5, 100, 101), (101, 102, 99.5, 100), (101, 111, 100.5, 108), (108, 109, 107, 108)]


def _c7_inputs(ohlc):
    import numpy as np
    import pandas as pd

    from features.causal_structure import causal_structure_series
    from features.smc.choch import change_of_character
    from semantics.market.conditions import momentum_bias, session
    from semantics.registry import active_config_value as cfg

    ts = list(pd.date_range("2026-07-06", periods=len(ohlc), freq="15min").strftime("%Y-%m-%d %H:%M:%S"))
    o, h, l, c = (np.array(col, dtype=float) for col in zip(*ohlc))
    history = {"timestamp": ts, "open": o, "high": h, "low": l, "close": c}
    s = causal_structure_series(h, l, c, np.ones(len(c)), k=int(cfg("feature_pipeline.swing_window")),
                                double_sweep_window=int(cfg("feature_pipeline.double_sweep_window")))
    mom = momentum_bias(c, fast=cfg("feature_pipeline.ema_fast_span"), slow=cfg("feature_pipeline.ema_slow_span")).values
    sess = session(ts, basis=cfg("feature_pipeline.session_timestamp_basis"),
                   windows=cfg("feature_pipeline.session_windows_utc")).values
    features = {}
    for i, t in enumerate(ts):
        slot = {k: float(s[k][i]) for k in ("break_of_structure", "double_sweep", "swing_high", "swing_low",
                                              "higher_high", "lower_low", "liquidity_sweep", "sweep_detected")}
        slot["trend_bias"], slot["session"] = float(mom[i]), float(sess[i])
        slot["change_of_character"] = float(change_of_character(slot["break_of_structure"], slot["trend_bias"]))
        features[t] = slot
    bars = [{"bar": 100 + i, "candle": {"timestamp": t}} for i, t in enumerate(ts)]
    return bars, features, history


def _c7(features=None, history=None, bars=None):
    from semantics.integration.checks import check_feature_slots

    return check_feature_slots(CheckContext(bars or [], [], features=features, history=history),
                               load_representation_shards())


def _rows(ohlc, mutate=None):
    bars, features, history = _c7_inputs(ohlc)
    if mutate:
        mutate(features, history)
    return _c7(features, history, bars)


def _at(rows, concept, bar, slot):
    return [r for r in rows if r.concept_id == concept and r.bar == bar
            and isinstance(r.engine, dict) and r.engine.get("slot") == slot]


def test_c7_tie_and_absence_are_recorded_and_a_broken_level_is_not_sweepable():
    from semantics.integration.checks import NOTE_BROKEN

    rows = _rows(_TIE)
    concepts = load_concept_contracts()["concepts"]
    tie = _at(rows, "MKT-E01", 109, "sweep_detected")[0]
    assert tie.verdict == EXPECTED_DIVERGENCE and tie.divergence_ref == attribute(concepts, "MKT-E01", "FM-058 tie")
    broken = _at(rows, "MKT-E01", 111, "liquidity_sweep")[0]
    assert broken.verdict == UNEXPLAINED and broken.note == NOTE_BROKEN
    assert _at(rows, "MKT-E01", 112, "sweep_detected")[0].verdict == AGREE
    assert _at(rows, "MKT-C01", 100, "break_of_structure")[0].divergence_ref == attribute(concepts, "MKT-C01", "FM-057")
    assert _at(rows, "MKT-C01", 113, "break_of_structure")[0].verdict == AGREE
    assert _at(rows, "MKT-L01", 105, "swing_high")[0].verdict == AGREE
    assert _at(rows, "MKT-L01", 108, "swing_low")[0].verdict == AGREE
    assert _at(rows, "MKT-E08", 109, "higher_high")[0].verdict == AGREE
    assert _at(rows, "MKT-E08", 113, "lower_low")[0].verdict == AGREE
    for cid in ("MKT-C03", "MKT-C06"):     # every bar agrees: one summary row each, no per-bar rows
        assert [(r.verdict, r.bar) for r in rows if r.concept_id == cid] == [(AGREE, None)]
    assert not [r for r in rows if r.concept_id == "MKT-C07" and r.verdict == UNEXPLAINED]


def test_c7_two_sided_bar_is_the_recorded_encoding_divergence_and_a_swept_level_is_consumed():
    from semantics.integration.checks import E01_TWO_SIDED, NOTE_SWEPT

    rows = _rows(_TWO_SIDED)
    on9 = _at(rows, "MKT-E01", 109, "liquidity_sweep")
    assert {(r.contract if isinstance(r.contract, str) else tuple(r.contract), r.verdict) for r in on9} == {
        (("LOWER", "UPPER"), AGREE), ("LOWER", EXPECTED_DIVERGENCE)}
    lower = next(r for r in on9 if r.verdict == EXPECTED_DIVERGENCE)
    assert lower.divergence_ref == attribute(load_concept_contracts()["concepts"], "MKT-E01", E01_TWO_SIDED)
    repeat = _at(rows, "MKT-E01", 110, "liquidity_sweep")[0]
    assert repeat.verdict == UNEXPLAINED and repeat.note == NOTE_SWEPT
    # MKT-C04 v2: both sides swept within W; the slot is FM-060 on its one-sided history -> recorded
    c04 = _at(rows, "MKT-C04", 109, "double_sweep")[0]
    assert c04.verdict == EXPECTED_DIVERGENCE and c04.engine["value"] == 0 and c04.contract is True
    assert c04.divergence_ref == attribute(load_concept_contracts()["concepts"], "MKT-C04",
                                           "FM-060 rule on the liquidity_sweep slot")


def test_c7_double_sweep_slot_not_following_its_own_fm060_is_unexplained():
    def wrong(features, history):
        t = history["timestamp"][7]          # no sweep anywhere near bar 7: FM-060 and contract both 0
        features[t] = dict(features[t], double_sweep=1.0)

    row = _at(_rows(_TIE, wrong), "MKT-C04", 107, "double_sweep")[0]
    assert row.verdict == UNEXPLAINED and row.note == "slot is not FM-060 of its own liquidity_sweep history"


# 9 sweeps only 110 (95 stays ACTIVE); 10 re-fires on the SWEPT 110 and sweeps the ACTIVE 95.
_PRECEDENCE = _BASE + [(100, 111, 99, 100), (100, 110.5, 94, 100), (100, 101, 99, 100), (100, 101, 99, 100)]


def test_c7_one_sided_contract_bar_is_not_called_two_sided():
    from semantics.integration.checks import NOTE_PRECEDENCE, NOTE_SWEPT

    rows = _at(_rows(_PRECEDENCE), "MKT-E01", 110, "liquidity_sweep")
    got = {(r.contract if isinstance(r.contract, str) else tuple(r.contract), r.verdict, r.note) for r in rows}
    assert got == {(("LOWER",), UNEXPLAINED, NOTE_SWEPT), ("LOWER", UNEXPLAINED, NOTE_PRECEDENCE)}
    assert all(r.divergence_ref is None for r in rows)


def test_c7_older_active_level_swept_is_reported():
    from semantics.integration.checks import NOTE_OLDER

    row = _at(_rows(_OLDER), "MKT-E01", 111, "liquidity_sweep")[0]
    assert row.verdict == UNEXPLAINED and row.note == NOTE_OLDER and row.engine["value"] == 0


def test_c7_a_wrong_slot_value_is_unexplained():
    def wrong(features, history):
        t = history["timestamp"][12]
        features[t] = dict(features[t], sweep_detected=0.0, session=features[t]["session"] + 1,
                           change_of_character=1.0)   # contract: no break on bar 12 -> 0

    rows = [r for r in _rows(_TIE, wrong) if r.bar == 112]
    assert {(r.concept_id, r.verdict) for r in rows} >= {
        ("MKT-E01", UNEXPLAINED), ("MKT-C06", UNEXPLAINED), ("MKT-C07", UNEXPLAINED)}


def test_c7_without_the_feature_frame_says_so_and_levels_reach_d4():
    from semantics.integration.report import inventory

    assert {r.verdict for r in _c7()} == {NOT_CHECKABLE}
    rows = _rows(_TIE)
    levels = {i["concept_id"]: i["level"]
              for i in d_levels(load_concept_contracts()["concepts"], load_representation_shards(), rows)}
    # MKT-C07 stays D2 here: this fixture has no break against momentum (covered in the wrong-slot test)
    assert all(levels[c] == "D4" for c in ("MKT-C01", "MKT-C03", "MKT-C04", "MKT-C06", "MKT-E01", "MKT-E08", "MKT-L01"))
    assert {g["mechanism"] for g in inventory(rows) if g["concept_id"] == "MKT-E01"} >= {
        "inclusive tie: close equals the latest swing level"}


def test_attribution_must_name_a_recorded_divergence():
    with pytest.raises(KeyError):
        attribute(load_concept_contracts()["concepts"], "TRS-03", "no such surface")


def test_replay_gate():
    a = [{"candle_index": 1, "event": "RESET", "state_to": "RANGE", "reason": "x"}]
    assert replay_gate(a, copy.deepcopy(a))["status"] == "PASS"
    b = copy.deepcopy(a)
    b[0]["reason"] = "y"
    assert replay_gate(a, b)["status"] == "REPLAY_NOT_FAITHFUL"


def test_report_levels_and_no_performance_numbers():
    concepts = load_concept_contracts()["concepts"]
    rows = check_sweeps(ctx(setup_bars()))
    levels = {i["concept_id"]: i["level"] for i in d_levels(concepts, load_representation_shards(), rows)}
    assert levels["MKT-E01"] == "D4" and levels["MKT-E03"] == "D1"
    summary = summarize(rows, {}, {"status": "PASS"}, [])

    def keys(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield str(k).lower()
                yield from keys(v)

    assert not any(word in k for k in keys(summary) for word in ("pnl", "expectancy", "win_rate", "profit"))
