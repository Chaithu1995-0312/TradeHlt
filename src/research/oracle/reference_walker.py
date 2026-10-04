"""reference_walker.py — deliberately naive twin of `multi_tp_walk`, for triangulation.

WHY A SECOND IMPLEMENTATION
---------------------------
The usual correctness proof for a new exit kernel is parity against
`research.measurement.forward_walk`. That proof is only as good as `forward_walk`, and
this program treats existing measurement workflows as unverified rather than as ground
truth. Parity against a suspect kernel proves consistency, not correctness.

So this module re-derives the same geometry from a DIFFERENT mental model, on purpose:

  * `multi_tp_walk` tracks one position with a status flag and prices the exit as a
    weighted BLEND of two levels (the `backtest_v2` formulation).
  * this walker tracks TWO INDEPENDENT LEGS — a partial leg targeting TP1 and a runner
    leg targeting TP2 — walks each to its own exit, and SUMS their contributions.

The two agree algebraically, but nothing about the second follows from the first. Two
implementations written from one mental model can share a bug; these two cannot share an
arithmetic one, because neither computes the other's quantity.

It is written for obviousness, not speed: explicit state strings, no early-exit
cleverness, one concern per block. Do not optimise it. Its only job is to disagree loudly
when the fast kernel is wrong.
"""

from __future__ import annotations

from typing import Sequence

from research.oracle.multi_tp_walk import (
    OUT_STOPPED,
    OUT_TIMEOUT,
    OUT_TP1_BE_STOP,
    OUT_TP1_TP2,
    RUNNER_ENGINE_PNL,
    RUNNER_LEDGER_BLEND,
    EXIT_KIND_AMBIGUOUS,
    RR_BASIS_ACTUAL,
    RR_BASIS_COMPAT_MIN_BRANCH,
    TIE_BREAK_OBSERVABLE,
    TIE_BREAK_OPTIMISTIC,
    TIE_BREAK_PRODUCTION,
    TIMEOUT_MARK_TO_CLOSE,
    OracleOutcome,
    _stop_fill_price,
)


def _reference_observable(entry, direction, sl, tp1, tp2, future, *, partial_fraction,
                          trail_fraction, runner_stop_pricing, timeout_pricing, max_forward,
                          adverse_fill, entry_index) -> OracleOutcome:
    """Naive observable_only twin: enumerate every legal path, price legs independently.

    Deliberately NOT sharing `_legal_branches` with the fast kernel: the fork rules are
    re-stated inline from the price geometry so a mistake in one cannot hide in the other.
    """
    is_long = direction == "long"
    d = 1.0 if is_long else -1.0
    risk = abs(entry - sl)
    f = float(partial_fraction)
    tp1_active = f > 0.0
    trail_level = float(sl) if trail_fraction is None else entry + trail_fraction * (tp1 - entry)
    bars = list(future)[:max_forward]

    def touches(bar, level_stop):
        hi, lo = float(bar.high), float(bar.low)
        if is_long:
            return lo <= level_stop, hi >= tp1, hi >= tp2
        return hi >= level_stop, lo <= tp1, lo <= tp2

    paths = []  # (event, bar_i, reached_tp1, stop_level)

    def explore(i, state, stop_level):
        # state: "OPEN" | "TP1". Returns nothing; appends terminal paths.
        for j in range(i, len(bars)):
            bar = bars[j]
            if entry_index is not None:
                bidx = getattr(bar, "index", None)
                if bidx is None or int(bidx) <= int(entry_index):   # missing .index fails closed
                    raise ValueError(
                        f"reference_walk lookahead: bar index {bidx} <= entry_index {entry_index}"
                    )
            s, t1, t2 = touches(bar, stop_level)
            # Legal continuations of this bar.
            options = []
            if state == "OPEN":
                if s:
                    options.append("STOP")
                if t2:
                    options.append("TP2")        # crossing TP2 means TP1 was crossed first
                elif tp1_active and t1:
                    options.append("TP1")
            else:
                if s:
                    options.append("STOP")
                if t2:
                    options.append("TP2")
            if not options:
                continue
            for opt in options:
                if opt == "STOP":
                    paths.append(("STOP", j, state == "TP1", stop_level))
                elif opt == "TP2":
                    paths.append(("TP2", j, tp1_active, stop_level))
                else:  # TP1 transition: the armed trail is not tested on this bar
                    explore(j + 1, "TP1", trail_level if trail_fraction is not None else stop_level)
            return
        paths.append(("TIMEOUT", len(bars) - 1, state == "TP1", stop_level))

    explore(0, "OPEN", float(sl))

    priced = []
    for event, bi, reached, stop_level in paths:
        mfe = mae = 0.0
        for k in range(bi + 1):
            hi, lo = float(bars[k].high), float(bars[k].low)
            mfe = max(mfe, (hi - entry) if is_long else (entry - lo))
            mae = min(mae, (lo - entry) if is_long else (entry - hi))
        gapped = False
        if event == "STOP":
            fill, gapped = _stop_fill_price(bars[bi], stop_level, is_long, adverse_fill)
            if reached:
                p_leg = tp1
                r_leg = entry if runner_stop_pricing == RUNNER_ENGINE_PNL else fill
                outcome, kind = OUT_TP1_BE_STOP, "SL_HIT"
            else:
                p_leg = r_leg = fill
                outcome, kind = OUT_STOPPED, "SL_HIT"
        elif event == "TP2":
            p_leg, r_leg = (tp1, tp2) if tp1_active else (tp2, tp2)
            outcome, kind = OUT_TP1_TP2, "TP_HIT"
        else:
            outcome, kind = OUT_TIMEOUT, "TIMEOUT"
            if not bars:
                p_leg = r_leg = entry
            else:
                lc = float(bars[-1].close)
                if reached:
                    p_leg = tp1
                    r_leg = lc if timeout_pricing == TIMEOUT_MARK_TO_CLOSE else stop_level
                else:
                    p_leg = r_leg = lc
        rr = (f * d * (p_leg - entry) + (1.0 - f) * d * (r_leg - entry)) / risk
        priced.append(dict(
            outcome=outcome, kind=kind, rr=round(float(rr), 6),
            px=round(float(f * p_leg + (1.0 - f) * r_leg), 8), dur=bi + 1 if bars else 0,
            tp1=reached, mfe=mfe, mae=mae, gapped=gapped,
        ))

    distinct = {(p["outcome"], p["rr"]) for p in priced}
    compat = min(priced, key=lambda p: p["rr"])
    amb = len(distinct) > 1
    kinds = {p["kind"] for p in priced}
    return OracleOutcome(
        outcome=compat["outcome"], rr_gross=compat["rr"], exit_price=compat["px"],
        duration_candles=compat["dur"], reached_tp1=compat["tp1"],
        bars_to_tp1=None,  # not independently derived by this twin; callers must not compare
        mfe=round(float(compat["mfe"]), 8), mae=round(float(compat["mae"]), 8),
        risk_distance=float(risk),
        exit_kind=compat["kind"] if len(kinds) == 1 else EXIT_KIND_AMBIGUOUS,
        gapped_stop=compat["gapped"], ambiguous=amb,
        rr_band=(min(p["rr"] for p in priced), max(p["rr"] for p in priced)) if amb else None,
        n_branches=len(distinct),
        rr_gross_basis=RR_BASIS_COMPAT_MIN_BRANCH if amb else RR_BASIS_ACTUAL,
    )


