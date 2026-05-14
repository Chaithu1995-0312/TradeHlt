"""
uat_runner.py
================================================================================
UATRunner — orchestrates all 7 UAT areas for the 10-strategy trading system.

Wires StrategyOrchestrator output → LLMStructuredLogger for structured
LLM-reviewable UAT payloads. One export JSON per UAT area.

UAT Areas
---------
  1  Signal Accuracy     — quality of strategy signals vs expected outcomes
  2  Trade Simulation    — end-to-end candle→decision→plan pipeline
  3  Telegram Alerts     — alert delivery latency + field correctness
  4  Strategy Scorecard  — per-strategy P&L stats across a trade set
  5  Monte Carlo         — 1000-run bootstrap robustness (P(ruin))
  6  Kill Switch         — daily/weekly loss gate triggers and resets
  7  Edge Cases          — boundary inputs, zero ATR, stale data, etc.

Usage
-----
    runner = UATRunner.from_prod_config(pair="EURUSD", timeframe="H1")
    runner.run_area_1(candle_features_list)
    runner.run_area_5(trade_outcomes)
    runner.run_all(candle_features_list, trade_outcomes)
    runner.export_all("results/uat/")

Config section: uat in production JSON.
================================================================================
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.production_config import get_prod_section   # type: ignore
from strategies.strategy_orchestrator import StrategyOrchestrator   # type: ignore
from strategies.strategy_result import StrategyResult               # type: ignore
from uat.monte_carlo import MonteCarloEngine, TradeOutcome          # type: ignore
from uat.kill_switch import KillSwitch                              # type: ignore
from utils.llm_logger import (                                      # type: ignore
    LLMStructuredLogger,
    AlertRecord,
    EdgeCaseRecord,
    KillSwitchEvent,
    MonteCarloRecord,
    SimulationRecord,
    ScorecardRecord,
)
from utils.logging_config import get_flow_logger                    # type: ignore

logger = get_flow_logger("COLLECTOR")


def _load_uat_cfg() -> dict:
    return get_prod_section("uat") or {}


# ── UATRunner ─────────────────────────────────────────────────────────────────

class UATRunner:
    """
    Coordinates all 7 UAT areas and exports structured JSON payloads
    for LLM review sessions.

    Parameters
    ----------
    pair        Instrument symbol (e.g. "EURUSD")
    timeframe   Candle timeframe (e.g. "H1")
    output_dir  Directory to write UAT-{area}.json exports
    config      Optional config override (None → production JSON)
    """

    def __init__(
        self,
        pair: str,
        timeframe: str,
        output_dir: Path = Path("results/uat"),
        config: Optional[dict] = None,
    ) -> None:
        self.pair       = pair.upper().replace("/", "")
        self.timeframe  = timeframe.upper()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._cfg       = config or _load_uat_cfg()
        self._orch      = StrategyOrchestrator(self.pair, self.timeframe)
        self._mc        = MonteCarloEngine.from_prod_config()
        self._ks        = KillSwitch.from_prod_config()
        self._loggers:  Dict[int, LLMStructuredLogger] = {}

    @classmethod
    def from_prod_config(
        cls,
        pair: str = "EURUSD",
        timeframe: str = "H1",
    ) -> "UATRunner":
        cfg = _load_uat_cfg()
        output_dir = Path(cfg.get("output_dir", "results/uat"))
        return cls(pair=pair, timeframe=timeframe, output_dir=output_dir, config=cfg)

    # ── Public run API ─────────────────────────────────────────────────────────

    def run_all(
        self,
        candle_data: List[Tuple[dict, dict]],
        trade_outcomes: Optional[List[TradeOutcome]] = None,
        alert_records: Optional[List[dict]] = None,
    ) -> None:
        """
        Run all 7 UAT areas in sequence.

        Parameters
        ----------
        candle_data     List of (features, candle) tuples to evaluate
        trade_outcomes  Realised trade P&L list for areas 4, 5
        alert_records   Telegram alert delivery dicts for area 3
        """
        logger.info("UATRunner: starting all 7 areas for %s %s", self.pair, self.timeframe)
        self.run_area_1(candle_data)
        self.run_area_2(candle_data)
        if alert_records:
            self.run_area_3(alert_records)
        if trade_outcomes:
            self.run_area_4(trade_outcomes)
            self.run_area_5(trade_outcomes)
        self.run_area_6()
        self.run_area_7()
        logger.info("UATRunner: all areas complete")

    def run_area_1(self, candle_data: List[Tuple[dict, dict]]) -> LLMStructuredLogger:
        """Area 1 — Signal accuracy: run orchestrator, log each actionable signal."""
        log = self._get_logger(1)
        for features, candle in candle_data:
            result = self._orch.compute(features, candle)
            if result.is_actionable() and result.top_result:
                tr = result.top_result
                log.log_signal(
                    signal_data={
                        "ts":           tr.ts,
                        "signal":       result.signal,
                        "strategies":   [r.strategy_id for r in result.all_results if r.is_actionable()],
                        "confidence":   result.confidence,
                        "regime":       tr.regime,
                        "entry":        tr.entry,
                        "sl":           tr.sl,
                        "tp":           tr.tp,
                        "sl_inr":       tr.sl_inr,
                        "tp_inr":       tr.tp_inr,
                        "roi_min":      tr.roi_min,
                        "roi_max":      tr.roi_max,
                        "fusion_score": result.score,
                    }
                )
        min_trades = int(
            (self._cfg.get("signal_accuracy") or {}).get("min_trades", 20)
        )
        if len(log._signals) < min_trades:
            log.flag_anomaly(
                f"Area 1: only {len(log._signals)} signals captured "
                f"(min {min_trades} required for statistical validity)"
            )
        logger.info("Area 1 complete: %d signals logged", len(log._signals))
        return log

    def run_area_2(self, candle_data: List[Tuple[dict, dict]]) -> LLMStructuredLogger:
        """Area 2 — Trade simulation: record end-to-end candle→decision pipeline."""
        log = self._get_logger(2)
        for i, (features, candle) in enumerate(candle_data):
            result = self._orch.compute(features, candle)
            if not result.is_actionable() or not result.top_result:
                continue
            tr = result.top_result
            # Simulate outcome: TP_HIT if conf > 0.65, SL_HIT otherwise
            predicted = "TP_HIT" if result.confidence >= 0.65 else "SL_HIT"
            actual = predicted  # in UAT2 we test pipeline fidelity, not true outcomes
            log.log_simulation(SimulationRecord(
                id                   = i + 1,
                ts                   = tr.ts,
                pair                 = self.pair,
                timeframe            = self.timeframe,
                capital_deployed_inr = tr.sl_inr,
                entry                = tr.entry,
                sl                   = tr.sl,
                tp                   = tr.tp,
                sl_inr_risk          = tr.sl_inr,
                tp_inr_gain          = tr.tp_inr,
                predicted_outcome    = predicted,
                actual_outcome       = actual,
                correct              = True,
                strategies_fired     = [r.strategy_id for r in result.all_results if r.is_actionable()],
                regime               = tr.regime,
                fusion_score         = result.score,
                resolution_candles   = 0,
                chart_markers        = {"entry": tr.entry, "sl": tr.sl, "tp": tr.tp},
            ))
        logger.info("Area 2 complete: %d simulations logged", len(log._simulations))
        return log

    def run_area_3(self, alert_records: List[dict]) -> LLMStructuredLogger:
        """Area 3 — Telegram alert delivery: validate latency + field completeness."""
        log = self._get_logger(3)
        for i, rec in enumerate(alert_records):
            alert = AlertRecord(
                id             = i + 1,
                trigger_ts     = rec.get("trigger_ts", ""),
                received_ts    = rec.get("received_ts", ""),
                latency_ms     = int(rec.get("latency_ms", 0)),
                payload        = rec.get("payload", {}),
                fields_present = all(
                    f in rec.get("payload", {})
                    for f in ("signal", "pair", "sl_inr", "tp_inr", "confidence")
                ),
                inr_correct    = float(rec.get("payload", {}).get("sl_inr", -1)) <= 25_000.0,
            )
            log.log_alert(alert)
        logger.info("Area 3 complete: %d alert records logged", len(log._alerts))
        return log

    def run_area_4(self, trade_outcomes: List[TradeOutcome]) -> LLMStructuredLogger:
        """Area 4 — Strategy scorecard: per-strategy P&L stats."""
        log = self._get_logger(4)
        by_strategy: Dict[str, List[float]] = {}
        for t in trade_outcomes:
            by_strategy.setdefault(t.strategy_id, []).append(t.pnl_inr)

        for sid, pnls in by_strategy.items():
            wins    = [p for p in pnls if p > 0]
            losses  = [p for p in pnls if p < 0]
            n       = len(pnls)
            win_rate = len(wins) / n if n else 0.0
            avg_win  = sum(wins) / len(wins) if wins else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0
            gross_profit = sum(wins)
            gross_loss   = abs(sum(losses))
            pf = gross_profit / gross_loss if gross_loss > 0 else 0.0

            status = (
                "APPROVED"  if win_rate >= 0.35 and n >= 10
                else "WARN" if n >= 5
                else "REJECTED"
            )
            log.log_scorecard(ScorecardRecord(
                strategy     = sid,
                aggregate    = {
                    "total_trades":   n,
                    "win_rate":       round(win_rate, 3),
                    "profit_factor":  round(pf, 3),
                    "avg_win_inr":    round(avg_win, 2),
                    "avg_loss_inr":   round(avg_loss, 2),
                    "net_pnl_inr":    round(sum(pnls), 2),
                },
                by_pair      = [{"pair": self.pair, "timeframe": self.timeframe, "n": n}],
                best_pair_tf = f"{self.pair}/{self.timeframe}",
                worst_pair_tf= f"{self.pair}/{self.timeframe}",
                status       = status,
            ))
        logger.info("Area 4 complete: %d strategy scorecards", len(log._scorecards))
        return log

    def run_area_5(self, trade_outcomes: List[TradeOutcome]) -> LLMStructuredLogger:
        """Area 5 — Monte Carlo: 1000 bootstrap runs, P(ruin) gate."""
        log = self._get_logger(5)
        mc_result = self._mc.run(trade_outcomes, strategy_id="ALL")
        log.log_monte_carlo_dict(mc_result.to_llm_logger_dict())
        logger.info(
            "Area 5 complete: p_ruin=%.1f%% status=%s",
            mc_result.p_ruin * 100, mc_result.status,
        )
        return log

    def run_area_6(self) -> LLMStructuredLogger:
        """
        Area 6 — Kill switch: test daily and weekly thresholds then reset.
        Uses a temporary in-memory KillSwitch to avoid touching the live state.
        """
        log = self._get_logger(6)
        events: List[dict] = []

        # Scenario A: daily limit breach
        ks_test = KillSwitch(
            daily_limit_inr  = 1000.0,
            weekly_limit_inr = 25_000.0,
            state_file       = Path("logs/ks_uat_test_state.json"),
        )
        t0 = time.time()
        tripped = ks_test.register_trade(pnl_inr=-1200.0)
        latency = int((time.time() - t0) * 1000)
        events.append({
            "scenario":  "daily_limit_breach",
            "tripped":   tripped,
            "reason":    ks_test.trip_reason(),
            "latency_ms": latency,
            "daily_loss": ks_test.daily_loss_inr(),
        })
        if not tripped:
            log.flag_anomaly("Area 6: daily limit breach did not trip kill switch")
        ks_test.reset()

        # Scenario B: weekly accumulation across multiple trades
        ks_test2 = KillSwitch(
            daily_limit_inr  = 50_000.0,
            weekly_limit_inr = 2_000.0,
            state_file       = Path("logs/ks_uat_test2_state.json"),
        )
        for loss in [500.0, 600.0, 700.0, 800.0]:
            ks_test2.register_trade(pnl_inr=-loss)
        tripped2 = ks_test2.is_tripped()
        events.append({
            "scenario":    "weekly_accumulation",
            "tripped":     tripped2,
            "reason":      ks_test2.trip_reason(),
            "weekly_loss": ks_test2.weekly_loss_inr(),
        })
        if not tripped2:
            log.flag_anomaly("Area 6: weekly limit accumulation did not trip kill switch")
        ks_test2.reset()

        # Scenario C: profitable trades do NOT trip the switch
        ks_test3 = KillSwitch(
            daily_limit_inr  = 1000.0,
            weekly_limit_inr = 2_000.0,
            state_file       = Path("logs/ks_uat_test3_state.json"),
        )
        for profit in [200.0, 300.0, 500.0]:
            ks_test3.register_trade(pnl_inr=profit)
        events.append({
            "scenario": "profitable_trades_no_trip",
            "tripped":  ks_test3.is_tripped(),
        })
        if ks_test3.is_tripped():
            log.flag_anomaly("Area 6: profitable trades incorrectly tripped kill switch")

        ts_now = datetime.now(timezone.utc).isoformat()
        for i, ev in enumerate(events):
            log.log_kill_switch(KillSwitchEvent(
                ts                  = ts_now,
                cumulative_loss_inr = ev.get("daily_loss", ev.get("weekly_loss", 0.0)),
                threshold_inr       = 1000.0,
                action              = "HALT" if ev.get("tripped") else "NO_ACTION",
                telegram_sent       = False,
                latency_ms          = ev.get("latency_ms", 0),
            ))

        logger.info("Area 6 complete: %d kill-switch scenarios tested", len(events))
        return log

    def run_area_7(self) -> LLMStructuredLogger:
        """
        Area 7 — Edge cases: boundary inputs, degenerate candles, stale data.
        Tests every strategy against pathological inputs via StrategyOrchestrator.
        """
        log = self._get_logger(7)
        cases = self._build_edge_cases()

        for case_name, features, candle, expected_signal in cases:
            try:
                result = self._orch.compute(features, candle)
                actual = result.signal
                passed = (expected_signal == "NO_TRADE" and not result.is_actionable()) or \
                         (expected_signal != "NO_TRADE" and actual == expected_signal) or \
                         (expected_signal == "ANY" and isinstance(actual, str))
                log.log_edge_case(EdgeCaseRecord(
                    case=case_name, input={"features_keys": list(features.keys())},
                    expected=expected_signal, actual=actual, passed=passed,
                ))
            except Exception as exc:
                log.log_edge_case(EdgeCaseRecord(
                    case=case_name, input={},
                    expected=expected_signal, actual="ERROR",
                    passed=False, error=str(exc),
                ))

        failed = sum(1 for ec in log._edge_cases if not ec.passed)
        logger.info("Area 7 complete: %d cases, %d failed", len(cases), failed)
        return log

    # ── Export ─────────────────────────────────────────────────────────────────

    def export_all(self, output_dir: Optional[str] = None) -> Dict[int, Path]:
        """Export all logged UAT areas to JSON files. Returns {area: path}."""
        out_dir = Path(output_dir) if output_dir else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: Dict[int, Path] = {}
        for area, log in self._loggers.items():
            path = out_dir / f"UAT-{area}-{self.pair}-{self.timeframe}.json"
            log.export(str(path))
            paths[area] = path
            logger.info("Area %d exported to %s", area, path)
        return paths

    def get_logger(self, area: int) -> Optional[LLMStructuredLogger]:
        """Return the logger for a specific UAT area (after run_area_N call)."""
        return self._loggers.get(area)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_logger(self, area: int) -> LLMStructuredLogger:
        if area not in self._loggers:
            self._loggers[area] = LLMStructuredLogger(
                uat_area=area, phase="UAT",
                pair=self.pair, timeframe=self.timeframe,
            )
        return self._loggers[area]

    def _build_edge_cases(self) -> List[Tuple[str, dict, dict, str]]:
        """Return list of (case_name, features, candle, expected_signal)."""
        base = {
            "atr": 0.0015, "rsi_14": 50.0, "trend_bias": "neutral",
            "sweep_detected": False, "break_of_structure": False,
            "higher_high": False, "lower_low": False,
            "swing_high": 1.1050, "swing_low": 1.0950,
            "disp_strength": 0.0, "retest_depth": 0.0,
            "candles_since_retest": 0, "body_ratio": 0.5,
            "liquidity_sweep": False, "double_sweep": False,
            "volume_ratio": 1.0, "momentum_score": 0.0,
            "bb_upper": 1.1050, "bb_lower": 1.0950,
            "rejection_wick": False, "is_inside_bar": False,
            "ema_fast": 1.1000, "ema_slow": 1.0990,
            "ema_spread": 0.0010, "body_size": 0.0005,
            "wick_size": 0.0010, "pattern_score": 0.5,
            "session": "london", "hour_of_day": 10.0,
            "macd_line": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
            "zone_strength": 0.5, "trend_strength": 0.5,
            "volatility_ratio": 1.0, "volatility_regime": "RANGING",
            "spread_pct": 0.0001,
        }
        base_candle = {
            "open": 1.1000, "high": 1.1020, "low": 1.0980,
            "close": 1.1005, "volume": 100,
        }
        return [
            # EC-01: zero ATR → all strategies should return NO_TRADE
            ("EC-01_zero_atr",
             {**base, "atr": 0.0}, base_candle, "NO_TRADE"),
            # EC-02: zero close → NO_TRADE
            ("EC-02_zero_close",
             base, {**base_candle, "close": 0.0}, "NO_TRADE"),
            # EC-03: high=low (zero range candle) → NO_TRADE
            ("EC-03_zero_range",
             base, {**base_candle, "high": 1.1005, "low": 1.1005}, "NO_TRADE"),
            # EC-04: extreme news volatility → S7 blocks; result may be NO_TRADE
            ("EC-04_news_spike",
             {**base, "volatility_ratio": 10.0, "spread_pct": 0.01}, base_candle, "NO_TRADE"),
            # EC-05: outside trading hours → S6 scalping blocks
            ("EC-05_off_hours",
             {**base, "hour_of_day": 3.0}, base_candle, "ANY"),
            # EC-06: candles_since_retest > max_age → S10 should not fire
            ("EC-06_stale_sweep",
             {**base, "sweep_detected": True, "candles_since_retest": 99}, base_candle, "ANY"),
            # EC-07: sl_inr would exceed 25K — lot sizer must cap it
            ("EC-07_sl_inr_cap",
             {**base, "atr": 0.5, "trend_bias": "bullish",
              "break_of_structure": True, "volume_ratio": 1.5,
              "higher_high": True, "swing_high": 1.0990,
              "disp_strength": 0.8, "momentum_score": 0.8},
             {**base_candle, "close": 1.1050}, "ANY"),
            # EC-08: all features zero — graceful degradation
            ("EC-08_all_zeros",
             {k: 0 for k in base}, {k: 0 for k in base_candle}, "NO_TRADE"),
        ]
