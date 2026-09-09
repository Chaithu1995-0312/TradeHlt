"""
Test floor for scripts/analysis/crt_config_completeness_census.py -- pins the measured blast
radius of wiring crt_config_completeness.require_complete() into the shared production loader.

This is the evidence a future "wire it in as a hard raise" decision needs, measured once here
rather than re-derived from scratch. Read-only: imports the analyzer and calls its pure function.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "analysis" / "crt_config_completeness_census.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("crt_config_completeness_census", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report():
    return _load_tool().build_census()


def test_census_covers_24_production_config_files(report):
    # If this drifts, a config file was added/removed/archived since this floor was authored --
    # re-run and read the new numbers before touching this test.
    assert report["total_files"] == 24


def test_zero_files_currently_pass_the_completeness_check(report):
    """Almost none of the 24 production config files declare every required field today -- this
    is the concrete evidence against wiring require_complete() into the shared loader without a
    dedicated, separately-authorized migration across every file.

    CORRECTED 2026-08-31 (Phase E0 / CR-1): this floor previously pinned complete=0/incomplete=23,
    asserting NO file could pass. That was itself wrong for the same reason the single-file floor
    was wrong -- `allowed_sessions` was being required in crt_engine/params, a section it cannot
    be satisfied from. With the externally-owned check now looking at each file's own
    `engine_runner` section, `v2_dispkill_shadow_2026_08.json` (47 crt_engine keys, the previous
    "best case 1 missing" file) genuinely clears all 47 scalar-required fields AND declares
    engine_runner.allowed_sessions -- it is legitimately COMPLETE, not a bug in the census."""
    assert report["complete"] == 1
    assert report["incomplete"] == 22
    assert report["skipped_or_unreadable"] == 1  # regime_map.json, a non-CRTConfig-shaped file


def test_regime_map_is_skipped_not_counted_as_a_failure(report):
    row = next(r for r in report["results"] if r["file"] == "regime_map.json")
    assert row["status"] == "SKIPPED_NOT_CRT_SHAPED"


def test_the_one_complete_file_is_correct(report):
    """Positive proof, not just a count: v2_dispkill_shadow_2026_08.json is COMPLETE and its
    completeness genuinely rests on declaring engine_runner.allowed_sessions, not on an
    externally-owned-field bug letting it through for free."""
    row = next(r for r in report["results"] if r["file"] == "v2_dispkill_shadow_2026_08.json")
    assert row["status"] == "COMPLETE"
    assert row["missing_scalar_count"] == 0
    assert row["missing_externally_owned_fields"] == []


def test_worst_and_best_case_missing_counts(report):
    """Pins the range so a future change to the excluded-field set or the config corpus is
    visible as a number moving, not silently. Worst case unchanged at 43 (v2_test.json /
    v2_test_archived_20260411_200110.json, both zero crt_engine keys AND missing
    engine_runner.allowed_sessions); best-among-incomplete is now 2, since the previous best
    (v2_dispkill_shadow_2026_08.json, 1 missing) reclassified to COMPLETE above."""
    by_file = {r["file"]: r for r in report["results"] if r["status"] == "INCOMPLETE"}
    worst = max(r["missing_scalar_count"] for r in by_file.values())
    best = min(r["missing_scalar_count"] for r in by_file.values())
    assert worst == 43
    assert best == 2
    assert by_file["v2_test.json"]["missing_scalar_count"] == 43
    assert by_file["v2_test_archived_20260411_200110.json"]["missing_scalar_count"] == 43


def test_active_config_matches_the_single_file_completeness_floor(report):
    """Cross-check against tests/test_crt_config_completeness.py's own direct measurement of the
    active config -- both must agree on the same 2-field gap (corrected from 3; allowed_sessions
    is declared via engine_runner, not genuinely missing)."""
    row = next(r for r in report["results"] if r["file"] == "v2_htfcrt_2026_08.json")
    assert row["missing_scalar_count"] == 2
    assert set(row["missing_scalar_fields"]) == {
        "displacement_origin_kill_enabled",
        "displacement_origin_kill_precedence",
    }
    assert row["missing_externally_owned_fields"] == []
