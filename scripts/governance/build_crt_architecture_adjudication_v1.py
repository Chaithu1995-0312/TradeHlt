"""
CRT Architecture Adjudication V1 package builder.

TASK_CLASS = OBSERVATION_ONLY
No production CRT/behavior change. Reads existing evidence + emits decision package.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

PKG = ROOT / "docs" / "governance" / "crt_architecture_adjudication_v1"
STAMP = datetime.now(timezone.utc).isoformat()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(rel: str):
    p = ROOT / rel
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write(rel_name: str, content: str | dict) -> Path:
    PKG.mkdir(parents=True, exist_ok=True)
    p = PKG / rel_name
    if isinstance(content, dict):
        p.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    else:
        p.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return p


def main() -> int:
    from config_layer.state_topology import VALID_TRANSITIONS, CRTState
    from features.feature_schema import CANONICAL_FEATURES, SCHEMA_HASH, FEATURE_ORDER_HASH

    vt = {
        (k.name if hasattr(k, "name") else str(k)): sorted(
            x.name if hasattr(x, "name") else str(x) for x in v
        )
        for k, v in dict(VALID_TRANSITIONS).items()
    }
    states = [s.name for s in CRTState]

    funnel = load_json("docs/governance/crt_xauusd_funnel_diagnostic-2026-07-14.json") or {}
    fail = load_json("docs/governance/crt_fail_reason_diagnostic-2026-07-14.json") or {}
    auth_in = load_json("docs/governance/CRT_INPUT_AUTHORITY_MATRIX_V1.json") or {}
    cov = load_json("docs/governance/CRT_TRANSITION_COVERAGE_MATRIX_V1.json") or {}
    freeze = load_json(
        "docs/governance/xauusd_crt_baseline_trace/XAUUSD_CRT_BASELINE_TRACE_V1_FREEZE.json"
    ) or {}
    closure = load_json("docs/governance/closure_authority_index.json") or {}
    state_graph = load_json("docs/governance/crt_executable_state_graph.json") or {}

    # ── 9-state graph with evidence ──
    edges_measured = {
        "RANGE->SWEEP": 3390,
        "RANGE->SHADOW_PENDING": 43,
        "SHADOW_PENDING->SWEEP": 43,
        "SWEEP->DISPLACEMENT": 315,
        "SWEEP->EXPANSION": 43,  # shadow resume
        "DISPLACEMENT->EXPANSION": 17,
        "EXPANSION->RETEST": 17,
        "RETEST->EXECUTION": 5,
        "EXECUTION->RESOLUTION": 1,
        "RESOLUTION->RANGE": 1,  # post-resolution reset path
        "EXPANSION->EXPIRED": 0,  # measured 0 TTL
        "EXPIRED->RANGE": 0,
    }

    edge_records = []
    edge_meta = {
        ("RANGE", "SWEEP"): {
            "guard": "detect_sweep then try_range_to_sweep",
            "market_inputs": ["high", "low", "close", "h_ref", "l_ref"],
            "state_memory": ["active_range", "sweep_event"],
            "config": [],
            "event": "SWEEP / SWEEP_DETECTED",
        },
        ("RANGE", "SHADOW_PENDING"): {
            "guard": "sweep matches pending_displacement_dir",
            "market_inputs": ["high", "low", "close"],
            "state_memory": ["pending_displacement_*", "sweep_event"],
            "config": ["pending_displacement_ttl_candles"],
            "event": "SHADOW_SWEEP_DETECTED",
        },
        ("SHADOW_PENDING", "SWEEP"): {
            "guard": "try_shadow_pending_to_expansion hop1",
            "market_inputs": [],
            "state_memory": ["pending_displacement_candle"],
            "config": [],
            "event": "STATE_TRANSITION (governed double hop)",
        },
        ("SWEEP", "DISPLACEMENT"): {
            "guard": "try_sweep_to_displacement (move/body/wick/age)",
            "market_inputs": ["open", "close", "body_ratio", "wick_size", "atr"],
            "state_memory": ["sweep_event", "atr"],
            "config": [
                "atr_min_displacement",
                "body_ratio_min",
                "atr_multiplier_min",
                "max_sweep_age_candles",
            ],
            "event": "DISPLACEMENT_CONFIRMED",
        },
        ("SWEEP", "EXPANSION"): {
            "guard": "shadow resume hop2 (skips disp strength)",
            "market_inputs": [],
            "state_memory": ["pending_displacement_candle"],
            "config": [],
            "event": "SHADOW_EXPANSION_CONFIRMED",
        },
        ("DISPLACEMENT", "EXPANSION"): {
            "guard": "try_displacement_to_expansion",
            "market_inputs": ["open", "close"],
            "state_memory": ["displacement_candle", "direction", "atr"],
            "config": ["expansion_atr_min_distance"],
            "event": "EXPANSION_CONFIRMED",
        },
        ("EXPANSION", "RETEST"): {
            "guard": "try_expansion_to_retest (depth floor/ceiling/disp strength)",
            "market_inputs": ["close"],
            "state_memory": ["active_range", "direction", "displacement_candle", "atr"],
            "config": [
                "retest_depth_max",
                "retest_atr_depth_fraction",
                "retest_min_depth_atr_fraction",
                "max_displacement_strength",
            ],
            "event": "RETEST_CONFIRMED / BEGIN_SOFT_CONF",
        },
        ("EXPANSION", "EXPIRED"): {
            "guard": "TTL max_expansion_age_candles/hours after retest fail",
            "market_inputs": [],
            "state_memory": ["_expansion_entry_idx", "_expansion_entry_ts"],
            "config": ["max_expansion_age_candles", "max_expansion_age_hours"],
            "event": "EXPANSION_EXPIRED",
        },
        ("EXPIRED", "RANGE"): {
            "guard": "one-bar soft archive reset",
            "market_inputs": [],
            "state_memory": [],
            "config": [],
            "event": "EXPANSION_TTL_RESET",
        },
        ("RETEST", "EXECUTION"): {
            "guard": "soft-conf approve + zone + session filters",
            "market_inputs": ["close", "EMA state"],
            "state_memory": ["cached_features", "risk_score", "retest_candle", "active_range"],
            "config": ["tier_*", "conf_*", "allowed_sessions", "session_windows"],
            "event": "TRADE_OPENED path / soft conf",
        },
        ("EXECUTION", "RESOLUTION"): {
            "guard": "trade exit via executor",
            "market_inputs": ["high", "low", "close"],
            "state_memory": ["active_trade"],
            "config": ["exit_model", "sl/tp mults"],
            "event": "TRADE_*",
        },
        ("RESOLUTION", "RANGE"): {
            "guard": "post-resolution / post-trade reset",
            "market_inputs": [],
            "state_memory": [],
            "config": [],
            "event": "RESET",
        },
    }

    for fr, tos in vt.items():
        for to in tos:
            key = f"{fr}->{to}"
            meta = edge_meta.get((fr, to), {})
            edge_records.append(
                {
                    "from_state": fr,
                    "to_state": to,
                    "in_valid_transitions": True,
                    "guard_function": meta.get("guard"),
                    "market_inputs_read": meta.get("market_inputs", []),
                    "state_memory_read": meta.get("state_memory", []),
                    "config_values_read": meta.get("config", []),
                    "output_event": meta.get("event"),
                    "candidate_lifecycle_effect": "single _active_candidate advances/closes",
                    "reset_behavior": "many edges force reset_to_range bypassing graph",
                    "observed_xauusd_full_run_count": edges_measured.get(key),
                    "observed": edges_measured.get(key, 0) is not None
                    and edges_measured.get(key, 0) > 0
                    if key in edges_measured
                    else "UNKNOWN",
                    "authority_source": "state_topology.VALID_TRANSITIONS + crt_engine_v2 + funnel diagnostic",
                }
            )

    # force-reset edges (not in VALID_TRANSITIONS as free graph)
    force_resets = {
        "from_any_via_reset_to_range": {
            "note": "reset_to_range bypasses VALID_TRANSITIONS",
            "observed_reset_events": 10881,
            "dominant_reason_class": "HTF",
            "resets_from_SWEEP": 3075,
            "resets_from_DISPLACEMENT": 298,
            "resets_from_EXPANSION": 43,
            "resets_from_RETEST": 12,
            "resets_from_EXECUTION": 4,
        }
    }

    graph_doc = {
        "_doc": "Executable 9-state CRT graph for adjudication V1",
        "generated_at_utc": STAMP,
        "states": states,
        "valid_transitions": vt,
        "edges": edge_records,
        "force_reset_surface": force_resets,
        "shadow_path": {
            "sequence": ["RANGE", "SHADOW_PENDING", "SWEEP", "EXPANSION"],
            "skips": "body_ratio/ATR displacement strength on shadow resume",
            "measured_SWEEP_to_EXPANSION_shadow": 43,
        },
        "single_active_candidate": True,
        "source": [
            "src/config_layer/state_topology.py",
            "src/config_layer/crt_engine_v2.py",
            "docs/governance/crt_executable_state_graph.json",
            "docs/governance/crt_xauusd_funnel_diagnostic-2026-07-14.json",
        ],
        "prior_state_graph_artifact": "docs/governance/crt_executable_state_graph.json",
    }
    write("CRT_9_STATE_EXECUTABLE_GRAPH_V1.json", graph_doc)

    # ── Input authority matrix (enriched schema) ──
    inputs_enriched = []
    for i, raw in enumerate(auth_in.get("inputs") or []):
        name = raw.get("name") or f"input_{i}"
        dup = raw.get("duplication_status") or ""
        if "PARALLEL" in dup:
            identity = "DUPLICATE_LOCAL_IMPLEMENTATION"
        elif "NAME_SHARED" in dup:
            identity = "APPROXIMATE"
        elif "PRIVATE" in dup or "LEGITIMATE" in dup:
            identity = "NO_CANONICAL_EQUIVALENT"
        elif name in ("open", "high", "low", "close") or raw.get("in_canonical_38"):
            identity = "EXACT" if name in CANONICAL_FEATURES else "TRANSFORM"
        elif "NOT_CONSUMED" in dup:
            identity = "EXACT"
        else:
            identity = "UNKNOWN"

        owner = raw.get("authority_owner_today") or "OTHER"
        owner_map = {
            "RAW_OHLC_STREAM": "FEATURE_PIPELINE",  # raw is market input; pipeline is bulk WHAT path
            "CRT_CANDLE_PROPERTY": "CRT_ENGINE",
            "CRT_LOCAL_ROLLING": "CRT_ENGINE",
            "CRT_LOCAL_DERIVED": "CRT_ENGINE",
            "CRT_LOCAL_EWM": "CRT_ENGINE",
            "CRT_STATE_MACHINE_MEMORY": "CRT_STATE_MEMORY",
            "CRT_CACHE + FORMULA_REGISTRY": "CRT_ENGINE",
            "CRT_LOCAL + FORMULA_REGISTRY": "CRT_ENGINE",
            "FEATUREPIPELINE + BACKTEST_JOURNAL": "BACKTEST_HARNESS",
        }
        auth_owner = owner_map.get(owner, owner if owner in {
            "MARKET_ONTOLOGY", "FEATURE_PIPELINE", "CRT_ENGINE", "CRT_STATE_MEMORY",
            "CRT_CONFIG", "BACKTEST_HARNESS", "ENGINE_RUNNER", "MODEL", "SESSION_POLICY", "OTHER"
        } else "OTHER")

        mig = raw.get("migration_recommendation") or ""
        if "KEEP_IN_CRT" in mig or "PRIVATE" in mig:
            mig_rec = "KEEP_CRT_PRIVATE_STATE"
        elif "PARITY" in mig or "BIND" in mig or "CANDIDATE_FOR_MSIP" in mig:
            mig_rec = "BIND_TO_CANONICAL_FEATURE"
        elif "MOVE" in mig or "MSIP" in mig:
            mig_rec = "MOVE_TO_INTERPRETATION_LAYER"
        elif "POLICY" in mig or "CONFIG" in owner:
            mig_rec = "KEEP_POLICY_CONFIG"
        elif "NOT_CLAIM" in mig:
            mig_rec = "MOVE_TO_INTERPRETATION_LAYER"
        else:
            mig_rec = "OWNER_DECISION_REQUIRED"

        conf = "PROVEN" if raw.get("observed_in_baseline_v1") or raw.get("observed_in_transition_window") else "STRONG"
        if identity == "UNKNOWN":
            conf = "PARTIAL"

        inputs_enriched.append(
            {
                "input_id": f"CRT-IN-{i+1:03d}",
                "runtime_name": name,
                "description": raw.get("source_location") or name,
                "read_locations": [raw.get("source_location")],
                "write_production_locations": [],
                "source_class": raw.get("runtime_source_class"),
                "formula_or_semantic": raw.get("source_location"),
                "formula_id": raw.get("formula_id"),
                "fm_id": raw.get("formula_id"),
                "canonical_feature_equivalent": raw.get("canonical_equivalent"),
                "identity_relationship": identity,
                "authority_owner": auth_owner,
                "temporal_semantics": "stateful" if raw.get("stateful") else "same_bar_or_stateless",
                "stateful_or_stateless": "STATEFUL" if raw.get("stateful") else "STATELESS",
                "instrument_specific": False,
                "configurable": bool(raw.get("config_dependency")),
                "current_consumer": "CRTEngine.process_candle / StateMachine.try_*",
                "required_future_owner": auth_owner if mig_rec.startswith("KEEP") else "MARKET_ONTOLOGY_OR_MSIP",
                "migration_recommendation": mig_rec,
                "evidence": [
                    "docs/governance/CRT_INPUT_AUTHORITY_MATRIX_V1.json (prior)",
                    "baseline/transition traces",
                    "crt_engine_v2.py",
                ],
                "confidence": conf,
                "prior_fields": raw,
            }
        )

    # config keys as HOW inputs
    for j, ck in enumerate(auth_in.get("config_keys") or []):
        inputs_enriched.append(
            {
                "input_id": f"CRT-CFG-{j+1:03d}",
                "runtime_name": ck.get("config_key"),
                "description": f"CRTConfig HOW: {ck.get('role')}",
                "read_locations": ck.get("guards"),
                "write_production_locations": ["configs/production/v2_multi_2026_04.json"],
                "source_class": "CONFIG_VALUE",
                "formula_or_semantic": ck.get("role"),
                "formula_id": None,
                "fm_id": None,
                "canonical_feature_equivalent": None,
                "identity_relationship": "NO_CANONICAL_EQUIVALENT",
                "authority_owner": "CRT_CONFIG",
                "temporal_semantics": "static_per_run",
                "stateful_or_stateless": "STATELESS",
                "instrument_specific": True,  # prod multi may carry instrument routing
                "configurable": True,
                "current_consumer": "CRTEngine",
                "required_future_owner": "CRT_CONFIG",
                "migration_recommendation": "KEEP_POLICY_CONFIG",
                "evidence": ["CRTConfig", "active prod config", "fail-reason diagnostic"],
                "confidence": "PROVEN",
            }
        )

    auth_matrix = {
        "_doc": "CRT_INPUT_AUTHORITY_MATRIX_V1 (adjudication package copy, enriched schema)",
        "generated_at_utc": STAMP,
        "package": "crt_architecture_adjudication_v1",
        "architectural_finding": auth_in.get("architectural_finding"),
        "inputs": inputs_enriched,
        "summary_counts": {
            "n_inputs": len(inputs_enriched),
            "keep_private": sum(1 for x in inputs_enriched if x["migration_recommendation"] == "KEEP_CRT_PRIVATE_STATE"),
            "keep_policy": sum(1 for x in inputs_enriched if x["migration_recommendation"] == "KEEP_POLICY_CONFIG"),
            "bind_canonical": sum(1 for x in inputs_enriched if x["migration_recommendation"] == "BIND_TO_CANONICAL_FEATURE"),
            "move_interpretation": sum(1 for x in inputs_enriched if x["migration_recommendation"] == "MOVE_TO_INTERPRETATION_LAYER"),
        },
        "msip_implications": auth_in.get("msip_implications"),
    }
    write("CRT_INPUT_AUTHORITY_MATRIX_V1.json", auth_matrix)
    write(
        "CRT_INPUT_AUTHORITY_MATRIX_V1.md",
        _auth_md(auth_matrix),
    )
    # also refresh governance root copies (enriched)
    (ROOT / "docs/governance/CRT_INPUT_AUTHORITY_MATRIX_V1.json").write_text(
        json.dumps(auth_matrix, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "docs/governance/CRT_INPUT_AUTHORITY_MATRIX_V1.md").write_text(
        _auth_md(auth_matrix), encoding="utf-8"
    )

    # ── WHAT/HOW/WHO map ──
    boundaries = [
        {
            "producer": "FeaturePipeline",
            "produced_quantity": "CANONICAL_FEATURES[38]",
            "authority_layer": "WHAT",
            "consumer": "BacktestRunner journal @ TRADE_OPENED",
            "consumer_role": "WHO (ledger/features attach)",
            "actual_binding": "timestamp lookup into feature_vectors",
            "expected_governed_binding": "canonical vector for models/research",
            "status": "ALIGNED",
            "architectural_consequence": "38-vector is real WHAT; not CRT transition surface",
            "evidence": "backtest_v2.py TRADE_OPENED path; baseline path verification",
        },
        {
            "producer": "FeaturePipeline",
            "produced_quantity": "CANONICAL_FEATURES[38]",
            "authority_layer": "WHAT",
            "consumer": "CRTEngine.process_candle",
            "consumer_role": "WHO (opportunity lifecycle)",
            "actual_binding": "NONE for transition guards",
            "expected_governed_binding": "often assumed full-vector consumer — FALSE",
            "status": "MISSING_BINDING",
            "architectural_consequence": "Split authority: continuous WHAT vs CRT-local math",
            "evidence": "XAUUSD baseline trace; process_candle(candle, htf_id)",
        },
        {
            "producer": "CRTEngine local (Candle props / ATR / EMA)",
            "produced_quantity": "body_ratio, wick_size, atr, emas, move",
            "authority_layer": "WHAT (market math) implemented inside WHO",
            "consumer": "StateMachine.try_*",
            "consumer_role": "WHO",
            "actual_binding": "CRT-local recompute",
            "expected_governed_binding": "ontology FM-010/002/041/043/044 where applicable",
            "status": "DUPLICATED_AUTHORITY",
            "architectural_consequence": "MARKET_MATH_LEAK_INTO_WHO; parity unproven vs pipeline",
            "evidence": "crt_engine_v2 try_sweep_to_displacement; CRT_INPUT_AUTHORITY_MATRIX",
        },
        {
            "producer": "CRT EngineState",
            "produced_quantity": "active_range, sweep_event, displacement_candle, candidate memory",
            "authority_layer": "WHO private lifecycle state (not WHAT)",
            "consumer": "CRTEngine",
            "consumer_role": "WHO",
            "actual_binding": "EngineState fields",
            "expected_governed_binding": "remain private opportunity state",
            "status": "LEGITIMATE_PRIVATE_STATE",
            "architectural_consequence": "Must not force into MarketStateVector",
            "evidence": "TelemetryCollector._active_candidate; EngineState",
        },
        {
            "producer": "CRTConfig / production JSON",
            "produced_quantity": "thresholds, TTL, sessions, conf weights",
            "authority_layer": "HOW",
            "consumer": "CRTEngine",
            "consumer_role": "WHO",
            "actual_binding": "CRTConfig fields",
            "expected_governed_binding": "config-first HOW",
            "status": "ALIGNED",
            "architectural_consequence": "Policy recalibration is HOW, not architecture replacement",
            "evidence": "v2_multi_2026_04; fail-reason active geometry",
        },
        {
            "producer": "session_windows / allowed_sessions",
            "produced_quantity": "session admission",
            "authority_layer": "HOW",
            "consumer": "CRT soft-conf / FILTER_REJECTED",
            "consumer_role": "WHO",
            "actual_binding": "CRTConfig session policy",
            "expected_governed_binding": "policy filter after pattern qualification",
            "status": "ALIGNED",
            "architectural_consequence": "Tertiary funnel residual OFF_SESSION (12/17)",
            "evidence": "funnel diagnostic FILTER_REJECTED",
        },
        {
            "producer": "HTFBuilder + reset_lg",
            "produced_quantity": "HTF range lifecycle / reset",
            "authority_layer": "HOW + WHO coupling",
            "consumer": "CRTEngine",
            "consumer_role": "WHO",
            "actual_binding": "reset_to_range force",
            "expected_governed_binding": "explicit lifecycle policy",
            "status": "POLICY_LEAK_INTO_WHAT",
            "architectural_consequence": "HTF reset dominates candidate death (3323/3433)",
            "evidence": "funnel diagnostic RESET_HTF",
        },
        {
            "producer": "EngineRunner fusion stack",
            "produced_quantity": "downstream admission",
            "authority_layer": "WHO",
            "consumer": "trade journal",
            "consumer_role": "WHO",
            "actual_binding": "optional BACKTEST_ENGINE_GATE",
            "expected_governed_binding": "post-CRT admission",
            "status": "ALIGNED",
            "architectural_consequence": "Not primary collapse surface on measured run",
            "evidence": "rejected_trades=0",
        },
    ]

    whw = {
        "_doc": "WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1",
        "generated_at_utc": STAMP,
        "definitions": {
            "WHAT": "Governed market mathematics and market observables",
            "HOW": "Interpretation policy and behavior-selection semantics",
            "WHO": "Executable consumers and decision owners",
        },
        "boundaries": boundaries,
        "answers": {
            "where_WHAT_computed": "FeaturePipeline + candle_math/derived_math/ontology; also CRT-local parallel math",
            "where_WHAT_duplicated": "CRT body_ratio/wick/atr/ema paths vs pipeline FM identities",
            "where_HOW_encoded": "CRTConfig + reset/TTL/session/soft-conf policy in crt_engine_v2",
            "HOW_config_driven": "most thresholds via prod config merge",
            "HOW_hardcoded": "some control-flow structure / VALID_TRANSITIONS graph (STRUCTURAL)",
            "WHO_reads_governed_WHAT": "Backtest journal, models (when enabled), research — not CRT transitions",
            "WHO_bypasses_governed_WHAT": "CRT transition guards (local math)",
            "bypass_legitimate": "partial — private lifecycle state YES; market math parallel recomputation is split authority",
            "candidate_lifecycle_belongs": "WHO/CRT EngineState — not MarketStateVector",
            "continuous_market_state_belongs": "WHAT + interpretation layer (MSIP shadow), independent of opportunity ownership",
        },
    }
    write("WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.json", whw)
    write("WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.md", _whw_md(whw))
    (ROOT / "docs/governance/WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.json").write_text(
        json.dumps(whw, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "docs/governance/WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.md").write_text(
        _whw_md(whw), encoding="utf-8"
    )

    # ── MSIP correction ──
    msip_md = _msip_md()
    write("MSIP_ARCHITECTURE_CORRECTION_V1.md", msip_md)
    (ROOT / "docs/governance/MSIP_ARCHITECTURE_CORRECTION_V1.md").write_text(msip_md, encoding="utf-8")

    # ── Evidence freeze ──
    evidence = {
        "generated_at_utc": STAMP,
        "task_class": "OBSERVATION_ONLY",
        "policy": {
            "BASELINE_HASH_PARITY_GENERAL_REQUIREMENT": "SUPERSEDED",
            "HISTORICAL_BASELINE_ARTIFACTS": "PRESERVED",
            "FUTURE_ACCEPTANCE_POLICY": "TASK_CLASSIFICATION_BASED",
            "ref": "docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md",
        },
        "baseline_trace_v1": freeze,
        "funnel_full_run": {
            "source": "docs/governance/crt_xauusd_funnel_diagnostic-2026-07-14.json",
            "run": "results/cert_xau_phase2/run_20260711_202626_XAUUSD",
            "candles": 47275,
            "RANGE_TO_SWEEP": 3390,
            "SWEEP_TO_DISPLACEMENT": 315,
            "DISPLACEMENT_TO_EXPANSION": 17,
            "SWEEP_TO_EXPANSION_shadow": 43,
            "UNIQUE_EXPANSION_EPISODES": 60,
            "EXPANSION_TO_RETEST": 17,
            "RETEST_TO_EXECUTION": 5,
            "EXECUTION_TO_RESOLUTION": 1,
            "TRADE_OPENED": 1,
            "RESET_HTF_candidate_deaths": "3323/3433",
            "expansion_ended_by": {"retest": 17, "reset": 43, "expired": 0, "eof": 0},
            "expansion_dwell": {"median": 1, "max": 346},
            "occupancy_note": "4605 EXPANSION candles != 60 episodes",
            "downstream_rejected_trades": 0,
        },
        "fail_reason_diagnostic": {
            "source": "docs/governance/crt_fail_reason_diagnostic-2026-07-14.json",
            "evidence_class": "DIAGNOSTIC_SAMPLE_EVIDENCE",
            "not": "POPULATION_RATE_EVIDENCE",
            "max_process_candles": fail.get("max_process_candles"),
            "on_off_parity": fail.get("on_off_action_parity"),
            "top_counts": (fail.get("fail_reason_counts") or {}).get("raw_counts"),
        },
        "schema": {
            "CANONICAL_FEATURE_DIM": 38,
            "SCHEMA_HASH": SCHEMA_HASH,
            "FEATURE_ORDER_HASH": FEATURE_ORDER_HASH,
            "CANONICAL_FEATURES": list(CANONICAL_FEATURES),
        },
        "closure_surfaces_untouched": [
            s for s in (closure.get("surfaces") or []) if s.get("status") == "CLOSED"
        ],
    }
    write("EVIDENCE_PACKAGE_INDEX.json", evidence)

    # ── Options evaluation ──
    options = _options_eval()
    write("OPTIONS_EVALUATION_V1.json", options)

    # ── Decision ──
    decision = {
        "_doc": "CRT_ARCHITECTURE_ADJUDICATION_V1 — frozen decision record",
        "generated_at_utc": STAMP,
        "task_class": "OBSERVATION_ONLY",
        "ARCHITECTURE_DECISION": "C",
        "SELECTED_OPTION": "C. SEPARATE_CONTINUOUS_MARKET_STATE_OBSERVATION_FROM_CRT_OPPORTUNITY_LIFECYCLE",
        "DECISION_STATUS": "DECIDED",
        "REJECTED_OPTIONS": {
            "A": "Insufficient as sole next phase — collapses architectural split to threshold search",
            "B": "Addresses concurrency only; leaves CRT-local WHAT duplication and continuous-state gap",
            "D": (
                "Unsupported by current evidence; D requires explicit CRT-boundary reopen authority "
                "(CLOSED is not permanent impossibility). Not selected."
            ),
        },
        "OPTION_E_REQUIRED": False,
        "OPTION_E_NOTE": (
            "Conditional future work may add concurrent candidates (B) or HOW recalibration (A) "
            "AFTER C's shadow continuous-state layer exists; that does not change primary decision C."
        ),
        "OPTION_D_CLARIFICATION": (
            "Boundary-scoped closure means D is not currently authorized without valid reopen "
            "conditions and new evidence; it is not permanently forbidden."
        ),
        "DECISIVE_CRITERIA": [
            "Executable dual path: governed 38-vector parallel to CRT-local transition inputs (PROVEN)",
            "CRT is single-candidate opportunity lifecycle, not continuous market-state observer (PROVEN)",
            "Primary collapse is lifecycle/geometry/HTF ownership, not EngineRunner rejection (PROVEN)",
            "Threshold tuning alone cannot fix split WHAT authority or single-candidate monopolization (STRONG)",
            "D requires explicit CRT-boundary reopen authority and is unsupported by current evidence "
            "(CLOSED does not make replacement permanently impossible)",
        ],
        "THRESHOLD_TUNING_AUTHORIZED": False,
        "IMPLEMENTATION_AUTHORIZED": False,
        "NEXT_PHASE_TASK_CLASS": "OBSERVATION_ONLY then EXPLORATORY_RESEARCH (shadow only)",
        "NEXT_PHASE_NAME": "MSIP_SHADOW_CONTINUOUS_STATE_LAYER_DESIGN",
        "NEXT_PHASE_SCOPE": (
            "Design + shadow-only continuous MarketState interpretation from governed WHAT; "
            "compare bar-by-bar to CRT lifecycle outcomes; no CRT cutover; no threshold optimization program"
        ),
        "BEHAVIOR_CHANGE_AUTHORIZED_FOR_NEXT_PHASE": False,
        "OWNER_DECISIONS_REQUIRED": [
            "Which CRT-local math quantities require formal parity audit before any future binding (body_ratio/ATR/EMA)",
            "Whether concurrent candidates enter roadmap only after shadow MSIP comparison exists",
        ],
        "REQUIRED_INVARIANTS": [
            "CRT CLOSED boundary (OHLCV→TRADE_OPENED) remains unreopened unless formal reopen conditions fire",
            "Canonical feature code surface CLOSED remains unreopened by this decision",
            "Non-transitive closure: continuous-state layer does not inherit production authority from feature CLOSED",
            "OBSERVATION_ONLY work remains behavior-neutral when hooks disabled",
            "Historical baselines preserved as comparison evidence",
            "No economic claims from architecture decision",
            "MarketStateVector must not silently become CRT transition authority without BEHAVIOR_CHANGE_AUTHORIZED plan",
        ],
        "GATES": {
            "GATE_1_EVIDENCE_SUFFICIENCY": "PASS",
            "GATE_2_EXECUTABLE_REALITY": "PASS",
            "GATE_3_AUTHORITY_MAP": "PASS",
            "GATE_4_WHAT_HOW_WHO_BOUNDARIES": "PASS",
            "GATE_5_ALTERNATIVE_COMPARISON": "PASS",
            "GATE_6_DECISION_REVERSIBILITY": "PASS",
            "GATE_7_CLOSED_BOUNDARY_COMPATIBILITY": "PASS",
            "GATE_8_IMPLEMENTATION_BOUNDARY": "PASS",
        },
        "proven_facts": [
            "CRT is a 9-state opportunity lifecycle with directed VALID_TRANSITIONS + force-reset surface",
            "CRT transition guards do not use the complete 38-feature vector as primary transition surface",
            "CRT includes local market math (body_ratio, wick, atr, move, emas) and private state memory",
            "One active candidate lifecycle is tracked (TelemetryCollector._active_candidate)",
            "XAUUSD full run: 3390 RANGE→SWEEP, 315 SWEEP→DISP, 60 expansion episodes, 17 retest, 5 exec, 1 trade",
            "HTF reset dominates candidate deaths (3323/3433)",
            "Expansion episodes: 17 retest / 43 reset / 0 TTL expired",
            "Downstream rejected_trades=0 on measured run",
            "Fail-reason sample shows depth_below_min, depth_above_ceiling, move_below_atr_min active",
            "Soft-conf score gate approved 17/17; 12 FILTER_REJECTED off_session",
        ],
        "strong_inferences": [
            {
                "claim": "Single-candidate ownership suppresses overlapping opportunity observation",
                "support": "singular _active_candidate; long expansion dwell max 346; HTF deaths",
                "unproven": "how many concurrent opportunities would have been economic",
            },
            {
                "claim": "Current CRT mixes continuous market observation with opportunity lifecycle ownership",
                "support": "dual OHLCV path; local math in try_*; state memory ownership",
                "unproven": "optimal split surface for every quantity",
            },
            {
                "claim": "Threshold recalibration alone cannot resolve architectural split authority",
                "support": "even perfect thresholds leave CRT-local WHAT vs pipeline WHAT dual implementation",
                "unproven": "instrument-specific retune magnitude of throughput change",
            },
            {
                "claim": "Binding CRT directly to MarketStateVector would be a consumer migration",
                "support": "CRT currently does not consume 38-vector for guards",
                "unproven": "future migration cost",
            },
        ],
        "open_questions": [
            "CRT ATR/EMA/body_ratio parity vs FeaturePipeline (decision-critical only for future BIND, not for choosing C)",
            "Whether concurrent candidates should be phase-2 under CRT HOW after shadow continuous state exists",
            "Session policy placement: CRT HOW vs shared policy layer",
        ],
        "non_problems": [
            "One trade / low trade count alone does not prove architecture failure",
            "Historical output hash changes are not automatic failures under BEHAVIOR_CHANGE_AUTHORIZED",
            "38 features need not all be consumed by every WHO",
            "CRT private lifecycle state is not automatically an authority violation",
            "Downstream fusion rejection is not the measured primary collapse",
            "TTL non-firing (0 expired) does not alone prove TTL should be shortened without ownership redesign",
        ],
        "next_phase": {
            "name": "MSIP_SHADOW_CONTINUOUS_STATE_LAYER_DESIGN",
            "task_class": "OBSERVATION_ONLY / EXPLORATORY_RESEARCH",
            "behavior_change_authorized": False,
            "entry_criteria": [
                "This adjudication package frozen and accepted",
                "CRT CLOSED remains unreopened",
                "No threshold program as primary workstream",
            ],
            "exit_criteria": [
                "Documented MarketStateVector dimension set bound to governed WHAT where possible",
                "Shadow comparison protocol vs CRT lifecycle outcomes defined",
                "CRT private memory explicitly out of scope of vector",
                "Implementation plan classified BEHAVIOR_CHANGE_AUTHORIZED only if CRT consumer cutover proposed later",
            ],
            "non_goals": [
                "Threshold optimization",
                "Trade-count maximization",
                "CRT rewrite",
                "Concurrent candidates implementation",
                "Feature certification reopening",
                "Production cutover",
            ],
            "rollback_comparison": "Keep current CRT path as comparison authority; shadow MSIP is additive",
            "future_conditional": {
                "after_shadow_msip": ["evaluate concurrent candidates (B)", "evaluate instrument HOW recalibration (A)"],
                "never_by_default": ["replace CRT SM (D) without reopen evidence"],
            },
        },
        "accepted_risks": [
            "Short-term no throughput improvement (by design)",
            "Shadow dual-path cost during design",
            "Delayed concurrent-candidate exploration",
        ],
        "unresolved_risks": [
            "Parity unknown between CRT-local ATR and pipeline atr",
            "Fail-reason sample not population rates",
            "Instrument transfer EURUSD-validated knobs on XAUUSD still open for later HOW work",
        ],
    }
    write("ARCHITECTURE_DECISION_RECORD_V1.json", decision)
    write("ARCHITECTURE_DECISION_RECORD_V1.md", _decision_md(decision, options))

    # frozen evidence summary md
    write("FROZEN_EVIDENCE_SUMMARY_V1.md", _evidence_md(evidence))
    write("PROBLEM_STATEMENT_V1.md", _problem_md(decision))
    write("NEXT_PHASE_BOUNDARY_V1.md", _next_md(decision))

    # package manifest
    files = sorted([p for p in PKG.rglob("*") if p.is_file() and p.name != "PACKAGE_MANIFEST.json"])
    file_list = []
    agg = hashlib.sha256()
    for p in files:
        rel = str(p.relative_to(PKG)).replace("\\", "/")
        h = sha256_file(p)
        file_list.append({"path": rel, "sha256": h, "bytes": p.stat().st_size})
        agg.update(f"{h}  {rel}\n".encode())
    manifest = {
        "_doc": "CRT Architecture Adjudication V1 frozen package manifest",
        "generated_at_utc": STAMP,
        "package_path": "docs/governance/crt_architecture_adjudication_v1",
        "task_class": "OBSERVATION_ONLY",
        "ARCHITECTURE_DECISION": "C",
        "files": file_list,
        "package_aggregate_sha256_over_files": None,  # filled after write
        "implementation_authorized": False,
        "threshold_tuning_authorized": False,
    }
    # write without aggregate first then include self? exclude manifest from aggregate
    man_path = PKG / "PACKAGE_MANIFEST.json"
    # compute aggregate of listed files only
    manifest["package_aggregate_sha256"] = agg.hexdigest()
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("ARCHITECTURE_DECISION = C")
    print("PACKAGE", PKG)
    print("AGGREGATE", manifest["package_aggregate_sha256"])
    print("FILES", len(file_list))
    return 0


def _auth_md(m: dict) -> str:
    lines = [
        "# CRT Input Authority Matrix V1",
        "",
        f"_Generated {m['generated_at_utc']}_",
        "",
        m.get("architectural_finding", ""),
        "",
        f"Inputs: **{m['summary_counts']['n_inputs']}**  ",
        f"Keep private: {m['summary_counts']['keep_private']} · "
        f"Keep policy: {m['summary_counts']['keep_policy']} · "
        f"Bind canonical: {m['summary_counts']['bind_canonical']} · "
        f"Move interpretation: {m['summary_counts']['move_interpretation']}",
        "",
        "| id | name | source | identity | owner | migration | conf |",
        "|---|---|---|---|---|---|---|",
    ]
    for x in m["inputs"]:
        lines.append(
            f"| {x['input_id']} | `{x['runtime_name']}` | {x['source_class']} | "
            f"{x['identity_relationship']} | {x['authority_owner']} | "
            f"{x['migration_recommendation']} | {x['confidence']} |"
        )
    lines += ["", "Rule: no name-similarity identity without math/temporal proof.", ""]
    return "\n".join(lines) + "\n"


def _whw_md(m: dict) -> str:
    lines = [
        "# WHAT / HOW / WHO Executable Boundary Map V1",
        "",
        f"_Generated {m['generated_at_utc']}_",
        "",
        "## Answers",
        "",
    ]
    for k, v in m["answers"].items():
        lines.append(f"- **{k}:** {v}")
    lines += ["", "## Boundaries", ""]
    for b in m["boundaries"]:
        lines.append(
            f"### {b['producer']} → {b['consumer']} ({b['status']})\n\n"
            f"- quantity: `{b['produced_quantity']}`\n"
            f"- layer: {b['authority_layer']}\n"
            f"- actual: {b['actual_binding']}\n"
            f"- consequence: {b['architectural_consequence']}\n"
            f"- evidence: {b['evidence']}\n"
        )
    return "\n".join(lines) + "\n"


def _msip_md() -> str:
    return f"""# MSIP Architecture Correction V1

