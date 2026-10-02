"""Loaders and validators for the Semantic OS v2 slice-1 registries.

Checks V-1..V-12 from docs/implementation_plan/semantic-os-v2-slice1-handoff.md.
Problems are strings. An empty list means the check passed. Mutation tests pass
altered documents in; this module does not write the registries.
"""

from __future__ import annotations

import ast
import json
import subprocess
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

import yaml

from config_layer.htf_state import HTFState, ObjectiveStatus
from config_layer.state_identity import CRTState
from features.feature_schema import CANONICAL_FEATURES
from semantics.types import LAYER_RANK, ContractStatus, Kind, Layer, TerminalAuthority, TerminalClass

ROOT = Path(__file__).resolve().parents[2]
CONCEPTS_PATH = ROOT / "configs" / "formulas" / "concept_contracts.yaml"
REPRESENTATION_DIR = ROOT / "configs" / "formulas" / "representation_registry"
TERMINAL_PATH = ROOT / "configs" / "formulas" / "terminal_reason_map.yaml"

_REQUIRED = (
    "canonical_name", "layer", "kind", "status", "definition", "identity",
    "parameterization", "inputs", "rule", "units", "absence", "authority",
    "divergences", "version",
)
_IDENTITY_KEYS = ("reference", "timeframe", "clock", "availability_rule")
_ACCEPTED_EVIDENCE = {"REPO", "USER_DECISION"}
_RESET_FILES = (
    ROOT / "src" / "config_layer" / "crt_engine_v2.py",
    ROOT / "src" / "runtime" / "backtest_v2.py",
)

_TRACKED: Optional[set[str]] = None


class UnmatchedTerminalReason(KeyError):
    """A RESET reason matched no terminal_reason_map entry."""


class FStringFragment(str):
    """Leading literal of an f-string reason: the runtime reason only starts with it (V-12)."""


class DuplicateKeyError(ValueError):
    """A registry mapping declares the same key twice (V-1: ids are unique)."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys instead of keeping the last one."""


def _unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen: set = set()
    for key_node, _value in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise DuplicateKeyError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def parse_registry(text: str) -> dict:
    """Parse registry YAML. Duplicate keys raise DuplicateKeyError (V-1)."""
    return yaml.load(text, Loader=_UniqueKeyLoader) or {}


def _load(path: Path) -> dict:
    return parse_registry(path.read_text(encoding="utf-8"))


def load_concept_contracts(path: Optional[Path] = None) -> dict:
    return _load(Path(path) if path else CONCEPTS_PATH)


def load_representation_shards(directory: Optional[Path] = None) -> dict[str, dict]:
    folder = Path(directory) if directory else REPRESENTATION_DIR
    return {path.name: _load(path) for path in sorted(folder.glob("*.yaml"))}


def load_terminal_reason_map(path: Optional[Path] = None) -> dict:
    return _load(Path(path) if path else TERMINAL_PATH)


def tracked_paths() -> set[str]:
    """Git-tracked paths relative to the repo root, forward-slashed."""
    global _TRACKED
    if _TRACKED is None:
        out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
        _TRACKED = {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()}
    return _TRACKED


def match_terminal(reason: str, entries: Optional[Sequence[Mapping[str, Any]]] = None) -> dict:
    """Longest matching entry. Exact wins a tie of equal length. Unmatched raises."""
    table = list(entries) if entries is not None else load_terminal_reason_map()["entries"]
    best = None
    best_rank = (-1, -1)
    for entry in table:
        token = str(entry.get("reason", ""))
        mode = entry.get("match")
        if mode == "exact":
            hit = reason == token
        elif mode == "prefix":
            hit = reason.startswith(token)
        else:
            continue
        if not hit:
            continue
        rank = (len(token), 1 if mode == "exact" else 0)
        if rank > best_rank:
            best = entry
            best_rank = rank
    if best is None:
        raise UnmatchedTerminalReason(reason)
    return dict(best)


def _is_config_ref(value: Any) -> bool:
    return isinstance(value, str) and "." in value and " " not in value


