"""PerformanceAnalyzer: win rate, expectancy, drawdown, and breakdown metrics.

QUARANTINE NOTE (trust-layer WS2B, 2026-06-10)
    This analyzer operates on a DIFFERENT data domain from the backtest metric path:
    it consumes live-feedback trade *dicts* with `result` (WIN/LOSS) and `pnl` in
    CURRENCY units — not the R-multiple `TradeRecord` ledger. Its `expectancy` /
    `profit_factor` are therefore currency-based and are NOT comparable to, and NOT a
    substitute for, the canonical R-multiple metrics in `runtime/backtest_v2.py`
    (`BacktestMetrics` / `MetricsEngine`). It is wired only into the AI feedback loop
    (`src/feedback/ai_feedback.py`) and MUST NOT feed promotion/validation decisions —
    the only promotion authority is `ConfigValidator` over `BacktestMetrics`.
    See docs/analysis/backtest-trust-audit-2026-06-10.md §3.
"""

# performance.py — PerformanceAnalyzer: win rate, expectancy, drawdown, breakdown
import logging
from typing import Optional

log = logging.getLogger(__name__)

_MIN_TRADES_FOR_ANALYSIS = 5


class PerformanceAnalyzer:
    """
    Computes performance metrics from a list of trade dicts.

    Input: list of dicts with keys: result (WIN/LOSS), pnl (float),
           regime (str), config_profile (str).

    Usage:
        pa = PerformanceAnalyzer()
        summary = pa.compute(trades)
        by_regime = pa.by_regime(trades)
    """

    def compute(self, trades: list) -> dict:
        if not trades:
            return self._empty_metrics()

        wins = [t for t in trades if t.get("result") == "WIN"]
        losses = [t for t in trades if t.get("result") == "LOSS"]
        total = len(trades)

        win_rate = len(wins) / total if total > 0 else 0.0
        avg_win = sum(t.get("pnl", 0.0) for t in wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(t.get("pnl", 0.0) for t in losses) / len(losses)) if losses else 0.0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        total_pnl = sum(t.get("pnl", 0.0) for t in trades)
        profit_factor = (sum(t.get("pnl", 0.0) for t in wins) /
                         abs(sum(t.get("pnl", 0.0) for t in losses))) if losses else float("inf")
        max_drawdown = self._compute_drawdown(trades)

        return {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "total_pnl": total_pnl,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
        }

    def by_regime(self, trades: list) -> dict:
        """Break down metrics by regime."""
        regimes = set(t.get("regime", "UNKNOWN") for t in trades)
        return {r: self.compute([t for t in trades if t.get("regime") == r]) for r in regimes}

    def by_config(self, trades: list) -> dict:
        """Break down metrics by config_profile."""
        profiles = set(t.get("config_profile", "UNKNOWN") for t in trades)
        return {p: self.compute([t for t in trades if t.get("config_profile") == p]) for p in profiles}

    @staticmethod
    def _compute_drawdown(trades: list) -> float:
        pnl_series = [t.get("pnl", 0.0) for t in trades]
        peak = 0.0
        max_dd = 0.0
        running = 0.0
        for pnl in pnl_series:
            running += pnl
            if running > peak:
                peak = running
            dd = (peak - running) / abs(peak) if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd

    @staticmethod
    def _empty_metrics() -> dict:
        return {
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
            "expectancy": 0.0, "total_pnl": 0.0,
            "profit_factor": 0.0, "max_drawdown": 0.0,
        }
