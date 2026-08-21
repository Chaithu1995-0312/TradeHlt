"""exit_analysis.py — SEM-020 exit-capture decomposition: what any exit COULD achieve.

WHY THIS EXISTS
---------------
`research.exit_grid.ceilings` already computes the four recoverable-value quantities, but
through `forward_walk` (a single-TP object) and a flat-bps `CostModel`. Production trades
the two-target object of SEM-017, and on XAUUSD the flat 12bps basis is roughly eleven
times the measured broker cost (SEM-015). A ceiling computed on a different exit object,
with a different cost basis, is not a ceiling for the thing being evaluated — so this
module recomputes the same algebra against the object and the cost that actually apply,
and adds the one quantity `exit_grid` does not distinguish: the CAUSAL ceiling.

THREE CEILINGS, AND ONLY ONE OF THEM IS HEADROOM
------------------------------------------------
    perfect_information   E[MFE_r] - min_cost   requires knowing the path. UNATTAINABLE.
    causal                best net E over the declared policy grid, past bars only.
    incumbent             what the production geometry actually realises.

Quoting the perfect-foresight bound as headroom is the interpretation error this module
exists to prevent: no causal rule reaches it, and the gap between it and the causal
ceiling is not recoverable by any amount of exit engineering.

TIE-BREAK COUPLING (from research/path/ambiguity_census.py, reproduced because it is
load-bearing here): `min_cost` cancels, so

    reality_gap == mfe_capture - e_gross      exactly.

`mfe_capture` is exit-agnostic and tie-break IMMUNE; `e_gross` is tie-break EXPOSED. Any
pessimism in the tie-break therefore inflates the apparent headroom one-for-one, which is
why the tie-break convention is recorded beside every ceiling rather than left implicit.
"""

from __future__ import annotations

import numpy as np

# A capture ratio above 1 is arithmetically impossible for one trade: a position cannot
# realise more than the favourable excursion its own path offered. Anything materially
# above this is a join/alignment defect, not a result. (SEM-020 validation rule.)
#
# The tolerance is 1e-6, not 0, and the reason is precision rather than laxity:
# `multi_tp_walk` returns `rr_gross` ROUNDED to 6 decimals, while `mfe_r` here is exact.
# A trade that exits exactly AT its favourable extreme -- a TIMEOUT whose final close is
# the window high, which does occur -- therefore divides a slightly-rounded-up numerator
# by an exact denominator and lands a few 1e-7 above 1. Measured on the XAUUSD M15 corpus:
# exactly one such unit (h20/fixed_atr/long, _pos 44965, ratio 1.0000), realised R and MFE
# agreeing to every stored digit. A tolerance below the stored precision reports arithmetic
# noise as a defect; one materially above it would hide a real join error.
CAPTURE_RATIO_MAX = 1.0 + 1e-6


def _sliding_max(a: np.ndarray, window: int) -> np.ndarray:
    """Max over `a[i : i+window]` for every i where a full window exists.

    Returned length is len(a) - window + 1. Uses a strided view: no copy of the data,
    which matters because the horizon sweep builds one of these per horizon.
    """
    if window <= 0:
        raise ValueError(f"_sliding_max: window must be positive (got {window})")
    if a.size < window:
        return np.empty(0, dtype=float)
    view = np.lib.stride_tricks.sliding_window_view(a, window)
    return view.max(axis=1)


def _sliding_min(a: np.ndarray, window: int) -> np.ndarray:
    if window <= 0:
        raise ValueError(f"_sliding_min: window must be positive (got {window})")
    if a.size < window:
        return np.empty(0, dtype=float)
    view = np.lib.stride_tricks.sliding_window_view(a, window)
    return view.min(axis=1)


