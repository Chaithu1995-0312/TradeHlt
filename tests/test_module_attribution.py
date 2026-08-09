"""Module attribution floor — the ratchet behind the "100% attributed" claim.

Sibling of ``tests/test_script_registry.py`` (which holds runnable paths at 371/371). Two
distinct guarantees, deliberately separated:

* **enumeration** — every ``src/**/*.py`` appears exactly once in the ledger. Enforced HARD
  from Phase 1, because a drifting denominator makes any percentage meaningless.
* **attribution** — every module is claimed by a real surface. Enforced as a MONOTONIC
  ratchet (``_ATTRIBUTED_FLOOR``) so progress can never regress; Phase 4 raises the floor
  to the full total and the 100% claim becomes permanent.

The ledger grants no production, activation, or economic authority (CLAUDE.md §6.5). This
floor never asserts a *status* — only that every module is accounted for.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from governance.module_attribution import (
    AUTHORITY,
    GRADE_ENUM,
    REACHABILITY_ENUM,
    REGIME_ENUM,
    UNATTRIBUTED,
    ModuleAttributionRegistry,
    load_surface_ids,
    mod_num,
    new_stub_record,
    validate_record,
)
from governance.module_census import (
    DEFAULT_STUB_TS,
    census_report,
    default_regime,
    discover_modules,
    package_of,
    write_stubs,
)

_REPO = Path(__file__).resolve().parents[1]
_CENSUS = _REPO / "scripts" / "analysis" / "module_census.py"
_STUBS = _REPO / "docs" / "governance" / "module_attribution_stubs.jsonl"

#: Phase-1 ratchet pin. Monotonic: raise it as overlays land, never lower it.
#: Phase 4 sets this equal to the discovered module count and the ratchet becomes 100%.
_ATTRIBUTED_FLOOR = 0


@pytest.fixture(scope="module")
def discovered() -> list:
    return discover_modules(_REPO)


@pytest.fixture(scope="module")
def registry() -> ModuleAttributionRegistry:
    return ModuleAttributionRegistry(_STUBS)


# ------------------------------------------------------------------ enumeration (HARD)


def test_every_src_module_is_enumerated_exactly_once(discovered, registry) -> None:
    """The denominator invariant. A module missing here makes the percentage a lie."""
    cov = registry.coverage_against_disk({m.path for m in discovered})
    assert cov["unregistered"] == [], f"modules on disk but not in ledger: {cov['unregistered']}"
    assert cov["missing_on_disk"] == [], f"ledger rows with no file: {cov['missing_on_disk']}"
    assert cov["enumeration_ok"] is True


def test_no_module_is_claimed_twice(registry) -> None:
    """`owner_surface` is exactly-one; a doubly-claimed module breaks the denominator."""
    paths = [r["module_path"] for r in registry.records]
    assert len(paths) == len(set(paths))


def test_ids_are_unique_and_well_formed(registry) -> None:
    ids = [r["id"] for r in registry.records]
    assert len(ids) == len(set(ids))
    for rid in ids:
        assert mod_num(rid) > 0


def test_census_discovers_no_build_residue(discovered) -> None:
    for m in discovered:
        assert "__pycache__" not in m.path
        assert "egg-info" not in m.path
        assert m.path.startswith("src/")
        assert m.path.endswith(".py")


# ------------------------------------------------------------------- schema validity


def test_all_rows_validate(registry) -> None:
    errors = registry.validate_all()
    assert errors == [], f"{len(errors)} invalid row(s); first 5: {errors[:5]}"


def test_authority_is_pinned(registry) -> None:
    """Coverage is inventory authority only — §6.5 tunability != authority."""
    for rec in registry.records:
        assert rec["authority"] == AUTHORITY


def test_owner_surface_resolves_to_the_closure_index(registry) -> None:
    """Ownership vocabulary is owned by closure_authority_index.json, not by this ledger."""
    known = load_surface_ids()
    for rec in registry.records:
        owner = rec["owner_surface"]
        assert owner == UNATTRIBUTED or owner in known, f"{rec['id']}: unknown surface {owner!r}"


def test_participates_in_never_confers_ownership(registry) -> None:
    """CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE — participation is informational."""
    known = load_surface_ids()
    for rec in registry.records:
        assert isinstance(rec["participates_in"], list)
        for sid in rec["participates_in"]:
            assert sid in known
        if rec["owner_surface"] == UNATTRIBUTED:
            # participation must not be used as a back door to imply a claim
            assert rec["grade"] == "G0_ATTRIBUTED"


def test_no_row_claims_economic_validation_without_a_grade(registry) -> None:
    """A green coverage % must never be readable as economic soundness."""
    for rec in registry.records:
        if rec["economically_validated"] is True:
            assert rec["grade"] in {"G2_AUDITED", "G3_CLOSED"}, (
                f"{rec['id']}: economic validation claimed at grade {rec['grade']}"
            )


def test_enums_are_respected(registry) -> None:
    for rec in registry.records:
        assert rec["regime"] in REGIME_ENUM
        assert rec["grade"] in GRADE_ENUM
        assert rec["reachability"] in REACHABILITY_ENUM


# ------------------------------------------------------------------ attribution ratchet


def test_attribution_ratchet_never_regresses(discovered, registry) -> None:
    cov = registry.coverage_against_disk({m.path for m in discovered})
    assert cov["attributed"] >= _ATTRIBUTED_FLOOR, (
        f"attribution regressed: {cov['attributed']} < floor {_ATTRIBUTED_FLOOR}"
    )


def test_ratchet_floor_is_not_silently_above_reality(discovered, registry) -> None:
    """Guard against pinning a floor the ledger cannot actually meet."""
    assert _ATTRIBUTED_FLOOR <= len(discovered)


# --------------------------------------------------------------------- census mechanics


def test_write_stubs_preserves_ids_and_is_byte_stable(tmp_path: Path, discovered) -> None:
    out = tmp_path / "stubs.jsonl"
    first = write_stubs(out, discovered, timestamp=DEFAULT_STUB_TS)
    blob1 = out.read_bytes()
    ids1 = {r["module_path"]: r["id"] for r in first}

    second = write_stubs(out, discovered, timestamp=DEFAULT_STUB_TS)
    blob2 = out.read_bytes()
    ids2 = {r["module_path"]: r["id"] for r in second}

    assert blob1 == blob2, "stub writer is not deterministic"
    assert ids1 == ids2, "MOD ids were reassigned on re-run"


def test_write_stubs_preserves_overlay_fields(tmp_path: Path, discovered) -> None:
    """Census owns module_path only; an attribution overlay must survive re-census."""
    out = tmp_path / "stubs.jsonl"
    write_stubs(out, discovered, timestamp=DEFAULT_STUB_TS)

    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows[0]["owner_surface"] = "CRT"
    rows[0]["grade"] = "G1_DECLARED"
    out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n",
        encoding="utf-8",
    )

    merged = write_stubs(out, discovered, timestamp=DEFAULT_STUB_TS)
    claimed = [r for r in merged if r["owner_surface"] == "CRT"]
    assert len(claimed) == 1
    assert claimed[0]["grade"] == "G1_DECLARED"


def test_write_stubs_retains_rows_whose_file_vanished(tmp_path: Path, discovered) -> None:
    """Deletions must surface as missing_on_disk, never as a silent row drop."""
    out = tmp_path / "stubs.jsonl"
    write_stubs(out, discovered, timestamp=DEFAULT_STUB_TS)
    before = len(out.read_text(encoding="utf-8").splitlines())

    merged = write_stubs(out, discovered[:-1], timestamp=DEFAULT_STUB_TS)
    assert len(merged) == before


def test_new_stub_is_never_auto_attributed() -> None:
    """An auto-stub must not silently claim a surface — an overlay is always required."""
    rec = new_stub_record(
        module_id="MOD-9999",
        module_path="src/core/example.py",
        regime="DECISION",
        timestamp=DEFAULT_STUB_TS,
    )
    assert rec["owner_surface"] == UNATTRIBUTED
    assert rec["grade"] == "G0_ATTRIBUTED"
    assert rec["economically_validated"] is False
    assert validate_record(rec, surface_ids=set()) == []


def test_package_and_regime_heuristics() -> None:
    assert package_of("src/core/engine_runner.py") == "core"
    assert package_of("src/__init__.py") == ""
    assert default_regime("src/core/engine_runner.py") == "DECISION"
    assert default_regime("src/research/anything.py") == "RESEARCH"
    assert default_regime("src/__init__.py") == "PLATFORM"


def test_no_module_falls_through_the_regime_map(discovered) -> None:
    """A new src/ package must be classified, not silently bucketed as UNKNOWN."""
    report = census_report(discovered)
    assert report["by_suggested_regime"].get("UNKNOWN", 0) == 0, (
        "unclassified package(s) — add them to governance.module_census.PACKAGE_REGIME"
    )


def test_only_decision_regime_is_expected_to_be_expensive(discovered) -> None:
    """The cost premise: the expensive G2/G3 set stays a small minority of src/."""
    report = census_report(discovered)
    decision = report["by_suggested_regime"].get("DECISION", 0)
    assert decision / report["total"] < 0.25, (
        f"DECISION regime grew to {decision}/{report['total']} — re-examine the partition"
    )


# ------------------------------------------------------------------------- CLI contract


def test_census_cli_runs_and_reports(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(_CENSUS), "--coverage"],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
    )
    assert "by_suggested_regime" in proc.stdout
    assert "coverage" in proc.stdout


def test_census_cli_enforce_flag_is_opt_in(tmp_path: Path) -> None:
    """Phase 1 is warn-mode: an unattributed ledger must not fail the default invocation."""
    proc = subprocess.run(
        [sys.executable, str(_CENSUS), "--coverage"],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
    )
    assert proc.returncode == 0
