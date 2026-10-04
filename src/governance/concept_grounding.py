"""Grounding for the Semantic OS v2 meaning plane (SEMANTIC_OS_V2_MEANING_PLANE.md §15).

Two claim kinds and two relations, reached through SemanticGrounder.ground:

  CONCEPT          concept id (incl. stage ids), canonical_name or alias -> the concept contract
  REPRESENTATION   `producer:key` or a bare key unique across shards -> the representation
  represents       representation --represents--> concept
  input_of         concept --input_of--> concept

The registries are read through `semantics.registry` loaders (one parser, I-8).
G-1: a PROPOSED concept grounds with a caveat. G-2: unmapped -> UNKNOWN, deprecated -> REFUSED.
G-3: NOUN never falls through to here. G-4: consumers are HEURISTIC.
Advisory only; grants no runtime authority (CLAUDE.md §6.5).
"""

from __future__ import annotations

from typing import Any, Optional

from governance.semantic_grounding import (
    GROUNDED, HEURISTIC, PROVEN, REFUSED, Grounding, _ambiguous, _hit, _unknown,
)

_CONCEPTS_FILE = "configs/formulas/concept_contracts.yaml"
_SHARD_DIR = "configs/formulas/representation_registry"
_PROPOSED_CAVEAT = (
    "PROPOSED: the rule is not accepted and nothing may bind to it (I-18). "
    "Naming it is grounded; asserting its rule as fact is not."
)
_CONSUMER_CAVEAT = (
    "consumers are HEURISTIC (AST name match; a homonym can be a false consumer) — where to look, not proof."
)


class MeaningPlane:
    """Loaded v2 registries plus lazily derived consumers."""

    def __init__(self, concepts: dict, shards: dict) -> None:
        self.concepts = concepts
        self.shards = shards
        self._consumers: Optional[dict] = None

    @classmethod
    def load(cls) -> "MeaningPlane":
        from semantics.registry import load_concept_contracts, load_representation_shards

        return cls(load_concept_contracts().get("concepts") or {}, load_representation_shards())

    @property
    def consumers(self) -> dict:
        if self._consumers is None:
            from semantics.consumers import consumers_by_concept

            self._consumers = consumers_by_concept(self.shards)
        return self._consumers

    # ---------------------------------------------------------------- lookup

    def resolve_concept(self, token: str) -> tuple[Optional[str], list[str]]:
        """(concept_id, candidates). Ids match exactly; names and aliases case-insensitively."""
        raw = str(token or "").strip()
        if raw in self.concepts:
            return raw, [raw]
        low = raw.lower()
        hits = []
        for cid, rec in self.concepts.items():
            if not isinstance(rec, dict):
                continue
            names = [rec.get("canonical_name")] + list(rec.get("aliases") or [])
            if any(isinstance(n, str) and n.lower() == low for n in names):
                hits.append(cid)
        if len(hits) == 1:
            return hits[0], hits
        return None, hits

    def representations_of(self, concept_id: str) -> list[str]:
        found = []
        for shard in self.shards.values():
            producer = shard.get("producer_id")
            for key, rep in (shard.get("representations") or {}).items():
                if isinstance(rep, dict) and rep.get("concept_id") == concept_id:
                    found.append(f"{producer}:{key}")
        return sorted(found)

    def resolve_representation(self, token: str) -> tuple[str, list[tuple[str, str, str, Any]]]:
        """('ok'|'none', [(shard_file, producer, key, (section, value))]) over representations,
        deprecated and unmapped."""
        raw = str(token or "").strip()
        producer, _, key = raw.partition(":") if ":" in raw else ("", "", raw)
        found = []
        for name, shard in self.shards.items():
            if producer and shard.get("producer_id") != producer:
                continue
            for section in ("representations", "deprecated", "unmapped"):
                entries = shard.get(section) or {}
                if key in entries:
                    found.append((name, str(shard.get("producer_id")), key, (section, entries[key])))
        return ("ok" if found else "none"), found


# -------------------------------------------------------------------- claims

