"""features.smc.choch — Change of Character (CHoCH).

Definition (standard ICT/SMC): a break-of-structure event that goes AGAINST the prevailing
trend is a "change of character" (a potential reversal signal); a break-of-structure event that
agrees with the prevailing trend is ordinary continuation (BOS, not CHoCH).

`configs/formulas/market_ontology.yaml:32` explicitly excludes "detection state-machines
(BOS/CHOCH/pivot)" from the ontology layer. This module does NOT reopen that exclusion — it
adds NO new detection state machine and does NO swing/pivot scanning of its own. It is a pure,
stateless algebraic combination of two ALREADY-REGISTERED canonical structural-state features
(`break_of_structure` FM-057, `trend_bias` FM-054), exactly like the ontology's existing
`derived_metrics` computation class combines other registered primitives. The distinction
matters: the exclusion is about NOT building a new BOS/CHoCH state machine in the ontology
layer; reusing the existing, already-governed BOS output is a different, smaller act.
"""

from __future__ import annotations


def change_of_character(break_of_structure: float, trend_bias: float) -> float:
    """Signed {-1, 0, +1}: the direction of a genuine character change, or 0.0 when there is
    no break event, no defined trend to change FROM (`trend_bias == 0`), or the break agrees
    with the prevailing trend (ordinary BOS continuation, not CHoCH).

    `break_of_structure` and `trend_bias` are expected in the same {-1, 0, +1}-ish signed
    convention the canonical vector already uses for both features."""
    if break_of_structure == 0 or trend_bias == 0:
        return 0.0
    if (break_of_structure > 0) != (trend_bias > 0):
        return break_of_structure
    return 0.0
