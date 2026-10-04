"""M2 anti-bias test: continuation + mean-reversion register and run through one
identical pipeline, and the measurement core never branches on a hypothesis's behavior.
"""

from datetime import datetime, timedelta
from pathlib import Path

import research.controls   # noqa: F401  (register controls)
import research.hypotheses  # noqa: F401  (register hypotheses)
from config_layer.crt_engine_v2 import Candle
from research.measurement.forward_walk import forward_walk
from research.measurement.metrics import EdgeAggregator
from research.registry import HYPOTHESIS_REGISTRY, get_hypothesis

_SRC_RESEARCH = Path(__file__).resolve().parents[2] / "src" / "research"


def _series(n: int = 150, start: float = 100.0, step: float = 0.5, wick: float = 0.1):
    out, prev = [], start
    for i in range(n):
        o = prev
        c = o + step
        out.append(Candle(timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * i),
                           open=o, high=c + wick, low=o - wick, close=c, volume=1.0, index=i))
        prev = c
    return out


def _run(hyp, candles, *, warmup=30, max_forward=10):
    ctx = {"instrument": "TEST"}
    outcomes = []
    for i in range(warmup, len(candles)):
        for s in hyp.detect(candles[:i + 1], {}, ctx):
            future = candles[i + 1:i + 1 + max_forward]
            if future:
                outcomes.append(forward_walk(s, future, max_forward=max_forward))
    return EdgeAggregator().aggregate(hyp.name, ["TEST"], outcomes)


def test_both_behaviors_registered():
    assert "expansion_breakout" in HYPOTHESIS_REGISTRY
    assert "mean_reversion" in HYPOTHESIS_REGISTRY
    # opposite behaviors, distinct families — but both first-class plugins
    assert get_hypothesis("expansion_breakout").family == "continuation"
    assert get_hypothesis("mean_reversion").family == "mean_reversion"


def test_opposite_behaviors_run_through_identical_pipeline():
    candles = _series()
    # Same machinery, zero special-casing: both produce a valid EdgeReport.
    for name in ("expansion_breakout", "mean_reversion"):
        rep = _run(get_hypothesis(name), candles)
        assert rep.hypothesis == name
        assert rep.n > 0                       # both fire on the synthetic series
        assert rep.round_trip_bps == 12.0


def test_measurement_core_does_not_branch_on_family():
    # The behavior-blindness guarantee: the measurement pipeline must never inspect
    # a hypothesis's behavior label. (runner/qualification add their own guard at M3/M4.)
    for fname in ("measurement/forward_walk.py", "measurement/metrics.py", "costs.py"):
        src = (_SRC_RESEARCH / fname).read_text(encoding="utf-8")
        assert "family" not in src, f"{fname} must not reference .family"
