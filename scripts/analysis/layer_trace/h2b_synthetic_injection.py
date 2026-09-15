"""h2b_synthetic_injection.py — H2, mechanism proof: force EngineRunner to fail every time it is
called, and confirm the trade survives unvetoed regardless.

Plan reference: pure-conversation-share-only-rosy-parnas.md §4 H2 (follow-up to
h2_engine_runner_failsoft.py, which found the natural trial count on one XAUUSD run too small —
n=3 — to call a clean null; user-selected follow-up: synthetic exception injection).

WHY INJECTION, NOT MORE NATURAL DATA
--------------------------------------
The natural-frequency run (h2_engine_runner_failsoft.py) is gated by how often CRT commits a trade
(the EngineRunner gate only runs post-commit — confirmed by source read). Accumulating more natural
trials means more corpora/instruments, which measures FREQUENCY, not MECHANISM. This script instead
makes the exception happen on EVERY gate call (`core.engine_runner.EngineRunner.run` monkeypatched
to always raise), which proves the fail-soft branch's BEHAVIOUR directly and exhaustively for every
trial this run does have — independent of how rarely the gate fires in practice.

WHAT THIS PROVES (if it survives)
-----------------------------------
Two independent checks, both must hold:
  1. Every gate call this run makes produces `layer="L5", status="EXCEPTION"` in layer_trace
     (the fail-soft path was genuinely exercised, not skipped by some earlier condition).
  2. Not one of those trades was rejected with an `engine_runner:` reason in the real trade
     journal/events stream — i.e. `_engine_vetoed` really did stay False and the trade really did
     survive, at the OUTPUT the rest of the system consumes, not just at the layer_trace row.

METHOD
------
Monkeypatches `core.engine_runner.EngineRunner.run` at the CLASS level (affects every instance
created during this run, since `_engine_runner` is a fresh local each `BacktestRunner.run()` call)
to always raise. Runs a REAL backtest with `layer_trace` shimmed on (same technique as
h2_engine_runner_failsoft.py). Restores the original method in a `finally` block regardless of
outcome — this must never leave the class patched for any other code in the same process.

USAGE
-----
    venv/Scripts/python.exe scripts/analysis/layer_trace/h2b_synthetic_injection.py \\
        --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_LAYER_TRACE_SECTION = {
    "enabled": True,
    "schema_version": "1.0.0",
    "output_dir": "results/layer_trace_h2b",
    "filename_suffix": "_layer_trace.jsonl",
    "flush_every": 50,
}

_INJECTED_MESSAGE = "H2B_SYNTHETIC_INJECTED_FAILURE"


def _shim_get_prod_section():
    import config_layer.production_config as prod_cfg

    real = prod_cfg.get_prod_section

    def _patched(name, version=None):
        if name == "layer_trace":
            return dict(_LAYER_TRACE_SECTION)
        return real(name, version=version)

    prod_cfg.get_prod_section = _patched
    return real


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(REPO_ROOT / "data" / "mt5" / "XAUUSD_M15.csv"))
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--output", default="results")
    args = ap.parse_args()

    if not Path(args.csv).exists():
        print(f"H2B: ABORT — corpus not found at {args.csv}", file=sys.stderr)
        return 2

    import config_layer.production_config as prod_cfg
    from core.engine_runner import EngineRunner

    real_get_prod_section = _shim_get_prod_section()
    real_run = EngineRunner.run
    call_count = {"n": 0}

    def _always_raise(self, *a, **k):
        call_count["n"] += 1
        raise RuntimeError(_INJECTED_MESSAGE)

    out_dir = REPO_ROOT / "results" / "layer_trace_h2b"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / f"{args.instrument}_layer_trace.jsonl"
    if trace_path.exists():
        trace_path.unlink()

    try:
        EngineRunner.run = _always_raise
        import runtime.backtest_v2 as bt2

        argv_backup = sys.argv[:]
        sys.argv = ["backtest_v2.py", "--csv", args.csv, "--instrument", args.instrument, "--output", args.output]
        try:
            bt2.main()
        finally:
            sys.argv = argv_backup
    finally:
        EngineRunner.run = real_run  # NEVER leave the class patched
        prod_cfg.get_prod_section = real_get_prod_section

    if not trace_path.exists():
        print(f"H2B: INCONCLUSIVE — no layer_trace output at {trace_path}", file=sys.stderr)
        return 3

    rows = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines()]
    l5_rows = [r for r in rows if r["layer"] == "L5"]
    l5_status_counts = Counter(r["status"] for r in l5_rows)
    exception_rows = [r for r in l5_rows if r["status"] == "EXCEPTION"]
    l8_trace_ids = {r["trace_id"] for r in rows if r["layer"] == "L8"}

    # Check 2: no rejected-trade reason contains "engine_runner:" anywhere in this run's real
    # output (the events stream the rest of the system actually consumes, not layer_trace).
    result_dirs = sorted((REPO_ROOT / args.output).glob(f"run_*_{args.instrument}"), key=lambda p: p.stat().st_mtime)
    events_path = result_dirs[-1] / f"{args.instrument}_events.jsonl" if result_dirs else None
    engine_runner_rejects_in_real_output = 0
    if events_path and events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            reason = str(ev.get("reason") or ev.get("detail") or "")
            if "engine_runner:" in reason:
                engine_runner_rejects_in_real_output += 1

    mechanism_confirmed = (
        call_count["n"] > 0
        and len(exception_rows) == call_count["n"]
        and l5_status_counts.get("PASS", 0) == 0
        and l5_status_counts.get("REJECT", 0) == 0
        and engine_runner_rejects_in_real_output == 0
    )

    verdict = {
        "hypothesis": "H2B_synthetic_injection",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "trace_path": str(trace_path),
        "engine_runner_run_call_count": call_count["n"],
        "l5_status_counts": dict(l5_status_counts),
        "l8_trade_opened_count": len(l8_trace_ids),
        "events_path_checked": str(events_path) if events_path else None,
        "engine_runner_rejects_found_in_real_output": engine_runner_rejects_in_real_output,
        "result": "MECHANISM_CONFIRMED" if mechanism_confirmed else "MECHANISM_NOT_CONFIRMED_REVIEW_NEEDED",
        "interpretation": (
            "Every EngineRunner.run() call this run made raised (by injection); layer_trace "
            "recorded EXCEPTION for all of them (never PASS/REJECT); and zero rejections in the "
            "real events stream cite 'engine_runner:' — the trade(s) that reached this gate "
            "survived the always-failing gate exactly as the source read predicted."
            if mechanism_confirmed else
            "One or more checks did not match the predicted fail-soft behaviour — see the raw "
            "counts above; do not assume the mechanism without reviewing why."
        ),
    }

    out_path = REPO_ROOT / "results" / f"h2b_synthetic_injection_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    print(f"H2B result: {verdict['result']}")
    print(f"  EngineRunner.run() calls (all injected to raise): {call_count['n']}")
    print(f"  L5 status counts: {dict(l5_status_counts)}")
    print(f"  'engine_runner:' rejects found in real events stream: {engine_runner_rejects_in_real_output}")
    print(f"  -> {out_path}")
    return 0 if mechanism_confirmed else 1


if __name__ == "__main__":
    raise SystemExit(main())
