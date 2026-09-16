"""REM-CRT-02 research smoke: CRT occupancy dual-write feeder (live-alert path).

RESEARCH ONLY. Does not change ACTIVE_VERSION, tokens.py, or Ultron live orders.

Produces chart-compatible ``{INSTR}_events.jsonl`` (same shape as backtest_v2 /
``crt_overlay.track_from_events``) by driving ``BacktestRunner`` over a limited
CandleLoader stream with ``BACKTEST_ENGINE_GATE=0``.

Usage:
  set PYTHONPATH=src
  .venv\\Scripts\\python.exe scripts\\research\\crt_occupancy_feeder_smoke.py ^
      --limit 3000 --out-dir results\\live_crt_occupancy_smoke_20260916
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))

from crt_occupancy_lib import (  # noqa: E402
    CSV_DEFAULT,
    INSTRUMENT_DEFAULT,
    VERSION_DEFAULT,
    run_crt_occupancy_feeder,
)


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="REM-CRT-02 CRT occupancy feeder smoke")
    ap.add_argument("--limit", type=int, default=3000, help="Max candles to stream (smoke)")
    ap.add_argument(
        "--out-dir",
        type=str,
        default="results/live_crt_occupancy_smoke_20260916",
        help="Output directory for events + meta + verify",
    )
    ap.add_argument("--csv", type=str, default=CSV_DEFAULT)
    ap.add_argument("--instrument", type=str, default=INSTRUMENT_DEFAULT)
    ap.add_argument("--version", type=str, default=VERSION_DEFAULT)
    ap.add_argument(
        "--skip-features",
        action="store_true",
        default=True,
        help="Skip FeaturePipeline (default True — occupancy events need engine only)",
    )
    ap.add_argument(
        "--with-features",
        action="store_true",
        help="Build FeaturePipeline on full CSV (slower; still limited stream)",
    )
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    skip_features = bool(args.skip_features) and not bool(args.with_features)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    log = logging.getLogger("crt_occupancy_feeder_smoke")

    result = run_crt_occupancy_feeder(
        out_dir=Path(args.out_dir),
        limit=int(args.limit),
        csv=args.csv,
        instrument=args.instrument,
        version=args.version,
        skip_features=skip_features,
        source="dual_write_smoke",
        verify=True,
    )
    verify = result.get("verify") or {}
    log.info("Wrote %s (%d events)", result["events_path"], result["n_events"])
    log.info("META %s", result["meta_path"])
    log.info(
        "VERIFY %s | stateish=%s | parseable=%s | track_ok=%s",
        result.get("verify_path"),
        verify.get("n_stateish"),
        verify.get("chart_overlay_parseable"),
        verify.get("track_from_events_ok"),
    )
    print(
        json.dumps(
            {
                "ok": True,
                "out_dir": result["out_dir"],
                **{
                    k: verify[k]
                    for k in (
                        "n_events_total",
                        "n_stateish",
                        "sample_state_names",
                        "chart_overlay_parseable",
                        "track_from_events_ok",
                    )
                    if k in verify
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
