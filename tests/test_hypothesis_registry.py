"""Hypothesis Registry alignment — the enforceable floor for the research-hypothesis ledger.

Mirrors tests/test_framework_registry.py (sibling registry, same seed-script committed-truth
pattern) against the schema + contract in docs/reference/schemas.md §9.6.

Contract tests: loads-valid · findings-exist · models-exist · code-hypotheses-exist ·
paths-resolve · unique-ids · authority-pinned · append-only-immutable.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from governance.hypothesis_registry import AUTHORITY, STATUS_ENUM, HypothesisRegistry
from governance.framework_registry import valid_finding_ids
from utils.jsonl_writer import read_jsonl

_REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = _REPO / "data" / "hypothesis_registry.jsonl"
_SEED = _REPO / "scripts" / "governance" / "seed_hypothesis_registry.py"
_ACTIVE_MODELS = _REPO / "active_models.yaml"

# Cross-cutting active_models.yaml keys that are not model entries.
_NON_MODEL_KEYS = {"meta", "philosophy"}


@pytest.fixture(scope="module", autouse=True)
def _ensure_seeded() -> None:
    """data/ is gitignored — a fresh checkout has no registry; reseed deterministically."""
    if not REGISTRY_PATH.exists():
        subprocess.run([sys.executable, str(_SEED)], check=True, cwd=_REPO)
    assert REGISTRY_PATH.exists(), f"seed failed to produce {REGISTRY_PATH}"


@pytest.fixture(scope="module")
def raw_lines() -> list[dict]:
    return read_jsonl(REGISTRY_PATH)


@pytest.fixture(scope="module")
def registry() -> HypothesisRegistry:
    reg = HypothesisRegistry()
    reg.load(REGISTRY_PATH)
    return reg


def test_registry_loads_valid_jsonl(raw_lines: list[dict]) -> None:
    """Every line parses and passes the closed-schema/enum/authority contract."""
    assert raw_lines, "hypothesis registry is empty"
    for rec in raw_lines:
        HypothesisRegistry.validate_record(rec)  # raises on violation


def test_every_finding_exists(registry: HypothesisRegistry) -> None:
    """Every findings[] id is a real F-NNN in docs/current-findings.md."""
    errors = registry.validate_findings(_REPO / "docs" / "current-findings.md")
    assert not errors, "finding problems:\n" + "\n".join(str(e) for e in errors)
    assert valid_finding_ids(_REPO / "docs" / "current-findings.md"), (
        "no F-NNN ids parsed from docs/current-findings.md"
    )


def test_every_model_exists(registry: HypothesisRegistry) -> None:
    """Every models[] entry is a top-level active_models.yaml model key."""
    doc = yaml.safe_load(_ACTIVE_MODELS.read_text(encoding="utf-8"))
    known = set(doc) - _NON_MODEL_KEYS
    errors = registry.validate_models(known)
    assert not errors, "model problems:\n" + "\n".join(str(e) for e in errors)


def test_every_code_hypothesis_exists(registry: HypothesisRegistry) -> None:
    """Every code_hypotheses[] name is registered in the research HYPOTHESIS_REGISTRY."""
    import research.controls  # noqa: F401 — registration side effect
    import research.hypotheses  # noqa: F401
    from research.registry import HYPOTHESIS_REGISTRY

    problems = [
        f"{r['id']}: unknown code hypothesis {name!r}"
        for r in registry.records
        for name in r.get("code_hypotheses") or []
        if name not in HYPOTHESIS_REGISTRY
    ]
    assert not problems, "\n".join(problems)


def test_program_and_evidence_paths_resolve(registry: HypothesisRegistry) -> None:
    """Every programs[] path and evidence[].path exists on disk (repo root)."""
    import os

    os.chdir(_REPO)  # validate_paths resolves relative to cwd
    errors = registry.validate_paths()
    assert not errors, "path problems:\n" + "\n".join(str(e) for e in errors)


def test_unique_ids(raw_lines: list[dict]) -> None:
    ids = [r["id"] for r in raw_lines]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate ids in registry: {dupes}"


def test_authority_is_pinned_and_status_in_enum(raw_lines: list[dict]) -> None:
    """§6.5 floor: authority is the pinned research literal; status vocabulary is closed."""
    for rec in raw_lines:
        assert rec["authority"] == AUTHORITY, f"{rec['id']}: authority {rec['authority']!r}"
        assert rec["status"] in STATUS_ENUM, f"{rec['id']}: status {rec['status']!r}"


def test_schema_rejects_authority_creep() -> None:
    """The closed schema refuses promotion/threshold fields (§6.5 negative guard)."""
    base = {
        "id": "H-999", "statement": "x", "family": None, "status": "open",
        "authority": "research", "findings": [], "models": [], "code_hypotheses": [],
        "programs": [], "evidence": [], "created": "2026-07-03T00:00:00Z",
        "last_validated": "2026-07-03T00:00:00Z", "notes": "",
    }
    HypothesisRegistry.validate_record(base)  # sanity: the base record is valid
    for creep in ("promotion_requirements", "min_delta_g001", "threshold"):
        with pytest.raises(ValueError, match="unknown keys"):
            HypothesisRegistry.validate_record(dict(base, **{creep: 0.1}))
    with pytest.raises(ValueError, match="authority"):
        HypothesisRegistry.validate_record(dict(base, authority="production"))


def test_append_only_immutable(tmp_path: Path) -> None:
    """Appending a line leaves all prior lines byte-identical (append-only ledger)."""
    f = tmp_path / "hyp.jsonl"
    base = {
        "id": "H-001", "statement": "seed", "family": None, "status": "open",
        "authority": "research", "findings": [], "models": [], "code_hypotheses": [],
        "programs": [], "evidence": [], "created": "2026-07-03T00:00:00Z",
        "last_validated": "2026-07-03T00:00:00Z", "notes": "",
    }
    HypothesisRegistry.dump(f, [base])
    before = f.read_text(encoding="utf-8")

    reg = HypothesisRegistry(f)
    reg.load()
    reg.append(dict(base, id="H-002", statement="second"))

    after = f.read_text(encoding="utf-8")
    assert after.startswith(before), "append mutated existing lines"
    assert json.loads(after.splitlines()[-1])["id"] == "H-002"
    assert reg.load() == 2
