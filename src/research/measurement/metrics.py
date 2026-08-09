"""metrics.py — EdgeAggregator: turn a list of Outcomes into an EdgeReport.

Computes only the *measurable* fields (win rate, profit factor, expectancy, MFE/MAE
distribution, continuation probability, time-to-failure, drawdown). OOS split,
significance vs. baseline, meta-profile, economic rationale, and the final verdict are
filled by later milestones (M4 / M4.5 / M4.7). Pure stdlib — no numpy/pandas.

QUARANTINE NOTE (trust-layer WS2B, 2026-06-10)
    This is the Edge Discovery research platform's OWN metric layer, intentionally
    isolated from the live spine (its own `EdgeReport`/`Outcome` contracts, byte-identical
    determinism proven in tests/research/). It is deliberately NOT routed through
    `analytics/metrics_oracle` or `runtime/backtest_v2` so the research platform stays
    decoupled and dependency-free. Its metrics are research telemetry and MUST NOT feed
    promotion/validation decisions. See docs/analysis/backtest-trust-audit-2026-06-10.md §3.
"""

from __future__ import annotations

from statistics import median
from typing import Sequence

from research.contracts import EdgeReport, Outcome
from research.costs import DEFAULT_COST_MODEL, CostModel


def _percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (p in [0, 100]). Empty -> 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


class EdgeAggregator:
    """Aggregates forward-walk Outcomes into an EdgeReport."""

    def aggregate(
        self,
        hypothesis: str,
        instruments: Sequence[str],
        outcomes: Sequence[Outcome],
        cost_model: CostModel = DEFAULT_COST_MODEL,
    ) -> EdgeReport:
        outs = list(outcomes)
        n = len(outs)

        if n == 0:
            return EdgeReport(
                hypothesis=hypothesis, instruments=list(instruments), n=0,
                wins=0, losses=0, win_rate=0.0, profit_factor=0.0, expectancy_rr=0.0,
                mfe_p50=0.0, mfe_p90=0.0, mae_p50=0.0, mae_p90=0.0,
                median_time_to_failure=0.0, continuation_prob=0.0, max_drawdown_rr=0.0,
                round_trip_bps=cost_model.round_trip_bps, reject_reasons=["no_outcomes"],
            )

        # NET every gross R by the round-trip cost — all gates qualify on NET.
        rrs = [
            cost_model.net_rr(o.rr_achieved, o.signal.entry, o.signal.sl_atr_mult * o.signal.atr)
            for o in outs
        ]
        wins = sum(1 for r in rrs if r > 0)
        losses = sum(1 for r in rrs if r <= 0)
        gross_win = sum(r for r in rrs if r > 0)
        gross_loss = -sum(r for r in rrs if r < 0)   # positive magnitude

        win_rate = wins / n
        # Profit factor: gross win / gross loss. No losses with positive wins -> inf-like cap.
        if gross_loss > 0:
            profit_factor = gross_win / gross_loss
        else:
            profit_factor = float("inf") if gross_win > 0 else 0.0
        expectancy_rr = sum(rrs) / n

        mfes = [o.mfe for o in outs]
        maes = [o.mae for o in outs]
        failures = [o.time_to_failure for o in outs if o.time_to_failure is not None]
        continuation_prob = sum(1 for o in outs if o.reached_1r) / n

        return EdgeReport(
            hypothesis=hypothesis,
            instruments=list(instruments),
            n=n,
            wins=wins,
            losses=losses,
            win_rate=round(win_rate, 4),
            profit_factor=round(profit_factor, 4) if profit_factor != float("inf") else profit_factor,
            expectancy_rr=round(expectancy_rr, 4),
            mfe_p50=round(_percentile(mfes, 50), 6),
            mfe_p90=round(_percentile(mfes, 90), 6),
            mae_p50=round(_percentile(maes, 50), 6),
            mae_p90=round(_percentile(maes, 10), 6),   # p10 = the worst-decile adverse move
            median_time_to_failure=float(median(failures)) if failures else 0.0,
            continuation_prob=round(continuation_prob, 4),
            max_drawdown_rr=round(self._max_drawdown_rr(rrs), 4),
            round_trip_bps=cost_model.round_trip_bps,
        )

    @staticmethod
    def _max_drawdown_rr(rrs: list[float]) -> float:
        """Peak-to-trough drawdown of the cumulative-R equity curve (returned positive)."""
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in rrs:
            equity += r
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
        return max_dd
