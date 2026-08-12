"""
Magnitude state layer — Phase 2A continuous VALUE → discrete STATE (shadow only).

Promotes *already measured* continuous features into ontology-declared magnitude bands:

  O6  body_commitment     ← body_ratio          (identity bins; CRT-coherent high edge)
  O7  atr_magnitude       ← atr                 (series percentile; relative FM-041)
  O18 momentum_magnitude  ← |momentum_score|    (abs series percentile; F-061-safe)

Design rules (EPISODE_SEMANTIC_INTEGRATION_PHASE2.md):
  - No new OHLC formulas / no new indicators.
  - No thresholds hardcoded as module constants: edges come from ontology ``band_edges``.
  - FeatureStateEncoder remains a pure integer-domain interpreter; this module
    pre-discretizes continuous values, then delegates name lookup to that encoder.
  - Not on the decision spine. Nothing in core/engines imports this.

Transform vocabulary (ontology ``source_transform``):
  identity              — bin the raw continuous value against band_edges
  series_percentile     — percentile rank of value within a provided finite series, then bin
  abs_series_percentile — same on abs(value) / abs(series)  (F-061 for momentum)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from features.feature_states import FeatureStateEncoder, X_PREFIX
from features.registry import load_ontology, _ITERATED_SECTIONS

# Phase-2A identity set (must match ontology structural_states entries with band_edges).
MAGNITUDE_STATE_NAMES: tuple[str, ...] = (
    "body_commitment",
    "atr_magnitude",
    "momentum_magnitude",
)

_VALID_TRANSFORMS = frozenset(
    {"identity", "series_percentile", "abs_series_percentile"}
)


@dataclass(frozen=True)
class MagnitudeBandSpec:
    """One ontology magnitude-state identity."""

    name: str
    fm_id: str
    section: str
    source_feature: str
    source_transform: str
    band_edges: tuple[float, ...]
    n_bins: int


def bin_ordered(value: float, edges: Sequence[float]) -> int:
    """Map a finite scalar into bin index using ascending half-open edges.

    edges = [e0, e1, ..., e_{k-1}] → k+1 bins:
      0: x < e0
      1: e0 <= x < e1
      ...
      k: x >= e_{k-1}
    """
    if not math.isfinite(value):
        raise ValueError(f"bin_ordered requires finite value, got {value!r}")
    if not edges:
        raise ValueError("bin_ordered requires non-empty edges")
    prev = None
    for i, e in enumerate(edges):
        ef = float(e)
        if not math.isfinite(ef):
            raise ValueError(f"non-finite band edge {e!r}")
        if prev is not None and ef < prev:
            raise ValueError(f"band_edges must be non-decreasing, got {list(edges)}")
        prev = ef
        if value < ef:
            return i
    return len(edges)


def percentile_rank(value: float, series: Sequence[float]) -> float:
    """Midrank percentile in [0, 1] of *value* among finite *series* members.

    Fail-closed: empty / all-non-finite series → nan (caller emits X_ marker).
    """
    vals = [float(x) for x in series if math.isfinite(float(x))]
    if not vals or not math.isfinite(value):
        return float("nan")
    less = sum(1 for x in vals if x < value)
    equal = sum(1 for x in vals if x == value)
    return (less + 0.5 * equal) / len(vals)


class MagnitudeStateEncoder:
    """Ontology-driven continuous → magnitude STATE classifier (shadow)."""

    def __init__(
        self,
        ontology: dict | None = None,
        state_encoder: FeatureStateEncoder | None = None,
    ):
        ont = ontology if ontology is not None else load_ontology()
        self._state_encoder = (
            state_encoder if state_encoder is not None else FeatureStateEncoder(ont)
        )
        specs: dict[str, MagnitudeBandSpec] = {}

        for section in _ITERATED_SECTIONS:
            for name, spec in (ont.get(section) or {}).items():
                if not isinstance(spec, dict):
                    continue
                edges = spec.get("band_edges")
                if edges is None:
                    continue
                if name not in MAGNITUDE_STATE_NAMES:
                    # Allow future banded identities only when listed — fail closed on surprise.
                    raise ValueError(
                        f"ontology {section}.{name}: has band_edges but is not in "
                        f"MAGNITUDE_STATE_NAMES {MAGNITUDE_STATE_NAMES}"
                    )
                if not isinstance(edges, (list, tuple)) or len(edges) < 1:
                    raise ValueError(
                        f"ontology {section}.{name}: band_edges must be a non-empty list"
                    )
                edge_t = tuple(float(e) for e in edges)
                src = spec.get("source_feature")
                if not isinstance(src, str) or not src:
                    raise ValueError(
                        f"ontology {section}.{name}: source_feature required for magnitude bands"
                    )
                transform = str(spec.get("source_transform") or "identity")
                if transform not in _VALID_TRANSFORMS:
                    raise ValueError(
                        f"ontology {section}.{name}: source_transform {transform!r} "
                        f"not in {sorted(_VALID_TRANSFORMS)}"
                    )
                states = spec.get("states") or []
                if not states:
                    raise ValueError(
                        f"ontology {section}.{name}: magnitude identity requires non-empty states"
                    )
                n_bins = len(edge_t) + 1
                if len(states) != n_bins:
                    raise ValueError(
                        f"ontology {section}.{name}: expected {n_bins} states for "
                        f"{len(edge_t)} edges, got {len(states)}"
                    )
                # Must be registered with FeatureStateEncoder as non-vector stateful.
                if name not in self._state_encoder.stateful_features:
                    raise ValueError(
                        f"ontology {section}.{name}: states not loaded by FeatureStateEncoder"
                    )
                if self._state_encoder.spec(name).vector_index is not None:
                    raise ValueError(
                        f"ontology {section}.{name}: magnitude states must be non-vector "
                        "(continuous source stays on its own vector slot)"
                    )
                specs[name] = MagnitudeBandSpec(
                    name=name,
                    fm_id=str(spec.get("id") or ""),
                    section=section,
                    source_feature=src,
                    source_transform=transform,
                    band_edges=edge_t,
                    n_bins=n_bins,
                )

        missing = [n for n in MAGNITUDE_STATE_NAMES if n not in specs]
        if missing:
            raise ValueError(
                f"MagnitudeStateEncoder: ontology missing banded identities {missing}"
            )
        self._specs = specs

    @property
    def magnitude_features(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def spec(self, name: str) -> MagnitudeBandSpec:
        return self._specs[name]

    def continuous_to_code(
        self,
        name: str,
        continuous_value: float,
        *,
        series: Sequence[float] | None = None,
    ) -> int | None:
        """Return integer bin code, or None when the transform cannot be evaluated."""
        ms = self._specs[name]
        v = float(continuous_value)
        if not math.isfinite(v):
            return None
        transform = ms.source_transform
        if transform == "identity":
            x = v
        elif transform == "series_percentile":
            if series is None:
                return None
            x = percentile_rank(v, series)
            if not math.isfinite(x):
                return None
        elif transform == "abs_series_percentile":
            if series is None:
                return None
            abs_series = [abs(float(s)) for s in series]
            x = percentile_rank(abs(v), abs_series)
            if not math.isfinite(x):
                return None
        else:
            raise ValueError(f"unknown transform {transform!r}")
        return bin_ordered(x, ms.band_edges)

    def classify_value(
        self,
        name: str,
        continuous_value: float,
        *,
        series: Sequence[float] | None = None,
    ) -> str:
        """Continuous measurement → declared magnitude state name (or X_ marker)."""
        code = self.continuous_to_code(name, continuous_value, series=series)
        if code is None:
            return f"{X_PREFIX}UNMAPPED({continuous_value!r})"
        return self._state_encoder.classify_value(name, float(code))

    def classify_features(
        self,
        features: Mapping[str, float],
        *,
        series_context: Mapping[str, Sequence[float]] | None = None,
    ) -> dict[str, str]:
        """Classify all magnitude identities from a feature map (+ optional series).

        Missing *source* features RAISE (no silent skip). Percentile transforms without
        series_context[source] become X_UNMAPPED rather than inventing ranks.
        """
        series_context = series_context or {}
        out: dict[str, str] = {}
        missing_src: list[str] = []
        for name, ms in self._specs.items():
            if ms.source_feature not in features:
                missing_src.append(f"{name}←{ms.source_feature}")
                continue
            series = series_context.get(ms.source_feature)
            out[name] = self.classify_value(
                name,
                float(features[ms.source_feature]),
                series=series,
            )
        if missing_src:
            raise KeyError(
                f"classify_features(): required source features absent: {missing_src} "
                "(no defaults — pass continuous measurements for every magnitude identity)"
            )
        return out
