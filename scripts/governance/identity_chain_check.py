"""identity_chain_check.py — CLI for the 9-invariant closed identity chain checker (Phase 3).

Thin wrapper over `src.governance.identity_chain.check_run`. Report-only authority: verifies
identity joins across Spine journal (trades.csv), Oracle labeler (labels.csv), layer-trace
(L8), journal, and engine telemetry (crt_telemetry.jsonl); grants nothing and changes nothing.

    python scripts/governance/identity_chain_check.py \
        --telemetry  results/<run>/XAUUSD_crt_telemetry.jsonl \
        --trades     results/<run>/XAUUSD_trades.csv \
        --layer-trace results/layer_trace/XAUUSD_layer_trace.jsonl \
        --labels     results/research/oracle_labels/<tag>/labels.csv \
        --bar-identity results/bar_clock/XAUUSD_bar_identity.jsonl \
        --run-manifest results/<run>/run_manifest.json \
        --corpus-sha256 <sha256>

--run-manifest (optional): the per-run run_manifest.json. F-101: the telemetry envelope's
run_id and the layer-trace subsystem's own run_id are different strings for the same run;
I5/I6 use the manifest's layer_trace_id to scope their L8 lookup against a layer-trace file
that may hold multiple runs, falling back to telemetry's run_id when no manifest is given.

Exit code (default mode): 0 = no invariant FAILs; 1 = any FAIL (SKIP does not affect the
exit code — a partially-wired run with only some inputs supplied still exits 0). Pass
--require-all to additionally treat every SKIP as a violation (exit 1) — this is the only
mode that proves the chain is CLOSED end to end; use it once all five inputs are expected.
The summary line always states whether the verdict was PARTIAL (some invariants skipped)
so CLOSED can never be misread as "all nine verified" by glancing at the exit code alone.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.identity_chain import INVARIANTS, FAIL, SKIP, check_run  # noqa: E402

_WIDTH = max(len(n) for _, n in INVARIANTS) + 4


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="identity_chain_check",
        description="9-invariant closed identity chain checker (report-only).",
    )
    ap.add_argument("--telemetry", help="path to {instrument}_crt_telemetry.jsonl")
    ap.add_argument("--trades", help="path to {instrument}_trades.csv")
    ap.add_argument("--layer-trace", help="path to {instrument}_layer_trace.jsonl")
    ap.add_argument("--labels", help="path to research oracle labels.csv")
    ap.add_argument("--bar-identity", help="path to {instrument}_bar_identity.jsonl (bridge)")
    ap.add_argument("--run-manifest", help="path to the per-run run_manifest.json (F-101 layer_trace_id pointer)")
    ap.add_argument("--corpus-sha256", default=None, help="optional corpus hash to bind labels to")
    ap.add_argument(
        "--require-all", action="store_true",
        help="treat every SKIP as a violation (only a run with all 5 inputs can pass)",
    )
    args = ap.parse_args(argv)

    ok, outcomes = check_run(
        telemetry_path=args.telemetry,
        trades_path=args.trades,
        layer_trace_path=args.layer_trace,
        labels_path=args.labels,
        bar_identity_path=args.bar_identity,
        run_manifest_path=args.run_manifest,
        corpus_sha256=args.corpus_sha256,
        require_all=args.require_all,
    )
    print(f"{'INV':<4} {'NAME':<{_WIDTH}} STATUS  DETAIL")
    for o in outcomes:
        print(f"{o.invariant:<4} {o.name:<{_WIDTH}} {o.status:<7} {o.detail}")
    n_fail = sum(1 for o in outcomes if o.status == FAIL)
    n_skip = sum(1 for o in outcomes if o.status == SKIP)
    n_total = len(outcomes)
    verdict = "CLOSED" if ok else "VIOLATED"
    if n_skip and ok:
        # require_all is False here (a require_all run with any skip is never `ok`) —
        # disclose partial coverage so CLOSED is never misread as "7/7 verified".
        detail = f"PARTIAL - {n_skip} of {n_total} skipped, not verified"
    elif n_fail == 0 and n_skip == 0:
        detail = f"{n_total}/{n_total} verified"
    else:
        detail = f"{n_fail} fail, {n_skip} skip of {n_total} invariants"
    print(f"\nidentity chain: {verdict} ({detail})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_main())