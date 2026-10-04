#!/usr/bin/env python3
"""Compare docs/book citations vs src/scripts functionality Excel inventories."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO = Path(r"D:\Tradelatest")
BOOK = REPO / "docs" / "book"
OUT = REPO / "grok" / "Book_PDF_File_Coverage_Grok.xlsx"

BOOK_DORMANT_HINTS = {
    "cognitive",
    "strategies",
    "scanner",
    "feedback",
    "llm_research",
    "monitoring",
    "journal",
    "data_ingestion",
    "uat",
    "ui",
}
BOOK_SIDECAR_HINTS = {
    "expansion",
    "replay",
    "portfolio",
    "regime",
    "retrieval",
    "msip",
    "analytics",
    "events",
    "validation_access",
    "search",
    "logs",
    "utils",
    "bitnet",
    "training",
    "multi_llm",
}

CITE_RE = re.compile(
    r"`("
    r"(?:src|scripts|docs|configs|tests|models|multi_llm|archive|results)"
    r"/[A-Za-z0-9_./\-]+(?:\.[A-Za-z0-9_]+)?"
    r"|[A-Za-z0-9_./\-]+\.(?:py|md|json|yaml|yml|jsonl|dot)"
    r"|active_models\.yaml|CLAUDE\.md|assistant_project\.md"
    r")`"
)
PLAIN_RE = re.compile(
    r"(?<![A-Za-z0-9_/])"
    r"((?:src|scripts|docs|configs|tests|models|multi_llm|archive|results)"
    r"/[A-Za-z0-9_./\-]+(?:\.[A-Za-z0-9_]+)?)"
)


def normalize(p: str) -> str:
    p = p.strip().strip("`").replace("\\", "/")
    p = re.sub(r":\d+(?:-\d+)?$", "", p)
    p = p.rstrip(").,;]")
    if "*" in p:
        p = p.split("*")[0].rstrip("/")
    return p


def extract_citations() -> dict[str, set[str]]:
    cites: dict[str, set[str]] = defaultdict(set)
    for md in sorted(BOOK.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        found = set()
        for m in CITE_RE.finditer(text):
            found.add(normalize(m.group(1)))
        for m in PLAIN_RE.finditer(text):
            found.add(normalize(m.group(1)))
        for p in found:
            if not p or p.startswith("#"):
                continue
            cites[p].add(md.name)
    return cites


def expand_to_files(cites: dict[str, set[str]]) -> dict[str, set[str]]:
    file_cites: dict[str, set[str]] = defaultdict(set)
    for path, chapters in cites.items():
        full = REPO / path
        if full.is_file():
            file_cites[path.replace("\\", "/")].update(chapters)
        elif full.is_dir():
            file_cites[path.rstrip("/") + "/"].update(chapters)
            # Only expand src package directories into oriented children
            if path.startswith("src/") and path.count("/") >= 1:
                for child in full.rglob("*"):
                    if child.is_file() and child.suffix.lower() in {
                        ".py",
                        ".md",
                        ".json",
                        ".yaml",
                        ".yml",
                        ".jsonl",
                        ".toml",
                    }:
                        rel = child.relative_to(REPO).as_posix()
                        file_cites[rel].update({f"{ch} [dir-orient]" for ch in chapters})
        else:
            hit = False
            for ext in (".py", ".md", ".json", ".yaml", ".yml"):
                c = REPO / f"{path}{ext}"
                if c.is_file():
                    file_cites[c.relative_to(REPO).as_posix()].update(chapters)
                    hit = True
            if not hit:
                file_cites[path].update(chapters)
    return file_cites


def load_src_inventory():
    p = REPO / "results" / "analysis" / "src_business_functionality.xlsx"
    if not p.exists():
        p = REPO / "src_business_functionality.xlsx"
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        name = (row[0] or "").replace("\\", "/")
        if not name:
            continue
        if not name.startswith("src/"):
            name = "src/" + name.lstrip("/")
        rows.append({"file": name, "summary": row[1] or "", "referred": row[2] or ""})
    wb.close()
    return rows


def load_scripts_inventory():
    p = REPO / "scripts_business_functionality.xlsx"
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    ws = wb["Scripts Analysis"]
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        name = (row[0] or "").replace("\\", "/")
        if not name:
            continue
        if not name.startswith("scripts/"):
            name = "scripts/" + name.lstrip("/")
        rows.append({"file": name, "summary": row[1] or "", "referred": row[2] or ""})
    wb.close()
    return rows


def package_of(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 2:
        return parts[1]
    return parts[0]


def coverage_status(
    file_path: str,
    file_cites: dict[str, set[str]],
    raw_cites: dict[str, set[str]],
) -> tuple[str, str, str]:
    fp = file_path.replace("\\", "/")

    # Exact path cited in book text (wins over directory orientation)
    if fp in raw_cites:
        return "CITED", "exact_path_in_book", "; ".join(sorted(raw_cites[fp]))

    # Bare filename / path without src/ prefix sometimes appears in backticks
    stem = Path(fp).name
    for k, chs in raw_cites.items():
        if k == stem or k.endswith("/" + stem):
            # only treat as exact if k points to this same relative path or unique stem hit
            if k == fp or k.endswith("/" + stem):
                # prefer full relative match
                if k == fp or k.replace("\\", "/") == fp:
                    return "CITED", "exact_path_in_book", "; ".join(sorted(chs))
                if k == stem:
                    return "NAME_MATCH", k, "; ".join(sorted(chs))

    if fp in file_cites:
        chs = file_cites[fp]
        exactish = {c for c in chs if "[dir-orient]" not in c}
        if exactish:
            return "CITED", "resolved_from_citation", "; ".join(sorted(exactish))
        return "DIR_ORIENTED", "package_directory_cited", "; ".join(sorted(chs))

    parts = fp.split("/")
    for i in range(len(parts) - 1, 0, -1):
        parent = "/".join(parts[:i])
        parent_slash = parent + "/"
        chs = set()
        if parent in raw_cites:
            chs = raw_cites[parent]
        elif parent_slash in file_cites:
            chs = file_cites[parent_slash]
        elif parent in file_cites:
            chs = file_cites[parent]
        if chs:
            return "PARENT_CITED", f"parent:{parent}", "; ".join(sorted(chs))

    return "NOT_IN_BOOK", "", ""


def dormancy_guess(file_path: str, status: str) -> str:
    fp = file_path.replace("\\", "/")
    pkg = package_of(fp)
    if fp.startswith("archive/") or "ARCHIVED" in fp:
        return "ARCHIVED"
    if pkg in BOOK_DORMANT_HINTS:
        return "LIKELY_DORMANT_PER_BOOK"
    if pkg in BOOK_SIDECAR_HINTS:
        return "SIDECAR_OR_SUPPORTING"
    if status == "CITED":
        return "BOOK_COVERED_READ_PATH"
    if status in {"DIR_ORIENTED", "PARENT_CITED", "NAME_MATCH"}:
        return "PACKAGE_MENTIONED_NOT_FILE_DEPTH"
    if status == "NOT_IN_BOOK":
        if fp.startswith("src/") and pkg in {
            "core",
            "engines",
            "features",
            "config_layer",
            "runtime",
            "governance",
            "agent",
            "control_plane",
            "inout",
            "execution",
            "live",
        }:
            return "SPINE_AREA_BUT_FILE_NOT_CITED"
        return "NOT_COVERED_ASSUME_UNREAD"
    return "UNKNOWN"


def classify_inventory(rows, kind, file_cites, raw):
    out = []
    counts: dict[str, int] = defaultdict(int)
    dorm_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        status, match, chapters = coverage_status(r["file"], file_cites, raw)
        dorm = dormancy_guess(r["file"], status)
        counts[status] += 1
        dorm_counts[dorm] += 1
        out.append(
            {
                **r,
                "inventory": kind,
                "package": package_of(r["file"]),
                "book_status": status,
                "match_type": match,
                "chapters": chapters,
                "dormancy_hint": dorm,
            }
        )
    return out, counts, dorm_counts


def style_header(ws, n):
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(color="FFFFFF", bold=True)
    for c in range(1, n + 1):
        cell = ws.cell(1, c)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="center")


def autosize(ws, max_width=48):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        m = 0
        for cell in col[:100]:
            m = max(m, len(str(cell.value or "")))
        ws.column_dimensions[letter].width = min(max(m + 2, 10), max_width)


def main() -> int:
    raw = extract_citations()
    file_cites = expand_to_files(raw)
    src_rows = load_src_inventory()
    script_rows = load_scripts_inventory()

    src_class, src_counts, src_dorm = classify_inventory(src_rows, "src", file_cites, raw)
    scr_class, scr_counts, scr_dorm = classify_inventory(
        script_rows, "scripts", file_cites, raw
    )
    all_class = src_class + scr_class

    pkg: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "cited": 0, "dir_or_parent": 0, "not_in_book": 0}
    )
    for r in src_class:
        p = r["package"]
        pkg[p]["total"] += 1
        if r["book_status"] == "CITED":
            pkg[p]["cited"] += 1
        elif r["book_status"] in {"DIR_ORIENTED", "PARENT_CITED", "NAME_MATCH"}:
            pkg[p]["dir_or_parent"] += 1
        else:
            pkg[p]["not_in_book"] += 1

    n_raw = len(raw)
    n_resolved_files = sum(1 for k in file_cites if (REPO / k).is_file())
    n_dirs = sum(
        1
        for k in file_cites
        if k.endswith("/") or (REPO / k.rstrip("/")).is_dir()
    )

    wb = openpyxl.Workbook()
    green = PatternFill("solid", fgColor="C6EFCE")
    yellow = PatternFill("solid", fgColor="FFEB9C")
    red = PatternFill("solid", fgColor="FFC7CE")
    thin = Border(
        left=Side(style="thin", color="B0B0B0"),
        right=Side(style="thin", color="B0B0B0"),
        top=Side(style="thin", color="B0B0B0"),
        bottom=Side(style="thin", color="B0B0B0"),
    )

    ws = wb.active
    ws.title = "Summary"
    summary_rows = [
        ("Metric", "Value", "How to use"),
        (
            "Book source chapters (docs/book/*.md)",
            len(list(BOOK.glob("*.md"))),
            "PDF is export of these markdown files",
        ),
        ("Unique path strings cited in book", n_raw, "Files, dirs, configs, docs"),
        ("Resolved to real files on disk", n_resolved_files, "Citation exists as a file"),
        (
            "Directory-level citations",
            n_dirs,
            "Package/dir mentioned -> children DIR_ORIENTED",
        ),
        ("", "", ""),
        (
            "SRC inventory total (Excel)",
            len(src_rows),
            "results/analysis/src_business_functionality.xlsx",
        ),
        (
            "SRC CITED exact file in book",
            src_counts.get("CITED", 0),
            "Safe to treat as book-covered",
        ),
        (
            "SRC DIR_ORIENTED / PARENT / NAME",
            src_counts.get("DIR_ORIENTED", 0)
            + src_counts.get("PARENT_CITED", 0)
            + src_counts.get("NAME_MATCH", 0),
            "Package mentioned; individual file may be unread",
        ),
        (
            "SRC NOT_IN_BOOK",
            src_counts.get("NOT_IN_BOOK", 0),
            "Assume unread by book; may still be live code",
        ),
        (
            "SRC coverage % (CITED only)",
            f"{100 * src_counts.get('CITED', 0) / max(len(src_rows), 1):.1f}%",
            "Strict file-level coverage",
        ),
        (
            "SRC coverage % (CITED+parent/dir)",
            f"{100 * (len(src_rows) - src_counts.get('NOT_IN_BOOK', 0)) / max(len(src_rows), 1):.1f}%",
            "Loose package-level coverage",
        ),
        ("", "", ""),
        (
            "SCRIPTS inventory total (Excel)",
            len(script_rows),
            "scripts_business_functionality.xlsx",
        ),
        ("SCRIPTS CITED", scr_counts.get("CITED", 0), ""),
        (
            "SCRIPTS DIR/PARENT/NAME",
            scr_counts.get("DIR_ORIENTED", 0)
            + scr_counts.get("PARENT_CITED", 0)
            + scr_counts.get("NAME_MATCH", 0),
            "",
        ),
        (
            "SCRIPTS NOT_IN_BOOK",
            scr_counts.get("NOT_IN_BOOK", 0),
            "Most scripts are operational; book rarely cites each",
        ),
        (
            "SCRIPTS coverage % (CITED only)",
            f"{100 * scr_counts.get('CITED', 0) / max(len(script_rows), 1):.1f}%",
            "",
        ),
        ("", "", ""),
        ("INTERPRETATION (src dormancy_hint counts)", "", ""),
        (
            "BOOK_COVERED_READ_PATH",
            src_dorm.get("BOOK_COVERED_READ_PATH", 0),
            "Cited; book path of understanding",
        ),
        (
            "PACKAGE_MENTIONED_NOT_FILE_DEPTH",
            src_dorm.get("PACKAGE_MENTIONED_NOT_FILE_DEPTH", 0),
            "Do not assume file was deep-read",
        ),
        (
            "LIKELY_DORMANT_PER_BOOK",
            src_dorm.get("LIKELY_DORMANT_PER_BOOK", 0),
            "Book labels package dormant/sidecar",
        ),
        (
            "SIDECAR_OR_SUPPORTING",
            src_dorm.get("SIDECAR_OR_SUPPORTING", 0),
            "Supporting; not main candle->order spine",
        ),
        (
            "SPINE_AREA_BUT_FILE_NOT_CITED",
            src_dorm.get("SPINE_AREA_BUT_FILE_NOT_CITED", 0),
            "Live area, but this file not in book",
        ),
        (
            "NOT_COVERED_ASSUME_UNREAD",
            src_dorm.get("NOT_COVERED_ASSUME_UNREAD", 0),
            "Safe default: not covered by PDF",
        ),
        ("ARCHIVED", src_dorm.get("ARCHIVED", 0), "Under archive/"),
        ("", "", ""),
        (
            "Rule of thumb",
            "NOT_IN_BOOK != dead code",
            "Use dormancy_hint + package map; code wins",
        ),
        (
            "Rule of thumb 2",
            "CITED != exhaustively verified",
            "Book is a map; many cites are pointers",
        ),
    ]
    for r in summary_rows:
        ws.append(list(r))
    style_header(ws, 3)
    autosize(ws, 60)

    ws2 = wb.create_sheet("Src_Package_Coverage")
    ws2.append(
        [
            "package",
            "total_files",
            "cited_exact",
            "dir_or_parent",
            "not_in_book",
            "cited_pct",
            "loose_cover_pct",
            "dormancy_hint",
            "assume",
        ]
    )
    for p, d in sorted(pkg.items(), key=lambda x: (-x[1]["total"], x[0])):
        total = d["total"]
        cited = d["cited"]
        loose = cited + d["dir_or_parent"]
        if p in BOOK_DORMANT_HINTS:
            dorm = "LIKELY_DORMANT_PER_BOOK"
            assume = "Can deprioritize deep-read unless reopening"
        elif p in BOOK_SIDECAR_HINTS:
            dorm = "SIDECAR_OR_SUPPORTING"
            assume = "Read only when task touches package"
        elif cited / max(total, 1) >= 0.15 or loose / max(total, 1) >= 0.5:
            dorm = "BOOK_ENGAGED"
            assume = "Part of book narrative; still may have unread files"
        else:
            dorm = "MOSTLY_UNREAD_IN_BOOK"
            assume = "Assume unread unless you need it"
        ws2.append(
            [
                p,
                total,
                cited,
                d["dir_or_parent"],
                d["not_in_book"],
                round(100 * cited / max(total, 1), 1),
                round(100 * loose / max(total, 1), 1),
                dorm,
                assume,
            ]
        )
    style_header(ws2, 9)
    autosize(ws2, 40)

    ws3 = wb.create_sheet("File_Coverage_All")
    headers = [
        "inventory",
        "file",
        "package",
        "book_status",
        "dormancy_hint",
        "match_type",
        "chapters",
        "summary",
        "referred_files",
    ]
    ws3.append(headers)
    for r in sorted(
        all_class, key=lambda x: (x["inventory"], x["book_status"] != "CITED", x["file"])
    ):
        ws3.append(
            [
                r["inventory"],
                r["file"],
                r["package"],
                r["book_status"],
                r["dormancy_hint"],
                r["match_type"],
                r["chapters"],
                (r["summary"] or "")[:300],
                (r["referred"] or "")[:200],
            ]
        )
    style_header(ws3, len(headers))
    for row in range(2, ws3.max_row + 1):
        val = ws3.cell(row, 4).value
        if val == "CITED":
            fill = green
        elif val in {"DIR_ORIENTED", "PARENT_CITED", "NAME_MATCH"}:
            fill = yellow
        else:
            fill = red
        ws3.cell(row, 4).fill = fill
        for c in range(1, len(headers) + 1):
            ws3.cell(row, c).border = thin
            ws3.cell(row, c).alignment = Alignment(wrap_text=True, vertical="top")
    autosize(ws3, 36)
    ws3.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws3.max_row}"
    ws3.freeze_panes = "A2"

    ws4 = wb.create_sheet("NOT_IN_BOOK_Src")
    ws4.append(["file", "package", "dormancy_hint", "summary"])
    for r in sorted(src_class, key=lambda x: (x["package"], x["file"])):
        if r["book_status"] == "NOT_IN_BOOK":
            ws4.append(
                [r["file"], r["package"], r["dormancy_hint"], (r["summary"] or "")[:240]]
            )
    style_header(ws4, 4)
    autosize(ws4, 50)
    ws4.auto_filter.ref = f"A1:D{ws4.max_row}"
    ws4.freeze_panes = "A2"

    ws5 = wb.create_sheet("CITED_Src")
    ws5.append(["file", "package", "chapters", "summary"])
    for r in sorted(src_class, key=lambda x: x["file"]):
        if r["book_status"] == "CITED":
            ws5.append(
                [r["file"], r["package"], r["chapters"], (r["summary"] or "")[:240]]
            )
    style_header(ws5, 4)
    autosize(ws5, 50)
    ws5.auto_filter.ref = f"A1:D{ws5.max_row}"
    ws5.freeze_panes = "A2"

    ws6 = wb.create_sheet("Book_Citations_Raw")
    ws6.append(["cited_path", "exists", "type", "chapters"])
    for path in sorted(raw.keys()):
        full = REPO / path
        if full.is_file():
            typ, exists = "file", "Y"
        elif full.is_dir() or path.endswith("/"):
            typ = "dir"
            exists = "Y" if (full.is_dir() or (REPO / path.rstrip("/")).is_dir()) else "N"
        else:
            typ = "unresolved"
            exists = (
                "Y"
                if any(
                    (REPO / f"{path}{ext}").is_file()
                    for ext in (".py", ".md", ".json", ".yaml")
                )
                else "N"
            )
        ws6.append([path, exists, typ, "; ".join(sorted(raw[path]))])
    style_header(ws6, 4)
    autosize(ws6, 50)
    ws6.auto_filter.ref = f"A1:D{ws6.max_row}"
    ws6.freeze_panes = "A2"

    ws7 = wb.create_sheet("Legend")
    for row in [
        ("Field", "Meaning"),
        ("CITED", "Book names this file. PDF covers it as a pointer/map entry."),
        (
            "DIR_ORIENTED",
            "Book cites package/directory; children oriented, not deep-read.",
        ),
        ("PARENT_CITED", "A parent path of this file was cited."),
        ("NAME_MATCH", "Filename matched a citation path (weaker)."),
        (
            "NOT_IN_BOOK",
            "No citation. Safe to assume the PDF did not cover this file.",
        ),
        (
            "LIKELY_DORMANT_PER_BOOK",
            "Book lists package as DORMANT / off live decision path.",
        ),
        ("SIDECAR_OR_SUPPORTING", "Supporting/research/shadow — not primary spine."),
        (
            "SPINE_AREA_BUT_FILE_NOT_CITED",
            "In core packages but this file never mentioned — may still be live.",
        ),
        (
            "NOT_COVERED_ASSUME_UNREAD",
            "Default: treat as unread for book purposes.",
        ),
        (
            "Important",
            "NOT_IN_BOOK does NOT mean code is dead. It means the book did not cover it.",
        ),
        (
            "Important",
            "CITED does NOT mean every line was verified. Book is a map; code wins.",
        ),
        (
            "Inventories used",
            "results/analysis/src_business_functionality.xlsx + scripts_business_functionality.xlsx",
        ),
        ("Book source", "docs/book/*.md (source of *Grok.pdf exports)"),
    ]:
        ws7.append(list(row))
    style_header(ws7, 2)
    autosize(ws7, 80)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)

    print("WROTE", OUT)
    print(
        "SRC total",
        len(src_rows),
        "CITED",
        src_counts.get("CITED", 0),
        "DIR/PARENT/NAME",
        src_counts.get("DIR_ORIENTED", 0)
        + src_counts.get("PARENT_CITED", 0)
        + src_counts.get("NAME_MATCH", 0),
        "NOT_IN_BOOK",
        src_counts.get("NOT_IN_BOOK", 0),
    )
    print(
        "SCRIPTS total",
        len(script_rows),
        "CITED",
        scr_counts.get("CITED", 0),
        "NOT_IN_BOOK",
        scr_counts.get("NOT_IN_BOOK", 0),
    )
    print("Raw citations", n_raw, "resolved files", n_resolved_files, "dirs", n_dirs)
    print("\nTop packages by NOT_IN_BOOK:")
    for p, d in sorted(pkg.items(), key=lambda x: -x[1]["not_in_book"])[:15]:
        print(
            f"  {p:20} total={d['total']:4} not_in_book={d['not_in_book']:4} cited={d['cited']:3}"
        )
    print("\nTop packages by CITED:")
    for p, d in sorted(pkg.items(), key=lambda x: -x[1]["cited"])[:12]:
        print(
            f"  {p:20} cited={d['cited']:3} total={d['total']:4} loose={d['cited']+d['dir_or_parent']:4}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
