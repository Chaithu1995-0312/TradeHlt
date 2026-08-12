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
  Non-vector stateful identities (rsi_state, displacement_flag, retest_flag, magnitude twins)
  are ALLOWED when the caller computed them — the required set and the allowed set are both
  ontology-defined.
- A state string must be either a declared state name for its feature or an ``X_`` marker from
  the encoder. Anything else RAISES (garbage is a caller bug, not data).
- ``X_`` markers PROPAGATE into the context and are surfaced on ``x_markers`` — a context is an
  honest description, and "this feature's value fell outside its declared domain" is part of it.
- UNKNOWN is distinguishable from a real state: a missing optional feature is ABSENT (not
  forced into NoSweep/NormalVolatility/…); an X_ marker is domain drift, not a state name;
  continuous features without declared states are listed as unresolved, never banded here.
- Temporal: session is *observed_time_context* via the Time dimension (session owner =
  session_classifier). Episode *causality* is UNKNOWN unless an explicit causal rule exists
  (none declared today — never infer "session == cause").

Structured closure fields (L4 contract):
  dimension_records / completeness / unknown_dimensions / unresolved_continuous /
  provenance / temporal

The flat ``dimensions`` map (category -> {feature: state}) remains the substrate for Layer 5
shape identity — content-addressed, deterministic, unchanged in form.

Shadow-only: nothing on the decision spine consumes this output.

The ``signature`` / ``context_hash`` are deterministic renderings of the full description —
the substrate Phase 5 (Market Shape) clusters on.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from features.feature_states import FeatureStateEncoder, X_PREFIX
from features.registry import load_ontology

# Explicit status vocabulary (closed).
DIM_STATUS_POPULATED = "POPULATED"       # ≥1 known (non-X_) state observed
DIM_STATUS_DRIFT = "DRIFT"               # only X_ markers observed
DIM_STATUS_EMPTY = "EMPTY"               # no features supplied for this category
DIM_STATUS_PARTIAL = "PARTIAL"           # mix of known + missing optional vector-bound

COMPLETENESS_COMPLETE = "COMPLETE"       # all vector-bound states present and known (no X_)
COMPLETENESS_PARTIAL = "PARTIAL"         # vector-bound present but X_ markers or optional gaps
COMPLETENESS_UNKNOWN = "UNKNOWN"         # should not appear after successful build

# Source tags for provenance (not authority — traceability only).
SRC_FEATURE_STATES = "feature_states"
SRC_MAGNITUDE_STATES = "magnitude_states"
SRC_SESSION_CLASSIFIER = "session_classifier"

# Magnitude twin identities (Phase 2A) — non-vector stateful; optional in build input.
_MAGNITUDE_FEATURES = frozenset(
    {"body_commitment", "atr_magnitude", "momentum_magnitude"}
)

# Temporal causality: no declared causal rule in this repository.
_TEMPORAL_CAUSALITY_UNKNOWN = "UNKNOWN"
_TEMPORAL_CAUSALITY_NOTE = (
    "No declared episode-causality rule binds session/time labels to move causality. "
    "observed_time_context is labeled; inferred_episode_causality remains UNKNOWN."
)


@dataclass(frozen=True)
class DimensionFeatureState:
    """One feature's contribution inside a context dimension."""

    feature: str
    state: str
    known: bool                    # False when state is an X_ domain-drift marker
    source: str                    # feature_states | magnitude_states | ...
    fm_id: str
    vector_bound: bool
    category: str


