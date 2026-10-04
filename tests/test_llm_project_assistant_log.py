"""Workflow-log structural floor — mirrors tests/test_session_log.py for the multi-LLM log.

Enforces the *structural* contract of CLAUDE.md §6 "Two logs" on `llm_project_assistant.md`
(the workflow/coordination log): the doctrine header is present and every `📝 SESSION LOG ENTRY`
block is well-formed (dated + core fields) and bounded. Structure only, never semantics.
"""
from __future__ import annotations

import re
from pathlib import Path

_LOG = Path("llm_project_assistant.md")

_MARKER = "📝 SESSION LOG ENTRY"
_MARKER_RE = re.compile(r"^📝 SESSION LOG ENTRY[ \t]*$", re.MULTILINE)
_CORE_FIELDS = ("Date", "Topic", "Decision/Output", "Open Questions", "Next Step")
_DATE_LINE_RE = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def _blocks() -> list[str]:
    text = _LOG.read_text(encoding="utf-8")
    starts = [m.start() for m in _MARKER_RE.finditer(text)]
    return [text[s : (starts[i + 1] if i + 1 < len(starts) else len(text))]
            for i, s in enumerate(starts)]


def _has_field(block: str, name: str) -> bool:
    return re.search(rf"^{re.escape(name)}:", block, re.MULTILINE) is not None


def test_workflow_log_exists_and_is_doctrine_headed() -> None:
    assert _LOG.exists(), "llm_project_assistant.md (the workflow log) is missing"
    text = _LOG.read_text(encoding="utf-8")
    assert "MULTI-LLM WORKFLOW LOG" in text, (
        "llm_project_assistant.md missing its top doctrine block (CLAUDE.md §6 Two-logs)"
    )
    assert _MARKER in text, "llm_project_assistant.md contains no 📝 SESSION LOG ENTRY blocks"


def test_every_entry_has_core_fields() -> None:
    problems: list[str] = []
    for i, block in enumerate(_blocks(), start=1):
        missing = [f for f in _CORE_FIELDS if not _has_field(block, f)]
        if missing:
            head = block.strip().splitlines()[0] if block.strip() else "<empty>"
            problems.append(f"entry #{i} ({head[:60]!r}): missing field(s) {missing}")
    assert not problems, "malformed workflow-log entries (CLAUDE.md §6):\n" + "\n".join(problems)


def test_every_entry_has_iso_date() -> None:
    for i, block in enumerate(_blocks(), start=1):
        assert _DATE_LINE_RE.search(block), f"workflow-log entry #{i} missing ISO Date:"


def test_entry_count_is_bounded() -> None:
    n = len(_blocks())
    assert n <= 30, (
        f"{n} entries in {_LOG} exceeds the cap. "
        "Run: python scripts/maintenance/rotate_session_log.py --file llm_project_assistant.md"
    )
