"""Primitive registry — the OHLC-identity layer. Maps declared primitive impl names to the
immutable candle_math callables (NO eval). Internal module: consumers import the aggregated
FORMULA_REGISTRY from the package facade, never this module directly."""
from __future__ import annotations

from typing import Callable

from features import candle_math

# Declared impl name (primitives.<name>.impl in the ontology) -> explicit callable.
PRIMITIVES: dict[str, Callable] = {
    "candle_math.body_size":    candle_math.body_size,
    "candle_math.candle_range": candle_math.candle_range,
    "candle_math.upper_wick":   candle_math.upper_wick,
    "candle_math.lower_wick":   candle_math.lower_wick,
    "candle_math.total_wick":   candle_math.total_wick,
}

# Composition numerator/denominator short-names resolve to these primitive callables.
PRIMITIVE_SHORTNAME: dict[str, Callable] = {
    "body_size":    candle_math.body_size,
    "candle_range": candle_math.candle_range,
    "upper_wick":   candle_math.upper_wick,
    "lower_wick":   candle_math.lower_wick,
    "total_wick":   candle_math.total_wick,
}
