"""Framework Registry alignment — the enforceable floor for the architecture map.

Validates ``data/framework_registry.jsonl`` against the schema + contract in
``docs/reference/framework_registry_schema.md`` (CLAUDE.md §6.2). Mirrors the
read-a-file-and-assert shape of ``tests/test_current_findings.py`` /
``tests/test_doc_citations.py``; the validators it calls ARE the standing CI gate
(``query_registry.py --validate``).

The 8 contract tests (001_FRAMEWORK_REGISTRY.md §M0):
  loads-valid · evidence-paths-exist · findings-exist · no-dangling-parent ·
  no-dangling-child · level-matches-type · unique-ids · append-only-immutable.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from governance.framework_registry import FrameworkRegistry, valid_finding_ids
from utils.jsonl_writer import read_jsonl

_REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = _REPO / "data" / "framework_registry.jsonl"
_SEED = _REPO / "scripts" / "governance" / "seed_framework_registry.py"


@pytest.fixture(scope="module", autouse=True)
def _ensure_seeded() -> None:
    """data/ is gitignored, so a fresh checkout has no registry — reseed (deterministic) from
    current code. This also makes the validators run against HEAD, strengthening drift detection."""
    if not REGISTRY_PATH.exists():
        subprocess.run([sys.executable, str(_SEED)], check=True, cwd=_REPO)
    assert REGISTRY_PATH.exists(), f"seed failed to produce {REGISTRY_PATH}"


@pytest.fixture(scope="module")
def raw_lines() -> list[dict]:
    return read_jsonl(REGISTRY_PATH)


@pytest.fixture(scope="module")
def registry() -> FrameworkRegistry:
    reg = FrameworkRegistry()
    reg.load(REGISTRY_PATH)
    return reg


def test_registry_loads_valid_jsonl(raw_lines: list[dict]) -> None:
    """Every line parses and passes the schema/enum/level-binding contract."""
    assert raw_lines, "registry is empty"
    for rec in raw_lines:
        FrameworkRegistry.validate_record(rec)  # raises on violation


def test_every_evidence_path_exists(registry: FrameworkRegistry) -> None:
    """Every evidence path resolves; code-evidence symbol within the ±30-line window."""
    errors = registry.validate_evidence()
    assert not errors, "evidence problems:\n" + "\n".join(str(e) for e in errors)


def test_every_finding_exists(registry: FrameworkRegistry) -> None:
    """Every findings[] id is a real F-NNN in docs/current-findings.md."""
    errors = registry.validate_findings()
    assert not errors, "finding problems:\n" + "\n".join(str(e) for e in errors)
    # Guard: the check is meaningless if the findings doc can't be parsed.
    assert valid_finding_ids(), "no F-NNN ids parsed from docs/current-findings.md"


def test_no_dangling_parent(registry: FrameworkRegistry) -> None:
    bad = [e for e in registry.validate_links() if e.kind == "parent"]
    assert not bad, "dangling parents:\n" + "\n".join(str(e) for e in bad)


def test_no_dangling_child(registry: FrameworkRegistry) -> None:
    bad = [e for e in registry.validate_links() if e.kind == "child"]
    assert not bad, "dangling children:\n" + "\n".join(str(e) for e in bad)


def test_level_matches_type(raw_lines: list[dict]) -> None:
    """type=domain implies level=1, style→2, risk→5, etc. (validate_record enforces; assert here too)."""
    from governance.framework_registry import _TYPE_LEVEL

    for rec in raw_lines:
        bound = _TYPE_LEVEL.get(rec["type"])
        if bound is not None:
            assert rec["level"] == bound, (
                f"{rec['id']}: type {rec['type']} requires level {bound}, got {rec['level']}"
            )


def test_unique_ids(raw_lines: list[dict]) -> None:
    """No duplicate id across lines (latest-per-id load would silently mask dupes)."""
    ids = [r["id"] for r in raw_lines]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate ids in registry: {dupes}"


def test_append_only_immutable(tmp_path: Path) -> None:
    """Appending a line leaves all prior lines byte-identical (append-only ledger)."""
    f = tmp_path / "reg.jsonl"
    base = {
        "id": "DOMAIN-001", "type": "domain", "level": 1, "name": "CryptoSpot",
        "parent": None, "children": [], "evidence": [], "findings": [], "tests": [],
        "status": "implicit", "created": "2026-06-16T00:00:00Z",
        "last_validated": "2026-06-16T00:00:00Z", "notes": "seed",
    }
    FrameworkRegistry.dump(f, [base])
    before = f.read_text(encoding="utf-8")

    reg = FrameworkRegistry(f)
    reg.load()
    new = dict(base, id="STYLE-001", type="style", level=2, name="ReactionBased", parent="DOMAIN-001")
    reg.append(new)

    after = f.read_text(encoding="utf-8")
    assert after.startswith(before), "append mutated existing lines"
    assert json.loads(after.splitlines()[-1])["id"] == "STYLE-001"
    assert reg.load() == 2
