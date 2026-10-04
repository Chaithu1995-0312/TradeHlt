#!/usr/bin/env python3
"""
Build machine-readable twin of Repository Encyclopedia rows.

Output (GENERATED — regenerate, do not hand-edit as sole truth):
  docs/book/encyclopedia/encyclopedia_rows.jsonl

Each line is one JSON object:
  id, path, kind, phase, group, relevance, purpose, package, classes,
  source_doc, book_status, bytes, generated_at

Usage:
  python grok/build_encyclopedia_jsonl.py
  python grok/build_encyclopedia_jsonl.py --check   # verify non-empty + schema keys
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "book" / "encyclopedia" / "encyclopedia_rows.jsonl"
COVERAGE_XLSX = REPO / "grok" / "Book_PDF_File_Coverage_Grok.xlsx"

# phase → (group, default_relevance, source_doc, package roots relative to repo)
PHASE_SCOPES: list[tuple[str, str, str, str, list[str]]] = [
    (
        "E1",
        "A",
        "LIVE",
        "docs/book/encyclopedia/E1-spine-implementation.md",
        [
            "src/core",
            "src/config_layer",
            "src/engines",
            "src/runtime",
            "src/execution",
            "src/live",
            "src/inout",
            "src/control_plane",
        ],
    ),
    (
        "E1b",
        "A",
        "LIVE",
        "docs/book/encyclopedia/E1b-features-registry.md",
        ["src/features"],
    ),
    (
        "E2",
        "D",
        "RESEARCH",
        "docs/book/encyclopedia/E2-research-utilities.md",
        ["src/research", "scripts/research"],
    ),
    (
        "E3",
        "D",
        "LIVE_OPS",
        "docs/book/encyclopedia/E3-governance-tooling.md",
        [
            "src/governance",
            "scripts/governance",
            "scripts/analysis",
            "scripts/maintenance",
        ],
    ),
    (
        "E4",
        "B",
        "SIDECAR",
        "docs/book/encyclopedia/E4-sidecar-modules.md",
        [
            "src/bitnet",
            "src/utils",
            "src/retrieval",
            "src/training",
            "src/expansion",
            "src/portfolio",
            "src/replay",
            "src/analytics",
            "src/regime",
            "src/msip",
            "src/multi_llm",
            "src/events",
            "src/search",
            "src/monitoring",
        ],
    ),
    (
        "E5",
        "C",
        "DORMANT",
        "docs/book/encyclopedia/E5-dormant-modules.md",
        [
            "src/strategies",
            "src/scanner",
            "src/journal",
            "src/cognitive",
            "src/feedback",
            "src/llm_research",
            "src/data_ingestion",
            "src/uat",
            "src/ui",
            "archive",
        ],
    ),
    (
        "E6",
        "D",
        "OPS",
        "docs/book/encyclopedia/E6-remaining-scripts.md",
        [
            "scripts/data",
            "scripts/training",
            "scripts/context",
            "scripts/misc",
            "scripts/evaluation",
            "scripts/export",
            "scripts/groq_bridge",
            "scripts/backtest",
            "scripts/control_plane",
            "scripts/metrics",
            "scripts/multi_llm",
            "scripts/portfolio",
        ],
    ),
]

# path-prefix overrides for relevance
RELEVANCE_OVERRIDES: list[tuple[str, str]] = [
    (r"^src/features/feature_pipeline\.py$", "LIVE"),
    (r"^src/features/feature_schema\.py$", "LIVE"),
    (r"^src/features/registry/", "LIVE"),
    (r"^src/features/candle_math\.py$", "LIVE"),
    (r"^src/features/derived_math\.py$", "LIVE"),
    (r"^src/data_ingestion/dataset_integrity\.py$", "LIVE_RESEARCH"),
    (r"^src/data_ingestion/historical_fetcher\.py$", "LEGACY"),
    (r"^src/bitnet/", "INERT_UNTIL_CONFIG"),
    (r"^src/msip/", "OBSERVE_ONLY"),
    (r"^src/portfolio/", "UNWIRED_LIVE"),
    (r"^src/replay/", "SIDECAR"),
    (r"^src/strategies/", "DORMANT"),
    (r"^src/scanner/", "DORMANT"),
    (r"^src/cognitive/", "DORMANT"),
    (r"^src/feedback/", "DORMANT"),
    (r"^src/llm_research/", "DORMANT"),
    (r"^src/uat/", "DORMANT"),
    (r"^src/ui/", "DORMANT"),
    (r"^archive/", "ARCHIVED"),
    (r"^src/config_layer/rr/rr_fusion\.py$", "INERT_DISABLED"),
    (r"^src/training/trade_net_v2\.py$", "UNWIRED"),
    (r"^src/research/", "RESEARCH"),
    (r"^scripts/research/", "RESEARCH"),
    (r"^scripts/governance/", "LIVE_OPS"),
    (r"^scripts/analysis/", "OBSERVE_ONLY"),
    (r"^src/governance/promotion_manager\.py$", "LIVE"),
    (r"^src/core/(engine_runner|fusion_engine|decision_engine|ultron_risk_gate)\.py$", "LIVE"),
    (r"^src/config_layer/(crt_engine_v2|production_config|execution_planner)\.py$", "LIVE"),
]


def first_doc(path: Path) -> str:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
        d = ast.get_docstring(tree) or ""
    except Exception:
        return ""
    if not d:
        return ""
    lines = [
        ln.strip()
        for ln in d.strip().splitlines()
        if ln.strip() and not set(ln.strip()) <= set("=─- #*╔╗╚╝║═")
    ]
    return " ".join(lines[:4])[:400]


def class_names(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        return [n.name for n in tree.body if isinstance(n, ast.ClassDef)][:12]
    except Exception:
        return []


def slug_id(path: str) -> str:
    s = path.replace("\\", "/").replace("/", "-").replace(".", "-")
    s = re.sub(r"[^A-Za-z0-9_\-]", "", s)
    return "enc-" + s[:180]


def relevance_for(path: str, default: str) -> str:
    for pat, rel in RELEVANCE_OVERRIDES:
        if re.search(pat, path.replace("\\", "/")):
            return rel
    return default


def load_book_status() -> dict[str, str]:
    status: dict[str, str] = {}
    if not COVERAGE_XLSX.exists():
        return status
    try:
        import openpyxl

        wb = openpyxl.load_workbook(COVERAGE_XLSX, read_only=True, data_only=True)
        ws = wb["File_Coverage_All"]
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue
            # inventory, file, package, book_status, ...
            f = (row[1] or "").replace("\\", "/")
            st = row[3] or ""
            if f:
                status[f] = str(st)
        wb.close()
    except Exception:
        pass
    return status


def iter_py_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file() and root.suffix == ".py":
        return [root]
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def build_rows() -> list[dict]:
    today = date.today().isoformat()
    book_status = load_book_status()
    rows: list[dict] = []
    seen: set[str] = set()

    # Meta row for charter
    rows.append(
        {
            "id": "enc-meta-charter",
            "path": "docs/book/24-repository-encyclopedia.md",
            "kind": "charter",
            "phase": "E0",
            "group": "META",
            "relevance": "CHARTER",
            "purpose": "Repository Encyclopedia charter: Groups A-D, phases E0-E6, path from architecture guide to file map.",
            "package": "docs/book",
            "classes": [],
            "source_doc": "docs/book/24-repository-encyclopedia.md",
            "book_status": "N/A",
            "bytes": (REPO / "docs/book/24-repository-encyclopedia.md").stat().st_size
            if (REPO / "docs/book/24-repository-encyclopedia.md").exists()
            else 0,
            "generated_at": today,
        }
    )

    for phase, group, default_rel, source_doc, roots in PHASE_SCOPES:
        for root_rel in roots:
            root = REPO / root_rel
            for path in iter_py_files(root):
                rel = path.relative_to(REPO).as_posix()
                if rel in seen:
                    # prefer earlier phase assignment (E1 before E5, etc.)
                    continue
                seen.add(rel)
                pkg = rel.split("/")[1] if rel.startswith("src/") and "/" in rel[4:] else (
                    rel.split("/")[1] if rel.startswith("scripts/") else rel.split("/")[0]
                )
                purpose = first_doc(path)
                if not purpose:
                    purpose = f"{Path(rel).name} — see {source_doc}"
                rows.append(
                    {
                        "id": slug_id(rel),
                        "path": rel,
                        "kind": "module",
                        "phase": phase,
                        "group": group,
                        "relevance": relevance_for(rel, default_rel),
                        "purpose": purpose,
                        "package": pkg,
                        "classes": class_names(path),
                        "source_doc": source_doc,
                        "book_status": book_status.get(rel, "UNKNOWN"),
                        "bytes": path.stat().st_size,
                        "generated_at": today,
                    }
                )

    # Root scripts/*.py not in a subdir (E6 residual)
    scripts_root = REPO / "scripts"
    if scripts_root.exists():
        for path in sorted(scripts_root.glob("*.py")):
            rel = path.relative_to(REPO).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            rows.append(
                {
                    "id": slug_id(rel),
                    "path": rel,
                    "kind": "module",
                    "phase": "E6",
                    "group": "D",
                    "relevance": relevance_for(rel, "OPS"),
                    "purpose": first_doc(path) or f"{path.name} — root scripts operator CLI",
                    "package": "scripts",
                    "classes": class_names(path),
                    "source_doc": "docs/book/encyclopedia/E6-remaining-scripts.md",
                    "book_status": book_status.get(rel, "UNKNOWN"),
                    "bytes": path.stat().st_size,
                    "generated_at": today,
                }
            )

    # Encyclopedia document index rows
    enc_dir = REPO / "docs" / "book" / "encyclopedia"
    for md in sorted(enc_dir.glob("*.md")):
        rel = md.relative_to(REPO).as_posix()
        if rel in seen:
            continue
        rows.append(
            {
                "id": slug_id(rel),
                "path": rel,
                "kind": "encyclopedia_doc",
                "phase": "META",
                "group": "META",
                "relevance": "DOCUMENTATION",
                "purpose": first_doc(md) or md.name,
                "package": "encyclopedia",
                "classes": [],
                "source_doc": rel,
                "book_status": "N/A",
                "bytes": md.stat().st_size,
                "generated_at": today,
            }
        )

    return rows


REQUIRED_KEYS = {
    "id",
    "path",
    "kind",
    "phase",
    "group",
    "relevance",
    "purpose",
    "source_doc",
    "generated_at",
}


def write_jsonl(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def check_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"MISSING {path}")
    n = 0
    phases: dict[str, int] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            missing = REQUIRED_KEYS - obj.keys()
            if missing:
                raise SystemExit(f"schema miss {missing} in {obj.get('id')}")
            n += 1
            phases[obj.get("phase", "?")] = phases.get(obj.get("phase", "?"), 0) + 1
    if n < 100:
        raise SystemExit(f"too few rows: {n}")
    print(f"CHECK OK rows={n} phases={phases}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    if args.check:
        check_file(args.out)
        return 0
    rows = build_rows()
    write_jsonl(rows, args.out)
    # summary
    phases: dict[str, int] = {}
    for r in rows:
        phases[r["phase"]] = phases.get(r["phase"], 0) + 1
    print(f"WROTE {args.out} rows={len(rows)}")
    for k in sorted(phases):
        print(f"  {k:6} {phases[k]:5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
