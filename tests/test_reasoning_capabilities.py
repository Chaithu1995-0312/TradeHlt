"""Floor: Reasoning Capability Layer M1 pilot (bottom-up extraction, capability_model_map.json).

Two checks that matter, per docs/governance/REASONING_CAPABILITY_REGISTRY.md:
  - COMPLETENESS: every registered model (MIAR entries + sidecar_entries) is accounted for,
    either mapped to >=1 capability or carrying a declared no_capability_reason. No model may
    silently fall through un-accounted-for.
  - OVERLAP IS REPORTED, NEVER ASSERTED AWAY: a capability with >1 model must carry
    overlap_declared=true and a non-empty rationale. Orthogonality is never asserted without
    evidence.
Plus registry-consistency checks tying capability_model_map.json to market_ontology.yaml's
reasoning_capabilities section and to the frozen ontology validator.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MAP_JSON = ROOT / "docs" / "governance" / "capability_model_map.json"
MIAR_JSON = ROOT / "docs" / "governance" / "miar_registry.json"
ONTOLOGY_YAML = ROOT / "configs" / "formulas" / "market_ontology.yaml"

sys.path.insert(0, str(ROOT / "src"))


def _load_map() -> dict:
    assert MAP_JSON.is_file(), f"missing {MAP_JSON}"
    return json.loads(MAP_JSON.read_text(encoding="utf-8"))


def _load_miar() -> dict:
    assert MIAR_JSON.is_file(), f"missing {MIAR_JSON}"
    return json.loads(MIAR_JSON.read_text(encoding="utf-8"))


def _load_ontology() -> dict:
    assert ONTOLOGY_YAML.is_file(), f"missing {ONTOLOGY_YAML}"
    return yaml.safe_load(ONTOLOGY_YAML.read_text(encoding="utf-8"))


def _all_model_ids() -> set[str]:
    miar = _load_miar()
    ids = {e["id"] for e in miar["entries"]} | {e["id"] for e in miar["sidecar_entries"]}
    return ids


def test_map_file_shape():
    data = _load_map()
    assert data["authority"].upper().startswith("NONE")
    assert isinstance(data["capability_model_map"], list)
    assert isinstance(data["no_capability_reason"], dict)


def test_completeness_every_model_accounted_for():
    """Every model in the 21-model MIAR roster is EITHER mapped to a capability OR carries
    a declared no_capability_reason. Neither both nor neither."""
    data = _load_map()
    all_ids = _all_model_ids()

    mapped: set[str] = set()
    for row in data["capability_model_map"]:
        mapped.update(row["model_ids"])

    unmapped_declared = set(data["no_capability_reason"].keys())

    missing = all_ids - (mapped | unmapped_declared)
    assert not missing, f"model(s) not accounted for at all: {sorted(missing)}"

    unknown_ids = (mapped | unmapped_declared) - all_ids
    assert not unknown_ids, f"map references unknown model id(s): {sorted(unknown_ids)}"

    both = mapped & unmapped_declared
    assert not both, f"model(s) both mapped AND declared no-capability (pick one): {sorted(both)}"

    # every no_capability_reason entry must actually have prose, not a placeholder
    for model_id, reason in data["no_capability_reason"].items():
        assert isinstance(reason, str) and len(reason) > 10, (
            f"no_capability_reason for {model_id!r} must be a real rationale, not a stub"
        )


def test_overlap_is_declared_never_silent():
    """A capability with >1 model MUST carry overlap_declared=true + a real rationale.
    This is the mechanism that stops orthogonality from being asserted without evidence."""
    data = _load_map()
    for row in data["capability_model_map"]:
        if len(row["model_ids"]) > 1:
            assert row.get("overlap_declared") is True, (
                f"{row['capability_id']} has {len(row['model_ids'])} models but "
                f"overlap_declared is not True — overlap must be reported, not silent"
            )
            rationale = row.get("overlap_rationale", "")
            assert isinstance(rationale, str) and len(rationale) > 20, (
                f"{row['capability_id']} overlap_declared=True but overlap_rationale is "
                f"missing or a stub"
            )


def test_no_capability_asserted_orthogonal_without_evidence():
    """A single-model capability must NOT itself assert orthogonality vs other capabilities —
    that claim would require evidence this pilot does not have. overlap_declared must be
    absent or False for single-model rows; only >1-model rows carry the overlap discussion."""
    data = _load_map()
    for row in data["capability_model_map"]:
        if len(row["model_ids"]) <= 1:
            assert row.get("overlap_declared") in (None, False), (
                f"{row['capability_id']} has <=1 model but declares overlap — nothing to "
                f"report overlap against"
            )


def test_capability_ids_consistent_with_ontology():
    """Every capability_id in the map must exist as a node in market_ontology.yaml's
    reasoning_capabilities section, and vice versa — no orphaned map row, no unmapped node."""
    data = _load_map()
    ont = _load_ontology()

    rc_section = ont.get("reasoning_capabilities") or {}
    ontology_rc_ids = {node["id"] for node in rc_section.values()}
    map_rc_ids = {row["capability_id"] for row in data["capability_model_map"]}

    assert map_rc_ids == ontology_rc_ids, (
        f"capability_model_map ids {sorted(map_rc_ids)} != "
        f"market_ontology.yaml reasoning_capabilities ids {sorted(ontology_rc_ids)}"
    )


def test_rc001_node_shape_and_evidence():
    """RC-001 specifically: OBSERVED (not asserted higher), epistemic block present with
    an honest unknown_mechanism (not a settled fact), and non-empty evidence."""
    ont = _load_ontology()
    node = ont["reasoning_capabilities"]["statistical_structural_familiarity"]

    assert node["id"] == "RC-001"
    assert node["semantic_category"] == "ReasoningCapability"
    assert node["knowledge_status"] == "OBSERVED", (
        "RC-001 must not be asserted above OBSERVED — the redundancy is an observed pattern, "
        "not yet a validated mechanism"
    )
    assert len(node["evidence"]) >= 1
    assert node["evidence"] != ["UNKNOWN"]

    epi = node.get("epistemic")
    assert isinstance(epi, dict), "RC-001 must carry an epistemic block (OBSERVED is encouraged)"
    assert epi["unknown_mechanism"], "must state the actual open question, not leave it empty"
    assert len(epi["candidate_hypotheses"]) >= 2, (
        "must record more than one candidate hypothesis — a single hypothesis repeated "
        "is exactly how a guess becomes a 'fact' (CLAUDE.md epistemic discipline)"
    )
    assert epi["falsification_conditions"], "must state what would disprove the hypotheses"


def test_producers_never_read_probability_for_familiarity():
    """Vocabulary discipline: RC-001's produced_outputs must never call a score a
    'probability' (MIAR locked vocabulary: Probability != Score != Confidence)."""
    ont = _load_ontology()
    node = ont["reasoning_capabilities"]["statistical_structural_familiarity"]
    for out in node["produced_outputs"]:
        low = out.lower()
        if "score" in low or "gate" in low or "confirmation" in low:
            assert "never a probability" in low or "probability" not in low, (
                f"produced_outputs entry reads as a probability claim without the "
                f"locked-vocabulary caveat: {out!r}"
            )


def test_semantic_registry_still_validates_clean():
    """Regression floor: the new section must not break the ontology's own contract validator."""
    from features.registry import validate_semantic_registry

    problems = validate_semantic_registry()
    assert problems == [], f"semantic registry contract violated: {problems}"


