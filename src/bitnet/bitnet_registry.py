"""
bitnet_registry.py
==================
BitNet version-registry governance (Exists ≠ Selected ≠ Enabled).

Catalog lives at ``models/bitnet/bitnet_registry.json`` (ModelPaths.BITNET_REGISTRY).

Contracts
---------
* **Exists** — entry present with ``model_file`` that resolves on disk.
* **Selected** — exactly zero or one entry with ``active: true`` (spine selection).
* **Enabled** — ``crt_engine.use_bitnet`` (HOW); not owned here.

Serve rules
-----------
* Composition default (``bitnet_score`` / ``get_default_composition``) resolves via
  ``_governance.composition_default_version`` when no selection is active.
* When ``use_bitnet=true``, ``assert_serve_allowed()`` requires a selected version
  (fail-closed) so enablement cannot bypass explicit selection.
* Dual-schema fork is documented in the registry (legacy_6 vs export_35) — not unified.

Authority: catalog + load contract only. No economic promote (F-004 / F-055).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from config_layer.model_paths import ModelPaths as _ModelPaths
    DEFAULT_REGISTRY_PATH: Path = Path(str(_ModelPaths.BITNET_REGISTRY))
except Exception:  # pragma: no cover
    DEFAULT_REGISTRY_PATH = Path("models/bitnet/bitnet_registry.json")

_REPO_ROOT = Path(__file__).resolve().parents[2]


class BitNetRegistryError(RuntimeError):
    """Fail-closed BitNet registry / serve-contract error."""


@dataclass(frozen=True)
class BitNetRegistryEntry:
    version: str
    model_file: str
    schema: Optional[str]
    feature_schema_dim: Optional[int]
    feature_order: Optional[List[str]]
    active: bool
    role: Optional[str]
    raw: Dict[str, Any]

    @property
    def artifact_path(self) -> Path:
        p = Path(str(self.model_file).replace("\\", "/"))
        if not p.is_absolute():
            p = (_REPO_ROOT / p).resolve()
        return p

    def exists(self) -> bool:
        return self.artifact_path.is_file()


class BitNetRegistry:
    """Load + query the BitNet version registry."""

    def __init__(self, registry_path: Path | str | None = None):
        self.registry_path = Path(registry_path or DEFAULT_REGISTRY_PATH)
        if not self.registry_path.is_absolute():
            self.registry_path = (_REPO_ROOT / self.registry_path).resolve()
        self._raw: Dict[str, Any] = {}
        self._entries: Dict[str, BitNetRegistryEntry] = {}
        self._governance: Dict[str, Any] = {}

    def load(self) -> "BitNetRegistry":
        if not self.registry_path.is_file():
            raise BitNetRegistryError(
                f"BitNet registry not found: {self.registry_path}"
            )
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise BitNetRegistryError(
                f"BitNet registry unreadable: {self.registry_path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise BitNetRegistryError("BitNet registry must be a JSON object")

        self._raw = data
        gov = data.get("_governance")
        self._governance = gov if isinstance(gov, dict) else {}

        entries: Dict[str, BitNetRegistryEntry] = {}
        for key, val in data.items():
            if key.startswith("_") or not isinstance(val, dict):
                continue
            if "model_file" not in val and "version" not in val:
                continue
            ver = str(val.get("version") or key)
            entries[ver] = BitNetRegistryEntry(
                version=ver,
                model_file=str(val.get("model_file") or ""),
                schema=val.get("schema"),
                feature_schema_dim=(
                    int(val["feature_schema_dim"])
                    if val.get("feature_schema_dim") is not None
                    else None
                ),
                feature_order=(
                    list(val["feature_order"])
                    if isinstance(val.get("feature_order"), list)
                    else None
                ),
                active=bool(val.get("active", False)),
                role=val.get("role"),
                raw=dict(val),
            )
        self._entries = entries

        # Exactly zero or one active
        actives = [e.version for e in entries.values() if e.active]
        if len(actives) > 1:
            raise BitNetRegistryError(
                f"BitNet registry has multiple active entries {actives}; "
                f"exactly zero or one allowed (Exists≠Selected≠Enabled)."
            )
        return self

    @classmethod
    def load_default(cls) -> "BitNetRegistry":
        return cls().load()

    @property
    def governance(self) -> Dict[str, Any]:
        return dict(self._governance)

    def versions(self) -> List[str]:
        return sorted(self._entries.keys())

    def get(self, version: str) -> Optional[BitNetRegistryEntry]:
        return self._entries.get(version)

    def selected_version(self) -> Optional[str]:
        for e in self._entries.values():
            if e.active:
                return e.version
        return None

    def selected_entry(self) -> Optional[BitNetRegistryEntry]:
        ver = self.selected_version()
        return self._entries.get(ver) if ver else None

    def composition_default_version(self) -> Optional[str]:
        v = self._governance.get("composition_default_version")
        return str(v) if v else None

    def composition_default_entry(self) -> Optional[BitNetRegistryEntry]:
        ver = self.composition_default_version()
        if not ver:
            # Fall back: entry with role composition_default
            for e in self._entries.values():
                if e.role == "composition_default":
                    return e
            return None
        return self._entries.get(ver)

    def resolve_composition_model_path(self) -> str:
        """Path for bitnet_score / get_default_composition.

        Prefer active selection when present; else composition_default.
        """
        selected = self.selected_entry()
        if selected is not None:
            if not selected.exists():
                raise BitNetRegistryError(
                    f"Selected BitNet version {selected.version!r} artifact missing: "
                    f"{selected.artifact_path}"
                )
            return str(selected.model_file).replace("\\", "/")

        default = self.composition_default_entry()
        if default is None:
            raise BitNetRegistryError(
                "No BitNet selection and no composition_default_version in registry"
            )
        if not default.exists():
            raise BitNetRegistryError(
                f"Composition-default BitNet artifact missing: {default.artifact_path}"
            )
        return str(default.model_file).replace("\\", "/")

    def dual_schema_report(self) -> Dict[str, Any]:
        dims = {
            e.version: {
                "schema": e.schema,
                "feature_schema_dim": e.feature_schema_dim,
                "role": e.role,
                "active": e.active,
                "exists": e.exists(),
            }
            for e in self._entries.values()
        }
        distinct_dims = {
            e.feature_schema_dim
            for e in self._entries.values()
            if e.feature_schema_dim is not None
        }
        return {
            "entries": dims,
            "distinct_feature_schema_dims": sorted(d for d in distinct_dims if d is not None),
            "fork_present": len(distinct_dims) > 1,
            "governance_note": self._governance.get("dual_schema_fork"),
            "selected": self.selected_version(),
            "composition_default": self.composition_default_version(),
        }

    def assert_serve_allowed(self, *, use_bitnet: bool) -> None:
        """Fail-closed gate when CRT enables BitNet.

        * use_bitnet=false → no-op (inert spine path).
        * use_bitnet=true → requires exactly one active selection whose artifact exists,
          when governance.require_selection_when_enabled is true (default).
        """
        if not use_bitnet:
            return
        require = bool(self._governance.get("require_selection_when_enabled", True))
        selected = self.selected_entry()
        if require and selected is None:
            raise BitNetRegistryError(
                "crt_engine.use_bitnet=true but no active selection in "
                f"{self.registry_path}. Set exactly one registry entry "
                f"'active': true before enabling (Exists≠Selected≠Enabled)."
            )
        if selected is not None and not selected.exists():
            raise BitNetRegistryError(
                f"Selected BitNet version {selected.version!r} artifact missing: "
                f"{selected.artifact_path}"
            )
        # Composition path must still resolve
        self.resolve_composition_model_path()


def assert_serve_allowed(*, use_bitnet: bool, registry_path: Path | str | None = None) -> None:
    """Module-level helper for CRT / hooks."""
    BitNetRegistry(registry_path).load().assert_serve_allowed(use_bitnet=use_bitnet)


def resolve_composition_model_path(registry_path: Path | str | None = None) -> str:
    """Resolve model path for get_default_composition / bitnet_score."""
    return BitNetRegistry(registry_path).load().resolve_composition_model_path()
