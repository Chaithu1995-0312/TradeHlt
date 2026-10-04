"""Tier 0B — TradeExecutionLinkV1 (transport correlation, disposable)."""
import dataclasses

import pytest

from src.journal.trade_execution_link_v1_0 import SCHEMA_VERSION, TradeExecutionLinkV1


def test_requires_trade_id_and_venue():
    with pytest.raises(ValueError):
        TradeExecutionLinkV1(trade_id="", venue="MT5")
    with pytest.raises(ValueError):
        TradeExecutionLinkV1(trade_id="t1", venue="")


def test_magic_not_required_identity_survives_missing_transport():
    # Contract invariant #5: magic != identity. A link with no magic/comment is still valid;
    # the join simply degrades to fallback correlation.
    link = TradeExecutionLinkV1(trade_id="t1", venue="MT5")
    assert link.magic is None and link.comment is None
    assert link.trade_id == "t1"
    assert link.created_at.endswith("Z")
    assert link.schema_version == SCHEMA_VERSION


def test_is_frozen():
    link = TradeExecutionLinkV1(trade_id="t1", venue="MT5", magic=42)
    with pytest.raises(dataclasses.FrozenInstanceError):
        link.magic = 99  # type: ignore[misc]


def test_dict_round_trip_with_optional_fields():
    link = TradeExecutionLinkV1(
        trade_id="t1", venue="MT5", magic=20260501, comment="t1",
        order_ticket=111, deal_ticket=222, position_id=333, episode_id="333:...:abcd",
        created_at="2026-07-05T00:00:00Z",
    )
    d = link.to_dict()
    assert d["magic"] == 20260501 and d["episode_id"] == "333:...:abcd"
    assert TradeExecutionLinkV1.from_dict({**d, "unknown": 1}) == link
