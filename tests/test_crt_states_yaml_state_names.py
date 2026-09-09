"""market_crt_states.yaml `states[].name` parity — Phase F1 (CH-crt-sot-2026-08-31).

`tests/test_crt_states_yaml_transition_parity.py` (SK-0, 2026-08-18) already guards
`market_crt_states.yaml:valid_transitions` against `state_identity.VALID_TRANSITIONS`.
`tests/test_crt_state_invariants.py` already guards the CRTState *enum membership* against
`active_models.yaml`. Neither one — nor anything else in the repo — checks the OTHER
state-bearing block in the same file: `states:` (the 9 entries carrying the resolver's `when:`
predicates). That is the gap this file closes.

WHY THIS MATTERS (not cosmetic)
--------------------------------
`crt_state_resolver.py::_find_state_def(name)` returns `{}` on a miss, and
`_predicates_match({}, ...)` treats an empty `when` as **unconditionally TRUE**
(`if not when: return True`). So a typo'd or renamed `states[].name` does not error — it silently
degrades to an always-true predicate. Concretely: `_check_resolution` calls
`self._find_state_def("RANGE").get("when", {})`; misspell `RANGE` in the YAML and RESOLUTION
fires on every bar with a trade active, with no error anywhere. Same silent-gap class as
F-079/F-056/F-083/F-085 (a skipped check is indistinguishable from an absent one).

THE 9-vs-12 DIFFERENCE IS DECLARED, NOT TOLERATED
----------------------------------------------------
`CRTState` has 12 members; `states:` declares only 9. The 3 absent
(`RANGE_C1`/`MANIPULATION_C2`/`DISTRIBUTION_C3`) are the parent-timeframe 3-candle sub-graph
(CH-htfcrt-parent-candle-smc-v1) — the resolver runs the M15 execution-timeframe track only, so
they legitimately have no resolver predicate. Pinned below by name, with a reason, mirroring the
SK-0 file's own `_DECLARED_ALLOWANCES` discipline for `SHADOW_PENDING -> EXPANSION`: if this set
ever changes, that is a fact requiring a deliberate decision, not silent drift.

THE LOAD-TIME GUARD (crt_state_resolver.py, added same turn as this floor)
-----------------------------------------------------------------------------
`CRTStateResolver.__init__` -> `_validate_predicates()` now raises `PredicateValidationError` on
any `states[].name` that is not a real `CRTState` member, or that repeats. Proven INERT TODAY
(construction against the real, unmodified config below) and PROVEN EFFECTIVE (the mutation test
plants a typo in a scratch copy and asserts the exception fires) — the F-068 lesson: a guard
whose only evidence is its own docstring is worth nothing.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from config_layer.state_identity import CRTState  # noqa: E402
from features.crt_state_resolver import (  # noqa: E402
    CRTStateResolver,
    PredicateValidationError,
)

_YAML_PATH = _REPO / "configs" / "formulas" / "market_crt_states.yaml"

#: The 3 CRTState members declared in valid_transitions (the parent-CRT sub-graph) that
#: DELIBERATELY have no entry in `states:` -- the resolver is M15-only. Pinned by name + reason,
#: same discipline as SK-0's `_DECLARED_ALLOWANCES`. If this set changes, update it here with a
#: source-verified reason, not silently.
_PARENT_CRT_STATES_WITHOUT_RESOLVER_PREDICATE = {
    "RANGE_C1": "parent-timeframe 3-candle sub-graph (CH-htfcrt-parent-candle-smc-v1); "
                "the resolver runs the M15 execution-timeframe track only",
    "MANIPULATION_C2": "see RANGE_C1",
    "DISTRIBUTION_C3": "see RANGE_C1",
}


def _yaml_state_names() -> list[str]:
    doc = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    return [sd["name"] for sd in doc["states"]]


def test_every_declared_state_name_is_a_real_crtstate() -> None:
    known = {s.name for s in CRTState}
    unknown = sorted(set(_yaml_state_names()) - known)
    assert not unknown, (
        f"market_crt_states.yaml:states declares non-CRTState name(s): {unknown}"
    )


def test_no_duplicate_state_names() -> None:
    names = _yaml_state_names()
    assert len(names) == len(set(names)), (
        f"market_crt_states.yaml:states has duplicate name(s): "
        f"{sorted({n for n in names if names.count(n) > 1})}"
    )


def test_the_nine_declared_states_are_exactly_the_non_parent_crt_states() -> None:
    """Pins the 9-vs-12 gap by NAME, not just by count. If a future CRT state legitimately
    gains a resolver predicate (or an existing one loses one), this must change deliberately."""
    declared = set(_yaml_state_names())
    all_states = {s.name for s in CRTState}
    missing = all_states - declared
    assert missing == set(_PARENT_CRT_STATES_WITHOUT_RESOLVER_PREDICATE), (
        f"states[] gap changed: expected exactly the parent-CRT set "
        f"{sorted(_PARENT_CRT_STATES_WITHOUT_RESOLVER_PREDICATE)} to be absent, got {sorted(missing)}. "
        "If this is intentional, update _PARENT_CRT_STATES_WITHOUT_RESOLVER_PREDICATE with a "
        "source-verified reason."
    )
    assert len(declared) == 9
    assert len(all_states) == 12


def test_resolver_constructs_cleanly_against_the_real_config() -> None:
    """Inert-today proof: the new fail-closed guard must not raise on the unmodified,
    currently-valid config."""
    CRTStateResolver()  # raises on failure; no assertion needed beyond "did not raise"


def test_load_time_guard_rejects_an_unknown_state_name() -> None:
    """Mutation test: plant a typo in a SCRATCH copy of the real config (never the tracked
    file) and confirm PredicateValidationError actually fires, naming the bad value."""
    doc = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    for sd in doc["states"]:
        if sd["name"] == "RANGE":
            sd["name"] = "RNAGE"  # deliberate typo
            break
    else:
        pytest.fail("fixture assumption broken: 'RANGE' not found in states[] to mutate")

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    try:
        yaml.safe_dump(doc, tmp)
        tmp.close()
        with pytest.raises(PredicateValidationError, match="RNAGE"):
            CRTStateResolver(config_path=tmp.name)
    finally:
        os.unlink(tmp.name)


def test_load_time_guard_rejects_a_duplicate_state_name() -> None:
    """Mutation test: duplicate an existing valid state name in a scratch copy and confirm the
    guard catches it (not just unknown names)."""
    doc = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    range_def = next(sd for sd in doc["states"] if sd["name"] == "RANGE")
    doc["states"].append(dict(range_def))  # exact duplicate

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    try:
        yaml.safe_dump(doc, tmp)
        tmp.close()
        with pytest.raises(PredicateValidationError, match="declared more than once"):
            CRTStateResolver(config_path=tmp.name)
    finally:
        os.unlink(tmp.name)
