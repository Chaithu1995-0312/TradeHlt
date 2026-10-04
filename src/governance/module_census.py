"""Module attribution census core — discovery + path-stable stub merge for ``src/**/*.py``.

Mirrors :mod:`governance.script_census` (SITS) one-for-one; the CLI wrapper is thin at
``scripts/analysis/module_census.py``. Stdlib-only by design: the ratchet this feeds is a
CI floor and must never fail for environment reasons (no pandas / openpyxl).

Inventory authority only — never import from the trading spine.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from governance.module_attribution import (
    REGIME_ENUM,
    UNATTRIBUTED,
    new_stub_record,
    normalize_posix,
)

# Aligned with governance.script_census.EXCLUDED_PARTS
EXCLUDED_PARTS = frozenset({
    ".git",
    ".claude",
    "archive",
    "venv",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "__pycache__",
})

#: Directories under src/ that are build residue, not source.
EXCLUDED_PACKAGES = frozenset({"tradelatest.egg-info"})

CENSUS_OWNED_FIELDS = frozenset({"module_path"})
DEFAULT_STUB_TS = "2026-08-07T00:00:00Z"

# Repo root: src/governance/this → parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Package → regime heuristic. SUGGESTION ONLY — it seeds `regime` on new stub rows and
#: never sets `owner_surface`, which stays UNATTRIBUTED until an overlay claims it.
#: Only DECISION is expected to pursue the expensive G2/G3 grades.
PACKAGE_REGIME: dict[str, str] = {
    # the live decision path — CRT TRADE_OPENED → ORDER
    "core": "DECISION",
    "engines": "DECISION",
    "runtime": "DECISION",
    "execution": "DECISION",
    "inout": "DECISION",
    "live": "DECISION",
    # feature/config substrate (largely covered by CANONICAL_FEATURE_CODE_SURFACE)
    "features": "SUBSTRATE",
    "config_layer": "SUBSTRATE",
    # model train/serve lineages (already AUDITED as surfaces)
    "bitnet": "MODEL_LINEAGE",
    "training": "MODEL_LINEAGE",
    # research regime — one surface under the Measurement Contract, not per-module audit
    "research": "RESEARCH",
    "llm_research": "RESEARCH",
    "interpreters": "RESEARCH",
    "msip": "RESEARCH",
    "retrieval": "RESEARCH",
    "expansion": "RESEARCH",
    "regime": "RESEARCH",
    "search": "RESEARCH",
    # platform / tooling — governs the repo, does not decide trades
    "governance": "PLATFORM",
    "control_plane": "PLATFORM",
    "agent": "PLATFORM",
    "utils": "PLATFORM",
    "multi_llm": "PLATFORM",
    "journal": "PLATFORM",
    "events": "PLATFORM",
    "monitoring": "PLATFORM",
    "uat": "PLATFORM",
    "validation_access": "PLATFORM",
    "ui": "PLATFORM",
    "logs": "PLATFORM",
    # sidecar / orphaned per F-012 (ReplayMemory/CognitiveBus/Cluster/HMF) and
    # F-013 (scan→allocate→ExecutionLoop + PortfolioAllocator built but orphaned)
    "replay": "TERMINAL",
    "cognitive": "TERMINAL",
    "portfolio": "TERMINAL",
    "scanner": "TERMINAL",
    "feedback": "TERMINAL",
    "analytics": "TERMINAL",
    "strategies": "TERMINAL",
    "data_ingestion": "TERMINAL",
}


@dataclass(frozen=True)
class DiscoveredModule:
    path: str  # POSIX repo-relative
    package: str  # top-level package under src/ ("" for src/__init__.py)
    is_package_init: bool
    suggested_regime: str


def _is_excluded(path: Path) -> bool:
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return True
    return any(part in EXCLUDED_PACKAGES for part in path.parts)


def package_of(rel_posix: str) -> str:
    """Top-level package under src/. Returns "" for src/__init__.py."""
    parts = normalize_posix(rel_posix).split("/")
    if len(parts) < 3:  # src/<file>.py
        return ""
    return parts[1]


def default_regime(rel_posix: str) -> str:
    pkg = package_of(rel_posix)
    if not pkg:  # src/__init__.py — the package root marker itself
        return "PLATFORM"
    regime = PACKAGE_REGIME.get(pkg, "UNKNOWN")
    return regime if regime in REGIME_ENUM else "UNKNOWN"


def discover_modules(repo_root: Path | None = None) -> list[DiscoveredModule]:
    """Walk every ``src/**/*.py``. This set is the closure denominator."""
    root = (repo_root or _REPO_ROOT).resolve()
    src_dir = root / "src"
    found: list[DiscoveredModule] = []
    if not src_dir.is_dir():
        return found

    for path in sorted(src_dir.rglob("*.py")):
        if _is_excluded(path):
            continue
        rel = normalize_posix(path.relative_to(root))
        found.append(
            DiscoveredModule(
                path=rel,
                package=package_of(rel),
                is_package_init=path.name == "__init__.py",
                suggested_regime=default_regime(rel),
            )
        )

    by_path = {f.path: f for f in found}
    return [by_path[k] for k in sorted(by_path)]


def write_stubs(
    out_path: Path,
    discovered: Iterable[DiscoveredModule],
    *,
    timestamp: str = DEFAULT_STUB_TS,
) -> list[dict]:
    """Path-stable merge: MOD ids are never reassigned; max+1 only for genuinely new paths.

    Rows whose module_path has vanished from disk are retained (never silently dropped) so
    the deletion shows up as ``missing_on_disk`` in coverage rather than disappearing.
    """
    out_path = Path(out_path)
    existing_by_path: dict[str, dict] = {}
    if out_path.exists():
        with out_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                p = normalize_posix(rec.get("module_path", ""))
                if p:
                    existing_by_path[p] = rec

    max_n = 0
    for rec in existing_by_path.values():
        rid = rec.get("id", "")
        if isinstance(rid, str) and rid.startswith("MOD-"):
            try:
                max_n = max(max_n, int(rid.split("-", 1)[1]))
            except ValueError:
                continue

    out: list[dict] = []
    seen_paths: set[str] = set()

    for f in sorted(discovered, key=lambda x: x.path):
        path = normalize_posix(f.path)
        seen_paths.add(path)
        if path in existing_by_path:
            # Census owns module_path only; every attribution field is overlay-owned.
            rec = dict(existing_by_path[path])
            rec["module_path"] = path
            out.append(rec)
        else:
            max_n += 1
            out.append(
                new_stub_record(
                    module_id=f"MOD-{max_n:04d}",
                    module_path=path,
                    regime=f.suggested_regime,
                    reachability="UNKNOWN",
                    timestamp=timestamp,
                    notes="AUTO_STUB — regime is a package heuristic; owner_surface needs an overlay",
                )
            )

    for path, rec in existing_by_path.items():
        if path not in seen_paths:
            out.append(dict(rec))

    out.sort(key=lambda r: r["id"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for rec in out:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    return out


def census_report(discovered: list[DiscoveredModule]) -> dict:
    by_regime: dict[str, int] = {}
    by_package: dict[str, int] = {}
    inits = 0
    for f in discovered:
        by_regime[f.suggested_regime] = by_regime.get(f.suggested_regime, 0) + 1
        key = f.package or "<src root>"
        by_package[key] = by_package.get(key, 0) + 1
        if f.is_package_init:
            inits += 1
    return {
        "total": len(discovered),
        "by_suggested_regime": dict(sorted(by_regime.items())),
        "by_package": dict(sorted(by_package.items())),
        "package_init_count": inits,
        "unattributed_sentinel": UNATTRIBUTED,
        "note": (
            "suggested_regime is a package heuristic seeded onto NEW stub rows only; "
            "owner_surface is never set by the census and requires an overlay"
        ),
    }
