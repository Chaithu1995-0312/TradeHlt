"""
Test floor for src/config_layer/crt_config_completeness.py -- Phase C of the "CRT single source
of truth" plan (2026-08-31 session).

Two things this floor must prove, not just assert in isolation:
  1. Non-vacuity: the check currently DOES raise against the real, unmodified active config
     (which still has only 5 params + 45 crt_engine keys, per Phase A's census) -- a completeness
     checker that never fails is not a checker.
  2. Satisfiability: the check DOES pass against Phase B's proven "48 fields declared" params dict
     -- so the primitive correctly recognizes success, not just failure.
Both are read from real repo state, not synthetic fixtures, so this floor breaks the moment
either side of that story stops being true (e.g. if a future phase actually writes the declared
params into the active config, requirement 1 should flip and this test must be updated then --
not silently left green on a stale premise).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from config_layer.crt_config_completeness import (  # noqa: E402
    EXTERNALLY_OWNED_FIELDS,
    NONSCALAR_UNCOERCED_IN_PARAMS_FIELDS,
    all_crtconfig_fields,
    missing_externally_owned_fields,
    missing_nonscalar_fields,
    missing_scalar_fields,
    require_complete,
    scalar_required_fields,
)


def test_all_fields_count_matches_measured_crtconfig():
    assert len(all_crtconfig_fields()) == 53


def test_excluded_set_is_exactly_five_fields():
    assert NONSCALAR_UNCOERCED_IN_PARAMS_FIELDS == {
        "session_windows", "sizing_bands", "conf_weights",
        "risk_score_weights", "score_component_weights",
    }


def test_externally_owned_set_is_allowed_sessions():
    """Corrected 2026-08-31 (Phase E0 / CR-1): allowed_sessions is NOT a scalar-required field --
    it is owned by a THIRD config section (engine_runner), applied by the loader after the
    crt_engine/params merge. Requiring it in crt_engine/params is a wrong requirement, not a
    strict one."""
    assert EXTERNALLY_OWNED_FIELDS == {"allowed_sessions": "engine_runner.allowed_sessions"}


def test_scalar_required_is_47_fields():
    """53 - 5 (nonscalar, coercion-sensitive) - 1 (externally owned) = 47. Was pinned at 48
    before Phase E0 corrected the externally-owned exclusion."""
    assert len(scalar_required_fields()) == 47


def _load_active_config() -> dict:
    version = (_REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(
        encoding="utf-8"
    ).strip()
    return json.loads(
        (_REPO / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8")
    )


def test_active_config_is_currently_incomplete_non_vacuity():
    """The real active config, unmodified, must currently FAIL this check -- proves the checker
    is non-vacuous. If this ever goes green because someone declared the params for real, that
    is GOOD NEWS but this test must be consciously updated to reflect it, not left passing on a
    premise that no longer holds.

    CORRECTED 2026-08-31 (Phase E0 / CR-1): `allowed_sessions` was previously asserted as one of
    the 3 missing fields -- wrong, it is declared via `engine_runner.allowed_sessions` and is now
    excluded from `scalar_required_fields()` entirely (checked separately below and by
    `test_allowed_sessions_satisfies_the_externally_owned_check`)."""
    cfg = _load_active_config()
    missing = missing_scalar_fields(cfg.get("crt_engine", {}), cfg.get("params", {}))
    assert missing == {
        "displacement_origin_kill_enabled",
        "displacement_origin_kill_precedence",
    }
    with pytest.raises(ValueError, match="undeclared in crt_engine/params"):
        require_complete(cfg.get("crt_engine", {}), cfg.get("params", {}), context="active config")


def test_active_config_nonscalar_fields_are_all_declared_via_crt_engine():
    """The 5 coercion-sensitive fields ARE already declared, correctly, via crt_engine on the
    active config -- this axis is not the source of today's incompleteness."""
    cfg = _load_active_config()
    assert missing_nonscalar_fields(cfg.get("crt_engine", {})) == frozenset()


def test_allowed_sessions_satisfies_the_externally_owned_check():
    """The real active config DOES declare engine_runner.allowed_sessions -- proves
    missing_externally_owned_fields correctly recognizes a satisfied externally-owned field, not
    just an absent one."""
    cfg = _load_active_config()
    assert missing_externally_owned_fields(cfg.get("engine_runner", {})) == frozenset()
    # And require_complete, given the real owning section, raises ONLY on the 2 genuinely
    # undeclared fields -- allowed_sessions must not appear in the error at all.
    with pytest.raises(ValueError) as exc_info:
        require_complete(
            cfg.get("crt_engine", {}), cfg.get("params", {}), cfg.get("engine_runner", {}),
            context="active config, externally-owned section supplied",
        )
    assert "allowed_sessions" not in str(exc_info.value)


def test_missing_externally_owned_fields_detects_a_genuine_absence():
    """Mutation test: an EMPTY engine_runner section must report allowed_sessions missing --
    proves the check actually fires, not just passes."""
    assert missing_externally_owned_fields({}) == {"allowed_sessions"}


def test_phase_b_declared_params_satisfies_completeness():
    """Rebuild Phase B's proven 48-field params dict (same function, same active config) and
    confirm it clears the completeness check -- the primitive must recognize success, not just
    detect failure."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "crt_threshold_authority_census",
        _REPO / "scripts" / "analysis" / "crt_threshold_authority_census.py",
    )
    census_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(census_mod)
    report = census_mod.build_census()

    spec2 = importlib.util.spec_from_file_location(
        "crt_declare_all_knobs_parity",
        _REPO / "scripts" / "analysis" / "crt_declare_all_knobs_parity.py",
    )
    parity_mod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(parity_mod)

    cfg = _load_active_config()
    declared_params = parity_mod.build_declared_params(cfg, report)
    assert len(declared_params) == 47

    missing = missing_scalar_fields(cfg.get("crt_engine", {}), declared_params)
    assert missing == frozenset()
    require_complete(cfg.get("crt_engine", {}), declared_params, context="phase B declared")


def test_require_complete_raises_on_a_stripped_field():
    """Mutation test: strip one known-present field from a complete dict and confirm the check
    catches exactly that field, not a vacuous pass."""
    cfg = _load_active_config()
    crt_engine = dict(cfg.get("crt_engine", {}))
    # atr_period is declared in crt_engine on the active config -- strip it.
    assert "atr_period" in crt_engine
    del crt_engine["atr_period"]

    with pytest.raises(ValueError) as exc_info:
        require_complete(crt_engine, cfg.get("params", {}), context="mutation test")
    assert "atr_period" in str(exc_info.value)