def horizon_excursions(
    high: np.ndarray,
    low: np.ndarray,
    entry: np.ndarray,
    *,
    horizon: int,
) -> dict:
    """Exit-agnostic MFE/MAE in PRICE units for every bar, both directions.

    Vectorised counterpart of `research.measurement.forward_walk.horizon_excursion`,
    which this must agree with bar-for-bar (asserted by
    `tests/research/test_exit_ceilings.py`, not assumed).

    For bar i the window is bars i+1 .. i+horizon — strictly after the entry bar, the
    same no-lookahead contract the scalar version enforces per bar. Bars without a full
    forward window yield NaN rather than a truncated measurement, because a short window
    is a different measurement, not a missing one.

    MFE is clamped at >= 0 and MAE at <= 0, matching the scalar version, which starts
    both accumulators at 0.0 and only moves them in one direction.
    """
    n = entry.size
    fwd_hi = np.full(n, np.nan)
    fwd_lo = np.full(n, np.nan)
    # Window starting at i+1 of length `horizon`; valid while i+horizon <= n-1.
    m = _sliding_max(high, horizon)
    k = _sliding_min(low, horizon)
    valid = n - horizon                      # bars 0 .. valid-1 have a full window
    if valid > 0:
        fwd_hi[:valid] = m[1 : valid + 1]
        fwd_lo[:valid] = k[1 : valid + 1]

    long_mfe = np.maximum(0.0, fwd_hi - entry)
    long_mae = np.minimum(0.0, fwd_lo - entry)
    short_mfe = np.maximum(0.0, entry - fwd_lo)
    short_mae = np.minimum(0.0, entry - fwd_hi)
    return {
        "long": {"mfe": long_mfe, "mae": long_mae},
        "short": {"mfe": short_mfe, "mae": short_mae},
        "n_valid": int(max(0, valid)),
    }


def passive_exposure_r(
    close: np.ndarray,
    entry: np.ndarray,
    risk_distance: np.ndarray,
    *,
    horizon: int,
    direction: str,
) -> np.ndarray:
    """Buy-and-hold the same direction for `horizon` bars, in R. The binding control.

    XAUUSD rose across this corpus, so a wide stop on a long is partly just exposure to
    that drift. Benchmarking a cell against zero credits the drift to the exit rule;
    benchmarking against this does not. Returns NaN where no full window exists.
    """
    n = entry.size
    out = np.full(n, np.nan)
    valid = n - horizon
    if valid > 0:
        exit_px = close[horizon : horizon + valid]
        d = 1.0 if direction == "long" else -1.0
        out[:valid] = d * (exit_px - entry[:valid]) / risk_distance[:valid]
    return out


def min_achievable_cost(
    cost_model,
    *,
    entry: np.ndarray,
    atr_abs: np.ndarray,
    widest_sl_atr_mult: float,
    direction: str = "long",
) -> float:
    """Lowest cost in R any cell in the declared grid could incur.

    Three things are simultaneously most favourable: the WIDEST stop in the grid (cost_r
    is cost_price/risk_distance, so a wide stop dilutes cost), a LIMIT exit (a take-profit
    pays no stop slippage), and ZERO overnight nights. It is a genuine floor, not an
    average — which is what makes it usable as a ceiling term.
    """
    risk = widest_sl_atr_mult * atr_abs
    ok = risk > 0
    if not ok.any():
        return float("nan")
    cost_price = cost_model.cost_price(exit_kind="TP_HIT", direction=direction, nights_held=0)
    return float(np.mean(cost_price / risk[ok]))


def capture_ratios(realised_r: np.ndarray, mfe_r: np.ndarray) -> np.ndarray:
    """Fraction of the available favourable excursion the exit actually converted.

    Undefined where no favourable excursion existed (mfe_r ~ 0): a trade that was never
    in profit has no capture to measure, and including it as a 0 would understate the
    exit's performance on the trades where capture was possible at all.
    """
    out = np.full(realised_r.size, np.nan)
    ok = mfe_r > 1e-9
    out[ok] = realised_r[ok] / mfe_r[ok]
    return out


def _pctl(a: np.ndarray, q: float):
    a = a[np.isfinite(a)]
    return None if a.size == 0 else round(float(np.percentile(a, q)), 6)


def _mean(a: np.ndarray):
    a = a[np.isfinite(a)]
    return None if a.size == 0 else round(float(a.mean()), 6)


