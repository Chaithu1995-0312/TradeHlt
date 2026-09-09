"""
predicate_registry — the governed interpreter for `structural_predicates` definitions.

HOW-COMPUTATION, NOT SEMANTIC AUTHORITY. The meaning of a structural predicate lives in
`configs/formulas/market_ontology.yaml` under `structural_predicates.<name>.definition`.
This module is the one mechanism that *interprets* that data. Adding a new predicate means
adding YAML — never adding a branch here.

NEVER `eval`. There is no `eval`, `exec`, `compile`, or `ast.literal_eval` in this module and
there must never be one. The walker is a closed `if op == ...` dispatch over `OPERATORS`;
anything outside that frozenset raises `PredicateDefinitionError`. That is the same doctrine
the ontology header states ("named scalar callables — NEVER eval'd") applied to a tree instead
of a call.

GENERIC BY CONSTRUCTION. There is deliberately no `if semantic_id == "SP-001"` anywhere. A
node that exists only as YAML must evaluate correctly — `tests/test_predicate_registry.py`
pins this with a synthetic `SP-099` fixture that this module has never heard of.

WHAT THE TREE MAY NOT CONTAIN (v1). Arithmetic (`+ - * /`), function calls, attribute access,
subscripts, string/enum literals, and any name not declared in `definition.inputs`. Config-key
names are a hard error: magnitude thresholds (`body_ratio_min`, `atr_min_displacement`, …) are
HOW-policy applied by the CALLER, not part of a predicate's meaning. Admitting them here would
silently unify `parent_crt` (direction core only) with `visual_crt` (four magnitude gates) —
two call sites that are correctly different.

Lazy by design: nothing on the CRT decision path imports this module.
"""

from __future__ import annotations

from typing import Any, Mapping

from features.registry._loader import load_ontology

__all__ = [
    "OPERATORS",
    "EMIT_OPS",
    "ENUM_TOKENS_V1",
    "PredicateDefinitionError",
    "evaluate_predicate",
    "validate_predicate_definitions",
]


class PredicateDefinitionError(ValueError):
    """A definition is malformed, uses an unknown operator, or names an undeclared input."""


# ── Closed vocabularies. Widening any of these is a schema version bump, never a quiet edit. ──
_COMPARISONS = frozenset({"gt", "lt", "ge", "le", "eq", "ne"})
_BOOLEANS = frozenset({"and", "or", "not"})
OPERATORS: frozenset[str] = _COMPARISONS | _BOOLEANS
EMIT_OPS: frozenset[str] = frozenset({"hit", "select_enum", "select_input"})
ENUM_TOKENS_V1: frozenset[str] = frozenset({"LONG", "SHORT"})

_DEFINITION_SCHEMA = "predicate_definition/v1"
_EMIT_SCHEMA = "predicate_emit/v1"

# Names that must never appear as a predicate input: these are HOW-policy knobs (CRTConfig /
# production JSON), and a predicate that reads one has stopped being a meaning and become a
# policy. Kept as an explicit denylist so the error message can say *why*.
ILLEGAL_INPUT_NAMES: frozenset[str] = frozenset({
    "body_ratio_min", "atr_min_displacement", "atr_multiplier_min", "max_sweep_age_candles",
    "max_displacement_strength", "retest_depth_max", "retest_atr_depth_fraction",
    "retest_min_depth_atr_fraction", "expansion_atr_min_distance", "score_threshold",
})

_SECTION = "structural_predicates"


def _cmp(op: str, left: Any, right: Any) -> bool:
    if op == "gt":
        return left > right
    if op == "lt":
        return left < right
    if op == "ge":
        return left >= right
    if op == "le":
        return left <= right
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    raise PredicateDefinitionError(f"unknown comparison {op!r}")   # pragma: no cover


def _resolve_leaf(name: str, inputs: Mapping[str, Any], clauses: Mapping[str, bool]) -> Any:
    """A bare string is a clause result first, then a declared input. Nothing else."""
    if name in clauses:
        return clauses[name]
    if name in inputs:
        return inputs[name]
    raise PredicateDefinitionError(
        f"name {name!r} is neither an evaluated clause nor a declared input "
        f"(clauses={sorted(clauses)}, inputs={sorted(inputs)})"
    )


