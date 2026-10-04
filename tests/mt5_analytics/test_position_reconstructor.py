"""
Phase 2a — Position Reconstruction Torture Tests (THE GATE).

*Reconstruction is sacred.* Every higher layer inherits truth from here, so this suite
must be green before any intelligence is layered on. Each test feeds a synthetic deal
stream and asserts VWAP basis, net P&L (profit+swap+commission), direction, episode
boundaries, and the completion guard.
"""
from __future__ import annotations

import math

from mt5_analytics.engines.position_reconstructor import reconstruct_position_episodes
from mt5_analytics.schemas.position_episode_v1_0 import to_iso_utc


def _approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)


# ── basics ──────────────────────────────────────────────────────────────────────
def test_simple_long_win(deal):
    deals = [
        deal.make(100, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0, t=deal.base),
        deal.make(100, 2, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=110.0,
                  t=deal.base + 60, profit=10.0),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 1
    e = eps[0]
    assert e.direction == "long"
    assert _approx(e.entry_vwap, 100.0) and _approx(e.exit_vwap, 110.0)
    assert _approx(e.volume, 1.0)
    assert _approx(e.net_pnl, 10.0)
    assert e.duration_seconds == 60.0


def test_simple_short_loss(deal):
    deals = [
        deal.make(101, 1, entry=deal.IN, deal_type=deal.SELL, volume=2.0, price=50.0, t=deal.base),
        deal.make(101, 2, entry=deal.OUT, deal_type=deal.BUY, volume=2.0, price=52.0,
                  t=deal.base + 120, profit=-4.0),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 1
    assert eps[0].direction == "short"
    assert _approx(eps[0].net_pnl, -4.0)


# ── partial close (finalize only on volume balance) ───────────────────────────────
def test_partial_scale_out(deal):
    deals = [
        deal.make(200, 1, entry=deal.IN, deal_type=deal.BUY, volume=2.0, price=100.0, t=deal.base),
        deal.make(200, 2, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=108.0,
                  t=deal.base + 60, profit=8.0),
        deal.make(200, 3, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=112.0,
                  t=deal.base + 120, profit=12.0),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 1
    e = eps[0]
    assert _approx(e.volume, 2.0)
    assert _approx(e.exit_vwap, 110.0)  # (108*1 + 112*1)/2
    assert _approx(e.net_pnl, 20.0)


def test_premature_completion_guard(deal):
    # IN 2, OUT 1 only -> still open 1 lot -> NO episode emitted.
    deals = [
        deal.make(201, 1, entry=deal.IN, deal_type=deal.BUY, volume=2.0, price=100.0, t=deal.base),
        deal.make(201, 2, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=105.0,
                  t=deal.base + 60),
    ]
    eps = reconstruct_position_episodes(deals, open_position_ids=frozenset({201}))
    assert eps == []


# ── pyramiding (VWAP entry) ───────────────────────────────────────────────────────
def test_pyramiding_vwap_entry(deal):
    deals = [
        deal.make(300, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0, t=deal.base),
        deal.make(300, 2, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=102.0,
                  t=deal.base + 30),
        deal.make(300, 3, entry=deal.OUT, deal_type=deal.SELL, volume=2.0, price=110.0,
                  t=deal.base + 90, profit=18.0),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 1
    assert _approx(eps[0].entry_vwap, 101.0)  # NOT 100.0 (first-deal price)
    assert _approx(eps[0].volume, 2.0)


# ── multiple tickets sharing one position_id ──────────────────────────────────────
def test_multiple_tickets_one_position(deal):
    deals = [
        deal.make(400, 11, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=10.0, t=deal.base),
        deal.make(400, 12, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=10.0,
                  t=deal.base + 10),
        deal.make(400, 13, entry=deal.OUT, deal_type=deal.SELL, volume=2.0, price=12.0,
                  t=deal.base + 60, profit=4.0),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 1
    assert set(eps[0].deal_tickets) == {11, 12, 13}


# ── separate commission / swap deal records ───────────────────────────────────────
def test_commission_as_separate_deal(deal):
    # Broker emits commission as its own zero-volume record.
    deals = [
        deal.make(500, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0,
                  t=deal.base, commission=-2.0),
        deal.make(500, 2, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=105.0,
                  t=deal.base + 60, profit=5.0, commission=-2.0),
        deal.make(500, 3, entry=deal.OUT, deal_type=deal.BUY, volume=0.0, price=0.0,
                  t=deal.base + 61, commission=-1.0),  # standalone commission record
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 1
    assert _approx(eps[0].commission, -5.0)
    assert _approx(eps[0].net_pnl, 5.0 - 5.0)  # profit 5 + commission -5
    assert _approx(eps[0].volume, 1.0)         # zero-volume record does not inflate volume


def test_post_close_swap_attaches_to_last_episode(deal):
    deals = [
        deal.make(501, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0, t=deal.base),
        deal.make(501, 2, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=105.0,
                  t=deal.base + 60, profit=5.0),
        # swap posts AFTER the position is balanced/closed.
        deal.make(501, 3, entry=deal.OUT, deal_type=deal.BUY, volume=0.0, price=0.0,
                  t=deal.base + 3600, swap=-0.75),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 1
    assert _approx(eps[0].swap, -0.75)
    assert _approx(eps[0].net_pnl, 5.0 - 0.75)


# ── INOUT reversal (close-old + open-new) ─────────────────────────────────────────
def test_inout_reversal_two_episodes(deal):
    # BUY 1 @100; SELL 2 (INOUT) @110 -> close long 1, open short 1; BUY 1 @105 closes short.
    deals = [
        deal.make(600, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0, t=deal.base),
        deal.make(600, 2, entry=deal.INOUT, deal_type=deal.SELL, volume=2.0, price=110.0,
                  t=deal.base + 60, profit=10.0),
        deal.make(600, 3, entry=deal.OUT, deal_type=deal.BUY, volume=1.0, price=105.0,
                  t=deal.base + 120, profit=5.0),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 2
    long_ep = next(e for e in eps if e.direction == "long")
    short_ep = next(e for e in eps if e.direction == "short")
    assert _approx(long_ep.entry_vwap, 100.0) and _approx(long_ep.exit_vwap, 110.0)
    assert _approx(long_ep.volume, 1.0)
    assert _approx(short_ep.entry_vwap, 110.0) and _approx(short_ep.exit_vwap, 105.0)
    assert _approx(short_ep.volume, 1.0)
    assert long_ep.episode_id != short_ep.episode_id


def test_inout_open_leg_not_emitted_until_closed(deal):
    # Reversal leaves an OPEN short -> only the closed long episode is emitted.
    deals = [
        deal.make(601, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0, t=deal.base),
        deal.make(601, 2, entry=deal.INOUT, deal_type=deal.SELL, volume=2.0, price=110.0,
                  t=deal.base + 60, profit=10.0),
    ]
    eps = reconstruct_position_episodes(deals, open_position_ids=frozenset({601}))
    assert len(eps) == 1
    assert eps[0].direction == "long"


# ── reopen after close (distinct episodes / identity) ─────────────────────────────
def test_reopen_after_close_two_distinct_episodes(deal):
    deals = [
        deal.make(700, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0, t=deal.base),
        deal.make(700, 2, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=104.0,
                  t=deal.base + 60, profit=4.0),
        deal.make(700, 3, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=106.0,
                  t=deal.base + 600),
        deal.make(700, 4, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=109.0,
                  t=deal.base + 660, profit=3.0),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 2
    assert eps[0].position_id == eps[1].position_id == 700
    assert eps[0].episode_id != eps[1].episode_id      # logical id reused, analytical id not
    assert _approx(eps[0].net_pnl, 4.0) and _approx(eps[1].net_pnl, 3.0)


# ── K-2: cashflow before entry must not mis-seed the leg ──────────────────────────
def test_cashflow_before_entry(deal):
    # A zero-volume commission record (wrong/placeholder type) arrives BEFORE the IN.
    deals = [
        deal.make(1000, 1, entry=deal.OUT, deal_type=deal.SELL, volume=0.0, price=0.0,
                  t=deal.base, commission=-1.0),                       # pre-entry cashflow
        deal.make(1000, 2, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0,
                  t=deal.base + 60),
        deal.make(1000, 3, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=110.0,
                  t=deal.base + 120, profit=10.0),
    ]
    eps = reconstruct_position_episodes(deals)
    assert len(eps) == 1
    e = eps[0]
    assert e.direction == "long"                       # from the IN, NOT the cashflow record
    assert e.entry_time == to_iso_utc(deal.base + 60)  # the IN time, NOT base
    assert e.duration_seconds == 60.0
    assert _approx(e.net_pnl, 9.0)                     # profit 10 + commission -1


# ── determinism ───────────────────────────────────────────────────────────────────
def test_determinism_same_input_same_episodes(deal):
    deals = [
        deal.make(800, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0, t=deal.base),
        deal.make(800, 2, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=110.0,
                  t=deal.base + 60, profit=10.0),
    ]
    a = [e.to_dict() for e in reconstruct_position_episodes(deals)]
    b = [e.to_dict() for e in reconstruct_position_episodes(list(reversed(deals)))]
    assert a == b  # deal order within a position must not change the result
