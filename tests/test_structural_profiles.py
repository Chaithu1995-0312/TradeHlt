"""RC-9 — founding profiles as data (`SPP-*`), their validator, and their grounding.

A profile names the answer to *"what is the box?"* — the reference object a structural
predicate is evaluated against. Before RC-9 a program expressed its founding by writing a
MODULE, so "which founding produced this evidence?" was answered by reading import paths.

Three properties are pinned here, and each is proved by MUTATION rather than by a green run —
the lesson this program has now re-learned three times (SK-0 registered without enforcement;
the RC-4 binding test could not fail; the RC-6 shape check had a recall hole):

  1. the seed validates, and the validator rejects each way a profile can be wrong;
  2. `SPP-*` grounds AND cites its own declaring file — with the negative case proving BOTH
     halves (regex + collection) are load-bearing rather than one masking the other;
  3. a missing sibling is a VALIDATOR PROBLEM, never an import-time raise — the property most
     likely to regress silently, because it only shows up when the file is absent.
"""
from __future__ import annotations

import copy

import pytest

from features.registry import (
    load_ontology,
    load_structural_profiles,
    validate_registry,
    validate_semantic_registry,
    validate_structural_profiles,
)

_SEED_IDS = {"SPP-001", "SPP-002", "SPP-003", "SPP-004"}


@pytest.fixture(scope="module")
def ont() -> dict:
    return load_ontology()


@pytest.fixture(scope="module")
def profiles() -> dict:
    return load_structural_profiles()


# ── The seed ─────────────────────────────────────────────────────────────────

def test_seed_profiles_validate(ont) -> None:
    assert validate_structural_profiles(ont) == []


def test_all_four_foundings_are_declared(profiles) -> None:
    ids = {p["id"] for p in profiles["structural_profiles"].values()}
    assert ids == _SEED_IDS


def test_the_incumbent_is_declared_alongside_research(profiles) -> None:
    """The live engine founding must be a peer, or a research profile is an orphan."""
    by_id = {p["id"]: p for p in profiles["structural_profiles"].values()}
    assert by_id["SPP-001"]["status"] == "registered"
    assert by_id["SPP-002"]["status"] == "registered"   # armed on the active config
    assert by_id["SPP-003"]["status"] == "research"
    assert by_id["SPP-004"]["status"] == "research"


def test_profiles_do_not_disturb_the_existing_validators(ont) -> None:
    """A sibling file must not leak into the walkers that own the main ontology."""
    assert validate_registry(ont) == []
    assert validate_semantic_registry(ont) == []


def test_profiles_are_not_a_semantic_registry_section(ont) -> None:
    """Listing them in `sections:` would force the wrong 25-field contract onto them."""
    sr = ont["spec_schema"]["semantic_registry"]
    assert "structural_profiles" not in tuple(sr.get("sections") or ())
    assert sr["external_sections"]["structural_profiles"].endswith("structure_profiles.yaml")


# ── The validator must reject every way a profile can be wrong ───────────────

def _mutate(ont: dict, profiles: dict, fn) -> tuple[dict, dict]:
    o, p = copy.deepcopy(ont), copy.deepcopy(profiles)
    fn(p["structural_profiles"])
    return o, p


def _problems_with(monkeypatch, ont: dict, mutated: dict) -> list[str]:
    import features.registry as reg
    monkeypatch.setattr(reg, "load_structural_profiles", lambda ontology=None: mutated)
    return reg.validate_structural_profiles(ont)


@pytest.mark.parametrize(
    "mutator,expect",
    [
        (lambda b: b["crt_m15_live"].__setitem__("id", "SP-001"), "must match"),
        (lambda b: b["crt_m15_live"].__setitem__("id", "SPP-abc"), "must match"),
        (lambda b: b["crt_m15_live"].__setitem__("status", "promoted"), "status"),
        (lambda b: b["crt_m15_live"].__setitem__("version", "1"), "version must be an int"),
        (lambda b: b["crt_m15_live"].pop("owner"), "missing required key 'owner'"),
        (lambda b: b["crt_m15_live"].pop("evidence"), "missing required key 'evidence'"),
        (lambda b: b["crt_m15_live"].pop("origin"), "missing required key 'origin'"),
        (lambda b: b["crt_m15_live"].__setitem__("walk", "SP-999"), "not a declared ontology id"),
        (lambda b: b["crt_m15_live"].__setitem__("predicates", ["SP-404"]), "not a declared ontology id"),
        (lambda b: b["crt_m15_live"]["founding"].__setitem__("identity", "SEM-999"), "not a declared ontology id"),
        (lambda b: b["crt_m15_live"].__setitem__("founding", "a string"), "founding must be a mapping"),
        (lambda b: b["crt_m15_live"].__setitem__("aliases", "not-a-list"), "aliases must be a list"),
        (lambda b: b["parent_h4"].__setitem__("id", "SPP-001"), "duplicate id"),
    ],
    ids=[
        "wrong-namespace", "non-numeric-id", "unknown-status", "string-version",
        "missing-owner", "missing-evidence", "missing-origin",
        "undeclared-walk", "undeclared-predicate", "undeclared-founding",
        "founding-not-mapping", "aliases-not-list", "duplicate-id",
    ],
)
def test_validator_rejects_a_malformed_profile(monkeypatch, ont, profiles, mutator, expect) -> None:
    o, mutated = _mutate(ont, profiles, mutator)
    problems = _problems_with(monkeypatch, o, mutated)
    assert any(expect in p for p in problems), f"expected {expect!r}; got {problems}"


