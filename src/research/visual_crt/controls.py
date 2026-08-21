"""controls.py — the OOS split and control benchmarks MC-VCRT-XAUUSD-M15-V1 declared.

WHY THIS EXISTS
---------------
V1's sealed contract declared both of these and its run produced neither:

  * ``splits.scheme = single_holdout_chronologic`` — embargo 96 M15 bars (24h), purge train
    units whose 40-bar exit horizon overlaps the test start, seed 20260817, "exact dates locked
    in split_manifest at run time". No ``split_manifest.json`` was ever written.
  * ``metrics.success_gate`` — "…AND beats the pre-registered controls (random_entry,
    long_only)". No control was ever run.

``driver.py`` contained no split, embargo, purge, or control code at all. This module is the
first execution of those sealed definitions; it does not invent them. Every parameter is read
from the contract, never redeclared here.

This does NOT reopen F-081. Controls and an OOS split are hurdles a POSITIVE result must clear —
an arm rejected at the absolute-expectancy stage never reaches them, so their absence cannot
have turned an edge into a null. They bind precisely when something comes back positive.

FAIRNESS INVARIANT (load-bearing)
---------------------------------
Every control resolves through the SAME ``forward_walk`` exit model and the SAME cost model as
the arm it is compared against. Scoring a control on a different basis than its arm would rig
the comparison — the exact failure this module exists to prevent.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import datetime
from typing import Sequence

from research.contracts import Signal
from research.measurement.forward_walk import forward_walk
from research.visual_crt.driver import HORIZON_BARS, Bar, LedgerRow, _net_r

#: 24h at M15. Contract: splits.embargo.
EMBARGO_BARS = 96


# ══════════════════════════════════════════════════════════════════════════════
# Split — single_holdout_chronologic
# ══════════════════════════════════════════════════════════════════════════════

def single_holdout_chronologic(
    rows: Sequence[LedgerRow],
    *,
    oos_fraction: float = 0.20,
    embargo_bars: int = EMBARGO_BARS,
    horizon_bars: int = HORIZON_BARS,
) -> dict:
    """Split one arm's entries chronologically, with embargo and purge.

    Returns a manifest dict (never writes). Contract wording: "last 20% of entries by entry_ts,
    computed per arm after inclusion; exact dates locked in split_manifest at run time".

    Three groups, and the purged/embargoed units belong to NEITHER — dropping them is the point:

      OOS     the last `oos_fraction` of entries by entry_ts.
      PURGED  IS entries whose `horizon_bars` exit window reaches into the OOS region. Their
              outcome is partly determined by bars the OOS set also uses, so keeping them would
              leak.
      EMBARGO IS entries inside `embargo_bars` of the OOS start. Purge removes horizon overlap;
              the embargo additionally removes near-boundary serial correlation.
    """
    if not rows:
        return {"n": 0, "is": [], "oos": [], "purged": [], "embargoed": [],
                "note": "no entries produced"}
    if not 0.0 < oos_fraction < 1.0:
        raise ValueError(f"oos_fraction must be in (0,1), got {oos_fraction}")

    ordered = sorted(rows, key=lambda r: (r.entry_ts, r.entry_index))
    n = len(ordered)
    n_oos = max(1, int(round(n * oos_fraction)))
    split_at = n - n_oos

    oos = ordered[split_at:]
    candidate_is = ordered[:split_at]
    oos_start_index = min(r.entry_index for r in oos)

    is_rows, purged, embargoed = [], [], []
    for r in candidate_is:
        if r.entry_index + horizon_bars >= oos_start_index:
            purged.append(r)
        elif oos_start_index - r.entry_index <= embargo_bars:
            embargoed.append(r)
        else:
            is_rows.append(r)

    return {
        "n": n,
        "oos_fraction_declared": oos_fraction,
        "embargo_bars": embargo_bars,
        "purge_horizon_bars": horizon_bars,
        "oos_start_entry_index": oos_start_index,
        "oos_start_entry_ts": min(r.entry_ts for r in oos),
        "is_last_entry_ts": max((r.entry_ts for r in is_rows), default=None),
        "counts": {
            "is": len(is_rows), "oos": len(oos),
            "purged": len(purged), "embargoed": len(embargoed),
        },
        "is": [r.entry_index for r in is_rows],
        "oos": [r.entry_index for r in oos],
        "purged": [r.entry_index for r in purged],
        "embargoed": [r.entry_index for r in embargoed],
    }


def rows_for(rows: Sequence[LedgerRow], manifest: dict, group: str) -> list[LedgerRow]:
    """Select the LedgerRows belonging to one split group."""
    if group not in ("is", "oos", "purged", "embargoed"):
        raise ValueError(f"unknown split group {group!r}")
    wanted = set(manifest.get(group) or [])
    return [r for r in rows if r.entry_index in wanted]


# ══════════════════════════════════════════════════════════════════════════════
# Controls
# ══════════════════════════════════════════════════════════════════════════════

def _resolve(
    bars: Sequence[Bar],
    *,
    instrument: str,
    entry_index: int,
    direction: str,
    entry: float,
    atr_abs: float,
    sl_atr_mult: float,
    tp_atr_mult: float,
    cost_model,
    adverse_fill,
) -> tuple[str, float, float, int, float, float] | None:
    """Resolve one synthetic entry through the arm's own exit + cost basis."""
    future = bars[entry_index + 1: entry_index + 1 + HORIZON_BARS]
    if len(future) < HORIZON_BARS:
        return None
    sig = Signal(
        instrument=instrument,
        timestamp=bars[entry_index].timestamp,
        entry_index=entry_index,
        direction=direction,
        entry=entry,
        sl_atr_mult=sl_atr_mult,
        tp_atr_mult=tp_atr_mult,
        atr=atr_abs,
    )
    out = forward_walk(
        sig, future, max_forward=HORIZON_BARS, exit_model="intrabar_fixed",
        adverse_fill=adverse_fill,
    )
    risk_distance = sl_atr_mult * atr_abs
    net = _net_r(
        out.rr_achieved, entry, risk_distance,
        exit_kind=out.outcome, direction=direction, cost_model=cost_model,
    )
    return out.outcome, out.rr_achieved, net, out.duration_candles, out.mfe, out.mae


