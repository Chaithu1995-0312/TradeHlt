"""
heuristic_gaussian_engine.py
============================
Heuristic Gaussian probability scoring using EMA/momentum kernel.

Renamed from gaussian_engine.py — class GaussianEngine → HeuristicGaussianEngine.
The original gaussian_engine.py now imports this as a backward-compat alias.

Input contract:
  features dict with at least CANONICAL_FEATURES keys.
  Uses: ema_fast, ema_slow, momentum_score (all canonical).
  KeyError → RuntimeError (fail-fast — no silent score=0.0).
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Optional

from features.feature_schema import CANONICAL_FEATURES

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

GAUSSIAN_REGISTRY_PATH: str = "models/gaussian_registry.json"
GAUSSIAN_MODELS_DIR: str = "models"

_FALLBACK_PRIORITY = ["v1", "import_fix_v1"]


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY NORMALISATION
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_registry_entry(version: str, entry: dict) -> dict:
    model_file = entry.get("model_file") or f"{version}.json"
    return {
        "version":    entry.get("version", version),
        "model_file": model_file,
        "active":     bool(entry.get("active", False)),
        "metrics":    entry.get("metrics", {}),
        "mu":         float(entry.get("mu", 0.0)),
        "sigma":      float(entry.get("sigma", 1.0)),
        "feature_schema": entry.get("feature_schema", []),
        "trained_at": entry.get("trained_at", "unknown"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY LOADER
# ─────────────────────────────────────────────────────────────────────────────

class GaussianRegistry:
    """Registry loader with artifact validation and version fallback."""

    def __init__(self, registry_path: str = GAUSSIAN_REGISTRY_PATH,
                 models_dir: str = GAUSSIAN_MODELS_DIR):
        self.registry_path = registry_path
        self.models_dir = models_dir
        self._entries: dict = {}
        self._active_version: Optional[str] = None

    def load(self) -> "GaussianRegistry":
        if not os.path.exists(self.registry_path):
            raise FileNotFoundError(
                f"GaussianRegistry: registry not found at '{self.registry_path}'."
            )

        with open(self.registry_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, dict):
            raise ValueError(
                f"GaussianRegistry: registry must be a JSON object, got {type(raw).__name__}"
            )

        self._entries = {
            v: _normalize_registry_entry(v, entry)
            for v, entry in raw.items()
        }

        active_versions = [v for v, e in self._entries.items() if e["active"]]

        if not active_versions:
            raise RuntimeError(
                "GaussianRegistry: no version has active=true in the registry."
            )

        if len(active_versions) > 1:
            logger.warning(
                "GaussianRegistry: multiple active versions found %s — using first: %s",
                active_versions, active_versions[0],
            )

        requested_version = active_versions[0]
        self._active_version = self._resolve_with_fallback(requested_version)
        return self

    def _artifact_exists(self, version: str) -> bool:
        entry = self._entries.get(version, {})
        model_file = entry.get("model_file", f"{version}.json")
        path = os.path.join(self.models_dir, model_file)
        return os.path.exists(path)

    def _resolve_with_fallback(self, requested: str) -> str:
        if self._artifact_exists(requested):
            return requested

        logger.warning(
            "GaussianRegistry: SAFE MODE — active version '%s' artifact is MISSING. "
            "Attempting fallback versions %s.", requested, _FALLBACK_PRIORITY,
        )

        for candidate in _FALLBACK_PRIORITY:
            if candidate == requested:
                continue
            if candidate not in self._entries:
                continue
            if self._artifact_exists(candidate):
                logger.warning(
                    "GaussianRegistry: FALLBACK ACTIVE — using version '%s' "
                    "(requested '%s' artifact missing).", candidate, requested,
                )
                return candidate

        raise RuntimeError(
            f"GaussianRegistry: FAIL CLOSED — active version '{requested}' "
            f"and all fallback versions {_FALLBACK_PRIORITY} have missing artifacts."
        )

    @property
    def active_version(self) -> str:
        if self._active_version is None:
            raise RuntimeError("GaussianRegistry.active_version accessed before .load().")
        return self._active_version

    @property
    def active_entry(self) -> dict:
        return self._entries[self.active_version]

    @property
    def mu(self) -> float:
        return self.active_entry["mu"]

    @property
    def sigma(self) -> float:
        sigma = self.active_entry["sigma"]
        return sigma if sigma > 0 else 1.0


# ─────────────────────────────────────────────────────────────────────────────
# HEURISTIC GAUSSIAN ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class HeuristicGaussianEngine:
    """
    Probability scoring using a Gaussian kernel on EMA/momentum features.

    Uses 3 canonical features: ema_fast, ema_slow, momentum_score.
    All other features from the 32-dim canonical dict are accepted but ignored.

    mu/sigma come from:
      1. config dict keys "gaussian_mu" / "gaussian_sigma" (explicit override)
      2. GaussianRegistry.load() (registry-driven, with safe-mode fallback)
      3. Defaults (mu=0.0, sigma=1.0) if registry is absent and no override
    """

    def __init__(self, config: dict, preload_registry: bool = False):
        self.config = config
        self._registry: Optional[GaussianRegistry] = None

        self._mu_override: Optional[float] = (
            float(config["gaussian_mu"]) if "gaussian_mu" in config else None
        )
        self._sigma_override: Optional[float] = (
            float(config["gaussian_sigma"]) if "gaussian_sigma" in config else None
        )

        if preload_registry:
            self._load_registry()

    def _load_registry(self) -> None:
        registry_path = self.config.get("gaussian_registry_path", GAUSSIAN_REGISTRY_PATH)
        try:
            self._registry = GaussianRegistry(registry_path).load()
            logger.info(
                "HeuristicGaussianEngine: loaded registry — active version '%s'",
                self._registry.active_version,
            )
        except (FileNotFoundError, RuntimeError) as exc:
            logger.warning(
                "HeuristicGaussianEngine: registry load failed (%s). "
                "Using config/default mu=%.2f, sigma=%.2f.",
                exc,
                self._mu_override or 0.0,
                self._sigma_override or 1.0,
            )
            self._registry = None

    @property
    def mu(self) -> float:
        if self._mu_override is not None:
            return self._mu_override
        if self._registry is not None:
            return self._registry.mu
        return 0.0

    @property
    def sigma(self) -> float:
        if self._sigma_override is not None:
            return self._sigma_override
        if self._registry is not None:
            return self._registry.sigma
        return 1.0

    def compute(self, input_data: dict, candle_idx: int = 0, direction: str = "long") -> dict:
        """
        Compute Gaussian probability score from canonical feature dict.

        direction is accepted for API compatibility with MLGaussianEngine but is
        intentionally ignored — the heuristic Gaussian kernel is direction-agnostic.

        Args:
            input_data: dict with at least ema_fast, ema_slow, momentum_score
            candle_idx: unused, accepted for interface compatibility

        Returns:
            dict with 'score' (float in [0,1]) and 'reason' (str)
        """
        if self._registry is None and self._mu_override is None:
            self._load_registry()

        assert isinstance(input_data, dict), "HeuristicGaussianEngine input must be dict"
        assert len(input_data) >= len(CANONICAL_FEATURES), (
            f"HeuristicGaussianEngine: input has {len(input_data)} features, "
            f"expected at least {len(CANONICAL_FEATURES)}"
        )

        try:
            ema_fast = input_data["ema_fast"]
            ema_slow = input_data["ema_slow"]
            momentum = input_data["momentum_score"]
        except KeyError as e:
            raise RuntimeError(
                f"HeuristicGaussianEngine missing canonical feature: {e}"
            ) from e

        if ema_fast == ema_slow and momentum == 0.0:
            logger.warning(
                "HeuristicGaussianEngine: neutral_synthetic_condition detected; returning 0.5"
            )
            return {"score": 0.5, "reason": "neutral_synthetic_condition"}

        if ema_slow == 0:
            raise RuntimeError(
                "HeuristicGaussianEngine: ema_slow is 0 — cannot compute EMA ratio"
            )

        ema_diff = (ema_fast - ema_slow) / ema_slow
        momentum_norm = math.tanh(momentum)
        x = (ema_diff + momentum_norm) / 2.0

        mu = self.mu
        sigma = self.sigma

        exponent = -((x - mu) ** 2) / (2 * sigma ** 2)
        score = math.exp(exponent)

        return {
            "score": round(score, 4),
            "reason": "gaussian_computed",
            "meta": {
                "mu": mu,
                "sigma": sigma,
                "x": round(x, 6),
            },
        }