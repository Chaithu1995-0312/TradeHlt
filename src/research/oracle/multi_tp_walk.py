"""multi_tp_walk.py — SEM-017 two-target partial-exit forward walk.

WHY THIS EXISTS
---------------
`research.measurement.forward_walk` models ONE take-profit, no partial fill and no
trail. Production does not: `crt_engine_v2.ExecutionEngine.update_trade` realises a
configured fraction at TP1, trails the stop to the half-way point, and runs the
remainder to TP2. Every outcome-bearing research result in this repository has
therefore been measured on a *different exit object* than the one production trades.

This kernel reproduces the production object as a pure function over forward bars so a
measurement can declare which object it used. It is ADDITIVE: `forward_walk` is not
touched, and under a degenerate configuration this kernel reduces to it (see
`tests/research/test_multi_tp_walk_parity.py`).

SAME-BAR PRECEDENCE — READ THIS BEFORE CHANGING ANYTHING
--------------------------------------------------------
`update_trade` declares a `TP2 > SL > TP1` branch order, but it is fed a single scalar
trigger price by `crt_engine_v2._intrabar_trigger_price`, which tests `sl_touch` BEFORE
any target ("conservative: SL before TP1 on a spanning bar"). The EFFECTIVE precedence on
the backtest path is therefore **SL-first**, and the declared branch order almost never
binds. Reading the branch-order comment as the effective rule is a mistake this docstring
exists to prevent.

The optimistic target-first precedence over raw high/low exists only in
`analytics/sl_tp_comparator.simulate_exit`, an analytics sidecar the backtest never calls.
Both are selectable here as `tie_break="production"` / `"optimistic"`; they can only
disagree on a bar whose range spans both a target and the stop.

TWO DECLARED BASIS AMBIGUITIES
------------------------------
1. `runner_stop_pricing` — on a runner stopped at the trail, the engine's internal
   `trade.pnl` credits the runner nothing (partial only) while the `backtest_v2` ledger
   prices it at the blended trail level. At f=0.5 / tp1_mult=1.0 that is +0.5R vs +0.75R.
   Every recorded backtest R came from the ledger blend, so `"ledger_blend"` is the
   default; `"engine_pnl"` is exposed so the gap can be measured rather than assumed.
2. `timeout_pricing` — `backtest_v2`'s `BACKTEST_END` marks an unblended `last.close`,
   but that is a run-termination artifact, not a horizon policy. A finite research
   horizon needs one, so the default is position-weighted mark-to-close: the TP1 partial
   is already realised and only the runner marks to the last close.

NO LOOKAHEAD
------------
`future` must contain only bars strictly after the entry bar. When `entry_index` is given
every bar's `.index` is asserted greater than it, mirroring `forward_walk`'s guard.
"""

from __future__ import annotations

import dataclasses
from typing import Sequence

from research.oracle.stop_policy import StopState, tighten_only

TIE_BREAK_PRODUCTION = "production"
TIE_BREAK_OPTIMISTIC = "optimistic"
_TIE_BREAKS = (TIE_BREAK_PRODUCTION, TIE_BREAK_OPTIMISTIC)

RUNNER_LEDGER_BLEND = "ledger_blend"
RUNNER_ENGINE_PNL = "engine_pnl"
_RUNNER_PRICING = (RUNNER_LEDGER_BLEND, RUNNER_ENGINE_PNL)

TIMEOUT_MARK_TO_CLOSE = "mark_to_close"
TIMEOUT_TRAIL = "trail"
_TIMEOUT_PRICING = (TIMEOUT_MARK_TO_CLOSE, TIMEOUT_TRAIL)

# Exit reasons mirror the `backtest_v2` vocabulary so a label is greppable against a ledger.
OUT_STOPPED = "STOPPED"          # clean stop from OPEN, never reached TP1
OUT_TP1_BE_STOP = "TP1_BE_STOP"  # reached TP1, runner stopped at the trail
OUT_TP1_TP2 = "TP1_TP2"          # reached TP1, runner reached TP2
OUT_TIMEOUT = "TIMEOUT"          # horizon expired

# Cost-model exit kinds. `ComponentCostModel.cost_price` charges stop slippage only on
# these, so a TP1_BE_STOP must be declared a stop exit even though it is profitable.
_STOP_EXITS = (OUT_STOPPED, OUT_TP1_BE_STOP)


