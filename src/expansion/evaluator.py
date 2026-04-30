# evaluator.py — profit-aware scoring for expansion configs
#
from src.expansion.policy_schema import ExpansionStep


class Evaluator:
    """
    Scores a backtest result relative to baseline.
    Optimizes for profit density, not raw trade count or win rate.

    score = pnl - (drawdown_penalty) + (trade_bonus)

    Weights are deliberately conservative:
    - drawdown penalized 2× pnl weight
    - trade bonus is small (avoid frequency chasing)
    """

    DRAWDOWN_WEIGHT = 2.0
    TRADE_BONUS_WEIGHT = 10.0   # per additional trade above baseline

    @staticmethod
    def score(metrics: dict, baseline: dict) -> float:
        """
        Args:
            metrics: BacktestMetrics dict from current config run
            baseline: BacktestMetrics dict from base config
        Returns:
            float score (higher = better)
        """
        pnl = metrics.get("total_pnl", 0.0)
        drawdown = metrics.get("max_drawdown", 0.0)
        trades = metrics.get("trades", 0)
        baseline_trades = baseline.get("trades", 1)

        extra_trades = max(0, trades - baseline_trades)
        trade_bonus = extra_trades * Evaluator.TRADE_BONUS_WEIGHT
        drawdown_penalty = drawdown * Evaluator.DRAWDOWN_WEIGHT

        return pnl - drawdown_penalty + trade_bonus

    @staticmethod
    def passes_guardrails(metrics: dict, baseline: dict) -> tuple[bool, str]:
        """
        Check hard stop conditions.
        Returns (passes, reason_if_failed).
        """
        from src.expansion.policy_schema import MIN_PNL_RATIO, MAX_DRAWDOWN_RATIO

        pnl = metrics.get("total_pnl", 0.0)
        drawdown = metrics.get("max_drawdown", 0.0)
        baseline_pnl = baseline.get("total_pnl", 0.0)
        baseline_dd = baseline.get("max_drawdown", 0.0)

        if baseline_pnl > 0 and pnl < baseline_pnl * MIN_PNL_RATIO:
            return False, f"pnl_drop ({pnl:.0f} < {baseline_pnl * MIN_PNL_RATIO:.0f})"

        if baseline_dd > 0 and drawdown > baseline_dd * MAX_DRAWDOWN_RATIO:
            return False, f"drawdown_exceeded ({drawdown:.3f} > {baseline_dd * MAX_DRAWDOWN_RATIO:.3f})"

        return True, ""

    @staticmethod
    def classify_config(score: float, baseline_score: float, trades: int, baseline_trades: int) -> str:
        """Classify a config into SAFE / BALANCED / AGGRESSIVE tier."""
        ratio = trades / max(baseline_trades, 1)
        if ratio < 1.3:
            return "SAFE"
        elif ratio < 1.8:
            return "BALANCED"
        else:
            return "AGGRESSIVE"