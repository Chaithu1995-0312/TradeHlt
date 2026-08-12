"""Composition registry — trading-interpretation ratios (numerator/denominator over primitives).
Executes declared compositions via named callables (NO eval). Internal module."""
from __future__ import annotations

import inspect
from typing import Callable

from features.registry._loader import load_ontology
from features.registry.primitive_registry import PRIMITIVE_SHORTNAME


def _primitive_arity(o: float, h: float, l: float, c: float, fn: Callable) -> float:
    """Call a primitive with whichever of (open, high, low, close) its signature needs."""
    params = list(inspect.signature(fn).parameters)
    argmap = {"open_": o, "high": h, "low": l, "close": c}
    return fn(*[argmap[p] for p in params])


def compute_composition(name: str, open_: float, high: float, low: float, close: float,
                        ontology: dict | None = None) -> float:
    """
    Compute a declared feature composition (e.g. body_ratio) from OHLC via the registry.

    numerator / denominator, bounded to the declared range when present. Denominator <= 0
    returns 0.0 (matches the candle_math / pipeline guard). Raises KeyError for an unknown
    composition or an unresolvable primitive reference.
    """
    ont = ontology or load_ontology()
    comp = ont["feature_compositions"][name]
    num_fn = PRIMITIVE_SHORTNAME[comp["numerator"]]
    den_fn = PRIMITIVE_SHORTNAME[comp["denominator"]]
    num = _primitive_arity(open_, high, low, close, num_fn)
    den = _primitive_arity(open_, high, low, close, den_fn)
    val = num / den if den > 0 else 0.0
    bounds = comp.get("bounded")
    if bounds:
        lo, hi = bounds
        val = max(lo, min(hi, val))
    return val
