"""stories — the Phase-A market-story library (4 active families).

Each family module exposes a list of StorySpec; ALL_STORIES aggregates them in a stable order.
"""
from __future__ import annotations

from research.synthetic.stories.breakout import BREAKOUT
from research.synthetic.stories.liquidity_reversal import LIQUIDITY_REVERSAL
from research.synthetic.stories.range_rotation import RANGE_ROTATION
from research.synthetic.stories.trend_continuation import TREND_CONTINUATION

ALL_STORIES = [
    *LIQUIDITY_REVERSAL,
    *TREND_CONTINUATION,
    *RANGE_ROTATION,
    *BREAKOUT,
]

__all__ = ["ALL_STORIES"]
