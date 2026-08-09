"""
MSIP_SHADOW_CONTINUOUS_STATE_LAYER_DESIGN_V1 package builder.

TASK_CLASS = OBSERVATION_ONLY (design freeze only)
NO implementation, NO threshold selection, NO CRT migration, NO MarketStateVector class.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

PKG = ROOT / "docs" / "governance" / "msip_shadow_design_v1"
STAMP = datetime.now(timezone.utc).isoformat()
SCHEMA_VERSION = "1.0.0"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def w(name: str, content: str | dict) -> Path:
    PKG.mkdir(parents=True, exist_ok=True)
    p = PKG / name
    if isinstance(content, dict):
        p.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    else:
        p.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return p


def main() -> int:
    from features.feature_schema import CANONICAL_FEATURES, SCHEMA_HASH, FEATURE_ORDER_HASH

    # ── MARKET_STATE_VECTOR_SCHEMA_V1 ──
    dimensions = [
        {
            "dimension_id": "MSD-STRUCTURE",
            "name": "structure_state",
            "semantic": "Causal swing/structure regime snapshot (HH/LL/BOS/sweep presence)",
            "dtype": "object",
            "encoding": {
                "higher_high": "int8_0_1",
                "lower_low": "int8_0_1",
                "break_of_structure": "int8_neg1_0_1",
                "liquidity_sweep": "int8_neg1_0_1",
                "sweep_detected": "int8_0_1",
            },
            "nullability": "NaN/missing only if source feature missing; production pipeline assumes valid bars",
            "temporal": "same_bar continuous; causal publication delay on swings (FC1-A)",
            "confidence_representation": "optional float32 confidence ∈[0,1] per subfield; default 1.0 when exact",
            "what_feed_candidates": [
                "swing_high", "swing_low", "higher_high", "lower_low",
                "break_of_structure", "liquidity_sweep", "sweep_detected", "double_sweep",
            ],
            "not_in_vector": ["CRT active_range refs", "CRT sweep_event object", "candidate_id"],
        },
        {
            "dimension_id": "MSD-LIQUIDITY",
            "name": "liquidity_state",
            "semantic": "ATR-normalized distance/pressure to structural levels",
            "dtype": "object",
            "encoding": {
                "liquidity_distance": "float32_ge0",
                "liquidity_pressure_score": "float32",
            },
            "nullability": "NaN when atr*close<=0 or no finite level (FM-025 policy)",
            "temporal": "same_bar continuous; depends on causal swings/BOS",
            "confidence_representation": "1.0 if finite; 0.0 if NaN source",
            "what_feed_candidates": ["liquidity_distance", "liquidity_pressure_score", "atr", "close"],
            "not_in_vector": ["CRT range h_ref/l_ref as private levels unless published as WHAT"],
            "parity_notes": "FM-025 provenance residual (UNRESOLVED_REMEDIATED) does not block shadow observation",
        },
        {
            "dimension_id": "MSD-VOLATILITY",
            "name": "volatility_state",
            "semantic": "Canonical volatility regime + supporting ATR/vol ratio",
            "dtype": "object",
            "encoding": {
                "volatility_regime": "int8_0_1_2",
                "atr": "float32",
                "volatility_ratio": "float32",
            },
            "nullability": "warmup NaN for atr/ratio; regime may default per pipeline NaN→2 policy",
            "temporal": "rolling causal (ATR14, rank200 for regime)",
            "confidence_representation": "1.0 finite; 0.5 during warmup",
            "what_feed_candidates": ["volatility_regime", "atr", "true_range", "volatility_ratio"],
            "not_in_vector": ["CRT-local atr until parity audit PASS"],
            "parity_gate": "CRT_LOCAL_MATH_PARITY_AUDIT_V1 must pass before deprecating CRT-local atr",
        },
        {
            "dimension_id": "MSD-SESSION",
            "name": "session_state",
            "semantic": "Canonical pipeline session code + hour",
            "dtype": "object",
            "encoding": {
                "session": "int8_0_1_2",
                "hour_of_day": "int8_0_23",
            },
            "nullability": "invalid timestamps fail upstream (no soft NaT)",
            "temporal": "same_bar pure transform of timestamp",
            "confidence_representation": "1.0",
            "what_feed_candidates": ["session", "hour_of_day", "timestamp"],
            "not_in_vector": [
                "SESSION_MAP permutations",
                "dashboard 1-based labels",
                "CRT allowed_sessions policy decisions",
            ],
            "encoding_debt": "consumer encoding mismatches remain non-blocking for shadow emission",
        },
        {
            "dimension_id": "MSD-TREND",
            "name": "trend_state",
            "semantic": "Canonical trend strength + bias; not dual_engine abs(ema_spread)",
            "dtype": "object",
            "encoding": {
                "trend_strength": "float32_signed",
                "trend_bias": "int8_neg1_0_1",
                "ema_fast": "float32",
                "ema_slow": "float32",
            },
            "nullability": "warmup NaN for nested rolling strength",
            "temporal": "rolling causal",
            "confidence_representation": "1.0 finite; 0.5 warmup",
            "what_feed_candidates": ["trend_strength", "trend_bias", "ema_fast", "ema_slow"],
            "not_in_vector": ["dual_engine local trend_strength", "CRT EMA until parity PASS"],
            "parity_gate": "CRT_LOCAL_MATH_PARITY_AUDIT_V1 for ema_fast/ema_slow",
        },
        {
            "dimension_id": "MSD-CANDLE_QUALITY",
            "name": "candle_quality_state",
            "semantic": "Body/range geometry quality (FM-010 body_ratio and related)",
            "dtype": "object",
            "encoding": {
                "body_ratio": "float32_0_1",
                "body_size": "float32",
                "wick_size": "float32",
            },
            "nullability": "finite under production OHLC",
            "temporal": "same_bar",
            "confidence_representation": "1.0",
            "what_feed_candidates": ["body_ratio", "body_size", "wick_size", "upper_wick", "lower_wick"],
            "not_in_vector": ["CRT displacement gate decision (HOW)"],
            "parity_gate": "body_ratio CRT Candle property vs pipeline FM-010 parity",
        },
        {
            "dimension_id": "MSD-CRT_PHASE_OBS",
            "name": "crt_phase_observation",
            "semantic": "READ-ONLY observation of current CRT state name if available to shadow runner",
            "dtype": "object",
            "encoding": {"crt_state": "enum_string_or_null", "observed": "bool"},
            "nullability": "null when CRT not running / not bound for observation",
            "temporal": "same_bar after CRT process when co-running; optional",
            "confidence_representation": "1.0 when observed else 0.0",
            "what_feed_candidates": [],
            "not_in_vector": [
                "ability to mutate CRT",
                "candidate private memory dump",
            ],
            "role": "comparison join key only — NOT a MarketState driver of CRT",
        },
    ]

    msv_schema = {
        "schema_id": "MARKET_STATE_VECTOR_SCHEMA_V1",
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": STAMP,
        "vector_name": "MarketStateVector",
        "authority": "research/governance design only — not implemented",
        "task_class": "OBSERVATION_ONLY",
        "architecture_decision": "C",
        "architecture_ref": "docs/governance/crt_architecture_adjudication_v1/ARCHITECTURE_DECISION_RECORD_V1.json",
        "top_level_fields": {
            "schema_version": "string semver",
            "symbol": "string",
            "timeframe": "string",
            "bar_timestamp": "ISO-8601 or pipeline timestamp string",
            "bar_index": "int optional",
            "dimensions": "object map dimension_id → dimension payload",
            "provenance": "see SHADOW_PROVENANCE_CONTRACT_V1",
            "shadow_flags": {
                "affects_crt": "MUST_BE_FALSE",
                "affects_execution": "MUST_BE_FALSE",
                "affects_events": "MUST_BE_FALSE",
            },
        },
        "dimensions": dimensions,
        "explicitly_not_in_market_state_vector": [
            "CRT EngineState private fields (sweep_event, displacement_candle, pending_*, active_trade)",
            "candidate_id / death_reason / single-candidate ownership",
            "entry/SL/TP/order intents",
            "EngineRunner fusion scores as market state",
            "economic expectancy / PnL",
            "session admission decisions (HOW)",
            "thresholds themselves (HOW lives in interpretation config)",
            "SUPERSEDED vector slots as authority (ema_spread/momentum_score are historical 38-dim, not MSIP authority)",
        ],
        "versioning_rules": {
            "schema_version_bump": "breaking dimension remove/rename/type change",
            "additive_dimension": "minor bump allowed if null-safe for old readers",
            "config_version": "independent of schema_version; recorded in provenance",
        },
        "canonical_feature_context": {
            "canonical_feature_dim": 38,
            "schema_hash": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH,
            "note": "MSIP prefers pipeline-emitted governed features; does not require CRT to consume all 38",
        },
    }
    w("MARKET_STATE_VECTOR_SCHEMA_V1.json", msv_schema)
    w("MARKET_STATE_VECTOR_SCHEMA_V1.md", _schema_md(msv_schema))

    # ── DIMENSION AUTHORITY MATRIX ──
    dim_auth = {
        "schema_id": "MARKET_STATE_DIMENSION_AUTHORITY_MATRIX_V1",
        "generated_at_utc": STAMP,
        "rows": [],
    }
    for d in dimensions:
        for feat in d.get("what_feed_candidates") or ["(none)"]:
            in38 = feat in CANONICAL_FEATURES
            parity = d.get("parity_gate")
            dim_auth["rows"].append(
                {
                    "dimension_id": d["dimension_id"],
                    "dimension_name": d["name"],
                    "what_quantity": feat,
                    "in_canonical_38": in38,
                    "fm_id_hint": _fm_hint(feat),
                    "producer_authority": "FeaturePipeline / registry" if feat != "(none)" else "CRT observation optional",
                    "shadow_binding": "READ_ONLY_FROM_FEATURE_SURFACE",
                    "crt_local_duplicate": feat in {
                        "body_ratio", "wick_size", "atr", "ema_fast", "ema_slow",
                    },
                    "parity_audit_required_before_deprecating_crt_local": bool(
                        parity and feat in {"body_ratio", "wick_size", "atr", "ema_fast", "ema_slow"}
                    ),
                    "how_policy_allowed": "interpretation bands/labels only; not dimension raw identity",
                    "must_not_include": d.get("not_in_vector"),
                }
            )
    w("MARKET_STATE_DIMENSION_AUTHORITY_MATRIX_V1.json", dim_auth)
    w("MARKET_STATE_DIMENSION_AUTHORITY_MATRIX_V1.md", _dim_auth_md(dim_auth))

    # ── INTERPRETATION CONFIG SCHEMA ──
    interp = {
        "schema_id": "INTERPRETATION_CONFIG_SCHEMA_V1",
        "generated_at_utc": STAMP,
        "config_section_name": "msip_shadow",
        "load_policy": "strict _require when section present; absent section = shadow disabled",
        "dynamic_loading": {
            "allowed": True,
            "semantics": "reload interpretation config between runs only unless explicit hot-reload plan; no silent mid-bar mutation",
            "not_authorized_now": "hot-reload implementation code",
        },
        "fields": {
            "enabled": {"type": "bool", "default_when_absent": False, "class": "HOW"},
            "schema_version_required": {"type": "string", "example": "1.0.0"},
            "dimensions": {
                "type": "object",
                "per_dimension": {
                    "enabled": "bool",
                    "source_features": "list[str] subset of WHAT feeds",
                    "label_bands": "optional ordered thresholds for categorical labels ONLY (HOW)",
                    "instrument_overrides": "optional map instrument → band overrides",
                    "timeframe_overrides": "optional map timeframe → band overrides",
                },
            },
            "comparison": {
                "emit_disagreement_events": "bool default true",
                "crt_phase_observation_enabled": "bool default true",
            },
            "output": {
                "path_template": "results/msip_shadow/{run_id}/market_state.jsonl",
                "include_provenance": "bool default true",
            },
        },
        "validation_rules": [
            "enabled true requires non-empty dimensions with at least one enabled",
            "source_features must exist in FeaturePipeline / CANONICAL or registered non-vector WHAT",
            "label_bands must be monotonic finite",
            "no field may authorize CRT mutation",
            "no field may set trade thresholds for CRTConfig",
        ],
        "ownership": {
            "WHAT": "ontology + feature_pipeline + formula_registry",
            "HOW": "msip_shadow config section only",
            "WHO": "shadow emitter / research consumers — not CRTEngine until BEHAVIOR_CHANGE_AUTHORIZED migration",
        },
        "explicitly_out_of_scope": [
            "CRTConfig body_ratio_min / retest_* / TTL knobs",
            "concurrent candidate policy",
            "EngineRunner fusion weights",
        ],
    }
    w("INTERPRETATION_CONFIG_SCHEMA_V1.json", interp)
    w("INTERPRETATION_CONFIG_SCHEMA_V1.md", _interp_md(interp))

    # ── SHADOW RUNTIME BINDING ──
    binding = {
        "schema_id": "SHADOW_RUNTIME_BINDING_SPEC_V1",
        "generated_at_utc": STAMP,
        "execution_model": {
            "stream": "same OHLCV candle stream as backtest/live",
            "order": [
                "1. Load OHLCV bar",
                "2. FeaturePipeline already-built series lookup OR incremental if live (design allows either; must be PIT)",
                "3. Optionally run CRT process_candle for comparison observation only",
                "4. Compute MarketStateVector from feature surface + interpretation config",
                "5. Emit vector + provenance",
                "6. Optionally record disagreement vs CRT observations",
            ],
            "hard_invariants": [
                "shadow_flags.affects_crt == false always",
                "shadow_flags.affects_execution == false always",
                "shadow must not call StateMachine.try_* or mutate EngineState",
                "shadow must not open/close trades",
                "shadow must not write production ACTIVE_VERSION configs",
            ],
        },
        "inputs": {
            "feature_surface": "FeaturePipeline vectors / columns (authoritative WHAT for MSIP)",
            "crt_observation": "optional read-only snapshot of CRT state name after process_candle",
            "interpretation_config": "msip_shadow section",
        },
        "outputs": {
            "market_state_jsonl": "one object per bar",
            "disagreement_jsonl": "optional",
            "run_manifest": "hashes of config, schema, corpus, commit",
        },
        "co_run_with_crt": {
            "allowed": True,
            "purpose": "comparison only",
            "crt_remains_authoritative_for": "opportunity lifecycle and trades",
        },
        "not_authorized": [
            "MarketStateVector class implementation in this design task",
            "dynamic loader coding",
            "CRT consumer migration",
            "threshold selection for CRTConfig",
        ],
    }
    w("SHADOW_RUNTIME_BINDING_SPEC_V1.json", binding)
    w("SHADOW_RUNTIME_BINDING_SPEC_V1.md", _binding_md(binding))

    # ── PROVENANCE ──
    prov = {
        "schema_id": "SHADOW_PROVENANCE_CONTRACT_V1",
        "generated_at_utc": STAMP,
        "required_fields_per_bar": {
            "schema_version": "MARKET_STATE_VECTOR_SCHEMA_V1 version",
            "config_id": "hash or version of msip_shadow config",
            "repository_commit": "git sha when known",
            "corpus_path": "if batch",
            "corpus_sha256": "if batch",
            "feature_schema_hash": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH,
            "dimension_sources": "map dimension_id → list of {feature, fm_id?, value_hash_or_value}",
            "parity_audit_refs": "list of audit artifact IDs used",
            "crt_observation": "optional {crt_state, bar_index}",
        },
        "completeness_rule": "provenance incomplete ⇒ bar status PARTIAL; cannot promote to any authority",
        "retention": "append-only JSONL; no rewrite of historical shadow runs",
    }
    w("SHADOW_PROVENANCE_CONTRACT_V1.json", prov)
    w("SHADOW_PROVENANCE_CONTRACT_V1.md", _json_md("Shadow Provenance Contract V1", prov))

    # ── CRT LOCAL MATH PARITY AUDIT PLAN ──
    parity = {
        "schema_id": "CRT_LOCAL_MATH_PARITY_AUDIT_V1",
        "generated_at_utc": STAMP,
        "status": "PLAN_FROZEN_NOT_EXECUTED",
        "task_class_when_executed": "OBSERVATION_ONLY",
        "purpose": (
            "Before any deprecation of CRT-local market math or BIND_TO_CANONICAL_FEATURE migration, "
            "prove identity/parity of CRT-local quantities vs governed FeaturePipeline / formula_registry."
        ),
        "targets": [
            {
                "quantity": "body_ratio",
                "crt_source": "Candle.body_ratio property",
                "governed_source": "FM-010 / pipeline body_ratio",
                "pass_criterion": "max abs err ≤ 1e-9 on finite bars of frozen XAUUSD Phase-1 corpus sample",
                "blocks_migration": True,
            },
            {
                "quantity": "wick_size",
                "crt_source": "Candle.wick_size",
                "governed_source": "FM-002 / pipeline wick_size",
                "pass_criterion": "exact high-low identity",
                "blocks_migration": True,
            },
            {
                "quantity": "atr",
                "crt_source": "RangeDetector.compute_atr (absolute? period atr_period)",
                "governed_source": "FM-041 pipeline atr (close-relative documented)",
                "pass_criterion": "document scale relationship; FAIL if assumed equal without transform proof",
                "blocks_migration": True,
                "note": "Likely TRANSFORM not EXACT — must not bind as identical without transform registry",
            },
            {
                "quantity": "ema_fast / ema_slow",
                "crt_source": "EngineState.update_emas",
                "governed_source": "FM-043 / FM-044 pipeline",
                "pass_criterion": "span/adjust parity proof or registered transform",
                "blocks_migration": True,
            },
        ],
        "not_in_audit": [
            "active_range / sweep_event / displacement_candle (private lifecycle)",
            "thresholds (HOW)",
        ],
        "outputs_when_run": [
            "parity report JSON with per-quantity PASS/FAIL/TRANSFORM",
            "no production CRT change",
        ],
        "authorization": "measurement only; does not authorize CRT consumer migration",
    }
    w("CRT_LOCAL_MATH_PARITY_AUDIT_V1.json", parity)
    w("CRT_LOCAL_MATH_PARITY_AUDIT_V1.md", _json_md("CRT Local Math Parity Audit V1 (plan)", parity))

    # ── COMPARISON AND DISAGREEMENT ──
    compare = {
        "schema_id": "SHADOW_COMPARISON_AND_DISAGREEMENT_SPEC_V1",
        "generated_at_utc": STAMP,
        "purpose": "Define what evidence permits later A/B/consumer-migration decisions",
        "comparison_unit": "bar (timestamp, symbol, timeframe)",
        "metrics": [
            {
                "id": "COV-01",
                "name": "shadow_emission_coverage",
                "definition": "fraction of bars with COMPLETE provenance MarketStateVector",
                "gate_for_next": "≥ 0.99 on declared population after warmup",
            },
            {
                "id": "DET-01",
                "name": "determinism",
                "definition": "byte-identical shadow JSONL on same inputs/config/commit",
                "gate_for_next": "PASS two-run equality",
            },
            {
                "id": "PROV-01",
                "name": "provenance_completeness",
                "definition": "required provenance fields present",
                "gate_for_next": "100% COMPLETE or explicit PARTIAL taxonomy",
            },
            {
                "id": "CMP-01",
                "name": "crt_state_join_rate",
                "definition": "fraction of bars with crt_phase_observation when co-running",
                "gate_for_next": "≥ 0.99 when CRT co-run enabled",
            },
            {
                "id": "DIS-01",
                "name": "disagreement_rate_by_taxonomy",
                "definition": "counts of disagreement classes below",
                "gate_for_next": "reported; no automatic fail threshold (architecture not trade-count)",
            },
        ],
        "disagreement_taxonomy": [
            {
                "class": "D-OBS-ABSENT",
                "meaning": "shadow dimension null while CRT used related local math",
            },
            {
                "class": "D-SCALE-MISMATCH",
                "meaning": "parity audit TRANSFORM not applied; values disagree in scale",
            },
            {
                "class": "D-LABEL-POLICY",
                "meaning": "HOW label bands differ from CRT threshold decisions (expected; not a bug)",
            },
            {
                "class": "D-STRUCTURE-VS-SWEEP",
                "meaning": "pipeline liquidity_sweep vs CRT detect_sweep geometry diverge",
            },
            {
                "class": "D-SESSION-ENCODING",
                "meaning": "canonical session vs CRT session policy path diverge",
            },
            {
                "class": "D-LIFECYCLE-ONLY",
                "meaning": "CRT private lifecycle event with no continuous-state analogue (expected)",
            },
        ],
        "market_regime_coverage": {
            "requirement": "document coverage across high/low vol regimes and sessions on frozen corpus",
            "not_required_for_design_freeze": "full multi-year multi-instrument before design contract",
            "required_before_consumer_migration": True,
        },
        "criteria_for_later_options": {
            "A_policy_research": "shadow coverage+determinism PASS; then instrument-specific HOW experiments EXPLORATORY",
            "B_concurrent_candidates": "evidence that single-candidate suppression is binding after continuous-state measurement exists",
            "CRT_consumer_migration": "parity audits PASS; BEHAVIOR_CHANGE_AUTHORIZED plan; shadow comparison shows stable intended coupling; CRT reopen conditions evaluated if lifecycle changes",
        },
    }
    w("SHADOW_COMPARISON_AND_DISAGREEMENT_SPEC_V1.json", compare)
    w("SHADOW_COMPARISON_AND_DISAGREEMENT_SPEC_V1.md", _json_md("Shadow Comparison & Disagreement Spec V1", compare))

    # ── PROMOTION GATES ──
    gates = {
        "schema_id": "MSIP_SHADOW_PROMOTION_GATES_V1",
        "generated_at_utc": STAMP,
        "note": "These gates promote *design readiness* and *shadow run quality*, not production CRT authority",
        "gates": [
            {
                "id": "G-DESIGN-01",
                "name": "design_contract_frozen",
                "criterion": "This package manifest complete and owner-accepted",
                "status": "PENDING_OWNER_ACCEPTANCE",
            },
            {
                "id": "G-IMPL-01",
                "name": "implementation_may_start",
                "criterion": "All design artifacts agree; TASK_CLASS for coding declared; still shadow-only",
                "status": "NOT_PASSED",
                "blocks": "MarketStateVector class coding",
            },
            {
                "id": "G-SHADOW-01",
                "name": "shadow_run_quality",
                "criterion": "COV-01, DET-01, PROV-01 PASS on declared population",
                "status": "NOT_PASSED",
            },
            {
                "id": "G-PARITY-01",
                "name": "crt_local_math_parity",
                "criterion": "CRT_LOCAL_MATH_PARITY_AUDIT_V1 executed with PASS/TRANSFORM registry",
                "status": "NOT_PASSED",
                "blocks": "deprecating CRT-local market math",
            },
            {
                "id": "G-MIG-01",
                "name": "crt_consumer_migration",
                "criterion": "BEHAVIOR_CHANGE_AUTHORIZED plan + comparison evidence + reopen if needed",
                "status": "NOT_PASSED",
                "blocks": "CRT cutover",
            },
        ],
        "explicit_non_gates": [
            "trade count increase",
            "historical baseline hash equality",
            "economic expectancy",
        ],
    }
    w("MSIP_SHADOW_PROMOTION_GATES_V1.json", gates)
    w("MSIP_SHADOW_PROMOTION_GATES_V1.md", _json_md("MSIP Shadow Promotion Gates V1", gates))

    # ── DESIGN CONTRACT (umbrella) ──
    contract = _design_contract_md(msv_schema, binding, gates)
    w("MSIP_SHADOW_DESIGN_CONTRACT_V1.md", contract)
    # also root governance pointer
    (ROOT / "docs/governance/MSIP_SHADOW_DESIGN_CONTRACT_V1.md").write_text(
        contract, encoding="utf-8"
    )

    # ── Owner acceptance stub ──
    accept = {
        "schema_id": "OWNER_ACCEPTANCE_DECISION_C_AND_SHADOW_DESIGN",
        "generated_at_utc": STAMP,
        "architecture_decision": "C",
        "architecture_decision_status": "PENDING_OWNER_ACCEPTANCE",
        "d_wording_correction": (
            "D requires explicit CRT-boundary reopen authority and is unsupported by current evidence; "
            "CLOSED does not make replacement permanently impossible"
        ),
        "shadow_design_status": "FROZEN_PENDING_OWNER_ACCEPTANCE",
        "implementation_authorized": False,
        "threshold_selection_authorized": False,
        "crt_migration_authorized": False,
    }
    w("OWNER_ACCEPTANCE_STUB_V1.json", accept)

    # ── README ──
    w(
        "README.md",
        f"""# MSIP Shadow Continuous State Layer Design V1

