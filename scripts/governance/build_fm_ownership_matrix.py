#!/usr/bin/env python3
"""build_fm_ownership_matrix.py — permanent FM ownership / consumer matrix.

Generates machine-readable + markdown artifacts from the ontology, resolve_fm
binding phases, and known parity/test surfaces. READ-MOSTLY: does not change
production behaviour.

Authority:
  - Semantic correctness (parity / resolve_fm) is recorded per FM.
  - Economic / G001 authority is NEVER inferred from parity (always NONE at
    feature layer). Consumer-level G001 status lives in
    g001_consumer_attribution.json (sibling artifact).

Usage:
  python scripts/governance/build_fm_ownership_matrix.py
  python scripts/governance/build_fm_ownership_matrix.py --check  # exit 1 if drift
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.fm_resolve import (  # noqa: E402
    PHASE2_CRT_FM_IDS,
    PHASE3A_FEATURE_BUILDER_FM_IDS,
    PHASE3B_SCORING_FM_IDS,
    PHASE3C_CAUSAL_STRUCTURE_FM_IDS,
)
from features.registry import load_ontology  # noqa: E402

_OUT_JSON = ROOT / "docs" / "governance" / "fm_ownership_consumer_matrix.json"
_OUT_MD = ROOT / "docs" / "governance" / "fm_ownership_consumer_matrix.md"

_SECTIONS = (
    "primitives",
    "feature_compositions",
    "derived_metrics",
    "rolling_indicators",
    "temporal_context",
    "structural_states",
)

# Explicit parity / certification test ownership (same spirit as coverage report).
_PARITY_TESTS: dict[str, list[str]] = {
    "body_size": ["tests/test_candle_math.py"],
    "candle_range": ["tests/test_candle_math.py"],
    "upper_wick": ["tests/test_candle_math.py"],
    "lower_wick": ["tests/test_candle_math.py"],
    "total_wick": ["tests/test_candle_math.py"],
    "body_ratio": ["tests/test_candle_math.py", "tests/test_fm_resolution_phase2.py"],
    "disp_strength": ["tests/test_derived_math.py"],
    "retest_depth": ["tests/test_derived_math.py"],
    "ema_spread": ["tests/test_derived_math.py"],
    "momentum_score": ["tests/test_derived_math.py"],
    "volatility_ratio": ["tests/test_derived_math.py"],
    "liquidity_distance": [
        "tests/features/test_liquidity_distance.py",
        "tests/test_fm_resolution_phase3.py",
    ],
    "liquidity_pressure_score": [
        "tests/features/test_liquidity_distance.py",
        "tests/test_fm_resolution_phase3.py",
    ],
    "displacement_retrace": ["tests/test_fm027_displacement_retrace_certification.py"],
    "displacement_atr_ratio": [
        "tests/test_crt_adversarial_closure.py",
        "tests/test_fm_resolution_phase2.py",
    ],
    "disp_strength_atr_rescale": [
        "tests/test_gd004_gd005_identity_closure.py",
        "tests/test_fm_resolution_phase3.py",
    ],
    "ema_spread_atr": ["tests/test_b2a_feature_candidate_certification.py"],
    "momentum_score_atr": ["tests/test_b2a_feature_candidate_certification.py"],
    "true_range": ["tests/test_feature_rolling_indicators.py"],
    "atr": ["tests/test_feature_rolling_indicators.py"],
    "rsi_14": ["tests/test_feature_rolling_indicators.py"],
    "ema_fast": ["tests/test_feature_rolling_indicators.py"],
    "ema_slow": ["tests/test_feature_rolling_indicators.py"],
    "macd_line": ["tests/test_feature_rolling_indicators.py"],
    "macd_signal": ["tests/test_feature_rolling_indicators.py"],
    "macd_hist_raw": ["tests/test_feature_rolling_indicators.py"],
    "macd_hist_z": ["tests/test_feature_rolling_indicators.py"],
    "volatility_regime": [
        "tests/test_feature_rolling_indicators.py",
        "tests/test_fc1d_volregime_causal.py",
    ],
    "volume_ratio": ["tests/test_feature_rolling_indicators.py"],
    "volume_spike": ["tests/test_feature_volume_spike_parity.py"],
    "swing_high": ["tests/test_fc1a_swing_oracle_parity.py"],
    "swing_low": ["tests/test_fc1a_swing_oracle_parity.py"],
    "last_swing_high_price": ["tests/test_fc1a_swing_oracle_parity.py"],
    "last_swing_low_price": ["tests/test_fc1a_swing_oracle_parity.py"],
    "hour_of_day": ["tests/test_feature_temporal_context.py"],
    "session": [
        "tests/test_feature_temporal_context.py",
        "tests/test_session_classifier.py",
    ],
    "trend_bias": ["tests/test_feature_structural_states.py"],
    "higher_high": ["tests/test_feature_structural_states.py"],
    "lower_low": ["tests/test_feature_structural_states.py"],
    "break_of_structure": [
        "tests/test_feature_structural_states_complex.py",
        "tests/test_fc1a_swing_oracle_parity.py",
    ],
    "liquidity_sweep": [
        "tests/test_feature_structural_states_complex.py",
        "tests/test_fc1a_swing_oracle_parity.py",
    ],
    "sweep_detected": ["tests/test_feature_structural_states.py"],
    "double_sweep": ["tests/test_feature_structural_states_complex.py"],
    "retest_flag": ["tests/test_feature_structural_states_complex.py"],
    "rsi_state": ["tests/test_feature_structural_states.py"],
    "displacement_flag": ["tests/test_feature_structural_states.py"],
}

_RESOLVE_BINDINGS: dict[str, list[str]] = {}
for _phase, _ids in (
    ("phase2_crt", PHASE2_CRT_FM_IDS),
    ("phase3a_feature_builder", PHASE3A_FEATURE_BUILDER_FM_IDS),
    ("phase3b_scoring", PHASE3B_SCORING_FM_IDS),
    ("phase3c_causal_structure", PHASE3C_CAUSAL_STRUCTURE_FM_IDS),
):
    for _fid in _ids:
        _RESOLVE_BINDINGS.setdefault(_fid, []).append(_phase)

# Known runtime consumers (module-level; not G001 authority).
_CONSUMERS: dict[str, dict] = {
    "crt_engine_v2": {
        "path": "src/config_layer/crt_engine_v2.py",
        "fm_ids": sorted(PHASE2_CRT_FM_IDS),
        "role": "CRT state machine + scoring inputs (hot path)",
    },
    "scoring_engine": {
        "path": "src/engines/scoring_engine.py",
        "fm_ids": sorted(PHASE3B_SCORING_FM_IDS),
        "role": "CRT composite score (breakout uses FM-029)",
    },
    "feature_pipeline": {
        "path": "src/features/feature_pipeline.py",
        "fm_ids": [],  # produces most vector FMs; listed per-feature produced_by
        "role": "Batch/live feature vector producer (primary computation for series FMs)",
    },
    "causal_structure": {
        "path": "src/features/causal_structure.py",
        "fm_ids": sorted(PHASE3C_CAUSAL_STRUCTURE_FM_IDS),
        "role": "Online FC1-A structure + liquidity for FeatureStore",
    },
    "crt_feature_builder": {
        "path": "src/features/crt_feature_builder.py",
        "fm_ids": sorted(PHASE3A_FEATURE_BUILDER_FM_IDS),
        "role": "BitNet feeder transcriber (historically 0 live callers)",
    },
    "engine_runner_fusion": {
        "path": "src/core/engine_runner.py",
        "fm_ids": [],
        "role": "Fusion of crt/gaussian/zone_gate/rr scores (consumes scores, not raw FM math)",
    },
    "feature_state_encoder_shadow": {
        "path": "src/features/feature_states.py",
        "fm_ids": [],
        "role": "Shadow: numeric → state names (research; not trading gate)",
    },
}


def _computation_authority(section: str, spec: dict) -> str:
    if section == "primitives":
        return "FORMULA_REGISTRY"
    if section == "derived_metrics":
        return "FORMULA_REGISTRY"
    if section == "feature_compositions":
        return "COMPOSITION"
    if section == "rolling_indicators":
        return "PIPELINE"
    if section == "temporal_context":
        return "CALENDAR"
    if section == "structural_states":
        return "STRUCTURAL_PIPELINE"
    return "UNKNOWN"


def _semantic_status(name: str, tests: list[str]) -> str:
    if not tests:
        return "NO_PARITY_FLOOR"
    if name in (
        "break_of_structure",
        "liquidity_sweep",
        "double_sweep",
        "retest_flag",
    ):
        return "PARITY_PLUS_ORACLE_SCENARIO"
    if name in ("swing_high", "swing_low", "last_swing_high_price", "last_swing_low_price"):
        return "ORACLE_PARITY"
    if name.startswith("macd") or name in (
        "atr",
        "rsi_14",
        "true_range",
        "ema_fast",
        "ema_slow",
        "volume_ratio",
        "volume_spike",
        "volatility_regime",
    ):
        return "SERIES_PARITY"
    if name in ("hour_of_day", "session"):
        return "TEMPORAL_PARITY"
    if name in (
        "body_size",
        "candle_range",
        "body_ratio",
        "disp_strength",
        "retest_depth",
        "ema_spread",
        "momentum_score",
        "volatility_ratio",
        "displacement_retrace",
        "displacement_atr_ratio",
        "disp_strength_atr_rescale",
        "liquidity_distance",
        "liquidity_pressure_score",
    ):
        return "SCALAR_PARITY"
    return "PARITY_FLOOR_PRESENT"


def build_matrix() -> dict:
    ont = load_ontology()
    features: list[dict] = []
    for section in _SECTIONS:
        block = ont.get(section) or {}
        if not isinstance(block, dict):
            raise TypeError(f"{section} must be mapping")
        for name, spec in block.items():
            if not isinstance(spec, dict):
                raise TypeError(f"{section}.{name} must be mapping")
            if "id" not in spec:
                raise KeyError(f"{section}.{name}: missing id")
            if "lifecycle" not in spec:
                raise KeyError(f"{section}.{name}: missing lifecycle")
            fid = spec["id"]
            lineage = spec.get("lineage") or {}
            tests = list(_PARITY_TESTS.get(name, []))
            # drop missing files from report but keep declared intent
            tests_exist = [t for t in tests if (ROOT / t).is_file()]
            features.append(
                {
                    "fm_id": fid,
                    "name": name,
                    "section": section,
                    "lifecycle": spec["lifecycle"],
                    "computation_class": spec.get("computation_class")
                    or (
                        "scalar"
                        if section in ("primitives", "derived_metrics", "feature_compositions")
                        else None
                    ),
                    "computation_authority": _computation_authority(section, spec),
                    "impl": spec.get("impl"),
                    "produced_by": lineage.get("produced_by"),
                    "consumed_by_declared": lineage.get("consumed_by"),
                    "vector_key": lineage.get("vector_key"),
                    "vector_index": lineage.get("vector_index"),
                    "resolve_fm_bindings": list(_RESOLVE_BINDINGS.get(fid, [])),
                    "parity_tests": tests_exist,
                    "semantic_status": _semantic_status(name, tests_exist),
                    # Permanent invariant: feature-layer parity never grants G001 authority.
                    "economic_authority": "NONE",
                    "g001_status": "NOT_APPLICABLE_AT_FEATURE_LAYER",
                }
            )

    features.sort(key=lambda r: r["fm_id"] or r["name"])
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": (
            "Permanent FM ownership / consumer matrix. Semantic correctness (parity, "
            "resolve_fm) is tracked per FM. Economic/G001 authority is NEVER derived "
            "from this matrix — see g001_consumer_attribution.json."
        ),
        "invariants": [
            "economic_authority is always NONE at the feature layer",
            "parity_tests prove formula/PIT semantics, not expectancy",
            "resolve_fm_bindings list bind phases only; series FMs stay pipeline-owned",
        ],
        "summary": {
            "feature_count": len(features),
            "resolve_fm_bound_count": sum(
                1 for f in features if f["resolve_fm_bindings"]
            ),
            "parity_floor_count": sum(1 for f in features if f["parity_tests"]),
            "no_parity_floor_count": sum(
                1 for f in features if not f["parity_tests"]
            ),
        },
        "consumers": _CONSUMERS,
        "features": features,
    }


def render_md(matrix: dict) -> str:
    lines = [
        "# FM Ownership / Consumer Matrix",
        "",
        f"> Generated: `{matrix['generated_at_utc']}` · schema v{matrix['schema_version']}",
        ">",
        f"> **Source script:** `scripts/governance/build_fm_ownership_matrix.py`",
        ">",
        "> **Invariant:** feature-layer `economic_authority` is always `NONE`.",
        "> G001 contribution is tracked only in "
        "[`g001_consumer_attribution.md`](g001_consumer_attribution.md).",
        "",
        "## Summary",
        "",
        f"- Features: **{matrix['summary']['feature_count']}**",
        f"- resolve_fm bound: **{matrix['summary']['resolve_fm_bound_count']}**",
        f"- With parity floor: **{matrix['summary']['parity_floor_count']}**",
        f"- Without parity floor: **{matrix['summary']['no_parity_floor_count']}**",
        "",
        "## Consumers (runtime modules)",
        "",
        "| Consumer | Path | Role | Bound FMs |",
        "|---|---|---|---|",
    ]
    for cid, c in matrix["consumers"].items():
        fms = ", ".join(c.get("fm_ids") or []) or "—"
        lines.append(
            f"| `{cid}` | `{c['path']}` | {c['role']} | {fms} |"
        )
    lines += [
        "",
        "## Features",
        "",
        "| FM | Name | Section | Authority | resolve_fm | Semantic | Economic | Tests |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in matrix["features"]:
        binds = ",".join(f["resolve_fm_bindings"]) if f["resolve_fm_bindings"] else "—"
        tests = ";".join(Path(t).name for t in f["parity_tests"][:2]) or "—"
        if len(f["parity_tests"]) > 2:
            tests += ";…"
        lines.append(
            f"| {f['fm_id']} | `{f['name']}` | {f['section']} | "
            f"{f['computation_authority']} | {binds} | {f['semantic_status']} | "
            f"{f['economic_authority']} | {tests} |"
        )
    lines += [
        "",
        "## How to regenerate",
        "",
        "```bash",
        "python scripts/governance/build_fm_ownership_matrix.py",
        "python scripts/governance/build_fm_ownership_matrix.py --check",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if on-disk JSON differs from freshly built matrix (ignore generated_at)",
    )
    args = parser.parse_args()
    matrix = build_matrix()

    if args.check:
        if not _OUT_JSON.is_file():
            print(f"MISSING {_OUT_JSON}", file=sys.stderr)
            return 1
        on_disk = json.loads(_OUT_JSON.read_text(encoding="utf-8"))
        a = {**on_disk, "generated_at_utc": None}
        b = {**matrix, "generated_at_utc": None}
        if a != b:
            print("DRIFT: fm_ownership_consumer_matrix.json is stale; regenerate.", file=sys.stderr)
            return 1
        print("OK: fm_ownership_consumer_matrix.json matches builder")
        return 0

    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    _OUT_MD.write_text(render_md(matrix), encoding="utf-8")
    print(f"Wrote {_OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {_OUT_MD.relative_to(ROOT)}")
    print(
        f"features={matrix['summary']['feature_count']} "
        f"bound={matrix['summary']['resolve_fm_bound_count']} "
        f"parity={matrix['summary']['parity_floor_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
