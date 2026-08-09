"""
XAUUSD CRT baseline 16-bar (4h M15) executable trace runner.

Reuses production FeaturePipeline + CRTEngine construction/replay semantics.
Trace disabled during prefix; enabled for exactly 16 consecutive finalized bars.

Does NOT redesign CRT, recompute features, or enable MSIP.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd  # noqa: E402

from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import (  # noqa: E402
    CANONICAL_FEATURES,
    FEATURE_ORDER_HASH,
    SCHEMA_HASH,
)
from config_layer.crt_engine_v2 import CRTEngine  # noqa: E402
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig,
    CandleLoader,
    HTFBuilder,
    guard_xauusd_csv_path,
)
from runtime.crt_baseline_trace import (  # noqa: E402
    CRTBaselineTraceHooks,
    TRACE_SCHEMA_VERSION,
    build_bar_record,
    classify_output,
    git_meta,
    sha256_file,
    _jsonable,
)

# Executable Phase-1 frozen candidate (fail-closed binding):
# src/data_ingestion/xauusd_phase1_candidate.py → data/mt5/XAUUSD_M15.csv
CORPUS_REL = "data/mt5/XAUUSD_M15.csv"
CORPUS_PIN = "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
CORPUS_ROWS = 47275
OUT_DIR = ROOT / "docs" / "governance" / "xauusd_crt_baseline_trace"
TARGET_N = 16


def load_crt_and_backtest_config():
    """Match BacktestRunner CLI path: load_prod_config_from_registry + BacktestConfig.from_prod_config."""
    from config_layer.production_config import PROD_VERSION
    from runtime.backtest_v2 import load_prod_config_from_registry

    crt_cfg = load_prod_config_from_registry(PROD_VERSION, "XAUUSD")
    bt_cfg = BacktestConfig.from_prod_config(instrument="XAUUSD", crt_config=crt_cfg)
    return bt_cfg, crt_cfg


def effective_config_snapshot(crt_cfg) -> dict:
    raw = {}
    for f in dataclasses.fields(crt_cfg):
        try:
            raw[f.name] = _jsonable(getattr(crt_cfg, f.name))
        except Exception as e:
            raw[f.name] = f"<error {e}>"
    return {
        "config_file_path": "configs/production/v2_multi_2026_04.json",
        "prod_version": (ROOT / "configs/production/ACTIVE_VERSION").read_text(encoding="utf-8").strip(),
        "effective_crt_config": raw,
        "constructor_mapping": "BacktestConfig.from_prod_config → CRTConfig fields",
        "runtime_overrides": {},
        "environment_overrides": {
            "TRUST_INTRABAR_TOUCH": os.environ.get("TRUST_INTRABAR_TOUCH"),
            "BACKTEST_ENGINE_GATE": os.environ.get("BACKTEST_ENGINE_GATE"),
        },
        "post_construction_mutations": [],
        "note": "CRT process_candle does not consume the 38-dim FeaturePipeline vector for guards.",
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"xauusd-crt-trace-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    git = git_meta(ROOT)

    # Fail-closed XAUUSD binding (same as BacktestRunner) — rewrites to Phase-1 candidate
    csv_path = guard_xauusd_csv_path(str(ROOT / "data/XAUUSD_M15.csv"), "XAUUSD")
    corpus = Path(csv_path)
    corpus_sha = sha256_file(corpus)
    if corpus_sha != CORPUS_PIN:
        print(f"BLOCKED: corpus hash mismatch {corpus_sha} != {CORPUS_PIN}")
        return 2
    # relative path for manifest
    try:
        corpus_rel = str(corpus.resolve().relative_to(ROOT)).replace("\\", "/")
    except Exception:
        corpus_rel = CORPUS_REL

    prod_path = ROOT / "configs/production/v2_multi_2026_04.json"
    prod_sha = sha256_file(prod_path)

    bt_cfg, crt_cfg = load_crt_and_backtest_config()
    eff_cfg = effective_config_snapshot(crt_cfg)
    eff_cfg["config_file_sha256"] = prod_sha

    # FeaturePipeline full corpus
    raw_df = pd.read_csv(csv_path)
    raw_df.columns = [c.strip().lower() for c in raw_df.columns]
    pipeline = FeaturePipeline(raw_df)
    enriched_df, feature_vectors = pipeline.run()
    ts_series = pd.to_datetime(enriched_df["timestamp"])
    feature_ts_to_idx = {
        ts.strftime("%Y-%m-%d %H:%M:%S"): i for i, ts in enumerate(ts_series)
    }
    # First finalized eligible bar = first timestamp present in feature map
    finalized_ts_ordered = list(feature_ts_to_idx.keys())
    if len(finalized_ts_ordered) < TARGET_N:
        print("BLOCKED: fewer than 16 finalized feature bars")
        return 2

    # Selection: first finalized bar + next 15 consecutive finalized timestamps
    target_ts = finalized_ts_ordered[:TARGET_N]
    target_start = target_ts[0]
    target_end = target_ts[-1]
    target_set = set(target_ts)

    # CRT engine + HTF like backtest
    engine = CRTEngine(crt_cfg)
    hooks = CRTBaselineTraceHooks()
    engine.baseline_trace = hooks
    htf = HTFBuilder(bt_cfg.htf_candles_per_range, "XAUUSD")
    loader = CandleLoader(str(csv_path), "XAUUSD")

    records = []
    candle_idx = 0
    warmup_done = False
    initialised = False
    prefix_processed = 0
    target_count = 0
    state_at_target_start = None
    state_at_target_end = None
    tracing = False

    for candle in loader.stream():
        candle_idx += 1
        htf.push(candle)

        if not warmup_done:
            if candle_idx < bt_cfg.warmup_candles:
                continue
            warmup_done = True

        if not initialised:
            if htf.seed_candles():
                session = "UNKNOWN"
                engine.initialise_range(htf.seed_candles(), htf.current_htf_id, session)
                initialised = True
            continue

        ts_key = candle.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        is_target = ts_key in target_set

        if is_target and not tracing:
            # enable immediately before first target
            tracing = True
            state_at_target_start = engine.state.current_state.name

        if tracing and is_target:
            hooks.enabled = True
        else:
            hooks.enabled = False
            engine.sm.trace_hooks = None

        events_before = len(engine.state.event_log)
        result = engine.process_candle(candle, htf.current_htf_id)
        events_after = list(engine.state.event_log[events_before:])

        if not (tracing and is_target):
            prefix_processed += 1
            continue

        # Capture bar record
        fv_idx = feature_ts_to_idx.get(ts_key, -1)
        if fv_idx < 0:
            values_list = [None] * len(CANONICAL_FEATURES)
            values_by_name = {n: None for n in CANONICAL_FEATURES}
            missing_feat = True
        else:
            row = feature_vectors[fv_idx]
            values_list = [float(x) for x in row]
            # de-literalized 2026-08-01 (was hardcoded range(38); schema v4.0 is 39-dim, so the
            # old literal silently dropped the last canonical name from values_by_name).
            values_by_name = {
                CANONICAL_FEATURES[i]: values_list[i] for i in range(len(CANONICAL_FEATURES))
            }
            missing_feat = False

        identity = {
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "run_id": run_id,
            "trace_sequence": target_count,
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "bar_index": candle_idx,
            "timestamp": ts_key,
            "corpus_path": corpus_rel,
            "corpus_sha256": corpus_sha,
            "repository_commit": git["repository_commit"],
            "dirty_worktree_status": git["dirty_worktree_status"],
            "production_config_path": "configs/production/v2_multi_2026_04.json",
            "production_config_sha256": prod_sha,
            "config_id": "v2_multi_2026_04",
            "prod_version": eff_cfg["prod_version"],
            "canonical_schema_hash": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH,
        }
        raw_bar = {
            "timestamp": ts_key,
            "open": float(candle.open),
            "high": float(candle.high),
            "low": float(candle.low),
            "close": float(candle.close),
            "volume": float(candle.volume) if candle.volume is not None else None,
        }
        canon = {
            "feature_count": len(CANONICAL_FEATURES),
            "feature_names_in_canonical_order": list(CANONICAL_FEATURES),
            "values_by_name": values_by_name,
            "values_in_canonical_order": values_list,
            "schema_hash": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH,
            "feature_vector_index": fv_idx,
            "lookup_miss": missing_feat,
        }
        # Invariants
        assert canon["feature_count"] == len(CANONICAL_FEATURES)
        assert set(canon["values_by_name"].keys()) == set(CANONICAL_FEATURES)
        assert len(canon["values_in_canonical_order"]) == len(CANONICAL_FEATURES)

        events_ser = []
        for ev in events_after:
            events_ser.append(
                {
                    "event": getattr(ev, "event", None),
                    "timestamp": _jsonable(getattr(ev, "timestamp", None)),
                    "candle_index": getattr(ev, "candle_index", None),
                    "state_from": getattr(ev, "state_from", None),
                    "state_to": getattr(ev, "state_to", None),
                    "reason": getattr(ev, "reason", None),
                    "direction": getattr(ev, "direction", None),
                    "price": getattr(ev, "price", None),
                }
            )

        rec = build_bar_record(
            identity=identity,
            raw_bar=raw_bar,
            canonical_features=canon,
            hooks=hooks,
            effective_config=eff_cfg,
            events_emitted=events_ser,
            output_classification=classify_output(result),
        )
        if missing_feat:
            rec["integrity"]["warnings"].append("feature_timestamp_lookup_miss")
            rec["integrity"]["status"] = "PARTIAL"
        records.append(rec)
        target_count += 1
        state_at_target_end = engine.state.current_state.name

        if target_count >= TARGET_N:
            hooks.enabled = False
            engine.sm.trace_hooks = None
            break

    if target_count != TARGET_N:
        print(f"BLOCKED: captured {target_count} != {TARGET_N}")
        return 2

    # Write JSONL (fully jsonable — no datetime/Enum leakage)
    def _deep_jsonable(obj):
        if isinstance(obj, dict):
            return {str(k): _deep_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_deep_jsonable(v) for v in obj]
        return _jsonable(obj)

    trace_path = OUT_DIR / "xauusd_crt_baseline_trace_v1.jsonl"
    with trace_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(_deep_jsonable(r), ensure_ascii=False) + "\n")
    trace_sha = sha256_file(trace_path)

    # Summaries
    summary_rows = []
    for r in records:
        st = r["state_transition"]
        raw = r["raw_bar"]
        summary_rows.append(
            {
                "timestamp": r["trace_identity"]["timestamp"],
                "OHLC": f"{raw['open']}/{raw['high']}/{raw['low']}/{raw['close']}",
                "state_before": st["state_before"],
                "evaluated_guard_count": r["integrity"]["evaluated_guard_count"],
                "true_guard_count": r["integrity"]["true_guard_count"],
                "selected_transition": st["selected_transition"],
                "state_after": st["state_after"],
                "event_count": len(r["outputs"]["events_emitted"]),
                "output_classification": r["outputs"]["output_classification"],
                "trade_emitted": r["outputs"]["trade_output"] is not None,
                "trace_status": r["integrity"]["status"],
            }
        )

    # Feature variation
    feat_var = []
    for i, name in enumerate(CANONICAL_FEATURES):
        series = [r["canonical_features"]["values_in_canonical_order"][i] for r in records]
        finite = [float(x) for x in series if isinstance(x, (int, float))]
        feat_var.append(
            {
                "feature": name,
                "min": min(finite) if finite else None,
                "max": max(finite) if finite else None,
                "first": series[0],
                "last": series[-1],
                "changed_across_window": len(set(repr(x) for x in series)) > 1,
            }
        )

    # CRT input usage
    input_usage: dict[str, dict] = {}
    for r in records:
        for inp in r["crt_inputs"]["inputs"]:
            n = inp.get("name") or "?"
            u = input_usage.setdefault(
                n,
                {
                    "input": n,
                    "source_class": inp.get("source_class"),
                    "canonical_feature": inp.get("feature_id") in CANONICAL_FEATURES
                    if inp.get("feature_id")
                    else False,
                    "bars_read": 0,
                    "guards_affected": 0,
                    "provenance_status": inp.get("provenance_status"),
                },
            )
            u["bars_read"] += 1
            u["guards_affected"] += 1

    config_usage: dict[str, dict] = {}
    for r in records:
        for g in r["state_transition"]["guards_evaluated"]:
            for th in g.get("thresholds") or []:
                ck = th.get("config_key") or th.get("name")
                u = config_usage.setdefault(
                    ck,
                    {
                        "config_key": ck,
                        "effective_value": th.get("runtime_value"),
                        "bars_read": 0,
                        "guards_affected": 0,
                        "provenance_status": "PROVEN",
                    },
                )
                u["bars_read"] += 1
                u["guards_affected"] += 1

    manifest = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_commit": git["repository_commit"],
        "dirty_worktree_status": git["dirty_worktree_status"],
        "corpus_path": corpus_rel,
        "corpus_hash": corpus_sha,
        "corpus_rows": CORPUS_ROWS,
        "config_path": "configs/production/v2_multi_2026_04.json",
        "config_hash": prod_sha,
        "config_id": "v2_multi_2026_04",
        "prod_version": eff_cfg["prod_version"],
        "feature_schema_hash": SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "canonical_feature_count": len(CANONICAL_FEATURES),
        "selection_rule": (
            "After FeaturePipeline finalize, take first finalized timestamp and the next "
            "15 consecutive finalized timestamps (16 total). Prefix: full CRT replay from "
            "stream start with warmup+init; trace disabled until first target bar."
        ),
        "prefix_bars_processed": prefix_processed,
        "target_start_timestamp": target_start,
        "target_end_timestamp": target_end,
        "target_bar_count": TARGET_N,
        "CRT_initial_reset_boundary": "initialise_range after warmup_candles + HTF seed",
        "CRT_state_at_target_start": state_at_target_start,
        "CRT_state_at_target_end": state_at_target_end,
        "trace_file_path": str(trace_path.relative_to(ROOT)).replace("\\", "/"),
        "trace_sha256": trace_sha,
        "behavior_parity_verdict": "SEE_TESTS",
        "trace_completeness_verdict": (
            "COMPLETE"
            if all(r["integrity"]["status"] == "COMPLETE" for r in records)
            else "PARTIAL"
        ),
        "notes": [
            "CRT process_candle does not consume the 38-dim FeaturePipeline vector for transition guards.",
            "Canonical features captured by timestamp lookup into batch FeaturePipeline output.",
            "Guard instrumentation covers principal try_sweep_to_displacement / "
            "try_displacement_to_expansion / try_expansion_to_retest decision points; "
            "RANGE sweep detection and soft-confirmation manifold may show fewer guard rows "
            "if those paths were not entered.",
        ],
    }

    man_path = OUT_DIR / "xauusd_crt_baseline_trace_v1.manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Markdown summary
    lines = [
        "# XAUUSD CRT Baseline Trace v1 — Summary",
        "",
        f"**run_id:** `{run_id}`  ",
        f"**target:** {target_start} → {target_end} ({TARGET_N} bars)  ",
        f"**prefix bars (non-target after init):** {prefix_processed}  ",
        f"**state at target start/end:** {state_at_target_start} → {state_at_target_end}  ",
        f"**trace sha256:** `{trace_sha}`  ",
        f"**completeness:** {manifest['trace_completeness_verdict']}",
        "",
        "## 16-bar matrix",
        "",
        "| ts | OHLC | before | guards | true | after | events | class | status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summary_rows:
        lines.append(
            f"| {s['timestamp']} | {s['OHLC']} | {s['state_before']} | "
            f"{s['evaluated_guard_count']} | {s['true_guard_count']} | {s['state_after']} | "
            f"{s['event_count']} | {s['output_classification']} | {s['trace_status']} |"
        )
    lines += ["", "## Canonical feature variation (changed only)", ""]
    for fv in feat_var:
        if fv["changed_across_window"]:
            lines.append(
                f"- `{fv['feature']}`: min={fv['min']} max={fv['max']} first={fv['first']} last={fv['last']}"
            )
    lines += ["", "## CRT input usage", ""]
    for u in input_usage.values():
        lines.append(
            f"- `{u['input']}` class={u['source_class']} bars={u['bars_read']} "
            f"canonical={u['canonical_feature']} prov={u['provenance_status']}"
        )
    lines += ["", "## Config usage", ""]
    for u in config_usage.values():
        lines.append(
            f"- `{u['config_key']}` value={u['effective_value']} guards={u['guards_affected']}"
        )
    lines += [
        "",
        "## Executable coupling note",
        "",
        "FeaturePipeline 38-vector is **decoupled** from CRT guard evaluation. "
        "CRT uses RAW_OHLC + CRT_LOCAL_DERIVED (ATR, body_ratio, wick_size) + STATE_MEMORY + CRTConfig.",
        "",
    ]
    sum_path = OUT_DIR / "xauusd_crt_baseline_trace_v1.summary.md"
    sum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # machine summary json for tests
    (OUT_DIR / "xauusd_crt_baseline_trace_v1.summary.json").write_text(
        json.dumps(
            {
                "summary_rows": summary_rows,
                "feature_variation": feat_var,
                "input_usage": list(input_usage.values()),
                "config_usage": list(config_usage.values()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("SUCCESS")
    print("run_id", run_id)
    print("target", target_start, "->", target_end)
    print("records", len(records))
    print("trace", trace_path)
    print("sha256", trace_sha)
    print("completeness", manifest["trace_completeness_verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
