"""Unit tests for the Phase D exit-grid core (research.exit_grid).

Covers: determinism, planted-edge recovery (a real edge MUST surface as a lead — harness validity),
cost monotonicity (wider SL ⇒ lower achievable cost), incumbent-cell presence, and the ceiling /
regime classification. Pure — no spine, no data files.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from research.exit_grid import (
    Entry, INCUMBENT, ceilings, cell_metrics, min_achievable_cost, pool_cells,
    sweep_instrument, verdict, _cell_key,
)

SL_GRID = (0.5, 1.0, 2.0)
TP_GRID = (1.0, 2.0, 5.0)


class _C:
    __slots__ = ("high", "low", "close", "timestamp", "index")

    def __init__(self, high, low, close, ts, index):
        self.high, self.low, self.close, self.timestamp, self.index = high, low, close, ts, index


def _rising(n=400):
    """Monotonically rising series → a long entry always reaches TP and never SL (planted edge)."""
    t0 = datetime(2024, 1, 1)
    return [_C(100.0 + i + 0.5, 100.0 + i - 0.5, 100.0 + i, t0 + timedelta(minutes=15 * i), i)
            for i in range(n)]


def _long_entries(candles, atr=1.0, start=30, stop=360):
    return [Entry(entry_index=i, entry=candles[i].close, direction="long", atr=atr)
            for i in range(start, stop)]


def test_cell_metrics_basic():
    m = cell_metrics([1.0, -1.0, 2.0])
    assert m["n"] == 3 and m["win_rate"] == round(2 / 3, 4)
    assert m["max_dd_r"] >= 0.0
    assert cell_metrics([])["expectancy"] is None


def test_incumbent_cell_present():
    candles = _rising()
    grid = sweep_instrument(_long_entries(candles), candles, sl_grid=(1.0,), tp_grid=(2.0,),
                            max_forward=40, cost=_cost(), oos_split=0.3)
    assert _cell_key(*INCUMBENT) in grid


def _cost():
    from research.costs import CostModel
    return CostModel(12.0)


def test_planted_edge_surfaces_as_lead():
    candles = _rising()
    grid = sweep_instrument(_long_entries(candles), candles, sl_grid=SL_GRID, tp_grid=TP_GRID,
                            max_forward=40, cost=_cost(), oos_split=0.3)
    pooled = pool_cells({"X": grid}, SL_GRID, TP_GRID)
    vd = verdict(pooled)
    assert vd["has_lead"], "a monotonically favorable entry set must produce E>0 IS&OOS leads"
    assert vd["best_expectancy_oos"] is not None and vd["best_expectancy_oos"] > 0


def test_determinism():
    candles = _rising()
    ents = _long_entries(candles)
    a = sweep_instrument(ents, candles, sl_grid=SL_GRID, tp_grid=TP_GRID,
                         max_forward=40, cost=_cost(), oos_split=0.3)
    b = sweep_instrument(ents, candles, sl_grid=SL_GRID, tp_grid=TP_GRID,
                         max_forward=40, cost=_cost(), oos_split=0.3)
    assert a == b


def test_cost_monotonic_in_sl_width():
    recs = [{"entry": 100.0, "atr": 1.0, "max_favorable_excursion_r": 2.0,
             "rr_gross_intrabar": 0.0}]
    wide = min_achievable_cost(recs, 3.0, 12.0)
    tight = min_achievable_cost(recs, 0.5, 12.0)
    assert wide < tight    # wider stop ⇒ lower cost in R


def test_ceilings_regime_classification():
    recs = [{"entry": 100.0, "atr": 1.0, "max_favorable_excursion_r": 2.0}]
    alpha = ceilings(recs, {"expectancy_gross": 0.5}, widest_sl=3.0, bps=12.0)
    assert alpha["regime"] == "ALPHA" and alpha["structural_upper_bound"] > 0
    eng = ceilings(recs, {"expectancy_gross": -0.1}, widest_sl=3.0, bps=12.0)
    assert eng["regime"] == "ENGINEERING" and eng["structural_upper_bound"] <= 0
    # reality_gap = perfect − structural; perfect uses E[MFE]=2.0
    assert alpha["reality_gap"] is not None and alpha["reality_gap"] > 0
