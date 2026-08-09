"""
Market Context layer — Layer 4 of the semantic pipeline (roadmap Phase 3).

"Context explains." This module combines individual feature STATES into one complete market
description — the answer to "what is happening in the market?" on a single bar.

THE DIMENSIONS ARE NOT INVENTED HERE. The ontology already assigns every stateful identity a
`taxonomy.category` from the closed `spec_schema.category_vocabulary` (Trend, Momentum,
Volatility, Liquidity, MarketStructure, Retest, Volume, Time, ...). A Market Context is exactly
that grouping applied to one bar's state vector: each populated category becomes a context
dimension carrying the states of its features. One declared axis, one aggregation — no second
taxonomy, no priority rules, no headline heuristics (collapsing a dimension to a single verdict
would be new policy; Phase 5 consumes the full description instead).

CONTRACT (same discipline as feature_states.py — no defaults, no fallbacks)
---------------------------------------------------------------------------
- Input state keys must ALL be declared stateful identities; an unknown key RAISES.
- Every vector-bound stateful feature is REQUIRED; missing ones RAISE, listed in full.
  Non-vector stateful identities (rsi_state, displacement_flag, retest_flag) are ALLOWED when
  the caller computed them — the required set and the allowed set are both ontology-defined.
- A state string must be either a declared state name for its feature or an ``X_`` marker from
  the encoder. Anything else RAISES (garbage is a caller bug, not data).
- ``X_`` markers PROPAGATE into the context and are surfaced on ``x_markers`` — a context is an
  honest description, and "this feature's value fell outside its declared domain" is part of it.

Shadow-only: nothing on the decision spine consumes this output.

The ``signature`` / ``context_hash`` are deterministic renderings of the full description —
the substrate Phase 5 (Market Shape) clusters on.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Sequence

from features.feature_states import FeatureStateEncoder, X_PREFIX
from features.registry import load_ontology


@dataclass(frozen=True)
class MarketContext:
    """One bar's complete semantic description, grouped by declared context dimension."""
    dimensions: dict[str, dict[str, str]]   # category -> {feature: state}; deterministic order
    signature: str                          # canonical one-line rendering (stable across runs)
    context_hash: str                       # sha256[:16] of signature — the Phase-5 clustering key
    x_markers: tuple[str, ...]              # "feature=X_..." entries; non-empty == domain drift

    def describe(self) -> str:
        """Multi-line human rendering — the literal 'what is happening in the market?' answer."""
        lines = []
        for category, feats in self.dimensions.items():
            parts = ", ".join(f"{state} ({feat})" for feat, state in feats.items())
            lines.append(f"{category}: {parts}")
        return "\n".join(lines)


class MarketContextBuilder:
    """Aggregates encoder state output into a MarketContext along the declared category axis."""

    def __init__(self, encoder: FeatureStateEncoder | None = None,
                 ontology: dict | None = None):
        ont = ontology if ontology is not None else load_ontology()
        self._encoder = encoder if encoder is not None else FeatureStateEncoder(ont)

        vocabulary = list((ont.get("spec_schema") or {}).get("category_vocabulary") or [])
        if not vocabulary:
            raise ValueError("ontology spec_schema.category_vocabulary is missing/empty")

        # category -> feature names, in vocabulary order; features alphabetical within.
        by_category: dict[str, list[str]] = {}
        for name in self._encoder.stateful_features:
            sf = self._encoder.spec(name)
            if sf.category not in vocabulary:
                raise ValueError(
                    f"stateful feature {name!r} declares category {sf.category!r} "
                    "outside spec_schema.category_vocabulary — cannot be ordered"
                )
            by_category.setdefault(sf.category, []).append(name)
        self._dimension_order: tuple[str, ...] = tuple(
            c for c in vocabulary if c in by_category
        )
        self._by_category: dict[str, tuple[str, ...]] = {
            c: tuple(sorted(by_category[c])) for c in self._dimension_order
        }
        self._required = set(self._encoder.vector_bound_features)
        self._allowed = set(self._encoder.stateful_features)

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def dimensions(self) -> tuple[str, ...]:
        """Context dimensions this ontology can populate, in vocabulary order."""
        return self._dimension_order

    def features_of(self, category: str) -> tuple[str, ...]:
        """Stateful features belonging to one dimension. Raises KeyError on unknown category."""
        return self._by_category[category]

    # ── aggregation ──────────────────────────────────────────────────────────

    def build(self, states: Mapping[str, str]) -> MarketContext:
        """Aggregate a {feature: state} mapping (encoder output) into a MarketContext."""
        unknown = sorted(set(states) - self._allowed)
        if unknown:
            raise KeyError(
                f"build(): keys are not declared stateful identities: {unknown} "
                "(the ontology defines the allowed set — no silent drop)"
            )
        missing = sorted(self._required - set(states))
        if missing:
            raise KeyError(
                f"build(): required vector-bound states absent: {missing} "
                "(no defaults — classify the full canonical input first)"
            )

        x_markers: list[str] = []
        dimensions: dict[str, dict[str, str]] = {}
        for category in self._dimension_order:
            feats: dict[str, str] = {}
            for name in self._by_category[category]:
                if name not in states:
                    continue  # allowed-but-absent non-vector identity: caller did not compute it
                state = states[name]
                sf = self._encoder.spec(name)
                if state.startswith(X_PREFIX):
                    x_markers.append(f"{name}={state}")
                elif state not in sf.value_to_state.values():
                    raise ValueError(
                        f"build(): {name}={state!r} is neither a declared state of {sf.fm_id} "
                        f"nor an {X_PREFIX} marker — refusing to describe garbage"
                    )
                feats[name] = state
            if feats:
                dimensions[category] = feats

        signature = "|".join(
            f"{category}[" + ",".join(f"{f}={s}" for f, s in feats.items()) + "]"
            for category, feats in dimensions.items()
        )
        return MarketContext(
            dimensions=dimensions,
            signature=signature,
            context_hash=hashlib.sha256(signature.encode()).hexdigest()[:16],
            x_markers=tuple(x_markers),
        )

    def build_from_vector(self, vector: Sequence[float]) -> MarketContext:
        """Canonical 39-dim vector -> MarketContext (vector-bound dimensions only)."""
        return self.build(self._encoder.classify_vector(vector))

    def build_from_features(self, features: Mapping[str, float]) -> MarketContext:
        """Canonical feature mapping -> MarketContext (vector-bound dimensions only)."""
        return self.build(self._encoder.classify(features))
