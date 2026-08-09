"""Contract floor for the GENERATED Object layer.

The Object layer's whole value is that it never guesses. These tests pin that property:

  * the denominator is DISK, not an artifact's row count (artifacts are enrichments);
  * every emitted field has a reviewed entry in FIELD_EVIDENCE_CLASS (exhaustive, both ways);
  * fields that cannot be computed honestly stay null/sentinel rather than being invented;
  * textual test hits are never conflated with coverage;
  * the whole build is deterministic.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from governance.semantic_objects import (  # noqa: E402
    FIELD_EVIDENCE_CLASS,
    _is_main_guard,
    _package_for,
    ast_import_census,
    build_module_index,
    build_objects,
    coverage_report,
    discover_universe,
)

_SEED = _REPO / "scripts" / "governance" / "seed_semantic_os.py"
_OUT = _REPO / "data" / "semantic_os" / "objects.jsonl"


@pytest.fixture(scope="module")
def objects() -> list[dict]:
    return build_objects(universe="code")


@pytest.fixture(scope="module")
def by_path(objects) -> dict[str, dict]:
    return {o["path"]: o for o in objects}


# ── universe / denominator ──────────────────────────────────────────────────────────────────

def test_universe_is_disk_not_an_artifact(objects):
    on_disk = set(discover_universe("code"))
    emitted = {o["path"] for o in objects}
    assert emitted == on_disk, "object set must equal disk enumeration exactly"


def test_universe_covers_all_three_trees(objects):
    kinds = {o["kind"] for o in objects}
    assert {"module", "script", "root_script"} <= kinds


def test_all_universe_adds_tests():
    code = set(discover_universe("code"))
    everything = set(discover_universe("all"))
    assert code < everything
    assert any(p.startswith("tests/") for p in everything - code)


def test_unknown_universe_is_rejected():
    with pytest.raises(ValueError, match="unknown universe"):
        discover_universe("everything-ever")


def test_coverage_gaps_are_published_not_hidden(objects):
    report = coverage_report(objects)
    # Each enrichment is measurably incomplete today; the report must SAY so.
    assert report["encyclopedia"]["missing_count"] > 0
    assert report["module_attribution"]["missing_count"] > 0
    assert report["graph_dot"]["absent_count"] > 0
    assert report["total_objects"] == len(objects)
    for block in ("encyclopedia", "module_attribution", "graph_dot"):
        assert report[block]["note"], f"{block} gap reported without an explanatory note"


def test_encyclopedia_is_not_the_denominator(objects):
    """813 encyclopedia rows vs 847 files on disk — adopting its count would under-report."""
    missing = [o for o in objects if "encyclopedia" not in o["present_in"]]
    assert missing, "fixture assumption broken: encyclopedia now covers everything"
    for obj in missing:
        assert obj["relevance"] is None and obj["group"] is None, (
            f"{obj['path']}: absent from the encyclopedia but carries curated fields — invented"
        )


# ── evidence-class discipline ───────────────────────────────────────────────────────────────

def test_every_emitted_field_has_an_evidence_class(objects):
    emitted: set[str] = set()
    for obj in objects:
        emitted |= set(obj)
    undeclared = sorted(emitted - set(FIELD_EVIDENCE_CLASS))
    assert not undeclared, f"fields emitted with no reviewed evidence class: {undeclared}"


def test_no_declared_evidence_class_is_dead(objects):
    emitted: set[str] = set()
    for obj in objects:
        emitted |= set(obj)
    dead = sorted(set(FIELD_EVIDENCE_CLASS) - emitted)
    assert not dead, f"FIELD_EVIDENCE_CLASS declares fields nothing emits: {dead}"


def test_evidence_classes_use_the_closed_vocabulary():
    allowed = {"PROVEN", "HEURISTIC", "TEXT_REFERENCE"}
    bad = {k: v for k, v in FIELD_EVIDENCE_CLASS.items() if v not in allowed}
    assert not bad, f"unknown evidence classes: {bad}"


def test_curated_classifications_are_not_claimed_proven():
    """These come from a human's judgement call, not from the artifact that owns the fact."""
    for field in (
        "relevance", "phase", "group", "book_status", "regime", "reachability_declared",
        "semantic_id", "semantic_name", "filename_semantic_status",
    ):
        assert FIELD_EVIDENCE_CLASS[field] == "HEURISTIC", f"{field} must not claim PROVEN"


