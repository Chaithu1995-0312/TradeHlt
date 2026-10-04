"""Failing mutations for the slice-2 registry checks. Shipped registries stay clean."""

from __future__ import annotations

import copy

import pytest

from semantics.registry import (
    _in_domain,
    load_concept_contracts,
    load_representation_shards,
    open_deferred_decisions,
    validate_all,
    validate_concepts,
    validate_deferred_decisions,
    validate_representations,
    validate_role_source,
    validate_role_status_untouched,
    warn_open_deferred_decisions,
)

_DECISION = "When a thesis is invalidated while its position is open, does the position close?"


def _doc():
    return copy.deepcopy(load_concept_contracts())


def _concepts():
    return _doc()["concepts"]


def _shards():
    return copy.deepcopy(load_representation_shards())


def _with_open_d2_2(concepts):
    """Re-open the settled D2-2 deferral on a copy (slice 3 settled it as DEX-07, D3-1)."""
    for item in concepts["TRS-03"]["divergences"]:
        if item.get("decided_in") == "slice_3":
            item["decide_in"] = item.pop("decided_in")
    return concepts


def test_shipped_registries_pass_and_d2_2_is_settled():
    concepts = load_concept_contracts()["concepts"]
    assert validate_concepts(load_concept_contracts()) == []
    assert validate_representations(concepts, load_representation_shards()) == []
    assert validate_role_status_untouched() == []
    assert validate_deferred_decisions(concepts) == []
    assert open_deferred_decisions(concepts) == []
    settled = [d for d in concepts["TRS-03"]["divergences"] if d.get("decided_in") == "slice_3"]
    assert len(settled) == 1 and _DECISION == settled[0]["decision"] and "DEX-07" in settled[0]["resolution"]
    assert validate_all() == []


def test_an_open_slice_3_deferral_still_warns():
    concepts = _with_open_d2_2(_concepts())
    pending = open_deferred_decisions(concepts)
    assert any(row["concept_id"] == "TRS-03" and row["decide_in"] == "slice_3" for row in pending)
    with pytest.warns(UserWarning, match="slice_3") as caught:
        warn_open_deferred_decisions(concepts)
    assert _DECISION in " ".join(str(item.message) for item in caught)


def test_v13_a_thesis_without_invalidation_or_with_an_unknown_role_fails():
    doc = _doc()
    del doc["concepts"]["TRS-01"]["roles"]["invalidation"]
    problems = validate_concepts(doc)
    assert any("I-11" in item and "invalidation" in item for item in problems)

    doc = _doc()
    doc["concepts"]["TRS-01"]["roles"]["stop"] = "NO-SUCH"
    problems = validate_concepts(doc)
    assert any("NO-SUCH" in item and "I-11" in item for item in problems)


def test_v1_an_alias_equal_to_a_canonical_name_or_another_alias_fails():
    doc = _doc()
    doc["concepts"]["MKT-E10"]["aliases"] = ["sweep"]
    problems = validate_concepts(doc)
    assert any("sweep" in item and "canonical_name" in item for item in problems)

    doc = _doc()
    doc["concepts"]["MKT-E10"]["aliases"] = ["retest_entry"]
    problems = validate_concepts(doc)
    assert any("retest_entry" in item and "MKT-E09" in item for item in problems)


def test_v14_outcome_basis_and_walk_are_required():
    concepts = load_concept_contracts()["concepts"]
    shards = _shards()
    rep = shards["research_walks.yaml"]["representations"]["Outcome.rr_achieved"]
    rep["parameterization"]["basis"] = "net"
    problems = validate_representations(concepts, shards)
    assert any("net" in item and "I-15" in item for item in problems)

    shards = _shards()
    rep = shards["research_walks.yaml"]["representations"]["Outcome.rr_achieved"]
    rep["parameterization"]["cost_model"] = "component"
    problems = validate_representations(concepts, shards)
    assert any("gross" in item and "I-15" in item for item in problems)

    shards = _shards()
    rep = shards["research_walks.yaml"]["representations"]["Outcome.rr_achieved"]
    del rep["parameterization"]["walk"]
    problems = validate_representations(concepts, shards)
    assert any("walk" in item and "I-15" in item for item in problems)


