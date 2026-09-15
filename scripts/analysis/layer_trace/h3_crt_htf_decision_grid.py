"""h3_crt_htf_decision_grid.py — H3: does the CRT<->HTF relationship look different once you
count DECISIONS instead of bars?

Plan reference: pure-conversation-share-only-rosy-parnas.md §4 H3, §8 decisions ("CRT -> HTF
stays H3. Not built. Wire it only if H3 produces evidence that justifies the complexity").

WHY DECISIONS, NOT BAR OCCUPANCY
-----------------------------------
This repo's own established rule (confirmed independently 4 times, per session memory): state
research must start at entry DECISIONS, never OCCUPANCY (bar counts) — e.g. F-069's 671-bar
EXPANSION dwell is really ~3 episodes, not 671 independent observations. A CRT-state x HTF-state
occupancy table over 47,275 bars would grossly overstate how much is actually KNOWN about the
joint distribution at decision time. This script tabulates only at TRADE_OPENED (L8) events.

METHOD
------
Reads the layer_trace JSONL from a real run (reuses `results/layer_trace_h2/XAUUSD_layer_trace.jsonl`
if present from an earlier H2 run over the same corpus+config; runs a fresh shimmed backtest
otherwise — same technique as h2_engine_runner_failsoft.py). For every `trace_id` that has an L8
(TRADE_OPENED) row, joins back to that SAME trace_id's L3 (CRT state, `output_hash`) and L4 (HTF
state, parsed from the `note` field's `htf_state=X`) rows, and cross-tabulates.

WHAT THIS DOES NOT DO
------------------------
It does NOT wire CRT<->HTF together, and does NOT compute a bidirectional coupling — per plan §8
that stays a hypothesis, not an architecture change. This is a descriptive cross-tab only.

KILL RULE / POWER CAVEAT
--------------------------
This repo's own Epistemic Integrity ritual Q2 ("Could INSUFFICIENT explain the observation?")
applies directly: on a corpus with only 3 trade-commit events (the SAME n that underpowered H2),
any cross-tab here is INSUFFICIENT_POWER by construction, not evidence either way. The script
reports the cross-tab honestly as INSUFFICIENT_POWER when n < 30 (this repo's own established
`min_cell_samples` floor, e.g. F-030/F-043's pre-registrations), never a false CONFIRMED/FALSIFIED.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_HTF_STATE_RE = re.compile(r"htf_state=(\S+)")
_MIN_CELL_SAMPLES = 30  # this repo's own established floor (F-030/F-043 pre-registrations)

_LAYER_TRACE_SECTION = {
    "enabled": True,
    "schema_version": "1.0.0",
    "output_dir": "results/layer_trace_h3",
    "filename_suffix": "_layer_trace.jsonl",
    "flush_every": 200,
}


def _run_fresh(csv: str, instrument: str, output: str) -> Path:
    import config_layer.production_config as prod_cfg

    real = prod_cfg.get_prod_section

    def _patched(name, version=None):
        if name == "layer_trace":
            return dict(_LAYER_TRACE_SECTION)
        return real(name, version=version)

    prod_cfg.get_prod_section = _patched
    out_dir = REPO_ROOT / "results" / "layer_trace_h3"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / f"{instrument}_layer_trace.jsonl"
    if trace_path.exists():
        trace_path.unlink()
    try:
        import runtime.backtest_v2 as bt2

        argv_backup = sys.argv[:]
        sys.argv = ["backtest_v2.py", "--csv", csv, "--instrument", instrument, "--output", output]
        try:
            bt2.main()
        finally:
            sys.argv = argv_backup
    finally:
        prod_cfg.get_prod_section = real
    return trace_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(REPO_ROOT / "data" / "mt5" / "XAUUSD_M15.csv"))
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--output", default="results")
    ap.add_argument("--reuse", default=str(REPO_ROOT / "results" / "layer_trace_h2" / "XAUUSD_layer_trace.jsonl"))
    args = ap.parse_args()

    reuse_path = Path(args.reuse)
    if reuse_path.exists():
        trace_path = reuse_path
        print(f"H3: reusing existing layer_trace output at {trace_path}")
    else:
        if not Path(args.csv).exists():
            print(f"H3: ABORT — corpus not found at {args.csv}", file=sys.stderr)
            return 2
        trace_path = _run_fresh(args.csv, args.instrument, args.output)

    if not trace_path.exists():
        print(f"H3: INCONCLUSIVE — no layer_trace output at {trace_path}", file=sys.stderr)
        return 3

    rows = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines()]
    by_trace_layer: dict = defaultdict(dict)
    for r in rows:
        by_trace_layer[r["trace_id"]][r["layer"]] = r

    decision_trace_ids = [tid for tid, layers in by_trace_layer.items() if "L8" in layers]

    grid: Counter = Counter()
    unresolved = []
    for tid in decision_trace_ids:
        layers = by_trace_layer[tid]
        crt_state = layers.get("L3", {}).get("output_hash")
        l4_note = layers.get("L4", {}).get("note") or ""
        m = _HTF_STATE_RE.search(l4_note)
        htf_state = m.group(1) if m else ("NO_PARENT_FEED" if "parent_crt.enabled=false" in l4_note else "UNKNOWN")
        if crt_state is None:
            unresolved.append(tid)
            continue
        grid[(crt_state, htf_state)] += 1

    total_decisions = len(decision_trace_ids)
    insufficient_power = total_decisions < _MIN_CELL_SAMPLES

    verdict = {
        "hypothesis": "H3",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "trace_path": str(trace_path),
        "total_decisions_n": total_decisions,
        "min_cell_samples_floor": _MIN_CELL_SAMPLES,
        "grid": {f"{crt}|{htf}": n for (crt, htf), n in grid.items()},
        "unresolved_decisions": unresolved,
        "result": "INSUFFICIENT_POWER" if insufficient_power else "MEASURED_SEE_GRID",
        "interpretation": (
            f"Only {total_decisions} decision(s) on this corpus, below the "
            f"min_cell_samples={_MIN_CELL_SAMPLES} floor this repo's own pre-registrations use "
            "(F-030/F-043). This does NOT confirm or falsify a CRT<->HTF interaction — it is a "
            "descriptive grid at n too small to say anything about the joint distribution. Per "
            "plan §8, CRT->HTF wiring stays unbuilt regardless of this result; a real H3 answer "
            "needs either a multi-instrument/multi-year pooled decision set, or a much longer "
            "single-instrument corpus, before min_cell_samples is reachable."
            if insufficient_power else
            "n clears the floor — see grid for the cross-tab."
        ),
    }

    out_path = REPO_ROOT / "results" / f"h3_crt_htf_decision_grid_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    print(f"H3 result: {verdict['result']}")
    print(f"  total decisions (n): {total_decisions} (floor: {_MIN_CELL_SAMPLES})")
    print(f"  grid: {dict(grid)}")
    print(f"  -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
