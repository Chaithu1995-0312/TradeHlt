"""Tier 0A — unit tests for the sacred-minimum trade identity.

Guards the invariant that `TradeIdentityV1` is (1) exactly the three permanent fields,
(2) frozen/immutable, (3) fail-fast on empty identity, (4) round-trips through dict, and
(5) mints unique trade_ids per intent even for a shared (deterministic) alert_id.
"""
import dataclasses

import pytest

from src.journal.trade_identity_v1_0 import (
    SCHEMA_VERSION,
    TradeIdentityV1,
    mint_trade_id,
)


def test_sacred_minimum_fields_only():
    # Identity must carry ONLY the permanent fields + schema_version — nothing that churns.
    names = {f.name for f in dataclasses.fields(TradeIdentityV1)}
    assert names == {"trade_id", "alert_id", "created_at", "schema_version"}
    # Explicitly assert the churn-fields never leaked in.
    for leaked in ("symbol", "direction", "magic", "comment", "config_hash",
                   "model_version", "episode_id", "position_id", "status"):
        assert leaked not in names


def test_new_mints_and_stamps():
    ident = TradeIdentityV1.new("alert123")
    assert ident.alert_id == "alert123"
    assert ident.created_at.endswith("Z")
    assert ident.schema_version == SCHEMA_VERSION


def test_trade_id_is_opaque():
    # Contract invariant #1: trade_id embeds nothing — no alert_id, never parseable.
    ident = TradeIdentityV1.new("alert123")
    assert "alert123" not in ident.trade_id
    assert ":" not in ident.trade_id
    assert len(ident.trade_id) == 32 and all(c in "0123456789abcdef" for c in ident.trade_id)


def test_trade_id_is_unique_per_intent_for_same_alert():
    # alert_id is deterministic on decision-context, so it is NOT unique per intent.
    a = TradeIdentityV1.new("same_alert")
    b = TradeIdentityV1.new("same_alert")
    assert a.alert_id == b.alert_id
    assert a.trade_id != b.trade_id  # each intent gets a fresh id


def test_injectable_deterministic_values():
    ident = TradeIdentityV1.new(
        "alertX", trade_id="TID-1", created_at="2026-07-04T00:00:00Z"
    )
    assert ident.trade_id == "TID-1"
    assert ident.created_at == "2026-07-04T00:00:00Z"


def test_is_frozen():
    ident = TradeIdentityV1.new("alertY", trade_id="TID-2",
                                created_at="2026-07-04T00:00:00Z")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ident.trade_id = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize("bad", ["", None])
@pytest.mark.parametrize("field_pos", ["trade_id", "alert_id", "created_at"])
def test_fail_fast_on_empty_identity(field_pos, bad):
    kwargs = {"trade_id": "t", "alert_id": "a", "created_at": "2026-07-04T00:00:00Z"}
    kwargs[field_pos] = bad
    with pytest.raises(ValueError):
        TradeIdentityV1(**kwargs)


def test_mint_trade_id_is_opaque_and_unique():
    a, b = mint_trade_id(), mint_trade_id()
    assert a != b                       # unique per intent
    assert len(a) == 32 and ":" not in a  # opaque uuid4 hex, no embedded lineage


def test_dict_round_trip():
    ident = TradeIdentityV1.new("alertZ", trade_id="TID-3",
                                created_at="2026-07-04T00:00:00Z")
    d = ident.to_dict()
    assert d == {
        "trade_id": "TID-3",
        "alert_id": "alertZ",
        "created_at": "2026-07-04T00:00:00Z",
        "schema_version": SCHEMA_VERSION,
    }
    # from_dict ignores unknown/foreign keys (forward-compat with sidecar records).
    d_with_extra = {**d, "magic": 12345, "config_hash": "deadbeef"}
    assert TradeIdentityV1.from_dict(d_with_extra) == ident
