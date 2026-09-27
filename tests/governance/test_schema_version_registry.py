"""Mechanical floor for the Schema Evolution & Preservation Workflow.

Parses docs/governance/schema_version_registry.json and, for every registered schema,
checks that a version bump has propagated to every declared downstream slot per its
kind (TRACKS_HEAD / ACCUMULATES / FROZEN / DERIVED). Full procedure:
docs/governance/SCHEMA_EVOLUTION_CONTRACT.md.

Also runs a completeness ratchet: every module-level `*SCHEMA_VERSION*`-shaped symbol
under src/ must be either registered or listed in the registry's `unregistered_pinned`
debt list, and that list may only shrink.

Discovered 2026-09-18: feature_schema.SCHEMA_VERSION bumped 5.0->6.0 (F-107) without
identity/tokens.py's ACCUMULATES vocabulary or identity/certify.py's TRACKS_HEAD
emission following — this floor is the fix, seeded to fail on that exact drift before
it did not exist (see history in the plan / SESSION LOG for the demonstrated RED run).

Read-only. Does not mutate any config, model, or runtime behavior.
"""
from __future__ import annotations

import ast
import importlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REGISTRY_PATH = ROOT / "docs" / "governance" / "schema_version_registry.json"

VALID_KINDS = {"TRACKS_HEAD", "ACCUMULATES", "FROZEN", "DERIVED"}
VALID_LOCATOR_KINDS = {
    "python_symbol", "ast_no_literal_dict_value", "text_contains",
    "text_last_corrected_marker", "frozen_unchanged",
}


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


REGISTRY = _load_registry()


# ─────────────────────────────────────────────────────────────────────────────
# structural shape of the registry itself
# ─────────────────────────────────────────────────────────────────────────────

def test_registry_parses_and_ids_unique():
    ids = [s["schema_id"] for s in REGISTRY["schemas"]]
    assert len(ids) == len(set(ids)), f"duplicate schema_id: {ids}"


def test_registry_paths_exist():
    missing = []
    for s in REGISTRY["schemas"]:
        for loc in _all_locators(s):
            p = loc.get("path") or _module_to_path(loc.get("module"))
            if p and not (ROOT / p).exists():
                missing.append(p)
    for entry in REGISTRY["unregistered_pinned"]:
        if not (ROOT / entry["path"]).exists():
            missing.append(entry["path"])
    assert not missing, f"registry references nonexistent paths: {missing}"


def test_registry_kinds_are_closed_vocabulary():
    for s in REGISTRY["schemas"]:
        for slot in s["slots"]:
            assert slot["kind"] in VALID_KINDS, slot
            assert slot["locator"]["kind"] in VALID_LOCATOR_KINDS, slot
        for d in s.get("derived", []):
            assert d["locator"]["kind"] in VALID_LOCATOR_KINDS, d


def _module_to_path(module: str | None) -> str | None:
    if not module:
        return None
    return "src/" + module.replace(".", "/") + ".py"


def _all_locators(schema: dict):
    yield schema["declaration"]["locator"]
    for d in schema.get("derived", []):
        yield d["locator"]
    for slot in schema["slots"]:
        yield slot["locator"]


# ─────────────────────────────────────────────────────────────────────────────
# locator evaluation — the actual checks, one function per locator kind
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_python_symbol(loc: dict):
    mod = importlib.import_module(loc["module"])
    importlib.reload(mod)  # never trust a cached prior-test import
    return getattr(mod, loc["symbol"])


def _check_ast_no_literal_dict_value(loc: dict) -> tuple[bool, str]:
    """TRACKS_HEAD via structural import-binding proof (no execution required).

    PASS iff: (1) the file imports `requires_import.symbol` from `requires_import.module`,
    and (2) no dict literal in the file assigns a bare string constant to the key
    `dict_key` (that would be a hardcoded literal reintroduced on some future edit).
    """
    path = ROOT / loc["path"]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    req = loc["requires_import"]
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == req["module"]:
            for alias in node.names:
                if alias.name == req["symbol"]:
                    imported_names.add(alias.asname or alias.name)
    if not imported_names:
        return False, f"{loc['path']} does not import {req['symbol']} from {req['module']}"

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and k.value == loc["dict_key"]:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    offenders.append(f"line {node.lineno}: hardcoded literal {v.value!r}")
    if offenders:
        return False, f"{loc['path']} still hardcodes '{loc['dict_key']}': {offenders}"
    return True, ""


def _check_text_contains(loc: dict) -> tuple[bool, str]:
    text = (ROOT / loc["path"]).read_text(encoding="utf-8")
    if re.search(loc["pattern"], text) is None:
        return False, f"{loc['path']} does not contain pattern {loc['pattern']!r}"
    return True, ""


def _check_frozen_unchanged(loc: dict) -> tuple[bool, str]:
    return _check_text_contains(loc)  # same mechanics; kept as a distinct kind for intent


def _check_text_last_corrected_marker(loc: dict, expected_version: str) -> tuple[bool, str]:
    text = (ROOT / loc["path"]).read_text(encoding="utf-8")
    matches = list(re.finditer(loc["marker_regex"], text))
    if not matches:
        return False, (
            f"{loc['path']} has no CORRECTED marker matching {loc['marker_regex']!r} "
            f"— frozen contract not yet corrected for the current version"
        )
    last = matches[-1]
    found = last.group("version")
    if found != expected_version:
        return False, f"{loc['path']} last CORRECTED marker names {found!r}, expected {expected_version!r}"
    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# per-schema checks
# ─────────────────────────────────────────────────────────────────────────────

