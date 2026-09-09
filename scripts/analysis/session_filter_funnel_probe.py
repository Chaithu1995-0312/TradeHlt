#!/usr/bin/env python3
"""
session_filter_funnel_probe.py
===============================
Why do XAUUSD CRT RETESTs die at the session filter, and when would one pass?

The Excel trace over 2026-07-22 -> 2026-08-07 found 2 RETESTs and 0 trades, both killed at
crt_engine_v2.py:3096-3130 with `off_session:OFF_SESSION`. n=2 cannot say how often a RETEST
*would* pass, so this probe replays a large corpus and measures the whole gate chain, then
re-runs it under three counterfactual arms to isolate which of the clock, the allowed set, or
the window widths is actually binding.

Gate chain classified (read off crt_engine_v2.py:3000-3135):

    RETEST_CONFIRMED
      -> soft-conf score gate   (approve_with_soft_conf -> LOW_SCORE / other RejectReason)
      -> shadow age-decay gate  (shadow candidates only)
      -> zone gate              ("Not in discount zone" / "Not in premium zone")
      -> SESSION GATE           ("off_session:<NAME>")     <- the gate under study
      -> shadow_advisory_only block
      -> TRADE_OPENED

"Reached the session gate" is counted separately from "passed it": a RETEST that dies at score
or zone never reaches session and must not be scored against it.

Arms (each a FULL independent replay -- a veto changes the trajectory via reset_to_range, so
arms cannot share one pass; that is F-055's removed-!=-added lesson):

    A0 baseline      as configured today
    A1 clock         _session_ts_basis = "utc_corrected"          (is the timezone binding?)
    A2 allowed_set   allowed_sessions + ASIA                      (is the allowed set binding?)
    A3 windows       A1's clock + session_windows rebuilt from the already-registered
                     feature_pipeline.session_windows_utc         (are the widths binding?)

Every arm is a process-local dataclasses.replace + instance-attribute override. NOTHING is
written to config, src/, or ACTIVE_VERSION.

SCOPE: this counts trade OPPORTUNITIES, not profitability. More trades is not better trades
(F-015: detection-gate relaxation is not quality-preserving). An arm that unlocks trades earns
a follow-up backtest, not a config change. It also does NOT settle whether session_windows is
UTC-authored or broker-authored -- F-066 records that the filter was empirically tuned on broker
time and left alone deliberately. A1/A3 measure what the correction WOULD do; choosing it is an
economic decision.

Usage:
    venv/Scripts/python.exe scripts/analysis/session_filter_funnel_probe.py
    venv/Scripts/python.exe scripts/analysis/session_filter_funnel_probe.py \\
        --csv data/XAUUSD_M15.csv --arms A0          # 17-day regression anchor
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
os.chdir(ROOT)

# CRT-isolated spine (F-037): no fusion veto in this measurement.
os.environ.setdefault("BACKTEST_ENGINE_GATE", "0")

import pandas as pd

from config_layer.crt_engine_v2 import CRTEngine, Candle
from config_layer.production_config import (
    get_active_version,
    get_prod_section,
    load_prod_config_from_registry,
)
from runtime.backtest_v2 import HTFBuilder

# Reused verbatim from the sibling trace script — same corpus loader, same hashing.
from xauusd_excel_feature_state_trace import _sha256, load_from_csv, load_from_xlsx

logger = logging.getLogger("SESSION_FUNNEL")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEFAULT_INSTRUMENT = "XAUUSD"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "session_filter_funnel"
BAR_MINUTES = 15
# Broker calendar: 23 trading hours/day (the 23:45->01:00 rollover break), 5 days/week.
TRADING_HOURS_PER_DAY = 23.0
TRADING_DAYS_PER_WEEK = 5.0

ZONE_REASONS = {"Not in discount zone", "Not in premium zone"}
EVENT_ACTIONS = {"RETEST_CONFIRMED", "TRADE_OPENED", "SHADOW_ADVISORY_BLOCK"}


def _event_row(
    arm: "Arm",
    candle: Candle,
    state_before: str,
    engine: CRTEngine,
    action: str | None,
    bar_reasons: list[tuple[str, str | None]],
    *,
    build_called: bool = False,
    build_failed: bool = False,
) -> dict[str, Any]:
    """One inspectable row per notable bar. Display-only; feeds no counter."""
    from features import broker_clock as _bc

    utc = _bc.mt5_server_to_utc_scalar(candle.timestamp)
    reason = ";".join(r for r, _ in bar_reasons) or None
    sess = next((s for _, s in bar_reasons if s), None)

    if action == "TRADE_OPENED":
        verdict = "TRADE_OPENED"
    elif build_failed:
        # Passed session, then executor.build_trade returned None (e.g. inverted SL).
        verdict = "TRADE_BUILD_FAILED"
    elif any(r.startswith("off_session:") for r, _ in bar_reasons):
        verdict = "SESSION_REJECTED"
    elif any(r in ZONE_REASONS for r, _ in bar_reasons):
        verdict = "ZONE_REJECTED"
    elif bar_reasons:
        verdict = "OTHER_REJECTED"
    else:
        verdict = action or "—"

    st = engine.state
    return {
        "arm": arm.name,
        "bar_index": candle.index,
        "timestamp_broker": candle.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp_utc": utc.strftime("%Y-%m-%d %H:%M:%S"),
        "hour_broker": candle.timestamp.hour,
        "hour_utc": utc.hour,
        "action": action,
        "state_before": state_before,
        "state_after": st.current_state.name,
        "direction": st.direction.name if st.direction is not None else None,
        "reason": reason,
        # session_name is the ENGINE's own label (crt_engine_v2.py:3120), not a recomputation.
        "session_name": sess,
        "session_passed": build_called or action == "SHADOW_ADVISORY_BLOCK",
        "retest_close": float(st.retest_candle.close) if st.retest_candle else None,
        "disp_high": float(st.displacement_candle.high) if st.displacement_candle else None,
        "disp_low": float(st.displacement_candle.low) if st.displacement_candle else None,
        "atr_abs": float(st.atr_abs),
        "verdict": verdict,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ARMS
# ─────────────────────────────────────────────────────────────────────────────
@dataclasses.dataclass(frozen=True)
class Arm:
    name: str
    label: str
    ts_basis: str                                   # "broker_local" | "utc_corrected"
    allowed_sessions: tuple[str, ...] | None        # None = leave config value
    session_windows: dict[str, tuple[dtime, dtime]] | None  # None = leave config value


def _windows_from_utc_hours(spec: dict[str, list[int]]) -> dict[str, tuple[dtime, dtime]]:
    """feature_pipeline.session_windows_utc ({'ASIA':[0,9],...}) -> CRTConfig window shape.

    Config dict order is preserved: the engine's window loop breaks on FIRST match, and these
    windows overlap (ASIA 0-9 vs LONDON 7-16), so order decides the label on shared hours.
    """
    out: dict[str, tuple[dtime, dtime]] = {}
    for name, (start_h, end_h) in spec.items():
        out[name.upper()] = (dtime(int(start_h), 0), dtime(int(end_h), 0))
    return out


def build_arms(names: list[str]) -> list[Arm]:
    utc_windows = _windows_from_utc_hours(
        get_prod_section("feature_pipeline")["session_windows_utc"]
    )
    catalogue = {
        "A0": Arm("A0", "baseline (as configured)", "broker_local", None, None),
        "A1": Arm("A1", "clock: utc_corrected", "utc_corrected", None, None),
        "A2": Arm("A2", "allowed_sessions + ASIA", "broker_local",
                  ("LONDON", "NEWYORK", "OVERLAP", "ASIA"), None),
        "A3": Arm("A3", "utc clock + session_windows_utc", "utc_corrected",
                  ("LONDON", "NEWYORK", "OVERLAP", "ASIA"), utc_windows),
    }
    missing = [n for n in names if n not in catalogue]
    if missing:
        raise SystemExit(f"unknown arm(s): {missing}; known: {sorted(catalogue)}")
    return [catalogue[n] for n in names]


# ─────────────────────────────────────────────────────────────────────────────
# REPLAY  (arm-aware; instrumented for the gate chain)
# ─────────────────────────────────────────────────────────────────────────────
def replay_arm(candles: list[Candle], arm: Arm, instrument: str) -> dict[str, Any]:
    base = load_prod_config_from_registry(get_active_version(), instrument)
    overrides: dict[str, Any] = {}
    if arm.allowed_sessions is not None:
        overrides["allowed_sessions"] = arm.allowed_sessions
    if arm.session_windows is not None:
        overrides["session_windows"] = arm.session_windows
    cfg = dataclasses.replace(base, **overrides) if overrides else base

    engine = CRTEngine(cfg)
    # Process-local clock override. The attribute is assigned from config at
    # crt_engine_v2.py:2483; reassigning the instance attribute changes nothing on disk.
    engine._session_ts_basis = arm.ts_basis

    htf = HTFBuilder(4, instrument)
    initialized = False

    reasons: Counter[str] = Counter()
    session_names: Counter[str] = Counter()
    retest_hours: Counter[int] = Counter()
    pass_hours: Counter[int] = Counter()
    trade_hours: Counter[int] = Counter()

    # Per-bar reason capture, so a rejection is attributable to the bar it fired on.
    # (reason, session_name) — session_name comes from the ENGINE's own metadata at
    # crt_engine_v2.py:3117-3121, never recomputed here: a second implementation of the
    # window-matching logic would be free to drift from the one under test.
    bar_reasons: list[tuple[str, str | None]] = []
    events: list[dict[str, Any]] = []
    orig_record = engine.ev_log.record

    def record(event, candle, **kwargs):  # type: ignore[no-untyped-def]
        if str(getattr(event, "name", event)) == "FILTER_REJECTED":
            r = str(kwargs.get("reason") or "")
            if r:
                meta = kwargs.get("metadata") or {}
                sess = meta.get("session_name") if isinstance(meta, dict) else None
                bar_reasons.append((r, sess))
        return orig_record(event, candle, **kwargs)

    engine.ev_log.record = record  # type: ignore[method-assign]

    # ── build_trade wrap ──────────────────────────────────────────────────
    # executor.build_trade is called at crt_engine_v2.py:3152, STRICTLY AFTER the session gate
    # and the shadow-advisory block. So a call here is proof the setup PASSED session — even
    # when the build then fails (inverted SL), which emits no FILTER_REJECTED and no
    # TRADE_OPENED. Counting session passes off TRADE_OPENED alone silently loses those.
    # (Wrap precedent: reports/xauusd_retest_pathb_counterfactual_probe.py:265.)
    build_stats = {"calls": 0, "failed": 0, "this_bar": 0}
    orig_build = engine.executor.build_trade

    def build_trade_traced(state, risk_engine=None):  # type: ignore[no-untyped-def]
        build_stats["calls"] += 1
        build_stats["this_bar"] += 1
        trade = orig_build(state, risk_engine)
        if trade is None:
            build_stats["failed"] += 1
        return trade

    engine.executor.build_trade = build_trade_traced  # type: ignore[method-assign]

    counts: Counter[str] = Counter()
    for candle in candles:
        completed = htf.push(candle)
        if not initialized:
            if completed:
                engine.initialise_range(htf.seed_candles(), htf.current_htf_id, "UNKNOWN")
                initialized = True
            continue

        bar_reasons.clear()
        build_stats["this_bar"] = 0
        state_before = engine.state.current_state.name
        result = engine.process_candle(candle, htf.current_htf_id)
        action = result.get("action") if isinstance(result, dict) else str(result)
        hour = candle.timestamp.hour

        if action == "RETEST_CONFIRMED":
            counts["retest_confirmed"] += 1
            retest_hours[hour] += 1

        for r, sess in bar_reasons:
            reasons[r] += 1
            if r.startswith("off_session:"):
                counts["session_rejected"] += 1
                session_names[r.split(":", 1)[1]] += 1
            elif r in ZONE_REASONS:
                counts["zone_rejected"] += 1
            else:
                counts["other_rejected"] += 1

        # A build_trade call on this bar == the setup cleared the session gate, whether or not
        # the build succeeded. This is the only reliable pass signal (see the wrap comment).
        if build_stats["this_bar"]:
            counts["session_passed"] += 1
            pass_hours[hour] += 1
            if action == "TRADE_OPENED":
                counts["trade_opened"] += 1
                trade_hours[hour] += 1
            else:
                counts["trade_build_failed"] += 1
        elif action == "SHADOW_ADVISORY_BLOCK":
            # Passed session, then died to the shadow-advisory block (before build_trade).
            counts["shadow_blocked"] += 1
            counts["session_passed"] += 1
            pass_hours[hour] += 1

        # ── Per-event detail (additive; affects no counter above) ──────────
        if action in EVENT_ACTIONS or bar_reasons or build_stats["this_bar"]:
            events.append(
                _event_row(
                    arm, candle, state_before, engine, action, bar_reasons,
                    build_called=bool(build_stats["this_bar"]),
                    build_failed=bool(build_stats["this_bar"]) and action != "TRADE_OPENED",
                )
            )

    engine.ev_log.record = orig_record  # type: ignore[method-assign]
    engine.executor.build_trade = orig_build  # type: ignore[method-assign]

    counts["reached_session"] = counts["session_rejected"] + counts["session_passed"]
    counts["build_trade_calls"] = build_stats["calls"]
    # Unresolved = RETESTs that never reached the session gate and never died at zone/score
    # (e.g. still evaluating soft-confirmation at corpus end, or a confirmation timeout).
    counts["retest_unresolved"] = max(
        0,
        counts["retest_confirmed"]
        - counts["reached_session"]
        - counts["zone_rejected"]
        - counts["other_rejected"],
    )

    return {
        "arm": arm.name,
        "label": arm.label,
        "config": {
            "ts_basis": arm.ts_basis,
            "allowed_sessions": list(cfg.allowed_sessions),
            "session_windows": {
                k: [v[0].strftime("%H:%M"), v[1].strftime("%H:%M")]
                for k, v in cfg.session_windows.items()
            },
        },
        "counts": dict(counts),
        "reasons": dict(reasons),
        "session_names": dict(session_names),
        "retest_hours": dict(retest_hours),
        "pass_hours": dict(pass_hours),
        "trade_hours": dict(trade_hours),
        "events": events,
    }


# ─────────────────────────────────────────────────────────────────────────────
# RATES
# ─────────────────────────────────────────────────────────────────────────────
def compute_rates(res: dict[str, Any], n_bars: int) -> dict[str, Any]:
    c = res["counts"]
    trades = c.get("trade_opened", 0)
    span_hours = n_bars * BAR_MINUTES / 60.0
    span_trading_days = span_hours / TRADING_HOURS_PER_DAY
    span_calendar_days = span_trading_days * (7.0 / TRADING_DAYS_PER_WEEK)

    def per(n: int) -> dict[str, Any]:
        if n <= 0:
            return {"count": 0, "bars_per": None, "calendar_days_between": None}
        return {
            "count": n,
            "bars_per": round(n_bars / n, 1),
            "calendar_days_between": round(span_calendar_days / n, 1),
        }

    reached = c.get("reached_session", 0)
    passed = c.get("session_passed", 0)
    return {
        "arm": res["arm"],
        "label": res["label"],
        "bars": n_bars,
        "span_calendar_days": round(span_calendar_days, 1),
        "retest_confirmed": per(c.get("retest_confirmed", 0)),
        "reached_session": reached,
        "session_passed": passed,
        "session_pass_rate": round(passed / reached, 4) if reached else None,
        "trade_opened": per(trades),
    }


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
FUNNEL_STAGES = [
    ("retest_confirmed", "RETEST_CONFIRMED"),
    ("zone_rejected", "  died: zone gate"),
    ("other_rejected", "  died: score / other"),
    ("retest_unresolved", "  unresolved (no terminal event)"),
    ("reached_session", "reached SESSION gate"),
    ("session_rejected", "  died: session gate"),
    ("session_passed", "  passed session"),
    ("shadow_blocked", "    died: shadow-advisory block"),
    ("trade_build_failed", "    died: trade build (e.g. inverted SL)"),
    ("trade_opened", "TRADE_OPENED"),
]


def write_outputs(out_dir: Path, results: list[dict], rates: list[dict], manifest: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    funnel_rows = []
    for res in results:
        n_ret = res["counts"].get("retest_confirmed", 0)
        for key, label in FUNNEL_STAGES:
            n = res["counts"].get(key, 0)
            funnel_rows.append(
                {
                    "arm": res["arm"], "arm_label": res["label"],
                    "stage": label, "stage_key": key, "count": n,
                    "pct_of_retests": round(100.0 * n / n_ret, 1) if n_ret else None,
                }
            )
    pd.DataFrame(funnel_rows).to_csv(out_dir / "funnel.csv", index=False)

    rej_rows = []
    for res in results:
        for reason, n in sorted(res["reasons"].items(), key=lambda kv: -kv[1]):
            rej_rows.append(
                {
                    "arm": res["arm"], "reason": reason, "count": n,
                    "is_session": reason.startswith("off_session:"),
                }
            )
    pd.DataFrame(rej_rows).to_csv(out_dir / "rejections.csv", index=False)

    event_rows = [row for res in results for row in res.get("events", [])]
    if event_rows:
        pd.DataFrame(event_rows).to_csv(out_dir / "events.csv", index=False)

    hour_rows = []
    for res in results:
        for h in range(24):
            hour_rows.append(
                {
                    "arm": res["arm"], "broker_hour": h,
                    "retests": res["retest_hours"].get(h, 0),
                    "session_passes": res["pass_hours"].get(h, 0),
                    "trades": res["trade_hours"].get(h, 0),
                }
            )
    pd.DataFrame(hour_rows).to_csv(out_dir / "hour_profile.csv", index=False)

    with open(out_dir / "rates.json", "w", encoding="utf-8") as fh:
        json.dump({"manifest": manifest, "rates": rates, "arms": results}, fh, indent=2, default=str)

    lines = [
        f"# Session-filter funnel — {manifest['corpus']['instrument']}",
        "",
        f"Corpus: `{manifest['source']['path']}` — {manifest['corpus']['bars']:,} bars, "
        f"{manifest['corpus']['first_timestamp']} → {manifest['corpus']['last_timestamp']} "
        f"(broker-server time).",
        f"Active config: `{manifest['config']['active_version']}`.",
        "",
        "| Arm | Setup | RETESTs | reached session | passed | TRADE_OPENED | days between trades |",
        "|---|---|---|---|---|---|---|",
    ]
    for r, res in zip(rates, results):
        lines.append(
            f"| {r['arm']} | {r['label']} | {r['retest_confirmed']['count']} | "
            f"{r['reached_session']} | {r['session_passed']} | {r['trade_opened']['count']} | "
            f"{r['trade_opened']['calendar_days_between'] or '—'} |"
        )
    lines += [
        "",
        "## Scope",
        "",
        "- Counts trade OPPORTUNITIES, not profitability. More trades is not better trades "
        "(F-015). An arm that unlocks trades earns a follow-up backtest, not a config change.",
        "- Does not settle whether `session_windows` is UTC- or broker-authored. F-066 records "
        "the filter was empirically tuned on broker time and left alone deliberately. A1/A3 "
        "measure what the correction would do; choosing it is an economic decision.",
        "- No config was modified. Every arm is a process-local `dataclasses.replace`.",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--instrument", default=DEFAULT_INSTRUMENT,
                    help="instrument symbol; picks the default corpus data/mt5/<INST>_M15.csv")
    ap.add_argument("--csv", type=Path, default=None, help="corpus CSV (overrides --instrument default)")
    ap.add_argument("--xlsx", type=Path, default=None, help="Excel corpus alternative")
    ap.add_argument("--arms", default="A0,A1,A2,A3", help="comma-separated arm ids")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = ap.parse_args(argv or sys.argv[1:])

    instrument = args.instrument.upper()
    source = (args.xlsx or args.csv or (ROOT / "data" / "mt5" / f"{instrument}_M15.csv")).resolve()
    if not source.exists():
        logger.error("source not found: %s", source)
        return 1

    if source.suffix.lower() in (".xlsx", ".xlsm"):
        candles, _ = load_from_xlsx(source)
    else:
        candles, _ = load_from_csv(source)
    logger.info("loaded %d candles from %s", len(candles), source)

    arms = build_arms([a.strip() for a in args.arms.split(",") if a.strip()])
    results, rates = [], []
    for arm in arms:
        logger.info("replaying arm %s (%s) ...", arm.name, arm.label)
        res = replay_arm(candles, arm, instrument)
        c = res["counts"]
        # Real closure invariants. (An earlier version asserted
        # reached_session == passed + rejected, which was VACUOUS -- reached_session is DEFINED
        # as that sum, so the assert could never fail. These two can.)
        assert c.get("build_trade_calls", 0) == (
            c.get("trade_opened", 0) + c.get("trade_build_failed", 0)
        ), f"arm {arm.name}: build_trade outcomes do not close: {c}"
        assert c.get("retest_confirmed", 0) == (
            c.get("reached_session", 0) + c.get("zone_rejected", 0)
            + c.get("other_rejected", 0) + c.get("retest_unresolved", 0)
        ), f"arm {arm.name}: RETEST funnel does not close: {c}"
        results.append(res)
        rates.append(compute_rates(res, len(candles)))
        logger.info(
            "  %s: retests=%d reached_session=%d passed=%d trades=%d",
            arm.name, c.get("retest_confirmed", 0), c.get("reached_session", 0),
            c.get("session_passed", 0), c.get("trade_opened", 0),
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / stamp
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/analysis/session_filter_funnel_probe.py",
        "read_only": True,
        "source": {
            "path": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
            "sha256": _sha256(source),
        },
        "corpus": {
            "instrument": instrument,
            "bars": len(candles),
            "first_timestamp": candles[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "last_timestamp": candles[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp_basis": "broker-server time as exported by MT5 (F-066)",
        },
        "config": {"active_version": get_active_version(), "modified": False},
        "arms": [a.name for a in arms],
    }
    write_outputs(out_dir, results, rates, manifest)

    logger.info("wrote -> %s", out_dir.relative_to(ROOT))
    print()
    print(f"{'arm':4} {'setup':34} {'RETEST':>7} {'reachSess':>10} {'passed':>7} {'TRADES':>7} {'days/trade':>11}")
    for r in rates:
        print(
            f"{r['arm']:4} {r['label'][:34]:34} {r['retest_confirmed']['count']:>7} "
            f"{r['reached_session']:>10} {r['session_passed']:>7} "
            f"{r['trade_opened']['count']:>7} "
            f"{str(r['trade_opened']['calendar_days_between'] or '-'):>11}"
        )
    print(f"\n-> {out_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
