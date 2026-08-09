"""
XAUUSD_CRT_TRANSITION_TRACE_V1 — transition-rich executable coverage.

Does NOT overwrite baseline V1.

Selection (deterministic):
  - Normal CRT prefix with TRACE OFF
  - Find first executable RANGE → SWEEP (action SWEEP_DETECTED)
  - Capture PRE_CONTEXT (default 8) + transition bar + POST_CONTEXT (default 15)
    = 24 target bars
  - Also continue full-corpus scan (TRACE OFF except when collecting additional
    first-occurrence families) to populate transition coverage corpus index

Emits:
  docs/governance/xauusd_crt_transition_trace/
    xauusd_crt_transition_trace_v1.jsonl
    xauusd_crt_transition_trace_v1.manifest.json
    xauusd_crt_transition_trace_v1.summary.md
    crt_executable_transition_coverage_corpus_v1.json
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
import uuid
from collections import defaultdict
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
from config_layer.crt_engine_v2 import CRTEngine, CRTState  # noqa: E402
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig,
    CandleLoader,
    HTFBuilder,
    guard_xauusd_csv_path,
    load_prod_config_from_registry,
)
from config_layer.production_config import PROD_VERSION  # noqa: E402
from runtime.crt_baseline_trace import (  # noqa: E402
    CRTBaselineTraceHooks,
    TRACE_SCHEMA_VERSION,
    build_bar_record,
    classify_output,
    git_meta,
    sha256_file,
    _jsonable,
)

CORPUS_PIN = "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
CORPUS_ROWS = 47275
PRE_N = 8
POST_N = 15
WINDOW_N = PRE_N + 1 + POST_N  # 24
OUT_DIR = ROOT / "docs" / "governance" / "xauusd_crt_transition_trace"

# Transition families for coverage corpus (from → to / action tags)
FAMILY_SPECS = [
    {"family_id": "RANGE_TO_SWEEP", "from": "RANGE", "to": "SWEEP", "actions": {"SWEEP_DETECTED"}},
    {"family_id": "RANGE_TO_SHADOW", "from": "RANGE", "to": "SHADOW_PENDING", "actions": {"SHADOW_SWEEP_DETECTED"}},
    {"family_id": "SHADOW_TO_EXPANSION", "from": "SHADOW_PENDING", "to": "EXPANSION", "actions": {"SHADOW_EXPANSION_CONFIRMED"}},
    {"family_id": "SWEEP_TO_DISPLACEMENT", "from": "SWEEP", "to": "DISPLACEMENT", "actions": {"DISPLACEMENT_CONFIRMED"}},
    {"family_id": "DISPLACEMENT_TO_EXPANSION", "from": "DISPLACEMENT", "to": "EXPANSION", "actions": {"EXPANSION_CONFIRMED"}},
    {"family_id": "EXPANSION_TO_RETEST", "from": "EXPANSION", "to": "RETEST", "actions": {"RETEST_CONFIRMED"}},
    {"family_id": "EXPANSION_TO_EXPIRED", "from": "EXPANSION", "to": "EXPIRED", "actions": {"EXPANSION_EXPIRED"}},
    {"family_id": "EXPIRED_TO_RANGE", "from": "EXPIRED", "to": "RANGE", "actions": {"EXPANSION_TTL_RESET"}},
    {"family_id": "RETEST_TO_EXECUTION", "from": "RETEST", "to": "EXECUTION", "actions": set()},  # soft-conf path
    {"family_id": "EXECUTION_TO_RESOLUTION", "from": "EXECUTION", "to": "RESOLUTION", "actions": set()},
    {"family_id": "RESET_TO_RANGE", "from": "*", "to": "RANGE", "actions": {"RESET", "SWEEP_EXPIRED", "FILTER_REJECTED", "SHADOW_LEAK"}},
    {"family_id": "TRADE_OPENED", "from": "*", "to": "*", "actions": set()},  # substring TRADE_OPENED
    {"family_id": "TRADE_EXIT", "from": "*", "to": "*", "actions": set()},
]


def deep_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): deep_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [deep_jsonable(v) for v in obj]
    return _jsonable(obj)


def load_configs():
    crt_cfg = load_prod_config_from_registry(PROD_VERSION, "XAUUSD")
    bt_cfg = BacktestConfig.from_prod_config(instrument="XAUUSD", crt_config=crt_cfg)
    return bt_cfg, crt_cfg


def effective_config_snapshot(crt_cfg, prod_sha: str) -> dict:
    raw = {}
    for f in dataclasses.fields(crt_cfg):
        try:
            raw[f.name] = _jsonable(getattr(crt_cfg, f.name))
        except Exception as e:
            raw[f.name] = f"<error {e}>"
    return {
        "config_file_path": "configs/production/v2_multi_2026_04.json",
        "config_file_sha256": prod_sha,
        "prod_version": (ROOT / "configs/production/ACTIVE_VERSION").read_text(encoding="utf-8").strip(),
        "effective_crt_config": raw,
        "constructor_mapping": "load_prod_config_from_registry + BacktestConfig.from_prod_config",
        "runtime_overrides": {},
        "environment_overrides": {
            "TRUST_INTRABAR_TOUCH": os.environ.get("TRUST_INTRABAR_TOUCH"),
            "BACKTEST_ENGINE_GATE": os.environ.get("BACKTEST_ENGINE_GATE"),
        },
        "note": "CRT process_candle does not consume 38-dim FeaturePipeline vector for guards.",
    }


def match_family(state_before: str, state_after: str, action: str) -> list[str]:
    hits = []
    a = action or ""
    for fam in FAMILY_SPECS:
        fid = fam["family_id"]
        if fid == "TRADE_OPENED" and "TRADE_OPENED" in a:
            hits.append(fid)
            continue
        if fid == "TRADE_EXIT" and a.startswith("TRADE_") and "OPENED" not in a:
            hits.append(fid)
            continue
        fr, to = fam["from"], fam["to"]
        acts = fam["actions"]
        from_ok = fr == "*" or fr == state_before
        to_ok = to == "*" or to == state_after
        act_ok = (not acts) or (a in acts)
        # Prefer action match when actions specified
        if acts and a in acts and from_ok:
            hits.append(fid)
        elif not acts and from_ok and to_ok and state_before != state_after:
            if fid in ("RETEST_TO_EXECUTION", "EXECUTION_TO_RESOLUTION"):
                if state_before == fr and state_after == to:
                    hits.append(fid)
    # also pure state edge
    edge = f"{state_before}->{state_after}"
    if state_before != state_after:
        for fam in FAMILY_SPECS:
            if fam["from"] == state_before and fam["to"] == state_after:
                if fam["family_id"] not in hits:
                    hits.append(fam["family_id"])
    return hits


def make_bar_record(
    *,
    run_id,
    git,
    corpus_rel,
    corpus_sha,
    prod_sha,
    eff_cfg,
    candle_idx,
    candle,
    ts_key,
    feature_ts_to_idx,
    feature_vectors,
    hooks,
    events_after,
    result,
    sequence,
    window_role,
    families,
):
    fv_idx = feature_ts_to_idx.get(ts_key, -1)
    if fv_idx < 0:
        values_list = [None] * 38
        values_by_name = {n: None for n in CANONICAL_FEATURES}
        missing_feat = True
    else:
        row = feature_vectors[fv_idx]
        values_list = [float(x) for x in row]
        values_by_name = {CANONICAL_FEATURES[i]: values_list[i] for i in range(38)}
        missing_feat = False

    identity = {
        "trace_schema_version": TRACE_SCHEMA_VERSION,
        "run_id": run_id,
        "trace_sequence": sequence,
        "window_role": window_role,
        "transition_families": families,
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
        "artifact_id": "XAUUSD_CRT_TRANSITION_TRACE_V1",
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
        "feature_count": 38,
        "feature_names_in_canonical_order": list(CANONICAL_FEATURES),
        "values_by_name": values_by_name,
        "values_in_canonical_order": values_list,
        "schema_hash": SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "feature_vector_index": fv_idx,
        "lookup_miss": missing_feat,
        "consumed_by_crt_guards": False,
        "consumption_note": "38-vector not read by process_candle transition guards",
    }
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
        if rec["integrity"]["status"] == "COMPLETE":
            rec["integrity"]["status"] = "PARTIAL"
    return rec


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = (
        f"xauusd-crt-transition-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
        f"{uuid.uuid4().hex[:8]}"
    )
    git = git_meta(ROOT)

    csv_path = guard_xauusd_csv_path(str(ROOT / "data/XAUUSD_M15.csv"), "XAUUSD")
    corpus = Path(csv_path)
    corpus_sha = sha256_file(corpus)
    if corpus_sha != CORPUS_PIN:
        print(f"BLOCKED: corpus hash mismatch {corpus_sha}")
        return 2
    try:
        corpus_rel = str(corpus.resolve().relative_to(ROOT)).replace("\\", "/")
    except Exception:
        corpus_rel = "data/mt5/XAUUSD_M15.csv"

    prod_path = ROOT / "configs/production/v2_multi_2026_04.json"
    prod_sha = sha256_file(prod_path)
    bt_cfg, crt_cfg = load_configs()
    eff_cfg = effective_config_snapshot(crt_cfg, prod_sha)

    # FeaturePipeline once
    raw_df = pd.read_csv(csv_path)
    raw_df.columns = [c.strip().lower() for c in raw_df.columns]
    pipeline = FeaturePipeline(raw_df)
    enriched_df, feature_vectors = pipeline.run()
    ts_series = pd.to_datetime(enriched_df["timestamp"])
    feature_ts_to_idx = {
        ts.strftime("%Y-%m-%d %H:%M:%S"): i for i, ts in enumerate(ts_series)
    }

    # ── Pass 1: find first RANGE→SWEEP index and first occurrence of each family ──
    engine = CRTEngine(crt_cfg)
    htf = HTFBuilder(bt_cfg.htf_candles_per_range, "XAUUSD")
    loader = CandleLoader(str(csv_path), "XAUUSD")

    candle_idx = 0
    warmup_done = False
    initialised = False
    first_sweep_stream_idx = None  # 1-based candle_idx of selected SWEEP_DETECTED
    first_family_hits: dict[str, dict] = {}
    history: list[dict] = []  # lightweight per-bar history after init

    def _window_feature_ready(hist: list[dict], center_i: int) -> bool:
        """PRE+center+POST timestamps all present in finalized FeaturePipeline map."""
        lo = center_i - PRE_N
        hi = center_i + POST_N
        if lo < 0 or hi >= len(hist):
            return False
        for j in range(lo, hi + 1):
            if hist[j]["ts"] not in feature_ts_to_idx:
                return False
        return True

    for candle in loader.stream():
        candle_idx += 1
        htf.push(candle)
        if not warmup_done:
            if candle_idx < bt_cfg.warmup_candles:
                continue
            warmup_done = True
        if not initialised:
            if htf.seed_candles():
                engine.initialise_range(htf.seed_candles(), htf.current_htf_id, "UNKNOWN")
                initialised = True
            continue

        state_before = engine.state.current_state.name
        result = engine.process_candle(candle, htf.current_htf_id)
        state_after = engine.state.current_state.name
        action = result.get("action", "NONE")
        ts_key = candle.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        families = match_family(state_before, state_after, action)
        rec_lite = {
            "candle_idx": candle_idx,
            "ts": ts_key,
            "state_before": state_before,
            "state_after": state_after,
            "action": action,
            "families": families,
            "feature_ready": ts_key in feature_ts_to_idx,
        }
        history.append(rec_lite)

        # First SWEEP_DETECTED with PRE_N history AND full 24-bar feature coverage
        if action == "SWEEP_DETECTED" and first_sweep_stream_idx is None:
            hist_i = len(history) - 1
            if hist_i >= PRE_N and _window_feature_ready(history, hist_i):
                first_sweep_stream_idx = candle_idx

        for fid in families:
            if fid not in first_family_hits:
                first_family_hits[fid] = {
                    "family_id": fid,
                    "first_candle_idx": candle_idx,
                    "timestamp": ts_key,
                    "state_before": state_before,
                    "state_after": state_after,
                    "action": action,
                    "status": "OBSERVED_TRUE",
                    "feature_ready": ts_key in feature_ts_to_idx,
                }

    # Fallback: any SWEEP with PRE_N + feature window readiness (scan history)
    if first_sweep_stream_idx is None:
        for i, h in enumerate(history):
            if h["action"] == "SWEEP_DETECTED" and i >= PRE_N and _window_feature_ready(history, i):
                first_sweep_stream_idx = h["candle_idx"]
                break
    if first_sweep_stream_idx is None:
        print("BLOCKED: no RANGE→SWEEP with PRE/POST feature-ready context found")
        return 2

    # Window: 8 before + transition + 15 after
    hist_by_idx = {h["candle_idx"]: i for i, h in enumerate(history)}
    if first_sweep_stream_idx not in hist_by_idx:
        print("BLOCKED: first sweep not in post-init history")
        return 2
    h_i = hist_by_idx[first_sweep_stream_idx]
    start_i = max(0, h_i - PRE_N)
    end_i = min(len(history) - 1, h_i + POST_N)
    window_hist = history[start_i : end_i + 1]
    window_idxs = {h["candle_idx"] for h in window_hist}
    # roles
    role_by_idx = {}
    for h in window_hist:
        if h["candle_idx"] < first_sweep_stream_idx:
            role_by_idx[h["candle_idx"]] = "PRE_CONTEXT"
        elif h["candle_idx"] == first_sweep_stream_idx:
            role_by_idx[h["candle_idx"]] = "TRANSITION"
        else:
            role_by_idx[h["candle_idx"]] = "POST_CONTEXT"

    # ── Pass 2: replay with trace ON only for window ──
    engine2 = CRTEngine(crt_cfg)
    hooks = CRTBaselineTraceHooks()
    engine2.baseline_trace = hooks
    htf2 = HTFBuilder(bt_cfg.htf_candles_per_range, "XAUUSD")
    loader2 = CandleLoader(str(csv_path), "XAUUSD")

    records = []
    candle_idx = 0
    warmup_done = False
    initialised = False
    seq = 0
    state_at_window_start = None
    state_at_window_end = None

    for candle in loader2.stream():
        candle_idx += 1
        htf2.push(candle)
        if not warmup_done:
            if candle_idx < bt_cfg.warmup_candles:
                continue
            warmup_done = True
        if not initialised:
            if htf2.seed_candles():
                engine2.initialise_range(htf2.seed_candles(), htf2.current_htf_id, "UNKNOWN")
                initialised = True
            continue

        in_window = candle_idx in window_idxs
        if in_window and state_at_window_start is None:
            state_at_window_start = engine2.state.current_state.name

        if in_window:
            hooks.enabled = True
        else:
            hooks.enabled = False
            engine2.sm.trace_hooks = None

        events_before = len(engine2.state.event_log)
        state_before = engine2.state.current_state.name
        result = engine2.process_candle(candle, htf2.current_htf_id)
        state_after = engine2.state.current_state.name
        action = result.get("action", "NONE")
        events_after = list(engine2.state.event_log[events_before:])
        ts_key = candle.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        if not in_window:
            continue

        families = match_family(state_before, state_after, action)
        rec = make_bar_record(
            run_id=run_id,
            git=git,
            corpus_rel=corpus_rel,
            corpus_sha=corpus_sha,
            prod_sha=prod_sha,
            eff_cfg=eff_cfg,
            candle_idx=candle_idx,
            candle=candle,
            ts_key=ts_key,
            feature_ts_to_idx=feature_ts_to_idx,
            feature_vectors=feature_vectors,
            hooks=hooks,
            events_after=events_after,
            result=result,
            sequence=seq,
            window_role=role_by_idx.get(candle_idx, "TARGET"),
            families=families,
        )
        records.append(rec)
        seq += 1
        state_at_window_end = engine2.state.current_state.name

        if candle_idx == max(window_idxs):
            hooks.enabled = False
            engine2.sm.trace_hooks = None
            break

    if len(records) < PRE_N + 1:
        print(f"BLOCKED: insufficient window records {len(records)}")
        return 2

    # Write JSONL
    trace_path = OUT_DIR / "xauusd_crt_transition_trace_v1.jsonl"
    with trace_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(deep_jsonable(r), ensure_ascii=False) + "\n")
    trace_sha = sha256_file(trace_path)

    # Aggregate inputs/config from window
    input_usage: dict[str, dict] = {}
    config_usage: dict[str, dict] = {}
    for r in records:
        for inp in r["crt_inputs"]["inputs"]:
            n = inp.get("name") or "?"
            u = input_usage.setdefault(
                n,
                {
                    "input": n,
                    "source_class": inp.get("source_class"),
                    "source_name": inp.get("source_name"),
                    "formula_id": inp.get("formula_id"),
                    "feature_id": inp.get("feature_id"),
                    "canonical_feature": bool(
                        inp.get("feature_id") in CANONICAL_FEATURES if inp.get("feature_id") else False
                    ),
                    "bars_read": 0,
                    "guards_affected": set(),
                    "provenance_status": inp.get("provenance_status"),
                },
            )
            u["bars_read"] += 1
        for g in r["state_transition"]["guards_evaluated"]:
            gid = g.get("guard_id")
            for inp in g.get("operands") or []:
                n = inp.get("name") or "?"
                if n in input_usage:
                    input_usage[n]["guards_affected"].add(gid)
            for th in g.get("thresholds") or []:
                ck = th.get("config_key") or th.get("name")
                u = config_usage.setdefault(
                    ck,
                    {
                        "config_key": ck,
                        "effective_value": th.get("runtime_value"),
                        "bars_read": 0,
                        "guards_affected": set(),
                        "provenance_status": "PROVEN",
                    },
                )
                u["bars_read"] += 1
                u["guards_affected"].add(gid)

    for u in input_usage.values():
        u["guards_affected"] = sorted(u["guards_affected"])
    for u in config_usage.values():
        u["guards_affected"] = sorted(u["guards_affected"])

    # Coverage corpus
    coverage_families = []
    for fam in FAMILY_SPECS:
        fid = fam["family_id"]
        if fid in first_family_hits:
            hit = dict(first_family_hits[fid])
            hit["classification"] = "OBSERVED_TRUE"
            coverage_families.append(hit)
        else:
            coverage_families.append(
                {
                    "family_id": fid,
                    "classification": "REACHABLE_NOT_OBSERVED"
                    if fid
                    not in (
                        # none forced unreachable
                    )
                    else "UNKNOWN",
                    "status": "NOT_OBSERVED_IN_CORPUS_SCAN",
                    "note": "No first occurrence in full Phase-1 corpus scan under active config",
                }
            )

    # Refine: observed false guards in window
    observed_false_guards = []
    observed_true_guards = []
    for r in records:
        for g in r["state_transition"]["guards_evaluated"]:
            entry = {
                "timestamp": r["trace_identity"]["timestamp"],
                "guard_id": g["guard_id"],
                "from_state": g["from_state"],
                "candidate_to_state": g["candidate_to_state"],
                "result": g["result"],
                "window_role": r["trace_identity"]["window_role"],
            }
            if g["result"]:
                observed_true_guards.append(entry)
            else:
                observed_false_guards.append(entry)

    coverage = {
        "_doc": "CRT_EXECUTABLE_TRANSITION_COVERAGE_CORPUS V1 — first-occurrence scan + primary transition window",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "corpus_path": corpus_rel,
        "corpus_sha256": corpus_sha,
        "primary_window": {
            "anchor_family": "RANGE_TO_SWEEP",
            "anchor_candle_idx": first_sweep_stream_idx,
            "anchor_timestamp": next(
                h["ts"] for h in history if h["candle_idx"] == first_sweep_stream_idx
            ),
            "pre_context_bars": PRE_N,
            "post_context_bars": POST_N,
            "records_captured": len(records),
            "trace_sha256": trace_sha,
        },
        "families": coverage_families,
        "window_guard_true": observed_true_guards,
        "window_guard_false": observed_false_guards,
        "full_scan_family_first_hits": first_family_hits,
        "classification_legend": {
            "OBSERVED_TRUE": "At least one occurrence in corpus scan or window",
            "OBSERVED_FALSE": "Guard evaluated false in instrumented window",
            "REACHABLE_NOT_OBSERVED": "Family defined in code; not hit in this corpus/config scan",
            "UNREACHABLE": "Structurally impossible under current code (none asserted yet)",
            "UNKNOWN": "Insufficient evidence",
        },
        "architectural_note": (
            "CRT transition guards do not consume the 38-dim FeaturePipeline vector. "
            "Coverage is over CRT-local inputs + config + state memory."
        ),
    }
    cov_path = OUT_DIR / "crt_executable_transition_coverage_corpus_v1.json"
    cov_path.write_text(json.dumps(deep_jsonable(coverage), indent=2) + "\n", encoding="utf-8")

    # Manifest
    anchor_ts = next(h["ts"] for h in history if h["candle_idx"] == first_sweep_stream_idx)
    manifest = {
        "artifact_id": "XAUUSD_CRT_TRANSITION_TRACE_V1",
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_commit": git["repository_commit"],
        "dirty_worktree_status": git["dirty_worktree_status"],
        "does_not_overwrite": "XAUUSD_CRT_BASELINE_TRACE_V1",
        "baseline_v1_sha256": "26e185b943ec5caeee31d32a0b598b543f00a48f953d9fefc9a272eb77ea72d7",
        "corpus_path": corpus_rel,
        "corpus_hash": corpus_sha,
        "corpus_rows": CORPUS_ROWS,
        "config_path": "configs/production/v2_multi_2026_04.json",
        "config_hash": prod_sha,
        "config_id": "v2_multi_2026_04",
        "prod_version": eff_cfg["prod_version"],
        "feature_schema_hash": SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "canonical_feature_count": 38,
        "selection_rule": (
            f"First SWEEP_DETECTED after normal warmup+init; capture {PRE_N} bars before + "
            f"transition bar + {POST_N} bars after (target up to {WINDOW_N}). "
            "Full-corpus first-occurrence scan for coverage corpus (trace off)."
        ),
        "pre_context_bars": PRE_N,
        "post_context_bars": POST_N,
        "anchor_family": "RANGE_TO_SWEEP",
        "anchor_timestamp": anchor_ts,
        "anchor_candle_idx": first_sweep_stream_idx,
        "target_start_timestamp": records[0]["trace_identity"]["timestamp"],
        "target_end_timestamp": records[-1]["trace_identity"]["timestamp"],
        "target_bar_count": len(records),
        "CRT_state_at_window_start": state_at_window_start,
        "CRT_state_at_window_end": state_at_window_end,
        "trace_file_path": str(trace_path.relative_to(ROOT)).replace("\\", "/"),
        "trace_sha256": trace_sha,
        "coverage_corpus_path": str(cov_path.relative_to(ROOT)).replace("\\", "/"),
        "families_observed_in_full_scan": sorted(first_family_hits.keys()),
        "trace_completeness_verdict": (
            "COMPLETE"
            if all(r["integrity"]["status"] == "COMPLETE" for r in records)
            else "PARTIAL"
        ),
        "behavior_parity_verdict": "INHERITED_FROM_BASELINE_HOOKS_TESTS",
    }
    man_path = OUT_DIR / "xauusd_crt_transition_trace_v1.manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Summary MD
    lines = [
        "# XAUUSD CRT Transition Trace V1 — Summary",
        "",
        f"**run_id:** `{run_id}`  ",
        f"**anchor:** RANGE→SWEEP @ `{anchor_ts}` (candle_idx={first_sweep_stream_idx})  ",
        f"**window:** {records[0]['trace_identity']['timestamp']} → {records[-1]['trace_identity']['timestamp']} "
        f"({len(records)} bars; PRE={PRE_N} +1 + POST={POST_N})  ",
        f"**states:** {state_at_window_start} → {state_at_window_end}  ",
        f"**trace_sha256:** `{trace_sha}`  ",
        f"**does not overwrite baseline V1** (`26e185b9…`)",
        "",
        "## Window matrix",
        "",
        "| seq | role | ts | before | after | action | guards | class | status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        st = r["state_transition"]
        lines.append(
            f"| {r['trace_identity']['trace_sequence']} | {r['trace_identity']['window_role']} | "
            f"{r['trace_identity']['timestamp']} | {st['state_before']} | {st['state_after']} | "
            f"{(st.get('action') or {}).get('action')} | {r['integrity']['evaluated_guard_count']} | "
            f"{r['outputs']['output_classification']} | {r['integrity']['status']} |"
        )
    lines += ["", "## Full-scan first family hits", ""]
    for fid, hit in sorted(first_family_hits.items()):
        lines.append(
            f"- `{fid}` @ {hit['timestamp']} {hit['state_before']}→{hit['state_after']} action={hit['action']}"
        )
    lines += ["", "## Families not observed in full scan", ""]
    for fam in coverage_families:
        if fam.get("classification") == "REACHABLE_NOT_OBSERVED":
            lines.append(f"- `{fam['family_id']}`")
    lines += ["", "## CRT inputs observed in window", ""]
    for u in input_usage.values():
        lines.append(
            f"- `{u['input']}` class={u['source_class']} bars={u['bars_read']} "
            f"canonical_name={u['canonical_feature']} formula={u.get('formula_id')}"
        )
    lines += ["", "## Config keys observed in window", ""]
    if not config_usage:
        lines.append("- _(none — no thresholded try_* path entered in window after sweep)_")
    for u in config_usage.values():
        lines.append(f"- `{u['config_key']}` value={u['effective_value']} bars={u['bars_read']}")
    sum_path = OUT_DIR / "xauusd_crt_transition_trace_v1.summary.md"
    sum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT_DIR / "xauusd_crt_transition_trace_v1.summary.json").write_text(
        json.dumps(
            deep_jsonable(
                {
                    "input_usage": list(input_usage.values()),
                    "config_usage": list(config_usage.values()),
                    "first_family_hits": first_family_hits,
                    "records": len(records),
                }
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("SUCCESS")
    print("run_id", run_id)
    print("anchor", anchor_ts, "idx", first_sweep_stream_idx)
    print("records", len(records))
    print("trace_sha256", trace_sha)
    print("families_observed", sorted(first_family_hits.keys()))
    print("completeness", manifest["trace_completeness_verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
