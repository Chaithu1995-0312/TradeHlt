"""FM-129 reward_risk_bracket — the card's reward:risk construction.

The card diagram is 1:3: abs(target - entry) / abs(entry - stop) >= 3.
`multiple` is required. There is no silent default. A zero risk distance does not clear.

This function does not read or write ultron_risk_gate.min_rr_ratio. The live gate stays
1.5. A ratio that clears 1.5 does not thereby clear the card's multiple of 3.
"""
from __future__ import annotations


def reward_risk_clears(entry, stop, target, multiple) -> bool:
    """True when reward/risk is at least `multiple`. False when the risk distance is 0."""
    risk = abs(entry - stop)
    if risk == 0:
        return False
    return abs(target - entry) / risk >= multiple
