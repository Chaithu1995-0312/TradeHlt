#!/usr/bin/env python3
"""Seed FeatureContract v1 instance (FC-0). No production code changes."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

OUT = ROOT / "docs" / "governance" / "feature_contract_v1-2026-07-10.json"

SPECIAL = {
    "swing_high": ("LEAKING", "center=True publish at t; k=2 future bars", 2),
    "swing_low": ("LEAKING", "center=True publish at t; k=2 future bars", 2),
    "higher_high": ("LEAKING", "depends on last_swing from centered swings", 2),
    "lower_low": ("LEAKING", "depends on last_swing from centered swings", 2),
    "break_of_structure": ("LEAKING", "depends on last_swing refs", 2),
    "liquidity_sweep": ("LEAKING", "depends on last_swing refs", 2),
    "sweep_detected": ("LEAKING", "from liquidity_sweep", 2),
    "double_sweep": ("LEAKING", "from liquidity_sweep", 2),
    "liquidity_distance": ("LEAKING", "uses last_swing prices", 2),
    "liquidity_pressure_score": ("LEAKING", "from liquidity_distance", 2),
    "retest_depth": (
        "FORMULA_AUTHORITY_AMBIGUOUS",
        "FM-021 pipeline; BitNet may alias FM-027",
        0,
    ),
    "candles_since_retest": ("LEAKING", "depends on liquidity_sweep groups", 2),
    "volume": (
        "SEMANTICALLY_DIVERGENT",
        "TICK_VOLUME on XAU; T-003 same-name proxy if all-zero",
        0,
    ),
    "volume_ratio": ("SEMANTICALLY_DIVERGENT", "inherits volume semantic", 0),
    "volume_spike": ("SEMANTICALLY_DIVERGENT", "inherits volume semantic", 0),
    "disp_strength": (
        "FORMULA_AUTHORITY_AMBIGUOUS",
        "FM-020 pipeline; CRT/BitNet may use FM-028 under alias",
        0,
    ),
    "volatility_regime": ("LEAKING", "global atr rank uses full batch", 0),
}


def make_entry(
    name: str,
    order: int | None,
    *,
    status: str = "UNADJUDICATED",
    note: str = "",
    formula_id: str | None = None,
    is_vector: bool = True,
    is_synthetic: bool = False,
    impl: str = "src/features/feature_pipeline.py",
    lookahead: int | str = 0,
    intent: str = "retain; FC-2 full adjudication",
    src_sem: str = "see census / OHLCV",
) -> dict:
    return {
        "feature_name": name,
        "feature_id": f"FEAT-{name.upper()}",
        "formula_id": formula_id or f"FORMULA-LEGACY-{name.upper()}",
        "formula_version": "legacy-v1",
        "formula_definition": note or f"Legacy pipeline semantics for {name}",
        "formula_authority": "LEGACY_FEATURE_SEMANTICS_V1 / FeaturePipeline default",
        "implementation_authority": impl,
        "source_fields": ["ohlcv"],
        "source_field_semantics": src_sem,
        "intermediate_dependencies": [],
        "direct_feature_dependencies": [],
        "transitive_feature_dependencies": [],
        "lookback": "see docs/governance/feature_38_lineage_census-2026-07-10.json",
        "lookahead": lookahead,
        "warmup": "FeaturePipeline finalize / ATR 14 / MA 200 as applicable",
        "statefulness": "batch DataFrame",
        "value_timestamp": "bar t",
        "available_at_timestamp": "bar t (legacy default; may be incorrect for swings)",
        "publication_delay": 0 if lookahead == 0 else "see notes",
        "PIT_semantic": status if status in ("LEAKING",) else "UNADJUDICATED",
        "batch_semantic": "FeaturePipeline.run full frame",
        "runtime_semantic": "backtest dual-load FeaturePipeline; live path TBD FC-3",
        "missing_value_policy": "NaN drop in finalize for ATR-gated; retest_depth 0.0 if no retest",
        "fallback_policy": "implementation-defined",
        "synthetic_input_policy": "none" if not is_synthetic else "explicit synthetic feature",
        "normalization_policy": "NORMALIZE_COLS rolling z-score 50 where applicable",
        "dtype": "float32 in vector",
        "bounds": None,
        "units": None,
        "output_order": order,
        "active_consumers": ["FeaturePipeline vector"],
        "training_consumers": ["BitNet / gaussian / stage1 paths — FC-5 audit"],
        "backtest_consumers": ["BacktestRunner feature index"],
        "live_consumers": ["live_engine_hook — FC-3"],
        "model_artifact_requirements": ["feature_id + formula_id at FC-7"],
        "tests": [],
        "adversarial_probes": [],
        "status": status,
        "evidence": [
            "docs/governance/feature_semantic_adjudication_pass_a-2026-07-10.json",
            "docs/governance/feature_38_lineage_census-2026-07-10.json",
        ],
        "notes": note,
        "is_vector_member": is_vector,
        "is_synthetic": is_synthetic,
        "planned_canonical_intent": intent,
    }


def main() -> int:
    features: list[dict] = []
    for i, name in enumerate(CANONICAL_FEATURES):
        if name in SPECIAL:
            st, note, la = SPECIAL[name]
            fid = None
            intent = "retain with FC-1/FC-2 remediation"
            src = "see census / OHLCV"
            if name == "volume":
                fid = "FORMULA-SOURCE-TICK-VOLUME"
                src = "TICK_VOLUME on frozen XAUUSD (MT5 tick_volume)"
                intent = "bind TICK_VOLUME; proxy becomes FEAT-VOLUME_RANGE_PROXY"
            if name == "disp_strength":
                fid = "FM-020"
                intent = "canonical FM-020; CRT uses FEAT-DISPLACEMENT_ATR_RATIO"
            if name == "retest_depth":
                fid = "FM-021"
                intent = "canonical FM-021; CRT uses FEAT-DISPLACEMENT_RETRACE"
            if name == "volatility_regime":
                intent = "causal regime in FC-1; global rank is LEGACY only"
            if name in ("swing_high", "swing_low"):
                intent = "causal delayed publish available_at=t+k in FC-1"
            features.append(
                make_entry(
                    name,
                    i,
                    status=st,
                    note=note,
                    formula_id=fid,
                    lookahead=la,
                    intent=intent,
                    src_sem=src,
                )
            )
        else:
            features.append(make_entry(name, i))

    # Explicit separation identities (not all vector members yet)
    features.append(
        make_entry(
            "volume_range_proxy",
            None,
            status="UNADJUDICATED",
            note="T-003 high-low proxy under NEW identity only (FC-1)",
            formula_id="FORMULA-T003-RANGE-PROXY",
            is_vector=False,
            is_synthetic=True,
            intent="optional derived; never alias as volume",
            src_sem="SYNTHETIC_PRICE_RANGE_PROXY",
        )
    )
    features[-1]["feature_id"] = "FEAT-VOLUME_RANGE_PROXY"

    features.append(
        make_entry(
            "displacement_retrace",
            None,
            status="FORMULA_AUTHORITY_AMBIGUOUS",
            note="FM-027 CRT cross-candle retrace; distinct from retest_depth FM-021",
            formula_id="FM-027",
            is_vector=False,
            impl="src/features/derived_math.py + src/config_layer/crt_engine_v2.py",
            intent="CRT/BitNet must bind this ID not retest_depth alias",
        )
    )
    features[-1]["feature_id"] = "FEAT-DISPLACEMENT_RETRACE"

    features.append(
        make_entry(
            "displacement_atr_ratio",
            None,
            status="FORMULA_AUTHORITY_AMBIGUOUS",
            note="FM-028 CRT range/ATR; distinct from disp_strength FM-020",
            formula_id="FM-028",
            is_vector=False,
            impl="src/features/derived_math.py + src/config_layer/crt_engine_v2.py",
            intent="CRT/BitNet must bind this ID not disp_strength alias",
        )
    )
    features[-1]["feature_id"] = "FEAT-DISPLACEMENT_ATR_RATIO"

    contract = {
        "contract_id": "FEATURE-CONTRACT-V1",
        "schema_version": "1.0.0",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "production_remediation_started": False,
        "economic_claims_allowed": False,
        "legacy_freeze_ref": "docs/governance/legacy_feature_semantics_v1-2026-07-10.json",
        "fingerprint_ref": "docs/governance/legacy_feature_output_fingerprint_xauusd-2026-07-10.json",
        "corpus_binding": {
            "physical_path": "data/mt5/XAUUSD_M15.csv",
            "sha256": "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56",
            "rows": 47275,
            "status": "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION",
            "allowed_time_range": {
                "start": "2024-05-22T01:00:00",
                "end": "2026-05-21T23:45:00",
            },
        },
        "vector_members": [f"FEAT-{n.upper()}" for n in CANONICAL_FEATURES],
        "explicit_separations": [
            {
                "id": "SEP-A-SWING-CAUSAL",
                "legacy": "center=True publish at t",
                "canonical_intent": "delayed available_at=t+k; no env flag authority",
            },
            {
                "id": "SEP-B-VOLUME",
                "legacy": "T-003 same column name volume",
                "canonical_intent": "volume=TICK_VOLUME; proxy=FEAT-VOLUME_RANGE_PROXY",
            },
            {
                "id": "SEP-C-FM",
                "legacy": "name collisions FM-020/028 and FM-021/027",
                "canonical_intent": "distinct feature_ids FEAT-DISP_STRENGTH/RETEST_DEPTH vs FEAT-DISPLACEMENT_*",
            },
            {
                "id": "SEP-D-VOLREGIME",
                "legacy": "global atr rank",
                "canonical_intent": "causal regime; expanding vs rolling adjudicated in FC-1",
            },
        ],
        "features": features,
    }
    OUT.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    ids = [f["feature_id"] for f in features]
    assert len(ids) == len(set(ids)), "duplicate feature_id"
    print(f"wrote {OUT} n_features={len(features)} vector={len(CANONICAL_FEATURES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
