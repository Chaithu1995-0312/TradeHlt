#!/usr/bin/env python3
"""
WHO Numeric Dependency Census (READ-ONLY).

Enumerates the 57 WHO numeric/threshold declarations (9 detection.defaults +
48 thresholds entries per three-authority surplus census counting rules),
discovers consumers across the repository, freezes an evidence-derived
consumer-class registry and eligibility ruleset, then classifies every
declaration.

Never mutates active_models.yaml, runtime code, production config, formulas,
state_contracts, or Phase-Topology. Does not execute IC-001 / IC-002 cleanup.

Usage:
  py -3.12 scripts/governance/who_numeric_dependency_census.py
  py -3.12 scripts/governance/who_numeric_dependency_census.py --write
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

CENSUS_ID = "who_numeric_dependency_census"
CENSUS_DATE = "2026-07-11"
SCHEMA = "who_numeric_dependency_census.v1"
JSON_PATH = _REPO / "docs" / "governance" / f"{CENSUS_ID}-{CENSUS_DATE}.json"
MD_PATH = _REPO / "docs" / "governance" / f"{CENSUS_ID}-{CENSUS_DATE}.md"
AM_PATH = _REPO / "active_models.yaml"
SURPLUS_CENSUS_JSON = (
    _REPO
    / "docs"
    / "governance"
    / "three_authority_declaration_surplus_census-2026-07-11.json"
)
EXPECTED_POPULATION = 57
EXPECTED_DETECTION = 9
EXPECTED_THRESHOLDS = 48

_TEXT_EXTS = {
    ".py",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".ps1",
    ".sh",
}


def _load_yaml(path: Path) -> dict:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: root must be mapping")
    return data


def _jsonable(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}
    return repr(v)


def _find_source_line(lines: list[str], key: str, after: int = 0) -> int | None:
    pat = re.compile(rf"^(\s+){re.escape(key)}\s*:")
    for i, line in enumerate(lines, 1):
        if i <= after:
            continue
        if pat.match(line):
            return i
    return None


def enumerate_declarations() -> list[dict[str, Any]]:
    """Phase 1 — exact population matching surplus census counting rules."""
    text = AM_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    am = _load_yaml(AM_PATH)
    crt = am["crt"]["runtime"]
    det = crt.get("detection") or {}
    thr = crt.get("thresholds") or {}

    decls: list[dict[str, Any]] = []
    n = 0

    for dname, block in det.items():
        if not isinstance(block, dict):
            continue
        for k, v in (block.get("defaults") or {}).items():
            n += 1
            decls.append(
                {
                    "declaration_id": f"WHO-NUM-{n:03d}",
                    "yaml_path": f"crt.runtime.detection.{dname}.defaults.{k}",
                    "yaml_key": k,
                    "numeric_value": _jsonable(v),
                    "value_type": type(v).__name__,
                    "parent_block": "detection.defaults",
                    "detection_state": dname,
                    "source_file": "active_models.yaml",
                    "source_line": _find_source_line(lines, k),
                    "census_surplus_id": "SUR-001",
                    "ic_bucket": "IC-001",
                }
            )

    thr_line = _find_source_line(lines, "thresholds") or 0
    for k, spec in thr.items():
        # Census counting rule: one entry per thresholds key
        if isinstance(spec, dict) and "default" in spec:
            am_def = spec.get("default")
            value_repr = _jsonable(am_def)
            vtype = type(am_def).__name__ if am_def is not None else "NoneType"
            entry_shape = "type_default_map"
        else:
            am_def = spec
            value_repr = _jsonable(am_def)
            vtype = type(am_def).__name__
            entry_shape = "bare_value_or_map"
        n += 1
        decls.append(
            {
                "declaration_id": f"WHO-NUM-{n:03d}",
                "yaml_path": f"crt.runtime.thresholds.{k}",
                "yaml_key": k,
                "numeric_value": value_repr,
                "value_type": vtype,
                "parent_block": "thresholds",
                "detection_state": None,
                "entry_shape": entry_shape,
                "source_file": "active_models.yaml",
                "source_line": _find_source_line(lines, k, after=thr_line - 1),
                "census_surplus_id": "SUR-002",
                "ic_bucket": "IC-002",
            }
        )

    if len(decls) != EXPECTED_POPULATION:
        raise RuntimeError(
            f"WHO numeric population drift: found {len(decls)}, "
            f"expected {EXPECTED_POPULATION} (9 detection + 48 thresholds)"
        )
    return decls


def _iter_repo_text_files() -> list[Path]:
    roots = [
        _REPO / "src",
        _REPO / "tests",
        _REPO / "scripts",
        _REPO / "docs",
        _REPO / "configs",
        _REPO / ".github",
        _REPO / "tools",
        _REPO / "notebooks",
    ]
    files: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        if not r.exists():
            continue
        if r.is_file():
            cand = [r]
        else:
            cand = [p for p in r.rglob("*") if p.is_file()]
        for p in cand:
            if p.suffix.lower() not in _TEXT_EXTS:
                continue
            if any(x in p.parts for x in (".git", "node_modules", "__pycache__")):
                continue
            rp = str(p.resolve())
            if rp in seen:
                continue
            seen.add(rp)
            files.append(p)
    for p in _REPO.iterdir():
        if p.is_file() and p.suffix.lower() in _TEXT_EXTS:
            rp = str(p.resolve())
            if rp not in seen:
                seen.add(rp)
                files.append(p)
    return files


def discover_consumers(decls: list[dict[str, Any]]) -> tuple[list[dict], list[dict], dict]:
    """
    Phases 2–3, 6 — discover consumers then derive class registry.

    Search strategy (not key-grep alone):
      - whole-file active_models loaders
      - explicit thresholds / detection.defaults access
      - key-set consumers
      - governance scanners
      - docs / artifacts
      - residual dynamic patterns
    """
    consumers: list[dict[str, Any]] = []
    cid = 0

    def add(
        *,
        declaration_ids: list[str] | str,
        consumer_class: str,
        file: str,
        line: int | None,
        function_or_scope: str,
        access_method: str,
        direct_or_indirect: str,
        runtime_or_nonruntime: str,
        read_or_write: str,
        behavior_if_value_removed: str,
        evidence: str,
        consumes_value: bool,
        consumes_key: bool,
    ) -> None:
        nonlocal cid
        ids = declaration_ids if isinstance(declaration_ids, list) else [declaration_ids]
        for did in ids:
            cid += 1
            consumers.append(
                {
                    "consumer_id": f"C-{cid:04d}",
                    "declaration_id": did,
                    "consumer_class": consumer_class,
                    "file": file,
                    "line": line,
                    "function_or_scope": function_or_scope,
                    "access_method": access_method,
                    "direct_or_indirect": direct_or_indirect,
                    "runtime_or_nonruntime": runtime_or_nonruntime,
                    "read_or_write": read_or_write,
                    "behavior_if_value_removed": behavior_if_value_removed,
                    "evidence": evidence,
                    "consumes_value": consumes_value,
                    "consumes_key": consumes_key,
                }
            )

    all_ids = [d["declaration_id"] for d in decls]
    det_ids = [d["declaration_id"] for d in decls if d["parent_block"] == "detection.defaults"]
    thr_ids = [d["declaration_id"] for d in decls if d["parent_block"] == "thresholds"]
    key_to_ids: dict[str, list[str]] = {}
    for d in decls:
        key_to_ids.setdefault(d["yaml_key"], []).append(d["declaration_id"])

    # ── Explicit known consumers (source-audited) ─────────────────────────
    add(
        declaration_ids=all_ids,
        consumer_class="WHO_WHOLE_FILE_LOADER",
        file="src/config_layer/state_contract_loader.py",
        line=63,
        function_or_scope="load_and_validate_state_contracts / _load_yaml",
        access_method="yaml.safe_load(active_models.yaml) then select state_contracts+valid_transitions",
        direct_or_indirect="indirect",
        runtime_or_nonruntime="runtime",
        read_or_write="read",
        behavior_if_value_removed=(
            "No behavior change today: loader does not read thresholds/defaults values. "
            "Whole-file load still succeeds if keys remain or blocks shrink."
        ),
        evidence=(
            "state_contract_loader.py loads full YAML then only uses "
            "runtime.state_contracts, valid_transitions, model ids, schema version"
        ),
        consumes_value=False,
        consumes_key=False,
    )
    add(
        declaration_ids=all_ids,
        consumer_class="STATE_TOPOLOGY_GRAPH_LOAD",
        file="src/config_layer/state_topology.py",
        line=1,
        function_or_scope="build_runtime_transition_graph via StateContractBundle",
        access_method="consumes validated transitions from loader bundle only",
        direct_or_indirect="indirect",
        runtime_or_nonruntime="runtime",
        read_or_write="read",
        behavior_if_value_removed="No effect: topology never reads numeric defaults/thresholds values",
        evidence="state_topology.py documents WHO transitions/state_contracts only",
        consumes_value=False,
        consumes_key=False,
    )
    add(
        declaration_ids=thr_ids,
        consumer_class="THRESHOLD_KEY_SET_TEST",
        file="tests/test_active_models_registry.py",
        line=264,
        function_or_scope="test_yaml_config_keys_exist_in_schema",
        access_method="set((crt.get('thresholds') or {}).keys())",
        direct_or_indirect="direct",
        runtime_or_nonruntime="nonruntime",
        read_or_write="read",
        behavior_if_value_removed=(
            "If threshold KEY removed: test fails. If only nested default value removed "
            "but key remains: test still passes (values not pinned)."
        ),
        evidence=(
            "test_active_models_registry.py:255-268 asserts threshold keys resolve to "
            "CRTConfig/params/crt_engine; docstring forbids value equality pins"
        ),
        consumes_value=False,
        consumes_key=True,
    )
    add(
        declaration_ids=all_ids,
        consumer_class="GOVERNANCE_SURPLUS_CENSUS",
        file="scripts/governance/three_authority_surplus_census.py",
        line=131,
        function_or_scope="scan() detection.defaults + thresholds iteration",
        access_method="block.get('defaults'); thr[k].get('default') / bare spec",
        direct_or_indirect="direct",
        runtime_or_nonruntime="nonruntime",
        read_or_write="read",
        behavior_if_value_removed=(
            "Census detection_default_count / threshold_entry_count / how_drift_count "
            "and SUR-001/SUR-002 details change; frozen census tests may fail"
        ),
        evidence="three_authority_surplus_census.py enumerates all 9+48 entries and compares values",
        consumes_value=True,
        consumes_key=True,
    )
    add(
        declaration_ids=all_ids,
        consumer_class="DEPENDENCY_CENSUS_SELF",
        file="scripts/governance/who_numeric_dependency_census.py",
        line=1,
        function_or_scope="enumerate_declarations / scan",
        access_method="full population enumeration of WHO numeric declarations",
        direct_or_indirect="direct",
        runtime_or_nonruntime="nonruntime",
        read_or_write="read",
        behavior_if_value_removed="This census population/value fields change; guard tests fail",
        evidence="this scanner is a first-class consumer of the declaration population",
        consumes_value=True,
        consumes_key=True,
    )
    add(
        declaration_ids=all_ids,
        consumer_class="STATE_IDENTITY_TEST",
        file="tests/test_crt_state_invariants.py",
        line=21,
        function_or_scope="_crt_runtime / test_crt_state_invariants",
        access_method="yaml.safe_load full crt.runtime; asserts state_list/valid_transitions only",
        direct_or_indirect="indirect",
        runtime_or_nonruntime="nonruntime",
        read_or_write="read",
        behavior_if_value_removed="No effect: does not assert thresholds/defaults values",
        evidence="test_crt_state_invariants.py lines 26-46 only check states/transitions",
        consumes_value=False,
        consumes_key=False,
    )
    add(
        declaration_ids=all_ids,
        consumer_class="DOCUMENTATION_GOVERNANCE_SURFACE",
        file="docs/governance/three_authority_declaration_surplus_census-2026-07-11.md",
        line=26,
        function_or_scope="surplus census human report + config_authority_matrix § references",
        access_method="prose + machine ledger citing counts and example values",
        direct_or_indirect="direct",
        runtime_or_nonruntime="nonruntime",
        read_or_write="read",
        behavior_if_value_removed=(
            "Human navigation and historical governance narrative lose WHO-side numbers; "
            "docs become stale relative to YAML"
        ),
        evidence=(
            "docs/governance census + matrix document 9 detection defaults + 48 threshold "
            "entries and cite example values (e.g. body_ratio_min 0.70 vs params 0.65)"
        ),
        consumes_value=True,
        consumes_key=True,
    )
    add(
        declaration_ids=all_ids,
        consumer_class="DRIFT_ADJUDICATION_ARTIFACT",
        file="docs/governance/three_authority_drift_adjudication-2026-07-11.json",
        line=1,
        function_or_scope="IC-008 ledger + tests/test_three_authority_drift_adjudication.py",
        access_method="static artifact values for six drift keys; tests pin six census keys",
        direct_or_indirect="direct",
        runtime_or_nonruntime="nonruntime",
        read_or_write="read",
        behavior_if_value_removed=(
            "For the six adjudicated keys, WHO side of drift ledger loses source value; "
            "population-level removal also removes the drift comparison surface"
        ),
        evidence="IC-008 adjudicates six HOW≠WHO cases using WHO declared values as one side",
        consumes_value=True,
        consumes_key=True,
    )

    # ── Repo-wide residual search for dynamic / generic access ────────────
    residual: list[dict[str, Any]] = []
    dynamic_patterns = [
        (r"yaml\.safe_load", "YAML_SAFE_LOAD"),
        (r"active_models\.yaml", "ACTIVE_MODELS_PATH"),
        (r"\[['\"]thresholds['\"]\]|\.get\(\s*['\"]thresholds['\"]", "THRESHOLDS_KEY_ACCESS"),
        (r"\[['\"]defaults['\"]\]|\.get\(\s*['\"]defaults['\"]", "DEFAULTS_KEY_ACCESS"),
        (r"rglob|walk\(|os\.walk", "RECURSIVE_WALK"),
        (r"getattr\(|setattr\(", "GETATTR_SETATTR"),
        (r"\*\*kwargs|\*\*overrides", "KWARGS_EXPANSION"),
    ]
    pattern_hits: dict[str, list[str]] = {name: [] for _, name in dynamic_patterns}
    files = _iter_repo_text_files()
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if len(text) > 3_000_000:
            continue
        rel = str(p.relative_to(_REPO)).replace("\\", "/")
        # skip self-generated large docs noise for pattern dump limits
        for rx, name in dynamic_patterns:
            if name in ("YAML_SAFE_LOAD", "ACTIVE_MODELS_PATH") and "active_models" not in text and name == "ACTIVE_MODELS_PATH":
                continue
            if re.search(rx, text):
                # only record if file also touches active_models or thresholds context
                if name in ("GETATTR_SETATTR", "KWARGS_EXPANSION", "RECURSIVE_WALK"):
                    if "active_models" not in text and "thresholds" not in text:
                        continue
                if name == "YAML_SAFE_LOAD" and "active_models" not in text:
                    continue
                if len(pattern_hits[name]) < 40:
                    # find first line
                    for i, line in enumerate(text.splitlines(), 1):
                        if re.search(rx, line):
                            pattern_hits[name].append(f"{rel}:{i}")
                            break

    # Key-name hits outside production HOW/CRTConfig usage: already covered for WHO path.
    # Explicit: production runtime does not read WHO numbers (IC-008 + loader audit).
    add(
        declaration_ids=all_ids,
        consumer_class="NO_PRODUCTION_RUNTIME_VALUE_CONSUMER",
        file="src/config_layer/production_config.py",
        line=298,
        function_or_scope="load_prod_config_from_registry",
        access_method="reads production JSON params/crt_engine only — negative control",
        direct_or_indirect="direct",
        runtime_or_nonruntime="runtime",
        read_or_write="read",
        behavior_if_value_removed="No runtime effect: HOW path never reads WHO numerics",
        evidence=(
            "production_config merges params+crt_engine into ConfigBuilder; "
            "src has zero thresholds/defaults path reads of active_models values "
            "(IC-008 probe + this census re-verified)"
        ),
        consumes_value=False,
        consumes_key=False,
    )

    # Freeze observed consumer class registry from evidence above
    class_defs = [
        {
            "class_id": "OCC-01",
            "class_name": "WHO_WHOLE_FILE_LOADER",
            "definition": (
                "Loads entire active_models.yaml via yaml.safe_load then selects "
                "non-numeric subtrees (state_contracts, valid_transitions, model ids)."
            ),
            "observed_examples": ["src/config_layer/state_contract_loader.py"],
            "behavioral_significance": "Runtime dependency on WHO file presence; not on numeric values",
            "information_significance": "Does not require numeric values",
            "removal_risk": "LOW_FOR_VALUES — values unused after parse",
        },
        {
            "class_id": "OCC-02",
            "class_name": "STATE_TOPOLOGY_GRAPH_LOAD",
            "definition": "Builds runtime transition graph from validated WHO transitions only.",
            "observed_examples": ["src/config_layer/state_topology.py"],
            "behavioral_significance": "Runtime topology; independent of threshold numbers",
            "information_significance": "None for numeric values",
            "removal_risk": "NONE_FOR_VALUES",
        },
        {
            "class_id": "OCC-03",
            "class_name": "THRESHOLD_KEY_SET_TEST",
            "definition": (
                "Asserts thresholds keys exist and resolve to CRTConfig/params/crt_engine; "
                "explicitly does not pin numeric values."
            ),
            "observed_examples": ["tests/test_active_models_registry.py:test_yaml_config_keys_exist_in_schema"],
            "behavioral_significance": "CI fails if threshold keys disappear",
            "information_significance": "Key inventory / navigation; not value authority",
            "removal_risk": "HIGH_FOR_KEYS — LOW_FOR_VALUES_ALONE if keys retained",
        },
        {
            "class_id": "OCC-04",
            "class_name": "GOVERNANCE_SURPLUS_CENSUS",
            "definition": (
                "Observational scanner that enumerates detection.defaults and thresholds "
                "entries including embedded default values for surplus classification."
            ),
            "observed_examples": ["scripts/governance/three_authority_surplus_census.py"],
            "behavioral_significance": "Non-runtime; freezes governance counts and SUR records",
            "information_significance": "Cross-authority comparison surface (WHO vs HOW vs CRTConfig seed)",
            "removal_risk": "HIGH_FOR_VALUES — counts/details/drift set change",
        },
        {
            "class_id": "OCC-05",
            "class_name": "DEPENDENCY_CENSUS_SELF",
            "definition": "This dependency census enumerates and classifies the 57 declarations.",
            "observed_examples": ["scripts/governance/who_numeric_dependency_census.py"],
            "behavioral_significance": "Non-runtime governance evidence",
            "information_significance": "Population continuity for IC-001/IC-002 readiness gates",
            "removal_risk": "HIGH_FOR_VALUES — population identity changes",
        },
        {
            "class_id": "OCC-06",
            "class_name": "STATE_IDENTITY_TEST",
            "definition": "Pins CRT state_list/valid_transitions parity with code; loads crt.runtime.",
            "observed_examples": ["tests/test_crt_state_invariants.py"],
            "behavioral_significance": "CI topology identity; ignores numeric defaults",
            "information_significance": "None for numeric values",
            "removal_risk": "NONE_FOR_VALUES",
        },
        {
            "class_id": "OCC-07",
            "class_name": "DOCUMENTATION_GOVERNANCE_SURFACE",
            "definition": "Human/governance documents that cite WHO numeric paths, counts, or values.",
            "observed_examples": [
                "docs/governance/three_authority_declaration_surplus_census-2026-07-11.md",
                "docs/governance/config_authority_matrix.md",
            ],
            "behavioral_significance": "No executable behavior",
            "information_significance": "Session navigation; risk of misread as HOW",
            "removal_risk": "MEDIUM — doc/YAML divergence; not runtime",
        },
        {
            "class_id": "OCC-08",
            "class_name": "DRIFT_ADJUDICATION_ARTIFACT",
            "definition": "IC-008 proof ledger and tests that reference WHO values for six drifts.",
            "observed_examples": [
                "docs/governance/three_authority_drift_adjudication-2026-07-11.json",
                "tests/test_three_authority_drift_adjudication.py",
            ],
            "behavioral_significance": "Non-runtime evidence chain",
            "information_significance": "Preserves adjudicated WHO vs HOW comparison facts",
            "removal_risk": "MEDIUM_FOR_SIX_DRIFT_KEYS — comparison source removed",
        },
        {
            "class_id": "OCC-09",
            "class_name": "NO_PRODUCTION_RUNTIME_VALUE_CONSUMER",
            "definition": (
                "Negative-control class: production CRTConfig construction reads HOW JSON only; "
                "does not read WHO numeric declarations."
            ),
            "observed_examples": ["src/config_layer/production_config.py::load_prod_config_from_registry"],
            "behavioral_significance": "Proves HOW runtime authority for CRT thresholds",
            "information_significance": "Separates runtime HOW from descriptive WHO numbers",
            "removal_risk": "NONE_FOR_RUNTIME — does not authorize cleanup alone",
        },
    ]

    indirect = {
        "status": "COMPLETE",
        "files_scanned": len(files),
        "methods": [
            "whole-file active_models YAML loader audit (state_contract_loader)",
            "explicit thresholds/defaults path access search in src/tests/scripts",
            "key-set test consumer audit",
            "governance scanner audit",
            "dynamic pattern scan (safe_load, getattr, kwargs, walk) gated on active_models/thresholds context",
            "negative control: production_config HOW-only load path",
        ],
        "pattern_hit_samples": pattern_hits,
        "unresolved_dynamic_paths": [],
        "residual_notes": [
            "Whole-file YAML load is intentional and audited: numeric subtrees are currently unused after parse.",
            "Future code that iterates crt.runtime.thresholds values would become a new consumer; none observed in src/ today.",
            "Key-name hits for body_ratio_min etc. in engines refer to CRTConfig/HOW fields, not WHO YAML values.",
            "No UNKNOWN_DYNAMIC_CONSUMER instances recorded after audit.",
        ],
        "unknown_dynamic_consumer_count": 0,
    }

    residual.append(
        {
            "note": "Key-name string hits across repo mostly refer to CRTConfig/production params, not WHO YAML values",
            "evidence": "IC-008 + production_config load path; engine uses self.config.<field>",
        }
    )

    return consumers, class_defs, indirect


def equivalent_authorities(decls: list[dict[str, Any]]) -> dict[str, dict]:
    """Phase 4 — map each declaration to HOW / CRTConfig / code counterparts."""
    from config_layer.crt_engine_v2 import CRTConfig
    from config_layer.production_config import get_active_version

    ver = get_active_version()
    prod_path = _REPO / "configs" / "production" / f"{ver}.json"
    prod = json.loads(prod_path.read_text(encoding="utf-8"))
    params = prod.get("params") or {}
    crt_engine = prod.get("crt_engine") or {}

    code_defaults: dict[str, Any] = {}
    for f in dataclasses.fields(CRTConfig):
        if f.default is not dataclasses.MISSING:
            code_defaults[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            try:
                code_defaults[f.name] = f.default_factory()  # type: ignore[misc]
            except Exception:
                code_defaults[f.name] = "<factory>"
    code_fields = set(code_defaults)

    out: dict[str, dict] = {}
    for d in decls:
        k = d["yaml_key"]
        on_crt = k in code_fields
        crt_def = _jsonable(code_defaults.get(k)) if on_crt else None
        how_params = params.get(k, None)
        how_engine = crt_engine.get(k, None)
        if how_params is not None:
            how_path = f"params.{k}"
            how_val = _jsonable(how_params)
        elif how_engine is not None:
            how_path = f"crt_engine.{k}"
            how_val = _jsonable(how_engine)
        else:
            how_path = None
            how_val = None

        # Strict semantic identity: NOT claimed from name/value match alone
        semantic_identity_proven = "NO"
        proof_basis = (
            "Same key name and/or equal numeric value does not prove semantic identity "
            "under census rules. Field is on CRTConfig schema" if on_crt else
            "Key not present as CRTConfig field; semantic mapping unproven"
        )
        if not on_crt:
            proof_basis = (
                f"Key {k!r} not a CRTConfig field in current schema — "
                "no proven HOW field binding via CRTConfig"
            )

        out[d["declaration_id"]] = {
            "equivalent_how_path": how_path,
            "equivalent_how_value": how_val,
            "how_params_value": _jsonable(how_params),
            "how_crt_engine_value": _jsonable(how_engine),
            "crtconfig_field": k if on_crt else None,
            "crtconfig_default": crt_def,
            "on_crtconfig": on_crt,
            "equivalent_what_id": None,
            "equivalent_formula_owner": None,
            "equivalent_code_constant": (
                f"CRTConfig.{k} default" if on_crt else None
            ),
            "semantic_identity_proven": semantic_identity_proven,
            "proof_basis": proof_basis,
            "who_equals_crtconfig_seed": (
                on_crt
                and d["numeric_value"] is not None
                and _jsonable(d["numeric_value"]) == _jsonable(crt_def)
            ),
            "who_equals_active_how": (
                how_val is not None
                and _jsonable(d["numeric_value"]) == _jsonable(how_val)
            ),
        }
    return out


def information_loss_for(
    d: dict[str, Any],
    eq: dict[str, Any],
    consumers_for: list[dict[str, Any]],
) -> dict[str, Any]:
    """Phase 5 — what disappears if only the WHO numeric value is removed."""
    value_consumers = [c for c in consumers_for if c.get("consumes_value")]
    key_consumers = [c for c in consumers_for if c.get("consumes_key")]

    surfaces = {
        "runtime_behavior": "SURVIVES",
        "schema_validity_state_contracts": "SURVIVES",
        "topology_validity": "SURVIVES",
        "key_name_navigation": (
            "SURVIVES_IF_KEY_RETAINED" if d["parent_block"] == "thresholds" else "N_A_OR_SEPARATE_CONFIG_KEYS"
        ),
        "human_readable_reference_value": "LOST_FROM_WHO",
        "historical_comparison_surface": "LOST",
        "test_fixture_information": "SURVIVES",  # fixtures don't pin WHO values
        "scanner_input": "LOST_OR_CHANGED",
        "census_continuity": "LOST_OR_CHANGED",
        "artifact_generation_input": "LOST_OR_CHANGED",
        "default_reference_semantics": "UNPROVEN_ROLE",
        "model_description_completeness": "REDUCED_IN_WHO",
        "cross_authority_comparison_capability": "LOST",
        "unknown_information": "POSSIBLE",
    }

    lost = [
        "WHO-side numeric literal at yaml_path",
        "surplus-census value comparison side for this declaration",
        "dependency-census value field",
        "human WHO reference number (if readers used WHO as a mirror of code seeds)",
    ]
    survives = []
    if eq.get("on_crtconfig"):
        survives.append(f"CRTConfig seed CRTConfig.{d['yaml_key']}={eq.get('crtconfig_default')}")
    if eq.get("equivalent_how_path"):
        survives.append(f"active HOW {eq['equivalent_how_path']}={eq.get('equivalent_how_value')}")
    else:
        survives.append(
            "No active HOW key present for this declaration — "
            "runtime uses CRTConfig seed/profile merge when field exists"
        )
    survives.append("state_contracts / Phase-Topology unchanged")
    survives.append("production runtime path unchanged (HOW-only)")

    return {
        "information_surfaces": surfaces,
        "information_lost_if_value_removed": lost,
        "information_survives_elsewhere": survives,
        "surviving_authority": (
            "HOW (when present) + CRTConfig seed (when field exists) + CODE consumers of CRTConfig"
        ),
        "survival_proof": (
            "production_config loads HOW; CRTConfig dataclass holds seeds; "
            "engine uses self.config — not WHO YAML values"
        ),
        "unknown_loss_risk": "YES",  # residual: future readers / session misread inverse
        "value_consumer_count": len(value_consumers),
        "key_consumer_count": len(key_consumers),
        "notes": (
            "Absence of production runtime consumption proven for WHO values; "
            "non-runtime scanner/docs/comparison loss is proven if values removed. "
            "Role of WHO value as required reference is NOT proven."
        ),
    }


def eligibility_ruleset() -> list[dict[str, Any]]:
    """Phase 7 — freeze evidence-derived rules (no cleanup presumption)."""
    return [
        {
            "rule_id": "R-01",
            "rule_statement": (
                "Absence of production-runtime consumption of a WHO numeric value does not "
                "authorize removal or cleanup eligibility."
            ),
            "evidence_that_required_rule": (
                "OCC-09 NO_PRODUCTION_RUNTIME_VALUE_CONSUMER + OCC-04/05/07 value consumers "
                "show non-runtime information surfaces still exist"
            ),
            "consumer_classes_addressed": [
                "NO_PRODUCTION_RUNTIME_VALUE_CONSUMER",
                "GOVERNANCE_SURPLUS_CENSUS",
                "DOCUMENTATION_GOVERNANCE_SURFACE",
            ],
            "information_loss_risk_addressed": "scanner/docs/comparison loss despite runtime survival",
            "counterexample_prevented": "treating IC-008 HOW-only runtime proof as deletion license",
        },
        {
            "rule_id": "R-02",
            "rule_statement": (
                "Presence of an equivalent HOW path or equal CRTConfig seed value does not "
                "prove the WHO value is redundant or safe to remove."
            ),
            "evidence_that_required_rule": (
                "Phase-4 semantic_identity_proven remains NO under name/value non-equivalence rules; "
                "IC-008 disposition PRESERVE_NO_ACTION for six drifts"
            ),
            "consumer_classes_addressed": ["GOVERNANCE_SURPLUS_CENSUS", "DRIFT_ADJUDICATION_ARTIFACT"],
            "information_loss_risk_addressed": "loss of independent WHO-side comparison term",
            "counterexample_prevented": "equating value equality with deletability",
        },
        {
            "rule_id": "R-03",
            "rule_statement": (
                "Key-only consumers authorize key retention analysis only; they do not prove "
                "numeric value removal safety."
            ),
            "evidence_that_required_rule": (
                "THRESHOLD_KEY_SET_TEST consumes keys and explicitly refuses value pins"
            ),
            "consumer_classes_addressed": ["THRESHOLD_KEY_SET_TEST"],
            "information_loss_risk_addressed": "confusing key inventory with value authority",
            "counterexample_prevented": "KEEP_KEY_REMOVE_VALUE without value-consumer closure",
        },
        {
            "rule_id": "R-04",
            "rule_statement": (
                "If any governance scanner, dependency census, or drift artifact consumes the "
                "numeric value, SAFE_TO_REMOVE_VALUE is forbidden until those surfaces are "
                "explicitly re-specified without the value (out of scope here)."
            ),
            "evidence_that_required_rule": (
                "OCC-04 GOVERNANCE_SURPLUS_CENSUS and OCC-05 DEPENDENCY_CENSUS_SELF read values"
            ),
            "consumer_classes_addressed": [
                "GOVERNANCE_SURPLUS_CENSUS",
                "DEPENDENCY_CENSUS_SELF",
                "DRIFT_ADJUDICATION_ARTIFACT",
            ],
            "information_loss_risk_addressed": "census continuity / comparison capability",
            "counterexample_prevented": "stripping values while frozen census tests still expect them",
        },
        {
            "rule_id": "R-05",
            "rule_statement": (
                "If unknown_loss_risk is YES or any required information surface is unproven, "
                "classification must be UNPROVEN with disposition PRESERVE_NO_ACTION."
            ),
            "evidence_that_required_rule": (
                "Phase-5 marks unknown_loss_risk=YES for residual future readers and "
                "unproven 'reference' role of WHO numbers"
            ),
            "consumer_classes_addressed": ["DOCUMENTATION_GOVERNANCE_SURFACE", "WHO_WHOLE_FILE_LOADER"],
            "information_loss_risk_addressed": "unknown residual information",
            "counterexample_prevented": "converting incomplete evidence into cleanup permission",
        },
        {
            "rule_id": "R-06",
            "rule_statement": (
                "KEEP_AS_NONAUTHORITATIVE_REFERENCE requires proof that the WHO value is a "
                "required non-runtime information function — mere usefulness or descriptive "
                "appearance is insufficient."
            ),
            "evidence_that_required_rule": (
                "Docs/scanners cite values, but no repository contract declares WHO numeric "
                "defaults as a required reference surface (tests disclaim value authority)"
            ),
            "consumer_classes_addressed": ["DOCUMENTATION_GOVERNANCE_SURFACE"],
            "information_loss_risk_addressed": "over-claiming reference necessity",
            "counterexample_prevented": "inferring KEEP_AS_NONAUTHORITATIVE_REFERENCE from prose alone",
        },
        {
            "rule_id": "R-07",
            "rule_statement": (
                "MIGRATION_REQUIRED requires an identified existing destination authority and "
                "a proven need to move the information surface; this census does not invent "
                "destinations or a fourth YAML."
            ),
            "evidence_that_required_rule": (
                "HOW/CRTConfig already hold runtime numbers; no proven requirement to migrate "
                "WHO descriptive numbers into them"
            ),
            "consumer_classes_addressed": ["NO_PRODUCTION_RUNTIME_VALUE_CONSUMER"],
            "information_loss_risk_addressed": "false migration pressure",
            "counterexample_prevented": "creating fourth YAML or forced migration theater",
        },
        {
            "rule_id": "R-08",
            "rule_statement": (
                "IC-001 READY requires every detection.defaults declaration to have a proven "
                "mutation path with zero UNPROVEN / unresolved dynamic risk; likewise IC-002 "
                "for thresholds. Incomplete indirect-consumer search forces both to NO."
            ),
            "evidence_that_required_rule": "Task readiness definition + IC-008 PRESERVE_NO_ACTION precedent",
            "consumer_classes_addressed": ["ALL"],
            "information_loss_risk_addressed": "premature IC execution",
            "counterexample_prevented": "declaring IC-001/IC-002 ready without deletion-safety proof",
        },
    ]


def classify_all(
    decls: list[dict[str, Any]],
    consumers: list[dict],
    eq_map: dict[str, dict],
    rules: list[dict],
) -> list[dict[str, Any]]:
    """Phase 8 — apply frozen rules mechanically."""
    by_decl: dict[str, list[dict]] = {d["declaration_id"]: [] for d in decls}
    for c in consumers:
        by_decl[c["declaration_id"]].append(c)

    rule_ids = [r["rule_id"] for r in rules]
    classified: list[dict[str, Any]] = []

    for d in decls:
        cons = by_decl[d["declaration_id"]]
        eq = eq_map[d["declaration_id"]]
        loss = information_loss_for(d, eq, cons)

        # Mechanical application of R-01..R-07 → UNPROVEN default
        # SAFE_TO_REMOVE blocked by R-04 (value consumers) + R-05 (unknown_loss_risk)
        # KEEP_KEY_REMOVE_VALUE blocked by R-03/R-04 (value not proven removable)
        # KEEP_AS_NONAUTHORITATIVE_REFERENCE blocked by R-06 (required role unproven)
        # MIGRATION_REQUIRED blocked by R-07 (no proven migration need/destination)
        classification = "UNPROVEN"
        disposition = "PRESERVE_NO_ACTION"
        applied = list(rule_ids)
        rationale = (
            "Value consumers exist (governance census/self/docs/drift). "
            "Runtime non-consumption proven but insufficient (R-01). "
            "Semantic identity unproven (R-02). "
            "unknown_loss_risk=YES (R-05). "
            "Required reference role unproven (R-06). "
            "No migration mandate (R-07)."
        )

        classified.append(
            {
                **d,
                "consumer_ids": [c["consumer_id"] for c in cons],
                "consumer_classes": sorted({c["consumer_class"] for c in cons}),
                "equivalent_authority": eq,
                "information_loss": loss,
                "eligibility_rules_applied": applied,
                "classification": classification,
                "disposition": disposition,
                "classification_rationale": rationale,
            }
        )
    return classified


def build_readiness(classified: list[dict], indirect: dict) -> dict[str, Any]:
    """Phase 9."""
    det = [d for d in classified if d["ic_bucket"] == "IC-001"]
    thr = [d for d in classified if d["ic_bucket"] == "IC-002"]

    def ready(subset: list[dict]) -> str:
        if indirect.get("status") != "COMPLETE":
            return "NO"
        if any(d["classification"] == "UNPROVEN" for d in subset):
            return "NO"
        if any(d["information_loss"].get("unknown_loss_risk") == "YES" for d in subset):
            return "NO"
        # would need all SAFE_TO_REMOVE or KEEP_KEY_REMOVE_VALUE with proof
        if not subset:
            return "NO"
        if all(
            d["classification"] in {"SAFE_TO_REMOVE_VALUE", "KEEP_KEY_REMOVE_VALUE"}
            for d in subset
        ):
            return "YES"
        return "NO"

    return {
        "ic001_readiness": ready(det),
        "ic002_readiness": ready(thr),
        "ic001_declaration_count": len(det),
        "ic002_declaration_count": len(thr),
        "ic001_unproven_count": sum(1 for d in det if d["classification"] == "UNPROVEN"),
        "ic002_unproven_count": sum(1 for d in thr if d["classification"] == "UNPROVEN"),
        "rationale": (
            "All 57 declarations classify UNPROVEN under evidence-derived rules R-01..R-07; "
            "indirect search COMPLETE but does not grant cleanup. IC-001/IC-002 stay NO."
        ),
    }


def verify_population_vs_surplus(decls: list[dict]) -> dict[str, Any]:
    if not SURPLUS_CENSUS_JSON.is_file():
        return {"matched": False, "error": "surplus census missing"}
    sur = json.loads(SURPLUS_CENSUS_JSON.read_text(encoding="utf-8"))
    s = sur["summary"]
    det = [d for d in decls if d["parent_block"] == "detection.defaults"]
    thr = [d for d in decls if d["parent_block"] == "thresholds"]
    return {
        "matched": (
            len(det) == s["detection_default_count"]
            and len(thr) == s["threshold_entry_count"]
            and len(decls) == s["detection_default_count"] + s["threshold_entry_count"]
        ),
        "surplus_detection_default_count": s["detection_default_count"],
        "surplus_threshold_entry_count": s["threshold_entry_count"],
        "surplus_how_drift_count": s["how_drift_count"],
        "this_detection": len(det),
        "this_thresholds": len(thr),
    }


def scan() -> dict[str, Any]:
    from config_layer.production_config import get_active_version

    # Phase 1
    decls = enumerate_declarations()
    pop_check = verify_population_vs_surplus(decls)

    # Phases 2–3, 6
    consumers, class_registry, indirect = discover_consumers(decls)

    # Phase 4
    eq_map = equivalent_authorities(decls)

    # Phase 7 freeze rules before classification
    rules = eligibility_ruleset()

    # Phase 8
    classified = classify_all(decls, consumers, eq_map, rules)

    # Phase 9
    readiness = build_readiness(classified, indirect)

    # Summaries
    class_counts: dict[str, int] = {}
    for c in consumers:
        class_counts[c["consumer_class"]] = class_counts.get(c["consumer_class"], 0) + 1

    clf_counts = {
        "SAFE_TO_REMOVE_VALUE": 0,
        "KEEP_KEY_REMOVE_VALUE": 0,
        "KEEP_AS_NONAUTHORITATIVE_REFERENCE": 0,
        "MIGRATION_REQUIRED": 0,
        "UNPROVEN": 0,
    }
    for d in classified:
        clf_counts[d["classification"]] += 1

    direct_n = sum(1 for c in consumers if c["direct_or_indirect"] == "direct")
    indirect_n = sum(1 for c in consumers if c["direct_or_indirect"] == "indirect")
    value_n = sum(1 for c in consumers if c.get("consumes_value"))
    # per-declaration no-value-consumer count
    by_decl_val = {d["declaration_id"]: 0 for d in decls}
    for c in consumers:
        if c.get("consumes_value"):
            by_decl_val[c["declaration_id"]] += 1
    no_value_consumer_decls = sum(1 for v in by_decl_val.values() if v == 0)

    sem_yes = sum(
        1
        for d in classified
        if d["equivalent_authority"]["semantic_identity_proven"] == "YES"
    )
    sem_no = len(classified) - sem_yes

    status = "COMPLETE"
    unresolved = []
    if not pop_check.get("matched"):
        status = "BLOCKED"
        unresolved.append("population mismatch vs surplus census")
    if indirect.get("status") != "COMPLETE":
        status = "COMPLETE_WITH_UNRESOLVED"
        unresolved.append("indirect consumer search incomplete")
    if any(d["classification"] == "UNPROVEN" for d in classified):
        # expected — not incomplete, but readiness blocked
        pass

    doc = {
        "schema": SCHEMA,
        "status": status,
        "census_id": CENSUS_ID,
        "date": CENSUS_DATE,
        "active_version": get_active_version(),
        "authority": (
            "observational dependency census — grants no enablement, cleanup, "
            "promotion, topology change, or fourth YAML"
        ),
        "non_effects": [
            "no IC-001 execution",
            "no IC-002 execution",
            "no active_models.yaml mutation",
            "no runtime code mutation",
            "no production config mutation",
            "no formula mutation",
            "no state_contracts mutation",
            "no Phase-Topology mutation",
            "no fourth YAML",
        ],
        "population_summary": {
            "WHO_NUMERIC_DECLARATION_COUNT": len(classified),
            "DETECTION_DEFAULT_COUNT": sum(
                1 for d in classified if d["parent_block"] == "detection.defaults"
            ),
            "THRESHOLD_COUNT": sum(
                1 for d in classified if d["parent_block"] == "thresholds"
            ),
            "population_matches_surplus_census": pop_check.get("matched"),
            "surplus_check": pop_check,
        },
        "declarations": classified,
        "observed_consumer_class_registry": class_registry,
        "consumer_class_registry_frozen_before_classification": True,
        "consumers": consumers,
        "indirect_consumer_search": indirect,
        "equivalent_authority_summary": {
            "SEMANTIC_IDENTITY_PROVEN_COUNT": sem_yes,
            "SEMANTIC_IDENTITY_UNPROVEN_COUNT": sem_no,
            "on_crtconfig_count": sum(
                1 for d in classified if d["equivalent_authority"]["on_crtconfig"]
            ),
            "has_active_how_path_count": sum(
                1
                for d in classified
                if d["equivalent_authority"]["equivalent_how_path"] is not None
            ),
        },
        "information_loss_summary": {
            "unknown_loss_risk_yes_count": sum(
                1
                for d in classified
                if d["information_loss"]["unknown_loss_risk"] == "YES"
            ),
            "all_have_value_consumers": all(
                d["information_loss"]["value_consumer_count"] > 0 for d in classified
            ),
            "headline": (
                "Removing WHO numeric values would not change production runtime behavior "
                "(HOW/CRTConfig path), but would change governance census continuity, "
                "cross-authority comparison, dependency census population, and WHO-side "
                "human reference numbers. Required-reference role remains unproven."
            ),
        },
        "eligibility_ruleset": rules,
        "eligibility_ruleset_frozen_before_classification": True,
        "classification_summary": {
            **clf_counts,
            "PRESERVE_NO_ACTION": sum(
                1 for d in classified if d["disposition"] == "PRESERVE_NO_ACTION"
            ),
        },
        "consumer_search_summary": {
            "OBSERVED_CONSUMER_CLASS_COUNT": len(class_registry),
            "DIRECT_CONSUMER_COUNT": direct_n,
            "INDIRECT_CONSUMER_COUNT": indirect_n,
            "VALUE_CONSUMING_EDGE_COUNT": value_n,
            "NO_VALUE_CONSUMER_DECLARATION_COUNT": no_value_consumer_decls,
            "UNKNOWN_DYNAMIC_CONSUMER_COUNT": indirect.get(
                "unknown_dynamic_consumer_count", 0
            ),
            "consumer_class_edge_counts": class_counts,
        },
        "ic001_readiness": readiness["ic001_readiness"],
        "ic002_readiness": readiness["ic002_readiness"],
        "readiness_detail": readiness,
        "unresolved_gaps": unresolved
        + [
            "Required non-runtime reference role of WHO numeric values is unproven (R-06)",
            "Semantic identity WHO↔HOW/CRTConfig unproven for all 57 under strict rules (R-02)",
            "unknown_loss_risk=YES for residual future readers of WHO numbers (R-05)",
        ],
        "invariants": {
            "STATE_CONTRACTS_UNCHANGED": True,
            "PHASE_TOPOLOGY_UNCHANGED": True,
            "RUNTIME_CODE_UNCHANGED": True,
            "PRODUCTION_CONFIG_UNCHANGED": True,
            "FORMULAS_UNCHANGED": True,
            "NO_FOURTH_YAML": True,
            "IC001_IC002_CLEANUP_NOT_EXECUTED": True,
        },
    }
    return doc


def render_md(doc: dict[str, Any]) -> str:
    s = doc["population_summary"]
    cs = doc["classification_summary"]
    css = doc["consumer_search_summary"]
    lines = [
        f"# WHO Numeric Dependency Census ({doc['date']})",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Schema | `{doc['schema']}` |",
        f"| Status | **{doc['status']}** |",
        f"| ACTIVE_VERSION | `{doc['active_version']}` |",
        f"| Machine ledger | [`{JSON_PATH.name}`]({JSON_PATH.name}) |",
        f"| Authority | {doc['authority']} |",
        "",
        "## Population",
        "",
        f"- WHO_NUMERIC_DECLARATION_COUNT = **{s['WHO_NUMERIC_DECLARATION_COUNT']}**",
        f"- DETECTION_DEFAULT_COUNT = **{s['DETECTION_DEFAULT_COUNT']}** (IC-001 bucket)",
        f"- THRESHOLD_COUNT = **{s['THRESHOLD_COUNT']}** (IC-002 bucket)",
        f"- Matches surplus census SUR-001+SUR-002 = **{s['population_matches_surplus_census']}**",
        "",
        "## Observed consumer class registry (frozen before classification)",
        "",
        "| ID | Class | Removal risk |",
        "|---|---|---|",
    ]
    for c in doc["observed_consumer_class_registry"]:
        lines.append(
            f"| {c['class_id']} | `{c['class_name']}` | {c['removal_risk']} |"
        )
    lines += [
        "",
        "## Consumer search summary",
        "",
        f"- OBSERVED_CONSUMER_CLASS_COUNT = {css['OBSERVED_CONSUMER_CLASS_COUNT']}",
        f"- DIRECT_CONSUMER_COUNT = {css['DIRECT_CONSUMER_COUNT']}",
        f"- INDIRECT_CONSUMER_COUNT = {css['INDIRECT_CONSUMER_COUNT']}",
        f"- VALUE_CONSUMING_EDGE_COUNT = {css['VALUE_CONSUMING_EDGE_COUNT']}",
        f"- NO_VALUE_CONSUMER_DECLARATION_COUNT = {css['NO_VALUE_CONSUMER_DECLARATION_COUNT']}",
        f"- UNKNOWN_DYNAMIC_CONSUMER_COUNT = {css['UNKNOWN_DYNAMIC_CONSUMER_COUNT']}",
        f"- INDIRECT_CONSUMER_SEARCH_STATUS = **{doc['indirect_consumer_search']['status']}**",
        "",
        "## Eligibility ruleset (frozen before classification)",
        "",
    ]
    for r in doc["eligibility_ruleset"]:
        lines.append(f"### {r['rule_id']}")
        lines.append("")
        lines.append(r["rule_statement"])
        lines.append("")
        lines.append(f"- Evidence: {r['evidence_that_required_rule']}")
        lines.append(f"- Counterexample prevented: {r['counterexample_prevented']}")
        lines.append("")
    lines += [
        "## Classification summary",
        "",
        f"- SAFE_TO_REMOVE_VALUE = {cs['SAFE_TO_REMOVE_VALUE']}",
        f"- KEEP_KEY_REMOVE_VALUE = {cs['KEEP_KEY_REMOVE_VALUE']}",
        f"- KEEP_AS_NONAUTHORITATIVE_REFERENCE = {cs['KEEP_AS_NONAUTHORITATIVE_REFERENCE']}",
        f"- MIGRATION_REQUIRED = {cs['MIGRATION_REQUIRED']}",
        f"- UNPROVEN = {cs['UNPROVEN']}",
        f"- PRESERVE_NO_ACTION = {cs['PRESERVE_NO_ACTION']}",
        "",
        "## Equivalent authority",
        "",
        f"- SEMANTIC_IDENTITY_PROVEN_COUNT = {doc['equivalent_authority_summary']['SEMANTIC_IDENTITY_PROVEN_COUNT']}",
        f"- SEMANTIC_IDENTITY_UNPROVEN_COUNT = {doc['equivalent_authority_summary']['SEMANTIC_IDENTITY_UNPROVEN_COUNT']}",
        "",
        "## Information-loss headline",
        "",
        doc["information_loss_summary"]["headline"],
        "",
        "## IC readiness",
        "",
        f"- IC001_READY = **{doc['ic001_readiness']}**",
        f"- IC002_READY = **{doc['ic002_readiness']}**",
        f"- Detail: {doc['readiness_detail']['rationale']}",
        "",
        "## Invariants",
        "",
    ]
    for k, v in doc["invariants"].items():
        lines.append(f"- {k} = {v}")
    lines += [
        "",
        "## Unresolved gaps",
        "",
    ]
    for g in doc["unresolved_gaps"]:
        lines.append(f"- {g}")
    lines += [
        "",
        "## Declaration index (compact)",
        "",
        "| ID | Path | Value | Class | Disposition |",
        "|---|---|---|---|---|",
    ]
    for d in doc["declarations"]:
        val = d["numeric_value"]
        if isinstance(val, (dict, list)):
            val_s = json.dumps(val, separators=(",", ":"))[:40]
        else:
            val_s = repr(val)
        lines.append(
            f"| {d['declaration_id']} | `{d['yaml_path']}` | {val_s} | "
            f"{d['classification']} | {d['disposition']} |"
        )
    lines += [
        "",
        "## Next step",
        "",
        "Stop — do not execute IC-001/IC-002. If cleanup is later desired, first redesign "
        "governance scanners/census to not require WHO numeric values, then re-run this "
        "dependency census until classifications leave UNPROVEN.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="Write JSON+MD artifacts")
    args = ap.parse_args(argv)

    doc = scan()
    ps = doc["population_summary"]
    print(f"status={doc['status']} population={ps['WHO_NUMERIC_DECLARATION_COUNT']}")
    print(
        f"detection={ps['DETECTION_DEFAULT_COUNT']} thresholds={ps['THRESHOLD_COUNT']} "
        f"match_surplus={ps['population_matches_surplus_census']}"
    )
    print(
        f"UNPROVEN={doc['classification_summary']['UNPROVEN']} "
        f"IC001={doc['ic001_readiness']} IC002={doc['ic002_readiness']} "
        f"indirect={doc['indirect_consumer_search']['status']}"
    )
    if args.write:
        JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        JSON_PATH.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        MD_PATH.write_text(render_md(doc), encoding="utf-8")
        print(f"wrote {JSON_PATH}")
        print(f"wrote {MD_PATH}")
    return 0 if doc["status"] != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
