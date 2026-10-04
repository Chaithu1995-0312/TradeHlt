#!/usr/bin/env python3
"""
run_crt_trace_workflow.py
==========================
One command for the SURVEY -> LOCATE -> PROVE trace workflow.

    [1/3] SURVEY   xauusd_excel_feature_state_trace   what happened, bar by bar
    [2/3] LOCATE   session_filter_funnel_probe        where does it die, and what would change it
    [3/3] PROVE    crt_episode_number_trace           exactly which numbers produced that

Method and discipline: scripts/analysis/CRT_TRACE_WORKFLOW.md

Read-only. No src/, no config, no ACTIVE_VERSION. Every stage is observe-only; this driver only
sequences them, checks preconditions, and indexes the artifacts.

FAIL LOUDLY. Any assert firing inside any stage aborts the whole workflow naming that stage. A
partial workflow must never be mistaken for a complete one.

Usage:
    venv/Scripts/python.exe scripts/analysis/run_crt_trace_workflow.py --instrument EURUSD
    venv/Scripts/python.exe scripts/analysis/run_crt_trace_workflow.py \\
        --instrument XAUUSD --corpus data/XAUUSD_M15_20260807_203705.xlsx
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
os.chdir(ROOT)

os.environ.setdefault("BACKTEST_ENGINE_GATE", "0")

import pandas as pd

from config_layer.production_config import get_active_version, load_prod_config_from_registry

import crt_episode_number_trace as S3_PROVE
import session_filter_funnel_probe as S2_LOCATE
import xauusd_excel_feature_state_trace as S1_SURVEY

logger = logging.getLogger("CRT_WORKFLOW")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEFAULT_OUTPUT_DIR = ROOT / "results" / "crt_workflow"
DEFAULT_INSTRUMENT = "XAUUSD"

# All six MT5 instruments currently resolve to IDENTICAL CRT config (same allowed_sessions,
# sl_atr_buffer, body_ratio_min). A cross-instrument run therefore varies DATA ONLY — it is not
# a config comparison. Preflight says so out loud so the distinction is never lost.
CONFIG_INVARIANCE_NOTE = (
    "All MT5 instruments currently resolve to the SAME CRT config. A cross-instrument run varies "
    "DATA ONLY, not configuration — and any config-level defect found here (e.g. the OVERLAP "
    "dead token) is repo-wide, not instrument-specific."
)


# ─────────────────────────────────────────────────────────────────────────────
# PREFLIGHT
# ─────────────────────────────────────────────────────────────────────────────
def preflight(instrument: str, corpus: Path) -> dict[str, Any]:
    """Fail before any replay, naming the cause. Never half-run."""
    try:
        cfg = load_prod_config_from_registry(get_active_version(), instrument)
    except Exception as exc:
        raise SystemExit(
            f"PREFLIGHT FAILED: config does not resolve for instrument {instrument!r}: "
            f"{type(exc).__name__}: {exc}"
        )
    if not corpus.exists():
        raise SystemExit(f"PREFLIGHT FAILED: corpus not found for {instrument}: {corpus}")

    if corpus.suffix.lower() in (".xlsx", ".xlsm"):
        candles, _ = S1_SURVEY.load_from_xlsx(corpus)
    else:
        candles, _ = S1_SURVEY.load_from_csv(corpus)
    if not candles:
        raise SystemExit(f"PREFLIGHT FAILED: corpus {corpus} contains no candles")

    windows = {k: [v[0].strftime("%H:%M"), v[1].strftime("%H:%M")]
               for k, v in cfg.session_windows.items()}
    # Surface the dead-token class directly: an allowed session with no window can never match.
    unmatched = [s for s in cfg.allowed_sessions if s.upper() not in
                 {k.upper() for k in cfg.session_windows}]

    info = {
        "instrument": instrument,
        "active_version": get_active_version(),
        "corpus": str(corpus.relative_to(ROOT)) if corpus.is_relative_to(ROOT) else str(corpus),
        "corpus_sha256": S1_SURVEY._sha256(corpus),
        "bars": len(candles),
        "first_timestamp": candles[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "last_timestamp": candles[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "allowed_sessions": list(cfg.allowed_sessions),
        "session_windows": windows,
        "sl_atr_buffer": float(cfg.sl_atr_buffer),
        "body_ratio_min": float(cfg.body_ratio_min),
        "unmatchable_allowed_sessions": unmatched,
        "config_invariance_note": CONFIG_INVARIANCE_NOTE,
    }
    logger.info("preflight OK — %s, %d bars, %s -> %s", instrument, info["bars"],
                info["first_timestamp"], info["last_timestamp"])
    if unmatched:
        logger.warning("allowed_sessions %s have NO window and can never match (dead tokens)",
                       unmatched)
    return info


# ─────────────────────────────────────────────────────────────────────────────
# STAGE RUNNER
# ─────────────────────────────────────────────────────────────────────────────
def run_stage(label: str, module, argv: list[str], stage_dir: Path) -> Path:
    """Call a stage's main(argv) in-process. Abort the workflow on any failure."""
    logger.info("[%s] %s ...", label, module.__name__)
    stage_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in stage_dir.iterdir() if p.is_dir()}
    try:
        rc = module.main(argv)
    except Exception as exc:
        traceback.print_exc()
        raise SystemExit(
            f"WORKFLOW ABORTED at {label} ({module.__name__}): {type(exc).__name__}: {exc}\n"
            f"A partial workflow is not a complete one — nothing downstream was run."
        )
    if rc != 0:
        raise SystemExit(f"WORKFLOW ABORTED at {label} ({module.__name__}): exit code {rc}")

    created = [p for p in stage_dir.iterdir() if p.is_dir() and p.name not in before]
    if not created:
        raise SystemExit(f"WORKFLOW ABORTED at {label}: stage produced no output directory")
    return sorted(created)[-1]


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARIES  (read each stage's own artifacts — never re-derive)
# ─────────────────────────────────────────────────────────────────────────────
def summarize_survey(d: Path) -> dict[str, Any]:
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    return {
        "bars": man["corpus"]["bars"],
        "warmup_complete_bars": man["features"]["warmup_complete_bars"],
        "state_counts": man["states"]["state_after_counts"],
        "action_counts": man["states"]["action_counts"],
        "retests": man["states"]["action_counts"].get("RETEST_CONFIRMED", 0),
    }


def summarize_locate(d: Path) -> dict[str, Any]:
    rates = json.loads((d / "rates.json").read_text(encoding="utf-8"))
    funnel = pd.read_csv(d / "funnel.csv")
    rows = []
    for r in rates["rates"]:
        arm = r["arm"]
        g = funnel[funnel.arm == arm].set_index("stage_key")["count"].to_dict()
        rows.append({
            "arm": arm, "label": r["label"],
            "retests": r["retest_confirmed"]["count"],
            "reached_session": r["reached_session"],
            "session_passed": r["session_passed"],
            "trade_build_failed": int(g.get("trade_build_failed", 0)),
            "trades": r["trade_opened"]["count"],
            "days_between_trades": r["trade_opened"]["calendar_days_between"],
        })
    return {"arms": rows}


def summarize_prove(d: Path) -> dict[str, Any]:
    if not (d / "episodes.json").exists():
        return {"episodes": [], "parity": []}
    eps = json.loads((d / "episodes.json").read_text(encoding="utf-8"))["episodes"]
    parity = []
    for e in eps:
        g = (e.get("bars") or [{}])[-1].get("geometry") or {}
        if g.get("parity"):
            parity.append({
                "arm": e["arm"], "ts": e["terminal_ts"], "direction": e["direction"],
                "sl_engine": g["engine"]["sl"], "sl_trace": g["sl"],
                "delta_sl": g["parity"]["delta_sl"], "verdict": g["parity"]["verdict"],
            })
    return {
        "episodes": [{"arm": e["arm"], "ts": e["terminal_ts"], "direction": e["direction"],
                      "terminal": e["terminal_action"]} for e in eps],
        "parity": parity,
    }


# ─────────────────────────────────────────────────────────────────────────────
# INDEX
# ─────────────────────────────────────────────────────────────────────────────
def write_index(out_dir: Path, info: dict, stages: dict, summ: dict) -> None:
    L = [f"# CRT trace workflow — {info['instrument']}", ""]
    L.append(f"Generated {datetime.now(timezone.utc).isoformat()} · "
             f"active config `{info['active_version']}` · read-only")
    L.append("")

    L.append("## Preflight")
    L.append("")
    L.append(f"- corpus `{info['corpus']}` (sha256 `{info['corpus_sha256'][:12]}…`)")
    L.append(f"- **{info['bars']:,} bars**, {info['first_timestamp']} → {info['last_timestamp']} "
             f"(broker-server time, F-066)")
    L.append(f"- `allowed_sessions` = {info['allowed_sessions']}")
    L.append(f"- `session_windows` = {info['session_windows']}")
    L.append(f"- `sl_atr_buffer` = {info['sl_atr_buffer']} · "
             f"`body_ratio_min` = {info['body_ratio_min']}")
    if info["unmatchable_allowed_sessions"]:
        L.append(f"- ⚠ **dead tokens**: {info['unmatchable_allowed_sessions']} are in "
                 f"`allowed_sessions` but have no window — they can never match.")
    L.append(f"- {info['config_invariance_note']}")
    L.append("")

    s = summ["survey"]
    L.append("## [1/3] SURVEY — what happened")
    L.append("")
    L.append(f"{s['bars']:,} bars · {s['warmup_complete_bars']:,} warmup-complete · "
             f"**{s['retests']} RETEST_CONFIRMED**")
    L.append("")
    L.append(f"States: `{s['state_counts']}`")
    L.append("")
    L.append(f"Actions: `{s['action_counts']}`")
    L.append("")
    if s["retests"] == 0:
        L.append("> **No RETESTs in this corpus.** Stages 2 and 3 have nothing to explain — this "
                 "is a real finding about the window, not an error. Widen the corpus or pick a "
                 "different instrument.")
        L.append("")
    L.append(f"Artifacts: [`trace.csv`]({stages['survey']}/trace.csv) · "
             f"[`trace.jsonl`]({stages['survey']}/trace.jsonl) · "
             f"[`manifest.json`]({stages['survey']}/manifest.json)")
    L.append("")

    L.append("## [2/3] LOCATE — where it dies")
    L.append("")
    L.append("| arm | setup | RETESTs | reached session | passed | build failed | trades | days/trade |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in summ["locate"]["arms"]:
        L.append(f"| {r['arm']} | {r['label']} | {r['retests']} | {r['reached_session']} | "
                 f"{r['session_passed']} | {r['trade_build_failed']} | {r['trades']} | "
                 f"{r['days_between_trades'] or '—'} |")
    L.append("")
    L.append(f"Artifacts: [`funnel.csv`]({stages['locate']}/funnel.csv) · "
             f"[`rejections.csv`]({stages['locate']}/rejections.csv) · "
             f"[`hour_profile.csv`]({stages['locate']}/hour_profile.csv) · "
             f"[`events.csv`]({stages['locate']}/events.csv) · "
             f"[`summary.md`]({stages['locate']}/summary.md)")
    L.append("")

    p = summ["prove"]
    L.append("## [3/3] PROVE — exactly which numbers")
    L.append("")
    if not p["episodes"]:
        L.append("> No episodes reached a terminal decision worth proving.")
    else:
        L.append("| arm | timestamp | dir | terminal |")
        L.append("|---|---|---|---|")
        for e in p["episodes"]:
            L.append(f"| {e['arm']} | {e['ts']} | {e['direction']} | `{e['terminal']}` |")
        L.append("")
        if p["parity"]:
            L.append("**Engine-parity** (`DERIVED` vs `ENGINE`, never collapsed):")
            L.append("")
            L.append("| arm | timestamp | dir | sl_engine | sl_trace | \\|delta\\| | verdict |")
            L.append("|---|---|---|---|---|---|---|")
            for r in p["parity"]:
                L.append(f"| {r['arm']} | {r['ts']} | {r['direction']} | {r['sl_engine']} | "
                         f"{r['sl_trace']:.7f} | {r['delta_sl']:.3e} | **{r['verdict']}** |")
            L.append("")
    L.append(f"Artifacts: [`journeys.md`]({stages['prove']}/journeys.md) · "
             f"[`operands.csv`]({stages['prove']}/operands.csv) · "
             f"[`bars.csv`]({stages['prove']}/bars.csv) · "
             f"[`episodes.json`]({stages['prove']}/episodes.json)")
    L.append("")
    L.append("---")
    L.append("")
    L.append("> **Scope.** Descriptive. This workflow explains engine behavior and surfaces "
             "defects; it grants no authority to change the SL rule, the session windows, the "
             "RETEST acceptance rule, or any config. Anything here that warrants a behavior "
             "change is a separate, separately authorized decision.")
    L.append("")
    L.append("Method: [`CRT_TRACE_WORKFLOW.md`](../../../scripts/analysis/CRT_TRACE_WORKFLOW.md)")

    text = "\n".join(L)
    (out_dir / "INDEX.md").write_text(text, encoding="utf-8")

    # No dead links: every relative artifact path in the index must exist on disk.
    import re as _re
    missing = [
        m for m in _re.findall(r"\]\((stage_\d_[^)]+)\)", text)
        if not (out_dir / m).exists()
    ]
    if missing:
        raise SystemExit(f"INDEX.md references {len(missing)} missing artifact(s): {missing}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instrument", default=DEFAULT_INSTRUMENT)
    ap.add_argument("--corpus", type=Path, default=None,
                    help="CSV or XLSX; defaults to data/mt5/<INSTRUMENT>_M15.csv")
    ap.add_argument("--arms", default="A0,A1,A2,A3")
    ap.add_argument("--prove-arms", default="A0,A3",
                    help="arms to render episode proofs for (a subset of --arms)")
    ap.add_argument("--overlay", choices=("all", "events", "none"), default="events")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = ap.parse_args(argv or sys.argv[1:])

    instrument = args.instrument.upper()
    corpus = (args.corpus or (ROOT / "data" / "mt5" / f"{instrument}_M15.csv")).resolve()

    info = preflight(instrument, corpus)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / f"{instrument}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus_flag = "--xlsx" if corpus.suffix.lower() in (".xlsx", ".xlsm") else "--csv"

    d1 = run_stage("1/3 SURVEY", S1_SURVEY,
                   ["--instrument", instrument, corpus_flag, str(corpus),
                    "--overlay", args.overlay, "--output-dir", str(out_dir / "stage_1_survey")],
                   out_dir / "stage_1_survey")
    d2 = run_stage("2/3 LOCATE", S2_LOCATE,
                   ["--instrument", instrument, corpus_flag, str(corpus),
                    "--arms", args.arms, "--output-dir", str(out_dir / "stage_2_locate")],
                   out_dir / "stage_2_locate")
    d3 = run_stage("3/3 PROVE", S3_PROVE,
                   ["--instrument", instrument, corpus_flag, str(corpus),
                    "--arms", args.prove_arms, "--output-dir", str(out_dir / "stage_3_prove")],
                   out_dir / "stage_3_prove")

    stages = {
        "survey": f"stage_1_survey/{d1.name}",
        "locate": f"stage_2_locate/{d2.name}",
        "prove": f"stage_3_prove/{d3.name}",
    }
    summ = {"survey": summarize_survey(d1), "locate": summarize_locate(d2),
            "prove": summarize_prove(d3)}
    write_index(out_dir, info, stages, summ)

    with open(out_dir / "workflow.json", "w", encoding="utf-8") as fh:
        json.dump({"preflight": info, "stages": stages, "summary": summ}, fh,
                  indent=2, default=str)

    logger.info("workflow complete -> %s", out_dir.relative_to(ROOT))
    print()
    print(f"  instrument : {instrument}")
    print(f"  bars       : {summ['survey']['bars']:,}  RETESTs: {summ['survey']['retests']}")
    for r in summ["locate"]["arms"]:
        print(f"  {r['arm']:3} passed={r['session_passed']:<3} "
              f"build_failed={r['trade_build_failed']:<3} trades={r['trades']}")
    for r in summ["prove"]["parity"]:
        print(f"  parity {r['arm']} {r['ts']} |delta|={r['delta_sl']:.3e} {r['verdict']}")
    print(f"\n-> {(out_dir / 'INDEX.md').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
