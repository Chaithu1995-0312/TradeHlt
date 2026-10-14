"""Feature semantic equivalence — identity contract, not name or width.

A shared feature name, a shared vector length, a read-side alias, or a schema
hash is not proof that two branches compute the same quantity. This module:

* builds a versioned definition for each canonical slot in the frozen
  35-feature prefix (``CANONICAL_FEATURES[:SCHEMA_V2_FEATURE_DIM]``) plus any
  later vector slot the ontology already binds, without reordering that prefix
* hashes every behaviorally relevant definition field
* checks a producer or consumer implementation into exactly one of
  MATCH, DRIFT, UNMAPPED, AMBIGUOUS, UNVERIFIED
* refuses model load / train-stamp / inference when the binding is not MATCH

It does not rewrite formulas, models, configs, or historical findings.
Unresolved ontology fields stay the token UNMAPPED. Economic usefulness is
out of scope.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from features.feature_schema import (
    CANONICAL_FEATURES,
    SCHEMA_V2_FEATURE_DIM,
    SCHEMA_V3_ALIASES,
    SCHEMA_V5_ALIASES,
)
from features.registry import _ITERATED_SECTIONS, load_ontology

CONTRACT_ID = "FEATURE-SEMANTIC-EQUIVALENCE-V1"
CONTRACT_VERSION = "1.0.0"
UNMAPPED = "UNMAPPED"
AMBIGUOUS_TOKEN = "AMBIGUOUS"

STATUSES = ("MATCH", "DRIFT", "UNMAPPED", "AMBIGUOUS", "UNVERIFIED")

# Fields that change what a number means. Names and vector position are not
# in this list; they are bound separately and never stand in for these.
BEHAVIOR_FIELDS = (
    "formula",
    "source_inputs",
    "lookback",
    "warmup",
    "timing",
    "units",
    "normalization",
    "encoding",
    "missing_value_policy",
    "edge_cases",
    "causal_availability",
)

# Evidence kind that is allowed to support a MATCH. A manifest row, a width,
# or an alias table is not execution evidence.
SOURCE_EVIDENCE = "source"

_READ_ALIASES = {**SCHEMA_V3_ALIASES, **SCHEMA_V5_ALIASES}

_REPO = Path(__file__).resolve().parents[2]
_BRANCH_PATH = _REPO / "configs" / "formulas" / "feature_consumer_branches_v1.json"
_MANIFEST_PATH = (
    _REPO / "docs" / "governance" / "feature_consumer_binding_manifest_fc05-2026-07-10.json"
)
_REPORT_DIR = _REPO / "docs" / "governance"


class FeatureSemanticIncompatible(ValueError):
    """Model load, training stamp, or inference refused.

    ``status`` is one of DRIFT, UNMAPPED, AMBIGUOUS, UNVERIFIED.
    """

    def __init__(self, status: str, message: str, details: Optional[dict] = None):
        if status not in STATUSES or status == "MATCH":
            raise ValueError(f"refusal status must be a non-MATCH conformance status, got {status!r}")
        self.status = status
        self.details = details or {}
        super().__init__(f"{status}: {message}")


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _sha(payload: Any) -> str:
    return hashlib.sha256(_canon(payload).encode("utf-8")).hexdigest()


def _norm_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return " ".join(value.split())


def _as_inputs(value: Any) -> Any:
    if value == UNMAPPED or value is None:
        return UNMAPPED
    if isinstance(value, (list, tuple)):
        return sorted(str(v) for v in value)
    return value


def _present(spec: Mapping, key: str) -> Any:
    value = spec.get(key)
    if value is None or value == "" or value == [] or value == {}:
        return UNMAPPED
    if isinstance(value, str):
        return _norm_text(value)
    return value


def _formula_of(spec: Mapping) -> Any:
    formula = spec.get("formula")
    if isinstance(formula, str) and formula.strip():
        return _norm_text(formula)
    numerator = spec.get("numerator")
    denominator = spec.get("denominator")
    if isinstance(numerator, str) and isinstance(denominator, str) and numerator and denominator:
        return _norm_text(f"{numerator} / {denominator}")
    return UNMAPPED


def _behavior(spec: Mapping) -> dict:
    """Copy only fields the ontology actually states. Missing stays UNMAPPED."""
    inputs = spec.get("depends_on")
    if inputs is None:
        inputs = spec.get("source_inputs")
    return {
        "formula": _formula_of(spec),
        "source_inputs": _as_inputs(inputs) if inputs not in (None, "", []) else UNMAPPED,
        "lookback": _present(spec, "lookback"),
        "warmup": _present(spec, "warmup"),
        "timing": _present(spec, "timing") if spec.get("timing") is not None else (
            _present(spec, "value_timestamp") if spec.get("value_timestamp") is not None else UNMAPPED
        ),
        "units": _present(spec, "units"),
        "normalization": _present(spec, "normalization")
        if spec.get("normalization") is not None
        else _present(spec, "normalization_policy"),
        "encoding": _present(spec, "bounds") if spec.get("bounds") is not None else _present(spec, "encoding"),
        "missing_value_policy": _present(spec, "missing_value_policy"),
        "edge_cases": _present(spec, "edge_cases"),
        "causal_availability": _present(spec, "causal_availability")
        if spec.get("causal_availability") is not None
        else _present(spec, "available_at_timestamp"),
    }


def _blank_behavior() -> dict:
    return {field: UNMAPPED for field in BEHAVIOR_FIELDS}


def _definition_from_spec(section: str, entry_name: str, spec: Mapping, vector_index: Optional[int]) -> dict:
    behavior = _behavior(spec)
    concept_id = spec.get("id")
    if not isinstance(concept_id, str) or not concept_id:
        concept_id = UNMAPPED
    definition = {
        "concept_id": concept_id,
        "entry_name": entry_name,
        "ontology_section": section,
        "ontology_version": spec.get("version", UNMAPPED),
        "vector_index": vector_index,
        "vector_key": (spec.get("lineage") or {}).get("vector_key") or entry_name,
        **behavior,
    }
    definition["definition_hash"] = feature_definition_hash(definition)
    return definition


def feature_definition_hash(definition: Mapping) -> str:
    """Hash behavior fields and concept_id. Names and sibling order are excluded."""
    payload = {"concept_id": definition.get("concept_id", UNMAPPED)}
    for field in BEHAVIOR_FIELDS:
        payload[field] = definition.get(field, UNMAPPED)
    return _sha(payload)


def build_contract() -> dict:
    """Build the versioned contract from the ontology. Does not invent formulas."""
    ont = load_ontology()
    prefix = list(CANONICAL_FEATURES[:SCHEMA_V2_FEATURE_DIM])
    if len(prefix) != SCHEMA_V2_FEATURE_DIM:
        raise RuntimeError("35-feature prefix length drifted from SCHEMA_V2_FEATURE_DIM")

    by_vector_key: dict[str, list] = {}
    by_id: dict[str, dict] = {}
    for section in _ITERATED_SECTIONS:
        for entry_name, spec in (ont.get(section) or {}).items():
            if not isinstance(spec, dict):
                continue
            lineage = spec.get("lineage") or {}
            raw_index = lineage.get("vector_index")
            vector_index = raw_index if isinstance(raw_index, int) else None
            definition = _definition_from_spec(section, entry_name, spec, vector_index)
            concept_id = definition["concept_id"]
            if concept_id != UNMAPPED:
                if concept_id in by_id:
                    definition = {
                        **definition,
                        "concept_id": AMBIGUOUS_TOKEN,
                        "formula": AMBIGUOUS_TOKEN,
                        "collides_with": by_id[concept_id]["entry_name"],
                    }
                    definition["definition_hash"] = feature_definition_hash(definition)
                else:
                    by_id[concept_id] = definition
            key = lineage.get("vector_key")
            if isinstance(key, str) and key:
                by_vector_key.setdefault(key, []).append(definition)

    features = []
    for index, name in enumerate(CANONICAL_FEATURES):
        claimants = by_vector_key.get(name, [])
        if len(claimants) == 1:
            slot = dict(claimants[0])
            slot["slot_name"] = name
            slot["vector_index"] = index
            slot["binding"] = "UNIQUE"
        elif len(claimants) == 0:
            slot = {
                "concept_id": UNMAPPED,
                "entry_name": UNMAPPED,
                "ontology_section": UNMAPPED,
                "ontology_version": UNMAPPED,
                "vector_index": index,
                "vector_key": name,
                "slot_name": name,
                "binding": "UNMAPPED",
                **_blank_behavior(),
            }
            slot["definition_hash"] = feature_definition_hash(slot)
        else:
            slot = {
                "concept_id": AMBIGUOUS_TOKEN,
                "entry_name": AMBIGUOUS_TOKEN,
                "ontology_section": AMBIGUOUS_TOKEN,
                "ontology_version": AMBIGUOUS_TOKEN,
                "vector_index": index,
                "vector_key": name,
                "slot_name": name,
                "binding": "AMBIGUOUS",
                "claimants": [item["concept_id"] for item in claimants],
                **_blank_behavior(),
            }
            slot["formula"] = AMBIGUOUS_TOKEN
            slot["definition_hash"] = feature_definition_hash(slot)
        features.append(slot)

    adjacent = []
    for concept_id, definition in sorted(by_id.items()):
        if definition.get("vector_index") in (None, [], ""):
            adjacent.append(definition)

    contract = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "schema_prefix_dim": SCHEMA_V2_FEATURE_DIM,
        "schema_prefix_order": prefix,
        "prefix_frozen": True,
        "full_vector_order": list(CANONICAL_FEATURES),
        "full_vector_dim": len(CANONICAL_FEATURES),
        "economic_claims_allowed": False,
        "production_formulas_changed": False,
        "aliases_are_not_equivalence": dict(_READ_ALIASES),
        "features": features,
        "adjacent_concepts": adjacent,
    }
    contract["contract_hash"] = contract_hash(contract)
    return contract


def contract_hash(contract: Mapping) -> str:
    """Deterministic hash of order plus every behavior field. Not a name hash."""
    rows = []
    for feature in contract["features"]:
        rows.append(
            {
                "vector_index": feature.get("vector_index"),
                "slot_name": feature.get("slot_name"),
                "definition_hash": feature.get("definition_hash")
                or feature_definition_hash(feature),
            }
        )
    payload = {
        "contract_id": contract["contract_id"],
        "contract_version": contract["contract_version"],
        "schema_prefix_order": list(contract["schema_prefix_order"]),
        "features": rows,
    }
    return _sha(payload)


def _index_contract(contract: Mapping) -> dict:
    by_name = {}
    by_id = {}
    for feature in contract["features"]:
        by_name[feature["slot_name"]] = feature
        concept_id = feature.get("concept_id")
        if isinstance(concept_id, str) and concept_id not in (UNMAPPED, AMBIGUOUS_TOKEN):
            by_id[concept_id] = feature
    for feature in contract.get("adjacent_concepts") or []:
        concept_id = feature.get("concept_id")
        if isinstance(concept_id, str) and concept_id not in by_id:
            by_id[concept_id] = feature
    return {"by_name": by_name, "by_id": by_id}


def _evidence_is_source(evidence: Optional[Sequence[Mapping]]) -> bool:
    if not evidence:
        return False
    return any(isinstance(item, Mapping) and item.get("kind") == SOURCE_EVIDENCE for item in evidence)


def _normalize_implementation(implementation: Optional[Mapping]) -> dict:
    base = _blank_behavior()
    if not implementation:
        return base
    for field in BEHAVIOR_FIELDS:
        if field not in implementation or implementation[field] in (None, ""):
            continue
        value = implementation[field]
        if field == "formula" and isinstance(value, str):
            value = _norm_text(value)
        if field == "source_inputs":
            value = _as_inputs(value)
        base[field] = value
    return base


def _compare_fields(canonical: Mapping, implementation: Mapping) -> str:
    """One status for a field-by-field comparison. DRIFT outranks gaps."""
    saw_unmapped = False
    saw_unverified = False
    for field in BEHAVIOR_FIELDS:
        left = canonical.get(field, UNMAPPED)
        right = implementation.get(field, UNMAPPED)
        if left == AMBIGUOUS_TOKEN or right == AMBIGUOUS_TOKEN:
            return "AMBIGUOUS"
        if left == UNMAPPED and right == UNMAPPED:
            saw_unmapped = True
            continue
        if left == UNMAPPED and right != UNMAPPED:
            saw_unmapped = True
            continue
        if left != UNMAPPED and right == UNMAPPED:
            saw_unverified = True
            continue
        if left != right:
            return "DRIFT"
    if saw_unverified:
        return "UNVERIFIED"
    if saw_unmapped:
        return "UNMAPPED"
    return "MATCH"


def _transformation_resolves(transformation: Optional[Mapping], canonical: Mapping) -> Optional[str]:
    """A reviewed, versioned transformation may resolve a difference.

    An alias string is not a transformation. An unreviewed block is ignored.
    """
    if not transformation:
        return None
    if transformation.get("reviewed") is not True:
        return None
    if not transformation.get("transformation_id") or not transformation.get("version"):
        return None
    output = transformation.get("output")
    if not isinstance(output, Mapping):
        return "DRIFT"
    return _compare_fields(canonical, _normalize_implementation(output))


def check_consumer(
    surface_name: str,
    *,
    contract: Optional[Mapping] = None,
    implementation: Optional[Mapping] = None,
    evidence: Optional[Sequence[Mapping]] = None,
    concept_id: Optional[str] = None,
    transformation: Optional[Mapping] = None,
) -> dict:
    """Return exactly one conformance status for one consumer or producer claim."""
    contract = contract or build_contract()
    index = _index_contract(contract)
    aliases = contract.get("aliases_are_not_equivalence") or _READ_ALIASES
    alias_target = aliases.get(surface_name)
    named = index["by_name"].get(surface_name)
    target = None
    alias_used = False

    if concept_id:
        declared = index["by_id"].get(concept_id)
        if declared is None:
            return _result("UNMAPPED", surface_name, concept_id, "declared concept_id is not in the contract")
        if named and named.get("concept_id") not in (UNMAPPED, AMBIGUOUS_TOKEN, concept_id):
            return _result(
                "AMBIGUOUS",
                surface_name,
                concept_id,
                f"surface {surface_name} binds to {named.get('concept_id')} but the claim declares {concept_id}",
            )
        target = declared
    elif named is not None:
        if named.get("binding") == "AMBIGUOUS" or named.get("concept_id") == AMBIGUOUS_TOKEN:
            return _result(
                "AMBIGUOUS",
                surface_name,
                AMBIGUOUS_TOKEN,
                f"slot {surface_name} has multiple ontology claimants",
                extra={"claimants": named.get("claimants")},
            )
        if named.get("concept_id") == UNMAPPED:
            return _result("UNMAPPED", surface_name, UNMAPPED, f"no ontology concept for {surface_name}")
        target = named
    elif alias_target:
        alias_used = True
        target = index["by_name"].get(alias_target)
        if target is None or target.get("concept_id") in (UNMAPPED, AMBIGUOUS_TOKEN):
            return _result(
                "UNMAPPED",
                surface_name,
                UNMAPPED,
                f"alias {surface_name}->{alias_target} has no contracted target",
                extra={"alias_used": True, "alias_is_not_proof": True},
            )
    else:
        return _result("UNMAPPED", surface_name, UNMAPPED, f"{surface_name} is not a contracted slot")

    if not _evidence_is_source(evidence):
        return _result(
            "UNVERIFIED",
            surface_name,
            target.get("concept_id"),
            "no source evidence; name, width, manifest row, or alias is not equivalence",
            extra={"alias_used": alias_used, "alias_is_not_proof": True},
        )

    if not implementation:
        return _result(
            "UNVERIFIED",
            surface_name,
            target.get("concept_id"),
            "source cited but no implementation fields were declared",
            extra={"alias_used": alias_used, "alias_is_not_proof": True},
        )

    normalized = _normalize_implementation(implementation)
    status = _compare_fields(target, normalized)
    resolved_by = None
    transformed = _transformation_resolves(transformation, target)
    if transformed == "MATCH":
        status = "MATCH"
        resolved_by = transformation.get("transformation_id")
    elif alias_used and status not in ("DRIFT", "AMBIGUOUS"):
        # An alias is not proof. A concrete mismatch stays DRIFT. A copied
        # definition, including one that is still UNMAPPED, stays UNVERIFIED
        # until a reviewed transformation's output equals the target.
        status = "UNVERIFIED"

    return _result(
        status,
        surface_name,
        target.get("concept_id"),
        "field comparison against the contracted definition",
        extra={
            "alias_used": alias_used,
            "alias_is_not_proof": True,
            "resolved_by": resolved_by,
            "definition_hash": target.get("definition_hash"),
            "implementation_hash": feature_definition_hash(
                {"concept_id": target.get("concept_id"), **normalized}
            ),
        },
    )


# Aggregate rank. A concrete mismatch stays visible when another slot is only
# unverified: DRIFT outranks every gap status.
_AGGREGATE_RANK = {
    "MATCH": 0,
    "UNMAPPED": 1,
    "AMBIGUOUS": 2,
    "UNVERIFIED": 3,
    "DRIFT": 4,
}


def _aggregate_status(statuses: Sequence[str]) -> str:
    worst = "MATCH"
    for status in statuses:
        if status not in _AGGREGATE_RANK:
            raise RuntimeError(f"checker produced {status!r}")
        if _AGGREGATE_RANK[status] > _AGGREGATE_RANK[worst]:
            worst = status
    return worst


def check_vector(
    order: Sequence[str],
    *,
    contract: Optional[Mapping] = None,
    implementations: Optional[Mapping[str, Mapping]] = None,
    evidence: Optional[Sequence[Mapping]] = None,
) -> dict:
    """Width or order equality is not semantic compatibility."""
    contract = contract or build_contract()
    prefix = list(contract["schema_prefix_order"])
    order = list(order)
    if len(order) != len(prefix) or order != prefix:
        return {
            "status": "DRIFT",
            "reason": "vector order or dimension differs from the frozen 35-feature prefix",
            "expected_dim": len(prefix),
            "got_dim": len(order),
            "expected_order": prefix,
            "got_order": order,
        }
    if not implementations:
        return {
            "status": "UNVERIFIED",
            "reason": "prefix order matches; dimension equality does not establish semantic compatibility",
            "expected_dim": len(prefix),
            "got_dim": len(order),
        }
    per_slot = []
    for name in prefix:
        item = check_consumer(
            name,
            contract=contract,
            implementation=(implementations or {}).get(name),
            evidence=evidence,
        )
        per_slot.append(item)
    return {
        "status": _aggregate_status(item["status"] for item in per_slot),
        "slots": per_slot,
        "expected_dim": len(prefix),
        "got_dim": len(order),
    }


def _result(status: str, surface_name: str, concept_id: Any, reason: str, extra: Optional[dict] = None) -> dict:
    if status not in STATUSES:
        raise RuntimeError(f"checker produced {status!r}")
    out = {
        "status": status,
        "surface_name": surface_name,
        "concept_id": concept_id,
        "reason": reason,
    }
    if extra:
        out.update(extra)
    return out


def evaluate_artifact_binding(
    feature_names: Sequence[str],
    declared: Optional[Mapping],
    *,
    contract: Optional[Mapping] = None,
) -> dict:
    """Bind a serialized model to the contract.

    A declared hash equal to the current contract is still not MATCH while any
    required definition field is UNMAPPED. Absent declaration is UNVERIFIED.
    Dimension and alias resolution are ignored on purpose.
    """
    contract = contract or build_contract()
    names = [str(name) for name in feature_names]
    if not names:
        return {
            "status": "UNVERIFIED",
            "reason": "artifact names no features; width is not semantic compatibility",
            "feature_names": names,
            "contract_hash": contract["contract_hash"],
        }
    if not declared:
        return {
            "status": "UNVERIFIED",
            "reason": "artifact has no semantic contract; n_features and aliases are not compatibility",
            "feature_names": names,
            "contract_hash": contract["contract_hash"],
        }
    declared_hash = declared.get("contract_hash")
    if declared_hash != contract["contract_hash"]:
        return {
            "status": "DRIFT",
            "reason": "artifact semantic contract hash does not equal the current definition hash",
            "declared_contract_hash": declared_hash,
            "contract_hash": contract["contract_hash"],
            "feature_names": names,
        }
    index = _index_contract(contract)
    per_feature = []
    for name in names:
        if name in _READ_ALIASES:
            # A read-side rename is not a reviewed transformation and is not proof.
            per_feature.append(
                {
                    "surface_name": name,
                    "resolved_name": _READ_ALIASES[name],
                    "status": "UNVERIFIED",
                    "alias_is_not_proof": True,
                }
            )
            continue
        slot = index["by_name"].get(name)
        if slot is None or slot.get("concept_id") == UNMAPPED:
            status = "UNMAPPED"
        elif slot.get("concept_id") == AMBIGUOUS_TOKEN or slot.get("binding") == "AMBIGUOUS":
            status = "AMBIGUOUS"
        else:
            # Same object on both sides. MATCH only when every behavior field is concrete.
            status = _compare_fields(slot, _behavior_view(slot))
        per_feature.append({"surface_name": name, "resolved_name": name, "status": status})
    return {
        "status": _aggregate_status(item["status"] for item in per_feature),
        "reason": "artifact hash binds to this contract snapshot; unresolved definitions stay unresolved",
        "contract_hash": contract["contract_hash"],
        "features": per_feature,
    }


def _behavior_view(slot: Mapping) -> dict:
    return {field: slot.get(field, UNMAPPED) for field in BEHAVIOR_FIELDS}


def require_artifact_compatible(
    feature_names: Sequence[str],
    declared: Optional[Mapping],
    *,
    contract: Optional[Mapping] = None,
    what: str = "model",
) -> dict:
    """Fail closed unless the artifact binding status is MATCH."""
    binding = evaluate_artifact_binding(feature_names, declared, contract=contract)
    if binding["status"] != "MATCH":
        raise FeatureSemanticIncompatible(
            binding["status"],
            f"{what} semantic binding is {binding['status']}: {binding['reason']}",
            binding,
        )
    return binding


def require_training_feature_contract(
    feature_names: Sequence[str],
    *,
    contract: Optional[Mapping] = None,
) -> dict:
    """Training entry point. Width-only matrices are not accepted here.

    Callers that still fit an unnamed matrix do not pass through this function.
    A named training set loads only when every named feature is MATCH.
    """
    contract = contract or build_contract()
    implementations = {}
    index = _index_contract(contract)
    for name in feature_names:
        raw = str(name)
        if raw in _READ_ALIASES:
            raise FeatureSemanticIncompatible(
                "UNVERIFIED",
                f"training feature {raw!r} is a read-side alias of "
                f"{_READ_ALIASES[raw]!r}; an alias is not semantic equivalence",
                {"surface_name": raw, "alias_target": _READ_ALIASES[raw]},
            )
        slot = index["by_name"].get(raw)
        if slot is None or slot.get("concept_id") in (UNMAPPED, AMBIGUOUS_TOKEN):
            raise FeatureSemanticIncompatible(
                "UNMAPPED" if slot is None or slot.get("concept_id") == UNMAPPED else "AMBIGUOUS",
                f"training feature {raw!r} is not a unique contracted concept",
            )
        implementations[raw] = _behavior_view(slot)
    for name in feature_names:
        raw = str(name)
        result = check_consumer(
            raw,
            contract=contract,
            implementation=implementations[raw],
            evidence=[{
                "path": "src/features/semantic_equivalence.py",
                "lines": "require_training_feature_contract",
                "kind": SOURCE_EVIDENCE,
            }],
        )
        if result["status"] != "MATCH":
            raise FeatureSemanticIncompatible(
                result["status"],
                f"training feature {raw} is {result['status']}: {result['reason']}",
                result,
            )
    return {"status": "MATCH", "n_features": len(list(feature_names))}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(*, contract: Optional[Mapping] = None) -> dict:
    """Per-edge status. Manifest consumers are preserved as their own edges."""
    contract = contract or build_contract()
    manifest = _load_json(_MANIFEST_PATH)
    overlay = _load_json(_BRANCH_PATH)
    edges = []
    for consumer in manifest.get("consumers") or []:
        edges.append(
            {
                "branch_id": f"manifest:{consumer.get('consumer')}",
                "parent_consumer": consumer.get("consumer"),
                "role": consumer.get("type"),
                "entrypoint": consumer.get("entrypoint"),
                "preserved_verdict": consumer.get("compatibility_verdict"),
                "status": "UNVERIFIED",
                "reason": (
                    "binding-manifest row preserved; its feature list and verdict "
                    "are not semantic equivalence"
                ),
                "evidence": [
                    {
                        "path": str(_MANIFEST_PATH.relative_to(_REPO)).replace("\\", "/"),
                        "kind": "manifest",
                    }
                ],
                "surface_names": consumer.get("features") or [],
            }
        )
    for edge in overlay.get("edges") or []:
        if edge.get("vector_order") is not None:
            checked = check_vector(
                edge["vector_order"],
                contract=contract,
                implementations=edge.get("implementations"),
                evidence=edge.get("evidence"),
            )
            result = {
                "status": checked["status"],
                "reason": checked.get("reason"),
            }
        else:
            result = check_consumer(
                edge["surface_name"],
                contract=contract,
                implementation=edge.get("implementation"),
                evidence=edge.get("evidence"),
                concept_id=edge.get("concept_id"),
                transformation=edge.get("transformation"),
            )
        edges.append(
            {
                "branch_id": edge["branch_id"],
                "parent_consumer": edge.get("parent_consumer"),
                "role": edge.get("role"),
                "entrypoint": edge.get("entrypoint"),
                "surface_name": edge.get("surface_name"),
                "concept_id": result.get("concept_id", edge.get("concept_id")),
                "status": result["status"],
                "reason": result.get("reason"),
                "evidence": edge.get("evidence") or [],
                "alias_used": result.get("alias_used", False),
                "resolved_by": result.get("resolved_by"),
                "note": edge.get("note"),
            }
        )
    counts = {status: 0 for status in STATUSES}
    for edge in edges:
        counts[edge["status"]] = counts.get(edge["status"], 0) + 1
    consistent = counts["MATCH"] == len(edges) and len(edges) > 0
    return {
        "contract_id": contract["contract_id"],
        "contract_version": contract["contract_version"],
        "contract_hash": contract["contract_hash"],
        "schema_prefix_dim": contract["schema_prefix_dim"],
        "schema_prefix_order": contract["schema_prefix_order"],
        "architecture_semantically_consistent": consistent,
        "economic_claims_allowed": False,
        "counts": counts,
        "edges": edges,
    }


def change_impact(audit_report: Mapping, contract: Optional[Mapping] = None) -> dict:
    """Which branches a change to each concept would touch. Not a migration."""
    contract = contract or build_contract()
    index = _index_contract(contract)
    impacts = []
    for feature in contract["features"]:
        concept_id = feature.get("concept_id")
        name = feature.get("slot_name")
        affected = []
        for edge in audit_report["edges"]:
            surface = edge.get("surface_name")
            names = edge.get("surface_names") or []
            hit = (
                edge.get("concept_id") == concept_id
                or surface == name
                or name in names
                or (surface in _READ_ALIASES and _READ_ALIASES[surface] == name)
            )
            if hit:
                affected.append(
                    {
                        "branch_id": edge["branch_id"],
                        "status": edge["status"],
                        "parent_consumer": edge.get("parent_consumer"),
                    }
                )
        impacts.append(
            {
                "concept_id": concept_id,
                "slot_name": name,
                "vector_index": feature.get("vector_index"),
                "in_frozen_prefix": isinstance(feature.get("vector_index"), int)
                and feature["vector_index"] < SCHEMA_V2_FEATURE_DIM,
                "definition_hash": feature.get("definition_hash"),
                "definition_complete": _compare_fields(feature, _behavior_view(feature)) == "MATCH",
                "affected_branches": affected,
            }
        )
    return {
        "contract_hash": contract["contract_hash"],
        "note": (
            "A definition change moves definition_hash and contract_hash. "
            "Branches listed here are the ones that would have to be re-checked. "
            "This report does not migrate them."
        ),
        "unmapped_slot_count": sum(1 for row in impacts if row["concept_id"] == UNMAPPED),
        "impacts": impacts,
        "index_size": len(index["by_id"]),
    }


def write_reports(dest: Optional[Path] = None) -> dict:
    """Write the audit, the consumer graph, and the change-impact report."""
    dest = dest or _REPORT_DIR
    dest.mkdir(parents=True, exist_ok=True)
    contract = build_contract()
    report = audit(contract=contract)
    impact = change_impact(report, contract)
    graph = {
        "graph_id": "feature-semantic-consumer-graph-v1",
        "preserves": str(_MANIFEST_PATH.relative_to(_REPO)).replace("\\", "/"),
        "contract_hash": contract["contract_hash"],
        "architecture_semantically_consistent": report["architecture_semantically_consistent"],
        "nodes": sorted({edge.get("parent_consumer") or edge["branch_id"] for edge in report["edges"]}),
        "edges": report["edges"],
    }
    (dest / "feature_semantic_contract_v1.json").write_text(
        json.dumps(contract, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (dest / "feature_semantic_equivalence_audit.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (dest / "feature_semantic_change_impact.json").write_text(
        json.dumps(impact, indent=2) + "\n", encoding="utf-8"
    )
    (dest / "feature_semantic_consumer_graph_v1.json").write_text(
        json.dumps(graph, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Feature semantic equivalence audit",
        "",
        f"Contract `{contract['contract_id']}` version `{contract['contract_version']}`.",
        f"Contract hash `{contract['contract_hash']}`.",
        "",
        "The frozen 35-feature prefix order is unchanged. This audit does not migrate it.",
        "Name equality, vector length, read-side aliases, and schema hashes are not semantic equivalence.",
        "Semantic conformance is not model quality, execution correctness, or profitability.",
        "",
        f"Architecture semantically consistent: **{report['architecture_semantically_consistent']}**.",
        "",
        "| Status | Edges |",
        "|---|---:|",
    ]
    for status in STATUSES:
        lines.append(f"| {status} | {report['counts'][status]} |")
    lines.extend(["", "| Branch | Concept | Status | Evidence |", "|---|---|---|---|"])
    for edge in report["edges"]:
        evidence = edge.get("evidence") or []
        cite = ""
        if evidence:
            first = evidence[0]
            cite = f"`{first.get('path')}`"
            if first.get("lines"):
                cite += f" {first.get('lines')}"
        lines.append(
            f"| `{edge['branch_id']}` | {edge.get('concept_id') or edge.get('surface_name') or ''} | {edge['status']} | {cite} |"
        )
    lines.extend(
        [
            "",
            "Unresolved edges stay UNMAPPED, AMBIGUOUS, or UNVERIFIED. They are not promoted to MATCH.",
            "No production formula, model artifact, or config was edited to produce this report.",
            "",
        ]
    )
    (dest / "feature_semantic_equivalence_audit.md").write_text("\n".join(lines), encoding="utf-8")
    return {"audit": report, "impact": impact, "contract_hash": contract["contract_hash"]}


def main() -> None:
    written = write_reports()
    print(written["contract_hash"])
    print(written["audit"]["counts"])
    print("architecture_semantically_consistent", written["audit"]["architecture_semantically_consistent"])


if __name__ == "__main__":
    main()
