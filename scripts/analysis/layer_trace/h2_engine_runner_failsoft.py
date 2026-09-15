"""h2_engine_runner_failsoft.py — H2: does EngineRunner ever error out and let the trade
through unvetoed, silently?

Plan reference: C:\\Users\\Hi\\.claude\\plans\\pure-conversation-share-only-rosy-parnas.md §4 H2.

CLAIM UNDER TEST
----------------
`runtime/backtest_v2.py`'s EngineRunner gate (source-verified, current line ~3169-3183) wraps the
whole gate call in `try/except Exception as _er_exc:` and, on ANY exception, only logs at DEBUG
and falls through — `_engine_vetoed` stays False, so `if not _p5_rejected and not _drift_vetoed and
not _engine_vetoed:` lets the trade through with no other record distinguishing "engine approved"
from "engine never ran". This could be part of the mechanism behind F-070's "0/30 vetoes on the
active config epoch".

KILL RULE
---------
Zero `layer="L5", status="EXCEPTION"` rows over the full corpus (hypothesis falsified for this
corpus — EngineRunner never actually throws here in practice, the fail-soft path is dead code on
this evidence, not a live risk).

METHOD
------
Runs a REAL backtest with `layer_trace.enabled=true` shimmed in-process (no config file touched —
`config_layer.production_config.get_prod_section` is monkeypatched for the single key
`"layer_trace"` only; every other section resolves through the real, unmodified loader). Then reads
the emitted `layer_trace` JSONL and counts `EXCEPTION` rows on L5, plus cross-tabulates L5 status
against whether a trade actually opened on the same `trace_id` (L8 presence) — an EXCEPTION row
that never blocked a trade is direct evidence for the claim above.

USAGE
-----
    venv/Scripts/python.exe scripts/analysis/layer_trace/h2_engine_runner_failsoft.py \\
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
    "output_dir": "results/layer_trace_h2",
    "filename_suffix": "_layer_trace.jsonl",
    "flush_every": 200,
}


def _shim_get_prod_section():
    """Monkeypatch ONLY the `layer_trace` key; every other section goes through the real,
    unmodified loader — this script must not change any other config-driven behaviour."""
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
        print(f"H2: ABORT — corpus not found at {args.csv}", file=sys.stderr)
        return 2

    import config_layer.production_config as prod_cfg

    real_get_prod_section = _shim_get_prod_section()
    out_dir = REPO_ROOT / "results" / "layer_trace_h2"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / f"{args.instrument}_layer_trace.jsonl"
    if trace_path.exists():
        trace_path.unlink()  # fresh run — this script's own scratch output only

    try:
        import runtime.backtest_v2 as bt2

        argv_backup = sys.argv[:]
        sys.argv = ["backtest_v2.py", "--csv", args.csv, "--instrument", args.instrument, "--output", args.output]
        try:
            bt2.main()
        finally:
            sys.argv = argv_backup
    finally:
        prod_cfg.get_prod_section = real_get_prod_section  # never leave the shim installed

    if not trace_path.exists():
        print(f"H2: INCONCLUSIVE — no layer_trace output at {trace_path} (emitter did not construct)", file=sys.stderr)
        return 3

    rows = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines()]
    l5_status_counts = Counter(r["status"] for r in rows if r["layer"] == "L5")
    exception_rows = [r for r in rows if r["layer"] == "L5" and r["status"] == "EXCEPTION"]
    trace_ids_with_trade = {r["trace_id"] for r in rows if r["layer"] == "L8"}

    exceptions_that_let_a_trade_through = [
        r for r in exception_rows if r["trace_id"] in trace_ids_with_trade
    ]

    verdict = {
        "hypothesis": "H2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "trace_path": str(trace_path),
        "total_l5_rows": sum(l5_status_counts.values()),
        "l5_status_counts": dict(l5_status_counts),
        "exception_count": len(exception_rows),
        "exceptions_that_coincide_with_a_trade": len(exceptions_that_let_a_trade_through),
        "sample_exception_notes": [r["note"] for r in exception_rows[:10]],
        "result": (
            "CONFIRMED_FAILSOFT_OBSERVED" if exception_rows else
            "FALSIFIED_NO_EXCEPTIONS_ON_THIS_CORPUS"
        ),
    }

    out_path = REPO_ROOT / "results" / f"h2_engine_runner_failsoft_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    print(f"H2 result: {verdict['result']}")
    print(f"  L5 status counts: {dict(l5_status_counts)}")
    print(f"  EXCEPTION rows: {len(exception_rows)} (of which {len(exceptions_that_let_a_trade_through)} coincide with a trade opening on the same bar)")
    print(f"  -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
