"""
monte_carlo.py
================================================================================
Monte Carlo Engine — bootstrap resampling for strategy robustness validation.

Simulates N random re-orderings of the historical trade sequence and computes
distribution statistics on final equity and drawdown to estimate the probability
of ruin under different luck scenarios.

Usage
-----
    from uat.monte_carlo import MonteCarloEngine, TradeOutcome

    trades = [TradeOutcome(pnl_inr=500.0), TradeOutcome(pnl_inr=-300.0), ...]
    engine = MonteCarloEngine.from_prod_config()
    result = engine.run(trades, strategy_id="ALL")
    print(f"P(ruin)={result.p_ruin:.1%}")

Config section: uat.monte_carlo in production JSON.
================================================================================
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.production_config import get_prod_section   # type: ignore
from utils.logging_config import get_flow_logger               # type: ignore

logger = get_flow_logger("COLLECTOR")


# ── Input / Output contracts ───────────────────────────────────────────────────

@dataclass
class TradeOutcome:
    """Single realised trade result for Monte Carlo input."""
    pnl_inr: float                      # positive = win, negative = loss
    strategy_id: str = "UNKNOWN"
    signal: str = "BUY"
    pair: str = "EURUSD"
    sl_inr: float = 0.0
    tp_inr: float = 0.0


@dataclass
class MonteCarloResult:
    """
    Full statistical summary from N Monte Carlo simulations.

    Fields
    ------
    strategy            Strategy identifier (or "ALL" for combined)
    n_simulations       Number of bootstrap resamples run
    n_trades            Number of input trades
    p_ruin              Fraction of simulations that hit the ruin threshold
    p_ruin_pass         True when p_ruin <= max_ruin_threshold (0.05 default)
    initial_capital_inr Starting capital for each simulation
    ruin_threshold_inr  Capital level defined as ruin
    median_equity_inr   Median final equity across all simulations
    pct5_equity_inr     5th percentile final equity (worst 5% of scenarios)
    pct95_equity_inr    95th percentile final equity (best 5% of scenarios)
    avg_max_drawdown_pct Average peak-to-trough drawdown (%) across simulations
    worst_loss_streak_p95 95th percentile worst consecutive loss streak
    equity_percentiles  {sim_idx: [equity at each trade step]} — sampled subset
    status              PASSED | FAILED | INSUFFICIENT_DATA
    """
    strategy:               str
    n_simulations:          int
    n_trades:               int
    p_ruin:                 float
    p_ruin_pass:            bool
    initial_capital_inr:    float
    ruin_threshold_inr:     float
    median_equity_inr:      float
    pct5_equity_inr:        float
    pct95_equity_inr:       float
    avg_max_drawdown_pct:   float
    worst_loss_streak_p95:  int
    equity_percentiles:     dict
    status:                 str

    def to_llm_logger_dict(self) -> dict:
        """Format compatible with LLMStructuredLogger.log_monte_carlo_dict()."""
        return {
            "strategy":                 self.strategy,
            "input_trades":             self.n_trades,
            "p_ruin":                   self.p_ruin,
            "p_ruin_pass":              self.p_ruin_pass,
            "median_final_equity_inr":  self.median_equity_inr,
            "pct5_equity_inr":          self.pct5_equity_inr,
            "pct95_equity_inr":         self.pct95_equity_inr,
            "avg_max_drawdown_pct":     self.avg_max_drawdown_pct,
            "worst_loss_streak_p95":    self.worst_loss_streak_p95,
            "equity_curve_points":      self.equity_percentiles,
            "status":                   self.status,
        }


# ── Engine ─────────────────────────────────────────────────────────────────────

class MonteCarloEngine:
    """
    Bootstrap Monte Carlo simulator for trading strategy robustness.

    Each simulation:
      1. Randomly shuffles the trade sequence (sampling with replacement)
      2. Runs the equity curve from initial_capital_inr
      3. Records: final equity, max drawdown, worst loss streak
      4. Checks ruin condition: equity <= ruin_threshold_inr

    Ruin threshold = initial_capital * (1 - ruin_threshold_pct).
    Default: 50% drawdown = ruin.
    """

    MIN_TRADES = 10  # minimum trades for a valid simulation

    def __init__(
        self,
        n_simulations: int = 1000,
        initial_capital_inr: float = 100_000.0,
        ruin_threshold_pct: float = 0.50,
        random_seed: Optional[int] = 42,
    ) -> None:
        self.n_simulations       = n_simulations
        self.initial_capital_inr = initial_capital_inr
        self.ruin_threshold_inr  = initial_capital_inr * (1.0 - ruin_threshold_pct)
        self._rng                = random.Random(random_seed)

    @classmethod
    def from_prod_config(cls) -> "MonteCarloEngine":
        cfg = (get_prod_section("uat") or {}).get("monte_carlo", {})
        return cls(
            n_simulations       = int(cfg.get("n_simulations",       1000)),
            initial_capital_inr = float(cfg.get("initial_capital_inr", 100_000.0)),
            ruin_threshold_pct  = float(cfg.get("ruin_threshold_pct",  0.50)),
            random_seed         = cfg.get("random_seed", 42),
        )

    def run(self, trades: List[TradeOutcome], strategy_id: str = "ALL") -> MonteCarloResult:
        """
        Run N Monte Carlo simulations on the given trade list.

        Returns MonteCarloResult with full distribution statistics.
        """
        n = len(trades)

        if n < self.MIN_TRADES:
            logger.warning(
                "MonteCarloEngine: only %d trades — minimum %d required. "
                "Returning INSUFFICIENT_DATA.", n, self.MIN_TRADES
            )
            return MonteCarloResult(
                strategy=strategy_id, n_simulations=0, n_trades=n,
                p_ruin=0.0, p_ruin_pass=True,
                initial_capital_inr=self.initial_capital_inr,
                ruin_threshold_inr=self.ruin_threshold_inr,
                median_equity_inr=self.initial_capital_inr,
                pct5_equity_inr=self.initial_capital_inr,
                pct95_equity_inr=self.initial_capital_inr,
                avg_max_drawdown_pct=0.0, worst_loss_streak_p95=0,
                equity_percentiles={}, status="INSUFFICIENT_DATA",
            )

        pnls = [t.pnl_inr for t in trades]
        final_equities: List[float] = []
        max_drawdowns: List[float] = []
        loss_streaks: List[int] = []
        ruin_count = 0

        # Store sampled equity curves for 3 representative percentile sims
        _sample_curves: List[List[float]] = []

        for sim_idx in range(self.n_simulations):
            shuffled = self._rng.choices(pnls, k=n)
            equity = self.initial_capital_inr
            peak = equity
            max_dd = 0.0
            ruined = False
            cur_streak = 0
            worst_streak = 0
            curve: List[float] = [equity]

            for pnl in shuffled:
                equity += pnl
                curve.append(round(equity, 2))
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0.0
                max_dd = max(max_dd, dd)
                if pnl < 0:
                    cur_streak += 1
                    worst_streak = max(worst_streak, cur_streak)
                else:
                    cur_streak = 0
                if equity <= self.ruin_threshold_inr:
                    ruined = True
                    break

            if ruined:
                ruin_count += 1
            final_equities.append(equity)
            max_drawdowns.append(max_dd * 100.0)
            loss_streaks.append(worst_streak)

            # Sample ~3 curves (at 5th, 50th, 95th percentile positions)
            if sim_idx in (
                int(self.n_simulations * 0.05),
                int(self.n_simulations * 0.50),
                int(self.n_simulations * 0.95),
            ):
                # Downsample curve to max 20 points for token efficiency
                step = max(1, len(curve) // 20)
                _sample_curves.append(curve[::step])

        p_ruin = ruin_count / self.n_simulations
        sorted_eq = sorted(final_equities)
        i5  = int(self.n_simulations * 0.05)
        i50 = int(self.n_simulations * 0.50)
        i95 = int(self.n_simulations * 0.95)
        sorted_streaks = sorted(loss_streaks)

        status = "PASSED" if p_ruin <= 0.05 else "FAILED"

        equity_percentiles = {
            "p05": _sample_curves[0] if len(_sample_curves) > 0 else [],
            "p50": _sample_curves[1] if len(_sample_curves) > 1 else [],
            "p95": _sample_curves[2] if len(_sample_curves) > 2 else [],
        }

        result = MonteCarloResult(
            strategy=strategy_id,
            n_simulations=self.n_simulations,
            n_trades=n,
            p_ruin=round(p_ruin, 4),
            p_ruin_pass=p_ruin <= 0.05,
            initial_capital_inr=self.initial_capital_inr,
            ruin_threshold_inr=self.ruin_threshold_inr,
            median_equity_inr=round(sorted_eq[i50], 2),
            pct5_equity_inr=round(sorted_eq[i5], 2),
            pct95_equity_inr=round(sorted_eq[i95], 2),
            avg_max_drawdown_pct=round(
                sum(max_drawdowns) / self.n_simulations, 2
            ),
            worst_loss_streak_p95=sorted_streaks[i95],
            equity_percentiles=equity_percentiles,
            status=status,
        )
        logger.info(
            "MonteCarlo %s: n=%d p_ruin=%.1%% median=INR%.0f p5=INR%.0f p95=INR%.0f status=%s",
            strategy_id, n, p_ruin,
            result.median_equity_inr, result.pct5_equity_inr, result.pct95_equity_inr,
            status,
        )
        return result
