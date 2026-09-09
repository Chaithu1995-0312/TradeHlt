"""
crt_identity_schema.py
═══════════════════════════════════════════════════════════════════════════════
CRT Semantic Authority — PR-1 validator for `configs/formulas/crt_state_identity.yaml`.

Declaration-only. This module does NOT build a `CRTModel`, does NOT wire a loader into
`CRTEngine.__init__`, and does NOT change generation. See
`docs/implementation_plan/crt-state-identity-ontology-2026-09.md` (Alternative I,
"constructor-neutral identity") for the full design this validates against.

WHAT THIS ENFORCES
-------------------
The identity file partitions CRT state metadata into three tiers, and this validator is
the mechanical enforcement of that partition:

  Tier 1  identity.states.<NAME>                        — semantic core, constructor-
          neutral. CLOSED field set (_TIER1_FIELDS). No Tier-2 field name (handler,
          dispatch, htf_protected, records_entry_index, reset_telemetry, ttl_kind, ...)
          may appear here — that is the "neutrality lint": the one check that stops
          identity from silently becoming engine-shaped again.
  Tier 2  identity.constructors.<C>.states.<NAME>        — per-constructor bindings.
          Engine's binding set is CLOSED and must cover every state_list member.
          Resolver's binding set may be a subset (covers_states) with its own closed
          optional field set.
  Tier 2  identity.constructors.<C>.parameterization      — WHICH construction this is.
          Closed manifest (pointers + closed-vocabulary invocation choices) whose
          canonical-JSON sha256 is `constructor_id`. `producer_id` alone cannot
          distinguish two parameterizations of the same constructor; this can.
          `determined: false` <=> `constructor_id: null` AND not runtime_eligible.
  Tier 3  identity.constructors.<C>.capabilities         — capability contract.
          `blocking_gaps` non-empty <=> `runtime_eligible: false` (enforced both
          directions so the flag cannot silently drift out of sync with the ledger).

Never eval YAML. Never dispatch models. Never execute formulas — `when` / `condition` /
`formula` / `eval` / `code` / `thresholds` / `required_fm` / `config_keys` /
`eligible_models` are forbidden anywhere in this document; those belong to the resolver's
own file or to WHO `state_contracts`, never to identity (design KD-2, Non-Goals).
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IDENTITY_PATH = _REPO_ROOT / "configs" / "formulas" / "crt_state_identity.yaml"


class CRTIdentityError(ValueError):
    """Fail-closed validation error for `crt_state_identity.yaml`."""


# ── Closed vocabularies (design §1) ──────────────────────────────────────────

_TIMEFRAME_ROLES = frozenset({"parent_timeframe", "execution_timeframe"})
_SUBGRAPHS = frozenset({"m15_execution", "parent_three_candle"})
_OCCUPANCY_CLASSES = frozenset({"ground", "event", "memory", "trade", "archive"})
_KNOWLEDGE_STATUS = frozenset({
    "UNKNOWN", "OBSERVED", "CHARACTERIZED", "MATHEMATICALLY_DEFINED",
    "FORMULA_DERIVED", "VALIDATED",
    # PRODUCTION_CERTIFIED and STABLE are ontology/G001 rungs. This program cites no G001.
})
_LIFECYCLE = frozenset({"proposed", "research", "registered", "parity_verified", "consumable", "deprecated"})
_DISPATCH = frozenset({"state_eq", "parent_track", "none"})
_TTL_KIND = frozenset({"none", "pending_displacement", "expansion_age"})
_RESET_TELEMETRY = frozenset({"none", "displacement_age", "candidate_age"})
_HANDLER_ALLOWLIST = frozenset({
    "process_range", "process_shadow_pending", "process_sweep", "process_displacement",
    "process_expansion", "process_expired", "process_c1", "process_c2", "process_c3",
})

# Tier 1 — semantic core. CLOSED. Every state must carry exactly this field set.
_TIER1_FIELDS = frozenset({
    "id", "name", "sem_id", "timeframe_role", "subgraph", "description", "occupancy_class",
    "requires_memory", "is_ground", "can_emit_signal", "can_emit_bias", "is_cycle_reset",
    "is_one_bar_archive", "self_loop_legal", "lifecycle", "knowledge_status", "epistemic", "notes",
})

# Tier 2 — engine constructor binding fields. CLOSED. Required for every state.
_ENGINE_BINDING_FIELDS = frozenset({
    "dispatch", "handler", "ttl_applies", "ttl_kind", "htf_protected",
    "htf_protect_via_active_trade", "creates_shadow_on_htf_reset", "records_entry_index",
    "records_entry_timestamp", "ends_expansion_telemetry_on_enter", "reset_telemetry",
    "reset_target", "source_ref",
})

# Tier 2 — resolver constructor binding fields. Required + optional (closed union).
_RESOLVER_BINDING_REQUIRED = frozenset({"defined", "predicate_source", "sticky", "reachable"})
_RESOLVER_BINDING_OPTIONAL = frozenset({"unreachable_reason", "construction_diverges_from_engine"})
_RESOLVER_BINDING_ALLOWED = _RESOLVER_BINDING_REQUIRED | _RESOLVER_BINDING_OPTIONAL

# Tier 2 — constructor PARAMETERIZATION manifest. Closed. Answers "WHICH construction of
# this identity is this?", which `producer_id` alone cannot: the repo holds at least two
# resolver occupancy series (RANGE 39,308 vs 21,745 on the same XAUUSD corpus) that differ
# only in parameterization and are today indistinguishable.
#
# The manifest declares POINTERS and closed-vocabulary choices, never file-content hashes.
# A content hash here would go stale on any unrelated config promotion and would turn this
# validator into a drift alarm for someone else's change. Content hashes belong on the
# RECORD (the separately-authorized `src/identity/` half), not on the declaration.
_PARAM_TOP_FIELDS = frozenset({"determined", "constructor_id", "construction", "invocation"})
_PARAM_INVOCATION_FIELDS = frozenset({"supply_set", "htf_source", "injection"})
_ENGINE_CONSTRUCTION_FIELDS = frozenset({
    "config_source", "config_selector", "topology_source", "state_machine_source",
})
_RESOLVER_CONSTRUCTION_FIELDS = frozenset({
    "states_config", "links_config", "variant", "enabled_links", "ontology_source",
    "waived_when_features",
})

# What a constructor is fed per bar. The two resolver callers differ HERE — this is the
# field that separates the two series above, and the reason a construction-only manifest
# would have been useless.
_SUPPLY_SETS = frozenset({
    "ohlcv_candle_stream",          # engine: Candle objects through process_candle
    "canonical_vector_only",        # CANONICAL_FEATURES only
    "canonical_plus_non_vector",    # + SOME named non-vector state inputs (historical
                                    # run_crt_state_on_mt5_xauusd: retest_flag +
                                    # displacement_flag only, rsi_state ABSENT, NaN->0.0)
    "enriched_all_columns",         # every enriched column (historical build_bar_matrix)
    "canonical_v5_plus_nonvector",  # CONTRACT-COMPLETE (features.resolver_supply):
                                    # every CANONICAL_FEATURES value sourced from the
                                    # vector + exactly the non-vector `when:`-named
                                    # features from the enriched frame, and NOTHING else.
                                    # Must equal resolver_supply.SUPPLY_SET_ID.
})
_HTF_SOURCES = frozenset({
    "internal_htf_builder",         # engine's own HTFBuilder
    "internal_counter",             # resolver's own counter (htf_id omitted — phase-drifts)
    "phase_locked_timeline",        # build_htf_id_timeline over the RAW stream
    "external_ids",                 # caller-supplied ids from another source
})
_INJECTION_MODES = frozenset({"none", "engine_state", "engine_reset", "both"})

# Fields that must never appear inside identity.states.<NAME> — Tier-2/WHO/resolver
# concerns. This is the "neutrality lint": it is what makes identity constructor-neutral
# mechanically, not just by convention.
_FORBIDDEN_IN_TIER1 = frozenset({
    "when", "condition", "formula", "eval", "code", "thresholds",
    "required_fm", "config_keys", "eligible_models", "parameterization",
}) | _ENGINE_BINDING_FIELDS

# Forbidden anywhere in the document root (execute-from-YAML rejection, design Non-Goals).
_FORBIDDEN_AT_ROOT = frozenset({"when", "condition", "formula", "eval", "code", "thresholds"})

_IDENTIFIER_BAD_CHARS = ("=", "*", "/", "(", ")", " ", "\t", "\n")

_REQUIRED_CONSTRUCTOR_CAPABILITY_FIELDS = frozenset({
    "produces_occupancy", "produces_memory", "covers_states", "reaches_signal_state",
    "produces_trade_geometry", "runtime_eligible", "blocking_gaps",
})


def _check_identifier(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CRTIdentityError(f"{where}: expected a non-empty string identifier, got {value!r}")
    if any(ch in value for ch in _IDENTIFIER_BAD_CHARS):
        raise CRTIdentityError(
            f"{where}={value!r} looks like an expression/formula — only bare identifiers allowed"
        )
    return value


def _require_keys(mapping: Mapping[str, Any], required: frozenset, *, where: str) -> None:
    missing = required - set(mapping.keys())
    if missing:
        raise CRTIdentityError(f"{where}: missing required field(s) {sorted(missing)}")


def _reject_unknown_keys(mapping: Mapping[str, Any], allowed: frozenset, *, where: str) -> None:
    unknown = set(mapping.keys()) - allowed
    if unknown:
        raise CRTIdentityError(f"{where}: unknown/forbidden field(s) {sorted(unknown)}")


# ── Root-level structural validation ─────────────────────────────────────────

def _validate_root(doc: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(doc, dict):
        raise CRTIdentityError(f"document root must be a mapping, got {type(doc).__name__}")
    if set(doc.keys()) != {"identity"}:
        raise CRTIdentityError(
            f"document root must be exactly {{'identity': <schema>}}, got keys {sorted(doc.keys())}"
        )
    ident = doc["identity"]
    if not isinstance(ident, dict):
        raise CRTIdentityError("identity: must be a mapping")
    return ident


def _validate_header(ident: Mapping[str, Any]) -> None:
    if ident.get("schema") != "crt_state_identity/v1":
        raise CRTIdentityError(f"identity.schema must be 'crt_state_identity/v1', got {ident.get('schema')!r}")
    version = ident.get("version")
    if not isinstance(version, int) or version < 1:
        raise CRTIdentityError(f"identity.version must be an int >= 1, got {version!r}")
    if ident.get("authority") != "user_approved":
        raise CRTIdentityError(f"identity.authority must be 'user_approved', got {ident.get('authority')!r}")
    for forbidden in _FORBIDDEN_AT_ROOT:
        if forbidden in ident:
            raise CRTIdentityError(f"identity.{forbidden} is forbidden — never eval'd, never authored here")


def _validate_state_list(ident: Mapping[str, Any]) -> list[str]:
    state_list = ident.get("state_list")
    if not isinstance(state_list, list) or not state_list:
        raise CRTIdentityError("identity.state_list must be a non-empty list")
    for i, name in enumerate(state_list):
        _check_identifier(name, where=f"identity.state_list[{i}]")
    if len(set(state_list)) != len(state_list):
        raise CRTIdentityError(f"identity.state_list has duplicate names: {state_list}")
    return list(state_list)


def _validate_parent_partition(ident: Mapping[str, Any], state_set: frozenset[str]) -> frozenset[str]:
    parent = ident.get("parent_timeframe_states")
    if not isinstance(parent, list):
        raise CRTIdentityError("identity.parent_timeframe_states must be a list")
    parent_set = frozenset(parent)
    unknown = parent_set - state_set
    if unknown:
        raise CRTIdentityError(f"identity.parent_timeframe_states names undeclared states: {sorted(unknown)}")
    if "execution_timeframe_states" in ident:
        raise CRTIdentityError(
            "identity.execution_timeframe_states must NOT be authored — it is the derived "
            "complement (state_list minus parent_timeframe_states)"
        )
    return parent_set


def _validate_transitions(ident: Mapping[str, Any], state_list: list[str]) -> dict[str, frozenset[str]]:
    state_set = frozenset(state_list)
    transitions = ident.get("valid_transitions")
    if not isinstance(transitions, dict):
        raise CRTIdentityError("identity.valid_transitions must be a mapping")
    if set(transitions.keys()) != state_set:
        only_t = sorted(set(transitions.keys()) - state_set)
        only_s = sorted(state_set - set(transitions.keys()))
        raise CRTIdentityError(
            f"identity.valid_transitions keys != state_list (only in transitions: {only_t}; "
            f"only in state_list: {only_s})"
        )
    edges: dict[str, frozenset[str]] = {}
    for src, targets in transitions.items():
        if not isinstance(targets, list):
            raise CRTIdentityError(f"identity.valid_transitions.{src} must be a list")
        for t in targets:
            _check_identifier(t, where=f"identity.valid_transitions.{src}[]")
            if t not in state_set:
                raise CRTIdentityError(f"identity.valid_transitions.{src} references undeclared state {t!r}")
        if len(set(targets)) != len(targets):
            raise CRTIdentityError(f"identity.valid_transitions.{src} has duplicate targets: {targets}")
        edges[src] = frozenset(targets)

    # Ratchet: SHADOW_PENDING -> EXPANSION is a resolver projection allowance ONLY, never
    # an identity edge (design KD-5).
    if "EXPANSION" in edges.get("SHADOW_PENDING", frozenset()):
        raise CRTIdentityError(
            "identity.valid_transitions.SHADOW_PENDING must NOT contain EXPANSION — that edge "
            "is a resolver projection allowance (constructors.resolver.projection_allowances), "
            "not an identity edge"
        )
    return edges


# ── Tier 1 — semantic core ────────────────────────────────────────────────────

def _validate_tier1_states(
    ident: Mapping[str, Any], state_list: list[str], parent_set: frozenset[str]
) -> Mapping[str, Mapping[str, Any]]:
    states = ident.get("states")
    if not isinstance(states, dict):
        raise CRTIdentityError("identity.states must be a mapping")
    state_set = frozenset(state_list)
    if set(states.keys()) != state_set:
        raise CRTIdentityError(
            f"identity.states keys != state_list (only in states: "
            f"{sorted(set(states.keys()) - state_set)}; only in state_list: "
            f"{sorted(state_set - set(states.keys()))})"
        )

    ground_by_subgraph: dict[str, list[str]] = {}
    for name, sd in states.items():
        where = f"identity.states.{name}"
        if not isinstance(sd, dict):
            raise CRTIdentityError(f"{where} must be a mapping")

        forbidden = _FORBIDDEN_IN_TIER1 & set(sd.keys())
        if forbidden:
            raise CRTIdentityError(
                f"{where}: Tier-2/constructor field(s) {sorted(forbidden)} are forbidden in the "
                f"semantic core — move to identity.constructors.<name>.states.{name} instead "
                f"(neutrality lint)"
            )
        _reject_unknown_keys(sd, _TIER1_FIELDS, where=where)
        _require_keys(sd, _TIER1_FIELDS, where=where)

        if sd["name"] != name:
            raise CRTIdentityError(f"{where}.name ({sd['name']!r}) must equal the mapping key ({name!r})")
        _check_identifier(sd["id"], where=f"{where}.id")
        if not sd["id"].startswith("CRT-S-"):
            raise CRTIdentityError(f"{where}.id must start with 'CRT-S-', got {sd['id']!r}")
        if sd["sem_id"] is not None:
            _check_identifier(sd["sem_id"], where=f"{where}.sem_id")

        if sd["timeframe_role"] not in _TIMEFRAME_ROLES:
            raise CRTIdentityError(f"{where}.timeframe_role invalid: {sd['timeframe_role']!r}")
        if sd["subgraph"] not in _SUBGRAPHS:
            raise CRTIdentityError(f"{where}.subgraph invalid: {sd['subgraph']!r}")
        expect_parent = name in parent_set
        role_is_parent = sd["timeframe_role"] == "parent_timeframe"
        if role_is_parent != expect_parent:
            raise CRTIdentityError(
                f"{where}.timeframe_role={sd['timeframe_role']!r} disagrees with "
                f"parent_timeframe_states membership ({expect_parent})"
            )
        subgraph_is_parent = sd["subgraph"] == "parent_three_candle"
        if subgraph_is_parent != expect_parent:
            raise CRTIdentityError(
                f"{where}.subgraph={sd['subgraph']!r} disagrees with parent_timeframe_states "
                f"membership ({expect_parent})"
            )

        if sd["occupancy_class"] not in _OCCUPANCY_CLASSES:
            raise CRTIdentityError(f"{where}.occupancy_class invalid: {sd['occupancy_class']!r}")
        for flag in (
            "requires_memory", "is_ground", "can_emit_signal", "can_emit_bias",
            "is_cycle_reset", "is_one_bar_archive", "self_loop_legal",
        ):
            if not isinstance(sd[flag], bool):
                raise CRTIdentityError(f"{where}.{flag} must be a bool")
        if sd["lifecycle"] not in _LIFECYCLE:
            raise CRTIdentityError(f"{where}.lifecycle invalid: {sd['lifecycle']!r}")
        if sd["knowledge_status"] not in _KNOWLEDGE_STATUS:
            raise CRTIdentityError(
                f"{where}.knowledge_status invalid or forbidden (no G001 rungs): {sd['knowledge_status']!r}"
            )
        if sd["knowledge_status"] in ("UNKNOWN", "OBSERVED") and sd["epistemic"] is None:
            raise CRTIdentityError(
                f"{where}: knowledge_status={sd['knowledge_status']!r} requires a non-null epistemic block"
            )
        if not isinstance(sd["description"], str) or not sd["description"].strip():
            raise CRTIdentityError(f"{where}.description must be a non-empty string")
        if not isinstance(sd["notes"], str):
            raise CRTIdentityError(f"{where}.notes must be a string (may be empty)")

        if sd["is_ground"]:
            ground_by_subgraph.setdefault(sd["subgraph"], []).append(name)

    for subgraph in _SUBGRAPHS:
        grounds = ground_by_subgraph.get(subgraph, [])
        if len(grounds) != 1:
            raise CRTIdentityError(
                f"subgraph {subgraph!r} must have exactly one is_ground state, found {grounds}"
            )

    return states


def _validate_disjointness(states: Mapping[str, Mapping[str, Any]], edges: Mapping[str, frozenset[str]]) -> None:
    for src, targets in edges.items():
        src_role = states[src]["timeframe_role"]
        for dst in targets:
            dst_role = states[dst]["timeframe_role"]
            if src_role != dst_role:
                raise CRTIdentityError(
                    f"identity.valid_transitions.{src} -> {dst} crosses timeframe_role "
                    f"({src_role} -> {dst_role}) — parent/execution subgraphs must stay disjoint (F-075)"
                )


def _validate_self_loops(states: Mapping[str, Mapping[str, Any]], edges: Mapping[str, frozenset[str]]) -> None:
    for name, targets in edges.items():
        has_self_loop = name in targets
        declared_legal = states[name]["self_loop_legal"]
        if has_self_loop != declared_legal:
            raise CRTIdentityError(
                f"identity.states.{name}.self_loop_legal={declared_legal} disagrees with the "
                f"presence of a {name} -> {name} edge in valid_transitions ({has_self_loop})"
            )


def _validate_signal_bias_uniqueness(states: Mapping[str, Mapping[str, Any]]) -> None:
    signal_states = [n for n, sd in states.items() if sd["can_emit_signal"]]
    if signal_states != ["EXECUTION"]:
        raise CRTIdentityError(f"exactly one state (EXECUTION) may have can_emit_signal: true, got {signal_states}")
    bias_states = [n for n, sd in states.items() if sd["can_emit_bias"]]
    if bias_states != ["DISTRIBUTION_C3"]:
        raise CRTIdentityError(f"exactly one state (DISTRIBUTION_C3) may have can_emit_bias: true, got {bias_states}")


# ── Tier 2/3 — constructors ───────────────────────────────────────────────────

def _validate_capabilities(caps: Mapping[str, Any], *, where: str) -> None:
    if not isinstance(caps, dict):
        raise CRTIdentityError(f"{where} must be a mapping")
    _require_keys(caps, _REQUIRED_CONSTRUCTOR_CAPABILITY_FIELDS, where=where)
    _reject_unknown_keys(caps, _REQUIRED_CONSTRUCTOR_CAPABILITY_FIELDS, where=where)
    for flag in ("produces_occupancy", "produces_memory", "reaches_signal_state",
                 "produces_trade_geometry", "runtime_eligible"):
        if not isinstance(caps[flag], bool):
            raise CRTIdentityError(f"{where}.{flag} must be a bool")
    if not isinstance(caps["covers_states"], list):
        raise CRTIdentityError(f"{where}.covers_states must be a list")
    if not isinstance(caps["blocking_gaps"], list):
        raise CRTIdentityError(f"{where}.blocking_gaps must be a list")
    for i, gap in enumerate(caps["blocking_gaps"]):
        if not isinstance(gap, dict) or not {"id", "capability", "summary", "evidence"} <= set(gap.keys()):
            raise CRTIdentityError(
                f"{where}.blocking_gaps[{i}] must carry id/capability/summary/evidence"
            )
        _check_identifier(gap["id"], where=f"{where}.blocking_gaps[{i}].id")

    # The load-bearing bidirectional invariant: the flag cannot silently drift from the ledger.
    has_gaps = bool(caps["blocking_gaps"])
    if has_gaps and caps["runtime_eligible"]:
        raise CRTIdentityError(f"{where}: runtime_eligible=true but blocking_gaps is non-empty")
    if not has_gaps and not caps["runtime_eligible"] and caps["reaches_signal_state"] and caps["produces_trade_geometry"]:
        raise CRTIdentityError(
            f"{where}: runtime_eligible=false with no blocking_gaps despite full capability — "
            f"either declare a gap or set runtime_eligible: true"
        )


def _validate_projection_allowances(
    allowances: Any, state_set: frozenset[str], identity_edges: Mapping[str, frozenset[str]], *, where: str
) -> None:
    if not isinstance(allowances, list):
        raise CRTIdentityError(f"{where} must be a list")
    for i, allow in enumerate(allowances):
        if not isinstance(allow, dict) or {"from", "to", "reason"} - set(allow.keys()):
            raise CRTIdentityError(f"{where}[{i}] must carry from/to/reason")
        src, dst = allow["from"], allow["to"]
        _check_identifier(src, where=f"{where}[{i}].from")
        _check_identifier(dst, where=f"{where}[{i}].to")
        if src not in state_set or dst not in state_set:
            raise CRTIdentityError(f"{where}[{i}] references undeclared state(s): {src!r} -> {dst!r}")
        if dst in identity_edges.get(src, frozenset()):
            raise CRTIdentityError(
                f"{where}[{i}] {src} -> {dst} is already an identity edge — a projection "
                f"allowance must be an ADDITIONAL edge, not a duplicate"
            )
        if not isinstance(allow["reason"], str) or not allow["reason"].strip():
            raise CRTIdentityError(f"{where}[{i}].reason must be a non-empty string")


def derive_constructor_id(parameterization: Mapping[str, Any]) -> str:
    """sha256 over the canonical JSON of {construction, invocation}.

    Same discipline `certify.py:238-240` already uses for `topology_id`, one level lower:
    `topology_id` identifies the transition GRAPH (which both constructors share by
    construction), this identifies the PARAMETERIZATION that produced a given occupancy.

    Sorted keys + compact separators so the id is a function of the declared values, not of
    YAML authoring order.
    """
    payload = {
        "construction": parameterization.get("construction"),
        "invocation": parameterization.get("invocation"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_parameterization(
    param: Any,
    *,
    where: str,
    construction_fields: frozenset,
    runtime_eligible: bool,
) -> None:
    """Validate one constructor's parameterization manifest.

    Two bidirectional invariants, both fail-closed, in the same shape as the existing
    `blocking_gaps <=> runtime_eligible` check:

      determined: true   => no null anywhere, and constructor_id == derive_constructor_id()
      determined: false  => constructor_id is null, at least one field IS null (otherwise
                            "undetermined" is a lie about a complete manifest), and the
                            constructor is NOT runtime_eligible — a construction nobody can
                            name cannot be eligible to run.
    """
    if not isinstance(param, dict):
        raise CRTIdentityError(f"{where} must be a mapping")
    _require_keys(param, _PARAM_TOP_FIELDS, where=where)
    _reject_unknown_keys(param, _PARAM_TOP_FIELDS, where=where)

    if not isinstance(param["determined"], bool):
        raise CRTIdentityError(f"{where}.determined must be a bool")

    construction = param["construction"]
    if not isinstance(construction, dict):
        raise CRTIdentityError(f"{where}.construction must be a mapping")
    _require_keys(construction, construction_fields, where=f"{where}.construction")
    _reject_unknown_keys(construction, construction_fields, where=f"{where}.construction")

    invocation = param["invocation"]
    if not isinstance(invocation, dict):
        raise CRTIdentityError(f"{where}.invocation must be a mapping")
    _require_keys(invocation, _PARAM_INVOCATION_FIELDS, where=f"{where}.invocation")
    _reject_unknown_keys(invocation, _PARAM_INVOCATION_FIELDS, where=f"{where}.invocation")

    for field, vocab in (
        ("supply_set", _SUPPLY_SETS),
        ("htf_source", _HTF_SOURCES),
        ("injection", _INJECTION_MODES),
    ):
        value = invocation[field]
        if value is not None and value not in vocab:
            raise CRTIdentityError(
                f"{where}.invocation.{field}={value!r} not in closed vocabulary {sorted(vocab)}"
            )

    has_null = any(v is None for v in construction.values()) or any(
        v is None for v in invocation.values()
    )

    if param["determined"]:
        if has_null:
            raise CRTIdentityError(
                f"{where}: determined=true but a construction/invocation field is null — "
                f"a determined manifest names every field"
            )
        expected = derive_constructor_id(param)
        if param["constructor_id"] != expected:
            raise CRTIdentityError(
                f"{where}.constructor_id does not match the derived manifest hash "
                f"(declared {param['constructor_id']!r}, derived {expected!r})"
            )
    else:
        if param["constructor_id"] is not None:
            raise CRTIdentityError(
                f"{where}: determined=false requires constructor_id: null"
            )
        if not has_null:
            raise CRTIdentityError(
                f"{where}: determined=false but every field is named — either set "
                f"determined: true or null the field that is genuinely undetermined"
            )
        if runtime_eligible:
            raise CRTIdentityError(
                f"{where}: runtime_eligible=true requires a determined parameterization — "
                f"a construction that cannot be named cannot be eligible to run"
            )


def _validate_engine_constructor(
    engine: Mapping[str, Any], state_list: list[str], identity_edges: Mapping[str, frozenset[str]]
) -> None:
    where = "identity.constructors.engine"
    if not isinstance(engine, dict):
        raise CRTIdentityError(f"{where} must be a mapping")
    _require_keys(
        engine,
        frozenset({"source", "description", "projection_allowances", "capabilities",
                   "parameterization", "states"}),
        where=where,
    )
    _validate_projection_allowances(
        engine["projection_allowances"], frozenset(state_list), identity_edges, where=f"{where}.projection_allowances"
    )
    _validate_capabilities(engine["capabilities"], where=f"{where}.capabilities")
    _validate_parameterization(
        engine["parameterization"],
        where=f"{where}.parameterization",
        construction_fields=_ENGINE_CONSTRUCTION_FIELDS,
        runtime_eligible=bool(engine["capabilities"]["runtime_eligible"]),
    )
    if not set(engine["capabilities"]["covers_states"]) <= frozenset(state_list):
        raise CRTIdentityError(f"{where}.capabilities.covers_states must be a subset of state_list")

    states = engine.get("states")
    if not isinstance(states, dict) or set(states.keys()) != frozenset(state_list):
        raise CRTIdentityError(f"{where}.states must define every state in state_list, no more, no fewer")
    for name, sd in states.items():
        sub_where = f"{where}.states.{name}"
        if not isinstance(sd, dict):
            raise CRTIdentityError(f"{sub_where} must be a mapping")
        _require_keys(sd, _ENGINE_BINDING_FIELDS, where=sub_where)
        _reject_unknown_keys(sd, _ENGINE_BINDING_FIELDS, where=sub_where)
        if sd["dispatch"] not in _DISPATCH:
            raise CRTIdentityError(f"{sub_where}.dispatch invalid: {sd['dispatch']!r}")
        if sd["dispatch"] == "none":
            if sd["handler"] is not None:
                raise CRTIdentityError(f"{sub_where}.handler must be null when dispatch == 'none'")
        else:
            if sd["handler"] not in _HANDLER_ALLOWLIST:
                raise CRTIdentityError(
                    f"{sub_where}.handler={sd['handler']!r} not in the planned allowlist {sorted(_HANDLER_ALLOWLIST)}"
                )
        if sd["ttl_kind"] not in _TTL_KIND:
            raise CRTIdentityError(f"{sub_where}.ttl_kind invalid: {sd['ttl_kind']!r}")
        if sd["ttl_applies"] and sd["ttl_kind"] == "none":
            raise CRTIdentityError(f"{sub_where}: ttl_applies=true requires ttl_kind != 'none'")
        if not sd["ttl_applies"] and sd["ttl_kind"] != "none":
            raise CRTIdentityError(f"{sub_where}: ttl_kind={sd['ttl_kind']!r} requires ttl_applies: true")
        if sd["reset_telemetry"] not in _RESET_TELEMETRY:
            raise CRTIdentityError(f"{sub_where}.reset_telemetry invalid: {sd['reset_telemetry']!r}")
        if sd["reset_telemetry"] == "displacement_age" and sd["reset_telemetry"] == "candidate_age":
            raise CRTIdentityError(f"{sub_where}: reset_telemetry arms are mutually exclusive")  # unreachable, defensive
        _check_identifier(sd["reset_target"], where=f"{sub_where}.reset_target")
        if sd["reset_target"] not in state_list:
            raise CRTIdentityError(f"{sub_where}.reset_target references undeclared state {sd['reset_target']!r}")
        for flag in (
            "ttl_applies", "htf_protected", "htf_protect_via_active_trade",
            "creates_shadow_on_htf_reset", "records_entry_index", "records_entry_timestamp",
            "ends_expansion_telemetry_on_enter",
        ):
            if not isinstance(sd[flag], bool):
                raise CRTIdentityError(f"{sub_where}.{flag} must be a bool")
        if not isinstance(sd["source_ref"], str) or not sd["source_ref"].strip():
            raise CRTIdentityError(f"{sub_where}.source_ref must be a non-empty string")


def _validate_resolver_constructor(
    resolver: Mapping[str, Any], state_list: list[str], identity_edges: Mapping[str, frozenset[str]]
) -> None:
    where = "identity.constructors.resolver"
    if not isinstance(resolver, dict):
        raise CRTIdentityError(f"{where} must be a mapping")
    _require_keys(
        resolver,
        frozenset({"source", "description", "projection_allowances", "capabilities",
                   "parameterization", "states"}),
        where=where,
    )
    state_set = frozenset(state_list)
    _validate_projection_allowances(
        resolver["projection_allowances"], state_set, identity_edges, where=f"{where}.projection_allowances"
    )
    _validate_capabilities(resolver["capabilities"], where=f"{where}.capabilities")
    _validate_parameterization(
        resolver["parameterization"],
        where=f"{where}.parameterization",
        construction_fields=_RESOLVER_CONSTRUCTION_FIELDS,
        runtime_eligible=bool(resolver["capabilities"]["runtime_eligible"]),
    )
    covers = resolver["capabilities"]["covers_states"]
    if not set(covers) <= state_set:
        raise CRTIdentityError(f"{where}.capabilities.covers_states must be a subset of state_list (no 13th state)")
    # F-069 floor: 9 of 12 today. Not pinned to an exact count (a future measured change
    # to resolver coverage should not require editing this validator), but it must never
    # exceed identity's own state_list.

    states = resolver.get("states")
    if not isinstance(states, dict) or not set(states.keys()) <= state_set:
        raise CRTIdentityError(f"{where}.states keys must be a subset of state_list (no invented 13th state)")
    for name, sd in states.items():
        sub_where = f"{where}.states.{name}"
        if not isinstance(sd, dict):
            raise CRTIdentityError(f"{sub_where} must be a mapping")
        _require_keys(sd, _RESOLVER_BINDING_REQUIRED, where=sub_where)
        _reject_unknown_keys(sd, _RESOLVER_BINDING_ALLOWED, where=sub_where)
        if not isinstance(sd["defined"], bool):
            raise CRTIdentityError(f"{sub_where}.defined must be a bool")
        if not isinstance(sd["sticky"], bool):
            raise CRTIdentityError(f"{sub_where}.sticky must be a bool")
        if not isinstance(sd["reachable"], bool):
            raise CRTIdentityError(f"{sub_where}.reachable must be a bool")
        if not sd["reachable"] and "unreachable_reason" not in sd:
            raise CRTIdentityError(f"{sub_where}: reachable=false requires unreachable_reason")
        if sd["reachable"] and sd["defined"] and not sd["predicate_source"]:
            raise CRTIdentityError(f"{sub_where}: reachable+defined requires a non-empty predicate_source")


def _validate_constructors(ident: Mapping[str, Any], state_list: list[str], identity_edges: Mapping[str, frozenset[str]]) -> Mapping[str, Any]:
    constructors = ident.get("constructors")
    if not isinstance(constructors, dict):
        raise CRTIdentityError("identity.constructors must be a mapping")
    _require_keys(constructors, frozenset({"engine", "resolver"}), where="identity.constructors")
    _validate_engine_constructor(constructors["engine"], state_list, identity_edges)
    _validate_resolver_constructor(constructors["resolver"], state_list, identity_edges)

    eligible = [
        name for name, c in constructors.items()
        if isinstance(c, dict) and c.get("capabilities", {}).get("runtime_eligible")
    ]
    if eligible != ["engine"]:
        raise CRTIdentityError(
            f"exactly one constructor must be runtime_eligible today (engine); got {eligible}"
        )
    return constructors


# ── Public API ────────────────────────────────────────────────────────────────

def validate_crt_identity(doc: Mapping[str, Any]) -> Mapping[str, Any]:
    """Fail-closed validation of a parsed `crt_state_identity.yaml` document.

    Returns the inner `identity` mapping on success. Raises `CRTIdentityError` on any
    violation. Does not load a file, does not build a `CRTModel`, does not touch
    `CRTEngine.__init__` (that binding is PR-2/PR-3 scope — see design KD-16: an unused
    hold must not take down production).
    """
    ident = _validate_root(doc)
    _validate_header(ident)
    state_list = _validate_state_list(ident)
    parent_set = _validate_parent_partition(ident, frozenset(state_list))
    edges = _validate_transitions(ident, state_list)
    states = _validate_tier1_states(ident, state_list, parent_set)
    _validate_disjointness(states, edges)
    _validate_self_loops(states, edges)
    _validate_signal_bias_uniqueness(states)
    _validate_constructors(ident, state_list, edges)
    return ident


def load_crt_identity_yaml(path: Path | str = DEFAULT_IDENTITY_PATH) -> Mapping[str, Any]:
    """Read + parse (not validate) the identity YAML. utf-8, matching the generator's own
    encoding discipline (`gen_crt_state_identity.py:_load_runtime`)."""
    with io.open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_crt_identity_file(path: Path | str = DEFAULT_IDENTITY_PATH) -> Mapping[str, Any]:
    """Load + validate in one call. Convenience for tests/tooling; not called from any
    production import path in PR-1."""
    return validate_crt_identity(load_crt_identity_yaml(path))
