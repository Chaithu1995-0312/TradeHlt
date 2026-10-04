"""Identity contract (SEMANTIC_OS_V2_MEANING_PLANE.md §5).

    SEMANTIC        = (concept_id, kind, reference, timeframe, clock, availability_rule)
    PARAMETERIZATION= identity-bearing parameters only            -> parameterization_id
    SETTINGS        = config_hash / config_version                 (lineage; never identity)
    REPRESENTATION  = SEMANTIC + parameterization_id + producer_id + encoding + schema_version
    INSTANCE        = SEMANTIC + parameterization_id + instance_key (NO producer: engine and
                      resolver describing the same bar are two representations, never one id —
                      L3 §7.2 forbidden equality)

`parameterization_id` reuses `crt_identity_schema.derive_constructor_id` (the canonical-JSON sha256
the frozen L3 contract already uses for constructor identity) so both ids share one discipline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Optional

from config_layer.crt_identity_schema import derive_constructor_id


def _canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SemanticIdentity:
    concept_id: str
    kind: str
    reference: str
    timeframe: str
    clock: str
    availability_rule: str

    @property
    def id(self) -> str:
        return _canonical_hash(asdict(self))


def parameterization_id(
    concept_id: str,
    params: Mapping[str, Any],
    identity_bearing: Iterable[str],
) -> str:
    """Hash of the identity-bearing parameter VALUES only.

    A settings change that alters an identity-bearing value yields a new id (I-17); a change to
    any other key does not. A missing identity-bearing key is an error, never a default.
    """
    names = sorted(set(identity_bearing))
    missing = [n for n in names if n not in params]
    if missing:
        raise KeyError(f"{concept_id}: identity-bearing parameter(s) missing: {missing}")
    return derive_constructor_id({
        "construction": concept_id,
        "invocation": {n: params[n] for n in names},
    })


@dataclass(frozen=True)
class RepresentationIdentity:
    semantic: SemanticIdentity
    parameterization_id: str
    producer_id: str
    encoding: str
    schema_version: str

    @property
    def id(self) -> str:
        return _canonical_hash({
            "semantic": self.semantic.id,
            "parameterization_id": self.parameterization_id,
            "producer_id": self.producer_id,
            "encoding": self.encoding,
            "schema_version": self.schema_version,
        })


@dataclass(frozen=True)
class InstanceKey:
    anchor: str            # formed_at bar | event bar | episode start, as a string
    side: Optional[str] = None
    parent: Optional[str] = None


def instance_id(semantic: SemanticIdentity, param_id: str, key: InstanceKey) -> str:
    return _canonical_hash({"semantic": semantic.id, "parameterization_id": param_id, "key": asdict(key)})
