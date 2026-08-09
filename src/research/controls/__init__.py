"""Falsification controls — the platform's immune system.

Importing this package registers the controls so any hypothesis run is benchmarked
against them. Built BEFORE any real hypothesis (M2).
"""

from research.controls.always_long import AlwaysLong
from research.controls.random_baseline import RandomBaseline
from research.registry import register_hypothesis

# Parametrized null controls + the anti-drift control.
register_hypothesis(RandomBaseline(name="random_uniform", long_prob=0.5))
register_hypothesis(RandomBaseline(name="random_biased_70", long_prob=0.7))
register_hypothesis(AlwaysLong())

__all__ = ["RandomBaseline", "AlwaysLong"]
