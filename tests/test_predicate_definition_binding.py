"""RC-3 / RC-4 — the ontology `definition` IS the meaning; `structure.predicates` conforms to it.

This is the test that makes the 2026-08-19 decision real rather than declarative.

SK-1 proved the nine migrated sweep sites agree **with each other**. It did not prove they
agree with the **declared meaning**, because the meaning was a prose `formula:` string. Here
the ontology `definition:` block is evaluated by `features.registry.predicate_registry` and
compared against `structure.predicates` over the pinned slice. If they ever diverge, the
Python has stopped being a conforming implementation and this fails — which is the whole
point of demoting it from authority to HOW-computation.

Also pins the two properties that keep the evaluator honest:
  * **Generic by construction** — a synthetic `SP-099` node the evaluator has never heard of
    must evaluate purely from YAML. If someone adds `if semantic_id == "SP-001"`, this still
    passes, so the real guard is that SP-099 works *at all* with no code change.
  * **Fail-closed vocabulary** — `eval`-shaped operators, arithmetic, literals, undeclared
    names, and HOW-policy thresholds are rejected, not silently tolerated.
"""
from __future__ import annotations

import copy
import csv
from pathlib import Path

import pytest

from features.registry import load_ontology
from features.registry.predicate_registry import (
    ENUM_TOKENS_V1,
    OPERATORS,
    PredicateDefinitionError,
    evaluate_predicate,
    validate_predicate_definitions,
)
from structure.predicates import directional_impulse, swept_high, swept_low

_SLICE_MONTH = "2026-03"
_ENVELOPE = 14
_CSV = Path(__file__).resolve().parents[1] / "data" / "mt5" / "XAUUSD_M15.csv"


@pytest.fixture(scope="module")
def ont() -> dict:
    return load_ontology()


@pytest.fixture(scope="module")
def bars() -> list[dict]:
    if not _CSV.exists():                                     # pragma: no cover
        pytest.skip(f"pinned corpus absent: {_CSV}")
    rows = [r for r in csv.DictReader(_CSV.open(encoding="utf-8"))
            if r["timestamp"][:7] == _SLICE_MONTH]
    if not rows:                                              # pragma: no cover
        pytest.skip(f"pinned slice {_SLICE_MONTH} absent")
    return rows


# ── Static contract ──────────────────────────────────────────────────────────

def test_all_definitions_are_valid(ont) -> None:
    assert validate_predicate_definitions(ont) == []


def test_sp003_is_declared_deferred_not_silently_missing(ont) -> None:
    """An absent definition must be an explicit, reasoned deferral — never an oversight."""
    deferred = (ont["spec_schema"]["semantic_registry"] or {}).get("definition_deferred") or {}
    assert "SP-003" in deferred, "SP-003 has no definition; it must be listed as deferred"
    assert "OQ7" in deferred["SP-003"], "the deferral must name the open fork it is waiting on"


def test_operator_vocabulary_is_pinned() -> None:
    """Widening the closed set is a schema bump; this fails if someone adds `call` 'just once'."""
    assert OPERATORS == frozenset({"gt", "lt", "ge", "le", "eq", "ne", "and", "or", "not"})
    assert ENUM_TOKENS_V1 == frozenset({"LONG", "SHORT"})


# ── RC-4: the binding — declared meaning vs the Python implementation ─────────

def test_sp001_definition_binds_to_structure_predicates(bars) -> None:
    """SP-001's declared meaning and `structure.predicates` agree on every bar of the slice."""
    H = [float(r["high"]) for r in bars]
    L = [float(r["low"]) for r in bars]
    C = [float(r["close"]) for r in bars]

    hi = lo = compared = 0
    for i in range(_ENVELOPE, len(bars)):
        h_ref, l_ref = max(H[i - _ENVELOPE:i]), min(L[i - _ENVELOPE:i])
        got = evaluate_predicate(
            "SP-001",
            {"high": H[i], "low": L[i], "close": C[i], "h_ref": h_ref, "l_ref": l_ref},
        )
        py_hi = swept_high(H[i], C[i], h_ref)
        py_lo = swept_low(L[i], C[i], l_ref)

        assert got["clauses"]["swept_high"] == py_hi, f"SP-001 swept_high diverged at bar {i}"
        assert got["clauses"]["swept_low"] == py_lo, f"SP-001 swept_low diverged at bar {i}"
        assert got["hit"] == (py_hi or py_lo)

        if got["hit"]:
            # the emit contract: direction + sweep_price follow the winning clause
            assert got["direction"] == ("SHORT" if py_hi else "LONG")
            assert got["sweep_price"] == (H[i] if py_hi else L[i])
        compared += 1
        hi += py_hi
        lo += py_lo

    assert compared >= 2000, f"only {compared} comparisons — slice too small to be decisive"
    assert hi > 0 and lo > 0, f"VACUOUS: high={hi} low={lo}"


