"""exit_sweep.py — geometry x dynamic-stop-policy sweep over the dense bar universe.

Every cell is the SAME entry population (every bar, one direction) under a different exit.
Entries never change, so a difference between cells is attributable to the exit and only
to the exit -- the fair-comparison discipline `analytics/sl_tp_comparator` states for its
two-method comparison, applied to a grid.

THREE THINGS THIS REFUSES TO DO SILENTLY
----------------------------------------
1. Report a structurally-unreachable cell as a measured no-effect. A trail wider than the
   remaining distance to the target can never bind, because the target ends the trade
   first. Such cells are labelled STRUCTURALLY_INERT, not "no effect" (SEM-019).
2. Benchmark against zero on a drifting instrument. Passive same-direction exposure is
   carried on every cell and is the binding control.
3. Treat overlapping labels as independent. Adjacent bars share almost their whole forward
   window, so every interval is a block bootstrap sized to the horizon.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from research.oracle.labeler import Bar
from research.oracle.multi_tp_walk import TIE_BREAK_PRODUCTION, multi_tp_walk
from research.oracle.stop_policy import POLICY_PRODUCTION, NoModification

#: Stop-placement variants. `disp_bar` is bar-local (the production construction); the
#: `fixed_*` family is a width sweep off close in ATR multiples.
#: Below this share of altered trades a cell is reported as NEARLY_INERT rather than as a
#: measured comparison: it is the baseline wearing a policy name.
NEARLY_INERT_FRACTION = 0.01

SL_DISP_BAR = "disp_bar"
FIXED_SL_MULTS = (0.5, 1.0, 2.0, 3.0)


def sl_variants() -> tuple[str, ...]:
    return (SL_DISP_BAR,) + tuple(f"fixed_{m:g}" for m in FIXED_SL_MULTS)


def _sl_for(variant: str, *, entry, bar_low, bar_high, atr, is_long, sl_atr_buffer):
    if variant == SL_DISP_BAR:
        return (bar_low - sl_atr_buffer * atr) if is_long else (bar_high + sl_atr_buffer * atr)
    mult = float(variant.split("_", 1)[1])
    return (entry - mult * atr) if is_long else (entry + mult * atr)


@dataclass(frozen=True)
class CellResult:
    key: str
    n: int
    mean_net: float
    mean_gross: float
    mean_cost: float
    win_rate: float
    passive_mean: float
    vs_passive: float
    outcome_mix: dict
    changed_vs_fixed: int
    status: str          # OK | STRUCTURALLY_INERT
    mean_duration: float
    stop_exit_rate: float


def build_bars(raw) -> list:
    return [Bar(high=float(h), low=float(lo), close=float(c), open=float(o), index=int(i))
            for h, lo, c, o, i in zip(raw["high"], raw["low"], raw["close"],
                                      raw["open"], raw["_pos"])]


def sweep_cell(
    *,
    bars: list,
    pos_list: list,
    close_list: list,
    atr_list: list,
    tp1_mult_list: list,
    ts_by_pos: list,
    direction: str,
    sl_variant: str,
    policy,
    horizon: int,
    tp2_mult: float,
    partial_fraction: float,
    sl_atr_buffer: float,
    cost_model,
    adverse_fill,
    nights_fn,
    trail_fraction,
    same_bar_update: bool = False,
    baseline_outcomes: "list | None" = None,
) -> tuple[CellResult, np.ndarray, np.ndarray, list]:
    """Walk every bar in one direction under one exit configuration.

    Returns (summary, y_net, positions, outcome_tuples). `outcome_tuples` is kept so a
    caller can compare against a baseline cell and count how many trades the policy
    actually changed -- the structural-inertness check.
    """
    is_long = direction == "long"
    n_raw = len(bars)
    y_net, y_gross, costs, keep, durations, outcomes = [], [], [], [], [], []
    stop_exits = 0

    for row_i, p in enumerate(pos_list):
        if p + horizon >= n_raw:
            continue
        entry = close_list[row_i]
        atr = atr_list[row_i]
        if not (atr > 0):
            continue
        bar_t = bars[p]
        sl = _sl_for(sl_variant, entry=entry, bar_low=bar_t.low, bar_high=bar_t.high,
                     atr=atr, is_long=is_long, sl_atr_buffer=sl_atr_buffer)
        if (is_long and sl >= entry) or ((not is_long) and sl <= entry):
            continue
        risk = abs(entry - sl)
        d = 1.0 if is_long else -1.0
        tp1 = entry + d * tp1_mult_list[row_i] * risk
        tp2 = entry + d * tp2_mult * risk

        o = multi_tp_walk(
            entry, direction, sl, tp1, tp2, bars[p + 1: p + 1 + horizon],
            partial_fraction=partial_fraction, tie_break=TIE_BREAK_PRODUCTION,
            trail_fraction=trail_fraction, max_forward=horizon,
            adverse_fill=adverse_fill, entry_index=p,
            stop_policy=policy, atr=atr, same_bar_update=same_bar_update,
        )
        nights = nights_fn(ts_by_pos[p], ts_by_pos[min(p + o.duration_candles, n_raw - 1)])
        c = cost_model.cost_r(entry, risk, exit_kind=o.exit_kind,
                              direction=direction, nights_held=nights)
        y_net.append(o.rr_gross - c)
        y_gross.append(o.rr_gross)
        costs.append(c)
        keep.append(p)
        durations.append(o.duration_candles)
        outcomes.append((o.outcome, round(o.rr_gross, 6)))
        if o.exit_kind == "SL_HIT":
            stop_exits += 1

    y_net = np.asarray(y_net, dtype=float)
    y_gross = np.asarray(y_gross, dtype=float)
    keep_arr = np.asarray(keep, dtype=int)

    changed = -1
    status = "OK"
    if baseline_outcomes is not None:
        changed = sum(1 for a, b in zip(baseline_outcomes, outcomes) if a != b)
        # Binary reachable/unreachable is not enough. A trail that alters 8 trades out of
        # 1,900 has not been "measured and found neutral" -- it is the baseline with noise,
        # and quoting its expectancy as a policy result would be reporting the control
        # twice under two names.
        if changed == 0:
            status = "STRUCTURALLY_INERT"
        elif outcomes and changed / len(outcomes) < NEARLY_INERT_FRACTION:
            status = "NEARLY_INERT"

    from collections import Counter
    mix = {k: int(v) for k, v in Counter(o[0] for o in outcomes).items()}
    res = CellResult(
        key="", n=int(y_net.size),
        mean_net=float(y_net.mean()) if y_net.size else float("nan"),
        mean_gross=float(y_gross.mean()) if y_gross.size else float("nan"),
        mean_cost=float(np.mean(costs)) if costs else float("nan"),
        win_rate=float((y_net > 0).mean()) if y_net.size else float("nan"),
        passive_mean=float("nan"), vs_passive=float("nan"),
        outcome_mix=mix, changed_vs_fixed=changed, status=status,
        mean_duration=float(np.mean(durations)) if durations else float("nan"),
        stop_exit_rate=(stop_exits / len(outcomes)) if outcomes else float("nan"),
    )
    return res, y_net, keep_arr, outcomes


def policy_for(name: str, grid: dict):
    """Resolve an arm name to (policy, trail_fraction).

    `production` is not a StopPolicy -- it is the kernel's own TP1 half-way trail, so it
    is expressed as trail_fraction=0.5 with no policy. Every other arm sets
    trail_fraction=None so the comparison isolates the stop-modification rule from the
    partial exit, which all arms keep.
    """
    if name == POLICY_PRODUCTION:
        return None, 0.5
    if name == NoModification.name:
        return NoModification(), None
    return grid[name], None
