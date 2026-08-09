"""
Feature State layer — Layer 2 of the semantic pipeline (roadmap Phase 2C).

"Features measure. States interpret." This module converts already-computed feature VALUES into
their declared semantic STATES. The single source of state truth is the ontology
(configs/formulas/market_ontology.yaml): every entry carrying a non-empty ``states`` block defines
the legal value→meaning map, and this encoder is a pure interpreter of that declaration.

WHAT THIS MODULE IS NOT
-----------------------
- NOT a feature computer. It never derives a feature from OHLC or from other features — that is
  the pipeline/registry's job, and re-derivation here would trip the ownership lint
  (scripts/analysis/feature_math_lint.py). It maps values it is GIVEN.
- NOT a threshold owner. There is not a single numeric cut in this file. Banding continuous
  features (e.g. ema_spread magnitude) requires declared states in the ontology first; the
  ema_spread case is explicitly BLOCKED on the FM-030 activation (F-061: legacy magnitudes scale
  with price level, so fixed bands would bake the dimensional defect into the semantic layer).
- NOT on the decision path. Shadow-only: nothing on the spine consumes this output.

CONTRACT (no defaults, no fallbacks)
------------------------------------
- A missing input feature RAISES. There is no ``.get(key, default)`` anywhere: absence is a caller
  contract violation, never silently skipped (CLAUDE.md §6.5 hard rule, F-018/F-056 class).
- A value with no declared state is NEVER coerced to a neighbouring state and NEVER dropped. It is
  encoded as an explicit, greppable marker state:
      X_UNMAPPED(<value>)    — finite value outside the declared domain
      X_NON_FINITE(<value>)  — NaN / inf
  The ``X_`` prefix is the searchable signature: any occurrence in downstream artifacts means a
  declared domain and reality disagreed, and points at exactly which feature and which value.
- A malformed ontology states block raises AT CONSTRUCTION, not at classify time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from features.registry import load_ontology, _ITERATED_SECTIONS
from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP

# Greppable marker prefix for values the declared domain does not cover. Deliberately short and
# distinctive: `grep -r "X_"` over emitted artifacts finds every declaration/reality mismatch.
X_PREFIX = "X_"


@dataclass(frozen=True)
class StatefulFeature:
    """One ontology identity that declares semantic states."""
    name: str                      # ontology entry name (== column/vector name where bound)
    fm_id: str                     # stable FM-0NN handle
    section: str                   # ontology section it lives in
    category: str                  # taxonomy.category — the Market Context dimension it belongs to
    vector_index: int | None       # CANONICAL_FEATURES index, or None when not a vector slot
    value_to_state: dict[int, str]  # declared value -> state name (exact, integer domain)


class FeatureStateEncoder:
    """Pure interpreter: feature values -> declared semantic states.

    Built once from the ontology; ``classify``/``classify_vector`` are then side-effect-free.
    """

    def __init__(self, ontology: dict | None = None):
        ont = ontology if ontology is not None else load_ontology()

        stateful: dict[str, StatefulFeature] = {}
        for section in _ITERATED_SECTIONS:
            for name, spec in (ont.get(section) or {}).items():
                states = spec.get("states")
                if not states:
                    continue  # continuous / unbanded — declared empty, deliberately not encoded
                value_to_state: dict[int, str] = {}
                for st in states:
                    # Fail at construction on malformed declarations — no lenient parsing.
                    if "value" not in st or "name" not in st:
                        raise ValueError(
                            f"ontology {section}.{name}: states entry missing 'value'/'name': {st!r}"
                        )
                    value = st["value"]
                    if not isinstance(value, int):
                        raise ValueError(
                            f"ontology {section}.{name}: state {st['name']!r} has non-integer "
                            f"value {value!r} — enumerated domains are integer-valued"
                        )
                    if value in value_to_state:
                        raise ValueError(
                            f"ontology {section}.{name}: duplicate state value {value}"
                        )
                    value_to_state[value] = str(st["name"])

                category = (spec.get("taxonomy") or {}).get("category")
                if not isinstance(category, str) or not category:
                    # Mandatory schema-wide (validate_registry enforces it too); a stateful
                    # identity without a dimension cannot be placed in a Market Context.
                    raise ValueError(
                        f"ontology {section}.{name}: missing taxonomy.category "
                        "(required — it is the Market Context dimension)"
                    )
                vk = (spec.get("lineage") or {}).get("vector_key")
                index = FEATURE_INDEX_MAP[vk] if isinstance(vk, str) and vk else None
                stateful[name] = StatefulFeature(
                    name=name,
                    fm_id=str(spec["id"]),
                    section=section,
                    category=category,
                    vector_index=index,
                    value_to_state=value_to_state,
                )

        if not stateful:
            raise ValueError("ontology declares no states — encoder has nothing to interpret")

        self._stateful = stateful
        # Vector-bound subset, in canonical index order — the deterministic emission order.
        self._vector_bound: tuple[StatefulFeature, ...] = tuple(sorted(
            (sf for sf in stateful.values() if sf.vector_index is not None),
            key=lambda sf: sf.vector_index,
        ))
        # Canonical features with NO declared states — the explicit "continuous / uninterpreted"
        # remainder, exposed so coverage is checkable instead of implicit.
        bound_names = {sf.name for sf in self._vector_bound}
        self._continuous: tuple[str, ...] = tuple(
            f for f in CANONICAL_FEATURES if f not in bound_names
        )

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def stateful_features(self) -> tuple[str, ...]:
        """Every ontology identity with declared states (vector-bound or not)."""
        return tuple(sorted(self._stateful))

    @property
    def vector_bound_features(self) -> tuple[str, ...]:
        """Stateful identities bound to a canonical vector slot, in index order."""
        return tuple(sf.name for sf in self._vector_bound)

    @property
    def continuous_features(self) -> tuple[str, ...]:
        """Canonical features with no declared states — measured, not (yet) interpreted."""
        return self._continuous

    def spec(self, name: str) -> StatefulFeature:
        """The declared state map for one feature. Raises KeyError for non-stateful names."""
        return self._stateful[name]

    # ── classification ───────────────────────────────────────────────────────

    def classify_value(self, name: str, value: float) -> str:
        """Map one feature's value to its declared state name.

        Out-of-domain values return an explicit ``X_``-prefixed marker (never coerced, never
        dropped); an unknown feature NAME raises — that is a programming error, not data.
        """
        sf = self._stateful[name]  # KeyError = caller bug; no fallback
        v = float(value)
        if not math.isfinite(v):
            return f"{X_PREFIX}NON_FINITE({value!r})"
        r = round(v)
        # Exact integer domain: 1.0 matches state 1; 0.5 matches nothing and must say so.
        if abs(v - r) > 1e-6 or int(r) not in sf.value_to_state:
            return f"{X_PREFIX}UNMAPPED({value!r})"
        return sf.value_to_state[int(r)]

    def classify(self, features: Mapping[str, float]) -> dict[str, str]:
        """Interpret every vector-bound stateful feature present in *features*.

        Every vector-bound stateful feature MUST be present — a missing key raises with the full
        missing list. Non-vector stateful identities (rsi_state, displacement_flag, retest_flag)
        are classified only via ``classify_value`` by callers that actually computed them; this
        method never invents them from their inputs (that would be re-derivation).
        """
        missing = [sf.name for sf in self._vector_bound if sf.name not in features]
        if missing:
            raise KeyError(
                f"classify(): required stateful features absent from input: {missing} "
                "(no defaults — pass the full canonical mapping)"
            )
        return {sf.name: self.classify_value(sf.name, features[sf.name]) for sf in self._vector_bound}

    def classify_vector(self, vector: Sequence[float]) -> dict[str, str]:
        """Interpret a full canonical vector (schema v4.0, 39 dims) into its state vector."""
        if len(vector) != len(CANONICAL_FEATURES):
            raise ValueError(
                f"classify_vector(): expected {len(CANONICAL_FEATURES)}-dim canonical vector, "
                f"got {len(vector)}"
            )
        return {
            sf.name: self.classify_value(sf.name, vector[sf.vector_index])
            for sf in self._vector_bound
        }
