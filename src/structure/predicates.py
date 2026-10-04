"""
Structural decision predicates — HOW-COMPUTATION for SP-001 / SP-002.

**THIS MODULE IS NOT THE SEMANTIC AUTHORITY.** (Demoted 2026-08-19, RC-5.)

The MEANING of these predicates is declared as data in
`configs/formulas/market_ontology.yaml` under `structural_predicates.<name>.definition`,
and interpreted by `features.registry.predicate_registry`. This module is a *conforming
implementation* of that declaration — fast, scalar, importable from the decision path — and
`tests/test_predicate_definition_binding.py` FAILS if the two ever disagree.

Why the distinction is load-bearing: an earlier pass unified nine copies of this arithmetic
behind these functions and called the problem solved. That made the nine sites agree with
*each other*, but nothing made them agree with the *declared* meaning, because the meaning
was a prose string. Centralizing code is not centralizing meaning. If you need to change what
"swept" means, change the ontology `definition` block — then make this file conform.

MECHANISM, NOT POLICY. These are the elementary boolean tests the CRT construction is built
from. Like `features/candle_math.py` (the precedent this module deliberately mirrors, see
F-046), they are mathematical identities over OHLC and a reference level — not trading
interpretations. They live in code, are never configurable, and are never `eval`'d.

WHY THIS MODULE EXISTS
----------------------
The boundary-sweep test was written out longhand in NINE places and the F-074 directional
impulse in THREE. Every copy's docstring asserted it "mirrors" the engine, and nothing
checked that it still did — so when F-074 landed (2026-08-13) the fix had to be
hand-propagated to three files. A geometry fix was a manual broadcast.

    ONTOLOGY (WHAT — the authority)          THIS MODULE (HOW — conforms to it)
    SP-001 swept_boundary.definition  ────>  swept_high / swept_low
    SP-002 directional_impulse.definition ─> directional_impulse
    SP-003 retest_band                ────>  none — definition DEFERRED on OQ7
                                             (signed-vs-abs depth unresolved)

WHAT THIS MODULE DOES *NOT* OWN
-------------------------------
1. **The founding.** WHICH reference level counts as liquidity — an M15 structural range, a
   parent candle, a weekly calendar range, a chart-visible pool — is supplied by the caller
   and stays deliberately pluggable. That independence is what made F-042 and F-081
   legitimately NEW ontologies rather than re-runs of the incumbent; unifying the arithmetic
   must never collapse it.

2. **The FM-058 feature family.** `liquidity_sweep` / `sweep_detected` / `double_sweep`
   (`feature_pipeline.compute_structure_liquidity`) are a DIFFERENT QUANTITY that merely
   shares the English word "sweep": they reference a swing pivot
   (`last_swing_high_price.shift(1)`) and use an INCLUSIVE boundary (`close <= ref`), where
   these predicates reference a founding range and use a STRICT one (`close < ref`). The
   repository already treats the two as selectable alternatives —
   `market_crt_states.yaml: thresholds.sweep_geometry` ∈ {`htf_range`, `pipeline_swing`}.
   Routing the feature family through here would silently redefine a registered feature and
   move the 48-dim vector. Do not.

3. **Magnitude gating.** `body_ratio_min`, `atr_min_displacement`, `atr_multiplier_min`,
   `max_sweep_age_candles` are CALLER-APPLIED parameters, not part of the direction
   contract. This is why the three impulse call sites are not identical and are still
   correct: `parent_crt` deliberately applies no magnitude gate at all.

All functions are scalar, pure, and total: no config reads, no I/O, no state, no logging,
no defaults. A silent default here would be the config-illusion class F-056 documented.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────
# SP-001 — swept_boundary
# ─────────────────────────────────────────────────────────────────

def swept_high(high: float, close: float, h_ref: float) -> bool:
    """Buy-side liquidity taken: traded ABOVE `h_ref` but closed back BELOW it.

    Strict on both sides. A bar that merely touches `h_ref`, or that closes exactly at it,
    is NOT a sweep — it has not demonstrated rejection. (The FM-058 feature family makes the
    opposite choice, `close <= ref`; see the module docstring. Different quantity.)

    Direction convention: sweeping a HIGH implies SHORT.
    """
    return high > h_ref and close < h_ref


def swept_low(low: float, close: float, l_ref: float) -> bool:
    """Sell-side liquidity taken: traded BELOW `l_ref` but closed back ABOVE it.

    Mirror of `swept_high`. Direction convention: sweeping a LOW implies LONG.
    """
    return low < l_ref and close > l_ref


# ─────────────────────────────────────────────────────────────────
# SP-002 — directional_impulse (the F-074 contract)
# ─────────────────────────────────────────────────────────────────

def directional_impulse(
    open_: float,
    close: float,
    sweep_price: float,
    *,
    is_long: bool,
) -> bool:
    """The F-074 directional displacement contract (user-authorized 2026-08-13).

    The impulse must travel AWAY from the swept side, on its own body, and CLEAR the level
    that was swept:

        LONG  (a low was swept):  close > open  AND  close > sweep_price
        SHORT (a high was swept): close < open  AND  close < sweep_price

    Unsigned energy-only displacement is not legal — a large bar in the wrong direction is a
    rejection of the setup, not a confirmation of it. This is what F-074 changed.

    `is_long` is INHERITED from the sweep that produced `sweep_price`; it is never re-derived
    from this bar. Re-deriving it would reintroduce the exact defect F-074 closed.

    Magnitude gates (body quality, ATR-relative size, sweep age) are the CALLER's and are
    deliberately absent here — see the module docstring.
    """
    if is_long:
        return close > open_ and close > sweep_price
    return close < open_ and close < sweep_price
