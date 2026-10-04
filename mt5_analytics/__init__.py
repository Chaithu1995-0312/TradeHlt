"""
mt5_analytics — MT5-first post-trade analytics & reporting subsystem.

A separate, disposable intelligence layer beside Tradelatest. It consumes MT5's
executed history (deals / orders / candles) read-only and produces position-centric
analytics, reports and a dashboard. It NEVER owns balances, positions, equity or
trade state — MT5 is the sole financial truth.

Doctrine: MT5-first · position-centric · idempotent · replayable · verifiable ·
schema-stable. Kernel doctrine: *position reconstruction is sacred; everything else
is disposable.*

This package lives at the repo root (paralleling multi_llm/ and flow_context/) and
reuses proven engines from `src/`. The path bootstrap below mirrors
`src/inout/mt5_candle_fetcher.py:42` so `from utils.* import …` / `from research.*
import …` resolve regardless of how the process is launched.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__all__ = ["__version__"]
__version__ = "0.1.0"
