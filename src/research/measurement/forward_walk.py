"""forward_walk.py — no-lookahead forward simulation of a Signal.

Lifted from `scripts/research/opportunity_scanner.py:_simulate` (trailing-stop
convention preserved verbatim so research RR matches the existing backtest), then
extended with `time_to_tp`, `time_to_failure`, and `reached_1r` for edge discovery.

NO-LOOKAHEAD GUARANTEE
----------------------
`forward_walk` receives ONLY the bars strictly after the signal's entry — the caller
slices `candles[entry_index+1:]`. The function additionally asserts every supplied bar
has `.index > signal.entry_index`; a bar at/before the entry raises ValueError. The
entry bar itself is never visible, so a hypothesis cannot leak its own bar's outcome.

The conservative tie-break matches the backtest: if a single bar touches both the
trailing stop and TP, the stop (SL) wins — unless the stop has already trailed past TP,
in which case price must have crossed TP first, so TP is honoured.
"""

from __future__ import annotations

import dataclasses
from typing import Sequence

from research.contracts import Outcome, Signal


def forward_walk(
    signal: Signal,
    future: Sequence,            # bars strictly after entry_index; each has .high/.low/.close/.index
    *,
    max_forward: int = 40,
    trail_mult: float = 0.5,
    exit_model: str = "intrabar_fixed",
) -> Outcome:
    """Forward-walk `future` bars; return a measured Outcome.

    Exit geometry is intrabar high/low touch with a conservative SL-before-TP tie-break
    in BOTH modes (matches `CRTEngine._intrabar_trigger_price` / the governed spine truth).

    Args:
        signal: the candidate event. SL/TP are derived from its ATR multiples.
        future: ordered bars AFTER the entry bar (index strictly > signal.entry_index).
        max_forward: cap on bars simulated (timeout horizon).
        trail_mult: trailing-stop activation distance as a fraction of risk_distance
            (used only when exit_model == "trailing").
        exit_model: "intrabar_fixed" (GOVERNING truth — fixed SL + TP, intrabar wick touch,
            no ratchet); "trailing" (opt-in legacy — stop ratchets toward price); or
            "close_only" (MEASURE-ONLY forensic bound — fixed SL/TP triggered only when
            bar.close crosses the level, never a wick touch; the optimistic counterfactual).
    """
    direction = signal.direction
    entry = signal.entry
    risk_distance = signal.sl_atr_mult * signal.atr
    reward_distance = signal.tp_atr_mult * signal.atr

    if risk_distance <= 0:
        raise ValueError(f"forward_walk: non-positive risk_distance ({risk_distance})")
    if direction not in ("long", "short"):
        raise ValueError(f"forward_walk: bad direction '{direction}'")
    if exit_model not in ("intrabar_fixed", "trailing", "close_only"):
        raise ValueError(f"forward_walk: bad exit_model '{exit_model}'")

    if direction == "long":
        sl = entry - risk_distance
        tp = entry + reward_distance
    else:
        sl = entry + risk_distance
        tp = entry - reward_distance

    trail_dist = trail_mult * risk_distance
    trail_stop = sl            # starts at original SL price
    peak = entry               # most favorable price seen
    mfe = 0.0                  # max favorable excursion (price units, >= 0)
    mae = 0.0                  # max adverse excursion (price units, <= 0)
    duration = 0
    time_to_tp: int | None = None

    bars = list(future)[:max_forward]

    for i, bar in enumerate(bars):
        # No-lookahead guard: forward bars must come strictly after the entry bar.
        if getattr(bar, "index", signal.entry_index + 1) <= signal.entry_index:
            raise ValueError(
                f"forward_walk lookahead: bar index {getattr(bar, 'index', None)} "
                f"<= entry_index {signal.entry_index}"
            )

        high = float(bar.high)
        low = float(bar.low)
        duration = i + 1

        close = float(bar.close)
        if direction == "long":
            peak = max(peak, high)
            if exit_model == "trailing" and peak >= entry + trail_dist:
                trail_stop = max(trail_stop, peak - trail_dist)
            unrealized_hi = high - entry
            unrealized_lo = low - entry
            # close_only: trigger on the bar CLOSE crossing the level (optimistic bound,
            # measure-only). intrabar_fixed/trailing: trigger on the wick touch (governing).
            if exit_model == "close_only":
                sl_hit = close <= trail_stop
                tp_hit = close >= tp
            else:
                sl_hit = low <= trail_stop
                tp_hit = high >= tp
        else:
            peak = min(peak, low)
            if exit_model == "trailing" and peak <= entry - trail_dist:
                trail_stop = min(trail_stop, peak + trail_dist)
            unrealized_hi = entry - low
            unrealized_lo = entry - high
            if exit_model == "close_only":
                sl_hit = close >= trail_stop
                tp_hit = close <= tp
            else:
                sl_hit = high >= trail_stop
                tp_hit = low <= tp

        if unrealized_hi > mfe:
            mfe = unrealized_hi
        if unrealized_lo < mae:
            mae = unrealized_lo
        if tp_hit and time_to_tp is None:
            time_to_tp = duration

        if sl_hit:
            # If the trail has moved past TP, price crossed TP first — honour TP.
            trail_past_tp = (
                (direction == "long" and trail_stop >= tp)
                or (direction == "short" and trail_stop <= tp)
            )
            if trail_past_tp:
                rr = reward_distance / risk_distance
                return _result(signal, "TP_HIT", rr, mfe, mae, duration,
                               time_to_tp, None, risk_distance)
            rr = ((trail_stop - entry) if direction == "long" else (entry - trail_stop)) / risk_distance
            return _result(signal, "SL_HIT", rr, mfe, mae, duration,
                           time_to_tp, duration, risk_distance)

        if tp_hit:
            rr = reward_distance / risk_distance
            return _result(signal, "TP_HIT", rr, mfe, mae, duration,
                           time_to_tp, None, risk_distance)

    # Timeout: mark-to-last-close.
    if not bars:
        unrealized = 0.0
    else:
        last_close = float(bars[-1].close)
        unrealized = (last_close - entry) if direction == "long" else (entry - last_close)
    rr = unrealized / risk_distance
    return _result(signal, "TIMEOUT", rr, mfe, mae, duration,
                   time_to_tp, None, risk_distance)


