"""Build RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx/csv from script docstrings/CLI."""
from __future__ import annotations

import ast
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

ROOT = Path(r"D:\Tradelatest")
OUT_DIR = ROOT / "docs" / "research"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLUMNS = [
    "script_path",
    "script_name",
    "folder",
    "intent",
    "status_hints",
    "claim_class_or_authority",
    "primary_inputs",
    "primary_outputs",
    "related_episode_or_id",
    "last_mtime",
    "notes",
]

STATUS_PATTERNS = [
    r"MEASURE[- ]ONLY",
    r"READ[- ]ONLY",
    r"measurement[- ]only",
    r"\bfrozen\b",
    r"\bprobe\b",
    r"\bSHADOW\b",
    r"DESCRIPTIVE[_ ]ONLY",
    r"economic_claims_allowed\s*=\s*false",
    r"NO[_ ]ECONOMIC",
    r"research[- ]only",
    r"offline[- ]only",
    r"do not (?:promote|trade|deploy)",
    r"non[- ]actionable",
    r"audit[- ]only",
    r"diagnostic[- ]only",
    r"certification",
    r"kill[- ]test",
    r"parity",
    r"information not authority",
]

CLAIM_PATTERNS = [
    r"DESCRIPTIVE[_ ]ONLY",
    r"economic_claims_allowed\s*=\s*false",
    r"claim[_ ]class\s*[:=]\s*\S+",
    r"authority\s*[:=]\s*\S+",
    r"NO[_ ]ECONOMIC[_ ]CLAIMS?",
    r"MEASURE[_ ]ONLY",
    r"READ[_ ]ONLY",
    r"information not authority",
    r"no edge(?:/profit)? claim",
    r"failure structure only",
]

EPISODE_PATTERNS = [
    r"\bL-?00[0-9][A-Za-z0-9]*\b",
    r"\bJSE[-_]?00[0-9]\b",
    r"\bSEM[-_]?0?[0-9]{2,3}\b",
    r"\bIC[-_]?00[0-9][A-Za-z]?\b",
    r"\bRC[-_]?00[0-9]\b",
    r"\bPhase[-_ ]?[0-9A-Za-z]+\b",
    r"\bSHADOW\b",
    r"\bCRT\b",
    r"\bMSIP\b",
    r"\bGate[-_]?[0-9O]\b",
    r"\bM[-_]?GATE[-_]?0?1\b",
    r"\bH[-_]?RR\b",
    r"\bH[-_]?MSIP[-_]?00[12]\b",
    r"\bH[-_]?G001\b",
    r"\bFM[-_]?030\b",
    r"\bERP\b",
    r"\bP[-_]?STRUCT[-_]?01\b",
    r"\bP00[1-9]\b",
    r"\bP[1-4][A-Za-z0-9]*\b",
    r"\bBNBUSDT\b",
    r"\bXAUUSD\b",
]


def first_n_lines(text: str, n: int = 80) -> str:
    return "\n".join(text.splitlines()[:n])


def get_docstring(path: Path) -> str | None:
    try:
        src = path.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
        try:
            tree = ast.parse(src)
            doc = ast.get_docstring(tree)
            if doc and doc.strip():
                return doc.strip()
        except SyntaxError:
            pass
        m = re.match(r'\s*(?:#.*?\n\s*)*"""(.*?)"""', src, re.S)
        if not m:
            m = re.match(r"\s*(?:#.*?\n\s*)*'''(.*?)'''", src, re.S)
        if m:
            doc = m.group(1).strip()
            return doc or None
        return None
    except Exception:
        return None


