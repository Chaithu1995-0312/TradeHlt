"""Topic-doc alignment — the enforceable floor for the topic-visibility layer.

Mirrors tests/test_control_plane_doc_alignment.py: read-a-doc-and-assert. Checks only the
mechanical contract (date header + required section headings) per CLAUDE.md §6.1 — it does NOT
verify that the narrated code matches the source (that's the per-response Sync mandate's job).
"""
from __future__ import annotations

import re
from pathlib import Path

_TOPICS_DIR = Path("docs/topics")
_EXCLUDE = {"readme.md", "_template.md"}

_UPDATED_RE = re.compile(r"Updated:\s*\d{4}-\d{2}-\d{2}")
_CREATED_RE = re.compile(r"Created:\s*\d{4}-\d{2}-\d{2}")

# Section headings every topic doc must carry (from docs/topics/_template.md).
_REQUIRED_SECTIONS = (
    "## In plain language",
    "## Code covered",
    "## Ins / Outs",
    "## Entry points & validations",
    "## Tests",
    "## Fits in architecture",
    "## Discussion",
)


def _topic_docs() -> list[Path]:
    return sorted(p for p in _TOPICS_DIR.glob("*.md") if p.name not in _EXCLUDE)


def test_topics_dir_exists_with_index_and_template() -> None:
    assert (_TOPICS_DIR / "readme.md").exists(), "docs/topics/readme.md (the index) is missing"
    assert (_TOPICS_DIR / "_template.md").exists(), "docs/topics/_template.md is missing"


def test_every_topic_doc_is_dated() -> None:
    docs = _topic_docs()
    assert docs, "no topic docs found under docs/topics/ (besides readme/_template)"
    undated = [
        p.name
        for p in docs
        if not (_CREATED_RE.search(t := p.read_text(encoding="utf-8")) and _UPDATED_RE.search(t))
    ]
    assert not undated, f"topic docs missing a 'Created:'/'Updated: YYYY-MM-DD' header: {undated}"


def test_every_topic_doc_has_required_sections() -> None:
    for p in _topic_docs():
        text = p.read_text(encoding="utf-8")
        missing = [h for h in _REQUIRED_SECTIONS if h not in text]
        assert not missing, f"{p.name} missing required section headings: {missing}"
