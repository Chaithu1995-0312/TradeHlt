"""SITS script census core (PR-6 extract from scripts/analysis/script_census.py).

Library API for discovery + path-stable stub merge. CLI wrapper remains at
``scripts/analysis/script_census.py`` (thin). Inventory authority only — never import
from trading spine (engine_runner / live_engine_hook / backtest_v2).
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from governance.script_registry import ScriptRegistry, normalize_posix, scr_num
from utils.jsonl_writer import read_jsonl

# Aligned with scripts/analysis/python_source_static_census.EXCLUDED_PARTS
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

CENSUS_OWNED_FIELDS = frozenset({"path", "has_main"})
DEFAULT_STUB_TS = "2026-08-02T00:00:00Z"
THIN_MAX_NON_IMPORT_LOC = 40

# Repo root: src/governance/this → parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DiscoveredFile:
    path: str  # POSIX repo-relative
    has_main: bool
    hygiene_env_access: bool
    suggested_category: str
    suggested_lifecycle: str


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def _file_has_main(path: Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src, filename=str(path))
    except (OSError, SyntaxError):
        return False
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
            left, comps = test.left, test.comparators
            if (
                isinstance(left, ast.Name)
                and left.id == "__name__"
                and len(comps) == 1
                and isinstance(comps[0], ast.Constant)
                and comps[0].value == "__main__"
            ):
                return True
    return False


def _hygiene_env_access(path: Path) -> bool:
    """Report-only: dotenv / os.environ / os.getenv presence."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    needles = ("os.environ", "os.getenv", "dotenv", "load_dotenv")
    return any(n in text for n in needles)


def default_category(rel_posix: str) -> str:
    """Directory heuristic — never returns CANONICAL_CLI (K17)."""
    p = rel_posix
    name = Path(p).name
    if "/" not in p:
        return "PROBE" if name.startswith("_") else "ORPHAN"
    if p.startswith("scripts/probes/") or p.startswith("scripts/tmp/"):
        return "PROBE"
    if p.startswith("scripts/analysis/"):
        return "DIAGNOSTIC"
    if p.startswith("scripts/research/") or p.startswith("scripts/backtest/"):
        return "RESEARCH_RUNNER"
    if p.startswith("scripts/evaluation/") or p.startswith("scripts/portfolio/"):
        return "RESEARCH_RUNNER"
    if p.startswith("scripts/training/"):
        return "TRAINING"
    if p.startswith("scripts/governance/"):
        return "GOVERNANCE"
    if p.startswith("scripts/data/"):
        return "DATA"
    if p.startswith("scripts/maintenance/") or p.startswith("scripts/export/"):
        return "MAINTENANCE"
    if p.startswith("scripts/context/") or p.startswith("scripts/multi_llm/"):
        return "GOVERNANCE"
    if p.startswith("scripts/control_plane/") or p.startswith("scripts/groq_bridge/"):
        return "GOVERNANCE"
    return "ORPHAN"


def default_lifecycle(rel_posix: str) -> str:
    name = Path(rel_posix).name
    if "/" not in rel_posix and name.startswith("_"):
        return "EPHEMERAL"
    if rel_posix.startswith("scripts/probes/") or rel_posix.startswith("scripts/tmp/"):
        return "EPHEMERAL"
    return "ACTIVE"


def discover_paths(
    repo_root: Path | None = None,
    *,
    include_src_cli: bool = False,
) -> list[DiscoveredFile]:
    """Walk scripts/** + root *.py; optional src/** with __main__."""
    root = (repo_root or _REPO_ROOT).resolve()
    found: list[DiscoveredFile] = []

    scripts_dir = root / "scripts"
    if scripts_dir.is_dir():
        for path in sorted(scripts_dir.rglob("*.py")):
            if _is_excluded(path):
                continue
            rel = normalize_posix(path.relative_to(root))
            found.append(
                DiscoveredFile(
                    path=rel,
                    has_main=_file_has_main(path),
                    hygiene_env_access=_hygiene_env_access(path),
                    suggested_category=default_category(rel),
                    suggested_lifecycle=default_lifecycle(rel),
                )
            )

    for path in sorted(root.glob("*.py")):
        if _is_excluded(path):
            continue
        rel = normalize_posix(path.name)
        found.append(
            DiscoveredFile(
                path=rel,
                has_main=_file_has_main(path),
                hygiene_env_access=_hygiene_env_access(path),
                suggested_category=default_category(rel),
                suggested_lifecycle=default_lifecycle(rel),
            )
        )

    if include_src_cli:
        src_dir = root / "src"
        if src_dir.is_dir():
            for path in sorted(src_dir.rglob("*.py")):
                if _is_excluded(path):
                    continue
                if not _file_has_main(path):
                    continue
                rel = normalize_posix(path.relative_to(root))
                found.append(
                    DiscoveredFile(
                        path=rel,
                        has_main=True,
                        hygiene_env_access=_hygiene_env_access(path),
                        suggested_category="ORPHAN",
                        suggested_lifecycle="ACTIVE",
                    )
                )

    by_path: dict[str, DiscoveredFile] = {}
    for f in found:
        by_path[f.path] = f
    return [by_path[k] for k in sorted(by_path)]


def write_stubs(
    out_path: Path,
    discovered: Iterable[DiscoveredFile],
    *,
    timestamp: str = DEFAULT_STUB_TS,
) -> list[dict]:
    """Path-stable merge (K14/K19). Preserve SCR ids; max+1 only for new paths."""
    out_path = Path(out_path)
    existing_by_path: dict[str, dict] = {}
    if out_path.exists():
        for rec in read_jsonl(out_path):
            p = normalize_posix(rec.get("path", ""))
            if p:
                existing_by_path[p] = rec

    max_n = 0
    for rec in existing_by_path.values():
        try:
            max_n = max(max_n, scr_num(rec["id"]))
        except (ValueError, KeyError):
            continue

    disc_list = sorted(discovered, key=lambda x: x.path)
    out: list[dict] = []
    seen_paths: set[str] = set()

    for f in disc_list:
        path = normalize_posix(f.path)
        seen_paths.add(path)
        if path in existing_by_path:
            rec = dict(existing_by_path[path])
            rec["path"] = path
            rec["has_main"] = f.has_main
            out.append(rec)
        else:
            max_n += 1
            rec = ScriptRegistry.new_stub_record(
                script_id=f"SCR-{max_n:03d}",
                path=path,
                has_main=f.has_main,
                category=f.suggested_category,
                lifecycle=f.suggested_lifecycle,
                timestamp=timestamp,
            )
            out.append(rec)

    for path, rec in existing_by_path.items():
        if path not in seen_paths:
            out.append(dict(rec))

    out.sort(key=lambda r: r["id"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for rec in out:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    return out


def census_report(discovered: list[DiscoveredFile]) -> dict:
    by_cat: dict[str, int] = {}
    env_hits = 0
    main_hits = 0
    for f in discovered:
        by_cat[f.suggested_category] = by_cat.get(f.suggested_category, 0) + 1
        if f.hygiene_env_access:
            env_hits += 1
        if f.has_main:
            main_hits += 1
    return {
        "total": len(discovered),
        "by_suggested_category": dict(sorted(by_cat.items())),
        "has_main_count": main_hits,
        "hygiene_env_access_count": env_hits,
        "note": "hygiene_env_access is report-only; never fails --validate",
    }
