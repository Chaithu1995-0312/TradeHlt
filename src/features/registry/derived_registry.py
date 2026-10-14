"""Derived registry — deterministic normalized metrics (ATR/price-relative). Maps declared impl
names to the immutable derived_math callables (NO eval), and dispatches by declared signature.
Internal module."""
from __future__ import annotations

import inspect
from typing import Callable

from features import candle_patterns as _candle_patterns
from features import derived_math
from features.registry._loader import load_ontology
from features.smc import breaker as _smc_breaker
from features.smc import fvg as _smc_fvg
from features.smc import levels as _smc_levels
from features.smc import mitigation as _smc_mitigation
from features.reward_bracket import reward_risk_clears
from features.smc import order_block as _smc_order_block
from features.smc import rejection as _smc_rejection

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
    # FM-096 (2026-10-08, CH-feature-semantic-fixes-v7): signed retracement, selected over FM-027
    # by `setup.retrace_semantics`.
    "derived_math.displacement_retrace_signed": derived_math.displacement_retrace_signed,
    # GD-004 closure 2026-07-11: scoring_engine's as-wired breakout displacement input (FM-029).
    "derived_math.disp_strength_atr_rescale": derived_math.disp_strength_atr_rescale,
    # FM-030/031 (2026-07-22): scale-invariant corrections of FM-022/FM-023, selected by
    # `feature_pipeline.normalization_basis`. Registered so the identity is executable and
    # parity-testable; ontology entries stay `active: false` (no production authority, §6.5).
    "derived_math.ema_spread_atr":            derived_math.ema_spread_atr,
    "derived_math.momentum_score_atr":        derived_math.momentum_score_atr,
    # FM-070 (2026-07-31): CRT engine's live bars-since-retest-candle count, registered to
    # resolve the FM-065 candles_since_sweep name collision (see that entry's note).
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
    # FM-097..FM-102 (2026-10-08, CH-feature-semantic-fixes-v7, schema v7.0): zone/cluster
    # presence flags, separating "no zone" from "price on the zone edge" (both 0.0 in *_distance).
    "features.smc.order_block.order_block_present":   _smc_order_block.order_block_present,
    "features.smc.fvg.fvg_present":                   _smc_fvg.fvg_present,
    "features.smc.breaker.breaker_present":           _smc_breaker.breaker_present,
    "features.smc.mitigation.mitigation_block_present": _smc_mitigation.mitigation_block_present,
    "features.smc.levels.eqh_eql_present":            _smc_levels.eqh_eql_present,
    # FM-103..FM-119 (2026-10-08, CH-candle-pattern-observations-v8, schema v8.0): candle-pattern
    # observations. Per-bar scalar identities; the pipeline's vectorized mirror
    # (candle_patterns.compute_all) is parity-bound by tests/test_candle_patterns.py.
    **{f"features.candle_patterns.{_n}": getattr(_candle_patterns, _n)
       for _n in _candle_patterns.PATTERN_COLUMNS},
    # FM-120 (CH-card-identity-census-v9): morning star is a candle-geometry identity and is
    # not a member of PATTERN_COLUMNS (slots 54-70 stay that tuple; morning_star is slot 71).
    "features.candle_patterns.morning_star": _candle_patterns.morning_star,
    # FM-124..127: live rejection-block presence and distance.
    "features.smc.rejection.rejection_bull_present": _smc_rejection.rejection_bull_present,
    "features.smc.rejection.rejection_bear_present": _smc_rejection.rejection_bear_present,
    "features.smc.rejection.rejection_bull_distance": _smc_rejection.rejection_bull_distance,
    "features.smc.rejection.rejection_bear_distance": _smc_rejection.rejection_bear_distance,
    # FM-129: card reward:risk bracket. Not the live min_rr_ratio gate.
    "features.reward_bracket.reward_risk_clears": reward_risk_clears,
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
