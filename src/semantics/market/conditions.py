"""Market CONDITIONS: per-bar truths that persist until a defined market change.

    MKT-C01 structural_position     = FM-057 break_of_structure (what that slot actually measures)
    MKT-C03 momentum_bias           = FM-054 trend_bias (EMA momentum sign, not structure)
    MKT-C04 two_sided_sweep{k,W}    = MKT-E01 events of both sides within W (contract v2; the
                                      double_sweep slot's FM-060 rule is a recorded divergence)
    MKT-C06 session{basis}          = FM-052 session (clock declared via basis)
    MKT-C07 break_against_momentum  = FM-083 change_of_character (its documented meaning)

MKT-C02 structural_trend is PROPOSED and not implemented (I-18).
Absence: a bar with no confirmed reference has value None, never 0 (I-7).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Sequence

import numpy as np

from features.causal_structure import causal_structure_series
from features.smc.choch import change_of_character

from semantics.identity import parameterization_id

STRUCTURAL_POSITION = "MKT-C01"
MOMENTUM_BIAS = "MKT-C03"
TWO_SIDED_SWEEP = "MKT-C04"
SESSION = "MKT-C06"
BREAK_AGAINST_MOMENTUM = "MKT-C07"


class StructuralPosition(IntEnum):
    BELOW_LAST_SWING_LOW = -1
    INSIDE = 0
    ABOVE_LAST_SWING_HIGH = 1


@dataclass(frozen=True)
class ConditionSeries:
    concept_id: str
    parameterization_id: str
    values: tuple            # one entry per bar; None = no reference yet (absence)
    available_at_offset: int = 0   # value at bar i is knowable at bar i + offset (0 = bar close)
    parameters: tuple = ()   # identity-bearing (name, value) pairs, for consumers such as MKT-E02

    def available_at(self, index: int) -> int:
        """I-6 `available_at` of the value at bar `index` (a series stores it as one offset)."""
        return index + self.available_at_offset


def _series(highs, lows, closes, *, k: int, window: int = 1) -> dict:
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    c = np.asarray(closes, dtype=float)
    with np.errstate(all="ignore"):
        return causal_structure_series(h, l, c, np.ones(len(h)), k=k, double_sweep_window=window)


def _refs_as_of_previous(series: dict):
    """Swing prices the BOS slot actually compared, as of t-1.

    `causal_structure` stores 'no swing yet' as 0.0 (recorded divergence). Callers treat
    both refs at 0.0 as absence. A traded price of 0.0 would collide with that sentinel.
    """
    ref_h = np.roll(series["_last_swing_high_price"], 1)
    ref_l = np.roll(series["_last_swing_low_price"], 1)
    ref_h[0] = 0.0
    ref_l[0] = 0.0
    return ref_h, ref_l


def structural_position(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
                        *, k: int) -> ConditionSeries:
    """Close relative to the last CONFIRMED swing high / low (FC1-A causal, references as of i-1).

    Reuses `causal_structure_series` (the BOS computation). Where neither reference exists yet the
    value is None — the slot's 0 conflates "inside" with "no reference" (recorded divergence).
    """
    s = _series(highs, lows, closes, k=k)
    ref_h, ref_l = _refs_as_of_previous(s)
    vals = []
    for i, b in enumerate(s["break_of_structure"]):
        if ref_h[i] == 0.0 and ref_l[i] == 0.0:   # causal_structure encodes "no swing yet" as 0.0
            vals.append(None)
        else:
            vals.append(StructuralPosition(int(b)))
    pid = parameterization_id(STRUCTURAL_POSITION, {"k": int(k)}, ("k",))
    return ConditionSeries(STRUCTURAL_POSITION, pid, tuple(vals), parameters=(("k", int(k)),))


def two_sided_sweep(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
                    *, k: int, window: int) -> ConditionSeries:
    """MKT-C04 (contract v2): an UPPER and a LOWER MKT-E01{swing_pivot(k)} event within the last
    `window` bars, bar i included.

    The events come from the MKT-L01 lifecycle walk (`events.level_lifecycle`: any ACTIVE level,
    consumed once SWEPT or BROKEN, strict GP-04), so a bar that sweeps both sides is two events and
    counts. It never reads a signed sweep slot: the v1 rule FM-060 on `liquidity_sweep` is a recorded
    divergence. UNDEFINED until at least one swing level is available (as of bar i-1).
    """
    from semantics.market.events import level_lifecycle   # events imports this module
    from semantics.market.levels import swing_levels
    from semantics.types import OhlcBar

    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    c = np.asarray(closes, dtype=float)
    levels = swing_levels(h, l, k=k)
    # GP-01/02/04 read high, low and close only; open is not an input, so it is left NaN.
    bars = [OhlcBar(float("nan"), h[i], l[i], c[i], i) for i in range(len(c))]
    life = level_lifecycle(levels, bars)
    first_level = min((lvl.available_at for lvl in levels), default=None)
    sides_per_bar = [{ev.side.value for ev in evs} for evs in life.events]
    vals = []
    for i in range(len(c)):
        if first_level is None or first_level > i - 1:
            vals.append(None)   # fewer than one reference level = UNDEFINED
            continue
        seen: set = set()
        for t in range(max(0, i - int(window) + 1), i + 1):
            seen |= sides_per_bar[t]
        vals.append(len(seen) == 2)
    pid = parameterization_id(TWO_SIDED_SWEEP, {"k": int(k), "window": int(window)}, ("k", "window"))
    return ConditionSeries(
        TWO_SIDED_SWEEP, pid, tuple(vals), parameters=(("k", int(k)), ("window", int(window))),
    )


def momentum_bias(closes: Sequence[float], *, fast: int, slow: int) -> ConditionSeries:
    """MKT-C03 = FM-054: sign(ema_fast - ema_slow), EMAs per FM-043/044 (`ewm(span, adjust=False)`).

    Momentum, not structure. The contract says "before EMA warmup = UNDEFINED" but declares no
    warmup length, so no bar is marked None here (open contract question, not a choice made here).
    """
    import pandas as pd

    c = pd.Series(np.asarray(closes, dtype=float))
    spread = (c.ewm(span=int(fast), adjust=False).mean() - c.ewm(span=int(slow), adjust=False).mean()).to_numpy()
    vals = tuple(int(np.sign(v)) for v in spread)
    params = {"ema_fast_span": int(fast), "ema_slow_span": int(slow)}
    pid = parameterization_id(MOMENTUM_BIAS, params, ("ema_fast_span", "ema_slow_span"))
    return ConditionSeries(MOMENTUM_BIAS, pid, vals, parameters=tuple(params.items()))


def session(timestamps: Sequence, *, basis: str, windows: dict) -> ConditionSeries:
    """MKT-C06 = FM-052: the session ordinal of each bar on a declared clock.

    `basis` is the identity-bearing clock (`broker_local` = the timestamp as recorded,
    `utc_corrected` = MT5 server time converted by `features.broker_clock`). `windows` is the
    FM-052 `session_windows_utc` mapping; it is required, because the classifier's no-config path
    falls back to built-in defaults. Reuses the registered FM-052 classifier
    (`features.session_classifier.classify_session_feature`); the contract rule is that classifier.
    Available at bar open.
    """
    import pandas as pd

    from features import broker_clock
    from features.session_classifier import classify_session_feature

    if basis not in ("broker_local", "utc_corrected"):
        raise ValueError(f"MKT-C06 basis {basis!r} is not declared")
    ts = pd.to_datetime(pd.Series(list(timestamps)))
    clock = broker_clock.mt5_server_to_utc(ts) if basis == "utc_corrected" else ts
    cfg = {"session_windows_utc": windows}
    vals = tuple(int(classify_session_feature(int(h), cfg)) for h in clock.dt.hour)
    pid = parameterization_id(SESSION, {"session_timestamp_basis": basis}, ("session_timestamp_basis",))
    return ConditionSeries(SESSION, pid, vals, parameters=(("session_timestamp_basis", basis),))


def break_against_momentum(position: Optional[StructuralPosition], momentum_bias: Optional[int]) -> Optional[int]:
    """FM-083 meaning: a non-INSIDE structural position whose sign opposes momentum_bias.

    Delegates to `features.smc.choch.change_of_character`. This is NOT the conventional CHoCH;
    MKT-E03 `choch` stays PROPOSED with no representation (I-18).
    """
    if position is None or momentum_bias is None:
        return None
    return int(change_of_character(float(position), float(momentum_bias)))
