"""
Phase 8 — dashboard data layer (pure, read-only, no Streamlit).

Proves the loaders + display aggregations are correct so the dashboard renders truth.
"""
from __future__ import annotations

import json

from mt5_analytics.ui import dashboard_data as dd
from mt5_analytics.storage.partition_writer import PartitionWriter

_FEATURES = [
    {"realized_r": 2.0, "mfe_r": 3.0, "mae_r": -0.5, "session": "LONDON",
     "regime": "N", "duration_minutes": 30.0, "direction": "long",
     "symbol": "EURUSD", "entry_time": "2026-06-19T10:00:00Z",
     "exit_time": "2026-06-19T10:30:00Z", "episode_id": "1:a"},
    {"realized_r": -1.0, "mfe_r": 0.5, "mae_r": -1.2, "session": "NY",
     "regime": None, "duration_minutes": 10.0, "direction": "short",
     "symbol": "EURUSD", "entry_time": "2026-06-19T14:00:00Z",
     "exit_time": "2026-06-19T14:10:00Z", "episode_id": "2:b"},
    {"realized_r": None, "mfe_r": None, "mae_r": None, "session": "OVERLAP",
     "regime": "E", "duration_minutes": 5.0, "direction": "long",
     "symbol": "EURUSD", "entry_time": "2026-06-19T15:00:00Z",
     "exit_time": "2026-06-19T15:05:00Z", "episode_id": "3:c"},
]


def test_summary_stats():
    s = dd.summary_stats(_FEATURES)
    assert s["n_episodes"] == 3 and s["n_with_r"] == 2
    assert s["win_rate"] == 0.5
    assert s["profit_factor"] == 2.0       # gross win 2 / gross loss 1
    assert s["expectancy_r"] == 0.5        # (2 - 1) / 2


def test_session_and_regime_breakdown():
    sb = dd.session_breakdown(_FEATURES)
    assert sb["LONDON"]["n"] == 1 and sb["LONDON"]["expectancy_r"] == 2.0
    assert sb["OVERLAP"]["expectancy_r"] is None     # no realized_r
    rb = dd.regime_breakdown(_FEATURES)
    assert rb == {"N": 1, "INSUFFICIENT": 1, "E": 1}  # None -> INSUFFICIENT


def test_points_and_durations_skip_none():
    assert dd.mfe_mae_points(_FEATURES) == [(3.0, -0.5), (0.5, -1.2)]
    assert dd.durations_minutes(_FEATURES) == [30.0, 10.0, 5.0]


def test_empty_features_safe():
    s = dd.summary_stats([])
    assert s["n_episodes"] == 0 and s["win_rate"] is None
    assert dd.mfe_mae_points([]) == [] and dd.regime_breakdown([]) == {}


def test_loaders_read_partitions(tmp_path):
    PartitionWriter(tmp_path, "features").write(_FEATURES, generated_by="test")
    loaded = dd.load_features(tmp_path)
    assert len(loaded) == 3
    assert {f["episode_id"] for f in loaded} == {"1:a", "2:b", "3:c"}
    assert dd.load_episodes(tmp_path) == []     # none written


def test_load_reports(tmp_path):
    reality = tmp_path / "reality"
    reality.mkdir(parents=True)
    (reality / "deal_coverage.json").write_text(json.dumps({"coverage_score": 50, "tier": "Silver"}))
    (reality / "coverage_gaps.json").write_text(json.dumps({"validated": ["partial_closes"], "missing": []}))
    (tmp_path / "verification").mkdir()
    (tmp_path / "verification" / "daily_verification.md").write_text("**Status:** PASS\n")
    assert dd.load_coverage(tmp_path)["tier"] == "Silver"
    assert dd.load_coverage_gaps(tmp_path)["validated"] == ["partial_closes"]
    assert "PASS" in dd.load_verification_md(tmp_path)
    assert dd.load_coverage(tmp_path / "nope") is None     # missing -> None
