"""One-shot: build .grok/HOW_INDEX.md from topics + Excel package counts."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "docs" / "topics"
SKIP = {"_template.md", "readme.md"}
WB_SRC = ROOT / "results" / "analysis" / "src_business_functionality.xlsx"
WB_SCRIPTS = ROOT / "scripts_business_functionality.xlsx"
WB_TESTS = ROOT / "docs" / "analysis" / "tests_functionality_inventory.xlsx"
EXCEL_LIST = ROOT / ".grok" / "excel_file_list.json"


def _pkg_key(rel: str) -> str:
    rel = rel.replace("\\", "/").strip()
    parts = rel.split("/")
    if len(parts) <= 2:
        return rel
    return "/".join(parts[:2])


def rebuild_excel_file_list() -> dict:
    """Recount unique .py rows from the three GCMC v1 workbooks."""
    from openpyxl import load_workbook

    def col_paths(path: Path, sheet: str, col_name: str, *, scripts_relative: bool = False) -> list[str]:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet]
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        idx = headers.index(col_name)
        out: list[str] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            raw = row[idx]
            if not raw:
                continue
            rel = str(raw).replace("\\", "/").strip()
            if scripts_relative and not rel.startswith("scripts/"):
                rel = "scripts/" + rel
            out.append(rel)
        wb.close()
        return out

    src = col_paths(WB_SRC, "src_py_inventory", "File Name")
    scripts = col_paths(WB_SCRIPTS, "Scripts Analysis", "File Name", scripts_relative=True)
    tests = col_paths(WB_TESTS, "By File", "Relative Path")
    pkg = {
        "src_n": len(set(src)),
        "scripts_n": len(set(scripts)),
        "tests_n": len(set(tests)),
        "src_pkgs": dict(sorted(Counter(_pkg_key(p) for p in src).items())),
        "scripts_pkgs": dict(sorted(Counter(_pkg_key(p) for p in scripts).items())),
        "tests_pkgs": dict(sorted(Counter(_pkg_key(p) for p in tests).items())),
        "generated": date.today().isoformat(),
    }
    EXCEL_LIST.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
    return pkg

NEEDED = {
    "crt-spine.md": "Incumbent structure path (Sense A). Candle to order.",
    "scoring-engines.md": "What Gaussian/Zone/RR actually score (not p(win)).",
    "fusion-decision.md": "Who may approve a decision.",
    "execution-planning.md": "Entry/SL/TP geometry after approval.",
    "ultron-risk-gate.md": "Final risk/money gate.",
    "feature-schema.md": "What numbers every engine sees; leakage risk.",
    "live-execution.md": "Whether a live book even exists (F-073).",
    "research-measurement-contract.md": "How a money claim must be measured.",
    "promotion-governance.md": "What may enter production.",
    "goal-layer.md": "G001 / earn-money metric ownership.",
    "model-intent-and-feature-ownership.md": "Who owns which market question (MIAR).",
    "bitnet-gate.md": "Hard-reject when enabled; inert on active patch.",
    "config-validation.md": "What APPROVE on a config actually promises.",
}

USEFUL = {
    "analytics-sltp.md": "What-if exits on identical entries.",
    "metrics-layer.md": "Second-order measurement (RR/distribution).",
    "regime-classifier.md": "Regime label vs fusion weights.",
    "training-calibration.md": "Offline model fit; not a live edge.",
    "replay-memory.md": "Sidecar memory; zero spine consumption (F-012).",
    "portfolio-allocation.md": "Built; live path is single-candle (F-013).",
    "execution-loop.md": "Multi-signal loop; test/orphan surface (F-013).",
    "ai-automation-agent.md": "Operator agent; not a strategy.",
    "expansion-engine.md": "Bounded config search.",
    "weight-search.md": "Regime weight search; no authority.",
    "event-fabric.md": "Telemetry envelope.",
    "context-report.md": "Control-plane run explainer.",
    "capital-pressure-ratio.md": "Named latent; not validated; no TRADE_OPENED.",
    "interpreter-contract.md": "Interpreter vs engine authority.",
}


def section(text: str, name: str) -> str:
    pat = re.compile(rf"^## {re.escape(name)}\s*$", re.M | re.I)
    m = pat.search(text)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^## ", text[start:], re.M)
    return text[start : start + nxt.start() if nxt else None].strip()


def first_sentences(text: str, n: int = 2, cap: int = 420) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    parts = re.split(r"(?<=[.!?])\s+", t)
    s = " ".join(parts[:n]).strip()
    return (s[: cap - 1] + "…") if len(s) > cap else s


def md_files(s: str) -> list[str]:
    files: list[str] = []
    for m in re.finditer(
        r"(src|scripts|tests|docs|configs)/[A-Za-z0-9_./-]+\.(?:py|md|json|yaml)", s
    ):
        files.append(m.group(0).split(":")[0].replace("\\", "/"))
    out, seen = [], set()
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def main() -> None:
    topics = []
    for p in sorted(TOPICS.glob("*.md")):
        if p.name.lower() in SKIP:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        title = p.stem
        m = re.search(r"^#\s+(.+)$", text, re.M)
        if m:
            title = m.group(1).strip()
        plain = section(text, "In plain language")
        ios = section(text, "Ins / Outs") or section(text, "Ins/Outs")
        code = section(text, "Code covered")
        tests = section(text, "Tests")
        ins = outs = ""
        for line in ios.splitlines():
            low = line.lower()
            if "**ins:**" in low:
                ins = re.sub(r"^[-*]\s*\*\*Ins:\*\*\s*", "", line, flags=re.I).strip()
            elif "**outs:**" in low:
                outs = re.sub(r"^[-*]\s*\*\*Outs:\*\*\s*", "", line, flags=re.I).strip()
        kind = (
            "NEEDED"
            if p.name in NEEDED
            else ("USEFUL" if p.name in USEFUL else "OTHER")
        )
        why = (
            NEEDED.get(p.name)
            or USEFUL.get(p.name)
            or "Topic exists; not on the money-validation path by default."
        )
        topics.append(
            {
                "name": p.name,
                "title": title,
                "kind": kind,
                "why": why,
                "plain": first_sentences(plain, 2),
                "ins": first_sentences(ins or ios, 2),
                "outs": first_sentences(outs or "", 2),
                "files": md_files(code + "\n" + tests + "\n" + ios)[:24],
            }
        )

    pkg = rebuild_excel_file_list()
    order = {"NEEDED": 0, "USEFUL": 1, "OTHER": 2}
    topics.sort(key=lambda t: (order[t["kind"]], t["name"]))

    lines: list[str] = []
    A = lines.append
    A("# How-index — topics × Excel files")
    A("")
    stamp = date.today().isoformat()
    A(f"Generated {stamp} from `docs/topics/*.md` + the three functionality Excels.")
    A("This file is the **How** extract. GROK.md points here. Do not paste this into GROK.md.")
    A("")
    A(f"Workbooks (file-list, generated {stamp}; GCMC is listed ∩ disk — see `.grok/CLOSURE_KPI.md`):")
    A("")
    A("| Workbook | Unique files | Role in How |")
    A("|---|---:|---|")
    A(
        f"| `results/analysis/src_business_functionality.xlsx` | {pkg['src_n']} | Does this `src/` file exist as inventoried behavior? |"
    )
    A(
        f"| `scripts_business_functionality.xlsx` | {pkg['scripts_n']} | Does this `scripts/` helper exist? |"
    )
    A(
        f"| `docs/analysis/tests_functionality_inventory.xlsx` (`By File`) | {pkg['tests_n']} | Which test file covers a claim? |"
    )
    A("")
    A(
        "GCMC v1: see `.grok/CLOSURE_KPI.md`. "
        "This extract lists topic Ins/Outs; the KPI is file-list intersection."
    )
    A("")
    A("## How a trader claim uses this file")
    A("")
    A("1. Name the **topic** (meaning).")
    A("2. Read **Ins / Outs** (contract: what goes in, what is allowed out).")
    A("3. Open the **code files** cited (existence / current behavior).")
    A("4. Confirm the file is in the matching Excel (inventory).")
    A("5. Only then ask money (`P-GOAL-04`). Ins/outs that forbid TRADE_OPENED cannot mint an edge.")
    A("")
    A("## Needed vs useful")
    A("")
    A("- **NEEDED** — required to validate a money/structure/execution claim.")
    A("- **USEFUL** — real topics; sidecar, orphan, search, or not-yet-authoritative.")
    A("- **OTHER** — extracted but not classified above.")
    A("")
    A("## Topic extract")
    A("")
    for t in topics:
        A(f"### {t['kind']} — {t['title']}")
        A("")
        A(f"- File: [`docs/topics/{t['name']}`](../docs/topics/{t['name']})")
        A(f"- Why for How: {t['why']}")
        A(f"- Plain: {t['plain'] or '(none extracted)'}")
        A(f"- **Ins:** {t['ins'] or '(none extracted)'}")
        A(f"- **Outs:** {t['outs'] or '(none extracted)'}")
        if t["files"]:
            A("- Cited files: " + ", ".join(f"`{f}`" for f in t["files"]))
        else:
            A("- Cited files: (none extracted)")
        A("")

    A("## Excel package rollup (file names tracked)")
    A("")
    A("Counts are unique `.py` rows in the workbooks, not disk (see GROK.md §8).")
    A("")
    A("### src/")
    A("")
    A("| Package | Files |")
    A("|---|---:|")
    for k, n in sorted(pkg["src_pkgs"].items(), key=lambda x: (-x[1], x[0])):
        A(f"| `{k}` | {n} |")
    A("")
    A("### scripts/")
    A("")
    A("| Package | Files |")
    A("|---|---:|")
    for k, n in sorted(pkg["scripts_pkgs"].items(), key=lambda x: (-x[1], x[0])):
        A(f"| `{k}` | {n} |")
    A("")
    A("### tests/ (folders with ≥2 files; rest are singleton `test_*.py`)")
    A("")
    A("| Package | Files |")
    A("|---|---:|")
    rest = 0
    for k, n in sorted(pkg["tests_pkgs"].items(), key=lambda x: (-x[1], x[0])):
        if n >= 2:
            A(f"| `{k}` | {n} |")
        else:
            rest += n
    A(f"| *(root `tests/test_*.py` and singleton folders)* | {rest} |")
    A("")
    A(
        f"Full file names live in the three xlsx workbooks. "
        f"Do not copy the {pkg['src_n'] + pkg['scripts_n'] + pkg['tests_n']} rows here."
    )
    A("")
    A("## Needed-topic cited files")
    A("")
    A("| File | Topic |")
    A("|---|---|")
    for t in topics:
        if t["kind"] != "NEEDED":
            continue
        for f in t["files"]:
            A(f"| `{f}` | {t['name']} |")
    A("")
    A("## What this extract is not")
    A("")
    A("- Not economic proof.")
    A("- Not a second doctrine.")
    A("- Not complete if GCMC v1 is below 100% — leftovers live in `.grok/infra_architecture_link.xlsx` Gaps.")
    A("- Topic prose can drift; **source wins**.")
    A("")

    out = ROOT / ".grok" / "HOW_INDEX.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} topics={len(topics)}")


if __name__ == "__main__":
    main()
