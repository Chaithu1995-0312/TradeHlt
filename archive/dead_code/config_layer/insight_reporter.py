# ARCHIVED 2026-04-28 — Dead Code Pass
# Reason: only referenced in stale .claude/worktrees/ branches (dead git worktrees).
#         Zero importers in active src/. LLM reporting was never wired into the spine.
# Original: src/config_layer/insight_reporter.py
# Action required on original: remove src/config_layer/insight_reporter.py
"""
insight_reporter.py — LLM-powered narrative insight reporter.
See archive header above for reason this was removed from src/.
If re-enabling: wire into live_engine_hook.py post-decision path,
guard with optional-import pattern, and add feature flag in production config.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from config_layer.llama_gate import llm_insight, _fallback_insight

log = logging.getLogger("InsightReporter")


def _safe_fmt(value: Any, fmt: str = "") -> Any:
    if value is None:
        return "N/A"
    if fmt:
        try:
            return format(value, fmt)
        except (TypeError, ValueError):
            return str(value)
    return value


def _pct(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class InsightReporter:
    def __init__(self, symbol="UNKNOWN", output_dir="reports", enabled=True, verbose=True):
        self.symbol     = symbol
        self.output_dir = output_dir
        self.enabled    = enabled
        self.verbose    = verbose
        self._entries: List[str] = []
        os.makedirs(output_dir, exist_ok=True)

    def trade_decision(self, score_result, sub_scores=None):
        sub = sub_scores or {}
        context = {
            "gaussian_score":  _safe_fmt(score_result.get("gaussian", score_result.get("final_score", 0.0))),
            "ml_expected_rr":  _safe_fmt(score_result.get("expected_rr")),
            "ml_win_prob":     _safe_fmt(score_result.get("probability_of_win")),
            "sweep":           _safe_fmt(sub.get("sweep", "N/A")),
            "breakout":        _safe_fmt(sub.get("breakout", "N/A")),
            "retest":          _safe_fmt(sub.get("retest", "N/A")),
            "time":            _safe_fmt(sub.get("time", "N/A")),
            "decision":        score_result.get("decision", "N/A"),
            "reason":          score_result.get("reason", "N/A"),
        }
        narrative = self._generate("trade_decision", context)
        self._record("TRADE", narrative)
        return narrative

    def session_summary(self, session_name, trades=None, metrics=None):
        m = metrics or {}
        if trades and not m:
            approved = [t for t in trades if t.get("decision") == "EXECUTE"]
            wins     = [t for t in approved if _pct(t.get("pnl_rr_net", 0)) >= 1.0]
            m = {
                "n_trades":        len(trades),
                "approved_trades": len(approved),
                "win_rate":        len(wins) / len(approved) if approved else 0.0,
                "net_rr":          sum(_pct(t.get("pnl_rr_net", 0)) for t in approved),
                "avg_gaussian":    sum(_pct(t.get("gaussian", 0)) for t in approved) / max(len(approved), 1),
                "avg_ml_rr":       sum(_pct(t.get("expected_rr", 0)) for t in approved) / max(len(approved), 1),
                "max_drawdown":    0.0,
            }
        context = {
            "symbol": self.symbol, "session": session_name,
            "n_trades": _safe_fmt(m.get("n_trades")),
            "approved_trades": _safe_fmt(m.get("approved_trades")),
            "win_rate": _safe_fmt(m.get("win_rate")),
            "net_rr": _safe_fmt(m.get("net_rr")),
            "avg_gaussian": _safe_fmt(m.get("avg_gaussian")),
            "avg_ml_rr": _safe_fmt(m.get("avg_ml_rr")),
            "max_drawdown": _safe_fmt(m.get("max_drawdown")),
        }
        narrative = self._generate("session_summary", context)
        self._record("SESSION", narrative)
        return narrative

    def backtest_summary(self, metrics):
        context = {
            "symbol": self.symbol,
            "total_trades": _safe_fmt(metrics.get("total_trades", metrics.get("approved_trades"))),
            "win_rate": _safe_fmt(metrics.get("win_rate")),
            "expectancy_rr": _safe_fmt(metrics.get("expectancy_rr")),
            "max_drawdown_pct": _safe_fmt(metrics.get("max_drawdown_pct")),
            "sharpe": _safe_fmt(metrics.get("sharpe")),
        }
        narrative = self._generate("backtest_summary", context)
        self._record("BACKTEST", narrative)
        return narrative

    def regime_alert(self, prev_regime, curr_regime, volatility, session):
        context = {
            "symbol": self.symbol, "prev_regime": prev_regime,
            "curr_regime": curr_regime, "volatility": _safe_fmt(volatility), "session": session,
        }
        narrative = self._generate("regime_alert", context)
        self._record("REGIME", narrative)
        return narrative

    def save(self, filename=None):
        if not self._entries:
            return ""
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.output_dir, f"{self.symbol}_{ts}_insight.md")
        header = f"# Trade Insight Report\n**Symbol:** {self.symbol}  \n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n\n---\n\n"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(header + "\n\n".join(self._entries) + "\n")
        return filename

    def _generate(self, report_type, context):
        return llm_insight(context, report_type) if self.enabled else _fallback_insight(context, report_type)

    def _record(self, tag, narrative):
        ts = datetime.now().strftime("%H:%M:%S")
        log.info(f"[{tag}] {narrative}")
        self._entries.append(f"## [{tag}] — {ts}\n\n{narrative}")
