"""ambiguity_census.py — Program 10 / Phase 0A pure core: how often does the same-bar
SL-before-TP tie-break actually fire, and what is the worst case it could cost?

MEASURE-ONLY, deterministic. Reads `forward_walk` and NEVER edits it. Mirrors
`research.exit_grid.sweep_instrument` cell-for-cell (same Entry population, same grid, same
kernel call) so the census is directly commensurable with F-025's
`results/research/phase_d/phase_d_exit_grid.json`.

WHY THIS MATTERS (the exact coupling, not a diffuse risk)
---------------------------------------------------------
From `research.exit_grid.ceilings` the `min_achievable_cost` term cancels, so exactly:

    reality_gap  ==  mfe_capture - e_gross

`mfe_capture` comes from `horizon_excursion` — exit-agnostic, tie-break IMMUNE.
`e_gross`     comes from `forward_walk(exit_model="intrabar_fixed")` — tie-break EXPOSED.

So a pessimistic bias in the tie-break inflates F-025's `reality_gap` ONE-FOR-ONE.

THREE POPULATIONS, COUNTED SEPARATELY
-------------------------------------
Conflating them is the primary way this census could lie, so they never share a counter.

  P1  same-bar SL and TP        forward_walk.py:127   directional bias in e_gross   -> F-025
  P2  OCO double-edge touch     forward_walk.py:221   selection effect (D1 cancel)  -> Program 9
  P3  OCO fill-bar TP suppress  forward_walk.py:251   directional, OCO-only         -> Program 9

P1 is the ONLY population that enters the F-025 revision rule. P2/P3 belong to the straddle
population and are reported only when an OCO signal set is supplied.

DETECTION
---------
P1 needs NO re-scan of the kernel — it leaves an exact signature in the returned Outcome:

    P1 fired  <=>  outcome == "SL_HIT" and time_to_tp is not None

Exact in both directions (forward_walk.py:124-144): `time_to_tp` is assigned at :124, BEFORE
the sl_hit block at :127; and any earlier tp_hit without sl_hit would have returned TP_HIT at
:141. So an SL_HIT can carry a non-None time_to_tp only when both fired on the SAME bar.
Because the census reads the kernel's own output rather than re-deriving it, it cannot drift
from the kernel it audits.

P2/P3 have no such signature (forward_walk_oco returns None for BOTH D1 cancel and D3 TTL
expiry), so they are detected by an explicitly-specified re-scan whose consistency with the
kernel is asserted by test.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence

from research.contracts import Signal
from research.exit_grid import Entry, _cell_key
from research.measurement.forward_walk import forward_walk, forward_walk_oco

# In `intrabar_fixed` the trailing stop never ratchets (that is `trailing`-only), so a
# tie-break ALWAYS resolves to SL and the realized RR is exactly -1.0. Asserted, not assumed:
# `verify_sl_rr` records any deviation instead of silently trusting this model of the kernel.
EXPECTED_SL_RR = -1.0
SL_RR_TOL = 1e-6

# Frozen 0A stop gate (docs/research/preregistration-program-10-intrabar-path.md).
STOP_GATE_MAX_BIAS_R = 0.05

# Per-cell power floor: cells below this report INSUFFICIENT and are excluded from the
# pooled bias claim (E-001 question 2).
MIN_CELL_N = 30


@dataclass(frozen=True)
class P1Event:
    """One same-bar SL/TP collision under a specific (sl_m, tp_m) geometry."""

    entry_index: int
    sl_m: float
    tp_m: float
    rr_if_sl: float        # what the kernel actually returned (should be EXPECTED_SL_RR)
    rr_if_tp: float        # what it would have returned had TP been honoured: tp_m / sl_m
    r_swing: float         # rr_if_tp - rr_if_sl  == the max possible per-event bias
    duration: int
    atr: float
    entry: float
    exit_bar_range: float  # high-low of the colliding bar (0.0 if unavailable)
    tp_dist: float         # tp_m * atr
    session: str


def detect_p1(outcome) -> bool:
    """The exact P1 signature. See module docstring for the both-directions proof."""
    return outcome.outcome == "SL_HIT" and outcome.time_to_tp is not None


def _session_of(bar) -> str:
    """Coarse UTC session bucket; 'unknown' when the bar carries no timestamp."""
    ts = getattr(bar, "timestamp", None)
    hour = getattr(ts, "hour", None)
    if hour is None:
        return "unknown"
    if 0 <= hour < 8:
        return "asia"
    if 8 <= hour < 16:
        return "london"
    return "newyork"


def census_entry(entry: Entry, candles: Sequence, sl_m: float, tp_m: float, *,
                 max_forward: int) -> P1Event | None:
    """Forward-walk one fixed entry under (sl_m, tp_m); return a P1Event iff the tie-break fired.

    Deliberately GROSS (no CostModel): F-025's `e_gross` is pre-cost, so the bias this census
    bounds must be measured in the same units.
    """
    i = entry.entry_index
    if entry.atr <= 0.0:
        return None
    future = candles[i + 1: i + 1 + max_forward]
    if not future:
        return None

    sig = Signal(instrument="_", timestamp=candles[i].timestamp, entry_index=i,
                 direction=entry.direction, entry=entry.entry,
                 sl_atr_mult=sl_m, tp_atr_mult=tp_m, atr=entry.atr)
    o = forward_walk(sig, future, max_forward=max_forward, exit_model="intrabar_fixed")
    if not detect_p1(o):
        return None

    # The colliding bar is the exit bar: duration_candles is 1-based over `future`.
    j = o.duration_candles - 1
    exit_bar = future[j] if 0 <= j < len(future) else None
    bar_range = (float(exit_bar.high) - float(exit_bar.low)) if exit_bar is not None else 0.0

    rr_if_sl = float(o.rr_achieved)
    rr_if_tp = tp_m / sl_m
    return P1Event(
        entry_index=i, sl_m=sl_m, tp_m=tp_m,
        rr_if_sl=rr_if_sl, rr_if_tp=rr_if_tp, r_swing=rr_if_tp - rr_if_sl,
        duration=o.duration_candles, atr=entry.atr, entry=entry.entry,
        exit_bar_range=bar_range, tp_dist=tp_m * entry.atr,
        session=_session_of(exit_bar) if exit_bar is not None else "unknown",
    )


def cell_census(entries: Sequence[Entry], candles: Sequence, sl_m: float, tp_m: float, *,
                max_forward: int) -> dict:
    """P1 statistics for one (sl_m, tp_m) cell.

    `max_bias_R` is an UPPER BOUND (every tie-break decided wrongly), never an estimate. It can
    only trigger the 0A stop gate; establishing actual harm requires 0B's resolved split.
    """
    n_signals = 0
    events: list[P1Event] = []
    for e in entries:
        if e.atr <= 0.0:
            continue
        future = candles[e.entry_index + 1: e.entry_index + 1 + max_forward]
        if not future:
            continue
        n_signals += 1
        ev = census_entry(e, candles, sl_m, tp_m, max_forward=max_forward)
        if ev is not None:
            events.append(ev)

    n_p1 = len(events)
    rate = (n_p1 / n_signals) if n_signals else None
    swings = [ev.r_swing for ev in events]
    mean_swing = statistics.mean(swings) if swings else None
    max_bias = (rate * mean_swing) if (rate is not None and mean_swing is not None) else None

    return {
        "sl": sl_m, "tp": tp_m,
        "n_signals": n_signals,
        "n_p1": n_p1,
        "ambiguity_rate": round(rate, 6) if rate is not None else None,
        "mean_r_swing": round(mean_swing, 6) if mean_swing is not None else None,
        "max_bias_R": round(max_bias, 6) if max_bias is not None else None,
        "power": "INSUFFICIENT" if n_p1 < MIN_CELL_N else "POWERED",
        "sl_rr_deviations": verify_sl_rr(events),
        "conditioning": _conditioning(events),
    }


def verify_sl_rr(events: Sequence[P1Event]) -> int:
    """Count events whose realized SL RR deviates from the expected exact -1.0.

    This checks the census's MODEL of the kernel against the kernel's actual output. A non-zero
    count means `intrabar_fixed` did something other than resolve at the original stop, and the
    `r_swing` arithmetic below would be wrong. Reported, never silently tolerated.
    """
    return sum(1 for ev in events if abs(ev.rr_if_sl - EXPECTED_SL_RR) > SL_RR_TOL)


def _conditioning(events: Sequence[P1Event]) -> dict:
    """Descriptive conditioning of the ambiguous population (information only, no verdict)."""
    if not events:
        return {"by_session": {}, "mean_tp_dist_over_bar_range": None}
    by_session: dict[str, int] = {}
    for ev in events:
        by_session[ev.session] = by_session.get(ev.session, 0) + 1
    ratios = [ev.tp_dist / ev.exit_bar_range for ev in events if ev.exit_bar_range > 0.0]
    return {
        "by_session": dict(sorted(by_session.items())),
        "mean_tp_dist_over_bar_range": round(statistics.mean(ratios), 6) if ratios else None,
    }


def census_instrument(entries: Sequence[Entry], candles: Sequence, *,
                      sl_grid: Sequence[float], tp_grid: Sequence[float],
                      max_forward: int) -> dict:
    """Per-(sl,tp) P1 census for one instrument. Mirrors exit_grid.sweep_instrument's shape."""
    ents = sorted(entries, key=lambda e: e.entry_index)
    out: dict[str, dict] = {}
    for sl_m in sl_grid:
        for tp_m in tp_grid:
            out[_cell_key(sl_m, tp_m)] = cell_census(
                ents, candles, sl_m, tp_m, max_forward=max_forward)
    return out


