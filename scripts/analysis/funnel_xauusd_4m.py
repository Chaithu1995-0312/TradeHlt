# -*- coding: utf-8 -*-
"""Read-only stage funnel for the 4-month XAUUSD window search run."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

RUN = Path(
    "results/runtime_benchmarks/window_search_xauusd/"
    "trail_4m_gate0/run_20260720_022222_XAUUSD"
)
OUT = Path("results/runtime_benchmarks/window_search_xauusd/funnel_4m_gate0.json")


def main() -> None:
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
    summary = json.loads((RUN / "XAUUSD_summary.json").read_text(encoding="utf-8"))

    kinds = Counter()
    from_to = Counter()
    to_c = Counter()
    filter_reasons = Counter()
    for e in events:
        ev = e.get("event") or e.get("kind") or "UNKNOWN"
        kinds[ev] += 1
        if ev == "STATE_TRANSITION":
            fr, to = e.get("state_from"), e.get("state_to")
            from_to[f"{fr} -> {to}"] += 1
            to_c[str(to)] += 1
        if ev == "FILTER_REJECTED":
            filter_reasons[str(e.get("reason"))] += 1

    retests = [
        e
        for e in events
        if e.get("event") == "STATE_TRANSITION" and e.get("state_to") == "RETEST"
    ]
    dds = [e for e in tel if e.get("kind") == "DECISION_DISTANCE"]

    # Per-retest fate via candle_index proximity
    per_retest = []
    for r in retests:
        idx = r.get("candle_index")
        fate = []
        for e in events:
            ci = e.get("candle_index")
            if idx is None or ci is None:
                continue
            if 0 <= ci - idx <= 8:
                fate.append(
                    {
                        "timestamp": e.get("timestamp"),
                        "event": e.get("event"),
                        "state_from": e.get("state_from"),
                        "state_to": e.get("state_to"),
                        "reason": e.get("reason"),
                        "direction": e.get("direction"),
                    }
                )
        per_retest.append(
            {
                "retest_ts": r.get("timestamp"),
                "candle_index": idx,
                "reason": r.get("reason"),
                "nearby_events": fate,
            }
        )

    deaths = Counter()
    entered = Counter()
    lifecycle_reach = Counter()
    path_patterns = Counter()
    ages = []
    for e in tel:
        if e.get("kind") != "CANDIDATE_LIFECYCLE":
            continue
        deaths[str(e.get("death_reason"))] += 1
        ages.append(int(e.get("age_candles") or 0))
        st = list(e.get("entered_states") or [])
        path_patterns[tuple(st)] += 1
        for s in st:
            entered[s] += 1
        sset = set(st)
        for s in ("SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION"):
            if s in sset:
                lifecycle_reach[f"saw_{s}"] += 1

    reset_attr = Counter()
    for e in tel:
        if e.get("kind") == "RESET_ATTRIBUTED":
            reset_attr[
                str(
                    e.get("reason")
                    or e.get("reset_reason")
                    or e.get("cause")
                    or e.get("attribution")
                    or e.get("death_reason")
                    or "unknown"
                )
            ] += 1

    stages = [
        ("candles", summary.get("total_candles")),
        ("RANGE -> SWEEP", from_to.get("RANGE -> SWEEP", 0)),
        ("SWEEP entries (all paths)", to_c.get("SWEEP", 0)),
        ("SWEEP -> DISPLACEMENT", from_to.get("SWEEP -> DISPLACEMENT", 0)),
        ("SWEEP -> EXPANSION (direct)", from_to.get("SWEEP -> EXPANSION", 0)),
        ("RANGE -> SHADOW_PENDING", from_to.get("RANGE -> SHADOW_PENDING", 0)),
        ("SHADOW_PENDING -> SWEEP", from_to.get("SHADOW_PENDING -> SWEEP", 0)),
        ("DISPLACEMENT entries", to_c.get("DISPLACEMENT", 0)),
        ("DISPLACEMENT -> EXPANSION", from_to.get("DISPLACEMENT -> EXPANSION", 0)),
        ("EXPANSION entries", to_c.get("EXPANSION", 0)),
        ("EXPANSION -> RETEST", from_to.get("EXPANSION -> RETEST", 0)),
        ("RETEST entries", to_c.get("RETEST", 0)),
        (
            "DECISION_DISTANCE accepted",
            sum(1 for e in dds if e.get("accepted") is True),
        ),
        ("FILTER_REJECTED (session)", sum(filter_reasons.values())),
        ("RETEST -> EXECUTION", from_to.get("RETEST -> EXECUTION", 0)),
        ("TRADE_OPENED", kinds.get("TRADE_OPENED", 0)),
        ("TRADE_STOPPED", kinds.get("TRADE_STOPPED", 0)),
    ]

    # Conversion ratios relative to previous major stage
    def ratio(a, b):
        if not b:
            return None
        return round(a / b, 4)

    conv = {
        "sweep_per_candle": ratio(from_to.get("RANGE -> SWEEP", 0), summary.get("total_candles") or 0),
        "displacement_per_sweep_entry": ratio(
            from_to.get("SWEEP -> DISPLACEMENT", 0), to_c.get("SWEEP", 0)
        ),
        "expansion_per_displacement": ratio(
            from_to.get("DISPLACEMENT -> EXPANSION", 0)
            + from_to.get("SWEEP -> EXPANSION", 0),
            to_c.get("DISPLACEMENT", 0) + from_to.get("SWEEP -> EXPANSION", 0) or 1,
        ),
        "retest_per_expansion": ratio(
            from_to.get("EXPANSION -> RETEST", 0), to_c.get("EXPANSION", 0)
        ),
        "execution_per_retest": ratio(
            from_to.get("RETEST -> EXECUTION", 0), to_c.get("RETEST", 0)
        ),
        "trade_per_retest": ratio(kinds.get("TRADE_OPENED", 0), to_c.get("RETEST", 0)),
        "filter_reject_per_retest": ratio(
            sum(filter_reasons.values()), to_c.get("RETEST", 0)
        ),
    }

    report = {
        "scope": "READ_ONLY funnel; no behavioral changes",
        "window": {
            "csv": "data/XAUUSD_W2026-01-21-to-2026-05-21.csv",
            "months_trailing": 4,
            "rows": 7804,
            "first_ts": "2026-01-21 23:45:00",
            "last_ts": "2026-05-21 23:45:00",
            "run_dir": str(RUN).replace("\\", "/"),
            "gate": "BACKTEST_ENGINE_GATE=0",
            "config": "v2_multi_2026_04",
        },
        "summary_snapshot": {
            "total_candles": summary.get("total_candles"),
            "total_setups": summary.get("total_setups"),
            "approved_trades": summary.get("approved_trades"),
            "win_rate": summary.get("win_rate"),
            "avg_rr_net": summary.get("avg_rr_net"),
            "total_pnl_rr_net": summary.get("total_pnl_rr_net"),
            "state_distribution": summary.get("state_distribution"),
            "gap_resets": summary.get("gap_resets"),
        },
        "event_kinds": dict(kinds),
        "state_transitions": dict(from_to.most_common()),
        "to_state_entries": dict(to_c.most_common()),
        "stages": [{"stage": s, "count": n} for s, n in stages],
        "conversion_ratios": conv,
        "filter_reject_reasons": dict(filter_reasons),
        "decision_distance": dds,
        "per_retest_fate": per_retest,
        "candidate_lifecycle": {
            "n": sum(1 for e in tel if e.get("kind") == "CANDIDATE_LIFECYCLE"),
            "death_reasons": dict(deaths.most_common()),
            "entered_states": dict(entered),
            "lifecycle_reach": dict(lifecycle_reach),
            "path_patterns_top": [
                {"states": list(k), "count": v} for k, v in path_patterns.most_common(12)
            ],
            "age_candles_max": max(ages) if ages else None,
            "age_candles_median": sorted(ages)[len(ages) // 2] if ages else None,
        },
        "reset_attributed_top": dict(reset_attr.most_common(15)),
        "bottleneck_read": (
            "Primary choke is EXPANSION->RETEST (13 expansions, 3 retests) and then "
            "session filter (2/3 retests FILTER_REJECTED off_session). Only 1/3 retests "
            "reaches EXECUTION/TRADE. Upstream: SWEEP is abundant; DISPLACEMENT is rare "
            "relative to SWEEP (~9%). Scorer is NOT the killer on this window: all 3 "
            "DECISION_DISTANCE rows are APPROVED."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    # Human print
    print("=== 4-MONTH XAUUSD FUNNEL (gate OFF, read-only) ===")
    print(f"run: {RUN}")
    print(f"candles={summary.get('total_candles')} trades={summary.get('approved_trades')}")
    print()
    print(f"{'Stage':<40} {'Count':>8}")
    print("-" * 50)
    for s, n in stages:
        print(f"{s:<40} {n:>8}")
    print()
    print("Filter reasons:", dict(filter_reasons))
    print("Conversion:", json.dumps(conv, indent=2))
    print()
    print("Per-retest fate:")
    for pr in per_retest:
        print(f"  RETEST {pr['retest_ts']} idx={pr['candle_index']}")
        for ev in pr["nearby_events"]:
            if ev["event"] == "STATE_TRANSITION":
                print(
                    f"    {ev['timestamp']} {ev['state_from']}->{ev['state_to']} "
                    f"{(ev.get('reason') or '')[:50]}"
                )
            else:
                print(
                    f"    {ev['timestamp']} {ev['event']} "
                    f"{ev.get('reason') or ev.get('direction') or ''}"
                )
    print()
    print("DECISION_DISTANCE:")
    for e in dds:
        print(
            f"  cand={e.get('candidate_id')} score={e.get('score_actual'):.4f} "
            f"thr={e.get('score_threshold')} accepted={e.get('accepted')} "
            f"{e.get('rejection_reason')}"
        )
    print()
    print("Lifecycle deaths top:", deaths.most_common(8))
    print("BOTTLENECK:", report["bottleneck_read"])
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
