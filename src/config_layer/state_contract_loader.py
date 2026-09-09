"""
state_contract_loader.py
═══════════════════════════════════════════════════════════════════════════════
Phase 1 — State Contract Loading and Validation.

Pipeline:
  active_models.yaml
    → parse state_contracts
    → state-set / transition-graph parity vs CRTState / VALID_TRANSITIONS
    → FM IDs vs market ontology + FORMULA_REGISTRY / composition bindings
    → config_keys vs CRTConfig fields
    → eligible_models vs active_models model identity surface
    → immutable StateContractBundle

Never eval YAML. Never dispatch models. Never execute formulas.
Python VALID_TRANSITIONS remains executable transition authority.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Any, Optional

from config_layer.state_identity import CRTConfig, CRTState, VALID_TRANSITIONS
from config_layer.state_contract import (
    SCHEMA_VERSION,
    StateContract,
    StateContractBundle,
    freeze_bundle,
    parse_state_contract,
)

log = logging.getLogger("StateContractLoader")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ACTIVE_MODELS = _REPO_ROOT / "active_models.yaml"

# Top-level YAML keys that are NOT model identities (WHO narrative / meta).
_NON_MODEL_KEYS = frozenset({"meta", "philosophy", "feature_lineage"})

_CACHE: Optional[StateContractBundle] = None


class StateContractError(ValueError):
    """Fail-closed validation / load error with an actionable message."""


# ── Ontology / FM resolution ─────────────────────────────────────────────────
# Phase-2: shared resolve lives in features.fm_resolve (single authority for
# FM id → callable binding). Loader validates required_fm via that surface.

def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise StateContractError(
            "PyYAML is required to load state contracts from active_models.yaml"
        ) from exc
    if not path.exists():
        raise StateContractError(f"active_models path not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StateContractError(f"{path}: root must be a mapping")
    return data


def _resolve_fm(fm_id: str) -> Any:
    """Validate FM id resolves through Phase-2 fm_resolve (ontology + registry)."""
    from features.fm_resolve import FMResolveError, resolve_fm

    try:
        return resolve_fm(fm_id)
    except FMResolveError as exc:
        raise StateContractError(str(exc)) from exc


# ── Config key resolution ────────────────────────────────────────────────────

def _crt_config_field_names() -> frozenset[str]:
    return frozenset(f.name for f in dataclasses.fields(CRTConfig))


def _validate_config_key(key: str, crt_fields: frozenset[str]) -> str:
    """
    Returns status token; raises StateContractError if key does not exist.

    Status:
      CONFIG_KEY_EXISTS — field on CRTConfig (runtime HOW binding for CRT)
    """
    if key not in crt_fields:
        raise StateContractError(
            f"config_key {key!r}: CONFIG_KEY_MISSING — not a CRTConfig field "
            f"(runtime HOW binding). Known CRTConfig fields are the Phase-1 "
            f"config_key authority."
        )
    return "CONFIG_KEY_EXISTS"


# ── Model identity surface ───────────────────────────────────────────────────

def _canonical_model_ids(doc: dict) -> frozenset[str]:
    """Model IDs = top-level active_models keys excluding meta/philosophy/feature_lineage."""
    return frozenset(k for k in doc if k not in _NON_MODEL_KEYS and isinstance(doc[k], dict))


def _validate_model_id(model_id: str, known: frozenset[str]) -> None:
    if model_id not in known:
        raise StateContractError(
            f"eligible_models entry {model_id!r}: unknown model ID — not present "
            f"as a top-level model block in active_models.yaml. "
            f"Known={sorted(known)}"
        )


# ── Graph / state parity ─────────────────────────────────────────────────────

def _code_states() -> set[str]:
    return {s.name for s in CRTState}


def _code_transitions() -> dict[str, set[str]]:
    return {s.name: {t.name for t in targets} for s, targets in VALID_TRANSITIONS.items()}


def _validate_state_set(contract_ids: set[str]) -> None:
    code = _code_states()
    if contract_ids != code:
        missing = code - contract_ids
        extra = contract_ids - code
        raise StateContractError(
            f"state_contracts state-set parity failed: "
            f"missing={sorted(missing)} extra={sorted(extra)} "
            f"code={sorted(code)} declared={sorted(contract_ids)}"
        )


def _validate_transition_graph(yaml_trans: dict[str, list]) -> dict[str, tuple[str, ...]]:
    """Parity-check active_models.yaml's valid_transitions against the code seed.

    SEMANTICS CHANGED 2026-08-31 (CH-crt-state-generation-v1): the code seed
    (state_identity.VALID_TRANSITIONS) is now GENERATED from this same YAML block, so this is a
    FRESHNESS check on the committed generated artifact, not an independent cross-record
    comparison. It still fails closed and still catches the case that matters at runtime -- a
    stale generated module -- but it no longer constitutes independent corroboration.
    Independent guards: tests/test_crt_state_generated_parity.py (hand-transcribed anchor) and
    the market_crt_states.yaml floors (a different file). See
    scripts/maintenance/gen_crt_state_identity.py.
    """
    if not isinstance(yaml_trans, dict):
        raise StateContractError("crt.runtime.valid_transitions must be a mapping")
    code = _code_transitions()
    declared: dict[str, set[str]] = {}
    for src, targets in yaml_trans.items():
        if not isinstance(src, str):
            raise StateContractError(f"transition source must be str, got {type(src)}")
        if not isinstance(targets, (list, tuple)):
            raise StateContractError(
                f"valid_transitions.{src} must be a list, got {type(targets).__name__}"
            )
        seen: set[str] = set()
        for t in targets:
            if not isinstance(t, str):
                raise StateContractError(
                    f"valid_transitions.{src} target must be str, got {t!r}"
                )
            if t in seen:
                raise StateContractError(
                    f"valid_transitions.{src}: duplicate transition to {t!r}"
                )
            seen.add(t)
        declared[src] = seen

    code_set = {k: set(v) for k, v in code.items()}
    if declared != code_set:
        # Detailed mismatch
        all_keys = set(declared) | set(code_set)
        parts = []
        for k in sorted(all_keys):
            if declared.get(k) != code_set.get(k):
                parts.append(
                    f"{k}: declared={sorted(declared.get(k, set()))} "
                    f"code={sorted(code_set.get(k, set()))}"
                )
        raise StateContractError(
            "transition graph parity failed (YAML valid_transitions vs "
            f"VALID_TRANSITIONS): {'; '.join(parts)}"
        )
    # Preserve YAML declaration order for targets
    ordered: dict[str, tuple[str, ...]] = {}
    for src, targets in yaml_trans.items():
        ordered[src] = tuple(targets)
    return ordered


# ── Public loader ────────────────────────────────────────────────────────────

def load_and_validate_state_contracts(
    path: Path | str | None = None,
    *,
    force_reload: bool = False,
) -> StateContractBundle:
    """
    Load + fully validate state contracts from active_models.yaml.

    Fail-closed. Caches the validated bundle process-wide unless force_reload.
    """
    global _CACHE
    if _CACHE is not None and not force_reload and path is None:
        return _CACHE

    am_path = Path(path) if path is not None else _DEFAULT_ACTIVE_MODELS
    doc = _load_yaml(am_path)

    try:
        crt = doc["crt"]
        runtime = crt["runtime"]
    except (KeyError, TypeError) as exc:
        raise StateContractError(
            "active_models.yaml missing crt.runtime — cannot locate state_contracts"
        ) from exc

    schema_ver = runtime.get("state_contract_schema_version")
    if schema_ver is None:
        raise StateContractError(
            "crt.runtime.state_contract_schema_version is required "
            f"(expected {SCHEMA_VERSION!r})"
        )
    if str(schema_ver) != SCHEMA_VERSION:
        raise StateContractError(
            f"state_contract_schema_version={schema_ver!r} unsupported; "
            f"expected {SCHEMA_VERSION!r}"
        )

    raw_contracts = runtime.get("state_contracts")
    if raw_contracts is None:
        raise StateContractError("crt.runtime.state_contracts is required")
    if not isinstance(raw_contracts, dict):
        raise StateContractError(
            f"crt.runtime.state_contracts must be a mapping, got {type(raw_contracts).__name__}"
        )
    if not raw_contracts:
        raise StateContractError("crt.runtime.state_contracts is empty")

    # ── Parse each state ────────────────────────────────────────────────────
    contracts: dict[str, StateContract] = {}
    for state_id, body in raw_contracts.items():
        if not isinstance(state_id, str):
            raise StateContractError(
                f"state_contracts key must be str, got {type(state_id).__name__}"
            )
        contracts[state_id] = parse_state_contract(state_id, body)

    # ── State-set parity ────────────────────────────────────────────────────
    _validate_state_set(set(contracts))

    # ── Transition graph parity (declaration only) ──────────────────────────
    yaml_trans = runtime.get("valid_transitions")
    if yaml_trans is None:
        raise StateContractError(
            "crt.runtime.valid_transitions is required for transition-graph parity"
        )
    transitions = _validate_transition_graph(yaml_trans)

    # Graph keys must match contract states
    if set(transitions) != set(contracts):
        raise StateContractError(
            "valid_transitions keys must equal state_contracts keys: "
            f"trans={sorted(transitions)} contracts={sorted(contracts)}"
        )

    # ── FM resolution (Phase-2 shared fm_resolve) ───────────────────────────
    for sc in contracts.values():
        for fm_id in sc.required_fm:
            if not fm_id.startswith("FM-"):
                raise StateContractError(
                    f"state_contracts.{sc.state_id}.required_fm: {fm_id!r} "
                    f"is not an FM ID (expected FM-0NN form)"
                )
            _resolve_fm(fm_id)

    # ── Config keys ─────────────────────────────────────────────────────────
    crt_fields = _crt_config_field_names()
    for sc in contracts.values():
        for key in sc.config_keys:
            _validate_config_key(key, crt_fields)

    # ── Model IDs (no dispatch) ─────────────────────────────────────────────
    model_ids = _canonical_model_ids(doc)
    for sc in contracts.values():
        for mid in sc.eligible_models:
            _validate_model_id(mid, model_ids)

    # Deterministic key order: CRTState enum order
    ordered_contracts = {
        s.name: contracts[s.name] for s in CRTState if s.name in contracts
    }

    bundle = freeze_bundle(
        ordered_contracts,
        transitions,
        schema_version=str(schema_ver),
        source_path=str(am_path.resolve()),
    )
    log.info(
        "State contracts loaded: states=%d schema=%s path=%s",
        len(bundle.contracts),
        bundle.schema_version,
        bundle.source_path,
    )
    if path is None:
        _CACHE = bundle
    return bundle


def clear_state_contract_cache() -> None:
    """Test helper — drop process cache."""
    global _CACHE
    _CACHE = None


def get_cached_state_contracts() -> Optional[StateContractBundle]:
    return _CACHE