_Generated {STAMP}_  
**TASK_CLASS:** OBSERVATION_ONLY (this document)  
**Supersedes assumptions:** MSIP as mere dynamic config; CRT as 38-feature consumer for transitions

---

## 1. Corrected executable reality

```text
RAW MARKET DATA
        │
        ├──────────────► GOVERNED FEATURE PIPELINE
        │                       │
        │                       ▼
        │               38 CANONICAL FEATURES
        │                       │
        │                       ▼
        │               OTHER CONSUMER SURFACES
        │               (journal @ TRADE_OPENED, models when enabled)
        │
        └──────────────► CRT-LOCAL INTERPRETATION
                                +
                         CRT STATE MEMORY
                                +
                         CRTConfig / POLICY (HOW)
                                │
                                ▼
                         9-STATE CRT LIFECYCLE (single active candidate)
                                │
                                ▼
                         EVENTS / TRADE OUTPUT
```

**PROVEN:** CRT transition guards are not primarily driven by the 38-dim vector.

---

## 2. MSIP problem statement (corrected)

MSIP is the program to introduce a **continuous market-state interpretation layer**
from **governed WHAT** quantities, producing a **MarketStateVector** for observation
and research, **without** initially mutating CRT opportunity-lifecycle behavior.

MSIP is **not**:

- dynamic config loading alone  
- automatic CRT rewrite  
- mandatory concurrent candidates  
- claim that CRT already implements 38→HOW→decision  

---

## 3. Adjudicated design questions

| Question | Decision |
|---|---|
| MarketStateVector = continuous market state independent of opportunity ownership? | **YES** |
| Computed from governed WHAT quantities? | **YES** (primary); CRT-local math only after parity or new registration |
| CRT remains stateful opportunity-lifecycle consumer? | **YES** (near term; CLOSED boundary) |
| CRT private memory outside MarketStateVector? | **YES** |
| Policy produce dimensions without mutating CRT lifecycle? | **YES** (shadow HOW interpretation) |
| Migration begin in SHADOW mode? | **YES — REQUIRED** |
| Keep current CRT as comparison path? | **YES — REQUIRED** |
| Concurrent candidates separate from MarketStateVector introduction? | **YES — separate later decision (B), not phase-1 of C** |

---

## 4. Relation to architecture decision C

Adjudication V1 selects **Option C**: separate continuous market-state observation
from CRT opportunity lifecycle. MSIP shadow is the named next design phase under C.

**Not authorized now:** CRT cutover, threshold program as primary work, CRT replacement.

---

## 5. Authority

Design correction only. No production authority. No economic claims.
"""


def _options_eval() -> dict:
    return {
        "A": {
            "name": "PRESERVE_CURRENT_CRT_AND_RECALIBRATE_POLICY",
            "verdict": "REJECT_AS_PRIMARY",
            "benefits": ["low migration cost", "uses existing HOW config surface", "reversible knobs"],
            "costs": ["leaves dual WHAT implementation", "single-candidate monopolization intact", "does not create continuous state observation"],
            "authority_consistency": "HOW-only; does not resolve MARKET_MATH_LEAK_INTO_WHO",
            "evidence_for": "geometry fails active; instrument transfer EURUSD→XAUUSD possible",
            "evidence_against": "HTF reset 3323/3433; 0 TTL expiry; architectural not only parametric collapse",
            "reversibility": "HIGH for knobs",
            "score_summary": "Valid later HOW workstream; insufficient as architecture-governing next phase",
        },
        "B": {
            "name": "PRESERVE_CRT_LIFECYCLE_AND_ADD_CONCURRENT_CANDIDATES",
            "verdict": "REJECT_AS_PRIMARY",
            "benefits": ["attacks single-candidate suppression directly", "may raise opportunity throughput"],
            "costs": ["BEHAVIOR_CHANGE on CRT CLOSED surface", "complexity explosion", "still leaves CRT-local WHAT split"],
            "authority_consistency": "requires CRT reopen/careful lifecycle redesign",
            "evidence_for": "singular _active_candidate; long expansion dwell",
            "evidence_against": "does not create governed continuous market state; premature without shadow observation layer",
            "reversibility": "MEDIUM-LOW",
            "score_summary": "Conditional future after C shadow proves measurement need",
        },
        "C": {
            "name": "SEPARATE_CONTINUOUS_MARKET_STATE_OBSERVATION_FROM_CRT_OPPORTUNITY_LIFECYCLE",
            "verdict": "SELECT",
            "benefits": [
                "matches proven dual-path executable reality",
                "preserves CRT CLOSED as opportunity lifecycle",
                "enables governed WHAT → interpretation without forcing CRT cutover",
                "supports shadow comparison",
                "aligns MSIP correction",
            ],
            "costs": ["no immediate trade-count lift", "design work before behavior change"],
            "authority_consistency": "respects non-transitive closure; no silent production authority",
            "evidence_for": "baseline CRT≠38-vector; funnel ownership collapse; WHAT/HOW/WHO map",
            "evidence_against": "none decisive; residual parity questions are implementation details",
            "reversibility": "HIGH (shadow first)",
            "score_summary": "Best next governing architecture",
        },
        "D": {
            "name": "REPLACE_CRT_STATE_MACHINE_ARCHITECTURE",
            "verdict": "REJECT",
            "benefits": ["clean slate"],
            "costs": ["reopens CRT CLOSED", "destroys lifecycle evidence base", "highest risk"],
            "authority_consistency": "violates default closed policy without reopen evidence",
            "evidence_for": "none requiring replacement",
            "evidence_against": "CRT valid as opportunity SM; problem is boundary separation not SM existence",
            "reversibility": "LOW",
            "score_summary": "Unjustified",
        },
        "E": {
            "name": "HYBRID",
            "verdict": "NOT_REQUIRED_AS_PRIMARY_LABEL",
            "note": "C may later sequence A/B as conditional phases; primary decision remains C",
        },
    }


def _decision_md(d: dict, options: dict) -> str:
    lines = [
        "# CRT Architecture Decision Record V1",
        "",
        f"_Generated {d['generated_at_utc']}_",
        "",
        f"## DECISION: **{d['ARCHITECTURE_DECISION']}** — {d['SELECTED_OPTION']}",
        "",
        f"**Status:** {d['DECISION_STATUS']}  ",
        f"**Task class (this package):** {d['task_class']}  ",
        f"**Threshold tuning authorized:** {d['THRESHOLD_TUNING_AUTHORIZED']}  ",
        f"**Implementation authorized:** {d['IMPLEMENTATION_AUTHORIZED']}",
        "",
        "## Decisive criteria",
        "",
    ]
    for c in d["DECISIVE_CRITERIA"]:
        lines.append(f"- {c}")
    lines += ["", "## Rejected options", ""]
    for k, v in d["REJECTED_OPTIONS"].items():
        lines.append(f"- **{k}:** {v}")
    lines += ["", "## Next phase", ""]
    np = d["next_phase"]
    lines.append(f"- **Name:** {np['name']}")
    lines.append(f"- **Task class:** {np['task_class']}")
    lines.append(f"- **Behavior change authorized:** {np['behavior_change_authorized']}")
    lines += ["", "## Required invariants", ""]
    for i in d["REQUIRED_INVARIANTS"]:
        lines.append(f"- {i}")
    lines += ["", "## Gates", ""]
    for k, v in d["GATES"].items():
        lines.append(f"- {k}: **{v}**")
    return "\n".join(lines) + "\n"


def _evidence_md(e: dict) -> str:
    f = e["funnel_full_run"]
    return f"""# Frozen Evidence Summary V1

