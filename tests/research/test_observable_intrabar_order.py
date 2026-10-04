"""observable_only: OHLC establishes level TOUCHES, never the ORDER of competing touches.

Geometry (long): entry 100, SL 99 (risk 1), TP1 101, TP2 102, trail 100.5, partial 0.5.
Fork model (state-machine-legal only, never permutations):
    OPEN: SL+TP1 -> {STOP, TP1}; OPEN: SL+TP2 -> {STOP, TP2}; TP1: trail+TP2 -> {STOP, TP2}
Non-forks: TP1+TP2 (price must cross TP1 to reach TP2), TP1 + the trail it arms, trail
while OPEN (does not exist). A later single touch advances the live branch; it never
removes a terminal branch, so ambiguity is not retroactively resolved.
"""
from __future__ import annotations

import itertools
import random
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.contracts import Signal                                        # noqa: E402
from research.measurement.forward_walk import forward_walk                   # noqa: E402
from research.oracle.multi_tp_walk import (                                  # noqa: E402
    EV_STAY, EV_STOP, EV_TP1, EV_TP2, EXIT_KIND_AMBIGUOUS, RR_BASIS_ACTUAL,
    RR_BASIS_COMPAT_MIN_BRANCH, TIE_BREAK_OBSERVABLE, TIE_BREAK_PRODUCTION,
    _legal_branches, multi_tp_walk,
)
from research.oracle.reference_walker import reference_walk                  # noqa: E402

E, SL, TP1, TP2 = 100.0, 99.0, 101.0, 102.0


def B(i, hi, lo, close=None):
    return SimpleNamespace(index=i, high=hi, low=lo, open=(hi + lo) / 2,
                           close=(hi + lo) / 2 if close is None else close)


def walk(bars, tie=TIE_BREAK_OBSERVABLE, **kw):
    return multi_tp_walk(E, "long", SL, TP1, TP2, bars, tie_break=tie, entry_index=0, **kw)


QUIET = lambda i: B(i, 101.1, 100.9, 101.0)          # touches TP1 level only, trail untouched
TP1_ONLY = lambda i: B(i, 101.2, 100.8, 101.0)
SL_TP1 = lambda i: B(i, 101.2, 98.9, 101.0)           # competing: SL + TP1
SL_TP2 = lambda i: B(i, 102.2, 98.9, 101.0)           # competing: SL + TP2
TRAIL_ONLY = lambda i: B(i, 100.8, 100.4, 100.6)      # below trail 100.5, no TP2 (TP1 state)
TRAIL_TP2 = lambda i: B(i, 102.2, 100.4, 101.0)       # competing in TP1 state


# ---- single touch: unambiguous, actual R -------------------------------------------------
def test_sl_only():
    o = walk([B(1, 100.5, 98.9, 99.5)])
    assert (o.outcome, o.rr_gross, o.ambiguous, o.rr_gross_basis) == ("STOPPED", -1.0, False, RR_BASIS_ACTUAL)


def test_tp1_only():
    o = walk([TP1_ONLY(1), QUIET(2)])
    assert o.reached_tp1 and not o.ambiguous and o.outcome == "TIMEOUT"


def test_tp2_only():
    o = walk([B(1, 102.5, 100.2, 102.0)])
    assert (o.outcome, o.rr_gross, o.ambiguous) == ("TP1_TP2", 1.5, False)


def test_trail_only():
    o = walk([TP1_ONLY(1), TRAIL_ONLY(2)])
    assert (o.outcome, o.rr_gross, o.ambiguous, o.exit_kind) == ("TP1_BE_STOP", 0.75, False, "SL_HIT")


# ---- fork cases ---------------------------------------------------------------------------
def test_fork_open_sl_and_tp1():
    o = walk([SL_TP1(1), QUIET(2)])
    assert o.ambiguous and o.rr_band == (-1.0, 1.0) and o.n_branches == 2
    assert o.rr_gross == -1.0 and o.rr_gross_basis == RR_BASIS_COMPAT_MIN_BRANCH
    assert o.exit_kind == EXIT_KIND_AMBIGUOUS


def test_fork_open_sl_and_tp2():
    o = walk([SL_TP2(1)])
    assert o.ambiguous and o.rr_band == (-1.0, 1.5) and o.n_branches == 2


def test_fork_tp1_state_trail_and_tp2():
    o = walk([TP1_ONLY(1), TRAIL_TP2(2)])
    assert o.ambiguous and o.rr_band == (0.75, 1.5) and o.n_branches == 2


