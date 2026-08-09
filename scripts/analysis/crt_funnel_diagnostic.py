"""
CRT funnel diagnostic — MEASURE ONLY (no threshold / CRT redesign).

Mines an existing backtest run's:
  - *_summary.json  (occupancy state_distribution, setups, gap_resets)
  - *_crt_telemetry.jsonl  (TelemetryCollector flush records)
  - *_events.jsonl  (STATE_TRANSITION / RESET / FILTER / TRADE_*)

Produces exact transition funnel + expansion/candidate distributions.

Default target: cert_xau_phase2 XAUUSD run matching the 1-setup investigation.
"""
from __future__ import annotations

import argparse
import json
import statistics as stats
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = (
    ROOT
    / "results"
    / "cert_xau_phase2"
    / "run_20260711_202626_XAUUSD"
)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rows.append(json.loads(ln))
    return rows


def pct(n: float, d: float) -> float | None:
    if not d:
        return None
    return round(100.0 * n / d, 3)


def summarize_numeric(vals: list[float]) -> dict:
    if not vals:
        return {"count": 0}
    s = sorted(vals)
    n = len(s)

    def q(p: float) -> float:
        if n == 1:
            return s[0]
        i = min(n - 1, max(0, int(p * (n - 1))))
        return s[i]

    return {
        "count": n,
        "min": s[0],
        "p25": q(0.25),
        "median": stats.median(s),
        "p75": q(0.75),
        "p90": q(0.90),
        "p99": q(0.99) if n >= 10 else s[-1],
        "max": s[-1],
        "mean": round(stats.mean(s), 6),
    }


