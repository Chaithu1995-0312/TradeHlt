"""SITS ScriptRegistry floor — schema, stub-merge, and (PR-2) disk coverage.

PR-2: path-coverage assert is on GREEN_FLOOR atomically with this file.
Design: docs/implementation_plan/script-implementation-traceability-sits-design.md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from governance.script_registry import (
    AUTHORITY,
    CATEGORY_ENUM,
    IMPL_STATUS_ENUM,
    LIFECYCLE_ENUM,
    TERMINAL_LIFECYCLES,
    ScriptRegistry,
    normalize_posix,
    scr_num,
)
from utils.jsonl_writer import read_jsonl

_REPO = Path(__file__).resolve().parents[1]
_CENSUS = _REPO / "scripts" / "analysis" / "script_census.py"
_SEED = _REPO / "scripts" / "governance" / "seed_script_registry.py"
_QUERY = _REPO / "scripts" / "governance" / "query_scripts.py"
_STUBS = _REPO / "docs" / "governance" / "script_registry_stubs.jsonl"
_GRANDFATHER = _REPO / "docs" / "governance" / "script_registry_grandfather.json"
_COLOCATED = _REPO / "docs" / "governance" / "script_colocated_allowlist.json"
_CANONICAL_ALLOW = _REPO / "docs" / "governance" / "script_canonical_allowlist.json"
_REGISTRY = _REPO / "data" / "script_registry.jsonl"


@pytest.fixture(scope="module", autouse=True)
def _ensure_seeded() -> None:
    """data/ is gitignored — reseed from committed stubs (+ overlays) for coverage tests."""
    assert _STUBS.exists(), f"missing PRIMARY stubs {_STUBS} — run script_census --write-stubs"
    subprocess.run(
        [sys.executable, str(_SEED), "--stubs", str(_STUBS), "--out", str(_REGISTRY)],
        check=True,
        cwd=_REPO,
    )
    assert _REGISTRY.exists() and _REGISTRY.stat().st_size > 0


def _valid_rec(**overrides) -> dict:
    base = ScriptRegistry.new_stub_record(
        script_id="SCR-001",
        path="scripts/analysis/example_probe.py",
        has_main=True,
        category="DIAGNOSTIC",
        lifecycle="ACTIVE",
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- schema

def test_authority_pinned() -> None:
    assert AUTHORITY == "inventory"


def test_category_has_no_terminal_names() -> None:
    assert "DEAD" not in CATEGORY_ENUM
    assert "SUPERSEDED" not in CATEGORY_ENUM
    assert TERMINAL_LIFECYCLES <= LIFECYCLE_ENUM


def test_validate_record_accepts_minimal_stub() -> None:
    ScriptRegistry.validate_record(_valid_rec())


def test_validate_record_rejects_unknown_keys() -> None:
    rec = _valid_rec()
    rec["min_delta_g001"] = 0.1
    with pytest.raises(ValueError, match="unknown keys"):
        ScriptRegistry.validate_record(rec)


def test_validate_record_rejects_wrong_authority() -> None:
    rec = _valid_rec(authority="research")
    with pytest.raises(ValueError, match="authority"):
        ScriptRegistry.validate_record(rec)


def test_validate_record_rejects_non_null_agent_tool_id_v1() -> None:
    rec = _valid_rec(agent_tool_id="some_tool")
    with pytest.raises(ValueError, match="agent_tool_id"):
        ScriptRegistry.validate_record(rec)


def test_validate_record_rejects_backslash_path() -> None:
    rec = _valid_rec(path="scripts\\analysis\\x.py")
    with pytest.raises(ValueError, match="POSIX"):
        ScriptRegistry.validate_record(rec)


def test_r2_dead_requires_notes() -> None:
    rec = _valid_rec(lifecycle="DEAD", notes="")
    with pytest.raises(ValueError, match="DEAD"):
        ScriptRegistry.validate_record(rec)
    rec["notes"] = "retired after F-044 probe"
    ScriptRegistry.validate_record(rec)


def test_r3_superseded_requires_superseded_by() -> None:
    rec = _valid_rec(lifecycle="SUPERSEDED", superseded_by=None)
    with pytest.raises(ValueError, match="superseded_by"):
        ScriptRegistry.validate_record(rec)
    rec["superseded_by"] = "SCR-002"
    ScriptRegistry.validate_record(rec)


def test_r5_n_a_cannot_claim_logic_in_script() -> None:
    rec = _valid_rec(implementation_status="N_A", logic_in_script=True)
    with pytest.raises(ValueError, match="N_A"):
        ScriptRegistry.validate_record(rec)
    rec["logic_in_script"] = False
    rec["purpose"] = "thin CLI over src.foo"
    ScriptRegistry.validate_record(rec)


def test_r6_accepted_colocated_allowlist() -> None:
    rec = _valid_rec(
        path="scripts/governance/construction_protocol.py",
        implementation_status="ACCEPTED_COLOCATED",
        logic_in_script=True,
        purpose="Gate-6 validator",
    )
    with pytest.raises(ValueError, match="allowlist"):
        ScriptRegistry.validate_record(
            rec,
            colocated_allowlist={"scripts/other.py"},
        )
    ScriptRegistry.validate_record(
        rec,
        colocated_allowlist={"scripts/governance/construction_protocol.py"},
    )


def _load_census_module():
    """PR-6: census core is src/governance/script_census.py."""
    import governance.script_census as mod

    return mod


def test_never_auto_canonical_in_new_stub_categories() -> None:
    """Directory defaults used by census must not invent CANONICAL_CLI (K17)."""
    mod = _load_census_module()
    for sample in (
        "scripts/data/prepare_data.py",
        "scripts/training/train_pipeline.py",
        "scripts/analysis/foo.py",
        "_gate0_check.py",
    ):
        assert mod.default_category(sample) != "CANONICAL_CLI"


# --------------------------------------------------------------------------- promotion plan

def test_valid_promotion_plan_dest_modules() -> None:
    rec = _valid_rec(notes="extract planned", dest_modules=["src/governance/foo.py"])
    assert ScriptRegistry.is_valid_promotion_plan(rec)


def test_valid_promotion_plan_wontfix() -> None:
    rec = _valid_rec(notes="wontfix:reason=one-shot probe", dest_modules=[])
    assert ScriptRegistry.is_valid_promotion_plan(rec)


def test_invalid_promotion_plan_empty() -> None:
    rec = _valid_rec(notes="", dest_modules=[])
    assert not ScriptRegistry.is_valid_promotion_plan(rec)


def test_promotion_debt_ttl() -> None:
    reg = ScriptRegistry()
    reg._records = {
        "SCR-001": _valid_rec(
            id="SCR-001",
            ttl_days=30,
            notes="",
            dest_modules=[],
            implementation_status="LOGIC_IN_SCRIPT",
            logic_in_script=True,
        ),
        "SCR-002": _valid_rec(
            id="SCR-002",
            path="scripts/analysis/b.py",
            ttl_days=None,
            implementation_status="LOGIC_IN_SCRIPT",
        ),
        "SCR-003": _valid_rec(
            id="SCR-003",
            path="scripts/governance/construction_protocol.py",
            implementation_status="ACCEPTED_COLOCATED",
            ttl_days=1,
            notes="x",
            logic_in_script=True,
        ),
        "SCR-004": _valid_rec(
            id="SCR-004",
            path="scripts/analysis/c.py",
            ttl_days=30,
            notes="wontfix:reason=ephemeral",
            dest_modules=[],
            implementation_status="LOGIC_IN_SCRIPT",
        ),
    }
    debt = reg.promotion_debt(now_days=60)
    assert [r["id"] for r in debt] == ["SCR-001"]
    # valid plan clears debt even when expired
    assert "SCR-004" not in [r["id"] for r in debt]


def test_promotion_debt_calendar() -> None:
    from datetime import datetime, timezone, timedelta

    reg = ScriptRegistry()
    created = "2026-01-01T00:00:00Z"
    reg._records = {
        "SCR-001": _valid_rec(
            id="SCR-001",
            created=created,
            last_validated=created,
            ttl_days=30,
            notes="",
            dest_modules=[],
        ),
    }
    now = datetime(2026, 3, 1, tzinfo=timezone.utc)
    assert reg.promotion_debt(now=now)
    assert not reg.promotion_debt(now=datetime(2026, 1, 10, tzinfo=timezone.utc))


def test_age_days() -> None:
    from datetime import datetime, timezone

    rec = _valid_rec(created="2026-01-01T00:00:00Z")
    age = ScriptRegistry.age_days(
        rec, now=datetime(2026, 1, 31, tzinfo=timezone.utc)
    )
    assert age is not None and 29.9 < age < 30.1


# --------------------------------------------------------------------------- dump / load

def test_dump_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "script_registry.jsonl"
    recs = [
        _valid_rec(id="SCR-002", path="scripts/a.py"),
        _valid_rec(id="SCR-001", path="scripts/b.py"),
    ]
    n = ScriptRegistry.dump(path, recs)
    assert n == 2
    reg = ScriptRegistry()
    assert reg.load(path) == 2
    assert reg.get("SCR-001")["path"] == "scripts/b.py"
    s = reg.summary()
    assert s["total"] == 2
    assert s["authority"] == "inventory"


def test_dump_rejects_duplicate_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        ScriptRegistry.dump(
            tmp_path / "x.jsonl",
            [_valid_rec(id="SCR-001"), _valid_rec(id="SCR-001", path="scripts/c.py")],
        )


# --------------------------------------------------------------------------- paths / coverage

def test_validate_paths_non_terminal(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    f = tmp_path / "scripts" / "exists.py"
    f.write_text("# x\n", encoding="utf-8")
    reg = ScriptRegistry()
    reg._records = {
        "SCR-001": _valid_rec(
            id="SCR-001",
            path="scripts/exists.py",
            lifecycle="ACTIVE",
        ),
        "SCR-002": _valid_rec(
            id="SCR-002",
            path="scripts/gone.py",
            lifecycle="ACTIVE",
        ),
        "SCR-003": _valid_rec(
            id="SCR-003",
            path="scripts/also_gone.py",
            lifecycle="ARCHIVED",
            notes="archived",
        ),
    }
    errors = reg.validate_paths(tmp_path)
    assert len(errors) == 1
    assert errors[0].component_id == "SCR-002"


def test_coverage_against_disk() -> None:
    reg = ScriptRegistry()
    reg._records = {
        "SCR-001": _valid_rec(id="SCR-001", path="scripts/a.py", lifecycle="ACTIVE"),
        "SCR-002": _valid_rec(id="SCR-002", path="scripts/old.py", lifecycle="DEAD", notes="x"),
        "SCR-003": _valid_rec(id="SCR-003", path="scripts/missing.py", lifecycle="ACTIVE"),
    }
    cov = reg.coverage_against_disk({"scripts/a.py", "scripts/new.py"})
    assert cov["unregistered"] == ["scripts/new.py"]
    assert cov["missing_on_disk"] == ["scripts/missing.py"]
    # terminal DEAD path is not required on disk / not in non-terminal set
    assert "scripts/old.py" not in cov["missing_on_disk"]
    assert cov["ok"] is False


# --------------------------------------------------------------------------- write-stubs merge (K19)

def test_write_stubs_preserves_ids_and_is_byte_stable(tmp_path: Path) -> None:
    mod = _load_census_module()

    repo = tmp_path / "repo"
    (repo / "scripts" / "analysis").mkdir(parents=True)
    (repo / "scripts" / "analysis" / "probe_a.py").write_text(
        'if __name__ == "__main__":\n    pass\n', encoding="utf-8"
    )
    (repo / "scripts" / "analysis" / "probe_b.py").write_text("# no main\n", encoding="utf-8")
    (repo / "_root_probe.py").write_text("# root\n", encoding="utf-8")

    stubs_path = tmp_path / "stubs.jsonl"
    disc1 = mod.discover_paths(repo)
    out1 = mod.write_stubs(stubs_path, disc1, timestamp="2026-08-02T00:00:00Z")
    assert len(out1) == 3
    ids_first = {r["path"]: r["id"] for r in out1}
    text1 = stubs_path.read_text(encoding="utf-8")

    # Second run identical disk → byte-identical stubs
    disc2 = mod.discover_paths(repo)
    out2 = mod.write_stubs(stubs_path, disc2, timestamp="2026-08-02T00:00:00Z")
    text2 = stubs_path.read_text(encoding="utf-8")
    assert text1 == text2
    assert {r["path"]: r["id"] for r in out2} == ids_first

    # New file gets max+1; old ids preserved
    (repo / "scripts" / "analysis" / "probe_c.py").write_text("# c\n", encoding="utf-8")
    disc3 = mod.discover_paths(repo)
    out3 = mod.write_stubs(stubs_path, disc3, timestamp="2026-08-02T00:00:00Z")
    by_path = {r["path"]: r for r in out3}
    assert by_path["scripts/analysis/probe_a.py"]["id"] == ids_first["scripts/analysis/probe_a.py"]
    assert by_path["scripts/analysis/probe_b.py"]["id"] == ids_first["scripts/analysis/probe_b.py"]
    new_id = by_path["scripts/analysis/probe_c.py"]["id"]
    assert scr_num(new_id) == max(scr_num(i) for i in ids_first.values()) + 1

    # Removed file keeps stub row (id not recycled)
    (repo / "scripts" / "analysis" / "probe_b.py").unlink()
    disc4 = mod.discover_paths(repo)
    out4 = mod.write_stubs(stubs_path, disc4, timestamp="2026-08-02T00:00:00Z")
    still = {r["path"]: r["id"] for r in out4}
    assert "scripts/analysis/probe_b.py" in still
    assert still["scripts/analysis/probe_b.py"] == ids_first["scripts/analysis/probe_b.py"]


def test_write_stubs_never_auto_n_a(tmp_path: Path) -> None:
    mod = _load_census_module()

    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    # thin-looking file
    (repo / "scripts" / "thin.py").write_text(
        "from src.foo import bar\n\nif __name__ == '__main__':\n    bar()\n",
        encoding="utf-8",
    )
    stubs = mod.write_stubs(tmp_path / "s.jsonl", mod.discover_paths(repo))
    assert all(r["implementation_status"] == "LOGIC_IN_SCRIPT" for r in stubs)
    assert all(r["logic_in_script"] is True for r in stubs)
    assert all(r["purpose"] == "GRANDFATHER_UNCLASSIFIED" for r in stubs)
    assert all(r["ttl_days"] is None for r in stubs)


# --------------------------------------------------------------------------- CLI smoke

def test_query_validate_empty_registry_ok(tmp_path: Path) -> None:
    missing = tmp_path / "nope.jsonl"
    proc = subprocess.run(
        [sys.executable, str(_QUERY), "--registry", str(missing), "--validate"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VALIDATION OK" in proc.stdout


def test_seed_empty_stubs_ok(tmp_path: Path) -> None:
    stubs = tmp_path / "stubs.jsonl"
    # absent stubs
    out = tmp_path / "data" / "script_registry.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(_SEED),
            "--stubs",
            str(stubs),
            "--out",
            str(out),
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.exists()
    assert out.read_text(encoding="utf-8") == ""


def test_seed_with_stub_and_overlay_field(tmp_path: Path) -> None:
    """Overlay application unit (PR-6: core in governance.script_seed)."""
    from governance.script_seed import apply_overlays

    stub = _valid_rec(
        id="SCR-010",
        path="scripts/analysis/rr_confidence_probe.py",
        purpose="GRANDFATHER_UNCLASSIFIED",
    )
    overlays = [
        {
            "path": "scripts/analysis/rr_confidence_probe.py",
            "purpose": "In-sample RR Mahalanobis confidence probe (F-044).",
            "task_refs": ["F-044"],
            "category": "DIAGNOSTIC",
        }
    ]
    merged = apply_overlays([stub], overlays)
    assert len(merged) == 1
    assert merged[0]["purpose"].startswith("In-sample")
    assert merged[0]["id"] == "SCR-010"
    assert merged[0]["task_refs"] == ["F-044"]


def test_normalize_posix() -> None:
    assert normalize_posix(r"scripts\analysis\x.py") == "scripts/analysis/x.py"
    assert normalize_posix("./scripts/a.py") == "scripts/a.py"


def test_scr_num() -> None:
    assert scr_num("SCR-001") == 1
    assert scr_num("SCR-1000") == 1000
    with pytest.raises(ValueError):
        scr_num("H-001")


def test_filter_and_missing_impl() -> None:
    reg = ScriptRegistry()
    reg._records = {
        "SCR-001": _valid_rec(
            id="SCR-001",
            path="scripts/analysis/a.py",
            logic_in_script=True,
            notes="",
            dest_modules=[],
        ),
        "SCR-002": _valid_rec(
            id="SCR-002",
            path="scripts/analysis/b.py",
            logic_in_script=True,
            notes="wontfix:reason=ephemeral",
            dest_modules=[],
        ),
    }
    assert len(reg.filter(category="DIAGNOSTIC")) == 2
    missing = reg.missing_impl()
    assert [r["id"] for r in missing] == ["SCR-001"]


def test_control_plane_parity() -> None:
    reg = ScriptRegistry()
    reg._records = {
        "SCR-001": _valid_rec(
            id="SCR-001",
            category="CANONICAL_CLI",
            lifecycle="ACTIVE",
            control_plane_id="data.prepare_data",
            path="scripts/data/prepare_data.py",
        ),
        "SCR-002": _valid_rec(
            id="SCR-002",
            category="CANONICAL_CLI",
            lifecycle="ACTIVE",
            control_plane_id=None,
            path="scripts/data/orphan_cli.py",
        ),
    }
    errs = reg.validate_control_plane_parity(
        {"data.prepare_data"},
        set(),
    )
    assert len(errs) == 1
    assert errs[0].component_id == "SCR-002"


# --------------------------------------------------------------------------- PR-2 coverage floor

def test_stubs_and_grandfather_exist() -> None:
    assert _STUBS.exists()
    assert _GRANDFATHER.exists()
    assert _COLOCATED.exists()
    gf = json.loads(_GRANDFATHER.read_text(encoding="utf-8"))
    assert gf.get("version") == 1
    assert gf.get("match_key") == "path"
    assert isinstance(gf.get("paths"), list) and len(gf["paths"]) > 0
    col = json.loads(_COLOCATED.read_text(encoding="utf-8"))
    assert "scripts/governance/construction_protocol.py" in col.get("paths", [])


def test_seeded_registry_schema_valid() -> None:
    """Every seeded line passes closed schema; ACCEPTED_COLOCATED respects allowlist."""
    col = json.loads(_COLOCATED.read_text(encoding="utf-8"))
    allow = set(col.get("paths") or [])
    lines = read_jsonl(_REGISTRY)
    assert lines, "seeded registry empty"
    for rec in lines:
        ScriptRegistry.validate_record(rec, colocated_allowlist=allow)


def test_disk_coverage_full_universe() -> None:
    """discovered ⊆ non-terminal registry paths (100% registration).

    Refresh stubs after adding scripts:
      python scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl
      python scripts/governance/seed_script_registry.py
    """
    mod = _load_census_module()
    discovered = {f.path for f in mod.discover_paths(_REPO)}
    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    cov = reg.coverage_against_disk(discovered)
    assert not cov["unregistered"], (
        "Unregistered scripts on disk — run --write-stubs + seed, then re-commit stubs.\n"
        f"  unregistered ({len(cov['unregistered'])}): {cov['unregistered'][:20]}"
        + (" ..." if len(cov["unregistered"]) > 20 else "")
    )


def test_grandfather_paths_match_stubs() -> None:
    """Grandfather pin path set equals current stubs (Phase-1 freeze integrity)."""
    gf = json.loads(_GRANDFATHER.read_text(encoding="utf-8"))
    pin = {normalize_posix(p) for p in gf["paths"]}
    stub_paths = {
        normalize_posix(r["path"])
        for r in read_jsonl(_STUBS)
        if r.get("path")
    }
    assert pin == stub_paths, (
        f"grandfather pin drift vs stubs: "
        f"only_in_pin={sorted(pin - stub_paths)[:10]} "
        f"only_in_stubs={sorted(stub_paths - pin)[:10]}"
    )


def test_construction_protocol_is_accepted_colocated() -> None:
    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    hits = [
        r for r in reg.records
        if r.get("path") == "scripts/governance/construction_protocol.py"
    ]
    assert len(hits) == 1
    assert hits[0]["implementation_status"] == "ACCEPTED_COLOCATED"
    assert hits[0]["logic_in_script"] is True


# --------------------------------------------------------------------------- PR-3 grandfather ratchet (ENFORCE_NEW)

def test_grandfather_ratchet_unit() -> None:
    """New paths must be registered + purpose ≠ GRANDFATHER_UNCLASSIFIED."""
    reg = ScriptRegistry()
    reg._records = {
        "SCR-001": _valid_rec(
            id="SCR-001",
            path="scripts/analysis/old.py",
            purpose="GRANDFATHER_UNCLASSIFIED",
        ),
        "SCR-002": _valid_rec(
            id="SCR-002",
            path="scripts/probes/new_ok.py",
            purpose="One-shot F-044 follow-up probe.",
            category="PROBE",
            lifecycle="EPHEMERAL",
        ),
        "SCR-003": _valid_rec(
            id="SCR-003",
            path="scripts/probes/new_stub.py",
            purpose="GRANDFATHER_UNCLASSIFIED",
            category="PROBE",
            lifecycle="EPHEMERAL",
        ),
    }
    discovered = {
        "scripts/analysis/old.py",
        "scripts/probes/new_ok.py",
        "scripts/probes/new_stub.py",
        "scripts/probes/missing.py",
    }
    grandfather = {"scripts/analysis/old.py"}
    result = reg.grandfather_ratchet(discovered, grandfather)
    assert result["new_path_count"] == 3
    assert result["unregistered"] == ["scripts/probes/missing.py"]
    assert result["unclassified"] == ["scripts/probes/new_stub.py"]
    assert result["ok"] is False

    # Classified new path alone passes
    result_ok = reg.grandfather_ratchet(
        {"scripts/analysis/old.py", "scripts/probes/new_ok.py"},
        grandfather,
    )
    assert result_ok["ok"] is True
    assert result_ok["unclassified"] == []
    assert result_ok["unregistered"] == []


def test_grandfather_ratchet_live_universe() -> None:
    """Live disk: every non-grandfather path is classified (overlay or intentional close).

    When this fails for a *new* script you just added:
      1. script_census.py --write-stubs …
      2. Add OVERLAY in seed_script_registry.py with purpose ≠ GRANDFATHER_UNCLASSIFIED
      3. seed_script_registry.py + generate_script_matrix.py
    Do NOT hand-edit stubs for purpose/category.
    """
    gf = json.loads(_GRANDFATHER.read_text(encoding="utf-8"))
    pin = {normalize_posix(p) for p in gf["paths"]}
    mod = _load_census_module()
    discovered = {f.path for f in mod.discover_paths(_REPO)}
    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    result = reg.grandfather_ratchet(discovered, pin)
    assert result["ok"], (
        "Phase-2 grandfather ratchet failed — new paths must be registered via overlay "
        f"(purpose ≠ GRANDFATHER_UNCLASSIFIED).\n"
        f"  unregistered: {result['unregistered'][:15]}\n"
        f"  unclassified: {result['unclassified'][:15]}\n"
        f"  new_path_count: {result['new_path_count']}"
    )


# --------------------------------------------------------------------------- PR-4 CANONICAL_CLI ↔ CommandSpec parity

def test_command_specs_by_script_maps_scripts_paths() -> None:
    from governance.script_registry import command_specs_by_script

    m = command_specs_by_script()
    assert "scripts/data/prepare_data.py" in m
    assert m["scripts/data/prepare_data.py"] == "data.prepare_data"
    assert "inout.runner" not in m  # module mode skipped


def test_active_canonical_cli_control_plane_parity() -> None:
    """ACTIVE CANONICAL_CLI ⇒ control_plane_id ∈ CommandSpec ids OR path allowlisted."""
    from control_plane.registry import core_command_specs
    from governance.script_registry import load_canonical_allowlist

    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    command_ids = {s.id for s in core_command_specs()}
    allow = load_canonical_allowlist(_CANONICAL_ALLOW)
    errs = reg.validate_control_plane_parity(command_ids, allow)
    assert not errs, "CANONICAL_CLI parity gaps:\n" + "\n".join(str(e) for e in errs)


def test_control_plane_scripts_are_canonical_cli() -> None:
    """Every CommandSpec.script under scripts/ is productized as CANONICAL_CLI in the registry."""
    from governance.script_registry import command_specs_by_script

    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    by_path = {
        normalize_posix(r["path"]): r
        for r in reg.records
        if r.get("lifecycle") not in TERMINAL_LIFECYCLES
    }
    missing: list[str] = []
    wrong: list[str] = []
    for path, cid in command_specs_by_script().items():
        if not path.startswith("scripts/"):
            continue  # src/** CLI modules are outside default SITS universe
        rec = by_path.get(path)
        if rec is None:
            missing.append(f"{cid}: {path}")
            continue
        if rec.get("category") != "CANONICAL_CLI" or rec.get("control_plane_id") != cid:
            wrong.append(
                f"{cid}: category={rec.get('category')} control_plane_id={rec.get('control_plane_id')}"
            )
    assert not missing and not wrong, (
        f"CommandSpec scripts not linked as CANONICAL_CLI.\n"
        f"  missing from registry: {missing[:10]}\n"
        f"  wrong link: {wrong[:10]}\n"
        "Re-run: python scripts/governance/seed_script_registry.py"
    )


def test_no_path_heuristic_canonical_without_cp() -> None:
    """CANONICAL_CLI rows must not appear without CP id or allowlist (anti path-heuristic)."""
    from control_plane.registry import core_command_specs
    from governance.script_registry import load_canonical_allowlist

    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    command_ids = {s.id for s in core_command_specs()}
    allow = load_canonical_allowlist(_CANONICAL_ALLOW)
    for r in reg.records:
        if r.get("category") != "CANONICAL_CLI":
            continue
        if r.get("lifecycle") != "ACTIVE":
            continue
        cp = r.get("control_plane_id")
        path = normalize_posix(r.get("path", ""))
        assert (cp and cp in command_ids) or path in allow, (
            f"{r.get('id')} CANONICAL_CLI without CP link or allowlist: {path}"
        )


# --------------------------------------------------------------------------- PR-5 TTL debt gate + missing-impl export

def test_live_promotion_debt_floor_green() -> None:
    """CI-binding: no expired TTL without a valid promotion plan.

    Curated rows may set ``ttl_days`` only with a valid plan (dest_modules or
    wontfix:reason=). Default grandfather remains ``ttl_days=null`` (no debt).
    """
    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    debt = reg.promotion_debt()
    assert not debt, (
        "TTL promotion debt non-empty — set a valid promotion plan or clear/extend ttl_days:\n"
        + "\n".join(
            f"  {r.get('id')} ttl={r.get('ttl_days')} {r.get('path')}" for r in debt[:20]
        )
    )


def test_curated_ttl_rows_have_valid_plans() -> None:
    """Every row with ttl_days set must already carry a valid plan (anti debt-spam)."""
    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    tracked = [
        r for r in reg.records
        if r.get("ttl_days") is not None
        and r.get("lifecycle") not in TERMINAL_LIFECYCLES
    ]
    assert tracked, "expected PR-5 curated TTL overlays on hot DIAGNOSTIC rows"
    bad = [
        r for r in tracked
        if r.get("implementation_status") == "LOGIC_IN_SCRIPT"
        and not ScriptRegistry.is_valid_promotion_plan(r)
    ]
    # Rows with valid plans may still be LOGIC_IN_SCRIPT; invalid plan + ttl is the fail case
    assert not bad, (
        "ttl_days set without valid promotion plan (will become CI debt when expired):\n"
        + "\n".join(f"  {r.get('id')} {r.get('path')}" for r in bad)
    )


def test_missing_impl_queue_export_shape() -> None:
    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    lines = reg.missing_impl_queue_lines()
    assert lines, "expected a non-empty visibility backlog on grandfather inventory"
    sample = lines[0]
    for key in ("kind", "script_id", "path", "authority", "suggested_action"):
        assert key in sample
    assert sample["kind"] == "SITS_MISSING_IMPL"
    assert sample["authority"] == "inventory"


def test_debt_report_markdown_contains_summary() -> None:
    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    md = reg.debt_report_markdown()
    assert "TTL debt" in md
    assert "Missing-impl" in md
    assert "Curated TTL rows" in md


# --------------------------------------------------------------------------- PR-6 extract wave (spine boundary)

_SPINE_IMPORT_BAN = (
    "src/core/engine_runner.py",
    "src/runtime/live_engine_hook.py",
    "src/runtime/backtest_v2.py",
)
_SITS_MODULES = (
    "src/governance/script_registry.py",
    "src/governance/script_census.py",
    "src/governance/script_seed.py",
)


def test_pr6_extracted_sits_clis_status() -> None:
    """Census/seed/query CLIs productized under src/; status TESTED/WIRED."""
    reg = ScriptRegistry()
    reg.load(_REGISTRY)
    by_path = {normalize_posix(r["path"]): r for r in reg.records}
    census = by_path.get("scripts/analysis/script_census.py")
    seed = by_path.get("scripts/governance/seed_script_registry.py")
    query = by_path.get("scripts/governance/query_scripts.py")
    assert census and census["implementation_status"] == "TESTED"
    assert "src/governance/script_census.py" in (census.get("dest_modules") or [])
    assert census.get("logic_in_script") is False
    assert seed and seed["implementation_status"] == "TESTED"
    assert "src/governance/script_seed.py" in (seed.get("dest_modules") or [])
    assert query and query["implementation_status"] in ("WIRED", "TESTED", "REGISTERED")
    assert query.get("logic_in_script") is False


def test_pr6_sits_modules_not_imported_by_spine() -> None:
    """Completion criterion (a): SITS libs must not be on the trading spine import graph."""
    needles = (
        "script_registry",
        "script_census",
        "script_seed",
        "governance.script_",
    )
    offenders: list[str] = []
    for spine in _SPINE_IMPORT_BAN:
        text = (_REPO / spine).read_text(encoding="utf-8", errors="replace")
        for n in needles:
            if n in text:
                offenders.append(f"{spine} mentions {n!r}")
    assert not offenders, "SITS inventory modules imported/mentioned on spine:\n" + "\n".join(
        offenders
    )


def test_pr6_extracted_modules_exist() -> None:
    for rel in _SITS_MODULES:
        assert (_REPO / rel).is_file(), f"missing extract target {rel}"
    # Thin wrappers still exist and stay short
    for rel in (
        "scripts/analysis/script_census.py",
        "scripts/governance/seed_script_registry.py",
        "scripts/governance/query_scripts.py",
    ):
        text = (_REPO / rel).read_text(encoding="utf-8")
        assert "argparse" in text
        # census/seed wrappers should not re-implement discovery merge
        if "script_census.py" in rel:
            assert "def discover_paths" not in text
            assert "from governance.script_census import" in text
        if "seed_script_registry.py" in rel:
            assert "def apply_overlays" not in text
            assert "from governance.script_seed import" in text
