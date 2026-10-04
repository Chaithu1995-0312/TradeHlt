"""
gen_citation_map.py
===================
Reverse map: code symbol -> the docs that cite it.

WHY (CLAUDE.md §6.3 Citation Sync Mandate): docs cite code as ``path:line · Symbol`` so a reader
can jump to source. When you edit a symbol you must update every doc that cites it in the same
turn - but you first have to *find* them. This tool scans the mapped docs and emits the reverse
index (symbol -> citing docs), so the lookup is one grep instead of a repo sweep.

Pairs with tests/test_doc_citations.py (the forward check: does each citation still resolve).

Stdlib only (`re` + `pathlib`), deterministic output (everything sorted) - byte-identical across
runs on the same inputs, safe to commit.

Outputs:
  - docs/architecture/citation-map.generated.md

Usage:
  python scripts/analysis/gen_citation_map.py            # write the artifact
  python scripts/analysis/gen_citation_map.py --check     # print to stdout, write nothing
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

# Repo root = two levels up from scripts/analysis/gen_citation_map.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUT = _REPO_ROOT / "docs" / "architecture" / "citation-map.generated.md"

# Mapped docs: same high-value set the §6.3 contract covers (see tests/test_doc_citations.py).
_MAPPED_DOCS = (
    [_REPO_ROOT / "CLAUDE.md", _REPO_ROOT / "docs" / "current-findings.md"]
    + sorted((_REPO_ROOT / "docs" / "architecture").glob("*.md"))
    + sorted((_REPO_ROOT / "docs" / "reference").glob("*.md"))
    + sorted((_REPO_ROOT / "docs" / "topics").glob("*.md"))
)

# `path.py:LINE <middot> Symbol` - Symbol is the leading identifier only.
_CITATION_RE = re.compile(r"([\w./-]+\.py):(\d+)\s*·\s*([A-Za-z_]\w*)")


def _collect() -> dict[str, set[tuple[str, str, int]]]:
    """symbol -> {(path, citing_doc_rel, code_line)}."""
    by_symbol: dict[str, set[tuple[str, str, int]]] = {}
    for doc in _MAPPED_DOCS:
        if not doc.exists():
            continue
        doc_rel = doc.relative_to(_REPO_ROOT).as_posix()
        for text in doc.read_text(encoding="utf-8").splitlines():
            for m in _CITATION_RE.finditer(text):
                path_str, line, symbol = m.group(1), int(m.group(2)), m.group(3)
                by_symbol.setdefault(symbol, set()).add((path_str, doc_rel, line))
    return by_symbol


def _render(by_symbol: dict[str, set[tuple[str, str, int]]]) -> str:
    out: list[str] = []
    out.append("# citation-map.generated.md")
    out.append("")
    out.append("> **GENERATED — do not edit by hand.** Regenerate with "
               "`python scripts/analysis/gen_citation_map.py`.")
    out.append(">")
    out.append("> Reverse map for the CLAUDE.md §6.3 Citation Sync Mandate: each code **symbol** "
               "below lists the docs that cite it via `path:line · Symbol`. When you move or rename "
               "a symbol, update every doc listed for it in the same turn. Forward check: "
               "`tests/test_doc_citations.py`.")
    out.append("")
    if not by_symbol:
        out.append("_No dual-form `path:line · Symbol` citations found in the mapped docs yet._")
        out.append("")
        return "\n".join(out)

    out.append(f"**{len(by_symbol)} symbols cited** across the mapped docs "
               "(CLAUDE.md, current-findings.md, docs/architecture/*, docs/reference/*, docs/topics/*).")
    out.append("")
    out.append("| Symbol | Path | Cited by (doc:line) |")
    out.append("| --- | --- | --- |")
    for symbol in sorted(by_symbol):
        rows = sorted(by_symbol[symbol])
        paths = sorted({p for p, _, _ in rows})
        cites = ", ".join(f"`{d}` (code :{ln})" for _, d, ln in rows)
        out.append(f"| `{symbol}` | {' / '.join(f'`{p}`' for p in paths)} | {cites} |")
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="print to stdout, write nothing")
    args = ap.parse_args()

    content = _render(_collect())
    if args.check:
        print(content)
        return
    _OUT.write_text(content, encoding="utf-8")
    print(f"wrote {_OUT.relative_to(_REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