def forward_walk_oco(
    signal: Signal,
    future: Sequence,            # bars strictly after entry_index; each has .high/.low/.close/.index
    *,
    max_forward: int = 40,
    entry_ttl: int = 12,
    trail_mult: float = 0.5,
    exit_model: str = "intrabar_fixed",
) -> Outcome | None:
    """Both-sided stop-entry straddle (OCO) walk — Program 9's non-directional consumer.

    ADDITIVE by design: the legacy `forward_walk` above is byte-untouched; every filled
    straddle DELEGATES its post-fill bars to that unchanged function, so exit truth is
    the same audited kernel. Contract: `signal.direction == "oco"` with the box edges in
    `signal.meta["box_high"]` / `signal.meta["box_low"]`. `signal.entry` is telemetry
    only (e.g. box midpoint) — the real entry is the touched edge.

    Frozen pre-registration decisions (docs/research/preregistration-program-9.md):
      D1 — if BOTH edges are touched within one pending bar, the straddle is CANCELLED
           (returns None): the intrabar touch order is unknowable, inventing one is
           lookahead.
      D2 — on the fill bar, SL is checked by full-range wick touch but TP is NEVER
           credited (fill-touch vs TP-touch order unknowable; conservative, matches the
           kernel's SL-before-TP convention). `time_to_tp` is likewise never set from
           the fill bar.
      D3 — a straddle not filled within `entry_ttl` bars returns None (cancelled;
           excluded from n, same as no signal).

    Returned Outcome carries the RESOLVED signal (direction long/short, entry at the
    edge, entry_index = fill bar, meta["bars_to_fill"] = 1-based fill bar) with the
    fill bar merged in: duration/time_to_tp/time_to_failure offset by 1, MFE/MAE the
    max/min over fill bar + delegated walk. Same no-lookahead contract as forward_walk.
    """
    if signal.direction != "oco":
        raise ValueError(f"forward_walk_oco: bad direction '{signal.direction}' (expected 'oco')")
    if exit_model not in ("intrabar_fixed", "trailing", "close_only"):
        raise ValueError(f"forward_walk_oco: bad exit_model '{exit_model}'")
    if entry_ttl <= 0:
        raise ValueError(f"forward_walk_oco: non-positive entry_ttl ({entry_ttl})")
    try:
        box_high = float(signal.meta["box_high"])
        box_low = float(signal.meta["box_low"])
    except KeyError as e:
        raise ValueError(f"forward_walk_oco: signal.meta missing {e} (box edges required)")
    if not box_high > box_low:
        raise ValueError(f"forward_walk_oco: degenerate box (high {box_high} <= low {box_low})")
    risk_distance = signal.sl_atr_mult * signal.atr
    reward_distance = signal.tp_atr_mult * signal.atr
    if risk_distance <= 0:
        raise ValueError(f"forward_walk_oco: non-positive risk_distance ({risk_distance})")

    bars = list(future)

    # ── Phase A: pending straddle (bars 1..entry_ttl) ────────────────────────────
    fill_j: int | None = None
    direction = ""
    for j, bar in enumerate(bars[:entry_ttl]):
        if getattr(bar, "index", signal.entry_index + 1) <= signal.entry_index:
            raise ValueError(
                f"forward_walk_oco lookahead: bar index {getattr(bar, 'index', None)} "
                f"<= entry_index {signal.entry_index}")
        high, low = float(bar.high), float(bar.low)
        touched_high = high >= box_high
        touched_low = low <= box_low
        if touched_high and touched_low:
            return None                        # D1 — reject-bar: order unknowable
        if touched_high:
            fill_j, direction = j, "long"
            break
        if touched_low:
            fill_j, direction = j, "short"
            break
    if fill_j is None:
        return None                            # D3 — TTL expiry, never filled

    # ── Phase B: filled at the touched edge ──────────────────────────────────────
    fill_bar = bars[fill_j]
    entry = box_high if direction == "long" else box_low
    resolved = dataclasses.replace(
        signal, direction=direction, entry=entry, entry_index=int(fill_bar.index),
        meta={**signal.meta, "bars_to_fill": fill_j + 1, "oco_resolved": True},
    )

    high, low = float(fill_bar.high), float(fill_bar.low)
    if direction == "long":
        fill_mfe = max(0.0, high - entry)
        fill_mae = min(0.0, low - entry)
        fill_sl_hit = low <= entry - risk_distance
        sl_rr = -1.0
    else:
        fill_mfe = max(0.0, entry - low)
        fill_mae = min(0.0, entry - high)
        fill_sl_hit = high >= entry + risk_distance
        sl_rr = -1.0
    if fill_sl_hit:                            # D2 — SL honoured on the fill bar, TP never
        return Outcome(
            signal=resolved, outcome="SL_HIT", rr_achieved=round(sl_rr, 4),
            mfe=round(fill_mfe, 6), mae=round(fill_mae, 6), duration_candles=1,
            time_to_tp=None, time_to_failure=1, reached_1r=fill_mfe >= risk_distance,
        )

    # Delegate the post-fill bars to the UNCHANGED audited kernel, then merge the
    # fill bar back in (duration/time offsets +1; MFE/MAE = max/min across both).
    tail = bars[fill_j + 1:]
    oc = forward_walk(resolved, tail, max_forward=max_forward,
                      trail_mult=trail_mult, exit_model=exit_model)
    mfe = max(fill_mfe, oc.mfe)
    mae = min(fill_mae, oc.mae)
    return Outcome(
        signal=resolved,
        outcome=oc.outcome,
        rr_achieved=oc.rr_achieved,
        mfe=round(mfe, 6),
        mae=round(mae, 6),
        duration_candles=oc.duration_candles + 1,
        time_to_tp=None if oc.time_to_tp is None else oc.time_to_tp + 1,
        time_to_failure=None if oc.time_to_failure is None else oc.time_to_failure + 1,
        reached_1r=mfe >= risk_distance,
    )


