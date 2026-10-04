"""
CRT Semantic Authority — floor tests for `configs/formulas/crt_state_identity.yaml` (PR-1).

Declaration-only. No loader wiring, no `CRTModel`, no `CRTEngine.__init__` binding — this
file pins the identity YAML's own internal consistency, its parity against today's
generation source (`active_models.yaml`) and the generated artifact
(`_crt_state_generated.py`), and — the load-bearing check — the "neutrality lint" that
keeps Tier-2 (constructor) fields out of Tier-1 (semantic core).

See `docs/implementation_plan/crt-state-identity-ontology-2026-09.md` (Alternative I,
"constructor-neutral identity") for the design this pins.

conftest.py puts `src/` on sys.path.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from config_layer.crt_identity_schema import (
    CRTIdentityError,
    DEFAULT_IDENTITY_PATH,
    derive_constructor_id,
    load_crt_identity_yaml,
    validate_crt_identity,
    validate_crt_identity_file,
)
from config_layer.state_identity import (
    CRTState,
    VALID_TRANSITIONS,
    PARENT_TIMEFRAME_STATES,
)

_ROOT = Path(__file__).resolve().parents[1]
_MARKET_CRT_STATES_PATH = _ROOT / "configs" / "formulas" / "market_crt_states.yaml"


@pytest.fixture(scope="module")
def identity_doc() -> dict:
    return dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH))


@pytest.fixture(scope="module")
def identity() -> dict:
    return dict(validate_crt_identity_file(DEFAULT_IDENTITY_PATH))


@pytest.fixture(scope="module")
def active_models_crt_runtime() -> dict:
    with open(_ROOT / "active_models.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["crt"]["runtime"]


@pytest.fixture(scope="module")
def market_crt_states() -> dict:
    with open(_MARKET_CRT_STATES_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ── File exists and validates cleanly ────────────────────────────────────────

def test_identity_file_exists() -> None:
    assert DEFAULT_IDENTITY_PATH.exists(), f"missing {DEFAULT_IDENTITY_PATH}"


def test_identity_validates(identity: dict) -> None:
    assert identity["schema"] == "crt_state_identity/v1"
    assert identity["authority"] == "user_approved"


def test_document_root_is_exactly_identity_key(identity_doc: dict) -> None:
    assert set(identity_doc.keys()) == {"identity"}


# ── Parity vs the CURRENT generation source (active_models.yaml) ────────────
# PR-1 is declaration-only: the generator still reads active_models.yaml. This is the
# parity floor that must hold until PR-3 migrates SOURCE_YAML.

def test_state_list_matches_who_source_order(identity: dict, active_models_crt_runtime: dict) -> None:
    assert identity["state_list"] == list(active_models_crt_runtime["state_list"])


def test_parent_timeframe_states_matches_who_source(identity: dict, active_models_crt_runtime: dict) -> None:
    assert set(identity["parent_timeframe_states"]) == set(active_models_crt_runtime["parent_timeframe_states"])


def test_valid_transitions_matches_who_source_edge_set(identity: dict, active_models_crt_runtime: dict) -> None:
    got = {k: set(v) for k, v in identity["valid_transitions"].items()}
    want = {k: set(v) for k, v in active_models_crt_runtime["valid_transitions"].items()}
    assert got == want


# ── Parity vs the GENERATED artifact ──────────────────────────────────────────

def test_state_list_matches_generated_crtstate_order(identity: dict) -> None:
    generated_order = [m.name for m in sorted(CRTState, key=lambda m: m.value)]
    assert identity["state_list"] == generated_order


def test_valid_transitions_matches_generated_edge_set(identity: dict) -> None:
    got = {k: frozenset(v) for k, v in identity["valid_transitions"].items()}
    want = {src.name: frozenset(t.name for t in targets) for src, targets in VALID_TRANSITIONS.items()}
    assert got == want


def test_parent_timeframe_states_matches_generated(identity: dict) -> None:
    assert set(identity["parent_timeframe_states"]) == {s.name for s in PARENT_TIMEFRAME_STATES}


def test_execution_timeframe_states_not_authored(identity_doc: dict) -> None:
    assert "execution_timeframe_states" not in identity_doc["identity"]


# ── Forbidden vocabulary (never eval, never execute from YAML) ──────────────

@pytest.mark.parametrize(
    "forbidden",
    ["when", "condition", "formula", "eval", "code", "thresholds",
     "required_fm", "config_keys", "eligible_models"],
)
def test_forbidden_fields_absent_from_every_tier1_state(identity: dict, forbidden: str) -> None:
    for name, sd in identity["states"].items():
        assert forbidden not in sd, f"identity.states.{name}.{forbidden} is forbidden"


def test_negative_description_with_finding_citation_is_legal(identity: dict) -> None:
    """`(F-074)` etc. must pass — the injection guard is identifier-scoped, prose-exempt."""
    joined = " ".join(sd["notes"] + sd["description"] for sd in identity["states"].values())
    assert "F-074" in joined or "F-069" in joined  # sanity: real citations are present


def test_positive_handler_expression_injection_is_rejected() -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["constructors"]["engine"]["states"]["RANGE"]["handler"] = "abs(close-open)"
    with pytest.raises(CRTIdentityError):
        validate_crt_identity(doc)


# ── Neutrality lint — the load-bearing check ─────────────────────────────────

@pytest.mark.parametrize(
    "engine_field",
    ["handler", "dispatch", "htf_protected", "records_entry_index", "reset_telemetry",
     "ttl_kind", "creates_shadow_on_htf_reset"],
)
def test_engine_field_leaking_into_tier1_is_rejected(engine_field: str) -> None:
    """The neutrality lint: no Tier-2 (constructor-shaped) field name may appear under
    identity.states.<NAME>. This is what stops identity from becoming engine-shaped again —
    the exact defect the original draft's StateDefinition had."""
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["states"]["EXPANSION"][engine_field] = True
    with pytest.raises(CRTIdentityError, match="neutrality lint"):
        validate_crt_identity(doc)


