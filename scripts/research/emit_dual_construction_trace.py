#!/usr/bin/env python
"""emit_dual_construction_trace.py — run both v4 dual-construction emitters, proven neutral.

Part of the 2026-09-03 TV-forensic / Dataset-Identity / Constructor-Trace comparison plan
(Phase 3, live drill). Thin CLI wrapper: mechanics live in `src/utils/isolated_config_root.py`
(reused, following `scripts/research/emit_bar_structure_snapshots.py`'s own precedent) and the
comparison logic is imported from `scripts/analysis/v3_config_parity.py::compare` rather than
reimplemented a second time.

WHAT IT DOES
------------
Three isolated arms (repository `ACTIVE_VERSION` never touched):

  A. `v2_htfcrt_2026_08`                          — the real active config, no emitters.
  B. `v4_dual_construction_2026_09`, both OFF     — same `params` hash as A by construction.
  C. `v4_dual_construction_2026_09`, both ON      — `bar_structure_snapshot` (122 structural
     fields/bar) and `crt_construction_trace` (engine state + resolver state + gate trace,
     `injection` hard-pinned to "none" by the module) emitted together for the first time on
     any corpus outside the frozen 2-year candidate.

DECISION-NEUTRALITY PROOF (required before either stream is trusted)
----------------------------------------------------------------------
A == B == C on `events.jsonl` / `crt_telemetry.jsonl` (byte-identical) and `trades.csv` /
`summary.json` (identical except `config_version`, which MUST differ A-vs-B/C and MUST NOT
differ B-vs-C). A failure here means one of the two OBSERVATION_ONLY sections leaked into a
decision — the streams below are not to be used as constructor output if this proof fails.

NON-VACUITY
-----------
Both streams must have exactly one row per corpus bar (header excluded). A stream that emits
fewer rows silently under-covers the window; a stream that never runs would otherwise be
indistinguishable from "nothing to report" (the same silent-gap class as F-079/F-083/F-085).

USAGE
    python scripts/research/emit_dual_construction_trace.py \\
        --instrument XAUUSD --csv data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "analysis"))

from utils.isolated_config_root import build_config_root, run_backtest  # noqa: E402
from v3_config_parity import compare  # noqa: E402  -- reused, never reimplemented

V2 = "v2_htfcrt_2026_08"
V4 = "v4_dual_construction_2026_09"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--csv", required=True,
                    help="corpus path RELATIVE to the repo root (must be dataset-admitted)")
    ap.add_argument("--out", default="logs/dual_construction",
                    help="destination directory for both JSONL streams (relative to repo root)")
    ap.add_argument("--keep", action="store_true", help="keep scratch roots for inspection")
    args = ap.parse_args()

    corpus_rel = args.csv
    if not (REPO / corpus_rel).exists():
        raise SystemExit(f"corpus not found: {REPO / corpus_rel}")

    dest_dir = (REPO / args.out).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_snapshot = dest_dir / f"{args.instrument}_bar_structure.jsonl"
    dest_trace = dest_dir / f"{args.instrument}_crt_construction.jsonl"
    for d in (dest_snapshot, dest_trace):
        if d.exists():
            raise SystemExit(
                f"{d} already exists -- move or delete it first. This script refuses to "
                "overwrite a stream an existing measurement may already cite."
            )

    tmp = Path(tempfile.mkdtemp(prefix="dual_construction_"))
    try:
        print(f"corpus    : {corpus_rel}")

        print(f"\n[A] {V2} (active config, baseline) ...", flush=True)
        root_a = build_config_root(REPO, tmp / "arm_a_v2_baseline", V2)
        result_a = run_backtest(REPO, root_a, corpus_rel, args.instrument)
        print(f"    ledger  : {result_a}")

        print(f"\n[B] {V4} (both emitters OFF) ...", flush=True)
        root_b = build_config_root(REPO, tmp / "arm_b_v4_off", V4)
        result_b = run_backtest(REPO, root_b, corpus_rel, args.instrument)
        print(f"    ledger  : {result_b}")

        stream_dir = tmp / "arm_c_streams"

        def _enable(cfg: dict) -> None:
            for section in ("bar_structure_snapshot", "crt_construction_trace"):
                if section not in cfg:
                    raise SystemExit(f"{V4} has no {section} section")
                cfg[section]["enabled"] = True
                cfg[section]["output_dir"] = str(stream_dir)

        print(f"\n[C] {V4} (both emitters ON) ...", flush=True)
        root_c = build_config_root(REPO, tmp / "arm_c_v4_on", V4, mutate_config=_enable)
        result_c = run_backtest(REPO, root_c, corpus_rel, args.instrument)
        print(f"    ledger  : {result_c}")

        print("\n=== decision-neutrality proof ===")
        ok_ab = compare(result_a, result_b, args.instrument,
                         "A (v2 baseline) vs B (v4 dual-construction, emitters OFF)",
                         expect_version_stamp_differs=True)
        ok_bc = compare(result_b, result_c, args.instrument,
                         "B (v4 emitters OFF) vs C (v4 emitters ON)",
                         expect_version_stamp_differs=False)

        produced_snapshot = stream_dir / f"{args.instrument}_bar_structure.jsonl"
        produced_trace = stream_dir / f"{args.instrument}_crt_construction.jsonl"
        for produced, dest in ((produced_snapshot, dest_snapshot), (produced_trace, dest_trace)):
            if not produced.exists():
                raise SystemExit(f"non-vacuity FAILED: {produced.name} was not produced")
            shutil.copy2(produced, dest)

        rows_snapshot = sum(1 for _ in dest_snapshot.open(encoding="utf-8"))
        rows_trace = sum(1 for _ in dest_trace.open(encoding="utf-8"))
        with (REPO / corpus_rel).open(encoding="utf-8") as f:
            corpus_bars = sum(1 for _ in f) - 1  # minus header row

        print("\n=== non-vacuity ===")
        print(f"  corpus bars           : {corpus_bars:,}")
        snap_ok = rows_snapshot == corpus_bars
        trace_ok = rows_trace == corpus_bars
        print(f"  bar_structure rows    : {rows_snapshot:,}  {'OK' if snap_ok else 'MISMATCH'}")
        print(f"  crt_construction rows : {rows_trace:,}  {'OK' if trace_ok else 'MISMATCH'}")

        summary = {
            "instrument": args.instrument,
            "corpus": corpus_rel,
            "corpus_bars": corpus_bars,
            "decision_neutral_a_vs_b": ok_ab,
            "decision_neutral_b_vs_c": ok_bc,
            "bar_structure_stream": str(dest_snapshot),
            "bar_structure_rows": rows_snapshot,
            "crt_construction_stream": str(dest_trace),
            "crt_construction_rows": rows_trace,
        }
        print("\n" + json.dumps(summary, indent=2))
        (dest_dir / f"{args.instrument}_dual_construction_run_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )

        if args.keep:
            kept = dest_dir / "scratch_roots"
            shutil.copytree(tmp, kept, dirs_exist_ok=True)
            print(f"\nscratch roots kept at: {kept}")

        ok = ok_ab and ok_bc and snap_ok and trace_ok
        if not ok:
            print("\nFAILED -- see above")
        return 0 if ok else 1
    finally:
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