@dataclasses.dataclass(frozen=True)
class OracleOutcome:
    """Forward-measured result of one hypothetical two-target trade."""

    outcome: str                 # STOPPED | TP1_BE_STOP | TP1_TP2 | TIMEOUT
    rr_gross: float              # realised R before costs, position-weighted
    exit_price: float            # blended exit price (telemetry; rr is authority)
    duration_candles: int
    reached_tp1: bool
    bars_to_tp1: "int | None"
    mfe: float                   # max favorable excursion, price units (>= 0)
    mae: float                   # max adverse excursion, price units (<= 0)
    risk_distance: float
    exit_kind: str               # SL_HIT | TP_HIT | TIMEOUT — for the cost model
    gapped_stop: bool            # the triggering bar opened beyond the stop (SEM-016)


def _stop_fill_price(bar, stop: float, is_long: bool, adverse) -> "tuple[float, bool]":
    """Price at which a triggered stop actually fills, and whether it gapped.

    Returns `stop` unchanged when `adverse` is None — the historical behaviour, and the
    reason the default path matches `forward_walk`'s perfect-fill convention exactly.
    Deliberately asymmetric: take-profit is never adjusted, because a resting limit order
    does not fill better than its level.
    """
    if adverse is None:
        return stop, False
    if getattr(adverse, "model_gaps", False):
        open_ = getattr(bar, "open", None)
        if open_ is None:
            # Fail closed. Silently skipping gap modelling reintroduces exactly the
            # optimism this parameter exists to remove.
            raise ValueError(
                "multi_tp_walk(adverse_fill=...) with model_gaps=True requires bars "
                "carrying `.open`; this bar has none. Pass model_gaps=False to price "
                "slippage only."
            )
        open_ = float(open_)
        if is_long and open_ <= stop:
            return open_, True
        if (not is_long) and open_ >= stop:
            return open_, True
    slip = float(getattr(adverse, "stop_slippage", 0.0))
    return (stop - slip if is_long else stop + slip), False


