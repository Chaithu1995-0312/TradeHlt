"""Contract + mutation floor for the Semantic File Identity Layer (``kind: file_identity``).

Two halves, and the second is the one that matters:

  1. POSITIVE — the live curated (Tier 1/2) records plus the Tier-3 derived projection are clean,
     deterministic, order-invariant, total over the code universe, and cover the SPINE_FILES
     ratchet.
  2. NEGATIVE (mutation) — for every violation class, a deliberately broken copy MUST be caught,
     asserting the SPECIFIC message substring rather than merely "errors is non-empty".

Mirrors ``tests/test_semantic_os.py``'s pattern (deepcopy the live records, break one thing,
assert the matching validator fires).
"""
from __future__ import annotations

import copy
import random
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from governance.semantic_os import (  # noqa: E402
    SPINE_FILES,
    SemanticOSRegistry,
    _ID_RE,
    _IDENTITY_TIER1_FLOOR,
    foreign_id_namespace,
)
from governance.semantic_identity import (  # noqa: E402
    derive_tier3_identities,
    validate_projection,
)
from governance.semantic_objects import discover_universe  # noqa: E402

_SOURCE_DIR = _REPO / "docs" / "governance" / "semantic_os"
_SEED = _REPO / "scripts" / "governance" / "seed_semantic_os.py"
_OUT_DIR = _REPO / "data" / "semantic_os"


# ── helpers ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def live() -> SemanticOSRegistry:
    return SemanticOSRegistry.load(_SOURCE_DIR)


@pytest.fixture(scope="module")
def code_paths() -> list[str]:
    return discover_universe("code")


@pytest.fixture(scope="module")
def derived(live, code_paths) -> list[dict]:
    return derive_tier3_identities(code_paths, live.file_identities)


def _clone(reg: SemanticOSRegistry):
    return (
        copy.deepcopy(sorted(reg.concepts.values(), key=lambda r: r["id"])),
        copy.deepcopy(sorted(reg.boundaries.values(), key=lambda r: r["id"])),
        copy.deepcopy(sorted(reg.journeys.values(), key=lambda r: r["id"])),
        copy.deepcopy(sorted(reg.contracts.values(), key=lambda r: r["id"])),
        copy.deepcopy(sorted(reg.file_identities.values(), key=lambda r: r["id"])),
    )


def _rebuild(concepts, boundaries, journeys, contracts, identities) -> SemanticOSRegistry:
    return SemanticOSRegistry(concepts, boundaries, journeys, contracts, identities)


def _details(errors) -> str:
    return " | ".join(str(e) for e in errors)


def _assert_caught(errors, needle: str) -> None:
    assert errors, f"expected a validation error containing {needle!r}, got none"
    assert needle in _details(errors), f"expected {needle!r} in: {_details(errors)}"


# ── positive ────────────────────────────────────────────────────────────────────────────────

def test_live_registry_with_identities_is_clean(live):
    assert live.validate_all() == []


def test_live_registry_with_identities_is_clean_in_strict_mode(live):
    assert live.validate_all(strict=True) == []


def test_identity_ids_are_unique_and_globally_disjoint(live):
    foreign_ids: set[str] = set()
    for ids in foreign_id_namespace().values():
        foreign_ids |= ids
    collisions = set(live.file_identities) & foreign_ids
    assert not collisions, f"file_identity ids collide with a foreign namespace: {collisions}"


def test_identity_slugs_match_the_pinned_regex_and_carry_a_dot(live):
    pattern = _ID_RE["file_identity"]
    for rid in live.file_identities:
        assert pattern.match(rid), f"{rid} does not match {pattern.pattern}"
        assert "." in rid, f"{rid} has no dot — would collide with single-token MIAR entry ids"


def test_every_physical_path_exists_and_is_code(live):
    for rid, record in live.file_identities.items():
        path = record["physical_path"]
        assert (_REPO / path).is_file(), f"{rid}: {path} does not exist"
        assert path.endswith(".py"), f"{rid}: {path} is not a .py file"
        assert not path.startswith("tests/"), f"{rid}: {path} is under tests/ (decision 3)"


def test_exactly_one_canonical_identity_per_path(live):
    by_path: dict[str, list[str]] = {}
    for rid, record in live.file_identities.items():
        by_path.setdefault(record["physical_path"], []).append(rid)
    for path, ids in by_path.items():
        canonical = [rid for rid in ids if live.file_identities[rid]["canonical"] is True]
        assert len(canonical) == 1, f"{path}: expected exactly 1 canonical, got {canonical}"