def pool_census(per_instrument: dict, sl_grid: Sequence[float], tp_grid: Sequence[float]) -> dict:
    """Pool each cell across instruments.

    Rates pool on TOTALS (sum n_p1 / sum n_signals), not as a mean of per-instrument rates, so an
    instrument with few signals cannot dominate. Only POWERED cells contribute to the pooled
    bias claim; INSUFFICIENT cells are reported but excluded.
    """
    pooled: dict[str, dict] = {}
    for sl_m in sl_grid:
        for tp_m in tp_grid:
            key = _cell_key(sl_m, tp_m)
            tot_sig = tot_p1 = 0
            swings: list[float] = []
            powered = 0
            insufficient = 0
            for inst in sorted(per_instrument):
                c = per_instrument[inst].get(key)
                if not c:
                    continue
                tot_sig += c["n_signals"]
                tot_p1 += c["n_p1"]
                if c["mean_r_swing"] is not None:
                    swings.append(c["mean_r_swing"])
                if c["power"] == "POWERED":
                    powered += 1
                else:
                    insufficient += 1
            rate = (tot_p1 / tot_sig) if tot_sig else None
            mean_swing = statistics.mean(swings) if swings else None
            max_bias = (rate * mean_swing) if (rate is not None and mean_swing is not None) else None
            pooled[key] = {
                "sl": sl_m, "tp": tp_m,
                "n_signals": tot_sig, "n_p1": tot_p1,
                "ambiguity_rate": round(rate, 6) if rate is not None else None,
                "mean_r_swing": round(mean_swing, 6) if mean_swing is not None else None,
                "max_bias_R": round(max_bias, 6) if max_bias is not None else None,
                "instruments_powered": powered,
                "instruments_insufficient": insufficient,
            }
    return pooled


