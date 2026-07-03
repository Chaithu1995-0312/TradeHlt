"""active_models.yaml v2.1 reachability — citation-class reference-resolution floor.

Classification (conventions.md §9 Executable-Invariant Scope Policy): this is NOT a semantic
YAML↔code invariant (that scope stays test_crt_state_invariants.py only). It is the sibling of
tests/test_doc_citations.py / tests/test_framework_registry.py: every pointer the v2.1
`reachability` / `optimization` / `evidence.conflicts` / `evidence.hypotheses` blocks declare
must RESOLVE (paths exist, F-ids/H-ids/framework-ids are registered, event types are real).
Nothing volatile is pinned. Drift evidence for why pointer rot matters: F-041.

Plus the §6.5 negative guard: no promotion/threshold field can enter an `optimization` block —
the registry describes tunability, it never grants authority.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from events.event_fabric import EventType
from governance.framework_registry import valid_finding_ids

_REPO = Path(__file__).resolve().parents[1]
_YAML = _REPO / "active_models.yaml"
_NON_MODEL_KEYS = {"meta", "philosophy"}

_HYP_SEED = _REPO / "scripts" / "governance" / "seed_hypothesis_registry.py"
_HYP_PATH = _REPO / "data" / "hypothesis_registry.jsonl"
_FRAME_SEED = _REPO / "scripts" / "governance" / "seed_framework_registry.py"
_FRAME_PATH = _REPO / "data" / "framework_registry.jsonl"

# §6.5 authority-creep regression: these key patterns may never appear inside `optimization`.
_AUTHORITY_CREEP_RE = re.compile(r"promotion_requirements|min_delta|threshold", re.IGNORECASE)


@pytest.fixture(scope="module", autouse=True)
def _ensure_registries_seeded() -> None:
    """data/ is gitignored — reseed both sibling registries deterministically if absent."""
    for path, seed in ((_HYP_PATH, _HYP_SEED), (_FRAME_PATH, _FRAME_SEED)):
        if not path.exists():
            subprocess.run([sys.executable, str(seed)], check=True, cwd=_REPO)
        assert path.exists(), f"seed failed to produce {path}"


@pytest.fixture(scope="module")
def doc() -> dict:
    return yaml.safe_load(_YAML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def models(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in _NON_MODEL_KEYS}


def _jsonl_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as fh:
        return {json.loads(line)["id"] for line in fh if line.strip()}


def test_schema_version_and_layers(doc: dict) -> None:
    assert doc["meta"]["schema_version"] == 2.1
    assert doc["meta"]["truth_schema"]["canonical_layers"] == ["intent", "runtime", "evidence", "status"]
    assert doc["meta"]["truth_schema"]["version"] == 2.0, (
        "the truth-LAYER schema stays 2.0 — v2.1 is a file-format bump only (conventions.md §9)"
    )


def test_finding_ids_resolve(doc: dict, models: dict) -> None:
    """Every F-id in evidence.findings / evidence.conflicts / philosophy.authority.findings exists."""
    known = valid_finding_ids(_REPO / "docs" / "current-findings.md")
    assert known, "no F-NNN ids parsed from docs/current-findings.md"
    problems: list[str] = []
    cited: list[tuple[str, list]] = [
        (name, (entry.get("evidence") or {}).get(key) or [])
        for name, entry in models.items()
        for key in ("findings", "conflicts")
    ]
    cited.append(("philosophy", doc["philosophy"]["authority"].get("findings") or []))
    for name, fids in cited:
        problems.extend(f"{name}: unknown finding {fid}" for fid in fids if fid not in known)
    assert not problems, "\n".join(problems)


def test_hypothesis_ids_resolve(models: dict) -> None:
    """Every H-id in evidence.hypotheses exists in data/hypothesis_registry.jsonl (reseeded)."""
    known = _jsonl_ids(_HYP_PATH)
    problems = [
        f"{name}: unknown hypothesis {hid}"
        for name, entry in models.items()
        for hid in (entry.get("evidence") or {}).get("hypotheses") or []
        if hid not in known
    ]
    assert not problems, "\n".join(problems)


def test_machine_readable_sources_resolve(doc: dict) -> None:
    """meta.machine_readable_sources: generator + guard exist; path exists (post-reseed for data/)."""
    sources = doc["meta"]["machine_readable_sources"]
    assert sources, "meta.machine_readable_sources is empty"
    problems: list[str] = []
    for name, src in sources.items():
        for key in ("generator", "guard"):
            if not (_REPO / src[key]).exists():
                problems.append(f"{name}.{key}: missing {src[key]}")
        artifact = _REPO / src["path"]
        if not artifact.exists() and name != "findings_export":
            problems.append(f"{name}.path: missing {src['path']} (reseed fixture should have made it)")
        if name == "findings_export" and not artifact.exists():
            subprocess.run([sys.executable, str(_REPO / src["generator"])], check=True, cwd=_REPO)
            if not artifact.exists():
                problems.append(f"{name}.path: generator did not produce {src['path']}")
    assert not problems, "\n".join(problems)


def test_reachability_paths_resolve(models: dict) -> None:
    """Every reachability tests/topics path and telemetry emitter exists from repo root."""
    problems: list[str] = []
    for name, entry in models.items():
        reach = entry.get("reachability")
        if reach is None:
            problems.append(f"{name}: missing v2.1 reachability block")
            continue
        for key in ("tests", "topics"):
            for p in reach.get(key) or []:
                if not (_REPO / p).exists():
                    problems.append(f"{name}.reachability.{key}: missing {p}")
        for t in reach.get("telemetry") or []:
            if not (_REPO / t["emitter"]).exists():
                problems.append(f"{name}: telemetry emitter missing {t['emitter']}")
    assert not problems, "\n".join(problems)


def test_telemetry_semantic_contract(models: dict) -> None:
    """event_type is a real EventType; stream basename appears in the emitter source; the schema
    anchor's doc exists and carries the referenced §9 heading; purpose is non-empty.
    (Citation-class only — llm_questions content is deliberately NOT pinned.)"""
    valid_types = {e.value for e in EventType}
    problems: list[str] = []
    for name, entry in models.items():
        for t in (entry.get("reachability") or {}).get("telemetry") or []:
            if t["event_type"] not in valid_types:
                problems.append(f"{name}: {t['event_type']} not an EventType member")
            emitter = _REPO / t["emitter"]
            if emitter.exists():
                basename = Path(t["stream"]).name
                if basename not in emitter.read_text(encoding="utf-8"):
                    problems.append(f"{name}: stream {basename} not referenced in {t['emitter']}")
            doc_path, _, anchor = t["schema"].partition("#")
            schema_doc = _REPO / doc_path
            if not schema_doc.exists():
                problems.append(f"{name}: schema doc missing {doc_path}")
            elif anchor.startswith("94") and "### 9.4" not in schema_doc.read_text(encoding="utf-8"):
                problems.append(f"{name}: schema anchor §9.4 heading absent from {doc_path}")
            if not (t.get("purpose") or "").strip():
                problems.append(f"{name}: telemetry {t['event_type']} has empty purpose")
    assert not problems, "\n".join(problems)


def test_config_sections_are_active_config_keys(models: dict) -> None:
    """Every reachability/optimization config_sections entry is a top-level key of the config
    named by configs/production/ACTIVE_VERSION (branch-scoped truth, CLAUDE.md §4.0)."""
    version = (_REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    cfg = json.loads((_REPO / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    for name, entry in models.items():
        for block in ("reachability", "optimization"):
            for section in (entry.get(block) or {}).get("config_sections") or []:
                if section not in cfg:
                    problems.append(f"{name}.{block}: {section!r} not a top-level key of {version}.json")
    assert not problems, "\n".join(problems)


def test_optimization_is_descriptive_only(models: dict) -> None:
    """§6.5 floor: authority disclaims, cites §6.5, and NO promotion/threshold key exists in the
    block (authority-creep regression); promotion_standard points at the M4 gate + PromotionManager."""
    problems: list[str] = []
    for name, entry in models.items():
        opt = entry.get("optimization")
        if opt is None:
            problems.append(f"{name}: missing v2.1 optimization block")
            continue
        authority = opt.get("authority", "")
        if not authority.startswith("none") or "§6.5" not in authority:
            problems.append(f"{name}: optimization.authority must start 'none' and cite §6.5")
        creep = [k for k in opt if _AUTHORITY_CREEP_RE.search(k)]
        if creep:
            problems.append(f"{name}: authority-creep keys in optimization: {creep}")
        std = opt.get("promotion_standard") or {}
        for role, expected in (("research", "src/research/qualification.py"),
                               ("production", "src/governance/promotion_manager.py")):
            if std.get(role) != expected:
                problems.append(f"{name}: promotion_standard.{role} must be {expected}")
            elif not (_REPO / expected).exists():
                problems.append(f"{name}: promotion_standard.{role} path missing: {expected}")
    assert not problems, "\n".join(problems)


def test_framework_ids_resolve(models: dict) -> None:
    """Every reachability.framework_ids entry exists in data/framework_registry.jsonl (reseeded)."""
    known = _jsonl_ids(_FRAME_PATH)
    problems = [
        f"{name}: unknown framework id {fid}"
        for name, entry in models.items()
        for fid in (entry.get("reachability") or {}).get("framework_ids") or []
        if fid not in known
    ]
    assert not problems, "\n".join(problems)
