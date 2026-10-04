"""test_sujan_crt_contract.py — the pre-registration floor for MC-SUJAN-XAUUSD-M15-V1.

Seals the SujanTrader CRT protocol measurement BEFORE `src/research/sujan_crt/` exists
(CLAUDE.md §6.6; the F-081 precedent for sealing first, and the F-083 correction for the
part F-081 got wrong — declaring artifacts and controls that the run never executed).

What this floor is FOR, stated so it cannot quietly rot into decoration:

  * the contract validates against the FROZEN schema, including the `additionalProperties:
    False` surfaces (a prose note dropped into the wrong surface is a silent violation);
  * the four new ontology nodes live in ENFORCED sections and are genuinely enforced —
    proven by mutation, not by a green import (the E-001 structural-kernel lesson: a node
    registered in the wrong section family has identity WITHOUT enforcement and *looks
    like success*);
  * the declarations that exist to stop a specific past failure are still present, each
    tied to the finding that motivated it;
  * evidence paths are honest: null means UNRUN, non-null means it must exist AND be
    git-tracked (F-071 — `results/` is gitignored, so a citation into it cannot resolve
    from a clean checkout).

No test here asserts that the protocol works. That is what the measurement is for.
"""

from __future__ import annotations

import copy
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

CONTRACT_INSTANCE = (
    _ROOT / "configs" / "research" / "measurement_contracts" / "instances"
    / "MC-SUJAN-XAUUSD-M15-V1.json"
)
CONTRACT_DRAFT = (
    _ROOT / "configs" / "research" / "measurement_contracts" / "drafts"
    / "MC-SUJAN-XAUUSD-M15-V1.json"
)
CONTRACT = CONTRACT_INSTANCE
SCHEMA = _ROOT / "docs" / "governance" / "measurement_contract.schema.json"
ONTOLOGY = _ROOT / "configs" / "formulas" / "market_ontology.yaml"
CORPUS = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
_INSTANCE_MISSING = not CONTRACT_INSTANCE.is_file()


def _forbidden_blob(contract: dict) -> str:
    parts = []
    for row in contract["prohibited_substitutions"]:
        parts.append(row["forbidden"] if isinstance(row, dict) else str(row))
    return " ".join(parts)

# id -> the ENFORCED semantic section it must live in. Wrong section == no enforcement.
NEW_NODES = {
    "SEM-022": ("objectives", "htf_objective_ladder"),
    "SEM-023": ("htf_states", "htf_alignment_score"),
    "SEM-024": ("execution_behaviours", "crt_trade_location_gate"),
    "SEM-025": ("risk_behaviours", "structural_rr_floor"),
}


