#!/usr/bin/env python3
"""
One-off reading export: docs/book/*.md -> PDF under grok/.

Not trading-system tooling (no SITS registration). Pure-Python path:
markdown + xhtml2pdf. Internal chapter links rewritten to in-PDF anchors.

Usage:
  python grok/build_book_pdf_grok.py
  python grok/build_book_pdf_grok.py --quick-only
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from pathlib import Path

from markdown import markdown
from pypdf import PdfReader
from xhtml2pdf import pisa

REPO = Path(__file__).resolve().parents[1]
BOOK = REPO / "docs" / "book"
OUT_DIR = Path(__file__).resolve().parent

CHAPTER_ORDER = [
    "README.md",
    "00-quick-start.md",
    "01-why-tradelatest-exists.md",
    "02-invariants-and-happy-flow.md",
    "03-how-this-book-fits.md",
    "04-architecture-at-a-glance.md",
    "05-data-ingestion-no-lookahead.md",
    "06-market-ontology.md",
    "07-feature-pipeline.md",
    "08-crt-state-machine.md",
    "09-interpreters-pattern-contract.md",
    "10-four-scoring-engines.md",
    "11-fusion.md",
    "12-decision-engine.md",
    "13-execution-planner.md",
    "14-ultron-risk-gate.md",
    "15-live-execution-and-inout.md",
    "16-config-first-and-promotion.md",
    "17-truth-maintenance.md",
    "18-field-guide-governance.md",
    "19-research-programs.md",
    "20-research-platform.md",
    "21-ai-automation-agent.md",
    "22-control-plane.md",
    "23-multi-llm-coordination.md",
    "24-repository-encyclopedia.md",
    "encyclopedia/README.md",
    "encyclopedia/E1-spine-implementation.md",
    "encyclopedia/E1b-features-registry.md",
    "encyclopedia/E2-research-utilities.md",
    "encyclopedia/E3-governance-tooling.md",
    "encyclopedia/E4-sidecar-modules.md",
    "encyclopedia/E5-dormant-modules.md",
    "encyclopedia/E6-remaining-scripts.md",
    "A1-testing.md",
    "A2-unresolved-questions.md",
]

QUICK_ORDER = [
    "00-quick-start.md",
    "13-execution-planner.md",  # proposed remediations
    "15-live-execution-and-inout.md",  # INOUT resolution
    "19-research-programs.md",  # Program 9
    "A2-unresolved-questions.md",
]

RESEARCH_ORDER = [
    "19-research-programs.md",
    "20-research-platform.md",
    "09-interpreters-pattern-contract.md",  # same falsification discipline
    "A2-unresolved-questions.md",
]

ENCYCLOPEDIA_ORDER = [
    "24-repository-encyclopedia.md",
    "encyclopedia/README.md",
    "encyclopedia/E1-spine-implementation.md",
    "encyclopedia/E1b-features-registry.md",
    "encyclopedia/E2-research-utilities.md",
    "encyclopedia/E3-governance-tooling.md",
    "encyclopedia/E4-sidecar-modules.md",
    "encyclopedia/E5-dormant-modules.md",
    "encyclopedia/E6-remaining-scripts.md",
    "A2-unresolved-questions.md",
]

# Named HTML entities xhtml2pdf often mishandles with default fonts
ENTITY_FIXES = {
    "&rarr;": "->",
    "&larr;": "<-",
    "&mdash;": "—",
    "&ndash;": "-",
    "&hellip;": "...",
    "&times;": "x",
    "&ge;": ">=",
    "&le;": "<=",
    "&ne;": "!=",
    "&approx;": "~",
    "&nbsp;": " ",
    "&bull;": "*",
    "&middot;": "*",
    "&prime;": "'",
    "&Prime;": "\"",
}


def slug_anchor(filename: str) -> str:
    return "sec-" + filename.replace(".md", "").replace(".", "-").replace("/", "-").replace("\\", "-")


def rewrite_md_links(text: str, known: set[str]) -> str:
    """Rewrite [label](NN-foo.md) and [label](NN-foo.md#anchor) to #sec-NN-foo."""

    def repl(m: re.Match[str]) -> str:
        label, target = m.group(1), m.group(2)
        path = target.split("#", 1)[0]
        if path in known or path.endswith(".md") and Path(path).name in known:
            name = Path(path).name
            return f"[{label}](#{slug_anchor(name)})"
        # leave external / relative non-chapter links as plain text path note
        if path.startswith("http") or path.startswith("../"):
            return f"{label} (`{path}`)"
        return m.group(0)

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", repl, text)


def md_to_html_fragment(md_text: str, filename: str, known: set[str]) -> str:
    rewritten = rewrite_md_links(md_text, known)
    body = markdown(
        rewritten,
        extensions=["tables", "fenced_code", "toc", "sane_lists", "nl2br"],
        output_format="html5",
    )
    for ent, rep in ENTITY_FIXES.items():
        body = body.replace(ent, rep)
    # strip characters that often render as tofu in default PDF fonts
    body = body.replace("→", "->").replace("←", "<-").replace("×", "x")
    body = body.replace("≈", "~").replace("≤", "<=").replace("≥", ">=")
    body = body.replace("≠", "!=").replace("—", "-").replace("–", "-")
    body = body.replace("·", "*").replace("•", "*")
    anchor = slug_anchor(filename)
    return f'<div id="{anchor}" class="chapter">\n{body}\n</div>\n'


CSS = """
@page {
  size: a4;
  margin: 1.6cm 1.8cm 2.0cm 1.8cm;
  @frame footer {
    -pdf-frame-content: footerContent;
    bottom: 0.6cm;
    margin-left: 1.8cm;
    margin-right: 1.8cm;
    height: 1.0cm;
  }
}
body {
  font-family: Helvetica, Arial, sans-serif;
  font-size: 9.5pt;
  line-height: 1.35;
  color: #111;
}
h1 { font-size: 16pt; margin-top: 0.4cm; color: #0b1f33; }
h2 { font-size: 12.5pt; margin-top: 0.35cm; color: #123; border-bottom: 0.5pt solid #ccc; }
h3 { font-size: 11pt; margin-top: 0.3cm; color: #234; }
h4 { font-size: 10pt; margin-top: 0.25cm; }
p, li { orphans: 2; widows: 2; }
code, pre {
  font-family: Courier, monospace;
  font-size: 8pt;
  background: #f4f4f4;
}
pre {
  padding: 6pt;
  border: 0.4pt solid #ddd;
  white-space: pre-wrap;
}
table {
  border-collapse: collapse;
  width: 100%;
  margin: 8pt 0;
  font-size: 8.5pt;
}
th, td {
  border: 0.4pt solid #999;
  padding: 3pt 4pt;
  vertical-align: top;
}
th { background: #e8eef5; }
blockquote {
  border-left: 2pt solid #8aa;
  margin-left: 0;
  padding-left: 8pt;
  color: #333;
  font-size: 9pt;
}
.cover {
  text-align: center;
  margin-top: 3.5cm;
}
.cover h1 { font-size: 22pt; border: none; }
.cover .sub { font-size: 11pt; color: #444; margin-top: 0.6cm; }
.cover .meta { font-size: 9pt; color: #666; margin-top: 1.2cm; }
.chapter { page-break-before: always; }
.chapter:first-of-type { page-break-before: avoid; }
#toc h1 { page-break-before: always; }
a { color: #0645ad; text-decoration: none; }
.footer { font-size: 8pt; color: #555; text-align: center; }
"""


def build_html(files: list[str], title: str, subtitle: str) -> str:
    known = set(files)
    parts: list[str] = []
    parts.append(
        f"""
<div class="cover">
  <h1>{html.escape(title)}</h1>
  <p class="sub">{html.escape(subtitle)}</p>
  <p class="meta">Generated {dt.date.today().isoformat()} from docs/book/<br/>
  Grok review pass export &mdash; reading convenience only.<br/>
  On conflict, repository code/config wins.</p>
</div>
"""
    )
    parts.append('<div id="toc"><h1>Table of Contents</h1><pdf:toc /></div>')
    for name in files:
        path = BOOK / name
        if not path.exists():
            raise FileNotFoundError(path)
        md = path.read_text(encoding="utf-8")
        # Prefer filename as visible section title if README
        if name == "README.md":
            md = "# The Tradelatest Book — Table of Contents & Guide\n\n" + md
        parts.append(md_to_html_fragment(md, name, known))

    body = "\n".join(parts)
    # pdf:toc needs structure; xhtml2pdf picks up h1-h3
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>{CSS}</style></head>
<body>
{body}
<div id="footerContent" class="footer">
  {html.escape(title)} — page <pdf:pagenumber/> of <pdf:pagecount/>
</div>
</body></html>
"""


def write_pdf(html_doc: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        status = pisa.CreatePDF(html_doc, dest=fh, encoding="utf-8")
    if status.err:
        raise RuntimeError(f"xhtml2pdf reported {status.err} errors for {out_path}")


def verify(out_path: Path, min_pages: int = 3) -> dict:
    r = PdfReader(str(out_path))
    n = len(r.pages)
    sample = (r.pages[0].extract_text() or "")[:400]
    if n < min_pages:
        raise RuntimeError(f"{out_path.name}: only {n} pages (expected >= {min_pages})")
    if "Tradelatest" not in sample and "Quick Start" not in sample:
        # soft: page 0 might be blankish; check page 1
        sample2 = (r.pages[min(1, n - 1)].extract_text() or "")[:400]
        if "Tradelatest" not in sample2 and "candle" not in sample2.lower():
            raise RuntimeError(f"{out_path.name}: text extraction looks empty")
    return {"pages": n, "bytes": out_path.stat().st_size, "sample": sample[:120]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick-only", action="store_true")
    args = ap.parse_args()

    full_out = OUT_DIR / "Tradelatest-Canonical-Knowledge-Book-Grok.pdf"
    quick_out = OUT_DIR / "Tradelatest-Canonical-Knowledge-Book-QuickStart-Grok.pdf"
    delta_out = OUT_DIR / "Tradelatest-Canonical-Knowledge-Book-ReviewDelta-Grok.pdf"
    research_out = OUT_DIR / "Tradelatest-Canonical-Knowledge-Book-Research-Grok.pdf"
    encyclopedia_out = OUT_DIR / "Tradelatest-Repository-Encyclopedia-Grok.pdf"

    results = []

    if not args.quick_only:
        html_full = build_html(
            CHAPTER_ORDER,
            "The Tradelatest Book (Grok Review Pass)",
            "Canonical Knowledge Book — full narrative. Part VII Research = Chapters 19-20 "
            "(programs results table + platform data map).",
        )
        write_pdf(html_full, full_out)
        results.append(("full", full_out, verify(full_out, min_pages=40)))

    html_quick = build_html(
        ["00-quick-start.md"],
        "Tradelatest Quick Start (Grok)",
        "One candle's journey — short-circuit the meta-layers",
    )
    write_pdf(html_quick, quick_out)
    results.append(("quick", quick_out, verify(quick_out, min_pages=2)))

    html_delta = build_html(
        QUICK_ORDER,
        "Tradelatest Book — Grok Review Delta",
        "Chapters updated for the review: Quick Start, remediations, INOUT, Program 9, A2",
    )
    write_pdf(html_delta, delta_out)
    results.append(("delta", delta_out, verify(delta_out, min_pages=8)))

    html_research = build_html(
        RESEARCH_ORDER,
        "Tradelatest Book — RESEARCH (Grok)",
        "Part VII extract: Program 1-9 results data table, research platform map, "
        "artifact roots under results/research/, Measurement Contract gap.",
    )
    write_pdf(html_research, research_out)
    results.append(("research", research_out, verify(research_out, min_pages=6)))

    html_ency = build_html(
        ENCYCLOPEDIA_ORDER,
        "Tradelatest — Repository Encyclopedia (Grok)",
        "Charter for remaining files (Groups A-D), ~403 NOT_IN_BOOK, path from "
        "architecture guide to full repository encyclopedia.",
    )
    write_pdf(html_ency, encyclopedia_out)
    results.append(("encyclopedia", encyclopedia_out, verify(encyclopedia_out, min_pages=4)))

    for kind, path, meta in results:
        print(f"OK {kind}: {path.name} pages={meta['pages']} bytes={meta['bytes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
