#!/usr/bin/env python3
"""
crt_episode_number_trace.py
============================
Per-episode, named-value walkthrough of a CRT setup:

    OHLC  ->  features (name + value)  ->  CRT state (name + value)  ->  SL/TP arithmetic

Built to make a trade rejection readable end to end. For each RETEST episode it walks every bar
from the SWEEP that opened it through the terminal decision, showing the CRT-consumed features
with their values on every bar, the full 39-feature vector with ontology formulas on the decision
bars, the state machine's own variables (active_range / sweep / displacement / retest / risk
score) with their values, and finally the execution geometry as substituted equations.

TWO ARMS PER EPISODE. Under the production config (A0) `executor.build_trade` is NEVER CALLED --
the session gate rejects first, so the SL geometry is unreachable and invisible. Rendering the
same episode under A3 (session opened) exercises `build_trade` and exposes the geometry. Arms
come from session_filter_funnel_probe; nothing is written to config.

ATR PROVENANCE. The `atr` in the SL formula is `state.atr_abs` on the SOFT-CONFIRMATION bar, not
on the RETEST bar. They differ (07-22: 9.562143 vs 10.473571), and using the RETEST bar's value
reproduces neither the engine's SL nor its rejection. Both are rendered, on separate lines.

ANTI-DRIFT. This script RECOMPUTES the SL for display, so it could silently diverge from the
engine. A logging handler on the `CRT.Execution` logger captures the engine's own
`entry=... sl=... sweep=...` rejection message and the recomputed values are ASSERTED against it
to 5dp. A plausible wrong number is worse than a crash.

Read-only: no src/ edit, no config write.

Usage:
    venv/Scripts/python.exe scripts/analysis/crt_episode_number_trace.py
    venv/Scripts/python.exe scripts/analysis/crt_episode_number_trace.py --arms A0,A3 --context-bars 5
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
os.chdir(ROOT)

os.environ.setdefault("BACKTEST_ENGINE_GATE", "0")

import pandas as pd

from config_layer.crt_engine_v2 import CRTEngine, Candle, Direction
from config_layer.production_config import (
    get_active_version,
    get_prod_section,
    load_prod_config_from_registry,
)
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES, SCHEMA_VERSION
from features.registry import load_ontology
from runtime.backtest_v2 import HTFBuilder

import feature_trace_report as FTR
from session_filter_funnel_probe import build_arms
from xauusd_excel_feature_state_trace import _sha256, load_from_csv, load_from_xlsx

logger = logging.getLogger("CRT_EPISODE_TRACE")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEFAULT_XLSX = ROOT / "data" / "XAUUSD_M15_20260807_203705.xlsx"
DEFAULT_FEATURE_CSV = ROOT / "data" / "XAUUSD_M15.csv"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "crt_episode_trace"
DEFAULT_INSTRUMENT = "XAUUSD"

# Features the CRT state machine actually consumes, shown on EVERY bar. Each is either a
# threshold operand in crt_engine_v2 or a key the engine caches into state.cached_features
# (see _derive_trade_intent, crt_engine_v2.py:2161-2185, and the body_ratio_min /
# atr_min_displacement / retest_depth gates).
CRT_CONSUMED = [
    "close",                    # entry price source (retest_candle.close)
    "atr",                      # FM-041 close-relative; engine keeps its own atr_abs alongside
    "body_ratio",               # config.body_ratio_min gate
    "displacement_retrace",     # FM-027, _derive_trade_intent `rd`
    "displacement_atr_ratio",   # FM-028, displacement strength
    "momentum_score",           # _derive_trade_intent `mom`
    "ema_spread",               # soft-confirmation trend spread
    "trend_bias",
    "candles_since_retest",     # _derive_trade_intent `csr`
    "volume_spike",
    "rsi_14",
    "session",                  # FM-052 (feature label; the GATE uses its own window match)
]

EPISODE_START_ACTIONS = {"SWEEP_DETECTED", "SHADOW_SWEEP_DETECTED"}
TERMINAL_ACTIONS = {
    "TRADE_OPENED", "FILTER_REJECTED", "CONFIRMATION_FAILED", "SHADOW_ADVISORY_BLOCK",
}
DECISION_ACTIONS = {
    "SWEEP_DETECTED", "SHADOW_SWEEP_DETECTED", "DISPLACEMENT_CONFIRMED",
    "EXPANSION_CONFIRMED", "SHADOW_EXPANSION_CONFIRMED", "RETEST_CONFIRMED",
} | TERMINAL_ACTIONS

_INVERTED_RE = re.compile(
    r"inverted SL on (?P<dir>LONG|SHORT).*?entry=(?P<entry>[-\d.]+)\s+sl=(?P<sl>[-\d.]+)\s+sweep=(?P<sweep>[-\d.]+)"
)


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 1 — PROVENANCE
#
# Every displayed number carries a source class. A number without provenance is an
# INSTRUMENTATION ERROR, not an incomplete display, so _operand() raises rather than
# rendering a blank cell (same failure mode as an assert that cannot fail).
#
# NEVER collapse DERIVED and ENGINE even when they agree: sl_engine=4148.66243 and
# sl_trace=4148.6624286 are epistemically different objects that happen to share a value.
# Rendering one in place of the other destroys the evidence the parity check creates.
# ─────────────────────────────────────────────────────────────────────────────
PROVENANCE_CLASSES = {
    "OHLC":    "raw candle field",
    "FEATURE": "FeaturePipeline output",
    "STATE":   "EngineState field",
    "CONFIG":  "CRTConfig field",
    "DERIVED": "arithmetic performed by this script",
    "ENGINE":  "value the engine itself emitted",
}

# Epistemic strength, strongest first. Guards against the specific reporting error of
# calling something OBSERVED when it was only inferred from control flow.
EPISTEMIC_RANK = {"OBSERVED": 0, "DERIVED": 1, "INFERRED_BY_ORDER": 2, "N/A": 3}


def _operand(name: str, value: Any, cls: str, source: str, note: str = "") -> dict[str, Any]:
    """The single constructor for a displayed number. Raises on missing/unknown provenance."""
    if cls not in PROVENANCE_CLASSES:
        raise ValueError(
            f"operand {name!r}: provenance class {cls!r} is missing or unknown. "
            f"Known: {sorted(PROVENANCE_CLASSES)}. A number without provenance is an "
            f"instrumentation error."
        )
    if not source:
        raise ValueError(f"operand {name!r}: empty source. Name the field/expression it came from.")
    return {"name": name, "value": value, "class": cls, "source": source, "note": note}


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE-LOG CAPTURE (the anti-drift reference)
# ─────────────────────────────────────────────────────────────────────────────
class ExecutionLogCapture(logging.Handler):
    """Captures the engine's OWN inverted-SL numbers so our recompute can be asserted."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.inverted: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        m = _INVERTED_RE.search(record.getMessage())
        if m:
            self.inverted.append(
                {
                    "direction": m.group("dir"),
                    "entry": float(m.group("entry")),
                    "sl": float(m.group("sl")),
                    "sweep": float(m.group("sweep")),
                }
            )


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE-TRACE CONTEXT  (rebuilds what feature_trace_report.main() assembles)
# ─────────────────────────────────────────────────────────────────────────────
def build_ftr_context(csv_path: Path, n_bars: int) -> dict[str, Any]:
    """Reproduce feature_trace_report.main()'s setup so its renderers can be called directly.

    Mirrors feature_trace_report.py:996-1040 — same stages, same snapshots, finalize() skipped.
    """
    raw = pd.read_csv(csv_path)
    fp_cfg = get_prod_section("feature_pipeline")
    pipe = FeaturePipeline(raw, cfg=fp_cfg)
    raw_cols = set(pipe.df.columns)

    snap_vol_seed = None
    snap_pre_norm_trend = None
    col_sets, window_snaps = [], []
    for stage in FTR.PIPELINE_STAGES:
        getattr(pipe, stage)()
        if stage == "compute_volume_features":
            snap_vol_seed = pipe.df["volume_spike"].iloc[:n_bars].copy()
        elif stage == "compute_trend_features":
            snap_pre_norm_trend = pipe.df["trend_strength"].iloc[:n_bars].copy()
        col_sets.append(set(pipe.df.columns))
        window_snaps.append(pipe.df.iloc[:n_bars].copy())

    df = pipe.df
    stage_provenance = FTR._build_stage_provenance(raw_cols, col_sets, window_snaps)
    del window_snaps

    ont = load_ontology()
    numeric_cols = [n for n in CANONICAL_FEATURES if n not in FTR.RAW_OHLCV_NOTES]
    return {
        "df": df,
        "ont": ont,
        "ontology_index": FTR._build_ontology_index(ont),
        "lineage": FTR._build_lineage_index(ont),
        "fp_cfg": fp_cfg,
        "first_valid": {n: df[n].first_valid_index() for n in CANONICAL_FEATURES},
        "col_first_valid": {c: df[c].first_valid_index() for c in df.columns},
        "rank_df": df[numeric_cols].rank(pct=True),
        "snap_vol_seed": snap_vol_seed,
        "snap_pre_norm_trend": snap_pre_norm_trend,
        "stage_provenance": stage_provenance,
        "csv_path": csv_path,
        "csv_sha256": _sha256(csv_path),
        "prod_version": get_active_version(),
    }