def ceiling_block(
    *,
    mfe_r: np.ndarray,
    realised_gross_r: np.ndarray,
    min_cost: float,
    passive_r: np.ndarray | None = None,
    causal_best_net: float | None = None,
    exit_object: str,
    cost_basis: str,
    tie_break: str,
) -> dict:
    """The SEM-020 quantities for one (geometry, direction, horizon) cell.

    `exit_object`, `cost_basis` and `tie_break` are REQUIRED, not optional metadata: a
    ceiling is only comparable to something measured on the same object, with the same
    cost, under the same same-bar convention. Carrying them on the block is what stops
    a number being quoted against a population it does not bound.
    """
    mfe_capture = _mean(mfe_r)
    e_gross = _mean(realised_gross_r)
    perfect = None if (mfe_capture is None or min_cost != min_cost) else mfe_capture - min_cost
    structural = None if (e_gross is None or min_cost != min_cost) else e_gross - min_cost
    gap = None if (perfect is None or structural is None) else perfect - structural
    util = None if (not perfect or structural is None) else structural / perfect

    cr = capture_ratios(realised_gross_r, mfe_r)
    finite_cr = cr[np.isfinite(cr)]
    violations = int((finite_cr > CAPTURE_RATIO_MAX).sum())

    return {
        "n": int(np.isfinite(realised_gross_r).sum()),
        "exit_object": exit_object,
        "cost_basis": cost_basis,
        "tie_break": tie_break,
        "mfe_capture": mfe_capture,
        "expectancy_gross": e_gross,
        "min_achievable_cost": None if min_cost != min_cost else round(min_cost, 6),
        "perfect_information_upper_bound": None if perfect is None else round(perfect, 6),
        "causal_upper_bound": None if causal_best_net is None else round(causal_best_net, 6),
        "structural_upper_bound": None if structural is None else round(structural, 6),
        "reality_gap": None if gap is None else round(gap, 6),
        "ceiling_utilization": None if util is None else round(util, 4),
        "regime": "ALPHA" if (structural is not None and structural > 0) else "ENGINEERING",
        "capture_ratio_p50": _pctl(cr, 50),
        "capture_ratio_p90": _pctl(cr, 90),
        "n_with_opportunity": int(finite_cr.size),
        "capture_ratio_violations": violations,
        "mfe_r_p50": _pctl(mfe_r, 50),
        "mfe_r_p90": _pctl(mfe_r, 90),
        "passive_exposure_r": None if passive_r is None else _mean(passive_r),
        # The gate. Reported as a field so a downstream stage cannot proceed on a verbal
        # reading of the report; it reads this.
        "exit_axis_open": bool(perfect is not None and perfect > 0),
    }


def gate_verdict(blocks: dict) -> dict:
    """Stage-A gate: is there room for ANY exit rule to profit on this population?

    If no cell's perfect-foresight ceiling clears zero net of measured cost, then no exit
    policy of any kind can help and the search is pointless — the SEM-020 falsification
    condition. Computing this BEFORE the policy grid is the whole point of running Stage A
    first; it costs one pass and can close the axis outright.
    """
    open_cells = [k for k, b in blocks.items() if b.get("exit_axis_open")]
    worst = min((b["perfect_information_upper_bound"] for b in blocks.values()
                 if b.get("perfect_information_upper_bound") is not None), default=None)
    best = max((b["perfect_information_upper_bound"] for b in blocks.values()
                if b.get("perfect_information_upper_bound") is not None), default=None)
    violations = sum(b.get("capture_ratio_violations", 0) for b in blocks.values())
    return {
        "cells": len(blocks),
        "cells_with_room": len(open_cells),
        "perfect_ceiling_min": worst,
        "perfect_ceiling_max": best,
        "capture_ratio_violations": violations,
        "capture_ratio_ok": violations == 0,
        "verdict": "EXIT_AXIS_OPEN" if open_cells else "EXIT_AXIS_CLOSED",
        "note": (
            "EXIT_AXIS_OPEN means only that a perfect-foresight exit could profit. It is "
            "NOT headroom: no causal rule reaches that bound. The causal ceiling is the "
            "attainable one and is measured in the policy sweep, not here."
        ),
    }
