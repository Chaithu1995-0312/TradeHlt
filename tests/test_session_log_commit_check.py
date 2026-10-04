"""Unit tests for the commit-linkage guard (scripts/maintenance/check_session_log_commit.py).

Exercises the git-free decision core: which changes require a log, the [nolog] escape, and the
same-day well-formed-entry requirement. No git, no real commit — pure functions only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SRC = Path("scripts/maintenance/check_session_log_commit.py")
_spec = importlib.util.spec_from_file_location("check_session_log_commit", _SRC)
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

_TODAY = "2026-06-13"

_GOOD_ENTRY = (
    "📝 SESSION LOG ENTRY\n"
    f"Date: {_TODAY}\n"
    "Topic: did a governed thing\n"
    "Decision/Output: wired X into Y\n"
    "Belief Update / ROI / Goal: none\n"
    "Open Questions: none\n"
    "Next Step: ship it\n"
)


def test_requires_log_only_for_governed_paths() -> None:
    assert chk.requires_log(["src/core/engine_runner.py"])
    assert chk.requires_log(["configs/production/v2_multi_2026_04.json"])
    assert chk.requires_log(["src\\core\\engine_runner.py"])  # backslash normalized
    assert not chk.requires_log(["docs/current-findings.md", "README.md"])
    assert not chk.requires_log(["tests/test_session_log.py", "scripts/maintenance/x.py"])
    assert not chk.requires_log([])


def test_nolog_escape_detection() -> None:
    assert chk.has_nolog_escape("chore: rename var [nolog]")
    assert chk.has_nolog_escape("fix [NOLOG] trivial")
    assert not chk.has_nolog_escape("feat: real change with a belief")


def test_valid_today_entry_requires_today_and_core_fields() -> None:
    assert chk.has_valid_today_entry(_GOOD_ENTRY, _TODAY)
    # Right shape but yesterday's date → not valid for today.
    assert not chk.has_valid_today_entry(_GOOD_ENTRY.replace(_TODAY, "2026-06-12"), _TODAY)
    # Today but missing Next Step → malformed.
    missing = _GOOD_ENTRY.replace("Next Step: ship it\n", "")
    assert not chk.has_valid_today_entry(missing, _TODAY)
    # Marker mentioned mid-prose must not count as an entry.
    prose = "Decision/Output: discussed the 📝 SESSION LOG ENTRY format inline\n"
    assert not chk.has_valid_today_entry(prose, _TODAY)


def test_check_decision_matrix() -> None:
    governed = ["src/core/engine_runner.py"]
    docs_only = ["docs/x.md"]

    # governed + no today entry → BLOCK
    ok, _ = chk.check(governed, "feat: change", "", _TODAY)
    assert not ok
    # governed + today entry → ALLOW
    ok, _ = chk.check(governed, "feat: change", _GOOD_ENTRY, _TODAY)
    assert ok
    # governed + [nolog] → ALLOW even without entry
    ok, reason = chk.check(governed, "chore: trivial [nolog]", "", _TODAY)
    assert ok and "nolog" in reason.lower()
    # non-governed → ALLOW regardless
    ok, _ = chk.check(docs_only, "docs: tweak", "", _TODAY)
    assert ok