**Status:** FROZEN design package (pending owner acceptance)  
**Generated:** {STAMP}  
**Architecture:** Decision **C** (continuous market-state observation separate from CRT lifecycle)  
**Task class:** OBSERVATION_ONLY  

## Do not implement yet

No `MarketStateVector` class, no dynamic loader coding, no CRT migration, no threshold selection
until owner acceptance and **G-IMPL-01**.

## Artifacts

See `PACKAGE_MANIFEST.json`.

## Related

- Architecture decision: `docs/governance/crt_architecture_adjudication_v1/`
- Behavior policy: `docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`
""",
    )

    # manifest
    files = sorted(p for p in PKG.rglob("*") if p.is_file() and p.name != "PACKAGE_MANIFEST.json")
    file_list = []
    agg = hashlib.sha256()
    for p in files:
        rel = str(p.relative_to(PKG)).replace("\\", "/")
        h = sha256_file(p)
        file_list.append({"path": rel, "sha256": h, "bytes": p.stat().st_size})
        agg.update(f"{h}  {rel}\n".encode())
    manifest = {
        "_doc": "MSIP_SHADOW_CONTINUOUS_STATE_LAYER_DESIGN_V1 frozen package",
        "generated_at_utc": STAMP,
        "package_path": "docs/governance/msip_shadow_design_v1",
        "architecture_decision": "C",
        "implementation_authorized": False,
        "threshold_selection_authorized": False,
        "files": file_list,
        "package_aggregate_sha256": agg.hexdigest(),
    }
    (PKG / "PACKAGE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("PACKAGE", PKG)
    print("AGGREGATE", manifest["package_aggregate_sha256"])
    print("FILES", len(file_list))
    return 0


def _fm_hint(feat: str) -> str | None:
    hints = {
        "body_ratio": "FM-010",
        "wick_size": "FM-002",
        "body_size": "FM-001",
        "atr": "FM-041",
        "true_range": "FM-040",
        "ema_fast": "FM-043",
        "ema_slow": "FM-044",
        "liquidity_distance": "FM-025",
        "liquidity_pressure_score": "FM-026",
        "volatility_ratio": "FM-024",
        "swing_high": "FM-045",
        "swing_low": "FM-046",
    }
    return hints.get(feat)


def _schema_md(s: dict) -> str:
    lines = [
        "# MarketStateVector Schema V1",
        "",
        f"Version `{s['schema_version']}` · Decision **C** · Not implemented",
        "",
        "## Dimensions",
        "",
    ]
    for d in s["dimensions"]:
        lines.append(f"### {d['dimension_id']} — `{d['name']}`")
        lines.append("")
        lines.append(d["semantic"])
        lines.append("")
        lines.append(f"- feeds: `{d.get('what_feed_candidates')}`")
        lines.append(f"- not in vector: `{d.get('not_in_vector')}`")
        lines.append("")
    lines += ["## Explicitly excluded", ""]
    for x in s["explicitly_not_in_market_state_vector"]:
        lines.append(f"- {x}")
    return "\n".join(lines) + "\n"


def _dim_auth_md(m: dict) -> str:
    lines = [
        "# Market State Dimension Authority Matrix V1",
        "",
        "| dim | feature | in38 | crt_dup | parity_before_deprecate |",
        "|---|---|---|---|---|",
    ]
    for r in m["rows"]:
        lines.append(
            f"| {r['dimension_id']} | `{r['what_quantity']}` | {r['in_canonical_38']} | "
            f"{r['crt_local_duplicate']} | {r['parity_audit_required_before_deprecating_crt_local']} |"
        )
    return "\n".join(lines) + "\n"


def _interp_md(m: dict) -> str:
    return (
        f"# Interpretation Config Schema V1\n\n"
        f"Section: `{m['config_section_name']}`  \n"
        f"Load: {m['load_policy']}\n\n"
        f"See JSON for field dictionary. HOW only — never mutates CRT.\n"
    )


def _binding_md(m: dict) -> str:
    lines = ["# Shadow Runtime Binding Spec V1", "", "## Hard invariants", ""]
    for x in m["execution_model"]["hard_invariants"]:
        lines.append(f"- {x}")
    lines += ["", "## Order", ""]
    for x in m["execution_model"]["order"]:
        lines.append(f"- {x}")
    return "\n".join(lines) + "\n"


def _json_md(title: str, obj: dict) -> str:
    return f"# {title}\n\n```json\n{json.dumps(obj, indent=2)}\n```\n"


def _design_contract_md(schema: dict, binding: dict, gates: dict) -> str:
    return f"""# MSIP Shadow Design Contract V1

