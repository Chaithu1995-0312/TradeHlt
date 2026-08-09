"""Session-log structural floor — the enforceable shell for the Persistent Logging Mandate.

Mirrors tests/test_current_findings.py (read-a-doc-and-assert). Enforces the *timeless
structural* contract of CLAUDE.md §6 / §7.4 on `assistant_project.md`: every `📝 SESSION LOG
ENTRY` block is well-formed (dated + carries its core fields), so a truncated, headerless, or
field-dropped entry fails CI instead of silently breaking the audit trail.

Scope note (the shell, not the semantics — CLAUDE.md §6.1):
  - This checks that an entry HAS its fields, never that the content is *true* or the
    `Belief Update` reasoning is *sound* — that residual is irreducible and stays doctrine.
  - It deliberately does NOT require the `Belief Update / ROI / Goal` field on every block.
    That field is a FORWARD mandate introduced after most historical entries; retroactive
    enforcement would just go red on history. The forward "every code-changing commit ships a
    belief line" contract belongs in the per-commit hook (plan item 4), which can gate NEW
    entries without rewriting the permanent record.
"""
from __future__ import annotations

import re
from pathlib import Path

_LOG = Path("assistant_project.md")

# Entries are delimited by the marker line; a block runs to the next marker (or EOF).
# Must be anchored to a standalone line — the marker also appears mid-prose inside entries
# that discuss the logging mandate itself, and a substring split would shred those.
_MARKER = "📝 SESSION LOG ENTRY"
_MARKER_RE = re.compile(r"^📝 SESSION LOG ENTRY[ \t]*$", re.MULTILINE)

# Core fields every entry has carried since April 2026 (Belief Update is intentionally absent —
# see module docstring). Date is validated separately for its YYYY-MM-DD prefix.
_CORE_FIELDS = ("Date", "Topic", "Decision/Output", "Open Questions", "Next Step")

# Date line: any of the historical time-formats (T..Z, +05:30, " IST", bare), but the value
# must START with an ISO calendar date. No trailing \b — `2026-05-28T...` is digit→`T` (no
# word boundary), so \b would spuriously reject the most common format.
_DATE_LINE_RE = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def _blocks() -> list[str]:
    """Return the text of every SESSION LOG ENTRY block, split on standalone marker lines."""
    text = _LOG.read_text(encoding="utf-8")
    starts = [m.start() for m in _MARKER_RE.finditer(text)]
    return [text[s : (starts[i + 1] if i + 1 < len(starts) else len(text))]
            for i, s in enumerate(starts)]


def _has_field(block: str, name: str) -> bool:
    return re.search(rf"^{re.escape(name)}:", block, re.MULTILINE) is not None


def test_session_log_exists_and_is_doctrine_headed() -> None:
    assert _LOG.exists(), "assistant_project.md (the persistent session log) is missing"
    text = _LOG.read_text(encoding="utf-8")
    assert "ARCHITECTURE MIGRATION DOCTRINE" in text, (
        "assistant_project.md missing its top doctrine block (CLAUDE.md §6)"
    )
    assert _MARKER in text, "assistant_project.md contains no 📝 SESSION LOG ENTRY blocks"


def test_every_entry_has_core_fields() -> None:
    """Each entry carries Date/Topic/Decision/Open Questions/Next Step (the structural floor)."""
    problems: list[str] = []
    for i, block in enumerate(_blocks(), start=1):
        missing = [f for f in _CORE_FIELDS if not _has_field(block, f)]
        if missing:
            head = block.strip().splitlines()[0] if block.strip() else "<empty>"
            problems.append(f"entry #{i} ({head[:60]!r}): missing field(s) {missing}")
    assert not problems, (
        "malformed SESSION LOG entries (CLAUDE.md §6 / §7.4):\n" + "\n".join(problems)
    )


def test_session_log_entry_count_is_bounded() -> None:
    """The live log stays bounded — enforces the #3 context-ceiling fix (rotation).

    Old entries are spilled to docs/analysis/session-log-archive/ by
    scripts/maintenance/rotate_session_log.py; the hot file keeps only the newest ~20.
    """
    n = len(_blocks())
    assert n <= 30, (
        f"{n} SESSION LOG entries in {_LOG} exceeds the cap (rotation keeps ~20). "
        "Run: python scripts/maintenance/rotate_session_log.py"
    )


def test_no_corrupted_markers() -> None:
    """No emoji-corrupted '?? SESSION LOG ENTRY' markers (cp1252 round-trip damage).

    These hide from _blocks() (which matches only the canonical 📝 marker), so a corrupted
    entry would silently escape every other check. rotate_session_log.py repairs them to 📝.
    """
    bad = [i for i, ln in enumerate(_LOG.read_text(encoding="utf-8").splitlines(), 1)
           if ln.strip() == "?? SESSION LOG ENTRY"]
    assert not bad, (
        f"corrupted '?? SESSION LOG ENTRY' markers at line(s) {bad} — repair to '📝' "
        "(scripts/maintenance/rotate_session_log.py does this)."
    )


def test_every_entry_is_dated_iso() -> None:
    """Each entry's Date line starts with a YYYY-MM-DD calendar date (any time-format suffix)."""
    problems: list[str] = []
    for i, block in enumerate(_blocks(), start=1):
        if not _DATE_LINE_RE.search(block):
            m = re.search(r"^Date:.*$", block, re.MULTILINE)
            problems.append(f"entry #{i}: Date line {m.group(0) if m else '<absent>'!r} not YYYY-MM-DD")
    assert not problems, "SESSION LOG entries with a non-ISO Date:\n" + "\n".join(problems)
