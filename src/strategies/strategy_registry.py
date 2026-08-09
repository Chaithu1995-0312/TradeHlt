"""
strategy_registry.py
================================================================================
StrategyRegistry — load/list/resolve StrategyPackage versions from
configs/strategies/*.json (target-strategy-architecture.md §8 / §14.C).

A package on disk is a SNAPSHOT captured via `StrategyPackage.from_active_config()`
(or hand-authored for a research candidate) — the registry itself performs no
promotion. Activating a strategy version still means promoting the production
config it maps to (§14.C "Promotion activates strategy version only via
existing governance"); this registry only answers "what did we name this, and
which config version/hash does it map to."
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from strategies.strategy_package import StrategyPackage

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STRATEGIES_DIR = _ROOT / "configs" / "strategies"


class StrategyNotFoundError(LookupError):
    """Raised when a named strategy version has no file in the registry dir."""


class StrategyRegistry:
    def __init__(self, strategies_dir: Optional[Path] = None):
        self.dir = Path(strategies_dir) if strategies_dir else DEFAULT_STRATEGIES_DIR

    def _path_for(self, name: str, version: str) -> Path:
        return self.dir / f"{name}__{version}.json"

    def save(self, package: StrategyPackage) -> Path:
        """Persist a package snapshot. Overwrites an existing (name, version) file —
        callers that want append-only history should bump `version`."""
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(package.name, package.version)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(package.to_dict(), f, indent=2, default=str)
            f.write("\n")
        return path

    def load(self, name: str, version: str) -> StrategyPackage:
        path = self._path_for(name, version)
        if not path.is_file():
            raise StrategyNotFoundError(
                f"No strategy package at {path}. Known packages: {[p.stem for p in self.list_paths()]}"
            )
        with open(path, encoding="utf-8") as f:
            return StrategyPackage.from_dict(json.load(f))

    def list_paths(self) -> list[Path]:
        if not self.dir.is_dir():
            return []
        return sorted(self.dir.glob("*.json"))

    def list_versions(self) -> list[dict]:
        """Return [{"name", "version", "config_version", "config_hash"}] for every
        saved package — the strategy-version <-> production-config-version/hash map
        (§14.C 'Mapping: strategy version <-> production config version / hash')."""
        out = []
        for p in self.list_paths():
            try:
                pkg = StrategyPackage.from_dict(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
            out.append({
                "name":           pkg.name,
                "version":        pkg.version,
                "config_version": pkg.provenance.get("parent_config"),
                "config_hash":    pkg.provenance.get("config_hash"),
                "content_hash":   pkg.content_hash(),
                "path":           str(p),
            })
        return out

    def resolve_for_instrument(self, instrument: str, name: Optional[str] = None) -> StrategyPackage:
        """Load the saved package for `instrument` if one exists; otherwise build
        (but do not persist) a live projection of the ACTIVE config. This is the
        call research harnesses / BacktestConfig should use — it never silently
        invents thresholds, it either loads a named snapshot or projects the
        current governed config."""
        strategy_name = name or f"active_{instrument.lower()}"
        for p in self.list_paths():
            try:
                pkg = StrategyPackage.from_dict(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
            if pkg.name == strategy_name:
                return pkg
        return StrategyPackage.from_active_config(instrument, name=strategy_name)
