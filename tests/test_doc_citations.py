"""Code-citation alignment - the enforceable floor for the Citation Sync layer.

Mirrors tests/test_topic_docs.py / tests/test_current_findings.py (read-a-doc-and-assert)
and enforces the CLAUDE.md §6.3 Citation Sync Mandate: every dual-form code citation in the
mapped docs must still resolve to real code.

A dual-form citation is written ``path:line · Symbol`` (e.g.
``src/config_layer/crt_engine_v2.py:1074 · VALID_TRANSITIONS``):
  - the *symbol* is the authoritative anchor (survives refactors);
  - the *line* is a maintained hint.

For each such citation this test asserts:
  (a) the file resolves (full repo-relative path, or a unique basename under src/tests/scripts);
  (b) the symbol token appears in the file;
  (c) the cited line is within the file and the symbol sits within a small drift window of it.

It intentionally matches ONLY the middot dual form, so legacy bare ``file.py:line`` refs and
doc-to-doc ``*.md:line`` refs are out of scope (per the convention: legacy tolerated, upgrade
when touched). This check can go red purely from code moving under a stale citation - by design:
the mechanical "code moved, docs didn't" cure. It does NOT verify the cited code still *means*
what the prose claims (that is the per-response Sync mandate's job).
"""
from __future__ import annotations

import re
from pathlib import Path

# Roots a bare-basename citation may resolve against.
_SEARCH_ROOTS = ("src", "tests", "scripts")
# How far the symbol may sit from the cited line before we call it drift.
_DRIFT_WINDOW = 30

# Mapped docs: the high-value set kept under the §6.3 contract.
# `active_models.yaml` is in-scope despite not being Markdown: it is the registry loaded FIRST in
# every session, so a stale pointer there misleads a session before it reads anything else. Its
# citations drifted undetected precisely because nothing scanned it (found 2026-07-22: 9 of 10 CRT
# `file_line` refs stale, two naming the wrong file after the state_identity extraction).
_MAPPED_DOCS: list[Path] = (
    [Path("CLAUDE.md"), Path("docs/current-findings.md"), Path("active_models.yaml")]
    + sorted(Path("docs/architecture").glob("*.md"))
    + sorted(Path("docs/reference").glob("*.md"))
    + sorted(Path("docs/topics").glob("*.md"))
)

# `path.py:LINE <middot> Symbol` - Symbol is the leading identifier only (stops at <, space, (...).
_CITATION_RE = re.compile(
    r"([\w./-]+\.py):(\d+)\s*·\s*([A-Za-z_]\w*)"
)


def _iter_citations():
    """Yield (doc, doc_lineno, path_str, code_line, symbol) for every dual-form citation."""
    for doc in _MAPPED_DOCS:
        if not doc.exists():
            continue
        for i, text in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            for m in _CITATION_RE.finditer(text):
                yield doc, i, m.group(1), int(m.group(2)), m.group(3)


def _resolve(path_str: str) -> list[Path]:
    """Resolve a citation path: full repo-relative path, else unique basename search."""
    if "/" in path_str:
        p = Path(path_str)
        return [p] if p.exists() else []
    hits: list[Path] = []
    for root in _SEARCH_ROOTS:
        hits.extend(Path(root).rglob(path_str))
    return sorted(set(hits))


def test_mapped_docs_exist() -> None:
    assert Path("CLAUDE.md").exists(), "CLAUDE.md missing"
    assert Path("docs/current-findings.md").exists(), "docs/current-findings.md missing"
    assert Path("active_models.yaml").exists(), "active_models.yaml missing"


def test_active_models_citations_are_covered() -> None:
    """The registry must carry dual-form citations, or its coverage is silently zero.

    Adding a file to _MAPPED_DOCS does nothing unless its refs use the `path:line · Symbol`
    form the regex matches — legacy `path:line  # symbol` comments would pass by never matching.
    This pins the coverage so the guard cannot be hollowed out by reverting the form.
    """
    reg = Path("active_models.yaml")
    found = sum(1 for doc, *_ in _iter_citations() if doc == reg)
    assert found >= 15, (
        f"active_models.yaml has only {found} dual-form `path:line · Symbol` citations; "
        "legacy `path:line  # symbol` refs are NOT checked — upgrade them when touched"
    )


def test_every_code_citation_resolves() -> None:
    """Each `path:line · Symbol` citation resolves to a real file + symbol near the line."""
    problems: list[str] = []
    seen = 0
    for doc, doc_ln, path_str, code_ln, symbol in _iter_citations():
        seen += 1
        where = f"{doc}:{doc_ln}  ->  {path_str}:{code_ln} · {symbol}"
        matches = _resolve(path_str)
        if not matches:
            problems.append(f"{where}  [FILE NOT FOUND]")
            continue
        if len(matches) > 1:
            problems.append(f"{where}  [AMBIGUOUS: {[str(m) for m in matches]}]")
            continue
        lines = matches[0].read_text(encoding="utf-8").splitlines()
        if symbol not in "\n".join(lines):
            problems.append(f"{where}  [SYMBOL ABSENT from {matches[0]}]")
            continue
        if code_ln < 1 or code_ln > len(lines):
            problems.append(f"{where}  [LINE {code_ln} out of range 1..{len(lines)}]")
            continue
        lo = max(0, code_ln - 1 - _DRIFT_WINDOW)
        hi = min(len(lines), code_ln - 1 + _DRIFT_WINDOW + 1)
        if not any(symbol in lines[k] for k in range(lo, hi)):
            actual = [k + 1 for k, ln in enumerate(lines) if symbol in ln]
            problems.append(
                f"{where}  [DRIFT: symbol not within +-{_DRIFT_WINDOW} lines; found at {actual}]"
            )
    assert not problems, "Stale/broken code citations (CLAUDE.md §6.3):\n" + "\n".join(problems)
    # Guard: the contract is meaningless if the regex stops matching anything.
    assert seen > 0, "no dual-form `path:line · Symbol` citations found in mapped docs"
