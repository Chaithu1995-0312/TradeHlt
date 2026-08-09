"""
model_paths.py — CODE layout authority for model artifacts (Phase 0).

Single place that may define ``models/…`` path constants. Loaders and resolvers
import from here; they must not invent parallel filesystem roots.

Authority (three-layer model):
  - Registry JSON     → active version id + relative artifact name (promote)
  - ModelPaths (CODE) → root + family registry/runtime path *layout*
  - HOW (production)  → enablement + optional path keys that must *match* resolve
  - active_models.yaml identity → WHO mirror of version (not a loader)

Phase 0 maps the *current flat* ``models/`` tree. A later phase may reorganize
into ``models/{family}/`` without changing call sites beyond this module.
"""
from __future__ import annotations

from pathlib import Path


class ModelPaths:
    """Repository-relative model layout (flat tree, Phase 0)."""

    ROOT: Path = Path("models")

    # ── Version registries (promote / active selection) ──────────────────────
    RR_REGISTRY: Path = ROOT / "rr_registry.json"
    GAUSSIAN_REGISTRY: Path = ROOT / "gaussian_registry.json"
    ZONE_GATE_VERSION_REGISTRY: Path = ROOT / "zone_gate_registry.json"
    TRADENET_REGISTRY: Path = ROOT / "tradenet_registry.json"
    BITNET_REGISTRY: Path = ROOT / "bitnet" / "bitnet_registry.json"

    # ── Runtime aliases consumed by HOW / EngineRunner (must stay parity-pinned)
    # Zone: F-041 — version registry active.model_file → this runtime file.
    # SCHEMA-V4 (2026-07-22): repointed from `zone_registry.json` (v3-aligned; its feature_order
    # names macd_hist/wick_size, so it now fails closed with ZoneFeatureOrderError) to the remapped
    # v4 artifact. The v3 file is retained for rollback, NOT deleted. This alias is the fallback the
    # resolver uses when no explicit how_path is given, so it must track the promoted version or
    # `resolve_zone_gate_runtime` reports a HOW/registry divergence.
    ZONE_GATE_RUNTIME_ALIAS: Path = ROOT / "zone_registry_v4_2026_07.json"
    # RR fusion HOW key often points here; registry active may name a versioned file.
    RR_RUNTIME_ALIAS: Path = ROOT / "rr_model.json"
    RR_DATASET_DEFAULT: Path = ROOT / "rr_dataset.json"

    @classmethod
    def resolve(cls, rel: str | Path, *, repo_root: Path | None = None) -> Path:
        """Join a models-relative or repo-relative path under optional repo_root."""
        p = Path(str(rel).replace("\\", "/"))
        if p.is_absolute():
            return p
        base = repo_root if repo_root is not None else Path(".")
        # Strip leading "models/" if already under ROOT to avoid double-join mistakes
        # when callers pass registry model_file values.
        return (base / p).resolve() if repo_root is not None else (base / p)


# Convenience aliases matching historical constant names
MODELS_DIR = ModelPaths.ROOT
GAUSSIAN_REGISTRY_PATH = ModelPaths.GAUSSIAN_REGISTRY
ZONE_REGISTRY_PATH = ModelPaths.ZONE_GATE_RUNTIME_ALIAS
RR_REGISTRY_PATH = ModelPaths.RR_REGISTRY

__all__ = [
    "ModelPaths",
    "MODELS_DIR",
    "GAUSSIAN_REGISTRY_PATH",
    "ZONE_REGISTRY_PATH",
    "RR_REGISTRY_PATH",
]