def ground_concept(plane: MeaningPlane, token: str) -> Grounding:
    cid, candidates = plane.resolve_concept(token)
    if cid is None:
        if len(candidates) > 1:
            return _ambiguous("CONCEPT", token, candidates)
        return _unknown("CONCEPT", token, f"no v2 concept, canonical_name or alias matches {token!r}")
    rec = plane.concepts[cid]
    authority = rec.get("authority") if isinstance(rec.get("authority"), dict) else {}
    consumers = plane.consumers.get(cid, [])
    payload = {
        "concept_id": cid,
        "canonical_name": rec.get("canonical_name"),
        "aliases": list(rec.get("aliases") or []),
        "layer": rec.get("layer"),
        "kind": rec.get("kind"),
        "status": rec.get("status"),
        "definition": rec.get("definition"),
        "rule": rec.get("rule"),
        "parameters": sorted((rec.get("parameterization") or {}).keys()),
        "inputs": list(rec.get("inputs") or []),
        "divergences": [
            {k: d.get(k) for k in ("surface", "disposition", "decide_in", "decided_in") if k in d}
            for d in (rec.get("divergences") or []) if isinstance(d, dict)
        ],
        "representations": plane.representations_of(cid),
        "consumers": consumers,
        "consumers_evidence_class": HEURISTIC,
    }
    caveats = [_CONSUMER_CAVEAT]
    if rec.get("status") == "PROPOSED":
        caveats.insert(0, _PROPOSED_CAVEAT)
    return _hit(
        "CONCEPT", token, authority="concept_contracts", record_id=cid, record_kind="concept",
        evidence_class=PROVEN, artifacts=[_CONCEPTS_FILE] + list(authority.get("sources") or []),
        payload=payload, caveats=caveats,
    )


def ground_representation(plane: MeaningPlane, token: str) -> Grounding:
    _status, found = plane.resolve_representation(token)
    if not found:
        return _unknown("REPRESENTATION", token, f"no representation shard declares {token!r}")
    if len(found) > 1:
        return _ambiguous("REPRESENTATION", token, [f"{p}:{k}" for _n, p, k, _v in found])
    from semantics.consumers import representation_consumers

    shard_file, producer, key, (section, value) = found[0]
    rid = f"{producer}:{key}"
    artifact = f"{_SHARD_DIR}/{shard_file}"
    if section == "unmapped":
        return _unknown("REPRESENTATION", token, f"{rid} is unmapped: {value}")
    if section == "deprecated":
        return Grounding(
            claim_kind="REPRESENTATION", token=token, status=REFUSED,
            authority="representation_registry", record_id=rid, record_kind="representation",
            artifacts=[artifact], payload={"deprecated": value},
            ungrounded_reason=f"{rid} is deprecated (I-13: marked dead, never asserted): {value}",
            caveats=["REFUSED is not GROUNDED and not UNKNOWN — do not assert this representation."],
        )
    payload = {
        "representation": rid,
        "producer": producer,
        "schema_version": plane.shards[shard_file].get("schema_version"),
        "concept_id": value.get("concept_id"),
        "parameterization": dict(value.get("parameterization") or {}),
        "encoding": value.get("encoding"),
        "absence": value.get("absence"),
        "divergence_ref": value.get("divergence_ref"),
        "consumers": representation_consumers(producer, key),
        "consumers_evidence_class": HEURISTIC,
    }
    return _hit(
        "REPRESENTATION", token, authority="representation_registry", record_id=rid,
        record_kind="representation", evidence_class=PROVEN, artifacts=[artifact],
        payload=payload, caveats=[_CONSUMER_CAVEAT],
    )


def ground_meaning_relation(plane: MeaningPlane, relation: str, source: str, target: str) -> Grounding:
    token = f"{source} --{relation}--> {target}"
    if relation == "represents":
        src = ground_representation(plane, source)
        if src.status != GROUNDED:
            return _unknown("RELATIONSHIP", token, f"source not grounded: {src.ungrounded_reason}")
        dst = ground_concept(plane, target)
        if dst.status != GROUNDED:
            return _unknown("RELATIONSHIP", token, f"target not grounded: {dst.ungrounded_reason}")
        if src.payload["concept_id"] != dst.record_id:
            return _unknown("RELATIONSHIP", token,
                            f"{src.record_id} represents {src.payload['concept_id']}, not {dst.record_id}")
        return _hit("RELATIONSHIP", token, authority="representation_registry",
                    record_id=f"{src.record_id}->{dst.record_id}", record_kind="represents",
                    evidence_class=PROVEN, artifacts=src.artifacts,
                    payload={"representation": src.record_id, "concept_id": dst.record_id})
    src = ground_concept(plane, source)
    if src.status != GROUNDED:
        return _unknown("RELATIONSHIP", token, f"source not grounded: {src.ungrounded_reason}")
    dst = ground_concept(plane, target)
    if dst.status != GROUNDED:
        return _unknown("RELATIONSHIP", token, f"target not grounded: {dst.ungrounded_reason}")
    if src.record_id not in dst.payload["inputs"]:
        return _unknown("RELATIONSHIP", token, f"{src.record_id} is not an input of {dst.record_id}")
    return _hit("RELATIONSHIP", token, authority="concept_contracts",
                record_id=f"{src.record_id}->{dst.record_id}", record_kind="input_of",
                evidence_class=PROVEN, artifacts=[_CONCEPTS_FILE],
                payload={"input": src.record_id, "concept_id": dst.record_id})
