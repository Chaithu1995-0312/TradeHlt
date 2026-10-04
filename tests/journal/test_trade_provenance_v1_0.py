"""Tier 0B — TradeProvenanceV1 (governance lineage, append)."""
import dataclasses

import pytest

from src.journal.trade_provenance_v1_0 import SCHEMA_VERSION, TradeProvenanceV1


def test_requires_trade_id_only():
    with pytest.raises(ValueError):
        TradeProvenanceV1(trade_id="")
    # All lineage fields optional — provenance never blocks identity.
    prov = TradeProvenanceV1(trade_id="t1")
    assert prov.config_hash is None and prov.model_version is None
    assert prov.captured_at.endswith("Z")
    assert prov.schema_version == SCHEMA_VERSION


def test_is_frozen():
    prov = TradeProvenanceV1(trade_id="t1", config_hash="deadbeef")
    with pytest.raises(dataclasses.FrozenInstanceError):
        prov.config_hash = "cafe"  # type: ignore[misc]


def test_dict_round_trip():
    prov = TradeProvenanceV1(
        trade_id="t1", strategy_id="crt_spine", promotion_version="v2_multi_2026_04",
        config_hash="abc123", config_version="v2_multi_2026_04", model_version="gaussian_v3",
        captured_at="2026-07-05T00:00:00Z",
    )
    d = prov.to_dict()
    assert d["config_version"] == "v2_multi_2026_04"
    assert TradeProvenanceV1.from_dict({**d, "foreign": True}) == prov
