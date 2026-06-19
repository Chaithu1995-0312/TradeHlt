"""
analytics_config — strict loader for the dedicated `config/analytics.json`.

Kept separate from the trading production config (so the analytics layer stays disposable
and never triggers a params rehash). Fail-fast: `_require` raises on a missing key — NO
silent `.get(key, default)` (CLAUDE.md §6.5).
"""
from __future__ import annotations

import json
from pathlib import Path

_CFG_PATH = Path(__file__).resolve().parent / "config" / "analytics.json"


def _require(cfg: dict, key: str) -> object:
    """Strict accessor — raises KeyError if `key` is absent from a present section."""
    if key not in cfg:
        raise KeyError(
            f"analytics_config: required key '{key}' missing from analytics.json."
        )
    return cfg[key]


def load_config(path: "str | Path | None" = None) -> dict:
    """Load and return the analytics config dict (raises if the file is missing)."""
    p = Path(path) if path else _CFG_PATH
    if not p.exists():
        raise FileNotFoundError(f"analytics_config: config not found at {p}")
    return json.loads(p.read_text(encoding="utf-8"))