def test_htf_protected_move_out_of_tier1_fails_as_specified() -> None:
    """The exact negative check named in the plan verification section."""
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["states"]["EXPANSION"]["htf_protected"] = True
    with pytest.raises(CRTIdentityError):
        validate_crt_identity(doc)


# ── Resolver cannot invent a 13th state (9 subset of 12) ─────────────────────

def test_resolver_covers_states_is_subset_of_identity(identity: dict) -> None:
    resolver = identity["constructors"]["resolver"]
    covers = set(resolver["capabilities"]["covers_states"])
    assert covers <= set(identity["state_list"])
    assert covers == {"RANGE", "SHADOW_PENDING", "SWEEP", "DISPLACEMENT", "EXPANSION",
                       "EXPIRED", "RETEST", "EXECUTION", "RESOLUTION"}


def test_resolver_defined_names_are_subset_of_market_crt_states_yaml(identity: dict, market_crt_states: dict) -> None:
    resolver_defined = {
        name for name, sd in identity["constructors"]["resolver"]["states"].items() if sd["defined"]
    }
    market_names = {s["name"] for s in market_crt_states["states"]}
    assert resolver_defined <= market_names


def test_resolver_invented_state_is_rejected() -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["constructors"]["resolver"]["capabilities"]["covers_states"].append("NOT_A_REAL_STATE")
    with pytest.raises(CRTIdentityError):
        validate_crt_identity(doc)


# ── SHADOW_PENDING -> EXPANSION: resolver allowance only, never an identity edge ─

def test_shadow_pending_to_expansion_absent_from_identity_graph(identity: dict) -> None:
    assert "EXPANSION" not in set(identity["valid_transitions"]["SHADOW_PENDING"])


def test_shadow_pending_to_expansion_present_exactly_once_as_resolver_allowance(identity: dict) -> None:
    allowances = identity["constructors"]["resolver"]["projection_allowances"]
    matches = [a for a in allowances if a["from"] == "SHADOW_PENDING" and a["to"] == "EXPANSION"]
    assert len(matches) == 1


