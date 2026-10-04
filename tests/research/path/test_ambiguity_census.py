"""Program 10 / Phase 0A — census tests.

The load-bearing test is `test_p1_signature_is_exact_vs_kernel`: it brute-forces bar geometries
and asserts the census's P1 signature agrees with an INDEPENDENT re-derivation of the kernel's
own exit logic on every case. That is the safety property — a census that drifts from the kernel
it audits would silently misreport the very convention it exists to measure.
"""

import itertools
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from research.contracts import Signal
from research.exit_grid import Entry
from research.measurement.forward_walk import forward_walk, forward_walk_oco
from research.path.ambiguity_census import (
    EXPECTED_SL_RR,
    MIN_CELL_N,
    P1Event,
    cell_census,
    census_entry,
    census_instrument,
    overlap_census,
    detect_p1,
    oco_census,
    pool_census,
    stop_gate,
    verify_sl_rr,
)


@dataclass
class Bar:
    """Minimal Candle-like bar (kernels duck-type .high/.low/.close/.index/.timestamp)."""
    high: float
    low: float
    close: float
    index: int
    timestamp: datetime = datetime(2026, 1, 1, 10, 0)


def _bars(specs, start_index=1):
    return [Bar(high=h, low=l, close=c, index=start_index + k)
            for k, (h, l, c) in enumerate(specs)]


def _sig(direction="long", entry_index=0, sl_m=1.0, tp_m=2.0):
    return Signal(instrument="TEST", timestamp=datetime(2026, 1, 1), entry_index=entry_index,
                  direction=direction, entry=100.0, sl_atr_mult=sl_m, tp_atr_mult=tp_m, atr=1.0)


# ── the exactness proof ──────────────────────────────────────────────────────
def _ground_truth_tiebreak(sig: Signal, bars) -> bool:
    """Independently re-derive whether the kernel's same-bar tie-break fired.

    Deliberately NOT importing the kernel's internals: this mirrors forward_walk's
    intrabar_fixed logic from the module docstring (trail_stop == sl, never ratchets) so the
    comparison is a genuine cross-check rather than a tautology.
    """
    risk = sig.sl_atr_mult * sig.atr
    reward = sig.tp_atr_mult * sig.atr
    if sig.direction == "long":
        sl, tp = sig.entry - risk, sig.entry + reward
    else:
        sl, tp = sig.entry + risk, sig.entry - reward
    for bar in bars:
        if sig.direction == "long":
            sl_hit, tp_hit = bar.low <= sl, bar.high >= tp
        else:
            sl_hit, tp_hit = bar.high >= sl, bar.low <= tp
        if sl_hit:
            return tp_hit          # exits here; tie-break fired iff TP also touched
        if tp_hit:
            return False           # clean TP exit
    return False                   # timeout


