# -*- coding: utf-8 -*-
"""Read-only CRT state-transition audit for the 4-month XAUUSD window.

Answers: how does the *code* decide SWEEP / DISPLACEMENT / EXPANSION / RETEST,
and what did those predicates look like on two real episodes?

Episodes (from trail_4m_gate0):
  PASS  — RETEST 2026-02-04T09:30 → EXECUTION → TRADE_OPENED SHORT → STOPPED
  FAIL  — RETEST 2026-02-23T17:45 → FILTER_REJECTED off_session:OFF_SESSION

No behavioral changes. No config edits.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from config_layer.production_config import (  # noqa: E402
    get_active_version,
    load_prod_config_from_registry,
)
from features import candle_math  # noqa: E402

RUN = ROOT / (
    "results/runtime_benchmarks/window_search_xauusd/"
    "trail_4m_gate0/run_20260720_022222_XAUUSD"
)
CSV = ROOT / "data" / "XAUUSD_W2026-01-21-to-2026-05-21.csv"
OUT_JSON = ROOT / (
    "results/runtime_benchmarks/window_search_xauusd/"
    "crt_state_transition_audit_4m.json"
)
OUT_MD = ROOT / (
    "results/runtime_benchmarks/window_search_xauusd/"
    "crt_state_transition_audit_4m.md"
)


def _row(ts: str, df: pd.DataFrame) -> pd.Series:
    t = pd.Timestamp(ts)
    m = df[df["timestamp"] == t]
    if m.empty:
        # try without seconds / iso
        m = df[df["timestamp"].astype(str).str.startswith(ts[:16])]
    if m.empty:
        raise KeyError(ts)
    return m.iloc[0]


def _bar(ts: str, df: pd.DataFrame) -> dict:
    r = _row(ts, df)
    o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
    return {
        "timestamp": str(r["timestamp"]),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "body_ratio": candle_math.body_ratio(o, h, l, c),
        "body_size": candle_math.body_size(o, c),
        "candle_range": candle_math.candle_range(h, l),
        "wick_size": candle_math.candle_range(h, l),  # CRT Candle.wick_size == candle_range (F-046)
        "move": abs(c - o),
        "bearish": c < o,
        "bullish": c > o,
    }


def _parse_retest_reason(reason: str) -> dict:
    # "Retest | depth_abs=5.92000 ceiling=7.66800"
    out = {}
    if not reason:
        return out
    for part in reason.replace("Retest |", "").split():
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                out[k.strip()] = float(v)
            except ValueError:
                out[k.strip()] = v
    return out


def _chain_for_retest(events: list[dict], retest_ts: str) -> list[dict]:
    """Walk backward from retest to find SWEEP→… path for this episode."""
    # Collect transitions with timestamps before or equal retest, take last complete chain
    transitions = [
        e
        for e in events
        if e.get("event") == "STATE_TRANSITION" and e.get("timestamp") is not None
    ]
    # find retest event index
    ridx = None
    for i, e in enumerate(transitions):
        if e.get("state_to") == "RETEST" and e.get("timestamp") == retest_ts:
            ridx = i
            break
    if ridx is None:
        return []
    # walk back until RANGE or start of a new RANGE->SWEEP after a RESOLUTION
    chain = [transitions[ridx]]
    j = ridx - 1
    while j >= 0:
        e = transitions[j]
        chain.append(e)
        if e.get("state_from") == "RANGE" and e.get("state_to") in (
            "SWEEP",
            "SHADOW_PENDING",
        ):
            break
        if e.get("state_to") == "RANGE":
            # don't include terminal reset before this episode
            chain.pop()
            break
        j -= 1
    chain.reverse()
    return chain


def _code_predicates(cfg) -> dict:
    return {
        "topology": {
            "source": "src/config_layer/state_identity.py:69-79 VALID_TRANSITIONS",
            "edges": {
                "RANGE": ["SWEEP", "SHADOW_PENDING"],
                "SHADOW_PENDING": ["SWEEP", "RANGE"],
                "SWEEP": ["DISPLACEMENT", "EXPANSION", "RANGE"],
                "DISPLACEMENT": ["EXPANSION", "RANGE"],
                "EXPANSION": ["RETEST", "EXPIRED", "RANGE"],
                "RETEST": ["EXECUTION", "RANGE"],
                "EXECUTION": ["RESOLUTION"],
                "RESOLUTION": ["RANGE"],
            },
            "note": (
                "SWEEP→EXPANSION is legal in the graph but the golden path in "
                "process_candle is SWEEP→DISPLACEMENT→EXPANSION. Direct SWEEP→EXPANSION "
                "appears via shadow resume (try_shadow_pending_to_expansion) which skips "
                "the displacement strength checks."
            ),
        },
        "RANGE_to_SWEEP": {
            "function": "RangeDetector.detect_sweep",
            "file": "src/config_layer/crt_engine_v2.py:879-933",
            "predicates": [
                {
                    "id": "P_SWEEP_HIGH",
                    "operator": "high > h_ref AND close < h_ref",
                    "meaning": "wick above range high, close back inside → SHORT sweep",
                },
                {
                    "id": "P_SWEEP_LOW",
                    "operator": "low < l_ref AND close > l_ref",
                    "meaning": "wick below range low, close back inside → LONG sweep",
                },
            ],
            "NOT_required": [
                "feature_pipeline.liquidity_sweep flag (engine uses OHLCV vs h_ref/l_ref)",
                "body_ratio / ATR (those gate DISPLACEMENT, not SWEEP)",
            ],
            "config_keys": [],
        },
        "SWEEP_to_DISPLACEMENT": {
            "function": "StateMachine.try_sweep_to_displacement",
            "file": "src/config_layer/crt_engine_v2.py:1087-1261",
            "predicates": [
                {
                    "id": "P_DISP_MOVE",
                    "operator": "abs(close-open) >= atr_min_displacement * atr_abs",
                    "config_key": "atr_min_displacement",
                    "config_value": cfg.atr_min_displacement,
                },
                {
                    "id": "P_DISP_AGE",
                    "operator": "(idx - sweep_idx) <= max_sweep_age_candles",
                    "config_key": "max_sweep_age_candles",
                    "config_value": cfg.max_sweep_age_candles,
                },
                {
                    "id": "P_DISP_BODY",
                    "operator": "body_ratio >= body_ratio_min",
                    "config_key": "body_ratio_min",
                    "config_value": cfg.body_ratio_min,
                    "formula": "body_size/candle_range (FM-010 via Candle.body_ratio)",
                },
                {
                    "id": "P_DISP_WICK",
                    "operator": "wick_size >= atr_multiplier_min * atr_abs",
                    "config_key": "atr_multiplier_min",
                    "config_value": cfg.atr_multiplier_min,
                    "note": "wick_size property == candle_range (FM-002), not total_wick",
                },
            ],
        },
        "DISPLACEMENT_to_EXPANSION": {
            "function": "StateMachine.try_displacement_to_expansion",
            "file": "src/config_layer/crt_engine_v2.py:1263-1431",
            "predicates": [
                {
                    "id": "P_EXP_DIR",
                    "operator": "LONG: close>open; SHORT: close<open",
                },
                {
                    "id": "P_EXP_EXTEND",
                    "operator": "LONG: close>disp_close; SHORT: close<disp_close",
                },
                {
                    "id": "P_EXP_ATR_DIST",
                    "operator": "abs(close-disp_close) >= expansion_atr_min_distance * atr_abs",
                    "config_key": "expansion_atr_min_distance",
                    "config_value": cfg.expansion_atr_min_distance,
                },
            ],
        },
        "EXPANSION_to_RETEST": {
            "function": "StateMachine.try_expansion_to_retest",
            "file": "src/config_layer/crt_engine_v2.py:1433-1653",
            "predicates": [
                {
                    "id": "P_RET_MIN_DEPTH",
                    "operator": "depth_abs >= retest_min_depth_atr_fraction * atr",
                    "config_key": "retest_min_depth_atr_fraction",
                    "config_value": cfg.retest_min_depth_atr_fraction,
                    "depth_def": "LONG: close-l_ref; SHORT: h_ref-close",
                },
                {
                    "id": "P_RET_CEILING",
                    "operator": "depth_abs <= adaptive_ceiling",
                    "adaptive_ceiling": "max(retest_depth_max*range_size, retest_atr_depth_fraction*atr)",
                    "config_keys": {
                        "retest_depth_max": cfg.retest_depth_max,
                        "retest_atr_depth_fraction": cfg.retest_atr_depth_fraction,
                    },
                },
                {
                    "id": "P_RET_DISP_STRENGTH",
                    "operator": "FM-028(disp.wick_size, atr) <= max_displacement_strength",
                    "config_key": "max_displacement_strength",
                    "config_value": cfg.max_displacement_strength,
                },
            ],
            "note": "NOT the pipeline feature retest_depth (FM-021). Depth is local vs active_range boundary.",
        },
        "RETEST_to_EXECUTION": {
            "function": "process_candle RETEST branch + try_retest_to_execution",
            "file": "src/config_layer/crt_engine_v2.py:2935-3079 / 1655+",
            "predicates_after_retest": [
                "soft confirmation window (evaluating_soft_conf)",
                "session filter (outside session → FILTER_REJECTED)",
                "score gate (DECISION_DISTANCE / score_threshold / soft conf)",
                "zone / shadow advisory checks",
                "then try_retest_to_execution (legal graph edge only)",
            ],
            "score_threshold_config": cfg.score_threshold,
            "note": (
                "On the 4m run DECISION_DISTANCE used score_threshold=0.3 in telemetry "
                f"while CRTConfig.score_threshold={cfg.score_threshold} — soft-conf path "
                "may use tier threshold; do not conflate with structural state predicates."
            ),
        },
        "feature_pipeline_role": {
            "note": (
                "Feature pipeline metrics (liquidity_sweep, disp_strength, retest_depth, "
                "canonical atr) are NOT the state-machine predicates for SWEEP/DISPLACEMENT/"
                "EXPANSION/RETEST. CRT uses OHLCV + local atr_abs + active_range memory. "
                "Pipeline features feed scoring/BitNet/vector, not transition guards."
            )
        },
    }


def _episode_tables(chain: list[dict], df: pd.DataFrame, cfg, fate: str) -> list[dict]:
    rows = []
    atr_from_meta = None
    for e in chain:
        meta = e.get("metadata") or {}
        if meta.get("atr") is not None:
            atr_from_meta = meta.get("atr")
        ts = e.get("timestamp")
        fr, to = e.get("state_from"), e.get("state_to")
        reason = e.get("reason") or ""
        bar = None
        try:
            bar = _bar(ts, df)
        except Exception:
            bar = None

        if fr == "RANGE" and to == "SWEEP":
            # reconstruct sweep geometry needs h_ref — not always in event; use reason price
            rows.append(
                {
                    "state": "SWEEP",
                    "predicate": "P_SWEEP_HIGH or P_SWEEP_LOW (close back inside after wick beyond h_ref/l_ref)",
                    "values": {
                        "timestamp": ts,
                        "ohlc": bar,
                        "reason": reason,
                        "atr_abs_in_metadata": atr_from_meta,
                    },
                    "threshold": "h_ref / l_ref from active HTF range (state memory)",
                    "result": "PASS",
                    "code": "crt_engine_v2.py:887-893",
                }
            )
        elif fr == "SWEEP" and to == "DISPLACEMENT" and bar:
            move = bar["move"]
            thr_move = cfg.atr_min_displacement * (atr_from_meta or 0)
            thr_wick = cfg.atr_multiplier_min * (atr_from_meta or 0)
            rows.append(
                {
                    "state": "DISPLACEMENT",
                    "predicate": "P_DISP_MOVE / P_DISP_BODY / P_DISP_WICK (all must pass)",
                    "values": {
                        "timestamp": ts,
                        "move_abs_close_open": move,
                        "body_ratio": bar["body_ratio"],
                        "wick_size_as_range": bar["wick_size"],
                        "atr_abs": atr_from_meta,
                        "reason": reason,
                    },
                    "threshold": {
                        "move_min": thr_move,
                        "body_ratio_min": cfg.body_ratio_min,
                        "wick_min": thr_wick,
                        "atr_min_displacement": cfg.atr_min_displacement,
                        "atr_multiplier_min": cfg.atr_multiplier_min,
                    },
                    "checks": {
                        "move_pass": None if atr_from_meta is None else move >= thr_move,
                        "body_pass": bar["body_ratio"] >= cfg.body_ratio_min,
                        "wick_pass": None
                        if atr_from_meta is None
                        else bar["wick_size"] >= thr_wick,
                    },
                    "result": "PASS (transition fired)",
                    "code": "crt_engine_v2.py:1087-1261",
                }
            )
        elif fr == "DISPLACEMENT" and to == "EXPANSION" and bar:
            rows.append(
                {
                    "state": "EXPANSION",
                    "predicate": "P_EXP_DIR + P_EXP_EXTEND + P_EXP_ATR_DIST",
                    "values": {
                        "timestamp": ts,
                        "close": bar["close"],
                        "open": bar["open"],
                        "bullish": bar["bullish"],
                        "bearish": bar["bearish"],
                        "reason": reason,
                        "atr_abs": atr_from_meta,
                    },
                    "threshold": {
                        "expansion_atr_min_distance": cfg.expansion_atr_min_distance,
                        "min_distance_abs": (
                            cfg.expansion_atr_min_distance * atr_from_meta
                            if atr_from_meta
                            else None
                        ),
                    },
                    "result": "PASS (transition fired)",
                    "code": "crt_engine_v2.py:1263-1431",
                    "note": "disp_close is state memory; distance checked vs that, not range mid",
                }
            )
        elif fr == "SWEEP" and to == "EXPANSION":
            rows.append(
                {
                    "state": "EXPANSION (direct / shadow)",
                    "predicate": "shadow path skips displacement strength (try_shadow_pending_to_expansion)",
                    "values": {"timestamp": ts, "reason": reason},
                    "threshold": "N/A — strength check skipped on shadow resume",
                    "result": "PASS",
                    "code": "crt_engine_v2.py:1061-1085",
                }
            )
        elif fr == "EXPANSION" and to == "RETEST":
            parsed = _parse_retest_reason(reason)
            rows.append(
                {
                    "state": "RETEST",
                    "predicate": "P_RET_MIN_DEPTH + P_RET_CEILING + P_RET_DISP_STRENGTH",
                    "values": {
                        "timestamp": ts,
                        "depth_abs_from_reason": parsed.get("depth_abs"),
                        "ceiling_from_reason": parsed.get("ceiling"),
                        "ohlc": bar,
                        "reason": reason,
                        "atr_abs": atr_from_meta,
                    },
                    "threshold": {
                        "retest_min_depth_atr_fraction": cfg.retest_min_depth_atr_fraction,
                        "retest_depth_max": cfg.retest_depth_max,
                        "retest_atr_depth_fraction": cfg.retest_atr_depth_fraction,
                        "max_displacement_strength": cfg.max_displacement_strength,
                        "min_depth_abs": (
                            cfg.retest_min_depth_atr_fraction * atr_from_meta
                            if atr_from_meta
                            else None
                        ),
                    },
                    "checks": {
                        "depth_le_ceiling": (
                            parsed.get("depth_abs") is not None
                            and parsed.get("ceiling") is not None
                            and parsed["depth_abs"] <= parsed["ceiling"]
                        ),
                        "depth_ge_min": (
                            parsed.get("depth_abs") is not None
                            and atr_from_meta is not None
                            and parsed["depth_abs"]
                            >= cfg.retest_min_depth_atr_fraction * atr_from_meta
                        ),
                    },
                    "result": "PASS (transition fired)",
                    "code": "crt_engine_v2.py:1433-1653",
                }
            )
        elif fr == "RETEST" and to == "EXECUTION":
            rows.append(
                {
                    "state": "EXECUTION",
                    "predicate": "post-retest gates (session + score + zone) then try_retest_to_execution",
                    "values": {"timestamp": ts, "reason": reason},
                    "threshold": {
                        "score_threshold_CRTConfig": cfg.score_threshold,
                        "session": "must be inside allowed session set",
                    },
                    "result": "PASS",
                    "code": "crt_engine_v2.py RETEST branch",
                }
            )
        else:
            rows.append(
                {
                    "state": f"{fr}->{to}",
                    "predicate": "(see chain)",
                    "values": {"timestamp": ts, "reason": reason, "ohlc": bar},
                    "threshold": None,
                    "result": "observed",
                }
            )
    # fate row
    rows.append(
        {
            "state": "POST_RETEST_FATE",
            "predicate": "session / score / risk after RETEST",
            "values": {"episode_fate": fate},
            "threshold": None,
            "result": fate,
        }
    )
    return rows


def main() -> int:
    cfg = load_prod_config_from_registry("v2_multi_2026_04", "XAUUSD")
    df = pd.read_csv(CSV, parse_dates=["timestamp"])
    events = [
        json.loads(l)
        for l in (RUN / "XAUUSD_events.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    tel = [
        json.loads(l)
        for l in (RUN / "XAUUSD_crt_telemetry.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    # funnel stage counts from events
    from_to = Counter()
    for e in events:
        if e.get("event") == "STATE_TRANSITION":
            from_to[f"{e.get('state_from')} -> {e.get('state_to')}"] += 1

    # Episodes
    pass_ts = "2026-02-04T09:30:00"
    fail_ts = "2026-02-23T17:45:00"
    pass_chain = _chain_for_retest(events, pass_ts)
    fail_chain = _chain_for_retest(events, fail_ts)

    # DECISION_DISTANCE for both
    dds = [e for e in tel if e.get("kind") == "DECISION_DISTANCE"]

    # EXPANSION_RETRACE for context
    erc = [e for e in tel if e.get("kind") == "EXPANSION_RETRACE_CHECK"]

    report = {
        "scope": "READ_ONLY implementation audit — conceptual vs code vs two real episodes",
        "active_version": get_active_version(),
        "window_csv": str(CSV.relative_to(ROOT)).replace("\\", "/"),
        "run_dir": str(RUN.relative_to(ROOT)).replace("\\", "/"),
        "gate": "BACKTEST_ENGINE_GATE=0",
        "funnel_observed_4m": dict(from_to.most_common()),
        "live_crt_config_thresholds": {
            "body_ratio_min": cfg.body_ratio_min,
            "atr_multiplier_min": cfg.atr_multiplier_min,
            "atr_min_displacement": cfg.atr_min_displacement,
            "max_sweep_age_candles": cfg.max_sweep_age_candles,
            "expansion_atr_min_distance": cfg.expansion_atr_min_distance,
            "retest_depth_max": cfg.retest_depth_max,
            "retest_atr_depth_fraction": cfg.retest_atr_depth_fraction,
            "retest_min_depth_atr_fraction": cfg.retest_min_depth_atr_fraction,
            "max_displacement_strength": cfg.max_displacement_strength,
            "score_threshold": cfg.score_threshold,
            "atr_period": cfg.atr_period,
        },
        "code_predicates": _code_predicates(cfg),
        "episodes": {
            "PASS_to_EXECUTION": {
                "retest_ts": pass_ts,
                "fate": "RETEST -> EXECUTION -> TRADE_OPENED SHORT -> TRADE_STOPPED",
                "chain_transitions": [
                    {
                        "ts": e.get("timestamp"),
                        "from": e.get("state_from"),
                        "to": e.get("state_to"),
                        "reason": e.get("reason"),
                        "metadata": e.get("metadata"),
                    }
                    for e in pass_chain
                ],
                "predicate_table": _episode_tables(pass_chain, df, cfg, "TRADE_THEN_STOPPED"),
            },
            "FAIL_session_filter": {
                "retest_ts": fail_ts,
                "fate": "RETEST -> FILTER_REJECTED off_session:OFF_SESSION",
                "chain_transitions": [
                    {
                        "ts": e.get("timestamp"),
                        "from": e.get("state_from"),
                        "to": e.get("state_to"),
                        "reason": e.get("reason"),
                        "metadata": e.get("metadata"),
                    }
                    for e in fail_chain
                ],
                "predicate_table": _episode_tables(
                    fail_chain, df, cfg, "FILTER_REJECTED_OFF_SESSION"
                ),
            },
        },
        "decision_distance_all": dds,
        "selectivity_interpretation": {
            "SWEEP_527": (
                "Cheap geometric test vs HTF range refs — no body/ATR gate. High count expected."
            ),
            "DISPLACEMENT_48": (
                "SWEEP→DISPLACEMENT requires move>=1.2*ATR AND body_ratio>=0.65 AND "
                "range>=1.0*ATR AND sweep age<=20. Most sweeps fail body/move/wick size."
            ),
            "EXPANSION_13": (
                "DISPLACEMENT→EXPANSION requires directional bar, close beyond disp_close, "
                "and distance>=0.3*ATR. Also 10 SWEEP→EXPANSION via shadow path in this run "
                f"(count SWEEP->EXPANSION={from_to.get('SWEEP -> EXPANSION', 0)})."
            ),
            "RETEST_3": (
                "EXPANSION→RETEST requires depth between min(0.1*ATR) and adaptive ceiling "
                "max(0.15*range_size, 0.3*ATR), and FM-028 <= 2.0. Thin completion of "
                "expansion→retest is the mid-funnel choke; not the scorer."
            ),
            "POST_RETEST": (
                "All 3 DECISION_DISTANCE rows APPROVED. 2/3 die on session filter — "
                "admission, not structure, kills most retests on this window."
            ),
        },
        "conceptual_vs_implementation": {
            "conceptual_chain_user": (
                "RANGE→SWEEP→DISPLACEMENT→SHADOW_PENDING→EXPANSION→RETEST→EXECUTION"
            ),
            "implementation_correction": (
                "SHADOW_PENDING is a BRANCH from RANGE (parallel to SWEEP), not a step "
                "between DISPLACEMENT and EXPANSION. Golden path is "
                "RANGE→SWEEP→DISPLACEMENT→EXPANSION→RETEST→EXECUTION→RESOLUTION→RANGE. "
                "SHADOW_PENDING→SWEEP→EXPANSION is the shadow resume branch."
            ),
        },
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")

    # Markdown
    lines = []
    lines.append("# CRT State-Transition Audit — XAUUSD 4-month window")
    lines.append("")
    lines.append("**Read-only.** No behavioral changes.")
    lines.append("")
    lines.append(f"- Active config: `{get_active_version()}`")
    lines.append(f"- CSV: `{CSV.name}` (7804 rows)")
    lines.append(f"- Run: `{RUN.name}` / gate OFF")
    lines.append("")
    lines.append("## 1. Conceptual vs implementation topology")
    lines.append("")
    lines.append("| Claim | Verdict |")
    lines.append("|---|---|")
    lines.append(
        "| SHADOW_PENDING sits between DISPLACEMENT and EXPANSION | "
        "**Incorrect** — it is a RANGE branch, not mid-golden-path |"
    )
    lines.append(
        "| Golden path RANGE→SWEEP→DISPLACEMENT→EXPANSION→RETEST→EXECUTION | "
        "**Correct** (VALID_TRANSITIONS + process_candle) |"
    )
    lines.append(
        "| Feature-pipeline `liquidity_sweep` / `retest_depth` drive transitions | "
        "**Incorrect** — CRT uses OHLCV + `atr_abs` + range memory |"
    )
    lines.append("")
    lines.append("## 2. Live thresholds (CRTConfig from production)")
    lines.append("")
    lines.append("| Key | Value | Role |")
    lines.append("|---|---:|---|")
    thr = report["live_crt_config_thresholds"]
    roles = {
        "atr_min_displacement": "DISPLACEMENT body move floor (× atr_abs)",
        "body_ratio_min": "DISPLACEMENT body quality",
        "atr_multiplier_min": "DISPLACEMENT min range/ATR",
        "max_sweep_age_candles": "DISPLACEMENT sweep TTL",
        "expansion_atr_min_distance": "EXPANSION min extend beyond disp_close",
        "retest_min_depth_atr_fraction": "RETEST min depth floor",
        "retest_depth_max": "RETEST static ceiling fraction of range size",
        "retest_atr_depth_fraction": "RETEST ATR ceiling fraction",
        "max_displacement_strength": "RETEST max FM-028",
        "score_threshold": "score gate (post-RETEST, not structure)",
        "atr_period": "local atr_abs window",
    }
    for k, v in thr.items():
        lines.append(f"| `{k}` | {v} | {roles.get(k, '')} |")
    lines.append("")
    lines.append("## 3. Why the funnel thins (implementation answer)")
    lines.append("")
    lines.append("```text")
    lines.append("RANGE  (geometry vs HTF h_ref/l_ref)")
    lines.append("  └─ SWEEP          cheap: wick beyond ref + close back inside")
    lines.append("       └─ DISPLACEMENT  expensive: move≥1.2·ATR ∧ body≥0.65 ∧ range≥1.0·ATR ∧ age≤20")
    lines.append("            └─ EXPANSION   directional bar + extend beyond disp_close ≥0.3·ATR")
    lines.append("                 └─ RETEST  depth in [0.1·ATR, adaptive_ceiling] ∧ FM-028≤2.0")
    lines.append("                      └─ EXECUTION  session + score + risk  (not pure geometry)")
    lines.append("```")
    lines.append("")
    for k, v in report["selectivity_interpretation"].items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")
    lines.append("## 4. Episode A — PASS (to trade)")
    lines.append("")
    lines.append(f"Retest `{pass_ts}` → EXECUTION → SHORT → STOPPED.")
    lines.append("")
    lines.append("| State | Predicate | Values (observed) | Threshold | Result |")
    lines.append("|---|---|---|---|---|")
    for row in report["episodes"]["PASS_to_EXECUTION"]["predicate_table"]:
        vals = json.dumps(row.get("values"), default=str)[:120]
        thr_s = json.dumps(row.get("threshold"), default=str)[:80]
        lines.append(
            f"| {row.get('state')} | {str(row.get('predicate'))[:60]} | "
            f"`{vals}` | `{thr_s}` | {row.get('result')} |"
        )
    lines.append("")
    lines.append("## 5. Episode B — FAIL (session)")
    lines.append("")
    lines.append(f"Retest `{fail_ts}` → FILTER_REJECTED `off_session:OFF_SESSION`.")
    lines.append("")
    lines.append(
        "Structure completed the same geometric ladder to RETEST; "
        "**session admission** rejected after soft-conf start — not a DISPLACEMENT/EXPANSION fail."
    )
    lines.append("")
    lines.append("| State | Predicate | Values (observed) | Threshold | Result |")
    lines.append("|---|---|---|---|---|")
    for row in report["episodes"]["FAIL_session_filter"]["predicate_table"]:
        vals = json.dumps(row.get("values"), default=str)[:120]
        thr_s = json.dumps(row.get("threshold"), default=str)[:80]
        lines.append(
            f"| {row.get('state')} | {str(row.get('predicate'))[:60]} | "
            f"`{vals}` | `{thr_s}` | {row.get('result')} |"
        )
    lines.append("")
    lines.append("## 6. DECISION_DISTANCE (all 3 retests on this window)")
    lines.append("")
    lines.append("| candidate | score | thr (telemetry) | accepted | reason |")
    lines.append("|---|---:|---:|---|---|")
    for e in dds:
        lines.append(
            f"| {e.get('candidate_id')} | {e.get('score_actual'):.4f} | "
            f"{e.get('score_threshold')} | {e.get('accepted')} | {e.get('rejection_reason')} |"
        )
    lines.append("")
    lines.append(
        f"Note: CRTConfig.score_threshold={cfg.score_threshold} but telemetry thr=0.3 "
        "on these rows — soft-conf / tier path. Structural transitions do not use this number."
    )
    lines.append("")
    lines.append("## 7. Sources")
    lines.append("")
    lines.append("- `src/config_layer/state_identity.py` VALID_TRANSITIONS")
    lines.append("- `src/config_layer/crt_engine_v2.py` detect_sweep + try_* guards")
    lines.append("- Production CRTConfig via `load_prod_config_from_registry(v2_multi_2026_04, XAUUSD)`")
    lines.append(f"- Events: `{RUN / 'XAUUSD_events.jsonl'}`")
    lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", OUT_JSON)
    print("Wrote", OUT_MD)
    print("--- PASS chain ---")
    for e in pass_chain:
        print(f"  {e.get('timestamp')} {e.get('state_from')}->{e.get('state_to')} | {e.get('reason')}")
    print("--- FAIL chain ---")
    for e in fail_chain:
        print(f"  {e.get('timestamp')} {e.get('state_from')}->{e.get('state_to')} | {e.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
