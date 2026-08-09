#!/usr/bin/env python3
"""Phase 1 RUN 1.5A — Quantity role adjudication only (142 RUN-1 records).

Does not expand the denominator, does not define canonical formulas,
does not modify production feature code.

  python scripts/analysis/phase1_run15a_quantity_role_adjudication.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GOV = ROOT / "docs" / "governance"
DATE = "2026-07-10"
UNIVERSE = GOV / f"phase1_run1_feature_universe_census-{DATE}.json"

PRIMARY_ROLES = {
    "CANONICAL_FEATURE_CANDIDATE",
    "CANONICAL_SOURCE_FIELD",
    "IMPLEMENTATION_INTERMEDIATE",
    "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
    "RESEARCH_ONLY_QUANTITY",
    "TRAINING_ONLY_QUANTITY",
    "LIVE_ONLY_QUANTITY",
    "LABEL_OR_TARGET",
    "STATE_OR_CACHE",
    "DIAGNOSTIC_OR_METRIC",
    "INTENTIONAL_ALIAS",
    "DUPLICATE_IMPLEMENTATION",
    "PROVEN_UNREACHABLE_OR_ARCHIVED",
    "BLOCKED",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git() -> tuple[str, bool]:
    try:
        c = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip()
        d = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True, cwd=ROOT).strip())
        return c, d
    except Exception:
        return "UNKNOWN", True


def _base(q: dict, role: str, **extra: Any) -> dict:
    rec = {
        "quantity_id": q["id"],
        "names": list(q.get("names") or []),
        "run1_class": q.get("class"),
        "formula_summary": q.get("formula"),
        "source_fields": q.get("source_fields"),
        "impl": q.get("impl"),
        "PRIMARY_ROLE": role,
        "producers": extra.pop("producers", list(q.get("impl") or [])[:8]),
        "consumers": extra.pop("consumers", []),
        "direct_inputs": extra.pop("direct_inputs", q.get("source_fields") or []),
        "crosses_subsystem_boundary": extra.pop("crosses_subsystem_boundary", False),
        "persisted": extra.pop("persisted", False),
        "model_input": extra.pop("model_input", False),
        "training_input": extra.pop("training_input", False),
        "is_label_or_target": extra.pop("is_label_or_target", False),
        "temporary_impl_state": extra.pop("temporary_impl_state", False),
        "state_or_cache": extra.pop("state_or_cache", False),
        "diagnostic": extra.pop("diagnostic", False),
        "model_or_subsystem_specific": extra.pop("model_or_subsystem_specific", False),
        "research_only": extra.pop("research_only", False),
        "training_only": extra.pop("training_only", False),
        "live_only": extra.pop("live_only", False),
        "alias_of": extra.pop("alias_of", None),
        "duplicate_of_quantity_id": extra.pop("duplicate_of_quantity_id", None),
        "unreachable_or_archived": extra.pop("unreachable_or_archived", False),
        "evidence_refs": extra.pop("evidence_refs", list(q.get("evidence") or [])),
        "adversarial_review": extra.pop("adversarial_review", {}),
        "notes": extra.pop("notes", ""),
    }
    rec.update(extra)
    return rec


def adjudicate_curated(q: dict) -> dict:
    qid = q["id"]

    # --- Source fields ---
    if qid in ("Q-RAW-OPEN", "Q-RAW-HIGH", "Q-RAW-LOW", "Q-RAW-CLOSE"):
        return _base(
            q,
            "CANONICAL_SOURCE_FIELD",
            producers=["OHLCV corpus / CandleLoader / FeaturePipeline passthrough"],
            consumers=["FeaturePipeline", "all structure/indicator features", "CRT", "research"],
            crosses_subsystem_boundary=True,
            persisted=True,
            model_input=True,
            training_input=True,
            notes="Raw OHLCV price field; also appears in 38-vector by design",
            adversarial_review={
                "not_intermediate": True,
                "not_model_specific": True,
                "not_label": True,
                "shared_source": True,
            },
        )

    if qid == "Q-VOL-TICK":
        return _base(
            q,
            "CANONICAL_SOURCE_FIELD",
            producers=["MT5 tick volume / FeaturePipeline passthrough when non-all-zero"],
            consumers=["volume_ratio", "volume_spike", "Feature vector consumers"],
            crosses_subsystem_boundary=True,
            persisted=True,
            model_input=True,
            training_input=True,
            known_defects=["T-003 may rewrite under same name (see Q-VOL-PROXY-T003)"],
            notes="Intended source semantic TICK_VOLUME on frozen XAUUSD",
            adversarial_review={"could_be_proxy": "only under T-003 mutation"},
        )

    if qid == "Q-VOL-PROXY-T003":
        return _base(
            q,
            "DUPLICATE_IMPLEMENTATION",
            duplicate_of_quantity_id="Q-VOL-RANGE-PROXY-SEPARATE",
            same_name_or_different_name="different_name_vs_proxy_id_but_collides_with_volume",
            formula_relationship="same high-low proxy math as intended separate proxy; wrongly stored under volume",
            temporal_relationship="t",
            source_semantic_relationship="price_range_proxy vs tick_volume",
            known_equivalent_or_divergent="equivalent to range proxy math; divergent from tick volume",
            producers=["FeaturePipeline.compute_volume_features T-003 branch"],
            consumers=["same as volume column consumers when activated"],
            crosses_subsystem_boundary=True,
            notes="Same-name substitution defect — not intentional alias of tick volume",
            evidence_refs=["PASS-A", "feature_pipeline T-003", "FC-0 SEP-B"],
            adversarial_review={"not_intentional_alias_of_tick": True},
        )

    if qid == "Q-VOL-RANGE-PROXY-SEPARATE":
        return _base(
            q,
            "CANONICAL_FEATURE_CANDIDATE",
            shared_boundary_evidence=(
                "Contract-separated identity FEAT-VOLUME_RANGE_PROXY; intended to cross "
                "pipeline/consumers as explicit proxy distinct from tick volume"
            ),
            producers=["FeatureContract intent / not yet exclusive production path"],
            consumers=["future consumers declaring range-proxy semantic"],
            crosses_subsystem_boundary=True,
            known_collisions=["currently may only exist as T-003 under volume name"],
            current_semantic_identity="high-low price range proxy",
            evidence_refs=["feature_contract_v1 SEP-B", "FC-0"],
            adversarial_review={
                "could_be_intermediate": False,
                "could_be_model_specific": False,
                "shared_intent": True,
            },
        )

    # --- Config-dependent temporal variants of swings / vol regime ---
    if qid == "Q-SWING-CAUSAL-ENV":
        return _base(
            q,
            "DUPLICATE_IMPLEMENTATION",
            duplicate_of_quantity_id="Q-SWING-CENTER",
            same_name_or_different_name="same_name",
            formula_relationship="center swing + shift(k) under TRUST_SWING_CAUSAL=1",
            temporal_relationship="causal delayed vs leaking publish-at-t",
            source_semantic_relationship="same high/low",
            known_equivalent_or_divergent="divergent temporal publication",
            producers=["FeaturePipeline env branch"],
            consumers=["same structure consumers when env set"],
            evidence_refs=["feature_pipeline TRUST_SWING_CAUSAL"],
        )

    if qid in ("Q-VR-EXPAND", "Q-VR-ROLL"):
        return _base(
            q,
            "DUPLICATE_IMPLEMENTATION",
            duplicate_of_quantity_id="Q-VR-GLOBAL",
            same_name_or_different_name="same_name",
            formula_relationship="expanding or rolling ATR rank vs global rank",
            temporal_relationship="causal vs full-batch",
            source_semantic_relationship="same atr_14",
            known_equivalent_or_divergent="divergent temporal / values",
            producers=["FeaturePipeline TRUST_VOLREGIME_CAUSAL"],
            consumers=["volatility_regime consumers when env set"],
            evidence_refs=["feature_pipeline compute_volatility_regime", "FC-0.5"],
        )

    if qid == "Q-BODY-RATIO-NONCANON-LIVE":
        return _base(
            q,
            "DUPLICATE_IMPLEMENTATION",
            duplicate_of_quantity_id="Q-BODY-RATIO",
            same_name_or_different_name="same_name",
            formula_relationship="body/total_wick vs body/range",
            temporal_relationship="t",
            source_semantic_relationship="same OHLC different formula",
            known_equivalent_or_divergent="divergent",
            producers=["live_engine_hook non-canonical path"],
            consumers=["live fusion path conditional"],
            live_only=True,
            model_or_subsystem_specific=True,
            evidence_refs=["F-047 GD-001", "live_engine_hook"],
        )

    # --- Intermediates ---
    if qid in ("Q-INTER-LAST-SWING-H", "Q-INTER-LAST-SWING-L", "Q-INTER-RETEST-FLAG"):
        return _base(
            q,
            "IMPLEMENTATION_INTERMEDIATE",
            producers=["FeaturePipeline.compute_structure_liquidity"],
            consumers=["higher_high/lower_low/BOS/liquidity/retest_depth within pipeline"],
            temporary_impl_state=True,
            crosses_subsystem_boundary=False,
            known_temporal_issues=["inherits centered swing leak"],
            adversarial_review={
                "crosses_boundary": False,
                "persisted_in_38_vector": False,
                "consumed_outside_pipeline": "not as public vector member",
                "model_input_direct": False,
                "semantic_dependents_inside_pipeline": True,
            },
            notes="Not in CANONICAL_FEATURES 38-vector; feeds structure features",
            evidence_refs=["feature_pipeline", "FC-0.5 graph intermediates"],
        )

    # --- Intentional multi-site body_ratio ---
    if qid == "Q-BODY-RATIO":
        return _base(
            q,
            "CANONICAL_FEATURE_CANDIDATE",
            shared_boundary_evidence=(
                "body_ratio is in 38-vector; consumed by CRT, BitNet feature map, "
                "FeatureMonitor drift cols, live snapshots; unified via candle_math F-046"
            ),
            producers=["candle_math", "FeaturePipeline", "CRT"],
            consumers=["CRT", "BitNet (if enabled)", "FeatureMonitor", "backtest vector"],
            crosses_subsystem_boundary=True,
            model_input=True,
            training_input=True,
            persisted=True,
            current_semantic_identity="body/range [0,1]",
            known_collisions=["live non-canonical body/total_wick path Q-BODY-RATIO-NONCANON-LIVE"],
            evidence_refs=["F-046", "CANONICAL_FEATURES", "candle_math"],
            adversarial_review={
                "could_be_intermediate": False,
                "could_be_model_specific": False,
                "could_be_duplicate": "live path is separate record",
                "shared": True,
            },
        )

    # --- FM CRT-specific distinct formulas ---
    if qid == "Q-FM028":
        return _base(
            q,
            "CANONICAL_FEATURE_CANDIDATE",
            shared_boundary_evidence=(
                "CH-002 displacement_atr_ratio FM-028 emitted in CRT cached_features; "
                "distinct math from pipeline disp_strength FM-020; BitNet may alias names"
            ),
            producers=["derived_math.displacement_atr_ratio", "crt_engine_v2"],
            consumers=["CRT cached_features", "BitNet map if use_bitnet"],
            crosses_subsystem_boundary=True,
            model_input=True,
            current_semantic_identity="candle_range/atr",
            known_collisions=["historical name disp_strength/disp_str"],
            known_defects=["name collision with FM-020"],
            evidence_refs=["FM-028", "CH-002", "F-050"],
            adversarial_review={
                "could_be_model_specific": "CRT/BitNet primary; still shared boundary quantity",
                "could_be_duplicate_of_fm020": "NO — different formula",
            },
        )

    if qid == "Q-FM027":
        return _base(
            q,
            "CANONICAL_FEATURE_CANDIDATE",
            shared_boundary_evidence=(
                "CH-002 displacement_retrace FM-027 in CRT cached_features; "
                "distinct from pipeline retest_depth FM-021"
            ),
            producers=["derived_math.displacement_retrace", "crt_engine_v2"],
            consumers=["CRT cached_features", "BitNet map if use_bitnet"],
            crosses_subsystem_boundary=True,
            model_input=True,
            current_semantic_identity="cross-candle retrace to displacement open",
            known_collisions=["historical name retest_depth"],
            evidence_refs=["FM-027", "CH-002", "F-050"],
            adversarial_review={"could_be_duplicate_of_fm021": "NO — different formula"},
        )

    # --- Model-specific bundles ---
    if qid == "Q-GAUSS-3":
        return _base(
            q,
            "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
            producers=["heuristic_gaussian_engine"],
            consumers=["EngineRunner gaussian slot"],
            model_or_subsystem_specific=True,
            model_input=True,
            notes="Live 3-feature heuristic scoring over shared features; not a new feature identity",
            evidence_refs=["active_models.yaml gaussian live"],
        )

    if qid == "Q-GAUSS-38":
        return _base(
            q,
            "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
            producers=["gaussian 38-dim experimental artifact path"],
            consumers=["unwired experimental"],
            model_or_subsystem_specific=True,
            model_input=True,
            training_input=True,
            notes="38-dim NB experimental; train lineage not recovered in this run",
            evidence_refs=["active_models experimental", "FC-0.5 ARTIFACT_BINDING_UNKNOWN"],
        )

    if qid == "Q-BITNET-6":
        return _base(
            q,
            "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
            producers=["CRT BitNet map / BitNetZoneGate"],
            consumers=["BitNet hard-reject when use_bitnet"],
            model_or_subsystem_specific=True,
            model_input=True,
            notes="Consumes shared features; alias risk FM-027/028 into pipeline names",
            evidence_refs=["use_bitnet:false", "FC-0.5"],
        )

    if qid == "Q-RR-POLARITY":
        return _base(
            q,
            "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
            producers=["rr_engine"],
            consumers=["EngineRunner rr slot", "DecisionEngine gate (F-048)"],
            model_or_subsystem_specific=True,
            model_input=True,
            notes="Candle polarity misnamed rr_ratio — engine-local quantity",
            evidence_refs=["F-048", "rr_engine"],
        )

    if qid == "Q-RR-FUSION-38":
        return _base(
            q,
            "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
            producers=["rr_fusion historical path"],
            consumers=["disabled rr_fusion"],
            model_or_subsystem_specific=True,
            model_input=True,
            training_input=True,
            notes="enabled:false; Mahalanobis 38-dim historical",
            evidence_refs=["F-038/044/045"],
        )

    if qid == "Q-TRADENET":
        return _base(
            q,
            "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
            producers=["tradenet artifact intent"],
            consumers=["unwired fusion neural slot"],
            model_or_subsystem_specific=True,
            notes="F-005 unwired",
            evidence_refs=["F-005"],
        )

    if qid == "Q-ZONE-MEMBER":
        return _base(
            q,
            "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
            producers=["zone_gate_engine", "zone_registry.json"],
            consumers=["EngineRunner zone_gate"],
            model_or_subsystem_specific=True,
            model_input=True,
            notes="Zone membership geometry — not 38-vector feature",
            evidence_refs=["F-041", "zone_gate_engine"],
        )

    if qid == "Q-SCORING-DISP":
        return _base(
            q,
            "BLOCKED",
            exact_missing_evidence=(
                "Full call-site graph and formula proof for scoring_engine local "
                "disp_strength=move/atr vs FM-020 not established in RUN-1.5A scope"
            ),
            paths_inspected=["RUN-1 residual note", "FC-0.5 unknown list"],
            evidence_found=["name disp_strength appears in scoring residual UNKNOWN"],
            why_terminal_classification_is_not_possible=(
                "Cannot distinguish EXPLICIT_MODEL_SPECIFIC vs DUPLICATE of Q-FM020 without call-site proof"
            ),
            highest_leverage_next_search="AST/grep scoring_engine and engines for move/atr disp_strength",
        )

    if qid == "Q-CRT-FEATURE-BUILDER":
        return _base(
            q,
            "BLOCKED",
            exact_missing_evidence="Complete call-site reachability and formula set of crt_feature_builder.py",
            paths_inspected=["RUN-1 note git-modified crt_feature_builder", "F-046 orphan claim history"],
            evidence_found=["module exists; historical claim of zero call sites may be stale"],
            why_terminal_classification_is_not_possible=(
                "May be PROVEN_UNREACHABLE or IMPLEMENTATION_INTERMEDIATE or DUPLICATE — not proven"
            ),
            highest_leverage_next_search="import graph + grep crt_feature_builder callers",
        )

    if qid == "Q-DATASET-BUILDER":
        return _base(
            q,
            "TRAINING_ONLY_QUANTITY",
            producers=["dataset_builder.build_feature_vector"],
            consumers=["LiveEngine.process", "training dataset construction"],
            training_only=False,  # also live trade-event path
            training_input=True,
            model_input=True,
            notes=(
                "Trade-event vector assembly from trade_data; training-primary but also live_engine. "
                "PRIMARY_ROLE=TRAINING_ONLY_QUANTITY as dominant historical role; live reuse noted."
            ),
            evidence_refs=["dataset_builder", "live_engine.py"],
        )

    if qid in ("Q-RESEARCH-INDICATORS", "Q-SECONDLOW", "Q-REGIME-LABELER", "Q-MARKOV-FORECAST"):
        return _base(
            q,
            "RESEARCH_ONLY_QUANTITY",
            producers=list(q.get("impl") or []),
            consumers=["research qualification / program experiments"],
            research_only=True,
            crosses_subsystem_boundary=False,
            evidence_refs=list(q.get("evidence") or []),
        )

    # --- Remaining curated → pipeline shared features ---
    shared_pipeline = {
        "Q-EMA-FAST", "Q-EMA-SLOW", "Q-ATR", "Q-VOL-RATIO", "Q-VOL-SPIKE",
        "Q-EMA-SPREAD", "Q-MOMENTUM", "Q-RSI", "Q-MACD-L", "Q-MACD-S", "Q-MACD-H",
        "Q-TREND-BIAS", "Q-TREND-STR", "Q-VOLATILITY-RATIO",
        "Q-SWING-CENTER",
        "Q-STRUCT-HIGHER_HIGH", "Q-STRUCT-LOWER_LOW", "Q-STRUCT-BREAK_OF_STRUCTURE",
        "Q-STRUCT-LIQUIDITY_SWEEP", "Q-STRUCT-SWEEP_DETECTED", "Q-STRUCT-DOUBLE_SWEEP",
        "Q-STRUCT-LIQUIDITY_DISTANCE", "Q-STRUCT-LIQUIDITY_PRESSURE_SCORE",
        "Q-STRUCT-CANDLES_SINCE_RETEST",
        "Q-BODY-SIZE", "Q-WICK-SIZE",
        "Q-FM020", "Q-FM021",
        "Q-VR-GLOBAL",
        "Q-SESSION", "Q-HOUR",
    }
    if qid in shared_pipeline:
        defects = []
        temporal = []
        collisions = []
        if qid == "Q-SWING-CENTER" or qid.startswith("Q-STRUCT-"):
            temporal.append("centered swing inheritance LEAKING (PASS-A / FC-0.5)")
            defects.append("PIT future-bar dependence under default center=True")
        if qid == "Q-FM021":
            temporal.append("retest_depth inherits liquidity_sweep → swing leak")
        if qid == "Q-VR-GLOBAL":
            defects.append("GLOBAL_FIT full-batch ATR rank")
            temporal.append("available_at depends on future rows in batch")
        if qid == "Q-FM020":
            collisions.append("name collision with FM-028")
        if qid == "Q-FM021":
            collisions.append("name collision with FM-027")
        if qid in ("Q-VOL-RATIO", "Q-VOL-SPIKE"):
            defects.append("inherits volume T-003 semantic risk")

        boundary = (
            f"{qid} ({q['names']}) is in CANONICAL_FEATURES 38-vector and/or structure "
            f"outputs of FeaturePipeline; consumed by BacktestRunner feature index, "
            f"research paths, and engine-facing feature dicts — shared mathematical surface"
        )
        if qid in ("Q-SWING-CENTER",):
            boundary += "; swing_high/low are vector members and feed multi-feature structure graph"

        return _base(
            q,
            "CANONICAL_FEATURE_CANDIDATE",
            shared_boundary_evidence=boundary,
            producers=["FeaturePipeline"],
            consumers=["BacktestRunner", "engines via feature dict", "research using pipeline"],
            crosses_subsystem_boundary=True,
            model_input=True,
            training_input=True,
            persisted=True,
            current_semantic_identity=q.get("formula"),
            known_defects=defects,
            known_collisions=collisions,
            known_temporal_issues=temporal,
            evidence_refs=["feature_schema CANONICAL_FEATURES", "feature_pipeline", "FC-0/0.5"],
            adversarial_review={
                "could_be_intermediate": qid.startswith("Q-STRUCT-") and False,
                "could_be_model_specific": False,
                "could_be_label": False,
                "could_be_state": False,
                "could_be_diagnostic": False,
                "could_be_duplicate": bool(collisions),
                "could_be_unreachable": False,
                "conclusion": "shared pipeline vector/structure → CANONICAL_FEATURE_CANDIDATE",
            },
        )

    return _base(
        q,
        "BLOCKED",
        exact_missing_evidence=f"No adjudication rule for curated id {qid}",
        paths_inspected=["phase1_run1 universe"],
        evidence_found=[str(q.get("class"))],
        why_terminal_classification_is_not_possible="Unhandled curated id",
        highest_leverage_next_search="manual review",
    )


def adjudicate_ast(q: dict) -> dict:
    name = (q.get("names") or ["?"])[0]
    impl = q.get("impl") or []
    impl_s = " ".join(impl)

    # CLI argparse keys masquerading as columns
    if name.startswith("--"):
        return _base(
            q,
            "PROVEN_UNREACHABLE_OR_ARCHIVED",
            unreachable_or_archived=True,
            producers=impl,
            consumers=[],
            notes="AST false positive: argparse/option key assignment, not a time-series feature",
            evidence_refs=impl,
            adversarial_review={"is_math_quantity": False, "reason": "CLI flag key"},
        )

    # Phase-1 / corpus validation gate labels
    if name.startswith("G0") or name.startswith("G1") or name.startswith("G2") or name.startswith("G3") or name.startswith("G4") or name.startswith("G5") or name.startswith("PROBE_") or name.startswith("PASS_") or name in (
        "adversarial_clean_path",
        "PIT_transitive_status",
        "artifacts_created",
        "build_trade_success",
        "TRUST_VOLREGIME_CAUSAL",
        "TRUST_INTRABAR_TOUCH",
        "RESEARCH_SPINE_CONFIG",
        "backtest_v2",
        "belief_registry",
        "block_reason_dist",
    ):
        return _base(
            q,
            "DIAGNOSTIC_OR_METRIC",
            diagnostic=True,
            producers=impl,
            consumers=["validation scripts / tests / reports"],
            notes="Diagnostic, probe, or report-field key — not a market feature quantity",
            evidence_refs=impl,
        )

    # CRT state machine token
    if name == "RANGE":
        return _base(
            q,
            "STATE_OR_CACHE",
            state_or_cache=True,
            temporary_impl_state=True,
            producers=["crt_engine_v2 CRTState"],
            consumers=["CRT state machine"],
            model_or_subsystem_specific=True,
            notes="CRT state enum member RANGE, not a numeric feature column",
            evidence_refs=impl,
        )

    if name == "action":
        return _base(
            q,
            "STATE_OR_CACHE",
            state_or_cache=True,
            producers=["crt_engine_v2"],
            consumers=["CRT decision emission"],
            model_or_subsystem_specific=True,
            notes="CRT action field, not CANONICAL_FEATURES member",
            evidence_refs=impl,
        )

    if name == "active":
        return _base(
            q,
            "STATE_OR_CACHE",
            state_or_cache=True,
            producers=["model_registry"],
            consumers=["registry promotion state"],
            notes="Model registry active flag",
            evidence_refs=impl,
        )

    # Pipeline intermediates that DO feed other pipeline columns in the same module.
    # ma_200 is deliberately NOT in this set (T-13 2026-07-20): it has zero consumers —
    # ma_20 feeds price_vs_ma20 / ma_slope_20 -> trend_strength; ma_50 feeds price_vs_ma50;
    # ma_200 is computed and dropped on the floor. See dedicated branch below.
    if name in (
        "atr_14_raw",
        "true_range",
        "candle_body",
        "bb_lower",
        "bb_upper",
        "bb_width",
        "bb_position",
        "prev_close",
        "delta_close",
        "upper_wick",
        "lower_wick",
        "direction",
        "volume_ma20",
        "ma_20",
        "ma_50",
        "ma_slope_20",
        "price_vs_ma20",
        "price_vs_ma50",
        "rsi_state",
        "day_of_week",
    ):
        return _base(
            q,
            "IMPLEMENTATION_INTERMEDIATE",
            producers=["FeaturePipeline"],
            consumers=["downstream pipeline features within same module"],
            temporary_impl_state=True,
            crosses_subsystem_boundary=False,
            notes=f"Computed in FeaturePipeline but not a CANONICAL_FEATURES vector member: {name}",
            evidence_refs=impl or ["feature_pipeline.py"],
            adversarial_review={
                "crosses_boundary": False,
                "in_38_vector": False,
                "model_input_direct": False,
            },
        )

    # T-13: ma_200 was bucketed with ma_20/ma_50 by pattern, not by consumer trace.
    # Consumers=[] is the accurate record — column is emitted, never read.
    if name == "ma_200":
        return _base(
            q,
            "IMPLEMENTATION_INTERMEDIATE",
            producers=["FeaturePipeline"],
            consumers=[],
            temporary_impl_state=True,
            crosses_subsystem_boundary=False,
            notes=(
                "Computed in FeaturePipeline (ma_periods includes 200) but not a "
                "CANONICAL_FEATURES member and has ZERO consumers — unlike ma_20 "
                "(price_vs_ma20 / ma_slope_20 -> trend_strength) and ma_50 "
                "(price_vs_ma50). Does not drive finalize() drop (dropna uses "
                "CANONICAL_FEATURES only). Corrected T-13 2026-07-20; prior claim "
                "'downstream pipeline features within same module' was false."
            ),
            evidence_refs=impl or ["feature_pipeline.py"],
            adversarial_review={
                "crosses_boundary": False,
                "in_38_vector": False,
                "model_input_direct": False,
                "zero_consumers": True,
            },
        )

    # Cached CRT/trade fields on trades
    if name.startswith("cached_"):
        return _base(
            q,
            "STATE_OR_CACHE",
            state_or_cache=True,
            producers=["backtest_v2 trade enrichment"],
            consumers=["trade ledger / forensics"],
            notes=f"Persisted trade cache field {name}",
            evidence_refs=impl,
            persisted=True,
        )

    # BitNet scores / decisions
    if name.startswith("bitnet_"):
        return _base(
            q,
            "EXPLICIT_MODEL_SPECIFIC_QUANTITY",
            model_or_subsystem_specific=True,
            model_input=False,
            producers=impl,
            consumers=["backtest enrichment / diagnostics"],
            notes=f"BitNet model output/metadata field {name}",
            evidence_refs=impl,
            diagnostic=True,
        )

    # Research geometry / ATR variants
    if name in (
        "ATR14",
        "HH20",
        "LL20",
        "LL20_2nd",
        "atr_100",
        "atr_200",
        "atr_p70_threshold_200",
        "atr_pct",
        "atr_pctile",
        "atr_percentile_proxy",
        "atr_t__sign_next",
        "atr_tercile",
        "S_within_tercile",
        "body_pct",
        "bh_q",
        "bh_significant",
    ):
        return _base(
            q,
            "RESEARCH_ONLY_QUANTITY",
            research_only=True,
            producers=impl,
            consumers=["research scripts"],
            notes=f"Research-local series/metric {name}",
            evidence_refs=impl,
        )

    # Session config / capital ledger / trade bookkeeping
    if name in (
        "added_sessions",
        "allowed_sessions",
        "allowed_sessions_overrides",
        "capital_after",
        "capital_before",
        "candle_idx",
        "candle_ts",
        "alert_id",
        "cancelled",
    ):
        role = "DIAGNOSTIC_OR_METRIC"
        if name in ("capital_after", "capital_before"):
            role = "DIAGNOSTIC_OR_METRIC"
        if name in ("allowed_sessions", "allowed_sessions_overrides", "added_sessions"):
            role = "STATE_OR_CACHE"
        return _base(
            q,
            role,
            diagnostic=role == "DIAGNOSTIC_OR_METRIC",
            state_or_cache=role == "STATE_OR_CACHE",
            producers=impl,
            consumers=["config / trade ledger / live"],
            notes=f"Operational/config/ledger field {name}, not market feature math",
            evidence_refs=impl,
        )

    # Default: blocked with missing evidence rather than force
    return _base(
        q,
        "BLOCKED",
        exact_missing_evidence=(
            f"AST record name={name!r} not mapped to a proven mathematical feature role; "
            f"may be dict key, metric, or unreviewed series"
        ),
        paths_inspected=impl[:5] or ["AST discovery only"],
        evidence_found=[f"name={name}", f"impl={impl[:3]}"],
        why_terminal_classification_is_not_possible=(
            "Insufficient formula/producer/consumer proof within RUN 1.5A no-rediscovery scope"
        ),
        highest_leverage_next_search=f"open {impl[0] if impl else 'unknown'} and identify object type of key {name}",
    )


def main() -> int:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    qs = universe["quantities"]
    if len(qs) != 142:
        raise SystemExit(f"RUN1 denominator expected 142, got {len(qs)}")

    records = []
    backlog: list[dict] = []
    # incidental discoveries while classifying (not added to 142)
    backlog.append(
        {
            "discovery_id": "NDB-001",
            "path": "src/features/feature_pipeline.py",
            "line_function": "compute_price_features / indicators",
            "discovery_reason": (
                "Pipeline writes many intermediate columns (prev_close, ma_*, bb_*, "
                "volume_ma20, day_of_week, etc.) not all present as curated RUN-1 quantities"
            ),
            "parent_quantity_id": "Q-ATR",
            "potential_role": "IMPLEMENTATION_INTERMEDIATE",
            "evidence": "feature_pipeline df column writes; some appear only as AST subset",
        }
    )
    backlog.append(
        {
            "discovery_id": "NDB-002",
            "path": "src/features/feature_pipeline.py",
            "line_function": "compute_structure_liquidity",
            "discovery_reason": "last_swing_* intermediates already curated; true_range/atr_14_raw may be partial",
            "parent_quantity_id": "Q-INTER-LAST-SWING-H",
            "potential_role": "IMPLEMENTATION_INTERMEDIATE",
            "evidence": "pipeline structure block",
        }
    )

    for q in qs:
        if str(q["id"]).startswith("Q-AST-COL-"):
            rec = adjudicate_ast(q)
        else:
            rec = adjudicate_curated(q)
        if rec["PRIMARY_ROLE"] not in PRIMARY_ROLES:
            raise SystemExit(f"illegal role {rec['PRIMARY_ROLE']} for {rec['quantity_id']}")
        records.append(rec)

    # Integrity
    ids = [r["quantity_id"] for r in records]
    assert len(ids) == 142
    assert len(set(ids)) == 142
    input_ids = {q["id"] for q in qs}
    assert set(ids) == input_ids

    counts = Counter(r["PRIMARY_ROLE"] for r in records)
    assert sum(counts.values()) == 142
    assert counts.get("UNKNOWN", 0) == 0
    assert "UNKNOWN" not in counts

    # Validate constraints
    for r in records:
        role = r["PRIMARY_ROLE"]
        if role == "CANONICAL_FEATURE_CANDIDATE":
            assert r.get("shared_boundary_evidence"), r["quantity_id"]
        if role == "INTENTIONAL_ALIAS":
            assert r.get("alias_of"), r["quantity_id"]
        if role == "DUPLICATE_IMPLEMENTATION":
            assert r.get("duplicate_of_quantity_id"), r["quantity_id"]
        if role == "BLOCKED":
            assert r.get("exact_missing_evidence"), r["quantity_id"]

    commit, dirty = _git()
    blocked = [r for r in records if r["PRIMARY_ROLE"] == "BLOCKED"]
    canonical = [r for r in records if r["PRIMARY_ROLE"] == "CANONICAL_FEATURE_CANDIDATE"]

    status = "COMPLETE"
    # COMPLETE if all rules satisfied (BLOCKED is a valid PRIMARY_ROLE)
    if len(records) != 142 or sum(counts.values()) != 142:
        status = "BLOCKED:COUNT_MISMATCH"

    adjudication = {
        "_doc": "Phase 1 RUN 1.5A quantity role adjudication. Does not freeze canonical universe or formulas.",
        "generated_at_utc": _now(),
        "RUN1_INPUT_RECORDS": 142,
        "RECORDS_ADJUDICATED": 142,
        "PRIMARY_ROLE_COUNTS": dict(counts),
        "UNKNOWN_PRIMARY_ROLE": 0,
        "records": records,
        "canonical_feature_candidates": [
            {
                "quantity_id": r["quantity_id"],
                "names": r["names"],
                "shared_boundary_evidence": r.get("shared_boundary_evidence"),
                "current_semantic_identity": r.get("current_semantic_identity") or r.get("formula_summary"),
                "known_defects": r.get("known_defects") or [],
                "known_collisions": r.get("known_collisions") or [],
                "known_temporal_issues": r.get("known_temporal_issues") or [],
                "evidence_refs": r.get("evidence_refs") or [],
            }
            for r in canonical
        ],
        "NEW_DISCOVERY_BACKLOG_COUNT": len(backlog),
        "denominator_expanded": False,
        "production_feature_code_changed": False,
        "model_enablement_changed": False,
        "model_artifacts_changed": False,
    }

    blocked_doc = {
        "_doc": "Phase 1 RUN 1.5A BLOCKED records only",
        "generated_at_utc": _now(),
        "n_blocked": len(blocked),
        "records": [
            {
                "quantity_id": r["quantity_id"],
                "names": r["names"],
                "exact_missing_evidence": r.get("exact_missing_evidence"),
                "paths_inspected": r.get("paths_inspected"),
                "evidence_found": r.get("evidence_found"),
                "why_terminal_classification_is_not_possible": r.get(
                    "why_terminal_classification_is_not_possible"
                ),
                "highest_leverage_next_search": r.get("highest_leverage_next_search"),
            }
            for r in blocked
        ],
    }

    backlog_doc = {
        "_doc": "NEW_DISCOVERY_BACKLOG — not adjudicated in RUN 1.5A; not part of 142 denominator",
        "generated_at_utc": _now(),
        "count": len(backlog),
        "items": backlog,
    }

    manifest = {
        "program": "PHASE1_CANONICAL_FEATURE_TRUTH_AND_MODEL_LINEAGE",
        "run": "1.5A",
        "PHASE1_RUN15A_STATUS": status,
        "RUN15B_AUTHORIZATION": "NOT_AUTOMATIC",
        "generated_at_utc": _now(),
        "repository_commit": commit,
        "worktree_dirty": dirty,
        "RUN1_INPUT_RECORDS": 142,
        "RECORDS_ADJUDICATED": 142,
        "PRIMARY_ROLE_COUNTS": dict(counts),
        "UNKNOWN_PRIMARY_ROLE": 0,
        "NEW_DISCOVERY_BACKLOG_COUNT": len(backlog),
        "denominator_expanded": False,
        "production_feature_code_changed": False,
        "model_enablement_changed": False,
        "model_artifacts_changed": False,
        "ECONOMIC_CLAIMS_ALLOWED": False,
        "model_training_lineage_started": False,
        "canonical_formulas_defined": False,
        "feature_universe_frozen": False,
        "artifacts": [
            f"docs/governance/phase1_run15a_quantity_role_adjudication-{DATE}.json",
            f"docs/governance/phase1_run15a_quantity_role_adjudication-{DATE}.md",
            f"docs/governance/phase1_run15a_blocked_records-{DATE}.json",
            f"docs/governance/phase1_run15a_new_discovery_backlog-{DATE}.json",
            f"docs/governance/phase1_run15a_manifest-{DATE}.json",
            "scripts/analysis/phase1_run15a_quantity_role_adjudication.py",
            "tests/test_phase1_run15a_quantity_roles.py",
        ],
    }

    # Write JSON (stable key order via sort_keys for determinism of non-record fields;
    # records keep input order)
    def dump(path: Path, obj: dict) -> None:
        path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

    dump(GOV / f"phase1_run15a_quantity_role_adjudication-{DATE}.json", adjudication)
    dump(GOV / f"phase1_run15a_blocked_records-{DATE}.json", blocked_doc)
    dump(GOV / f"phase1_run15a_new_discovery_backlog-{DATE}.json", backlog_doc)
    dump(GOV / f"phase1_run15a_manifest-{DATE}.json", manifest)

    # MD summary
    lines = [
        "# Phase 1 RUN 1.5A — Quantity Role Adjudication",
        "",
        f"**PHASE1_RUN15A_STATUS** = `{status}`",
        "",
        f"RUN1_INPUT_RECORDS = 142",
        f"RECORDS_ADJUDICATED = 142",
        f"UNKNOWN_PRIMARY_ROLE = 0",
        f"NEW_DISCOVERY_BACKLOG_COUNT = {len(backlog)}",
        "",
        "## PRIMARY_ROLE counts",
        "",
        "```",
        json.dumps(dict(counts), indent=2),
        "```",
        "",
        f"Sum = {sum(counts.values())}",
        "",
        "## CANONICAL_FEATURE_CANDIDATE",
        "",
    ]
    for r in canonical:
        lines.append(
            f"- `{r['quantity_id']}` {r['names']}: {r.get('shared_boundary_evidence', '')[:160]}..."
        )
    lines += [
        "",
        "## BLOCKED",
        "",
    ]
    for r in blocked:
        lines.append(f"- `{r['quantity_id']}`: {r.get('exact_missing_evidence')}")
    lines += [
        "",
        "## What this does not prove",
        "",
        "- feature-universe search not closed",
        "- NEW_DISCOVERY_BACKLOG not adjudicated",
        "- dynamic paths not resolved",
        "- collision exhaustiveness not proven",
        "- canonical universe not frozen; formulas not defined",
        "- no production/model changes",
        "",
    ]
    (GOV / f"phase1_run15a_quantity_role_adjudication-{DATE}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "PHASE1_RUN15A_STATUS": status,
        "PRIMARY_ROLE_COUNTS": dict(counts),
        "sum": sum(counts.values()),
        "n_canonical": counts.get("CANONICAL_FEATURE_CANDIDATE", 0),
        "n_blocked": counts.get("BLOCKED", 0),
        "backlog": len(backlog),
    }, indent=2))
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
