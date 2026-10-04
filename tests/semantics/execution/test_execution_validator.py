"""Failing mutations for the slice-3 registry checks (V-15 ext, V-16 ext, V-17, V-18)."""

from __future__ import annotations

import copy

from semantics.registry import (
    load_concept_contracts,
    validate_all,
    validate_execution_never_moves_a_thesis,
    validate_execution_source,
    validate_exit_reasons,
    validate_role_status_untouched,
    validate_settled_decisions,
)


def _concepts():
    return copy.deepcopy(load_concept_contracts()["concepts"])


def test_shipped_slice_3_is_clean():
    concepts = _concepts()
    assert validate_all() == []
    assert validate_execution_never_moves_a_thesis() == []
    assert validate_exit_reasons(concepts) == []
    assert validate_settled_decisions(concepts) == []
    assert validate_role_status_untouched() == []


def test_v15_ext_a_missing_execution_package_is_an_error(tmp_path):
    (tmp_path / "src" / "semantics" / "trading").mkdir(parents=True)
    problems = validate_role_status_untouched(tmp_path)
    assert any("src/semantics/execution: package missing" in item for item in problems)


def test_v16_ext_a_settled_decision_needs_a_resolution():
    concepts = _concepts()
    for item in concepts["TRS-03"]["divergences"]:
        if "decided_in" in item:
            item["resolution"] = "  "
    assert any("no resolution" in item for item in validate_settled_decisions(concepts))


def test_v17_flags_thesis_transitions_attribute_writes_and_replace():
    assert any("mark_failed" in p for p in validate_execution_source("mark_failed(t, b)\n", name="x.py"))
    assert any("attribute assignment .price" in p for p in validate_execution_source("fill.price = 1\n", name="x.py"))
    assert any("replace(" in p for p in validate_execution_source("dataclasses.replace(t, status=1)\n", name="x.py"))
    assert validate_execution_source("x = breach(inv, bar, d)\n", name="x.py") == []


def test_v18_exit_reasons_must_match_the_position_enum():
    concepts = _concepts()
    concepts["DEX-05"]["lifecycle"]["exit_reasons"] = ["STOP", "STOP"]
    problems = validate_exit_reasons(concepts)
    assert any("repeats" in p for p in problems) and any("!= position.ExitReason" in p for p in problems)
    concepts = _concepts()
    concepts["DEX-05"]["lifecycle"]["exit_reasons"].append("lower_case")
    assert any("upper-case" in p for p in validate_exit_reasons(concepts))
    concepts = _concepts()
    del concepts["DEX-05"]["lifecycle"]["exit_reasons"]
    assert any("missing" in p for p in validate_exit_reasons(concepts))
