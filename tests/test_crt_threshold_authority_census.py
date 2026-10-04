"""
Test floor for scripts/analysis/crt_threshold_authority_census.py.

Pins the CRT config authority census (CODE default / ROUTER class base / crt_engine / params /
RESOLVED-via-the-real-production-loader / YAML resolver thresholds) as the frozen instrument for
the "CRT single source of truth" migration (2026-08-31 plan). A later phase must MOVE a known
divergence or shrink the undeclared set, never silently gain a new one -- this floor is the
tripwire for that.

v2 (2026-08-31, same day as v1): v1 pinned a 5-key "diverged" set computed by comparing CODE vs
YAML vs params as an undifferentiated 3-way set. That conflated two different questions -- "does
production tuning differ from the raw code default" (expected, 5 keys, not a problem) and "does
the YAML the resolver reads disagree with what the engine actually runs" (the real question, only
2 keys). Corrected here to pin the right two things instead: the UNDECLARED set (real
silent-default risk, 3 fields) and the YAML-vs-RESOLVED set (real resolver/engine mismatch,
2 fields). See the script's own module docstring "History" section for the full account.

Read-only: imports the analyzer module and calls its pure functions. Does not shell out.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "analysis" / "crt_threshold_authority_census.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("crt_threshold_authority_census", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report():
    mod = _load_tool()
    return mod.build_census()


def test_tool_is_importable_and_runnable(report):
    assert isinstance(report, dict)
    assert report["rows"]


def test_active_version_is_expected(report):
    # If this ever fails, ACTIVE_VERSION moved since this floor was authored -- re-run the
    # census against the new active config before touching the pinned sets below (do not just
    # bump this string).
    assert report["active_version"] == "v2_htfcrt_2026_08"


def test_authority_counts_match_measured_census(report):
    assert report["field_count"] == 53
    assert report["router_field_count"] == 5
    assert report["crt_engine_field_count"] == 45
    assert report["params_field_count"] == 5
    assert report["yaml_threshold_count"] == 18


def test_pinned_undeclared_set_is_exactly_two_fields(report):
    """The real silent-default risk class: fields absent from ROUTER, crt_engine, params, AND
    (for the 1 externally-owned field) their real owning section -- where RESOLVED falls through
    to the bare CRTConfig default with zero declaration anywhere. Phase C ("CRTConfig becomes
    defaultless") should SHRINK this toward empty -- update this test in the SAME turn as that
    phase, with the finding cited, never silently.

    CORRECTED 2026-08-31 (Phase E0 / CR-1): this floor previously pinned a 3-field set including
    `allowed_sessions`, which is NOT genuinely undeclared -- it is declared via
    `engine_runner.allowed_sessions`, a fifth authority the census (v2) had not yet modeled. The
    census was fixed to check that section (v3); this floor is corrected to match, in the same
    turn, per the file's own stated update discipline."""
    expected = {
        "displacement_origin_kill_enabled",
        "displacement_origin_kill_precedence",
    }
    assert set(report["undeclared_fields"]) == expected


def test_allowed_sessions_is_declared_via_engine_runner_not_undeclared(report):
    """Positive proof of the CR-1 fix: allowed_sessions must classify as declared, with
    declared_where naming its real owning section, not silently absent from the undeclared set
    for the wrong reason."""
    row = next(r for r in report["rows"] if r["field"] == "allowed_sessions")
    assert "engine_runner" in row["declared_where"]
    assert row["classification"] in ("DECLARED_DEFAULT", "DECLARED_TUNED")
    assert "allowed_sessions" not in report["undeclared_fields"]


def test_pinned_yaml_vs_resolved_divergence_is_exactly_one_field(report):
    """The real resolver-vs-engine mismatch: CRTStateResolver reads market_crt_states.yaml, but
    crt_engine_v2 runs on the RESOLVED production value. NOTE: 3 other keys (body_ratio_min,
    atr_multiplier_min, expansion_atr_min_distance) differ from the bare CODE default but agree
    between YAML and RESOLVED -- that is expected production tuning, not a resolver/engine
    mismatch, and must not be re-added to this set.

    CORRECTED 2026-08-31 (Phase E1): was 2 fields (retest_atr_depth_fraction,
    retest_depth_max). retest_depth_max REMOVED after being measured non-pivotal for the
    resolver at 0.08/0.15/0.25 (scripts/research/e1_retest_depth_max_probe.py -- byte-identical
    agreement and RETEST recall across all three) and then aligned in market_crt_states.yaml
    0.08 -> 0.15 to match production. retest_atr_depth_fraction remains -- a DEAD duplicate the
    resolver never reads (Phase D, consumed:false), retained per Phase E2 rather than treated as
    a live value conflict."""
    expected = {"retest_atr_depth_fraction"}
    assert set(report["yaml_diverged_fields"]) == expected


def test_retest_depth_max_is_declared_tuned_and_no_longer_diverged(report):
    """CORRECTED 2026-08-31 (Phase E1): was a genuine 3-way split (code 0.25 / resolved 0.15 /
    yaml 0.08). YAML aligned to 0.15 after the divergence was measured non-pivotal -- YAML and
    RESOLVED now agree; CODE's bare default is the only value that still differs, which is
    expected production tuning, not a resolver/engine mismatch."""
    row = next(r for r in report["rows"] if r["field"] == "retest_depth_max")
    assert row["code_default"] == 0.25
    assert row["resolved_xauusd"] == 0.15
    assert row["yaml_threshold"] == 0.15
    assert row["classification"] == "DECLARED_TUNED"
    assert row["yaml_vs_resolved_verdict"] == "agree"


def test_router_class_differentiation_is_inert_for_all_five_declared_keys(report):
    """Verified finding: market_router.classes[FOREX] and [CRYPTO] declare different values for
    5 keys, but params unconditionally overrides all 5 for every instrument, so
    load_prod_config_from_registry resolves identically for a FOREX and a CRYPTO instrument on
    these keys despite the router declaring per-class differentiation."""
    expected = {
        "body_ratio_min", "atr_multiplier_min", "expansion_atr_min_distance",
        "retest_atr_depth_fraction", "retest_depth_max",
    }
    assert set(report["router_class_differentiation_inert_fields"]) == expected


def test_declared_default_vs_tuned_split(report):
    """46 fields are explicitly declared (mostly in crt_engine, plus allowed_sessions via
    engine_runner) at a value that happens to equal the CRTConfig code default; 5 are declared
    and tuned away from it; 2 are undeclared. This is the corrected replacement for v1's wrong
    "48 of 53 run on defaults" framing -- most of those 48 are committed values that coincide
    with the default, not silent inheritance.

    CORRECTED 2026-08-31 (Phase E0 / CR-1): counts were 45/5/3 before allowed_sessions moved from
    UNDECLARED to DECLARED_DEFAULT (its resolved value, ('LONDON','NEWYORK','OVERLAP'), equals
    the CRTConfig bare default -- it is declared, just coincidentally at the default value)."""
    from collections import Counter
    counts = Counter(r["classification"] for r in report["rows"])
    assert counts["DECLARED_DEFAULT"] == 46
    assert counts["DECLARED_TUNED"] == 5
    assert counts["UNDECLARED"] == 2


def test_check_flag_exits_zero_while_pinned_sets_hold():
    mod = _load_tool()
    assert mod.main(["--check"]) == 0
