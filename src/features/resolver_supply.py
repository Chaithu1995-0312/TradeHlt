"""
resolver_supply.py
================================================================================
The ONE way a caller feeds ``CRTStateResolver.resolve()``.

WHY THIS EXISTS
---------------
``FeaturePipeline.run()`` returns TWO objects -- ``enriched_df`` (every
intermediate column) and ``vectors`` (exactly ``CANONICAL_FEATURES``, in order).
Callers were each taking a different slice of that one return value:

  scripts/research/run_crt_state_on_mt5_xauusd.py
      canonical-intersection + retest_flag + displacement_flag,
      with a silent ``if pd.isna(val): val = 0.0`` coercion.
  scripts/research/build_bar_matrix.py
      ``enriched.to_dict("records")`` -- EVERY column, native dtypes, no coercion.

That is not a style difference, because of ``crt_state_resolver.resolve()``::

    non_vector_features = {}
    for fname in feat_dict:                       # <- every key the CALLER passed
        non_vector_features[fname] = self._encoder.classify_value(...)
    feature_states.update(non_vector_features)    # <- overwrites classify()'s output

``feature_states`` is therefore a function of WHAT THE CALLER HAPPENED TO PASS.
Extra columns whose names the encoder recognises silently add or overwrite
entries. The encoder's stateful vocabulary contains SIX non-vector names --
``retest_flag``, ``rsi_state``, ``displacement_flag``, ``atr_magnitude``,
``body_commitment``, ``momentum_magnitude`` -- not the three the resolver's own
source comment lists.

The recorded symptom is two resolver occupancy series on the same XAUUSD corpus
differing by 17,563 RANGE bars, with
``constructors.resolver.parameterization.invocation.supply_set`` left ``null``
in ``crt_state_identity.yaml`` because no one had adjudicated which caller was
canonical.

THE FIX IS A CONTRACT, NOT AN ADJUDICATION
------------------------------------------
Picking a winner resolves one instance and leaves the class open. The consumer
already PUBLISHES its contract (``required_when_features`` / ``waived_when_features``).
What was missing is a producer-side adapter that satisfies it, so no caller
chooses:

  * every ``CANONICAL_FEATURES`` name is sourced from ``vectors`` -- the
    canonical, order-defined surface -- never from an enriched column that
    merely shares the name;
  * ``when:``-named features that are NOT vector-bound are sourced from
    ``enriched``, because that is the only place they exist;
  * NOTHING ELSE is passed. No ``_pos``, no ``timestamp``, no base-layer
    intermediate. The overwrite loop above therefore has nothing extra to chew on.

NaN POLICY (explicit, because the old one was silent)
-----------------------------------------------------
Canonical columns cannot be NaN -- ``finalize()`` drops any row carrying NaN in
any of them. The non-vector flags are NOT canonical and so are NOT dropped, and
they can be NaN in the leading window.

This module PROPAGATES NaN rather than coercing it to 0.0, and counts it. The
resolver's own supply-contract comment draws the distinction: a missing key is a
SUPPLY failure (raise); an out-of-domain value is a VALUE failure that should
fail its predicate normally via ``classify_value``'s X_UNMAPPED marker. Coercing
NaN to 0.0 converts the second into a silent, confident ``NoRetest`` --
indistinguishable from a real one. Callers that want the legacy behaviour must
ask for it by name (``nan_policy="zero"``) so a run's treatment is readable from
its manifest instead of inferred.

AUTHORITY: none. This module makes the supply set DECLARABLE and stable; it
grants no runtime eligibility, promotes nothing, and does not close F-069.
================================================================================
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

from features.feature_schema import CANONICAL_FEATURES

logger = logging.getLogger("CRT.ResolverSupply")

# Human-readable name for this supply construction. Goes into
# `crt_state_identity.yaml` at constructors.resolver.parameterization.invocation.supply_set.
SUPPLY_SET_ID = "canonical_v5_plus_nonvector"

_NAN_POLICIES = ("propagate", "zero")


class ResolverSupplyError(RuntimeError):
    """The producer cannot satisfy the consumer's published contract."""


@dataclass(frozen=True)
class SupplyPlan:
    """The resolved key plan for one (resolver, pipeline) pairing.

    ``fingerprint`` is a sha256 over the exact sourced key lists -- the same
    discipline ``crt_identity_schema.derive_constructor_id`` uses. Two runs with
    the same fingerprint provably fed the resolver the same key set; two runs
    with different fingerprints provably did not. That is the question the
    17,563-bar divergence could not answer.
    """

    supply_set_id: str
    from_vector: tuple[str, ...]
    from_enriched: tuple[str, ...]
    fingerprint: str
    nan_policy: str
    stats: dict = field(default_factory=dict)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.from_vector) | set(self.from_enriched)))


