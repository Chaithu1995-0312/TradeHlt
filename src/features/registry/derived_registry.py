"""Derived registry — deterministic normalized metrics (ATR/price-relative). Maps declared impl
names to the immutable derived_math callables (NO eval), and dispatches by declared signature.
Internal module."""
from __future__ import annotations

import inspect
from typing import Callable

from features import derived_math
from features.registry._loader import load_ontology
from features.smc import breaker as _smc_breaker
from features.smc import fvg as _smc_fvg
from features.smc import levels as _smc_levels
from features.smc import mitigation as _smc_mitigation
from features.smc import order_block as _smc_order_block

# Declared impl name (derived_metrics.<name>.impl in the ontology) -> explicit callable.
DERIVED: dict[str, Callable] = {
    "derived_math.disp_strength":            derived_math.disp_strength,
    "derived_math.retest_depth":             derived_math.retest_depth,
    "derived_math.ema_spread":               derived_math.ema_spread,
    "derived_math.momentum_score":           derived_math.momentum_score,
    "derived_math.volatility_ratio":         derived_math.volatility_ratio,
    "derived_math.liquidity_distance":       derived_math.liquidity_distance,
    "derived_math.liquidity_pressure_score": derived_math.liquidity_pressure_score,
    # F-050 remediation CH-001: the two formerly name-colliding CRT quantities, now first-class.
    "derived_math.displacement_retrace":     derived_math.displacement_retrace,
    "derived_math.displacement_atr_ratio":   derived_math.displacement_atr_ratio,
    # GD-004 closure 2026-07-11: scoring_engine's as-wired breakout displacement input (FM-029).
    "derived_math.disp_strength_atr_rescale": derived_math.disp_strength_atr_rescale,
    # FM-030/031 (2026-07-22): scale-invariant corrections of FM-022/FM-023, selected by
    # `feature_pipeline.normalization_basis`. Registered so the identity is executable and
    # parity-testable; ontology entries stay `active: false` (no production authority, §6.5).
    "derived_math.ema_spread_atr":            derived_math.ema_spread_atr,
    "derived_math.momentum_score_atr":        derived_math.momentum_score_atr,
    # FM-070 (2026-07-31): CRT engine's live bars-since-retest-candle count, registered to
    # resolve the FM-065 candles_since_retest name collision (see that entry's note).
    "derived_math.candles_since_retest_state": derived_math.candles_since_retest_state,
    # FM-075..FM-082 (2026-08-15, CH-htfcrt-parent-candle-smc-v1): the 8 SMC distance
    # primitives. Unlike every entry above, these are NOT in derived_math — they live in the
    # isolated features.smc package (pure, window-based Candle scanners; see that package's
    # __init__.py LAYERING/isolation note). Registered here by their real qualified impl path
    # so FORMULA_REGISTRY resolution works identically to every other derived_metrics entry.
    "features.smc.order_block.order_block_distance": _smc_order_block.order_block_distance,
    "features.smc.fvg.fvg_distance":                  _smc_fvg.fvg_distance,
    "features.smc.breaker.breaker_distance":          _smc_breaker.breaker_distance,
    "features.smc.mitigation.mitigation_block_distance": _smc_mitigation.mitigation_block_distance,
    "features.smc.levels.pdh_pdl_distance":           _smc_levels.pdh_pdl_distance,
    "features.smc.levels.eqh_eql_distance":           _smc_levels.eqh_eql_distance,
}


def compute_derived(name: str, ontology: dict | None = None, **inputs) -> float:
    """
    Compute a declared derived metric by name via the registry (NO eval).

    `inputs` are matched to the impl's signature by parameter name. For a variadic impl
    (e.g. liquidity_distance(close, atr, *levels)) pass the tail as `levels=[...]`.
    """
    ont = ontology or load_ontology()
    entry = ont["derived_metrics"][name]
    fn = DERIVED[entry["impl"]]
    sig = inspect.signature(fn)
    has_var = any(p.kind == p.VAR_POSITIONAL for p in sig.parameters.values())
    if has_var:
        fixed = [inputs[p.name] for p in sig.parameters.values()
                 if p.kind == p.POSITIONAL_OR_KEYWORD and p.name in inputs]
        return fn(*fixed, *inputs.get("levels", []))
    kwargs = {p: inputs[p] for p in sig.parameters if p in inputs}
    return fn(**kwargs)