def _schema_ids():
    return [s["schema_id"] for s in REGISTRY["schemas"]]


@pytest.mark.parametrize("schema_id", _schema_ids())
def test_declaration_yields_current_version(schema_id):
    schema = next(s for s in REGISTRY["schemas"] if s["schema_id"] == schema_id)
    loc = schema["declaration"]["locator"]
    assert loc["kind"] == "python_symbol", "declarations must be live-importable"
    value = _resolve_python_symbol(loc)
    assert value == schema["current_version"], (
        f"{schema_id} declaration {loc['module']}.{loc['symbol']} = {value!r}, "
        f"registry says current_version={schema['current_version']!r}"
    )


@pytest.mark.parametrize("schema_id", _schema_ids())
def test_derived_values_recompute(schema_id):
    schema = next(s for s in REGISTRY["schemas"] if s["schema_id"] == schema_id)
    for d in schema.get("derived", []):
        loc = d["locator"]
        stored = _resolve_python_symbol(loc)
        # Recompute independently rather than trust the module's own derivation call —
        # a stale cached value would otherwise pass trivially.
        mod = importlib.import_module(loc["module"])
        if d["recompute"] == "md5_join":
            import hashlib
            names = getattr(mod, "CANONICAL_FEATURES")
            recomputed = hashlib.md5("".join(names).encode()).hexdigest()
        elif d["recompute"] == "sha256_ordered_names_16":
            import hashlib
            names = getattr(mod, "CANONICAL_FEATURES")
            payload = json.dumps(list(names), sort_keys=False).encode()
            recomputed = hashlib.sha256(payload).hexdigest()[:16]
        else:
            pytest.fail(f"unknown recompute kind {d['recompute']!r}")
        assert stored == recomputed, f"{schema_id} DERIVED {loc['symbol']} stale: {stored!r} != {recomputed!r}"


@pytest.mark.parametrize("schema_id", _schema_ids())
def test_slots_satisfy_their_kind(schema_id):
    schema = next(s for s in REGISTRY["schemas"] if s["schema_id"] == schema_id)
    failures = []
    for slot in schema["slots"]:
        kind = slot["kind"]
        loc = slot["locator"]
        lk = loc["kind"]

        if kind == "ACCUMULATES":
            assert lk == "python_symbol"
            value = _resolve_python_symbol(loc)
            required = set(schema["history"]) | {schema["current_version"]}
            missing = required - set(value)
            if missing:
                failures.append(f"{loc['module']}.{loc['symbol']} missing versions {missing}")

        elif kind == "TRACKS_HEAD":
            if lk == "ast_no_literal_dict_value":
                ok, msg = _check_ast_no_literal_dict_value(loc)
            elif lk == "text_contains":
                ok, msg = _check_text_contains(loc)
            elif lk == "text_last_corrected_marker":
                ok, msg = _check_text_last_corrected_marker(loc, schema["current_version"])
            else:
                pytest.fail(f"unsupported TRACKS_HEAD locator kind {lk!r}")
            if not ok:
                failures.append(msg)

        elif kind == "FROZEN":
            if lk == "frozen_unchanged":
                ok, msg = _check_frozen_unchanged(loc)
            elif lk == "text_contains":
                ok, msg = _check_text_contains(loc)
            else:
                pytest.fail(f"unsupported FROZEN locator kind {lk!r}")
            if not ok:
                failures.append(msg)

        else:
            pytest.fail(f"unhandled slot kind {kind!r}")

    assert not failures, f"{schema_id} slot violations:\n  " + "\n  ".join(failures)


# ─────────────────────────────────────────────────────────────────────────────
# completeness ratchet — every *SCHEMA_VERSION*-shaped module symbol is accounted for
# ─────────────────────────────────────────────────────────────────────────────

def _census_schema_version_symbols() -> set[tuple[str, str]]:
    hits = set()
    for f in sorted(SRC.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError:
            continue
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for name in targets:
                if "SCHEMA_VERSION" in name:
                    hits.add((rel, name))
    return hits


def test_schema_version_symbol_census_is_fully_accounted_for():
    found = _census_schema_version_symbols()

    registered = {
        (s["declaration"]["locator"]["path"] if "path" in s["declaration"]["locator"]
         else _module_to_path(s["declaration"]["locator"]["module"]),
         s["declaration"]["locator"]["symbol"])
        for s in REGISTRY["schemas"]
    }
    excluded = {(e["path"], e["symbol"]) for e in REGISTRY["excluded_infrastructure_symbols"]}
    pinned = {(e["path"], e["symbol"]) for e in REGISTRY["unregistered_pinned"]}

    accounted = registered | excluded | pinned
    unaccounted = found - accounted
    assert not unaccounted, (
        f"new *SCHEMA_VERSION* symbol(s) not registered and not pinned as debt: {unaccounted}\n"
        f"Register in docs/governance/schema_version_registry.json's `schemas` (if you know its "
        f"slots) or `unregistered_pinned` (if not) — see SCHEMA_EVOLUTION_CONTRACT.md."
    )


def test_unregistered_pinned_list_only_shrinks():
    """Ratchet: the debt list recorded at registry-creation time is the ceiling."""
    CEILING_AT_SEED = 23  # measured 2026-09-18 — see registry.seed_reason
    assert len(REGISTRY["unregistered_pinned"]) <= CEILING_AT_SEED, (
        "unregistered_pinned grew — a new SCHEMA_VERSION symbol was added without being "
        "registered as a slot-aware schema; that is new debt, not existing debt shrinking."
    )
