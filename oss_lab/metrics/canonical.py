"""Canonical metric calculation from normalized BenchmarkTradeRecord lists.

METRIC AUTHORITY RULE:
  Do NOT blindly compare framework-native metrics.
  Compute independently from PRESENT fields on BenchmarkTradeRecord.

Formulas deliberately align with research.measurement.metrics.EdgeAggregator
(profit factor = sum(wins)/sum(|losses|), expectancy = mean(net), drawdown on
cumulative equity) but operate on the OSS-lab ledger and carry no promotion
authority. Research EdgeAggregator remains the edge-discovery quarantine path;
this module is the cross-engine comparison path.

Never invent missing PnL — trades lacking net_pnl (and gross fallback) are
counted as incomplete and excluded from economic aggregates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import mean, median
from typing import Any, Optional, Sequence

from oss_lab.contracts.presence import Presence
from oss_lab.contracts.trade_record import BenchmarkTradeRecord


@dataclass
class CanonicalMetrics:
    """Descriptive comparison metrics — NOT promotion authority."""

    n_trades_completed: int = 0
    n_trades_incomplete: int = 0
    n_signals: Optional[int] = None  # separate counters if provided
    n_orders: Optional[int] = None
    n_fills: Optional[int] = None

    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    win_rate: Optional[float] = None

    gross_pnl_sum: Optional[float] = None
    net_pnl_sum: Optional[float] = None
    fees_sum: Optional[float] = None
    spread_cost_sum: Optional[float] = None
    slippage_cost_sum: Optional[float] = None

    profit_factor: Optional[float] = None
    expectancy: Optional[float] = None  # mean(net_pnl)
    expectancy_r: Optional[float] = None  # mean(net_pnl / initial_risk)
    max_drawdown: Optional[float] = None  # peak-to-trough on cumulative net_pnl
    sharpe: Optional[float] = None  # UNKNOWN unless return series + frequency declared

    mfe_median: Optional[float] = None
    mae_median: Optional[float] = None
    mfe_r_median: Optional[float] = None
    mae_r_median: Optional[float] = None

    # Explicit status map for matrix cells
    status: dict[str, str] = field(default_factory=dict)
    definition_notes: list[str] = field(default_factory=list)
    authority: str = "RESEARCH_LAB_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pnl(t: BenchmarkTradeRecord) -> Optional[float]:
    if t.net_pnl is not None and t.presence_of("net_pnl") == Presence.PRESENT:
        return float(t.net_pnl)
    if t.gross_pnl is not None and t.presence_of("gross_pnl") == Presence.PRESENT:
        return float(t.gross_pnl)
    return None


def _max_drawdown(pnls: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def compute_canonical_metrics(
    trades: Sequence[BenchmarkTradeRecord],
    *,
    n_signals: Optional[int] = None,
    n_orders: Optional[int] = None,
    n_fills: Optional[int] = None,
    return_frequency: Optional[str] = None,
) -> CanonicalMetrics:
    """Compute independent metrics. Sharpe stays UNKNOWN without declared frequency + series."""
    m = CanonicalMetrics(
        n_signals=n_signals,
        n_orders=n_orders,
        n_fills=n_fills,
        definition_notes=[
            "profit_factor = sum(positive net_pnl) / abs(sum(negative net_pnl))",
            "expectancy = mean(net_pnl) over completed trades",
            "expectancy_r = mean(net_pnl / initial_risk) when initial_risk PRESENT and > 0",
            "max_drawdown = peak-to-trough of cumulative net_pnl equity curve",
            "sharpe requires declared return_frequency + equity series — else UNKNOWN",
            "Authority: RESEARCH_LAB_ONLY — never promotion evidence without MC seal",
        ],
    )

    pnls: list[float] = []
    r_multiples: list[float] = []
    mfes: list[float] = []
    maes: list[float] = []
    mfe_rs: list[float] = []
    mae_rs: list[float] = []
    grosses: list[float] = []
    fees: list[float] = []
    spreads: list[float] = []
    slips: list[float] = []

    for t in trades:
        p = _pnl(t)
        if p is None:
            m.n_trades_incomplete += 1
            continue
        m.n_trades_completed += 1
        pnls.append(p)
        if p > 0:
            m.wins += 1
        elif p < 0:
            m.losses += 1
        else:
            m.breakevens += 1

        if t.gross_pnl is not None and t.presence_of("gross_pnl") == Presence.PRESENT:
            grosses.append(float(t.gross_pnl))
        if t.fees is not None and t.presence_of("fees") == Presence.PRESENT:
            fees.append(float(t.fees))
        if t.spread_cost is not None and t.presence_of("spread_cost") == Presence.PRESENT:
            spreads.append(float(t.spread_cost))
        if t.slippage_cost is not None and t.presence_of("slippage_cost") == Presence.PRESENT:
            slips.append(float(t.slippage_cost))
        if (
            t.initial_risk is not None
            and t.presence_of("initial_risk") == Presence.PRESENT
            and float(t.initial_risk) > 0
        ):
            r_multiples.append(p / float(t.initial_risk))
        if t.mfe is not None and t.presence_of("mfe") == Presence.PRESENT:
            mfes.append(float(t.mfe))
        if t.mae is not None and t.presence_of("mae") == Presence.PRESENT:
            maes.append(float(t.mae))
        if t.mfe_r is not None and t.presence_of("mfe_r") == Presence.PRESENT:
            mfe_rs.append(float(t.mfe_r))
        if t.mae_r is not None and t.presence_of("mae_r") == Presence.PRESENT:
            mae_rs.append(float(t.mae_r))

    if not pnls:
        m.status = {
            "profit_factor": "UNKNOWN",
            "expectancy": "UNKNOWN",
            "max_drawdown": "UNKNOWN",
            "sharpe": "UNKNOWN",
            "trade_count": "MEASURED",
        }
        return m

    win_sum = sum(p for p in pnls if p > 0)
    loss_sum = -sum(p for p in pnls if p < 0)
    if loss_sum > 0:
        m.profit_factor = win_sum / loss_sum
        m.status["profit_factor"] = "MEASURED"
    elif win_sum > 0:
        m.profit_factor = float("inf")
        m.status["profit_factor"] = "MEASURED"
    else:
        m.profit_factor = 0.0
        m.status["profit_factor"] = "MEASURED"

    m.expectancy = mean(pnls)
    m.status["expectancy"] = "MEASURED"
    m.net_pnl_sum = sum(pnls)
    m.win_rate = m.wins / len(pnls) if pnls else None
    m.max_drawdown = _max_drawdown(pnls)
    m.status["max_drawdown"] = "MEASURED"
    m.status["trade_count"] = "MEASURED"

    if r_multiples:
        m.expectancy_r = mean(r_multiples)
        m.status["expectancy_r"] = "MEASURED"
    else:
        m.status["expectancy_r"] = "UNKNOWN"

    if grosses:
        m.gross_pnl_sum = sum(grosses)
        m.status["gross_pnl"] = "MEASURED"
    else:
        m.status["gross_pnl"] = "UNKNOWN"
    if fees:
        m.fees_sum = sum(fees)
        m.status["fees"] = "MEASURED"
    else:
        m.status["fees"] = "UNKNOWN"
    if spreads:
        m.spread_cost_sum = sum(spreads)
        m.status["spread_cost"] = "MEASURED"
    else:
        m.status["spread_cost"] = "UNKNOWN"
    if slips:
        m.slippage_cost_sum = sum(slips)
        m.status["slippage_cost"] = "MEASURED"
    else:
        m.status["slippage_cost"] = "UNKNOWN"

    if mfes:
        m.mfe_median = median(mfes)
        m.status["mfe"] = "MEASURED"
    else:
        m.status["mfe"] = "UNKNOWN"
    if maes:
        m.mae_median = median(maes)
        m.status["mae"] = "MEASURED"
    else:
        m.status["mae"] = "UNKNOWN"
    if mfe_rs:
        m.mfe_r_median = median(mfe_rs)
        m.status["mfe_r"] = "MEASURED"
    else:
        m.status["mfe_r"] = "UNKNOWN"
    if mae_rs:
        m.mae_r_median = median(mae_rs)
        m.status["mae_r"] = "MEASURED"
    else:
        m.status["mae_r"] = "UNKNOWN"

    # Sharpe: refuse without declared frequency (never invent annualization).
    if return_frequency is None:
        m.sharpe = None
        m.status["sharpe"] = "UNKNOWN"
        m.definition_notes.append(
            "sharpe=UNKNOWN: pass return_frequency + use equity series to close gap"
        )
    else:
        # Population std of per-trade net_pnl — NOT annualized; frequency only labeled.
        if len(pnls) >= 2:
            mu = mean(pnls)
            var = sum((x - mu) ** 2 for x in pnls) / len(pnls)
            std = var ** 0.5
            m.sharpe = (mu / std) if std > 0 else None
            m.status["sharpe"] = "MEASURED" if m.sharpe is not None else "UNKNOWN"
            m.definition_notes.append(
                f"sharpe = mean(net_pnl)/std(net_pnl) per trade; frequency label={return_frequency}; "
                "NOT annualized"
            )
        else:
            m.status["sharpe"] = "UNKNOWN"

    return m
