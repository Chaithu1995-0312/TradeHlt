"""Floor: semantic rename bitnet_zone_threshold → feature_cluster_similarity_cluster_threshold.

Pure naming refactor — value and consumption must stay the cluster-score
threshold used by EngineRunner (no BitNet neural semantics).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from config_layer.production_config import get_prod_section
from core.engine_runner import ENGINE_RUNNER_DEFAULTS


def test_active_engine_runner_uses_feature_cluster_similarity_cluster_threshold() -> None:
    er = get_prod_section("engine_runner")
    assert "feature_cluster_similarity_cluster_threshold" in er, (
        "engine_runner must declare feature_cluster_similarity_cluster_threshold after semantic rename"
    )
    assert "bitnet_zone_threshold" not in er, (
        "legacy key bitnet_zone_threshold must not remain on active engine_runner"
    )
    assert float(er["feature_cluster_similarity_cluster_threshold"]) == 0.25


def test_engine_runner_defaults_fixture_uses_new_key() -> None:
    assert "feature_cluster_similarity_cluster_threshold" in ENGINE_RUNNER_DEFAULTS
    assert "bitnet_zone_threshold" not in ENGINE_RUNNER_DEFAULTS
    assert float(ENGINE_RUNNER_DEFAULTS["feature_cluster_similarity_cluster_threshold"]) == 0.25


def test_engine_runner_source_reads_feature_cluster_similarity_cluster_threshold() -> None:
    src = Path("src/core/engine_runner.py").read_text(encoding="utf-8")
    assert ' "feature_cluster_similarity_cluster_threshold"' in src or '"feature_cluster_similarity_cluster_threshold"' in src
    assert "bitnet_zone_threshold" not in src


def test_live_engine_comment_uses_new_name() -> None:
    src = Path("src/engines/live_engine.py").read_text(encoding="utf-8")
    assert "feature_cluster_similarity_cluster_threshold" in src
    assert "bitnet_zone_threshold" not in src
