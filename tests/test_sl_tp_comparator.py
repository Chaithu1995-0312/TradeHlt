"""
tests/test_sl_tp_comparator.py — Unit tests for SLTPComparator.

Covers:
  Group A — Pure functions (derive_intent, compute_legacy_levels, simulate_exit)
  Group B — Aggregate metrics
  Group C — SLTPComparator.compare() end-to-end
  Group D — Winner determination logic
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from analytics.sl_tp_comparator import (
    derive_intent_from_features,
    compute_legacy_levels,
    simulate_exit,
    SLTPComparator,
    ComparisonReport,
    _aggregate_variant_results,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

_BASE_CFG = {
    "legacy_sl_atr_mult":          1.0,
    "legacy_tp_atr_mult_breakout": 2.0,
    "legacy_tp_atr_mult_pullback": 1.5,
    "legacy_tp_atr_mult_reversal": 1.0,
    "legacy_tp_atr_mult_sweep":    1.2,
    "primary_metric":              "expectancy_rr",
    "max_candles_per_trade":       50,
}


def _breakout_features(**ov):
    f = {
        "close": 100.0, "high": 102.0, "low": 98.0, "atr": 2.0,
        "body_ratio": 0.8, "disp_strength": 2.2,
        "sweep_detected": False, "double_sweep": False,
        "retest_depth": 0.1, "candles_since_retest": 10,
        "ema_fast": 99.5, "ema_slow": 98.5, "momentum_score": 0.7,
    }
    f.update(ov)
    return f


def _make_candles(n: int, base=100.0, step=0.0) -> list[dict]:
    """Generate n flat/trending candles."""
    candles = []
    price = base
    for i in range(n):
        price += step
        candles.append({
            "open": price - 0.1, "high": price + 0.5,
            "low": price - 0.5,  "close": price,
            "timestamp": f"2026-01-01T{i:02d}:00:00",
        })
    return candles


def _make_trade_record(
    entry_fill=100.0, direction="LONG",
    sl=98.0, tp1=102.0, tp2=104.0,
    pnl_rr_net=1.0, exit_reason="TP1",
    candle_open=0, candle_close=5,
    features=None,
) -> dict:
    f = features or _breakout_features()
    return {
        "trade_id":        "T001",
        "direction":       direction,
        "entry_price_fill":entry_fill,
        "entry_price_raw": entry_fill,
        "sl_price":        sl,
        "tp1_price":       tp1,
        "tp2_price":       tp2,
        "pnl_rr_net":      pnl_rr_net,
        "exit_reason":     exit_reason,
        "candle_open":     candle_open,
        "candle_close":    candle_close,
        "live_atr":        2.0,
        "features":        f,
    }


# ── Group A: Pure functions ───────────────────────────────────────────────────

class TestDeriveIntent:
    def test_liq_sweep_single(self):
        f = _breakout_features(sweep_detected=True)
        assert derive_intent_from_features(f, 1) == "LIQ_SWEEP"

    def test_liq_sweep_double(self):
        f = _breakout_features(double_sweep=True)
        assert derive_intent_from_features(f, 1) == "LIQ_SWEEP"

    def test_pullback(self):
        f = _breakout_features(retest_depth=0.5, candles_since_retest=3,
                                momentum_score=0.3, body_ratio=0.3, disp_strength=0.5,
                                sweep_detected=False, double_sweep=False)
        assert derive_intent_from_features(f, 1) == "PULLBACK"

    def test_breakout(self):
        f = _breakout_features(body_ratio=0.85, disp_strength=2.5,
                                sweep_detected=False, double_sweep=False,
                                retest_depth=0.1, candles_since_retest=10)
        assert derive_intent_from_features(f, 1) == "BREAKOUT"

    def test_reversal_long(self):
        # ema_fast < ema_slow + direction=1 → reversal
        f = _breakout_features(body_ratio=0.2, disp_strength=0.3,
                                sweep_detected=False, double_sweep=False,
                                ema_fast=98.0, ema_slow=100.0, retest_depth=0.0,
                                candles_since_retest=10, momentum_score=-0.1)
        assert derive_intent_from_features(f, 1) == "REVERSAL"

    def test_unknown(self):
        f = _breakout_features(body_ratio=0.1, disp_strength=0.3,
                                sweep_detected=False, double_sweep=False,
                                ema_fast=99.5, ema_slow=98.5,
                                retest_depth=0.1, candles_since_retest=10,
                                momentum_score=0.0)
        assert derive_intent_from_features(f, 1) == "UNKNOWN"


class TestComputeLegacyLevels:
    def test_long_breakout_formula(self):
        f = _breakout_features()  # breakout intent, close=100, atr=2
        result = compute_legacy_levels(100.0, 1, f, _BASE_CFG)
        # sl = close - 1.0*atr = 100 - 2 = 98
        # tp1 = entry + 2.0*atr = 100 + 4 = 104
        # tp2 = entry + 4.0*atr = 100 + 8 = 108
        assert result["sl"]  == pytest.approx(98.0)
        assert result["tp1"] == pytest.approx(104.0)
        assert result["tp2"] == pytest.approx(108.0)
        assert result["intent"] == "BREAKOUT"

    def test_short_breakout_formula(self):
        f = _breakout_features(ema_fast=101.0, ema_slow=99.0)  # breakout
        result = compute_legacy_levels(100.0, -1, f, _BASE_CFG)
        # sl = close + 1.0*atr = 100 + 2 = 102
        # tp1 = entry - 2.0*atr = 100 - 4 = 96
        assert result["sl"]  == pytest.approx(102.0)
        assert result["tp1"] == pytest.approx(96.0)
        assert result["tp2"] == pytest.approx(92.0)

    def test_rr_is_computed(self):
        f = _breakout_features()
        result = compute_legacy_levels(100.0, 1, f, _BASE_CFG)
        # risk_dist = |100 - 98| = 2; tp1_dist = |104 - 100| = 4; rr = 2.0
        assert result["rr"] == pytest.approx(2.0)

    def test_risk_dist_nonzero(self):
        f = _breakout_features()
        result = compute_legacy_levels(100.0, 1, f, _BASE_CFG)
        assert result["risk_dist"] > 0

    def test_pullback_uses_lower_tp_mult(self):
        f = _breakout_features(retest_depth=0.5, candles_since_retest=3,
                                momentum_score=0.3, body_ratio=0.3, disp_strength=0.5,
                                sweep_detected=False, double_sweep=False)
        result = compute_legacy_levels(100.0, 1, f, _BASE_CFG)
        # tp_mult = 1.5 for pullback; tp1 = entry + 1.5*atr = 103
        assert result["tp1"] == pytest.approx(103.0)
        assert result["intent"] == "PULLBACK"

    def test_sweep_uses_sweep_mult(self):
        f = _breakout_features(sweep_detected=True)
        result = compute_legacy_levels(100.0, 1, f, _BASE_CFG)
        # tp_mult = 1.2 for sweep; tp1 = entry + 1.2*atr = 102.4
        assert result["tp1"] == pytest.approx(102.4)

    def test_zero_atr_risk_dist_is_zero(self):
        f = _breakout_features(atr=0.0)
        result = compute_legacy_levels(100.0, 1, f, _BASE_CFG)
        assert result["risk_dist"] == 0.0
        assert result["rr"] == 0.0


class TestSimulateExit:
    def test_tp2_hit_long(self):
        # entry=100, sl=98, tp1=102, tp2=104 — candle goes to 105
        candles = [{"high": 105.0, "low": 99.0, "close": 104.5}]
        r = simulate_exit(100.0, 1, 98.0, 102.0, 104.0, candles)
        assert r["exit_reason"] == "TP2"
        assert r["realized_rr"] == pytest.approx(2.0)
        assert r["candles_held"] == 1

    def test_sl_hit_long(self):
        candles = [{"high": 100.5, "low": 97.0, "close": 97.5}]
        r = simulate_exit(100.0, 1, 98.0, 102.0, 104.0, candles)
        assert r["exit_reason"] == "SL"
        assert r["realized_rr"] < 0

    def test_tp1_hit_long(self):
        candles = [{"high": 102.5, "low": 99.0, "close": 102.0}]
        r = simulate_exit(100.0, 1, 98.0, 102.0, 104.0, candles)
        assert r["exit_reason"] == "TP1"
        assert r["realized_rr"] == pytest.approx(1.0)

    def test_tp2_priority_over_sl_same_candle(self):
        # Candle spans both SL and TP2 — TP2 should win (same as BacktestRunner)
        candles = [{"high": 105.0, "low": 97.0, "close": 101.0}]
        r = simulate_exit(100.0, 1, 98.0, 102.0, 104.0, candles)
        assert r["exit_reason"] == "TP2"

    def test_short_tp2_hit(self):
        # entry=100, direction=-1, sl=102, tp1=98, tp2=96 — candle dips to 95
        candles = [{"high": 101.0, "low": 95.0, "close": 96.0}]
        r = simulate_exit(100.0, -1, 102.0, 98.0, 96.0, candles)
        assert r["exit_reason"] == "TP2"

    def test_timeout_no_hit(self):
        # Flat candles that never hit SL or TP
        candles = _make_candles(5, base=100.0)  # high=100.5, low=99.5
        r = simulate_exit(100.0, 1, 95.0, 105.0, 110.0, candles, max_candles=5)
        assert r["exit_reason"] == "TIMEOUT"

    def test_empty_candles_returns_timeout(self):
        r = simulate_exit(100.0, 1, 98.0, 102.0, 104.0, [])
        assert r["exit_reason"] == "TIMEOUT"

    def test_candles_held_correct(self):
        # SL hit on 3rd candle
        candles = [
            {"high": 100.5, "low": 99.5, "close": 100.0},
            {"high": 100.5, "low": 99.5, "close": 100.0},
            {"high": 100.5, "low": 97.0, "close": 97.5},
        ]
        r = simulate_exit(100.0, 1, 98.0, 102.0, 104.0, candles)
        assert r["candles_held"] == 3


# ── Group B: Aggregate metrics ────────────────────────────────────────────────

class TestAggregateMetrics:
    def test_empty_returns_zeros(self):
        m = _aggregate_variant_results([])
        assert m["total_trades"] == 0
        assert m["win_rate"] == 0.0

    def test_all_wins(self):
        results = [
            {"exit_reason": "TP2", "realized_rr": 2.0, "candles_held": 3, "sl_dist_atr": 1.0},
            {"exit_reason": "TP1", "realized_rr": 1.0, "candles_held": 2, "sl_dist_atr": 1.0},
        ]
        m = _aggregate_variant_results(results)
        assert m["win_rate"] == pytest.approx(1.0)
        assert m["sl_rate"] == 0.0

    def test_all_losses(self):
        results = [
            {"exit_reason": "SL", "realized_rr": -1.0, "candles_held": 2, "sl_dist_atr": 1.0},
            {"exit_reason": "SL", "realized_rr": -1.0, "candles_held": 1, "sl_dist_atr": 1.0},
        ]
        m = _aggregate_variant_results(results)
        assert m["win_rate"] == pytest.approx(0.0)
        assert m["sl_rate"] == pytest.approx(1.0)

    def test_expectancy_rr_formula(self):
        # 1 win at +2R, 1 loss at -1R → expectancy = 0.5*2 + 0.5*(-1) = 0.5
        results = [
            {"exit_reason": "TP2", "realized_rr":  2.0, "candles_held": 3, "sl_dist_atr": 1.0},
            {"exit_reason": "SL",  "realized_rr": -1.0, "candles_held": 2, "sl_dist_atr": 1.0},
        ]
        m = _aggregate_variant_results(results)
        assert m["expectancy_rr"] == pytest.approx(0.5)

    def test_tp_rates_sum_to_1(self):
        results = [
            {"exit_reason": "TP2",     "realized_rr": 2.0, "candles_held": 3, "sl_dist_atr": 1.0},
            {"exit_reason": "TP1",     "realized_rr": 1.0, "candles_held": 2, "sl_dist_atr": 1.0},
            {"exit_reason": "SL",      "realized_rr":-1.0, "candles_held": 1, "sl_dist_atr": 1.0},
            {"exit_reason": "TIMEOUT", "realized_rr": 0.5, "candles_held": 5, "sl_dist_atr": 1.0},
        ]
        m = _aggregate_variant_results(results)
        total = m["tp2_rate"] + m["tp1_rate"] + m["sl_rate"] + m["timeout_rate"]
        assert total == pytest.approx(1.0)

    def test_max_drawdown_computed(self):
        # equity curve: +2, -1, -1, +2 → peak=2, min after=0 → dd=2
        results = [
            {"exit_reason": "TP2", "realized_rr":  2.0, "candles_held": 1, "sl_dist_atr": 1.0},
            {"exit_reason": "SL",  "realized_rr": -1.0, "candles_held": 1, "sl_dist_atr": 1.0},
            {"exit_reason": "SL",  "realized_rr": -1.0, "candles_held": 1, "sl_dist_atr": 1.0},
            {"exit_reason": "TP2", "realized_rr":  2.0, "candles_held": 1, "sl_dist_atr": 1.0},
        ]
        m = _aggregate_variant_results(results)
        assert m["max_drawdown_r"] == pytest.approx(2.0)


# ── Group C: SLTPComparator.compare() ────────────────────────────────────────

class TestSLTPComparator:
    def _comp(self, **overrides) -> SLTPComparator:
        cfg = {**_BASE_CFG, **overrides}
        return SLTPComparator(cfg)

    def test_empty_trades_returns_empty_report(self):
        comp = self._comp()
        report = comp.compare([], [])
        assert report.trades_compared == 0

    def test_single_trade_produces_report(self):
        comp = self._comp()
        rec = _make_trade_record(entry_fill=100.0)
        candles = _make_candles(60, base=100.0)
        report = comp.compare([rec], candles)
        assert report.trades_compared == 1
        assert "win_rate" in report.crt
        assert "win_rate" in report.legacy

    def test_per_trade_has_both_methods(self):
        comp = self._comp()
        rec = _make_trade_record()
        candles = _make_candles(60)
        report = comp.compare([rec], candles)
        assert len(report.per_trade) == 1
        pt = report.per_trade[0]
        assert "crt" in pt
        assert "legacy" in pt
        assert "sl" in pt["crt"]
        assert "sl" in pt["legacy"]

    def test_crt_levels_match_trade_record(self):
        comp = self._comp()
        rec = _make_trade_record(sl=98.0, tp1=102.0, tp2=104.0)
        candles = _make_candles(60)
        report = comp.compare([rec], candles)
        pt = report.per_trade[0]
        assert pt["crt"]["sl"]  == pytest.approx(98.0)
        assert pt["crt"]["tp1"] == pytest.approx(102.0)

    def test_legacy_sl_different_from_crt(self):
        """CRT sl=low-0.2*atr ≠ legacy sl=close-1.0*atr in general."""
        comp = self._comp()
        rec = _make_trade_record(sl=97.6)  # CRT sl = 98 - 0.2*2 = 97.6
        candles = _make_candles(60)
        report = comp.compare([rec], candles)
        pt = report.per_trade[0]
        # Legacy sl = close(100) - 1.0*atr(2) = 98.0
        assert pt["legacy"]["sl"] == pytest.approx(98.0)
        assert pt["crt"]["sl"] != pt["legacy"]["sl"]

    def test_report_has_winner(self):
        comp = self._comp()
        recs = [_make_trade_record() for _ in range(5)]
        candles = _make_candles(60)
        report = comp.compare(recs, candles)
        assert report.winner in ("crt", "legacy", "tie")

    def test_report_recommendation_is_string(self):
        comp = self._comp()
        rec = _make_trade_record()
        candles = _make_candles(60)
        report = comp.compare([rec], candles)
        assert isinstance(report.recommendation, str)
        assert len(report.recommendation) > 0

    def test_to_dict_serializable(self):
        import json
        comp = self._comp()
        rec = _make_trade_record()
        candles = _make_candles(60)
        report = comp.compare([rec], candles)
        d = report.to_dict()
        # Should be JSON-serializable
        json.dumps(d, default=str)

    def test_primary_metric_override(self):
        comp = self._comp(primary_metric="win_rate")
        assert comp._primary_metric == "win_rate"

    def test_multiple_trades(self):
        comp = self._comp()
        recs = [_make_trade_record(pnl_rr_net=1.0, exit_reason="TP1") for _ in range(10)]
        candles = _make_candles(200)
        report = comp.compare(recs, candles)
        assert report.trades_compared == 10
        assert report.crt["total_trades"] == 10
        assert report.legacy["total_trades"] == 10


# ── Group D: Winner determination ─────────────────────────────────────────────

class TestWinnerDetermination:
    def _comp(self):
        return SLTPComparator(_BASE_CFG)

    def test_crt_wins_when_higher_metric(self):
        comp = self._comp()
        crt    = {"expectancy_rr": 0.5, "avg_sl_dist_atr": 1.0, "tp2_rate": 0.3}
        legacy = {"expectancy_rr": 0.2, "avg_sl_dist_atr": 1.2, "tp2_rate": 0.2}
        winner, delta, rec = comp._determine_winner(crt, legacy)
        assert winner == "crt"
        assert delta > 0
        assert "CRT wins" in rec

    def test_legacy_wins_when_higher_metric(self):
        comp = self._comp()
        crt    = {"expectancy_rr": 0.1, "avg_sl_dist_atr": 1.0, "tp2_rate": 0.2}
        legacy = {"expectancy_rr": 0.6, "avg_sl_dist_atr": 0.9, "tp2_rate": 0.4}
        winner, delta, rec = comp._determine_winner(crt, legacy)
        assert winner == "legacy"
        assert delta > 0
        assert "Legacy wins" in rec

    def test_tie_when_delta_tiny(self):
        comp = self._comp()
        crt    = {"expectancy_rr": 0.50005, "avg_sl_dist_atr": 1.0, "tp2_rate": 0.3}
        legacy = {"expectancy_rr": 0.50000, "avg_sl_dist_atr": 1.0, "tp2_rate": 0.3}
        # delta = 0.00005 < 1e-4 → tie
        winner, delta, rec = comp._determine_winner(crt, legacy)
        assert winner == "tie"
        assert "tie" in rec.lower() or "equivalent" in rec.lower()

    def test_recommendation_mentions_legacy_reintroduction(self):
        comp = self._comp()
        crt    = {"expectancy_rr": 0.1, "avg_sl_dist_atr": 1.0, "tp2_rate": 0.2}
        legacy = {"expectancy_rr": 0.8, "avg_sl_dist_atr": 0.8, "tp2_rate": 0.5}
        _, _, rec = comp._determine_winner(crt, legacy)
        assert "legacy" in rec.lower() or "re-introduc" in rec.lower()
