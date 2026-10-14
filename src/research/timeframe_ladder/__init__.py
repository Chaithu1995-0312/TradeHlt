"""Program 12 timeframe ladder — research only.

Slice 1 certifies the projector (`parity`). Slice 2 walks projected H1/H4
through a research clone (`run`). This package must not call CandleLoader,
admit_csv_path, or declare_in_process, and must not load native XAUUSD HTF
as the ladder population. `run` is not imported here, so importing the package
does not import the backtest stack.
"""

from research.timeframe_ladder.parity import (  # noqa: F401
    DECLARED_PARENT_END,
    DECLARED_PARENT_N,
    DECLARED_PARENT_PATH,
    DECLARED_PARENT_START,
    compare_projected_vs_native,
    is_daily_open_slot,
    load_ohlcv_csv,
    project,
)

__all__ = [
    "DECLARED_PARENT_END",
    "DECLARED_PARENT_N",
    "DECLARED_PARENT_PATH",
    "DECLARED_PARENT_START",
    "compare_projected_vs_native",
    "is_daily_open_slot",
    "load_ohlcv_csv",
    "project",
]
