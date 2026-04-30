"""Tests for src/expansion/ modules."""
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from src.expansion.policy_schema import (
    ExpansionCandidate, ExpansionPlan, ExpansionStep, PARAM_BOUNDS,
    MAX_PARAM_CHANGE, MIN_PNL_RATIO, MAX_DRAWDOWN_RATIO
)
from src.expansion.config_mutator import ConfigMutator
from src.expansion.evaluator import Evaluator


# ── ConfigMutator tests ────────────────────────────────────────────────────────

def test_mutate_decrease():
    config = {"fusion_min_score": 0.65, "version": "v1"}
    new = ConfigMutator.mutate(config, "fusion_min_score", "decrease", 0.05)
    assert new["fusion_min_score"] == pytest.approx(0.60, abs=1e-4)
    assert config["fusion_min_score"] == 0.65  # original not mutated


def test_mutate_increase():
    config = {"fusion_min_score": 0.65}
    new = ConfigMutator.mutate(config, "fusion_min_score", "increase", 0.05)
    assert new["fusion_min_score"] == pytest.approx(0.70, abs=1e-4)


def test_mutate_clips_to_floor():
    config = {"fusion_min_score": 0.42}
    new = ConfigMutator.mutate(config, "fusion_min_score", "decrease", 0.05)
    lo, _ = PARAM_BOUNDS["fusion_min_score"]
    assert new["fusion_min_score"] >= lo


def test_mutate_respects_max_param_change():
    config = {"fusion_min_score": 0.65}
    # Try to make a huge change — should be capped
    new = ConfigMutator.mutate(config, "fusion_min_score", "decrease", 0.30,
                                baseline_value=0.65)
    change = abs(new["fusion_min_score"] - 0.65)
    assert change <= MAX_PARAM_CHANGE + 1e-6


def test_mutate_raises_for_unknown_param():
    config = {"fusion_min_score": 0.65}
    with pytest.raises(ValueError, match="not in config"):
        ConfigMutator.mutate(config, "nonexistent_param", "decrease", 0.05)


# ── Evaluator tests ────────────────────────────────────────────────────────────

def _baseline():
    return {"total_pnl": 25000.0, "max_drawdown": 0.18, "trades": 42, "wins": 23}

def _metrics(pnl, dd, trades):
    return {"total_pnl": pnl, "max_drawdown": dd, "trades": trades, "wins": int(trades * 0.55)}


def test_evaluator_score_higher_for_better_pnl():
    baseline = _baseline()
    good = _metrics(32000, 0.18, 60)
    bad = _metrics(20000, 0.25, 55)
    assert Evaluator.score(good, baseline) > Evaluator.score(bad, baseline)


def test_guardrails_pass_normal():
    baseline = _baseline()
    metrics = _metrics(26000, 0.20, 50)
    passes, reason = Evaluator.passes_guardrails(metrics, baseline)
    assert passes


def test_guardrails_fail_pnl_drop():
    baseline = _baseline()
    metrics = _metrics(20000, 0.18, 55)  # < 90% of 25000
    passes, reason = Evaluator.passes_guardrails(metrics, baseline)
    assert not passes
    assert "pnl" in reason.lower()


def test_guardrails_fail_drawdown():
    baseline = _baseline()
    metrics = _metrics(26000, 0.32, 55)  # > 150% of 0.18
    passes, reason = Evaluator.passes_guardrails(metrics, baseline)
    assert not passes
    assert "drawdown" in reason.lower()


def test_tier_classification():
    baseline = _baseline()
    assert Evaluator.classify_config(100, 80, 42, 42) == "SAFE"      # ratio=1.0
    assert Evaluator.classify_config(100, 80, 60, 42) == "BALANCED"  # ratio=1.43
    assert Evaluator.classify_config(100, 80, 90, 42) == "AGGRESSIVE"  # ratio=2.14


# ── ExpansionPlan schema tests ─────────────────────────────────────────────────

def test_expansion_candidate_construction():
    c = ExpansionCandidate(
        param="fusion_min_score",
        direction="decrease",
        step=0.05,
        priority=1,
        floor=0.40,
        ceiling=0.85,
    )
    assert c.param == "fusion_min_score"
    assert c.step == 0.05


def test_expansion_plan_defaults():
    plan = ExpansionPlan(base_metrics={"trades": 42})
    assert plan.target_multiplier == 2.0
    assert plan.candidates == []


# ── ExpansionEngine integration test (mocked backtest) ────────────────────────

def test_expansion_engine_run_with_mocked_backtest():
    from src.expansion.expansion_engine import ExpansionEngine

    base_config = {
        "version": "test_v1",
        "fusion_min_score": 0.65,
        "zone_gate_threshold": 0.60,
        "body_ratio_min": 0.65,
        "min_rr_ratio": 2.0,
    }

    plan = ExpansionPlan(
        base_metrics={"trades": 42, "total_pnl": 25000.0, "max_drawdown": 0.18},
        candidates=[
            ExpansionCandidate("fusion_min_score", "decrease", 0.05, 1, 0.40, 0.85),
        ],
        target_multiplier=1.5,
    )

    engine = ExpansionEngine(target_multiplier=1.5)

    # Mock BacktestRunner
    call_count = [0]
    def mock_backtest(runner_cls, config, csv_paths):
        call_count[0] += 1
        # Baseline: 42 trades; subsequent: 55 trades (better)
        trades = 42 if call_count[0] == 1 else 55
        return {"trades": trades, "wins": int(trades * 0.56), "losses": int(trades * 0.44),
                "total_pnl": 25000 + (trades - 42) * 300, "max_drawdown": 0.19,
                "win_rate": 0.56, "expectancy": 0.8, "fitness": 0.45}

    with patch.object(engine, "_run_backtest", side_effect=mock_backtest):
        result = engine.run(base_config, plan, ["data/test.csv"])

    assert result.best_config is not None
    assert len(result.configs) >= 1
    assert len(result.steps) > 0


def test_expansion_engine_stops_on_pnl_drop():
    from src.expansion.expansion_engine import ExpansionEngine

    base_config = {"version": "v1", "fusion_min_score": 0.65, "zone_gate_threshold": 0.60,
                   "body_ratio_min": 0.65, "min_rr_ratio": 2.0}

    plan = ExpansionPlan(
        base_metrics={"trades": 42, "total_pnl": 25000.0, "max_drawdown": 0.18},
        candidates=[ExpansionCandidate("fusion_min_score", "decrease", 0.05, 1, 0.40, 0.85)],
    )

    engine = ExpansionEngine()
    call_count = [0]

    def mock_backtest(runner_cls, config, csv_paths):
        call_count[0] += 1
        if call_count[0] == 1:
            return {"trades": 42, "wins": 23, "losses": 19, "total_pnl": 25000.0,
                    "max_drawdown": 0.18, "win_rate": 0.55}
        # Step 1: drop PnL below 90% threshold → should stop
        return {"trades": 50, "wins": 20, "losses": 30, "total_pnl": 15000.0,
                "max_drawdown": 0.20, "win_rate": 0.40}

    with patch.object(engine, "_run_backtest", side_effect=mock_backtest):
        result = engine.run(base_config, plan, ["data/test.csv"])

    # Rejected step should be in steps with rejected status
    rejected = [s for s in result.steps if "rejected" in s.status]
    assert len(rejected) >= 1