def test_sp002_definition_binds_to_structure_predicates(bars) -> None:
    O = [float(r["open"]) for r in bars]
    C = [float(r["close"]) for r in bars]
    H = [float(r["high"]) for r in bars]
    L = [float(r["low"]) for r in bars]

    long_fired = short_fired = 0
    for i in range(1, len(bars)):
        for is_long, sweep_price in ((True, L[i - 1]), (False, H[i - 1])):
            got = evaluate_predicate(
                "SP-002",
                {"open": O[i], "close": C[i], "sweep_price": sweep_price, "is_long": is_long},
            )
            py = directional_impulse(O[i], C[i], sweep_price, is_long=is_long)
            assert got["hit"] == py, f"SP-002 diverged at bar {i}, is_long={is_long}"
            if py and is_long:
                long_fired += 1
            elif py:
                short_fired += 1

    assert long_fired > 0 and short_fired > 0, (
        f"VACUOUS: long={long_fired} short={short_fired}"
    )


def test_sp002_direction_is_an_inherited_input_not_re_derived(bars) -> None:
    """The declared meaning inherits direction, exactly as the Python does (F-074)."""
    for is_long, expected in ((True, True), (False, False)):
        got = evaluate_predicate(
            "SP-002", {"open": 100.0, "close": 104.0, "sweep_price": 103.0, "is_long": is_long}
        )
        assert got["hit"] is expected


# ── Boundary-exact binding: the ONLY place strict-vs-inclusive is observable ──
#
# The corpus loop above cannot see this difference. `close < ref` and `close <= ref` diverge
# only when close == ref EXACTLY, and real float prices essentially never land there — a
# mutation of the declared meaning from `lt` to `le` passed the corpus test unchanged
# (verified 2026-08-19). A gate that cannot fail is not a gate, so the binding is pinned here
# on hand-built inputs that sit exactly on the boundary.

_BOUNDARY_CASES = [
    # (high, low, close, h_ref, l_ref, why)
    (101.0, 95.0, 100.0, 100.0, 90.0, "close EXACTLY at h_ref — strict: not a sweep"),
    (100.0, 95.0,  99.0, 100.0, 90.0, "high EXACTLY at h_ref — no pierce"),
    (105.0, 90.0,  90.0, 100.0, 90.0, "close EXACTLY at l_ref — strict: not a sweep"),
    (105.0, 90.0,  95.0, 100.0, 90.0, "low EXACTLY at l_ref — no pierce"),
    (101.0, 95.0,  99.0, 100.0, 90.0, "clean high sweep"),
    (105.0, 89.0,  95.0, 100.0, 90.0, "clean low sweep"),
    (100.0, 90.0,  95.0, 100.0, 90.0, "both refs touched, neither pierced"),
]


@pytest.mark.parametrize("high,low,close,h_ref,l_ref,why", _BOUNDARY_CASES)
def test_sp001_binding_on_exact_boundaries(high, low, close, h_ref, l_ref, why) -> None:
    """Declared meaning == Python at the exact-equality boundary. Catches lt/le drift."""
    got = evaluate_predicate(
        "SP-001", {"high": high, "low": low, "close": close, "h_ref": h_ref, "l_ref": l_ref}
    )
    assert got["clauses"]["swept_high"] is swept_high(high, close, h_ref), why
    assert got["clauses"]["swept_low"] is swept_low(low, close, l_ref), why


@pytest.mark.parametrize(
    "open_,close,sweep_price,is_long,why",
    [
        (100.0, 100.0, 99.0, True,  "close EXACTLY at open — no body, not an impulse"),
        (100.0, 103.0, 103.0, True, "close EXACTLY at sweep_price — did not CLEAR it"),
        (100.0, 103.0, 103.0, False, "mirror: close exactly at sweep_price, short"),
        (100.0, 100.0, 101.0, False, "no body, short side"),
        (100.0, 104.0, 103.0, True,  "clean long impulse"),
        (100.0,  96.0,  97.0, False, "clean short impulse"),
    ],
)
def test_sp002_binding_on_exact_boundaries(open_, close, sweep_price, is_long, why) -> None:
    got = evaluate_predicate(
        "SP-002",
        {"open": open_, "close": close, "sweep_price": sweep_price, "is_long": is_long},
    )
    assert got["hit"] is directional_impulse(open_, close, sweep_price, is_long=is_long), why


# ── Generic-by-construction: a node the evaluator has never seen ─────────────