# ---- non-forks ----------------------------------------------------------------------------
def test_tp1_and_tp2_is_deterministic():
    o = walk([B(1, 102.2, 100.6, 102.0)])
    assert not o.ambiguous and o.outcome == "TP1_TP2" and o.n_branches == 1


def test_tp1_with_newly_armed_trail_not_tested_same_bar():
    # low 100.2 pierces the 100.5 trail that TP1 arms, but the trail does not exist before TP1.
    o = walk([B(1, 101.2, 100.2, 101.0), QUIET(2)])
    assert not o.ambiguous and o.reached_tp1 and o.outcome == "TIMEOUT"


def test_generator_never_emits_illegal_branches():
    for status, active, s, t1, t2 in itertools.product([False, True], [True, False], [False, True],
                                                       [False, True], [False, True]):
        evs = _legal_branches(status, active, s, t1, t2)
        assert evs and len(evs) <= 2 and len(set(evs)) == len(evs)
        if len(evs) == 2:
            assert evs[0] == EV_STOP and s and evs[1] in (EV_TP1, EV_TP2)   # fork only on SL + a target
        if status:
            assert EV_TP1 not in evs                                        # no second TP1
        if t2:
            assert EV_TP1 not in evs                                        # TP1+TP2 -> TP2, no TP1 fork
        if not s:
            assert EV_STOP not in evs and len(evs) == 1                     # no stop touch, no fork
        # nothing resembling "trail while OPEN": there is no trail event at all
        assert set(evs) <= {EV_STOP, EV_TP1, EV_TP2, EV_STAY}


# ---- sequential resolution (live branch advances; dead branch is never excluded) ---------
def test_fork_then_sl_resolves_live_branch_to_stop():
    o = walk([SL_TP1(1), TRAIL_ONLY(2)])
    assert o.ambiguous and o.rr_band == (-1.0, 0.75) and o.exit_kind == "SL_HIT"


def test_fork_then_tp1_touch_does_not_remove_sl_branch():
    o = walk([SL_TP1(1), B(2, 101.3, 100.6, 101.0), QUIET(3)])
    assert o.ambiguous and o.rr_band[0] == -1.0


def test_fork_then_tp2_resolves_live_branch():
    o = walk([SL_TP1(1), B(2, 102.1, 100.6, 102.0)])
    assert o.ambiguous and o.rr_band == (-1.0, 1.5) and o.exit_kind == EXIT_KIND_AMBIGUOUS


def test_fork_then_trail_resolves_live_branch():
    o = walk([SL_TP1(1), B(2, 100.8, 100.4, 100.6)])
    assert o.rr_band == (-1.0, 0.75)


# ---- window termination -------------------------------------------------------------------
def test_unresolved_at_window_end_uses_timeout_pricing():
    o = walk([SL_TP1(1), QUIET(2), QUIET(3)], max_forward=3)
    # live branch: TP1 realised + runner marked to last close 101 -> +1.0R; dead branch -1R
    assert o.rr_band == (-1.0, 1.0) and o.n_branches == 2
    o2 = walk([SL_TP1(1), QUIET(2), QUIET(3)], max_forward=3, timeout_pricing="trail")
    assert o2.rr_band == (-1.0, 0.75)


# ---- regression: default untouched; unambiguous paths equal production --------------------
def test_default_tie_break_is_production():
    bars = [SL_TP1(1)]
    assert walk(bars, tie=TIE_BREAK_PRODUCTION).rr_gross == -1.0
    assert multi_tp_walk(E, "long", SL, TP1, TP2, bars, entry_index=0).rr_gross == -1.0
    assert not multi_tp_walk(E, "long", SL, TP1, TP2, bars, entry_index=0).ambiguous


@pytest.mark.parametrize("tie", [TIE_BREAK_PRODUCTION, TIE_BREAK_OBSERVABLE])
def test_forward_bar_without_index_is_rejected(tie):
    no_index = SimpleNamespace(high=101.1, low=100.9, close=101.0, open=101.0)
    with pytest.raises(ValueError, match="lookahead"):
        multi_tp_walk(E, "long", SL, TP1, TP2, [no_index], entry_index=0, tie_break=tie)
    with pytest.raises(ValueError, match="lookahead"):
        reference_walk(E, "long", SL, TP1, TP2, [no_index], entry_index=0, tie_break=tie)


def test_entry_index_is_required():
    with pytest.raises(TypeError):
        multi_tp_walk(E, "long", SL, TP1, TP2, [QUIET(1)])
    with pytest.raises(TypeError):
        reference_walk(E, "long", SL, TP1, TP2, [QUIET(1)])
    with pytest.raises(ValueError, match="entry_index is required"):
        multi_tp_walk(E, "long", SL, TP1, TP2, [QUIET(1)], entry_index=None)
    with pytest.raises(ValueError, match="entry_index is required"):
        reference_walk(E, "long", SL, TP1, TP2, [QUIET(1)], entry_index=None)


