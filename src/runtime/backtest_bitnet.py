"""
backtest_bitnet.py
==============
Row-by-row backtest runner with BitNet as HARD GATEKEEPER.

Flow
----
    raw CSV
        │
        ▼
    FeaturePipeline.run()
        │  - validates input, computes all indicators/structure/liquidity
        │  - normalizes continuous features (rolling z-score)
        │  - drops warmup NaN rows
        │  - returns enriched_df (N rows)
        │
        ▼
    features = {k: float(row[k]) for k in CANONICAL_FEATURES}   ← SINGLE SOURCE
        │
        ▼
    BitNetRunner.predict(features)  →  {score, decision}         ← HARD GATE
        │
        ├── REJECT → log + continue (EngineRunner NEVER runs)
        │
        └── ACCEPT → EngineRunner.run(features)

Performance note
----------------
FeaturePipeline is fully vectorised (pandas/numpy) — < 1 s for 100 k rows.
BitNet inference per row is microseconds (pure numpy matmul on 24 inputs).
The EngineRunner.run() call is the practical bottleneck.

Integration note
----------------
model_path is read from config["model_path"] (default: "model_export_format.json").
To use a different model file, add "model_path" to your production config JSON.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

from core.engine_runner import EngineRunner
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES, SCHEMA_HASH
from utils.console_safe import safe_print

# BitNet Integration
from bitnet.bitnet_runner import BitNetRunner

logger = logging.getLogger(__name__)


def _derive_symbol_from_data_path(data_path: str) -> str:
    """
    Derive symbol from filename.
    Example: AUDUSD_M15.csv -> AUDUSD
    """
    stem = os.path.splitext(os.path.basename(data_path))[0].upper()
    if not stem:
        return "UNKNOWN"
    parts = stem.split("_")
    return parts[0] if parts else stem


def _to_serializable(obj):
    """Recursively convert numpy types to Python native for JSON serialization."""
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(i) for i in obj]
    return obj


def _build_engine_runner_config(config: dict) -> dict:
    """
    Build EngineRunner config from the sectioned production config.
    All sections are required — raises if any are absent.
    Nested sections (fusion_engine, execution_planner, ultron_risk_gate)
    are preserved as nested dicts so downstream consumers can access them.
    """
    if not isinstance(config, dict):
        raise RuntimeError(
            "_build_engine_runner_config: config must be a dict loaded from "
            "configs/production/v1_multi_2026_03.json."
        )

    required_sections = (
        "engine_runner", "decision_engine", "fusion_engine",
        "execution_planner", "ultron_risk_gate",
    )
    missing = [s for s in required_sections if not isinstance(config.get(s), dict)]
    if missing:
        raise RuntimeError(
            f"_build_engine_runner_config: missing required sections in config: {missing}. "
            "Add them to configs/production/v1_multi_2026_03.json."
        )

    resolved = {}
    resolved.update(config["engine_runner"])
    resolved.update(config["decision_engine"])
    # Nested sections preserved as keys for EngineRunner + downstream layers
    resolved["fusion_engine"]    = config["fusion_engine"]
    resolved["execution_planner"] = config["execution_planner"]
    resolved["ultron_risk_gate"]  = config["ultron_risk_gate"]

    # Keep RR threshold consistent across DecisionEngine and RREngine.
    if "rr_threshold" in resolved and "min_rr" not in resolved:
        resolved["min_rr"] = resolved["rr_threshold"]

    return resolved


def _resolve_timestamp_series(df: pd.DataFrame) -> pd.Series:
    """
    Resolve a timestamp series from common market-data column patterns.
    """
    lower_map = {str(c).strip().lower(): c for c in df.columns}

    single_candidates = ["timestamp", "datetime", "date time", "open time"]
    for key in single_candidates:
        if key in lower_map:
            return pd.to_datetime(df[lower_map[key]], errors="coerce")

    if "date" in lower_map and "time" in lower_map:
        merged = df[lower_map["date"]].astype(str) + " " + df[lower_map["time"]].astype(str)
        return pd.to_datetime(merged, errors="coerce")

    raise ValueError(
        "Could not resolve timestamp column. Expected one of "
        "timestamp/datetime/date time/open time or date+time."
    )


def _apply_month_filter(df: pd.DataFrame, months: int | None) -> pd.DataFrame:
    """
    Keep only the last `months` months (relative to max timestamp in the file).
    """
    if months is None:
        return df
    if months <= 0:
        raise ValueError(f"months must be > 0, got {months}")

    ts = _resolve_timestamp_series(df)
    if ts.isna().all():
        raise ValueError("Timestamp parse failed for all rows; cannot apply month filter.")

    max_ts = ts.max()
    cutoff = max_ts - pd.DateOffset(months=months)
    mask = ts >= cutoff
    out = df.loc[mask].copy()
    return out.reset_index(drop=True)


def run_backtest(
    config: dict,
    data_path: str,
    gate_mode: str = "hard_gate",
    months: int | None = None,
) -> list:
    """
    gate_mode:
      - hard_gate: reject rows when BitNet decision != ACCEPT
      - score_only_audit: always run EngineRunner; keep BitNet decision as audit metadata
      - force_accept_baseline: treat every row as ACCEPT baseline for recall diagnostics
    """
    if gate_mode not in {"hard_gate", "score_only_audit", "force_accept_baseline"}:
        raise ValueError(f"Unsupported gate_mode: {gate_mode}")

    runner = EngineRunner(_build_engine_runner_config(config))
    # Shared collector so exception records appear in the same audit file
    # as all accept/reject decisions written by engine_runner.
    collector = runner.collector
    results = []

    # Create unique decision log file for this run
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    symbol = _derive_symbol_from_data_path(data_path)
    log_filename = f"logs/backtest_decisions_{symbol}_{timestamp}.jsonl"
    decision_log = open(log_filename, 'w', encoding='utf-8')
    logger.info("Writing all decision records to: %s", log_filename)

    raw_df = pd.read_csv(data_path)
    raw_rows = len(raw_df)
    raw_df = _apply_month_filter(raw_df, months)
    filtered_rows = len(raw_df)
    if months is not None:
        logger.info(
            "Month filter applied: last %d month(s) | rows %d -> %d",
            months,
            raw_rows,
            filtered_rows,
        )

    # ── Pre-process: run full feature pipeline on entire DataFrame ────────────────────
    try:
        pipeline = FeaturePipeline(raw_df)
        df, _ = pipeline.run()  # vectors discarded — single feature source used below
        logger.info(
            "FeaturePipeline completed: %d rows after warmup",
            len(df),
        )
    except Exception as exc:
        # A pipeline failure is fatal — no point running the loop with bad data.
        logger.critical("FeaturePipeline failed: %s", exc)
        raise RuntimeError(f"FeaturePipeline failed: {exc}") from exc

    # ── One-time schema integrity log ─────────────────────────────────────────────────
    safe_print(f"SCHEMA HASH: {SCHEMA_HASH}")
    safe_print(f"CANONICAL FEATURES ({len(CANONICAL_FEATURES)}): {list(CANONICAL_FEATURES)}")
    safe_print("\n📊 PIPELINE OUTPUT KEYS:")
    safe_print(df.columns.tolist()[:30])
    # Validate that canonical features exist in output DataFrame
    missing_canonical = [c for c in CANONICAL_FEATURES if c not in df.columns]
    if missing_canonical:
        raise ValueError(f"Pipeline missing canonical features: {missing_canonical}")
    # ──────────────────────────────────────────────────────────────────────────────────

    # ── Load BitNet runner ───────────────────────────────────────────────────────────
    _er_section = config.get("engine_runner") or {}
    model_path = _er_section.get("model_path")
    if not model_path:
        raise KeyError(
            "run_backtest: 'model_path' missing from 'engine_runner' section. "
            "Add it to configs/production/v1_multi_2026_03.json under 'engine_runner'."
        )
    try:
        runner_bitnet = BitNetRunner(model_path)
        logger.info("BitNetRunner loaded from '%s'", model_path)
    except FileNotFoundError as exc:
        logger.critical("BitNetRunner: %s", exc)
        raise

    # ── Metrics Tracking ─────────────────────────────────────────────────────────────
    accept_count = 0
    reject_count = 0
    reason_counts = {
        "bitnet_reject": 0,
        "no_trade": 0,
        "error": 0
    }
    accepted_by_score = 0
    accepted_by_debug_fallback = 0
    accepted_by_override = 0
    adapter_reject_count = 0
    debug_log = []

    # ─────────────────────────────────────────────────────────────────────────────────

    # ── Row loop ─────────────────────────────────────────────────────────────────────
    MAX_DEBUG_ROWS = 10
    PROGRESS_INTERVAL = 1000
    total_rows = len(df)
    
    for i in range(total_rows):
        try:
            row = df.iloc[i]

            # ── STRICT SCHEMA ENFORCEMENT — fail loudly on missing features ───
            missing = [k for k in CANONICAL_FEATURES if k not in row.index]
            if missing:
                raise ValueError(f"Row {i}: Missing canonical features: {missing}")

            # SINGLE feature source — no dual pipeline, no vector
            features = {k: float(row[k]) for k in CANONICAL_FEATURES}

            # ── NaN CHECK ─────────────────────────────────────────────────────
            nan_keys = [k for k, v in features.items() if np.isnan(v)]
            if nan_keys:
                raise ValueError(f"Row {i}: NaN detected in features: {nan_keys}")

            # EngineRunner compatibility patch (attach after numeric checks)
            features["_data_integrity"] = "real"

            # ── Debug: first N rows ───────────────────────────────────────────
            if i < MAX_DEBUG_ROWS:
                safe_print(f"\n=== DEBUG ROW {i} ===")
                for k, v in list(features.items())[:10]:
                    safe_print(f"  {k:25s}: {v}")

            # ── BitNet HARD GATEKEEPER ────────────────────────────────────────
            bitnet_result = runner_bitnet.predict(features)
            score = bitnet_result["score"]
            raw_decision = bitnet_result["decision"]
            bitnet_error = bitnet_result.get("error")
            decision = raw_decision

            if gate_mode == "force_accept_baseline":
                decision = "ACCEPT"
                if raw_decision == "ACCEPT":
                    if bitnet_error:
                        accepted_by_debug_fallback += 1
                    else:
                        accepted_by_score += 1
                else:
                    accepted_by_override += 1
            elif raw_decision == "ACCEPT":
                if bitnet_error:
                    accepted_by_debug_fallback += 1
                else:
                    accepted_by_score += 1

            if i < MAX_DEBUG_ROWS:
                safe_print(f"  BITNET: score={score:.4f} → {decision} (raw={raw_decision})")

            logger.debug("Row %d — BitNet score=%.4f, decision=%s", i, score, decision)

            # ── HARD REJECT — EngineRunner NEVER runs ─────────────────────────
            if gate_mode == "hard_gate" and decision != "ACCEPT":
                reject_count += 1
                reason_counts["bitnet_reject"] += 1

                confidence_bucket = (
                    "HIGH_REJECT" if score < 0.2 else
                    "MID_REJECT" if score < 0.5 else
                    "EDGE_REJECT"
                )
                reject_record = {
                    "decision": "BITNET_REJECT",
                    "bitnet_score": score,
                    "candle_idx": i,
                    "confidence_bucket": confidence_bucket,
                    "gate_mode": gate_mode,
                    "months_window": months,
                }
                results.append(reject_record)
                decision_log.write(json.dumps(reject_record) + '\n')
                continue  # ← ABSOLUTE GATE: EngineRunner NEVER executes on reject

            # ── EngineRunner on accepted row (or audit/override mode) ─────────
            accept_count += 1

            result = runner.run(features, context={})
            result = _to_serializable(result)

            if str(result.get("reject_stage", "")) == "adapter":
                adapter_reject_count += 1

            result.update({
                "bitnet_score": score,
                "bitnet_decision": decision,
                "bitnet_raw_decision": raw_decision,
                "bitnet_error": bitnet_error,
                "candle_idx": i,
                "gate_mode": gate_mode,
                "months_window": months,
            })

            results.append(result)
            decision_log.write(json.dumps(result) + '\n')

            # Save debug sample
            if i < MAX_DEBUG_ROWS:
                debug_log.append({
                    "row_id": i,
                    "score": score,
                    "decision": decision,
                })

        except Exception as e:
            logger.error("Row %d failed: %s", i, e)
            reject_count += 1
            reason_counts["error"] += 1
            error_record = {
                "decision": "ERROR",
                "reason": str(e),
                "row_index": int(i),
                "score": 0.0,
            }
            # Guaranteed audit trail — every row produces a collector entry.
            collector.log(error_record)
            results.append(error_record)

            decision_log.write(json.dumps(error_record) + '\n')
            
        # Progress + Flush every N rows
        if (i + 1) % PROGRESS_INTERVAL == 0:
            decision_log.flush()
            progress_pct = ((i + 1) / total_rows) * 100
            safe_print(f"[{i+1:6d}/{total_rows}] {progress_pct:5.1f}% | ACCEPT: {accept_count:5d} | REJECT: {reject_count:5d} | Rate: {(accept_count/(i+1)*100):4.1f}%")
            
    # ─────────────────────────────────────────────────────────────────────────────────

    # Final flush before close
    decision_log.flush()
    
    # Close decision log file
    decision_log.close()
    logger.info("Completed: %d decision records saved to %s", len(results), log_filename)

    # ── FINAL SUMMARY ────────────────────────────────────────────────────────────────
    total = accept_count + reject_count
    accept_rate = (accept_count / total * 100) if total > 0 else 0.0

    safe_print("\n" + "=" * 60)
    safe_print("✅ BITNET BACKTEST COMPLETE")
    safe_print("=" * 60)
    safe_print(f"Total rows processed:    {len(results)}")
    safe_print(f"BitNet ACCEPT:           {accept_count}")
    safe_print(f"BitNet REJECT:           {reject_count}")
    safe_print(f"Accept rate:             {accept_rate:.1f} %")
    safe_print(f"BitNet rejected:         {reason_counts['bitnet_reject']}")
    safe_print(f"Errors:                  {reason_counts['error']}")
    safe_print(f"Accepted by score:       {accepted_by_score}")
    safe_print(f"Accepted by fallback:    {accepted_by_debug_fallback}")
    safe_print(f"Accepted by override:    {accepted_by_override}")
    safe_print(f"Adapter rejects:         {adapter_reject_count}")
    safe_print(f"Gate mode:               {gate_mode}")
    if months is not None:
        safe_print(f"Months window:           {months}")
    safe_print("=" * 60)

    if debug_log:
        safe_print("\n🔍 DEBUG SAMPLES (first accepted rows):")
        for sample in debug_log:
            safe_print(f"Row {sample['row_id']:3d} | Score: {sample['score']:.4f} | {sample['decision']}")

    logger.info(
        "BitNet Summary[%s]: ACCEPT=%d REJECT=%d rate=%.1f%% score_accept=%d fallback_accept=%d override_accept=%d adapter_reject=%d",
        gate_mode,
        accept_count,
        reject_count,
        accept_rate,
        accepted_by_score,
        accepted_by_debug_fallback,
        accepted_by_override,
        adapter_reject_count,
    )

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/production/v1_multi_2026_03.json")
    parser.add_argument("--data", default="data.csv")
    parser.add_argument(
        "--gate-mode",
        default="hard_gate",
        choices=["hard_gate", "score_only_audit", "force_accept_baseline"],
    )
    parser.add_argument("--months", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    results = run_backtest(
        config,
        args.data,
        gate_mode=args.gate_mode,
        months=args.months,
    )
    if args.output:
        # Save results to CSV for shadow promotion
        df_out = pd.DataFrame(results)
        df_out.to_csv(args.output, index=False)
    else:
        safe_print(json.dumps(results, indent=2))
