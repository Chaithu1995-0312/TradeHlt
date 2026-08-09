"""M2 tests: falsification controls register and flow through the pipeline unmodified."""

from datetime import datetime, timedelta

import research.controls  # noqa: F401  (registers controls on import)
from config_layer.crt_engine_v2 import Candle
from research.costs import DEFAULT_COST_MODEL
from research.measurement.forward_walk import forward_walk
from research.measurement.metrics import EdgeAggregator
from research.registry import get_hypothesis


def _uptrend(n: int = 120, start: float = 100.0, step: float = 0.5, wick: float = 0.1):
    out, prev = [], start
    for i in range(n):
        o = prev
        c = o + step
        out.append(Candle(timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * i),
                           open=o, high=c + wick, low=o - wick, close=c, volume=1.0, index=i))
        prev = c
    return out


def _run(hyp, candles, *, warmup=25, max_forward=10, cost_model=DEFAULT_COST_MODEL):
    """Minimal stand-in for the M3 HypothesisRunner: detect -> forward_walk -> aggregate."""
    ctx = {"instrument": "TEST"}
    outcomes = []
    for i in range(warmup, len(candles)):
        for s in hyp.detect(candles[:i + 1], {}, ctx):
            future = candles[i + 1:i + 1 + max_forward]
            if future:
                outcomes.append(forward_walk(s, future, max_forward=max_forward))
    return EdgeAggregator().aggregate(hyp.name, ["TEST"], outcomes, cost_model=cost_model)


def test_controls_are_registered():
    names = {"random_uniform", "random_biased_70", "always_long"}
    for n in names:
        assert get_hypothesis(n).name == n


def test_always_long_profitable_on_uptrend():
    rep = _run(get_hypothesis("always_long"), _uptrend())
    assert rep.n > 0
    assert rep.expectancy_rr > 0          # NET — gate must clear a real, drift-driven bar
    assert rep.round_trip_bps == 12.0


def test_always_long_only_emits_longs():
    al = get_hypothesis("always_long")
    candles = _uptrend(60)
    dirs = {s.direction for i in range(25, len(candles)) for s in al.detect(candles[:i + 1], {}, {})}
    assert dirs == {"long"}


def test_random_bias_distribution_and_determinism():
    candles = _uptrend(400)
    biased = get_hypothesis("random_biased_70")

    def directions():
        return [s.direction for i in range(25, len(candles))
                for s in biased.detect(candles[:i + 1], {}, {"instrument": "TEST"})]

    d1 = directions()
    d2 = directions()
    assert d1 == d2                                   # deterministic given (seed, instrument, index)
    long_frac = d1.count("long") / len(d1)
    assert 0.6 < long_frac < 0.8                      # ~0.70 bias