def _walk(node: Any, inputs: Mapping[str, Any], clauses: Mapping[str, bool]) -> Any:
    """Generic recursive evaluation. No per-predicate knowledge lives here."""
    if isinstance(node, str):
        return _resolve_leaf(node, inputs, clauses)
    if not isinstance(node, dict):
        raise PredicateDefinitionError(
            f"definition node must be a mapping or a name, got {type(node).__name__}"
        )

    op = node.get("op")
    if op not in OPERATORS:
        raise PredicateDefinitionError(
            f"operator {op!r} is not in the closed v1 set {sorted(OPERATORS)} — "
            "widening the vocabulary is a schema version bump, not an edit"
        )

    if op in _COMPARISONS:
        for side in ("left", "right"):
            if side not in node:
                raise PredicateDefinitionError(f"comparison {op!r} missing {side!r}")
        left = _resolve_leaf(node["left"], inputs, clauses) if isinstance(node["left"], str) else None
        right = _resolve_leaf(node["right"], inputs, clauses) if isinstance(node["right"], str) else None
        if left is None or right is None:
            raise PredicateDefinitionError(
                f"comparison {op!r} operands must be NAMED INPUTS (v1 forbids literals and "
                "nested arithmetic)"
            )
        return _cmp(op, left, right)

    if op == "not":
        if "arg" not in node:
            raise PredicateDefinitionError("'not' requires 'arg'")
        return not _walk(node["arg"], inputs, clauses)

    args = node.get("args")
    if not isinstance(args, list) or not args:
        raise PredicateDefinitionError(f"{op!r} requires a non-empty 'args' list")
    results = [bool(_walk(a, inputs, clauses)) for a in args]
    return all(results) if op == "and" else any(results)


def _get_node(semantic_id: str, ontology: dict | None) -> tuple[str, dict]:
    ont = ontology if ontology is not None else load_ontology()
    for name, spec in (ont.get(_SECTION) or {}).items():
        if spec.get("id") == semantic_id:
            return name, spec
    raise PredicateDefinitionError(
        f"{semantic_id!r} is not a declared {_SECTION} node — do not invent semantic ids"
    )


def evaluate_predicate(
    semantic_id: str,
    inputs: Mapping[str, Any],
    *,
    ontology: dict | None = None,
) -> dict:
    """Evaluate a declared predicate's `definition` against `inputs`.

    Returns `{"hit": bool, "clauses": {...}, **emitted}`. Fail-closed on every malformed or
    out-of-vocabulary construct; never returns a default on error.
    """
    name, spec = _get_node(semantic_id, ontology)
    definition = spec.get("definition")
    if not definition:
        raise PredicateDefinitionError(
            f"{semantic_id} ({name}) has no `definition` block — it may be intentionally "
            "deferred (see spec_schema.semantic_registry.definition_deferred), in which case it "
            "cannot be evaluated"
        )
    if definition.get("schema") != _DEFINITION_SCHEMA:
        raise PredicateDefinitionError(
            f"{semantic_id}: unsupported definition schema {definition.get('schema')!r}"
        )

    declared = list(definition.get("inputs") or ())
    missing = [i for i in declared if i not in inputs]
    if missing:
        raise PredicateDefinitionError(f"{semantic_id}: missing declared input(s) {missing}")
    scoped = {k: inputs[k] for k in declared}          # undeclared extras are NOT visible

    clauses: dict[str, bool] = {}
    for clause_name, tree in (definition.get("clauses") or {}).items():
        clauses[clause_name] = bool(_walk(tree, scoped, clauses))

    emit = definition.get("emit") or {}
    if emit.get("schema") != _EMIT_SCHEMA:
        raise PredicateDefinitionError(f"{semantic_id}: unsupported emit schema {emit.get('schema')!r}")
    for key in emit:
        if key != "schema" and key not in EMIT_OPS:
            raise PredicateDefinitionError(
                f"{semantic_id}: unknown emit op {key!r} (closed set {sorted(EMIT_OPS)})"
            )

    out: dict[str, Any] = {}
    hit = bool(_walk(emit["hit"], scoped, clauses)) if "hit" in emit else False
    out["hit"] = hit
    out["clauses"] = dict(clauses)

    winner = next((c for c, v in clauses.items() if v), None) if hit else None

    for field, mapping in (emit.get("select_enum") or {}).items():
        token = mapping.get(winner) if winner else None
        if token is not None and token not in ENUM_TOKENS_V1:
            raise PredicateDefinitionError(
                f"{semantic_id}: enum token {token!r} not in v1 set {sorted(ENUM_TOKENS_V1)}"
            )
        out[field] = token

    for field, mapping in (emit.get("select_input") or {}).items():
        src = mapping.get(winner) if winner else None
        if src is not None and src not in declared:
            raise PredicateDefinitionError(
                f"{semantic_id}: select_input {field!r} names {src!r}, not a declared input"
            )
        out[field] = scoped[src] if src is not None else None

    return out


