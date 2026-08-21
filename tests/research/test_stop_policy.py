"""Floor for SEM-019 causal dynamic stop policies.

Four things are protected here, in descending order of how badly a failure would mislead:

  CAUSALITY    a policy must not be able to use the current bar to set the stop that bar
               is tested against. That is the one bug that manufactures free money at
               scale, because the ambiguity recurs on every bar of every trade.
  INERTNESS    adding the policy machinery must not perturb the default path, and every
               declared policy must actually CHANGE something. An arm that is silently a
               no-op looks exactly like an arm that was measured and found ineffective.
  MONOTONICITY no policy may widen risk mid-trade, enforced by the kernel rather than
               trusted to each policy.
  ARITHMETIC   each policy places the stop where its own definition says.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.oracle.multi_tp_walk import multi_tp_walk  # noqa: E402
from research.oracle.stop_policy import (  # noqa: E402
    BreakevenAtR,
    NoModification,
    RatchetATR,
    RatchetR,
    StopPolicy,
    StopState,
    TimeDecay,
    default_policy_grid,
    tighten_only,
)


@dataclass
class B:
    high: float
    low: float
    close: float
    open: float = 0.0
    index: int = 0

    def __post_init__(self):
        if self.open == 0.0:
            self.open = self.close


def _bars(rows):
    return [B(high=h, low=l, close=c, open=o, index=i + 1)
            for i, (h, l, c, o) in enumerate(rows)]


def _random_paths(n_paths=300, n_bars=40, seed=5):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_paths):
        px = 100.0 + np.cumsum(rng.normal(0, 0.5, n_bars))
        hi = px + np.abs(rng.normal(0, 0.3, n_bars))
        lo = px - np.abs(rng.normal(0, 0.3, n_bars))
        op = np.r_[100.0, px[:-1]]
        out.append(_bars(list(zip(hi, lo, px, op))))
    return out


def _walk(bars, policy=None, **kw):
    kw.setdefault("tp1", 101.0)
    kw.setdefault("tp2", 102.0)
    return multi_tp_walk(100.0, "long", 99.0, kw.pop("tp1"), kw.pop("tp2"), bars,
                         stop_policy=policy, atr=1.0, **kw)


# ─────────────────────────────────────────────────────────────────────────────
# CAUSALITY
# ─────────────────────────────────────────────────────────────────────────────
def test_policy_cannot_see_the_current_bar():
    """A spike-then-collapse bar must NOT arm a ratchet that then stops on that same bar.

    Bar 1 runs to 101.5 (mfe 1.5R) and collapses to 99.4. A same-bar ratchet moves the
    stop to 101.5-1.0 = 100.5 and is hit on that same bar. Causally the stop is still at
    99.0 while bar 1 is being tested, so the trade survives into bar 2 -- where the
    ratchet, now legitimately armed from a COMPLETED bar, does bind.

    Note what is NOT asserted: a direction. See the non-dominance test below.
    """
    bars = _bars([(101.5, 99.4, 99.5, 100.0),      # spike and collapse
                  (99.6, 98.8, 99.0, 99.5)])
    causal = _walk(bars, RatchetR(1.0), trail_fraction=None)
    same_bar = _walk(bars, RatchetR(1.0), trail_fraction=None, same_bar_update=True)

    assert causal.duration_candles == 2, "causal arm exited on the spike bar — leak"
    assert same_bar.duration_candles == 1, "same-bar arm should exit on the spike bar"
    assert causal != same_bar, "the two arms must be distinguishable at all"


def test_same_bar_arm_is_a_band_not_an_optimism_bound():
    """CORRECTED 2026-08-21 (E-001). Pins the direction that was asserted backwards.

    Arming a stop from the current bar's own extreme makes it TIGHTER SOONER, so for an
    extreme-following policy the bar that arms the ratchet becomes the bar that exits on
    it. `breakeven_at_1r` is the sharpest case: it can never do better same-bar. A future
    change that made the same-bar arm uniformly better would be reintroducing the bug this
    test exists to pin, so the assertion is on the direction, not merely on a difference.
    """
    paths = _random_paths(600, seed=11)
    for policy, expect_worse in ((RatchetR(0.5), True), (BreakevenAtR(1.0), True)):
        causal = np.array([_walk(b, policy, trail_fraction=None).rr_gross for b in paths])
        same = np.array([_walk(b, policy, trail_fraction=None,
                               same_bar_update=True).rr_gross for b in paths])
        delta = same - causal
        assert np.any(delta != 0), f"{policy.name}: arms never diverge — test is vacuous"
        if expect_worse:
            assert delta.mean() < 0, (
                f"{policy.name}: same-bar arm is NOT better on average; "
                f"measured mean delta {delta.mean():+.5f}")
            assert (delta < 0).sum() > (delta > 0).sum()


def test_state_carries_only_completed_bars():
    """`bars_elapsed` must equal the number of bars already closed, not include this one."""
    seen = []

    class Recorder(StopPolicy):
        name = "recorder"

        def stop_for_bar(self, st, current_stop):
            seen.append((st.bars_elapsed, st.mfe))
            return current_stop

    bars = _bars([(100.5, 99.5, 100.2, 100.0), (101.0, 100.0, 100.8, 100.2)])
    _walk(bars, Recorder(), trail_fraction=None)
    assert seen[0] == (0, 0.0), "first bar must see zero elapsed bars and zero excursion"
    assert seen[1][0] == 1
    assert seen[1][1] == pytest.approx(0.5)     # bar 1's high only


# ─────────────────────────────────────────────────────────────────────────────
# INERTNESS / NON-VACUITY
# ─────────────────────────────────────────────────────────────────────────────
def test_no_modification_policy_is_identical_to_no_policy():
    """The plumbing must not perturb the default path."""
    for bars in _random_paths(150):
        a = _walk(bars, None)
        b = _walk(bars, NoModification())
        assert a == b, (a, b)


def test_trail_fraction_none_leaves_the_stop_where_it_started():
    """The no-modification control: TP1 books the partial but the stop does not move."""
    # Reaches TP1 (101), pulls back below the half-way trail (100.5), never hits 99.
    bars = _bars([(101.2, 100.0, 101.0, 100.0), (100.9, 99.6, 99.8, 101.0),
                  (100.2, 99.7, 100.0, 99.8)])
    trailed = _walk(bars, None, trail_fraction=0.5)
    fixed = _walk(bars, None, trail_fraction=None)
    assert trailed.outcome == "TP1_BE_STOP", trailed
    assert fixed.outcome == "TIMEOUT", fixed
    assert fixed.reached_tp1 and trailed.reached_tp1


@pytest.mark.parametrize("policy", default_policy_grid(), ids=lambda p: p.name)
def test_every_declared_policy_can_bind_on_a_reachable_geometry(policy):
    """A silently inert arm is indistinguishable from a measured no-effect.

    The geometry matters and is chosen deliberately: TP2 is placed far away (110) so that
    every trail distance in the grid CAN engage before the target ends the trade. On the
    default geometry the widest trails cannot bind at all — see the structural-inertness
    test below, which pins that as a fact rather than letting it masquerade as a result.
    """
    paths = _random_paths(400, seed=9)
    kw = dict(tp1=101.0, tp2=110.0, trail_fraction=None)
    base = [_walk(b, NoModification(), **kw) for b in paths]
    got = [_walk(b, policy, **kw) for b in paths]
    differing = sum(1 for x, y in zip(base, got) if x != y)
    if policy.name == "fixed":
        assert differing == 0
    else:
        assert differing > 0, f"policy {policy.name} never changed an outcome — inert arm"


def test_a_trail_wider_than_the_target_is_inert_by_construction():
    """Structurally unreachable, NOT measured-no-effect. The distinction is the point.

    A 3-ATR trail needs 3 ATR of favourable excursion to engage, but TP2 sits at 2 ATR and
    ends the trade first. Reporting such a cell as "no effect" would present an arm that
    could never have fired as evidence that stop policies do not help.
    """
    paths = _random_paths(400, seed=9)
    tight = dict(tp1=101.0, tp2=102.0, trail_fraction=None)   # TP2 at 2 ATR
    base = [_walk(b, NoModification(), **tight) for b in paths]
    wide = [_walk(b, RatchetATR(3.0), **tight) for b in paths]
    assert all(a == b for a, b in zip(base, wide)), "expected structural inertness"

    far = dict(tp1=101.0, tp2=110.0, trail_fraction=None)
    reachable = [_walk(b, RatchetATR(3.0), **far) for b in paths]
    base_far = [_walk(b, NoModification(), **far) for b in paths]
    assert any(a != b for a, b in zip(base_far, reachable)), (
        "the same policy must bind once the target is far enough away — otherwise the "
        "inertness above is a bug, not a structural fact")


def test_policy_requiring_atr_refuses_to_run_without_it():
    """Silently degrading to a no-op would report an unmeasured arm as measured."""
    bars = _random_paths(1)[0]
    with pytest.raises(ValueError, match="requires a positive atr"):
        multi_tp_walk(100.0, "long", 99.0, 101.0, 102.0, bars,
                      stop_policy=RatchetATR(2.0), atr=None)


# ─────────────────────────────────────────────────────────────────────────────
# MONOTONICITY
# ─────────────────────────────────────────────────────────────────────────────
def test_kernel_clamps_a_policy_that_tries_to_widen_risk():
    class Rogue(StopPolicy):
        name = "rogue"

        def stop_for_bar(self, st, current_stop):
            return st.entry - 99.0        # absurdly wide

    bars = _bars([(100.5, 98.5, 99.0, 100.0)])    # would stop at 99.0
    rogue = _walk(bars, Rogue(), trail_fraction=None)
    plain = _walk(bars, NoModification(), trail_fraction=None)
    assert rogue == plain, "a widening proposal was not clamped"


def test_tighten_only_respects_direction():
    assert tighten_only(99.0, 99.5, True) == 99.5
    assert tighten_only(99.0, 98.5, True) == 99.0
    assert tighten_only(101.0, 100.5, False) == 100.5
    assert tighten_only(101.0, 101.5, False) == 101.0
    assert tighten_only(99.0, float("nan"), True) == 99.0


def test_stops_are_monotone_across_a_whole_walk():
    levels = []

    class Spy(StopPolicy):
        name = "spy"
        inner = RatchetR(0.5)

        def stop_for_bar(self, st, current_stop):
            levels.append(current_stop)
            return self.inner.stop_for_bar(st, current_stop)

    rng = np.random.default_rng(2)
    px = 100.0 + np.cumsum(rng.normal(0.05, 0.4, 40))
    bars = _bars(list(zip(px + 0.3, px - 0.3, px, np.r_[100.0, px[:-1]])))
    _walk(bars, Spy(), trail_fraction=None)
    assert all(b >= a - 1e-12 for a, b in zip(levels, levels[1:])), levels


# ─────────────────────────────────────────────────────────────────────────────
# ARITHMETIC
# ─────────────────────────────────────────────────────────────────────────────
def _state(mfe, bars_elapsed=1, atr=1.0):
    return StopState(entry=100.0, is_long=True, initial_stop=99.0, tp1=101.0, tp2=102.0,
                     risk=1.0, atr=atr, reached_tp1=False, bars_elapsed=bars_elapsed,
                     mfe=mfe, mae=0.0)


def test_breakeven_triggers_at_its_threshold_and_lands_on_entry():
    p = BreakevenAtR(1.0)
    assert p.stop_for_bar(_state(0.99), 99.0) == 99.0        # below trigger: unchanged
    assert p.stop_for_bar(_state(1.00), 99.0) == 100.0       # at trigger: entry


def test_ratchet_r_engages_only_once_in_profit_by_its_distance():
    p = RatchetR(0.5)
    assert p.stop_for_bar(_state(0.4), 99.0) == 99.0
    # mfe 1.2R -> extreme 101.2, trail 0.5R behind -> 100.7
    assert p.stop_for_bar(_state(1.2), 99.0) == pytest.approx(100.7)


def test_ratchet_atr_uses_atr_not_risk():
    """The two ratchets must diverge when risk and ATR differ — the disp_bar case."""
    st = StopState(entry=100.0, is_long=True, initial_stop=99.5, tp1=101.0, tp2=102.0,
                   risk=0.5, atr=2.0, reached_tp1=False, bars_elapsed=3, mfe=5.0, mae=0.0)
    assert RatchetATR(1.0).stop_for_bar(st, 99.5) == pytest.approx(103.0)   # 105 - 1*2
    assert RatchetR(1.0).stop_for_bar(st, 99.5) == pytest.approx(104.5)     # 105 - 1*0.5


def test_time_decay_interpolates_from_the_original_stop_toward_entry():
    p = TimeDecay(start_bar=5, decay_bars=10)
    assert p.stop_for_bar(_state(0.0, bars_elapsed=5), 99.0) == 99.0        # not started
    assert p.stop_for_bar(_state(0.0, bars_elapsed=10), 99.0) == pytest.approx(99.5)
    assert p.stop_for_bar(_state(0.0, bars_elapsed=15), 99.0) == pytest.approx(100.0)
    # Never past entry: it is a risk-reduction rule, not a profit-taking rule.
    assert p.stop_for_bar(_state(0.0, bars_elapsed=99), 99.0) == pytest.approx(100.0)


def test_policies_reject_nonsense_parameters():
    for bad in (lambda: BreakevenAtR(0.0), lambda: RatchetR(-1.0),
                lambda: RatchetATR(0.0), lambda: TimeDecay(0, 0)):
        with pytest.raises(ValueError):
            bad()


def test_short_side_is_mirrored():
    st = StopState(entry=100.0, is_long=False, initial_stop=101.0, tp1=99.0, tp2=98.0,
                   risk=1.0, atr=1.0, reached_tp1=False, bars_elapsed=3, mfe=1.2, mae=0.0)
    assert RatchetR(0.5).stop_for_bar(st, 101.0) == pytest.approx(99.3)   # 98.8 + 0.5
    assert BreakevenAtR(1.0).stop_for_bar(st, 101.0) == pytest.approx(100.0)


# --------------------------------------------------------------------------------------
# SEM-017 / F-088 — the `partial_tp_breakeven_enabled` naming trap, pinned mechanically.
#
# The config key reads as "move the stop to breakeven". The code does NOT do that: it moves
# the stop to the HALF-WAY point between entry and TP1, which is already in profit. The key
# name and the behaviour disagree, and the code is what runs.
#
# Renaming the key is a config change (10 files under configs/production/ plus a strict read
# site) requiring its own authorisation, so the key is retained-as-named and documented at
# docs/reference/config-reference.md and docs/topics/execution-planning.md. These tests exist
# so the divergence cannot be resolved in the WRONG direction — i.e. so nobody "fixes" the
# code to match the key name — without a floor failing. They assert the LEVEL, and separately
# assert the DIRECTION (strictly beyond entry), because a direction-only assertion would still
# pass if the trail were moved to breakeven-plus-a-tick.
# --------------------------------------------------------------------------------------

def _trail_exit(direction: str, trail_fraction):
    """Hit TP1, then reverse hard enough to take out whatever stop the TP1 transition set.

    Returns the walk outcome. `runner_stop_pricing` is left at its default ledger blend, so
    `exit_price` is `f*tp1 + (1-f)*fill` — from which the fill (the stop level) is recoverable
    exactly, with `partial_fraction=0.5`.
    """
    if direction == "long":
        entry, sl, tp1, tp2 = 100.0, 99.0, 102.0, 104.0
        rows = [(102.5, 99.5, 102.2, 100.1),   # TP1 touched
                (102.3, 90.0, 90.5, 102.0)]    # deep reversal: takes out any stop >= 90
    else:
        entry, sl, tp1, tp2 = 100.0, 101.0, 98.0, 96.0
        rows = [(100.5, 97.5, 97.8, 99.9),
                (110.0, 97.7, 109.5, 98.0)]
    return multi_tp_walk(
        entry=entry, direction=direction, sl=sl, tp1=tp1, tp2=tp2,
        future=_bars(rows), partial_fraction=0.5, trail_fraction=trail_fraction,
        max_forward=10,
    )


def _recover_stop_level(out, tp1: float, f: float = 0.5) -> float:
    """Invert the TP1_BE_STOP ledger blend `px = f*tp1 + (1-f)*fill` for the stop fill."""
    return (out.exit_price - f * tp1) / (1.0 - f)


@pytest.mark.parametrize(
    "direction,entry,tp1",
    [("long", 100.0, 102.0), ("short", 100.0, 98.0)],
)
def test_production_trail_lands_half_way_to_tp1_not_at_breakeven(direction, entry, tp1):
    """SEM-017: the post-TP1 stop is entry + 0.5*(tp1 - entry), NOT entry.

    If someone changes the trail to actual breakeven to match `partial_tp_breakeven_enabled`,
    the recovered level becomes `entry` and this fails.
    """
    out = _trail_exit(direction, trail_fraction=0.5)
    assert out.reached_tp1 is True
    assert out.outcome == "TP1_BE_STOP", (
        f"expected the trail to be taken out after TP1, got {out.outcome!r}"
    )

    level = _recover_stop_level(out, tp1)
    half_way = entry + 0.5 * (tp1 - entry)
    assert level == pytest.approx(half_way), (
        f"post-TP1 stop is {level}, expected the HALF-WAY level {half_way}. "
        f"If this now equals entry ({entry}), the trail was changed to real breakeven to "
        f"match the config key name `partial_tp_breakeven_enabled` — that is a behaviour "
        f"change, not a rename. See SEM-017 / F-088."
    )
    assert level != pytest.approx(entry), "the production trail is NOT breakeven (SEM-017)"


@pytest.mark.parametrize("direction,entry,sign", [("long", 100.0, 1.0), ("short", 100.0, -1.0)])
def test_production_trail_is_strictly_in_profit_after_tp1(direction, entry, sign):
    """Direction guard: the trail sits strictly BEYOND entry in the trade's favour.

    Pinned separately from the level so a regression that keeps the sign but loses the
    magnitude (e.g. a breakeven-plus-epsilon trail) still fails the test above.
    """
    out = _trail_exit(direction, trail_fraction=0.5)
    tp1 = 102.0 if direction == "long" else 98.0
    level = _recover_stop_level(out, tp1)
    assert sign * (level - entry) > 0.0, (
        f"{direction}: post-TP1 stop {level} is not strictly in profit vs entry {entry}"
    )


def test_trail_fraction_none_is_the_honest_no_modification_control():
    """`trail_fraction=None` must leave the ORIGINAL stop in place after TP1.

    This is the benchmark F-087 measured production's half-way trail against; if it silently
    also trailed, the comparison would be vacuous — the F-085/F-083 silent-gap class.
    """
    out = _trail_exit("long", trail_fraction=None)
    assert out.reached_tp1 is True
    level = _recover_stop_level(out, tp1=102.0)
    assert level == pytest.approx(99.0), (
        f"with trail_fraction=None the stop must stay at the initial 99.0, got {level}"
    )
