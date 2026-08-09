"""
MSIP-1 Verification Package Construction (READ-ONLY w.r.t. production code).

Collects authoritative repository slices, mechanically extracts the CRT nine-state
baseline, runs the mechanical test subset, emits SHA256 manifest + design matrices,
and freezes everything under msip_1_verification_package/.

Does NOT modify production code, configs, ledgers, or ontology.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "msip_1_verification_package"
STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
PY = sys.executable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(ROOT / "src"))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip()
    except Exception:
        return "UNKNOWN"


def git_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip()
    except Exception:
        return "UNKNOWN"


def copy_file(src_rel: str, dest: Path, required: bool = True) -> dict:
    src = ROOT / src_rel
    rec = {
        "source_path": src_rel.replace("\\", "/"),
        "package_path": str(dest.relative_to(PKG)).replace("\\", "/"),
        "required": required,
        "exists": src.exists(),
    }
    if not src.exists():
        rec["status"] = "MISSING"
        rec["sha256"] = None
        rec["bytes"] = 0
        if required:
            rec["error"] = "required source missing"
        return rec
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    rec["sha256"] = sha256_file(dest)
    rec["bytes"] = dest.stat().st_size
    rec["status"] = "COPIED"
    return rec


# ── package layout ────────────────────────────────────────────────────────────

DIRS = [
    "00_manifest",
    "01_governance",
    "02_feature_authority",
    "03_feature_evidence",
    "04_crt_runtime",
    "05_tests",
    "06_design",
    "07_llm_responses",
]


# authority_class values: AUTHORITY | EVIDENCE | POINTER | HISTORICAL | QUERY_SURFACE | DESIGN | TEST | REPORT
FILE_PLAN: list[tuple[str, str, str, str, bool]] = [
    # (src_rel, dest_rel, authority_class, purpose, required)
    # 01 governance
    ("CLAUDE.md", "01_governance/CLAUDE.md", "AUTHORITY", "Repository doctrine, closure rules, evidence discipline", True),
    ("assistant_project.md", "01_governance/assistant_project.md", "EVIDENCE", "Historical architecture decisions and session state", True),
    ("docs/governance/closure_authority_index.json", "01_governance/closure_authority_index.json", "AUTHORITY", "Boundary-scoped non-transitive closure index", True),
    # 02 feature authority
    ("configs/formulas/market_ontology.yaml", "02_feature_authority/market_ontology.yaml", "AUTHORITY", "WHAT-layer formula identities", True),
    ("src/features/feature_schema.py", "02_feature_authority/feature_schema.py", "AUTHORITY", "CANONICAL_FEATURES + schema hashes", True),
    ("src/features/candle_math.py", "02_feature_authority/candle_math.py", "AUTHORITY", "Immutable OHLC geometry identities", True),
    ("src/features/derived_math.py", "02_feature_authority/derived_math.py", "AUTHORITY", "Canonical normalized scalar mathematics", True),
    ("src/features/feature_pipeline.py", "02_feature_authority/feature_pipeline.py", "AUTHORITY", "Primary executable batch feature producer", True),
    ("src/features/causal_structure.py", "02_feature_authority/causal_structure.py", "AUTHORITY", "Causal structure + delayed swing semantics", True),
    ("src/features/fm_resolve.py", "02_feature_authority/fm_resolve.py", "AUTHORITY", "FM ID → callable resolution + lifecycle", True),
    ("src/features/formula_registry.py", "02_feature_authority/formula_registry.py", "AUTHORITY", "Registry facade over ontology bindings", True),
    ("src/features/registry/__init__.py", "02_feature_authority/registry/__init__.py", "AUTHORITY", "Registry package entry", True),
    ("src/features/registry/_loader.py", "02_feature_authority/registry/_loader.py", "AUTHORITY", "Ontology loader", True),
    ("src/features/registry/primitive_registry.py", "02_feature_authority/registry/primitive_registry.py", "AUTHORITY", "Primitive bindings", True),
    ("src/features/registry/derived_registry.py", "02_feature_authority/registry/derived_registry.py", "AUTHORITY", "Derived bindings", True),
    ("src/features/registry/composition_registry.py", "02_feature_authority/registry/composition_registry.py", "AUTHORITY", "Composition bindings", True),
    # 03 feature evidence
    ("docs/governance/phase1_feature_identity_registry-2026-07-10.json", "03_feature_evidence/phase1_feature_identity_registry-2026-07-10.json", "EVIDENCE", "Canonical identities / aliases / authority", True),
    ("docs/governance/feature_dependency_graph_fc05-2026-07-10.json", "03_feature_evidence/feature_dependency_graph_fc05-2026-07-10.json", "HISTORICAL", "Historical deps/PIT — may be superseded by FC1-A; see AUTHORITY_FRESHNESS.md", True),
    ("docs/governance/phase1_run1_feature_producer_consumer_graph-2026-07-10.json", "03_feature_evidence/phase1_run1_feature_producer_consumer_graph-2026-07-10.json", "EVIDENCE", "Producer/write-site census", True),
    ("docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json", "03_feature_evidence/feature_consumer_binding_manifest_fc05-2026-07-10.json", "EVIDENCE", "Consumer/model bindings (2026-07-10; may lag M9–M15)", True),
    ("docs/governance/feature_contract_v1-2026-07-10.json", "03_feature_evidence/feature_contract_v1-2026-07-10.json", "HISTORICAL", "Historical contract — not current authority where superseded", True),
    ("docs/governance/feature_38_lineage_census.LATEST.json", "03_feature_evidence/feature_38_lineage_census.LATEST.json", "POINTER", "Stable pointer to lineage census", True),
    ("docs/governance/feature_38_lineage_census-2026-07-11.json", "03_feature_evidence/feature_38_lineage_census-2026-07-11.json", "EVIDENCE", "Current lineage census body (pointer target)", True),
    ("docs/governance/canonical_feature_code_surface_closure-2026-07-11.md", "03_feature_evidence/canonical_feature_code_surface_closure-2026-07-11.md", "AUTHORITY", "Feature code-surface closure report", True),
    ("docs/governance/feature_surface_closure_audit-2026-07-11.json", "03_feature_evidence/feature_surface_closure_audit-2026-07-11.json", "EVIDENCE", "Per-feature closure audit consumed by query surface", True),
    ("docs/governance/feature_surface_closure_audit-2026-07-11.md", "03_feature_evidence/feature_surface_closure_audit-2026-07-11.md", "EVIDENCE", "Human-readable surface audit companion", False),
    ("scripts/governance/feature_surface_query.py", "03_feature_evidence/feature_surface_query.py", "QUERY_SURFACE", "Read-only evidence aggregation — does NOT replace authorities", True),
    ("docs/governance/feature_dag_layers.LATEST.json", "03_feature_evidence/feature_dag_layers.LATEST.json", "POINTER", "Live DAG layer pointer", False),
    ("docs/governance/feature_dag_layers-2026-07-14.json", "03_feature_evidence/feature_dag_layers-2026-07-14.json", "EVIDENCE", "Live 48-node DAG artifact", False),
    ("docs/governance/feature_certification_ledger.jsonl", "03_feature_evidence/feature_certification_ledger.jsonl", "EVIDENCE", "Append-only feature certification ledger", False),
    ("docs/governance/feature_completion_alignment_census-2026-07-14.json", "03_feature_evidence/feature_completion_alignment_census-2026-07-14.json", "EVIDENCE", "M15 completion census (post-identity frontier)", False),
    ("docs/governance/FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md", "03_feature_evidence/FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md", "AUTHORITY", "FC1-A causal swing contract superseding historical LEAKING double_sweep notes", False),
    # 04 CRT runtime
    ("src/config_layer/crt_engine_v2.py", "04_crt_runtime/crt_engine_v2.py", "AUTHORITY", "Primary CRT state machine", True),
    ("src/core/engine_runner.py", "04_crt_runtime/engine_runner.py", "AUTHORITY", "Downstream orchestration", True),
    ("src/features/crt_feature_builder.py", "04_crt_runtime/crt_feature_builder.py", "EVIDENCE", "Secondary/stale builder — classify carefully (not active authority)", True),
    ("active_models.yaml", "04_crt_runtime/active_models.yaml", "AUTHORITY", "Active model registry + state_contracts WHO layer", True),
    ("configs/production/v2_multi_2026_04.json", "04_crt_runtime/v2_multi_2026_04.json", "AUTHORITY", "Active production config", True),
    ("configs/production/ACTIVE_VERSION", "04_crt_runtime/ACTIVE_VERSION", "AUTHORITY", "Tier-0 active version pointer", True),
    ("docs/governance/crt_closure_report.md", "04_crt_runtime/crt_closure_report.md", "AUTHORITY", "CRT CLOSED proof boundary", True),
    ("docs/governance/crt_config_reachability.json", "04_crt_runtime/crt_config_reachability.json", "EVIDENCE", "Config key reachability into CRT", True),
    ("src/config_layer/state_contract.py", "04_crt_runtime/state_contract.py", "AUTHORITY", "Typed state contract runtime types", True),
    ("src/config_layer/state_contract_loader.py", "04_crt_runtime/state_contract_loader.py", "AUTHORITY", "State contract load/validate pipeline", True),
    ("src/config_layer/state_topology.py", "04_crt_runtime/state_topology.py", "AUTHORITY", "Immutable VALID_TRANSITIONS view + topology", True),
    # 05 tests (copied for offline review; report is separate)
    ("tests/test_candle_math.py", "05_tests/test_candle_math.py", "TEST", "Primitive/vectorized parity", True),
    ("tests/test_derived_math.py", "05_tests/test_derived_math.py", "TEST", "Derived-math parity", True),
    ("tests/test_crt_state_invariants.py", "05_tests/test_crt_state_invariants.py", "TEST", "CRT state invariants", True),
    ("tests/test_fc1a_swing_causal.py", "05_tests/test_fc1a_swing_causal.py", "TEST", "Causal swing FC1-A", True),
    ("tests/test_fm_resolution_phase2.py", "05_tests/test_fm_resolution_phase2.py", "TEST", "FM resolver lifecycle", True),
    ("tests/test_feature_lineage.py", "05_tests/test_feature_lineage.py", "TEST", "Feature lineage exhaustiveness", True),
    ("tests/test_feature_surface_query.py", "05_tests/test_feature_surface_query.py", "TEST", "Query surface floors", True),
    ("tests/test_closure_authority_index.py", "05_tests/test_closure_authority_index.py", "TEST", "Closure index shape floors", True),
    ("tests/test_crt_adversarial_closure.py", "05_tests/test_crt_adversarial_closure.py", "TEST", "CRT adversarial/closure suite", True),
    ("tests/test_state_contracts.py", "05_tests/test_state_contracts.py", "TEST", "State contract mechanical checks", True),
    ("tests/test_state_topology_phase.py", "05_tests/test_state_topology_phase.py", "TEST", "Topology parity checks", True),
    ("tests/test_feature_math_lint.py", "05_tests/test_feature_math_lint.py", "TEST", "Feature math ownership lint", False),
]


def write_text(path: Path, content: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return {
        "source_path": None,
        "package_path": str(path.relative_to(PKG)).replace("\\", "/"),
        "required": True,
        "exists": True,
        "status": "GENERATED",
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "authority_class": "DESIGN" if "06_design" in str(path) or "00_manifest" in str(path) else "REPORT",
    }


def extract_crt_baseline() -> dict:
    import yaml
    from config_layer.state_topology import VALID_TRANSITIONS, CRTState

    am = yaml.safe_load((ROOT / "active_models.yaml").read_text(encoding="utf-8"))
    crt = am["crt"]
    runtime = crt["runtime"]
    sc = runtime["state_contracts"]
    vt_yaml = runtime["valid_transitions"]

    # normalize code VALID_TRANSITIONS
    vt_code = {}
    for k, v in dict(VALID_TRANSITIONS).items():
        kk = k.name if hasattr(k, "name") else str(k)
        vt_code[kk] = sorted(x.name if hasattr(x, "name") else str(x) for x in v)

    states = [s.name for s in CRTState]
    # detection / lifecycle / thresholds summaries (descriptive excerpts)
    detection = runtime.get("detection") or {}
    lifecycle = runtime.get("lifecycle") or {}
    thresholds = runtime.get("thresholds") or {}
    cached = runtime.get("cached_features_at_retest") or {}

    # config reachability summary if present
    reach_path = ROOT / "docs/governance/crt_config_reachability.json"
    reach = None
    if reach_path.exists():
        try:
            reach = json.loads(reach_path.read_text(encoding="utf-8"))
        except Exception as e:
            reach = {"error": str(e)}

    # production CRT section keys (names only, not full dump of secrets)
    prod = json.loads((ROOT / "configs/production/v2_multi_2026_04.json").read_text(encoding="utf-8"))
    crt_cfg = prod.get("crt_engine") or prod.get("params") or {}
    # prefer crt_engine section; params often holds CRT knobs too
    params = prod.get("params") or {}

    return {
        "_doc": "Mechanically extracted CRT nine-state baseline for MSIP-1 verification. READ-ONLY extract.",
        "extracted_at": STAMP,
        "sources": [
            "src/config_layer/state_topology.py (VALID_TRANSITIONS / CRTState)",
            "active_models.yaml crt.runtime.state_contracts / valid_transitions",
            "configs/production/v2_multi_2026_04.json (key inventory)",
            "docs/governance/crt_config_reachability.json (if present)",
        ],
        "n_states": len(states),
        "states": states,
        "golden_path": [
            "RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION", "RESOLUTION"
        ],
        "branch_paths": {
            "shadow": ["RANGE", "SHADOW_PENDING", "SWEEP"],
            "ttl_soft_archive": ["EXPANSION", "EXPIRED", "RANGE"],
        },
        "valid_transitions_code": vt_code,
        "valid_transitions_yaml": vt_yaml,
        "transitions_parity_code_vs_yaml": {
            st: {
                "code": sorted(vt_code.get(st, [])),
                "yaml": sorted(vt_yaml.get(st, [])),
                "match": sorted(vt_code.get(st, [])) == sorted(vt_yaml.get(st, [])),
            }
            for st in states
        },
        "state_contracts": sc,
        "detection_excerpt": detection,
        "lifecycle_excerpt": lifecycle,
        "thresholds_excerpt": thresholds,
        "cached_features_at_retest": cached,
        "production_config_section_keys": {
            "crt_engine_keys": sorted(crt_cfg.keys()) if isinstance(crt_cfg, dict) else [],
            "params_sample_crt_related": sorted(
                k for k in params.keys()
                if any(s in k.lower() for s in ("atr", "retest", "sweep", "body", "session", "ttl", "ema", "conf", "disp", "expansion"))
            )[:80] if isinstance(params, dict) else [],
        },
        "crt_config_reachability_present": reach is not None,
        "crt_config_reachability_summary": {
            "top_keys": list(reach.keys())[:30] if isinstance(reach, dict) else None,
        } if reach else None,
        "authority_notes": [
            "CRT CLOSED boundary = OHLCV → TRADE_OPENED only (crt_closure_report.md).",
            "CRT CLOSED does NOT imply EngineRunner admission, DecisionEngine, live SM, or model lineages closed.",
            "Python VALID_TRANSITIONS remains executable transition authority; YAML must parity.",
            "state_contracts required_fm / config_keys / eligible_models are WHO-layer declarations.",
        ],
        "msip_relationship_placeholder": (
            "MSIP proposes an interpretation layer that REUSES CRT state semantics as one consumer/"
            "dimension source — it does NOT reopen CRT CLOSED by existing, and must not mutate "
            "CRT transition authority without a CRT reopen condition."
        ),
    }


def build_design_docs(crt_baseline: dict) -> None:
    design_dir = PKG / "06_design"
    design_dir.mkdir(parents=True, exist_ok=True)

    # OPEN QUESTIONS first (feeds contract)
    open_q = {
        "_doc": "Unresolved MSIP-1 design questions. LLMs must NOT treat these as decided.",
        "generated_at": STAMP,
        "questions": [
            {
                "id": "OQ-001",
                "question": "Is MSIP a pure observation/sidecar layer, or does it eventually replace CRT as the interpretation authority?",
                "status": "OPEN",
                "default_assumption_forbidden": True,
            },
            {
                "id": "OQ-002",
                "question": "Does MarketStateVector include CRT state as a first-class dimension, or only non-CRT dimensions (session, vol regime, structure, liquidity)?",
                "status": "OPEN",
            },
            {
                "id": "OQ-003",
                "question": "Are MSIP dimensions allowed to introduce new formulas, or must they only compose already-certified FM identities?",
                "status": "OPEN_WITH_BIAS",
                "bias": "config-first + ontology-first: prefer compose certified FMs; new formulas require FM registration first",
            },
            {
                "id": "OQ-004",
                "question": "What is the publication cadence — same-bar as FeaturePipeline, event-gated like CRT, or multi-timeframe?",
                "status": "OPEN",
            },
            {
                "id": "OQ-005",
                "question": "Does MSIP bind into EngineRunner / DecisionEngine in phase 1, or remain shadow/telemetry only?",
                "status": "OPEN_WITH_BIAS",
                "bias": "shadow/telemetry first; production binding requires Authority Ladder evidence (ΔG001)",
            },
            {
                "id": "OQ-006",
                "question": "How are known consumer encoding debts (session 0/1/2 vs SESSION_MAP; trend_strength name collision; volatility_regime int8 vs s05 strings) handled before MSIP activation?",
                "status": "OPEN",
                "related_evidence": "docs/governance/feature_completion_alignment_census-2026-07-14.json",
            },
            {
                "id": "OQ-007",
                "question": "Is visual validation (charts/overlays) in-scope for MSIP-1 implementation gate, or deferred?",
                "status": "OPEN",
            },
            {
                "id": "OQ-008",
                "question": "What is the MSIP config section name and ownership relative to crt_engine / engine_runner / fusion?",
                "status": "OPEN",
            },
        ],
    }
    (design_dir / "MSIP-1_OPEN_QUESTIONS.json").write_text(
        json.dumps(open_q, indent=2) + "\n", encoding="utf-8"
    )

    state_dim = {
        "_doc": "Proposed MSIP state-dimension matrix (UNDER VERIFICATION — not implemented).",
        "generated_at": STAMP,
        "vector_name": "MarketStateVector",
        "status": "PROPOSED",
        "dimensions": [
            {
                "dimension_id": "MSD-STRUCTURE",
                "name": "structure_state",
                "semantic": "Swing/structure regime: range vs break vs sweep presence",
                "candidate_features": ["swing_high", "swing_low", "higher_high", "lower_low", "break_of_structure", "liquidity_sweep", "sweep_detected", "double_sweep"],
                "candidate_fm": ["FM-045", "FM-046"],
                "output_type": "categorical_or_int_code",
                "config_semantics": "thresholds for structure significance if any — config-owned",
                "proposed_consumers": ["telemetry", "research", "optional CRT shadow"],
                "depends_on_crt": False,
                "notes": "Must respect FC1-A causal swing publication; do not use historical LEAKING labels from fc05 graph as current truth",
            },
            {
                "dimension_id": "MSD-LIQUIDITY",
                "name": "liquidity_state",
                "semantic": "Distance/pressure relative to structural levels",
                "candidate_features": ["liquidity_distance", "liquidity_pressure_score", "liquidity_sweep"],
                "candidate_fm": ["FM-025", "FM-026"],
                "output_type": "float_and_or_tercile",
                "config_semantics": "optional banding thresholds",
                "proposed_consumers": ["telemetry", "research"],
                "depends_on_crt": False,
                "notes": "FM-025 has UNRESOLVED provenance debt (M6R); FM-026 independently discharged (M7V)",
            },
            {
                "dimension_id": "MSD-VOLATILITY",
                "name": "volatility_state",
                "semantic": "Canonical volatility_regime int8 tercile of absolute ATR14",
                "candidate_features": ["volatility_regime", "atr", "true_range", "volatility_ratio"],
                "candidate_fm": ["FM-041", "FM-040", "FM-024"],
                "output_type": "int8_{0,1,2}",
                "config_semantics": "window/edges currently structural in pipeline; externalization is design decision",
                "proposed_consumers": ["telemetry", "research", "NOT s05 string without adapter"],
                "depends_on_crt": False,
                "notes": "Consumer debt: s05_grid string TRENDING vs int8",
            },
            {
                "dimension_id": "MSD-SESSION",
                "name": "session_state",
                "semantic": "Canonical pipeline session int8 Asia=0/London=1/NY=2",
                "candidate_features": ["session", "hour_of_day"],
                "candidate_fm": [],
                "output_type": "int8_{0,1,2}",
                "config_semantics": "hour boundaries currently pipeline-hardcoded; externalization is design decision",
                "proposed_consumers": ["telemetry", "research", "CRT allowed_sessions only via explicit adapter"],
                "depends_on_crt": False,
                "notes": "Encoding debts vs SESSION_MAP/dashboard/CRT strings — must not silently unify",
            },
            {
                "dimension_id": "MSD-TREND",
                "name": "trend_state",
                "semantic": "Canonical trend_strength nested rolling + optional trend_bias sign",
                "candidate_features": ["trend_strength", "trend_bias", "ema_fast", "ema_slow"],
                "candidate_fm": ["FM-043", "FM-044"],
                "output_type": "signed_float_plus_sign",
                "config_semantics": "windows currently structural",
                "proposed_consumers": ["telemetry", "research"],
                "depends_on_crt": False,
                "notes": "NAME COLLISION: dual_engine local trend_strength = abs(ema_spread) — different quantity",
            },
            {
                "dimension_id": "MSD-CRT_PHASE",
                "name": "crt_phase",
                "semantic": "Optional CRTState projection into MarketStateVector",
                "candidate_features": [],
                "candidate_fm": ["FM-010", "FM-027", "FM-028"],
                "output_type": "enum_9_states",
                "config_semantics": "owned by crt_engine / active_models state_contracts — MSIP MUST NOT fork",
                "proposed_consumers": ["telemetry", "research", "shadow co-display"],
                "depends_on_crt": True,
                "notes": "OQ-002 unresolved; if included, MSIP is a reader of CRT, not a second SM",
            },
            {
                "dimension_id": "MSD-SETUP_QUALITY",
                "name": "setup_quality",
                "semantic": "Optional composite of body_ratio / retest_depth / disp metrics at event bars",
                "candidate_features": ["body_ratio", "retest_depth", "disp_strength", "displacement_retrace", "displacement_atr_ratio"],
                "candidate_fm": ["FM-010", "FM-021", "FM-020", "FM-027", "FM-028"],
                "output_type": "float_or_tier",
                "config_semantics": "weights/thresholds config-owned if introduced",
                "proposed_consumers": ["research", "shadow only until Authority Ladder"],
                "depends_on_crt": "partial",
                "notes": "FM-021 is gated composition; FM-027 is CRT-cache identity — do not collapse names",
            },
        ],
        "non_dimensions": [
            "Economic expectancy / PnL",
            "Order placement authority",
            "Model training labels without re-derive",
        ],
    }
    (design_dir / "MSIP-1_STATE_DIMENSION_MATRIX.json").write_text(
        json.dumps(state_dim, indent=2) + "\n", encoding="utf-8"
    )

    (design_dir / "MSIP-1_CRT_STATE_BASELINE.json").write_text(
        json.dumps(crt_baseline, indent=2) + "\n", encoding="utf-8"
    )

    config_own = {
        "_doc": "Proposed MSIP config ownership matrix (UNDER VERIFICATION).",
        "generated_at": STAMP,
        "doctrine": "Config-first: BEHAVIORAL knobs externalized via strict _require / from_prod_config; STRUCTURAL frozen in code",
        "parameters": [
            {
                "param": "msip.enabled",
                "current_owner": "NONE (not implemented)",
                "proposed_owner": "configs/production/*.json top-level section msip",
                "class": "BEHAVIORAL",
                "default_policy": "fail-closed if section present but incomplete; absent section = feature off",
            },
            {
                "param": "msip.dimensions.*.enabled",
                "current_owner": "NONE",
                "proposed_owner": "msip section",
                "class": "BEHAVIORAL",
            },
            {
                "param": "msip.session.encoding",
                "current_owner": "FeaturePipeline hardcoded piecewise hours",
                "proposed_owner": "UNDECIDED (OQ-006) — do not silently change pipeline identity",
                "class": "STRUCTURAL_OR_BEHAVIORAL",
            },
            {
                "param": "msip.volatility_regime.*",
                "current_owner": "FeaturePipeline (window 200, edges 0.33/0.66)",
                "proposed_owner": "UNDECIDED — currently structural in pipeline",
                "class": "STRUCTURAL_TODAY",
            },
            {
                "param": "crt_engine.* thresholds",
                "current_owner": "configs/production + CRTConfig / active_models state_contracts",
                "proposed_owner": "REMAINS crt_engine — MSIP must not duplicate",
                "class": "EXISTING_AUTHORITY",
            },
            {
                "param": "msip.shadow_only",
                "current_owner": "NONE",
                "proposed_owner": "msip section",
                "class": "BEHAVIORAL",
                "bias": "true until Authority Ladder promotion",
            },
            {
                "param": "msip.consumer_adapters.session_map",
                "current_owner": "NONE",
                "proposed_owner": "msip.adapters or separate encoding registry",
                "class": "BEHAVIORAL",
                "purpose": "map foreign encodings without mutating canonical session",
            },
        ],
    }
    (design_dir / "MSIP-1_CONFIG_OWNERSHIP_MATRIX.json").write_text(
        json.dumps(config_own, indent=2) + "\n", encoding="utf-8"
    )

    consumer_impact = {
        "_doc": "MSIP consumer impact matrix (UNDER VERIFICATION — proposed).",
        "generated_at": STAMP,
        "consumers": [
            {
                "consumer": "CRTEngine (crt_engine_v2)",
                "impact": "NONE in phase-1 if MSIP is sidecar; READ-ONLY if MSD-CRT_PHASE included",
                "mutation_surface": "none (forbidden without CRT reopen)",
                "risk": "name collision if MSIP redefines CRT semantics",
            },
            {
                "consumer": "EngineRunner",
                "impact": "NONE until explicit wire; must not auto-bind",
                "mutation_surface": "future optional consume MarketStateVector",
                "risk": "premature authority without ΔG001",
            },
            {
                "consumer": "FeaturePipeline",
                "impact": "READ — MSIP consumes pipeline outputs; should not re-implement math",
                "mutation_surface": "none preferred",
                "risk": "duplicate formula math (forbidden by construction protocol)",
            },
            {
                "consumer": "Models (Gaussian/BitNet/TradeNet/RR)",
                "impact": "NONE — feature-surface CLOSED does not authorize model reuse",
                "mutation_surface": "none in MSIP-1",
                "risk": "false authorization from closure confusion",
            },
            {
                "consumer": "Backtest / live",
                "impact": "shadow telemetry only unless approved",
                "mutation_surface": "optional journal fields",
                "risk": "lookahead if multi-TF dimensions introduced carelessly",
            },
            {
                "consumer": "Research / interpreters",
                "impact": "PRIMARY early consumer of MarketStateVector",
                "mutation_surface": "research packages only",
                "risk": "overclaiming economic edge from descriptive states",
            },
            {
                "consumer": "Telemetry / dashboard",
                "impact": "visual validation surface (OQ-007)",
                "mutation_surface": "UI labels — must use canonical encodings",
                "risk": "session label permutation debt",
            },
            {
                "consumer": "crt_feature_builder",
                "impact": "NONE — stale secondary surface; do not treat as MSIP authority",
                "mutation_surface": "none",
                "risk": "mistaken for active producer",
            },
        ],
    }
    (design_dir / "MSIP-1_CONSUMER_IMPACT_MATRIX.json").write_text(
        json.dumps(consumer_impact, indent=2) + "\n", encoding="utf-8"
    )

    contract = textwrap.dedent(
        f"""\
        # MSIP-1 Design Contract — Market-State Interpretation Program

        **Status:** PROPOSED UNDER VERIFICATION (not implemented; not authorized)  
        **Package generated:** {STAMP}  
        **Repository commit (at package build):** see `00_manifest/MSIP-1_SOURCE_MANIFEST.json`  
        **Authority:** research/governance design under multi-LLM verification only  
        **Does NOT grant:** production wiring, model enablement, economic claims, CRT reopen, feature formula changes

        ---

        ## 0. Purpose of this document

        This contract freezes the **proposed** MSIP-1 design for independent verification. Verifiers must answer:

        1. What is the proposed design?
        2. What does the repository actually do?
        3. Where do they contradict?
        4. Is there enough evidence to declare the design verified and ready for implementation?

        Evidence labels for every material claim:

        | Label | Meaning |
        |---|---|
        | `PROVEN_BY_EXECUTABLE_EVIDENCE` | Demonstrated by code + tests |
        | `PROVEN_BY_AUTHORITATIVE_ARTIFACT` | Demonstrated by named authority doc/config |
        | `CONTRADICTED` | Design conflicts with executable or authority |
        | `UNKNOWN` | Insufficient evidence in package |
        | `DESIGN_DECISION_REQUIRED` | Open question; not silently fillable |

        **Do not majority-vote.** Five LLMs agreeing on a false claim remains false.

        ---

        ## 1. Problem statement

        The repository already has:

        - a **feature math surface** (ontology → registry → pipeline/derived_math/candle_math) with identity certification progress and a CLOSED **canonical feature code surface** boundary;
        - a **CRT interpretation state machine** (9 states) that is **CLOSED** for OHLCV → `TRADE_OPENED`;
        - multiple **consumers** (EngineRunner, models, backtest, research, dashboards) with known encoding/name collisions.

        Missing is a **governed, config-first interpretation layer** that composes certified market features into a stable **MarketStateVector** for observation/research/shadow use **without**:

        - re-deriving feature math locally,
        - forking CRT transitions,
        - claiming model or economic authority from upstream closure.

        MSIP-1 is that proposed layer.

        ---

        ## 2. Proposed architecture

        ```text
        OHLCV
          → FeaturePipeline / candle_math / derived_math   (FEATURE AUTHORITY — existing)
          → (optional) CRTEngine state machine             (CRT AUTHORITY — existing, CLOSED)
          → MarketStateInterpreter (NEW, proposed)         (MSIP — compose, not invent math)
                → MarketStateVector
                → shadow telemetry / research consumers
                → (FUTURE, gated) production consumers
        ```

        ### 2.1 MarketStateVector

        A structured, versioned interpretation object with named dimensions (see
        `MSIP-1_STATE_DIMENSION_MATRIX.json`):

        - `structure_state`
        - `liquidity_state`
        - `volatility_state`
        - `session_state`
        - `trend_state`
        - optional `crt_phase` (OQ-002)
        - optional `setup_quality` (event-gated composite)

        Each dimension must declare:

        - candidate features / FM IDs
        - output type + domain
        - config ownership
        - consumers
        - PIT / publication semantics
        - whether it depends on CRT

        ### 2.2 Config boundaries

        - New section: `msip` in production config (proposed).
        - Strict load (`_require` / `from_prod_config`); no silent defaults for new knobs.
        - CRT thresholds remain under `crt_engine` / `params` / `active_models` state_contracts.
        - MSIP must not duplicate CRT knobs under new names.

        See `MSIP-1_CONFIG_OWNERSHIP_MATRIX.json`.

        ### 2.3 CRT relationship

        | Rule | Statement |
        |---|---|
        | R1 | CRT CLOSED remains authoritative for CRT transitions |
        | R2 | MSIP may **read** CRT state as a dimension only if OQ-002 decides yes |
        | R3 | MSIP must not implement a second state machine that redefines CRT edges |
        | R4 | MSIP existence does **not** reopen CRT; CRT reopen conditions stay as in `closure_authority_index.json` |
        | R5 | CH-002 emission names (`displacement_retrace`, `displacement_atr_ratio`) are CRT cache identities — MSIP must use those names for CRT-side quantities |

        Baseline extract: `MSIP-1_CRT_STATE_BASELINE.json` (9 states, transitions, state_contracts).

        ### 2.4 Feature relationship

        | Rule | Statement |
        |---|---|
        | F1 | Feature math remains ontology/registry/pipeline authority |
        | F2 | MSIP composes features; does not re-implement FM math |
        | F3 | `CANONICAL_FEATURE_CODE_SURFACE CLOSED` ≠ MSIP closed ≠ model authorization |
        | F4 | Feature Query Surface is a **join tool**, not an authority that replaces lineage/closure artifacts |
        | F5 | Historical fc05 dependency graph may mark structure features LEAKING; **FC1-A** is current production causal contract — freshness rules apply |

        ### 2.5 Visual validation (proposed gate, OQ-007)

        If in-scope, visual validation means:

        - overlays of MarketStateVector dimensions vs price
        - encoding legends that match canonical codes (session 0/1/2, vol regime 0/1/2)
        - no dashboard-only remapping without an adapter layer

        ---

        ## 3. Invariants (must hold if implemented)

        1. **No local formula math** — new quantities registered first (construction protocol).
        2. **Non-transitive closure** — CRT CLOSED / feature-code CLOSED do not authorize MSIP production authority.
        3. **Config-first behavioral knobs** — no magic numbers in new MSIP code paths.
        4. **PIT / no lookahead** — any multi-bar dimension must be prefix-invariant.
        5. **Single encoding authority per dimension** — foreign encodings require explicit adapters.
        6. **Shadow-first** — production consumers off until Authority Ladder evidence.
        7. **Identity preservation** — FM-021 split identity, FM-027 role grounding, M14B vol regime deps, session pipeline identity remain.
        8. **Logging** — SESSION LOG + no silent truth divergence.

        ---

        ## 4. Non-goals (MSIP-1)

        - Economic edge discovery or promotion
        - Retrain / re-enable Gaussian, BitNet, TradeNet, rr_fusion
        - Replacing CRT as trade lifecycle authority
        - Expanding the 38-dim vector without a migration program
        - Resolving all M15 completion debts inside MSIP-1 (session encoding may be a **dependency**, not a free gift)
        - Using backtest PnL as MSIP verification evidence

        ---

        ## 5. Gates before implementation

        | Gate | Requirement |
        |---|---|
        | G0 | Multi-LLM verification package complete + identical across reviewers |
        | G1 | No CONTRADICTED material design claims unresolved |
        | G2 | All DESIGN_DECISION_REQUIRED items either decided by user or deferred with stop boundary |
        | G3 | CRT baseline parity (code VALID_TRANSITIONS ↔ YAML) holds |
        | G4 | Mechanical test subset green (see test report) |
        | G5 | Construction protocol classification ready for first implementation slice |

        ---

        ## 6. Stop conditions

        Stop and re-scope if:

        - verification finds MSIP requires reopening CRT CLOSED without a valid reopen condition;
        - design requires ungoverned formula math;
        - design assumes feature-surface or query-surface closure authorizes model use;
        - consumer encoding collisions are ignored while claiming activation readiness;
        - LLMs disagree on material executable facts that repository recheck cannot resolve.

        ---

        ## 7. What the repository actually does today (summary for verifiers)

        **Proven by package evidence (verifiers must re-check):**

        - Feature production: `feature_pipeline.py` (+ candle_math/derived_math) builds the 38-dim vector and structural series.
        - CRT: `crt_engine_v2.py` runs 9-state SM; closed for OHLCV→TRADE_OPENED (`crt_closure_report.md`).
        - Orchestration: `engine_runner.py` fuses engines; research spine may run CRT-only (F-037 class).
        - `crt_feature_builder.py` is a secondary surface — package includes it so verifiers do not confuse it with pipeline authority.
        - Closures are boundary-scoped (`closure_authority_index.json`).

        **Not present today:**

        - No `MarketStateVector` type or `msip` config section (as of package build).
        - No MSIP interpreter module under `src/`.

        ---

        ## 8. Known friction (pre-registered)

        From M15 completion census and certification artifacts:

        - session encoding multi-surface mismatch
        - trend_strength name collision with dual_engine
        - volatility_regime int8 vs s05 strings
        - FM-025 provenance unresolved (does not auto-taint FM-026)
        - SUPERSEDED ema_spread/momentum_score still in 38-vector; successors unbound

        These are **not automatically MSIP blockers**, but activation claims that ignore them are invalid.

        ---

        ## 9. Success criteria for verification verdict

        | Verdict | When |
        |---|---|
        | **MSIP-1 VERIFIED** | Design coherent with executable reality; no material CONTRADICTED claims; open questions either decided or explicitly non-blocking; ready for construction-protocol implementation planning |
        | **MSIP-1 VERIFIED WITH BLOCKERS** | Design direction sound but listed blockers must clear before implementation |
        | **MSIP-1 REJECTED** | Material contradictions with repository authority/executable behavior, or design violates non-transitive closure / construction protocol |

        ---

        ## 10. Package map

        | Dir | Content |
        |---|---|
        | `00_manifest/` | Contract, prompt, source manifest, freshness rules |
        | `01_governance/` | CLAUDE.md, assistant_project.md, closure index |
        | `02_feature_authority/` | Ontology, schema, math, pipeline, FM resolve |
        | `03_feature_evidence/` | Identity/deps/consumers/lineage/closure/query surface |
        | `04_crt_runtime/` | CRT engine, runner, models, config, state contracts, CRT closure |
        | `05_tests/` | Mechanical tests + execution report |
        | `06_design/` | This contract + matrices + CRT baseline extract |
        | `07_llm_responses/` | Empty; store each LLM response verbatim |

        ---

        ## 11. Explicit non-claims

        - This contract is **not** a finding in `docs/current-findings.md`.
        - This contract is **not** a closure of MSIP.
        - Packaging is **not** implementation.
        """
    )
    (design_dir / "MSIP-1_DESIGN_CONTRACT.md").write_text(contract, encoding="utf-8")

    # Also copy design contract into 00_manifest as required by table
    shutil.copy2(design_dir / "MSIP-1_DESIGN_CONTRACT.md", PKG / "00_manifest" / "MSIP-1_DESIGN_CONTRACT.md")


def build_verification_prompt() -> str:
    return textwrap.dedent(
        f"""\
        # MSIP-1 Verification Prompt (IDENTICAL for every LLM)

        **Generated:** {STAMP}  
        **Role:** Independent verifier. You receive only the frozen `msip_1_verification_package/`.  
        **You do not have the full repository.** Do not invent files outside the package.

        ---

        ## Mission

        Verify the proposed Market-State Interpretation Program (MSIP-1) against repository evidence in this package.

        Answer exactly these four questions:

        1. **What is the proposed design?**
        2. **What does the repository actually do?**
        3. **Where do they contradict?**
        4. **Is there enough evidence to declare the design verified and ready for implementation?**

        Final verdict must be one of:

        - `MSIP-1 VERIFIED`
        - `MSIP-1 VERIFIED WITH BLOCKERS`
        - `MSIP-1 REJECTED`

        ---

        ## Hard rules

        1. **No majority voting.** Even if you know other models might agree, each claim needs evidence labels.
        2. Every material claim must be labeled:
           - `PROVEN_BY_EXECUTABLE_EVIDENCE`
           - `PROVEN_BY_AUTHORITATIVE_ARTIFACT`
           - `CONTRADICTED`
           - `UNKNOWN`
           - `DESIGN_DECISION_REQUIRED`
        3. **Non-transitive closure:**  
           - CRT CLOSED ≠ EngineRunner / DecisionEngine / live SM closed  
           - CANONICAL_FEATURE_CODE_SURFACE CLOSED ≠ model reuse authorized  
           - Feature Query Surface AUTHORITY_ACTIVE ≠ producer/consumer/model closed  
           Read `01_governance/closure_authority_index.json`.
        4. **Freshness / supersession:**  
           Read `00_manifest/AUTHORITY_FRESHNESS.md` before trusting historical fc05 graphs or contracts.  
           When historical and later artifacts conflict, the later authority wins **only if** the freshness doc says so.
        5. **feature_surface_query.py** is a join tool. Prefer underlying authoritative artifacts for conclusions.
        6. **crt_feature_builder.py** is included to be classified — do not assume it is active production authority.
        7. Do not use economic/backtest PnL as MSIP verification evidence.
        8. Open questions in `06_design/MSIP-1_OPEN_QUESTIONS.json` are **not decided**. Label any use of them `DESIGN_DECISION_REQUIRED`.
        9. Do not propose production code changes in the verification response (recommendations only).

        ---

        ## Required reading order

        1. `00_manifest/MSIP-1_SOURCE_MANIFEST.json` (integrity)
        2. `00_manifest/AUTHORITY_FRESHNESS.md`
        3. `00_manifest/MSIP-1_DESIGN_CONTRACT.md` and `06_design/*`
        4. `01_governance/closure_authority_index.json` + `CLAUDE.md` (doctrine sections)
        5. Feature authority (`02_feature_authority/`)
        6. Feature evidence (`03_feature_evidence/`) — note historical vs current
        7. CRT runtime (`04_crt_runtime/`) + CRT baseline extract
        8. Tests + `05_tests/TEST_EXECUTION_REPORT.json`

        ---

        ## Required output format

        ```markdown
        # MSIP-1 Verification — <MODEL_NAME>

        ## 1. Proposed design (summary)
        ...

        ## 2. Repository actual behavior (summary)
        ...

        ## 3. Contradictions and frictions
        | ID | Design claim | Repo evidence | Label | Notes |
        |---|---|---|---|---|

        ## 4. Claim matrix (material)
        | Claim | Label | Evidence paths |
        |---|---|---|

        ## 5. Open questions used / remaining
        ...

        ## 6. Blockers (if any)
        ...

        ## 7. Verdict
        MSIP-1 VERIFIED | MSIP-1 VERIFIED WITH BLOCKERS | MSIP-1 REJECTED

        ## 8. Confidence and unknowns
        ...
        ```

        Store your full response unchanged under:

        `07_llm_responses/<MODEL_NAME>_<UTC_DATE>.md`

        ---

        ## Integrity check before you start

        Confirm you can see:

        - design contract
        - source manifest with SHA256 list
        - feature_schema.py
        - feature_38_lineage_census-2026-07-11.json (not only LATEST pointer)
        - canonical_feature_code_surface_closure-2026-07-11.md
        - feature_surface_closure_audit-2026-07-11.json
        - crt_closure_report.md
        - crt_config_reachability.json
        - state_contract*.py / state_topology.py / active_models.yaml
        - test execution report

        If any required file is missing, verdict = `MSIP-1 REJECTED` with reason `INCOMPLETE_PACKAGE`.
        """
    )


def build_freshness_doc() -> str:
    return textwrap.dedent(
        f"""\
        # Authority & Freshness Rules (MSIP-1 package)

        **Generated:** {STAMP}

        Independent verifiers **must** apply these rules. Historical evidence remains in the package
        for lineage, but must not override fresher authorities.

        ## Precedence (high → low) within this package

        1. **Executable production code** in `02_feature_authority/` and `04_crt_runtime/`
        2. **Active config / WHO registry:** `ACTIVE_VERSION`, `v2_multi_2026_04.json`, `active_models.yaml`
        3. **Closure authorities:** `closure_authority_index.json` → named authoritative artifacts
        4. **Dated governance evidence 2026-07-11+** (lineage census body, feature-code closure, surface audit, FC1-A)
        5. **Certification ledger / DAG layers / M15 census** (descriptive; grants no production authority)
        6. **Historical 2026-07-10 fc05 / phase1 / feature_contract_v1** — useful history; **superseded where noted**
        7. **feature_surface_query.py** — join/aggregation only
        8. **MSIP design docs** — proposed; not repository truth until verified + implemented

        ## Explicit supersessions

        | Topic | Stale risk | Current authority in package |
        |---|---|---|
        | Swing / structure PIT | fc05 dependency graph may say LEAKING / inherited lookahead for double_sweep family | FC1-A contract + `causal_structure.py` + `feature_pipeline.py` causal publication + `test_fc1a_swing_causal.py` |
        | CRT emission names retest/disp | pre-CH-002 cache keys `retest_depth`/`disp_strength` confusion | `crt_closure_report.md` CH-002 + crt_engine_v2 emission of `displacement_retrace` / `displacement_atr_ratio` |
        | Feature contract v1 | may predate later separations | Use identity registry + ontology + pipeline; contract is HISTORICAL |
        | Consumer manifest 2026-07-10 | may lag M9–M15 certifications | Prefer later certification notes / M15 census for known encoding debts |
        | LATEST pointers | always resolve to dated body + verify sha256 | `feature_38_lineage_census-2026-07-11.json`, `feature_dag_layers-2026-07-14.json` |

        ## Non-transitive closure (mandatory)

        From `closure_authority_index.json`:

        - CRT CLOSED does **not** close Gaussian/ZoneGate/RR/BitNet/TradeNet or Feature Query Surface.
        - CANONICAL_FEATURE_CODE_SURFACE CLOSED does **not** authorize model enablement or economic claims.
        - Feature Query Surface AUTHORITY_ACTIVE does **not** close producers/consumers/models.

        MSIP must not be declared CLOSED by inheritance from any of the above.

        ## Economic evidence ban

        Backtest PnL, expectancy, and strategy performance are **out of scope** for MSIP-1 verification.
        """
    )


def run_tests() -> dict:
    """Run mechanical test subset; return structured report."""
    test_files = [
        "tests/test_candle_math.py",
        "tests/test_derived_math.py",
        "tests/test_crt_state_invariants.py",
        "tests/test_fc1a_swing_causal.py",
        "tests/test_fm_resolution_phase2.py",
        "tests/test_feature_lineage.py",
        "tests/test_feature_surface_query.py",
        "tests/test_closure_authority_index.py",
        "tests/test_crt_adversarial_closure.py",
        "tests/test_state_contracts.py",
        "tests/test_state_topology_phase.py",
    ]
    # filter to existing
    existing = [t for t in test_files if (ROOT / t).exists()]
    missing = [t for t in test_files if not (ROOT / t).exists()]

    cmd = [
        PY, "-m", "pytest",
        *existing,
        "-q", "--tb=no",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    started = datetime.now(timezone.utc).isoformat()
    try:
        r = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=600,
        )
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        code = r.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + "\n" + (e.stderr or "") + "\nTIMEOUT"
        code = -1
    ended = datetime.now(timezone.utc).isoformat()

    # parse pytest short summary
    passed = failed = skipped = errors = None
    import re
    m = re.search(r"(\d+) passed", out)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) skipped", out)
    if m:
        skipped = int(m.group(1))
    m = re.search(r"(\d+) error", out)
    if m:
        errors = int(m.group(1))

    report = {
        "_doc": "MSIP-1 mechanical test execution report",
        "started_at": started,
        "ended_at": ended,
        "commit_sha": git_commit(),
        "branch": git_branch(),
        "python": sys.version,
        "command": cmd,
        "exit_code": code,
        "tests_requested": test_files,
        "tests_existing": existing,
        "tests_missing": missing,
        "counts": {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
        },
        "stdout_stderr_tail": out[-12000:],
        "full_output_path": "05_tests/TEST_EXECUTION_OUTPUT.txt",
    }
    return report, out


def main() -> int:
    print(f"Building MSIP-1 verification package → {PKG}")
    if PKG.exists():
        shutil.rmtree(PKG)
    for d in DIRS:
        (PKG / d).mkdir(parents=True, exist_ok=True)
    (PKG / "07_llm_responses" / "README.md").write_text(
        "# LLM responses\n\nStore each model's verbatim verification response here.\n"
        "Do not edit responses after receipt.\n",
        encoding="utf-8",
    )

    commit = git_commit()
    branch = git_branch()
    records: list[dict] = []

    # copy planned files
    for src_rel, dest_rel, auth, purpose, required in FILE_PLAN:
        rec = copy_file(src_rel, PKG / dest_rel, required=required)
        rec["authority_class"] = auth
        rec["purpose"] = purpose
        records.append(rec)
        status = rec["status"]
        print(f"  [{status}] {src_rel}")

    # extract CRT baseline + design docs
    print("Extracting CRT baseline…")
    crt_baseline = extract_crt_baseline()
    print("Writing design docs…")
    build_design_docs(crt_baseline)

    # freshness + prompt
    write_text(PKG / "00_manifest" / "AUTHORITY_FRESHNESS.md", build_freshness_doc())
    write_text(PKG / "00_manifest" / "MSIP-1_VERIFICATION_PROMPT.md", build_verification_prompt())

    # register generated design files into records
    for p in sorted((PKG / "06_design").rglob("*")):
        if p.is_file():
            records.append({
                "source_path": None,
                "package_path": str(p.relative_to(PKG)).replace("\\", "/"),
                "required": True,
                "exists": True,
                "status": "GENERATED",
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "authority_class": "DESIGN",
                "purpose": "MSIP-1 design / extract artifact",
            })
    # design contract also in 00_manifest
    p = PKG / "00_manifest" / "MSIP-1_DESIGN_CONTRACT.md"
    if p.exists():
        records.append({
            "source_path": None,
            "package_path": "00_manifest/MSIP-1_DESIGN_CONTRACT.md",
            "required": True,
            "exists": True,
            "status": "GENERATED",
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
            "authority_class": "DESIGN",
            "purpose": "Design contract copy for manifest group 00",
        })
    for name in ("AUTHORITY_FRESHNESS.md", "MSIP-1_VERIFICATION_PROMPT.md"):
        p = PKG / "00_manifest" / name
        records.append({
            "source_path": None,
            "package_path": f"00_manifest/{name}",
            "required": True,
            "exists": True,
            "status": "GENERATED",
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
            "authority_class": "DESIGN",
            "purpose": name,
        })

    # run tests
    print("Running mechanical test subset…")
    report, raw_out = run_tests()
    out_txt = PKG / "05_tests" / "TEST_EXECUTION_OUTPUT.txt"
    out_txt.write_text(raw_out, encoding="utf-8")
    report_path = PKG / "05_tests" / "TEST_EXECUTION_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for p, purpose in (
        (out_txt, "Raw pytest output"),
        (report_path, "Structured test execution report"),
    ):
        records.append({
            "source_path": None,
            "package_path": str(p.relative_to(PKG)).replace("\\", "/"),
            "required": True,
            "exists": True,
            "status": "GENERATED",
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
            "authority_class": "REPORT",
            "purpose": purpose,
        })
    print(f"  tests exit={report['exit_code']} counts={report['counts']}")

    # README
    readme = textwrap.dedent(
        f"""\
        # MSIP-1 Verification Package

        Frozen multi-LLM verification corpus for the Market-State Interpretation Program.

        - **Generated:** {STAMP}
        - **Git commit:** `{commit}`
        - **Branch:** `{branch}`
        - **Production code mutated by packaging:** NO

        ## Start here

        1. Read `00_manifest/MSIP-1_VERIFICATION_PROMPT.md`
        2. Read `00_manifest/AUTHORITY_FRESHNESS.md`
        3. Read `00_manifest/MSIP-1_DESIGN_CONTRACT.md`
        4. Verify file hashes in `00_manifest/MSIP-1_SOURCE_MANIFEST.json`

        ## Verdict storage

        Place each LLM response under `07_llm_responses/` without editing.

        Final adjudication (ChatGPT or human) builds a cross-LLM claim matrix and
        rechecks material disputes against this package only.
        """
    )
    write_text(PKG / "README.md", readme)
    records.append({
        "source_path": None,
        "package_path": "README.md",
        "required": True,
        "exists": True,
        "status": "GENERATED",
        "sha256": sha256_file(PKG / "README.md"),
        "bytes": (PKG / "README.md").stat().st_size,
        "authority_class": "DESIGN",
        "purpose": "Package entrypoint",
    })

    missing_required = [r for r in records if r.get("required") and r.get("status") == "MISSING"]
    manifest = {
        "_doc": "MSIP-1 source package manifest — identical evidence set for every LLM",
        "schema_version": "1.0",
        "generated_at": STAMP,
        "repository_commit_sha": commit,
        "repository_branch": branch,
        "package_root": "msip_1_verification_package",
        "production_code_mutated": False,
        "file_count": len(records),
        "missing_required_count": len(missing_required),
        "missing_required": missing_required,
        "test_execution": {
            "exit_code": report["exit_code"],
            "counts": report["counts"],
            "report_path": "05_tests/TEST_EXECUTION_REPORT.json",
        },
        "authority_classes": sorted({r.get("authority_class") for r in records if r.get("authority_class")}),
        "files": sorted(records, key=lambda x: x.get("package_path") or ""),
        "integrity_note": "Each LLM must receive this entire package unchanged. Compare SHA256 of every file to this manifest.",
    }
    # write manifest last (exclude self from list — add after)
    man_path = PKG / "00_manifest" / "MSIP-1_SOURCE_MANIFEST.json"
    # compute package aggregate hash over all files currently present except empty dir placeholders
    file_hashes = []
    for f in sorted(PKG.rglob("*")):
        if f.is_file() and f.name != "MSIP-1_SOURCE_MANIFEST.json":
            rel = str(f.relative_to(PKG)).replace("\\", "/")
            file_hashes.append(f"{sha256_file(f)}  {rel}")
    agg = hashlib.sha256("\n".join(file_hashes).encode("utf-8")).hexdigest()
    manifest["package_aggregate_sha256"] = agg
    manifest["package_file_hash_list_count"] = len(file_hashes)
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # also write a simple SHA256SUMS
    sums_path = PKG / "00_manifest" / "SHA256SUMS.txt"
    # include manifest itself
    lines = file_hashes + [f"{sha256_file(man_path)}  00_manifest/MSIP-1_SOURCE_MANIFEST.json"]
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 72)
    print("MSIP-1 VERIFICATION PACKAGE COMPLETE")
    print(f"  path: {PKG}")
    print(f"  commit: {commit}")
    print(f"  files recorded: {len(records)}")
    print(f"  missing required: {len(missing_required)}")
    print(f"  aggregate_sha256: {agg}")
    print(f"  tests: {report['counts']} exit={report['exit_code']}")
    if missing_required:
        print("MISSING REQUIRED:")
        for m in missing_required:
            print(" ", m)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
