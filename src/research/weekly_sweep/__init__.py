"""weekly_sweep — Program 8: weekly liquidity-sweep ontology (pure geometry, no-lookahead).

See `weekly_range.py` for the accumulation-range builder + sweep detector. Consumed by
`research.hypotheses.weekly_sweep_reversal.WeeklySweepReversal`.
"""

from research.weekly_sweep.weekly_range import (
    WeeklyRange,
    WeeklySweepEvent,
    current_week_range,
    detect_weekly_sweep,
    is_week_structurally_valid,
)

__all__ = [
    "WeeklyRange",
    "WeeklySweepEvent",
    "current_week_range",
    "detect_weekly_sweep",
    "is_week_structurally_valid",
]