def multi_tp_walk(
    entry: float,
    direction: str,
    sl: float,
    tp1: float,
    tp2: float,
    future: Sequence,
    *,
    partial_fraction: float = 0.5,
    tie_break: str = TIE_BREAK_PRODUCTION,
    trail_fraction: "float | None" = 0.5,
    runner_stop_pricing: str = RUNNER_LEDGER_BLEND,
    timeout_pricing: str = TIMEOUT_MARK_TO_CLOSE,
    max_forward: int = 40,
    adverse_fill=None,
    entry_index: "int | None" = None,
    stop_policy=None,
    atr: "float | None" = None,
    same_bar_update: bool = False,
) -> OracleOutcome:
    """Walk `future` under the SEM-017 two-target partial-exit geometry.

    Args:
        entry: fill price of the hypothetical entry (production uses the retest close).
        direction: "long" | "short".
        sl: initial stop level, already placed by the caller's chosen geometry.
        tp1, tp2: the two target levels, R-anchored off `abs(entry - sl)` by the caller.
        future: bars strictly after the entry bar; each needs .high/.low/.close
            (and .open when `adverse_fill.model_gaps`).
        partial_fraction: fraction realised at TP1 (`execution_planner.partial_tp_fraction`).
        tie_break: "production" (SL-first, the backtest path) or "optimistic"
            (TP2 > SL > TP1 over raw high/low, the `sl_tp_comparator` convention).
        trail_fraction: where the stop moves after TP1, as a fraction of the entry->TP1
            distance. Production uses 0.5 — a HALF-WAY trail, not breakeven, despite the
            config key being named `partial_tp_breakeven_enabled`. Reproduced as written.
        runner_stop_pricing: see module docstring. "ledger_blend" is the backtest basis.
        timeout_pricing: how an unresolved position is marked at the horizon.
        max_forward: horizon in bars.
        adverse_fill: SEM-016 `AdverseFill`-shaped object, or None for a perfect stop fill.
        entry_index: when given, every bar's `.index` must exceed it (no-lookahead guard).
        stop_policy: SEM-019 causal stop policy, or None for no modification beyond the
            TP1 trail. Consulted BEFORE the current bar is read, so the stop applied to
            bar i depends only on bars strictly before i. Its output is clamped by
            `tighten_only`, so a policy can never widen risk mid-trade.
        atr: price-unit ATR at entry. REQUIRED when the policy declares `requires_atr`;
            a missing value raises rather than silently making that arm inert.
        same_bar_update: when True the policy also sees the CURRENT bar's extremes -- the
            second arm of the intrabar path ambiguity, never the primary basis, because on
            a real feed the ratchet and the stop touch could occur in either order and OHLC
            cannot say which. It is NOT an optimism bound: arming a stop from the current
            bar's own extreme makes it tighter sooner, which for a ratchet turns the very
            spike that armed it into the exit. Measured direction is policy-dependent
            (see stop_policy.py). Report both arms as a band.

    `trail_fraction=None` disables the TP1 stop move entirely, giving the two-target object
    with NO stop modification -- the control that makes the production trail's value
    measurable rather than assumed.
    """
    if direction not in ("long", "short"):
        raise ValueError(f"multi_tp_walk: bad direction {direction!r}")
    if tie_break not in _TIE_BREAKS:
        raise ValueError(f"multi_tp_walk: bad tie_break {tie_break!r}, expected one of {_TIE_BREAKS}")
    if runner_stop_pricing not in _RUNNER_PRICING:
        raise ValueError(f"multi_tp_walk: bad runner_stop_pricing {runner_stop_pricing!r}")
    if timeout_pricing not in _TIMEOUT_PRICING:
        raise ValueError(f"multi_tp_walk: bad timeout_pricing {timeout_pricing!r}")
    if not (0.0 <= partial_fraction <= 1.0):
        raise ValueError(f"multi_tp_walk: partial_fraction must be in [0,1], got {partial_fraction}")

    is_long = direction == "long"
    risk = abs(entry - sl)
    if risk <= 0:
        raise ValueError(f"multi_tp_walk: non-positive risk_distance ({risk})")
    # The engine's inverted-SL guard, reproduced: a stop on the wrong side of entry is
    # not a trade, it is a construction error, and must not be silently walked.
    if is_long and sl >= entry:
        raise ValueError(f"multi_tp_walk: long stop {sl} >= entry {entry}")
    if (not is_long) and sl <= entry:
        raise ValueError(f"multi_tp_walk: short stop {sl} <= entry {entry}")

    if stop_policy is not None and getattr(stop_policy, "requires_atr", False):
        if atr is None or not (float(atr) > 0):
            # Fail loudly. A policy silently reduced to a no-op is indistinguishable from
            # one that was measured and found inert -- the exact failure class this
            # repository has hit repeatedly (declared-but-unreached surfaces).
            raise ValueError(
                f"multi_tp_walk: stop_policy {getattr(stop_policy, 'name', stop_policy)!r} "
                f"requires a positive atr, got {atr!r}"
            )

    d = 1.0 if is_long else -1.0
    f = float(partial_fraction)
    sl_cur = float(sl)
    # None => the stop does NOT move on the TP1 transition (the no-modification control).
    trail_level = None if trail_fraction is None else entry + trail_fraction * (tp1 - entry)
    # partial_fraction == 0 means nothing is realised at TP1, so TP1 is not an event:
    # no partial, no transition, and critically no trail. The ladder collapses to a
    # single fixed-stop walk to TP2 — which is what makes the forward_walk reduction
    # test expressible at all.
    tp1_active = f > 0.0

    status_tp1 = False
    bars_to_tp1: "int | None" = None
    mfe = 0.0
    mae = 0.0
    duration = 0
    gapped = False

    bars = list(future)[:max_forward]

    def _finish(outcome: str, exit_price: float, rr: float, exit_kind: str) -> OracleOutcome:
        return OracleOutcome(
            outcome=outcome,
            rr_gross=round(float(rr), 6),
            exit_price=round(float(exit_price), 8),
            duration_candles=duration,
            reached_tp1=status_tp1,
            bars_to_tp1=bars_to_tp1,
            mfe=round(float(mfe), 8),
            mae=round(float(mae), 8),
            risk_distance=float(risk),
            exit_kind=exit_kind,
            gapped_stop=gapped,
        )

    def _stop_out(bar) -> OracleOutcome:
        """Resolve a triggered stop, from either OPEN or TP1 status."""
        nonlocal gapped
        fill, gp = _stop_fill_price(bar, sl_cur, is_long, adverse_fill)
        gapped = gp
        if not status_tp1:
            rr = d * (fill - entry) / risk
            return _finish(OUT_STOPPED, fill, rr, "SL_HIT")
        # Runner stopped at the trail. The two bases disagree here by design.
        if runner_stop_pricing == RUNNER_ENGINE_PNL:
            rr = f * d * (tp1 - entry) / risk          # runner credited nothing
            px = f * tp1 + (1.0 - f) * entry
        else:
            px = f * tp1 + (1.0 - f) * fill            # backtest_v2 TP1_BE_STOP blend
            rr = d * (px - entry) / risk
        return _finish(OUT_TP1_BE_STOP, px, rr, "SL_HIT")

    for i, bar in enumerate(bars):
        if entry_index is not None:
            bidx = getattr(bar, "index", None)
            if bidx is not None and int(bidx) <= int(entry_index):
                raise ValueError(
                    f"multi_tp_walk lookahead: bar index {bidx} <= entry_index {entry_index}"
                )
        hi = float(bar.high)
        lo = float(bar.low)
        duration = i + 1

        # SEM-019 CAUSALITY: the stop applied to THIS bar is decided from completed bars
        # only. `mfe`/`mae` still hold bars 0..i-1 at this point, and `i` is the count of
        # completed bars -- the current bar's extremes are read below, after this call.
        if stop_policy is not None and not same_bar_update:
            sl_cur = _apply_policy(stop_policy, sl_cur, entry, is_long, sl, tp1, tp2,
                                   risk, atr, status_tp1, i, mfe, mae)

        fav = (hi - entry) if is_long else (entry - lo)
        adv = (lo - entry) if is_long else (entry - hi)
        if fav > mfe:
            mfe = fav
        if adv < mae:
            mae = adv

        # The second ambiguity arm: the policy sees this bar's own extreme before the stop
        # is tested against it. Not reachable by default, and NOT an upper bound -- it is
        # usually WORSE for extreme-following policies. Reported beside the causal arm so
        # the size of the unresolvable intrabar ambiguity is visible.
        if stop_policy is not None and same_bar_update:
            sl_cur = _apply_policy(stop_policy, sl_cur, entry, is_long, sl, tp1, tp2,
                                   risk, atr, status_tp1, i + 1, mfe, mae)

        sl_touch = (lo <= sl_cur) if is_long else (hi >= sl_cur)
        tp1_touch = (hi >= tp1) if is_long else (lo <= tp1)
        tp2_touch = (hi >= tp2) if is_long else (lo <= tp2)

        if tie_break == TIE_BREAK_PRODUCTION:
            # crt_engine_v2._intrabar_trigger_price: the stop is tested first in BOTH
            # statuses, which is what makes the backtest path conservative.
            if status_tp1:
                if sl_touch:
                    return _stop_out(bar)
                if tp2_touch:
                    px = f * tp1 + (1.0 - f) * tp2
                    return _finish(OUT_TP1_TP2, px, d * (px - entry) / risk, "TP_HIT")
            else:
                if sl_touch:
                    return _stop_out(bar)
                if tp1_active and tp1_touch:
                    # Transition only. update_trade is called once per bar, so the trail
                    # cannot also trigger on this bar even if the low already pierced it.
                    status_tp1 = True
                    bars_to_tp1 = duration
                    if trail_level is not None:
                        sl_cur = trail_level
                elif (not tp1_active) and tp2_touch:
                    return _finish(OUT_TP1_TP2, tp2, d * (tp2 - entry) / risk, "TP_HIT")
        else:
            # analytics/sl_tp_comparator.simulate_exit: TP2 > SL > TP1 over raw high/low.
            if status_tp1:
                if tp2_touch:
                    px = f * tp1 + (1.0 - f) * tp2
                    return _finish(OUT_TP1_TP2, px, d * (px - entry) / risk, "TP_HIT")
                if sl_touch:
                    return _stop_out(bar)
            else:
                if tp2_touch:
                    # A bar reaching TP2 has necessarily passed TP1; the optimistic
                    # reading books both legs on the same bar.
                    status_tp1 = tp1_active
                    bars_to_tp1 = duration if tp1_active else None
                    px = f * tp1 + (1.0 - f) * tp2
                    return _finish(OUT_TP1_TP2, px, d * (px - entry) / risk, "TP_HIT")
                if sl_touch:
                    return _stop_out(bar)
                if tp1_active and tp1_touch:
                    status_tp1 = True
                    bars_to_tp1 = duration
                    if trail_level is not None:
                        sl_cur = trail_level

    # Horizon expired.
    if not bars:
        return _finish(OUT_TIMEOUT, entry, 0.0, "TIMEOUT")
    last_close = float(bars[-1].close)
    if not status_tp1:
        return _finish(OUT_TIMEOUT, last_close, d * (last_close - entry) / risk, "TIMEOUT")
    runner_px = last_close if timeout_pricing == TIMEOUT_MARK_TO_CLOSE else sl_cur
    px = f * tp1 + (1.0 - f) * runner_px
    return _finish(OUT_TIMEOUT, px, d * (px - entry) / risk, "TIMEOUT")


def _apply_policy(policy, current_stop, entry, is_long, initial_stop, tp1, tp2,
                  risk, atr, reached_tp1, bars_elapsed, mfe, mae) -> float:
    """Build the policy's view of the trade and clamp its answer to a tightening."""
    st = StopState(
        entry=entry, is_long=is_long, initial_stop=float(initial_stop),
        tp1=tp1, tp2=tp2, risk=risk, atr=float(atr) if atr else 0.0,
        reached_tp1=reached_tp1, bars_elapsed=bars_elapsed, mfe=mfe, mae=mae,
    )
    return tighten_only(current_stop, policy.stop_for_bar(st, current_stop), is_long)


def is_stop_exit(outcome: str) -> bool:
    """Whether this outcome closed on a stop order (charges stop slippage, SEM-015)."""
    return outcome in _STOP_EXITS