_Generated {e['generated_at_utc']}_

## Policy

- Baseline hash parity general requirement: **SUPERSEDED**
- Historical artifacts: **PRESERVED**

## Baseline Trace V1

- SHA: `{e['baseline_trace_v1'].get('trace_sha256')}`
- Discovery: CRT guards do not consume 38-vector as primary transition surface

## Full-run funnel (transition truth)

```text
candles                 {f['candles']}
RANGE → SWEEP           {f['RANGE_TO_SWEEP']}
SWEEP → DISPLACEMENT    {f['SWEEP_TO_DISPLACEMENT']}
DISPLACEMENT → EXP      {f['DISPLACEMENT_TO_EXPANSION']}
shadow SWEEP → EXP      {f['SWEEP_TO_EXPANSION_shadow']}
unique EXP episodes     {f['UNIQUE_EXPANSION_EPISODES']}
EXP → RETEST            {f['EXPANSION_TO_RETEST']}
RETEST → EXECUTION       {f['RETEST_TO_EXECUTION']}
EXEC → RESOLUTION       {f['EXECUTION_TO_RESOLUTION']}
TRADE_OPENED            {f['TRADE_OPENED']}
```

Occupancy ≠ candidates: 4605 EXPANSION candles ≠ 60 episodes.

## Fail-reason diagnostic