@dataclass(frozen=True)
class ContextDimension:
    """One ontology category as a structured context dimension."""

    category: str
    features: dict[str, DimensionFeatureState]   # feature -> record; deterministic order
    status: str                                  # POPULATED | DRIFT | EMPTY | PARTIAL
    observed_count: int
    known_count: int
    expected_vector_bound: tuple[str, ...]       # vector-bound features in this category
    absent_optional: tuple[str, ...]             # allowed non-vector not supplied by caller

    def to_flat(self) -> dict[str, str]:
        """Flat feature→state map (Layer-5 substrate / legacy consumers)."""
        return {f: rec.state for f, rec in self.features.items()}

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "status": self.status,
            "observed_count": self.observed_count,
            "known_count": self.known_count,
            "expected_vector_bound": list(self.expected_vector_bound),
            "absent_optional": list(self.absent_optional),
            "features": {
                f: {
                    "state": rec.state,
                    "known": rec.known,
                    "source": rec.source,
                    "fm_id": rec.fm_id,
                    "vector_bound": rec.vector_bound,
                }
                for f, rec in self.features.items()
            },
        }


@dataclass(frozen=True)
class TemporalContext:
    """Observed time labels vs inferred episode causality (never conflated)."""

    observed_time_context: dict[str, str]   # feature -> state for Time dimension
    session_owner: str                      # single session owner module
    causality: str                          # UNKNOWN unless explicit rule exists
    causality_note: str
    session_state: str | None               # convenience: session feature if present
    session_known: bool

    def to_dict(self) -> dict:
        return {
            "observed_time_context": dict(self.observed_time_context),
            "session_owner": self.session_owner,
            "causality": self.causality,
            "inferred_episode_causality": self.causality,  # alias for contract wording
            "causality_note": self.causality_note,
            "session_state": self.session_state,
            "session_known": self.session_known,
        }


@dataclass(frozen=True)
class MarketContext:
    """One bar's complete semantic description, grouped by declared context dimension."""

    dimensions: dict[str, dict[str, str]]   # category -> {feature: state}; Layer-5 substrate
    signature: str                          # canonical one-line rendering (stable across runs)
    context_hash: str                       # sha256[:16] of signature — the Phase-5 clustering key
    x_markers: tuple[str, ...]              # "feature=X_..." entries; non-empty == domain drift
    # --- L4 structured closure fields ---
    dimension_records: dict[str, ContextDimension] = field(default_factory=dict)
    completeness: str = COMPLETENESS_PARTIAL
    completeness_ratio: float = 0.0         # known vector-bound / required vector-bound
    unknown_dimensions: tuple[str, ...] = ()  # EMPTY or DRIFT-only categories
    unresolved_continuous: tuple[str, ...] = ()  # continuous features still without states
    provenance: tuple[str, ...] = ()
    temporal: TemporalContext | None = None

    def describe(self) -> str:
        """Multi-line human rendering — the literal 'what is happening in the market?' answer."""
        lines = []
        for category, feats in self.dimensions.items():
            parts = ", ".join(f"{state} ({feat})" for feat, state in feats.items())
            lines.append(f"{category}: {parts}")
        if self.temporal is not None:
            lines.append(
                f"Temporal: observed={self.temporal.observed_time_context}; "
                f"causality={self.temporal.causality}"
            )
        lines.append(
            f"Completeness: {self.completeness} "
            f"({self.completeness_ratio:.2f}); unknown_dimensions={list(self.unknown_dimensions)}"
        )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """JSON-ready structured contract (does not invent meaning)."""
        structured_dims: dict = {}
        for cat, feats in self.dimensions.items():
            if cat in self.dimension_records:
                structured_dims[cat] = self.dimension_records[cat].to_dict()
            else:
                structured_dims[cat] = {"features": feats, "status": "LEGACY_FLAT"}
        return {
            "dimensions": structured_dims,
            "dimensions_flat": self.dimensions,
            "dimension_records": {
                cat: rec.to_dict() for cat, rec in self.dimension_records.items()
            },
            "signature": self.signature,
            "context_hash": self.context_hash,
            "x_markers": list(self.x_markers),
            "completeness": self.completeness,
            "completeness_ratio": self.completeness_ratio,
            "unknown_dimensions": list(self.unknown_dimensions),
            "unresolved_continuous": list(self.unresolved_continuous),
            "provenance": list(self.provenance),
            "temporal": self.temporal.to_dict() if self.temporal else None,
        }