def stop_gate(pooled: dict, *, incumbent_cell: str = "1.0x2.0",
              threshold: float = STOP_GATE_MAX_BIAS_R) -> dict:
    """Evaluate the FROZEN 0A stop gate.

    CLOSE_PROGRAM  -> the convention is immaterial at the incumbent geometry; 0B-0D unfunded.
    PROCEED_TO_0B  -> the bound is material; M5 resolution is required to convert it into a
                      measured split. NOTE: proceeding asserts only that the bound is large
                      enough to matter, never that harm has been demonstrated.
    """
    inc = pooled.get(incumbent_cell, {})
    inc_bias = inc.get("max_bias_R")
    biases = [c["max_bias_R"] for c in pooled.values() if c.get("max_bias_R") is not None]
    worst_key, worst = None, None
    for key, c in pooled.items():
        b = c.get("max_bias_R")
        if b is not None and (worst is None or b > worst):
            worst_key, worst = key, b

    if inc_bias is None:
        verdict = "INSUFFICIENT"
    elif inc_bias < threshold:
        verdict = "CLOSE_PROGRAM"
    else:
        verdict = "PROCEED_TO_0B"

    return {
        "threshold_max_bias_R": threshold,
        "incumbent_cell": incumbent_cell,
        "incumbent_max_bias_R": inc_bias,
        "worst_cell": worst_key,
        "worst_max_bias_R": round(worst, 6) if worst is not None else None,
        "mean_max_bias_R": round(statistics.mean(biases), 6) if biases else None,
        "verdict": verdict,
    }


