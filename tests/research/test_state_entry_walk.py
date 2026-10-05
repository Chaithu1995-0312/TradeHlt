"""Floor for MC-STATEENTRY (src/research/state_entry/): synthetic bars only, never evidence.

Pins the measurement mechanics the contract declares: timestamp join (not candle_index),
setup direction carry, one unit per (setup, kind), the close-only arm ignoring wicks, the
no-lookahead entry-bar guard, horizon truncation, the engine's stop arithmetic, the split
purge/embargo, the BH family floor, and the verdict ladder.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from research.costs import xau_measured_cost_model
from research.state_entry import evaluate as ev_mod
from research.state_entry.evaluate import (
    INSUFFICIENT,
    NEGATIVE,
    POSITIVE,
    evaluate,
    overlap_count,
    split_rows,
    summarize,
)
from research.state_entry.extract import (
    ENTER_DISPLACEMENT,
    ENTER_RETEST,
    ENTER_SWEEP,
    EXECUTION_AT_APPROVAL,
    EXECUTION_LEGACY,
    REJECTED_AT_CONFIRMATION,
    Bar,
    EntryUnit,
    extract_units,
)
from research.state_entry.walk import (
    ARM_CLOSE_ONLY,
    ARM_SL_FIRST,
    GEOM_FIXED_ATR,
    GEOM_STRUCTURAL,
    Geometry,
    Levels,
    close_only_bars,
    unit_levels,
    walk_all,
    walk_unit,
)

_T0 = datetime(2025, 1, 6, 1, 0)
_G = Geometry(sl_atr_buffer=0.2, tp1_mult=1.0, tp2_mult=2.0, fixed_sl_atr_mult=1.0,
              partial_fraction=0.5)


def _bars(closes, *, wick=0.5):
    out = []
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        out.append(Bar(timestamp=_T0 + timedelta(minutes=15 * i), open=o,
                       high=max(o, c) + wick, low=min(o, c) - wick, close=c, index=i))
        prev = c
    return out


def _ts(bars, i):
    return bars[i].timestamp.strftime("%Y-%m-%dT%H:%M:%S")


def _unit(kind=ENTER_RETEST, direction="long", row=5, price=100.0, sweep=2, disp=3,
          atr=1.0, levels=None):
    return EntryUnit(entry_kind=kind, direction=direction, entry_row=row, entry_price=price,
                     setup_sweep_row=sweep, sweep_row=sweep, displacement_row=disp,
                     engine_atr=atr, engine_levels=levels)


# ── extract ──────────────────────────────────────────────────────────────────────────

def test_events_join_by_timestamp_not_candle_index():
    bars = _bars([100.0] * 20)
    events = [
        {"event": "SWEEP", "timestamp": _ts(bars, 4), "candle_index": 999, "direction": "LONG"},
        {"event": "STATE_TRANSITION", "timestamp": _ts(bars, 4), "candle_index": 999,
         "state_to": "SWEEP", "metadata": {"atr": 1.5}},
    ]
    units, _ = extract_units(events, bars)
    assert [(u.entry_kind, u.entry_row, u.direction) for u in units] == [(ENTER_SWEEP, 4, "long")]
    assert units[0].engine_atr == 1.5


def test_setup_direction_carries_and_one_unit_per_setup_kind():
    bars = _bars([100.0] * 30)
    events = [
        {"event": "STATE_TRANSITION", "timestamp": _ts(bars, 1), "state_to": "SWEEP"},  # no setup
        {"event": "SWEEP", "timestamp": _ts(bars, 2), "direction": "SHORT"},
        {"event": "STATE_TRANSITION", "timestamp": _ts(bars, 2), "state_to": "SWEEP"},
        {"event": "STATE_TRANSITION", "timestamp": _ts(bars, 3), "state_to": "DISPLACEMENT"},
        {"event": "STATE_TRANSITION", "timestamp": _ts(bars, 4), "state_to": "DISPLACEMENT"},
        {"event": "FILTER_REJECTED", "timestamp": _ts(bars, 6)},
        {"event": "SWEEP", "timestamp": _ts(bars, 10), "direction": "LONG"},
        {"event": "STATE_TRANSITION", "timestamp": _ts(bars, 10), "state_to": "SWEEP"},
    ]
    units, counts = extract_units(events, bars)
    assert counts["no_setup_direction"] == 1
    assert counts["duplicate_ENTER_DISPLACEMENT"] == 1
    assert counts["redisplacement_in_setup"] == 1
    got = [(u.entry_kind, u.direction, u.entry_row, u.displacement_row) for u in units]
    assert got == [
        (ENTER_SWEEP, "short", 2, None),
        (ENTER_DISPLACEMENT, "short", 3, 3),
        (REJECTED_AT_CONFIRMATION, "short", 6, 4),   # latest displacement, like the engine
        (ENTER_SWEEP, "long", 10, None),
    ]


def test_trade_opened_yields_legacy_and_at_approval_units():
    bars = _bars([100.0 + 0.1 * i for i in range(30)])
    events = [
        {"event": "SWEEP", "timestamp": _ts(bars, 2), "direction": "LONG"},
        {"event": "TRADE_OPENED", "timestamp": _ts(bars, 8), "direction": "LONG", "price": 99.5,
         "metadata": {"sl": 98.0, "tp1": 101.0, "tp2": 102.5}},
    ]
    units, _ = extract_units(events, bars)
    legacy, approval = units
    assert legacy.entry_kind == EXECUTION_LEGACY and legacy.entry_price == 99.5
    assert legacy.engine_levels == (98.0, 101.0, 102.5)
    assert approval.entry_kind == EXECUTION_AT_APPROVAL
    assert approval.entry_price == bars[8].close          # honest fill at the approval close


def test_trade_direction_disagreeing_with_setup_is_counted_not_relabelled():
    bars = _bars([100.0] * 20)
    events = [
        {"event": "SWEEP", "timestamp": _ts(bars, 2), "direction": "LONG"},
        {"event": "TRADE_OPENED", "timestamp": _ts(bars, 8), "direction": "SHORT", "price": 100.0,
         "metadata": {"sl": 101.0, "tp1": 99.0, "tp2": 98.0}},
    ]
    units, counts = extract_units(events, bars)
    assert units == [] and counts["trade_direction_mismatch"] == 1


# ── geometry ─────────────────────────────────────────────────────────────────────────

def test_structural_stop_uses_engine_anchor_arithmetic():
    bars = _bars([100.0] * 10, wick=1.0)
    sweep_unit = _unit(kind=ENTER_SWEEP, row=5, sweep=2, disp=None, atr=2.0)
    lv = unit_levels(sweep_unit, bars, GEOM_STRUCTURAL, _G)
    assert lv.sl == pytest.approx(bars[2].low - 0.2 * 2.0)      # sweep_extreme anchor
    disp_unit = _unit(kind=ENTER_RETEST, row=5, sweep=2, disp=3, atr=2.0)
    lv = unit_levels(disp_unit, bars, GEOM_STRUCTURAL, _G)
    assert lv.sl == pytest.approx(bars[3].low - 0.2 * 2.0)      # displacement anchor
    assert lv.tp1 == pytest.approx(lv.entry + lv.risk) and lv.tp2 == pytest.approx(lv.entry + 2 * lv.risk)


def test_fixed_atr_and_inverted_stop_guard():
    bars = _bars([100.0] * 10, wick=1.0)
    lv = unit_levels(_unit(direction="short", atr=2.0), bars, GEOM_FIXED_ATR, _G)
    assert lv.sl == pytest.approx(102.0) and lv.tp1 == pytest.approx(98.0)
    # displacement low above a long entry -> inverted stop -> engine refuses it
    bad = _unit(direction="long", price=90.0, atr=1.0)
    assert unit_levels(bad, bars, GEOM_STRUCTURAL, _G) is None


def test_legacy_keeps_engine_levels_and_at_approval_reanchors_targets():
    bars = _bars([100.0] * 10)
    legacy = _unit(kind=EXECUTION_LEGACY, price=99.5, levels=(98.0, 101.0, 102.5))
    lv = unit_levels(legacy, bars, GEOM_STRUCTURAL, _G)
    assert (lv.entry, lv.sl, lv.tp1, lv.tp2) == (99.5, 98.0, 101.0, 102.5)
    appr = _unit(kind=EXECUTION_AT_APPROVAL, price=100.0, levels=(98.0, 101.0, 102.5))
    lv = unit_levels(appr, bars, GEOM_STRUCTURAL, _G)
    assert lv.sl == 98.0 and lv.tp1 == pytest.approx(102.0) and lv.tp2 == pytest.approx(104.0)


# ── walk ─────────────────────────────────────────────────────────────────────────────

def _lv_long():
    return Levels(entry=100.0, sl=99.0, tp1=101.0, tp2=102.0, atr_abs=1.0)


def test_close_only_ignores_a_wick_through_the_stop_but_sl_first_does_not():
    closes = [100.0] * 6 + [99.5, 99.6, 99.7, 99.8]
    bars = _bars(closes, wick=0.8)            # bar 6 low = 98.7 < stop 99.0, closes 99.5
    u = _unit(row=5)
    ref = walk_unit(u, _lv_long(), bars, arm=ARM_SL_FIRST, horizon=4, partial_fraction=0.5)
    pri = walk_unit(u, _lv_long(), close_only_bars(bars), arm=ARM_CLOSE_ONLY, horizon=4,
                    partial_fraction=0.5)
    assert ref.outcome == "STOPPED"
    assert pri.outcome == "TIMEOUT"


def test_close_only_stop_fills_at_the_close_beyond_the_level():
    bars = _bars([100.0] * 6 + [98.0, 97.0])
    u = _unit(row=5)
    o = walk_unit(u, _lv_long(), close_only_bars(bars), arm=ARM_CLOSE_ONLY, horizon=2,
                  partial_fraction=0.5)
    assert o.outcome == "STOPPED" and o.rr_gross == pytest.approx(-2.0)


def test_entry_bar_range_never_exits_and_horizon_truncates():
    bars = _bars([100.0] * 5 + [90.0] + [100.0] * 3)   # entry bar 5 itself crashes
    u = _unit(row=5, price=100.0)
    o = walk_unit(u, _lv_long(), close_only_bars(bars), arm=ARM_CLOSE_ONLY, horizon=3,
                  partial_fraction=0.5)
    assert o is not None and o.duration_candles <= 3
    assert walk_unit(u, _lv_long(), bars, arm=ARM_SL_FIRST, horizon=10, partial_fraction=0.5) is None


def test_walk_all_emits_both_arms_geometries_and_horizons():
    bars = _bars([100.0 + 0.05 * i for i in range(60)])
    units = [_unit(row=10, sweep=8, disp=9, price=bars[10].close, atr=None)]
    rows, drops = walk_all(units, bars, _G, xau_measured_cost_model(), horizons=(4, 40))
    combos = {(r["arm"], r["geometry"], r["horizon"]) for r in rows}
    assert {(a, h) for a, _, h in combos} == {(a, h) for a in (ARM_CLOSE_ONLY, ARM_SL_FIRST)
                                             for h in (4, 40)}
    for r in rows:
        assert r["y_net"] == pytest.approx(r["y_gross"] - r["cost_r"]) and r["cost_r"] > 0


# ── evaluate ─────────────────────────────────────────────────────────────────────────

def test_split_purges_train_exits_and_embargoes_holdout():
    rows = [{"entry_row": i, "horizon": 40} for i in range(0, 1000, 10)]
    train, hold, m = split_rows(rows, 1000)
    assert m["cut_row"] == 700 and m["holdout_start_row"] == 796
    assert all(r["entry_row"] + 40 < 700 for r in train)
    assert all(r["entry_row"] >= 796 for r in hold)


def test_summarize_and_overlap():
    s = summarize([1.0, 1.0, 1.0, 1.1])
    assert s["n"] == 4 and s["p_one_sided"] < 0.001 and s["pf"] is None
    assert summarize([])["n"] == 0
    rows = [{"entry_row": 0, "duration": 5}, {"entry_row": 3, "duration": 1},
            {"entry_row": 10, "duration": 1}]
    assert overlap_count(rows) == 1


def _row(kind, direction, row, y, horizon=4):
    return {"entry_kind": kind, "direction": direction, "geometry": GEOM_FIXED_ATR,
            "arm": ARM_CLOSE_ONLY, "horizon": horizon, "entry_row": row, "duration": 1,
            "y_net": y, "y_gross": y, "entry": 100.0, "sl": 99.0, "sl_atr": 1.0, "hour": 1}


def test_verdict_ladder_negative_and_insufficient():
    bars = _bars([100.0] * 1000)
    rows = [_row(ENTER_SWEEP, "long", i, -0.5) for i in range(0, 600, 10)]
    rows += [_row(ENTER_DISPLACEMENT, "long", i, 2.0) for i in range(0, 50, 10)]
    out = evaluate(rows, bars, _G, xau_measured_cost_model())
    cells = out["cells"]
    assert cells[f"{ENTER_SWEEP}|long|{GEOM_FIXED_ATR}|4"]["verdict"] == NEGATIVE
    assert cells[f"{ENTER_DISPLACEMENT}|long|{GEOM_FIXED_ATR}|4"]["verdict"] == INSUFFICIENT
    assert out["family_size"] == 1                      # n < 30 never enters the BH family


def test_positive_requires_controls(monkeypatch):
    bars = _bars([100.0] * 2000)
    rows = [_row(ENTER_RETEST, "long", i, 1.0 + (i % 7) * 0.01) for i in range(0, 1390, 20)]
    rows += [_row(ENTER_RETEST, "long", i, 1.0 + (i % 7) * 0.01) for i in range(1500, 1990, 10)]
    monkeypatch.setattr(ev_mod, "random_entry_beats", lambda *a, **k: (100, []))
    out = evaluate(rows, bars, _G, xau_measured_cost_model())
    assert out["cells"][f"{ENTER_RETEST}|long|{GEOM_FIXED_ATR}|4"]["verdict"] == POSITIVE
    monkeypatch.setattr(ev_mod, "random_entry_beats", lambda *a, **k: (94, []))
    out = evaluate(rows, bars, _G, xau_measured_cost_model())
    assert out["cells"][f"{ENTER_RETEST}|long|{GEOM_FIXED_ATR}|4"]["verdict"] == "FAILS_CONTROL"


def test_contract_is_sealed_and_matches_module_constants():
    root = Path(__file__).resolve().parents[2]
    c = json.loads((root / "configs/research/measurement_contracts/instances/"
                    "MC-STATEENTRY-XAUUSD-M15-V1.json").read_text(encoding="utf-8"))
    from research.state_entry.walk import HORIZONS
    from research.state_entry.extract import ENTRY_KINDS
    assert c["exits"]["parameters"]["horizons_bars"] == list(HORIZONS)
    assert c["labels"]["horizon_bars"] == max(HORIZONS)
    assert c["metrics"]["multiplicity"]["n_variants_preregistered"] == len(ENTRY_KINDS) * 2 * 2 * len(HORIZONS)
    assert c["splits"]["seed"] == ev_mod.SEED
    assert c["trust_status"]["economic_claims_allowed"] is False