def _fingerprint(from_vector: Sequence[str], from_enriched: Sequence[str], nan_policy: str) -> str:
    payload = json.dumps(
        {
            "supply_set_id": SUPPLY_SET_ID,
            "from_vector": sorted(from_vector),
            "from_enriched": sorted(from_enriched),
            "nan_policy": nan_policy,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def plan_supply(
    resolver,
    enriched_columns: Iterable[str],
    *,
    nan_policy: str = "propagate",
) -> SupplyPlan:
    """Resolve which keys come from the vector and which from the enriched frame.

    Fails closed when the consumer requires a ``when:``-named feature that is
    neither canonical nor present in the enriched frame -- previously that
    surfaced only as a state that silently never fired.
    """
    if nan_policy not in _NAN_POLICIES:
        raise ResolverSupplyError(
            f"nan_policy must be one of {_NAN_POLICIES}, got {nan_policy!r}"
        )

    canon = tuple(CANONICAL_FEATURES)
    cols = set(enriched_columns)
    required = set(resolver.required_when_features)
    waived = set(resolver.waived_when_features)

    from_vector = tuple(canon)
    non_vector_required = sorted((required - set(canon)) - waived)

    missing = [n for n in non_vector_required if n not in cols]
    if missing:
        raise ResolverSupplyError(
            "enriched frame cannot satisfy the resolver's supply contract; "
            f"missing non-vector `when:`-named feature(s): {missing}. "
            "These are produced by FeaturePipeline as intermediates -- a caller "
            "that fabricates them (e.g. `enriched[col] = 0`) manufactures a "
            "confident state where there was no evidence. Supply them, or name "
            "them in the resolver's allow_missing_when_features."
        )

    from_enriched = tuple(non_vector_required)
    return SupplyPlan(
        supply_set_id=SUPPLY_SET_ID,
        from_vector=from_vector,
        from_enriched=from_enriched,
        fingerprint=_fingerprint(from_vector, from_enriched, nan_policy),
        nan_policy=nan_policy,
        stats={},
    )


def build_supply_rows(
    enriched,
    vectors,
    plan: SupplyPlan,
) -> tuple[list[dict[str, float]], dict]:
    """Build one supply dict per bar, plus a stats block for the run manifest.

    ``vectors`` is authoritative for every canonical name. ``enriched`` supplies
    only the non-vector ``when:``-named features. Row i of ``vectors`` and row i
    of ``enriched`` correspond because ``finalize()`` reset the index before
    ``build_feature_vector()`` read the same frame.
    """
    n = len(enriched)
    if vectors is None or len(vectors) != n:
        raise ResolverSupplyError(
            f"vectors/enriched length mismatch: {None if vectors is None else len(vectors)} "
            f"vs {n}. They must come from the same FeaturePipeline.run() call."
        )
    width = len(plan.from_vector)
    if vectors.shape[1] != width:
        raise ResolverSupplyError(
            f"vector width {vectors.shape[1]} != {width} canonical features. "
            "Schema drift between the pipeline and features.feature_schema."
        )

    enriched_cols = {name: enriched[name].to_numpy() for name in plan.from_enriched}
    nan_counts = {name: 0 for name in plan.from_enriched}
    zero_policy = plan.nan_policy == "zero"

    rows: list[dict[str, float]] = []
    for i in range(n):
        row = {name: float(vectors[i][j]) for j, name in enumerate(plan.from_vector)}
        for name, arr in enriched_cols.items():
            val = arr[i]
            try:
                fval = float(val)
            except (TypeError, ValueError):
                fval = math.nan
            if math.isnan(fval):
                nan_counts[name] += 1
                if zero_policy:
                    fval = 0.0
            row[name] = fval
        rows.append(row)

    total_nan = sum(nan_counts.values())
    if total_nan:
        logger.warning(
            "[resolver_supply] %d NaN value(s) in non-vector features %s under "
            "nan_policy=%s. These are NOT canonical, so finalize() did not drop "
            "their rows.",
            total_nan,
            {k: v for k, v in nan_counts.items() if v},
            plan.nan_policy,
        )

    stats = {
        "supply_set_id": plan.supply_set_id,
        "supply_fingerprint": plan.fingerprint,
        "nan_policy": plan.nan_policy,
        "rows": n,
        "keys_from_vector": len(plan.from_vector),
        "keys_from_enriched": list(plan.from_enriched),
        "nan_counts": nan_counts,
    }
    return rows, stats


def build_resolver_supply(
    resolver,
    enriched,
    vectors,
    *,
    nan_policy: str = "propagate",
) -> tuple[list[dict[str, float]], dict]:
    """Convenience: plan then build. The single entry point callers should use."""
    plan = plan_supply(resolver, enriched.columns, nan_policy=nan_policy)
    return build_supply_rows(enriched, vectors, plan)
