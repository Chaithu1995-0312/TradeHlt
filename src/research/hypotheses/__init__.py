"""Behavior hypotheses. Importing this package registers each one via its decorator.

Continuation and its opposite (mean reversion) ship together at M2 — the architecture
privileges neither.
"""

from research.hypotheses import expansion_breakout, mean_reversion  # noqa: F401  (register on import)
from research.hypotheses import spine_hypothesis  # noqa: F401  (registers the production-spine composite)
from research.hypotheses import compression_breakout  # noqa: F401  (Program-4b transition consumer)
from research.hypotheses import weekly_sweep_reversal  # noqa: F401  (Program-8 weekly-sweep consumer)

__all__ = ["expansion_breakout", "mean_reversion", "spine_hypothesis", "compression_breakout",
           "weekly_sweep_reversal"]
