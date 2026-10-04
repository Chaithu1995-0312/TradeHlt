"""features.level_lifecycle — the one MKT-L01 lifecycle implementation (LevelBook)."""

from __future__ import annotations

import numpy as np

from features.level_lifecycle import LOWER, UPPER, LevelBook, swing_level_sweeps


def test_a_level_is_swept_once_then_consumed():
    book = LevelBook()
    key = book.add(110.0, UPPER, formed_at=0, available_at=0)
    assert book.step(0, 111.0, 99.0, 105.0).swept == (key,)
    assert book.step(1, 112.0, 104.0, 106.0).swept == ()        # SWEPT levels are not tested again
    assert book.ended[key] == ("SWEPT", 0)


def test_close_beyond_breaks_and_a_close_at_the_level_keeps_it_active():
    book = LevelBook()
    up = book.add(110.0, UPPER, formed_at=0, available_at=0)
    lo = book.add(90.0, LOWER, formed_at=0, available_at=0)
    r0 = book.step(0, 111.0, 95.0, 110.0)                        # pierce, close AT the level
    assert r0.swept == () and r0.broken == () and up not in book.ended
    r1 = book.step(1, 112.0, 95.0, 111.0)                        # close beyond -> BROKEN
    assert r1.broken == (up,) and book.ended[up] == ("BROKEN", 1)
    assert lo not in book.ended


def test_levels_wait_for_availability_and_two_sides_on_one_bar_are_two_events():
    book = LevelBook()
    up = book.add(110.0, UPPER, formed_at=0, available_at=0)
    lo = book.add(90.0, LOWER, formed_at=1, available_at=2)
    assert book.step(1, 105.0, 89.0, 100.0).swept == ()          # 90 not available on bar 1
    both = book.step(2, 111.0, 89.0, 100.0)
    assert set(both.swept) == {up, lo} and both.sides(book) == {UPPER, LOWER}


def test_older_active_level_is_still_sweepable():
    book = LevelBook()
    old = book.add(110.0, UPPER, formed_at=0, available_at=2)
    new = book.add(103.0, UPPER, formed_at=8, available_at=10)
    r = book.step(11, 111.0, 100.5, 108.0)
    assert r.swept == (old,) and r.broken == (new,)


def test_swing_level_sweeps_match_the_semantics_walker():
    from semantics.market.events import level_lifecycle
    from semantics.market.levels import swing_levels
    from semantics.types import OhlcBar

    rng = np.random.default_rng(7)
    c = 100 + np.cumsum(rng.normal(0, 1, 400))
    h = c + rng.uniform(0.1, 1.5, 400)
    lo = c - rng.uniform(0.1, 1.5, 400)
    o = c + rng.normal(0, 0.3, 400)
    levels = swing_levels(h, lo, k=2)
    life = level_lifecycle(levels, [OhlcBar(o[i], h[i], lo[i], c[i], i) for i in range(400)])
    sh = np.zeros(400)
    sl = np.zeros(400)
    for lvl in levels:
        (sh if lvl.side.value == UPPER else sl)[lvl.available_at] = 1
    up, down = swing_level_sweeps(h, lo, c, sh, sl, k=2)
    assert any(up) and any(down)
    for i, evs in enumerate(life.events):
        sides = {e.side.value for e in evs}
        assert (UPPER in sides) == bool(up[i]) and (LOWER in sides) == bool(down[i])
