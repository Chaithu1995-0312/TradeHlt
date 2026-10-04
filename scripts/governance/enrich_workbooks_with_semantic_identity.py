#!/usr/bin/env python3
"""enrich_workbooks_with_semantic_identity.py — append Semantic File Identity columns to the
three existing business-functionality workbooks. Additive only: never renames a file, never
touches columns A-C (A-F on the tests workbook), never reorders or inserts columns.

Reads the GENERATED projection ``data/semantic_os/file_identities.jsonl`` (produced by
``scripts/governance/seed_semantic_os.py``) — run that first. This script fails loudly if the
projection is absent rather than silently degrading to an empty join: a workbook full of blank
Semantic ID cells must read as "coverage not measured", never as "coverage measured at zero".

Workbooks touched:
  1. scripts_business_functionality.xlsx / "Scripts Analysis" (+ "Counts")
  2. results/analysis/src_business_functionality.xlsx / "src_py_inventory"
  3. docs/analysis/tests_functionality_inventory.xlsx / "Test Functionality" + "By File" (+ "README")

Workbooks 1/2 get a direct join (this file's own identity): Semantic ID / Semantic Name /
Filename Semantic Status / Identity Tier / Identity Provenance.

Workbook 3 (tests) gets NO own identity column (test files are out of scope for identities by
design — see docs/governance/SEMANTIC_FILE_IDENTITY_REPORT.md decision 3). Instead it gets a
"Covers Semantic ID" column derived from its existing "Referred files" column, turning the tests
workbook into a coverage map of which semantic identities are exercised by which tests.

Idempotent: re-running looks up each header by name and reuses its column if present, so
running twice does not duplicate columns or grow the sheet.

Usage:
    python scripts/governance/enrich_workbooks_with_semantic_identity.py
    python scripts/governance/enrich_workbooks_with_semantic_identity.py --workbook src
    python scripts/governance/enrich_workbooks_with_semantic_identity.py --check --json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import openpyxl
    from openpyxl.utils import get_column_letter
except ImportError:
    print("openpyxl required", file=sys.stderr)
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console guard

_ROOT = Path(__file__).resolve().parents[2]
_PROJECTION_DEFAULT = _ROOT / "data" / "semantic_os"

_WB_SCRIPTS = _ROOT / "scripts_business_functionality.xlsx"
_WB_SRC = _ROOT / "results" / "analysis" / "src_business_functionality.xlsx"
_WB_TESTS = _ROOT / "docs" / "analysis" / "tests_functionality_inventory.xlsx"

_IDENTITY_HEADERS = (
    "Semantic ID", "Semantic Name", "Filename Semantic Status", "Identity Tier", "Identity Provenance",
)
_COVERS_HEADERS = (
    "Covers Semantic ID", "Covers Semantic Name", "Covers Filename Status", "Coverage Join Method",
)

_HEADER_FILL_BLUE = "1F4E79"


# ── projection load ─────────────────────────────────────────────────────────────────────────

def load_identity_by_path(projection_dir: Path) -> dict[str, dict]:
    """``physical_path -> canonical file_identity record``, read from the GENERATED projection."""
    path = projection_dir / "file_identities.jsonl"
    if not path.is_file():
        raise SystemExit(
            f"ERROR: {path.relative_to(_ROOT).as_posix()} not found. Run "
            "`python scripts/governance/seed_semantic_os.py` first — this script never degrades "
            "to an empty join (a blank Semantic ID column would misread as zero coverage rather "
            "than 'not measured')."
        )
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if record.get("canonical") is True and record.get("physical_path"):
            out[record["physical_path"]] = record
    return out


# ── join helpers ────────────────────────────────────────────────────────────────────────────

def _scripts_join_key(raw: str) -> str:
    """Mirrors grok/book_file_coverage_report.py:149-153 exactly, so both consumers agree."""
    name = (raw or "").replace("\\", "/")
    if not name.startswith("scripts/"):
        name = "scripts/" + name.lstrip("/")
    return name


def _src_join_key(raw: str) -> str:
    return (raw or "").replace("\\", "/")


_REFERRED_EMPTY_SENTINELS = frozenset({
    "", "(no project file imports)", "(none / stdlib-only)", "(parse failed — imports unavailable)",
})


def covers_from_referred(referred: Optional[str], identity_by_path: dict[str, dict]) -> tuple[list[dict], str]:
    """Derive (matched identity records, join-method label) from a 'Referred files' cell.

    A raw import token is NOT proof a file exists — test_functionality_excel.py emits a
    best-effort path even for imports that resolve to nothing on disk (see its
    ``_resolve_module_to_file`` docstring). Collapsing a miss into a blank cell would silently
    overstate coverage, so misses are counted and surfaced in the method label, never hidden.
    """
    text = (referred or "").strip()
    if text in _REFERRED_EMPTY_SENTINELS:
        return [], "NONE"
    tokens = [t.strip().replace("\\", "/") for t in text.split(";")]
    candidates = [t for t in tokens if t.endswith(".py") and not t.startswith("tests/")]
    if not candidates:
        return [], "NONE"
    hits: dict[str, dict] = {}
    misses = 0
    for token in candidates:
        record = identity_by_path.get(token)
        if record:
            hits[record["id"]] = record
        else:
            misses += 1
    if not hits:
        return [], f"UNRESOLVED:{misses}"
    ordered = sorted(hits.values(), key=lambda r: r["id"])
    method = "IMPORT_PATH_EXACT" if misses == 0 else f"IMPORT_PATH_PARTIAL:{misses}"
    return ordered, method


# ── sheet-level column append (idempotent) ─────────────────────────────────────────────────

def _header_columns(ws) -> dict[str, int]:
    return {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(1, c).value}


def _ensure_columns(ws, headers: tuple[str, ...]) -> dict[str, int]:
    """Return {header: column_index}, reusing an existing column by name or appending one."""
    existing = _header_columns(ws)
    out: dict[str, int] = {}
    next_col = ws.max_column + 1
    header_style_src = ws.cell(1, 1)
    for header in headers:
        if header in existing:
            out[header] = existing[header]
            continue
        col = next_col
        next_col += 1
        cell = ws.cell(1, col, header)
        cell.fill = copy.copy(header_style_src.fill)
        cell.font = copy.copy(header_style_src.font)
        cell.alignment = copy.copy(header_style_src.alignment)
        out[header] = col
    return out


def _set_widths(ws, widths: dict[str, int]) -> None:
    for letter, w in widths.items():
        ws.column_dimensions[letter].width = w


def _refresh_autofilter(ws) -> None:
    ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"


def _write_row_style(ws, row_idx: int, col: int, value: Any) -> None:
    cell = ws.cell(row_idx, col, value)
    style_src = ws.cell(row_idx, 1)
    cell.alignment = copy.copy(style_src.alignment)
    cell.border = copy.copy(style_src.border)
    cell.fill = copy.copy(style_src.fill)


# ── per-workbook enrichers ──────────────────────────────────────────────────────────────────

def enrich_scripts_workbook(path: Path, identity_by_path: dict[str, dict]) -> dict:
    wb = openpyxl.load_workbook(path)
    ws = wb["Scripts Analysis"]
    cols = _ensure_columns(ws, _IDENTITY_HEADERS)

    joined = 0
    total = 0
    for r in range(2, ws.max_row + 1):
        raw = ws.cell(r, 1).value
        if raw is None or str(raw).strip() == "":
            continue
        total += 1
        key = _scripts_join_key(str(raw))
        record = identity_by_path.get(key)
        if record:
            joined += 1
        _write_row_style(ws, r, cols["Semantic ID"], record["id"] if record else None)
        _write_row_style(ws, r, cols["Semantic Name"], record["semantic_name"] if record else None)
        _write_row_style(ws, r, cols["Filename Semantic Status"], record["filename_semantic_status"] if record else None)
        _write_row_style(ws, r, cols["Identity Tier"], record["tier"] if record else None)
        _write_row_style(ws, r, cols["Identity Provenance"], record["provenance"] if record else None)

    _set_widths(ws, {
        get_column_letter(cols["Semantic ID"]): 34,
        get_column_letter(cols["Semantic Name"]): 34,
        get_column_letter(cols["Filename Semantic Status"]): 24,
        get_column_letter(cols["Identity Tier"]): 12,
        get_column_letter(cols["Identity Provenance"]): 16,
    })
    _refresh_autofilter(ws)

    ws2 = wb["Counts"]
    _append_count_row(ws2, "Rows joined to a semantic identity", joined)
    _append_count_row(ws2, "Rows unjoined", total - joined)
    _append_count_row(
        ws2, "Tier-1 curated rows in this sheet",
        sum(1 for r in range(2, ws.max_row + 1) if ws.cell(r, cols["Identity Tier"]).value == 1),
    )

    wb.save(path)
    return {"total": total, "joined": joined, "join_rate": (joined / total) if total else 0.0}


def _append_count_row(ws, label: str, value: Any) -> None:
    existing_labels = {ws.cell(r, 1).value for r in range(2, ws.max_row + 1)}
    if label in existing_labels:
        for r in range(2, ws.max_row + 1):
            if ws.cell(r, 1).value == label:
                ws.cell(r, 2, value)
                return
        return
    ws.append([label, value])


#: Sheets of the src workbook that carry declared file identities, so may be enriched.
#: ``tools_py_inventory`` / ``exec_telemetry_py_inventory`` are deliberately ABSENT: the
#: Semantic OS declares no identities for those trees, and a blank Semantic ID column would
#: read as "coverage measured at zero" rather than "coverage not measured".
_SRC_WORKBOOK_SHEETS = ("src_py_inventory", "root_py_inventory")


def _enrich_identity_sheet(ws, identity_by_path: dict[str, dict]) -> dict:
    """Append the five identity columns to one path-keyed sheet. Idempotent."""
    cols = _ensure_columns(ws, _IDENTITY_HEADERS)

    joined = 0
    total = 0
    for r in range(2, ws.max_row + 1):
        raw = ws.cell(r, 1).value
        if raw is None or str(raw).strip() == "":
            continue
        total += 1
        key = _src_join_key(str(raw))
        record = identity_by_path.get(key)
        if record:
            joined += 1
        _write_row_style(ws, r, cols["Semantic ID"], record["id"] if record else None)
        _write_row_style(ws, r, cols["Semantic Name"], record["semantic_name"] if record else None)
        _write_row_style(ws, r, cols["Filename Semantic Status"], record["filename_semantic_status"] if record else None)
        _write_row_style(ws, r, cols["Identity Tier"], record["tier"] if record else None)
        _write_row_style(ws, r, cols["Identity Provenance"], record["provenance"] if record else None)

    _set_widths(ws, {
        get_column_letter(cols["Semantic ID"]): 34,
        get_column_letter(cols["Semantic Name"]): 34,
        get_column_letter(cols["Filename Semantic Status"]): 24,
        get_column_letter(cols["Identity Tier"]): 12,
        get_column_letter(cols["Identity Provenance"]): 16,
    })
    _refresh_autofilter(ws)
    return {"total": total, "joined": joined, "join_rate": (joined / total) if total else 0.0}


def enrich_src_workbook(path: Path, identity_by_path: dict[str, dict]) -> dict:
    wb = openpyxl.load_workbook(path)
    per_sheet = {
        name: _enrich_identity_sheet(wb[name], identity_by_path)
        for name in _SRC_WORKBOOK_SHEETS
        if name in wb.sheetnames
    }
    wb.save(path)

    total = sum(v["total"] for v in per_sheet.values())
    joined = sum(v["joined"] for v in per_sheet.values())
    return {
        "total": total,
        "joined": joined,
        "join_rate": (joined / total) if total else 0.0,
        "sheets": per_sheet,
    }


_TESTS_README_LINES = (
    "Covers Semantic ID: joined from Referred files against data/semantic_os/file_identities.jsonl (semantic_os/1.1)",
    "Coverage Join Method: IMPORT_PATH_EXACT | IMPORT_PATH_PARTIAL:n | UNRESOLVED:n | NONE",
)


def _enrich_tests_sheet(ws, referred_col: int, identity_by_path: dict[str, dict]) -> dict:
    cols = _ensure_columns(ws, _COVERS_HEADERS)
    rows_with_coverage = 0
    total = 0
    for r in range(2, ws.max_row + 1):
        raw = ws.cell(r, referred_col).value
        if ws.cell(r, 1).value is None:
            continue
        total += 1
        matches, method = covers_from_referred(raw, identity_by_path)
        if matches:
            rows_with_coverage += 1
        _write_row_style(ws, r, cols["Covers Semantic ID"], "; ".join(m["id"] for m in matches) or None)
        _write_row_style(ws, r, cols["Covers Semantic Name"], "; ".join(m["semantic_name"] for m in matches) or None)
        _write_row_style(ws, r, cols["Covers Filename Status"], "; ".join(m["filename_semantic_status"] for m in matches) or None)
        _write_row_style(ws, r, cols["Coverage Join Method"], method)

    _set_widths(ws, {
        get_column_letter(cols["Covers Semantic ID"]): 55,
        get_column_letter(cols["Covers Semantic Name"]): 55,
        get_column_letter(cols["Covers Filename Status"]): 30,
        get_column_letter(cols["Coverage Join Method"]): 22,
    })
    _refresh_autofilter(ws)
    return {"total": total, "rows_with_coverage": rows_with_coverage}


def enrich_tests_workbook(path: Path, identity_by_path: dict[str, dict]) -> dict:
    wb = openpyxl.load_workbook(path)
    result = {}
    for sheet_name in ("Test Functionality", "By File"):
        ws = wb[sheet_name]
        headers = _header_columns(ws)
        assert "Semantic ID" not in headers, (
            f"{sheet_name}: test files must never get their own Semantic ID column (decision 3) "
            "— only a Covers Semantic ID pointer."
        )
        referred_col = headers["Referred files"]
        result[sheet_name] = _enrich_tests_sheet(ws, referred_col, identity_by_path)

    ws3 = wb["README"]
    existing = {ws3.cell(r, 1).value for r in range(1, ws3.max_row + 1)}
    for line in _TESTS_README_LINES:
        if line not in existing:
            ws3.append([line])

    wb.save(path)
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────────────────────

_WORKBOOKS = {
    "scripts": (_WB_SCRIPTS, enrich_scripts_workbook),
    "src": (_WB_SRC, enrich_src_workbook),
    "tests": (_WB_TESTS, enrich_tests_workbook),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", default="all", choices=("scripts", "src", "tests", "all"))
    parser.add_argument("--projection", default=str(_PROJECTION_DEFAULT))
    parser.add_argument("--check", action="store_true", help="dry run: report join rates, write nothing")
    parser.add_argument("--min-join-rate", type=float, default=0.98)
    parser.add_argument("--json", action="store_true", help="machine-readable summary to stdout")
    args = parser.parse_args(argv)

    identity_by_path = load_identity_by_path(Path(args.projection))

    targets = list(_WORKBOOKS.items()) if args.workbook == "all" else [(args.workbook, _WORKBOOKS[args.workbook])]

    summary: dict[str, Any] = {}
    floor_breached = False
    for name, (path, fn) in targets:
        if not path.is_file():
            summary[name] = {"skipped": "workbook not found (untracked/disposable artifact)"}
            continue
        if args.check:
            # --check must not mutate the real workbook: operate on an in-memory copy by loading
            # normally (openpyxl load is read-into-memory) and simply never calling wb.save.
            wb = openpyxl.load_workbook(path)
            wb.close()
            # Re-run the real enrich function against a throwaway temp copy so --check exercises
            # the identical join logic without touching the tracked file.
            import shutil
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp) / path.name
                shutil.copy(path, tmp_path)
                result = fn(tmp_path, identity_by_path)
        else:
            result = fn(path, identity_by_path)
        summary[name] = result
        rate = result.get("join_rate")
        if rate is not None and rate < args.min_join_rate:
            floor_breached = True

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        mode = "CHECK (no files written)" if args.check else "ENRICHED"
        print(f"SEMANTIC IDENTITY WORKBOOK ENRICHMENT: {mode}")
        for name, result in summary.items():
            print(f"  {name}: {result}")

    return 1 if floor_breached else 0


if __name__ == "__main__":
    raise SystemExit(main())
