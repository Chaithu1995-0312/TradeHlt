"""Thin CLI: dual TradeNet + EnvelopeNet clean-label builder (GATE-L / ENV-L).

Research tooling only. No spine wire, no train promote, no production config mutation.

Usage:
  python scripts/research/build_clean_labels_tn_env.py
  python scripts/research/build_clean_labels_tn_env.py --max-units 2000
  python scripts/research/build_clean_labels_tn_env.py \\
      --opportunities logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl \\
      --candles data/BNBUSDT_M15.csv --instrument BNBUSDT
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
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from bnbusdt_trade_anatomy import load_candles  # noqa: E402
from research.clean_labels.builder import BuildConfig, build_dataset, write_dataset_artifacts  # noqa: E402
from research.clean_labels.protocol import (  # noqa: E402
    MIN_SAMPLES_TRAIN_ELIGIBLE,
    PROTOCOL_ID,
    TP2_POLICY,
    compute_protocol_hash,
)


def _iter_opportunities(path: Path, max_scan: int | None):
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if max_scan is not None and i >= max_scan:
                break
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--opportunities",
        default="logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl",
    )
    ap.add_argument("--candles", default="data/BNBUSDT_M15.csv")
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--max-units", type=int, default=None, help="cap clean rows written")
    ap.add_argument("--max-scan", type=int, default=None, help="cap source lines read")
    ap.add_argument(
        "--out-dir",
        default=None,
        help="default results/clean_labels/<instrument>/<run_id>/",
    )
    args = ap.parse_args(argv)

    opp_path = ROOT / args.opportunities
    candle_path = ROOT / args.candles
    if args.instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
        candle_path = Path(guard_xauusd_csv_path(str(candle_path), args.instrument))
    if not opp_path.is_file():
        print(f"ERROR: opportunities not found: {opp_path}")
        return 2
    if not candle_path.is_file():
        print(f"ERROR: candles not found: {candle_path}")
        return 2

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else ROOT / "results" / "clean_labels" / args.instrument / run_id
    )
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    print(f"[clean-labels] protocol={PROTOCOL_ID} tp2_policy={TP2_POLICY}")
    print(f"[clean-labels] loading candles {candle_path}")
    candles, ts_to_idx, _ = load_candles(candle_path)
    print(f"[clean-labels] candles={len(candles)} loading opportunities {opp_path}")

    cfg = BuildConfig(
        instrument=args.instrument,
        max_units=args.max_units,
        source_path=str(args.opportunities),
        candle_path=str(args.candles),
        builder_entrypoint="scripts/research/build_clean_labels_tn_env.py",
    )
    records = list(_iter_opportunities(opp_path, args.max_scan))
    print(f"[clean-labels] scanned={len(records)} building…")
    result = build_dataset(records, candles, ts_to_idx, cfg)
    paths = write_dataset_artifacts(result, out_dir)

    # LATEST pointer (instrument-scoped)
    latest = ROOT / "results" / "clean_labels" / args.instrument / "LATEST"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "pointer.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "out_dir": str(out_dir),
                "protocol_id": PROTOCOL_ID,
                "protocol_hash": result.protocol_hash,
                "n_clean": result.n_clean,
                "train_eligible": result.train_eligible,
                "paths": paths,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[clean-labels] n_raw={result.n_raw} n_clean={result.n_clean} "
          f"train_eligible={result.train_eligible} (floor={MIN_SAMPLES_TRAIN_ELIGIBLE})")
    print(f"[clean-labels] skips={result.skips}")
    print(f"[clean-labels] agreement={result.agreement}")
    print(f"[clean-labels] protocol_hash={result.protocol_hash}")
    print(f"[clean-labels] wrote {out_dir}")
    print(f"[clean-labels] GATE_L_DATASET={'PASS' if result.train_eligible else 'BELOW_FLOOR'}")
    return 0 if result.n_clean > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