def get_argparse_description(src: str) -> str | None:
    # ArgumentParser(description="...") or description='...'
    m = re.search(
        r"ArgumentParser\s*\([^)]*?description\s*=\s*(['\"])(?P<d>.*?)\1",
        src,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        return re.sub(r"\s+", " ", m.group("d")).strip()
    # Also check add_argument help is too noisy; skip
    # Top-block comment before imports
    lines = src.splitlines()
    comments = []
    for line in lines[:40]:
        s = line.strip()
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            if body and not re.match(r"(?i)^(coding[:=]|!/|when run via|pin ROOT)", body):
                comments.append(body)
        elif s == "" or s.startswith('"""') or s.startswith("'''"):
            continue
        elif comments and not s.startswith("#"):
            break
    if comments:
        joined = " ".join(c for c in comments if c)
        if len(joined) > 20:
            return joined[:500]
    return None


def extract_paths_mentioned(text: str, kind: str) -> str:
    """Pull short input/output path hints from docstring/header text."""
    if not text:
        return ""
    # Common patterns
    outs = re.findall(
        r"(?:writes?|output(?:s)?|artifact(?:s)?|emits?|saves?|produces?|report(?:s)?)\s*(?:to|:)\s*`?([^\s`,'\"]+)`?",
        text,
        re.I,
    )
    inns = re.findall(
        r"(?:reads?|input(?:s)?|corpus|from|config|loads?)\s*(?:from|:)?\s*`?((?:data|artifacts|docs|config|runs|logs|results|exports|cache)[^\s`,'\"]*)`?",
        text,
        re.I,
    )
    pathish = re.findall(
        r"(?:artifacts|docs|data|config|runs|results|exports|cache)/[^\s`,'\"]+",
        text,
        re.I,
    )
    if kind == "out":
        items = outs + [p for p in pathish if any(k in p.lower() for k in ("out", "report", "artifact", "result", "eval", "census"))]
    else:
        items = inns + [p for p in pathish if any(k in p.lower() for k in ("data", "corpus", "config", "in", "label", "zone"))]
    # Also capture --arg defaults mentioned as paths
    # Dedup preserve order
    seen = []
    for x in items:
        x = x.rstrip(").,;:")
        if x and x not in seen:
            seen.append(x)
    return "; ".join(seen[:6])


def find_matches(text: str, patterns: list[str]) -> str:
    if not text:
        return ""
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            val = re.sub(r"\s+", " ", m.group(0)).strip()
            low = val.lower()
            if "descriptive" in low:
                val = "DESCRIPTIVE_ONLY"
            elif "economic_claims_allowed" in low:
                val = "economic_claims_allowed=false"
            elif "measure" in low and "only" in low:
                val = "MEASURE-ONLY"
            elif "read" in low and "only" in low:
                val = "READ-ONLY"
            elif "information not authority" in low:
                val = "information_not_authority"
            if val and val not in found:
                found.append(val)
    return "; ".join(found[:10])


def intent_from_text(doc: str | None, argparse_desc: str | None, name: str, src_head: str) -> tuple[str, str, bool]:
    """Return (intent, notes, explicit_docstring)."""
    explicit = bool(doc and len(doc.strip()) > 15)
    if explicit:
        # Take first 1-3 sentences
        cleaned = re.sub(r"\s+", " ", doc.strip())
        # Split sentences roughly
        parts = re.split(r"(?<=[.!?])\s+", cleaned)
        intent = " ".join(parts[:3]).strip()
        if len(intent) > 600:
            intent = intent[:597] + "..."
        return intent, "", True
    if argparse_desc and len(argparse_desc.strip()) > 15:
        cleaned = re.sub(r"\s+", " ", argparse_desc.strip())
        parts = re.split(r"(?<=[.!?])\s+", cleaned)
        intent = " ".join(parts[:3]).strip()
        if len(intent) > 600:
            intent = intent[:597] + "..."
        return intent, "INTENT_UNSTATED — inferred from CLI/top-comment only", False
    # Minimal name-based inference
    base = name.replace(".py", "").replace("_", " ")
    intent = f"Research utility: {base}."
    return intent, "INTENT_UNSTATED — inferred from name/CLI only", False


def is_research_oriented_analysis(path: Path, doc: str | None, head: str) -> bool:
    """Include analysis scripts that are clearly Phase/CRT/resolver research probes."""
    name = path.name.lower()
    text = f"{name}\n{doc or ''}\n{head}".lower()
    # Name patterns
    name_ok = bool(
        re.search(
            r"(phase|crt|resolver|shadow|probe|jse|sem|parity|gaussian|zone.?gate|rr_|msip|excursion|forensic|certification|replay.?evidence)",
            name,
        )
    )
    # Doc patterns
    doc_ok = bool(
        re.search(
            r"(phase[-_ ]?[0-9]|crt|resolver|shadow|research probe|measure[- ]only|descriptive|economic.?claim)",
            text,
        )
    )
    # Exclude pure tooling / code maps / dummy / html explorers
    exclude = bool(
        re.search(
            r"^(gen_|build_code|graph_query|render_chart|test_functionality|script_census|module_census|python_source|src_business|query_decision|query_trace|gen_dummy|gen_html|gen_pyan|gen_flow|gen_code)",
            name,
        )
    )
    if exclude:
        return False
    return name_ok or (doc_ok and ("probe" in name or "phase" in name or "crt" in name or "shadow" in name or "resolver" in name))


def process_file(path: Path, folder: str) -> dict:
    rel = path.relative_to(ROOT).as_posix()
    try:
        src = path.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    except Exception as e:
        return {
            "script_path": rel,
            "script_name": path.name,
            "folder": folder,
            "intent": "",
            "status_hints": "",
            "claim_class_or_authority": "",
            "primary_inputs": "",
            "primary_outputs": "",
            "related_episode_or_id": "",
            "last_mtime": "",
            "notes": f"READ_ERROR: {e}",
        }
    head = first_n_lines(src, 80)
    doc = get_docstring(path)
    ap = get_argparse_description(src)
    intent, notes, explicit = intent_from_text(doc, ap, path.name, head)
    corpus = "\n".join(filter(None, [doc or "", ap or "", head]))
    mtime = datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    return {
        "script_path": rel,
        "script_name": path.name,
        "folder": folder,
        "intent": intent,
        "status_hints": find_matches(corpus, STATUS_PATTERNS),
        "claim_class_or_authority": find_matches(corpus, CLAIM_PATTERNS),
        "primary_inputs": extract_paths_mentioned(corpus, "in"),
        "primary_outputs": extract_paths_mentioned(corpus, "out"),
        "related_episode_or_id": find_matches(corpus, EPISODE_PATTERNS),
        "last_mtime": mtime,
        "notes": notes,
        "_explicit": explicit,
    }


def write_excel(rows: list[dict], path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "research_scripts"
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    thin = Border(
        left=Side(style="thin", color="B0B0B0"),
        right=Side(style="thin", color="B0B0B0"),
        top=Side(style="thin", color="B0B0B0"),
        bottom=Side(style="thin", color="B0B0B0"),
    )
    for col, name in enumerate(COLUMNS, 1):
        cell = ws.cell(1, col, name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = thin
    for r_i, row in enumerate(rows, 2):
        for c_i, name in enumerate(COLUMNS, 1):
            cell = ws.cell(r_i, c_i, row.get(name, ""))
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = thin
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows)+1}"
    widths = {
        "A": 48, "B": 36, "C": 12, "D": 70, "E": 28, "F": 32,
        "G": 36, "H": 36, "I": 28, "J": 28, "K": 40,
    }
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.row_dimensions[1].height = 22
    wb.save(path)


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in COLUMNS})