**Status:** FROZEN design package — **PENDING_OWNER_ACCEPTANCE**  
**Generated:** {STAMP}  
**Architecture decision:** **C** — continuous market-state observation separate from CRT opportunity lifecycle  
**Task class:** OBSERVATION_ONLY  

---

## 1. Purpose

Define the **executable contract** for the next phase  
`MSIP_SHADOW_CONTINUOUS_STATE_LAYER_DESIGN` **before any implementation**.

This contract answers five questions:

1. What is MarketStateVector?  
2. Which governed WHAT quantities feed each dimension?  
3. What belongs to HOW?  
4. How does shadow execution work?  
5. What evidence permits the next decision (A / B / CRT migration)?

---

## 2. Non-goals (hard)

- No `MarketStateVector` class coding until **G-IMPL-01**  
- No dynamic-loader coding  
- No CRT migration / cutover  
- No threshold selection for CRTConfig  
- No concurrent-candidate implementation  
- No trade-count optimization as success metric  
- No restoration of historical baseline hash golden equality  

---

## 3. MarketStateVector (summary)

See `MARKET_STATE_VECTOR_SCHEMA_V1.json`.

Dimensions: structure, liquidity, volatility, session, trend, candle_quality, optional crt_phase_observation (read-only).

**Must not include:** CRT private lifecycle memory, orders, fusion scores, economic metrics, HOW thresholds as identity.

