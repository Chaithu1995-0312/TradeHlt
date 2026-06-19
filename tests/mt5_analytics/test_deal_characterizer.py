"""
Phase 5.6 — deal characterizer (CI, no terminal).

Runs over synthetic streams shaped like the Phase-2a torture fixtures and asserts each
broker pattern is counted, the gap/score derive correctly, and the deposit (account op)
is excluded — proving the coverage report is correct BEFORE any live run.
"""
from __future__ import annotations

from conftest import make_deal  # type: ignore

from mt5_analytics.engines.deal_characterizer import (
    EXPECTED_PATTERNS,
    broker_capabilities,
    characterize_deal_stream,
    coverage_gaps,
    coverage_score,
)
from mt5_analytics.engines.position_reconstructor import (
    DEAL_ENTRY_IN,
    DEAL_ENTRY_INOUT,
    DEAL_ENTRY_OUT,
    DEAL_TYPE_BUY,
    DEAL_TYPE_SELL,
)

B = 1_700_000_000


def _rich_stream():
    d = []
    # partial close (pos 200): IN 2, OUT 1, OUT 1
    d += [
        make_deal(200, 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY, volume=2.0, price=100, t=B),
        make_deal(200, 2, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL, volume=1.0, price=108, t=B + 60),
        make_deal(200, 3, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL, volume=1.0, price=112, t=B + 120),
    ]
    # pyramid (pos 300): IN 1, IN 1, OUT 2
    d += [
        make_deal(300, 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY, volume=1.0, price=100, t=B),
        make_deal(300, 2, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY, volume=1.0, price=102, t=B + 30),
        make_deal(300, 3, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL, volume=2.0, price=110, t=B + 90),
    ]
    # INOUT reversal (pos 600)
    d += [
        make_deal(600, 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY, volume=1.0, price=100, t=B),
        make_deal(600, 2, entry=DEAL_ENTRY_INOUT, deal_type=DEAL_TYPE_SELL, volume=2.0, price=110, t=B + 60),
        make_deal(600, 3, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_BUY, volume=1.0, price=105, t=B + 120),
    ]
    # reopen (pos 700): IN/OUT, IN/OUT
    d += [
        make_deal(700, 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY, volume=1.0, price=100, t=B),
        make_deal(700, 2, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL, volume=1.0, price=104, t=B + 60),
        make_deal(700, 3, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY, volume=1.0, price=106, t=B + 600),
        make_deal(700, 4, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL, volume=1.0, price=109, t=B + 660),
    ]
    # separate commission (pos 500)
    d += [
        make_deal(500, 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY, volume=1.0, price=100, t=B),
        make_deal(500, 2, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL, volume=1.0, price=105, t=B + 60, profit=5),
        make_deal(500, 3, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_BUY, volume=0.0, price=0, t=B + 61, commission=-1.0),
    ]
    # post-close swap (pos 501)
    d += [
        make_deal(501, 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY, volume=1.0, price=100, t=B),
        make_deal(501, 2, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL, volume=1.0, price=105, t=B + 60, profit=5),
        make_deal(501, 3, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_BUY, volume=0.0, price=0, t=B + 3600, swap=-0.75),
    ]
    # account op (deposit): position_id 0, type 2
    d += [make_deal(0, 9, entry=0, deal_type=2, volume=0.0, price=0, t=B, profit=100000.0)]
    return d


def test_all_patterns_counted():
    c = characterize_deal_stream(_rich_stream())
    assert c["partial_closes"] >= 1
    assert c["pyramids"] >= 1
    assert c["inout_reversals"] == 1
    assert c["reopens"] == 1
    assert c["separate_commission_deals"] == 1
    assert c["post_close_swaps"] == 1
    assert c["account_ops_skipped"] == 1     # deposit excluded
    assert c["trade_positions"] == 6


def test_reopen_not_miscounted_as_partial():
    # pos 700 has two OUT deals across two lifetimes — must NOT be a partial close.
    reopen_only = [d for d in _rich_stream() if d["position_id"] == 700]
    c = characterize_deal_stream(reopen_only)
    assert c["reopens"] == 1 and c["partial_closes"] == 0


def test_full_coverage_score_platinum():
    c = characterize_deal_stream(_rich_stream())
    assert coverage_gaps(c)["missing"] == []
    s = coverage_score(c)
    assert s["coverage_score"] == 100 and s["tier"] == "Platinum"
    assert all(broker_capabilities(c)[p] for p in EXPECTED_PATTERNS)


def test_empty_stream_bronze():
    c = characterize_deal_stream([])
    s = coverage_score(c)
    assert s["coverage_score"] == 0 and s["tier"] == "Bronze"
    assert set(coverage_gaps(c)["missing"]) == set(EXPECTED_PATTERNS)
