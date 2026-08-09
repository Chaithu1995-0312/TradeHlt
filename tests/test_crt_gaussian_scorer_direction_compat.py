"""Regression: Phase-5 gate call site always passes direction= to the scorer duck-type.

Failure class (pre-existing since b34d6a8): CRTGaussianScorer.compute() rejected
``direction`` while CRTCalibratedScorer and HeuristicGaussianEngine accept it,
so ``--scorer static`` TypeError'd mid-backtest.

This test pins the no-op scorer's API compatibility without changing scoring math.
"""
from __future__ import annotations

import inspect

from runtime.backtest_v2 import CRTCalibratedScorer, CRTGaussianScorer


def test_noop_scorer_accepts_direction_kwarg():
    scorer = CRTGaussianScorer()
    # Exact call shape used by BacktestRunner.run (direction=_p5_dir)
    out = scorer.compute({"body_ratio": 0.5}, candle_idx=10, direction="long")
    assert out is None
    out_short = scorer.compute({"body_ratio": 0.5}, 11, direction="short")
    assert out_short is None


def test_noop_scorer_signature_includes_direction():
    sig = inspect.signature(CRTGaussianScorer.compute)
    assert "direction" in sig.parameters
    assert sig.parameters["direction"].default == "long"


def test_calibrated_scorer_signature_includes_direction():
    """Duck-type parity: both scorers must accept direction=."""
    sig = inspect.signature(CRTCalibratedScorer.compute)
    assert "direction" in sig.parameters


def test_direction_kwarg_does_not_typeerror_positional_candle_idx():
    scorer = CRTGaussianScorer()
    # Caller sometimes uses positional candle_idx then keyword direction
    assert scorer.compute({}, 0, direction="long") is None
