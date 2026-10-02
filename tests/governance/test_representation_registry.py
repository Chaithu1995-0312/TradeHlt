"""V-6..V-11 on the representation shards. Mutations are in-memory copies."""

from __future__ import annotations

import copy

import pytest

from semantics.registry import (
    load_concept_contracts,
    load_representation_shards,
    validate_representations,
    validate_unmapped_shrink_only,
)

# Today's unmapped lists. Growth fails V-11. Removal fails the equality pin.
_FEATURE_UNMAPPED = (
    "volume_ratio", "ema_fast", "ema_slow", "ema_spread", "trend_strength_z",
    "momentum_score", "atr", "volatility_ratio", "rsi_14", "macd_line", "macd_signal",
    "macd_hist_raw", "macd_hist_z", "body_size", "candle_range", "body_ratio",
    "volatility_regime", "hour_of_day", "disp_strength", "retest_depth",
    "candles_since_sweep", "liquidity_distance", "liquidity_pressure_score", "volume_spike",
    "order_block_distance", "fvg_distance", "breaker_distance", "mitigation_block_distance",
    "pdh_distance", "pdl_distance", "eqh_distance", "eql_distance",
)
_CRT_UNMAPPED = (
    "CRTState.EXECUTION", "CRTState.RESOLUTION", "CRTState.EXPIRED",
    "CRTState.RANGE_C1", "CRTState.MANIPULATION_C2", "CRTState.DISTRIBUTION_C3",
    # slice 2: first coverage of the Trade type (non-plan fields; slice 3 owns most of them)
    "Trade.id", "Trade.risk_pct", "Trade.runner_active", "Trade.opened_at", "Trade.closed_at",
    "Trade.pnl", "Trade.partial_pnl", "Trade.status", "Trade.cached_features",
    "Trade.open_candle_index", "Trade.displacement_origin",
)
# slice 2: ObjectiveStatus mapped to TRS-02, so the parent list is empty.
_PARENT_UNMAPPED = ()
_PINNED = {
    "feature_pipeline": _FEATURE_UNMAPPED,
    "crt_engine": _CRT_UNMAPPED,
    "parent_crt": _PARENT_UNMAPPED,
    "research_walks": (),
    "research_costs": (),
}


def _concepts_and_shards():
    return load_concept_contracts()["concepts"], load_representation_shards()


def test_shipped_representations_pass_v6_through_v10():
    concepts, shards = _concepts_and_shards()
    assert validate_representations(concepts, shards) == []


def test_unmapped_lists_match_the_pin():
    _concepts, shards = _concepts_and_shards()
    by_producer = {shard["producer_id"]: shard for shard in shards.values()}
    for producer, pinned in _PINNED.items():
        assert tuple(by_producer[producer]["unmapped"]) == pinned
    assert validate_unmapped_shrink_only(shards, _PINNED) == []


def test_unmapped_growth_fails():
    _concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    shards["feature_pipeline.yaml"]["unmapped"]["brand_new_slot"] = "not in slice 1"
    problems = validate_unmapped_shrink_only(shards, _PINNED)
    assert any("brand_new_slot" in item for item in problems), problems


def test_parameter_outside_domain_fails():
    concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    shards["crt_engine.yaml"]["representations"]["SweepEvent"]["parameterization"]["tie"] = "sideways"
    problems = validate_representations(concepts, shards)
    assert any("sideways" in item for item in problems), problems


def test_legacy_value_without_divergence_ref_fails():
    concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    rep = shards["crt_engine.yaml"]["representations"]["SweepEvent"]
    rep["parameterization"]["tie"] = "inclusive"
    rep.pop("divergence_ref", None)
    problems = validate_representations(concepts, shards)
    assert any("inclusive" in item for item in problems), problems


def test_unknown_concept_id_fails():
    concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    shards["crt_engine.yaml"]["representations"]["SweepEvent"]["concept_id"] = "MKT-E99"
    problems = validate_representations(concepts, shards)
    assert any("MKT-E99" in item and "does not exist" in item for item in problems), problems


def test_config_reference_must_resolve_in_the_active_config():
    # A dotted value binds a parameter to settings; it passes only if the active config has
    # that key with an in-domain value (no blanket bypass for dotted strings).
    concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    shards["feature_pipeline.yaml"]["representations"]["session"]["parameterization"][
        "session_timestamp_basis"] = "feature_pipeline.no_such_key"
    problems = validate_representations(concepts, shards)
    assert any("no_such_key" in item for item in problems), problems


def test_missing_canonical_slot_fails():
    concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    del shards["feature_pipeline.yaml"]["unmapped"]["volume_ratio"]
    problems = validate_representations(concepts, shards)
    assert any("not covered" in item and "volume_ratio" in item for item in problems), problems


def test_wrong_slot_index_fails():
    concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    shards["feature_pipeline.yaml"]["representations"]["session"]["slot"] = 30
    problems = validate_representations(concepts, shards)
    assert any("session" in item and "canonical index" in item for item in problems), problems


@pytest.mark.parametrize(
    ("shard", "member"),
    [
        ("crt_engine.yaml", "CRTState.EXPIRED"),
        ("parent_crt.yaml", "HTFState.UNKNOWN"),
        ("parent_crt.yaml", "ObjectiveStatus.NONE"),
    ],
)
def test_dropped_enum_member_fails(shard, member):
    concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    for section in ("representations", "unmapped"):
        (shards[shard].get(section) or {}).pop(member, None)
    problems = validate_representations(concepts, shards)
    assert any(member in item and "not covered" in item for item in problems), problems


def test_duplicate_representation_identity_fails():
    concepts, shards = _concepts_and_shards()
    shards = copy.deepcopy(shards)
    original = shards["crt_engine.yaml"]["representations"]["SweepEvent"]
    shards["crt_engine.yaml"]["representations"]["SweepEventCopy"] = copy.deepcopy(original)
    problems = validate_representations(concepts, shards)
    assert any("duplicate representation identity" in item for item in problems), problems