def test_v7_a_config_reference_is_judged_on_its_resolved_legacy_value():
    concepts = load_concept_contracts()["concepts"]
    shards = _shards()
    rep = shards["crt_engine.yaml"]["representations"]["Trade.entry_price"]
    rep["parameterization"]["entry_semantics"] = "setup.entry_semantics"
    rep.pop("divergence_ref", None)
    problems = validate_representations(concepts, shards)
    assert any(
        "setup.entry_semantics" in item and "approval_bar_legacy" in item and "Trade.entry_price" in item
        for item in problems
    )

    shards = _shards()
    rep = shards["crt_engine.yaml"]["representations"]["Trade.entry_price"]
    rep["parameterization"]["entry_semantics"] = "setup.entry_semantics"
    assert validate_representations(concepts, shards) == []


def test_v10_every_trade_field_is_covered_and_a_bracket_key_covers_tp1():
    concepts = load_concept_contracts()["concepts"]
    shards = _shards()
    shards["crt_engine.yaml"]["unmapped"].pop("Trade.id")
    problems = validate_representations(concepts, shards)
    assert any("Trade.id" in item and "not covered" in item for item in problems)

    shards = _shards()
    reps = shards["crt_engine.yaml"]["representations"]
    for key in (
        "Trade.tp1_price[liq_sweep]",
        "Trade.tp1_price[pullback]",
        "Trade.tp1_price[breakout]",
    ):
        del reps[key]
    assert validate_representations(concepts, shards) == []

    del reps["Trade.tp1_price[reversal]"]
    problems = validate_representations(concepts, shards)
    assert any("Trade.tp1_price" in item and "not covered" in item for item in problems)


def test_v16_slice_3_is_an_error_only_after_an_accepted_decision_concept():
    concepts = {cid: rec for cid, rec in _with_open_d2_2(_concepts()).items()
                if rec.get("layer") != "DECISION_EXECUTION"}
    concepts["DX-01"] = {"layer": "DECISION_EXECUTION", "status": "PROPOSED"}
    assert validate_deferred_decisions(concepts) == []

    concepts["DX-01"]["status"] = "ACCEPTED"
    problems = validate_deferred_decisions(concepts)
    assert any("TRS-03" in item and "slice_3" in item and _DECISION in item for item in problems)

    concepts = _concepts()
    for item in concepts["TRS-03"]["divergences"]:
        if item.get("decide_in") == "slice_3":
            item["decide_in"] = "slice_9"
    concepts["DX-01"] = {
        "layer": "DECISION_EXECUTION",
        "status": "ACCEPTED",
        "divergences": [{"decide_in": "slice_9", "decision": "not a slice_3 deferral"}],
    }
    assert validate_deferred_decisions(concepts) == []


def test_str_and_mapping_domains():
    assert _in_domain("SYNTHETIC", "str") is True
    assert _in_domain("", "str") is False
    assert _in_domain(None, "str") is False
    assert _in_domain({"a": 1}, "mapping") is True
    assert _in_domain(["a"], "mapping") is False
    assert _in_domain("a", "mapping") is False


def test_v15_flags_status_writes_and_the_shipped_package_is_clean():
    assigned = validate_role_source("level.status = 1\n", name="bad.py")
    assert any("assignment to .status" in item and "I-10" in item for item in assigned)
    called = validate_role_source("level.with_status(1)\n", name="bad.py")
    assert any(".with_status(" in item and "I-10" in item for item in called)
    unpacked = validate_role_source("a.status, b.price = 1, 2\n", name="bad.py")
    assert any("assignment to .status" in item for item in unpacked)
    clean = validate_role_source(
        "def f(level):\n"
        "    s = level.status\n"
        "    return Item(status=level.status)\n",
        name="ok.py",
    )
    assert clean == []
    assert validate_role_status_untouched() == []
