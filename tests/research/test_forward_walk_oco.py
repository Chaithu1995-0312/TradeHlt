"""Program 9 — forward_walk_oco: the both-sided stop-entry straddle walk (pre-reg D1–D3).

Pins the frozen execution decisions: reject-bar cancel (D1), no fill-bar TP + fill-bar SL
by wick touch (D2), TTL expiry -> None (D3), fill at the touched edge, post-fill
delegation to the UNCHANGED forward_walk (merged offsets), lookahead guard, determinism.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import dataclasses                                                       # noqa: E402

from config_layer.crt_engine_v2 import Candle                            # noqa: E402
from research.contracts import Signal                                    # noqa: E402
from research.measurement.forward_walk import forward_walk, forward_walk_oco  # noqa: E402

_T0 = datetime(2026, 1, 1)


def _bar(i: int, h: float, l: float, c: float | None = None) -> Candle:
    c = c if c is not None else (h + l) / 2.0
    return Candle(timestamp=_T0 + timedelta(minutes=5 * i), open=(h + l) / 2.0,
                  high=h, low=l, close=c, volume=1.0, index=i)


def _sig(**over) -> Signal:
    base = dict(instrument="TEST", timestamp=_T0, entry_index=10, direction="oco",
                entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0,
                meta={"box_high": 101.0, "box_low": 99.0})
    base.update(over)
    return Signal(**base)


# Box: high=101, low=99. Long fill => entry 101, SL 100, TP 103.
#                        Short fill => entry 99,  SL 100, TP 97.

# ── fills ────────────────────────────────────────────────────────────────────────────
def test_long_fill_at_box_high_then_tp():
    future = [
        _bar(11, 100.8, 100.2),          # pending, no touch
        _bar(12, 101.5, 100.3),          # touches box_high -> long fill at 101
        _bar(13, 103.2, 100.9),          # TP (103) wick touch
    ]
    oc = forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12)
    assert oc is not None
    assert oc.signal.direction == "long"
    assert oc.signal.entry == 101.0                       # the edge, not close/midpoint
    assert oc.signal.entry_index == 12                    # fill bar
    assert oc.signal.meta["bars_to_fill"] == 2
    assert oc.outcome == "TP_HIT"
    assert oc.rr_achieved == pytest.approx(2.0)
    assert oc.duration_candles == 2                       # fill bar + 1 delegated bar
    assert oc.time_to_tp == 2


def test_short_fill_at_box_low_then_tp():
    future = [
        _bar(11, 99.8, 98.7),            # touches box_low -> short fill at 99 (high < SL 100)
        _bar(12, 99.2, 96.8),            # TP (97) wick touch
    ]
    oc = forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12)
    assert oc is not None
    assert oc.signal.direction == "short" and oc.signal.entry == 99.0
    assert oc.outcome == "TP_HIT" and oc.time_to_tp == 2


# ── D1: reject bar ───────────────────────────────────────────────────────────────────
def test_both_edges_same_bar_cancels():
    future = [_bar(11, 101.4, 98.6)]     # touches BOTH edges -> order unknowable -> None
    assert forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12) is None


def test_reject_bar_checked_before_single_touch():
    # Even with later clean bars, the reject bar cancels the straddle outright.
    future = [_bar(11, 101.4, 98.6), _bar(12, 103.5, 100.5)]
    assert forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12) is None


# ── D3: TTL expiry ───────────────────────────────────────────────────────────────────
def test_ttl_expiry_returns_none():
    future = [_bar(11 + i, 100.6, 99.4) for i in range(20)]   # never touches an edge
    assert forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12) is None


def test_touch_after_ttl_does_not_fill():
    future = [_bar(11 + i, 100.6, 99.4) for i in range(12)] + [_bar(23, 101.5, 100.5)]
    assert forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12) is None


# ── D2: fill-bar semantics ───────────────────────────────────────────────────────────
def test_fill_bar_sl_honoured():
    # Fill long at 101; same bar's low touches SL (100) -> SL_HIT, duration 1.
    future = [_bar(11, 101.3, 99.9)]
    oc = forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12)
    assert oc is not None
    assert oc.outcome == "SL_HIT"
    assert oc.rr_achieved == pytest.approx(-1.0)
    assert oc.duration_candles == 1 and oc.time_to_failure == 1
    assert oc.time_to_tp is None


def test_fill_bar_tp_never_credited():
    # Fill bar reaches TP (103) intrabar but TP must NOT be credited on the fill bar;
    # flat bars afterwards -> TIMEOUT, with the fill-bar MFE still recorded.
    future = [_bar(11, 103.4, 100.6)] + [_bar(12 + i, 101.2, 100.8, c=101.0) for i in range(50)]
    oc = forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12)
    assert oc is not None
    assert oc.outcome == "TIMEOUT"                        # not TP_HIT
    assert oc.time_to_tp is None                          # never set from the fill bar
    assert oc.mfe == pytest.approx(2.4)                   # 103.4 - 101 (fill-bar excursion kept)
    assert oc.reached_1r is True


# ── delegation == unchanged forward_walk (offset by the fill bar) ────────────────────
def test_post_fill_delegation_matches_forward_walk():
    future = [
        _bar(11, 100.9, 100.1),                            # pending
        _bar(12, 101.2, 100.4),                            # fill long at 101 (no SL touch: low > 100)
        _bar(13, 102.0, 100.6),
        _bar(14, 101.8, 100.2),                            # SL (100)? low 100.2 no; drifts
        _bar(15, 102.9, 101.1),
        _bar(16, 103.1, 101.5),                            # TP touch
    ]
    oc = forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12)
    assert oc is not None

    resolved = dataclasses.replace(
        _sig(), direction="long", entry=101.0, entry_index=12,
        meta={**_sig().meta, "bars_to_fill": 2, "oco_resolved": True})
    ref = forward_walk(resolved, future[2:], max_forward=40)   # tail after the fill bar (bars 13..)

    assert oc.outcome == ref.outcome
    assert oc.rr_achieved == ref.rr_achieved
    assert oc.duration_candles == ref.duration_candles + 1
    assert oc.time_to_tp == (None if ref.time_to_tp is None else ref.time_to_tp + 1)
    # fill bar contributed no larger excursion here -> MFE/MAE equal the delegated walk's
    assert oc.mfe == pytest.approx(max(ref.mfe, 101.2 - 101.0))
    assert oc.mae == pytest.approx(min(ref.mae, 100.4 - 101.0))


# ── guards ───────────────────────────────────────────────────────────────────────────
def test_lookahead_guard_raises():
    future = [_bar(10, 101.5, 100.5)]                      # index == entry_index -> lookahead
    with pytest.raises(ValueError, match="lookahead"):
        forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12)


def test_non_oco_direction_raises():
    with pytest.raises(ValueError, match="direction"):
        forward_walk_oco(_sig(direction="long"), [_bar(11, 101.5, 100.5)],
                         max_forward=40, entry_ttl=12)


def test_missing_box_meta_raises():
    with pytest.raises(ValueError, match="box"):
        forward_walk_oco(_sig(meta={}), [_bar(11, 101.5, 100.5)],
                         max_forward=40, entry_ttl=12)


def test_degenerate_box_raises():
    with pytest.raises(ValueError, match="degenerate"):
        forward_walk_oco(_sig(meta={"box_high": 99.0, "box_low": 101.0}),
                         [_bar(11, 101.5, 100.5)], max_forward=40, entry_ttl=12)


def test_deterministic():
    future = [_bar(11, 100.9, 100.1), _bar(12, 101.2, 100.4), _bar(13, 103.2, 100.9)]
    a = forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12)
    b = forward_walk_oco(_sig(), future, max_forward=40, entry_ttl=12)
    assert a == b