def test_identity_coverage_is_total_over_the_code_universe(live, code_paths, derived):
    curated_paths = {r["physical_path"] for r in live.file_identities.values()}
    derived_paths = {r["physical_path"] for r in derived}
    assert curated_paths | derived_paths == set(code_paths)


def test_spine_files_all_have_tier1_high_identities(live):
    tier1_paths = {r["physical_path"] for r in live.file_identities.values() if r["tier"] == 1}
    missing = [f for f in SPINE_FILES if f not in tier1_paths]
    assert not missing, f"spine modules missing a Tier-1 identity: {missing}"


def test_tier1_floor_cannot_regress(live):
    tier1_paths = {r["physical_path"] for r in live.file_identities.values() if r["tier"] == 1}
    covered = [f for f in SPINE_FILES if f in tier1_paths]
    assert len(covered) >= _IDENTITY_TIER1_FLOOR


def test_tier_confidence_provenance_move_together(live):
    coherence = {1: ("HIGH", "CURATED"), 2: ("MEDIUM", "CURATED"), 3: ("LOW", "DERIVED")}
    for rid, record in live.file_identities.items():
        expect_conf, expect_prov = coherence[record["tier"]]
        assert record["confidence"] == expect_conf, rid
        assert record["provenance"] == expect_prov, rid


def test_derived_rows_are_unambiguously_machine_made(derived):
    assert derived, "expected at least one Tier-3 derived row"
    for r in derived:
        assert r["provenance"] == "DERIVED"
        assert r["tier"] == 3
        assert r["derivation"] and r["derivation"].startswith("path_slug/")
        assert r["why_this_identity"] == ""
        assert r["filename_semantic_status"] == "UNKNOWN"
        assert r["aliases"] == []


def test_derivation_is_deterministic_and_order_invariant(live, code_paths):
    a = derive_tier3_identities(code_paths, live.file_identities)
    b = derive_tier3_identities(code_paths, live.file_identities)
    assert [r["id"] for r in a] == [r["id"] for r in b]

    shuffled = code_paths[:]
    random.Random(42).shuffle(shuffled)
    c = derive_tier3_identities(shuffled, live.file_identities)
    assert [r["id"] for r in a] == [r["id"] for r in c]


def test_derived_slugs_never_shadow_a_curated_slug(live, code_paths, derived):
    assert validate_projection(live.file_identities, derived, code_paths) == []


def test_no_derived_field_is_hand_authored_in_identities(live):
    assert live.validate_no_derived_in_source() == []


def test_classification_vocabulary_is_not_decorative(live):
    """A layer that classifies everything ALIGNED would pass every OTHER test here — this one
    forces at least one real example of each non-trivial status to exist."""
    statuses = {r["filename_semantic_status"] for r in live.file_identities.values()}
    for required in ("MISLEADING", "COMPATIBILITY", "HISTORICAL", "SPLIT"):
        assert required in statuses, f"no curated record classified {required} — layer looks decorative"
    assert len(live.file_identities) >= 50


def test_identity_layer_touches_no_runtime_module():
    """governance.semantic_identity is importable ONLY from semantic_objects / semantic_os — this
    is the permanent, mechanical guarantee that the identity layer never becomes a runtime dep."""
    importers = []
    for path in discover_universe("code"):
        if not path.startswith("src/"):
            continue
        text = (_REPO / path).read_text(encoding="utf-8", errors="replace")
        if "governance.semantic_identity" in text or "from governance import semantic_identity" in text:
            importers.append(path)
    assert set(importers) == {
        "src/governance/semantic_objects.py",
        "src/governance/semantic_os.py",
    }, f"unexpected importer(s) of governance.semantic_identity: {importers}"


def test_seed_emits_file_identities_and_is_byte_identical_on_rerun():
    def _run():
        proc = subprocess.run(
            [sys.executable, str(_SEED), "--objects"], cwd=_REPO, capture_output=True, text=True
        )
        assert proc.returncode == 0, f"seed failed: {proc.stdout}\n{proc.stderr}"
        return {p.name: p.read_bytes() for p in sorted(_OUT_DIR.glob("*.jsonl"))}

    first = _run()
    assert "file_identities.jsonl" in first
    second = _run()
    assert first == second


# ── negative: schema / id ───────────────────────────────────────────────────────────────────

def test_id_without_dot_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    ids[0]["id"] = "cratestatemachine"
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_schema(), "must match")


def test_duplicate_identity_id_is_caught(live, tmp_path):
    """The in-memory registry is dict-keyed by id (a duplicate silently collapses, same as
    concepts/boundaries/journeys); the write path (``dump``) is where it must be refused."""
    _, _, _, _, ids = _clone(live)
    twin = copy.deepcopy(ids[0])
    with pytest.raises(ValueError, match="duplicate id"):
        SemanticOSRegistry.dump(tmp_path / "dup.jsonl", [dict(ids[0]), dict(twin)])


