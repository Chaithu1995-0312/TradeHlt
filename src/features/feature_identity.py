"""
Phase-1 feature identity resolution — fail-closed lookup by feature_id.

Governed identities for the five duplicate/collision families live in
``docs/governance/phase1_feature_identity_registry-<date>.json``.

Rules:
  * Resolve by ``feature_id`` (always unique).
  * Bare-name lookup is allowed only when exactly one identity maps that name
    as ``canonical_name`` or an explicit non-ambiguous legacy alias.
  * Ambiguous bare names raise ``AmbiguousFeatureIdentityError``.
  * Environment flags must never mutate formula semantics under one feature_id
    (enforced by tests + pipeline identity-split paths).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_REGISTRY = (
    _REPO_ROOT
    / "docs"
    / "governance"
    / "phase1_feature_identity_registry-2026-07-10.json"
)

ALLOWED_STATUSES = frozenset(
    {
        "IDENTITY_CLOSED",
        "DISTINCT_SEMANTIC_PRESERVED",
        "CANONICAL_IMPLEMENTATION_SELECTED",
        "LEGACY_IMPLEMENTATION_SHADOW_ONLY",
        "BLOCKED",
    }
)


class FeatureIdentityError(Exception):
    """Base error for identity resolution."""


class AmbiguousFeatureIdentityError(FeatureIdentityError):
    """Bare name maps to more than one semantic identity."""


class UnknownFeatureIdentityError(FeatureIdentityError):
    """feature_id or name not present in the registry."""


@dataclass(frozen=True)
class FeatureIdentity:
    feature_id: str
    canonical_name: str
    formula_id: str
    formula_version: str
    semantic_description: str
    source_semantics: str
    units: str
    temporal_semantics: str
    parameters: dict
    implementation_authority: str
    consumer_bindings: list
    legacy_names: list
    legacy_implementations: list
    status: str
    family: str = ""
    raw: dict | None = None

    def binding_tuple(self) -> tuple[str, str, str]:
        return (self.feature_id, self.formula_id, self.formula_version)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def load_identity_registry(path: str | None = None) -> dict:
    p = Path(path) if path else _DEFAULT_REGISTRY
    if not p.is_file():
        raise FileNotFoundError(f"feature identity registry missing: {p}")
    data = _load_json(p)
    identities = data.get("identities") or []
    if not identities:
        raise FeatureIdentityError(f"empty identities in {p}")
    # uniqueness floors
    fids = [i["feature_id"] for i in identities]
    if len(fids) != len(set(fids)):
        raise FeatureIdentityError("duplicate feature_id in registry")
    # formula_id may be shared by symmetric high/low identities only when the
    # formula_definition is identical (not merely related). semantic_description
    # may differ (high vs low).
    formulas: dict[str, str] = {}
    for i in identities:
        fid = i["formula_id"]
        defn = i.get("formula_definition")
        if defn is not None:
            if fid in formulas and formulas[fid] != defn:
                raise FeatureIdentityError(
                    f"formula_id {fid} maps to divergent formula_definition values"
                )
            formulas[fid] = defn
        st = i.get("status")
        if st not in ALLOWED_STATUSES:
            raise FeatureIdentityError(f"illegal status {st!r} on {i['feature_id']}")
    return data


def _as_identity(row: dict) -> FeatureIdentity:
    return FeatureIdentity(
        feature_id=row["feature_id"],
        canonical_name=row["canonical_name"],
        formula_id=row["formula_id"],
        formula_version=str(row["formula_version"]),
        semantic_description=row.get("semantic_description", ""),
        source_semantics=row.get("source_semantics", ""),
        units=row.get("units", ""),
        temporal_semantics=row.get("temporal_semantics", ""),
        parameters=dict(row.get("parameters") or {}),
        implementation_authority=row.get("implementation_authority", ""),
        consumer_bindings=list(row.get("consumer_bindings") or []),
        legacy_names=list(row.get("legacy_names") or []),
        legacy_implementations=list(row.get("legacy_implementations") or []),
        status=row["status"],
        family=row.get("family", ""),
        raw=row,
    )


def all_identities(path: str | None = None) -> list[FeatureIdentity]:
    data = load_identity_registry(path)
    return [_as_identity(r) for r in data["identities"]]


def get_by_feature_id(feature_id: str, path: str | None = None) -> FeatureIdentity:
    for ident in all_identities(path):
        if ident.feature_id == feature_id:
            return ident
    raise UnknownFeatureIdentityError(f"unknown feature_id: {feature_id}")


def resolve_by_name(
    name: str,
    *,
    path: str | None = None,
    allow_legacy_alias: bool = False,
) -> FeatureIdentity:
    """
    Resolve a bare feature name.

    Default: only ``canonical_name`` matches (must be unique).
    With ``allow_legacy_alias=True``: also match ``legacy_names`` when that name
    appears on exactly one identity. Multiple matches → AmbiguousFeatureIdentityError.
    """
    matches: list[FeatureIdentity] = []
    for ident in all_identities(path):
        if ident.canonical_name == name:
            matches.append(ident)
        elif allow_legacy_alias and name in (ident.legacy_names or []):
            matches.append(ident)
    # de-dupe by feature_id
    by_id = {m.feature_id: m for m in matches}
    matches = list(by_id.values())
    if not matches:
        raise UnknownFeatureIdentityError(f"unknown feature name: {name}")
    if len(matches) > 1:
        ids = sorted(m.feature_id for m in matches)
        raise AmbiguousFeatureIdentityError(
            f"bare name {name!r} is ambiguous across identities {ids}; "
            "resolve by feature_id"
        )
    return matches[0]


def assert_consumer_binding(
    consumer: str,
    feature_id: str,
    formula_id: str,
    formula_version: str,
    *,
    path: str | None = None,
) -> FeatureIdentity:
    """Fail closed if consumer is not bound to the given identity triple."""
    ident = get_by_feature_id(feature_id, path=path)
    if ident.formula_id != formula_id or str(ident.formula_version) != str(formula_version):
        raise FeatureIdentityError(
            f"binding mismatch for {feature_id}: registry has "
            f"{ident.formula_id}@{ident.formula_version}, "
            f"consumer requested {formula_id}@{formula_version}"
        )
    bound = {
        c if isinstance(c, str) else c.get("consumer")
        for c in (ident.consumer_bindings or [])
    }
    if consumer not in bound and "*" not in bound:
        raise FeatureIdentityError(
            f"consumer {consumer!r} not bound to {feature_id}; "
            f"bound={sorted(x for x in bound if x)}"
        )
    return ident


def prohibit_same_name_substitution(
    name: str,
    *,
    path: str | None = None,
) -> None:
    """
    Fail if a historical bare name is still claimed as canonical by multiple
    identities (registry invariant).
    """
    canons = [i for i in all_identities(path) if i.canonical_name == name]
    if len(canons) > 1:
        raise AmbiguousFeatureIdentityError(
            f"canonical_name collision on {name!r}: "
            f"{[c.feature_id for c in canons]}"
        )


def identities_by_family(family: str, path: str | None = None) -> list[FeatureIdentity]:
    return [i for i in all_identities(path) if i.family == family]


def registry_path() -> Path:
    return _DEFAULT_REGISTRY


def clear_cache() -> None:
    load_identity_registry.cache_clear()
