"""Load and validate OSS capability registry records.

Fail-closed on schema-required fields. Does not install or import external packages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

_LAB_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_JSONL = Path(__file__).resolve().parent / "oss_capabilities.jsonl"
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"

# Trust tiers: T4 is forbidden by default for external OSS.
TRUST_TIERS = ("T0", "T1", "T2", "T3", "T4")
DECISIONS = (
    "DISCOVERED",
    "ASSESSED",
    "APPROVED_FOR_LAB",
    "BENCHMARKED",
    "CERTIFIED",
    "APPROVED_FOR_INTEGRATION",
    "PROMOTED",
    "REJECTED",
    "DEFERRED",
    "RESEARCH_ONLY",
    "ADAPTER_ONLY",
    "REFERENCE_ONLY",
)

REQUIRED_FIELDS = (
    "oss_id",
    "name",
    "repository",
    "version",
    "commit_or_tag",
    "license",
    "license_obligations",
    "security_status",
    "maintenance_status",
    "purpose",
    "capabilities",
    "integration_role",
    "trust_tier",
    "allowed_surfaces",
    "forbidden_surfaces",
    "input_contract",
    "output_contract",
    "adapter",
    "tests",
    "certification_status",
    "provenance",
    "known_risks",
    "decision",
    "decision_reason",
    "lifecycle_status",
)

# Surfaces that external OSS must never claim without explicit architecture decision.
PROTECTED_AUTHORITIES = (
    "market_ontology",
    "canonical_feature_identity",
    "crt_semantics",
    "fusion",
    "decision",
    "ultron",
    "governance_closure",
    "production_configuration",
)


class OSSRegistryError(ValueError):
    """Fail-closed registry validation error."""


@dataclass
class OSSRegistry:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_path: Optional[Path] = None

    def get(self, oss_id: str) -> dict[str, Any]:
        if oss_id not in self.records:
            raise OSSRegistryError(f"unknown oss_id: {oss_id}")
        return self.records[oss_id]

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for k in sorted(self.records):
            yield self.records[k]

    def by_tier(self, tier: str) -> list[dict[str, Any]]:
        return [r for r in self if r.get("trust_tier") == tier]

    def by_decision(self, decision: str) -> list[dict[str, Any]]:
        return [r for r in self if r.get("decision") == decision]

    def summary(self) -> dict[str, Any]:
        tiers: dict[str, int] = {}
        decisions: dict[str, int] = {}
        for r in self:
            tiers[r["trust_tier"]] = tiers.get(r["trust_tier"], 0) + 1
            decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1
        return {
            "count": len(self.records),
            "tiers": tiers,
            "decisions": decisions,
            "source": str(self.source_path) if self.source_path else None,
            "authority": "RESEARCH_LAB_ONLY",
            "t4_external_forbidden_default": True,
        }

    def validate_all(self) -> list[str]:
        errors: list[str] = []
        for rid, rec in self.records.items():
            errors.extend(_validate_record(rec))
        return errors


def _validate_record(rec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rid = rec.get("oss_id", "?")
    for f in REQUIRED_FIELDS:
        if f not in rec:
            errors.append(f"{rid}: missing required field {f}")
    if rec.get("trust_tier") not in TRUST_TIERS:
        errors.append(f"{rid}: trust_tier {rec.get('trust_tier')!r} invalid")
    if rec.get("decision") not in DECISIONS:
        errors.append(f"{rid}: decision {rec.get('decision')!r} invalid")
    if rec.get("lifecycle_status") not in DECISIONS:
        errors.append(f"{rid}: lifecycle_status {rec.get('lifecycle_status')!r} invalid")
    # External OSS at T4 is forbidden unless explicitly flagged (none today).
    if (
        rec.get("trust_tier") == "T4"
        and rec.get("oss_id") != "OSS-TRADLATEST-BASELINE"
        and not rec.get("explicit_t4_architecture_decision")
    ):
        errors.append(
            f"{rid}: T4 production authority forbidden for external OSS without "
            "explicit_t4_architecture_decision"
        )
    if not isinstance(rec.get("capabilities"), list) or not rec.get("capabilities"):
        errors.append(f"{rid}: capabilities must be a non-empty list")
    if not isinstance(rec.get("forbidden_surfaces"), list):
        errors.append(f"{rid}: forbidden_surfaces must be a list")
    # Baseline may have empty forbidden; external must list at least one protected surface.
    if rid != "OSS-TRADLATEST-BASELINE" and not rec.get("forbidden_surfaces"):
        errors.append(f"{rid}: external OSS must declare forbidden_surfaces")
    prov = rec.get("provenance")
    if not isinstance(prov, dict) or "sources" not in prov:
        errors.append(f"{rid}: provenance.sources required")
    return errors


def load_registry(path: Optional[Path] = None) -> OSSRegistry:
    p = Path(path) if path else _DEFAULT_JSONL
    if not p.is_file():
        raise OSSRegistryError(f"registry file missing: {p}")
    records: dict[str, dict[str, Any]] = {}
    for line_no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OSSRegistryError(f"{p}:{line_no}: invalid JSON: {exc}") from exc
        oss_id = rec.get("oss_id")
        if not oss_id:
            raise OSSRegistryError(f"{p}:{line_no}: missing oss_id")
        if oss_id in records:
            raise OSSRegistryError(f"duplicate oss_id: {oss_id}")
        records[oss_id] = rec
    reg = OSSRegistry(records=records, source_path=p)
    errors = reg.validate_all()
    if errors:
        raise OSSRegistryError("registry validation failed:\n  " + "\n  ".join(errors))
    return reg


def schema_path() -> Path:
    return _SCHEMA_PATH


def lab_root() -> Path:
    return _LAB_ROOT
