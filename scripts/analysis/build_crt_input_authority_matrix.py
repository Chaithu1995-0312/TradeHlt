"""
Build CRT_INPUT_AUTHORITY_MATRIX_V1 + CRT_TRANSITION_COVERAGE_MATRIX_V1
from executable instrumentation evidence + code-declared guard surfaces.

READ-ONLY regarding production CRT behavior (reads artifacts + source).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

OUT = ROOT / "docs" / "governance"
STAMP = datetime.now(timezone.utc).isoformat()


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    # Evidence sources
    base_freeze = load_json(
        OUT / "xauusd_crt_baseline_trace/XAUUSD_CRT_BASELINE_TRACE_V1_FREEZE.json"
    )
    trans_man = load_json(
        OUT / "xauusd_crt_transition_trace/xauusd_crt_transition_trace_v1.manifest.json"
    )
    coverage = load_json(
        OUT / "xauusd_crt_transition_trace/crt_executable_transition_coverage_corpus_v1.json"
    )
    trans_sum = load_json(
        OUT / "xauusd_crt_transition_trace/xauusd_crt_transition_trace_v1.summary.json"
    )

    # Aggregate observed inputs from transition window + baseline (baseline summary if any)
    observed_inputs: dict[str, dict] = {}
    for u in trans_sum.get("input_usage") or []:
        observed_inputs[u["input"]] = u

    # Code-declared CRT-local inputs (from path verification + source knowledge)
    # These are the authority candidates independent of whether this window hit them.
    code_inputs = [
        {
            "name": "open",
            "runtime_source_class": "RAW_OHLC",
            "source_location": "Candle.open / process_candle",
            "formula_id": None,
            "canonical_equivalent": "open",
            "in_canonical_38": True,
            "stateful": False,
            "config_dependency": None,
            "authority_owner_today": "RAW_OHLC_STREAM",
            "duplication_status": "NAME_SHARED_WITH_CANONICAL_BUT_NOT_VIA_FEATUREPIPELINE",
            "migration_recommendation": "KEEP_RAW_OR_BIND_MSIP_RAW_LAYER — not FeaturePipeline-mediated today",
            "observed_in_transition_window": "open" in observed_inputs,
            "observed_in_baseline_v1": True,
        },
        {
            "name": "high",
            "runtime_source_class": "RAW_OHLC",
            "source_location": "Candle.high; detect_sweep",
            "formula_id": None,
            "canonical_equivalent": "high",
            "in_canonical_38": True,
            "stateful": False,
            "config_dependency": None,
            "authority_owner_today": "RAW_OHLC_STREAM",
            "duplication_status": "NAME_SHARED_WITH_CANONICAL_BUT_NOT_VIA_FEATUREPIPELINE",
            "migration_recommendation": "KEEP_RAW; MSIP may re-export as market fact",
            "observed_in_transition_window": "high" in observed_inputs,
            "observed_in_baseline_v1": True,
        },
        {
            "name": "low",
            "runtime_source_class": "RAW_OHLC",
            "source_location": "Candle.low; detect_sweep",
            "formula_id": None,
            "canonical_equivalent": "low",
            "in_canonical_38": True,
            "stateful": False,
            "config_dependency": None,
            "authority_owner_today": "RAW_OHLC_STREAM",
            "duplication_status": "NAME_SHARED_WITH_CANONICAL_BUT_NOT_VIA_FEATUREPIPELINE",
            "migration_recommendation": "KEEP_RAW; MSIP may re-export as market fact",
            "observed_in_transition_window": "low" in observed_inputs,
            "observed_in_baseline_v1": True,
        },
        {
            "name": "close",
            "runtime_source_class": "RAW_OHLC",
            "source_location": "Candle.close; body_ratio/move/EMA update",
            "formula_id": None,
            "canonical_equivalent": "close",
            "in_canonical_38": True,
            "stateful": False,
            "config_dependency": None,
            "authority_owner_today": "RAW_OHLC_STREAM",
            "duplication_status": "NAME_SHARED_WITH_CANONICAL_BUT_NOT_VIA_FEATUREPIPELINE",
            "migration_recommendation": "KEEP_RAW; MSIP may re-export as market fact",
            "observed_in_transition_window": "close" in observed_inputs,
            "observed_in_baseline_v1": True,
        },
        {
            "name": "body_ratio",
            "runtime_source_class": "CRT_LOCAL_DERIVED",
            "source_location": "Candle.body_ratio property → FM-010 path / candle_math",
            "formula_id": "FM-010",
            "canonical_equivalent": "body_ratio",
            "in_canonical_38": True,
            "stateful": False,
            "config_dependency": "body_ratio_min (threshold only)",
            "authority_owner_today": "CRT_CANDLE_PROPERTY + FORMULA_REGISTRY",
            "duplication_status": "PARALLEL_TO_PIPELINE_SAME_FM — CRT does not read pipeline column",
            "migration_recommendation": "CANDIDATE_FOR_MSIP_CERTIFIED_FEATURE_BINDING (shadow first); prove byte-parity with pipeline body_ratio before cutover",
            "observed_in_transition_window": "body_ratio" in observed_inputs,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "wick_size",
            "runtime_source_class": "CRT_LOCAL_DERIVED",
            "source_location": "Candle.wick_size (candle_range / FM-002)",
            "formula_id": "FM-002",
            "canonical_equivalent": "wick_size",
            "in_canonical_38": True,
            "stateful": False,
            "config_dependency": "atr_multiplier_min",
            "authority_owner_today": "CRT_CANDLE_PROPERTY",
            "duplication_status": "PARALLEL_TO_PIPELINE_SAME_FM",
            "migration_recommendation": "CANDIDATE_FOR_MSIP_CERTIFIED_FEATURE_BINDING (shadow parity first)",
            "observed_in_transition_window": "wick_size" in observed_inputs,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "atr",
            "runtime_source_class": "CRT_LOCAL_DERIVED",
            "source_location": "RangeDetector.compute_atr(candle_buffer, atr_period)",
            "formula_id": "FM-041",
            "canonical_equivalent": "atr",
            "in_canonical_38": True,
            "stateful": True,
            "config_dependency": "atr_period, atr_buffer_multiplier",
            "authority_owner_today": "CRT_LOCAL_ROLLING",
            "duplication_status": "PARALLEL_TO_PIPELINE_ATR — may not be byte-identical (relative vs absolute; windowing)",
            "migration_recommendation": "AUTHORITY_AUDIT_REQUIRED before binding; do not assume pipeline atr == CRT atr",
            "observed_in_transition_window": "atr" in observed_inputs,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "move",
            "runtime_source_class": "CRT_LOCAL_DERIVED",
            "source_location": "abs(close-open) in try_sweep_to_displacement",
            "formula_id": None,
            "canonical_equivalent": None,
            "in_canonical_38": False,
            "stateful": False,
            "config_dependency": "atr_min_displacement",
            "authority_owner_today": "CRT_LOCAL_DERIVED",
            "duplication_status": "CRT_PRIVATE_QUANTITY",
            "migration_recommendation": "REGISTER_AS_MSIP_OR_CRT_PRIVATE — not currently a canonical feature",
            "observed_in_transition_window": "move" in observed_inputs,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "h_ref / l_ref / active_range",
            "runtime_source_class": "STATE_MEMORY",
            "source_location": "state.active_range (HTF range detector)",
            "formula_id": None,
            "canonical_equivalent": None,
            "in_canonical_38": False,
            "stateful": True,
            "config_dependency": "htf_candles_per_range (backtest HTF builder)",
            "authority_owner_today": "CRT_STATE_MACHINE_MEMORY",
            "duplication_status": "LEGITIMATE_CRT_PRIVATE_STATE",
            "migration_recommendation": "KEEP_IN_CRT — not a feature; MSIP may observe as state dimension only",
            "observed_in_transition_window": "h_ref" in observed_inputs or "l_ref" in observed_inputs,
            "observed_in_baseline_v1": True,
        },
        {
            "name": "sweep_event",
            "runtime_source_class": "STATE_MEMORY",
            "source_location": "state.sweep_event after detect_sweep",
            "formula_id": None,
            "canonical_equivalent": "liquidity_sweep / sweep_detected (pipeline) — DIFFERENT geometry",
            "in_canonical_38": False,
            "stateful": True,
            "config_dependency": "max_sweep_age_candles",
            "authority_owner_today": "CRT_STATE_MACHINE_MEMORY",
            "duplication_status": "SEMANTIC_NEAR_MISS_VS_PIPELINE_SWEEP — do not alias by name",
            "migration_recommendation": "KEEP_CRT_PRIVATE until ontology maps CRT sweep vs pipeline liquidity_sweep",
            "observed_in_transition_window": False,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "displacement_candle",
            "runtime_source_class": "STATE_MEMORY",
            "source_location": "state.displacement_candle",
            "formula_id": None,
            "canonical_equivalent": None,
            "in_canonical_38": False,
            "stateful": True,
            "config_dependency": None,
            "authority_owner_today": "CRT_STATE_MACHINE_MEMORY",
            "duplication_status": "LEGITIMATE_CRT_PRIVATE_STATE",
            "migration_recommendation": "KEEP_IN_CRT",
            "observed_in_transition_window": False,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "displacement_retrace",
            "runtime_source_class": "CACHED_FEATURE",
            "source_location": "cached_features at RETEST (FM-027 via FORMULA_REGISTRY)",
            "formula_id": "FM-027",
            "canonical_equivalent": None,
            "in_canonical_38": False,
            "stateful": True,
            "config_dependency": None,
            "authority_owner_today": "CRT_CACHE + FORMULA_REGISTRY",
            "duplication_status": "CRT_EMISSION_NOT_IN_38",
            "migration_recommendation": "MSIP may surface as non-vector dimension; do not confuse with FM-021 retest_depth",
            "observed_in_transition_window": False,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "displacement_atr_ratio",
            "runtime_source_class": "CACHED_FEATURE",
            "source_location": "cached_features / try_expansion_to_retest PATCH7 (FM-028)",
            "formula_id": "FM-028",
            "canonical_equivalent": None,
            "in_canonical_38": False,
            "stateful": False,
            "config_dependency": "max_displacement_strength",
            "authority_owner_today": "CRT_LOCAL + FORMULA_REGISTRY",
            "duplication_status": "CRT_EMISSION_NOT_IN_38; parallel naming risk vs disp_strength",
            "migration_recommendation": "MSIP shadow surface; CH-002 identity preserved",
            "observed_in_transition_window": False,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "ema_fast / ema_slow",
            "runtime_source_class": "CRT_LOCAL_DERIVED",
            "source_location": "state.update_emas each process_candle; soft-conf",
            "formula_id": "FM-043 / FM-044",
            "canonical_equivalent": "ema_fast / ema_slow",
            "in_canonical_38": True,
            "stateful": True,
            "config_dependency": "ema_fast, ema_slow spans",
            "authority_owner_today": "CRT_LOCAL_EWM",
            "duplication_status": "PARALLEL_TO_PIPELINE — parity unproven in this program",
            "migration_recommendation": "PARITY_AUDIT before any binding",
            "observed_in_transition_window": False,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "depth_abs / adaptive_ceiling",
            "runtime_source_class": "CRT_LOCAL_DERIVED",
            "source_location": "try_expansion_to_retest",
            "formula_id": None,
            "canonical_equivalent": None,
            "in_canonical_38": False,
            "stateful": True,
            "config_dependency": "retest_depth_max, retest_atr_depth_fraction, retest_min_depth_atr_fraction",
            "authority_owner_today": "CRT_LOCAL_DERIVED + CONFIG",
            "duplication_status": "CRT_PRIVATE_COMPOSITION (not FM-021 gated retest_depth)",
            "migration_recommendation": "REGISTER if MSIP owns retest geometry; else KEEP_CRT_PRIVATE",
            "observed_in_transition_window": False,
            "observed_in_baseline_v1": False,
        },
        {
            "name": "38-dim FeaturePipeline vector",
            "runtime_source_class": "CANONICAL_FEATURE_VECTOR",
            "source_location": "BacktestRunner TRADE_OPENED journal attach only",
            "formula_id": "schema bulk",
            "canonical_equivalent": "CANONICAL_FEATURES",
            "in_canonical_38": True,
            "stateful": True,
            "config_dependency": None,
            "authority_owner_today": "FEATUREPIPELINE + BACKTEST_JOURNAL",
            "duplication_status": "NOT_CONSUMED_BY_CRT_GUARDS",
            "migration_recommendation": "DO_NOT_CLAIM_CRT_CONSUMER; MSIP shadow may join CRT decisions bar-by-bar without CRT reading the vector",
            "observed_in_transition_window": True,
            "observed_in_baseline_v1": True,
            "note": "Captured in traces as market representation; process_candle does not index it",
        },
    ]

    # Config keys from CRTConfig used by guards (code census)
    config_keys = [
        {"config_key": "body_ratio_min", "role": "threshold", "guards": ["G_SWEEP_DISP_BODY"], "owner": "CRTConfig/prod"},
        {"config_key": "atr_min_displacement", "role": "threshold", "guards": ["G_SWEEP_DISP_MOVE"], "owner": "CRTConfig/prod"},
        {"config_key": "atr_multiplier_min", "role": "threshold", "guards": ["G_SWEEP_DISP_WICK"], "owner": "CRTConfig/prod"},
        {"config_key": "max_sweep_age_candles", "role": "threshold", "guards": ["G_SWEEP_DISP_AGE", "SWEEP_EXPIRED"], "owner": "CRTConfig/prod"},
        {"config_key": "expansion_atr_min_distance", "role": "threshold", "guards": ["G_DISP_EXP_ATR_DIST"], "owner": "CRTConfig/prod"},
        {"config_key": "retest_depth_max", "role": "threshold", "guards": ["G_EXP_RET_CEILING"], "owner": "CRTConfig/prod"},
        {"config_key": "retest_atr_depth_fraction", "role": "threshold", "guards": ["G_EXP_RET_CEILING"], "owner": "CRTConfig/prod"},
        {"config_key": "retest_min_depth_atr_fraction", "role": "threshold", "guards": ["G_EXP_RET_MIN_DEPTH"], "owner": "CRTConfig/prod"},
        {"config_key": "max_displacement_strength", "role": "threshold", "guards": ["G_EXP_RET_DISP_STRENGTH"], "owner": "CRTConfig/prod"},
        {"config_key": "atr_period", "role": "structural_window", "guards": ["ATR compute"], "owner": "CRTConfig/prod"},
        {"config_key": "ema_fast / ema_slow", "role": "structural_window", "guards": ["soft-conf / EMA"], "owner": "CRTConfig/prod"},
        {"config_key": "max_expansion_age_candles/hours", "role": "TTL policy", "guards": ["EXPANSION_EXPIRED"], "owner": "CRTConfig/prod"},
        {"config_key": "allowed_sessions / session_windows", "role": "policy filter", "guards": ["FILTER_REJECTED off_session"], "owner": "CRTConfig/prod"},
        {"config_key": "tier_2_threshold / conf_*", "role": "soft-conf policy", "guards": ["soft-conf approve"], "owner": "CRTConfig/prod"},
    ]

    authority_matrix = {
        "_doc": "CRT_INPUT_AUTHORITY_MATRIX_V1 — every CRT-relevant input class with authority owner and MSIP migration recommendation",
        "generated_at_utc": STAMP,
        "evidence": {
            "baseline_v1_freeze": base_freeze,
            "transition_trace_v1_manifest": {
                "run_id": trans_man.get("run_id"),
                "trace_sha256": trans_man.get("trace_sha256"),
                "anchor_timestamp": trans_man.get("anchor_timestamp"),
                "target_bar_count": trans_man.get("target_bar_count"),
            },
            "coverage_corpus": "docs/governance/xauusd_crt_transition_trace/crt_executable_transition_coverage_corpus_v1.json",
            "canonical_feature_count": len(CANONICAL_FEATURES),
        },
        "architectural_finding": (
            "CRT process_candle transition logic is NOT downstream of the 38-dim FeaturePipeline vector. "
            "The vector is produced in parallel and attached at TRADE_OPENED journaling."
        ),
        "inputs": code_inputs,
        "config_keys": config_keys,
        "summary_counts": {
            "inputs_total": len(code_inputs),
            "inputs_in_canonical_38_by_name": sum(1 for i in code_inputs if i.get("in_canonical_38")),
            "inputs_legitimate_crt_private": sum(
                1 for i in code_inputs if "PRIVATE" in (i.get("duplication_status") or "")
            ),
            "inputs_parallel_to_pipeline": sum(
                1 for i in code_inputs if "PARALLEL" in (i.get("duplication_status") or "")
            ),
            "config_keys": len(config_keys),
        },
        "msip_implications": [
            "Do not implement MarketStateVector and immediately bind CRT to it.",
            "Shadow-compute MSIP alongside current CRT; compare bar-by-bar.",
            "Migrate only CRT-local market math that has proven parity with certified features.",
            "Keep state-machine memory and policy/config outside the feature layer.",
        ],
        "authority": "research/governance only — descriptive matrix; grants no production cutover authority (§6.5)",
    }

    # Transition coverage matrix
    families = coverage.get("families") or []
    # Normalize classifications
    cov_rows = []
    for fam in families:
        fid = fam.get("family_id")
        cls = fam.get("classification") or fam.get("status")
        if fam.get("status") == "OBSERVED_TRUE" or cls == "OBSERVED_TRUE":
            classification = "OBSERVED_TRUE"
        elif cls == "REACHABLE_NOT_OBSERVED" or fam.get("status") == "NOT_OBSERVED_IN_CORPUS_SCAN":
            classification = "REACHABLE_NOT_OBSERVED"
        else:
            classification = "UNKNOWN"
        cov_rows.append(
            {
                "family_id": fid,
                "classification": classification,
                "first_timestamp": fam.get("timestamp"),
                "first_candle_idx": fam.get("first_candle_idx"),
                "state_before": fam.get("state_before"),
                "state_after": fam.get("state_after"),
                "action": fam.get("action"),
                "note": fam.get("note"),
            }
        )

    # Guard-level observations from transition window
    guard_obs = {
        "OBSERVED_TRUE": coverage.get("window_guard_true") or [],
        "OBSERVED_FALSE": coverage.get("window_guard_false") or [],
    }

    # Known code transition families not necessarily in FAMILY_SPECS list completely
    transition_matrix = {
        "_doc": "CRT_TRANSITION_COVERAGE_MATRIX_V1",
        "generated_at_utc": STAMP,
        "corpus_scan": {
            "corpus_path": coverage.get("corpus_path") or trans_man.get("corpus_path"),
            "primary_window": coverage.get("primary_window"),
        },
        "classification_legend": coverage.get("classification_legend"),
        "families": cov_rows,
        "family_counts": {
            "OBSERVED_TRUE": sum(1 for r in cov_rows if r["classification"] == "OBSERVED_TRUE"),
            "REACHABLE_NOT_OBSERVED": sum(
                1 for r in cov_rows if r["classification"] == "REACHABLE_NOT_OBSERVED"
            ),
            "UNKNOWN": sum(1 for r in cov_rows if r["classification"] == "UNKNOWN"),
            "UNREACHABLE": 0,
        },
        "window_guard_observations": {
            "true_count": len(guard_obs["OBSERVED_TRUE"]),
            "false_count": len(guard_obs["OBSERVED_FALSE"]),
            "true_guard_ids": sorted({g["guard_id"] for g in guard_obs["OBSERVED_TRUE"]}),
            "false_guard_ids": sorted({g["guard_id"] for g in guard_obs["OBSERVED_FALSE"]}),
        },
        "baseline_v1": {
            "status": "FROZEN_SUCCESS",
            "selection_rule": "FIRST_16_FINALIZED_BARS",
            "trace_sha256": base_freeze.get("trace_sha256"),
            "all_range_note": "Baseline window remained RANGE — mechanism proof, not transition coverage",
        },
        "gaps_for_msip": [
            "Per-family dedicated windows (8+1+15) not yet captured for every OBSERVED_TRUE family — only full-scan first-hit index + one RANGE→SWEEP window",
            "Soft-confirmation internal guard operand traces need deeper instrumentation when RETEST→EXECUTION fires",
            "CRT ATR vs pipeline atr parity not measured",
        ],
        "authority": "research/governance only",
    }

    p1 = OUT / "CRT_INPUT_AUTHORITY_MATRIX_V1.json"
    p2 = OUT / "CRT_TRANSITION_COVERAGE_MATRIX_V1.json"
    p1.write_text(json.dumps(authority_matrix, indent=2) + "\n", encoding="utf-8")
    p2.write_text(json.dumps(transition_matrix, indent=2) + "\n", encoding="utf-8")
    print("wrote", p1)
    print("wrote", p2)
    print("family_counts", transition_matrix["family_counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
