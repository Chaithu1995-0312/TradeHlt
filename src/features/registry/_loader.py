"""Ontology loader — leaf module (no intra-package deps) so registry submodules can share it
without import cycles. Lazy PyYAML import keeps the hot path free of a hard dependency."""
from __future__ import annotations

import copy
from pathlib import Path

# Repo-root-relative path to the WHAT authority (configs/formulas/market_ontology.yaml).
_ONTOLOGY_PATH = Path(__file__).resolve().parents[3] / "configs" / "formulas" / "market_ontology.yaml"
_CACHE: dict[Path, tuple[int, dict]] = {}


def load_ontology(path: Path | None = None) -> dict:
    """Load and return the market ontology dict. Lazy PyYAML import."""
    import yaml  # lazy — importing the registry never forces PyYAML onto the hot path
    p = (path or _ONTOLOGY_PATH).resolve()
    mtime_ns = p.stat().st_mtime_ns
    cached = _CACHE.get(p)
    if cached is None or cached[0] != mtime_ns:
        _CACHE[p] = (mtime_ns, yaml.safe_load(p.read_text(encoding="utf-8")))
    return copy.deepcopy(_CACHE[p][1])