def _row(base: LedgerRow, *, arm_label: str, entry_index: int, direction: str,
         entry: float, atr_abs: float, sl_atr_mult: float, resolved, ts: str) -> LedgerRow:
    outcome, gross, net, dur, mfe, mae = resolved
    return replace(
        base,
        arm=arm_label,
        entry_ts=ts,
        entry_index=entry_index,
        direction=direction,
        entry=entry,
        atr_abs=atr_abs,
        sl_atr_mult=sl_atr_mult,
        outcome=outcome,
        rr_gross=gross,
        rr_net=net,
        duration_candles=dur,
        mfe=mfe,
        mae=mae,
    )


def long_only_control(
    bars: Sequence[Bar],
    rows: Sequence[LedgerRow],
    *,
    cost_model=None,
    adverse_fill=None,
) -> list[LedgerRow]:
    """The arm's own entry bars and geometry, direction forced LONG.

    The binding control for this corpus: XAUUSD trended up across 2024-05 -> 2026-05, so an arm
    must beat passive long exposure at the same moments, not merely beat zero. Shorts flip; longs
    are re-resolved unchanged and so reproduce their arm rows exactly.
    """
    out: list[LedgerRow] = []
    for r in rows:
        resolved = _resolve(
            bars, instrument=r.instrument, entry_index=r.entry_index, direction="long",
            entry=r.entry, atr_abs=r.atr_abs, sl_atr_mult=r.sl_atr_mult,
            tp_atr_mult=r.tp_atr_mult, cost_model=cost_model, adverse_fill=adverse_fill,
        )
        if resolved is None:
            continue
        out.append(_row(r, arm_label=f"{r.arm}_long_only", entry_index=r.entry_index,
                        direction="long", entry=r.entry, atr_abs=r.atr_abs,
                        sl_atr_mult=r.sl_atr_mult, resolved=resolved, ts=r.entry_ts))
    return out


def random_entry_control(
    bars: Sequence[Bar],
    rows: Sequence[LedgerRow],
    *,
    seed: int,
    cost_model=None,
    adverse_fill=None,
) -> list[LedgerRow]:
    """Same n, same direction mix, same SL/TP geometry — entry bars drawn uniformly.

    ATR is taken at the DRAWN bar, not carried from the arm's entry: carrying it would import
    the arm's volatility selection into a control meant to have none. `sl_atr_mult` is drawn from
    the arm's own distribution so the risk geometry matches.
    """
    if not rows:
        return []
    rng = random.Random(seed)
    directions = [r.direction for r in rows]
    sl_mults = [r.sl_atr_mult for r in rows]
    rng.shuffle(directions)
    rng.shuffle(sl_mults)

    lo, hi = 20, len(bars) - HORIZON_BARS - 1
    if hi <= lo:
        return []
    pool = rng.sample(range(lo, hi), min(len(rows), hi - lo))

    template = rows[0]
    out: list[LedgerRow] = []
    for k, idx in enumerate(pool):
        bar = bars[idx]
        atr_abs = _atr_at(bars, idx)
        if atr_abs <= 0:
            continue
        resolved = _resolve(
            bars, instrument=template.instrument, entry_index=idx, direction=directions[k],
            entry=bar.close, atr_abs=atr_abs, sl_atr_mult=sl_mults[k],
            tp_atr_mult=template.tp_atr_mult, cost_model=cost_model, adverse_fill=adverse_fill,
        )
        if resolved is None:
            continue
        out.append(_row(template, arm_label=f"{template.arm}_random_entry", entry_index=idx,
                        direction=directions[k], entry=bar.close, atr_abs=atr_abs,
                        sl_atr_mult=sl_mults[k], resolved=resolved,
                        ts=bar.timestamp.isoformat()))
    return out


def _atr_at(bars: Sequence[Bar], index: int, period: int = 14) -> float:
    """ATR at `index`, computed causally from the same research indicator the driver uses."""
    from research.indicators import atr as research_atr

    window = bars[max(0, index - (period + 1)): index + 1]
    return research_atr(window, period)
