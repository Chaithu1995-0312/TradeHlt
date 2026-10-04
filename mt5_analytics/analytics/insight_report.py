"""
insight_report — the post-trade INTELLIGENCE read model (v0.6.0).

Pure, read-only: composes `analytics.metrics_oracle` primitives over persisted
PositionEpisode dicts + FeatureRecord dicts into an immutable, sufficiency-honest
`InsightReport`. INFORMATION, NOT AUTHORITY (§6.5) — it DESCRIBES executed reality for a
human and never feeds the trading spine (`insight -> HUMAN`, never `insight -> decisions`).
No new metric math lives here: every number comes from the independent oracle.

Sufficiency discipline (E-001 / F-019): every conditional bucket carries `n` + a
`SufficiencyStatus`; below `min_n` (default 30) the bucket makes **no claim** — its
`expectancy` / `capture_ratio` are `None`, so an underpowered "edge" cannot be read at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from analytics.metrics_oracle import (  # type: ignore
    adverse_efficiency,
    capture_ratio,
    expectancy_mean,
    largest_loser,
    largest_winner,
    max_drawdown_rr,
    median,
    percentile,
    profit_factor,
    recovery_factor,
    sharpe,
    top_n_contribution,
    win_rate,
)

DEFAULT_MIN_N = 30

# Duration buckets (minutes) — fixed boundaries so attribution keys are stable/deterministic.
_DURATION_EDGES = ((15.0, "<15m"), (60.0, "15-60m"), (240.0, "60-240m"))
_DURATION_TOP = ">240m"


class SufficiencyStatus(Enum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


def _status(n: int, min_n: int) -> SufficiencyStatus:
    return SufficiencyStatus.SUFFICIENT if n >= min_n else SufficiencyStatus.INSUFFICIENT


def _duration_bucket(minutes: "float | None") -> "str | None":
    if minutes is None:
        return None
    for edge, label in _DURATION_EDGES:
        if minutes < edge:
            return label
    return _DURATION_TOP


# ── sub-reports (all frozen; all derived purely from the oracle) ──────────────────

@dataclass(frozen=True)
class ExitEfficiency:
    """How much of the favorable excursion the exits actually captured."""
    n: int                                  # episodes with a measurable favorable excursion (mfe>0)
    median_capture_ratio: "float | None"    # median(realized_r / mfe_r)
    mean_capture_ratio: "float | None"
    total_giveback_r: float                 # Σ(mfe_r - realized_r): R handed back to the market


@dataclass(frozen=True)
class AdverseEfficiency:
    """Heat taken (MAE) per unit of favorable move (MFE), in R."""
    n: int
    median_adverse_ratio: "float | None"    # median(|mae_r| / mfe_r)
    p90_adverse_ratio: "float | None"


@dataclass(frozen=True)
class CostDrag:
    """How much edge disappears into commission + swap (currency; schema-free)."""
    n: int
    total_commission: float
    total_swap: float
    total_cost: float                       # commission + swap
    gross_profit_sum: float                 # Σ gross_profit (price PnL only)
    net_pnl_sum: float                      # Σ net_pnl (= gross + commission + swap)
    cost_fraction_of_gross: "float | None"  # |total_cost| / |gross_profit_sum|
    gross_expectancy: "float | None"        # gross_profit_sum / n (currency/trade)
    net_expectancy: "float | None"          # net_pnl_sum / n (currency/trade)


@dataclass(frozen=True)
class RiskAdjusted:
    """Risk-adjusted summary over the realized-R (gross) series."""
    n: int
    expectancy_r: float
    win_rate: float
    profit_factor: float
    sharpe: float
    recovery_factor: float
    max_drawdown_r: float
    r_p10: "float | None"
    r_p50: "float | None"
    r_p90: "float | None"


@dataclass(frozen=True)
class AttributionBucket:
    """Self-describing conditional cell: renders `⚠ INSUFFICIENT (n/min_n)` with no context."""
    key: str
    n: int
    min_n: int
    status: SufficiencyStatus
    expectancy: "float | None"      # None unless SUFFICIENT — an underpowered bucket makes no claim
    capture_ratio: "float | None"   # None unless SUFFICIENT


@dataclass(frozen=True)
class AttributionReport:
    min_n: int
    by_session: "tuple[AttributionBucket, ...]"
    by_regime: "tuple[AttributionBucket, ...]"
    by_duration_bucket: "tuple[AttributionBucket, ...]"


@dataclass(frozen=True)
class ConcentrationReport:
    """Is the edge diversified, or carried by a couple of outliers?"""
    n: int
    top_5_winner_share: "float | None"   # share of gross winning R from the top-5 winners
    largest_winner_r: float
    largest_loser_r: float
    effective_n: "float | None"          # Herfindahl effective #bets = 1/Σ(pᵢ²) over winning R


@dataclass(frozen=True)
class InsightReport:
    n_episodes: int                      # episodes carrying a realized_r
    min_n: int
    overall_status: SufficiencyStatus
    exit_efficiency: ExitEfficiency
    adverse_efficiency: AdverseEfficiency
    cost_drag: CostDrag
    risk_adjusted: RiskAdjusted
    attribution: AttributionReport
    concentration: ConcentrationReport


# ── builders ──────────────────────────────────────────────────────────────────

def _f(d: dict, k: str) -> "float | None":
    v = d.get(k)
    return float(v) if v is not None else None


def _exit_efficiency(features: "list[dict]") -> ExitEfficiency:
    caps: list[float] = []
    giveback_r = 0.0
    for f in features:
        r, mfe = _f(f, "realized_r"), _f(f, "mfe_r")
        if r is None or mfe is None or mfe <= 0:
            continue
        cr = capture_ratio(r, mfe)
        if cr is not None:
            caps.append(cr)
            giveback_r += (mfe - r)
    n = len(caps)
    return ExitEfficiency(
        n=n,
        median_capture_ratio=median(caps) if caps else None,
        mean_capture_ratio=(sum(caps) / n) if n else None,
        total_giveback_r=round(giveback_r, 10),
    )


def _adverse_efficiency(features: "list[dict]") -> AdverseEfficiency:
    ratios: list[float] = []
    for f in features:
        mae, mfe = _f(f, "mae_r"), _f(f, "mfe_r")
        if mae is None or mfe is None or mfe <= 0:
            continue
        ae = adverse_efficiency(mae, mfe)
        if ae is not None:
            ratios.append(ae)
    return AdverseEfficiency(
        n=len(ratios),
        median_adverse_ratio=median(ratios) if ratios else None,
        p90_adverse_ratio=percentile(ratios, 90.0) if ratios else None,
    )


def _cost_drag(episodes: "list[dict]") -> CostDrag:
    n = len(episodes)
    comm = sum(float(e.get("commission", 0.0) or 0.0) for e in episodes)
    swap = sum(float(e.get("swap", 0.0) or 0.0) for e in episodes)
    gross = sum(float(e.get("gross_profit", 0.0) or 0.0) for e in episodes)
    net = sum(float(e.get("net_pnl", 0.0) or 0.0) for e in episodes)
    cost = comm + swap
    return CostDrag(
        n=n,
        total_commission=round(comm, 10),
        total_swap=round(swap, 10),
        total_cost=round(cost, 10),
        gross_profit_sum=round(gross, 10),
        net_pnl_sum=round(net, 10),
        cost_fraction_of_gross=(abs(cost) / abs(gross)) if gross != 0 else None,
        gross_expectancy=round(gross / n, 10) if n else None,
        net_expectancy=round(net / n, 10) if n else None,
    )


def _risk_adjusted(rr: "list[float]") -> RiskAdjusted:
    return RiskAdjusted(
        n=len(rr),
        expectancy_r=round(expectancy_mean(rr), 10),
        win_rate=round(win_rate(rr), 10),
        profit_factor=round(profit_factor(rr), 10),
        sharpe=round(sharpe(rr), 10),
        recovery_factor=round(recovery_factor(rr), 10),
        max_drawdown_r=round(max_drawdown_rr(rr), 10),
        r_p10=percentile(rr, 10.0) if rr else None,
        r_p50=percentile(rr, 50.0) if rr else None,
        r_p90=percentile(rr, 90.0) if rr else None,
    )


def _bucket(key: str, rr: "list[float]", caps: "list[float]", min_n: int) -> AttributionBucket:
    n = len(rr)
    status = _status(n, min_n)
    sufficient = status is SufficiencyStatus.SUFFICIENT
    return AttributionBucket(
        key=key,
        n=n,
        min_n=min_n,
        status=status,
        expectancy=round(expectancy_mean(rr), 10) if (sufficient and rr) else None,
        capture_ratio=median(caps) if (sufficient and caps) else None,
    )


def _attribution_axis(features: "list[dict]", key_fn, min_n: int) -> "tuple[AttributionBucket, ...]":
    by_rr: dict[str, list[float]] = {}
    by_cap: dict[str, list[float]] = {}
    for f in features:
        k = key_fn(f)
        if k is None:
            k = "?"
        r = _f(f, "realized_r")
        if r is not None:
            by_rr.setdefault(k, []).append(r)
        mfe = _f(f, "mfe_r")
        if r is not None and mfe is not None and mfe > 0:
            cr = capture_ratio(r, mfe)
            if cr is not None:
                by_cap.setdefault(k, []).append(cr)
    keys = sorted(set(by_rr) | set(by_cap))   # deterministic ordering
    return tuple(
        _bucket(k, by_rr.get(k, []), by_cap.get(k, []), min_n) for k in keys
    )


def _concentration(rr: "list[float]") -> ConcentrationReport:
    wins = [r for r in rr if r > 0]
    total = sum(wins)
    if total > 0:
        shares = [w / total for w in wins]
        eff_n = 1.0 / sum(s * s for s in shares)
    else:
        eff_n = None
    return ConcentrationReport(
        n=len(rr),
        top_5_winner_share=top_n_contribution(rr, 5),
        largest_winner_r=round(largest_winner(rr), 10),
        largest_loser_r=round(largest_loser(rr), 10),
        effective_n=round(eff_n, 10) if eff_n is not None else None,
    )


def build_insight(
    episodes: "list[dict]", features: "list[dict]", *, min_n: int = DEFAULT_MIN_N
) -> InsightReport:
    """Compose persisted episodes + features into the immutable post-trade InsightReport.

    `episodes` supplies cash truth (gross_profit / commission / swap / net_pnl); `features`
    supply the R-space path metrics (realized_r / mfe_r / mae_r / session / regime /
    duration_minutes). Read-only; no MT5, no writes, no spine feedback.
    """
    rr = [v for v in (_f(f, "realized_r") for f in features) if v is not None]
    return InsightReport(
        n_episodes=len(rr),
        min_n=min_n,
        overall_status=_status(len(rr), min_n),
        exit_efficiency=_exit_efficiency(features),
        adverse_efficiency=_adverse_efficiency(features),
        cost_drag=_cost_drag(episodes),
        risk_adjusted=_risk_adjusted(rr),
        attribution=AttributionReport(
            min_n=min_n,
            by_session=_attribution_axis(features, lambda f: f.get("session"), min_n),
            by_regime=_attribution_axis(features, lambda f: f.get("regime"), min_n),
            by_duration_bucket=_attribution_axis(
                features, lambda f: _duration_bucket(_f(f, "duration_minutes")), min_n
            ),
        ),
        concentration=_concentration(rr),
    )
