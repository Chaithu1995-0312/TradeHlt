"""
gaussian_engine.py — BACKWARD-COMPATIBILITY SHIM
=================================================
The canonical implementation has moved to:
  engines/heuristic_gaussian_engine.py  (HeuristicGaussianEngine)

This module re-exports everything from that module and provides
a GaussianEngine alias so existing imports continue to work:

  from engines.gaussian_engine import GaussianEngine  # still works

New code should import directly:
  from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
"""

from engines.heuristic_gaussian_engine import (
    HeuristicGaussianEngine,
    GaussianRegistry,
    GAUSSIAN_REGISTRY_PATH,
    GAUSSIAN_MODELS_DIR,
    _FALLBACK_PRIORITY,
    _normalize_registry_entry,
)

# Backward-compat alias
GaussianEngine = HeuristicGaussianEngine

__all__ = [
    "GaussianEngine",
    "HeuristicGaussianEngine",
    "GaussianRegistry",
    "GAUSSIAN_REGISTRY_PATH",
    "GAUSSIAN_MODELS_DIR",
]