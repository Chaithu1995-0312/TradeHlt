"""exit_grid.py — Phase D pure core: SL/TP exit-geometry grid + the recoverable-value ceilings.

MEASURE-ONLY, deterministic. Holds entries FIXED and sweeps (sl_atr_mult × tp_atr_mult) under the
governing intrabar_fixed exit model + 12bps cost, reusing the audited `forward_walk` + `CostModel`.
Reports per-cell IS/OOS expectancy / PF / win-rate / MaxDD(R), the `max_recoverable_E` vs the
incumbent cell, and the strict-bar lead test.

The ceilings (computed in D1, BEFORE any grid ranking) gate interpretation:
  * structural_upper_bound       = E_gross − min_achievable_cost   (realistically attainable)
  * perfect_information_upper_bound = E[MFE_r] − min_achievable_cost (unattainable foresight)
  * reality_gap                  = perfect − structural            (value locked behind information)
  * ceiling_utilization          = structural / perfect            (fraction exits can reach)
If structural_upper_bound ≤ 0 the run is the ENGINEERING regime: grid cells are cost/risk shaping,
never alpha; only E>0 AND OOS counts as success.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence

from research.contracts import Signal
from research.costs import CostModel
from research.measurement.forward_walk import forward_walk

SL_GRID_DEFAULT = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
TP_GRID_DEFAULT = (1.0, 1.5, 2.0, 3.0, 4.0, 5.0)
INCUMBENT = (1.0, 2.0)


@dataclass(frozen=True)
class Entry:
    entry_index: int
    entry: float
    direction: str       # "long" | "short"
    atr: float


# ── per-cell re-simulation ───────────────────────────────────────────────────
def net_rr(entry: Entry, candles: Sequence, sl_m: float, tp_m: float, *,
           max_forward: int, cost: CostModel, exit_model: str = "intrabar_fixed") -> float | None:
    """Forward-walk one fixed entry under (sl_m, tp_m); return net-RR or None if unmeasurable."""
    i = entry.entry_index
    if entry.atr <= 0.0:
        return None
    future = candles[i + 1: i + 1 + max_forward]
    if not future:
        return None
    sig = Signal(instrument="_", timestamp=candles[i].timestamp, entry_index=i,
                 direction=entry.direction, entry=entry.entry,
                 sl_atr_mult=sl_m, tp_atr_mult=tp_m, atr=entry.atr)
    o = forward_walk(sig, future, max_forward=max_forward, exit_model=exit_model)
    return cost.net_rr(o.rr_achieved, entry.entry, sl_m * entry.atr)


def _max_dd_r(rrs: Sequence[float]) -> float:
    """Max peak-to-trough drawdown of the cumulative-R curve (>= 0)."""
    peak = 0.0
    cum = 0.0
    mdd = 0.0
    for r in rrs:
        cum += r
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    return mdd


def cell_metrics(rrs: Sequence[float]) -> dict:
    n = len(rrs)
    if n == 0:
        return {"n": 0, "expectancy": None, "pf": None, "win_rate": None, "max_dd_r": None}
    gw = sum(r for r in rrs if r > 0)
    gl = -sum(r for r in rrs if r < 0)
    pf = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0.0)
    return {
        "n": n,
        "expectancy": round(statistics.mean(rrs), 6),
        "pf": round(pf, 4) if pf != float("inf") else None,
        "win_rate": round(sum(1 for r in rrs if r > 0) / n, 4),
        "max_dd_r": round(_max_dd_r(rrs), 4),
    }


def sweep_instrument(entries: Sequence[Entry], candles: Sequence, *,
                     sl_grid: Sequence[float], tp_grid: Sequence[float],
                     max_forward: int, cost: CostModel, oos_split: float) -> dict:
    """Per-(sl,tp) cell metrics for one instrument, split IS/OOS chronologically by entry_index.
    Returns {"<sl>x<tp>": {"all":metrics, "is":metrics, "oos":metrics}}."""
    ents = sorted(entries, key=lambda e: e.entry_index)
    cut = int(round(len(ents) * (1.0 - oos_split)))
    out: dict[str, dict] = {}
    for sl_m in sl_grid:
        for tp_m in tp_grid:
            rrs_all, rrs_is, rrs_oos = [], [], []
            for k, e in enumerate(ents):
                v = net_rr(e, candles, sl_m, tp_m, max_forward=max_forward, cost=cost)
                if v is None:
                    continue
                rrs_all.append(v)
                (rrs_is if k < cut else rrs_oos).append(v)
            out[_cell_key(sl_m, tp_m)] = {
                "all": cell_metrics(rrs_all), "is": cell_metrics(rrs_is), "oos": cell_metrics(rrs_oos),
            }
    return out


def _cell_key(sl_m: float, tp_m: float) -> str:
    return f"{sl_m}x{tp_m}"


# ── pooling across instruments (mean of per-instrument cell E + sign-consistency) ─────
def pool_cells(per_instrument: dict, sl_grid, tp_grid) -> dict:
    """per_instrument = {inst: sweep_instrument(...)}. For each cell, pool IS/OOS expectancy as the
    mean of per-instrument cell expectancies, with sign-consistency (k/n instruments E_oos>0)."""
    pooled: dict[str, dict] = {}
    for sl_m in sl_grid:
        for tp_m in tp_grid:
            key = _cell_key(sl_m, tp_m)
            is_es, oos_es, dd_rs = [], [], []
            pos = 0
            tot = 0
            for inst in sorted(per_instrument):
                c = per_instrument[inst].get(key)
                if not c:
                    continue
                if c["is"]["expectancy"] is not None:
                    is_es.append(c["is"]["expectancy"])
                if c["oos"]["expectancy"] is not None:
                    oos_es.append(c["oos"]["expectancy"])
                    tot += 1
                    if c["oos"]["expectancy"] > 0:
                        pos += 1
                if c["all"]["max_dd_r"] is not None:
                    dd_rs.append(c["all"]["max_dd_r"])
            pooled[key] = {
                "sl": sl_m, "tp": tp_m,
                "expectancy_is": round(statistics.mean(is_es), 6) if is_es else None,
                "expectancy_oos": round(statistics.mean(oos_es), 6) if oos_es else None,
                "mean_max_dd_r": round(statistics.mean(dd_rs), 4) if dd_rs else None,
                "oos_sign_consistency": f"{pos}/{tot}",
            }
    return pooled


def verdict(pooled: dict) -> dict:
    """Strict bar: a lead requires E_IS>0 AND E_OOS>0 AND sign-consistent (>= majority).
    max_recoverable_E = best pooled E_oos − incumbent pooled E_oos."""
    inc = pooled.get(_cell_key(*INCUMBENT), {})
    inc_oos = inc.get("expectancy_oos")
    leads = []
    best_key, best_oos = None, float("-inf")
    for key, c in pooled.items():
        eo, ei = c["expectancy_oos"], c["expectancy_is"]
        if eo is not None and eo > best_oos:
            best_key, best_oos = key, eo
        if ei is not None and eo is not None and ei > 0 and eo > 0:
            pos, tot = (int(x) for x in c["oos_sign_consistency"].split("/"))
            if tot > 0 and pos / tot >= 0.5:
                leads.append(key)
    max_recoverable = (round(best_oos - inc_oos, 6)
                       if (best_oos != float("-inf") and inc_oos is not None) else None)
    return {
        "incumbent_cell": _cell_key(*INCUMBENT),
        "incumbent_expectancy_oos": inc_oos,
        "best_cell": best_key,
        "best_expectancy_oos": None if best_oos == float("-inf") else round(best_oos, 6),
        "max_recoverable_E": max_recoverable,
        "leads": leads,
        "has_lead": bool(leads),
    }


# ── D1 ceilings ──────────────────────────────────────────────────────────────
def min_achievable_cost(records: Sequence[dict], widest_sl: float, bps: float) -> float:
    """Mean cost_r at the widest SL (= the lowest achievable cost in R). records carry entry+atr."""
    cs = [(bps / 1e4 * r["entry"]) / (widest_sl * r["atr"])
          for r in records if r.get("atr", 0.0) > 0.0]
    return statistics.mean(cs) if cs else float("nan")


def ceilings(records: Sequence[dict], decomposition: dict, *, widest_sl: float, bps: float) -> dict:
    """The four recoverable-value quantities + regime classification. `records` are forensics
    per-trade dicts (carry rr_gross_intrabar, max_favorable_excursion_r, entry, atr)."""
    e_gross = decomposition.get("expectancy_gross")
    min_cost = min_achievable_cost(records, widest_sl, bps)
    mfes = [r["max_favorable_excursion_r"] for r in records
            if r.get("max_favorable_excursion_r") is not None]
    mfe_capture = statistics.mean(mfes) if mfes else float("nan")
    structural = (e_gross - min_cost) if (e_gross is not None and min_cost == min_cost) else None
    perfect = (mfe_capture - min_cost) if (mfe_capture == mfe_capture and min_cost == min_cost) else None
    gap = (perfect - structural) if (perfect is not None and structural is not None) else None
    util = (structural / perfect) if (perfect not in (None, 0) and structural is not None) else None
    regime = "ALPHA" if (structural is not None and structural > 0) else "ENGINEERING"
    return {
        "expectancy_gross": e_gross,
        "min_achievable_cost": round(min_cost, 6) if min_cost == min_cost else None,
        "mfe_capture": round(mfe_capture, 6) if mfe_capture == mfe_capture else None,
        "structural_upper_bound": round(structural, 6) if structural is not None else None,
        "perfect_information_upper_bound": round(perfect, 6) if perfect is not None else None,
        "reality_gap": round(gap, 6) if gap is not None else None,
        "ceiling_utilization": round(util, 4) if util is not None else None,
        "regime": regime,
    }
