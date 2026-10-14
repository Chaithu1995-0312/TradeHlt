"""1.5×ATR stop floor for the research walker. Not an engine key.

Widens the stop only when the structural distance is strictly inside the floor,
then rebuilds TP1/TP2 from the multipliers already on that trade.
"""

from __future__ import annotations

FLOOR_ATR_MULT = 1.5


def _side(direction: str) -> str:
    name = str(direction).strip().lower()
    if name in ("long", "buy"):
        return "long"
    if name in ("short", "sell"):
        return "short"
    raise ValueError(f"direction must be long or short, got {direction!r}")


def apply_stop_floor(
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    atr: float,
    direction: str,
) -> dict:
    """Return the primary-arm prices. `floored` is false when the stop already clears."""
    side = _side(direction)
    entry = float(entry)
    sl = float(sl)
    tp1 = float(tp1)
    tp2 = float(tp2)
    atr = float(atr)
    risk = abs(entry - sl)
    if atr <= 0:
        raise ValueError(f"apply_stop_floor: atr must be positive, got {atr}")
    if risk <= 0:
        raise ValueError(f"apply_stop_floor: risk distance must be positive, got {risk}")
    floor = FLOOR_ATR_MULT * atr
    tp1_mult = abs(tp1 - entry) / risk
    tp2_mult = abs(tp2 - entry) / risk
    if risk >= floor:
        return {
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "risk": risk,
            "atr": atr,
            "floored": False,
            "tp1_mult": tp1_mult,
            "tp2_mult": tp2_mult,
            "direction": side,
        }
    new_risk = floor
    if side == "long":
        new_sl = entry - new_risk
        new_tp1 = entry + tp1_mult * new_risk
        new_tp2 = entry + tp2_mult * new_risk
    else:
        new_sl = entry + new_risk
        new_tp1 = entry - tp1_mult * new_risk
        new_tp2 = entry - tp2_mult * new_risk
    return {
        "entry": entry,
        "sl": new_sl,
        "tp1": new_tp1,
        "tp2": new_tp2,
        "risk": new_risk,
        "atr": atr,
        "floored": True,
        "tp1_mult": tp1_mult,
        "tp2_mult": tp2_mult,
        "direction": side,
    }