def test_engine_constructor_has_no_projection_allowances(identity: dict) -> None:
    assert identity["constructors"]["engine"]["projection_allowances"] == []


def test_stale_allowance_would_be_rejected_as_duplicate_edge() -> None:
    """If SHADOW_PENDING -> EXPANSION were ever added to the identity graph itself, the
    allowance declaring the same edge becomes a duplicate and must fail (mirrors the
    stale-pin ratchet in tests/test_crt_states_yaml_transition_parity.py)."""
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["valid_transitions"]["SHADOW_PENDING"].append("EXPANSION")
    with pytest.raises(CRTIdentityError):
        validate_crt_identity(doc)


# ── Capability contract: blocking_gaps <=> not runtime_eligible ─────────────

def test_engine_is_runtime_eligible_with_no_blocking_gaps(identity: dict) -> None:
    caps = identity["constructors"]["engine"]["capabilities"]
    assert caps["runtime_eligible"] is True
    assert caps["blocking_gaps"] == []


def test_resolver_is_not_runtime_eligible_with_two_named_gaps(identity: dict) -> None:
    caps = identity["constructors"]["resolver"]["capabilities"]
    assert caps["runtime_eligible"] is False
    gap_ids = {g["id"] for g in caps["blocking_gaps"]}
    assert gap_ids == {"GAP-RESOLVER-001", "GAP-RESOLVER-002"}


def test_exactly_one_constructor_is_runtime_eligible(identity: dict) -> None:
    eligible = [
        name for name, c in identity["constructors"].items()
        if c["capabilities"]["runtime_eligible"]
    ]
    assert eligible == ["engine"]


def test_blocking_gaps_non_empty_forces_runtime_eligible_false() -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["constructors"]["resolver"]["capabilities"]["runtime_eligible"] = True
    with pytest.raises(CRTIdentityError):
        validate_crt_identity(doc)


def test_resolver_execution_gap_cites_source_independent_of_f069(identity: dict) -> None:
    caps = identity["constructors"]["resolver"]["capabilities"]
    gap = next(g for g in caps["blocking_gaps"] if g["id"] == "GAP-RESOLVER-001")
    assert gap["independent_of_f069"] is True
    assert "crt_state_resolver.py" in gap["evidence"]


# ── knowledge_status forbids G001 rungs ──────────────────────────────────────

def test_no_state_has_production_certified_or_stable(identity: dict) -> None:
    forbidden = {"PRODUCTION_CERTIFIED", "STABLE"}
    for name, sd in identity["states"].items():
        assert sd["knowledge_status"] not in forbidden, f"{name} carries a G001 rung"


def test_production_certified_knowledge_status_is_rejected() -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["states"]["RANGE"]["knowledge_status"] = "PRODUCTION_CERTIFIED"
    with pytest.raises(CRTIdentityError):
        validate_crt_identity(doc)


# ── Disjointness (F-075) and self-loop legality ──────────────────────────────

def test_no_edge_crosses_timeframe_role(identity: dict) -> None:
    states = identity["states"]
    for src, targets in identity["valid_transitions"].items():
        for dst in targets:
            assert states[src]["timeframe_role"] == states[dst]["timeframe_role"], (
                f"{src} -> {dst} crosses timeframe_role"
            )


def test_range_and_range_c1_are_not_collapsed(identity: dict) -> None:
    assert identity["states"]["RANGE"]["subgraph"] == "m15_execution"
    assert identity["states"]["RANGE_C1"]["subgraph"] == "parent_three_candle"
    assert identity["states"]["RANGE"]["is_ground"] is True
    assert identity["states"]["RANGE_C1"]["is_ground"] is True


def test_range_c1_self_loop_legal_m15_range_is_not(identity: dict) -> None:
    assert identity["states"]["RANGE_C1"]["self_loop_legal"] is True
    assert "RANGE_C1" in identity["valid_transitions"]["RANGE_C1"]
    assert identity["states"]["RANGE"]["self_loop_legal"] is False
    assert "RANGE" not in identity["valid_transitions"]["RANGE"]


# ── Capability declarations: exactly one signal state, one bias state ───────

