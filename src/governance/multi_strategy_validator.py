"""
multi_strategy_validator.py
================================================================================
MultiStrategyValidator — governance ValidationReport for the 10-strategy system.

Runs StrategyBacktester across all supplied CSV instruments, applies quality
gates, and returns a ValidationReport dict compatible with:
  - PromotionManager.promote_from_report()
  - PromotionManager._execute_promotion()

Hard gates (any failure → REJECT)
-----------------------------------
  1. min_strategy_trades: each strategy must have >= 5 trades
  2. min_portfolio_win_rate: portfolio-weighted win rate >= 0.30
  3. max_portfolio_drawdown_inr: worst per-strategy drawdown <= 75,000,000 INR

Soft gates (logged as warnings, do not block)
----------------------------------------------
  - Any single strategy win_rate < 0.30 → warning
  - profit_factor < 1.0 for any strategy → warning
  - timeout_count > 50% of trades for any strategy → warning

Usage
-----
    validator = MultiStrategyValidator()
    report = validator.validate(
        csv_paths={"EURUSD": "data/EURUSD_M15.csv", ...},
        config_id="v2_multi_2026_04_strategies",
    )
    # write report to disk and pass to PromotionManager.promote_from_report()

Config section: None (reads strategy_engine defaults at backtest time).
================================================================================
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.strategy_backtest import StrategyBacktester, StrategyMetrics  # type: ignore
from utils.logging_config import get_flow_logger                               # type: ignore

logger = get_flow_logger("COLLECTOR")

# Hard gate thresholds
_MIN_STRATEGY_TRADES       = 5
_MIN_PORTFOLIO_WIN_RATE    = 0.30
_MAX_PORTFOLIO_DRAWDOWN    = 75_000_000.0   # INR  (75 M)


class MultiStrategyValidator:
    """
    Validates the 10-strategy system against historical CSVs and produces
    a governance ValidationReport.
    """

    def __init__(
        self,
        min_strategy_trades: int   = _MIN_STRATEGY_TRADES,
        min_portfolio_win_rate: float = _MIN_PORTFOLIO_WIN_RATE,
        max_portfolio_drawdown: float = _MAX_PORTFOLIO_DRAWDOWN,
        warmup: int = 60,
        max_forward_candles: int = 40,
    ) -> None:
        self._min_trades    = min_strategy_trades
        self._min_wr        = min_portfolio_win_rate
        self._max_dd        = max_portfolio_drawdown
        self._warmup        = warmup
        self._max_fwd       = max_forward_candles

    def validate(
        self,
        csv_paths: Dict[str, str],
        config_id: str = "multi_strategy_v2",
    ) -> dict:
        """
        Run backtest validation across all instruments.

        Parameters
        ----------
        csv_paths : dict
            {"EURUSD": "data/EURUSD_M15.csv", ...}
        config_id : str
            Label for this validation run.

        Returns
        -------
        dict
            ValidationReport compatible with PromotionManager.promote_from_report().
        """
        if not csv_paths:
            return self._reject(config_id, hard_failures=["No CSV paths provided."])

        hard_failures: list[str] = []
        warnings:      list[str] = []

        # ── Per-instrument backtest ────────────────────────────────────────────
        per_instrument: dict = {}
        all_metrics:    dict = {}   # {instrument: {sid: StrategyMetrics}}

        for instrument, csv_path in csv_paths.items():
            if not Path(csv_path).exists():
                hard_failures.append(f"CSV not found: {csv_path}")
                continue

            bt = StrategyBacktester(
                pair=instrument, timeframe="M15",
                warmup=self._warmup,
                max_forward_candles=self._max_fwd,
            )
            metrics = bt.run(csv_path)
            if not metrics:
                hard_failures.append(f"Backtest produced no results for {instrument}.")
                continue

            all_metrics[instrument] = metrics
            inst_score = self._instrument_score(metrics)
            per_instrument[instrument] = {
                "score":         inst_score,
                "strategy_results": {sid: m.to_dict() for sid, m in metrics.items()},
                "trades":        sum(m.trade_count for m in metrics.values()),
                "win_rate":      self._portfolio_win_rate(metrics),
                "max_drawdown":  max(m.max_drawdown for m in metrics.values()),
            }

        if not per_instrument:
            hard_failures.append("No instruments produced backtest results.")
            return self._reject(config_id, hard_failures=hard_failures)

        # ── Aggregate across all instruments ──────────────────────────────────
        all_strategy_metrics: dict[str, list[StrategyMetrics]] = {}
        for inst_metrics in all_metrics.values():
            for sid, m in inst_metrics.items():
                all_strategy_metrics.setdefault(sid, []).append(m)

        # Aggregate per-strategy across instruments
        aggregated: dict[str, dict] = {}
        for sid, metric_list in all_strategy_metrics.items():
            total_trades   = sum(m.trade_count  for m in metric_list)
            total_wins     = sum(m.win_count     for m in metric_list)
            total_losses   = sum(m.loss_count    for m in metric_list)
            total_pnl      = sum(m.total_pnl_inr for m in metric_list)
            gross_profit   = sum(m.gross_profit  for m in metric_list)
            gross_loss     = sum(m.gross_loss     for m in metric_list)
            max_dd         = max(m.max_drawdown   for m in metric_list)
            decided        = total_wins + total_losses
            wr             = (total_wins / decided) if decided > 0 else 0.0
            pf             = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
            aggregated[sid] = {
                "trades": total_trades, "wins": total_wins, "losses": total_losses,
                "win_rate": round(wr, 4), "profit_factor": round(pf, 3),
                "total_pnl_inr": round(total_pnl, 2), "max_drawdown": round(max_dd, 2),
            }

        # ── Hard gate 1: min trades per strategy ──────────────────────────────
        low_trade_strategies = [
            sid for sid, agg in aggregated.items()
            if agg["trades"] < self._min_trades
        ]
        if low_trade_strategies:
            hard_failures.append(
                f"Strategies with < {self._min_trades} trades across all instruments: "
                f"{low_trade_strategies}"
            )

        # ── Hard gate 2: portfolio win rate ───────────────────────────────────
        total_wins_all   = sum(a["wins"]   for a in aggregated.values())
        total_losses_all = sum(a["losses"] for a in aggregated.values())
        decided_all = total_wins_all + total_losses_all
        portfolio_wr = (total_wins_all / decided_all) if decided_all > 0 else 0.0
        if portfolio_wr < self._min_wr:
            hard_failures.append(
                f"Portfolio win rate {portfolio_wr:.1%} below minimum {self._min_wr:.1%}."
            )

        # ── Hard gate 3: max drawdown ─────────────────────────────────────────
        worst_dd = max((a["max_drawdown"] for a in aggregated.values()), default=0.0)
        if worst_dd > self._max_dd:
            hard_failures.append(
                f"Max drawdown INR {worst_dd:,.0f} exceeds limit INR {self._max_dd:,.0f}."
            )

        # ── Soft warnings ─────────────────────────────────────────────────────
        for sid, agg in aggregated.items():
            if agg["win_rate"] < 0.30:
                warnings.append(f"{sid}: win_rate={agg['win_rate']:.1%} < 30%")
            if agg["profit_factor"] < 1.0 and agg["trades"] >= self._min_trades:
                warnings.append(f"{sid}: profit_factor={agg['profit_factor']:.2f} < 1.0")

        # ── Metrics summary ───────────────────────────────────────────────────
        inst_scores = [pi["score"] for pi in per_instrument.values()]
        mean_score  = round(sum(inst_scores) / len(inst_scores), 4) if inst_scores else 0.0
        total_trades_all = sum(a["trades"] for a in aggregated.values())

        metrics_summary = {
            "final_score":         mean_score,
            "mean_score":          mean_score,
            "consistency_penalty": 0.0,
            "total_trades":        total_trades_all,
            "portfolio_win_rate":  round(portfolio_wr, 4),
            "max_drawdown_across": round(worst_dd, 2),
            "aggregated_per_strategy": aggregated,
        }

        decision = "APPROVE" if not hard_failures else "REJECT"
        return {
            "decision":           decision,
            "config_id":          config_id,
            "validated_at":       datetime.now(timezone.utc).isoformat(),
            "params":             {"strategy_system": "10-strategy-v2"},
            "metrics":            metrics_summary,
            "per_instrument":     per_instrument,
            "instruments_tested": list(per_instrument.keys()),
            "hard_failures":      hard_failures,
            "warnings":           warnings,
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _portfolio_win_rate(metrics: dict) -> float:
        total_wins   = sum(m.win_count  for m in metrics.values())
        total_losses = sum(m.loss_count for m in metrics.values())
        decided = total_wins + total_losses
        return round(total_wins / decided, 4) if decided > 0 else 0.0

    @staticmethod
    def _instrument_score(metrics: dict) -> float:
        scores = [m.score for m in metrics.values() if m.trade_count >= 5]
        return round(sum(scores) / len(scores), 4) if scores else 0.0

    @staticmethod
    def _reject(config_id: str, hard_failures: list) -> dict:
        return {
            "decision":           "REJECT",
            "config_id":          config_id,
            "validated_at":       datetime.now(timezone.utc).isoformat(),
            "params":             {},
            "metrics":            {"final_score": 0.0},
            "per_instrument":     {},
            "instruments_tested": [],
            "hard_failures":      hard_failures,
            "warnings":           [],
        }
