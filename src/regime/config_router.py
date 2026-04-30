# config_router.py — maps market regime to config profile
#
# ConfigRouter selects which config file to use based on regime.
# Fallback is always SAFE.
#
# Config profile → file mapping loaded from:
#   configs/production/regime_map.json  (default)
# Or injected directly as a dict (for testing).
#
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from src.regime.regime_classifier import (
    REGIME_TRENDING,
    REGIME_RANGING,
    REGIME_HIGH_VOLATILITY,
)

DEFAULT_FUSION_WEIGHTS = {
    "crt": 0.40,
    "gaussian": 0.30,
    "zone": 0.20,
    "rr": 0.10
}

DEFAULT_BITNET_THRESHOLD = 0.50

log = logging.getLogger(__name__)

# Default regime → config profile mapping
_DEFAULT_REGIME_MAP = {
    REGIME_TRENDING: "BALANCED",
    REGIME_RANGING: "SAFE",
    REGIME_HIGH_VOLATILITY: "AGGRESSIVE",
    "DEFAULT": "SAFE",
}

_DEFAULT_MAP_PATH = Path("configs/production/regime_map.json")


class ConfigRouter:
    """
    Routes a regime string to a config profile name (SAFE | BALANCED | AGGRESSIVE).

    Can also resolve to an actual config dict or file path when config_dir is provided.

    Usage:
        router = ConfigRouter()
        profile = router.select_profile(regime)          # → "BALANCED"
        config = router.select_config(regime, config_dir) # → dict or None

    Guardrails:
        - Unknown regime → "SAFE" (never raises)
        - Missing config file → logs warning, returns None
    """

    def __init__(
        self,
        regime_map: Optional[dict] = None,
        map_path: Optional[str] = None,
    ):
        """
        Args:
            regime_map: optional dict override (regime → profile name).
                        If None, loads from map_path or uses hardcoded default.
            map_path: path to regime_map.json. Falls back to _DEFAULT_MAP_PATH.
        """
        if regime_map is not None:
            self._map = dict(regime_map)
        else:
            self._map = self._load_map(map_path or str(_DEFAULT_MAP_PATH))

        # Always ensure DEFAULT exists as SAFE fallback
        if "DEFAULT" not in self._map:
            self._map["DEFAULT"] = "SAFE"

    def select_profile(self, regime: str) -> str:
        """
        Map regime to config profile name.

        Args:
            regime: e.g. "TRENDING", "RANGING", "HIGH_VOLATILITY"

        Returns:
            Profile name string: "SAFE" | "BALANCED" | "AGGRESSIVE"
        """
        profile = self._map.get(regime, self._map.get("DEFAULT", "SAFE"))
        log.debug("ConfigRouter: regime=%s → profile=%s", regime, profile)
        return profile

    def select_config(self, regime: str, config_dir: str) -> Optional[dict]:
        """
        Resolve regime to a loaded config dict from disk.

        Args:
            regime: e.g. "TRENDING"
            config_dir: directory containing {version}_{profile}.json files

        Returns:
            Config dict or None if file not found.
        """
        profile = self.select_profile(regime)
        config_path = self._find_config_file(config_dir, profile)

        if config_path is None:
            log.warning(
                "ConfigRouter: no config file found for profile=%s in %s",
                profile, config_dir,
            )
            return None

        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            log.info(
                "ConfigRouter: loaded config profile=%s from %s",
                profile, config_path,
            )
            return cfg
        except Exception as exc:
            log.warning("ConfigRouter: failed to load %s: %s", config_path, exc)
            return None

    def get_map(self) -> dict:
        """Return a copy of the current regime → profile mapping."""
        return dict(self._map)

    # ── Private ────────────────────────────────────────────────────────────────

    def _load_map(self, map_path: str) -> dict:
        """Load regime map from JSON file; falls back to hardcoded default."""
        path = Path(map_path)
        if not path.exists():
            log.info(
                "ConfigRouter: regime map not found at %s — using default mapping",
                map_path,
            )
            return dict(_DEFAULT_REGIME_MAP)
        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            log.info("ConfigRouter: loaded regime map from %s", map_path)
            return {**_DEFAULT_REGIME_MAP, **loaded}  # loaded overrides defaults
        except Exception as exc:
            log.warning("ConfigRouter: failed to load regime map (%s) — using default", exc)
            return dict(_DEFAULT_REGIME_MAP)

    def get_fusion_weights(self, regime: str) -> Dict[str, float]:
        """
        Get optimized fusion weights for current regime.
        Falls back to default hardcoded weights if no regime map entry exists.
        """
        if "fusion_weights" not in self._map:
            return DEFAULT_FUSION_WEIGHTS.copy()
            
        return self._map["fusion_weights"].get(regime, DEFAULT_FUSION_WEIGHTS.copy())

    def get_bitnet_threshold(self, regime: str) -> float:
        """
        Get optimized BitNet threshold for current regime.
        Falls back to 0.50 default if no regime map entry exists.
        """
        if "bitnet_thresholds" not in self._map:
            return DEFAULT_BITNET_THRESHOLD
            
        return self._map["bitnet_thresholds"].get(regime, DEFAULT_BITNET_THRESHOLD)

    def update_regime_weights(self, search_results: list) -> None:
        """
        Update regime map with optimized weights from RegimeSearchResult objects.
        
        Parameters
        ----------
        search_results : list of RegimeSearchResult objects from weight searcher
        """
        if "fusion_weights" not in self._map:
            self._map["fusion_weights"] = {}
        if "bitnet_thresholds" not in self._map:
            self._map["bitnet_thresholds"] = {}
            
        for res in search_results:
            self._map["fusion_weights"][res.regime] = res.best_candidate.fusion_weights
            self._map["bitnet_thresholds"][res.regime] = res.best_candidate.bitnet_threshold
            log.info("Updated weights for %s: improvement %.2f%%", res.regime, res.improvement_pct)

    def save_map(self, map_path: Optional[str] = None) -> None:
        """
        Save current regime map including optimized weights to disk.
        """
        path = Path(map_path) if map_path else _DEFAULT_MAP_PATH
        path.parent.mkdir(exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._map, f, indent=2)
            
        log.info("Saved regime map to %s", path)

    def _find_config_file(self, config_dir: str, profile: str) -> Optional[Path]:
        """
        Find a config file matching the profile in config_dir.

        Looks for files containing the profile name (case-insensitive):
          e.g. v1_balanced.json, v1_multi_2026_03_BALANCED.json
        """
        base = Path(config_dir)
        if not base.exists():
            return None

        profile_lower = profile.lower()
        candidates = sorted(base.glob("*.json"))

        for p in candidates:
            if profile_lower in p.stem.lower():
                return p

        return None
