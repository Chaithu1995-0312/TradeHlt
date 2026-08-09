"""Gate-6 Construction Contract — adversarial floor.

Proves the protocol has TEETH: every bypass class FAILS validation, and valid representative changes
PASS. Unit-level (tmp manifests + monkeypatched git surfaces) so tests are deterministic and do not
depend on working-tree state.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "governance" / "construction_protocol.py"
_CONTRACTS = _REPO / "docs" / "governance" / "change_contracts.json"


def _load():
    spec = importlib.util.spec_from_file_location("construction_protocol", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def tool():
    return _load()


def _impact(tmp_path, **overrides):
    contracts = json.loads(_CONTRACTS.read_text(encoding="utf-8"))["change_classes"]
    classes = overrides.pop("change_classes", ["DERIVED_METRIC_CHANGE"])
    acked = sorted({c for cl in classes if cl in contracts for c in contracts[cl]["required_checks"]})
    m = {
        "change_id": "CH-TEST-001",
        "objective": "test",
        "change_classes": classes,
        "affected_files": ["src/features/derived_math.py"],
        "required_checks_ack": acked,
        "unknowns": [],
        "rollback_boundary": "single commit",
    }
    m.update(overrides)
    p = tmp_path / "impact.json"
    p.write_text(json.dumps(m), encoding="utf-8")
    return p


def _completion(tmp_path, tool, **overrides):
    m = {
        "change_id": "CH-TEST-001",
        "change_classes": overrides.pop("change_classes", ["DOCUMENTATION_ONLY"]),
        "declared_files": overrides.pop("declared_files", ["docs/topics/x.md"]),
        "checks_executed": ["tests/test_current_findings.py"],
        "repo_state_hash": overrides.pop("repo_state_hash", "PENDING"),
        "completion_status": overrides.pop("completion_status", "COMPLETE"),
    }
    m.update(overrides)
    p = tmp_path / "completion.json"
    p.write_text(json.dumps(m), encoding="utf-8")
    return p


# ── contracts registry sanity ────────────────────────────────────────────────

def test_contracts_registry_wellformed(tool):
    c = json.loads(_CONTRACTS.read_text(encoding="utf-8"))["change_classes"]
    assert len(c) == 13  # + SCRIPT_LIFECYCLE_CHANGE (SITS PR-3)
    assert "SCRIPT_LIFECYCLE_CHANGE" in c
    for name, spec in c.items():
        for f in ("description", "authorities_to_inspect", "artifacts_to_update",
                  "required_checks", "rollback_boundary", "completion_criteria"):
            assert spec.get(f), f"{name}: missing {f}"
    # every required pytest check must exist on disk (no typo'd enforcement)
    for name, spec in c.items():
        for chk in spec["required_checks"]:
            if chk.startswith("tests/"):
                assert (_REPO / chk).exists(), f"{name}: check target missing {chk}"
    sits = c["SCRIPT_LIFECYCLE_CHANGE"]
    assert "tests/test_script_registry.py" in sits["required_checks"]
    assert "tests/test_script_matrix_sync.py" in sits["required_checks"]


def test_construction_floor_targets_exist(tool):
    for t in tool.CONSTRUCTION_FLOOR:
        assert (_REPO / t).exists(), f"CONSTRUCTION_FLOOR target missing: {t}"


# ── adversarial: impact manifest ─────────────────────────────────────────────

def test_unknown_mandatory_field_blocks(tool, tmp_path):
    p = _impact(tmp_path, rollback_boundary="UNKNOWN")
    ok, problems = tool.validate_impact(p)
    assert not ok and any("UNKNOWN" in x for x in problems)


def test_unresolved_blocking_unknown_blocks(tool, tmp_path):
    p = _impact(tmp_path, unknowns=[{"question": "does X reach training?", "blocking": True}])
    ok, problems = tool.validate_impact(p)
    assert not ok and any("blocking unknown" in x for x in problems)


def test_unacknowledged_required_check_blocks(tool, tmp_path):
    p = _impact(tmp_path, required_checks_ack=[])
    ok, problems = tool.validate_impact(p)
    assert not ok and any("not acknowledged" in x for x in problems)


def test_unknown_change_class_blocks(tool, tmp_path):
    p = _impact(tmp_path, change_classes=["TOTALLY_NEW_CLASS"], required_checks_ack=[])
    ok, problems = tool.validate_impact(p)
    assert not ok and any("unknown change class" in x for x in problems)


def test_valid_impact_passes(tool, tmp_path):
    p = _impact(tmp_path)
    ok, problems = tool.validate_impact(p)
    assert ok, problems


# ── adversarial: completion manifest ─────────────────────────────────────────

def test_undeclared_governed_surface_fails(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_changed_files",
                        lambda: ["docs/topics/x.md", "src/engines/rogue_engine.py"])
    monkeypatch.setattr(tool, "_repo_state_hash", lambda: "abc+def")
    p = _completion(tmp_path, tool, repo_state_hash="abc+def")
    ok, problems, _d = tool.validate_completion(p, run_checks=False)
    assert not ok and any("UNDECLARED" in x for x in problems)


def test_script_declared_without_sits_floor_fails(tool, tmp_path, monkeypatch):
    """Belt-and-suspenders: declared scripts/**/*.py require test_script_registry floor."""
    monkeypatch.setattr(tool, "_changed_files", lambda: ["scripts/probes/new_probe.py"])
    monkeypatch.setattr(tool, "_repo_state_hash", lambda: "abc+def")
    p = _completion(
        tmp_path,
        tool,
        change_classes=["DOCUMENTATION_ONLY"],
        declared_files=["scripts/probes/new_probe.py", "docs/topics/x.md"],
        checks_executed=["tests/test_current_findings.py"],
        repo_state_hash="abc+def",
    )
    ok, problems, _d = tool.validate_completion(p, run_checks=False)
    assert not ok and any("test_script_registry" in x for x in problems)


def test_script_lifecycle_class_acks_sits_floor(tool, tmp_path, monkeypatch):
    """SCRIPT_LIFECYCLE_CHANGE required_checks include SITS floor → no belt fail."""
    monkeypatch.setattr(tool, "_changed_files", lambda: ["scripts/probes/new_probe.py"])
    monkeypatch.setattr(tool, "_repo_state_hash", lambda: "abc+def")
    p = _completion(
        tmp_path,
        tool,
        change_classes=["SCRIPT_LIFECYCLE_CHANGE"],
        declared_files=["scripts/probes/new_probe.py"],
        checks_executed=["tests/test_script_registry.py"],
        repo_state_hash="abc+def",
    )
    ok, problems, _d = tool.validate_completion(p, run_checks=False)
    assert ok, problems


def test_documentation_only_with_behavior_change_fails(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_changed_files", lambda: ["src/core/engine_runner.py"])
    monkeypatch.setattr(tool, "_repo_state_hash", lambda: "abc+def")
    p = _completion(tmp_path, tool, declared_files=["src/core/engine_runner.py"],
                    repo_state_hash="abc+def")
    ok, problems, _d = tool.validate_completion(p, run_checks=False)
    assert not ok and any("DOCUMENTATION_ONLY" in x for x in problems)


def test_stale_repo_hash_fails(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_changed_files", lambda: [])
    monkeypatch.setattr(tool, "_repo_state_hash", lambda: "NEW+HASH")
    p = _completion(tmp_path, tool, repo_state_hash="OLD+HASH")
    ok, problems, _d = tool.validate_completion(p, run_checks=False)
    assert not ok and any("stale" in x for x in problems)


def test_complete_claim_denied_when_validation_fails(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_changed_files", lambda: ["src/engines/rogue.py"])
    monkeypatch.setattr(tool, "_repo_state_hash", lambda: "h+h")
    p = _completion(tmp_path, tool, repo_state_hash="h+h", completion_status="COMPLETE")
    ok, problems, _d = tool.validate_completion(p, run_checks=False)
    assert not ok and any("mechanically DENIED" in x for x in problems)


def test_valid_documentation_only_passes(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_changed_files", lambda: ["docs/topics/x.md"])
    monkeypatch.setattr(tool, "_repo_state_hash", lambda: "h+h")
    p = _completion(tmp_path, tool, declared_files=["docs/topics/x.md"], repo_state_hash="h+h")
    ok, problems, _d = tool.validate_completion(p, run_checks=False)
    assert ok, problems


def test_missing_required_check_execution_fails(tool, tmp_path, monkeypatch):
    """A class whose required check FAILS at execution time cannot COMPLETE (never log-trusted)."""
    monkeypatch.setattr(tool, "_changed_files", lambda: [])
    monkeypatch.setattr(tool, "_repo_state_hash", lambda: "h+h")
    monkeypatch.setattr(tool, "_run_pytest", lambda targets: (False, "1 failed"))
    p = _completion(tmp_path, tool, change_classes=["DERIVED_METRIC_CHANGE"],
                    declared_files=[], repo_state_hash="h+h")
    ok, problems, _d = tool.validate_completion(p, run_checks=True)
    assert not ok and any("FAILED" in x for x in problems)


# ── the keystone bypass (B1) is closed: rogue formula → census-fresh floor ───

def test_rogue_formula_is_caught_by_fresh_census(tmp_path):
    """End-to-end teeth: a NEW geometry derivation in a scanned universe diverges the fresh census
    from the committed artifact (the exact condition test_geometry_census_is_fresh enforces)."""
    spec = importlib.util.spec_from_file_location(
        "geometry_census", _REPO / "scripts" / "analysis" / "geometry_census.py")
    gc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gc)
    rogue = "def rogue(open_, high, low, close):\n    my_edge = abs(close - open_) / (high - low)\n    return my_edge\n"
    occ = gc.scan_source(rogue, "src/engines/rogue_engine.py")
    derivs = [r for r in occ if r["derivation_id_or_null"]]
    assert derivs, "rogue local formula not detected by census scanner"
    committed = [json.loads(l) for l in
                 (_REPO / "docs/governance/geometry_census.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    committed_ids = {r["occurrence_id"] for r in committed}
    assert all(r["occurrence_id"] not in committed_ids for r in derivs), \
        "rogue derivation would collide with committed ids (should be NEW)"
