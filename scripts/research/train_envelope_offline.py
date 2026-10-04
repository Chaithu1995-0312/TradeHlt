"""CLI: ENV_OFFLINE_TRAIN_V1 multi-head Envelope offline train (research only).

Usage:
  python scripts/research/train_envelope_offline.py
  python scripts/research/train_envelope_offline.py --max-rows 80000
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research.envelope_offline.train import (  # noqa: E402
    CHARTER_ID,
    REQUIRED_PROTOCOL,
    TrainConfig,
    run_offline_train,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", default=None, help="clean_labels.jsonl (default BNB LATEST)")
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--max-rows", type=int, default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    if args.dataset:
        dataset = Path(args.dataset)
        if not dataset.is_absolute():
            dataset = ROOT / dataset
    else:
        pointer = ROOT / "results" / "clean_labels" / args.instrument / "LATEST" / "pointer.json"
        if not pointer.is_file():
            print(f"ERROR: no LATEST pointer at {pointer}")
            return 2
        dataset = Path(json.loads(pointer.read_text(encoding="utf-8"))["paths"]["dataset"])

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else ROOT / "results" / "envelope_offline" / args.instrument / run_id
    )
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    print(f"[{CHARTER_ID}] protocol={REQUIRED_PROTOCOL}")
    print(f"[{CHARTER_ID}] dataset={dataset}")
    print(f"[{CHARTER_ID}] out={out_dir}")

    cfg = TrainConfig(
        dataset_path=str(dataset),
        out_dir=str(out_dir),
        instrument=args.instrument,
        max_rows=args.max_rows,
    )
    try:
        bundle = run_offline_train(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"[{CHARTER_ID}] FAILED: {type(exc).__name__}: {exc}")
        return 1

    # LATEST pointer
    latest = ROOT / "results" / "envelope_offline" / args.instrument / "LATEST"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "pointer.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "out_dir": str(out_dir),
                "charter_id": CHARTER_ID,
                "signal_rollup": bundle["signal_rollup"],
                "dataset_protocol_hash": bundle.get("dataset_protocol_hash"),
                "bundle": str(out_dir / "envelope_bundle.json"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # durable docs summary
    docs = ROOT / "docs" / "analysis" / f"envelope-offline-train-{args.instrument}.LATEST.md"
    docs.write_text((out_dir / "report.md").read_text(encoding="utf-8"), encoding="utf-8")
    (ROOT / "docs" / "analysis" / f"envelope-offline-train-{args.instrument}.LATEST.json").write_text(
        json.dumps(bundle, indent=2), encoding="utf-8"
    )

    print(f"[{CHARTER_ID}] status={bundle['status']} rollup={bundle['signal_rollup']}")
    for key, h in bundle["heads"].items():
        print(f"  {key}: test_ic={h['test_ic']} tag={h['tag']}")
    print(f"[{CHARTER_ID}] wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
