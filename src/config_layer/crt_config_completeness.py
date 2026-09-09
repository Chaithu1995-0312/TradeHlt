"""
crt_config_completeness.py
================================================================================
Strict completeness check for CRTConfig field declaration -- Phase C of the
"CRT single source of truth" plan (2026-08-31 session).

Purpose
    CLAUDE.md Section 6.5's hard rule: "A missing key/section is an error (raise) — never a
    silent literal." Today, `CRTConfig` (state_identity.py) carries a Python default for every
    one of its 53 fields, so a production config that omits a field silently inherits that
    default with zero declaration anywhere on disk. Phase A's census
    (scripts/analysis/crt_threshold_authority_census.py) measured this precisely: on the active
    config, 3 fields are genuinely undeclared this way. This module is the enforcement
    primitive -- a function that, given the `crt_engine`/`params` dicts a config actually
    declares, names every field that would silently fall through.

Scope: 47 of 53 fields checked against crt_engine/params, 5 checked against crt_engine only,
1 checked against a THIRD section entirely
    **Non-scalar exclusion (5 fields).** `session_windows`, `sizing_bands`, `conf_weights` are
    excluded from the "must be in crt_engine or params" set because
    `config_layer.production_config._coerce_crt_engine` type-coerces them (JSON string times ->
    datetime.time, list-of-list -> list-of-tuple) ONLY on the way in from `crt_engine`, never
    `params`. `risk_score_weights` / `score_component_weights` are excluded too, though for a
    weaker reason: `CRTConfig.__post_init__` itself coerces list->tuple for these two regardless
    of source section, so they would actually be SAFE to declare via `params` — excluded anyway
    for consistency with the other three and because both are already correctly declared via
    `crt_engine` today, so narrowing the set buys nothing. (Corrected 2026-08-31, Phase E0 /
    CR-2: an earlier version of this docstring attributed all 5 to `_coerce_crt_engine`, which
    is wrong for these 2 specifically — the dataclass, not the loader, does the coercing.)
    Declaring any of the 5 via `params` instead of `crt_engine` resolves to the WRONG Python type
    for the 3 real cases and breaks downstream code (Phase B's first run crashed
    `backtest_v2._session` exactly this way).

    **Externally-owned exclusion (1 field).** `allowed_sessions` is excluded from
    `scalar_required_fields()` for a DIFFERENT reason than the 5 above: it is not declared in
    `crt_engine`/`params` at all on a correctly-configured file — its real owner is
    `engine_runner.allowed_sessions`, applied by
    `config_layer.production_config.resolve_allowed_sessions` AFTER the crt_engine/params merge,
    unconditionally overwriting whatever (if anything) `params` supplied. Requiring it in
    crt_engine/params is a WRONG requirement pointing at a section that cannot supply it, not a
    strict one — checked instead by `missing_externally_owned_fields()` against its real section.
    (Corrected 2026-08-31, Phase E0 / CR-1: an earlier version of this module classified
    `allowed_sessions` as genuinely undeclared, having missed this fifth authority layer
    entirely — the same class of error the Phase A census corrected once already, for
    `crt_engine`/`market_router.classes`, recurring on one specific field.)

NOT wired into the production loader's hot path
    `require_complete()` is NOT called anywhere in `production_config.py` or
    `config_builder.py`. Deliberately: a census across all 24 files under
    `configs/production/*.json` (2026-08-31) found most declare only the 5 legacy `params` keys,
    and several (`v1_multi_2026_03_force_accept.json`, `v2_test.json`,
    `v2_test_archived_20260411_200110.json`) declare ZERO `crt_engine` fields at all. Wiring a
    hard raise into the shared loader today would break loading for most production config files
    immediately -- a large, cross-file migration and a real production-code behaviour change,
    out of scope for a single-config declaration phase and requiring its own explicit
    authorization. This module exists so that decision can be made later against a real,
    tested primitive rather than from scratch.
"""
from __future__ import annotations

import dataclasses
from typing import FrozenSet

from config_layer.state_identity import CRTConfig

#: Fields that need type coercion to resolve correctly and so must stay declared via `crt_engine`
#: specifically -- see module docstring "Scope" section for which mechanism coerces which 3 of
#: these 5 (the loader's `_coerce_crt_engine`) vs the other 2 (CRTConfig.__post_init__ itself).
NONSCALAR_UNCOERCED_IN_PARAMS_FIELDS: FrozenSet[str] = frozenset({
    "session_windows",
    "sizing_bands",
    "conf_weights",
    "risk_score_weights",
    "score_component_weights",
})

