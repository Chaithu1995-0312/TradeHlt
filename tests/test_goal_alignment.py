"""
Research-loop G001 alignment floor (target-strategy-architecture.md §13 item6 / §14.D).

goal_alignment.py generalizes the ad-hoc mapping proven in
scripts/research/run_h_g001_001_sweep_veto.py. These tests pin: the unit-honest
metric mapping (no silent trades_per_month guess, no R->% drawdown fabrication),
and that job_kind never perturbs an existing config's config_sha256.
"""
from __future__ import annotations

import pytest

from research.config import ResearchConfig
from research.contracts import EdgeReport
from research.goal_alignment import (
    corpus_span_months,
    edge_report_metrics_dict,
    goal_report_for_edge,
)

_CFG = {
    "harness": {"warmup": 50, "window_size": 20, "min_samples": 30},
    "forward_walk": {"max_forward": 96, "trail_mult": 1.0},
    "signal": {"apply_signal_defaults": True, "sl_atr_mult": 1.0, "tp_atr_mult": 2.0},
    "costs": {"round_trip_bps": 12.0},
    "qualification": {},
    "universe": {"data_dir": "data", "pattern": "*.csv"},
}


def _edge_report(**overrides) -> EdgeReport:
    base = dict(
        hypothesis="h", instruments=["XAUUSD"], n=40, wins=15, losses=25,
        win_rate=0.375, profit_factor=1.1, expectancy_rr=0.05,
        mfe_p50=0.5, mfe_p90=1.5, mae_p50=-0.3, mae_p90=-0.9,
        median_time_to_failure=4.0, continuation_prob=0.4, max_drawdown_rr=-6.0,
    )
    base.update(overrides)
    return EdgeReport(**base)


def test_metrics_dict_omits_trades_per_month_without_months():
    m = edge_report_metrics_dict(_edge_report())
    assert "trades_per_month" not in m
    assert "max_drawdown_pct" not in m  # unit mismatch — never fabricated


def test_metrics_dict_computes_trades_per_month_when_months_given():
    m = edge_report_metrics_dict(_edge_report(n=40), months_observed=4.0)
    assert m["trades_per_month"] == 10.0


def test_avg_rr_proxy_matches_expectancy_rr_documented_convention():
    m = edge_report_metrics_dict(_edge_report(expectancy_rr=0.123))
    assert m["avg_rr"] == pytest.approx(0.123)
    assert m["expectancy_r"] == pytest.approx(0.123)


def test_goal_report_for_edge_returns_validator_shape():
    report = goal_report_for_edge(_edge_report(), months_observed=2.0)
    assert "decision" in report and "criteria" in report and "enabled" in report


def test_job_kind_never_perturbs_existing_config_hash():
    baseline = ResearchConfig.from_dict(_CFG)
    with_kind = ResearchConfig.from_dict({**_CFG, "job_kind": "threshold_search"})
    assert baseline.sha256() == with_kind.sha256()
    assert with_kind.job_kind == "threshold_search"
    assert baseline.job_kind == "unspecified"


def test_job_kind_rejects_unknown_value():
    with pytest.raises(ValueError):
        ResearchConfig.from_dict({**_CFG, "job_kind": "both"})