def write_readme(path: Path, n_research: int, n_analysis: int, n_explicit: int, n_unstated: int) -> None:
    text = f"""# Research Scripts Intent Tracker

Inventory of research-script intents for TradeHlt / TradeLatest.

## Deliverables

- `RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx` — sheet `research_scripts` (frozen header + filters)
- `RESEARCH_SCRIPTS_INTENT_TRACKER.csv` — twin for easy git diff
- This README

## Scope

- **Primary:** all `scripts/research/**/*.py` ({n_research} files)
- **Also:** research-oriented analysis scripts under `scripts/analysis/` that are clearly Phase / CRT / resolver / shadow / probe work ({n_analysis} files)
- `folder` column distinguishes `research` vs `analysis`

## Columns

| Column | Meaning |
|--------|---------|
| script_path | Repo-relative path (forward slashes) |
| script_name | Basename |
| folder | `research` or `analysis` |
| intent | 1–3 sentences grounded in module docstring / top comment / argparse description |
| status_hints | MEASURE-ONLY / READ-ONLY / frozen / probe / etc. when stated |
| claim_class_or_authority | DESCRIPTIVE_ONLY, economic_claims_allowed=false, etc. when stated |
| primary_inputs | Short corpus/config/path hints from the file |
| primary_outputs | Artifact/path hints from the file |
| related_episode_or_id | L-003, JSE, SHADOW, SEM-015, Phase-1, CRT, etc. when mentioned |
| last_mtime | ISO local mtime at inventory time |
| notes | Gaps such as `INTENT_UNSTATED — inferred from name/CLI only` |

## Stats (this build)

- Explicit module docstring: **{n_explicit}**
- Intent unstated / inferred: **{n_unstated}**
- Total rows: **{n_research + n_analysis}**

## How to maintain

1. Prefer completeness for `scripts/research/` first.
2. When adding a script, put a real module docstring (1–3 sentences of intent) plus argparse `description=` if CLI.
3. State status/claim authority explicitly in the docstring when applicable, e.g. `MEASURE-ONLY`, `DESCRIPTIVE_ONLY`, `economic_claims_allowed=false`.
4. Re-run the builder:

```powershell
$env:PYTHONPATH = "D:\\Tradelatest"
& .\\.venv\\Scripts\\python.exe docs\\research\\_build_research_scripts_intent_tracker.py
```

5. Diff the CSV twin in PRs; treat Excel as the human-facing workbook.
6. Do **not** invent intents. If the docstring is empty, mark `INTENT_UNSTATED` and keep name/CLI inference minimal.
7. Do not commit unless asked. This tracker is documentation only — no freeze/resolver economic work.

## Rebuild script

The generator lives at `docs/research/_build_research_scripts_intent_tracker.py`.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    research_files = sorted((ROOT / "scripts" / "research").rglob("*.py"))
    analysis_dir = ROOT / "scripts" / "analysis"
    analysis_candidates = sorted(analysis_dir.rglob("*.py")) if analysis_dir.exists() else []

    rows: list[dict] = []
    for p in research_files:
        rows.append(process_file(p, "research"))

    analysis_included = 0
    for p in analysis_candidates:
        try:
            src = p.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
        except Exception:
            continue
        head = first_n_lines(src, 80)
        doc = get_docstring(p)
        if is_research_oriented_analysis(p, doc, head):
            rows.append(process_file(p, "analysis"))
            analysis_included += 1

    rows.sort(key=lambda r: (r["folder"], r["script_path"]))

    n_explicit = sum(1 for r in rows if r.get("_explicit"))
    n_unstated = len(rows) - n_explicit

    xlsx = OUT_DIR / "RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx"
    csv_path = OUT_DIR / "RESEARCH_SCRIPTS_INTENT_TRACKER.csv"
    readme = OUT_DIR / "RESEARCH_SCRIPTS_INTENT_TRACKER_README.md"
    builder = OUT_DIR / "_build_research_scripts_intent_tracker.py"

    write_excel(rows, xlsx)
    write_csv(rows, csv_path)
    write_readme(readme, len(research_files), analysis_included, n_explicit, n_unstated)

    # Persist this builder next to outputs for maintainability
    this_file = Path(__file__).resolve() if "__file__" in dir() else None
    # Always write a copy of the builder source from stdin embedding — rewritten below by caller

    print(f"research={len(research_files)}")
    print(f"analysis_included={analysis_included}")
    print(f"total_rows={len(rows)}")
    print(f"explicit_docstring={n_explicit}")
    print(f"unstated={n_unstated}")
    print(f"xlsx={xlsx}")
    print(f"csv={csv_path}")
    print(f"readme={readme}")


if __name__ == "__main__":
    main()