def _resolve_domain(domain: Any, concepts: Mapping[str, dict]) -> Any:
    if isinstance(domain, str) and domain not in ("int", "float") and "." in domain:
        owner, field = domain.split(".", 1)
        spec = ((concepts.get(owner) or {}).get("parameterization") or {}).get(field) or {}
        inner = spec.get("domain")
        if inner is not None:
            return inner
    return domain


_MISSING = object()


def active_config_value(ref: str) -> Any:
    """Value of a dotted `section.key` reference in the ACTIVE_VERSION production config.

    Read from the JSON file itself (no CRTConfig coercion). An unresolved reference returns
    a sentinel the domain check rejects, so a REP cannot bind to a key that does not exist.
    """
    version = (ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    node: Any = json.loads((ROOT / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8"))
    for part in ref.split("."):
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _in_domain(value: Any, domain: Any) -> bool:
    """A concrete value must be a domain member. A dotted config reference is a binding to
    settings: it is accepted only if it resolves in the active config to a domain member."""
    if _is_config_ref(value):
        resolved = active_config_value(value)
        return resolved is not _MISSING and not _is_config_ref(resolved) and _in_domain(resolved, domain)
    if isinstance(domain, list):
        return value in domain
    if domain == "int":
        return type(value) is int
    if domain == "float":
        return type(value) in (int, float)
    if domain == "str":
        return isinstance(value, str) and value != ""
    if domain == "mapping":
        return isinstance(value, dict)
    return False


def _bound_value(value: Any) -> Any:
    """Concrete value a REP parameter binds to. A config reference is resolved first (I-2)."""
    if _is_config_ref(value):
        resolved = active_config_value(value)
        if resolved is _MISSING or _is_config_ref(resolved):
            return _MISSING
        return resolved
    return value


def validate_concepts(doc: Mapping[str, Any], *, tracked: Optional[set[str]] = None) -> list[str]:
    """V-1..V-5."""
    problems: list[str] = []
    concepts = doc.get("concepts")
    if not isinstance(concepts, dict) or not concepts:
        return ["concept_contracts: `concepts` must be a non-empty mapping"]
    files = tracked if tracked is not None else tracked_paths()
    for cid, rec in concepts.items():
        where = f"concept {cid}"
        if not isinstance(rec, dict):
            problems.append(f"{where}: record must be a mapping")
            continue
        for key in _REQUIRED:
            if key not in rec:
                problems.append(f"{where}: missing required field {key!r}")
        ident = rec.get("identity")
        if isinstance(ident, dict):
            for key in _IDENTITY_KEYS:
                if key not in ident:
                    problems.append(f"{where}: identity missing {key!r}")
        elif "identity" in rec:
            problems.append(f"{where}: identity must be a mapping")
        layer_name = rec.get("layer")
        kind_name = rec.get("kind")
        status_name = rec.get("status")
        try:
            layer = Layer(layer_name)
        except ValueError:
            problems.append(f"{where}: unknown layer {layer_name!r}")
            layer = None
        if kind_name not in {k.value for k in Kind}:
            problems.append(f"{where}: unknown kind {kind_name!r}")
        if status_name not in {s.value for s in ContractStatus}:
            problems.append(f"{where}: unknown status {status_name!r}")
        if type(rec.get("version")) is not int:
            problems.append(f"{where}: version must be an int")
        params = rec.get("parameterization")
        if isinstance(params, dict):
            for name, spec in params.items():
                if not isinstance(spec, dict):
                    problems.append(f"{where}: parameter {name} must be a mapping")
                    continue
                if "domain" not in spec:
                    problems.append(f"{where}: parameter {name} has no domain")
                if "identity_bearing" not in spec or type(spec.get("identity_bearing")) is not bool:
                    problems.append(f"{where}: parameter {name} must declare identity_bearing")
        elif "parameterization" in rec:
            problems.append(f"{where}: parameterization must be a mapping")
        if kind_name == Kind.MEASUREMENT.value:
            units = rec.get("units") if isinstance(rec.get("units"), dict) else {}
            if "unit" not in units or "normalization_basis" not in units:
                problems.append(f"{where}: MEASUREMENT requires units.unit and units.normalization_basis")
        inputs = rec.get("inputs")
        if isinstance(inputs, list) and layer is not None:
            for src in inputs:
                if src not in concepts:
                    problems.append(f"{where}: input {src!r} is not a concept")
                    continue
                try:
                    src_layer = Layer(concepts[src].get("layer"))
                except ValueError:
                    problems.append(f"{where}: input {src!r} has no known layer")
                    continue
                if LAYER_RANK[src_layer] > LAYER_RANK[layer]:
                    problems.append(
                        f"{where}: input {src} is layer {src_layer.value}, above {layer.value} (I-12)"
                    )
        elif "inputs" in rec and not isinstance(inputs, list):
            problems.append(f"{where}: inputs must be a list")
        problems.extend(_alias_problems_for(cid, rec, concepts))
        if status_name in (ContractStatus.ACCEPTED.value, ContractStatus.FROZEN.value):
            authority = rec.get("authority") if isinstance(rec.get("authority"), dict) else {}
            evidence = authority.get("evidence")
            if not isinstance(evidence, list) or not evidence or any(e not in _ACCEPTED_EVIDENCE for e in evidence):
                problems.append(
                    f"{where}: ACCEPTED evidence must be a non-empty subset of {sorted(_ACCEPTED_EVIDENCE)}"
                )
            sources = authority.get("sources")
            if not isinstance(sources, list) or not sources:
                problems.append(f"{where}: ACCEPTED authority.sources must be a non-empty list")
            else:
                for src in sources:
                    norm = str(src).replace("\\", "/")
                    if norm not in files:
                        problems.append(f"{where}: source {norm} is not git-tracked")
        if "divergences" in rec and not isinstance(rec.get("divergences"), list):
            problems.append(f"{where}: divergences must be a list")
    problems.extend(_v13_thesis_roles(concepts))
    return problems


def _parameter_spec(concept: Mapping[str, Any], concepts: Mapping[str, dict], name: str) -> Optional[dict]:
    """Parameter declaration on this concept, or on the concept named by identity.reference.

    Episode stages declare no parameters of their own. Their representations carry the
    episode's `founding` (identity.reference is the episode id).
    """
    declared = concept.get("parameterization") or {}
    spec = declared.get(name) if isinstance(declared, dict) else None
    if isinstance(spec, dict):
        return spec
    ref = (concept.get("identity") or {}).get("reference") if isinstance(concept.get("identity"), dict) else None
    if isinstance(ref, str) and ref in concepts:
        parent = (concepts[ref].get("parameterization") or {}).get(name)
        if isinstance(parent, dict):
            return parent
    return None


def _param_problems(where: str, rep: Mapping[str, Any], concept: Mapping[str, Any],
                    concepts: Mapping[str, dict]) -> list[str]:
    problems = []
    given = rep.get("parameterization") or {}
    if not isinstance(given, dict):
        return [f"{where}: parameterization must be a mapping"]
    for name, value in given.items():
        spec = _parameter_spec(concept, concepts, name)
        if not isinstance(spec, dict):
            problems.append(f"{where}: parameter {name!r} is not on the concept contract")
            continue
        domain = _resolve_domain(spec.get("domain"), concepts)
        bound = _bound_value(value)
        if bound is _MISSING:
            problems.append(f"{where}: parameter {name}={value!r} does not resolve")
            continue
        if _in_domain(bound, domain):
            continue
        legacy = spec.get("legacy_values") or []
        if bound in legacy and rep.get("divergence_ref"):
            continue
        resolved = "" if bound == value else f" (resolved {bound!r})"
        problems.append(
            f"{where}: parameter {name}={value!r} is outside domain {domain!r} "
            "and is not a legacy value with divergence_ref"
            f"{resolved}"
        )
    return problems


def _identity_tuple(concept_id: str, rep: Mapping[str, Any], shard: Mapping[str, Any]) -> tuple:
    params = rep.get("parameterization") or {}
    encoding = rep.get("encoding")
    if not isinstance(encoding, str):
        encoding = json.dumps(encoding, sort_keys=True, default=str)
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return (concept_id, canonical, str(shard.get("producer_id")), encoding, str(shard.get("schema_version")))


def validate_representations(concepts: Mapping[str, dict], shards: Mapping[str, dict],
                             canonical: Sequence[str] = CANONICAL_FEATURES) -> list[str]:
    """V-6..V-10."""
    problems: list[str] = []
    seen: dict[tuple, str] = {}
    canonical_list = list(canonical)
    for shard_name, shard in shards.items():
        producer = shard.get("producer_id")
        reps = shard.get("representations") or {}
        if not isinstance(reps, dict):
            problems.append(f"{shard_name}: representations must be a mapping")
            continue
        for key, rep in reps.items():
            where = f"{producer}:{key}"
            if not isinstance(rep, dict):
                problems.append(f"{where}: representation must be a mapping")
                continue
            cid = rep.get("concept_id")
            concept = concepts.get(cid)
            if concept is None:
                problems.append(f"{where}: concept_id {cid!r} does not exist")
                continue
            if concept.get("status") == ContractStatus.PROPOSED.value:
                problems.append(f"{where}: concept {cid} is PROPOSED (I-18)")
                continue
            problems.extend(_param_problems(where, rep, concept, concepts))
            if concept.get("kind") == Kind.OUTCOME.value:
                problems.extend(_v14_outcome(where, rep))
            if "encoding" not in rep:
                problems.append(f"{where}: encoding is required")
            ident = _identity_tuple(cid, rep, shard)
            if ident in seen:
                problems.append(f"{where}: duplicate representation identity with {seen[ident]}")
            else:
                seen[ident] = where
        if producer == "feature_pipeline":
            problems.extend(_v9(shard, canonical_list))
        elif producer == "crt_engine":
            problems.extend(_v10_crt(shard))
        elif producer == "parent_crt":
            problems.extend(_v10_parent(shard))
    return problems


def _v9(shard: Mapping[str, Any], canonical: Sequence[str]) -> list[str]:
    problems = []
    reps = shard.get("representations") or {}
    raw = list(shard.get("raw_observations") or [])
    unmapped = list(shard.get("unmapped") or [])
    names = list(reps) + raw + unmapped
    if len(names) != len(set(names)):
        dup = sorted({n for n in names if names.count(n) > 1})
        problems.append(f"feature_pipeline: name covered more than once: {dup}")
    if set(names) != set(canonical):
        missing = sorted(set(canonical) - set(names))
        extra = sorted(set(names) - set(canonical))
        if missing:
            problems.append(f"feature_pipeline: canonical slots not covered: {missing}")
        if extra:
            problems.append(f"feature_pipeline: names that are not canonical slots: {extra}")
    index = {name: i for i, name in enumerate(canonical)}
    for name, rep in reps.items():
        if name not in index or not isinstance(rep, dict):
            continue
        if rep.get("slot") != index[name]:
            problems.append(
                f"feature_pipeline:{name}: slot {rep.get('slot')!r} != canonical index {index[name]}"
            )
    return problems


def _covered(shard: Mapping[str, Any]) -> set[str]:
    names = set(shard.get("representations") or {})
    names |= set(shard.get("unmapped") or {})
    return names


def _v10_crt(shard: Mapping[str, Any]) -> list[str]:
    """CRTState members, plus every field of Trade. A Trade.tp1_price[intent] key covers tp1_price."""
    from dataclasses import fields

    from config_layer.crt_engine_v2 import Trade

    covered = _covered(shard)
    trade_covered = set(covered)
    for name in covered:
        if isinstance(name, str) and name.startswith("Trade.tp1_price[") and name.endswith("]"):
            trade_covered.add("Trade.tp1_price")
    missing = [f"CRTState.{m.name}" for m in CRTState if f"CRTState.{m.name}" not in covered]
    missing += [f"Trade.{field.name}" for field in fields(Trade) if f"Trade.{field.name}" not in trade_covered]
    if missing:
        return [f"crt_engine: members not covered: {missing}"]
    return []


def _v10_parent(shard: Mapping[str, Any]) -> list[str]:
    covered = _covered(shard)
    missing = [f"HTFState.{m.name}" for m in HTFState if f"HTFState.{m.name}" not in covered]
    missing += [f"ObjectiveStatus.{m.name}" for m in ObjectiveStatus
                if f"ObjectiveStatus.{m.name}" not in covered]
    if missing:
        return [f"parent_crt: members not covered: {missing}"]
    return []


def validate_unmapped_shrink_only(shards: Mapping[str, dict],
                                  pinned: Mapping[str, Iterable[str]]) -> list[str]:
    """V-11. A key that is not in the pinned list is growth and fails. Removals do not."""
    problems = []
    by_producer = {shard.get("producer_id"): shard for shard in shards.values()}
    for producer, allowed in pinned.items():
        shard = by_producer.get(producer)
        if shard is None:
            problems.append(f"unmapped pin: producer {producer!r} has no shard")
            continue
        extra = set(shard.get("unmapped") or {}) - set(allowed)
        if extra:
            problems.append(f"{producer}: unmapped grew by {sorted(extra)}")
    return problems


def _node_literals(node: ast.AST, func: ast.AST, module: ast.AST, depth: int) -> tuple[list[str], bool]:
    if depth > 8:
        return [], False
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return ([node.value] if node.value else []), True
        return [], False
    if isinstance(node, ast.JoinedStr):
        if (node.values and isinstance(node.values[0], ast.Constant)
                and isinstance(node.values[0].value, str)):
            text = node.values[0].value
            return ([FStringFragment(text)] if text else []), True
        return [], False
    if isinstance(node, ast.Name):
        return _assigned_literals(node.id, func, module, depth + 1)
    return [], False


def _assigned_literals(name: str, func: ast.AST, module: ast.AST, depth: int) -> tuple[list[str], bool]:
    found: list[str] = []
    saw = False
    unresolved = False
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            saw = True
            bits, ok = _node_literals(node.value, func, module, depth)
            found.extend(bits)
            unresolved = unresolved or not ok
        elif isinstance(target, ast.Tuple) and isinstance(node.value, ast.Call):
            for index, elt in enumerate(target.elts):
                if isinstance(elt, ast.Name) and elt.id == name:
                    saw = True
                    bits, ok = _call_return_literals(node.value, index, func, module, depth)
                    found.extend(bits)
                    unresolved = unresolved or not ok
    if not saw:
        return [], False
    if unresolved and not found:
        return [], False
    return found, True


def _constructed_class(name: str, tree: ast.AST) -> Optional[str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name):
                return func.id
    return None


def _attr_class(expr: ast.Attribute, module: ast.AST) -> Optional[str]:
    if not (isinstance(expr.value, ast.Name) and expr.value.id == "self"):
        return None
    for node in ast.walk(module):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (isinstance(target, ast.Attribute) and target.attr == expr.attr
                and isinstance(target.value, ast.Name) and target.value.id == "self"
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)):
            return node.value.func.id
    return None


def _class_of(expr: ast.AST, scope: ast.AST, module: ast.AST) -> Optional[str]:
    if isinstance(expr, ast.Name):
        return _constructed_class(expr.id, scope) or _constructed_class(expr.id, module)
    if isinstance(expr, ast.Attribute):
        return _attr_class(expr, module)
    return None


def _method(module: ast.AST, class_name: str, method: str) -> Optional[ast.FunctionDef]:
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method:
                    return item
    return None


def _resolve_call(func: ast.AST, scope: ast.AST, module: ast.AST) -> Optional[ast.FunctionDef]:
    if isinstance(func, ast.Attribute):
        class_name = _class_of(func.value, scope, module)
        if class_name is None:
            return None
        return _method(module, class_name, func.attr)
    if isinstance(func, ast.Name):
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and node.name == func.id:
                return node
    return None


def _call_return_literals(call: ast.Call, index: int, scope: ast.AST, module: ast.AST,
                          depth: int) -> tuple[list[str], bool]:
    func = _resolve_call(call.func, scope, module)
    if func is None:
        return [], False
    return _returns_at(func, index, module, depth)


def _returns_at(func: ast.FunctionDef, index: int, module: ast.AST,
                depth: int = 0) -> tuple[list[str], bool]:
    found: list[str] = []
    ok = True
    saw = False
    for node in ast.walk(func):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        saw = True
        value = node.value
        if isinstance(value, ast.Tuple):
            if len(value.elts) <= index:
                ok = False
                continue
            bits, good = _node_literals(value.elts[index], func, module, depth + 1)
        elif index == 0:
            bits, good = _node_literals(value, func, module, depth + 1)
        else:
            ok = False
            continue
        found.extend(bits)
        ok = ok and good
    return found, ok and saw


def _enclosing_function(module: ast.AST, call: ast.Call) -> ast.AST:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(module):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    current: Optional[ast.AST] = call
    while current is not None and not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
        current = parents.get(id(current))
    return current if current is not None else module


def _reason_node(call: ast.Call) -> Optional[ast.AST]:
    for keyword in call.keywords:
        if keyword.arg == "reason":
            return keyword.value
    if len(call.args) >= 2:
        return call.args[1]
    return None


def _is_reset_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr == "reset_to_range"
    return isinstance(func, ast.Name) and func.id == "reset_to_range"


def reset_reason_literals(path: Path) -> tuple[list[str], list[str]]:
    """(literals, unresolved descriptions) for one engine source file."""
    module = ast.parse(path.read_text(encoding="utf-8"))
    literals: list[str] = []
    unresolved: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and _is_reset_call(node):
            reason = _reason_node(node)
            scope = _enclosing_function(module, node)
            if reason is None:
                unresolved.append(f"{path.name}:{node.lineno}: reset_to_range has no reason argument")
                continue
            bits, ok = _node_literals(reason, scope, module, 0)
            literals.extend(bits)
            if not ok:
                unresolved.append(f"{path.name}:{node.lineno}: unresolved reset_to_range reason")
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and node.name == "ResetLogic":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "should_reset":
                    bits, ok = _returns_at(item, 1, module)
                    literals.extend(bits)
                    if not ok:
                        unresolved.append(f"{path.name}: ResetLogic.should_reset reason did not resolve")
    return literals, unresolved


def _literal_covered(text: str, entries: Sequence[Mapping[str, Any]]) -> bool:
    """A plain literal is the whole runtime reason, so it must resolve through match_terminal.

    An f-string fragment is only the start of the runtime reason: it is covered by a `prefix`
    entry that it starts with, or (best effort, the tail is a runtime value) by a `prefix`
    entry that starts with it.
    """
    if not isinstance(text, FStringFragment):
        try:
            match_terminal(text, entries)
            return True
        except UnmatchedTerminalReason:
            return False
    for entry in entries:
        token = str(entry.get("reason", ""))
        if token and entry.get("match") == "prefix" and (text.startswith(token) or token.startswith(text)):
            return True
    return False


def validate_terminal_reasons(doc: Mapping[str, Any], *, root: Optional[Path] = None) -> list[str]:
    """Map shape plus V-12 (AST coverage of reset reasons)."""
    problems: list[str] = []
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        return ["terminal_reason_map: entries must be a non-empty list"]
    authorities = {a.value for a in TerminalAuthority}
    classes = {c.value for c in TerminalClass}
    for key, expected in (("authorities", authorities), ("classes", classes)):
        declared = doc.get(key)
        if not isinstance(declared, list) or set(declared) != expected or len(declared) != len(expected):
            problems.append(f"terminal_reason_map: `{key}` must list exactly {sorted(expected)}")
    for index, entry in enumerate(entries):
        where = f"terminal entry[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be a mapping")
            continue
        if entry.get("match") not in ("exact", "prefix"):
            problems.append(f"{where}: match must be exact or prefix")
        if not isinstance(entry.get("reason"), str) or not entry.get("reason"):
            problems.append(f"{where}: reason must be a non-empty string")
        if entry.get("authority") not in authorities:
            problems.append(f"{where}: authority {entry.get('authority')!r} is not a terminal authority")
        if entry.get("class") not in classes:
            problems.append(f"{where}: class {entry.get('class')!r} is not a terminal class")
        if not isinstance(entry.get("code"), str) or not entry.get("code"):
            problems.append(f"{where}: code must be a non-empty string")
    base = Path(root) if root else ROOT
    for rel in ("src/config_layer/crt_engine_v2.py", "src/runtime/backtest_v2.py"):
        path = base / rel
        literals, unresolved = reset_reason_literals(path)
        problems.extend(unresolved)
        for text in literals:
            if text and not _literal_covered(text, entries):
                problems.append(f"{path.name}: reset reason {text!r} matches no terminal entry")
    return problems


def _alias_problems_for(cid: str, rec: Mapping[str, Any], concepts: Mapping[str, dict]) -> list[str]:
    """V-1 extension: an alias equals no canonical_name and no other concept's alias."""
    aliases = rec.get("aliases")
    if aliases is None:
        return []
    if not isinstance(aliases, list):
        return [f"concept {cid}: aliases must be a list"]
    names = {
        other.get("canonical_name"): other_id
        for other_id, other in concepts.items()
        if isinstance(other, dict) and isinstance(other.get("canonical_name"), str)
    }
    problems = []
    seen: set[str] = set()
    for alias in aliases:
        if not isinstance(alias, str) or not alias:
            problems.append(f"concept {cid}: alias {alias!r} must be a non-empty string")
            continue
        owner = names.get(alias)
        if owner is not None:
            problems.append(f"concept {cid}: alias {alias!r} equals canonical_name of {owner}")
        if alias in seen:
            problems.append(f"concept {cid}: alias {alias!r} is repeated")
        seen.add(alias)
        for other_id, other in concepts.items():
            if other_id == cid or not isinstance(other, dict):
                continue
            other_aliases = other.get("aliases") or []
            if isinstance(other_aliases, list) and alias in other_aliases:
                problems.append(f"concept {cid}: alias {alias!r} is also declared by {other_id}")
    return problems


def _v13_thesis_roles(concepts: Mapping[str, dict]) -> list[str]:
    """V-13. A THESIS has an INVALIDATION and a STOP, and every role id exists (I-11)."""
    problems = []
    for cid, rec in concepts.items():
        if not isinstance(rec, dict) or rec.get("kind") != Kind.THESIS.value:
            continue
        roles = rec.get("roles")
        where = f"concept {cid}"
        if not isinstance(roles, dict):
            problems.append(f"{where}: THESIS requires roles.invalidation and roles.stop (I-11)")
            continue
        for role_name, expected in (("invalidation", Kind.INVALIDATION.value), ("stop", Kind.STOP.value)):
            role_id = roles.get(role_name)
            role = concepts.get(role_id) if isinstance(role_id, str) else None
            if not isinstance(role, dict) or role.get("kind") != expected:
                problems.append(f"{where}: roles.{role_name} must be a {expected} concept (I-11)")
        for role_name, role_id in roles.items():
            if role_id not in concepts:
                problems.append(f"{where}: roles.{role_name} {role_id!r} is not a concept (I-11)")
    return problems


def _v14_outcome(where: str, rep: Mapping[str, Any]) -> list[str]:
    """V-14. An OUTCOME representation names walk and basis (I-15). walk_params are not required."""
    params = rep.get("parameterization") or {}
    if not isinstance(params, dict):
        return []
    problems = []
    if "walk" not in params:
        problems.append(f"{where}: OUTCOME representation requires walk (I-15)")
    if "basis" not in params:
        problems.append(f"{where}: OUTCOME representation requires basis (I-15)")
        return problems
    basis = _bound_value(params.get("basis"))
    if basis is _MISSING:
        problems.append(f"{where}: OUTCOME basis does not resolve (I-15)")
        return problems
    cost = _bound_value(params["cost_model"]) if "cost_model" in params else _MISSING
    if basis == "gross" and cost != "none":
        problems.append(f"{where}: basis gross requires cost_model none (I-15)")
    elif basis == "net" and cost in (_MISSING, "none", None):
        problems.append(f"{where}: basis net requires a cost model other than none (I-15)")
    return problems


def validate_role_source(source: str, *, name: str = "<source>") -> list[str]:
    """V-15 on one source string. A dataclass keyword status= is not an assignment."""
    tree = ast.parse(source)
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "with_status":
            problems.append(f"{name}:{node.lineno}: .with_status( call (I-10)")
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if _assigns_status(target):
                    problems.append(f"{name}:{node.lineno}: assignment to .status (I-10)")
    return problems


def _assigns_status(target: ast.AST) -> bool:
    if isinstance(target, ast.Attribute):
        return target.attr == "status"
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_assigns_status(elt) for elt in target.elts)
    if isinstance(target, ast.Starred):
        return _assigns_status(target.value)
    return False


