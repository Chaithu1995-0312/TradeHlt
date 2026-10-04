"""Module attribution registry core — governance-surface ownership for every ``src/`` module.

Sibling of :mod:`governance.script_registry` (which does the same job for runnable paths and
sits at 371/371). The denominator here is ``src/**/*.py``; the claim this registry supports is:

    100% ATTRIBUTED = every src/ module is claimed by exactly one surface.

That is deliberately **not** "every surface is CLOSED". Statuses stay honestly mixed and
advance only through the Closure & Authority Index
(``docs/governance/closure_authority_index.json``), never through this ledger.

Inventory/governance authority only — grants no production, activation, or economic
authority (CLAUDE.md §6.5). Never import from the trading spine (engine_runner /
live_engine_hook / backtest_v2).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from governance.script_registry import normalize_posix
from utils.jsonl_writer import read_jsonl

# --------------------------------------------------------------------------- enums

#: Cost/treatment class. Only DECISION modules are expected to pursue G2/G3.
REGIME_ENUM = frozenset({
    "DECISION",
    "RESEARCH",
    "PLATFORM",
    "SUBSTRATE",
    "MODEL_LINEAGE",
    "TERMINAL",
    "UNKNOWN",
})

#: Closure cost ladder. G0 is mechanical; G3 is the CRT-grade 9-criteria checklist.
GRADE_ENUM = frozenset({
    "G0_ATTRIBUTED",
    "G1_DECLARED",
    "G2_AUDITED",
    "G3_CLOSED",
})

REACHABILITY_ENUM = frozenset({
    "LIVE_DECISION",
    "BACKTEST_ONLY",
    "TOOLING",
    "RESEARCH_ONLY",
    "ORPHANED",
    "UNKNOWN",
})

#: Auto-stub sentinel. A row still carrying this has NOT been attributed; an overlay is
#: required to replace it. Mirrors script_registry's GRANDFATHER_UNCLASSIFIED discipline.
UNATTRIBUTED = "UNATTRIBUTED"

AUTHORITY = "inventory"  # pinned — §6.5: tunability/coverage never grants authority

_ID_RE = re.compile(r"^MOD-\d{4,}$")

_REQUIRED_FIELDS = (
    "id",
    "module_path",
    "owner_surface",
    "participates_in",
    "regime",
    "grade",
    "reachability",
    "economically_validated",
    "evidence",
    "created",
    "last_validated",
    "notes",
    "authority",
)
_LIST_FIELDS = ("participates_in", "evidence")

# Repo root: src/governance/this → parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REGISTRY_PATH = _REPO_ROOT / "data" / "module_attribution.jsonl"
DEFAULT_STUBS_PATH = _REPO_ROOT / "docs" / "governance" / "module_attribution_stubs.jsonl"
CLOSURE_INDEX_PATH = _REPO_ROOT / "docs" / "governance" / "closure_authority_index.json"


def mod_num(module_id: str) -> int:
    """Numeric part of MOD-NNNN; raises ValueError if malformed."""
    if not isinstance(module_id, str) or not _ID_RE.match(module_id):
        raise ValueError(f"id must match MOD-NNNN, got {module_id!r}")
    return int(module_id.split("-", 1)[1])


def load_surface_ids(path: "Path | str | None" = None) -> set[str]:
    """Surface ids declared in the Closure & Authority Index (the ownership vocabulary)."""
    p = Path(path) if path else CLOSURE_INDEX_PATH
    payload = json.loads(p.read_text(encoding="utf-8"))
    return {s["surface_id"] for s in payload.get("surfaces", []) if s.get("surface_id")}


def new_stub_record(
    *,
    module_id: str,
    module_path: str,
    regime: str = "UNKNOWN",
    reachability: str = "UNKNOWN",
    timestamp: str,
    notes: str = "",
) -> dict:
    """Auto-stub row: attributed to nobody until an overlay claims it."""
    return {
        "id": module_id,
        "module_path": normalize_posix(module_path),
        "owner_surface": UNATTRIBUTED,
        "participates_in": [],
        "regime": regime,
        "grade": "G0_ATTRIBUTED",
        "reachability": reachability,
        # Per user ruling: carried per-module so a green coverage % can never be read as
        # soundness. Advances only with a named authoritative artifact, never in bulk.
        "economically_validated": False,
        "evidence": [],
        "created": timestamp,
        "last_validated": timestamp,
        "notes": notes,
        "authority": AUTHORITY,
    }


class ValidationError(str):
    """Plain-string validation error (mirrors script_registry's shape)."""


class ModuleAttributionRegistry:
    """Read model over ``data/module_attribution.jsonl``."""

    def __init__(self, path: "Path | str | None" = None) -> None:
        self._path = Path(path) if path else DEFAULT_REGISTRY_PATH
        self._records: list[dict] = []
        if self._path.exists():
            self.load(self._path)

    def load(self, path: "Path | str | None" = None) -> int:
        self._path = Path(path) if path else self._path
        self._records = list(read_jsonl(self._path))
        return len(self._records)

    @property
    def records(self) -> list[dict]:
        return list(self._records)

    def get(self, module_id: str) -> dict:
        for rec in self._records:
            if rec.get("id") == module_id:
                return dict(rec)
        raise KeyError(module_id)

    def by_path(self, module_path: str) -> dict:
        target = normalize_posix(module_path)
        for rec in self._records:
            if normalize_posix(rec.get("module_path", "")) == target:
                return dict(rec)
        raise KeyError(target)

    # ----------------------------------------------------------------- coverage

    def coverage_against_disk(self, discovered_paths: set[str]) -> dict:
        """The ratchet's core comparison: disk vs ledger, both directions."""
        disc = {normalize_posix(p) for p in discovered_paths}
        registered = {normalize_posix(r.get("module_path", "")) for r in self._records}
        registered.discard("")
        unregistered = sorted(disc - registered)
        missing_on_disk = sorted(registered - disc)
        attributed = sorted(
            normalize_posix(r.get("module_path", ""))
            for r in self._records
            if r.get("owner_surface") not in (UNATTRIBUTED, None, "")
        )
        return {
            "discovered": len(disc),
            "registered": len(registered),
            "unregistered": unregistered,
            "missing_on_disk": missing_on_disk,
            "attributed": len(attributed),
            "unattributed": sorted(disc - set(attributed)),
            "attribution_pct": round(100.0 * len(attributed) / len(disc), 2) if disc else 0.0,
            "enumeration_ok": not unregistered and not missing_on_disk,
            "attribution_ok": len(attributed) == len(disc),
        }

    # --------------------------------------------------------------- validation

    def summary(self) -> dict:
        def _tally(key: str) -> dict:
            out: dict[str, int] = {}
            for rec in self._records:
                out[str(rec.get(key))] = out.get(str(rec.get(key)), 0) + 1
            return dict(sorted(out.items()))

        return {
            "total": len(self._records),
            "by_regime": _tally("regime"),
            "by_grade": _tally("grade"),
            "by_reachability": _tally("reachability"),
            "by_owner_surface": _tally("owner_surface"),
            "economically_validated_count": sum(
                1 for r in self._records if r.get("economically_validated") is True
            ),
        }

    def validate_all(self, *, surface_ids: Optional[set[str]] = None) -> list[str]:
        known = surface_ids if surface_ids is not None else load_surface_ids()
        errors: list[str] = []
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        for rec in self._records:
            errors.extend(validate_record(rec, surface_ids=known))
            rid = rec.get("id")
            if rid in seen_ids:
                errors.append(f"duplicate id: {rid}")
            seen_ids.add(rid)
            path = normalize_posix(rec.get("module_path", ""))
            if path in seen_paths:
                # This is the invariant that makes the percentage well-defined.
                errors.append(f"module claimed more than once: {path}")
            seen_paths.add(path)
        return errors


def validate_record(rec: dict, *, surface_ids: Optional[set[str]] = None) -> list[str]:
    """Field-level validation for one ledger row."""
    errors: list[str] = []
    rid = rec.get("id", "<no id>")

    for field in _REQUIRED_FIELDS:
        if field not in rec:
            errors.append(f"{rid}: missing required field {field!r}")

    try:
        mod_num(rec.get("id", ""))
    except ValueError as exc:
        errors.append(f"{rid}: {exc}")

    for field in _LIST_FIELDS:
        if field in rec and not isinstance(rec[field], list):
            errors.append(f"{rid}: {field!r} must be a list")

    if rec.get("regime") not in REGIME_ENUM:
        errors.append(f"{rid}: regime {rec.get('regime')!r} not in REGIME_ENUM")
    if rec.get("grade") not in GRADE_ENUM:
        errors.append(f"{rid}: grade {rec.get('grade')!r} not in GRADE_ENUM")
    if rec.get("reachability") not in REACHABILITY_ENUM:
        errors.append(f"{rid}: reachability {rec.get('reachability')!r} not in REACHABILITY_ENUM")
    if not isinstance(rec.get("economically_validated"), bool):
        errors.append(f"{rid}: economically_validated must be a bool")
    if rec.get("authority") != AUTHORITY:
        errors.append(f"{rid}: authority must be pinned to {AUTHORITY!r}")

    owner = rec.get("owner_surface")
    if owner != UNATTRIBUTED and surface_ids is not None and owner not in surface_ids:
        errors.append(
            f"{rid}: owner_surface {owner!r} is not a surface_id in closure_authority_index.json"
        )

    # participates_in is informational only and must never be read as ownership
    # (CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE).
    if surface_ids is not None:
        for sid in rec.get("participates_in", []) or []:
            if sid not in surface_ids:
                errors.append(f"{rid}: participates_in {sid!r} is not a known surface_id")

    return errors


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