def test_validator_rejects_a_threshold_VALUE_not_a_name(monkeypatch, ont, profiles) -> None:
    """Copying a number into a profile creates the second source of truth this program removes."""
    o, mutated = _mutate(
        ont, profiles,
        lambda b: b["crt_m15_live"]["founding"]["threshold_refs"].__setitem__("window", 14),
    )
    problems = _problems_with(monkeypatch, o, mutated)
    assert any("is a VALUE" in p for p in problems), problems


def test_unknown_is_the_permitted_stand_in(monkeypatch, ont, profiles) -> None:
    """`UNKNOWN` must pass where a real id is absent — never fabricate one (§6.6)."""
    o, mutated = _mutate(
        ont, profiles,
        lambda b: b["crt_m15_live"].__setitem__("walk", "UNKNOWN"),
    )
    assert _problems_with(monkeypatch, o, mutated) == []


# ── Grounding: both halves are load-bearing ──────────────────────────────────

@pytest.mark.parametrize("pid", sorted(_SEED_IDS))
def test_every_profile_id_grounds(pid) -> None:
    from governance.semantic_grounding import SemanticGrounder
    hit = SemanticGrounder.load().ground("NOUN", pid)
    assert hit.status == "GROUNDED", hit.to_dict()


@pytest.mark.parametrize("pid", sorted(_SEED_IDS))
def test_grounding_cites_the_declaring_file_not_the_main_ontology(pid) -> None:
    """An SPP-* hit that named market_ontology.yaml would be a false citation."""
    from governance.semantic_grounding import SemanticGrounder
    hit = SemanticGrounder.load().ground("NOUN", pid)
    assert hit.authority.endswith("structure_profiles.yaml"), hit.authority


def test_regex_alone_is_not_enough(monkeypatch) -> None:
    """NEGATIVE CASE: with collection reverted, the id is recognized but UNKNOWN.

    This is the proof that the two halves are independent. SK-0 shipped
    collected-but-not-recognized; reverting collection here reproduces the exact inverse, so
    neither half can silently mask the other going forward.
    """
    from governance import semantic_grounding as sg
    grounder = sg.SemanticGrounder.load()
    # simulate the pre-RC-9 collector: main ontology only
    from governance.semantic_os import ontology_id_sources
    main_only = {k: v for k, v in ontology_id_sources().items()
                 if v == "configs/formulas/market_ontology.yaml"}
    grounder._ontology_ids = set(main_only)
    grounder._ontology_id_sources = main_only

    hit = grounder.ground("NOUN", "SPP-001")
    assert hit.status == "UNKNOWN", (
        "SPP-001 resolved without the sibling collector — the regex half is masking a missing "
        "collector half, which is exactly the failure this test exists to prevent"
    )


def test_ids_from_both_files_coexist() -> None:
    from governance.semantic_os import ontology_id_sources
    src = ontology_id_sources()
    assert src["SP-001"].endswith("market_ontology.yaml")
    assert src["SPP-001"].endswith("structure_profiles.yaml")


# ── Fail-closed, never fail-at-import ────────────────────────────────────────

def test_missing_sibling_is_a_problem_not_an_exception(tmp_path, ont) -> None:
    """The property most likely to regress silently: it only shows when the file is absent.

    `load_ontology` sits on the path of `from features.registry import FORMULA_REGISTRY`,
    which `crt_engine_v2` imports — an import-time raise here would break the trading engine
    over a missing research-declaration file.
    """
    import features.registry as reg
    broken = copy.deepcopy(ont)
    broken["spec_schema"]["semantic_registry"]["external_sections"] = {
        "structural_profiles": "configs/formulas/does_not_exist.yaml"
    }
    problems = reg.validate_structural_profiles(broken)          # must NOT raise
    assert any("does not exist" in p for p in problems), problems
    assert reg.load_structural_profiles(broken) == {}            # must NOT raise


def test_absent_pointer_is_silent(ont) -> None:
    """No pointer declared at all == nothing to validate, not a failure."""
    import features.registry as reg
    no_pointer = copy.deepcopy(ont)
    no_pointer["spec_schema"]["semantic_registry"].pop("external_sections", None)
    assert reg.validate_structural_profiles(no_pointer) == []
    assert reg.load_structural_profiles(no_pointer) == {}