@pytest.mark.parametrize("direction", ["long", "short"])
def test_p1_signature_is_exact_vs_kernel(direction):
    """Brute-force: detect_p1(outcome) == independent ground truth, on every geometry."""
    sig = _sig(direction)
    # Offsets straddle SL (-1.0 / +1.0) and TP (+2.0 / -2.0) in both directions.
    levels = [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    checked = 0
    seen_p1 = 0
    for hi_off, lo_off in itertools.product(levels, levels):
        if lo_off > hi_off:
            continue
        high, low = 100.0 + hi_off, 100.0 + lo_off
        close = (high + low) / 2.0
        # Two-bar corpus: a benign first bar, then the candidate geometry. This also exercises
        # the "earlier clean exit masks a later collision" path.
        for prefix in ([], [(100.1, 99.9, 100.0)]):
            bars = _bars(prefix + [(high, low, close)])
            out = forward_walk(sig, bars, max_forward=10, exit_model="intrabar_fixed")
            expected = _ground_truth_tiebreak(sig, bars)
            assert detect_p1(out) is expected, (
                f"{direction} hi={high} lo={low} prefix={bool(prefix)}: "
                f"detect_p1={detect_p1(out)} expected={expected} outcome={out.outcome} "
                f"time_to_tp={out.time_to_tp}")
            checked += 1
            if expected:
                seen_p1 += 1
    assert checked > 100, "brute force did not cover enough geometries"
    assert seen_p1 > 0, "no tie-break cases generated — the test would be vacuous"


@pytest.mark.parametrize("direction", ["long", "short"])
def test_tiebreak_invariant_time_to_tp_equals_duration(direction):
    """On every detected P1, time_to_tp == duration_candles (the assignment order at :124)."""
    sig = _sig(direction)
    spanning = (103.0, 97.0, 100.0)      # spans SL and TP in both directions
    for prefix_len in range(0, 4):
        prefix = [(100.1, 99.9, 100.0)] * prefix_len
        bars = _bars(prefix + [spanning])
        out = forward_walk(sig, bars, max_forward=10, exit_model="intrabar_fixed")
        assert detect_p1(out)
        assert out.time_to_tp == out.duration_candles == prefix_len + 1


def test_clean_sl_and_clean_tp_are_not_p1():
    sig = _sig("long")
    clean_sl = forward_walk(sig, _bars([(100.2, 98.5, 98.8)]), exit_model="intrabar_fixed")
    assert clean_sl.outcome == "SL_HIT" and not detect_p1(clean_sl)
    clean_tp = forward_walk(sig, _bars([(102.5, 101.0, 102.0)]), exit_model="intrabar_fixed")
    assert clean_tp.outcome == "TP_HIT" and not detect_p1(clean_tp)


def test_tp_on_earlier_bar_then_sl_is_not_p1():
    """A later SL cannot retro-flag an earlier clean TP — guards against a false positive."""
    sig = _sig("long")
    bars = _bars([(102.5, 101.0, 102.0), (100.0, 98.0, 98.5)])
    out = forward_walk(sig, bars, max_forward=10, exit_model="intrabar_fixed")
    assert out.outcome == "TP_HIT"
    assert not detect_p1(out)


# ── event arithmetic ─────────────────────────────────────────────────────────
def _spanning_corpus(n_entries: int, sl_m=1.0, tp_m=2.0):
    """Corpus where every entry collides on its next bar."""
    candles = []
    for i in range(n_entries * 2 + 2):
        candles.append(Bar(high=100.1, low=99.9, close=100.0, index=i,
                           timestamp=datetime(2026, 1, 1, 10, 0) + timedelta(minutes=15 * i)))
    entries = []
    for k in range(n_entries):
        i = k * 2
        candles[i + 1] = Bar(high=103.0, low=97.0, close=100.0, index=i + 1,
                             timestamp=candles[i + 1].timestamp)
        entries.append(Entry(entry_index=i, entry=100.0, direction="long", atr=1.0))
    return entries, candles


def test_census_entry_arithmetic_and_sl_rr_is_exactly_minus_one():
    entries, candles = _spanning_corpus(1)
    ev = census_entry(entries[0], candles, 1.0, 2.0, max_forward=10)
    assert isinstance(ev, P1Event)
    assert ev.rr_if_sl == pytest.approx(EXPECTED_SL_RR)     # intrabar_fixed never ratchets
    assert ev.rr_if_tp == pytest.approx(2.0)                 # tp_m / sl_m
    assert ev.r_swing == pytest.approx(3.0)                  # tp_m/sl_m + 1.0
    assert verify_sl_rr([ev]) == 0


@pytest.mark.parametrize("sl_m,tp_m,expected_swing", [
    (1.0, 2.0, 3.0), (0.5, 1.0, 3.0), (2.0, 3.0, 2.5), (1.0, 5.0, 6.0),
])
def test_r_swing_matches_closed_form(sl_m, tp_m, expected_swing):
    """r_swing == tp_m/sl_m + 1.0 across the grid (the closed form used in the pre-registration)."""
    entries, candles = _spanning_corpus(1)
    # Widen the colliding bar so it spans SL and TP at every tested geometry.
    candles[1] = Bar(high=100.0 + tp_m + 1.0, low=100.0 - sl_m - 1.0, close=100.0, index=1,
                     timestamp=candles[1].timestamp)
    ev = census_entry(entries[0], candles, sl_m, tp_m, max_forward=10)
    assert ev is not None
    assert ev.r_swing == pytest.approx(expected_swing)


def test_verify_sl_rr_flags_deviation():
    """The kernel-model check is behavioral: a bad rr_if_sl is counted, not silently accepted."""
    bad = P1Event(entry_index=0, sl_m=1.0, tp_m=2.0, rr_if_sl=-0.4, rr_if_tp=2.0, r_swing=2.4,
                  duration=1, atr=1.0, entry=100.0, exit_bar_range=6.0, tp_dist=2.0,
                  session="london")
    assert verify_sl_rr([bad]) == 1


# ── cell / pooling / gate ────────────────────────────────────────────────────
def test_cell_census_rate_and_bound():
    entries, candles = _spanning_corpus(4)
    cell = cell_census(entries, candles, 1.0, 2.0, max_forward=10)
    assert cell["n_signals"] == 4
    assert cell["n_p1"] == 4
    assert cell["ambiguity_rate"] == pytest.approx(1.0)
    assert cell["mean_r_swing"] == pytest.approx(3.0)
    assert cell["max_bias_R"] == pytest.approx(3.0)
    assert cell["power"] == "INSUFFICIENT"          # 4 < MIN_CELL_N
    assert cell["sl_rr_deviations"] == 0


def test_power_floor_marks_powered_above_threshold():
    entries, candles = _spanning_corpus(MIN_CELL_N + 1)
    cell = cell_census(entries, candles, 1.0, 2.0, max_forward=10)
    assert cell["n_p1"] >= MIN_CELL_N
    assert cell["power"] == "POWERED"


def test_pooling_uses_totals_not_mean_of_rates():
    """A tiny instrument with a 100% rate must not outweigh a large clean one."""
    big_entries, big_candles = _spanning_corpus(1)
    # Large instrument: many entries, none colliding.
    clean = [Bar(high=100.1, low=99.9, close=100.0, index=i,
                 timestamp=datetime(2026, 1, 1)) for i in range(400)]
    clean_entries = [Entry(entry_index=i, entry=100.0, direction="long", atr=1.0)
                     for i in range(0, 200)]
    per_inst = {
        "SMALL": census_instrument(big_entries, big_candles, sl_grid=[1.0], tp_grid=[2.0],
                                   max_forward=10),
        "LARGE": census_instrument(clean_entries, clean, sl_grid=[1.0], tp_grid=[2.0],
                                   max_forward=10),
    }
    pooled = pool_census(per_inst, [1.0], [2.0])["1.0x2.0"]
    assert pooled["n_p1"] == 1
    assert pooled["n_signals"] == 201
    # Mean-of-rates would give ~0.5; totals give ~0.005. (abs tolerance: pool_census rounds
    # to 6 dp so the JSON body is byte-stable across runs.)
    assert pooled["ambiguity_rate"] == pytest.approx(1 / 201, abs=1e-6)
    assert pooled["ambiguity_rate"] < 0.01


def test_stop_gate_verdicts():
    close_case = {"1.0x2.0": {"sl": 1.0, "tp": 2.0, "max_bias_R": 0.01}}
    assert stop_gate(close_case)["verdict"] == "CLOSE_PROGRAM"
    proceed_case = {"1.0x2.0": {"sl": 1.0, "tp": 2.0, "max_bias_R": 0.28}}
    assert stop_gate(proceed_case)["verdict"] == "PROCEED_TO_0B"
    missing = {"1.0x2.0": {"sl": 1.0, "tp": 2.0, "max_bias_R": None}}
    assert stop_gate(missing)["verdict"] == "INSUFFICIENT"


def test_stop_gate_reports_worst_cell_not_just_incumbent():
    pooled = {
        "1.0x2.0": {"sl": 1.0, "tp": 2.0, "max_bias_R": 0.02},
        "2.0x1.0": {"sl": 2.0, "tp": 1.0, "max_bias_R": 0.40},
    }
    g = stop_gate(pooled)
    assert g["worst_cell"] == "2.0x1.0"
    assert g["worst_max_bias_R"] == pytest.approx(0.40)


# ── determinism ──────────────────────────────────────────────────────────────
def test_census_is_deterministic():
    entries, candles = _spanning_corpus(6)
    a = census_instrument(entries, candles, sl_grid=[1.0, 2.0], tp_grid=[2.0, 3.0], max_forward=10)
    b = census_instrument(entries, candles, sl_grid=[1.0, 2.0], tp_grid=[2.0, 3.0], max_forward=10)
    assert a == b


# ── P1 vs same_bar_conflict: the two populations are DISTINCT ────────────────
# These two tests are the constructive proof behind the 2026-07-19 pre-registration correction.
# If either ever fails, the claim "neither set contains the other" has changed and the prior in
# docs/research/preregistration-program-10-intrabar-path.md must be revisited.

def test_p1_without_same_bar_conflict_not_sufficient():
    """A bar spanning BOTH levels that closes back inside is P1 but NOT same_bar_conflict."""
    candles = [Bar(high=100.1, low=99.9, close=100.0, index=0)] + _bars(
        [(103.0, 98.0, 100.0)] + [(100.1, 99.9, 100.0)] * 4, start_index=1)
    entries = [Entry(entry_index=0, entry=100.0, direction="long", atr=1.0)]
    ov = overlap_census(entries, candles, 1.0, 2.0, max_forward=10)
    assert ov["n_p1"] == 1
    assert ov["p1_only"] == 1
    assert ov["n_same_bar_conflict"] == 0     # close_only never closes across TP
    assert ov["both"] == 0


def test_same_bar_conflict_without_p1_not_necessary():
    """A wick-only SL on bar 1 that close_only later scores TP is same_bar_conflict, NOT P1."""
    candles = [Bar(high=100.1, low=99.9, close=100.0, index=0)] + _bars(
        [(101.0, 98.5, 101.0),        # intrabar SL (low<=99), TP not touched -> not P1
         (103.0, 100.0, 102.5)],      # close_only closes >= 102 -> TP_HIT
        start_index=1)
    entries = [Entry(entry_index=0, entry=100.0, direction="long", atr=1.0)]
    ov = overlap_census(entries, candles, 1.0, 2.0, max_forward=10)
    assert ov["n_p1"] == 0
    assert ov["n_same_bar_conflict"] == 1
    assert ov["same_bar_conflict_only"] == 1
    assert ov["both"] == 0


def test_overlap_census_shapes_and_totals():
    entries, candles = _spanning_corpus(3)
    ov = overlap_census(entries, candles, 1.0, 2.0, max_forward=10)
    total = ov["both"] + ov["p1_only"] + ov["same_bar_conflict_only"] + ov["neither"]
    assert total == 3
    assert ov["geometry"] == "1.0x2.0"
    assert ov["n_p1"] == ov["both"] + ov["p1_only"]
    assert ov["n_same_bar_conflict"] == ov["both"] + ov["same_bar_conflict_only"]


# ── P2 / P3 (OCO) ────────────────────────────────────────────────────────────
def _oco_signal(entry_index=0):
    return Signal(instrument="TEST", timestamp=datetime(2026, 1, 1), entry_index=entry_index,
                  direction="oco", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0,
                  meta={"box_high": 101.0, "box_low": 99.0})


def test_p2_detection_agrees_with_kernel_returning_none():
    """A double-edge bar must be counted as P2 AND make the kernel cancel (return None)."""
    sig = _oco_signal()
    candles = [Bar(high=100.0, low=100.0, close=100.0, index=0)] + \
              _bars([(102.0, 98.0, 100.0)], start_index=1)
    out = forward_walk_oco(sig, candles[1:], max_forward=10, entry_ttl=4)
    assert out is None                                    # kernel cancels (D1)
    c = oco_census([sig], candles, max_forward=10, entry_ttl=4)
    assert c["p2_double_edge_cancelled"] == 1
    assert c["p2_rate"] == pytest.approx(1.0)


def test_p2_distinguished_from_ttl_expiry():
    """Both make the kernel return None; the census must NOT conflate them."""
    sig = _oco_signal()
    candles = [Bar(high=100.0, low=100.0, close=100.0, index=0)] + \
              _bars([(100.2, 99.8, 100.0)] * 5, start_index=1)
    assert forward_walk_oco(sig, candles[1:], max_forward=10, entry_ttl=4) is None
    c = oco_census([sig], candles, max_forward=10, entry_ttl=4)
    assert c["p2_double_edge_cancelled"] == 0
    assert c["n_ttl_expired"] == 1


def test_p3_fill_bar_tp_suppression_counted():
    """Fill bar touches the long edge, then spans both SL and TP -> D2 suppresses TP."""
    sig = _oco_signal()
    # Long fill at 101.0; risk=1.0 -> SL 100.0; reward=2.0 -> TP 103.0.
    candles = [Bar(high=100.0, low=100.0, close=100.0, index=0)] + \
              _bars([(103.5, 99.5, 101.0)], start_index=1)
    c = oco_census([sig], candles, max_forward=10, entry_ttl=4)
    assert c["n_filled"] == 1
    assert c["p3_fill_bar_tp_suppressed"] == 1
    out = forward_walk_oco(sig, candles[1:], max_forward=10, entry_ttl=4)
    assert out is not None and out.outcome == "SL_HIT" and out.time_to_tp is None
