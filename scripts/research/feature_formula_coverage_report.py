#!/usr/bin/env python3
"""feature_formula_coverage_report.py — ontology ↔ test-coverage semantic parity.

READ-ONLY research tool. Scans market_ontology.yaml feature entries and reports
whether a known test target exists for each. No production behaviour change.

No defaults:
  - every feature MUST declare `lifecycle` or we raise
  - expected test targets are an explicit map (not guessed)
  - unknown sections are reported, not silently skipped as "covered"

Usage:
  python scripts/research/feature_formula_coverage_report.py
  python scripts/research/feature_formula_coverage_report.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.registry import load_ontology  # noqa: E402

# Sections governed by the feature-math ontology iteration contract.
_SECTIONS = (
    "primitives",
    "feature_compositions",
    "derived_metrics",
    "rolling_indicators",
    "temporal_context",
    "structural_states",
)

# Explicit expected test ownership. Keys = feature name (or "*" section default).
# A feature is COVERED only if at least one listed path exists on disk.
# Features intentionally deferred are listed under DEFERRED with a reason.
_TEST_TARGETS: dict[str, list[str]] = {
    # temporal
    "hour_of_day": [
        "tests/test_feature_temporal_context.py",
        "tests/test_hour_of_day_certification.py",
    ],
    "session": [
        "tests/test_feature_temporal_context.py",
        "tests/test_session_classifier.py",
        "tests/test_session_certification.py",
    ],
    # structural simple
    "trend_bias": ["tests/test_feature_structural_states.py"],
    "higher_high": ["tests/test_feature_structural_states.py"],
    "lower_low": ["tests/test_feature_structural_states.py"],
    "sweep_detected": ["tests/test_feature_structural_states.py"],
    "rsi_state": ["tests/test_feature_structural_states.py"],
    "displacement_flag": ["tests/test_feature_structural_states.py"],
    # structural complex (domain + formula-level; swing oracle deferred)
    "break_of_structure": ["tests/test_feature_structural_states_complex.py"],
    "liquidity_sweep": ["tests/test_feature_structural_states_complex.py"],
    "double_sweep": ["tests/test_feature_structural_states_complex.py"],
    "retest_flag": ["tests/test_feature_structural_states_complex.py"],
    # rolling standard 11
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
        "tests/test_volatility_regime_certification.py",
        "tests/test_fc1d_volregime_causal.py",
    ],
    "volume_ratio": ["tests/test_feature_rolling_indicators.py"],
    "volume_spike": ["tests/test_feature_volume_spike_parity.py"],
    # FC1-A swing chain (independent oracle parity)
    "swing_high": [
        "tests/test_fc1a_swing_oracle_parity.py",
        "tests/test_fc1a_swing_causal.py",
    ],
    "swing_low": [
        "tests/test_fc1a_swing_oracle_parity.py",
        "tests/test_fc1a_swing_causal.py",
    ],
    "last_swing_high_price": ["tests/test_fc1a_swing_oracle_parity.py"],
    "last_swing_low_price": ["tests/test_fc1a_swing_oracle_parity.py"],
    # candle geometry / derived (existing floors)
    "body_size": ["tests/test_candle_math.py"],
    "candle_range": ["tests/test_candle_math.py"],
    "body_ratio": ["tests/test_candle_math.py"],
    "upper_wick": ["tests/test_candle_math.py"],
    "lower_wick": ["tests/test_candle_math.py"],
    "total_wick": ["tests/test_candle_math.py"],
    "disp_strength": ["tests/test_derived_math.py"],
    "retest_depth": ["tests/test_derived_math.py"],
    "ema_spread": ["tests/test_derived_math.py"],
    "momentum_score": ["tests/test_derived_math.py"],
    "volatility_ratio": ["tests/test_derived_math.py"],
    "liquidity_distance": ["tests/features/test_liquidity_distance.py"],
    "liquidity_pressure_score": ["tests/features/test_liquidity_distance.py"],
    "ema_spread_atr": [
        "tests/test_b2a_feature_candidate_certification.py",
        "tests/test_fm030_031_implementation_validation.py",
    ],
    "momentum_score_atr": [
        "tests/test_b2a_feature_candidate_certification.py",
        "tests/test_fm030_031_implementation_validation.py",
    ],
    "displacement_retrace": ["tests/test_fm027_displacement_retrace_certification.py"],
    "displacement_atr_ratio": ["tests/test_crt_adversarial_closure.py"],
    "disp_strength_atr_rescale": [
        "tests/test_gd004_gd005_identity_closure.py",
        "tests/test_fm_resolution_phase3.py",
    ],
}

# Features whose exact formula test is intentionally deferred (still reported).
_DEFERRED: dict[str, str] = {
    "body_to_total_wick_ratio": "research composition; no dedicated parity floor yet",
    "upper_wick_ratio": "research composition; no dedicated parity floor yet",
    "lower_wick_ratio": "research composition; no dedicated parity floor yet",
}


def _paths_exist(rel_paths: list[str]) -> list[str]:
    found = []
    for rel in rel_paths:
        if (ROOT / rel).is_file():
            found.append(rel)
    return found


def build_report() -> dict[str, Any]:
    ont = load_ontology()
    rows: list[dict[str, Any]] = []
    missing_lifecycle: list[str] = []
    gaps: list[str] = []
    covered = 0
    deferred = 0
    unmapped = 0

    for section in _SECTIONS:
        if section not in ont:
            raise KeyError(f"ontology missing required section {section!r}")
        block = ont[section]
        if not isinstance(block, dict):
            raise TypeError(f"ontology section {section!r} must be a mapping")

        for name, spec in block.items():
            if not isinstance(spec, dict):
                raise TypeError(f"{section}.{name} must be a mapping")
            if "lifecycle" not in spec:
                missing_lifecycle.append(f"{section}.{name}")
                continue
            if "id" not in spec:
                raise KeyError(f"{section}.{name}: missing id (no silent skip)")

            fid = spec["id"]
            lifecycle = spec["lifecycle"]
            status: str
            tests: list[str] = []
            note = ""

            if name in _DEFERRED:
                status = "DEFERRED"
                note = _DEFERRED[name]
                deferred += 1
            elif name in _TEST_TARGETS:
                tests = _paths_exist(_TEST_TARGETS[name])
                if not tests:
                    status = "GAP"
                    note = f"expected targets missing on disk: {_TEST_TARGETS[name]}"
                    gaps.append(f"{section}.{name}")
                else:
                    status = "COVERED"
                    covered += 1
            else:
                status = "UNMAPPED"
                note = "no entry in _TEST_TARGETS or _DEFERRED"
                unmapped += 1
                gaps.append(f"{section}.{name}")

            rows.append(
                {
                    "section": section,
                    "name": name,
                    "id": fid,
                    "lifecycle": lifecycle,
                    "status": status,
                    "tests": tests,
                    "note": note,
                }
            )

    if missing_lifecycle:
        raise KeyError(
            "features missing required lifecycle (no silent default): "
            + ", ".join(missing_lifecycle)
        )

    summary = {
        "total": len(rows),
        "covered": covered,
        "deferred": deferred,
        "unmapped_or_gap": unmapped + len([g for g in gaps if g.split(".")[-1] not in _DEFERRED]),
        "gap_count": len(gaps),
        "gaps": gaps,
    }
    return {"summary": summary, "features": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["summary"]["gap_count"] == 0 else 1

    s = report["summary"]
    print("=== Feature formula coverage report ===")
    print(
        f"total={s['total']}  covered={s['covered']}  "
        f"deferred={s['deferred']}  gaps={s['gap_count']}"
    )
    print()
    for row in report["features"]:
        mark = {
            "COVERED": "OK",
            "DEFERRED": "DF",
            "GAP": "!!",
            "UNMAPPED": "??",
        }[row["status"]]
        tests = ",".join(row["tests"]) if row["tests"] else "-"
        print(
            f"[{mark}] {row['id']:8} {row['section']:22} {row['name']:28} "
            f"lifecycle={row['lifecycle']:16} tests={tests}"
        )
        if row["note"]:
            print(f"       note: {row['note']}")

    if s["gaps"]:
        print()
        print("GAPS (must map or defer explicitly):")
        for g in s["gaps"]:
            print(f"  - {g}")
        return 1
    print()
    print("No coverage gaps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
