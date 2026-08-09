#!/usr/bin/env python3
"""
Three-Authority Declaration Surplus Census (READ-ONLY).

Scans WHO (active_models.yaml), WHAT (market_ontology.yaml), HOW (production
JSON + CRTConfig field surface) for declaration surplus — duplicate ownership,
formula prose in WHO, numeric defaults outside HOW, multi-homed topology.

Never mutates runtime code, YAML, formulas, production config, or behavior.
Writes only census artifacts under docs/governance/ when --write is passed.

Usage:
  py -3.12 scripts/governance/three_authority_surplus_census.py            # print summary
  py -3.12 scripts/governance/three_authority_surplus_census.py --write    # refresh artifacts
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

CENSUS_ID = "three_authority_declaration_surplus_census"
CENSUS_DATE = "2026-07-11"
SCHEMA = "three_authority_declaration_surplus_census.v1"
JSON_PATH = _REPO / "docs" / "governance" / f"{CENSUS_ID}-{CENSUS_DATE}.json"
MD_PATH = _REPO / "docs" / "governance" / f"{CENSUS_ID}-{CENSUS_DATE}.md"


def _load_yaml(path: Path) -> dict:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: root must be mapping")
    return data


def _crt_config_defaults() -> dict[str, Any]:
    from config_layer.crt_engine_v2 import CRTConfig

    out: dict[str, Any] = {}
    for f in dataclasses.fields(CRTConfig):
        if f.default is not dataclasses.MISSING:
            out[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            try:
                out[f.name] = f.default_factory()  # type: ignore[misc]
            except Exception:
                out[f.name] = "<factory>"
    return out


def _norm(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    return v


def _formulaish(s: str) -> bool:
    if not isinstance(s, str):
        return False
    markers = (
        ">=",
        "<=",
        "×",
        "*",
        "/",
        "exp(",
        " AND ",
        " OR ",
        "max(",
        "min(",
        "abs(",
        "^",
    )
    return any(m in s for m in markers)


def _walk(obj: Any, path: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            yield from _walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def scan() -> dict[str, Any]:
    """Pure scan — returns full census document as dict."""
    from config_layer.crt_engine_v2 import CRTState, VALID_TRANSITIONS
    from config_layer.production_config import get_active_version
    from features.registry import load_ontology

    am_path = _REPO / "active_models.yaml"
    ont_path = _REPO / "configs" / "formulas" / "market_ontology.yaml"
    graph_path = _REPO / "docs" / "governance" / "crt_executable_state_graph.json"

    am = _load_yaml(am_path)
    crt = am["crt"]["runtime"]
    sc = crt.get("state_contracts") or {}
    det = crt.get("detection") or {}
    thr = crt.get("thresholds") or {}
    scoring = crt.get("scoring") or {}
    lifecycle = crt.get("lifecycle") or {}
    cached = crt.get("cached_features_at_retest") or []

    ver = get_active_version()
    prod_path = _REPO / "configs" / "production" / f"{ver}.json"
    prod = json.loads(prod_path.read_text(encoding="utf-8"))
    params = prod.get("params") or {}
    crt_engine = prod.get("crt_engine") or {}

    code_defaults = _crt_config_defaults()
    code_fields = set(code_defaults)

    # ── detection defaults ────────────────────────────────────────────────
    det_defaults: list[dict[str, Any]] = []
    for dname, block in det.items():
        if not isinstance(block, dict):
            continue
        for k, v in (block.get("defaults") or {}).items():
            code_def = code_defaults.get(k, None)
            prod_val = params.get(k, crt_engine.get(k))
            det_defaults.append(
                {
                    "detection_state": dname,
                    "key": k,
                    "am_default": v,
                    "crtconfig_default": code_def if k in code_fields else None,
                    "on_crtconfig": k in code_fields,
                    "prod_params": params.get(k),
                    "prod_crt_engine": crt_engine.get(k),
                    "active_how": prod_val,
                    "am_equals_code_default": (
                        k in code_fields and _norm(v) == _norm(code_def)
                    ),
                    "am_equals_active_how": (
                        prod_val is not None and _norm(v) == _norm(prod_val)
                    ),
                }
            )

    # ── thresholds block ──────────────────────────────────────────────────
    thr_rows: list[dict[str, Any]] = []
    for k, spec in thr.items():
        am_def = spec.get("default") if isinstance(spec, dict) else spec
        code_def = code_defaults.get(k) if k in code_fields else None
        prod_val = params.get(k, crt_engine.get(k))
        thr_rows.append(
            {
                "key": k,
                "am_default": am_def,
                "on_crtconfig": k in code_fields,
                "crtconfig_default": code_def,
                "prod_params": params.get(k),
                "prod_crt_engine": crt_engine.get(k),
                "active_how": prod_val,
                "am_equals_code_default": (
                    k in code_fields
                    and am_def is not None
                    and _norm(am_def) == _norm(code_def)
                ),
                "am_equals_active_how": (
                    prod_val is not None and _norm(am_def) == _norm(prod_val)
                ),
            }
        )

    how_drift = [
        r
        for r in thr_rows
        if r["active_how"] is not None and not r["am_equals_active_how"]
    ]

    # ── formula prose ─────────────────────────────────────────────────────
    formula_paths: list[dict[str, str]] = []
    for p, v in _walk(
        {"detection": det, "scoring": scoring, "lifecycle": lifecycle}
    ):
        if isinstance(v, str) and _formulaish(v) and "file_line" not in p:
            formula_paths.append({"path": f"crt.runtime.{p}", "text": v})

    # ── topology multi-home ───────────────────────────────────────────────
    yaml_states = set(crt.get("state_list") or [])
    code_states = {s.name for s in CRTState}
    yaml_trans = {
        k: set(v) for k, v in (crt.get("valid_transitions") or {}).items()
    }
    code_trans = {
        s.name: {t.name for t in ts} for s, ts in VALID_TRANSITIONS.items()
    }
    graph_states: set[str] = set()
    graph_exists = graph_path.is_file()
    if graph_exists:
        g = json.loads(graph_path.read_text(encoding="utf-8"))
        graph_states = {s["name"] for s in g.get("states") or []}

    # ── state_contracts cleanliness ───────────────────────────────────────
    allowed_sc = {"required_fm", "config_keys", "eligible_models"}
    sc_violations: list[str] = []
    contract_fm: set[str] = set()
    contract_keys: set[str] = set()
    for sid, body in sc.items():
        if not isinstance(body, dict):
            sc_violations.append(f"{sid}: not a mapping")
            continue
        extra = set(body) - allowed_sc
        if extra:
            sc_violations.append(f"{sid}: extra fields {sorted(extra)}")
        for fm in body.get("required_fm") or []:
            contract_fm.add(fm)
        for k in body.get("config_keys") or []:
            contract_keys.add(k)

    det_config_keys: set[str] = set()
    for block in det.values():
        if isinstance(block, dict):
            det_config_keys |= set(block.get("config_keys") or [])

    thr_keys = set(thr.keys())

    # ── ontology ──────────────────────────────────────────────────────────
    ont = load_ontology()
    ontology_fm: set[str] = set()
    for sec in ("primitives", "feature_compositions", "derived_metrics"):
        for _name, spec in (ont.get(sec) or {}).items():
            if isinstance(spec, dict) and spec.get("id"):
                ontology_fm.add(spec["id"])

    # ── cached features ───────────────────────────────────────────────────
    cached_fm = [
        row.get("fm_id")
        for row in cached
        if isinstance(row, dict) and row.get("fm_id")
    ]
    cached_names = [
        row.get("feature")
        for row in cached
        if isinstance(row, dict) and row.get("feature")
    ]

    # ── surplus records ───────────────────────────────────────────────────
    records: list[dict[str, Any]] = []

    def add(
        rid: str,
        klass: str,
        *,
        surplus_layer: str,
        owner_layer: str,
        path: str,
        evidence: str,
        runtime_consumed: bool,
        authority_risk: str,
        candidate: dict[str, Any],
        count: int | None = None,
        details: Any = None,
    ) -> None:
        records.append(
            {
                "id": rid,
                "class": klass,
                "surplus_layer": surplus_layer,
                "owner_layer": owner_layer,
                "path": path,
                "evidence": evidence,
                "runtime_consumed": runtime_consumed,
                "authority_risk": authority_risk,
                "count": count,
                "details": details,
                "implementation_candidate_id": candidate["id"],
            }
        )

    # IC definitions (ledger)
    candidates: list[dict[str, Any]] = [
        {
            "id": "IC-001",
            "title": "Mark/strip detection.defaults numeric block",
            "action": "MARK_NON_AUTHORITATIVE_OR_STRIP",
            "priority": "P1",
            "touches": ["active_models.yaml crt.runtime.detection.*.defaults"],
            "parity_required": True,
            "runtime_impact": "none if currently unread (verify)",
            "depends_on": [],
            "note": "WHO must not own HOW numbers; keep config_keys names only",
        },
        {
            "id": "IC-002",
            "title": "Mark/strip crt.runtime.thresholds numeric defaults",
            "action": "MARK_NON_AUTHORITATIVE_OR_STRIP",
            "priority": "P1",
            "touches": ["active_models.yaml crt.runtime.thresholds"],
            "parity_required": True,
            "runtime_impact": "none if unread; session-doc only today",
            "depends_on": [],
            "note": "Replace with key-name index pointing at HOW/CRTConfig",
        },
        {
            "id": "IC-003",
            "title": "Convert detection logic strings → closed guard IDs",
            "action": "CONVERT_TO_GUARD_ID_REFS",
            "priority": "P2",
            "touches": ["active_models.yaml detection.*.logic*"],
            "parity_required": True,
            "runtime_impact": "none until dispatch phase; docs only first",
            "depends_on": ["guard-registry phase"],
            "note": "Never eval strings; Python registry remains executable",
        },
        {
            "id": "IC-004",
            "title": "Convert scoring formula prose → code/FM refs; optional HOW weights",
            "action": "CONVERT_TO_REFS_OR_HOWLIZE",
            "priority": "P2",
            "touches": [
                "active_models.yaml scoring.raw_formula",
                "scoring.decay",
                "scoring.soft_conf_fusion",
            ],
            "parity_required": True,
            "runtime_impact": "externalizing weights changes HOW surface only if wired",
            "depends_on": [],
            "note": "RiskScore 0.35/0.25/0.20/0.20 + soft-conf exponents are dual-homed",
        },
        {
            "id": "IC-005",
            "title": "Topology dual authority — keep parity or codegen seed",
            "action": "KEEP_LOAD_BEARING_DUAL_OR_CODEGEN",
            "priority": "P2",
            "touches": [
                "active_models.yaml valid_transitions",
                "crt_engine_v2.VALID_TRANSITIONS",
            ],
            "parity_required": True,
            "runtime_impact": "Phase-Topology already uses WHO graph; seed is baseline",
            "depends_on": [],
            "note": "Do not drop code seed without explicit approval",
        },
        {
            "id": "IC-006",
            "title": "Mark crt_executable_state_graph.json as DERIVED or re-pin",
            "action": "MARK_DERIVED_OR_REGENERATE",
            "priority": "P3",
            "touches": ["docs/governance/crt_executable_state_graph.json"],
            "parity_required": True,
            "runtime_impact": "none (docs/tests only)",
            "depends_on": [],
            "note": "Third topology home; tests already pin to code",
        },
        {
            "id": "IC-007",
            "title": "Externalize hardcoded min_depth 0.1*ATR + RiskScore weights to HOW",
            "action": "HOWLIZE_HARDCODED_BEHAVIORAL",
            "priority": "P3",
            "touches": [
                "crt_engine_v2 try_expansion_to_retest",
                "score_* weights",
                "production crt_engine",
            ],
            "parity_required": True,
            "runtime_impact": "requires config keys + parity proof",
            "depends_on": ["§6.5 config-first"],
            "note": "Deferred gaps from matrix §11.6",
        },
        {
            "id": "IC-008",
            "title": "Annotate WHO defaults that disagree with active HOW params",
            "action": "ANNOTATE_SEED_VS_ACTIVE_HOW",
            "priority": "P1",
            "touches": ["active_models thresholds/detection defaults", "params"],
            "parity_required": False,
            "runtime_impact": "docs only",
            "depends_on": [],
            "note": "body_ratio_min/params 0.65 vs WHO 0.70 etc. — prevent session misread",
        },
        {
            "id": "IC-009",
            "title": "Deduplicate detection.config_keys vs state_contracts.config_keys",
            "action": "SINGLE_SOURCE_KEY_NAMES",
            "priority": "P3",
            "touches": ["detection.*.config_keys", "state_contracts"],
            "parity_required": True,
            "runtime_impact": "none if contracts remain loader authority",
            "depends_on": [],
            "note": "detection config_keys are strict subset of contracts today",
        },
        {
            "id": "IC-010",
            "title": "Optional used_by_states on ontology FMs (DESC only)",
            "action": "OPTIONAL_DESC_TAG",
            "priority": "P3",
            "touches": ["market_ontology.yaml"],
            "parity_required": False,
            "runtime_impact": "none",
            "depends_on": [],
            "note": "Not surplus cleanup; navigation aid only",
        },
    ]

    add(
        "SUR-001",
        "NUMERIC_DEFAULT_IN_WHO",
        surplus_layer="WHO",
        owner_layer="HOW",
        path="active_models.yaml crt.runtime.detection.*.defaults",
        evidence=(
            f"{len(det_defaults)} numeric defaults under detection blocks "
            f"(displacement/expansion/retest/expired). Restate CRTConfig/HOW seeds; "
            f"not loaded by state_contract_loader or Phase-Topology."
        ),
        runtime_consumed=False,
        authority_risk="HIGH_DOC_DRIFT",
        count=len(det_defaults),
        details=det_defaults,
        candidate=candidates[0],
    )
    add(
        "SUR-002",
        "NUMERIC_DEFAULT_IN_WHO",
        surplus_layer="WHO",
        owner_layer="HOW",
        path="active_models.yaml crt.runtime.thresholds",
        evidence=(
            f"{len(thr_rows)} threshold entries with embedded default values. "
            f"Mirror CRTConfig dataclass defaults; session readers may treat as runtime HOW."
        ),
        runtime_consumed=False,
        authority_risk="HIGH_DOC_DRIFT",
        count=len(thr_rows),
        details={"keys": sorted(thr_keys), "how_drift_count": len(how_drift)},
        candidate=candidates[1],
    )
    add(
        "SUR-003",
        "HOW_ACTIVE_VS_WHO_DEFAULT_DRIFT",
        surplus_layer="WHO",
        owner_layer="HOW",
        path="params / crt_engine vs crt.runtime.thresholds|detection.defaults",
        evidence=(
            f"{len(how_drift)} keys where active production value ≠ WHO declared default "
            f"(e.g. body_ratio_min params=0.65 vs WHO 0.70). Runtime follows HOW when loaded."
        ),
        runtime_consumed=False,
        authority_risk="HIGH_SESSION_MISREAD",
        count=len(how_drift),
        details=how_drift,
        candidate=candidates[7],
    )
    add(
        "SUR-004",
        "FORMULA_PROSE_IN_WHO",
        surplus_layer="WHO",
        owner_layer="CODE_OR_WHAT",
        path="active_models.yaml crt.runtime.detection|scoring logic strings",
        evidence=(
            f"{len(formula_paths)} formula-like prose strings in detection/scoring. "
            f"Not executable; risk of dual-math narrative vs candle_math/derived_math/code."
        ),
        runtime_consumed=False,
        authority_risk="MEDIUM_DOC_DRIFT",
        count=len(formula_paths),
        details=formula_paths,
        candidate=candidates[2],
    )
    add(
        "SUR-005",
        "SCORING_WEIGHTS_IN_WHO",
        surplus_layer="WHO",
        owner_layer="CODE",
        path="active_models.yaml crt.runtime.scoring",
        evidence=(
            "raw_formula embeds 0.35/0.25/0.20/0.20; soft_conf G^0.70×C^0.30; "
            "decay exp(-0.05×…). Parallel to code hardcodes; no FM ids."
        ),
        runtime_consumed=False,
        authority_risk="MEDIUM_DOC_DRIFT",
        count=3,
        details={
            "raw_formula": scoring.get("raw_formula"),
            "decay": scoring.get("decay"),
            "soft_conf_fusion": scoring.get("soft_conf_fusion"),
        },
        candidate=candidates[3],
    )
    add(
        "SUR-006",
        "DUAL_TOPOLOGY_LOAD_BEARING",
        surplus_layer="WHO+CODE",
        owner_layer="WHO_RUNTIME_GRAPH+CODE_SEED",
        path="valid_transitions ↔ VALID_TRANSITIONS",
        evidence=(
            f"YAML transitions parity with code seed: {yaml_trans == code_trans}. "
            f"Phase-Topology injects WHO graph into StateMachine; module dict remains seed. "
            f"state_list==CRTState: {yaml_states == code_states}."
        ),
        runtime_consumed=True,
        authority_risk="LOW_IF_PARITY_ENFORCED",
        count=len(yaml_states),
        details={
            "yaml_states": sorted(yaml_states),
            "code_states": sorted(code_states),
            "transitions_equal": yaml_trans == code_trans,
            "states_equal": yaml_states == code_states,
        },
        candidate=candidates[4],
    )
    add(
        "SUR-007",
        "TRIPLE_TOPOLOGY_ARTIFACT",
        surplus_layer="DOCS",
        owner_layer="CODE",
        path="docs/governance/crt_executable_state_graph.json",
        evidence=(
            f"Third topology home exists={graph_exists}; "
            f"states match state_list: {graph_states == yaml_states if graph_exists else None}. "
            f"Pinned by tests/test_crt_executable_state_graph.py."
        ),
        runtime_consumed=False,
        authority_risk="LOW_TEST_PINNED",
        count=len(graph_states) if graph_exists else 0,
        details={"graph_exists": graph_exists, "states_match": graph_states == yaml_states},
        candidate=candidates[5],
    )
    add(
        "SUR-008",
        "HARDCODED_BEHAVIORAL_IN_CODE",
        surplus_layer="CODE",
        owner_layer="SHOULD_BE_HOW",
        path="crt_engine_v2 min_depth=0.1*ATR; RiskScore weights",
        evidence=(
            "detection.retest.min_depth prose '0.1 × ATR' and scoring weights lack production "
            "keys — behavioral constants frozen in code (matrix §11.6 deferred gaps)."
        ),
        runtime_consumed=True,
        authority_risk="MEDIUM_CONFIG_FIRST_GAP",
        count=2,
        details={
            "min_depth_prose": (det.get("retest") or {}).get("min_depth"),
            "adaptive_ceiling_prose": (det.get("retest") or {}).get("adaptive_ceiling"),
        },
        candidate=candidates[6],
    )
    add(
        "SUR-009",
        "KEY_NAME_REDUNDANCY",
        surplus_layer="WHO",
        owner_layer="WHO_STATE_CONTRACTS",
        path="detection.*.config_keys vs state_contracts.*.config_keys",
        evidence=(
            f"detection config_keys ({len(det_config_keys)}) are subset of "
            f"state_contracts config_keys ({len(contract_keys)}). "
            f"detection_only={sorted(det_config_keys - contract_keys)}; "
            f"intersection_n={len(det_config_keys & contract_keys)}."
        ),
        runtime_consumed=False,
        authority_risk="LOW",
        count=len(det_config_keys),
        details={
            "detection_config_keys": sorted(det_config_keys),
            "contract_config_keys_n": len(contract_keys),
            "intersection": sorted(det_config_keys & contract_keys),
        },
        candidate=candidates[8],
    )
    add(
        "SUR-010",
        "THRESHOLDS_NOT_IN_STATE_CONTRACTS",
        surplus_layer="WHO_INDEX_GAP",
        owner_layer="HOW",
        path="thresholds keys absent from state_contracts.config_keys",
        evidence=(
            f"{len(thr_keys - contract_keys)} threshold keys not listed on any state contract "
            f"(still on CRTConfig / crt_engine). Not surplus ownership — coverage gap in WHO contracts."
        ),
        runtime_consumed=False,
        authority_risk="LOW_NAVIGATION",
        count=len(thr_keys - contract_keys),
        details={"keys": sorted(thr_keys - contract_keys)},
        candidate=candidates[1],
    )
    add(
        "SUR-011",
        "CLEAN_STATE_CONTRACTS",
        surplus_layer="NONE",
        owner_layer="WHO",
        path="active_models.yaml crt.runtime.state_contracts",
        evidence=(
            f"9 state contracts; allowed fields only; violations={sc_violations or 'none'}; "
            f"required_fm={sorted(contract_fm)}; no numeric thresholds in contracts."
        ),
        runtime_consumed=True,
        authority_risk="NONE_POSITIVE_CONTROL",
        count=len(sc),
        details={
            "states": sorted(sc.keys()),
            "required_fm": sorted(contract_fm),
            "violations": sc_violations,
            "cached_fm_ids": cached_fm,
            "cached_feature_names": cached_names,
        },
        candidate={
            "id": "IC-KEEP",
            "title": "Keep state_contracts as WHO dependency authority",
            "action": "KEEP",
            "priority": "P0",
            "touches": ["state_contracts"],
            "parity_required": True,
            "runtime_impact": "already load-bearing",
            "depends_on": [],
            "note": "Positive control — not surplus",
        },
    )
    add(
        "SUR-012",
        "ONTOLOGY_FM_NOT_IN_CONTRACTS",
        surplus_layer="NONE",
        owner_layer="WHAT",
        path="market_ontology.yaml FM ids without state_contracts.required_fm",
        evidence=(
            f"{len(ontology_fm - contract_fm)} ontology FMs not declared on CRT state contracts. "
            f"Not surplus; optional navigation (used_by_states DESC)."
        ),
        runtime_consumed=False,
        authority_risk="NONE",
        count=len(ontology_fm - contract_fm),
        details={"fm_ids": sorted(ontology_fm - contract_fm)},
        candidate=candidates[9],
    )

    # attach IC-KEEP to candidates list for ledger completeness
    candidates_out = candidates + [
        {
            "id": "IC-KEEP",
            "title": "Keep state_contracts as WHO dependency authority",
            "action": "KEEP",
            "priority": "P0",
            "touches": ["state_contracts"],
            "parity_required": True,
            "runtime_impact": "already load-bearing",
            "depends_on": [],
            "note": "Positive control — not surplus",
        }
    ]

    summary = {
        "detection_default_count": len(det_defaults),
        "threshold_entry_count": len(thr_rows),
        "how_drift_count": len(how_drift),
        "formula_prose_count": len(formula_paths),
        "state_contract_count": len(sc),
        "state_contract_field_violations": len(sc_violations),
        "contract_required_fm": sorted(contract_fm),
        "contract_config_keys_n": len(contract_keys),
        "ontology_fm_n": len(ontology_fm),
        "ontology_fm_not_in_contracts_n": len(ontology_fm - contract_fm),
        "topology_yaml_code_equal": yaml_trans == code_trans and yaml_states == code_states,
        "surplus_record_count": len(records),
        "implementation_candidate_count": len(candidates_out),
        "p1_candidates": [c["id"] for c in candidates_out if c.get("priority") == "P1"],
    }

    doc = {
        "schema": SCHEMA,
        "census_id": CENSUS_ID,
        "date": CENSUS_DATE,
        "status": "CENSUS_ONLY",
        "authority": "observational — grants no enablement, promotion, or topology change",
        "non_effects": [
            "no runtime code change",
            "no YAML/formula/config mutation by this census",
            "no behavior change",
            "no fourth YAML recommended",
        ],
        "authority_model": {
            "WHAT": {
                "home": "configs/formulas/market_ontology.yaml",
                "owns": "FM identity, formula meaning, impl bindings, depends_on",
            },
            "WHO": {
                "home": "active_models.yaml",
                "owns": "model selection, state identities, transitions, required_fm, config key names, eligible_models",
                "must_not_own": "numeric thresholds, formula text, eval expressions",
            },
            "HOW": {
                "home": f"configs/production/{ver}.json (+ CRTConfig fields)",
                "owns": "threshold values, TTLs, flags, paths",
            },
            "CODE": {
                "home": "src/config_layer/crt_engine_v2.py (+ features/*)",
                "owns": "executable guards, CRTState enum, VALID_TRANSITIONS seed, formula callables",
            },
        },
        "active_version": ver,
        "surfaces_scanned": {
            "who": str(am_path.as_posix()),
            "what": str(ont_path.as_posix()),
            "how_production": str(prod_path.as_posix()),
            "how_schema": "CRTConfig fields in src/config_layer/crt_engine_v2.py",
            "topology_seed": "VALID_TRANSITIONS",
            "topology_artifact": str(graph_path.as_posix()),
        },
        "summary": summary,
        "surplus_records": records,
        "implementation_candidate_ledger": candidates_out,
        "positive_controls": {
            "state_contracts_ids_only": len(sc_violations) == 0,
            "required_fm_in_ontology": contract_fm <= ontology_fm,
            "contract_keys_on_crtconfig": contract_keys <= code_fields,
            "cached_features_use_fm_ids": set(cached_fm) <= {"FM-010", "FM-027", "FM-028"}
            or set(cached_fm) == {"FM-027", "FM-010", "FM-028"},
        },
    }
    return doc


def render_md(doc: dict[str, Any]) -> str:
    s = doc["summary"]
    lines = [
        f"# Three-Authority Declaration Surplus Census ({doc['date']})",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Schema | `{doc['schema']}` |",
        f"| Status | **{doc['status']}** — observational only |",
        f"| ACTIVE_VERSION | `{doc['active_version']}` |",
        f"| Authority | {doc['authority']} |",
        f"| Machine ledger | [`{JSON_PATH.name}`]({JSON_PATH.name}) |",
        "",
        "## Authority model (frozen)",
        "",
        "| Layer | Home | Owns | Must not own |",
        "|---|---|---|---|",
        "| **WHAT** | `configs/formulas/market_ontology.yaml` | FM identity, formulas, impl bindings | thresholds, state graph |",
        "| **WHO** | `active_models.yaml` | models, states, transitions, required_fm, config *names* | numbers, formula text, eval |",
        "| **HOW** | production JSON + `CRTConfig` | threshold values, TTLs, flags | FM math |",
        "| **CODE** | `crt_engine_v2` + `features/*` | guards, enum, seed graph, callables | — |",
        "",
        "**No fourth YAML.** Surplus cleanup = strip/mark/ref — not a new registry file.",
        "",
        "## Summary counts",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Detection numeric defaults (WHO) | {s['detection_default_count']} |",
        f"| Threshold block entries (WHO) | {s['threshold_entry_count']} |",
        f"| Active HOW ≠ WHO default drifts | {s['how_drift_count']} |",
        f"| Formula-like prose paths (WHO) | {s['formula_prose_count']} |",
        f"| State contracts (clean WHO) | {s['state_contract_count']} |",
        f"| Contract field violations | {s['state_contract_field_violations']} |",
        f"| Contract required_fm | {', '.join(s['contract_required_fm'])} |",
        f"| Ontology FMs not in contracts | {s['ontology_fm_not_in_contracts_n']} |",
        f"| Topology YAML≡code seed | {s['topology_yaml_code_equal']} |",
        f"| Surplus records | {s['surplus_record_count']} |",
        f"| Implementation candidates | {s['implementation_candidate_count']} |",
        f"| P1 candidates | {', '.join(s['p1_candidates'])} |",
        "",
        "## Surplus records",
        "",
        "| ID | Class | Surplus | Owner | Runtime? | Risk | IC |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in doc["surplus_records"]:
        lines.append(
            f"| {r['id']} | {r['class']} | {r['surplus_layer']} | {r['owner_layer']} | "
            f"{'Y' if r['runtime_consumed'] else 'N'} | {r['authority_risk']} | "
            f"{r['implementation_candidate_id']} |"
        )
    lines.extend(
        [
            "",
            "### Record detail (abridged)",
            "",
        ]
    )
    for r in doc["surplus_records"]:
        lines.extend(
            [
                f"#### {r['id']} — {r['class']}",
                "",
                f"- **Path:** `{r['path']}`",
                f"- **Evidence:** {r['evidence']}",
                f"- **Count:** {r.get('count')}",
                f"- **Candidate:** {r['implementation_candidate_id']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Implementation-candidate ledger",
            "",
            "| ID | Priority | Action | Title | Parity? |",
            "|---|---|---|---|---|",
        ]
    )
    for c in doc["implementation_candidate_ledger"]:
        lines.append(
            f"| {c['id']} | {c['priority']} | {c['action']} | {c['title']} | "
            f"{'Y' if c.get('parity_required') else 'N'} |"
        )
    lines.extend(
        [
            "",
            "### Recommended order (docs-only first)",
            "",
            "1. **IC-008** — annotate WHO seed vs active HOW drifts (prevents session misread).",
            "2. **IC-001 / IC-002** — mark or strip numeric defaults under detection/thresholds.",
            "3. **IC-005 / IC-006** — keep topology dual load-bearing; mark graph JSON derived.",
            "4. **IC-003 / IC-004** — guard/scoring prose → refs (after guard-registry design).",
            "5. **IC-007** — HOW-lize hardcoded behavioral constants (config-first parity).",
            "6. **IC-KEEP** — do not disturb clean `state_contracts`.",
            "",
            "## Positive controls",
            "",
        ]
    )
    for k, v in doc["positive_controls"].items():
        lines.append(f"- `{k}`: **{v}**")
    lines.extend(
        [
            "",
            "## Explicit non-effects of this census",
            "",
        ]
    )
    for n in doc["non_effects"]:
        lines.append(f"- {n}")
    lines.extend(
        [
            "",
            "## Regeneration",
            "",
            "```text",
            "py -3.12 scripts/governance/three_authority_surplus_census.py --write",
            "py -3.12 -m pytest tests/test_three_authority_surplus_census.py -q",
            "```",
            "",
            "---",
            "",
            f"*Generated {doc['date']} by `scripts/governance/three_authority_surplus_census.py`.*",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(doc: dict[str, Any]) -> None:
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8"
    )
    MD_PATH.write_text(render_md(doc), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--write",
        action="store_true",
        help="Write docs/governance census JSON + MD artifacts",
    )
    args = p.parse_args(argv)
    doc = scan()
    s = doc["summary"]
    print(f"census={CENSUS_ID} date={CENSUS_DATE}")
    print(f"detection_defaults={s['detection_default_count']} thresholds={s['threshold_entry_count']}")
    print(f"how_drift={s['how_drift_count']} formula_prose={s['formula_prose_count']}")
    print(f"records={s['surplus_record_count']} candidates={s['implementation_candidate_count']}")
    print(f"P1={s['p1_candidates']}")
    if args.write:
        write_artifacts(doc)
        print(f"wrote {JSON_PATH}")
        print(f"wrote {MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
