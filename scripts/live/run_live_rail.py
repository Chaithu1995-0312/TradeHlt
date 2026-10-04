"""Thin CLI: paper live-rail drain. Logic lives in src/runtime/live_rail_orchestrator.py.

Three arms, all file-backed. Zero network, zero broker, zero money.

    --arm tickdb   configured TickDB JSONL fixture (original PR-4c behaviour)
    --arm bars     historical OHLCV corpus injected as ClosedBar (BarBuilder bypassed)
    --arm ticks    historical OHLCV corpus expanded to ticks (BarBuilder exercised)

``--report-dir`` gives the run its own directory instead of appending to the shared
logs/live_rail.jsonl, so two runs can be diffed for determinism.

Optional research dual-write (paper only):
    --crt-occupancy-sidecar   after the rail drain, run CRT occupancy feeder into
                              report-dir/crt_occupancy/ (BacktestRunner islice path).
                              Does not change Ultron/orders path; no CRT→broker shortcut.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

_CRT_CSV_DEFAULT = "data/mt5/XAUUSD_M15.csv"


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
    ap.add_argument(
        "--crt-occupancy-sidecar",
        action="store_true",
        help=(
            "REM-CRT-02 research: after paper rail, also run CRT occupancy feeder "
            "into report-dir/crt_occupancy/ (requires --paper and --report-dir). "
            "Additive chart/alert dual-write only; production path unchanged when absent."
        ),
    )
    ap.add_argument(
        "--crt-csv",
        default=None,
        help=(
            "CSV for CRT occupancy sidecar (default: --corpus if set, else "
            f"{_CRT_CSV_DEFAULT})"
        ),
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
    if args.crt_occupancy_sidecar and not args.report_dir:
        print(
            "refuse: --crt-occupancy-sidecar requires --report-dir "
            "(writes report-dir/crt_occupancy/ + SIDECAR_META.json)",
            file=sys.stderr,
        )
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
        "crt_occupancy_sidecar": bool(args.crt_occupancy_sidecar),
    }

    sidecar_info = None
    if args.crt_occupancy_sidecar:
        # Research dual-write AFTER paper rail drain — additive occupancy only.
        # Does not touch Ultron/orders path; BACKTEST_ENGINE_GATE scoped inside lib.
        assert run_dir is not None
        logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
        research_dir = _ROOT / "scripts" / "research"
        if str(research_dir) not in sys.path:
            sys.path.insert(0, str(research_dir))
        from crt_occupancy_lib import (  # noqa: WPS433
            CSV_DEFAULT,
            run_crt_occupancy_feeder,
            write_sidecar_meta,
        )

        crt_csv = args.crt_csv or args.corpus or CSV_DEFAULT
        crt_limit = int(args.limit) if args.limit is not None else 500
        instrument = getattr(cfg, "symbol", None) or "XAUUSD"
        crt_dir = run_dir / "crt_occupancy"
        feeder_result = run_crt_occupancy_feeder(
            out_dir=crt_dir,
            limit=crt_limit,
            csv=crt_csv,
            instrument=instrument,
            source="paper_rail_sidecar",
            verify=True,
        )
        meta_path = write_sidecar_meta(
            paper_run_dir=run_dir,
            crt_occupancy_dir=crt_dir,
            events_path=feeder_result["events_path"],
            feeder_result=feeder_result,
            arm=args.arm,
            corpus=crt_csv,
            limit=crt_limit,
        )
        sidecar_info = {
            "crt_occupancy_dir": str(crt_dir).replace("\\", "/"),
            "events_path": feeder_result["events_path"],
            "n_events": feeder_result["n_events"],
            "sidecar_meta": str(meta_path).replace("\\", "/"),
            "crt_limit": crt_limit,
            "crt_csv": crt_csv,
        }
        summary["crt_occupancy"] = sidecar_info

    if run_dir is not None:
        (run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        f"exit={rc} arm={args.arm} closed_bars={orch.closed_bars_seen} "
        f"process_attempts={orch.process_attempts} process_calls={orch.process_calls} "
        f"audit={counts} report={report_path}"
    )
    if sidecar_info is not None:
        print(
            f"crt_sidecar events={sidecar_info['n_events']} "
            f"path={sidecar_info['events_path']} meta={sidecar_info['sidecar_meta']}"
        )
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
