"""h1_run_identity.py — H1: does one backtest run mint one run id, or several?

Plan reference: C:\\Users\\Hi\\.claude\\plans\\pure-conversation-share-only-rosy-parnas.md §4 H1.

CLAIM UNDER TEST
----------------
A single `runtime.backtest_v2.BacktestRunner` run mints THREE independently-computed identifiers,
none passed to the other two:

  1. `utils.logging_config.RUN_ID` — naive local time, computed at MODULE IMPORT time
     (`datetime.now().strftime("%Y%m%d_%H%M%S")`), names `logs/run_<A>/<INSTRUMENT>/`.
  2. The per-run config-dump id — UTC (`datetime.now(timezone.utc)`), minted later inside
     `BacktestRunner.__init__` (`backtest_v2.py`, "Per-run config dump" block), names
     `logs/config_dumps/<INSTRUMENT>_run_<B>_config.json`.
  3. `runtime.backtest_v2.ReportWriter.run_id` — naive local time, self-generated because the
     caller (`BacktestRunner.run()`) constructs `ReportWriter(output_dir, instrument)` WITHOUT
     passing a `run_id`, minted even later, names `results/<C>_<INSTRUMENT>/`.

KILL RULE
---------
All three ids are equal (this hypothesis is FALSIFIED — treat as a documentation-only finding,
not an architecture fix).

METHOD
------
Read-only observation of a REAL run's own filesystem output. Does not parse source — the
run itself is the evidence. Snapshots `logs/` and `results/` before invoking
`runtime.backtest_v2.main()` in-process (so this script's own process owns the one run being
measured — no ambiguity from concurrent sessions per CLAUDE.md's concurrent-session guidance),
diffs the directory listings afterward, and extracts each id from the new paths' own names.

USAGE
-----
    venv/Scripts/python.exe scripts/analysis/layer_trace/h1_run_identity.py \\
        --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD

Writes a JSON verdict to `results/h1_run_identity_<timestamp>.json` and prints a summary.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LOGS_DIR = REPO_ROOT / "logs"
RESULTS_DIR = REPO_ROOT / "results"
CONFIG_DUMPS_DIR = LOGS_DIR / "config_dumps"

_RUN_DIR_RE = re.compile(r"^run_(\d{8}_\d{6})$")
_RESULT_DIR_RE = re.compile(r"^run_(\d{8}_\d{6})_(.+)$")
_CONFIG_DUMP_RE = re.compile(r"^(.+)_run_(\d{8}_\d{6})_config\.json$")


def _snapshot() -> dict:
    return {
        "log_run_dirs": {p.name for p in LOGS_DIR.glob("run_*") if p.is_dir()} if LOGS_DIR.exists() else set(),
        "result_dirs": {p.name for p in RESULTS_DIR.glob("run_*") if p.is_dir()} if RESULTS_DIR.exists() else set(),
        "config_dumps": {p.name for p in CONFIG_DUMPS_DIR.glob("*_config.json")} if CONFIG_DUMPS_DIR.exists() else set(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(REPO_ROOT / "data" / "mt5" / "XAUUSD_M15.csv"))
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--output", default="results")
    args = ap.parse_args()

    if not Path(args.csv).exists():
        print(f"H1: ABORT — corpus not found at {args.csv}", file=sys.stderr)
        return 2

    before = _snapshot()

    # Run a real backtest in-process, exactly the CLAUDE.md §1.5 documented invocation, so the
    # three ids this script measures are minted by a real production code path, not a mock.
    import runtime.backtest_v2 as bt2

    argv_backup = sys.argv[:]
    sys.argv = ["backtest_v2.py", "--csv", args.csv, "--instrument", args.instrument, "--output", args.output]
    try:
        bt2.main()
    finally:
        sys.argv = argv_backup

    after = _snapshot()

    new_log_dirs = after["log_run_dirs"] - before["log_run_dirs"]
    new_result_dirs = after["result_dirs"] - before["result_dirs"]
    new_config_dumps = after["config_dumps"] - before["config_dumps"]

    id_a = None
    if new_log_dirs:
        m = _RUN_DIR_RE.match(sorted(new_log_dirs)[-1])
        id_a = m.group(1) if m else None

    id_c = None
    result_dir_name = None
    for name in new_result_dirs:
        m = _RESULT_DIR_RE.match(name)
        if m and m.group(2) == args.instrument:
            id_c = m.group(1)
            result_dir_name = name
            break

    id_b = None
    config_dump_name = None
    for name in new_config_dumps:
        m = _CONFIG_DUMP_RE.match(name)
        if m and m.group(1) == args.instrument:
            id_b = m.group(2)
            config_dump_name = name
            break

    ids = {"A_logging_config_RUN_ID": id_a, "B_config_dump_run_id": id_b, "C_report_writer_run_id": id_c}
    observed = {k: v for k, v in ids.items() if v is not None}
    distinct = set(observed.values())

    verdict = {
        "hypothesis": "H1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "csv": args.csv,
        "ids": ids,
        "distinct_id_count": len(distinct),
        "ids_observed_count": len(observed),
        "result": "CONFIRMED_SINGLE_RUN_ID" if len(distinct) <= 1 and len(observed) >= 2 else
                   ("SPLIT_RUN_IDENTITY" if len(distinct) > 1 else "INCONCLUSIVE_INSUFFICIENT_ARTIFACTS"),
        "new_log_dirs": sorted(new_log_dirs),
        "new_result_dirs": sorted(new_result_dirs),
        "new_config_dumps": sorted(new_config_dumps),
        "log_run_dir_name": (f"run_{id_a}" if id_a else None),
        "result_dir_name": result_dir_name,
        "config_dump_name": config_dump_name,
    }

    out_path = RESULTS_DIR / f"h1_run_identity_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    print(f"H1 result: {verdict['result']}")
    print(f"  ids: {ids}")
    print(f"  distinct non-null ids: {len(distinct)} (of {len(observed)} observed)")
    print(f"  -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