def _source_for(name: str) -> str:
    if name in _MAGNITUDE_FEATURES:
        return SRC_MAGNITUDE_STATES
    if name == "session":
        return SRC_SESSION_CLASSIFIER
    return SRC_FEATURE_STATES


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
        # Continuous remainder is declared gap material — never banded here.
        self._unresolved_continuous: tuple[str, ...] = tuple(self._encoder.continuous_features)

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def dimensions(self) -> tuple[str, ...]:
        """Context dimensions this ontology can populate, in vocabulary order."""
        return self._dimension_order

    def features_of(self, category: str) -> tuple[str, ...]:
        """Stateful features belonging to one dimension. Raises KeyError on unknown category."""
        return self._by_category[category]

    @property
    def unresolved_continuous(self) -> tuple[str, ...]:
        """Canonical features with no declared states (interpretation gap, not missing OHLC)."""
        return self._unresolved_continuous

    # ── aggregation ──────────────────────────────────────────────────────────

    def build(
        self,
        states: Mapping[str, str],
        *,
        extra_provenance: Sequence[str] | None = None,
    ) -> MarketContext:
        """Aggregate a {feature: state} mapping (encoder output) into a MarketContext.

        Optional non-vector states (magnitude twins, rsi_state, flags) are included when
        present. They are NEVER invented when absent.
        """
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
        dimensions_flat: dict[str, dict[str, str]] = {}
        dimension_records: dict[str, ContextDimension] = {}
        unknown_dims: list[str] = []
        known_vector_bound = 0
        provenance_set: set[str] = {
            "features.market_context.MarketContextBuilder",
            "configs/formulas/market_ontology.yaml#taxonomy.category",
            "features.feature_states.FeatureStateEncoder",
        }

        for category in self._dimension_order:
            expected_vb = tuple(
                n for n in self._by_category[category]
                if self._encoder.spec(n).vector_index is not None
            )
            optional_names = tuple(
                n for n in self._by_category[category]
                if self._encoder.spec(n).vector_index is None
            )
            feats_rec: dict[str, DimensionFeatureState] = {}
            for name in self._by_category[category]:
                if name not in states:
                    continue  # allowed-but-absent non-vector identity: not invented
                state = states[name]
                sf = self._encoder.spec(name)
                is_x = state.startswith(X_PREFIX)
                if is_x:
                    x_markers.append(f"{name}={state}")
                elif state not in sf.value_to_state.values():
                    raise ValueError(
                        f"build(): {name}={state!r} is neither a declared state of {sf.fm_id} "
                        f"nor an {X_PREFIX} marker — refusing to describe garbage"
                    )
                src = _source_for(name)
                provenance_set.add(src)
                if name == "session":
                    provenance_set.add(
                        "features.session_classifier (FM-052 owner; not reimplemented here)"
                    )
                rec = DimensionFeatureState(
                    feature=name,
                    state=state,
                    known=not is_x,
                    source=src,
                    fm_id=sf.fm_id,
                    vector_bound=sf.vector_index is not None,
                    category=category,
                )
                feats_rec[name] = rec
                if rec.vector_bound and rec.known:
                    known_vector_bound += 1

            absent_optional = tuple(n for n in optional_names if n not in feats_rec)
            known_count = sum(1 for r in feats_rec.values() if r.known)
            observed_count = len(feats_rec)
            if observed_count == 0:
                status = DIM_STATUS_EMPTY
                unknown_dims.append(category)
            elif known_count == 0:
                status = DIM_STATUS_DRIFT
                unknown_dims.append(category)
            elif any(n not in feats_rec for n in expected_vb):
                # Should not happen: vector-bound are required globally.
                status = DIM_STATUS_PARTIAL
            else:
                status = DIM_STATUS_POPULATED

            dim = ContextDimension(
                category=category,
                features=feats_rec,
                status=status,
                observed_count=observed_count,
                known_count=known_count,
                expected_vector_bound=expected_vb,
                absent_optional=absent_optional,
            )
            dimension_records[category] = dim
            if feats_rec:
                dimensions_flat[category] = dim.to_flat()

        # Temporal: observe Time dimension only; never invent causality.
        time_rec = dimension_records.get("Time")
        observed_time: dict[str, str] = time_rec.to_flat() if time_rec and time_rec.features else {}
        sess_state = observed_time.get("session")
        sess_known = bool(
            sess_state is not None and not str(sess_state).startswith(X_PREFIX)
        )
        temporal = TemporalContext(
            observed_time_context=observed_time,
            session_owner="features.session_classifier",
            causality=_TEMPORAL_CAUSALITY_UNKNOWN,
            causality_note=_TEMPORAL_CAUSALITY_NOTE,
            session_state=sess_state,
            session_known=sess_known,
        )

        n_required = len(self._required) or 1
        ratio = known_vector_bound / n_required
        if known_vector_bound == len(self._required) and not x_markers:
            completeness = COMPLETENESS_COMPLETE
        else:
            completeness = COMPLETENESS_PARTIAL

        # Signature remains the flat description substrate (backward-compatible hash).
        # Magnitude / optional states that the caller supplied DO enter the signature when
        # present — they are part of the honest description. Vector-only builds keep prior
        # signatures when only vector-bound states are passed (backward compatible).
        signature = "|".join(
            f"{category}[" + ",".join(f"{f}={s}" for f, s in feats.items()) + "]"
            for category, feats in dimensions_flat.items()
        )

        prov = tuple(sorted(provenance_set))
        if extra_provenance:
            prov = tuple(sorted(set(prov) | set(extra_provenance)))

        return MarketContext(
            dimensions=dimensions_flat,
            signature=signature,
            context_hash=hashlib.sha256(signature.encode()).hexdigest()[:16],
            x_markers=tuple(x_markers),
            dimension_records=dimension_records,
            completeness=completeness,
            completeness_ratio=ratio,
            unknown_dimensions=tuple(unknown_dims),
            unresolved_continuous=self._unresolved_continuous,
            provenance=prov,
            temporal=temporal,
        )

    def build_from_vector(self, vector: Sequence[float]) -> MarketContext:
        """Canonical 39-dim vector -> MarketContext (vector-bound dimensions only)."""
        return self.build(self._encoder.classify_vector(vector))

    def build_from_features(self, features: Mapping[str, float]) -> MarketContext:
        """Canonical feature mapping -> MarketContext (vector-bound dimensions only)."""
        return self.build(self._encoder.classify(features))

    def build_with_magnitude(
        self,
        vector_states: Mapping[str, str],
        magnitude_states: Mapping[str, str] | None = None,
        *,
        extra_states: Mapping[str, str] | None = None,
    ) -> MarketContext:
        """Merge vector-bound + magnitude (and other optional) states into one context.

        Magnitude states are NOT required. Absence leaves CandleGeometry/Momentum/Volatility
        partial on optional magnitude twins — never fabricates LowCommitment/etc.
        """
        merged: dict[str, str] = dict(vector_states)
        if magnitude_states:
            for k, v in magnitude_states.items():
                if k not in self._allowed:
                    raise KeyError(
                        f"build_with_magnitude(): {k!r} is not a declared stateful identity"
                    )
                merged[k] = v
        if extra_states:
            for k, v in extra_states.items():
                if k not in self._allowed:
                    raise KeyError(
                        f"build_with_magnitude(): {k!r} is not a declared stateful identity"
                    )
                merged[k] = v
        return self.build(
            merged,
            extra_provenance=(
                ("features.magnitude_states.MagnitudeStateEncoder",)
                if magnitude_states
                else ()
            ),
        )