def test_only_execution_can_emit_signal(identity: dict) -> None:
    signal_states = [n for n, sd in identity["states"].items() if sd["can_emit_signal"]]
    assert signal_states == ["EXECUTION"]


def test_only_distribution_c3_can_emit_bias(identity: dict) -> None:
    bias_states = [n for n, sd in identity["states"].items() if sd["can_emit_bias"]]
    assert bias_states == ["DISTRIBUTION_C3"]


# ── Engine binding covers all 12; handler allowlist ──────────────────────────

def test_engine_bindings_cover_every_state(identity: dict) -> None:
    assert set(identity["constructors"]["engine"]["states"].keys()) == set(identity["state_list"])


def test_engine_dispatch_none_implies_null_handler(identity: dict) -> None:
    for name, sd in identity["constructors"]["engine"]["states"].items():
        if sd["dispatch"] == "none":
            assert sd["handler"] is None, f"{name}: dispatch=none must have handler=null"


def test_retest_execution_resolution_have_dispatch_none(identity: dict) -> None:
    eng = identity["constructors"]["engine"]["states"]
    for name in ("RETEST", "EXECUTION", "RESOLUTION"):
        assert eng[name]["dispatch"] == "none", f"{name} is not a process_candle `s ==` branch"


# ── F-069 evidence preserved, not re-measured ────────────────────────────────

def test_expansion_construction_divergence_flagged_on_resolver(identity: dict) -> None:
    exp = identity["constructors"]["resolver"]["states"]["EXPANSION"]
    assert exp.get("construction_diverges_from_engine") is True


# ── Constructor parameterization: WHICH construction is this? ────────────────
#
# `producer_id` alone cannot distinguish two parameterizations of one constructor.
# The repo demonstrates the gap: two resolver occupancy series on the same XAUUSD
# corpus (RANGE 39,308 vs 21,745) differ only in `invocation.supply_set`.

def test_both_constructors_declare_a_parameterization(identity: dict) -> None:
    for name, c in identity["constructors"].items():
        assert "parameterization" in c, f"{name} declares no parameterization manifest"


def test_engine_parameterization_is_determined_and_id_matches_derivation(identity: dict) -> None:
    pm = identity["constructors"]["engine"]["parameterization"]
    assert pm["determined"] is True
    assert pm["constructor_id"] == derive_constructor_id(pm)


def test_resolver_parameterization_is_determined_by_the_supply_contract(identity: dict) -> None:
    """UPDATED 2026-09-04. This floor previously pinned `determined: false` while the
    39,308-vs-21,745 divergence was an explicit UNKNOWN. It was NOT resolved by picking
    a winner — `features/resolver_supply.py` made the supply set a single construction
    (canonical values from the vector, non-vector `when:` features from the enriched
    frame, nothing else), and the rewired caller reproduces the other series exactly.

    The pre-flip tokens are kept here so the transition is legible rather than erased
    (S6.2 rule 4): was determined=False / constructor_id=None / supply_set=None.
    """
    pm = identity["constructors"]["resolver"]["parameterization"]
    assert pm["determined"] is True
    assert pm["invocation"]["supply_set"] == "canonical_v5_plus_nonvector"
    assert pm["constructor_id"] == derive_constructor_id(pm)


def test_supply_set_token_matches_the_producing_module(identity: dict) -> None:
    """The YAML token and the adapter's SUPPLY_SET_ID are the same string by contract.
    If they drift, the manifest names a construction no code produces."""
    from features.resolver_supply import SUPPLY_SET_ID

    pm = identity["constructors"]["resolver"]["parameterization"]
    assert pm["invocation"]["supply_set"] == SUPPLY_SET_ID


def test_determined_supply_set_does_not_grant_runtime_eligibility(identity: dict) -> None:
    """Naming the parameterization is orthogonal to capability. The resolver still has
    two blocking gaps (EXECUTION unreachable, no trade geometry), so a determined
    manifest must NOT quietly promote it."""
    resolver = identity["constructors"]["resolver"]
    assert resolver["parameterization"]["determined"] is True
    assert resolver["capabilities"]["runtime_eligible"] is False
    assert len(resolver["capabilities"]["blocking_gaps"]) == 2