def test_physical_path_under_tests_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    ids[0]["physical_path"] = "tests/test_something.py"
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_schema(), "may not be under tests/")


def test_physical_path_missing_from_disk_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    ids[0]["physical_path"] = "src/definitely/not/here.py"
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_schema(), "does not exist on disk")


# ── negative: canonicality ──────────────────────────────────────────────────────────────────

def test_two_canonical_identities_for_one_path_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    dup = copy.deepcopy(ids[0])
    dup["id"] = ids[0]["id"] + "_dup"
    ids.append(dup)  # same physical_path, both canonical=true
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_identity_canonicality(), "multiple canonical")


def test_zero_canonical_identities_for_one_path_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    dup = copy.deepcopy(ids[0])
    dup["id"] = ids[0]["id"] + "_dup"
    dup["canonical"] = False
    ids[0]["canonical"] = False
    ids.append(dup)
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_identity_canonicality(), "no canonical")


# ── negative: tier coherence ────────────────────────────────────────────────────────────────

def test_tier1_with_low_confidence_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    tier1 = next(r for r in ids if r["tier"] == 1)
    tier1["confidence"] = "LOW"
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_schema(), "requires confidence=")


def test_tier1_with_unknown_filename_status_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    tier1 = next(r for r in ids if r["tier"] == 1)
    tier1["filename_semantic_status"] = "UNKNOWN"
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_schema(), "may not carry filename_semantic_status UNKNOWN")


def test_misleading_without_reason_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    misleading = next(r for r in ids if r["filename_semantic_status"] == "MISLEADING")
    misleading["filename_status_reason"] = ""
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_schema(), "filename_status_reason must be a non-empty string")


def test_derived_provenance_with_wrong_derivation_prefix_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    row = copy.deepcopy(ids[0])
    row.update(
        id="root.synthetic_derived_probe", tier=3, confidence="LOW", provenance="DERIVED",
        derivation="not_path_slug", why_this_identity="", aliases=[],
        filename_semantic_status="UNKNOWN",
    )
    _assert_caught(_rebuild(c, b, j, ct, ids + [row]).validate_schema(), "derivation must start with")


def test_derived_provenance_with_nonempty_why_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    row = copy.deepcopy(ids[0])
    row.update(
        id="root.synthetic_derived_probe2", tier=3, confidence="LOW", provenance="DERIVED",
        derivation="path_slug/v1", why_this_identity="a human wrote this", aliases=[],
        filename_semantic_status="UNKNOWN",
    )
    _assert_caught(_rebuild(c, b, j, ct, ids + [row]).validate_schema(), "must carry an empty why_this_identity")


def test_curated_provenance_with_nonnull_derivation_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    row = copy.deepcopy(ids[0])
    row["derivation"] = "path_slug/v1"
    _assert_caught(_rebuild(c, b, j, ct, ids[1:] + [row]).validate_schema(), "derivation must be null for CURATED")


# ── negative: alias domain / derived-field hygiene ──────────────────────────────────────────

def test_identity_alias_colliding_with_a_concept_name_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    concept_name = c[1]["name"]  # a different concept than whatever ids[0] might already cite
    ids[0]["aliases"] = list(ids[0]["aliases"]) + [concept_name]
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_alias_uniqueness(), "AMBIGUOUS")


def test_hand_authored_owner_boundary_on_identity_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    ids[0]["owner_boundary"] = "BD-001"
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_schema(), "may not be hand-authored on a file_identity")


def test_hand_authored_imports_on_identity_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    ids[0]["imports"] = ["governance.semantic_os"]
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_schema(), "may not be hand-authored")


# ── negative: spine ratchet + evidence drift ────────────────────────────────────────────────

def test_spine_module_losing_its_tier1_identity_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    spine_row = next(r for r in ids if r["physical_path"] in SPINE_FILES)
    spine_row["tier"] = 2  # demote a spine identity away from Tier 1
    _assert_caught(
        _rebuild(c, b, j, ct, ids).validate_identity_spine_coverage(),
        "no Tier-1 file_identity",
    )


def test_evidence_symbol_drift_on_identity_is_caught(live):
    c, b, j, ct, ids = _clone(live)
    row_with_evidence = next(r for r in ids if r.get("evidence"))
    row_with_evidence["evidence"][0]["line"] += 5000
    _assert_caught(_rebuild(c, b, j, ct, ids).validate_evidence(), "drifted")
