"""
stack_version.py — one composite identity over WHAT / HOW / WHO / EXECUTION.

WHY THIS EXISTS (Research Provenance Spine, Phase 0).
The four authorities (`market_ontology.yaml` = WHAT, `configs/production/*.json` = HOW,
`active_models.yaml` = WHO, `features/registry/` + `candle_math`/`derived_math` =
EXECUTION) are each independently versioned, and no identity names the combination. A
result produced today and a result produced after tomorrow's bug fix are indistinguishable
unless something records the boundary. This module is that boundary.

Two hashes, not one:

  behavior_hash  — ONLY inputs that can move a trade ledger (active formulas, the active
                   config file, executing model checkpoints, schema/execution source).
                   Editing a comment, a `notes:` block, or a disabled model's artifact
                   must NOT move this hash — that is what buys churn-free citation.
  provenance_hash — behavior_hash plus everything else worth knowing happened (all model
                   families regardless of execution status, full-file ontology/identity
                   hashes, divergences) — for audit, not for citation.

This is a READ-ONLY reconciliation, like `production_bundle.py` (which it reuses
directly for the WHO-enabled question — do not re-derive Selected/Enabled here).
Never writes, never promotes, never gates a run. `authority: NONE` throughout — a
`stack_epoch` changing is a fact about what ran, not permission to run it.

CLAUDE.md §6.2 rule 3: divergences are reported, never silently resolved.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Frozen runtime keys read by the ontology at import time (market_ontology.yaml
# spec_schema.frozen_runtime_keys, verified against source 2026-07-30 — do not
# hand-edit this list without re-reading the ontology header, it is the contract
# that makes behavior_hash blind to additive taxonomy/semantics/lineage churn).
_ONTOLOGY_FROZEN_KEYS: tuple[str, ...] = (
    "id",
    "version",
    "lifecycle",
    "formula",
    "impl",
    "computation_class",
    "depends_on",
    "numerator",
    "denominator",
)

# Sections of the ontology that are runtime-read (mirrors features/registry/__init__.py
# _ITERATED_SECTIONS, minus the two that are pure temporal/structural context — those
# don't feed candle_math/derived_math dispatch and are provenance-only).
_ONTOLOGY_BEHAVIOR_SECTIONS: tuple[str, ...] = (
    "primitives",
    "feature_compositions",
    "derived_metrics",
    "rolling_indicators",
)


class StackVersionError(RuntimeError):
    """Fail-closed error building a stack version (missing/unreadable source file)."""


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(obj: Any) -> str:
    canonical = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _ontology_behavior_slice(ontology: Mapping[str, Any]) -> dict:
    """Deterministic {section: {feature_id: {frozen_key: value}}} slice.

    Only `_ONTOLOGY_FROZEN_KEYS` fields survive per entry — additive-only fields
    (taxonomy/semantics/lineage/notes/known_issue/states/...) are excluded by
    construction, which is what buys churn-free `behavior_hash` versioning.
    """
    out: dict[str, dict] = {}
    for section in _ONTOLOGY_BEHAVIOR_SECTIONS:
        block = ontology.get(section)
        if not isinstance(block, Mapping):
            continue
        section_out: dict[str, dict] = {}
        for feat_id, entry in block.items():
            if not isinstance(entry, Mapping):
                continue
            section_out[str(feat_id)] = {
                k: entry.get(k) for k in _ONTOLOGY_FROZEN_KEYS if k in entry
            }
        out[section] = section_out
    return out


def _ontology_full_slice(ontology: Mapping[str, Any]) -> dict:
    """Every section (behavior + provenance-only), same per-entry filter dropped —
    used only inside provenance_hash via the full-file sha256, not recomputed here.
    Kept for callers that want a structural (not byte) view of the whole document.
    """
    return {k: v for k, v in ontology.items() if k != "spec_schema"}


@dataclass(frozen=True)
class StackVersion:
    """Immutable composite identity for one snapshot of WHAT/HOW/WHO/EXECUTION."""

    active_version: str
    behavior_hash: str
    provenance_hash: str
    executing_families: tuple[str, ...]
    divergences: tuple[str, ...]
    components: Mapping[str, Any] = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)


def compute_stack_version(
    *,
    repo_root: Path | None = None,
    active_version: str | None = None,
) -> StackVersion:
    """Read-only: compute (behavior_hash, provenance_hash) for the current stack.

    Never writes, never raises on divergence (mirrors `production_bundle`'s
    report-don't-resolve discipline) — but DOES raise `StackVersionError` if a
    required source file (config, ontology, identity doc) cannot be read at all,
    because a hash computed over a partially-missing stack is worse than no hash.
    """
    root = (repo_root or _REPO_ROOT).resolve()

    from config_layer.production_bundle import load_production_bundle
    from config_layer.production_config import get_active_version, get_full_config_dict
    from features.registry import load_ontology, _ONTOLOGY_PATH
    from features.feature_schema import (
        SCHEMA_VERSION,
        CANONICAL_FEATURE_DIM,
        SCHEMA_HASH,
    )

    version = active_version or get_active_version()

    # ── HOW ──────────────────────────────────────────────────────────────────
    config_path = root / "configs" / "production" / f"{version}.json"
    config_sha256 = _sha256_file(config_path)
    if config_sha256 is None:
        raise StackVersionError(f"cannot read production config: {config_path}")
    try:
        cfg = get_full_config_dict(version)
    except Exception as exc:
        raise StackVersionError(f"cannot parse production config {config_path}: {exc}") from exc

    # ── WHAT ─────────────────────────────────────────────────────────────────
    ontology_sha256 = _sha256_file(_ONTOLOGY_PATH)
    if ontology_sha256 is None:
        raise StackVersionError(f"cannot read ontology: {_ONTOLOGY_PATH}")
    try:
        ontology = load_ontology()
    except Exception as exc:
        raise StackVersionError(f"cannot parse ontology {_ONTOLOGY_PATH}: {exc}") from exc

    behavior_slice = _ontology_behavior_slice(ontology)
    ontology_behavior_hash = _sha256_json(behavior_slice)
    ontology_version = ontology.get("version")
    semantic_registry_version = (
        (ontology.get("spec_schema") or {}).get("semantic_registry", {}).get("version")
        if isinstance(ontology.get("spec_schema"), Mapping)
        else None
    )

    # ── WHO / bundle (Selected vs Enabled reconciliation — reused, not rebuilt) ──
    bundle = load_production_bundle(repo_root=root, active_version=version)

    # ── active_models.yaml full-file provenance ─────────────────────────────
    active_models_path = root / "active_models.yaml"
    active_models_sha256 = _sha256_file(active_models_path)
    if active_models_sha256 is None:
        raise StackVersionError(f"cannot read WHO identity file: {active_models_path}")
    try:
        import yaml

        identity_doc = yaml.safe_load(active_models_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise StackVersionError(f"cannot parse {active_models_path}: {exc}") from exc
    who_schema_version = (identity_doc.get("meta") or {}).get("schema_version")
    state_contract_schema_version = (
        ((identity_doc.get("crt") or {}).get("runtime") or {}).get(
            "state_contract_schema_version"
        )
    )

    # ── EXECUTION: candle_math / derived_math source + schema identity ──────
    candle_math_path = root / "src" / "features" / "candle_math.py"
    derived_math_path = root / "src" / "features" / "derived_math.py"
    candle_math_sha256 = _sha256_file(candle_math_path)
    derived_math_sha256 = _sha256_file(derived_math_path)
    if candle_math_sha256 is None:
        raise StackVersionError(f"cannot read {candle_math_path}")
    if derived_math_sha256 is None:
        raise StackVersionError(f"cannot read {derived_math_path}")

    # ── WHO-enabled: only families that actually execute a checkpoint ───────
    who_enabled = tuple(
        sorted(
            (
                m.family,
                m.selected_version,
                _sha256_file(m.artifact_path) if m.artifact_path else None,
            )
            for m in bundle.members.values()
            if m.executes_checkpoint
        )
    )

    behavior_components = {
        "active_version": version,
        "config_sha256": config_sha256,
        "ontology_behavior_hash": ontology_behavior_hash,
        "schema_version": SCHEMA_VERSION,
        "canonical_feature_dim": CANONICAL_FEATURE_DIM,
        "schema_hash": SCHEMA_HASH,
        "candle_math_sha256": candle_math_sha256,
        "derived_math_sha256": derived_math_sha256,
        "who_enabled": who_enabled,
    }
    behavior_hash = _sha256_json(behavior_components)

    # ── provenance: everything above + all families + full-file hashes ─────
    all_families_status = tuple(
        sorted(
            (m.family, m.selected_version, m.execution_status, m.contested)
            for m in bundle.members.values()
        )
    )
    provenance_components = {
        **behavior_components,
        "ontology_sha256": ontology_sha256,
        "ontology_version": ontology_version,
        "semantic_registry_version": semantic_registry_version,
        "active_models_sha256": active_models_sha256,
        "who_schema_version": who_schema_version,
        "state_contract_schema_version": state_contract_schema_version,
        "all_families_status": all_families_status,
        "bundle_divergences": bundle.divergences,
    }
    provenance_hash = _sha256_json(provenance_components)

    return StackVersion(
        active_version=version,
        behavior_hash=behavior_hash,
        provenance_hash=provenance_hash,
        executing_families=bundle.executing_families(),
        divergences=bundle.divergences,
        components=provenance_components,
        meta={
            "repo_root": str(root),
            "authority": "NONE",
            # Working tree structurally diverges from HEAD (untracked files imported
            # by tracked modules) — a bare git SHA would be a false pin. This module
            # deliberately does NOT compute one; callers needing git provenance must
            # verify tree cleanliness themselves before trusting a SHA.
            "git_sha_reliable": False,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# EPOCH LEDGER — configs/stack_epoch_log.jsonl
#
# Append-only, same discipline as configs/promotion_log.jsonl (CLAUDE.md §6.2 rule 4:
# never rewrite a line). `stack_epoch` is a monotonic int that increments ONLY when
# `behavior_hash` has never been seen before — so it stays a stable behavioral identity
# a finding/result can cite, immune to provenance-only churn (a `notes:` edit, an
# inert-model artifact swap). A provenance-only change appends a STACK_PROVENANCE
# record against the CURRENT epoch instead of minting a new one.
# ─────────────────────────────────────────────────────────────────────────────

_EPOCH_LOG_RELATIVE = Path("configs") / "stack_epoch_log.jsonl"


def _read_epoch_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines.append(json.loads(line))
    return lines


def resolve_epoch(
    stack: StackVersion,
    *,
    repo_root: Path | None = None,
    log_path: Path | None = None,
) -> tuple[int, bool]:
    """Return (stack_epoch, is_new_behavior) for `stack` against the existing ledger.

    Read-only — does not append. `is_new_behavior=True` means no prior ledger line
    carries this `behavior_hash`, i.e. calling `append_epoch_record` next will mint a
    new epoch rather than a provenance-only record against an existing one.
    """
    root = (repo_root or _REPO_ROOT).resolve()
    path = log_path or (root / _EPOCH_LOG_RELATIVE)
    records = _read_epoch_log(path)

    seen_behavior_hashes: dict[str, int] = {}
    max_epoch = 0
    for rec in records:
        if rec.get("kind") == "STACK_EPOCH":
            epoch = int(rec["stack_epoch"])
            max_epoch = max(max_epoch, epoch)
            seen_behavior_hashes.setdefault(rec["behavior_hash"], epoch)

    if stack.behavior_hash in seen_behavior_hashes:
        return seen_behavior_hashes[stack.behavior_hash], False
    return max_epoch + 1, True


def append_epoch_record(
    stack: StackVersion,
    *,
    repo_root: Path | None = None,
    log_path: Path | None = None,
) -> dict:
    """Append one record to the epoch ledger and return it.

    Mints `kind: STACK_EPOCH` (new `stack_epoch`, monotonic) when `behavior_hash` is
    unseen; otherwise appends `kind: STACK_PROVENANCE` against the existing epoch.
    Never rewrites an existing line. This is the ONLY function in this module that
    writes to disk — `compute_stack_version` / `resolve_epoch` are pure reads.
    """
    import datetime as _dt

    root = (repo_root or _REPO_ROOT).resolve()
    path = log_path or (root / _EPOCH_LOG_RELATIVE)
    epoch, is_new = resolve_epoch(stack, repo_root=root, log_path=path)

    record = {
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "kind": "STACK_EPOCH" if is_new else "STACK_PROVENANCE",
        "stack_epoch": epoch,
        "behavior_hash": stack.behavior_hash,
        "provenance_hash": stack.provenance_hash,
        "active_version": stack.active_version,
        "executing_families": list(stack.executing_families),
        "divergences": list(stack.divergences),
        "authority": "NONE",
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")

    return record


__all__ = [
    "StackVersion",
    "StackVersionError",
    "compute_stack_version",
    "resolve_epoch",
    "append_epoch_record",
]
