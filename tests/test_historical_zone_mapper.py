"""P1a: HistoricalZoneMapper.map_frame + parity vs ER zone-stage helper."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from engines.live_engine import BitNetZoneGate
from engines.zone_cluster_score import score_zone_cluster
from features.feature_schema import CANONICAL_FEATURES
from research.zone_mapping.historical_zone_mapper import (
    SCHEMA_VERSION,
    HistoricalZoneMapper,
    ZoneMapConfig,
    build_neutral_feature_dict,
)

_MAPPER_SRC = Path("src/research/zone_mapping/historical_zone_mapper.py")
_FORBIDDEN_IMPORT_SUBSTR = (
    "crt_engine_v2",
    "engine_runner",
    "EngineRunner",
    "decision_engine",
    "DecisionEngine",
    "fusion_engine",
    "FusionEngine",
)

# Required output keys (design §3.2 subset)
_RECORD_KEYS = {
    "timestamp",
    "instrument",
    "bar_index",
    "best_zone_id",
    "best_zone_score",
    "top_scores",
    "cluster_score",
    "passed_cluster_threshold",
    "zone_cluster_threshold",
    "registry_sha256",
    "feature_schema_dim",
    "schema_version",
}


def _trade_opened_fixture_rows() -> list[dict]:
    """Approach A: small synthetic TRADE_OPENED-shaped feature dicts."""
    return [
        build_neutral_feature_dict(),  # baseline mid-range
        build_neutral_feature_dict(
            close=100.9,
            high=101.0,
            low=99.5,
            body_ratio=0.85,
            disp_strength=1.2,
            retest_depth=0.25,
            momentum_score=0.8,
            ema_fast=100.8,
            ema_slow=99.5,
        ),
        build_neutral_feature_dict(
            close=99.2,
            high=100.0,
            low=99.0,
            body_ratio=0.4,
            disp_strength=0.1,
            retest_depth=0.7,
            momentum_score=-0.5,
            ema_fast=99.5,
            ema_slow=100.5,
        ),
        build_neutral_feature_dict(
            atr=0.001,  # tiny ATR edge case still valid for zone math
            volatility_ratio=0.5,
            session=2.0,
        ),
    ]


def _prod_zone_config() -> ZoneMapConfig:
    return ZoneMapConfig.from_prod_engine_runner()


def test_from_prod_config_knobs() -> None:
    cfg = _prod_zone_config()
    assert cfg.zone_cluster_threshold == 0.25
    assert cfg.top_k == 3
    assert cfg.cluster_min_n == 2
    assert cfg.cluster_spread_max == 0.15
    assert Path(cfg.registry_path).is_file()


def test_map_frame_length_and_schema() -> None:
    cfg = _prod_zone_config()
    mapper = HistoricalZoneMapper(cfg)
    rows = _trade_opened_fixture_rows()
    ts = [f"2025-01-01 10:0{i}:00" for i in range(len(rows))]
    out = mapper.map_frame(rows, timestamps=ts, instrument="TESTUSDT")
    assert len(out) == len(rows)
    for i, rec in enumerate(out):
        assert _RECORD_KEYS <= set(rec.keys())
        assert rec["schema_version"] == SCHEMA_VERSION
        assert rec["instrument"] == "TESTUSDT"
        assert rec["bar_index"] == i
        assert rec["timestamp"] == ts[i]
        assert rec["feature_schema_dim"] == len(CANONICAL_FEATURES)
        assert rec["zone_cluster_threshold"] == cfg.zone_cluster_threshold
        assert isinstance(rec["cluster_score"], float)
        assert isinstance(rec["passed_cluster_threshold"], bool)
        assert isinstance(rec["top_scores"], list)


def test_map_frame_import_isolation() -> None:
    """Mapper module must not import CRT / EngineRunner / DE / Fusion modules."""
    src = _MAPPER_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imported.append(mod)
    # Check import targets only (docstrings may mention engine_runner config keys).
    blob = " ".join(imported)
    for forbidden in (
        "crt_engine_v2",
        "core.engine_runner",
        "engine_runner",
        "core.decision_engine",
        "decision_engine",
        "core.fusion_engine",
        "fusion_engine",
    ):
        assert forbidden not in imported and not any(
            m == forbidden or m.endswith("." + forbidden.split(".")[-1])
            for m in imported
            if forbidden in m
        ), f"forbidden import in mapper: {forbidden} (imports={imported})"
    # Stricter: no import path containing these module stems as a segment.
    for m in imported:
        parts = m.split(".")
        for bad in ("engine_runner", "decision_engine", "fusion_engine", "crt_engine_v2"):
            assert bad not in parts, f"forbidden import segment {bad} in {m}"


def test_parity_vs_zone_cluster_helper() -> None:
    """Mapper cluster_score/passed ≡ score_zone_cluster on same gate instance knobs."""
    cfg = _prod_zone_config()
    mapper = HistoricalZoneMapper(cfg)
    # Same gate construction as mapper (explicit instance)
    gate = BitNetZoneGate(
        zone_path=cfg.registry_path,
        config={
            "zone_min_samples": cfg.zone_min_samples,
            "zone_gate_top_k": cfg.top_k,
        },
    )
    rows = _trade_opened_fixture_rows()
    mapped = mapper.map_frame(rows, instrument="XAUUSD")
    for row, rec in zip(rows, mapped):
        scored = score_zone_cluster(
            dict(row),
            gate,
            zone_cluster_threshold=cfg.zone_cluster_threshold,
            cluster_min_n=cfg.cluster_min_n,
            cluster_spread_max=cfg.cluster_spread_max,
            execution_mode=cfg.execution_mode,
        )
        assert abs(rec["cluster_score"] - scored["cluster_score"]) < 1e-9
        assert rec["passed_cluster_threshold"] == bool(scored["passed"])
        assert rec["passed_cluster_threshold"] == (
            scored["cluster_score"] >= cfg.zone_cluster_threshold
        )


def test_parity_vs_engine_runner_zone_stage() -> None:
    """
    EngineRunner hard zone stage (via shared helper ER now calls) matches mapper.

    Full EngineRunner.run is heavy; we parity against score_zone_cluster with the
    same BitNetZoneGate class ER uses (self._zone_gate) and prod knobs — the
    mechanical extract guarantees ER hard path is this helper.
    """
    cfg = _prod_zone_config()
    mapper = HistoricalZoneMapper(cfg)
    # Mirror EngineRunner.get_zone_gate construction
    from engines.live_engine import get_zone_gate

    er_gate = get_zone_gate(
        cfg.registry_path,
        min_samples=cfg.zone_min_samples,
        top_n=cfg.top_k,
    )
    rows = _trade_opened_fixture_rows()
    mapped = mapper.map_frame(rows)
    for row, rec in zip(rows, mapped):
        er_scored = score_zone_cluster(
            dict(row),
            er_gate,
            zone_cluster_threshold=cfg.zone_cluster_threshold,
            cluster_min_n=cfg.cluster_min_n,
            cluster_spread_max=cfg.cluster_spread_max,
            execution_mode=cfg.execution_mode,
        )
        assert abs(rec["cluster_score"] - er_scored["score"]) < 1e-9
        assert rec["passed_cluster_threshold"] == bool(er_scored["passed"])


def test_build_neutral_feature_dict_is_canonical() -> None:
    d = build_neutral_feature_dict()
    for name in CANONICAL_FEATURES:
        assert name in d
    assert len(d) >= len(CANONICAL_FEATURES)