def test_evaluator_is_generic_over_an_unknown_node(ont) -> None:
    """A synthetic SP-099 that exists only as YAML must evaluate with no code change."""
    fake = copy.deepcopy(ont)
    fake["structural_predicates"]["synthetic_probe"] = {
        "id": "SP-099",
        "definition": {
            "schema": "predicate_definition/v1",
            "inputs": ["a", "b", "c"],
            "clauses": {
                "a_over_b": {"op": "gt", "left": "a", "right": "b"},
                "c_under_b": {"op": "lt", "left": "c", "right": "b"},
                "both": {"op": "and", "args": ["a_over_b", "c_under_b"]},
            },
            "emit": {"schema": "predicate_emit/v1", "hit": "both"},
        },
    }
    assert evaluate_predicate("SP-099", {"a": 2.0, "b": 1.0, "c": 0.0}, ontology=fake)["hit"] is True
    assert evaluate_predicate("SP-099", {"a": 0.0, "b": 1.0, "c": 0.0}, ontology=fake)["hit"] is False


# ── Fail-closed ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_op", ["call", "import", "__import__", "add", "mul", "abs", "eval"])
def test_unknown_operator_is_rejected(ont, bad_op) -> None:
    fake = copy.deepcopy(ont)
    fake["structural_predicates"]["synthetic_probe"] = {
        "id": "SP-099",
        "definition": {
            "schema": "predicate_definition/v1",
            "inputs": ["a", "b"],
            "clauses": {"x": {"op": bad_op, "left": "a", "right": "b"}},
            "emit": {"schema": "predicate_emit/v1", "hit": "x"},
        },
    }
    with pytest.raises(PredicateDefinitionError):
        evaluate_predicate("SP-099", {"a": 1.0, "b": 2.0}, ontology=fake)


def test_undeclared_name_is_rejected(ont) -> None:
    fake = copy.deepcopy(ont)
    fake["structural_predicates"]["synthetic_probe"] = {
        "id": "SP-099",
        "definition": {
            "schema": "predicate_definition/v1",
            "inputs": ["a"],
            "clauses": {"x": {"op": "gt", "left": "a", "right": "smuggled"}},
            "emit": {"schema": "predicate_emit/v1", "hit": "x"},
        },
    }
    with pytest.raises(PredicateDefinitionError):
        evaluate_predicate("SP-099", {"a": 1.0, "smuggled": 0.0}, ontology=fake)


def test_how_policy_threshold_as_input_is_a_validator_error(ont) -> None:
    """A predicate that reads a magnitude threshold has stopped being a meaning."""
    fake = copy.deepcopy(ont)
    fake["structural_predicates"]["synthetic_probe"] = {
        "id": "SP-099",
        "definition": {
            "schema": "predicate_definition/v1",
            "inputs": ["close", "body_ratio_min"],
            "clauses": {"x": {"op": "gt", "left": "close", "right": "body_ratio_min"}},
            "emit": {"schema": "predicate_emit/v1", "hit": "x"},
        },
    }
    problems = validate_predicate_definitions(fake)
    assert any("body_ratio_min" in p and "HOW-policy" in p for p in problems), problems


def test_unknown_semantic_id_is_rejected(ont) -> None:
    with pytest.raises(PredicateDefinitionError):
        evaluate_predicate("SP-404", {}, ontology=ont)


def test_deferred_node_cannot_be_evaluated(ont) -> None:
    with pytest.raises(PredicateDefinitionError):
        evaluate_predicate("SP-003", {"close": 1.0}, ontology=ont)


def test_module_contains_no_eval_machinery() -> None:
    """AST guard: the doctrine is 'never eval', so no CALL to eval machinery may exist.

    Deliberately structural, not textual. A substring scan flags the module's own docstring —
    which names ast.literal_eval in order to FORBID it — so it would fail on prose that says
    exactly the right thing. Parsing and inspecting call targets checks the code itself.
    """
    import ast as _ast

    src = (Path(__file__).resolve().parents[1]
           / "src" / "features" / "registry" / "predicate_registry.py").read_text(encoding="utf-8")
    tree = _ast.parse(src)

    forbidden = {"eval", "exec", "compile", "literal_eval"}
    hits: list[str] = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, _ast.Name) else (
                fn.attr if isinstance(fn, _ast.Attribute) else None
            )
            if name in forbidden:
                hits.append(f"{name}() at line {node.lineno}")
        elif isinstance(node, (_ast.Import, _ast.ImportFrom)):
            for alias in node.names:
                if alias.name.split(".")[-1] in forbidden:
                    hits.append(f"import {alias.name} at line {node.lineno}")
    assert not hits, f"eval machinery present in predicate_registry: {hits}"