def full_feature_record(ctx: dict[str, Any], bar_index0: int) -> dict[str, Any]:
    """All 39 features with ontology formula/source/value/interpretation for one bar."""
    return FTR._build_bar_record(
        bar_index0 + 1, ctx["df"].iloc[bar_index0], ctx["ontology_index"],
        ctx["rank_df"].iloc[bar_index0], ctx["fp_cfg"], ctx["ont"], ctx["first_valid"],
        ctx["snap_vol_seed"], ctx["snap_pre_norm_trend"], ctx["csv_path"], ctx["csv_sha256"],
        ctx["prod_version"], ctx["lineage"], ctx["stage_provenance"], ctx["col_first_valid"],
    )


def consumed_features(ctx: dict[str, Any], bar_index0: int) -> list[dict[str, Any]]:
    """The CRT-consumed subset: name, value, FM id, formula."""
    row = ctx["df"].iloc[bar_index0]
    out = []
    for name in CRT_CONSUMED:
        if name not in ctx["df"].columns:
            out.append({"name": name, "value": None, "fm_id": None, "formula": "(not emitted)"})
            continue
        v = row[name]
        cit = FTR._citation_for(name, ctx["ontology_index"]) if name in CANONICAL_FEATURES else None
        spec = (cit or {}).get("spec") or {}
        out.append(
            {
                "name": name,
                "value": None if v != v else float(v),
                "fm_id": (cit or {}).get("fm_id"),
                "formula": spec.get("formula") or spec.get("description") or "",
            }
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# STATE SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────
def state_snapshot(engine: CRTEngine) -> dict[str, Any]:
    st = engine.state
    rng, sw = st.active_range, st.sweep_event
    disp, rt, rs = st.displacement_candle, st.retest_candle, st.risk_score
    snap: dict[str, Any] = {
        "current_state": st.current_state.name,
        "direction": st.direction.name if st.direction is not None else None,
        "atr_abs": float(st.atr_abs),
        "ema_fast_val": float(st.ema_fast_val),
        "ema_slow_val": float(st.ema_slow_val),
        "soft_conf_candles": getattr(st, "soft_conf_candles", None),
        "evaluating_soft_conf": getattr(st, "evaluating_soft_conf", None),
        "came_from_shadow": getattr(st, "_came_from_shadow", None),
    }
    snap["active_range"] = (
        {"h_ref": rng.h_ref, "l_ref": rng.l_ref, "equilibrium": rng.equilibrium,
         "size": rng.size, "htf_candle_id": rng.htf_candle_id, "session": rng.session}
        if rng else None
    )
    snap["sweep_event"] = (
        {"price": sw.price, "direction": sw.direction.name if sw.direction else None,
         "sweep_type": sw.sweep_type, "double_confirmed": sw.double_confirmed,
         "candle_index": sw.candle_index}
        if sw else None
    )
    snap["displacement_candle"] = (
        {"index": disp.index, "open": disp.open, "high": disp.high,
         "low": disp.low, "close": disp.close} if disp else None
    )
    snap["retest_candle"] = (
        {"index": rt.index, "open": rt.open, "high": rt.high,
         "low": rt.low, "close": rt.close} if rt else None
    )
    snap["risk_score"] = (
        {"sweep_score": rs.sweep_score, "breakout_score": rs.breakout_score,
         "retest_score": rs.retest_score, "time_score": rs.time_score,
         "decay_factor": rs.decay_factor, "score_override": rs.score_override,
         "weights": list(rs.weights), "final": float(rs.final)}
        if rs else None
    )
    snap["cached_features"] = dict(st.cached_features) if st.cached_features else None
    return snap


# ─────────────────────────────────────────────────────────────────────────────
# REPLAY with build_trade operand capture
# ─────────────────────────────────────────────────────────────────────────────
def replay(candles: list[Candle], arm, instrument: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = load_prod_config_from_registry(get_active_version(), instrument)
    over: dict[str, Any] = {}
    if arm.allowed_sessions is not None:
        over["allowed_sessions"] = arm.allowed_sessions
    if arm.session_windows is not None:
        over["session_windows"] = arm.session_windows
    cfg = dataclasses.replace(base, **over) if over else base

    engine = CRTEngine(cfg)
    engine._session_ts_basis = arm.ts_basis
    htf = HTFBuilder(4, instrument)
    initialized = False

    cap = ExecutionLogCapture()
    exec_logger = logging.getLogger("CRT.Execution")
    exec_logger.addHandler(cap)

    bar_reasons: list[tuple[str, str | None]] = []
    pre_reset: list[dict[str, Any]] = []
    orig_record = engine.ev_log.record

    def record(event, candle, **kwargs):  # type: ignore[no-untyped-def]
        name = str(getattr(event, "name", event))
        if name in ("FILTER_REJECTED", "CONFIRMATION_FAILED"):
            meta = kwargs.get("metadata") or {}
            bar_reasons.append(
                (str(kwargs.get("reason") or name),
                 meta.get("session_name") if isinstance(meta, dict) else None)
            )
            # Snapshot HERE, not after process_candle: record() fires BEFORE reset_to_range
            # (crt_engine_v2.py:3117 then :3122), which clears retest/displacement/sweep. A
            # post-call snapshot would render an empty state on the very bar being explained.
            pre_reset.append(state_snapshot(engine))
        return orig_record(event, candle, **kwargs)

    engine.ev_log.record = record  # type: ignore[method-assign]

    builds: list[dict[str, Any]] = []
    pending_build: list[dict[str, Any]] = []
    # ── GUARD 2 rung 2: score gate, OBSERVED (not inferred) ───────────────
    # approve_with_soft_conf returns (approved, reason, final_S) — crt_engine_v2.py:1953.
    # Capturing the engine's own return values makes this rung OBSERVED rather than assumed
    # from the absence of a rejection.
    score_gate: list[dict[str, Any]] = []
    orig_approve = engine.risk.approve_with_soft_conf

    def approve_traced(state, conf_candle):  # type: ignore[no-untyped-def]
        approved, reason, final_S = orig_approve(state, conf_candle)
        score_gate.append(
            {
                "approved": bool(approved),
                "reason": (getattr(reason, "value", None) or getattr(reason, "name", None)
                           if reason is not None else None),
                "final_S": float(final_S),
                "tier_1_threshold": float(cfg.tier_1_threshold),
                "tier_2_threshold": float(cfg.tier_2_threshold),
            }
        )
        return approved, reason, final_S

    engine.risk.approve_with_soft_conf = approve_traced  # type: ignore[method-assign]

    orig_build = engine.executor.build_trade

    def build_trade_traced(state, risk_engine=None):  # type: ignore[no-untyped-def]
        # Snapshot the operands BEFORE the call, then recompute the engine's own formula
        # (crt_engine_v2.py:2213-2242) so every number in the report has a named source.
        geom = _build_geometry(engine, state)
        trade = orig_build(state, risk_engine)
        geom["trade_built"] = trade is not None
        if trade is not None:
            geom["actual"] = {
                "entry": float(trade.entry_price), "sl": float(trade.sl_price),
                "tp1": float(trade.tp1_price), "tp2": float(trade.tp2_price),
                "risk_pct": float(trade.risk_pct),
            }
        builds.append(geom)
        pending_build.append(geom)
        return trade

    engine.executor.build_trade = build_trade_traced  # type: ignore[method-assign]

    bars: list[dict[str, Any]] = []
    for candle in candles:
        completed = htf.push(candle)
        if not initialized:
            if completed:
                engine.initialise_range(htf.seed_candles(), htf.current_htf_id, "UNKNOWN")
                initialized = True
            continue

        bar_reasons.clear()
        pending_build.clear()
        pre_reset.clear()
        score_gate.clear()
        before = engine.state.current_state.name
        result = engine.process_candle(candle, htf.current_htf_id)
        action = result.get("action") if isinstance(result, dict) else str(result)

        # Prefer the pre-reset snapshot when the bar rejected — see the record() comment.
        snap = pre_reset[0] if pre_reset else state_snapshot(engine)
        # Reference, NOT a copy: the anti-drift loop below attaches the ENGINE-class values and
        # parity result to these same dicts after the replay finishes. A dict() copy here would
        # silently strand the bar with a DERIVED-only geometry and no parity block.
        geom = pending_build[0] if pending_build else None
        bars.append(
            {
                "bar_index": candle.index,
                "timestamp": candle.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "ohlcv": {"open": candle.open, "high": candle.high, "low": candle.low,
                          "close": candle.close, "volume": candle.volume},
                "state_before": before,
                "action": action,
                "state": snap,
                "state_is_pre_reset": bool(pre_reset),
                "state_after_name": engine.state.current_state.name,
                "reasons": [{"reason": r, "session_name": s} for r, s in bar_reasons],
                "geometry": geom,
                "score_gate": dict(score_gate[-1]) if score_gate else None,
                "zone_gate": _zone_gate_eval(snap, bar_reasons),
            }
        )

    engine.ev_log.record = orig_record  # type: ignore[method-assign]
    engine.executor.build_trade = orig_build  # type: ignore[method-assign]
    engine.risk.approve_with_soft_conf = orig_approve  # type: ignore[method-assign]
    exec_logger.removeHandler(cap)

    # ── ANTI-DRIFT ASSERT ────────────────────────────────────────────────
    # Our recomputed entry/sl must equal the engine's own logged numbers. If a formula here
    # ever drifts from crt_engine_v2, this fails instead of rendering a plausible wrong value.
    rejected = [g for g in builds if not g["trade_built"] and g.get("inverted")]
    assert len(rejected) == len(cap.inverted), (
        f"arm {arm.name}: recomputed {len(rejected)} inverted-SL rejections but the engine "
        f"logged {len(cap.inverted)}"
    )
    for mine, theirs in zip(rejected, cap.inverted):
        assert round(mine["entry"], 5) == round(theirs["entry"], 5), (
            f"arm {arm.name}: entry drift — script {mine['entry']} vs engine {theirs['entry']}"
        )
        assert round(mine["sl"], 5) == round(theirs["sl"], 5), (
            f"arm {arm.name}: SL drift — script {mine['sl']} vs engine {theirs['sl']} "
            f"(recompute has diverged from crt_engine_v2.py:2213-2222)"
        )
        # GUARD 3: carry the ENGINE-class values alongside the DERIVED ones so the report can
        # show both. They are NEVER collapsed into one row, even though they agree here.
        mine["engine"] = {
            "entry": theirs["entry"], "sl": theirs["sl"], "sweep": theirs["sweep"],
            "source": "CRT.Execution log — 'Trade REJECTED: inverted SL'",
        }
        mine["parity"] = {
            "delta_entry": abs(mine["entry"] - theirs["entry"]),
            "delta_sl": abs(mine["sl"] - theirs["sl"]),
            "tolerance_dp": 5,
            "verdict": "PASS",
        }
    logger.info("arm %s: engine-parity assert passed on %d rejection(s)", arm.name, len(rejected))

    return bars, builds


ZONE_REASONS = {"Not in discount zone", "Not in premium zone"}


def _zone_gate_eval(snap: dict[str, Any], bar_reasons: list[tuple[str, str | None]]) -> dict[str, Any] | None:
    """Rung 4. OBSERVED on reject (the engine emits the reason); DERIVED on pass —
    recomputed from crt_engine_v2.py:3075-3078 with operands named."""
    observed = next((r for r, _ in bar_reasons if r in ZONE_REASONS), None)
    rng = snap.get("active_range")
    rt = snap.get("retest_candle")
    direction = snap.get("direction")
    if observed:
        return {"how": "OBSERVED", "passed": False, "reason": observed,
                "mid": None, "entry": None}
    if not rng or not rt or direction not in ("LONG", "SHORT"):
        return None
    mid = (float(rng["h_ref"]) + float(rng["l_ref"])) / 2.0
    entry = float(rt["close"])
    passed = (entry <= mid) if direction == "LONG" else (entry >= mid)
    return {
        "how": "DERIVED", "passed": passed, "reason": None,
        "h_ref": float(rng["h_ref"]), "l_ref": float(rng["l_ref"]),
        "mid": mid, "entry": entry, "direction": direction,
        "rule": ("LONG requires entry <= mid (discount)" if direction == "LONG"
                 else "SHORT requires entry >= mid (premium)"),
    }


SCORE_CONFOUND_NOTE = (
    "ARM CONFOUND: this arm overrides `session_windows`, which UltronRiskEngine.score_time "
    "also reads (crt_engine_v2.py:1837-1844) to set RiskScore.time_score. So this arm does not "
    "only open the session gate — it also RAISES final_S. The SL operands (entry, displacement "
    "extreme, atr_abs, buffer) are score-independent, so the inverted-SL conclusion is "
    "unaffected; but the two arms are NOT identical up to the session gate."
)


def build_journey(ep: dict[str, Any], arm_name: str, arm=None) -> list[dict[str, Any]]:
    """GUARD 2 — the ordered gate ladder, each rung tagged with HOW it is known.

    OBSERVED > DERIVED > INFERRED_BY_ORDER. The error this exists to prevent is calling
    something OBSERVED when it was only inferred from control flow: a session REJECT is
    observed (the engine emits reason + session_name), a session PASS is not — nothing is
    emitted, and we know it only because build_trade was subsequently called.
    """
    bars = ep["bars"]
    terminal = bars[-1]
    retest_bar = next((b for b in bars if b["action"] == "RETEST_CONFIRMED"), None)
    sg = next((b["score_gate"] for b in reversed(bars) if b.get("score_gate")), None)
    zg = next((b["zone_gate"] for b in reversed(bars) if b.get("zone_gate")), None)
    geom = terminal.get("geometry")
    sess_reject = next(
        (r for r in terminal["reasons"] if str(r["reason"]).startswith("off_session:")), None
    )
    came_from_shadow = bool((retest_bar or terminal)["state"].get("came_from_shadow"))

    rungs: list[dict[str, Any]] = []

    rungs.append({
        "gate": "RETEST_CONFIRMED", "how": "OBSERVED", "status": "PASS",
        "detail": f"action token at {retest_bar['timestamp']}" if retest_bar else "—",
    })

    if sg is not None:
        detail = (f"approve_with_soft_conf -> approved={sg['approved']}, "
                  f"final_S={sg['final_S']:.6f}, reason={sg['reason']}, "
                  f"tier_2={sg['tier_2_threshold']}")
        if arm is not None and getattr(arm, "session_windows", None) is not None:
            detail += f"\n{'':41}!! {SCORE_CONFOUND_NOTE}"
        rungs.append({
            "gate": "soft-conf score", "how": "OBSERVED",
            "status": "PASS" if sg["approved"] else "STOP",
            "detail": detail,
        })
    else:
        rungs.append({"gate": "soft-conf score", "how": "INFERRED_BY_ORDER", "status": "PASS",
                      "detail": "not captured on this bar; a later gate was reached"})

    rungs.append({
        "gate": "shadow age-decay", "how": "OBSERVED" if came_from_shadow else "N/A",
        "status": "PASS" if came_from_shadow else "N/A",
        "detail": "episode is not a shadow candidate" if not came_from_shadow else "shadow decay applied",
    })

    if zg is None:
        rungs.append({"gate": "zone", "how": "INFERRED_BY_ORDER", "status": "PASS",
                      "detail": "no zone rejection emitted and a later gate was reached"})
    elif zg["how"] == "OBSERVED":
        rungs.append({"gate": "zone", "how": "OBSERVED", "status": "STOP",
                      "detail": zg["reason"]})
    else:
        rungs.append({
            "gate": "zone", "how": "DERIVED",
            "status": "PASS" if zg["passed"] else "STOP",
            "detail": (f"mid=(h_ref {zg['h_ref']} + l_ref {zg['l_ref']})/2 = {zg['mid']:.5f} "
                       f"vs entry {zg['entry']} — {zg['rule']}"),
        })

    if sess_reject:
        rungs.append({
            "gate": "SESSION", "how": "OBSERVED", "status": "STOP",
            "detail": f"{sess_reject['reason']} (session_name={sess_reject['session_name']})",
        })
        return rungs

    if geom is not None:
        rungs.append({
            "gate": "SESSION", "how": "INFERRED_BY_ORDER", "status": "PASS",
            "detail": "no rejection emitted; known only because build_trade was subsequently called",
        })
        rungs.append({
            "gate": "shadow advisory", "how": "N/A" if not came_from_shadow else "OBSERVED",
            "status": "N/A" if not came_from_shadow else "PASS",
            "detail": "episode is not a shadow candidate" if not came_from_shadow else "",
        })
        rungs.append({"gate": "build_trade", "how": "OBSERVED", "status": "CALLED",
                      "detail": "executor.build_trade invoked (crt_engine_v2.py:3152)"})
        rungs.append({
            "gate": "SL guard", "how": "OBSERVED + DERIVED",
            "status": "STOP" if geom.get("inverted") else "PASS",
            "detail": (f"{geom.get('guard')}: sl {geom.get('sl'):.6f} vs entry {geom.get('entry')} "
                       f"-> {'FALSE' if geom.get('inverted') else 'TRUE'}"
                       + (f"  [{geom.get('guard_site')}]" if geom.get("inverted") else "")),
        })
        return rungs

    rungs.append({"gate": "SESSION", "how": "INFERRED_BY_ORDER", "status": "UNKNOWN",
                  "detail": "no rejection and no build_trade call on the terminal bar"})
    return rungs


def _build_geometry(engine: CRTEngine, state) -> dict[str, Any]:
    """Recompute crt_engine_v2.py:2201-2258 with every operand named. Asserted against the
    engine's own log above — never trusted on its own."""
    cfg = engine.config
    disp, rt = state.displacement_candle, state.retest_candle
    direction = state.direction
    atr = float(state.atr_abs)
    buf = float(cfg.sl_atr_buffer)
    entry = float(rt.close) if rt is not None else None
    dir_name = direction.name if direction is not None else None

    g: dict[str, Any] = {
        "direction": dir_name,
        "entry": entry,
        "entry_source": "state.retest_candle.close",
        "atr_abs": atr,
        "atr_source": "state.atr_abs (value on THIS bar — the soft-conf bar, not the RETEST bar)",
        "sl_atr_buffer": buf,
        "disp_high": float(disp.high) if disp else None,
        "disp_low": float(disp.low) if disp else None,
        "sweep_price": float(state.sweep_event.price) if state.sweep_event else None,
    }
    if disp is None or entry is None or dir_name not in ("LONG", "SHORT"):
        g.update({"sl": None, "inverted": None, "sl_expr": "(insufficient state)"})
        return g

    if direction == Direction.LONG:
        sl = float(disp.low) - buf * atr
        g["sl_expr"] = f"disp_low - sl_atr_buffer*atr = {disp.low} - {buf}*{atr:.6f}"
        g["guard"] = "LONG requires sl < entry"
        inverted = sl >= entry
    else:
        sl = float(disp.high) + buf * atr
        g["sl_expr"] = f"disp_high + sl_atr_buffer*atr = {disp.high} + {buf}*{atr:.6f}"
        g["guard"] = "SHORT requires sl > entry"
        inverted = sl <= entry

    g["sl"] = sl
    g["inverted"] = inverted
    g["guard_passed"] = not inverted
    g["guard_site"] = "crt_engine_v2.py:2231" if direction == Direction.LONG else "crt_engine_v2.py:2237"

    if not inverted:
        risk_dist = abs(entry - sl)
        intent = engine.executor._derive_trade_intent(
            state.cached_features or {}, cfg.breakout_disp_threshold
        )
        tp1_mult = getattr(cfg, f"tp1_atr_multiplier_{intent}", cfg.tp1_atr_multiplier)
        tp2_mult = cfg.tp2_atr_multiplier
        sign = 1.0 if direction == Direction.LONG else -1.0
        g.update(
            {
                "risk_dist": risk_dist, "intent": intent,
                "tp1_mult": float(tp1_mult), "tp2_mult": float(tp2_mult),
                "tp1": entry + sign * tp1_mult * risk_dist,
                "tp2": entry + sign * tp2_mult * risk_dist,
            }
        )
    return g


# ─────────────────────────────────────────────────────────────────────────────
# EPISODE SLICING
# ─────────────────────────────────────────────────────────────────────────────
def find_episodes(bars: list[dict[str, Any]], context: int) -> list[dict[str, Any]]:
    """Every terminal decision, sliced back to the SWEEP that opened it (+ context bars).

    A build_trade failure is terminal too, even though the engine leaves action="NONE" on that
    bar: `if trade:` simply never fires, so no action token is written (crt_engine_v2.py:3153).
    Keying on TERMINAL_ACTIONS alone silently misses exactly the case this script exists for.
    """
    episodes = []
    for i, b in enumerate(bars):
        is_build_failure = bool(b["geometry"]) and not b["geometry"].get("trade_built")
        if b["action"] not in TERMINAL_ACTIONS and not is_build_failure:
            continue
        # Restrict to episodes that actually reached RETEST. The state may already be reset on
        # this bar, so look BACKWARD for the RETEST_CONFIRMED rather than at current state.
        start = i
        saw_retest = False
        for j in range(i, -1, -1):
            if bars[j]["action"] == "RETEST_CONFIRMED":
                saw_retest = True
            if bars[j]["action"] in EPISODE_START_ACTIONS:
                start = j
                break
        if not saw_retest and b["action"] != "TRADE_OPENED":
            continue
        lo = max(0, start - context)
        episodes.append(
            {
                "terminal_index": b["bar_index"],
                "terminal_ts": b["timestamp"],
                "terminal_action": (
                    "TRADE_BUILD_FAILED" if is_build_failure else b["action"]
                ),
                "direction": (
                    b["state"].get("direction")
                    or (b["geometry"] or {}).get("direction")
                    or next((bars[j]["state"].get("direction")
                             for j in range(i, -1, -1) if bars[j]["state"].get("direction")), None)
                ),
                "bars": bars[lo: i + 1],
            }
        )
    return episodes


# ─────────────────────────────────────────────────────────────────────────────
# RENDERING
# ─────────────────────────────────────────────────────────────────────────────
def _f(v: Any, nd: int = 6) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}".rstrip("0").rstrip(".") if abs(v) < 1e7 else f"{v:.6g}"
    return str(v)


_STATUS_MARK = {"PASS": "OK", "STOP": "STOP", "N/A": "-", "CALLED": "->", "UNKNOWN": "?"}


def render_ladder(ep: dict[str, Any], arm_name: str, arm=None) -> str:
    """GUARD 2 — the causal journey as a ladder, every rung showing HOW it is known."""
    rungs = ep.get("journey") or build_journey(ep, arm_name, arm)
    L = [f"### Causal journey — arm {arm_name}", "", "```"]
    for i, r in enumerate(rungs):
        mark = _STATUS_MARK.get(r["status"], r["status"])
        L.append(f"{r['gate']:<20} {r['how']:<18} {mark}")
        if r["detail"]:
            L.append(f"{'':20} {'':18}    {r['detail']}")
        if i < len(rungs) - 1:
            L.append(f"{'':<8}v")
    L.append(f"{'':<8}v")
    L.append("       STOP" if rungs[-1]["status"] == "STOP" else "       (continues)")
    L.append("```")
    L.append("")
    return "\n".join(L)


def render_journeys(all_eps: list[dict[str, Any]]) -> str:
    """journeys.md — the two arms of each setup side by side."""
    L = ["# Causal journeys — A0 (observed production path) vs A3 (counterfactual)", ""]
    L.append("Each rung carries **how it is known**, ordered strongest first: "
             "`OBSERVED` > `DERIVED` > `INFERRED_BY_ORDER`.")
    L.append("")
    L.append("A session **rejection** is OBSERVED — the engine emits the reason and "
             "`session_name`. A session **pass** is INFERRED_BY_ORDER — nothing is emitted; it is "
             "known only because `build_trade` was subsequently called. These are not "
             "interchangeable and the report never renders the second as the first.")
    L.append("")

    by_setup: dict[str, dict[str, Any]] = {}
    for e in all_eps:
        by_setup.setdefault(e["terminal_ts"], {})[e["arm"]] = e

    for ts, arms in sorted(by_setup.items()):
        any_ep = next(iter(arms.values()))
        L.append(f"## {ts} — {any_ep['direction']}")
        L.append("")
        for arm_name in sorted(arms):
            ep = arms[arm_name]
            L.append(f"**{arm_name}** — terminal: `{ep['terminal_action']}`")
            L.append("")
            L.append(render_ladder(ep, arm_name, ep.get("_arm")))
        L.append("")

    L.append("---")
    L.append("")
    L.append("## The point")
    L.append("")
    L.append("**A3 did not turn the RETEST into a trade. It moved the same episode to the next "
             "binding gate.** Opening the session gate exposed `build_trade`, where the stop "
             "geometry is inverted and no `Trade` object is produced.")
    L.append("")
    L.append(SCOPE_NOTE)
    return "\n".join(L)


SCOPE_NOTE = (
    "> **Scope.** Descriptive only. This establishes that under current engine semantics these "
    "two counterfactual RETESTs produce inverted stop geometry and therefore cannot become "
    "trades. It is **not** a claim that the SL rule, the RETEST acceptance rule, or the session "
    "windows are wrong. Changing any of them is a separate hypothesis requiring its own "
    "authorization; this trace grants none."
)


def render_proof(ep: dict[str, Any], arm_name: str, ctx: dict[str, Any]) -> str:
    """proof.md — the compact evidence chain, one provenance class per line."""
    bars = ep["bars"]
    terminal = bars[-1]
    g = terminal.get("geometry")
    retest_bar = next((b for b in bars if b["action"] == "RETEST_CONFIRMED"), None)
    sg = next((b["score_gate"] for b in reversed(bars) if b.get("score_gate")), None)
    zg = next((b["zone_gate"] for b in reversed(bars) if b.get("zone_gate")), None)
    st = (retest_bar or terminal)["state"]
    sess = next((r for r in terminal["reasons"] if str(r["reason"]).startswith("off_session:")), None)

    L = [f"# Numerical proof — {ep['terminal_ts']} {ep['direction']} — arm {arm_name}", ""]
    L.append("| link | class | value |")
    L.append("|---|---|---|")

    if retest_bar:
        o = retest_bar["ohlcv"]
        L.append(f"| OHLC (retest bar {retest_bar['timestamp']}) | `OHLC` | "
                 f"o={_f(o['open'],2)} h={_f(o['high'],2)} l={_f(o['low'],2)} c={_f(o['close'],2)} |")
        feats = {f["name"]: f for f in consumed_features(ctx, retest_bar["bar_index"])}
        br, at = feats.get("body_ratio"), feats.get("atr")
        L.append(f"| feature | `FEATURE` | body_ratio={_f((br or {}).get('value'))} "
                 f"({(br or {}).get('fm_id')}), atr={_f((at or {}).get('value'))} "
                 f"({(at or {}).get('fm_id')}) |")
    rng = st.get("active_range")
    if rng:
        L.append(f"| CRT state | `STATE` | active_range h_ref={_f(rng['h_ref'])} "
                 f"l_ref={_f(rng['l_ref'])} |")
    L.append(f"| RETEST | `ENGINE` | RETEST_CONFIRMED @ "
             f"{retest_bar['timestamp'] if retest_bar else '—'} |")
    if sg:
        L.append(f"| score | `ENGINE` | approve_with_soft_conf -> approved={sg['approved']}, "
                 f"final_S={sg['final_S']:.6f} |")
    if zg:
        L.append(f"| zone | `ENGINE/DERIVED` | {zg['how']}: "
                 + (f"mid={_f(zg.get('mid'))} vs entry={_f(zg.get('entry'))} -> "
                    f"{'PASS' if zg['passed'] else 'STOP'}" if zg["how"] == "DERIVED"
                    else str(zg.get("reason"))) + " |")
    if sess:
        L.append(f"| session | `ENGINE` (OBSERVED) | {sess['reason']} -> STOP |")
    elif g:
        L.append("| session | INFERRED_BY_ORDER | no rejection emitted; build_trade was called |")

    if g:
        L.append(f"| entry | `STATE` | state.retest_candle.close = {_f(g['entry'])} |")
        ext = "disp_high" if g["direction"] == "SHORT" else "disp_low"
        L.append(f"| displacement extreme | `STATE` | state.displacement_candle."
                 f"{'high' if g['direction']=='SHORT' else 'low'} = {_f(g[ext])} |")
        L.append(f"| ATR | `STATE` | atr_abs @ soft-conf bar {terminal['timestamp']} = "
                 f"{_f(g['atr_abs'])} |")
        L.append(f"| buffer | `CONFIG` | crt_engine.sl_atr_buffer = {_f(g['sl_atr_buffer'])} |")
        L.append(f"| SL | `DERIVED` | {g['sl_expr']} = {g['sl']:.7f} |")
        if g.get("engine"):
            L.append(f"| engine SL | `ENGINE` | {g['engine']['sl']} |")
            L.append(f"| parity | `DERIVED`↔`ENGINE` | |delta|="
                     f"{g['parity']['delta_sl']:.3e} -> {g['parity']['verdict']} @5dp |")
        L.append(f"| invariant | `ENGINE` | {g['guard']} -> "
                 f"{'FALSE' if g.get('inverted') else 'TRUE'} |")
        L.append("| conclusion | | build_trade -> None -> no Trade object |")
    L.append("")
    if g:
        L.append(render_parity(g))
    L.append(SCOPE_NOTE)
    return "\n".join(L)


def render_episode(ep: dict[str, Any], arm_name: str, ctx: dict[str, Any], ftr_offset: int) -> str:
    L: list[str] = []
    L.append(f"# Episode {ep['terminal_ts']} — {ep['direction'] or '?'} — arm {arm_name}")
    L.append("")
    L.append(f"Terminal action: **{ep['terminal_action']}** at bar {ep['terminal_index']} "
             f"({ep['terminal_ts']}, broker time). {len(ep['bars'])} bars rendered.")
    L.append("")
    L.append(render_ladder(ep, arm_name, ep.get("_arm")))

    for b in ep["bars"]:
        o = b["ohlcv"]
        st = b["state"]
        decision = b["action"] in DECISION_ACTIONS
        mark = "  ***DECISION BAR***" if decision else ""
        L.append("---")
        L.append(f"## BAR {b['bar_index']}  {b['timestamp']}  "
                 f"[{b['state_before']} → {st['current_state']}]  action={b['action']}{mark}")
        L.append("")
        L.append(f"    OHLC   o={_f(o['open'],2)}  h={_f(o['high'],2)}  l={_f(o['low'],2)}  "
                 f"c={_f(o['close'],2)}  v={_f(o['volume'],0)}")
        L.append("")

        L.append("### CRT-consumed features")
        L.append("")
        L.append("| feature | value | FM id | formula |")
        L.append("|---|---|---|---|")
        for f in consumed_features(ctx, b["bar_index"] + ftr_offset):
            L.append(f"| `{f['name']}` | {_f(f['value'])} | {f['fm_id'] or '—'} | "
                     f"{(f['formula'] or '')[:70]} |")
        L.append("")

        L.append("### CRT state (named values)")
        L.append("")
        L.append("| variable | value |")
        L.append("|---|---|")
        for k in ("current_state", "direction", "atr_abs", "ema_fast_val", "ema_slow_val",
                  "soft_conf_candles", "evaluating_soft_conf", "came_from_shadow"):
            L.append(f"| `state.{k}` | {_f(st.get(k))} |")
        for grp in ("active_range", "sweep_event", "displacement_candle", "retest_candle",
                    "risk_score"):
            sub = st.get(grp)
            if not sub:
                L.append(f"| `state.{grp}` | — |")
                continue
            for k, v in sub.items():
                L.append(f"| `state.{grp}.{k}` | {_f(v)} |")
        if st.get("cached_features"):
            for k, v in sorted(st["cached_features"].items()):
                L.append(f"| `state.cached_features['{k}']` | {_f(v)} |")
        L.append("")

        if b["reasons"]:
            L.append("### Rejection")
            L.append("")
            for r in b["reasons"]:
                extra = f" (session_name=`{r['session_name']}`)" if r["session_name"] else ""
                L.append(f"- `{r['reason']}`{extra}")
            L.append("")

        if b["geometry"]:
            L.append("### SL operands (provenance-classed)")
            L.append("")
            L.append("| operand | value | class | source | note |")
            L.append("|---|---|---|---|---|")
            for op in geometry_operands(b["geometry"], ep, b["timestamp"]):
                L.append(f"| `{op['name']}` | {_f(op['value'])} | **{op['class']}** | "
                         f"`{op['source']}` | {op['note']} |")
            L.append("")
            L.append(render_geometry(b["geometry"]))
            L.append(render_parity(b["geometry"]))

        if decision:
            L.append("<details><summary>All 39 canonical features (ontology formula + value + "
                     "interpretation)</summary>")
            L.append("")
            rec = full_feature_record(ctx, b["bar_index"] + ftr_offset)
            L.append(FTR._render_bar_markdown(rec))
            L.append("")
            L.append("</details>")
            L.append("")
    return "\n".join(L)


def geometry_operands(g: dict[str, Any], ep: dict[str, Any], terminal_ts: str) -> list[dict[str, Any]]:
    """GUARD 1 — every SL operand as a classed, sourced row.

    The ATR pair is rendered TOGETHER at the point of use so a reader cannot substitute the
    visually-closest ATR: the RETEST bar's atr_abs is shown and marked UNUSED.
    """
    retest_bar = next((b for b in ep["bars"] if b["action"] == "RETEST_CONFIRMED"), None)
    retest_atr = retest_bar["state"]["atr_abs"] if retest_bar else None
    retest_ts = retest_bar["timestamp"] if retest_bar else "?"

    # The SL operand must be the SOFT-CONF bar's atr_abs, never the RETEST bar's. They differ
    # (07-22: 9.562143 vs 10.473571) and substituting the visually-closest one reproduces
    # neither the engine's SL nor its rejection.
    terminal_bar = ep["bars"][-1]
    if terminal_bar.get("geometry") is g:
        assert round(g["atr_abs"], 9) == round(float(terminal_bar["state"]["atr_abs"]), 9), (
            f"ATR provenance: SL operand {g['atr_abs']} != soft-conf bar atr_abs "
            f"{terminal_bar['state']['atr_abs']} @ {terminal_bar['timestamp']}"
        )
        if retest_atr is not None:
            assert round(g["atr_abs"], 9) != round(float(retest_atr), 9) or retest_bar is terminal_bar, (
                "ATR provenance: SL operand equals the RETEST-bar ATR; the pair must be "
                "distinguishable for this episode or the guard proves nothing"
            )

    ops = [
        _operand("direction", g["direction"], "STATE", "state.direction", f"@ {terminal_ts}"),
        _operand("entry", g["entry"], "STATE", "state.retest_candle.close",
                 f"retest candle @ {retest_ts}"),
    ]
    if retest_atr is not None:
        ops.append(_operand("atr_abs @ RETEST bar", retest_atr, "STATE", "state.atr_abs",
                            f"@ {retest_ts} — NOT the operand"))
    ops.append(_operand("atr_abs @ soft-conf bar", g["atr_abs"], "STATE", "state.atr_abs",
                        f"@ {terminal_ts} — <<< build_trade operand"))
    ops.append(_operand("sl_atr_buffer", g["sl_atr_buffer"], "CONFIG",
                        "crt_engine.sl_atr_buffer", "CRTConfig field"))
    if g.get("disp_high") is not None:
        ops.append(_operand("disp_high", g["disp_high"], "STATE",
                            "state.displacement_candle.high", ""))
    if g.get("disp_low") is not None:
        ops.append(_operand("disp_low", g["disp_low"], "STATE",
                            "state.displacement_candle.low", ""))
    if g.get("sweep_price") is not None:
        ops.append(_operand("sweep", g["sweep_price"], "STATE", "state.sweep_event.price", ""))
    ops.append(_operand("sl_trace", g["sl"], "DERIVED", g["sl_expr"], "recomputed by this script"))
    if g.get("engine"):
        ops.append(_operand("sl_engine", g["engine"]["sl"], "ENGINE", g["engine"]["source"],
                            "engine's own value — NOT collapsed with sl_trace"))
        ops.append(_operand("entry_engine", g["engine"]["entry"], "ENGINE", g["engine"]["source"], ""))
    return ops


def render_parity(g: dict[str, Any]) -> str:
    """GUARD 3 — parity promoted from an internal assert to reader-visible evidence."""
    if not g.get("engine") or not g.get("parity"):
        return ""
    e, p = g["engine"], g["parity"]
    L = [f"### Engine-parity proof — {g['direction']}", "", "```"]
    L.append("ENGINE")
    L.append(f"  entry     = {e['entry']}")
    L.append(f"  sl_engine = {e['sl']}")
    L.append(f"  source    : {e['source']}")
    L.append("")
    L.append("DERIVED")
    L.append(f"  sl_trace  = {g['sl_expr']}")
    L.append(f"            = {g['sl']:.7f}")
    L.append("")
    L.append("PARITY")
    L.append(f"  |delta_entry| = {p['delta_entry']:.3e}")
    L.append(f"  |delta_sl|    = {p['delta_sl']:.3e}")
    L.append(f"  -> {p['verdict']} @ {p['tolerance_dp']}dp")
    L.append("")
    L.append("ENGINE INVARIANT")
    L.append(f"  {g['guard']}")
    L.append(f"  {e['sl']} {'>' if g['direction'] == 'SHORT' else '<'} {e['entry']}  ->  FALSE")
    L.append("")
    L.append("CONCLUSION")
    L.append("  inverted SL -> build_trade returns None -> no Trade object")
    L.append("```")
    L.append("")
    return "\n".join(L)


def render_geometry(g: dict[str, Any]) -> str:
    L = ["### Execution geometry — `executor.build_trade` (crt_engine_v2.py:2191-2258)", "", "```"]
    L.append(f"direction  = state.direction                     = {g['direction']}")
    L.append(f"entry      = {g['entry_source']:<28} = {_f(g['entry'])}")
    L.append(f"atr        = state.atr_abs                       = {_f(g['atr_abs'])}")
    L.append(f"             ^ {g['atr_source']}")
    L.append(f"buffer     = config.sl_atr_buffer                = {_f(g['sl_atr_buffer'])}")
    if g.get("disp_high") is not None:
        L.append(f"disp_high  = state.displacement_candle.high      = {_f(g['disp_high'])}")
    if g.get("disp_low") is not None:
        L.append(f"disp_low   = state.displacement_candle.low       = {_f(g['disp_low'])}")
    if g.get("sweep_price") is not None:
        L.append(f"sweep      = state.sweep_event.price             = {_f(g['sweep_price'])}")
    L.append("")
    L.append(f"sl         = {g['sl_expr']}")
    L.append(f"           = {_f(g['sl'])}")
    L.append("")
    if g.get("inverted") is None:
        L.append("GUARD      : not evaluated (insufficient state)")
    elif g["inverted"]:
        L.append(f"GUARD ({g['guard']}): {_f(g['sl'])} vs entry {_f(g['entry'])}  ->  FALSE")
        L.append(f"  => build_trade returns None  [INVERTED SL]   {g['guard_site']}")
        L.append("  => no trade. TP1/TP2/risk_dist are never computed.")
    else:
        L.append(f"GUARD ({g['guard']}): PASSED")
        L.append(f"risk_dist  = |entry - sl|                        = {_f(g.get('risk_dist'))}")
        L.append(f"intent     = _derive_trade_intent(cached_features)= {g.get('intent')}")
        L.append(f"tp1        = entry ± tp1_mult*risk_dist ({_f(g.get('tp1_mult'))})   = {_f(g.get('tp1'))}")
        L.append(f"tp2        = entry ± tp2_mult*risk_dist ({_f(g.get('tp2_mult'))})   = {_f(g.get('tp2'))}")
    if g.get("actual"):
        L.append("")
        L.append(f"ENGINE Trade object: {json.dumps(g['actual'])}")
    L.append("```")
    L.append("")
    return "\n".join(L)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instrument", default=DEFAULT_INSTRUMENT,
                    help="instrument symbol; picks the default corpus data/mt5/<INST>_M15.csv")
    ap.add_argument("--xlsx", type=Path, default=None)
    ap.add_argument("--csv", type=Path, default=None, help="use a CSV corpus instead of --xlsx")
    ap.add_argument("--feature-csv", type=Path, default=None,
                    help="CSV twin for the ontology-rendered feature side "
                         "(defaults to the corpus itself when the corpus is a CSV)")
    ap.add_argument("--arms", default="A0,A3")
    ap.add_argument("--context-bars", type=int, default=5)
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = ap.parse_args(argv or sys.argv[1:])

    instrument = args.instrument.upper()
    if args.csv or args.xlsx:
        source = (args.csv or args.xlsx).resolve()
    elif instrument == DEFAULT_INSTRUMENT and DEFAULT_XLSX.exists():
        source = DEFAULT_XLSX.resolve()
    else:
        source = (ROOT / "data" / "mt5" / f"{instrument}_M15.csv").resolve()
    if not source.exists():
        raise SystemExit(f"corpus not found for {instrument}: {source}")
    if source.suffix.lower() in (".xlsx", ".xlsm"):
        candles, _ = load_from_xlsx(source)
    else:
        candles, _ = load_from_csv(source)
    logger.info("loaded %d candles from %s", len(candles), source)

    # The FTR renderers read a CSV. When the corpus IS a CSV, use it — the XAUUSD xlsx/CSV
    # twin was a special case, not the general shape. The same-corpus assert below still runs.
    if args.feature_csv is not None:
        feature_csv = args.feature_csv.resolve()
    elif source.suffix.lower() == ".csv":
        feature_csv = source
    else:
        feature_csv = DEFAULT_FEATURE_CSV.resolve()
    ctx = build_ftr_context(feature_csv, len(candles))
    # The feature side is rendered from the CSV twin; prove it is the same corpus, bar for bar.
    if len(ctx["df"]) != len(candles):
        raise SystemExit(
            f"feature CSV {feature_csv.name} has {len(ctx['df'])} rows but corpus "
            f"{source.name} has {len(candles)} — not the same corpus"
        )
    ftr_first = pd.Timestamp(ctx["df"].iloc[0]["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    if ftr_first != candles[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"):
        raise SystemExit(f"feature CSV starts {ftr_first}, corpus starts {candles[0].timestamp}")
    ftr_offset = 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    all_eps: list[dict[str, Any]] = []
    bar_rows: list[dict[str, Any]] = []
    operand_rows: list[dict[str, Any]] = []
    inverted_episodes: dict[str, set[str]] = {}
    for arm in build_arms([a.strip() for a in args.arms.split(",") if a.strip()]):
        logger.info("replaying arm %s (%s) ...", arm.name, arm.label)
        bars, builds = replay(candles, arm, instrument)
        eps = find_episodes(bars, args.context_bars)
        logger.info("  arm %s: %d episode(s), %d build_trade call(s)", arm.name, len(eps), len(builds))

        for ep in eps:
            ep["_arm"] = arm
            ep["journey"] = build_journey(ep, arm.name, arm)
            tag = f"{ep['terminal_ts'].replace(' ', '_').replace(':', '')}_{ep['direction'] or 'NA'}"
            path = out_dir / f"episode_{tag}_{arm.name}.md"
            path.write_text(render_episode(ep, arm.name, ctx, ftr_offset), encoding="utf-8")
            (out_dir / f"proof_{tag}_{arm.name}.md").write_text(
                render_proof(ep, arm.name, ctx), encoding="utf-8"
            )
            # GUARD 1 audit trail: every displayed SL operand, with its class.
            g_term = ep["bars"][-1].get("geometry")
            if g_term:
                if g_term.get("inverted"):
                    inverted_episodes.setdefault(arm.name, set()).add(tag)
                for op in geometry_operands(g_term, ep, ep["terminal_ts"]):
                    operand_rows.append({"arm": arm.name, "episode": tag, **op})
            all_eps.append({"arm": arm.name, "file": path.name, **{k: v for k, v in ep.items() if k != "bars"},
                            "bars": ep["bars"]})
            for b in ep["bars"]:
                row = {"arm": arm.name, "episode": tag, "bar_index": b["bar_index"],
                       "timestamp": b["timestamp"], **{f"ohlcv_{k}": v for k, v in b["ohlcv"].items()},
                       "state_before": b["state_before"], "action": b["action"]}
                for f in consumed_features(ctx, b["bar_index"] + ftr_offset):
                    row[f"feat_{f['name']}"] = f["value"]
                for k, v in b["state"].items():
                    if isinstance(v, dict):
                        for kk, vv in v.items():
                            row[f"state_{k}_{kk}"] = vv
                    else:
                        row[f"state_{k}"] = v
                bar_rows.append(row)

    pd.DataFrame(bar_rows).to_csv(out_dir / "bars.csv", index=False)
    (out_dir / "journeys.md").write_text(render_journeys(all_eps), encoding="utf-8")
    if operand_rows:
        od = pd.DataFrame(operand_rows)
        # GUARD 1 enforcement at the artifact boundary: no operand may reach disk unclassed.
        blank = od[od["class"].isna() | (od["class"].astype(str).str.strip() == "")]
        if len(blank):
            raise RuntimeError(f"{len(blank)} operand row(s) reached output without a "
                               f"provenance class — instrumentation error, not a display gap")
        # DERIVED and ENGINE must BOTH be present as distinct rows for every inverted-SL
        # rejection — never collapsed, and never silently missing. Phrased as a positive
        # requirement on the known rejection set: an `if "sl_engine" in names` guard would be
        # vacuous exactly when the ENGINE row went missing, which is the failure it must catch.
        for (arm_, ep_), grp in od.groupby(["arm", "episode"]):
            names = set(grp["name"])
            if ep_ in inverted_episodes.get(arm_, set()):
                missing = {"sl_trace", "sl_engine"} - names
                assert not missing, (
                    f"{arm_}/{ep_}: inverted-SL episode is missing {sorted(missing)} — DERIVED "
                    f"and ENGINE must both be rendered, as distinct rows"
                )
        od.to_csv(out_dir / "operands.csv", index=False)
    with open(out_dir / "episodes.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "source": {"path": str(source.relative_to(ROOT)), "sha256": _sha256(source)},
                "active_version": get_active_version(),
                "schema_version": SCHEMA_VERSION,
                "episodes": all_eps,
            },
            fh, indent=2, default=str,
        )

    logger.info("wrote -> %s", out_dir.relative_to(ROOT))
    print()
    for e in all_eps:
        print(f"  {e['arm']}  {e['terminal_ts']}  {e['direction'] or '?':5}  "
              f"{e['terminal_action']:20}  -> {e['file']}")
    print(f"\n-> {out_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
