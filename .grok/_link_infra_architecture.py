"""Name-census + infra-doc join for GCMC trees.

Does NOT read every source file. Walks paths, joins Excel inventories to
HOW_INDEX / INFRA / topics / architecture citations, assigns LLM stack rooms
from path prefixes, appends link columns to the existing workbooks, and
writes `.grok/infra_architecture_link.xlsx`.

Usage:
    python .grok/_link_infra_architecture.py
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIR = {"__pycache__", ".git", "venv", ".venv", ".claude", "node_modules", "logs"}
GCMC_V1 = ("src", "scripts", "tests")
GCMC_V2 = ("mt5_analytics", "oss_lab", "tools")
GCMC_V3_DIRS = (
    "archive", "grok", "exec_telemetry", "manual_tools", "reports", "docs",
    "msip_1_verification_package", "H-SECONDLOW-002_Complete_Package",
    ".grok", "results", "copiedSrcFiles", "terminals",
)
ROOT_PY_FILES = (
    "__init__.py", "_dedent.py", "_find_callers.py", "_find_context_calls.py",
    "_fm026_cert_probe.py", "_gate0_check.py", "_gate0b_check.py", "_gate0de_check.py",
    "_m6r_remediation.py", "_m7v_presession.py", "_m8_cert_probe.py", "_m8_checkpoint.py",
    "_m8_ledger_mutate.py", "_run_mr.py", "_scripts_functionality_export.py",
    "analyze_crt_pipeline.py", "audit.py", "build_zone_registry_forced.py",
    "build_zone_registry_from_trades.py", "count_audit_tmp.py", "run_phase_a_tests.py",
    "run_regime_search.py", "run_tests_capture.py",
)
EXCLUDED_TREES = {
    "logs": "whole-repo scratch-worktree copies, 0 tracked",
    ".claude": "agent worktree copies, 0 tracked",
}

TRACKED_PY: set[str] = set()  # populated by load_tracked_py() at start of main()


def load_tracked_py() -> set[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {line.strip().replace("\\", "/") for line in out.stdout.splitlines() if line.strip()}


def count_py_raw(tree: str) -> tuple[int, int]:
    """(.py count, git-tracked count) under `tree`, ignoring SKIP_DIR — for the Excluded sheet.

    Unlike walk_py(), this does not self-exclude `tree` via SKIP_DIR (SKIP_DIR now names
    `logs`/`.claude` precisely so other walks don't descend into them; this function is the
    one place that still needs to count what's inside).
    """
    root = ROOT / tree
    if not root.exists():
        return 0, 0
    n = 0
    tracked = 0
    for p in root.rglob("*.py"):
        if any(part in {"__pycache__", ".git", "venv", ".venv", "node_modules"} for part in p.parts):
            continue
        n += 1
        if p.relative_to(ROOT).as_posix() in TRACKED_PY:
            tracked += 1
    return n, tracked

WB_SRC = ROOT / "results" / "analysis" / "src_business_functionality.xlsx"
WB_SCRIPTS = ROOT / "scripts_business_functionality.xlsx"
WB_TESTS = ROOT / "docs" / "analysis" / "tests_functionality_inventory.xlsx"
WB_V2 = ROOT / ".grok" / "gcmc_v2_inventory.xlsx"
WB_LINK = ROOT / ".grok" / "infra_architecture_link.xlsx"
REPORT_JSON = ROOT / ".grok" / "infra_architecture_link_coverage.json"

LINK_HEADERS = [
    "Disk present",
    "Git tracked",
    "Cited in How-Index",
    "Cited in Topics",
    "Cited in Architecture",
    "Cited in INFRA",
    "Cited in remainder inventory",
    "Infra-doc referenced",
    "LLM stack room",
    "LLM allowance",
    "Spine or sidecar",
    "This analysis referenced",
]

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF")
YES_FILL = PatternFill("solid", fgColor="C6EFCE")
NO_FILL = PatternFill("solid", fgColor="FFC7CE")

PATH_RE = re.compile(
    r"(?:src|scripts|tests|mt5_analytics|oss_lab|tools"
    r"|archive|grok|exec_telemetry|manual_tools|reports|docs"
    r"|msip_1_verification_package|H-SECONDLOW-002_Complete_Package"
    r"|\.grok|results|copiedSrcFiles|terminals)"
    r"/[A-Za-z0-9_./\-]+\.py"
)
# Repo-root files carry no directory prefix, so PATH_RE can't see them without
# false-positiving on every bare "core/engine_runner.py"-style relative mention
# docs already make. Match those 23 names by exact token instead.
ROOT_PY_TOKEN_RE = re.compile(r"(?<![\w/])([A-Za-z_][A-Za-z0-9_]*\.py)(?![\w/])")

# More-specific prefixes first.
_ROOM_RULES: list[tuple[str, str, str, str]] = [
    # LLM sideline
    ("src/agent/", "llm_sideline", "GOVERNANCE_GATED", "sidecar"),
    ("src/llm_research/", "llm_sideline", "ALLOWED_SIDELINE", "sidecar"),
    ("src/multi_llm/", "llm_sideline", "ALLOWED_SIDELINE", "sidecar"),
    ("src/control_plane/context_report.py", "llm_sideline", "ALLOWED_SIDELINE", "sidecar"),
    ("src/control_plane/code_context_extractor.py", "llm_sideline", "ALLOWED_SIDELINE", "sidecar"),
    ("src/expansion/llm_pattern_extractor.py", "llm_sideline", "ALLOWED_SIDELINE", "sidecar"),
    ("src/config_layer/llm_scorer.py", "llm_sideline", "TIEBREAK_NEUTRAL_FALLBACK", "sidecar"),
    ("src/config_layer/llm_inference_client.py", "llm_sideline", "TIEBREAK_NEUTRAL_FALLBACK", "sidecar"),
    ("src/search/", "llm_sideline", "ALLOWED_SIDELINE", "sidecar"),
    # structure
    ("src/config_layer/crt_engine_v2.py", "structure", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/config_layer/parent_crt.py", "structure", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/config_layer/crt_", "structure", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/config_layer/state_", "structure", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/core/feature_store.py", "data_clock_identity", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/features/crt_", "structure", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/features/smc/", "structure", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/charts/", "structure", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/structure/", "structure", "FORBIDDEN_HOT_PATH", "spine"),
    # data / clock / identity
    ("src/identity/", "data_clock_identity", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/data_ingestion/", "data_clock_identity", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/features/broker_clock.py", "data_clock_identity", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/features/", "data_clock_identity", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/inout/", "data_clock_identity", "FORBIDDEN_HOT_PATH", "spine"),
    # trade object / costs / measurement
    ("src/research/", "measurement", "MEASUREMENT_ONLY", "sidecar"),
    ("src/analytics/", "trade_object_costs", "MEASUREMENT_ONLY", "sidecar"),
    ("src/journal/", "trade_object_costs", "FORBIDDEN_HOT_PATH", "spine"),
    # decision / risk / execution
    ("src/core/ultron", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/core/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/engines/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/runtime/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/execution/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/live/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/portfolio/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/config_layer/execution_planner.py", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/config_layer/", "governance", "GOVERNANCE_GATED", "spine"),
    # governance
    ("src/governance/", "governance", "GOVERNANCE_GATED", "sidecar"),
    ("src/control_plane/", "governance", "GOVERNANCE_GATED", "sidecar"),
    ("src/validation_access/", "governance", "GOVERNANCE_GATED", "sidecar"),
    ("src/bitnet/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/training/", "measurement", "MEASUREMENT_ONLY", "sidecar"),
    ("src/interpreters/", "structure", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/regime/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/expansion/", "governance", "GOVERNANCE_GATED", "sidecar"),
    # sidecar / orphan
    ("src/cognitive/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/replay/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/scanner/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/msip/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/feedback/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/monitoring/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/uat/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/ui/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/strategies/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("src/utils/", "data_clock_identity", "FORBIDDEN_HOT_PATH", "spine"),
    ("src/", "sidecar_orphan", "FORBIDDEN_HOT_PATH", "sidecar"),
    # scripts
    ("scripts/research/", "measurement", "MEASUREMENT_ONLY", "sidecar"),
    ("scripts/governance/", "governance", "GOVERNANCE_GATED", "sidecar"),
    ("scripts/analysis/", "measurement", "MEASUREMENT_ONLY", "sidecar"),
    ("scripts/data/", "data_clock_identity", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("scripts/live/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("scripts/training/", "measurement", "MEASUREMENT_ONLY", "sidecar"),
    ("scripts/backtest/", "decision_risk_execution", "FORBIDDEN_HOT_PATH", "sidecar"),
    ("scripts/context/", "llm_sideline", "ALLOWED_SIDELINE", "sidecar"),
    ("scripts/maintenance/", "governance", "GOVERNANCE_GATED", "sidecar"),
    ("scripts/", "tooling_scripts", "ALLOWED_SIDELINE", "sidecar"),
    # tests
    ("tests/", "tests", "N/A_TEST_FLOOR", "sidecar"),
    # v2 lab
    ("mt5_analytics/", "lab", "LAB_ONLY", "sidecar"),
    ("oss_lab/", "lab", "LAB_ONLY", "sidecar"),
    ("tools/", "lab", "LAB_ONLY", "sidecar"),
    # v3 — non-declared trees closed 2026-09-04 (GCMC v3 denominator fix)
    ("archive/", "archived_dead_code", "NOT_LIVE", "sidecar"),
    ("msip_1_verification_package/", "frozen_package", "NOT_LIVE", "sidecar"),
    ("H-SECONDLOW-002_Complete_Package/", "frozen_package", "NOT_LIVE", "sidecar"),
    (".grok/", "self_tooling", "ALLOWED_SIDELINE", "sidecar"),
    ("grok/", "self_tooling", "ALLOWED_SIDELINE", "sidecar"),
    ("results/", "untracked_scratch", "ALLOWED_SIDELINE", "sidecar"),
    ("copiedSrcFiles/", "untracked_scratch", "ALLOWED_SIDELINE", "sidecar"),
    ("terminals/", "untracked_scratch", "ALLOWED_SIDELINE", "sidecar"),
    ("exec_telemetry/", "measurement", "MEASUREMENT_ONLY", "sidecar"),
    ("manual_tools/", "measurement", "MEASUREMENT_ONLY", "sidecar"),
    ("reports/", "measurement", "MEASUREMENT_ONLY", "sidecar"),
    ("docs/", "tooling_scripts", "ALLOWED_SIDELINE", "sidecar"),
]

_ROOT_PY_ROOM = ("root_scripts", "ALLOWED_SIDELINE", "sidecar")


def walk_py(tree: str) -> list[str]:
    root = ROOT / tree
    if not root.exists():
        return []
    out: list[str] = []
    for p in root.rglob("*.py"):
        if any(part in SKIP_DIR for part in p.parts):
            continue
        out.append(p.relative_to(ROOT).as_posix())
    return sorted(out)


def walk_py_root() -> list[str]:
    """Repo-root *.py files only (non-recursive) — the SITS-governed set (CLAUDE.md 3.1b)."""
    out = [name for name in ROOT_PY_FILES if (ROOT / name).is_file()]
    return sorted(out)


def classify(rel: str) -> tuple[str, str, str]:
    rel = rel.replace("\\", "/")
    if "/" not in rel:
        return _ROOT_PY_ROOM
    for prefix, room, allow, spine in _ROOM_RULES:
        if rel.startswith(prefix) or rel == prefix.rstrip("/"):
            return room, allow, spine
    return "unmapped", "UNKNOWN", "sidecar"


def extract_citations(text: str) -> set[str]:
    norm = text.replace("\\", "/")
    found = set(PATH_RE.findall(norm))
    found |= {tok for tok in ROOT_PY_TOKEN_RE.findall(norm) if tok in ROOT_PY_FILES}
    return found


def load_doc_citations() -> dict[str, set[str]]:
    buckets: dict[str, set[str]] = {
        "how_index": set(),
        "infra": set(),
        "topics": set(),
        "architecture": set(),
        "remainder": set(),
    }
    how = ROOT / ".grok" / "HOW_INDEX.md"
    infra = ROOT / ".grok" / "INFRA.md"
    remainder = ROOT / ".grok" / "infra_file_citations.md"
    if how.is_file():
        buckets["how_index"] = extract_citations(how.read_text(encoding="utf-8", errors="replace"))
    if infra.is_file():
        buckets["infra"] = extract_citations(infra.read_text(encoding="utf-8", errors="replace"))
    if remainder.is_file():
        buckets["remainder"] = extract_citations(remainder.read_text(encoding="utf-8", errors="replace"))
    topics = ROOT / "docs" / "topics"
    if topics.is_dir():
        acc: set[str] = set()
        for p in topics.rglob("*.md"):
            acc |= extract_citations(p.read_text(encoding="utf-8", errors="replace"))
        buckets["topics"] = acc
    arch = ROOT / "docs" / "architecture"
    if arch.is_dir():
        acc = set()
        for p in arch.rglob("*.md"):
            acc |= extract_citations(p.read_text(encoding="utf-8", errors="replace"))
        buckets["architecture"] = acc
    return buckets


def yesno(flag: bool) -> str:
    return "YES" if flag else "NO"


def header_map(ws: Worksheet) -> dict[str, int]:
    out: dict[str, int] = {}
    for col in range(1, (ws.max_column or 1) + 1):
        val = ws.cell(1, col).value
        if val:
            out[str(val)] = col
    return out


def ensure_link_columns(ws: Worksheet) -> dict[str, int]:
    headers = header_map(ws)
    col = ws.max_column or 1
    for h in LINK_HEADERS:
        if h in headers:
            continue
        col += 1
        cell = ws.cell(1, col, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        headers[h] = col
    return headers


def paint_yesno(cell) -> None:
    if cell.value == "YES":
        cell.fill = YES_FILL
    elif cell.value == "NO":
        cell.fill = NO_FILL


def link_tuple(rel: str, disk: set[str], cites: dict[str, set[str]]) -> dict[str, str]:
    room, allow, spine = classify(rel)
    how = rel in cites["how_index"]
    topics = rel in cites["topics"]
    arch = rel in cites["architecture"]
    infra = rel in cites["infra"]
    remainder = rel in cites.get("remainder", set())
    any_doc = how or topics or arch or infra or remainder
    return {
        "Disk present": yesno(rel in disk),
        "Git tracked": yesno(rel in TRACKED_PY),
        "Cited in How-Index": yesno(how),
        "Cited in Topics": yesno(topics),
        "Cited in Architecture": yesno(arch),
        "Cited in INFRA": yesno(infra),
        "Cited in remainder inventory": yesno(remainder),
        "Infra-doc referenced": yesno(any_doc),
        "LLM stack room": room,
        "LLM allowance": allow,
        "Spine or sidecar": spine,
        "This analysis referenced": "YES",
    }


def apply_row(ws: Worksheet, row: int, headers: dict[str, int], payload: dict[str, str]) -> None:
    for h, v in payload.items():
        cell = ws.cell(row, headers[h], v)
        if h in {
            "Disk present",
            "Git tracked",
            "Cited in How-Index",
            "Cited in Topics",
            "Cited in Architecture",
            "Cited in INFRA",
            "Cited in remainder inventory",
            "Infra-doc referenced",
            "This analysis referenced",
        }:
            paint_yesno(cell)


def update_sheet(
    path: Path,
    sheet: str,
    file_col_name: str,
    cites: dict[str, set[str]],
    disk: set[str],
    *,
    scripts_relative: bool = False,
    alt_col_name: str | None = None,
) -> dict:
    wb = load_workbook(path)
    ws = wb[sheet]
    headers = ensure_link_columns(ws)
    file_col = headers[file_col_name]
    alt_col = headers[alt_col_name] if alt_col_name and alt_col_name in headers else None
    listed: list[str] = []
    missing_on_disk = 0
    referenced = 0
    for r in range(2, (ws.max_row or 1) + 1):
        raw = ws.cell(r, file_col).value
        if alt_col:
            alt = ws.cell(r, alt_col).value
            if alt:
                raw = alt
        if not raw:
            continue
        rel = str(raw).replace("\\", "/").strip()
        if scripts_relative and not rel.startswith("scripts/"):
            rel = "scripts/" + rel
        listed.append(rel)
        payload = link_tuple(rel, disk, cites)
        apply_row(ws, r, headers, payload)
        if payload["Disk present"] == "NO":
            missing_on_disk += 1
        if payload["Infra-doc referenced"] == "YES":
            referenced += 1
    wb.save(path)
    wb.close()
    return {
        "workbook": path.relative_to(ROOT).as_posix(),
        "sheet": sheet,
        "listed": len(listed),
        "unique": len(set(listed)),
        "missing_on_disk": missing_on_disk,
        "infra_doc_referenced": referenced,
        "paths": listed,
    }


def write_join_book(
    disk_v1: dict[str, list[str]],
    disk_v2: dict[str, list[str]],
    disk_v3: dict[str, list[str]],
    excel_listed: dict[str, set[str]],
    cites: dict[str, set[str]],
    stats: dict,
    excluded_stats: list[tuple[str, str, int, int]],
) -> None:
    wb = Workbook()

    # Coverage
    cov = wb.active
    cov.title = "Coverage"
    cov.append(["Metric", "Value"])
    for k, v in stats.items():
        if not isinstance(v, (str, int, float)):
            continue
        cov.append([k, v])
    cov.column_dimensions["A"].width = 48
    cov.column_dimensions["B"].width = 24
    for cell in cov[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    def add_file_sheet(name: str, rows: list[tuple[str, str]]) -> None:
        ws = wb.create_sheet(name)
        headers = [
            "Tree",
            "File Name",
            "Excel listed",
            *LINK_HEADERS,
        ]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
        for tree, rel in rows:
            payload = link_tuple(rel, {rel for _, rel in rows}, cites)
            # Disk present is always YES on a disk-derived sheet; override from actual disk set below
            excel_yes = yesno(rel in excel_listed.get(tree, set()) or rel in excel_listed.get("all", set()))
            ws.append(
                [
                    tree,
                    rel,
                    excel_yes,
                    *[payload[h] for h in LINK_HEADERS],
                ]
            )
            for col in range(3, 3 + 1 + len(LINK_HEADERS)):
                hdr = (["Excel listed", *LINK_HEADERS])[col - 3]
                if hdr in {
                    "Excel listed",
                    "Disk present",
                    "Git tracked",
                    "Cited in How-Index",
                    "Cited in Topics",
                    "Cited in Architecture",
                    "Cited in INFRA",
                    "Cited in remainder inventory",
                    "Infra-doc referenced",
                    "This analysis referenced",
                }:
                    paint_yesno(ws.cell(ws.max_row, col))
        ws.auto_filter.ref = ws.dimensions
        ws.freeze_panes = "A2"
        ws.column_dimensions["A"].width = 16
        ws.column_dimensions["B"].width = 72
        for i in range(3, 14):
            ws.column_dimensions[get_column_letter(i)].width = 22

    v1_rows = [(t, rel) for t, files in disk_v1.items() for rel in files]
    v2_rows = [(t, rel) for t, files in disk_v2.items() for rel in files]
    v3_rows = [(t, rel) for t, files in disk_v3.items() for rel in files]
    add_file_sheet("GCMC_v1_disk", v1_rows)
    add_file_sheet("GCMC_v2_disk", v2_rows)
    add_file_sheet("GCMC_v3_disk", v3_rows)

    # Gaps: on disk not in excel / in excel not on disk
    gap = wb.create_sheet("Gaps")
    gap.append(["Kind", "Tree", "File Name"])
    for cell in gap[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
    disk_all = {rel for _, rel in v1_rows + v2_rows}
    listed_all = excel_listed.get("all", set())
    for rel in sorted(disk_all - listed_all):
        tree = rel.split("/", 1)[0]
        gap.append(["ON_DISK_NOT_IN_EXCEL", tree, rel])
    for rel in sorted(listed_all - disk_all):
        tree = rel.split("/", 1)[0] if "/" in rel else "?"
        gap.append(["IN_EXCEL_NOT_ON_DISK", tree, rel])
    gap.column_dimensions["A"].width = 28
    gap.column_dimensions["B"].width = 16
    gap.column_dimensions["C"].width = 72
    gap.auto_filter.ref = gap.dimensions
    gap.freeze_panes = "A2"

    # Excluded: whole-repo scratch-worktree copies deliberately not swept (0 tracked each)
    excl = wb.create_sheet("Excluded")
    excl.append(["Tree", "Reason", ".py count", "Tracked count"])
    for cell in excl[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
    for tree, reason, n, tracked in excluded_stats:
        excl.append([tree, reason, n, tracked])
    excl.column_dimensions["A"].width = 16
    excl.column_dimensions["B"].width = 48
    excl.column_dimensions["C"].width = 14
    excl.column_dimensions["D"].width = 14
    excl.auto_filter.ref = excl.dimensions
    excl.freeze_panes = "A2"

    # Room rollup
    rooms = wb.create_sheet("Stack_rooms")
    rooms.append(["LLM stack room", "LLM allowance", "Spine or sidecar", "Disk files", "Infra-doc referenced", "Not referenced"])
    for cell in rooms[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
    bucket: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for _, rel in v1_rows + v2_rows + v3_rows:
        room, allow, spine = classify(rel)
        bucket[(room, allow, spine)].append(rel)
    all_cites = set().union(*cites.values())
    for key in sorted(bucket):
        files = bucket[key]
        ref = sum(1 for f in files if f in all_cites)
        rooms.append([key[0], key[1], key[2], len(files), ref, len(files) - ref])
    for col in rooms.columns:
        rooms.column_dimensions[get_column_letter(col[0].column)].width = 28
    rooms.freeze_panes = "A2"

    # Unreferenced spine files (the linking debt)
    debt = wb.create_sheet("Unreferenced_spine")
    debt.append(["File Name", "LLM stack room", "LLM allowance"])
    for cell in debt[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
    for _, rel in v1_rows:
        room, allow, spine = classify(rel)
        if spine == "spine" and rel not in all_cites:
            debt.append([rel, room, allow])
    debt.column_dimensions["A"].width = 72
    debt.column_dimensions["B"].width = 28
    debt.column_dimensions["C"].width = 32
    debt.auto_filter.ref = debt.dimensions
    debt.freeze_panes = "A2"

    wb.save(WB_LINK)


def main() -> None:
    global TRACKED_PY
    TRACKED_PY = load_tracked_py()
    cites = load_doc_citations()
    disk_v1 = {t: walk_py(t) for t in GCMC_V1}
    disk_v2 = {t: walk_py(t) for t in GCMC_V2}
    disk_v3: dict[str, list[str]] = {t: walk_py(t) for t in GCMC_V3_DIRS}
    disk_v3["."] = walk_py_root()
    disk = set()
    for files in list(disk_v1.values()) + list(disk_v2.values()):
        disk.update(files)
    disk_v3_set = set()
    for files in disk_v3.values():
        disk_v3_set.update(files)

    excluded_stats: list[tuple[str, str, int, int]] = []
    for tree, reason in EXCLUDED_TREES.items():
        n, tracked = count_py_raw(tree)
        excluded_stats.append((tree, reason, n, tracked))

    src_stats = update_sheet(WB_SRC, "src_py_inventory", "File Name", cites, disk)
    scripts_stats = update_sheet(
        WB_SCRIPTS, "Scripts Analysis", "File Name", cites, disk, scripts_relative=True
    )
    tests_stats = update_sheet(
        WB_TESTS, "By File", "Relative Path", cites, disk, alt_col_name="Relative Path"
    )
    # Test Functionality sheet uses the same Relative Path column
    tests_fn_stats = update_sheet(
        WB_TESTS, "Test Functionality", "Relative Path", cites, disk, alt_col_name="Relative Path"
    )
    v2_stats = update_sheet(WB_V2, "gcmc_v2", "File Name", cites, disk)

    excel_listed: dict[str, set[str]] = {
        "src": set(src_stats["paths"]),
        "scripts": set(scripts_stats["paths"]),
        "tests": set(tests_stats["paths"]),
        "mt5_analytics": {p for p in v2_stats["paths"] if p.startswith("mt5_analytics/")},
        "oss_lab": {p for p in v2_stats["paths"] if p.startswith("oss_lab/")},
        "tools": {p for p in v2_stats["paths"] if p.startswith("tools/")},
    }
    excel_listed["all"] = set().union(*[excel_listed[k] for k in excel_listed if k != "all"])

    n_v1 = sum(len(v) for v in disk_v1.values())
    n_v2 = sum(len(v) for v in disk_v2.values())
    listed_v1 = excel_listed["src"] | excel_listed["scripts"] | excel_listed["tests"]
    listed_v2 = excel_listed["mt5_analytics"] | excel_listed["oss_lab"] | excel_listed["tools"]
    disk_v1_set = set().union(*disk_v1.values()) if disk_v1 else set()
    disk_v2_set = set().union(*disk_v2.values()) if disk_v2 else set()
    gcmc_v1 = 100.0 * len(listed_v1 & disk_v1_set) / n_v1 if n_v1 else 0.0
    gcmc_v2 = 100.0 * len(listed_v2 & disk_v2_set) / n_v2 if n_v2 else 0.0

    all_cites = set().union(*cites.values())
    cited_on_disk_v1 = len(disk_v1_set & all_cites)
    cited_on_disk_all = len((disk_v1_set | disk_v2_set) & all_cites)

    room_counts = Counter(classify(rel)[0] for rel in sorted(disk_v1_set | disk_v2_set | disk_v3_set))

    stats = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sweep_kind": "name_census_not_source_read",
        "disk_src": len(disk_v1["src"]),
        "disk_scripts": len(disk_v1["scripts"]),
        "disk_tests": len(disk_v1["tests"]),
        "disk_gcmc_v1": n_v1,
        "disk_mt5_analytics": len(disk_v2["mt5_analytics"]),
        "disk_oss_lab": len(disk_v2["oss_lab"]),
        "disk_tools": len(disk_v2["tools"]),
        "disk_gcmc_v2": n_v2,
        "disk_all_declared": n_v1 + n_v2,
        "disk_gcmc_v3": len(disk_v3_set),
        "disk_total_py": n_v1 + n_v2 + len(disk_v3_set),
        "tracked_total_py": len(TRACKED_PY),
        "excel_src": src_stats["unique"],
        "excel_scripts": scripts_stats["unique"],
        "excel_tests_by_file": tests_stats["unique"],
        "excel_tests_functionality": tests_fn_stats["unique"],
        "excel_gcmc_v2": v2_stats["unique"],
        "gcmc_v1_pct": round(gcmc_v1, 1),
        "gcmc_v1_listed_intersect_disk": len(listed_v1 & disk_v1_set),
        "gcmc_v1_on_disk_not_in_excel": len(disk_v1_set - listed_v1),
        "gcmc_v1_in_excel_not_on_disk": len(listed_v1 - disk_v1_set),
        "gcmc_v2_pct": round(gcmc_v2, 1),
        "gcmc_v2_listed_intersect_disk": len(listed_v2 & disk_v2_set),
        "gcmc_v2_on_disk_not_in_excel": len(disk_v2_set - listed_v2),
        "gcmc_v2_in_excel_not_on_disk": len(listed_v2 - disk_v2_set),
        "citations_how_index": len(cites["how_index"]),
        "citations_infra": len(cites["infra"]),
        "citations_topics": len(cites["topics"]),
        "citations_architecture": len(cites["architecture"]),
        "citations_remainder": len(cites.get("remainder", set())),
        "citations_union": len(all_cites),
        "disk_v1_referenced_in_infra_docs": cited_on_disk_v1,
        "disk_v1_not_referenced_in_infra_docs": n_v1 - cited_on_disk_v1,
        "disk_all_referenced_in_infra_docs": cited_on_disk_all,
        "this_analysis_referenced_v1": n_v1,
        "this_analysis_referenced_all": n_v1 + n_v2,
        "disk_v3_referenced_in_infra_docs": len(disk_v3_set & all_cites),
        "disk_v3_not_referenced_in_infra_docs": len(disk_v3_set) - len(disk_v3_set & all_cites),
        "disk_all_referenced_in_infra_docs_incl_v3": len((disk_v1_set | disk_v2_set | disk_v3_set) & all_cites),
        "this_analysis_referenced_incl_v3": n_v1 + n_v2 + len(disk_v3_set),
        "pct_of_disk": round(
            100.0 * len((disk_v1_set | disk_v2_set | disk_v3_set) & all_cites)
            / (n_v1 + n_v2 + len(disk_v3_set)),
            1,
        ) if (n_v1 + n_v2 + len(disk_v3_set)) else 0.0,
        "pct_of_tracked": round(
            100.0 * len(((disk_v1_set | disk_v2_set | disk_v3_set) & all_cites) & TRACKED_PY)
            / len((disk_v1_set | disk_v2_set | disk_v3_set) & TRACKED_PY),
            1,
        ) if len((disk_v1_set | disk_v2_set | disk_v3_set) & TRACKED_PY) else 0.0,
        "excel_rows_written_src": src_stats["listed"],
        "excel_rows_written_scripts": scripts_stats["listed"],
        "excel_rows_written_tests_by_file": tests_stats["listed"],
        "excel_rows_written_tests_functionality": tests_fn_stats["listed"],
        "excel_rows_written_gcmc_v2": v2_stats["listed"],
        "excel_rows_written_note": "sheet ROWS updated by this pass, not file counts (Test Functionality has multiple rows per file)",
        "excluded_counts": {tree: {"reason": reason, "py_count": n, "tracked_count": tr} for tree, reason, n, tr in excluded_stats},
        "room_counts": dict(room_counts),
    }

    write_join_book(disk_v1, disk_v2, disk_v3, excel_listed, cites, stats, excluded_stats)
    REPORT_JSON.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    print(f"wrote {WB_LINK.relative_to(ROOT).as_posix()}")
    print(f"wrote {REPORT_JSON.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