# ── P1 vs F-025's `same_bar_conflict` — the overlap, measured not assumed ────────────────
def overlap_census(entries: Sequence[Entry], candles: Sequence, sl_m: float, tp_m: float, *,
                   max_forward: int) -> dict:
    """Measure |P1 ∩ same_bar_conflict| and both set differences at ONE geometry.

    WHY THIS EXISTS (pre-registration correction, 2026-07-19). F-025's loss decomposition reports
    a `same_bar_conflict` class, and this program's first draft treated its 9.11%/9.25% as an
    estimate of P1's mass. It is not. `forensics._classify:100` defines it as
    `close_only == TP_HIT and intrabar == SL_HIT`, which is:

      * NOT SUFFICIENT — a real P1 bar that wick-touches both levels then closes back inside is
        classified `plain_stop_loss`, because close_only never crosses TP on the close.
      * NOT NECESSARY  — a bar may wick the SL while closing high, after which close_only walks
        on and closes above TP many bars later. Counted as `same_bar_conflict`, no collision.

    The two sets overlap but neither contains the other, so the relationship is measured here
    rather than assumed. Run at the INCUMBENT geometry only: F-025's decomposition is itself
    computed at sl=1.0/tp=2.0 (`phase_d_exit_grid._records_from_entries`), so that is the only
    cell where the comparison is meaningful.
    """
    both = p1_only = sbc_only = neither = 0
    for e in entries:
        if e.atr <= 0.0:
            continue
        i = e.entry_index
        future = candles[i + 1: i + 1 + max_forward]
        if not future:
            continue
        sig = Signal(instrument="_", timestamp=candles[i].timestamp, entry_index=i,
                     direction=e.direction, entry=e.entry,
                     sl_atr_mult=sl_m, tp_atr_mult=tp_m, atr=e.atr)
        ib = forward_walk(sig, future, max_forward=max_forward, exit_model="intrabar_fixed")
        co = forward_walk(sig, future, max_forward=max_forward, exit_model="close_only")
        p1 = detect_p1(ib)
        sbc = (co.outcome == "TP_HIT" and ib.outcome == "SL_HIT")
        if p1 and sbc:
            both += 1
        elif p1:
            p1_only += 1
        elif sbc:
            sbc_only += 1
        else:
            neither += 1

    n_p1 = both + p1_only
    n_sbc = both + sbc_only
    return {
        "geometry": _cell_key(sl_m, tp_m),
        "n_p1": n_p1,
        "n_same_bar_conflict": n_sbc,
        "both": both,
        "p1_only": p1_only,
        "same_bar_conflict_only": sbc_only,
        "neither": neither,
        "jaccard": round(both / (both + p1_only + sbc_only), 6) if (both + p1_only + sbc_only) else None,
        "p1_share_of_sbc": round(both / n_sbc, 6) if n_sbc else None,
        "sbc_share_of_p1": round(both / n_p1, 6) if n_p1 else None,
        "note": ("P1 and same_bar_conflict are DISTINCT populations; neither contains the other. "
                 "Never equate these counts — cite this table."),
    }


# ── P2 / P3 — the OCO (straddle) populations. Separate signal set, separate counters. ────
def oco_census(signals: Sequence[Signal], candles: Sequence, *,
               max_forward: int, entry_ttl: int) -> dict:
    """P2 (D1 double-edge cancel) and P3 (D2 fill-bar TP suppression) over an OCO population.

    These belong to Program 9's straddle construction, NOT to F-025's directional population,
    and never enter the F-025 revision rule. Reported so Program 9's cancelled mass — currently
    an unquantified selection effect — becomes visible.

    `forward_walk_oco` returns None for BOTH D1 (double-edge) and D3 (TTL expiry), so unlike P1
    these require an explicitly-specified re-scan. Consistency with the kernel is asserted by
    tests/research/path/test_ambiguity_census.py.
    """
    n = n_p2 = n_p3 = n_filled = n_ttl = 0
    for sig in signals:
        i = sig.entry_index
        future = candles[i + 1: i + 1 + max_forward]
        if not future:
            continue
        n += 1
        box_high = float(sig.meta["box_high"])
        box_low = float(sig.meta["box_low"])
        risk = sig.sl_atr_mult * sig.atr
        reward = sig.tp_atr_mult * sig.atr

        # Re-scan the pending phase exactly as forward_walk_oco:213-230 does.
        p2 = False
        fill_j = None
        direction = ""
        for j, bar in enumerate(future[:entry_ttl]):
            hi, lo = float(bar.high), float(bar.low)
            th, tl = hi >= box_high, lo <= box_low
            if th and tl:
                p2 = True
                break
            if th:
                fill_j, direction = j, "long"
                break
            if tl:
                fill_j, direction = j, "short"
                break
        if p2:
            n_p2 += 1
            continue
        if fill_j is None:
            n_ttl += 1
            continue
        n_filled += 1

        # P3 = the fill bar hits SL (so D2 suppresses TP) AND that same bar also touched TP.
        fb = future[fill_j]
        hi, lo = float(fb.high), float(fb.low)
        entry = box_high if direction == "long" else box_low
        if direction == "long":
            sl_hit, tp_touch = lo <= entry - risk, hi >= entry + reward
        else:
            sl_hit, tp_touch = hi >= entry + risk, lo <= entry - reward
        if sl_hit and tp_touch:
            n_p3 += 1

    return {
        "n_straddles": n,
        "n_filled": n_filled,
        "n_ttl_expired": n_ttl,
        "p2_double_edge_cancelled": n_p2,
        "p2_rate": round(n_p2 / n, 6) if n else None,
        "p3_fill_bar_tp_suppressed": n_p3,
        "p3_rate_of_filled": round(n_p3 / n_filled, 6) if n_filled else None,
    }
