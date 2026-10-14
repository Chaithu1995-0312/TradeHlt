"""
goal_alignment.py
================================================================================
Research-loop G001 alignment (target-strategy-architecture.md §13 item6 / §14.D
"Expectancy/PF/DD/trades-per-month vs G001 reported every candidate").

Generalizes the ad-hoc mapping already proven in
`scripts/research/run_h_g001_001_sweep_veto.py` (`_metrics_dict` /
`_goal_metrics_for_validator`) into a reusable module so every research driver
can report the same gap-to-G001 the backtest side already does via
`config_layer.goal_validator.GoalValidator` / `BacktestMetrics.distribution["goal_report"]`.

Unit-honesty (matches the established precedent, not a new convention):
  - `trades_per_month` requires an explicit observation window — EdgeReport carries
    a trade COUNT, not a corpus duration, so callers that know the corpus span
    (via `corpus_span_months`) pass it in; otherwise this criterion SKIPs rather
    than guessing a duration.
  - `avg_rr` has no faithful EdgeReport field; `expectancy_rr` (net mean R) is
    used as the same documented proxy the sweep-veto driver uses.
  - `max_drawdown_pct` is intentionally OMITTED: EdgeReport's `max_drawdown_rr` is
    a sequence-of-trades R-multiple drawdown, not an equity percentage, and
    converting units silently would be a fabrication, not a measurement.

This module is measure-only — it never gates a research run and never writes
production config (§4 research/isolation invariant).
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

import pandas as pd

from config_layer.goal_schema import GoalSpec, load_goal_spec
from config_layer.strict_config import require_all
from config_layer.goal_validator import GoalReport, GoalValidator
from research.contracts import EdgeReport


def corpus_span_months(csv_path: str) -> float:
    """Wall-clock span of an OHLCV CSV's timestamp column, in months (~30.437
    days). Floors at one bar's worth of months so a degenerate 0/1-row corpus
    never divides trades_per_month by zero."""
    from data_ingestion.corpus_store import load as _corpus_load  # CH-corpus-ssot: the corpus SSOT
    df = _corpus_load(csv_path, sequence_check=False).frame()
    ts_col = next((c for c in df.columns if str(c).strip().lower() in
                   ("timestamp", "datetime", "date time", "open time")), None)
    if ts_col is None:
        raise ValueError(
            f"corpus_span_months: no timestamp-like column in {csv_path} "
            f"(columns={list(df.columns)})"
        )
    ts = pd.to_datetime(df[ts_col], errors="coerce")
    if len(ts) < 2 or ts.isna().all():
        return 1.0
    delta = ts.iloc[-1] - ts.iloc[0]
    days = max(delta.total_seconds() / 86400.0, 1.0)
    return max(days / 30.437, 1.0 / 30.437)


def edge_report_metrics_dict(report: EdgeReport, months_observed: Optional[float] = None) -> dict:
    """Map an EdgeReport onto the metric-name vocabulary GoalValidator.evaluate()
    understands. `months_observed=None` omits trades_per_month (SKIP, not a guess)."""
    metrics: dict[str, Any] = {
        "win_rate":     float(report.win_rate),
        "expectancy_r": float(report.expectancy_rr),
        # Documented proxy (matches run_h_g001_001_sweep_veto.py precedent): no
        # faithful "average RR achieved" field exists on EdgeReport, so net mean
        # R (expectancy_rr) stands in for avg_rr. NOT a distinct measurement.
        "avg_rr":       float(report.expectancy_rr),
        # max_drawdown_pct intentionally omitted: max_drawdown_rr is a sequence-of-
        # trades R-multiple drawdown, not a portfolio-equity percentage — the units
        # are not comparable without a risk-per-trade assumption this module
        # refuses to invent silently.
    }
    if months_observed is not None and months_observed > 0:
        metrics["trades_per_month"] = round(report.n / months_observed, 4)
    return metrics


def goal_report_for_edge(
    report: EdgeReport,
    months_observed: Optional[float] = None,
    spec: Optional[GoalSpec] = None,
) -> dict:
    """The G001 gap block for one EdgeReport — same shape as the backtest side's
    `BacktestMetrics.distribution["goal_report"]`. Measure-only; never gates."""
    metrics = edge_report_metrics_dict(report, months_observed)
    gr: GoalReport = GoalValidator.evaluate(metrics, spec=spec or load_goal_spec())
    return gr.to_dict()


def attach_goal_reports(
    run_result_dict: dict,
    months_observed: Optional[float] = None,
    spec: Optional[GoalSpec] = None,
) -> dict:
    """Additively attach `goal_report` to `run_result_to_dict()`'s pooled + each
    per_instrument entry, in place, and return it. `months_observed=None`
    (the default) means every trades_per_month criterion reports SKIP — callers
    that want it evaluated must supply the corpus span explicitly
    (`corpus_span_months`), matching the "no silent guess" rule."""
    goal_spec = spec or load_goal_spec()

    def _attach(edge_dict: dict) -> None:
        # edge_dict is dataclasses.asdict(EdgeReport) — rebuild the minimal
        # fields goal_report_for_edge needs rather than requiring the caller to
        # keep the original EdgeReport object around.
        require_all(
            edge_dict,
            ["hypothesis", "instruments", "n", "wins", "losses", "win_rate",
             "profit_factor", "expectancy_rr", "mfe_p50", "mfe_p90", "mae_p50",
             "mae_p90", "median_time_to_failure", "continuation_prob",
             "max_drawdown_rr"],
            section_name="edge_report",
            consumer="attach_goal_reports",
        )
        fake = EdgeReport(
            hypothesis=edge_dict["hypothesis"],
            instruments=edge_dict["instruments"],
            n=edge_dict["n"],
            wins=edge_dict["wins"],
            losses=edge_dict["losses"],
            win_rate=edge_dict["win_rate"],
            profit_factor=edge_dict["profit_factor"],
            expectancy_rr=edge_dict["expectancy_rr"],
            mfe_p50=edge_dict["mfe_p50"],
            mfe_p90=edge_dict["mfe_p90"],
            mae_p50=edge_dict["mae_p50"],
            mae_p90=edge_dict["mae_p90"],
            median_time_to_failure=edge_dict["median_time_to_failure"],
            continuation_prob=edge_dict["continuation_prob"],
            max_drawdown_rr=edge_dict["max_drawdown_rr"],
        )
        edge_dict["goal_report"] = goal_report_for_edge(fake, months_observed, goal_spec)

    if "pooled" in run_result_dict:
        _attach(run_result_dict["pooled"])
    per_instrument = run_result_dict.get("per_instrument")
    if per_instrument:
        for v in per_instrument.values():
            _attach(v)
    return run_result_dict
