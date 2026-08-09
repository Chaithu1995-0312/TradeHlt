"""Contract + mutation floor for the Semantic OS registry (CN / BD / JN / CT).

Two halves, and the second is the one that matters:

  1. POSITIVE — the live hand-authored registry is clean, deterministic, and covers the spine.
  2. NEGATIVE (mutation) — for every violation class, a deliberately broken copy MUST be caught,
     asserting the SPECIFIC message substring rather than merely "errors is non-empty". A validator
     that cannot be shown to fail is not enforcement (Program E-001F, `tests/governance/
     test_epistemic_invariants.py`).

Mutation pattern mirrors `tests/test_semantic_registry.py` — deepcopy the live records, break one
thing, assert the matching validator fires.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from governance.semantic_os import (  # noqa: E402
    AUTHORITY,
    SPINE_FILES,
    SemanticOSRegistry,
    _FORBIDDEN_HAND_FIELDS,
    book_toc_chapters,
    closure_surface_ids,
    foreign_id_namespace,
    graph_dot_modules,
    miar_stages,
    path_to_dotted,
    resolve_members,
    validate_record,
)

_SEED = _REPO / "scripts" / "governance" / "seed_semantic_os.py"
_SOURCE_DIR = _REPO / "docs" / "governance" / "semantic_os"
_OUT_DIR = _REPO / "data" / "semantic_os"


# ── helpers ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def live() -> SemanticOSRegistry:
    return SemanticOSRegistry.load(_SOURCE_DIR)


def _clone(
    reg: SemanticOSRegistry,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    return (
        copy.deepcopy(sorted(reg.concepts.values(), key=lambda r: r["id"])),
        copy.deepcopy(sorted(reg.boundaries.values(), key=lambda r: r["id"])),
        copy.deepcopy(sorted(reg.journeys.values(), key=lambda r: r["id"])),
        copy.deepcopy(sorted(reg.contracts.values(), key=lambda r: r["id"])),
    )


def _rebuild(concepts, boundaries, journeys, contracts=None) -> SemanticOSRegistry:
    return SemanticOSRegistry(concepts, boundaries, journeys, contracts or [])


def _details(errors) -> str:
    return " | ".join(str(e) for e in errors)


def _assert_caught(errors, needle: str) -> None:
    assert errors, f"expected a validation error containing {needle!r}, got none"
    assert needle in _details(errors), f"expected {needle!r} in: {_details(errors)}"


# ── positive / contract ─────────────────────────────────────────────────────────────────────

def test_live_registry_is_clean(live):
    errors = live.validate_all()
    assert errors == [], f"live Semantic OS registry has errors: {_details(errors)}"


def test_live_registry_is_clean_in_strict_mode(live):
    errors = live.validate_all(strict=True)
    assert errors == [], f"live registry fails --strict: {_details(errors)}"


def test_registry_is_non_empty(live):
    # Anti-hollowing: a registry that validates because it contains nothing is not enforcement.
    assert live.concepts, "no concepts authored"
    assert live.boundaries, "no boundaries authored"
    assert live.journeys, "no journeys authored"
    assert live.contracts, "no contracts authored (PR-2 CT-*)"


def test_every_concept_has_nonempty_why_it_exists(live):
    for cid, concept in live.concepts.items():
        assert concept.get("why_it_exists", "").strip(), f"{cid}: empty why_it_exists"
        assert concept.get("why_this_design", "").strip(), f"{cid}: empty why_this_design"
        assert concept.get("invariants"), f"{cid}: declares no invariants"


def test_every_boundary_protects_a_named_invariant(live):
    for bid, boundary in live.boundaries.items():
        assert boundary.get("invariant_protected", "").strip(), f"{bid}: empty invariant_protected"
        assert boundary.get("invariant_violation_symptom", "").strip(), f"{bid}: empty symptom"


def test_spine_files_are_fully_claimed(live):
    claimed: set[str] = set()
    for boundary in live.boundaries.values():
        claimed |= set(
            resolve_members(boundary.get("members") or [], boundary.get("members_exclude") or [], _REPO)
        )
    missing = [f for f in SPINE_FILES if f not in claimed]
    assert not missing, f"spine modules unclaimed by any boundary: {missing}"


def test_spine_files_all_exist_on_disk():
    missing = [f for f in SPINE_FILES if not (_REPO / f).is_file()]
    assert not missing, f"SPINE_FILES references non-existent paths: {missing}"


def test_authority_is_advisory_everywhere(live):
    for record in live.records:
        assert record.get("authority") == AUTHORITY, (
            f"{record.get('id')}: authority must be {AUTHORITY!r} — this layer never earns "
            f"production authority (CLAUDE.md §6.5)"
        )


def test_external_authorities_are_readable():
    # If these degrade to empty the FK validators silently weaken, so pin them explicitly.
    assert len(miar_stages()) == 7, "MIAR stages unreadable or changed shape"
    assert len(closure_surface_ids()) >= 9, "closure authority index unreadable"
    assert book_toc_chapters(), "book README TOC unreadable"
    foreign = foreign_id_namespace()
    for key in ("ontology", "findings", "module_attribution", "script_registry"):
        assert foreign[key], f"foreign namespace {key!r} is empty — FK checks would be vacuous"


def test_seed_runs_and_is_byte_identical_on_rerun():
    def _run():
        proc = subprocess.run(
            [sys.executable, str(_SEED)], cwd=_REPO, capture_output=True, text=True
        )
        assert proc.returncode == 0, f"seed failed: {proc.stdout}\n{proc.stderr}"
        return {p.name: p.read_bytes() for p in sorted(_OUT_DIR.glob("*.jsonl"))}

    first = _run()
    second = _run()
    assert first, "seed produced no JSONL output"
    assert first == second, "seed is not byte-identical across reruns (non-determinism)"


def test_seeded_projection_round_trips(live):
    subprocess.run([sys.executable, str(_SEED)], cwd=_REPO, capture_output=True, text=True, check=True)
    rows = [
        json.loads(line)
        for line in (_OUT_DIR / "concepts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {r["id"] for r in rows} == set(live.concepts)
    for row in rows:
        assert row["authority"] == AUTHORITY
        assert row["created"] == row["last_validated"], "seed timestamps must be pinned, not live"


def test_journey_steps_reference_declared_failure_modes(live):
    for journey, step in live.steps():
        concept = live.concepts[step["concept"]]
        declared = {m["mode"] for m in concept.get("failure_modes") or []}
        assert step["failure_mode"] in declared, (
            f"{step['step_id']}: failure_mode {step['failure_mode']!r} not declared by "
            f"{concept['id']} — journeys may only reference modes their concept owns"
        )


def test_no_derived_field_is_hand_authored(live):
    for record in live.records:
        leaked = sorted(set(record) & _FORBIDDEN_HAND_FIELDS)
        assert not leaked, f"{record['id']}: hand-authored derived field(s) {leaked}"


def test_path_to_dotted_matches_gen_code_map_convention():
    assert path_to_dotted("src/core/engine_runner.py") == "core.engine_runner"
    assert path_to_dotted("src/agent/__init__.py") == "agent"
    assert path_to_dotted("scripts/governance/seed_semantic_os.py") is None
    assert path_to_dotted("tests/test_semantic_os.py") is None


# ── negative: schema (validator 1) ──────────────────────────────────────────────────────────

def test_missing_required_field_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    del concepts[0]["why_it_exists"]
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "missing fields")


def test_authority_must_be_advisory(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["authority"] = "production"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "authority must be the pinned literal")


def test_bad_status_enum_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["status"] = "MAYBE"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "status")


def test_malformed_concept_id_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["id"] = "CN-1"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "must match")


def test_summary_50_over_cap_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["summary_50"] = "x" * 400
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "summary_50")


def test_concept_without_invariants_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["invariants"] = []
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "invariants must declare")


def test_duplicate_failure_mode_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    modes = concepts[0]["failure_modes"]
    modes.append(dict(modes[0]))
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "duplicate failure_mode")


def test_alternative_without_reason_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["alternatives_rejected"] = [{"alternative": "something", "why_rejected": ""}]
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "alternatives_rejected")


def test_bad_assumption_status_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["assumptions"][0]["status"] = "PROBABLY"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_schema(), "assumption status")


def test_empty_invariant_protected_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["invariant_protected"] = "   "
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_schema(), "invariant_protected")


def test_boundary_without_members_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["members"] = []
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_schema(), "members must declare")


def test_bad_authority_layer_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["authority_layer"] = "WHEN"
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_schema(), "authority_layer")


def test_bad_on_failure_enum_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["steps"][0]["on_failure"] = "PANIC"
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_schema(), "on_failure")


def test_step_id_not_namespaced_under_journey_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["steps"][0]["step_id"] = "JN-999.S01"
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_schema(), "namespaced under its journey")


def test_bad_feeder_kind_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["async_feeders"][0]["kind"] = "MAGIC"
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_schema(), "async_feeder kind")


def test_derived_field_in_hand_source_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["imports"] = ["features.feature_schema"]
    reg = _rebuild(concepts, b, j, contracts)
    _assert_caught(reg.validate_no_derived_in_source(), "derived field(s) hand-authored")
    _assert_caught(reg.validate_schema(), "may not be hand-authored")


# ── PR-2: first-class CT-* contracts ────────────────────────────────────────────────────────

def test_live_contracts_nonempty_and_advisory(live):
    assert live.contracts
    for ctid, contract in live.contracts.items():
        assert contract.get("kind") == "contract"
        assert contract.get("authority") == AUTHORITY
        assert contract.get("guarantees"), f"{ctid}: empty guarantees"
        assert contract.get("governs_concepts") or contract.get("governs_boundaries")


def test_boundary_contract_ids_resolve(live):
    for bid, boundary in live.boundaries.items():
        for ctid in boundary.get("contract_ids") or []:
            assert ctid in live.contracts, f"{bid} references missing {ctid}"


def test_contract_missing_guarantees_is_caught(live):
    c, b, j, contracts = _clone(live)
    contracts[0]["guarantees"] = []
    _assert_caught(_rebuild(c, b, j, contracts).validate_schema(), "guarantees must declare")


def test_contract_bad_kind_enum_is_caught(live):
    c, b, j, contracts = _clone(live)
    contracts[0]["contract_kind"] = "MAGIC"
    _assert_caught(_rebuild(c, b, j, contracts).validate_schema(), "contract_kind")


def test_contract_unknown_concept_fk_is_caught(live):
    c, b, j, contracts = _clone(live)
    contracts[0]["governs_concepts"] = ["CN-404"]
    _assert_caught(_rebuild(c, b, j, contracts).validate_fk_resolution(), "unknown governs_concepts")


def test_boundary_unknown_contract_id_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["contract_ids"] = ["CT-404"]
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_fk_resolution(), "unknown contract_ids")


def test_malformed_contract_id_is_caught(live):
    c, b, j, contracts = _clone(live)
    contracts[0]["id"] = "CT-1"
    _assert_caught(_rebuild(c, b, j, contracts).validate_schema(), "must match")


# ── negative: global id uniqueness (validator 2) ─────────────────────────────────────────────

def test_duplicate_concept_id_is_caught(live, tmp_path):
    """The in-memory registry is dict-keyed by id (so a duplicate silently collapses); the write
    path is where a duplicated id must be refused."""
    concepts, _, _, _ = _clone(live)
    twin = copy.deepcopy(concepts[0])
    with pytest.raises(ValueError, match="duplicate id"):
        SemanticOSRegistry.dump(tmp_path / "dup.jsonl", [dict(concepts[0]), dict(twin)])


@pytest.mark.parametrize(
    "foreign_id,source",
    [("FM-002", "ontology"), ("F-001", "findings"),
     ("MOD-0001", "module_attribution"), ("SCR-001", "script_registry")],
)
def test_duplicate_id_with_foreign_namespace_is_caught(live, foreign_id, source):
    """Ids must be globally unique. Called directly: the schema regex is the first line of
    defense (a concept id cannot literally be FM-002), so this validator is the backstop that
    keeps the guarantee true if a namespace is ever widened."""
    known = foreign_id_namespace()[source]
    if foreign_id not in known:
        pytest.skip(f"{foreign_id} not present in the live {source} namespace")
    concepts, b, j, contracts = _clone(live)
    concepts[0]["id"] = foreign_id
    _assert_caught(
        _rebuild(concepts, b, j, contracts).validate_unique_ids_global(),
        f"collides with the {source} namespace",
    )


def test_step_id_colliding_with_a_record_id_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    concepts, _, _, _ = _clone(live)
    journeys[0]["steps"][0]["step_id"] = concepts[0]["id"]
    _assert_caught(_rebuild(concepts, b, journeys, contracts).validate_unique_ids_global(), "collides")


# ── negative: orphans (validator 3) ─────────────────────────────────────────────────────────

def test_orphan_concept_is_caught(live):
    concepts, boundaries, journeys, contracts = _clone(live)
    orphan = copy.deepcopy(concepts[0])
    orphan["id"] = "CN-900"
    orphan["name"] = "Orphaned Probe Concept"
    orphan["aliases"] = []
    orphan["orphan_justification"] = None
    _assert_caught(
        _rebuild(concepts + [orphan], boundaries, journeys, contracts).validate_no_orphan_concepts(),
        "no boundary references this concept",
    )


def test_orphan_justification_suppresses_the_error(live):
    concepts, boundaries, journeys, contracts = _clone(live)
    orphan = copy.deepcopy(concepts[0])
    orphan["id"] = "CN-901"
    orphan["name"] = "Justified Probe Concept"
    orphan["aliases"] = []
    orphan["orphan_justification"] = "Deliberately unbound pending Phase 3 boundary authoring."
    errors = _rebuild(concepts + [orphan], boundaries, journeys, contracts).validate_no_orphan_concepts()
    assert "CN-901" not in _details(errors), f"justified orphan still flagged: {_details(errors)}"


def test_boundary_resolving_to_zero_files_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["members"] = ["src/definitely/not/here/**/*.py"]
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_no_orphan_concepts(), "zero member files")


def test_journey_with_one_step_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["steps"] = journeys[0]["steps"][:1]
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_no_orphan_concepts(), "fewer than 2 steps")


# ── negative: cycles (validator 4) ──────────────────────────────────────────────────────────

def test_self_consuming_boundary_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["consumers"] = [boundaries[0]["id"]]
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_no_cyclic_ownership(), "itself as a consumer")


def test_consumer_cycle_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    assert len(boundaries) >= 2, "need two boundaries to build a cycle"
    boundaries[0]["consumers"] = [boundaries[1]["id"]]
    boundaries[1]["consumers"] = [boundaries[0]["id"]]
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_no_cyclic_ownership(), "consumer cycle")


def test_membership_is_not_treated_as_a_cycle(live):
    """CN.owner_boundary == BD and CN in BD.concepts is REQUIRED by validator 5 — it is a
    symmetric declaration, not a dependency, and must never be reported as a cycle."""
    assert live.validate_no_cyclic_ownership() == []


# ── negative: bidirectional consistency (validator 5) ───────────────────────────────────────

def test_bidirectional_mismatch_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["concepts"] = []
    _assert_caught(
        _rebuild(c, boundaries, j, contracts).validate_bidirectional_consistency(),
        "does not list",
    )


# ── negative: foreign keys (validator 6) ────────────────────────────────────────────────────

def test_unknown_miar_stage_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["miar_stage"] = "vibes"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "unknown miar_stage")


def test_unknown_closure_surface_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["closure_surface_id"] = "NOT_A_SURFACE"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "unknown closure_surface_id")


def test_unknown_ontology_id_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["ontology_ids"] = ["FM-999"]
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "unknown ontology id")


def test_unknown_finding_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["research_findings"] = ["F-999"]
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "unknown finding")


def test_unknown_finding_in_assumption_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["assumptions"][0]["falsified_by"] = "F-998"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "unknown finding in assumption")


def test_unknown_change_class_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["change_classes"] = ["VIBES_CHANGE"]
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_fk_resolution(), "unknown change class")


def test_missing_book_chapter_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["book_chapter"] = "docs/book/99-nonexistent.md"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "book_chapter does not exist")


def test_book_chapter_not_in_toc_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    # A real file that is NOT linked from the book README TOC.
    concepts[0]["book_chapter"] = "docs/knowledge-map.md"
    assert (_REPO / "docs" / "knowledge-map.md").is_file(), "fixture path vanished"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "not linked from")


def test_missing_canonical_source_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["canonical_source"] = "src/nope/missing.py"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "canonical_source path does not exist")


def test_unknown_boundary_reference_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    concepts[0]["owner_boundary"] = "BD-777"
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_fk_resolution(), "unknown boundary")


# ── negative: members (validator 7) ─────────────────────────────────────────────────────────

def test_boundary_glob_matching_nothing_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["members"].append("src/**/definitely_not_a_module_xyz.py")
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_boundary_members(), "matches no file")


def test_file_claimed_by_two_boundaries_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    assert len(boundaries) >= 2
    shared = boundaries[0]["members"][0]
    boundaries[1]["members"] = list(boundaries[1]["members"]) + [shared]
    _assert_caught(
        _rebuild(c, boundaries, j, contracts).validate_boundary_members(), "single-ownership violated"
    )


# ── negative: spine coverage (validator 8) ──────────────────────────────────────────────────

def test_spine_coverage_floor_cannot_regress(live):
    c, boundaries, j, contracts = _clone(live)
    # Drop the risk gate from whichever boundary claims it.
    for boundary in boundaries:
        boundary["members"] = [
            m for m in boundary["members"] if m != "src/core/ultron_risk_gate.py"
        ]
    _assert_caught(
        _rebuild(c, boundaries, j, contracts).validate_spine_coverage(),
        "spine module not claimed by any boundary",
    )


# ── negative: journey DAG (validators 9 + 10) ───────────────────────────────────────────────

def test_journey_order_gap_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["steps"][1]["order"] = 5
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_journey_dag(), "order must be contiguous")


def test_journey_backward_edge_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    steps = journeys[0]["steps"]
    steps[1]["next"] = [steps[0]["step_id"]]
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_journey_dag(), "not strictly forward")


def test_journey_cycle_is_caught(live):
    """A backward edge IS the cycle in a strictly-ordered DAG — both guards must fire."""
    c, b, journeys, contracts = _clone(live)
    steps = journeys[0]["steps"]
    steps[1]["next"] = [steps[0]["step_id"]]
    errors = _rebuild(c, b, journeys, contracts).validate_journey_dag()
    assert errors, "backward edge produced no error"
    assert "not strictly forward" in _details(errors)


def test_unreachable_journey_step_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["steps"][0]["next"] = []
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_journey_dag(), "unreachable from order 1")


def test_dangling_next_target_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["steps"][0]["next"] = ["JN-001.S99"]
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_journey_dag(), "unknown step")


def test_no_terminal_step_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    steps = journeys[0]["steps"]
    steps[-1]["next"] = [steps[0]["step_id"]]
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_journey_dag(), "no terminal step")


def test_empty_terminal_outcomes_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["terminal_outcomes"] = []
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_journey_dag(), "terminal_outcomes is empty")


def test_async_feeder_dangling_step_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["async_feeders"][0]["joins_at_step"] = "JN-001.S42"
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_journey_dag(), "joins unknown step")


def test_step_failure_mode_not_declared_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["steps"][0]["failure_mode"] = "INVENTED_MODE"
    _assert_caught(
        _rebuild(c, b, journeys, contracts).validate_journey_step_fks(), "is not declared in"
    )


def test_step_boundary_not_owned_by_concept_is_caught(live):
    c, boundaries, journeys, contracts = _clone(live)
    step = journeys[0]["steps"][0]
    concept = next(x for x in c if x["id"] == step["concept"])
    allowed = {concept.get("owner_boundary")} | set(concept.get("related_boundaries") or [])
    other = next(b["id"] for b in boundaries if b["id"] not in allowed)
    step["boundary"] = other
    _assert_caught(
        _rebuild(c, boundaries, journeys, contracts).validate_journey_step_fks(),
        "neither owner_boundary nor a related_boundary",
    )


def test_step_unknown_concept_is_caught(live):
    c, b, journeys, contracts = _clone(live)
    journeys[0]["steps"][0]["concept"] = "CN-404"
    _assert_caught(_rebuild(c, b, journeys, contracts).validate_journey_step_fks(), "unknown concept")


# ── negative: evidence (validator 11) ───────────────────────────────────────────────────────

def test_evidence_path_missing_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["evidence"][0]["path"] = "src/gone/missing.py"
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_evidence(), "path not found")


def test_evidence_symbol_absent_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["evidence"][0]["symbol"] = "ThisSymbolDoesNotExistAnywhere"
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_evidence(), "absent from")


def test_owner_symbol_drift_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["owner_symbol"] = "NotARealClassName"
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_evidence(), "owner_symbol")


def test_evidence_line_drift_beyond_window_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    ev = next(e for e in boundaries[0]["evidence"] if e.get("type") == "code" and e.get("line"))
    ev["line"] = ev["line"] + 5000
    _assert_caught(_rebuild(c, boundaries, j, contracts).validate_evidence(), "drifted")


# ── negative: alias uniqueness (validator 12) ───────────────────────────────────────────────

def test_ambiguous_alias_is_caught(live):
    concepts, b, j, contracts = _clone(live)
    assert len(concepts) >= 2
    concepts[1]["aliases"] = list(concepts[1]["aliases"]) + [concepts[0]["name"]]
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_alias_uniqueness(), "AMBIGUOUS")


def test_alias_collision_is_case_insensitive(live):
    concepts, b, j, contracts = _clone(live)
    concepts[1]["aliases"] = list(concepts[1]["aliases"]) + [concepts[0]["name"].upper()]
    _assert_caught(_rebuild(concepts, b, j, contracts).validate_alias_uniqueness(), "AMBIGUOUS")


# ── negative: object reachability (validator 13) ────────────────────────────────────────────

def test_referenced_object_missing_from_disk_is_caught(live):
    c, boundaries, j, contracts = _clone(live)
    boundaries[0]["members"] = list(boundaries[0]["members"]) + ["src/not/a/real/file.py"]
    _assert_caught(
        _rebuild(c, boundaries, j, contracts).validate_referenced_objects_reachable(),
        "member path does not exist",
    )


def test_graph_staleness_is_reported_but_not_a_default_gate(live, monkeypatch):
    """graph.dot is a GENERATED cross-check this layer does not own. Staleness must not turn the
    registry red by default — it surfaces under --strict only.

    After ``gen_code_map.py`` the map is nearly exhaustive, so the fixture *simulates* staleness
    by hiding one claimed module from ``graph_dot_modules()`` rather than depending on a residual
    unmapped path (``src/__init__.py`` is not a graph node name and is filtered out).
    """
    c, boundaries, j, contracts = _clone(live)
    reg = _rebuild(c, boundaries, j, contracts)
    real_nodes = graph_dot_modules()
    assert real_nodes, "graph.dot must load for this test"
    claimed: list[str] = []
    for boundary in reg.boundaries.values():
        claimed.extend(
            resolve_members(
                boundary.get("members") or [],
                boundary.get("members_exclude") or [],
                _REPO,
            )
        )
    victim = next(
        (p for p in claimed if path_to_dotted(p) is not None and path_to_dotted(p) in real_nodes),
        None,
    )
    assert victim is not None, "need at least one claimed src module present in graph.dot"
    reduced = set(real_nodes) - {path_to_dotted(victim)}
    monkeypatch.setattr(
        "governance.semantic_os.graph_dot_modules",
        lambda path=None: reduced,  # noqa: ARG005 — match call signature
    )
    assert reg.validate_referenced_objects_reachable() == [], "staleness must not gate by default"
    _assert_caught(reg.validate_referenced_objects_reachable(strict=True), "stale_graph")


# ── dump / schema io ────────────────────────────────────────────────────────────────────────

def test_dump_rejects_an_invalid_record(tmp_path):
    with pytest.raises(ValueError):
        SemanticOSRegistry.dump(tmp_path / "x.jsonl", [{"id": "CN-001", "kind": "concept"}])


def test_validate_record_rejects_unknown_kind():
    with pytest.raises(ValueError, match="kind"):
        validate_record({"id": "CN-001", "kind": "widget"})
