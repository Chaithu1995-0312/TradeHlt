"""
llm_logger.py
================================================================================
LLMStructuredLogger — token-efficient structured logger for UAT/SIT sessions.

Instead of pasting raw logs (high noise, high token cost), each module calls
into this logger to build a compact JSON blob. You paste the blob here for
analysis. One blob per UAT area, per session.

Usage
-----
    logger = LLMStructuredLogger(uat_area=1, phase="UAT", pair="EURUSD", timeframe="H1")
    logger.log_signal(strategy_result, outcome="TP_HIT")
    logger.flag_anomaly("Signal #34: confidence=0.99 — check overfitting")
    payload = logger.export("results/uat/UAT-1.json")

CLI
---
    python -m utils.llm_logger --area 4 --phase UAT --export results/uat/UAT-4.json --print

UAT Areas
---------
  1  Signal quality review
  2  Visual backtest validation
  3  Telegram alert review
  4  Backtest scorecard review
  5  Monte Carlo validation
  6  Kill switch test
  7  Edge case scenarios
================================================================================
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional

# ── Path bootstrap ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Anomaly thresholds (aligned with architecture decisions) ─────────────────
_OVERFIT_CONFIDENCE  = 0.95
_OVERFIT_WIN_RATE    = 0.70
_OVERFIT_PF          = 3.0
_MIN_SL_PIPS         = 1.0
_MAX_SL_INR          = 25_000.0
_MAX_RUIN_PROB       = 0.05

# ── Max tokens for print_for_llm() ───────────────────────────────────────────
_MAX_SIGNALS_INLINE  = 5    # show first N signals fully, then summary stats
_EQUITY_SAMPLE_STEP  = 50   # sample every Nth equity curve point


# ============================================================================
# DATA CONTRACTS
# ============================================================================

@dataclass
class SignalRecord:
    id:                  int
    ts:                  str
    signal:              str
    strategies:          List[str]
    confidence:          float
    regime:              str
    entry:               float
    sl:                  float
    tp:                  float
    sl_inr:              float
    tp_inr:              float
    roi_min:             float
    roi_max:             float
    fusion_score:        float
    outcome:             Optional[str] = None
    actual_roi:          Optional[float] = None
    resolution_candles:  Optional[int] = None


@dataclass
class SimulationRecord:
    id:                      int
    ts:                      str
    pair:                    str
    timeframe:               str
    capital_deployed_inr:    float
    entry:                   float
    sl:                      float
    tp:                      float
    sl_inr_risk:             float
    tp_inr_gain:             float
    predicted_outcome:       str
    actual_outcome:          str
    correct:                 bool
    strategies_fired:        List[str]
    regime:                  str
    fusion_score:            float
    resolution_candles:      int
    chart_markers:           Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRecord:
    id:              int
    trigger_ts:      str
    received_ts:     str
    latency_ms:      int
    payload:         Dict[str, Any]
    fields_present:  bool
    inr_correct:     bool
    sla_pass:        bool = True


@dataclass
class ScorecardRecord:
    strategy:         str
    aggregate:        Dict[str, Any]
    by_pair:          List[Dict[str, Any]]
    best_pair_tf:     str
    worst_pair_tf:    str
    status:           str  # APPROVED | WARN | REJECTED


@dataclass
class MonteCarloRecord:
    strategy:                  str
    input_trades:              int
    p_ruin:                    float
    p_ruin_pass:               bool
    median_final_equity_inr:   float
    pct5_equity_inr:           float
    pct95_equity_inr:          float
    avg_max_drawdown_pct:      float
    worst_loss_streak_p95:     int
    equity_curve_points:       Dict[str, List[float]]
    status:                    str


@dataclass
class KillSwitchEvent:
    ts:                   str
    cumulative_loss_inr:  float
    threshold_inr:        float
    action:               str
    telegram_sent:        bool
    latency_ms:           int


@dataclass
class EdgeCaseRecord:
    case:      str
    input:     Dict[str, Any]
    expected:  str
    actual:    str
    passed:    bool
    error:     Optional[str] = None


@dataclass
class LLMLogPayload:
    session_id:  str
    uat_area:    int
    phase:       str
    pair:        str
    timeframe:   str
    timestamp:   str
    summary:     Dict[str, Any]
    data:        Dict[str, Any]
    anomalies:   List[str]
    open_items:  List[str]


# ============================================================================
# LOGGER
# ============================================================================

class LLMStructuredLogger:
    """
    Token-efficient structured logger for UAT/SIT analysis sessions.

    One instance = one session (one UAT area, one run). Export at the end of
    the session and paste the JSON blob for LLM analysis.
    """

    def __init__(
        self,
        uat_area:  int,
        phase:     str,
        pair:      str = "ALL",
        timeframe: str = "ALL",
    ) -> None:
        if uat_area not in range(1, 8):
            raise ValueError(f"uat_area must be 1–7, got {uat_area}")
        self._payload = LLMLogPayload(
            session_id  = f"UAT-{uat_area}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            uat_area    = uat_area,
            phase       = phase.upper(),
            pair        = pair,
            timeframe   = timeframe,
            timestamp   = datetime.now(timezone.utc).isoformat(),
            summary     = {},
            data        = {},
            anomalies   = [],
            open_items  = [],
        )
        self._signals:      List[SignalRecord]      = []
        self._simulations:  List[SimulationRecord]  = []
        self._alerts:       List[AlertRecord]       = []
        self._scorecards:   List[ScorecardRecord]   = []
        self._mc_results:   List[MonteCarloRecord]  = []
        self._kill_events:  List[KillSwitchEvent]   = []
        self._edge_cases:   List[EdgeCaseRecord]    = []

    # ── Area 1 — Signal quality ───────────────────────────────────────────────

    def log_signal(
        self,
        signal_data: Dict[str, Any],
        outcome: Optional[str] = None,
        actual_roi: Optional[float] = None,
        resolution_candles: Optional[int] = None,
    ) -> None:
        """Append one signal record (Area 1)."""
        idx = len(self._signals) + 1
        rec = SignalRecord(
            id                 = idx,
            ts                 = signal_data.get("ts", ""),
            signal             = signal_data.get("signal", ""),
            strategies         = signal_data.get("strategies", []),
            confidence         = float(signal_data.get("confidence", 0.0)),
            regime             = signal_data.get("regime", ""),
            entry              = float(signal_data.get("entry", 0.0)),
            sl                 = float(signal_data.get("sl", 0.0)),
            tp                 = float(signal_data.get("tp", 0.0)),
            sl_inr             = float(signal_data.get("sl_inr", 0.0)),
            tp_inr             = float(signal_data.get("tp_inr", 0.0)),
            roi_min            = float(signal_data.get("roi_min", 0.0)),
            roi_max            = float(signal_data.get("roi_max", 0.0)),
            fusion_score       = float(signal_data.get("fusion_score", 0.0)),
            outcome            = outcome,
            actual_roi         = actual_roi,
            resolution_candles = resolution_candles,
        )
        self._signals.append(rec)

    def log_signal_from_result(self, result: Any, outcome: Optional[str] = None) -> None:
        """Convenience: pass a StrategyResult object directly."""
        self.log_signal(
            signal_data={
                "ts":           getattr(result, "ts", ""),
                "signal":       result.signal,
                "strategies":   [result.strategy_id],
                "confidence":   result.confidence,
                "regime":       result.regime,
                "entry":        result.entry,
                "sl":           result.sl,
                "tp":           result.tp,
                "sl_inr":       result.sl_inr,
                "tp_inr":       result.tp_inr,
                "roi_min":      result.roi_min,
                "roi_max":      result.roi_max,
                "fusion_score": result.score,
            },
            outcome=outcome,
        )

    # ── Area 2 — Visual backtest ──────────────────────────────────────────────

    def log_simulation(self, sim: SimulationRecord) -> None:
        """Append one point-in-time simulation result (Area 2)."""
        self._simulations.append(sim)

    def log_simulation_dict(self, d: Dict[str, Any]) -> None:
        sim = SimulationRecord(**{k: v for k, v in d.items()
                                  if k in SimulationRecord.__dataclass_fields__})
        self.log_simulation(sim)

    # ── Area 3 — Telegram alert ───────────────────────────────────────────────

    def log_alert(self, alert: AlertRecord) -> None:
        """Append one Telegram alert record (Area 3)."""
        if alert.latency_ms > 2000:
            self.flag_anomaly(
                f"Alert #{alert.id}: latency {alert.latency_ms}ms exceeds 2000ms SLA"
            )
            alert.sla_pass = False
        self._alerts.append(alert)

    def log_alert_dict(self, d: Dict[str, Any]) -> None:
        alert = AlertRecord(**{k: v for k, v in d.items()
                               if k in AlertRecord.__dataclass_fields__})
        self.log_alert(alert)

    # ── Area 4 — Scorecard ────────────────────────────────────────────────────

    def log_scorecard(self, card: ScorecardRecord) -> None:
        """Append one strategy scorecard (Area 4)."""
        agg = card.aggregate
        if agg.get("win_rate", 0) > _OVERFIT_WIN_RATE:
            self.flag_anomaly(
                f"{card.strategy} win_rate={agg['win_rate']:.0%} exceeds "
                f"{_OVERFIT_WIN_RATE:.0%} overfitting threshold — verify",
                oi_ref="OI-02",
            )
        if agg.get("profit_factor", 0) > _OVERFIT_PF:
            self.flag_anomaly(
                f"{card.strategy} profit_factor={agg['profit_factor']:.2f} "
                f"exceeds {_OVERFIT_PF:.1f} — likely overfitted",
                oi_ref="OI-02",
            )
        if agg.get("total_trades", 0) == 0:
            self.flag_anomaly(
                f"{card.strategy} produced 0 trades — possible config issue",
            )
        self._scorecards.append(card)

    def log_scorecard_dict(self, d: Dict[str, Any]) -> None:
        card = ScorecardRecord(**{k: v for k, v in d.items()
                                  if k in ScorecardRecord.__dataclass_fields__})
        self.log_scorecard(card)

    # ── Area 5 — Monte Carlo ──────────────────────────────────────────────────

    def log_monte_carlo(self, mc: MonteCarloRecord) -> None:
        """Append one Monte Carlo result (Area 5)."""
        if mc.p_ruin > _MAX_RUIN_PROB:
            self.flag_anomaly(
                f"{mc.strategy}: P(ruin)={mc.p_ruin:.1%} exceeds "
                f"{_MAX_RUIN_PROB:.0%} gate — reduce position size",
                oi_ref="OI-08",
            )
        self._mc_results.append(mc)

    def log_monte_carlo_dict(self, d: Dict[str, Any]) -> None:
        mc = MonteCarloRecord(**{k: v for k, v in d.items()
                                 if k in MonteCarloRecord.__dataclass_fields__})
        self.log_monte_carlo(mc)

    # ── Area 6 — Kill switch ──────────────────────────────────────────────────

    def log_kill_switch(self, event: KillSwitchEvent) -> None:
        """Append a kill switch trigger event (Area 6)."""
        self._kill_events.append(event)

    def log_kill_switch_dict(self, d: Dict[str, Any]) -> None:
        ev = KillSwitchEvent(**{k: v for k, v in d.items()
                                if k in KillSwitchEvent.__dataclass_fields__})
        self.log_kill_switch(ev)

    # ── Area 7 — Edge cases ───────────────────────────────────────────────────

    def log_edge_case(self, case: EdgeCaseRecord) -> None:
        """Append one edge case test result (Area 7)."""
        if not case.passed:
            self.flag_anomaly(
                f"Edge case FAILED: {case.case} — {case.error or 'no error detail'}",
            )
        self._edge_cases.append(case)

    def log_edge_case_dict(self, d: Dict[str, Any]) -> None:
        ec = EdgeCaseRecord(**{k: v for k, v in d.items()
                               if k in EdgeCaseRecord.__dataclass_fields__})
        self.log_edge_case(ec)

    # ── Anomaly API ───────────────────────────────────────────────────────────

    def flag_anomaly(self, message: str, oi_ref: Optional[str] = None) -> None:
        """Manually flag an anomaly. Also adds OI reference if provided."""
        self._payload.anomalies.append(message)
        if oi_ref and oi_ref not in self._payload.open_items:
            self._payload.open_items.append(oi_ref)

    # ── Auto anomaly detection ────────────────────────────────────────────────

    def auto_detect_anomalies(self) -> None:
        """
        Run built-in anomaly rules against all logged data.
        Called automatically inside export().
        """
        for sig in self._signals:
            if sig.confidence > _OVERFIT_CONFIDENCE:
                self.flag_anomaly(
                    f"Signal #{sig.id}: confidence={sig.confidence:.2f} "
                    f"> {_OVERFIT_CONFIDENCE} — check overfitting",
                    oi_ref="OI-02",
                )
            sl_pips = self._approx_sl_pips(sig.entry, sig.sl, sig.ts)
            if 0 < sl_pips < _MIN_SL_PIPS:
                self.flag_anomaly(
                    f"Signal #{sig.id}: SL distance ~{sl_pips:.1f} pips "
                    f"< {_MIN_SL_PIPS} pip minimum — likely misconfiguration"
                )
            if sig.sl_inr > _MAX_SL_INR:
                self.flag_anomaly(
                    f"Signal #{sig.id}: sl_inr=INR {sig.sl_inr:.0f} "
                    f"exceeds INR {_MAX_SL_INR:.0f} cap"
                )

        for mc in self._mc_results:
            if not mc.p_ruin_pass:
                self.flag_anomaly(
                    f"MC {mc.strategy}: P(ruin)={mc.p_ruin:.1%} — "
                    "already flagged above",
                    oi_ref="OI-08",
                )

    # ── Summary builder ───────────────────────────────────────────────────────

    def build_summary(self) -> None:
        """Compute summary stats from all logged data. Called inside export()."""
        area = self._payload.uat_area

        if area == 1 and self._signals:
            confs = [s.confidence for s in self._signals]
            strategies_used: set = set()
            for s in self._signals:
                strategies_used.update(s.strategies)
            tp_hits = sum(1 for s in self._signals if s.outcome == "TP_HIT")
            sl_hits = sum(1 for s in self._signals if s.outcome == "SL_HIT")
            self._payload.summary = {
                "total_signals":      len(self._signals),
                "buy_count":          sum(1 for s in self._signals if s.signal == "BUY"),
                "sell_count":         sum(1 for s in self._signals if s.signal == "SELL"),
                "no_trade_count":     sum(1 for s in self._signals if s.signal == "NO_TRADE"),
                "avg_confidence":     round(mean(confs), 3) if confs else 0.0,
                "strategies_fired":   sorted(strategies_used),
                "tp_hits":            tp_hits,
                "sl_hits":            sl_hits,
                "sim_win_rate":       round(tp_hits / max(tp_hits + sl_hits, 1), 3),
            }

        elif area == 2 and self._simulations:
            correct = sum(1 for s in self._simulations if s.correct)
            self._payload.summary = {
                "candles_tested":   len(self._simulations),
                "correct_outcome":  correct,
                "incorrect_outcome": len(self._simulations) - correct,
                "accuracy_pct":     round(correct / len(self._simulations) * 100, 1),
            }

        elif area == 3 and self._alerts:
            latencies = [a.latency_ms for a in self._alerts]
            self._payload.summary = {
                "alerts_triggered":  len(self._alerts),
                "alerts_received":   len(self._alerts),
                "avg_latency_ms":    round(mean(latencies), 0) if latencies else 0,
                "max_latency_ms":    max(latencies) if latencies else 0,
                "sla_breaches":      sum(1 for a in self._alerts if not a.sla_pass),
            }

        elif area == 4 and self._scorecards:
            passed = sum(1 for c in self._scorecards if c.status == "APPROVED")
            self._payload.summary = {
                "strategies_tested":  len(self._scorecards),
                "strategies_passed":  passed,
                "strategies_failed":  len(self._scorecards) - passed,
                "total_trades":       sum(
                    c.aggregate.get("total_trades", 0) for c in self._scorecards
                ),
            }

        elif area == 5 and self._mc_results:
            all_passed = all(m.p_ruin_pass for m in self._mc_results)
            self._payload.summary = {
                "strategies_tested":   len(self._mc_results),
                "runs_per_strategy":   1000,
                "all_passed":          all_passed,
            }

        elif area == 6 and self._kill_events:
            ev = self._kill_events[-1]
            self._payload.summary = {
                "kill_switch_triggered": True,
                "trigger_threshold_inr": ev.threshold_inr,
                "actual_loss_inr":       ev.cumulative_loss_inr,
                "telegram_alert_fired":  ev.telegram_sent,
                "latency_ms":            ev.latency_ms,
            }

        elif area == 7 and self._edge_cases:
            passed = sum(1 for e in self._edge_cases if e.passed)
            self._payload.summary = {
                "edge_cases_tested": len(self._edge_cases),
                "passed":            passed,
                "failed":            len(self._edge_cases) - passed,
            }

    # ── Export ────────────────────────────────────────────────────────────────

    def export(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Finalise and return the full JSON payload.
        Optionally writes to disk.

        Returns the payload dict — paste into this chat for analysis.
        """
        self.auto_detect_anomalies()
        self.build_summary()
        self._payload.data = self._collect_data()

        payload = asdict(self._payload)

        if path:
            out = Path(path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

        return payload

    def print_for_llm(self) -> None:
        """
        Print a compact version of the payload.

        Large arrays are summarised to keep output under ~2000 tokens:
          - signals[50] → signals[0:5] + signal_stats{}
          - equity_curve[1000] → sampled every 50 points
        """
        payload = self.export()
        compact = dict(payload)

        # Compress signals array
        if "signals" in compact.get("data", {}):
            sigs = compact["data"]["signals"]
            if len(sigs) > _MAX_SIGNALS_INLINE:
                compact["data"]["signals_sample"] = sigs[:_MAX_SIGNALS_INLINE]
                compact["data"]["signals_omitted"] = (
                    f"... {len(sigs) - _MAX_SIGNALS_INLINE} more "
                    f"(see exported file for full list)"
                )
                del compact["data"]["signals"]

        # Compress equity curves
        for mc in compact.get("data", {}).get("mc_results", []):
            for band in ("p5", "p50", "p95"):
                curve = mc.get("equity_curve_points", {}).get(band, [])
                if len(curve) > _MAX_SIGNALS_INLINE * 2:
                    mc["equity_curve_points"][band] = (
                        curve[::_EQUITY_SAMPLE_STEP]
                        + ([curve[-1]] if curve else [])
                    )

        print(json.dumps(compact, indent=2, default=str))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _collect_data(self) -> Dict[str, Any]:
        area = self._payload.uat_area
        if area == 1:
            return {"signals": [asdict(s) for s in self._signals]}
        if area == 2:
            return {"simulations": [asdict(s) for s in self._simulations]}
        if area == 3:
            return {"alerts": [asdict(a) for a in self._alerts]}
        if area == 4:
            return {"scorecards": [asdict(c) for c in self._scorecards]}
        if area == 5:
            return {"mc_results": [asdict(m) for m in self._mc_results]}
        if area == 6:
            return {"kill_events": [asdict(e) for e in self._kill_events]}
        if area == 7:
            return {"edge_cases": [asdict(e) for e in self._edge_cases]}
        return {}

    @staticmethod
    def _approx_sl_pips(entry: float, sl: float, ts: str) -> float:
        """Heuristic: determine pip multiplier from price magnitude."""
        if entry <= 0:
            return 0.0
        diff = abs(entry - sl)
        # JPY pairs trade ~100–160; all others ~0.6–2.0
        multiplier = 100.0 if entry > 10.0 else 10_000.0
        return round(diff * multiplier, 2)


# ============================================================================
# CLI
# ============================================================================

def _main(argv: List[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="LLMStructuredLogger — export UAT session payload."
    )
    parser.add_argument("--area",     type=int, required=True,     help="UAT area 1–7")
    parser.add_argument("--phase",    type=str, default="UAT",     help="Phase label")
    parser.add_argument("--pair",     type=str, default="ALL")
    parser.add_argument("--timeframe",type=str, default="ALL")
    parser.add_argument("--export",   type=str, default=None,      help="Output JSON path")
    parser.add_argument("--print",    action="store_true",          help="Print compact payload")
    args = parser.parse_args(argv)

    llm_logger = LLMStructuredLogger(
        uat_area  = args.area,
        phase     = args.phase,
        pair      = args.pair,
        timeframe = args.timeframe,
    )

    payload = llm_logger.export(path=args.export)

    if args.print:
        llm_logger.print_for_llm()
    elif args.export:
        print(f"Exported to {args.export}")
    else:
        print(json.dumps(payload, indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
