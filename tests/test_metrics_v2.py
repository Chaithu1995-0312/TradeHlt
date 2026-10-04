"""
test_metrics_v2.py — Metrics Layer V2.

Phase 0 (this file, first): the HOT-LOOP gate. Prove that the live within-trade
MFE/MAE tracking (`TradeJournal.observe_open_bar` → `TradePathStats`) computes the
SAME excursions as the frozen research oracle `research.measurement.forward_walk`
over the same bar range. This is the determinism/anti-lookahead guard for the only
change that touches the Trust-Layer backtest loop.

Later phases (Layer B aggregates, efficiency, goal wiring) append here.

Run: python -m pytest tests/test_metrics_v2.py -q
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle
from research.contracts import Signal
from research.measurement.forward_walk import forward_walk
from runtime.backtest_v2 import TradeJournal, TradeRecord

_BASE = datetime(2025, 1, 1, 0, 0, 0)


def _bar(index: int, high: float, low: float, close: float) -> Candle:
    return Candle(timestamp=_BASE + timedelta(minutes=15 * index),
                  open=close, high=high, low=low, close=close,
                  volume=1.0, index=index)


def _live_path(entry: float, direction: str, bars: list[Candle]):
    """Drive observe_open_bar over `bars` exactly as the candle loop would.
    Journal built via __new__ — observe_open_bar only reads self.open_trade."""
    rec = TradeRecord(trade_id="t", instrument="X", direction=direction,
                      entry_price_raw=entry, sl_price=0.0, tp1_price=0.0, tp2_price=0.0)
    j = TradeJournal.__new__(TradeJournal)
    j.open_trade = rec
    for b in bars:
        j.observe_open_bar(b)
    return rec.path


def _signal(entry: float, direction: str) -> Signal:
    # risk_distance = 2.0, reward_distance = 3.0 (atr=1.0). entry_index=0.
    return Signal(instrument="X", timestamp=_BASE, entry_index=0, direction=direction,
                  entry=entry, sl_atr_mult=2.0, tp_atr_mult=3.0, atr=1.0)


def _assert_matches_oracle(entry: float, direction: str, future: list[Candle]):
    """forward_walk is the oracle: run it, then observe the SAME bars it consumed
    (bars[:duration], which includes the exit bar) and assert MFE/MAE are identical."""
    fw_dir = "long" if direction == "LONG" else "short"
    out = forward_walk(_signal(entry, fw_dir), future,
                       max_forward=len(future), exit_model="intrabar_fixed")
    observed = future[: out.duration_candles]
    p = _live_path(entry, direction, observed)
    assert p.mfe_price == pytest.approx(out.mfe), \
        f"MFE mismatch: live={p.mfe_price} oracle={out.mfe} ({direction})"
    assert p.mae_price == pytest.approx(out.mae), \
        f"MAE mismatch: live={p.mae_price} oracle={out.mae} ({direction})"
    return out, p


def test_long_tp_hit_matches_oracle():
    # rises into TP (entry 100, tp=103) on bar 2; MFE includes the exit bar.
    future = [_bar(1, high=101.0, low=99.5, close=100.5),
              _bar(2, high=103.5, low=100.0, close=103.2)]
    out, p = _assert_matches_oracle(100.0, "LONG", future)
    assert out.outcome == "TP_HIT"
    assert p.bars_to_peak == 2          # MFE set on the exit bar


def test_long_sl_hit_matches_oracle():
    # dips to SL (sl=98) on bar 2 after a small favorable poke on bar 1.
    future = [_bar(1, high=100.8, low=99.6, close=100.1),
              _bar(2, high=100.2, low=97.5, close=97.8)]
    out, p = _assert_matches_oracle(100.0, "LONG", future)
    assert out.outcome == "SL_HIT"
    assert p.mae_price < 0


def test_short_tp_hit_matches_oracle():
    # short entry 100, tp=97; falls into TP on bar 2.
    future = [_bar(1, high=100.4, low=99.2, close=99.6),
              _bar(2, high=100.0, low=96.5, close=96.8)]
    out, p = _assert_matches_oracle(100.0, "SHORT", future)
    assert out.outcome == "TP_HIT"
    assert p.mfe_price > 0


def test_timeout_matches_oracle():
    # never reaches SL(98)/TP(103) within the window → TIMEOUT; MFE/MAE span all bars.
    future = [_bar(1, high=101.0, low=99.0, close=100.2),
              _bar(2, high=101.5, low=99.3, close=100.8),
              _bar(3, high=100.9, low=99.1, close=100.0)]
    out, p = _assert_matches_oracle(100.0, "LONG", future)
    assert out.outcome == "TIMEOUT"
    assert p.bars_observed == out.duration_candles


def test_observe_excludes_entry_bar_semantics():
    # Sanity: observing zero post-entry bars yields a flat (no-excursion) path,
    # mirroring forward_walk receiving an empty `future`.
    p = _live_path(100.0, "LONG", [])
    assert p.mfe_price == 0.0 and p.mae_price == 0.0 and p.bars_observed == 0


# ════════════════════════════════════════════════════════════════════════════
# Phase 1+2 — Layer B aggregates + efficiency triad
# ════════════════════════════════════════════════════════════════════════════
from runtime.backtest_v2 import (   # noqa: E402
    BacktestMetrics, MetricsEngine, TradePathStats,
    _planned_rr, _top_n_contribution_pct, _v2_mean, _v2_percentile,
)


def _mk_trade(rr_net, *, entry=100.0, sl=98.0, tp1=104.0, direction="LONG",
              session="LONDON", dur=10, capture=0.5, giveback=0.5,
              time_eff=0.4, adv_eff=0.33, mfe_rr=1.5, mae_rr=-0.5, btp=4):
    t = TradeRecord(trade_id="t", instrument="X", direction=direction,
                    entry_price_raw=entry, sl_price=sl, tp1_price=tp1, tp2_price=tp1)
    t.pnl_rr_net = rr_net
    t.session = session
    t.candle_open, t.candle_close = 0, dur
    t.path = TradePathStats(
        mfe_price=3.0, mae_price=-1.0, bars_to_peak=btp, bars_observed=dur,
        mfe_rr=mfe_rr, mae_rr=mae_rr, capture_ratio=capture, giveback=giveback,
        time_efficiency=time_eff, adverse_efficiency=adv_eff,
    )
    return t


def test_planned_rr_direction_agnostic_and_guarded():
    long_t = _mk_trade(1.0, entry=100, sl=98, tp1=104)     # reward 4 / risk 2 = 2.0
    short_t = _mk_trade(1.0, direction="SHORT", entry=100, sl=102, tp1=94)  # 6/2 = 3.0
    assert _planned_rr(long_t) == pytest.approx(2.0)
    assert _planned_rr(short_t) == pytest.approx(3.0)
    degenerate = _mk_trade(1.0, entry=100, sl=100, tp1=104)  # risk 0 → None
    assert _planned_rr(degenerate) is None


def test_v2_percentile_linear_interpolation():
    assert _v2_percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert _v2_percentile([10], 90) == 10.0
    assert _v2_percentile([], 50) is None
    assert _v2_mean([]) is None


def test_top_n_contribution():
    assert _top_n_contribution_pct([5, 4, 3, 2, 1, 10], 5) == pytest.approx(
        (10 + 5 + 4 + 3 + 2) / 25)
    assert _top_n_contribution_pct([-1, -2], 5) is None      # no winners → None


def test_metrics_v2_block_shapes_and_values():
    eng = MetricsEngine("X")
    m = BacktestMetrics(instrument="X")
    m.trades_per_week, m.trades_per_month = 2.0, 8.0
    m.distribution = {}
    trades = [_mk_trade(2.0, session="LONDON"),
              _mk_trade(-1.0, session="ASIA"),
              _mk_trade(3.0, session="LONDON")]
    eng._metrics_v2_block(m, trades)
    b = m.distribution["metrics_v2"]
    assert b["rr"]["avg_realized_rr"] == pytest.approx((2 - 1 + 3) / 3)
    assert b["rr"]["avg_planned_rr"] == pytest.approx(2.0)     # 4/2 for every trade
    assert b["rr"]["median_rr"] == pytest.approx(2.0)
    assert b["concentration"]["largest_winner_rr"] == 3.0
    assert b["concentration"]["largest_loser_rr"] == -1.0
    assert b["concentration"]["top5_win_contribution_pct"] == pytest.approx(1.0)
    assert b["distribution"]["trades_per_session"] == {"LONDON": 2, "ASIA": 1}
    assert b["distribution"]["median_duration"] == 10
    assert b["survival"]["median_capture_ratio"] == pytest.approx(0.5)
    assert b["efficiency"]["median_time_efficiency"] == pytest.approx(0.4)
    assert b["efficiency"]["median_adverse_efficiency"] == pytest.approx(0.33)


def test_metrics_v2_block_empty_is_noop():
    eng = MetricsEngine("X")
    m = BacktestMetrics(instrument="X")
    m.distribution = {}
    eng._metrics_v2_block(m, [])
    assert "metrics_v2" not in m.distribution


# ════════════════════════════════════════════════════════════════════════════
# Phase 4 — Metrics Oracle V2 parity (production block == independent recompute)
# ════════════════════════════════════════════════════════════════════════════
from analytics import metrics_oracle as mo   # noqa: E402


def test_oracle_v2_parity_with_production_block():
    eng = MetricsEngine("X")
    m = BacktestMetrics(instrument="X")
    m.trades_per_week, m.trades_per_month = 1.0, 4.0
    m.distribution = {}
    # Varied RR and varied geometry so percentiles / planned-RR are non-trivial.
    trades = [
        _mk_trade(2.5,  entry=100, sl=98,  tp1=105),   # planned 5/2 = 2.5
        _mk_trade(-1.0, entry=200, sl=196, tp1=210),   # planned 10/4 = 2.5
        _mk_trade(0.7,  entry=50,  sl=49,  tp1=53),    # planned 3/1 = 3.0
        _mk_trade(4.0,  entry=10,  sl=9.5, tp1=12),    # planned 2/0.5 = 4.0
        _mk_trade(-0.4, entry=100, sl=97,  tp1=109),   # planned 9/3 = 3.0
    ]
    eng._metrics_v2_block(m, trades)
    b = m.distribution["metrics_v2"]

    rrs = [t.pnl_rr_net for t in trades]
    geo = [(t.entry_price_raw, t.sl_price, t.tp1_price) for t in trades]

    assert b["rr"]["avg_realized_rr"] == pytest.approx(mo.expectancy_mean(rrs), abs=1e-6)
    assert b["rr"]["avg_planned_rr"] == pytest.approx(mo.avg_planned_rr(geo), abs=1e-6)
    assert b["rr"]["median_rr"] == pytest.approx(mo.percentile(rrs, 50), abs=1e-6)
    assert b["rr"]["rr_p10"] == pytest.approx(mo.percentile(rrs, 10), abs=1e-6)
    assert b["rr"]["rr_p90"] == pytest.approx(mo.percentile(rrs, 90), abs=1e-6)
    assert b["concentration"]["top5_win_contribution_pct"] == pytest.approx(
        mo.top_n_contribution(rrs, 5), abs=1e-6)


def test_oracle_v2_percentile_matches_production_helper():
    # The two independent percentile impls must agree across a range of p.
    sample = [3.0, -1.0, 2.5, 0.0, 7.2, -4.1, 1.1]
    for p in (0, 10, 25, 50, 75, 90, 100):
        assert mo.percentile(sample, p) == pytest.approx(_v2_percentile(sample, p), abs=1e-9)


# ════════════════════════════════════════════════════════════════════════════
# Phase 3 — per-symbol attribution (multi-instrument aggregate)
# ════════════════════════════════════════════════════════════════════════════
import json as _json   # noqa: E402

from runtime.backtest_v2 import MultiInstrumentRunner   # noqa: E402


def _sym_metrics(instrument, *, trades, wins, losses, pnl_net, pf, dd):
    m = BacktestMetrics(instrument=instrument)
    m.approved_trades = trades
    m.wins, m.losses = wins, losses
    m.total_pnl_rr_net = pnl_net
    m.profit_factor = pf
    m.max_drawdown_pct = dd
    return m


def test_symbol_attribution_surfaces_concentration(tmp_path):
    # 30 trades, but 29 on BTC and 1 on ETH — the classic hidden concentration.
    btc = _sym_metrics("BTCUSDT", trades=29, wins=15, losses=14, pnl_net=4.0, pf=1.1, dd=0.08)
    eth = _sym_metrics("ETHUSDT", trades=1, wins=0, losses=1, pnl_net=-1.0, pf=0.0, dd=0.01)
    r = MultiInstrumentRunner.__new__(MultiInstrumentRunner)
    r.output_dir = tmp_path
    r._write_aggregate([btc, eth])

    agg = _json.loads((tmp_path / "aggregate_summary.json").read_text())
    assert agg["trades_per_symbol"] == {"BTCUSDT": 29, "ETHUSDT": 1}
    sa = agg["symbol_attribution"]
    assert sa["BTCUSDT"]["trades_pct"] == pytest.approx(29 / 30, abs=1e-4)
    assert sa["ETHUSDT"]["trades_pct"] == pytest.approx(1 / 30, abs=1e-4)
    assert sa["BTCUSDT"]["expectancy_rr"] == pytest.approx(4.0 / 29, abs=1e-6)
    assert sa["ETHUSDT"]["profit_factor"] == 0.0


# ════════════════════════════════════════════════════════════════════════════
# Phase A (Plan 3) — Metrics Oracle V3: efficiency / attribution / concentration
# ════════════════════════════════════════════════════════════════════════════
def test_oracle_v3_efficiency_formulas():
    assert mo.capture_ratio(1.5, 3.0) == pytest.approx(0.5)
    assert mo.giveback(1.5, 3.0) == pytest.approx(0.5)
    assert mo.time_efficiency(4, 10) == pytest.approx(0.4)
    assert mo.adverse_efficiency(-0.5, 1.5) == pytest.approx(1 / 3)
    # guards → None (never div-by-zero)
    assert mo.capture_ratio(1.0, 0.0) is None
    assert mo.giveback(1.0, 0.0) is None
    assert mo.time_efficiency(4, 0) is None
    assert mo.adverse_efficiency(-0.5, 0.0) is None


def test_oracle_v3_concentration_extras():
    rr = [2.0, -1.0, 3.0, -0.5]
    assert mo.largest_winner(rr) == 3.0
    assert mo.largest_loser(rr) == -1.0
    assert mo.largest_winner([-1.0, -2.0]) == 0.0      # no winners
    assert mo.largest_loser([1.0, 2.0]) == 0.0         # no losers


def test_oracle_v3_symbol_attribution():
    by_symbol = {"BTCUSDT": [2.0, -1.0, 3.0], "ETHUSDT": [-1.0]}
    sa = mo.symbol_attribution(by_symbol)
    assert sa["BTCUSDT"]["trades"] == 3
    assert sa["BTCUSDT"]["expectancy_rr"] == pytest.approx((2 - 1 + 3) / 3)
    assert sa["ETHUSDT"]["expectancy_rr"] == pytest.approx(-1.0)
    assert sa["ETHUSDT"]["profit_factor"] == pytest.approx(0.0)   # no winners


def test_oracle_v3_block_parity_efficiency_survival():
    # Production _metrics_v2_block survival/efficiency MEDIANS must equal the
    # independent oracle.percentile over the same per-trade path values.
    eng = MetricsEngine("X")
    m = BacktestMetrics(instrument="X")
    m.trades_per_week, m.trades_per_month = 1.0, 4.0
    m.distribution = {}
    trades = [
        _mk_trade(2.0, capture=0.6, giveback=0.4, time_eff=0.2, adv_eff=0.3, mfe_rr=2.0, mae_rr=-0.4),
        _mk_trade(-1.0, capture=0.1, giveback=0.9, time_eff=0.8, adv_eff=0.9, mfe_rr=0.5, mae_rr=-1.0),
        _mk_trade(1.0, capture=0.5, giveback=0.5, time_eff=0.5, adv_eff=0.5, mfe_rr=1.2, mae_rr=-0.6),
    ]
    eng._metrics_v2_block(m, trades)
    b = m.distribution["metrics_v2"]
    caps = [t.path.capture_ratio for t in trades]
    gbs = [t.path.giveback for t in trades]
    teff = [t.path.time_efficiency for t in trades]
    mfe_rrs = [t.path.mfe_rr for t in trades]
    assert b["survival"]["median_capture_ratio"] == pytest.approx(mo.percentile(caps, 50), abs=1e-6)
    assert b["survival"]["median_giveback"] == pytest.approx(mo.percentile(gbs, 50), abs=1e-6)
    assert b["survival"]["mfe_rr_p90"] == pytest.approx(mo.percentile(mfe_rrs, 90), abs=1e-6)
    assert b["efficiency"]["median_time_efficiency"] == pytest.approx(mo.percentile(teff, 50), abs=1e-6)
