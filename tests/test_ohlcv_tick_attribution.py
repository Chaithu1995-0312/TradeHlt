"""Synthetic BC-4 residual-attribution tests -- no live MT5.

Each frozen candidate must count what it claims, INCLUDING negative cases: a planted
duplicate/boundary/ask-only tick must be caught by the right candidate and missed by the
wrong ones. A candidate that cannot fail on a planted fixture is not enforcement.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from research.ohlcv_probe_report import SOURCE_LIVE, SOURCE_SYNTHETIC
from research.ohlcv_tick_attribution import (
    BAR_SECONDS,
    CANDIDATES,
    FROZEN_CANDIDATE_IDS,
    OUTCOME_ATTRIBUTED,
    OUTCOME_ATTRIBUTED_V2,
    OUTCOME_PENDING_HOLDOUT,
    OUTCOME_UNATTRIBUTED,
    OUTCOME_UNATTRIBUTED_V2,
    TICK_FLAG_ASK,
    TICK_FLAG_BID,
    TICK_FLAG_LAST,
    V2_CANDIDATE_ID,
    V2_MIN_HOLDOUT_BARS,
    attribute,
    c9_flag_bid,
    score_bar,
    score_v2,
    survivors,
)

T0 = 1_756_000_000  # arbitrary bar-start epoch, on no particular lattice


def _tick(offset_ms: int, bid: float, ask: float, flags: int, last: float = 0.0) -> dict:
    return {
        "time_msc": (T0 * 1000) + offset_ms,
        "bid": bid,
        "ask": ask,
        "last": last,
        "flags": flags,
    }


BID_ASK = TICK_FLAG_BID | TICK_FLAG_ASK


# ── each candidate counts what it claims ───────────────────────────────────────
def test_c0_counts_everything():
    ticks = [_tick(i, 100.0, 101.0, BID_ASK) for i in range(10)]
    assert score_bar(ticks, T0)["C0_len"] == 10


def test_c1_excludes_the_upper_boundary_tick():
    """A tick landing exactly at T+900s belongs to the NEXT bar."""
    inside = [_tick(i, 100.0, 101.0, BID_ASK) for i in range(5)]
    boundary = [_tick(BAR_SECONDS * 1000, 100.0, 101.0, BID_ASK)]
    got = score_bar(inside + boundary, T0)
    assert got["C0_len"] == 6, "C0 must include the boundary tick"
    assert got["C1_exclusive_upper"] == 5, "C1 must exclude it"


def test_c2_drops_planted_exact_duplicate_and_c1_does_not():
    base = [_tick(i, 100.0 + i, 101.0 + i, BID_ASK) for i in range(5)]
    dup = [dict(base[2])]  # exact duplicate of an existing tick
    got = score_bar(base + dup, T0)
    assert got["C1_exclusive_upper"] == 6, "C1 keeps duplicates"
    assert got["C2_dedup_exact"] == 5, "C2 must drop the planted duplicate"


def test_c3_counts_only_price_changing_ticks():
    ticks = [
        _tick(0, 100.0, 101.0, BID_ASK),
        _tick(1, 100.0, 101.0, BID_ASK),  # repeat, same quote
        _tick(2, 100.5, 101.0, BID_ASK),  # moved
        _tick(3, 100.5, 101.0, BID_ASK),  # repeat
    ]
    assert score_bar(ticks, T0)["C3_price_changed"] == 2


def test_c4_and_c9_differ_on_ask_only_ticks():
    """The distinction that decided V1: BID|ASK counts bare-ASK ticks, BID-only does not."""
    ticks = [
        _tick(0, 100.0, 101.0, BID_ASK),
        _tick(1, 100.0, 101.0, TICK_FLAG_ASK),  # ask-only
        _tick(2, 100.0, 101.0, TICK_FLAG_BID),  # bid-only
    ]
    got = score_bar(ticks, T0)
    assert got["C4_flag_bid_or_ask"] == 3, "C4 counts the ask-only tick"
    assert c9_flag_bid(ticks, T0) == 2, "C9 must NOT count the ask-only tick"


def test_c5_counts_last_flag_only():
    ticks = [
        _tick(0, 100.0, 101.0, BID_ASK),
        _tick(1, 100.0, 101.0, TICK_FLAG_LAST, last=100.5),
    ]
    assert score_bar(ticks, T0)["C5_flag_last"] == 1


def test_c6_counts_distinct_timestamps():
    ticks = [
        _tick(0, 100.0, 101.0, BID_ASK),
        _tick(0, 100.5, 101.5, BID_ASK),  # same time_msc
        _tick(1, 101.0, 102.0, BID_ASK),
    ]
    assert score_bar(ticks, T0)["C6_distinct_time_msc"] == 2


def test_c9_ignores_the_128_bit_vocabulary_difference():
    """134 = 128|4|2 and 6 = 4|2 both carry BID; 4 and 132 do not.

    The live feed changed vocabulary between sessions (discovery used 134/130/4,
    holdout used 6/2/4), so C9 must key on the BID bit, not on the literal value.
    """
    ticks = [
        _tick(0, 100.0, 101.0, 134),
        _tick(1, 100.0, 101.0, 130),
        _tick(2, 100.0, 101.0, 6),
        _tick(3, 100.0, 101.0, 2),
        _tick(4, 100.0, 101.0, 4),  # ask-only, no BID bit
        _tick(5, 100.0, 101.0, 132),  # 128|4, no BID bit
    ]
    assert c9_flag_bid(ticks, T0) == 4


# ── survivorship requires EXACT match on EVERY bar ─────────────────────────────
def _bar(tick_volume: int, **candidate_counts) -> dict:
    counts = {cid: -1 for cid in FROZEN_CANDIDATE_IDS}
    counts.update(candidate_counts)
    return {"T": "x", "tick_volume": tick_volume, "candidates": counts}


def test_survivor_requires_every_bar():
    bars = [_bar(100, C0_len=100), _bar(200, C0_len=201)]
    assert "C0_len" not in survivors(bars), "one mismatch must disqualify"
    bars_ok = [_bar(100, C0_len=100), _bar(200, C0_len=200)]
    assert "C0_len" in survivors(bars_ok)


def test_no_tolerance_band():
    """Off by one is a miss. There is no 'close enough'."""
    bars = [_bar(1000, C0_len=1001)]
    assert survivors(bars) == []


# ── outcome rules ──────────────────────────────────────────────────────────────
def test_zero_survivors_is_unattributed():
    r = attribute([_bar(100, C0_len=999)])
    assert r["outcome"] == OUTCOME_UNATTRIBUTED
    assert r["winner"] is None


def test_survivors_without_holdout_is_pending_not_attributed():
    r = attribute([_bar(100, C0_len=100)])
    assert r["outcome"] == OUTCOME_PENDING_HOLDOUT
    assert r["winner"] is None, "no winner may be declared without a holdout"


def test_unique_survivor_confirmed_by_holdout_is_attributed():
    disc = [_bar(100, C0_len=100)]
    hold = [_bar(300, C0_len=300)]
    r = attribute(disc, hold)
    assert r["outcome"] == OUTCOME_ATTRIBUTED
    assert r["winner"] == "C0_len"


def test_survivor_failing_holdout_is_unattributed():
    disc = [_bar(100, C0_len=100)]
    hold = [_bar(300, C0_len=999)]
    r = attribute(disc, hold)
    assert r["outcome"] == OUTCOME_UNATTRIBUTED
    assert r["winner"] is None


# ── V2 path ────────────────────────────────────────────────────────────────────
def _v2_bar(tick_volume: int, c9: int) -> dict:
    return {"T": "x", "tick_volume": tick_volume, "candidates": {V2_CANDIDATE_ID: c9}}


def test_v2_below_min_bars_is_pending_not_attributed():
    bars = [_v2_bar(100, 100)] * (V2_MIN_HOLDOUT_BARS - 1)
    r = score_v2(bars)
    assert r["v2_outcome"] == OUTCOME_PENDING_HOLDOUT


def test_v2_all_exact_is_attributed():
    bars = [_v2_bar(100, 100), _v2_bar(200, 200), _v2_bar(300, 300)]
    assert score_v2(bars)["v2_outcome"] == OUTCOME_ATTRIBUTED_V2


def test_v2_single_mismatch_fails_the_whole_holdout():
    """The live result: 3 of 4 exact, one off by 29 -> UNATTRIBUTED_V2."""
    bars = [_v2_bar(5466, 5437), _v2_bar(3061, 3061), _v2_bar(3155, 3155), _v2_bar(2737, 2737)]
    r = score_v2(bars)
    assert r["v2_outcome"] == OUTCOME_UNATTRIBUTED_V2
    assert sum(1 for row in r["v2_table"] if row["exact"]) == 3


def test_v2_candidate_is_not_in_the_v1_frozen_list():
    """V1's UNATTRIBUTED must stay reproducible: C9 was added AFTER seeing discovery."""
    assert V2_CANDIDATE_ID not in CANDIDATES
    assert V2_CANDIDATE_ID not in FROZEN_CANDIDATE_IDS
    assert len(FROZEN_CANDIDATE_IDS) == 9
