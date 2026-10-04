"""
funnel_diagnosis.py
===================
F-003 Phase A — CRT detection-funnel diagnosis (MEASURE-ONLY).

Counts per-stage forward conversions of the CRT state machine from a backtest's
`<INSTRUMENT>_events.jsonl` (STATE_TRANSITION events), to locate the binding
choke point on the CURRENT config BEFORE any threshold is touched.

Golden path: RANGE -> SWEEP -> DISPLACEMENT -> EXPANSION -> RETEST -> EXECUTION
-> RESOLUTION (+ SHADOW_PENDING and EXPIRED branches).

Reads only; writes a JSON summary to results/analysis/. No config change.

Usage:
  # 1) produce events (if not already present):
  python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/funnel
  # 2) diagnose:
  python scripts/analysis/funnel_diagnosis.py --events results/funnel/run_*/BNBUSDT_events.jsonl --instrument BNBUSDT
"""
from __future__ import annotations

import argparse
import json
import sys
import collections
from datetime import datetime, timezone
from pathlib import Path

CHAIN = ["RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION", "RESOLUTION"]


def diagnose(events_path: Path) -> dict:
    pairs = collections.Counter()
    ev_types = collections.Counter()
    reject_reasons = collections.Counter()
    n_trades = 0
    for line in events_path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        et = e.get("event")
        ev_types[et] += 1
        if et == "STATE_TRANSITION":
            pairs[(e.get("state_from"), e.get("state_to"))] += 1
        elif et == "TRADE_OPENED":
            n_trades += 1
        elif et == "FILTER_REJECTED":
            reject_reasons[e.get("reason", "?")] += 1

    funnel = []
    prev = None
    for i in range(len(CHAIN) - 1):
        a, b = CHAIN[i], CHAIN[i + 1]
        cnt = pairs[(a, b)]
        conv = round(cnt / prev * 100, 2) if prev else None
        funnel.append({"from": a, "to": b, "count": cnt, "conv_from_prev_pct": conv})
        prev = cnt
    # branch transitions of interest
    branches = {f"{a}->{b}": c for (a, b), c in pairs.items()
                if (a, b) not in {(CHAIN[i], CHAIN[i + 1]) for i in range(len(CHAIN) - 1)}}
    # binding stage = smallest conv_from_prev on the golden path
    staged = [f for f in funnel if f["conv_from_prev_pct"] is not None]
    binding = min(staged, key=lambda f: f["conv_from_prev_pct"]) if staged else None
    return {
        "schema": "funnel_diagnosis_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": str(events_path),
        "n_trades": n_trades,
        "golden_path_funnel": funnel,
        "binding_stage": binding,
        "branch_transitions": dict(sorted(branches.items(), key=lambda kv: -kv[1])),
        "event_type_counts": dict(ev_types.most_common()),
        "filter_reject_reasons": dict(reject_reasons.most_common()),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True, type=Path,
                    help="Path to <INSTRUMENT>_events.jsonl (glob ok via shell)")
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args(argv)

    d = diagnose(args.events)
    out = args.output or (Path("results/analysis") / f"funnel_{args.instrument}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, indent=2), encoding="utf-8")

    print(f"==== CRT FUNNEL — {args.instrument} (N_trades={d['n_trades']}) ====")
    for f in d["golden_path_funnel"]:
        conv = f"{f['conv_from_prev_pct']:6.2f}%" if f["conv_from_prev_pct"] is not None else "   -  "
        print(f"  {f['from']:>12} -> {f['to']:<12} {f['count']:>6}   conv={conv}")
    b = d["binding_stage"]
    if b:
        print(f"  BINDING STAGE: {b['from']}->{b['to']} at {b['conv_from_prev_pct']}%")
    print("  branches:", d["branch_transitions"])
    print(f"OUTPUT:funnel:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