def test_text_scans_are_labelled_text_reference():
    assert FIELD_EVIDENCE_CLASS["test_text_references"] == "TEXT_REFERENCE"
    assert FIELD_EVIDENCE_CLASS["purpose"] == "TEXT_REFERENCE"
    assert FIELD_EVIDENCE_CLASS["doc_citations"] == "HEURISTIC"


def test_text_references_and_imports_are_separate_fields(objects):
    """A test mentioning a filename is NOT the same claim as a test importing it, and the two
    must never be merged — there is no coverage data in this repo to justify the stronger claim."""
    assert "tests_importing" in FIELD_EVIDENCE_CLASS
    assert "test_text_references" in FIELD_EVIDENCE_CLASS
    differing = [
        o for o in objects
        if set(o["tests_importing"]) != set(o["test_text_references"]) and o["test_text_references"]
    ]
    assert differing, "the two test signals are identical everywhere — one is probably redundant"


# ── honesty: what must stay null ────────────────────────────────────────────────────────────

def test_owner_surface_is_never_fabricated(objects):
    """module_attribution reports UNATTRIBUTED on every row today. The Object layer must pass
    that sentinel through verbatim — inventing a surface would be the exact failure this layer
    exists to prevent."""
    surfaces = {o["owner_surface"] for o in objects if o["owner_surface"] is not None}
    assert surfaces == {"UNATTRIBUTED"}, (
        f"owner_surface carries values the attribution registry does not declare: {surfaces}"
    )


def test_absent_enrichment_yields_null_not_a_guess(by_path):
    missing = [o for o in by_path.values() if "module_attribution" not in o["present_in"]]
    assert missing, "fixture assumption broken"
    for obj in missing:
        assert obj["owner_surface"] is None
        assert obj["regime"] is None
        assert obj["reachability_declared"] is None


def test_reachability_signals_are_not_collapsed(objects):
    """`relevance` (curated), `reachability_declared` (registry), and import reachability are three
    different claims. A single `is_live` would fuse them into a false one."""
    for obj in objects:
        assert "is_live" not in obj
        assert "relevance" in obj and "reachability_declared" in obj and "imported_by" in obj


def test_graph_dot_disagreement_is_recorded_not_silently_dropped(objects):
    values = {o["graph_dot_agreement"] for o in objects}
    assert values <= {"PRESENT", "ABSENT_STALE_GRAPH", "NOT_APPLICABLE"}
    assert "ABSENT_STALE_GRAPH" in values, "graph.dot staleness must be visible, not hidden"
    for obj in objects:
        if not obj["path"].startswith("src/"):
            assert obj["graph_dot_agreement"] == "NOT_APPLICABLE", (
                "graph.dot is src/-scoped; a non-src file cannot be 'absent' from it"
            )


def test_parse_errors_are_reported_not_swallowed(objects):
    broken = [o for o in objects if o["parse_error"]]
    for obj in broken:
        assert obj["classes"] == [] and obj["functions"] == [], (
            f"{obj['path']}: unparseable yet reports symbols"
        )


def test_bom_files_are_not_reported_as_syntax_errors(by_path):
    """A UTF-8 BOM is stripped by CPython's tokenizer; reading as plain utf-8 and calling
    ast.parse would report a false syntax error."""
    bom_file = "scripts/governance/build_g001_consumer_attribution.py"
    if bom_file not in by_path:
        pytest.skip("fixture file absent")
    assert by_path[bom_file]["parse_error"] is None, "BOM misreported as a syntax error"


# ── AST import census ───────────────────────────────────────────────────────────────────────

def test_ast_census_covers_what_graph_dot_cannot(by_path):
    """graph.dot has zero scripts/ and tests/ nodes; the census must resolve their edges."""
    seed = by_path["scripts/governance/seed_semantic_os.py"]
    assert "src/governance/semantic_os.py" in seed["imports"]
    assert "src/governance/semantic_objects.py" in seed["imports"]


def test_relative_imports_resolve():
    imports, _, _, _ = ast_import_census(
        ["src/features/registry/__init__.py", "src/features/registry/_loader.py"], _REPO
    )
    resolved = imports.get("src/features/registry/__init__.py", [])
    assert "src/features/registry/_loader.py" in resolved, (
        f"relative import unresolved; got {resolved}"
    )


def test_import_edges_are_symmetric(objects):
    forward = {o["path"]: set(o["imports"]) for o in objects}
    reverse = {o["path"]: set(o["imported_by"]) for o in objects}
    for path, targets in forward.items():
        for target in targets:
            if target in reverse:
                assert path in reverse[target], f"{path} -> {target} missing from imported_by"