def horizon_excursion(signal: Signal, future: Sequence, *, max_forward: int = 40) -> dict:
    """[forensics Layer-2] EXIT-AGNOSTIC max favorable/adverse excursion over the horizon.

    Unlike `forward_walk`, this NEVER exits on SL/TP — it walks the full `max_forward` bars and
    measures raw price geometry in R (÷ risk_distance). It isolates the information in the ENTRY
    from the exit policy: a path that would have hit SL at bar 8 but later runs to +2.5R reports
    mfe_r≈2.5 / reached_2r=True. Same no-lookahead contract as `forward_walk`.

    Returns mfe_r, mae_r, reached_{0.5,1,1.5,2,3}r, favorable_first (+1R before −0.5R adverse),
    and bars_to_first_1r (1-based bar index of the first +1R, or None)."""
    direction = signal.direction
    entry = signal.entry
    risk = signal.sl_atr_mult * signal.atr
    if risk <= 0:
        raise ValueError(f"horizon_excursion: non-positive risk_distance ({risk})")
    if direction not in ("long", "short"):
        raise ValueError(f"horizon_excursion: bad direction '{direction}'")

    mfe = 0.0
    mae = 0.0
    bars_to_first_1r: int | None = None
    first_adverse_05_bar: int | None = None
    for i, bar in enumerate(list(future)[:max_forward]):
        if getattr(bar, "index", signal.entry_index + 1) <= signal.entry_index:
            raise ValueError(
                f"horizon_excursion lookahead: bar index {getattr(bar, 'index', None)} "
                f"<= entry_index {signal.entry_index}")
        high, low = float(bar.high), float(bar.low)
        if direction == "long":
            fav, adv = high - entry, low - entry
        else:
            fav, adv = entry - low, entry - high
        if fav > mfe:
            mfe = fav
        if adv < mae:
            mae = adv
        if bars_to_first_1r is None and fav >= risk:          # mfe_r >= 1.0
            bars_to_first_1r = i + 1
        if first_adverse_05_bar is None and adv <= -0.5 * risk:  # mae_r <= -0.5
            first_adverse_05_bar = i + 1

    mfe_r, mae_r = mfe / risk, mae / risk
    favorable_first = bars_to_first_1r is not None and (
        first_adverse_05_bar is None or bars_to_first_1r <= first_adverse_05_bar)
    return {
        "mfe_r": round(mfe_r, 4), "mae_r": round(mae_r, 4),
        "reached_0_5r": mfe_r >= 0.5, "reached_1r": mfe_r >= 1.0,
        "reached_1_5r": mfe_r >= 1.5, "reached_2r": mfe_r >= 2.0, "reached_3r": mfe_r >= 3.0,
        "favorable_first": favorable_first, "bars_to_first_1r": bars_to_first_1r,
    }


def _result(signal: Signal, outcome: str, rr: float, mfe: float, mae: float,
            duration: int, time_to_tp: int | None, time_to_failure: int | None,
            risk_distance: float) -> Outcome:
    return Outcome(
        signal=signal,
        outcome=outcome,
        rr_achieved=round(float(rr), 4),
        mfe=round(float(mfe), 6),
        mae=round(float(mae), 6),
        duration_candles=duration,
        time_to_tp=time_to_tp,
        time_to_failure=time_to_failure,
        reached_1r=mfe >= risk_distance,   # favorable excursion reached 1R before exit
    )