def validate_role_status_untouched(root: Optional[Path] = None) -> list[str]:
    """V-15. Scan src/semantics/trading. A missing package is an error."""
    base = (Path(root) if root else ROOT) / "src" / "semantics" / "trading"
    if not base.is_dir():
        return ["src/semantics/trading: package missing (I-10)"]
    problems = []
    for path in sorted(base.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        problems.extend(validate_role_source(path.read_text(encoding="utf-8"), name=relative))
    return problems


def open_deferred_decisions(concepts: Mapping[str, Any]) -> list[dict]:
    """Divergences that still say decide_in slice_3 (D2-2). Loud until a later slice settles them."""
    found = []
    for cid, rec in concepts.items():
        if not isinstance(rec, dict):
            continue
        for item in rec.get("divergences") or []:
            if isinstance(item, dict) and item.get("decide_in") == "slice_3":
                found.append({
                    "concept_id": cid,
                    "decide_in": item.get("decide_in"),
                    "decision": item.get("decision"),
                    "surface": item.get("surface"),
                })
    return found


def validate_deferred_decisions(concepts: Mapping[str, Any]) -> list[str]:
    """V-16. slice_3 deferrals are an error once an ACCEPTED DECISION_EXECUTION concept exists."""
    pending = open_deferred_decisions(concepts)
    if not pending:
        return []
    accepted = any(
        isinstance(rec, dict)
        and rec.get("layer") == Layer.DECISION_EXECUTION.value
        and rec.get("status") == ContractStatus.ACCEPTED.value
        for rec in concepts.values()
    )
    if not accepted:
        return []
    return [
        f"concept {item['concept_id']}: decide_in slice_3 is unsettled ({item.get('decision')}) "
        "and layer DECISION_EXECUTION has an ACCEPTED concept (D2-2)"
        for item in pending
    ]


def warn_open_deferred_decisions(concepts: Mapping[str, Any]) -> list[dict]:
    """Emit one UserWarning listing every open slice_3 decision. Returns the same rows."""
    pending = open_deferred_decisions(concepts)
    if pending:
        lines = [
            f"{item['concept_id']} decide_in={item['decide_in']}: {item.get('decision')}"
            for item in pending
        ]
        warnings.warn(
            "open deferred decisions (D2-2): " + "; ".join(lines),
            UserWarning,
            stacklevel=2,
        )
    return pending


def validate_all() -> list[str]:
    concepts_doc = load_concept_contracts()
    concepts = concepts_doc.get("concepts") or {}
    shards = load_representation_shards()
    problems = validate_concepts(concepts_doc)
    problems.extend(validate_representations(concepts, shards))
    problems.extend(validate_terminal_reasons(load_terminal_reason_map()))
    problems.extend(validate_role_status_untouched())
    problems.extend(validate_deferred_decisions(concepts))
    warn_open_deferred_decisions(concepts)
    return problems