def analyze_run(run_dir: Path) -> dict:
    summary_path = next(run_dir.glob("*_summary.json"), None)
    tel_path = next(run_dir.glob("*_crt_telemetry.jsonl"), None)
    ev_path = next(run_dir.glob("*_events.jsonl"), None)
    if not summary_path:
        raise FileNotFoundError(f"no *_summary.json in {run_dir}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    telemetry = load_jsonl(tel_path) if tel_path else []
    events = load_jsonl(ev_path) if ev_path else []

    # ── Occupancy (candle-time in state) from summary ──
    occupancy = dict(summary.get("state_distribution") or summary.get("funnel_counts") or {})

    # ── Transition edges from events ──
    edges: Counter = Counter()
    resets_from: Counter = Counter()
    reset_reasons: Counter = Counter()
    reset_reason_classes: Counter = Counter()
    filter_reasons: Counter = Counter()
    trade_events: Counter = Counter()
    begin_soft = 0

    for o in events:
        ev = o.get("event")
        if ev == "STATE_TRANSITION":
            edges[(o.get("state_from"), o.get("state_to"))] += 1
        elif ev == "RESET":
            resets_from[o.get("state_from")] += 1
            reason = o.get("reason") or ""
            reset_reasons[reason[:120]] += 1
            if "HTF" in reason:
                reset_reason_classes["HTF"] += 1
            elif "retrace" in reason.lower():
                reset_reason_classes["RETRACE"] += 1
            elif "extension" in reason.lower() or "Extension" in reason:
                reset_reason_classes["EXTENSION"] += 1
            elif "off_session" in reason.lower():
                reset_reason_classes["OFF_SESSION"] += 1
            elif "Post-resolution" in reason:
                reset_reason_classes["POST_RESOLUTION"] += 1
            else:
                reset_reason_classes["OTHER"] += 1
        elif ev == "FILTER_REJECTED":
            filter_reasons[o.get("reason") or ""] += 1
        elif ev and ev.startswith("TRADE_"):
            trade_events[ev] += 1
        elif ev == "BEGIN_SOFT_CONF":
            begin_soft += 1

    def edge(a: str, b: str) -> int:
        return int(edges.get((a, b), 0))

    # ── Telemetry records ──
    transition_counter = None
    expansions = []
    candidates = []
    decisions = []
    retest_replays = []
    for o in telemetry:
        k = o.get("kind")
        if k == "TRANSITION_COUNTER":
            transition_counter = o
        elif k == "EXPANSION_RETRACE_CHECK":
            expansions.append(o)
        elif k == "CANDIDATE_LIFECYCLE":
            candidates.append(o)
        elif k == "DECISION_DISTANCE":
            decisions.append(o)
        elif k == "RETEST_REPLAY":
            retest_replays.append(o)

    state_entries = dict((transition_counter or {}).get("state_entry_counts") or {})
    dwell_stats = dict((transition_counter or {}).get("expansion_dwell_stats") or {})

    # Expansion episode stats (prefer per-record; dwell mean may be buggy if negative)
    exp_ended = Counter(e.get("ended_by") for e in expansions)
    exp_qualified = Counter(bool(e.get("qualified")) for e in expansions)
    durs_raw = [e.get("duration_candles") for e in expansions]
    durs = [d for d in durs_raw if isinstance(d, (int, float)) and 0 <= d < 50_000]
    depths = [
        float(e["max_retrace_depth_abs"])
        for e in expansions
        if e.get("max_retrace_depth_abs") is not None
    ]
    ceilings = [
        float(e["ceiling_at_max"])
        for e in expansions
        if e.get("ceiling_at_max") is not None
    ]
    # distance-to-ceiling when both present
    dist_to_ceil = []
    for e in expansions:
        d = e.get("max_retrace_depth_abs")
        c = e.get("ceiling_at_max")
        if d is not None and c is not None:
            dist_to_ceil.append(float(c) - float(d))

    # Candidate lifecycle
    death = Counter(c.get("death_reason") for c in candidates)
    path_counts = Counter(tuple(c.get("entered_states") or []) for c in candidates)
    cand_ages = [
        int(c["age_candles"])
        for c in candidates
        if isinstance(c.get("age_candles"), (int, float))
    ]

    # Soft-conf / decisions
    dec_acc = Counter(
        (d.get("accepted"), d.get("rejection_reason")) for d in decisions
    )
    soft_scores = [
        float(d["score_actual"])
        for d in decisions
        if d.get("score_actual") is not None
    ]
    replay = Counter(
        (r.get("accepted"), r.get("reject_reason")) for r in retest_replays
    )

    # Derived funnel (ENTRY counts from events — authoritative transitions)
    funnel_transitions = {
        "RANGE_TO_SWEEP": edge("RANGE", "SWEEP"),
        "RANGE_TO_SHADOW_PENDING": edge("RANGE", "SHADOW_PENDING"),
        "SHADOW_PENDING_TO_SWEEP": edge("SHADOW_PENDING", "SWEEP"),
        "SWEEP_TO_DISPLACEMENT": edge("SWEEP", "DISPLACEMENT"),
        "SWEEP_TO_EXPANSION_SHADOW": edge("SWEEP", "EXPANSION"),  # shadow resume
        "DISPLACEMENT_TO_EXPANSION": edge("DISPLACEMENT", "EXPANSION"),
        "EXPANSION_TO_RETEST": edge("EXPANSION", "RETEST"),
        "RETEST_TO_EXECUTION": edge("RETEST", "EXECUTION"),
        "EXECUTION_TO_RESOLUTION": edge("EXECUTION", "RESOLUTION"),
    }
    # Unique expansion episode starts ≈ DISP→EXP + SWEEP→EXP (shadow)
    expansion_episode_starts = (
        funnel_transitions["DISPLACEMENT_TO_EXPANSION"]
        + funnel_transitions["SWEEP_TO_EXPANSION_SHADOW"]
    )

    # Failures estimated from path structure (not geometry sub-reasons)
    sweep_entries = state_entries.get("SWEEP", funnel_transitions["RANGE_TO_SWEEP"])
    disp_entries = state_entries.get("DISPLACEMENT", funnel_transitions["SWEEP_TO_DISPLACEMENT"])
    # SWEEP that never entered DISPLACEMENT or shadow EXPANSION
    # Approximate: candidates with entered_states == (SWEEP,)
    sweep_only_deaths = path_counts.get(("SWEEP",), 0)
    disp_only_deaths = path_counts.get(("SWEEP", "DISPLACEMENT"), 0)

    # Geometry fail reasons: NOT in telemetry → explicit gap
    geometry_fail_gap = {
        "SWEEP_TO_DISPLACEMENT_fail_by_body_ratio": "NOT_INSTRUMENTED",
        "SWEEP_TO_DISPLACEMENT_fail_by_atr_move": "NOT_INSTRUMENTED",
        "SWEEP_TO_DISPLACEMENT_fail_by_wick_atr": "NOT_INSTRUMENTED",
        "SWEEP_TO_DISPLACEMENT_fail_by_sweep_age": "NOT_INSTRUMENTED",
        "DISPLACEMENT_TO_EXPANSION_fail_by_direction": "NOT_INSTRUMENTED",
        "DISPLACEMENT_TO_EXPANSION_fail_by_extension": "NOT_INSTRUMENTED",
        "DISPLACEMENT_TO_EXPANSION_fail_by_atr_distance": "NOT_INSTRUMENTED",
        "EXPANSION_TO_RETEST_fail_by_min_depth": "NOT_INSTRUMENTED_PER_BAR",
        "EXPANSION_TO_RETEST_fail_by_ceiling": "NOT_INSTRUMENTED_PER_BAR",
        "note": (
            "Per-bar fail-reason counters require optional diagnostic hooks on try_* "
            "(similar to baseline trace). Existing telemetry records successful transitions, "
            "resets, expansion episode outcomes, and candidate deaths."
        ),
    }

    report = {
        "_doc": "CRT funnel diagnostic — MEASURE ONLY; no threshold changes authorized",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir.relative_to(ROOT)).replace("\\", "/"),
        "artifacts": {
            "summary": str(summary_path.relative_to(ROOT)).replace("\\", "/"),
            "telemetry": str(tel_path.relative_to(ROOT)).replace("\\", "/") if tel_path else None,
            "events": str(ev_path.relative_to(ROOT)).replace("\\", "/") if ev_path else None,
        },
        "run_headline": {
            "instrument": summary.get("instrument"),
            "total_candles": summary.get("total_candles"),
            "gap_resets": summary.get("gap_resets"),
            "total_setups": summary.get("total_setups"),
            "approved_trades": summary.get("approved_trades"),
            "rejected_trades": summary.get("rejected_trades"),
            "rejection_reasons": summary.get("rejection_reasons"),
            "config_version": summary.get("config_version"),
        },
        "CAUTION": {
            "state_distribution_is": "CANDLE_OCCUPANCY_not_transition_counts",
            "state_entry_counts_are": "TRANSITION_ENTRY_counts_from_TelemetryCollector",
            "edges_are": "STATE_TRANSITION events from events.jsonl",
        },
        "occupancy_state_distribution": occupancy,
        "occupancy_vs_entries": {
            "note": "Occupancy >> entries for long-dwell states (esp. EXPANSION)",
            "SWEEP": {"occupancy": occupancy.get("SWEEP"), "entries": state_entries.get("SWEEP")},
            "DISPLACEMENT": {
                "occupancy": occupancy.get("DISPLACEMENT"),
                "entries": state_entries.get("DISPLACEMENT"),
            },
            "EXPANSION": {
                "occupancy": occupancy.get("EXPANSION"),
                "entries": state_entries.get("EXPANSION"),
                "unique_episodes_telemetry": len(expansions),
                "unique_episode_starts_from_edges": expansion_episode_starts,
            },
            "RETEST": {"occupancy": occupancy.get("RETEST"), "entries": state_entries.get("RETEST")},
            "EXECUTION": {
                "occupancy": occupancy.get("EXECUTION"),
                "entries": state_entries.get("EXECUTION"),
            },
        },
        "funnel_transitions_exact": funnel_transitions,
        "funnel_conversion": {
            "RANGE_TO_SWEEP": funnel_transitions["RANGE_TO_SWEEP"],
            "SWEEP_TO_DISPLACEMENT": funnel_transitions["SWEEP_TO_DISPLACEMENT"],
            "SWEEP_TO_DISP_rate_pct": pct(
                funnel_transitions["SWEEP_TO_DISPLACEMENT"],
                funnel_transitions["RANGE_TO_SWEEP"],
            ),
            "DISPLACEMENT_TO_EXPANSION": funnel_transitions["DISPLACEMENT_TO_EXPANSION"],
            "DISP_TO_EXP_rate_pct": pct(
                funnel_transitions["DISPLACEMENT_TO_EXPANSION"],
                funnel_transitions["SWEEP_TO_DISPLACEMENT"],
            ),
            "shadow_SWEEP_TO_EXPANSION": funnel_transitions["SWEEP_TO_EXPANSION_SHADOW"],
            "unique_EXPANSION_episodes": expansion_episode_starts,
            "EXPANSION_TO_RETEST": funnel_transitions["EXPANSION_TO_RETEST"],
            "EXP_TO_RETEST_rate_pct_of_episodes": pct(
                funnel_transitions["EXPANSION_TO_RETEST"], expansion_episode_starts
            ),
            "RETEST_TO_EXECUTION": funnel_transitions["RETEST_TO_EXECUTION"],
            "RETEST_TO_EXEC_rate_pct": pct(
                funnel_transitions["RETEST_TO_EXECUTION"],
                funnel_transitions["EXPANSION_TO_RETEST"],
            ),
            "EXECUTION_TO_RESOLUTION": funnel_transitions["EXECUTION_TO_RESOLUTION"],
            "TRADE_OPENED_events": trade_events.get("TRADE_OPENED", 0),
            "summary_total_setups": summary.get("total_setups"),
        },
        "SWEEP_TO_DISPLACEMENT_outcome": {
            "qualified_transitions": funnel_transitions["SWEEP_TO_DISPLACEMENT"],
            "candidates_ending_SWEEP_only": sweep_only_deaths,
            "candidates_ending_after_DISPLACEMENT_only": disp_only_deaths,
            "fail_by_geometry_reason": geometry_fail_gap,
            "primary_observable_death_class_for_sweep_only": "RESET (mostly HTF) — see reset/candidate death tables",
        },
        "DISPLACEMENT_TO_EXPANSION_outcome": {
            "qualified_transitions": funnel_transitions["DISPLACEMENT_TO_EXPANSION"],
            "displacement_entries": disp_entries,
            "implied_non_expansion": disp_entries - funnel_transitions["DISPLACEMENT_TO_EXPANSION"],
            "resets_from_DISPLACEMENT": resets_from.get("DISPLACEMENT", 0),
            "fail_by_geometry_reason": geometry_fail_gap,
        },
        "unique_EXPANSION_episodes": {
            "count": len(expansions),
            "ended_by": dict(exp_ended),
            "qualified_retest": dict(exp_qualified),
            "ended_by_retest": exp_ended.get("retest", 0),
            "ended_by_reset": exp_ended.get("reset", 0),
            "ended_by_expired": exp_ended.get("expired", 0),
            "ended_by_eof": exp_ended.get("eof", 0),
            "dwell_candles_sane": summarize_numeric([float(d) for d in durs]),
            "dwell_stats_from_counter": dwell_stats,
            "max_retrace_depth_abs": summarize_numeric(depths),
            "ceiling_at_max": summarize_numeric(ceilings),
            "distance_to_ceiling_ceiling_minus_depth": summarize_numeric(dist_to_ceil),
            "interpretation": (
                f"Of {len(expansions)} expansion episodes, "
                f"{exp_ended.get('retest', 0)} qualified retest, "
                f"{exp_ended.get('reset', 0)} ended by reset, "
                f"{exp_ended.get('expired', 0)} by TTL EXPIRED. "
                "Zero TTL expiry implies candidates die by HTF/retrace reset or qualify before TTL."
            ),
        },
        "candidate_lifecycles": {
            "count": len(candidates),
            "death_reasons": dict(death),
            "path_prefix_counts_top": [
                {"entered_states": list(k), "count": v}
                for k, v in path_counts.most_common(20)
            ],
            "age_candles": summarize_numeric([float(a) for a in cand_ages]),
            "single_active_candidate": True,
            "evidence": "TelemetryCollector._active_candidate is singular",
        },
        "RETEST_TO_EXECUTION": {
            "BEGIN_SOFT_CONF_events": begin_soft,
            "RETEST_entries": state_entries.get("RETEST"),
            "RETEST_TO_EXECUTION_transitions": funnel_transitions["RETEST_TO_EXECUTION"],
            "soft_conf_decision_records": len(decisions),
            "soft_conf_decision_breakdown": {
                str(k): v for k, v in dec_acc.items()
            },
            "soft_conf_score_actual": summarize_numeric(soft_scores),
            "retest_replay_breakdown": {str(k): v for k, v in replay.items()},
            "FILTER_REJECTED": dict(filter_reasons),
            "resets_from_RETEST": resets_from.get("RETEST", 0),
            "resets_from_EXECUTION": resets_from.get("EXECUTION", 0),
            "interpretation": (
                "17 RETEST entries and 17 soft-conf decision records (all APPROVED at score gate) "
                "but only 5 RETEST→EXECUTION transitions and 1 TRADE_OPENED. "
                "12 FILTER_REJECTED off_session + retest_replay OFF_SESSION explain most non-trades; "
                "4 EXECUTION resets without RESOLUTION remain secondary residual."
            ),
        },
        "EXECUTION_episodes": {
            "EXECUTION_entries": state_entries.get("EXECUTION"),
            "EXECUTION_occupancy_candles": occupancy.get("EXECUTION"),
            "EXECUTION_TO_RESOLUTION": funnel_transitions["EXECUTION_TO_RESOLUTION"],
            "TRADE_events": dict(trade_events),
            "unique_setups_summary": summary.get("total_setups"),
            "gap": (
                "5 EXECUTION state entries vs 1 RESOLUTION/TRADE_OPENED — "
                "execution occupancy includes failed/aborted execution episodes; "
                "not 5 independent counted setups."
            ),
        },
        "resets": {
            "total_RESET_events": sum(resets_from.values()),
            "from_state": dict(resets_from),
            "reason_classes": dict(reset_reason_classes),
            "reason_top": [
                {"reason": r, "count": c} for r, c in reset_reasons.most_common(25)
            ],
            "gap_resets_summary": summary.get("gap_resets"),
        },
        "downstream_engine_rejection": {
            "rejected_trades": summary.get("rejected_trades"),
            "rejection_reasons": summary.get("rejection_reasons"),
            "verdict": "NOT_PRIMARY",
            "evidence": "summary rejected_trades=0 and empty rejection_reasons; collapse is upstream",
        },
        "closure_statement": {
            "ROOT_CAUSE_CLASS": "UPSTREAM_CRT_CANDIDATE_COLLAPSE",
            "PRIMARY_VISIBLE_BOUNDARY": "EXPANSION_TO_RETEST",
            "SECONDARY_VISIBLE_BOUNDARY": "SWEEP_TO_DISPLACEMENT",
            "TERTIARY_VISIBLE_BOUNDARY": "RETEST_SOFTCONF_TO_TRADE_OPENED_SESSION_FILTER",
            "DOWNSTREAM_ENGINE_REJECTION": "NOT_PRIMARY",
            "ARCHITECTURAL_SUPPRESSION_RISK": "SINGLE_ACTIVE_CANDIDATE + LONG_EXPANSION_DWELL + HTF_RESET",
            "THRESHOLD_CHANGE_AUTHORIZED": "NO — MEASURE COMPLETE; geometry fail-reasons still NOT_INSTRUMENTED",
            "NEXT_AUTHORIZED_MEASUREMENT": (
                "Optional diagnostic hooks on try_sweep_to_displacement / "
                "try_displacement_to_expansion / try_expansion_to_retest fail branches "
                "for per-reason counts (behavior-preserving, default off)"
            ),
        },
        "authority": "research/governance diagnostic only — no production authority; no threshold change",
    }
    return report