def validate_predicate_definitions(ontology: dict | None = None) -> list[str]:
    """Static validation of every `definition` block. Returns problems; [] == contract satisfied."""
    ont = ontology if ontology is not None else load_ontology()
    sr = (ont.get("spec_schema") or {}).get("semantic_registry") or {}
    deferred = dict(sr.get("definition_deferred") or {})
    problems: list[str] = []

    for name, spec in (ont.get(_SECTION) or {}).items():
        sid = spec.get("id", name)
        definition = spec.get("definition")
        if not definition:
            if sid not in deferred:
                problems.append(
                    f"{sid} ({name}): no `definition` and not listed in "
                    "spec_schema.semantic_registry.definition_deferred"
                )
            continue
        if sid in deferred:
            problems.append(f"{sid}: has a `definition` but is still listed as deferred — remove it")

        if definition.get("schema") != _DEFINITION_SCHEMA:
            problems.append(f"{sid}: definition.schema must be {_DEFINITION_SCHEMA}")
        declared = list(definition.get("inputs") or ())
        if not declared:
            problems.append(f"{sid}: definition.inputs is empty")
        for bad in sorted(set(declared) & ILLEGAL_INPUT_NAMES):
            problems.append(
                f"{sid}: input {bad!r} is a HOW-policy threshold — magnitude gates are applied by "
                "the caller and must never be part of a predicate's meaning"
            )

        clauses = definition.get("clauses") or {}
        if not clauses:
            problems.append(f"{sid}: definition.clauses is empty")

        seen: dict[str, bool] = {}
        for cname, tree in clauses.items():
            try:
                _walk(tree, {k: 0.0 for k in declared}, seen)
                seen[cname] = True
            except PredicateDefinitionError as exc:
                problems.append(f"{sid}.clauses.{cname}: {exc}")

        emit = definition.get("emit") or {}
        if emit.get("schema") != _EMIT_SCHEMA:
            problems.append(f"{sid}: emit.schema must be {_EMIT_SCHEMA}")
        for key in emit:
            if key != "schema" and key not in EMIT_OPS:
                problems.append(f"{sid}: unknown emit op {key!r}")
        for field, mapping in (emit.get("select_enum") or {}).items():
            for clause, token in (mapping or {}).items():
                if clause not in clauses:
                    problems.append(f"{sid}: select_enum.{field} names unknown clause {clause!r}")
                if token not in ENUM_TOKENS_V1:
                    problems.append(f"{sid}: select_enum.{field} token {token!r} not in v1 set")
        for field, mapping in (emit.get("select_input") or {}).items():
            for clause, src in (mapping or {}).items():
                if clause not in clauses:
                    problems.append(f"{sid}: select_input.{field} names unknown clause {clause!r}")
                if src not in declared:
                    problems.append(f"{sid}: select_input.{field} source {src!r} is not an input")

    for sid in deferred:
        if not any(spec.get("id") == sid for spec in (ont.get(_SECTION) or {}).values()):
            problems.append(f"definition_deferred names {sid!r}, which is not a declared node")

    return problems