- Class: DIAGNOSTIC_SAMPLE_EVIDENCE (not population rates)
- ON/OFF parity: {e['fail_reason_diagnostic'].get('on_off_parity')}
- See raw counts in package index JSON

## Non-use of economic performance

Architecture decision does **not** use PnL/win-rate as evidence.
"""


def _problem_md(d: dict) -> str:
    lines = ["# Current Architecture Problem Statement V1", "", "## Proven facts", ""]
    for x in d["proven_facts"]:
        lines.append(f"- {x}")
    lines += ["", "## Strong inferences", ""]
    for x in d["strong_inferences"]:
        lines.append(f"- **{x['claim']}**  \n  support: {x['support']}  \n  unproven: {x['unproven']}")
    lines += ["", "## Open questions", ""]
    for x in d["open_questions"]:
        lines.append(f"- {x}")
    lines += ["", "## Non-problems", ""]
    for x in d["non_problems"]:
        lines.append(f"- {x}")
    return "\n".join(lines) + "\n"


def _next_md(d: dict) -> str:
    np = d["next_phase"]
    lines = [
        "# Next Phase Boundary V1",
        "",
        f"## {np['name']}",
        "",
        f"Task class: `{np['task_class']}`  ",
        f"Behavior change authorized: **{np['behavior_change_authorized']}**",
        "",
        "## Entry criteria",
        "",
    ]
    for x in np["entry_criteria"]:
        lines.append(f"- {x}")
    lines += ["", "## Exit criteria", ""]
    for x in np["exit_criteria"]:
        lines.append(f"- {x}")
    lines += ["", "## Non-goals", ""]
    for x in np["non_goals"]:
        lines.append(f"- {x}")
    lines += ["", "## Rollback / comparison", "", np["rollback_comparison"], ""]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