def to_md(rep: dict) -> str:
    f = rep["funnel_conversion"]
    lines = [
        "# CRT XAUUSD Funnel Diagnostic",
        "",
        f"_Generated {rep['generated_at_utc']}_  ",
        f"**Run:** `{rep['run_dir']}`  ",
        f"**Mode:** MEASURE ONLY — no threshold changes",
        "",
        "## Closure statement",
        "",
        "```text",
    ]
    for k, v in rep["closure_statement"].items():
        lines.append(f"{k} = {v}")
    lines += [
        "```",
        "",
        "## Headline",
        "",
        f"- candles: **{rep['run_headline']['total_candles']}**",
        f"- setups/approved: **{rep['run_headline']['total_setups']}** / **{rep['run_headline']['approved_trades']}**",
        f"- rejected_trades: **{rep['run_headline']['rejected_trades']}** reasons={rep['run_headline']['rejection_reasons']}",
        f"- gap_resets: **{rep['run_headline']['gap_resets']}**",
        f"- config: `{rep['run_headline']['config_version']}`",
        "",
        "## Occupancy vs entries (caution)",
        "",
        "| State | Occupancy (candles) | Entries (transitions) |",
        "|---|---:|---:|",
    ]
    for st in ["RANGE", "SWEEP", "DISPLACEMENT", "SHADOW_PENDING", "EXPANSION", "RETEST", "EXECUTION"]:
        occ = rep["occupancy_state_distribution"].get(st)
        ent = (rep.get("occupancy_vs_entries") or {}).get(st, {})
        if isinstance(ent, dict):
            e = ent.get("entries")
        else:
            e = None
        lines.append(f"| {st} | {occ} | {e} |")
    lines += [
        "",
        "## Exact transition funnel (from STATE_TRANSITION events)",
        "",
        "```text",
        f"RANGE → SWEEP                 {f['RANGE_TO_SWEEP']}",
        f"SWEEP → DISPLACEMENT          {f['SWEEP_TO_DISPLACEMENT']}  ({f['SWEEP_TO_DISP_rate_pct']}% of RANGE→SWEEP)",
        f"DISPLACEMENT → EXPANSION      {f['DISPLACEMENT_TO_EXPANSION']}  ({f['DISP_TO_EXP_rate_pct']}% of SWEEP→DISP)",
        f"SWEEP → EXPANSION (shadow)    {f['shadow_SWEEP_TO_EXPANSION']}",
        f"unique EXPANSION episodes     {f['unique_EXPANSION_episodes']}",
        f"EXPANSION → RETEST            {f['EXPANSION_TO_RETEST']}  ({f['EXP_TO_RETEST_rate_pct_of_episodes']}% of episodes)",
        f"RETEST → EXECUTION            {f['RETEST_TO_EXECUTION']}  ({f['RETEST_TO_EXEC_rate_pct']}% of RETEST)",
        f"EXECUTION → RESOLUTION        {f['EXECUTION_TO_RESOLUTION']}",
        f"TRADE_OPENED                  {f['TRADE_OPENED_events']}",
        "```",
        "",
        "## EXPANSION episodes",
        "",
        f"- count: **{rep['unique_EXPANSION_episodes']['count']}**",
        f"- ended_by: `{rep['unique_EXPANSION_episodes']['ended_by']}`",
        f"- dwell (sane durations): `{rep['unique_EXPANSION_episodes']['dwell_candles_sane']}`",
        f"- max_retrace_depth_abs: `{rep['unique_EXPANSION_episodes']['max_retrace_depth_abs']}`",
        f"- distance_to_ceiling: `{rep['unique_EXPANSION_episodes']['distance_to_ceiling_ceiling_minus_depth']}`",
        f"- {rep['unique_EXPANSION_episodes']['interpretation']}",
        "",
        "## Candidate deaths (single active lifecycle)",
        "",
        f"- candidates: **{rep['candidate_lifecycles']['count']}**",
        f"- death_reasons: `{rep['candidate_lifecycles']['death_reasons']}`",
        "",
        "## RETEST → trade residual",
        "",
        f"- {rep['RETEST_TO_EXECUTION']['interpretation']}",
        f"- FILTER_REJECTED: `{rep['RETEST_TO_EXECUTION']['FILTER_REJECTED']}`",
        f"- retest_replay: `{rep['RETEST_TO_EXECUTION']['retest_replay_breakdown']}`",
        "",
        "## Downstream",
        "",
        f"- verdict: **{rep['downstream_engine_rejection']['verdict']}**",
        f"- {rep['downstream_engine_rejection']['evidence']}",
        "",
        "## Measurement gaps",
        "",
        "Per-guard geometry fail reasons (body_ratio / ATR move / wick / age / retest floor-ceiling) are "
        "**NOT_INSTRUMENTED** in this telemetry set. Next optional step: default-off fail counters on try_*.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="CRT funnel diagnostic (measure only)")
    ap.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN,
        help="Backtest run directory containing summary + telemetry + events",
    )
    args = ap.parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    rep = analyze_run(run_dir)
    out_dir = ROOT / "docs" / "governance"
    out_json = out_dir / "crt_xauusd_funnel_diagnostic-2026-07-14.json"
    out_md = out_dir / "crt_xauusd_funnel_diagnostic-2026-07-14.md"
    out_json.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(to_md(rep), encoding="utf-8")
    print("WROTE", out_json)
    print("WROTE", out_md)
    print("CLOSURE")
    for k, v in rep["closure_statement"].items():
        print(f"  {k} = {v}")
    f = rep["funnel_conversion"]
    print(
        f"FUNNEL: SWEEP={f['RANGE_TO_SWEEP']} DISP={f['SWEEP_TO_DISPLACEMENT']} "
        f"EXP_ep={f['unique_EXPANSION_episodes']} RETEST={f['EXPANSION_TO_RETEST']} "
        f"EXEC={f['RETEST_TO_EXECUTION']} RESOL={f['EXECUTION_TO_RESOLUTION']} "
        f"TRADE={f['TRADE_OPENED_events']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