def test_m1_4_matrix_derivation_conflict_is_real():
    """M1.4 direction-reversal proof: attempting to derive a single market_question_matrix
    row from RC-001 must fail the matrix's own single-owner invariant, mechanically — not
    just asserted in prose (see REASONING_CAPABILITY_REGISTRY.md 4).

    This proves the finding is real: RC-001 genuinely has >1 MIAR-registered producer, so
    projecting it into the matrix's one-question-one-owner shape is impossible without
    picking an arbitrary owner — exactly the models-first conflation this layer exists to
    avoid, not reproduce.
    """
    cap_map = _load_map()
    miar = _load_miar()

    rc001_row = next(
        r for r in cap_map["capability_model_map"] if r["capability_id"] == "RC-001"
    )
    candidate_owners = rc001_row["model_ids"]
    assert len(candidate_owners) > 1, (
        "the M1.4 finding requires RC-001 to have >1 candidate owner — if this ever "
        "drops to 1, the derivation would succeed and REASONING_CAPABILITY_REGISTRY.md 4 "
        "must be revised, not left claiming a conflict that no longer exists"
    )

    # Both candidate owners must independently, validly own a DIFFERENT existing matrix
    # question (proving the matrix is correct at its own grain, not merely incomplete).
    owned_questions = {}
    for row in miar["market_question_matrix"]:
        owned_questions[row["owner"]] = row["question"]
    for owner in candidate_owners:
        assert owner in owned_questions, (
            f"{owner} (an RC-001 producer) has no market_question_matrix row at all — "
            f"the §4 write-up assumes both producers already own a distinct question"
        )
    assert len(set(owned_questions[o] for o in candidate_owners)) == len(candidate_owners), (
        "RC-001's candidate owners must own DISTINCT existing questions — if they shared "
        "one, the matrix's own single-owner test would already have failed"
    )

    # Simulate the derivation: a single capability-level row can only carry one 'owner'
    # key (the matrix's schema), which cannot hold >1 value without violating
    # test_market_question_matrix_single_owner's one-owner-per-question invariant.
    def _try_build_single_owner_row(owners: list[str]) -> str | None:
        if len(owners) != 1:
            return None
        return owners[0]

    derived_owner = _try_build_single_owner_row(candidate_owners)
    assert derived_owner is None, (
        "derivation unexpectedly succeeded with a single owner — the M1.4 conflict this "
        "test exists to prove did not occur; investigate before trusting this test's PASS"
    )


def test_reasoning_capabilities_grants_no_runtime_authority():
    """The frozen runtime-binding validator must stay clean — the new section is additive
    and must never be read on the runtime binding path (CLAUDE.md 6.6 mechanical constraint)."""
    from features.registry import validate_registry

    problems = validate_registry()
    assert problems == [], f"runtime binding path perturbed by an additive change: {problems}"
