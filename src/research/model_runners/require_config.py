"""Strict config accessors for model_runners — single source of truth only.

No soft-get. No defaults. Missing keys raise KeyError with a full path.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def require_key(mapping: Mapping[str, Any], key: str, *, path: str) -> Any:
    """Return mapping[key] or raise KeyError('missing production config: path.key')."""
    if not isinstance(mapping, Mapping):
        raise KeyError(
            f"expected mapping at '{path}', got {type(mapping).__name__}"
        )
    if key not in mapping:
        loc = f"{path}.{key}" if path else key
        raise KeyError(f"missing production config: {loc}")
    return mapping[key]


def require_section(config: Mapping[str, Any], section: str) -> Mapping[str, Any]:
    """Return top-level production config section; must be a mapping."""
    value = require_key(config, section, path="")
    if not isinstance(value, Mapping):
        raise KeyError(
            f"production config section '{section}' must be a mapping, "
            f"got {type(value).__name__}"
        )
    return value


def load_production_json(
    *,
    repo_root: Path,
    config_path: Path | None,
) -> tuple[dict[str, Any], Path]:
    """Load exactly one production config file.

    Resolution (one path only):
      - if config_path is set → that file must exist
      - else ACTIVE_VERSION pointer → configs/production/{version}.json must exist

    No merge with ENGINE_RUNNER_DEFAULTS. No third path.
    """
    if config_path is not None:
        path = config_path if config_path.is_absolute() else (repo_root / config_path)
        if not path.is_file():
            raise FileNotFoundError(f"production config not found: {path}")
    else:
        pointer = repo_root / "configs" / "production" / "ACTIVE_VERSION"
        if not pointer.is_file():
            raise FileNotFoundError(
                f"ACTIVE_VERSION pointer missing: {pointer}. "
                "Pass --config-path explicitly or create the pointer."
            )
        version = pointer.read_text(encoding="utf-8").strip()
        if not version:
            raise RuntimeError(f"ACTIVE_VERSION is empty: {pointer}")
        path = repo_root / "configs" / "production" / f"{version}.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"production config for ACTIVE_VERSION={version!r} not found: {path}"
            )

    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError(f"production config root must be object: {path}")
    return data, path.resolve()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
