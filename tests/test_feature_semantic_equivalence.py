"""Feature semantic equivalence. Names, width, and aliases are not MATCH."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from features.feature_schema import CANONICAL_FEATURES, SCHEMA_V2_FEATURE_DIM
from features.semantic_equivalence import (
    BEHAVIOR_FIELDS,
    FeatureSemanticIncompatible,
    audit,
    build_contract,
    check_consumer,
    check_vector,
    contract_hash,
    evaluate_artifact_binding,
    feature_definition_hash,
    require_artifact_compatible,
    require_training_feature_contract,
    write_reports,
)

ROOT = Path(__file__).resolve().parents[1]
_SOURCE = [{"path": "tests/test_feature_semantic_equivalence.py", "lines": "1", "kind": "source"}]

_FROZEN_PREFIX = [
    "open", "high", "low", "close", "volume", "volume_ratio", "double_sweep",
    "ema_fast", "ema_slow", "ema_spread", "trend_bias", "trend_strength_z",
    "momentum_score", "atr", "volatility_ratio", "rsi_14", "macd_line",
    "macd_signal", "macd_hist_raw", "macd_hist_z", "sweep_detected",
    "liquidity_sweep", "break_of_structure", "swing_high", "swing_low",
    "higher_high", "lower_low", "body_size", "candle_range", "body_ratio",
    "volatility_regime", "session", "hour_of_day", "disp_strength", "retest_depth",
]


@pytest.fixture(scope="module")
def contract():
    return build_contract()


def _slot(contract, name):
    for feature in contract["features"]:
        if feature["slot_name"] == name:
            return feature
    raise AssertionError(name)


def _copy_behavior(slot):
    return {field: slot[field] for field in BEHAVIOR_FIELDS}


def test_frozen_prefix_is_the_live_35(contract):
    assert SCHEMA_V2_FEATURE_DIM == 35
    assert list(CANONICAL_FEATURES[:35]) == _FROZEN_PREFIX
    assert contract["schema_prefix_order"] == _FROZEN_PREFIX
    assert contract["prefix_frozen"] is True
    assert contract["production_formulas_changed"] is False
    assert contract["economic_claims_allowed"] is False
    assert len(contract["full_vector_order"]) == len(CANONICAL_FEATURES)
    assert contract["full_vector_order"] == list(CANONICAL_FEATURES)


def test_definition_hash_ignores_name_and_sees_formula(contract):
    body = _slot(contract, "body_ratio")
    same = feature_definition_hash({**body, "slot_name": "not_the_name", "entry_name": "other"})
    assert same == body["definition_hash"]
    changed = dict(body)
    changed["formula"] = "body_size / total_wick"
    assert feature_definition_hash(changed) != body["definition_hash"]
    mutated = json.loads(json.dumps(contract))
    mutated["features"][29]["formula"] = "body_size / total_wick"
    mutated["features"][29]["definition_hash"] = feature_definition_hash(mutated["features"][29])
    assert contract_hash(mutated) != contract["contract_hash"]


def test_body_ratio_formula_mismatch_is_drift(contract):
    result = check_consumer(
        "body_ratio",
        contract=contract,
        implementation={"formula": "body_size / total_wick"},
        evidence=_SOURCE,
    )
    assert result["status"] == "DRIFT"
    assert result["concept_id"] == "FM-010"


def test_explicit_fm013_on_body_ratio_is_ambiguous(contract):
    result = check_consumer(
        "body_ratio",
        contract=contract,
        concept_id="FM-013",
        implementation={"formula": "body_size / total_wick"},
        evidence=_SOURCE,
    )
    assert result["status"] == "AMBIGUOUS"


def test_double_sweep_lookback_mismatch_is_drift(contract):
    result = check_consumer(
        "double_sweep",
        contract=contract,
        implementation={"lookback": 1},
        evidence=_SOURCE,
    )
    assert result["status"] == "DRIFT"
    assert result["concept_id"] == "FM-060"
    same_window = check_consumer(
        "double_sweep",
        contract=contract,
        implementation={"lookback": 5},
        evidence=_SOURCE,
    )
    assert same_window["status"] != "MATCH"


def test_session_string_encoding_is_drift(contract):
    result = check_consumer(
        "session",
        contract=contract,
        implementation={"encoding": "string:{asia,london,new_york,overlap,closed}"},
        evidence=_SOURCE,
    )
    assert result["status"] == "DRIFT"
    assert result["concept_id"] == "FM-052"
    numeric = check_consumer(
        "session",
        contract=contract,
        implementation={"encoding": 0},
        evidence=_SOURCE,
    )
    assert numeric["status"] == "DRIFT"


def test_wick_size_alias_does_not_conceal_total_wick(contract):
    alias_only = check_consumer("wick_size", contract=contract, evidence=_SOURCE)
    assert alias_only["status"] == "UNVERIFIED"
    assert alias_only["alias_used"] is True
    drifted = check_consumer(
        "wick_size",
        contract=contract,
        implementation={"formula": "upper_wick + lower_wick"},
        evidence=_SOURCE,
    )
    assert drifted["status"] == "DRIFT"
    copied = _copy_behavior(_slot(contract, "candle_range"))
    equal_without_review = check_consumer(
        "wick_size",
        contract=contract,
        implementation=copied,
        evidence=_SOURCE,
    )
    assert equal_without_review["status"] == "UNVERIFIED"
    filled = json.loads(json.dumps(contract))
    filled_slot = _slot(filled, "candle_range")
    for field in BEHAVIOR_FIELDS:
        if filled_slot[field] == "UNMAPPED":
            filled_slot[field] = f"concrete:{field}"
    concrete = _copy_behavior(filled_slot)
    reviewed = check_consumer(
        "wick_size",
        contract=filled,
        implementation={"formula": "upper_wick + lower_wick"},
        evidence=_SOURCE,
        transformation={
            "transformation_id": "XFORM-TEST-WICK",
            "version": "1.0.0",
            "reviewed": True,
            "output": concrete,
        },
    )
    assert reviewed["status"] == "MATCH"
    assert reviewed["resolved_by"] == "XFORM-TEST-WICK"
    unreviewed = check_consumer(
        "wick_size",
        contract=contract,
        implementation={"formula": "upper_wick + lower_wick"},
        evidence=_SOURCE,
        transformation={
            "transformation_id": "XFORM-TEST-WICK",
            "version": "1.0.0",
            "reviewed": False,
            "output": concrete,
        },
    )
    assert unreviewed["status"] == "DRIFT"


def test_vector_order_and_dimension(contract):
    prefix = list(contract["schema_prefix_order"])
    assert check_vector(prefix, contract=contract)["status"] == "UNVERIFIED"
    swapped = prefix[:]
    swapped[0], swapped[1] = swapped[1], swapped[0]
    assert check_vector(swapped, contract=contract)["status"] == "DRIFT"
    assert check_vector(prefix[:-1], contract=contract)["status"] == "DRIFT"
    implementations = {
        "body_ratio": {"formula": "body_size / total_wick"},
    }
    mixed = check_vector(prefix, contract=contract, implementations=implementations, evidence=_SOURCE)
    assert mixed["status"] == "DRIFT"


def test_missing_value_policy_gap_is_not_fake_drift(contract):
    slot = _slot(contract, "double_sweep")
    impl = _copy_behavior(slot)
    impl["missing_value_policy"] = "substitute 0 when absent"
    assert slot["missing_value_policy"] == "UNMAPPED"
    result = check_consumer(
        "double_sweep",
        contract=contract,
        implementation=impl,
        evidence=_SOURCE,
    )
    assert result["status"] == "UNMAPPED"
    both = json.loads(json.dumps(contract))
    target = _slot(both, "double_sweep")
    target["missing_value_policy"] = "leave_absent"
    target["definition_hash"] = feature_definition_hash(target)
    impl["missing_value_policy"] = "substitute_0"
    drifted = check_consumer(
        "double_sweep",
        contract=both,
        implementation=impl,
        evidence=_SOURCE,
    )
    assert drifted["status"] == "DRIFT"


def test_unknown_surface_and_manifest_evidence():
    unknown = check_consumer("not_a_feature", evidence=_SOURCE)
    assert unknown["status"] == "UNMAPPED"
    manifest = check_consumer(
        "body_ratio",
        evidence=[{"path": "docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json", "kind": "manifest"}],
        implementation={"formula": "body_size / candle_range"},
    )
    assert manifest["status"] == "UNVERIFIED"


def test_artifact_width_and_alias_are_not_match(contract):
    names = list(contract["schema_prefix_order"])
    absent = evaluate_artifact_binding(names, None, contract=contract)
    assert absent["status"] == "UNVERIFIED"
    with pytest.raises(FeatureSemanticIncompatible) as exc_info:
        require_artifact_compatible(names, None, contract=contract)
    assert exc_info.value.status == "UNVERIFIED"
    wrong = evaluate_artifact_binding(
        names,
        {"contract_hash": "0" * 64},
        contract=contract,
    )
    assert wrong["status"] == "DRIFT"
    stamped = evaluate_artifact_binding(
        names,
        {"contract_hash": contract["contract_hash"]},
        contract=contract,
    )
    assert stamped["status"] == "UNMAPPED"
    with pytest.raises(FeatureSemanticIncompatible) as unmapped:
        require_artifact_compatible(
            names,
            {"contract_hash": contract["contract_hash"]},
            contract=contract,
        )
    assert unmapped.value.status == "UNMAPPED"
    aliased = evaluate_artifact_binding(
        ["wick_size"],
        {"contract_hash": contract["contract_hash"]},
        contract=contract,
    )
    assert aliased["status"] == "UNVERIFIED"
    with pytest.raises(FeatureSemanticIncompatible):
        require_training_feature_contract(["wick_size"], contract=contract)
    with pytest.raises(FeatureSemanticIncompatible) as named:
        require_training_feature_contract(["body_ratio"], contract=contract)
    assert named.value.status != "MATCH"


def test_audit_keeps_every_manifest_consumer_unverified(contract):
    report = audit(contract=contract)
    assert report["architecture_semantically_consistent"] is False
    manifest = [edge for edge in report["edges"] if edge["branch_id"].startswith("manifest:")]
    assert len(manifest) == 13
    assert {edge["status"] for edge in manifest} == {"UNVERIFIED"}
    by_id = {edge["branch_id"]: edge["status"] for edge in report["edges"]}
    assert by_id["live_engine_hook.historical_body_ratio"] == "DRIFT"
    assert by_id["semantics.market.levels.double_sweep_window_1"] == "DRIFT"
    assert by_id["live_engine_hook.session_string"] == "DRIFT"
    assert by_id["live_engine_hook.wick_size_local"] == "DRIFT"
    assert by_id["feature_pipeline.double_sweep_e01_arm"] == "DRIFT"
    assert by_id["gaussian_artifact.dimension_only"] == "UNVERIFIED"
    assert by_id["tradenet_artifact.dimension_only"] == "UNVERIFIED"
    assert by_id["gaussian_live_heuristic.names_only"] == "UNVERIFIED"
    assert by_id["semantics.market.conditions.double_sweep_window_param"] == "UNVERIFIED"
    assert by_id["manifest:Gaussian_live_heuristic"] == "UNVERIFIED"
    assert by_id["feature_store.missing_value_substitutes"] != "DRIFT"
    assert by_id["feature_pipeline.double_sweep_legacy_arm"] != "MATCH"
    assert "MATCH" not in report["counts"] or report["counts"]["MATCH"] != len(report["edges"])


def test_written_reports_match_fresh_audit(tmp_path, contract):
    written = write_reports(tmp_path)
    assert written["audit"]["architecture_semantically_consistent"] is False
    on_disk = json.loads((tmp_path / "feature_semantic_equivalence_audit.json").read_text(encoding="utf-8"))
    fresh = audit(contract=contract)
    assert on_disk["contract_hash"] == fresh["contract_hash"] == contract["contract_hash"]
    pairs = [(edge["branch_id"], edge["status"]) for edge in on_disk["edges"]]
    assert pairs == [(edge["branch_id"], edge["status"]) for edge in fresh["edges"]]
    impact = json.loads((tmp_path / "feature_semantic_change_impact.json").read_text(encoding="utf-8"))
    body = next(row for row in impact["impacts"] if row["slot_name"] == "body_ratio")
    touched = {item["branch_id"] for item in body["affected_branches"]}
    assert "live_engine_hook.historical_body_ratio" in touched
    assert "manifest:live_engine_hook" in touched or any(
        item["parent_consumer"] == "live_engine_hook" for item in body["affected_branches"]
    )
    text = (tmp_path / "feature_semantic_equivalence_audit.md").read_text(encoding="utf-8")
    for status in ("MATCH", "DRIFT", "UNMAPPED", "AMBIGUOUS", "UNVERIFIED"):
        assert status in text
    assert "False" in text


def test_legacy_length_mismatch_returns_none():
    from training.trade_net_v2 import TradeNetV2

    model = TradeNetV2.__new__(TradeNetV2)
    model._v1_n_features = 3
    model._v1_scaler = None
    assert model._predict_legacy([1.0, 2.0, 3.0, 4.0]) is None
    assert model._predict_legacy([1.0]) is None


def test_ml_gaussian_does_not_swallow_semantic_refusal(monkeypatch):
    from engines.ml_gaussian_engine import MLGaussianEngine

    class _Registry:
        def get_active_version(self, _instrument):
            return None

        def get_active_gaussian(self):
            return "v-test"

        def _load(self):
            return {"v-test": {"model_file": "missing.json"}}

    monkeypatch.setattr("core.model_registry.GaussianModelRegistry", _Registry)

    def _boom(_name):
        raise FeatureSemanticIncompatible("UNVERIFIED", "artifact has no semantic contract")

    monkeypatch.setattr("training.trainer.load_gaussian_model", _boom)
    engine = MLGaussianEngine({}, preload=False)
    engine._load_model()
    assert engine._semantic_refused is True
    with pytest.raises(FeatureSemanticIncompatible) as exc_info:
        engine.compute({})
    assert exc_info.value.status == "UNVERIFIED"


def test_ml_gaussian_ordinary_load_error_still_returns_neutral(monkeypatch):
    from engines.ml_gaussian_engine import MLGaussianEngine

    class _Registry:
        def get_active_version(self, _instrument):
            return None

        def get_active_gaussian(self):
            return "v-test"

        def _load(self):
            return {"v-test": {"model_file": "missing.json"}}

    monkeypatch.setattr("core.model_registry.GaussianModelRegistry", _Registry)

    def _boom(_name):
        raise RuntimeError("disk")

    monkeypatch.setattr("training.trainer.load_gaussian_model", _boom)
    engine = MLGaussianEngine({}, preload=False)
    engine._load_model()
    assert engine._semantic_refused is False
    assert engine._load_failed is True
    assert engine.compute({})["score"] == 0.5
