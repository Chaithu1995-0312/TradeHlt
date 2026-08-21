"""features.smc.fvg — Fair Value Gap (FVG) / imbalance detection.

Definition (standard ICT/SMC, 3-candle test): a BULLISH FVG exists at position `i` (the middle
candle of the three) when `bars[i-1].high < bars[i+1].low` — the gap zone is
`[bars[i-1].high, bars[i+1].low]`. A BEARISH FVG exists when `bars[i-1].low > bars[i+1].high`,
gap zone `[bars[i+1].high, bars[i-1].low]`. This is the primitive `market_reality_v1.yaml`
records as GENUINELY_ABSENT (`temporal_derivations.fair_value_gap`, `dimensions.imbalance`) —
both blockers close with this module.

An FVG is FILLED (mitigated) once price trades back through any part of the gap zone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from features.smc._geometry import Zone, is_mitigated, signed_atr_distance

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle


def _find_fvg_events(bars: "Sequence[Candle]") -> list[Zone]:
    """All FVG zones formed in `bars`, oldest-first, regardless of fill status. A 3-candle
    test evaluated at every interior position — no lookahead beyond the candle immediately
    after the middle one, which by construction is already CLOSED once the middle candle's own
    gap becomes detectable (the test needs `bars[i+1]` to exist)."""
    zones: list[Zone] = []
    n = len(bars)
    for i in range(1, n - 1):
        prev_high, prev_low = bars[i - 1].high, bars[i - 1].low
        next_high, next_low = bars[i + 1].high, bars[i + 1].low
        if prev_high < next_low:
            zones.append(Zone(high=next_low, low=prev_high, formed_at_index=bars[i].index, bullish=True))
        elif prev_low > next_high:
            zones.append(Zone(high=prev_low, low=next_high, formed_at_index=bars[i].index, bullish=False))
    return zones


def find_active_fvg(window: "Sequence[Candle]") -> Optional[Zone]:
    """The most recent UNFILLED FVG as of `window[-1]`. Pure; only inspects `window`."""
    bars = list(window)
    if len(bars) < 3:
        return None
    zones = _find_fvg_events(bars)
    for zone in reversed(zones):
        # Bars strictly after the gap's formation (the zone forms once bars[i+1] exists, so
        # mitigation can only come from bars[i+2:] onward relative to the middle candle — find
        # that position by index).
        formed_pos = next((p for p, b in enumerate(bars) if b.index == zone.formed_at_index), None)
        if formed_pos is None:
            continue
        later = bars[formed_pos + 2:]   # the gap-closing candle itself (i+1) does not "fill" it
        mitigated = any(is_mitigated(zone, b) for b in later)
        if not mitigated:
            return zone
    return None


def fvg_distance(window: "Sequence[Candle]", atr: float) -> float:
    """Signed, ATR-normalized, tanh-bounded distance from `window[-1].close` to the nearest
    active (unfilled) FVG's near edge. `0.0` if none exists."""
    zone = find_active_fvg(window)
    if zone is None:
        return 0.0
    close = window[-1].close
    if zone.bullish:
        return signed_atr_distance(close, zone.high, atr, favorable_sign=1)
    return signed_atr_distance(close, zone.low, atr, favorable_sign=-1)
