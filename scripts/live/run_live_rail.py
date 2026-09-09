"""Thin CLI: paper live-rail drain. Logic lives in src/runtime/live_rail_orchestrator.py.

Three arms, all file-backed. Zero network, zero broker, zero money.

    --arm tickdb   configured TickDB JSONL fixture (original PR-4c behaviour)
    --arm bars     historical OHLCV corpus injected as ClosedBar (BarBuilder bypassed)
    --arm ticks    historical OHLCV corpus expanded to ticks (BarBuilder exercised)

``--report-dir`` gives the run its own directory instead of appending to the shared
logs/live_rail.jsonl, so two runs can be diffed for determinism.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Paper run of LiveRailOrchestrator (not ACTIVE_VERSION, never live)."
    )
    ap.add_argument(
        "--config",
        required=True,
        help="JSON file containing a live_rail section (experimental only)",
    )
    ap.add_argument(
        "--paper",
        action="store_true",
        help="Required. Sets LIVE_ENGINE_ENABLED=1 for this process only.",
    )
    ap.add_argument(
        "--arm",
        choices=("tickdb", "bars", "ticks"),
        default="tickdb",
        help="tickdb: configured fixture. bars/ticks: historical corpus replay.",
    )
    ap.add_argument("--corpus", default=None, help="OHLCV CSV for --arm bars|ticks")
    ap.add_argument("--limit", type=int, default=None, help="Cap corpus rows")
    ap.add_argument("--report", default="logs/live_rail.jsonl", help="Audit JSONL path")
    ap.add_argument(
        "--report-dir",
        default=None,
        help="Per-run directory; writes audit.jsonl + summary.json (overrides --report)",
    )
    args = ap.parse_args(argv)

    if not args.paper:
        print(
            "refuse: pass --paper (sets LIVE_ENGINE_ENABLED=1 in-process only; no live book)",
            file=sys.stderr,
        )
        return 2
    if args.arm in ("bars", "ticks") and not args.corpus:
        print(f"refuse: --arm {args.arm} requires --corpus", file=sys.stderr)
        return 2
    os.environ["LIVE_ENGINE_ENABLED"] = "1"

    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        print(f"refuse: config not found: {cfg_path}", file=sys.stderr)
        return 2
    payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    section = payload.get("live_rail") if isinstance(payload, dict) else None
    if not isinstance(section, dict):
        print("refuse: config has no live_rail section", file=sys.stderr)
        return 2

    if args.report_dir:
        run_dir = Path(args.report_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        report_path = run_dir / "audit.jsonl"
        if report_path.exists():
            print(f"refuse: {report_path} exists (use a fresh --report-dir)", file=sys.stderr)
            return 2
    else:
        run_dir = None
        report_path = Path(args.report)

    from inout.live_rail.config import LiveRailConfig
    from runtime.live_rail_orchestrator import LiveRailOrchestrator, summarize_audit

    cfg = LiveRailConfig.from_prod_config(section)

    if args.arm == "bars":
        from inout.live_rail.ohlcv_replay_port import load_corpus_bars

        orch = LiveRailOrchestrator.from_config(cfg, report_path=report_path)
        bars = load_corpus_bars(Path(args.corpus), cfg, limit=args.limit)
        rc = asyncio.run(orch.run_bars(bars))
    elif args.arm == "ticks":
        from inout.live_rail.ohlcv_replay_port import OhlcvTickReplayPort

        replay = OhlcvTickReplayPort(cfg, Path(args.corpus), limit=args.limit)
        orch = LiveRailOrchestrator.from_config(cfg, report_path=report_path, port=replay)
        rc = asyncio.run(orch.run_until_exhausted())
    else:
        orch = LiveRailOrchestrator.from_config(cfg, report_path=report_path)
        rc = asyncio.run(orch.run_until_exhausted())

    counts = summarize_audit(report_path)
    summary = {
        "arm": args.arm,
        "corpus": args.corpus,
        "limit": args.limit,
        "exit": int(rc),
        "closed_bars": orch.closed_bars_seen,
        "process_attempts": orch.process_attempts,
        "process_calls": orch.process_calls,
        "audit_counts": counts,
    }
    if run_dir is not None:
        (run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        f"exit={rc} arm={args.arm} closed_bars={orch.closed_bars_seen} "
        f"process_attempts={orch.process_attempts} process_calls={orch.process_calls} "
        f"audit={counts} report={report_path}"
    )
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
