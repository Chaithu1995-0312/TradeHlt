"""The precomputed-`break_events` path must be bit-identical to recomputing.

CH-v3-unified-market-structure-v1.

`find_active_order_block`, `find_active_breaker` and `find_active_mitigation_block` each call
`_find_break_events(window, k)` independently, so the identical scan ran THREE times per bar.
On a 47,275-bar corpus that measured at 208s of SMC work, of which ~142s was the duplicated
scan. The three functions (and their `*_distance` wrappers) now accept an optional precomputed
result.

`_find_break_events` is pure, so passing its own output back in is identical BY CONSTRUCTION —
but "by construction" is exactly the kind of reasoning that has been wrong here before, and the
optimisation sits directly upstream of a canonical feature (SMC block, vector indices 39-47).
So it is pinned empirically, on real-shaped data, across every position where a zone actually
exists rather than only where the answer is the trivial `0.0`.
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle  # noqa: E402
from features.smc.breaker import breaker_distance, find_active_breaker  # noqa: E402
from features.smc.mitigation import (  # noqa: E402
    find_active_mitigation_block,
    mitigation_block_distance,
)
from features.smc.order_block import (  # noqa: E402
    _find_break_events,
    find_active_order_block,
    order_block_distance,
)

K = 2
ATR = 4.0
WINDOW = 100

PAIRS = (
    (order_block_distance, find_active_order_block),
    (breaker_distance, find_active_breaker),
    (mitigation_block_distance, find_active_mitigation_block),
)


def _synthetic_bars(n: int = 600, seed: int = 3) -> list:
    """A random walk with realistic wick structure — enough breaks, origins and mitigations to
    exercise every branch, rather than a hand-built fixture that only hits the easy path."""
    rng = random.Random(seed)
    price = 1900.0
    t0 = datetime(2025, 1, 1)
    bars = []
    for i in range(n):
        price += rng.gauss(0, 2.5)
        bars.append(Candle(
            timestamp=t0 + timedelta(minutes=15 * i),
            open=price,
            high=price + abs(rng.gauss(0, 2)),
            low=price - abs(rng.gauss(0, 2)),
            close=price + rng.gauss(0, 1),
            volume=0.0,
            index=i,
        ))
    return bars


@pytest.fixture(scope="module")
def bars() -> list:
    return _synthetic_bars()


def test_precomputed_break_events_are_bit_identical(bars):
    """Every position, every family: distance floats equal and Zone objects equal."""
    compared = 0
    non_trivial = 0
    for end in range(5, len(bars)):
        window = bars[max(0, end - WINDOW):end]
        if len(window) < 3:
            continue
        events = _find_break_events(window, K)
        for dist_fn, zone_fn in PAIRS:
            canonical_d = dist_fn(window, K, ATR)
            memoized_d = dist_fn(window, K, ATR, events)
            canonical_z = zone_fn(window, K)
            memoized_z = zone_fn(window, K, events)
            assert canonical_d == memoized_d, (
                f"{dist_fn.__name__} diverged at end={end}: "
                f"{canonical_d!r} != {memoized_d!r}"
            )
            assert canonical_z == memoized_z, (
                f"{zone_fn.__name__} zone diverged at end={end}"
            )
            compared += 1
            if canonical_d != 0.0:
                non_trivial += 1

    assert compared > 1000, f"too few comparisons to be meaningful: {compared}"
    # Without this the test would pass trivially on a corpus where no zone is ever found —
    # the exact shape of vacuous enforcement E-001 exists to catch.
    assert non_trivial > 200, (
        f"only {non_trivial} comparisons had a non-zero distance; the fixture is not "
        "exercising real zone geometry"
    )


def test_default_argument_still_recomputes(bars):
    """Omitting the argument must not change behaviour for any existing caller.

    `FeaturePipeline.compute_smc_features` calls these positionally without the new parameter,
    and it produces canonical vector indices 39-47. This pins that the added parameter is
    genuinely optional rather than accidentally required.
    """
    window = bars[-WINDOW:]
    for dist_fn, zone_fn in PAIRS:
        assert dist_fn(window, K, ATR) == dist_fn(window, K, ATR, None)
        assert zone_fn(window, K) == zone_fn(window, K, None)


def test_wrong_events_would_change_the_answer(bars):
    """The parameter is load-bearing, not ignored.

    If `find_active_*` silently discarded the argument, the equality tests above would pass for
    the wrong reason. Feeding a deliberately WRONG event list must change at least one answer.
    """
    changed = 0
    for end in range(200, len(bars), 25):
        window = bars[max(0, end - WINDOW):end]
        if len(window) < 3:
            continue
        real = _find_break_events(window, K)
        if not real:
            continue
        wrong = real[:-1]  # drop the most recent break event
        for dist_fn, _ in PAIRS:
            if dist_fn(window, K, ATR, real) != dist_fn(window, K, ATR, wrong):
                changed += 1
    assert changed > 0, (
        "supplying a different break-event list changed nothing anywhere -- the parameter is "
        "being ignored and the equality tests above prove nothing"
    )