#: Fields whose real declaration site is a THIRD config section entirely, applied by the loader
#: AFTER the crt_engine/params merge -- requiring them in crt_engine/params is a wrong
#: requirement, not a strict one. `allowed_sessions` -> `engine_runner.allowed_sessions`
#: (config_layer.production_config.resolve_allowed_sessions). See module docstring.
EXTERNALLY_OWNED_FIELDS: dict[str, str] = {
    "allowed_sessions": "engine_runner.allowed_sessions",
}


def all_crtconfig_fields() -> FrozenSet[str]:
    """Every field CRTConfig declares (53 as of schema authored 2026-08-31)."""
    return frozenset(f.name for f in dataclasses.fields(CRTConfig))


def scalar_required_fields() -> FrozenSet[str]:
    """Fields that MUST be explicitly declared (in `crt_engine` or `params`) under this phase's
    completeness rule -- every CRTConfig field except the 5 in
    NONSCALAR_UNCOERCED_IN_PARAMS_FIELDS (must stay in `crt_engine` specifically, checked by
    `missing_nonscalar_fields`) and the 1 in EXTERNALLY_OWNED_FIELDS (declared in a different
    section entirely, checked by `missing_externally_owned_fields`) -- 53 - 5 - 1 = 47."""
    return (
        all_crtconfig_fields()
        - NONSCALAR_UNCOERCED_IN_PARAMS_FIELDS
        - frozenset(EXTERNALLY_OWNED_FIELDS)
    )


def missing_scalar_fields(crt_engine: dict, params: dict) -> FrozenSet[str]:
    """Scalar-required fields declared in NEITHER `crt_engine` nor `params` -- these silently
    fall through to the bare CRTConfig code default with zero declaration on disk."""
    declared = set(crt_engine) | set(params)
    return scalar_required_fields() - declared


def missing_nonscalar_fields(crt_engine: dict) -> FrozenSet[str]:
    """The 5 coercion-sensitive fields not declared via `crt_engine` -- declaring them via
    `params` instead would silently misresolve (see module docstring), so this checks
    `crt_engine` specifically, not the union."""
    return NONSCALAR_UNCOERCED_IN_PARAMS_FIELDS - set(crt_engine)


def missing_externally_owned_fields(*sections: dict) -> FrozenSet[str]:
    """The externally-owned fields (currently just `allowed_sessions`) not declared in ANY of the
    given sections. Caller passes whichever real owning section(s) apply -- e.g.
    `missing_externally_owned_fields(cfg.get("engine_runner", {}))`. Distinct from
    `missing_scalar_fields`: checking crt_engine/params for these fields would always report them
    missing even when correctly configured, since that is not where they live."""
    declared: set[str] = set()
    for section in sections:
        declared |= set(section)
    return frozenset(EXTERNALLY_OWNED_FIELDS) - declared


def require_complete(
    crt_engine: dict, params: dict, *externally_owned_sections: dict, context: str = ""
) -> None:
    """Raise ValueError naming every CRTConfig field that is not explicitly declared, in its
    currently-correct location. `externally_owned_sections` are the real owning section(s) for
    EXTERNALLY_OWNED_FIELDS (e.g. pass `engine_runner`); omit to skip that check (backward
    compatible with callers that only care about the crt_engine/params surface). Read-only: takes
    plain dicts, mutates nothing, calls nothing else. Not wired into the production loader -- see
    module docstring."""
    missing_scalar = missing_scalar_fields(crt_engine, params)
    missing_nonscalar = missing_nonscalar_fields(crt_engine)
    missing_external = (
        missing_externally_owned_fields(*externally_owned_sections)
        if externally_owned_sections else frozenset()
    )
    if missing_scalar or missing_nonscalar or missing_external:
        parts = []
        if missing_scalar:
            parts.append(
                f"{len(missing_scalar)} field(s) undeclared in crt_engine/params "
                f"(would silently use the CRTConfig code default): {sorted(missing_scalar)}"
            )
        if missing_nonscalar:
            parts.append(
                f"{len(missing_nonscalar)} coercion-sensitive field(s) not declared via "
                f"crt_engine specifically: {sorted(missing_nonscalar)}"
            )
        if missing_external:
            parts.append(
                f"{len(missing_external)} externally-owned field(s) not declared in their real "
                f"section: {sorted(missing_external)}"
            )
        raise ValueError(
            f"CRTConfig completeness check failed{f' ({context})' if context else ''}: "
            + "; ".join(parts)
        )
