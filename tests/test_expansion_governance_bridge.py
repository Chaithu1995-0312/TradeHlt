"""
test_expansion_governance_bridge.py
=====================================
Phase A: Expansion → Governance Bridge tests.

Covers:
  - ViabilityFilter: passes/fails for pnl, drawdown, trades
  - Bridge: staged list populated when viable configs pass all gates
  - Bridge: empty staged when no viable configs
  - Bridge: hard assertion blocks pnl <= baseline
  - Bridge: history log written for accepted + rejected
  - Bridge: result always has required keys
  - Config diff generation is correct
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.expansion.policy_schema import (
    ExpansionCandidate,
    ExpansionPlan,
    ExpansionResult,
    ExpansionStep,
)
from src.governance.expansion_integration import (
    ExpansionGovernanceBridge,
    ViabilityFilter,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_plan():
    return ExpansionPlan(
        base_metrics={"trades": 42, "total_pnl": 25000.0, "max_drawdown": 0.18},
        candidates=[
            ExpansionCandidate("fusion_min_score", "decrease", 0.05, 1, 0.40, 0.85)
        ],
        target_multiplier=1.5,
    )


def _base_config():
    return {
        "version": "test_v1",
        "fusion_min_score": 0.65,
        "zone_gate_threshold": 0.60,
        "body_ratio_min": 0.65,
        "min_rr_ratio": 2.0,
    }


def _make_expansion_result(base_config, baseline_metrics):
    """Return a mocked ExpansionResult with all three tiers."""
    balanced_cfg = dict(base_config)
    balanced_cfg["fusion_min_score"] = 0.60
    aggressive_cfg = dict(base_config)
    aggressive_cfg["fusion_min_score"] = 0.55

    return ExpansionResult(
        baseline={"config": base_config, "metrics": baseline_metrics},
        configs=[
            {"name": "SAFE", "config": base_config, "metrics": baseline_metrics,
             "trades": baseline_metrics["trades"], "pnl": baseline_metrics["total_pnl"]},
            {"name": "BALANCED", "config": balanced_cfg,
             "metrics": {"trades": 60, "total_pnl": 28000.0, "max_drawdown": 0.19},
             "trades": 60, "pnl": 28000.0},
            {"name": "AGGRESSIVE", "config": aggressive_cfg,
             "metrics": {"trades": 80, "total_pnl": 30000.0, "max_drawdown": 0.22},
             "trades": 80, "pnl": 30000.0},
        ],
        steps=[],
        best_config=balanced_cfg,
        best_metrics={"trades": 60, "total_pnl": 28000.0, "max_drawdown": 0.19},
    )


def _mock_shadow_gate(promoted=True):
    gate = MagicMock()
    gate.promote_if_superior.return_value = {
        "promoted": promoted,
        "reason": "promoted" if promoted else "not promoted",
    }
    return gate


def _viable_fwd_metrics(pnl=26000.0, trades=45, drawdown=0.20):
    return {
        "trades": trades, "total_pnl": pnl, "max_drawdown": drawdown,
        "wins": 25, "losses": 20, "win_rate": 0.56,
    }


# ── ViabilityFilter tests ──────────────────────────────────────────────────────

def test_viability_passes_good_metrics():
    ok, reason = ViabilityFilter.passes(
        {"total_pnl": 5000.0, "max_drawdown": 0.15, "trades": 35}
    )
    assert ok
    assert reason == ""


def test_viability_fails_negative_pnl():
    ok, reason = ViabilityFilter.passes(
        {"total_pnl": -100.0, "max_drawdown": 0.10, "trades": 35}
    )
    assert not ok
    assert "pnl" in reason.lower()


def test_viability_fails_zero_pnl():
    ok, _ = ViabilityFilter.passes(
        {"total_pnl": 0.0, "max_drawdown": 0.10, "trades": 35}
    )
    assert not ok


def test_viability_fails_high_drawdown():
    ok, reason = ViabilityFilter.passes(
        {"total_pnl": 5000.0, "max_drawdown": 0.25, "trades": 35}
    )
    assert not ok
    assert "drawdown" in reason.lower()


def test_viability_fails_low_trades():
    ok, reason = ViabilityFilter.passes(
        {"total_pnl": 5000.0, "max_drawdown": 0.10, "trades": 29}
    )
    assert not ok
    assert "trades" in reason.lower()


def test_viability_filter_removes_bad_results():
    results = [
        {"name": "SAFE", "forward_metrics": {"total_pnl": 10000.0, "max_drawdown": 0.10, "trades": 40}},
        {"name": "BALANCED", "forward_metrics": {"total_pnl": -500.0, "max_drawdown": 0.10, "trades": 40}},
        {"name": "AGGRESSIVE", "forward_metrics": {"total_pnl": 8000.0, "max_drawdown": 0.10, "trades": 10}},
    ]
    viable = ViabilityFilter.filter_viable(results)
    assert len(viable) == 1
    assert viable[0]["name"] == "SAFE"


# ── Config diff tests ──────────────────────────────────────────────────────────

def test_diff_from_base_detects_changes():
    base = {"fusion_min_score": 0.65, "min_rr_ratio": 2.0, "version": "v1"}
    new = {"fusion_min_score": 0.60, "min_rr_ratio": 2.0, "version": "v1"}
    bridge = ExpansionGovernanceBridge()
    diff = bridge._diff_from_base(new, base)
    assert "fusion_min_score" in diff
    assert diff["fusion_min_score"] == {"old": 0.65, "new": 0.60}
    assert "min_rr_ratio" not in diff
    assert "version" not in diff


def test_diff_from_base_empty_when_identical():
    base = {"fusion_min_score": 0.65}
    bridge = ExpansionGovernanceBridge()
    diff = bridge._diff_from_base(base, base)
    assert diff == {}


# ── Bridge integration tests ───────────────────────────────────────────────────

def _make_bridge_with_mocks(tmp_path, forward_metrics_factory, promoted=True):
    """Helper: build bridge with mocked ExpansionEngine + forward test."""
    base_cfg = _base_config()
    baseline_metrics = {"trades": 42, "total_pnl": 25000.0, "max_drawdown": 0.18}
    expansion_result = _make_expansion_result(base_cfg, baseline_metrics)

    gate = _mock_shadow_gate(promoted=promoted)
    history_file = tmp_path / "expansion_history.jsonl"
    bridge = ExpansionGovernanceBridge(history_log=str(history_file), shadow_gate=gate)

    def mock_fwd_test(configs, forward_csv, BacktestRunner):
        return [
            {
                "name": slot["name"],
                "config": slot["config"],
                "train_metrics": slot.get("metrics", {}),
                "forward_metrics": forward_metrics_factory(i, slot),
            }
            for i, slot in enumerate(configs)
        ]

    return bridge, base_cfg, expansion_result, mock_fwd_test


def test_bridge_staged_when_all_viable(tmp_path):
    """All tiers pass viability + hard assertions → at least one staged."""
    def fwd_metrics(i, slot):
        return _viable_fwd_metrics(pnl=26000.0)  # > baseline 25000

    bridge, base_cfg, expansion_result, mock_fwd = _make_bridge_with_mocks(
        tmp_path, fwd_metrics, promoted=True
    )

    with patch.object(bridge, "_forward_test_configs", side_effect=mock_fwd):
        with patch("src.governance.expansion_integration.ExpansionEngine") as MockEng:
            MockEng.return_value.run.return_value = expansion_result
            result = bridge.run(base_cfg, _make_plan(), "train.csv", "forward.csv")

    assert len(result["staged"]) > 0
    for s in result["staged"]:
        assert "patch" in s
        assert "forward_metrics" in s
        assert "gate_result" in s


def test_bridge_empty_staged_when_no_viable(tmp_path):
    """All tiers fail viability → staged is empty, no crash."""
    def fwd_metrics(i, slot):
        return {"trades": 5, "total_pnl": -1000.0, "max_drawdown": 0.40,
                "wins": 2, "losses": 3, "win_rate": 0.40}

    bridge, base_cfg, expansion_result, mock_fwd = _make_bridge_with_mocks(
        tmp_path, fwd_metrics
    )

    with patch.object(bridge, "_forward_test_configs", side_effect=mock_fwd):
        with patch("src.governance.expansion_integration.ExpansionEngine") as MockEng:
            MockEng.return_value.run.return_value = expansion_result
            result = bridge.run(base_cfg, _make_plan(), "train.csv", "forward.csv")

    assert result["staged"] == []
    assert len(result["rejected"]) > 0


def test_bridge_hard_assertion_blocks_pnl_below_baseline(tmp_path):
    """Viability passes but forward_pnl <= baseline_pnl → rejected."""
    def fwd_metrics(i, slot):
        return _viable_fwd_metrics(pnl=24999.0)  # just below baseline 25000

    bridge, base_cfg, expansion_result, mock_fwd = _make_bridge_with_mocks(
        tmp_path, fwd_metrics, promoted=True
    )

    with patch.object(bridge, "_forward_test_configs", side_effect=mock_fwd):
        with patch("src.governance.expansion_integration.ExpansionEngine") as MockEng:
            MockEng.return_value.run.return_value = expansion_result
            result = bridge.run(base_cfg, _make_plan(), "train.csv", "forward.csv")

    assert result["staged"] == []


def test_bridge_history_log_written(tmp_path):
    """History log created; each entry has required keys."""
    def fwd_metrics(i, slot):
        # First tier passes, rest fail
        return _viable_fwd_metrics(pnl=26000.0) if i == 0 else {"trades": 5, "total_pnl": -100.0, "max_drawdown": 0.50, "wins": 1, "losses": 4, "win_rate": 0.2}

    gate = _mock_shadow_gate(promoted=True)
    history_file = tmp_path / "logs" / "expansion_history.jsonl"
    bridge = ExpansionGovernanceBridge(history_log=str(history_file), shadow_gate=gate)
    base_cfg = _base_config()
    baseline_metrics = {"trades": 42, "total_pnl": 25000.0, "max_drawdown": 0.18}
    expansion_result = _make_expansion_result(base_cfg, baseline_metrics)

    def mock_fwd(configs, forward_csv, BacktestRunner):
        return [
            {
                "name": slot["name"],
                "config": slot["config"],
                "train_metrics": {},
                "forward_metrics": fwd_metrics(i, slot),
            }
            for i, slot in enumerate(configs)
        ]

    with patch.object(bridge, "_forward_test_configs", side_effect=mock_fwd):
        with patch("src.governance.expansion_integration.ExpansionEngine") as MockEng:
            MockEng.return_value.run.return_value = expansion_result
            bridge.run(base_cfg, _make_plan(), "train.csv", "forward.csv")

    assert history_file.exists()
    lines = history_file.read_text().strip().split("\n")
    assert len(lines) >= 1
    for line in lines:
        entry = json.loads(line)
        assert "ts" in entry
        assert "tier" in entry
        assert "accepted" in entry
        assert isinstance(entry["accepted"], bool)


def test_bridge_result_always_has_required_keys(tmp_path):
    """Result dict always has staged, rejected, expansion_steps, baseline_metrics."""
    gate = _mock_shadow_gate(promoted=False)
    history_file = tmp_path / "expansion_history.jsonl"
    bridge = ExpansionGovernanceBridge(history_log=str(history_file), shadow_gate=gate)
    base_cfg = _base_config()
    baseline_metrics = {"trades": 42, "total_pnl": 25000.0, "max_drawdown": 0.18}
    expansion_result = _make_expansion_result(base_cfg, baseline_metrics)

    # No forward results at all
    with patch.object(bridge, "_forward_test_configs", return_value=[]):
        with patch("src.governance.expansion_integration.ExpansionEngine") as MockEng:
            MockEng.return_value.run.return_value = expansion_result
            result = bridge.run(base_cfg, _make_plan(), "train.csv", "forward.csv")

    assert "staged" in result
    assert "rejected" in result
    assert "expansion_steps" in result
    assert "baseline_metrics" in result
    assert isinstance(result["staged"], list)
    assert isinstance(result["rejected"], list)