def test_missing_invocation_half_fails_closed() -> None:
    """A construction-only manifest would give the two resolver series the SAME id —
    the exact failure this field exists to prevent."""
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    del doc["identity"]["constructors"]["engine"]["parameterization"]["invocation"]
    with pytest.raises(CRTIdentityError):
        validate_crt_identity(doc)


@pytest.mark.parametrize("field", ["supply_set", "htf_source", "injection"])
def test_out_of_vocabulary_invocation_value_is_rejected(field: str) -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["constructors"]["engine"]["parameterization"]["invocation"][field] = "whatever"
    with pytest.raises(CRTIdentityError, match="closed vocabulary"):
        validate_crt_identity(doc)


def test_parameterization_leaking_into_tier1_is_rejected() -> None:
    """Parameterization is a constructor concern, never semantic core."""
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["states"]["EXPANSION"]["parameterization"] = {"determined": False}
    with pytest.raises(CRTIdentityError, match="neutrality lint"):
        validate_crt_identity(doc)


def test_constructor_id_is_a_function_of_the_invocation_half() -> None:
    """Changing ONLY an invocation field must change the id — otherwise two callers
    feeding different supply sets would collide."""
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    pm = doc["identity"]["constructors"]["engine"]["parameterization"]
    before = derive_constructor_id(pm)
    pm["invocation"]["supply_set"] = "canonical_plus_non_vector"
    assert derive_constructor_id(pm) != before


def test_identical_manifests_derive_identical_ids() -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    pm = doc["identity"]["constructors"]["engine"]["parameterization"]
    assert derive_constructor_id(pm) == derive_constructor_id(copy.deepcopy(pm))


def test_declared_id_out_of_sync_with_manifest_is_rejected() -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["constructors"]["engine"]["parameterization"]["constructor_id"] = "0" * 64
    with pytest.raises(CRTIdentityError, match="derived manifest hash"):
        validate_crt_identity(doc)


def test_determined_true_with_a_null_field_is_rejected() -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    pm = doc["identity"]["constructors"]["engine"]["parameterization"]
    pm["invocation"]["htf_source"] = None
    pm["constructor_id"] = derive_constructor_id(pm)  # id kept consistent: the NULL is the defect
    with pytest.raises(CRTIdentityError, match="determined=true"):
        validate_crt_identity(doc)


def test_undetermined_constructor_cannot_be_runtime_eligible() -> None:
    """A construction that cannot be named cannot be eligible to run — the same
    bidirectional shape as blocking_gaps <=> runtime_eligible."""
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    pm = doc["identity"]["constructors"]["engine"]["parameterization"]
    pm["determined"] = False
    pm["constructor_id"] = None
    pm["invocation"]["supply_set"] = None
    with pytest.raises(CRTIdentityError, match="cannot be named"):
        validate_crt_identity(doc)


def test_undetermined_with_every_field_named_is_rejected() -> None:
    """`determined: false` must point at a genuinely null field, not be a free pass on a
    complete manifest — otherwise 'undetermined' becomes the silent-gap escape hatch."""
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    pm = doc["identity"]["constructors"]["resolver"]["parameterization"]
    # Construct the undetermined-but-complete shape explicitly rather than relying on
    # the live manifest still being undetermined — it is not, since 2026-09-04, and a
    # floor for an invariant must not depend on the current value it guards.
    pm["determined"] = False
    pm["constructor_id"] = None
    assert all(v is not None for v in pm["invocation"].values())
    assert all(v is not None for v in pm["construction"].values())
    with pytest.raises(CRTIdentityError, match="every field is named"):
        validate_crt_identity(doc)


def test_unknown_key_in_parameterization_is_rejected() -> None:
    doc = copy.deepcopy(dict(load_crt_identity_yaml(DEFAULT_IDENTITY_PATH)))
    doc["identity"]["constructors"]["resolver"]["parameterization"]["extra"] = 1
    with pytest.raises(CRTIdentityError):
        validate_crt_identity(doc)