---

## 4. WHAT feeds

See `MARKET_STATE_DIMENSION_AUTHORITY_MATRIX_V1.json`.

Primary producer: **FeaturePipeline / formula registry**.  
CRT-local ATR/EMA/body_ratio/wick: **parity audit required** before deprecating CRT-local use (`CRT_LOCAL_MATH_PARITY_AUDIT_V1`).

---

## 5. HOW

See `INTERPRETATION_CONFIG_SCHEMA_V1.json` (`msip_shadow` section).

HOW = bands, enables, instrument/timeframe overrides, comparison flags.  
HOW must not mutate CRT lifecycle or production admission.

---

## 6. Shadow execution

See `SHADOW_RUNTIME_BINDING_SPEC_V1.json`.

Hard invariant: **shadow cannot affect CRT state, events, trades, or execution**.

Provenance: `SHADOW_PROVENANCE_CONTRACT_V1.json`.

---

## 7. Comparison evidence for later decisions

See `SHADOW_COMPARISON_AND_DISAGREEMENT_SPEC_V1.json`.

Later **A** (policy research), **B** (concurrent candidates), or CRT consumer migration each have explicit criteria — none are automatic.

---

## 8. Promotion gates

See `MSIP_SHADOW_PROMOTION_GATES_V1.json`.

| Gate | Blocks |
|---|---|
| G-DESIGN-01 | Proceeding without owner acceptance |
| G-IMPL-01 | Coding MarketStateVector |
| G-SHADOW-01 | Claiming shadow quality |
| G-PARITY-01 | Deprecating CRT-local math |
| G-MIG-01 | CRT consumer cutover |

---

## 9. Option D wording (architecture package correction)

**D requires explicit CRT-boundary reopen authority and is unsupported by current evidence.**  
CLOSED does **not** make replacement permanently impossible; it makes D unauthorized until reopen conditions and new evidence.

---

## 10. Project state

```text
ARCHITECTURE QUESTION → DECIDED (C)
CURRENT CRT → remains authoritative opportunity lifecycle
NEXT PHASE → MSIP_SHADOW design (this package)
IMPLEMENTATION → NOT YET AUTHORIZED
```

---

## 11. Authority

Design freeze only. Grants no production authority, no economic claims, no CRT reopen.
"""


if __name__ == "__main__":
    raise SystemExit(main())