def test_no_self_import(objects):
    for obj in objects:
        assert obj["path"] not in obj["imports"], f"{obj['path']} imports itself"


def test_module_index_is_deterministic():
    paths = discover_universe("code")
    assert build_module_index(paths) == build_module_index(list(reversed(paths)))


def test_module_index_follows_pythonpath_order():
    index = build_module_index(["src/governance/semantic_os.py", "scripts/governance/query_x.py"])
    assert index["governance.semantic_os"] == "src/governance/semantic_os.py"


def test_unresolved_imports_are_external_only(by_path):
    """Third-party/stdlib names are recorded, never silently turned into repo edges."""
    unresolved = set(by_path["src/governance/semantic_objects.py"]["unresolved_imports"])
    assert {"ast", "hashlib", "json", "re"} <= unresolved
    assert not any(u.endswith(".py") for u in unresolved)


# ── source facts ────────────────────────────────────────────────────────────────────────────

def test_has_main_is_ast_derived_not_a_text_scan(by_path):
    assert by_path["scripts/governance/seed_semantic_os.py"]["has_main"] is True
    # This module mentions neither guard; a substring scan would false-positive on prose.
    assert by_path["src/governance/semantic_objects.py"]["has_main"] is False


def test_is_main_guard_rejects_lookalikes():
    import ast as _ast

    yes = _ast.parse('if __name__ == "__main__":\n    pass').body[0]
    no1 = _ast.parse('if __name__ == "__not_main__":\n    pass').body[0]
    no2 = _ast.parse('if x == "__main__":\n    pass').body[0]
    assert _is_main_guard(yes) and not _is_main_guard(no1) and not _is_main_guard(no2)


def test_package_strips_src_to_match_graph_dot():
    assert _package_for("src/features/feature_pipeline.py") == "features"
    assert _package_for("src/features/registry/_loader.py") == "features.registry"
    assert _package_for("scripts/governance/seed_semantic_os.py") == "scripts.governance"
    assert _package_for("audit.py") is None


def test_sha256_and_bytes_are_recomputed(by_path):
    import hashlib

    obj = by_path["src/governance/semantic_os.py"]
    raw = (_REPO / obj["path"]).read_bytes()
    assert obj["bytes"] == len(raw)
    assert obj["sha256"] == hashlib.sha256(raw).hexdigest()


# ── semantic joins ──────────────────────────────────────────────────────────────────────────

def test_boundary_membership_flows_into_objects(by_path):
    obj = by_path["src/features/feature_pipeline.py"]
    assert obj["owner_boundary"], "spine module has no owning boundary"
    assert obj["concepts"], "owning boundary contributes no concepts"


def test_config_keys_split_proven_from_heuristic(by_path):
    obj = by_path["src/features/feature_pipeline.py"]
    assert obj["config_keys"], "no READ_AND_USED config keys resolved for the pipeline"
    assert not set(obj["config_keys"]) & set(obj["config_keys_heuristic"]), "classes overlap"


def test_findings_evidence_is_exact_path_match(by_path):
    obj = by_path["src/features/feature_pipeline.py"]
    assert obj["findings_evidence"], "no findings cite the feature pipeline"
    assert all(f.startswith("F-") for f in obj["findings_evidence"])


# ── determinism / seed ──────────────────────────────────────────────────────────────────────

def test_build_is_deterministic():
    assert build_objects(universe="code") == build_objects(universe="code")


def test_objects_are_sorted_by_id(objects):
    assert [o["id"] for o in objects] == sorted(o["id"] for o in objects)


def test_object_ids_are_path_derived_and_unique(objects):
    ids = [o["id"] for o in objects]
    assert len(set(ids)) == len(ids)
    for obj in objects:
        assert obj["id"] == f"OBJ:{obj['path']}"


def test_seed_objects_round_trip_and_are_byte_identical():
    def _run():
        proc = subprocess.run(
            [sys.executable, str(_SEED), "--objects"], cwd=_REPO, capture_output=True, text=True
        )
        assert proc.returncode == 0, f"seed --objects failed: {proc.stdout}\n{proc.stderr}"
        return _OUT.read_bytes()

    assert _run() == _run(), "object projection is not byte-identical across reruns"
    rows = [json.loads(l) for l in _OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == len(build_objects(universe="code"))
