"""Market CONDITIONS: per-bar truths that persist until a defined market change.

    MKT-C01 structural_position     = FM-057 break_of_structure (what that slot actually measures)
    MKT-C04 two_sided_sweep{W}      = FM-060 double_sweep (W identity-bearing)
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
TWO_SIDED_SWEEP = "MKT-C04"
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
    """FM-060: swing-founded sweeps of BOTH sides within the last `window` bars.

    Reuses `causal_structure_series` verbatim, so the FM-058 inclusive tie (`close <= ref`) is
    inherited — a recorded divergence from GP-04 (strict), affecting ~0.40% of sweep bars.
    """
    s = _series(highs, lows, closes, k=k, window=window)
    ref_h, ref_l = _refs_as_of_previous(s)
    vals = []
    for i, v in enumerate(s["double_sweep"]):
        if ref_h[i] == 0.0 and ref_l[i] == 0.0:
            vals.append(None)   # fewer than one reference level = UNDEFINED
        else:
            vals.append(bool(v))
    pid = parameterization_id(TWO_SIDED_SWEEP, {"k": int(k), "window": int(window)}, ("k", "window"))
    return ConditionSeries(
        TWO_SIDED_SWEEP, pid, tuple(vals), parameters=(("k", int(k)), ("window", int(window))),
    )


def break_against_momentum(position: Optional[StructuralPosition], momentum_bias: Optional[int]) -> Optional[int]:
    """FM-083 meaning: a non-INSIDE structural position whose sign opposes momentum_bias.

    Delegates to `features.smc.choch.change_of_character`. This is NOT the conventional CHoCH;
    MKT-E03 `choch` stays PROPOSED with no representation (I-18).
    """
    if position is None or momentum_bias is None:
        return None
    return int(change_of_character(float(position), float(momentum_bias)))