def test_unambiguous_paths_equal_production_and_twin():
    rng = random.Random(7)
    n_cmp = n_amb = 0
    for _ in range(3000):
        bars, px = [], E
        for i in range(1, 30):
            mid = px + rng.uniform(-0.35, 0.35)
            hi, lo = mid + rng.uniform(0, 0.35), mid - rng.uniform(0, 0.35)
            if rng.random() < 0.05:                      # occasional wide bar -> real forks
                hi, lo = hi + rng.uniform(0, 1.5), lo - rng.uniform(0, 1.5)
            bars.append(B(i, hi, lo, mid))
            px = mid
        obs = walk(bars)
        twin = reference_walk(E, "long", SL, TP1, TP2, bars, tie_break=TIE_BREAK_OBSERVABLE,
                              entry_index=0)
        assert (twin.ambiguous, twin.rr_band, twin.n_branches, twin.rr_gross, twin.exit_kind) == \
               (obs.ambiguous, obs.rr_band, obs.n_branches, obs.rr_gross, obs.exit_kind)
        if obs.ambiguous:
            n_amb += 1
            continue
        if any(b.high >= TP2 for b in bars):
            continue                      # production defers a TP2-from-OPEN bar by one bar
        prod = walk(bars, tie=TIE_BREAK_PRODUCTION)
        assert (obs.outcome, obs.rr_gross, obs.exit_kind) == (prod.outcome, prod.rr_gross, prod.exit_kind)
        n_cmp += 1
    assert n_cmp > 500 and n_amb > 50     # neither comparison is vacuous


def test_observable_rejects_stop_policy():
    with pytest.raises(ValueError):
        walk([QUIET(1)], same_bar_update=True)


# ---- single-TP forward_walk ---------------------------------------------------------------
def _sig():
    return Signal(instrument="T", timestamp=datetime(2026, 1, 1), entry_index=0,
                  direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0, meta={})


def test_forward_walk_same_bar_sl_tp_is_ambiguous_but_default_is_sl_first():
    both = [B(1, 102.5, 98.5, 100.0)]
    d = forward_walk(_sig(), both)
    assert d.outcome == "SL_HIT" and not d.ambiguous           # historical default unchanged
    o = forward_walk(_sig(), both, tie_break="observable_only")
    assert o.ambiguous and o.rr_band == (-1.0, 2.0)


def test_forward_walk_single_touch_unchanged_in_observable_mode():
    for bars in ([B(1, 100.5, 98.5, 99.0)], [B(1, 102.5, 100.2, 102.0)], [B(1, 100.5, 99.5, 100.0)]):
        a = forward_walk(_sig(), bars)
        b = forward_walk(_sig(), bars, tie_break="observable_only")
        assert (a.outcome, a.rr_achieved) == (b.outcome, b.rr_achieved) and not b.ambiguous


# ---- entry bar: SL / TP1 / TP2 are never evaluated on it --------------------------------
ENTRY_BAR = B(0, 102.5, 98.5, 100.0)      # index 0 == entry_index; touches SL, TP1 and TP2


@pytest.mark.parametrize("call", [
    lambda bars: multi_tp_walk(E, "long", SL, TP1, TP2, bars, entry_index=0,
                               tie_break=TIE_BREAK_PRODUCTION),
    lambda bars: multi_tp_walk(E, "long", SL, TP1, TP2, bars, entry_index=0,
                               tie_break=TIE_BREAK_OBSERVABLE),
    lambda bars: reference_walk(E, "long", SL, TP1, TP2, bars, entry_index=0,
                                tie_break=TIE_BREAK_OBSERVABLE),
    lambda bars: forward_walk(_sig(), bars),
    lambda bars: forward_walk(_sig(), bars, tie_break="observable_only"),
], ids=["multi_prod", "multi_obs", "ref_obs", "fw_prod", "fw_obs"])
def test_entry_bar_is_never_walked(call):
    with pytest.raises(ValueError, match="lookahead"):
        call([ENTRY_BAR, QUIET(1)])
    # The caller's slice starts AFTER the entry bar, so its range cannot exit the trade.
    o = call([B(1, 100.4, 99.6, 100.0), B(2, 100.4, 99.6, 100.0)])
    assert getattr(o, "outcome") == "TIMEOUT"
