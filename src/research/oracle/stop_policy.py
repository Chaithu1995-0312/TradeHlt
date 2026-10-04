"""stop_policy.py — SEM-019 causal dynamic stop policies for the two-target object.

WHY THIS EXISTS
---------------
Production has exactly ONE dynamic stop: on the TP1 transition it moves the stop to the
half-way point (SEM-017). Whether that helps has never been measured in either direction,
and the rest of the class -- ratchets, breakeven rules, time-based tightening -- does not
exist for the two-target object at all. Three unrelated ratchets live elsewhere in the
repository (`forward_walk` exit_model="trailing", `replay/timing_reconstructor`, and the
one `path/ambiguity_census` notes is absent under intrabar_fixed) and not one of them
drives a trade with a partial fill and a runner.

THE CAUSALITY RULE, AND WHY IT IS NOT NEGOTIABLE
------------------------------------------------
The stop applied to bar i may depend only on bars STRICTLY BEFORE i.

A ratchet cannot be faithfully simulated from OHLC. If the ratchet condition and the stop
touch fall on the same bar, the within-bar order is unknowable -- and unlike the SEM-017
same-bar tie-break, which can only fire on a bar spanning both a target and the stop, this
ambiguity recurs on EVERY bar of EVERY trade. So `StopState` carries only completed-bar
quantities and the kernel calls the policy BEFORE reading the current bar.

THE SAME-BAR ARM IS NOT AN OPTIMISM BOUND. CORRECTED 2026-08-21 (E-001) -- an earlier
version of this docstring asserted that same-bar updating "manufactures free money at
scale", which is measurably backwards for most of this grid. Arming a stop from the
current bar's own extreme makes it TIGHTER SOONER, so the spike that armed the ratchet
becomes the bar that exits on it. Measured on 4,000 synthetic paths: `ratchet_0.5r` is
worse on 920 paths and better on only 248 (mean -0.0976R), `breakeven_at_1r` is NEVER
better (0 vs 34), while `time_decay_6_12` IS mostly better (876 vs 66) because it does not
depend on the favourable extreme at all. The sign is policy-dependent and neither arm
dominates.

The correct reading is the SEM-017 one: a band, not a bound. Both arms are reported and
the gap between them is the size of an ambiguity OHLC cannot resolve at this timeframe.
(Synthetic Gaussian paths; re-measured on the real corpus in the sweep stage, because a
synthetic estimate of exactly this kind had to be superseded once already on SEM-017.)

MONOTONICITY IS ENFORCED, NOT TRUSTED
-------------------------------------
`tighten_only` clamps every policy's output so a stop can never move away from price. A
rule that widens risk mid-trade is not a stop policy, and a bug in one policy must not be
able to produce a result that looks like an edge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Every policy arm replaces the SEM-017 TP1 half-way trail rather than composing with it
#: (the driver passes `trail_fraction=None` for policy arms), so a comparison isolates the
#: stop-modification rule. `production` and `fixed` are the two reference points.
POLICY_FIXED = "fixed"
POLICY_PRODUCTION = "production"


@dataclass(frozen=True)
class StopState:
    """Everything a policy may see. By construction, nothing from the current bar.

    `mfe` and `mae` are the favourable/adverse excursions over COMPLETED bars only, and
    `bars_elapsed` counts those same completed bars. A policy that wants the current bar's
    high has no way to ask for it, which is the point.
    """

    entry: float
    is_long: bool
    initial_stop: float
    tp1: float
    tp2: float
    risk: float
    atr: float
    reached_tp1: bool
    bars_elapsed: int
    mfe: float          # price units, >= 0, completed bars only
    mae: float          # price units, <= 0, completed bars only

    @property
    def favourable_extreme(self) -> float:
        """Best price seen so far, in price units."""
        d = 1.0 if self.is_long else -1.0
        return self.entry + d * self.mfe

    @property
    def mfe_r(self) -> float:
        return self.mfe / self.risk if self.risk > 0 else 0.0


def tighten_only(current: float, proposed: float, is_long: bool) -> float:
    """Clamp a proposed stop so it can only move TOWARD price, never away.

    Enforced centrally rather than left to each policy: monotonicity is a property of the
    class, and a policy bug must not be able to widen risk mid-trade.
    """
    if proposed is None or not math.isfinite(proposed):
        return current
    return max(current, proposed) if is_long else min(current, proposed)


class StopPolicy:
    """Base class. `stop_for_bar` returns a PROPOSED stop; the kernel clamps it."""

    name = "base"
    #: Declared so the kernel can REFUSE to run an arm whose input it lacks, rather than
    #: letting the policy quietly return current_stop and look like a measured no-effect.
    requires_atr = False

    def stop_for_bar(self, st: StopState, current_stop: float) -> float:
        raise NotImplementedError

    def describe(self) -> dict:
        return {"name": self.name}


class NoModification(StopPolicy):
    """The control: the stop never moves. Measures whether the CLASS is worth anything.

    Paired with `trail_fraction=None` this is a genuinely fixed stop -- the two-target
    object without any stop modification at all -- which is the only honest benchmark for
    production's half-way trail.
    """

    name = POLICY_FIXED

    def stop_for_bar(self, st: StopState, current_stop: float) -> float:
        return current_stop


class BreakevenAtR(StopPolicy):
    """Move the stop to entry once the trade has been `trigger_r` in profit.

    This is what the config key `partial_tp_breakeven_enabled` names and what production
    does NOT do: the production trail lands half-way to TP1, not at entry (SEM-017).
    """

    def __init__(self, trigger_r: float, offset_r: float = 0.0):
        if trigger_r <= 0:
            raise ValueError(f"BreakevenAtR: trigger_r must be positive (got {trigger_r})")
        self.trigger_r = float(trigger_r)
        self.offset_r = float(offset_r)
        self.name = f"breakeven_at_{trigger_r:g}r"

    def stop_for_bar(self, st: StopState, current_stop: float) -> float:
        if st.mfe_r < self.trigger_r:
            return current_stop
        d = 1.0 if st.is_long else -1.0
        return st.entry + d * self.offset_r * st.risk

    def describe(self) -> dict:
        return {"name": self.name, "trigger_r": self.trigger_r, "offset_r": self.offset_r}


class RatchetR(StopPolicy):
    """Trail `distance_r` R behind the best price seen. Activates once in profit enough.

    Deliberately does NOT activate immediately: a trail placed `distance_r` behind entry
    before the trade has moved would simply be a tighter initial stop, which is a geometry
    change masquerading as a policy. It engages only once the favourable excursion exceeds
    the trail distance, so the trail is always at or above breakeven when it first binds.
    """

    def __init__(self, distance_r: float):
        if distance_r <= 0:
            raise ValueError(f"RatchetR: distance_r must be positive (got {distance_r})")
        self.distance_r = float(distance_r)
        self.name = f"ratchet_{distance_r:g}r"

    def stop_for_bar(self, st: StopState, current_stop: float) -> float:
        if st.mfe_r < self.distance_r:
            return current_stop
        d = 1.0 if st.is_long else -1.0
        return st.favourable_extreme - d * self.distance_r * st.risk

    def describe(self) -> dict:
        return {"name": self.name, "distance_r": self.distance_r}


class RatchetATR(StopPolicy):
    """Chandelier: trail `distance_atr` ATR behind the best price seen.

    The scale-invariant counterpart to RatchetR. It differs from RatchetR whenever the
    stop geometry is not itself ATR-anchored -- notably the bar-local `disp_bar` geometry,
    where risk and ATR diverge sharply.
    """

    requires_atr = True

    def __init__(self, distance_atr: float):
        if distance_atr <= 0:
            raise ValueError(f"RatchetATR: distance_atr must be positive (got {distance_atr})")
        self.distance_atr = float(distance_atr)
        self.name = f"ratchet_{distance_atr:g}atr"

    def stop_for_bar(self, st: StopState, current_stop: float) -> float:
        if st.atr <= 0:
            return current_stop
        dist = self.distance_atr * st.atr
        if st.mfe < dist:
            return current_stop
        d = 1.0 if st.is_long else -1.0
        return st.favourable_extreme - d * dist

    def describe(self) -> dict:
        return {"name": self.name, "distance_atr": self.distance_atr}


class TimeDecay(StopPolicy):
    """Tighten linearly toward entry over `decay_bars`, starting after `start_bar`.

    Targets the timing asymmetry recorded as F-024: losers resolve almost immediately
    while winners mature over roughly 90 minutes, which makes elapsed time informative
    about which of the two is in progress. A trade still open and not in profit after the
    grace period is, on that evidence, more likely to be a loser -- so the risk is reduced
    rather than held.

    Tightens toward entry only, never past it: this is a risk-reduction rule, not a
    profit-taking rule, and letting it walk into profit would confound it with a ratchet.
    """

    def __init__(self, start_bar: int, decay_bars: int):
        if start_bar < 0:
            raise ValueError(f"TimeDecay: start_bar must be >= 0 (got {start_bar})")
        if decay_bars <= 0:
            raise ValueError(f"TimeDecay: decay_bars must be positive (got {decay_bars})")
        self.start_bar = int(start_bar)
        self.decay_bars = int(decay_bars)
        self.name = f"time_decay_{start_bar}_{decay_bars}"

    def stop_for_bar(self, st: StopState, current_stop: float) -> float:
        elapsed = st.bars_elapsed - self.start_bar
        if elapsed <= 0:
            return current_stop
        frac = min(1.0, elapsed / self.decay_bars)
        # Interpolate from the ORIGINAL stop toward entry, not from the current stop:
        # compounding off an already-tightened stop would make the schedule depend on how
        # often the policy happened to be called.
        return st.initial_stop + frac * (st.entry - st.initial_stop)

    def describe(self) -> dict:
        return {"name": self.name, "start_bar": self.start_bar, "decay_bars": self.decay_bars}


#: The declared policy grid. Fixed up front so the sweep cannot be widened after seeing
#: results. `production` is absent here because it is not a StopPolicy -- it is the
#: kernel's own `trail_fraction=0.5` behaviour, and the driver runs it as its own arm.
def default_policy_grid() -> list[StopPolicy]:
    return [
        NoModification(),
        BreakevenAtR(0.5), BreakevenAtR(1.0), BreakevenAtR(1.5),
        RatchetR(0.5), RatchetR(1.0), RatchetR(1.5),
        RatchetATR(1.0), RatchetATR(2.0), RatchetATR(3.0),
        TimeDecay(6, 12), TimeDecay(18, 12),
    ]
