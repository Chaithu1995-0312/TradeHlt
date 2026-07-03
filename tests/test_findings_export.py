"""Findings export contract — data/findings.jsonl is a faithful GENERATED derived view.

Mirrors tests/test_context_compiler.py (build-twice determinism, GENERATED-not-hand-edited
guard) for the machine-readable findings export (CLAUDE.md §6.2 derived-view rule):
docs/current-findings.md stays the single authoritative store; this floor proves the JSONL
never drifts from it and was never hand-edited.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from governance.findings_export import META_LINE, parse_findings, render

_REPO = Path(__file__).resolve().parents[1]
_FINDINGS_DOC = _REPO / "docs" / "current-findings.md"
_EXPORT_PATH = _REPO / "data" / "findings.jsonl"
_EXPORT_SCRIPT = _REPO / "scripts" / "governance" / "export_findings.py"

# The full-doc id census (terminal included) — same regex family as valid_finding_ids.
_ALL_IDS_RE = re.compile(r"^###\s+(F-\d{3})\b", re.MULTILINE)


@pytest.fixture(scope="module", autouse=True)
def _ensure_exported() -> None:
    """data/ is gitignored — a fresh checkout has no export; regenerate deterministically."""
    if not _EXPORT_PATH.exists():
        subprocess.run([sys.executable, str(_EXPORT_SCRIPT)], check=True, cwd=_REPO)
    assert _EXPORT_PATH.exists(), f"export failed to produce {_EXPORT_PATH}"


@pytest.fixture(scope="module")
def records() -> list[dict]:
    return parse_findings(_FINDINGS_DOC)


def test_render_is_deterministic(records: list[dict]) -> None:
    """Parsing + rendering twice is byte-identical (no timestamps, stable ordering)."""
    again = render(parse_findings(_FINDINGS_DOC))
    assert render(records) == again, "two renders of an unchanged doc differ"


def test_every_finding_exported_exactly_once(records: list[dict]) -> None:
    """The export covers every ### F-NNN block in the doc, once each, count-matched."""
    doc_ids = _ALL_IDS_RE.findall(
        _FINDINGS_DOC.read_text(encoding="utf-8").split("## Schema", 1)[-1]
    )
    doc_ids = [fid for fid in doc_ids if fid != "F-NNN"]  # the schema example block
    exported = [r["id"] for r in records]
    assert sorted(exported) == sorted(doc_ids), (
        f"export/doc id mismatch: only-in-doc={sorted(set(doc_ids) - set(exported))}, "
        f"only-in-export={sorted(set(exported) - set(doc_ids))}"
    )
    assert len(exported) == len(set(exported)), "duplicate finding ids in export"


def test_meta_line_identifies_the_generator() -> None:
    first = json.loads(_EXPORT_PATH.read_text(encoding="utf-8").splitlines()[0])
    assert first == META_LINE
    assert first["kind"] == "meta" and first["generated_by"].endswith("export_findings.py")


def test_nonterminal_records_carry_evidence(records: list[dict]) -> None:
    """Fidelity floor: every non-terminal finding has the doc's non-empty Evidence."""
    missing = [r["id"] for r in records if not r["terminal"] and not r["evidence"]]
    assert not missing, f"non-terminal findings exported without evidence: {missing}"


def test_on_disk_export_is_not_hand_edited(records: list[dict]) -> None:
    """The GENERATED guard: the on-disk file equals a fresh render of the current doc."""
    assert _EXPORT_PATH.read_text(encoding="utf-8") == render(records), (
        "data/findings.jsonl differs from a fresh render — it was hand-edited or is stale; "
        "regenerate via: python scripts/governance/export_findings.py (§6.2: never hand-edit)"
    )