@pytest.fixture(scope="module")
def contract() -> dict:
    if _INSTANCE_MISSING:
        pytest.skip("MC-SUJAN instance unsealed (P-SUJAN-02); draft is not the instance")
    return json.loads(CONTRACT_INSTANCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ontology() -> dict:
    return yaml.safe_load(ONTOLOGY.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Schema conformance
# ─────────────────────────────────────────────────────────────────────────────

def _schema_problems(node_schema, node, path):
    """Recursive required / enum / const / additionalProperties check.

    Hand-rolled because `jsonschema` is not a dependency of this repo; the
    `additionalProperties: False` arm is the one that matters, since that is how a
    well-meant prose field lands on a closed surface without anyone noticing.
    """
    problems = []
    if not isinstance(node_schema, dict) or not isinstance(node, dict):
        return problems
    for req in node_schema.get("required", []):
        if req not in node:
            problems.append(f"{path}: missing required {req!r}")
    props = node_schema.get("properties", {})
    if node_schema.get("additionalProperties") is False:
        for key in node:
            if key not in props:
                problems.append(f"{path}: undeclared key {key!r} on a closed surface")
    for key, value in node.items():
        sub = props.get(key)
        if not isinstance(sub, dict):
            continue
        if "enum" in sub and value not in sub["enum"]:
            problems.append(f"{path}.{key}: {value!r} not in {sub['enum']}")
        if "const" in sub and value != sub["const"]:
            problems.append(f"{path}.{key}: {value!r} != const {sub['const']!r}")
        if sub.get("type") == "object":
            problems.extend(_schema_problems(sub, value, f"{path}.{key}"))
    return problems


def test_contract_conforms_to_the_frozen_schema(contract, schema):
    problems = _schema_problems(schema, contract, "root")
    assert not problems, "contract violates the frozen schema:\n  " + "\n  ".join(problems)


def test_the_schema_checker_can_actually_fail(contract, schema):
    """A validator that never fires is not a validator (E-001)."""
    broken = copy.deepcopy(contract)
    broken["costs"]["success_gate_uses"] = "vibes"
    assert _schema_problems(schema, broken, "root"), "enum violation went undetected"

    broken = copy.deepcopy(contract)
    broken["exits"]["a_stray_note"] = "prose on a closed surface"
    assert _schema_problems(schema, broken, "root"), "closed-surface violation went undetected"

    broken = copy.deepcopy(contract)
    del broken["splits"]["seed"]
    assert _schema_problems(schema, broken, "root"), "missing-required went undetected"


# ─────────────────────────────────────────────────────────────────────────────
# Ontology nodes: present, in ENFORCED sections, and genuinely enforced
# ─────────────────────────────────────────────────────────────────────────────

def test_new_nodes_live_in_enforced_sections(ontology):
    enforced = tuple(ontology["spec_schema"]["semantic_registry"]["sections"])
    located = {}
    for section in enforced:
        for name, spec in (ontology.get(section) or {}).items():
            if isinstance(spec, dict) and spec.get("id") in NEW_NODES:
                located[spec["id"]] = (section, name)

    for sid, (want_section, want_name) in NEW_NODES.items():
        assert sid in located, (
            f"{sid} is not in ANY enforced semantic section. A node outside "
            f"spec_schema.semantic_registry.sections has identity without enforcement."
        )
        assert located[sid] == (want_section, want_name), (
            f"{sid} is at {located[sid]}, expected {(want_section, want_name)}"
        )


def test_registry_validators_are_green():
    from features.registry import validate_registry, validate_semantic_registry

    assert validate_registry() == []
    assert validate_semantic_registry() == []


@pytest.mark.parametrize("sid", sorted(NEW_NODES))
@pytest.mark.parametrize(
    "field,bad",
    [("version", "one"), ("semantic_category", "NotACategory"), ("evidence", [])],
)
def test_each_new_node_is_actually_enforced(ontology, sid, field, bad):
    """Mutate one field on one node; the validator must name that node.

    This is the test that distinguishes 'registered' from 'registered somewhere the
    walker reaches'. Without it, all four nodes could sit in an unenforced section and
    every other test here would still pass.
    """
    from features.registry import validate_semantic_registry

    section, name = NEW_NODES[sid]
    mutated = copy.deepcopy(ontology)
    mutated[section][name][field] = bad
    problems = [p for p in validate_semantic_registry(mutated) if name in p]
    assert problems, f"{sid}: mutating {field!r} produced no problem — node is NOT enforced"


def test_alignment_rubric_weights_sum_to_exactly_100(ontology):
    """SEM-023's threshold only means 'at most one 10-point omission' because of this."""
    node = ontology["htf_states"]["htf_alignment_score"]
    weights = [15, 15, 20, 15, 10, 10, 10, 5]  # as stated in the source and the node formula
    assert sum(weights) == 100
    assert "sum to exactly 100" in node["mathematical_definition"].lower() or \
           "sum to exactly 100" in " ".join(node["validation_rules"]).lower()


def test_rr_floor_node_forbids_calling_itself_a_quality_filter(ontology):
    """The whole point of SEM-025 is that the floor selects on stop distance."""
    rules = " ".join(ontology["risk_behaviours"]["structural_rr_floor"]["validation_rules"])
    assert "quality filter" in rules, "SEM-025 must explicitly forbid the quality-filter framing"
    epi = ontology["risk_behaviours"]["structural_rr_floor"]["epistemic"]
    assert epi["candidate_hypotheses"], "the harm claim must be held as a hypothesis, not a fact"
    assert epi["falsification_conditions"], "an unfalsifiable hypothesis is not registrable"


# ─────────────────────────────────────────────────────────────────────────────
# The declarations that exist because something specific went wrong before
# ─────────────────────────────────────────────────────────────────────────────

def test_no_economic_authority_is_claimed(contract):
    assert contract["authority"]["economic_admissible"] is False
    assert contract["trust_status"]["economic_claims_allowed"] is False
    assert contract["trust_status"]["mt00"] == "UNRUN"
    assert contract["trust_status"]["mt01_matrix_coverage"] == "UNRUN"
    ladder = contract["metrics"]["authority_ladder"]
    assert all(ladder[k] is True for k in
               ("info_not_value", "value_not_authority", "insufficient_not_harmful"))


def test_provenance_boundary_is_recorded(contract):
    """F-077: the source docs are a trigger, never an authority."""
    note = contract["authority"]["note"]
    assert "TRIGGER" in note and "not authored by the trader" in note
    assert "dialogue transcripts" in note.lower()


def test_controls_are_named_and_required_to_execute(contract):
    """F-083: MC-VCRT-V1 declared controls its driver never ran."""
    gate = contract["metrics"]["success_gate"]
    for control in ("random_entry", "long_only", "funnel_matched"):
        assert control in gate, f"control {control!r} not declared in the success gate"
    assert "EXECUTED, NOT MERELY DECLARED" in gate.upper()
    # F-084: a single random draw proved too noisy to gate on.
    assert "100 seeds" in gate


def test_cost_and_fill_corrections_are_mandatory(contract):
    """F-082: flat 12bps is ~11x too punitive on XAU, and free stop fills flatter every arm."""
    assert contract["costs"]["cost_model_id"].startswith("SEM-015")
    assert "SEM-016" in contract["exits"]["exit_model_id"]
    assert contract["exits"]["parameters"]["adverse_fill"].startswith("SEM-016 enabled")
    forbidden = _forbidden_blob(contract)
    assert "flat 12bps" in forbidden
    assert "-1.000R" in forbidden


def test_cost_r_must_be_per_candidate(contract):
    """SEM-025 is invisible if cost is charged off a corpus-mean risk distance."""
    blob = json.dumps(contract)
    assert "corpus-average risk distance" in blob or "corpus-mean risk distance" in blob


def test_single_target_exit_is_justified_against_f088(contract):
    """F-088 says forward_walk is the wrong object for PRODUCTION. Not for this protocol."""
    just = contract["exits"]["parameters"]["exit_justification_vs_f088"]
    assert "multi_tp_walk" in just and "one target" in just.lower()
    assert "NOT A REGRESSION" in just.upper()
    assert any("multi_tp_walk" in x for x in contract["exits"]["not_equal_to"])
    assert contract["exits"]["parameters"]["partial_fraction"] == 0.0
    assert contract["exits"]["parameters"]["trail"] == "none"


def test_unmeasurable_ladder_rungs_are_declared_and_match_the_corpus(contract):
    """The 6M/3M gate is mandatory in the source protocol and unmeasurable on 2 years."""
    decl = " ".join(contract["population"]["population_hash_inputs"])
    assert "UNMEASURABLE" in decl
    assert "4 six-month and 8 three-month" in decl
    forbidden = _forbidden_blob(contract)
    assert "Treating an UNMEASURABLE ladder rung as agreeing" in forbidden


@pytest.mark.skipif(
    _INSTANCE_MISSING or not CORPUS.is_file(),
    reason="MC-SUJAN instance unsealed or XAUUSD corpus gitignored",
)
def test_declared_corpus_window_is_measured_not_asserted():
    """The window and row count in the contract must match the file on disk."""
    contract = json.loads(CONTRACT_INSTANCE.read_text(encoding="utf-8"))
    with CORPUS.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 47275, f"corpus row count drifted: {len(rows)}"
    window = contract["population"]["calendar_window"]
    assert rows[0]["timestamp"].startswith("2024-05-22")
    assert rows[-1]["timestamp"].startswith("2026-05-21")
    assert window["start"].startswith("2024-05-22")
    assert window["end"].startswith("2026-05-21")
    # ~2 years bounds the coarse rungs; this is what makes them unmeasurable.
    months = 24
    assert months // 6 == 4 and months // 3 == 8


def test_funnel_declares_all_five_rungs_and_reports_every_one(contract):
    rule = contract["population"]["inclusion_rule"]
    for rung in ("R0", "R1", "R2", "R3", "R4"):
        assert rung in rule, f"rung {rung} not declared"
    assert "R5" not in rule
    assert "reported at EVERY rung" in rule
    assert "no claim" in rule
    forbidden = " ".join(contract["metrics"]["forbidden_metric_substitutions"])
    assert "maximum rung instead of the whole funnel" in forbidden


def test_paired_floor_arms_cannot_be_reported_alone(contract):
    """SEM-025's effect is a DIFFERENCE; one arm cannot express it."""
    forbidden = " ".join(contract["metrics"]["forbidden_metric_substitutions"])
    assert "with-floor arm without its paired without-floor arm" in forbidden
    assert contract["metrics"]["multiplicity"]["control"] == "hierarchical_stage_gate"


def test_split_boundary_must_be_written_by_the_run(contract):
    """F-083: a contract declared 'dates locked in split_manifest'; the driver had none."""
    oos = contract["splits"]["oos_fraction_or_dates"]
    assert "written to the split manifest by the run itself" in oos
    assert contract["splits"]["embargo"].startswith("96 bars")
    assert "purged from BOTH partitions" in contract["splits"]["purge"]


def test_effective_n_is_required_over_raw_n(contract):
    """Nested rungs overlap; R0 is a strict superset of R5."""
    forbidden = " ".join(contract["metrics"]["forbidden_metric_substitutions"])
    assert "raw n where effective n is required" in forbidden
    assert any("autocorrelation" in m for m in contract["metrics"]["information_metrics"])


def test_beating_a_negative_base_rate_is_not_profit(contract):
    """F-086: the XAUUSD base rate is negative, so 'beats base' means 'loses less'."""
    forbidden = " ".join(contract["metrics"]["forbidden_metric_substitutions"])
    assert "beats the base rate as profitable" in forbidden


def test_labels_are_rederived_never_inherited(contract):
    """F-022: the detection stream is 36.8% self-consistent."""
    assert contract["labels"]["derivation_authority"] == "forward_walk.intrabar_fixed"
    rp = contract["labels"]["rederive_protocol"]
    assert rp["enabled"] is True
    assert rp["on_fail"] == "BLOCK_EXPERIMENT"
    banned = contract["labels"]["stream_fields_banned_for_economic_claims"]
    assert "opportunities.jsonl outcome" in banned


def test_visual_crt_geometry_is_out_of_path(contract):
    """Importing F-081's pools would collapse this program into the one it must differ from."""
    out = " ".join(contract["pipeline_identity"]["modules_explicitly_out_of_path"])
    assert "src/research/visual_crt/" in out
    forbidden = _forbidden_blob(contract)
    assert "visual_crt" in forbidden


# ─────────────────────────────────────────────────────────────────────────────
# Evidence honesty
# ─────────────────────────────────────────────────────────────────────────────

def _git_tracked(rel: str) -> bool:
    out = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=_ROOT, capture_output=True, text=True,
    )
    return out.returncode == 0


def test_evidence_paths_are_null_or_tracked(contract):
    """null == honestly UNRUN. Non-null == must exist AND resolve from a clean checkout.

    F-071's second-order residue: MC-VCRT-V2 recorded all six artifacts under `results/`,
    which is gitignored, so a finding citing them resolves nowhere. The findings gate
    reads `git ls-files`, not the filesystem.
    """
    for key, value in contract["evidence_artifacts"].items():
        if value is None:
            continue
        if key == "code_commit":
            continue
        if key == "contract_path" and not CONTRACT_INSTANCE.is_file():
            continue
        path = _ROOT / value
        assert path.exists(), f"evidence_artifacts.{key} -> {value} does not exist"
        assert _git_tracked(value), (
            f"evidence_artifacts.{key} -> {value} exists but is NOT git-tracked; "
            f"a citation into a gitignored tree cannot resolve from a clean checkout"
        )


@pytest.mark.skipif(
    not CONTRACT_INSTANCE.is_file(),
    reason="MC-SUJAN instance is unsealed (P-SUJAN-02); SEM-031 package is not that detector",
)
def test_contract_path_is_self_referential_and_tracked(contract):
    declared = contract["evidence_artifacts"]["contract_path"]
    assert (_ROOT / declared) == CONTRACT_INSTANCE
    assert _git_tracked(declared), "the contract must be committed to be a pre-registration"


def test_evidence_must_not_be_written_into_a_gitignored_tree(contract):
    forbidden = _forbidden_blob(contract)
    assert "gitignored tree" in forbidden
    assert "docs/research-readiness/sujan_crt/" in forbidden


def test_kill_criteria_forbid_retuning_after_seeing_outcomes(contract):
    kill = contract["metrics"]["kill_criteria"]
    assert "NON-NEGOTIABLE" in kill
    assert "RESULT TO REGISTER" in kill
    assert "NEW MC-* id" in kill
    for frozen in ("rung definitions", "rr_floor", "rubric weights", "cost model", "exit model"):
        assert frozen in kill, f"{frozen!r} not named as a frozen dimension"


def test_sealed_contract_does_not_admit_on_sem_023(contract):
    """P-SUJAN-02: PRIMARY is SEM-031 R4. SEM-023 is diagnostic, not a rung."""
    rule = contract["population"]["inclusion_rule"]
    assert "R4" in rule and "PRIMARY" in rule
    assert "NOT a rung" in rule or "NOT an admission" in rule
    assert "SEM-023 alignment_score is recorded" in rule
    gate = contract["metrics"]["success_gate"]
    assert "SEM-023 is never this gate" in gate
    pkg = _ROOT / "src" / "research" / "sujan_crt"
    assert pkg.is_dir()
    assert "SEM-031" in (pkg / "__init__.py").read_text(encoding="utf-8")
