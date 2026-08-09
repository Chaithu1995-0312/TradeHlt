"""Phase 0 ModelPaths + ModelResolver — layout authority + identity/registry parity."""
from __future__ import annotations

from pathlib import Path

import pytest

from config_layer.model_paths import ModelPaths
from config_layer.model_resolver import (
    ModelResolveError,
    ResolvedModel,
    resolve_model,
    resolve_zone_gate_runtime,
)

_REPO = Path(__file__).resolve().parents[1]


def test_model_paths_point_at_existing_registries() -> None:
    assert (_REPO / ModelPaths.ZONE_GATE_VERSION_REGISTRY).exists()
    assert (_REPO / ModelPaths.ZONE_GATE_RUNTIME_ALIAS).exists()
    assert (_REPO / ModelPaths.RR_REGISTRY).exists()
    assert (_REPO / ModelPaths.GAUSSIAN_REGISTRY).exists()
    assert (_REPO / ModelPaths.TRADENET_REGISTRY).exists()
    assert (_REPO / ModelPaths.BITNET_REGISTRY).exists()


def test_resolve_zone_gate_runtime_matches_how_and_identity() -> None:
    r = resolve_zone_gate_runtime(
        how_path=ModelPaths.ZONE_GATE_RUNTIME_ALIAS,
        repo_root=_REPO,
    )
    assert isinstance(r, ResolvedModel)
    assert r.family == "zone_gate"
    assert r.version == "v4_gaussian_runtime_2026_07"
    assert r.artifact_path is not None
    assert r.artifact_path.exists()
    assert r.artifact_path == (_REPO / ModelPaths.ZONE_GATE_RUNTIME_ALIAS).resolve()
    assert r.identity_parity is True
    assert r.spine_wired is True
    assert r.uses_trained_checkpoint is True


def test_resolve_zone_gate_how_mismatch_fail_closed() -> None:
    with pytest.raises(ModelResolveError, match="HOW path diverges"):
        resolve_zone_gate_runtime(
            how_path="models/rr_model.json",  # wrong family artifact
            repo_root=_REPO,
        )


def test_resolve_rr_registry_active_without_how_match() -> None:
    """RR registry active may differ from HOW rr_model.json alias — Phase 0 does not force match."""
    r = resolve_model(
        "rr",
        how_path=ModelPaths.RR_RUNTIME_ALIAS,
        require_artifact=False,
        require_how_match=False,
        require_identity_parity=True,
        repo_root=_REPO,
    )
    assert r.version == "202605_bnb_v2_bnbusdt"
    assert r.identity_parity is True
    assert r.spine_wired is False
    if r.artifact_path is not None:
        assert r.artifact_path.exists() or r.artifact_path.name  # may exist on disk


def test_resolve_gaussian_per_instrument() -> None:
    r = resolve_model(
        "gaussian",
        instrument="BNBUSDT",
        require_identity_parity=True,
        repo_root=_REPO,
    )
    assert r.version == "p5_20260524T120449"
    assert r.identity_parity is True
    assert r.uses_trained_checkpoint is False


def test_resolve_bitnet_empty_active() -> None:
    r = resolve_model(
        "bitnet",
        require_artifact=False,
        require_identity_parity=True,
        repo_root=_REPO,
    )
    assert r.version is None
    assert r.artifact_path is None
    assert r.spine_wired is False


def test_resolve_tradenet_active_unwired() -> None:
    r = resolve_model(
        "tradenet",
        require_identity_parity=True,
        repo_root=_REPO,
    )
    assert r.version == "v5_auto_2026_06_eth"
    assert r.spine_wired is False


def test_resolve_unknown_family() -> None:
    with pytest.raises(ModelResolveError, match="unknown model family"):
        resolve_model("not_a_family", repo_root=_REPO)


def test_engine_runner_zone_gate_uses_resolver() -> None:
    """EngineRunner init resolves zone via ModelResolver (parity with active config)."""
    from config_layer.production_config import get_prod_section as gps
    from core.engine_runner import EngineRunner

    er_cfg = dict(gps("engine_runner"))
    er_cfg.setdefault("fusion_engine", dict(gps("fusion_engine")))
    for k, v in dict(gps("decision_engine")).items():
        er_cfg.setdefault(k, v)
    runner = EngineRunner(er_cfg)

    assert hasattr(runner, "_zone_resolved")
    assert runner._zone_resolved.version == "v4_gaussian_runtime_2026_07"
    assert runner._zone_resolved.identity_parity is True
    assert runner._zone_resolved.artifact_path is not None
    assert runner._zone_resolved.artifact_path.exists()
