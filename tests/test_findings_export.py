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

from governance.findings_export import _FIELDS, META_LINE, parse_findings, render

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


_FIELD_LINE_RE = re.compile(r"^-\s+([A-Z][A-Za-z-]*):", re.MULTILINE)
_BLOCK_SPLIT_RE = re.compile(r"^###\s+F-\d{3}", re.MULTILINE)

#: A field carried by at least this share of finding blocks is STRUCTURAL — part of the doc's
#: schema rather than prose inside a Note/Evidence body (`Date:`/`Update:` appear in nested
#: sub-entries at ~27% and below, and are deliberately not exported).
_STRUCTURAL_SHARE = 0.5


def test_export_fields_cover_the_docs_structural_schema() -> None:
    """Every structural field in the findings doc survives into the GENERATED export.

    Regression floor for the gap the 2026-08-26 provenance audit hit: `Family:`/`Contract:`
    entered the doc with the 2026-08-06 measurement-contract work and were never added to
    `_FIELDS`, so `data/findings.jsonl` — named in CLAUDE.md §2 as a machine-readable truth
    artifact — could not answer "what measurement basis?" or "what research family?" at all.
    Nothing compared the two schemas, so the divergence was silent for 20 days.
    """
    text = _FINDINGS_DOC.read_text(encoding="utf-8")
    blocks = _BLOCK_SPLIT_RE.split(text)[1:]
    assert blocks, "no finding blocks parsed from the doc"

    counts: dict[str, int] = {}
    for block in blocks:
        for name in {m.group(1) for m in _FIELD_LINE_RE.finditer(block)}:
            counts[name] = counts.get(name, 0) + 1

    exported = {doc_name for doc_name, _ in _FIELDS}
    structural = {n for n, c in counts.items() if c >= _STRUCTURAL_SHARE * len(blocks)}

    missing = sorted(structural - exported)
    assert not missing, (
        "findings-doc fields carried by most findings but absent from findings_export._FIELDS: "
        + ", ".join(f"{n} ({counts[n]}/{len(blocks)} findings)" for n in missing)
    )

    phantom = sorted(exported - set(counts))
    assert not phantom, (
        "findings_export._FIELDS exports fields the doc never uses: " + ", ".join(phantom)
    )

