"""Shared synthetic LONG plan for the slice-3 tests. Not a test module."""

from __future__ import annotations

from datetime import datetime, timedelta

from research.costs import MEASURED, ComponentCostModel

from semantics.execution.portfolio import admit
from semantics.execution.fill import fill
from semantics.execution.size import position_size
from semantics.market.levels import range_levels
from semantics.trading.entry import resting_entry
from semantics.trading.plan import trade_plan
from semantics.trading.stop import Stop
from semantics.trading.target import fixed_r_target
from semantics.trading.thesis import form_thesis
from semantics.types import Bias, OhlcBar

# Thesis: LOWER level 100 swept on bar 2, displacement bar 5 (open 102 -> close 110).
# Invalidation: 50% of 100 -> 110 = 105 (close strictly below). Origin = 102.
# Plan: entry 108 on retest bar 8, stop 98 (R = 10), TP1 118 (1R), TP2 128 (2R).
ORIGIN = 102.0
ENTRY_BAR = 8
T0 = datetime(2026, 9, 25, 20, 0)   # a Friday, broker-server time


def bar(index, open_, high, low, close, timestamp=None):
    return OhlcBar(open_, high, low, close, index, timestamp)


def thesis():
    _upper, lower = range_levels(
        120.0, 100.0, founding="m15_structural_range", formed_at=0, available_at=0,
        timeframe="M15", clock="htf_period",
    )
    made = form_thesis(
        bar(2, 103.0, 104.0, 99.0, 102.0), lower, bar(5, ORIGIN, 112.0, 101.0, 110.0),
        retrace_fraction=0.5, extension_fib=1.618, clock="htf_period",
    )
    assert made is not None and made.direction is Bias.LONG
    return made


def plan():
    th = thesis()
    entry = resting_entry(bar(ENTRY_BAR, 109.0, 109.5, 107.5, 108.0))
    stop = Stop("TRS-05", "test-stop", ENTRY_BAR, 98.0, "displacement", 0.0)
    targets = [
        fixed_r_target(108.0, 98.0, ordinal=1, r_multiple=1.0, direction=Bias.LONG, plan_bar=ENTRY_BAR,
                       intent="liq_sweep"),
        fixed_r_target(108.0, 98.0, ordinal=2, r_multiple=2.0, direction=Bias.LONG, plan_bar=ENTRY_BAR,
                       target_policy="fixed_r"),
    ]
    made = trade_plan(th, entry, stop, targets)
    assert made is not None and made.R == 10.0
    return made


def size(made=None, risk_fraction=0.01):
    return position_size(made or plan(), risk_fraction=risk_fraction, equity=100_000.0,
                         equity_basis="initial_capital")


def filled(made=None):
    made = made or plan()
    admission = admit(size(made), [], max_concurrent_positions=3, max_open_risk=0.05, bar=ENTRY_BAR)
    return made, fill(made.entry, admission)


def path(*ohlc, start=ENTRY_BAR + 1):
    """Bars after the fill, one hour apart from T0."""
    return [bar(start + i, *row, T0 + timedelta(hours=i + 1)) for i, row in enumerate(ohlc)]


def cost_model(*, swap_long=-0.5, source="SYNTHETIC"):
    return ComponentCostModel(
        half_spread=0.05, commission=0.04, entry_slippage=0.0, stop_slippage=0.09,
        swap_long_per_night=swap_long, swap_short_per_night=-0.4,
        instrument="XAUUSD", source=source, status=MEASURED,
    )