def reference_walk(
    entry: float,
    direction: str,
    sl: float,
    tp1: float,
    tp2: float,
    future: Sequence,
    *,
    partial_fraction: float = 0.5,
    tie_break: str = TIE_BREAK_PRODUCTION,
    trail_fraction: float = 0.5,
    runner_stop_pricing: str = RUNNER_LEDGER_BLEND,
    timeout_pricing: str = TIMEOUT_MARK_TO_CLOSE,
    max_forward: int = 40,
    adverse_fill=None,
    entry_index: int,
) -> OracleOutcome:
    """Same contract as `multi_tp_walk`, computed by summing two independent legs."""
    if entry_index is None:
        raise ValueError("reference_walk: entry_index is required (entry-bar exclusion guard)")
    if tie_break == TIE_BREAK_OBSERVABLE:
        return _reference_observable(
            entry, direction, sl, tp1, tp2, future, partial_fraction=partial_fraction,
            trail_fraction=trail_fraction, runner_stop_pricing=runner_stop_pricing,
            timeout_pricing=timeout_pricing, max_forward=max_forward,
            adverse_fill=adverse_fill, entry_index=entry_index,
        )
    is_long = direction == "long"
    d = 1.0 if is_long else -1.0
    risk = abs(entry - sl)
    f = float(partial_fraction)
    trail_level = entry + trail_fraction * (tp1 - entry)
    # See multi_tp_walk: a zero partial makes TP1 a non-event, collapsing the ladder to a
    # single fixed-stop walk to TP2.
    tp1_active = f > 0.0

    bars = list(future)[:max_forward]

    # ---- Pass 1: walk the bars and record WHAT HAPPENED, deciding nothing about price.
    # A plain event log. Keeping discovery separate from pricing is the whole point of
    # this file: if the two implementations disagree, the log says which bar diverged.
    state = "OPEN"
    stop_level = float(sl)
    tp1_bar = None
    exit_bar = None
    exit_event = None          # "STOP" | "TP2"
    n_walked = 0

    for i in range(len(bars)):
        bar = bars[i]
        if entry_index is not None:
            bidx = getattr(bar, "index", None)
            if bidx is None or int(bidx) <= int(entry_index):   # missing .index fails closed
                raise ValueError(
                    f"reference_walk lookahead: bar index {bidx} <= entry_index {entry_index}"
                )
        n_walked = i + 1
        high = float(bar.high)
        low = float(bar.low)

        if is_long:
            stop_touched = low <= stop_level
            tp1_touched = high >= tp1
            tp2_touched = high >= tp2
        else:
            stop_touched = high >= stop_level
            tp1_touched = low <= tp1
            tp2_touched = low <= tp2

        if tie_break == TIE_BREAK_PRODUCTION:
            # The engine resolves the bar to one trigger price, stop first, in both states.
            if state == "OPEN":
                if stop_touched:
                    exit_event, exit_bar = "STOP", i
                    break
                if tp1_active and tp1_touched:
                    state = "TP1"
                    tp1_bar = i
                    stop_level = trail_level
                    continue
                if (not tp1_active) and tp2_touched:
                    exit_event, exit_bar = "TP2", i
                    break
                continue
            if state == "TP1":
                if stop_touched:
                    exit_event, exit_bar = "STOP", i
                    break
                if tp2_touched:
                    exit_event, exit_bar = "TP2", i
                    break
                continue

        elif tie_break == TIE_BREAK_OPTIMISTIC:
            # sl_tp_comparator.simulate_exit ordering: TP2 beats SL beats TP1.
            if state == "OPEN":
                if tp2_touched:
                    if tp1_active:
                        state = "TP1"
                        tp1_bar = i
                    exit_event, exit_bar = "TP2", i
                    break
                if stop_touched:
                    exit_event, exit_bar = "STOP", i
                    break
                if tp1_active and tp1_touched:
                    state = "TP1"
                    tp1_bar = i
                    stop_level = trail_level
                    continue
                continue
            if state == "TP1":
                if tp2_touched:
                    exit_event, exit_bar = "TP2", i
                    break
                if stop_touched:
                    exit_event, exit_bar = "STOP", i
                    break
                continue
        else:
            raise ValueError(f"reference_walk: bad tie_break {tie_break!r}")

    # ---- Pass 2: excursions, measured over exactly the bars that were walked.
    mfe = 0.0
    mae = 0.0
    for i in range(n_walked):
        high = float(bars[i].high)
        low = float(bars[i].low)
        favourable = (high - entry) if is_long else (entry - low)
        adverse = (low - entry) if is_long else (entry - high)
        if favourable > mfe:
            mfe = favourable
        if adverse < mae:
            mae = adverse

    # ---- Pass 3: price each leg independently, then SUM. No blend formula anywhere.
    reached_tp1 = tp1_bar is not None
    gapped = False

    if exit_event == "STOP":
        fill, gapped = _stop_fill_price(bars[exit_bar], stop_level, is_long, adverse_fill)
        if reached_tp1:
            partial_leg_exit = tp1
            if runner_stop_pricing == RUNNER_ENGINE_PNL:
                runner_leg_exit = entry     # engine credits the runner nothing
            else:
                runner_leg_exit = fill
            outcome, exit_kind = OUT_TP1_BE_STOP, "SL_HIT"
        else:
            partial_leg_exit = fill
            runner_leg_exit = fill
            outcome, exit_kind = OUT_STOPPED, "SL_HIT"

    elif exit_event == "TP2":
        partial_leg_exit = tp1
        runner_leg_exit = tp2
        outcome, exit_kind = OUT_TP1_TP2, "TP_HIT"

    else:
        outcome, exit_kind = OUT_TIMEOUT, "TIMEOUT"
        if not bars:
            partial_leg_exit = entry
            runner_leg_exit = entry
        else:
            last_close = float(bars[-1].close)
            if reached_tp1:
                partial_leg_exit = tp1
                runner_leg_exit = (
                    last_close if timeout_pricing == TIMEOUT_MARK_TO_CLOSE else stop_level
                )
            else:
                partial_leg_exit = last_close
                runner_leg_exit = last_close

    partial_contribution = f * d * (partial_leg_exit - entry)
    runner_contribution = (1.0 - f) * d * (runner_leg_exit - entry)
    rr = (partial_contribution + runner_contribution) / risk if risk > 0 else 0.0

    # Reported exit price is the position-weighted average of the two legs — the same
    # number the blend produces, arrived at from the opposite direction.
    exit_price = f * partial_leg_exit + (1.0 - f) * runner_leg_exit

    return OracleOutcome(
        outcome=outcome,
        rr_gross=round(float(rr), 6),
        exit_price=round(float(exit_price), 8),
        duration_candles=n_walked,
        reached_tp1=reached_tp1,
        bars_to_tp1=None if tp1_bar is None else tp1_bar + 1,
        mfe=round(float(mfe), 8),
        mae=round(float(mae), 8),
        risk_distance=float(risk),
        exit_kind=exit_kind,
        gapped_stop=gapped,
    )
