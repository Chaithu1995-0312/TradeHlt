"""
bitnet_r25_kill_test.py
=======================
CLI for BitNet R2.5 kill-test harness (Spec v1.2.6).

Tries to falsify learning. PASS → earn R3 only. No production enable.

Examples
--------
  python scripts/research/bitnet_r25_kill_test.py --synthetic --signal strong
  python scripts/research/bitnet_r25_kill_test.py --csv data/BNBUSDT_M15.csv --max-samples 3000
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from bitnet.contract_c_trainer import TrainerConfig  # noqa: E402
from bitnet.r25_kill_test import (  # noqa: E402
    R25Config,
    R25_THRESHOLD_VERSION,
    R25_THRESHOLDS,
    run_r25_kill_test,
    write_r25_report,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="BitNet R2.5 kill-test (falsify before R3)")
    p.add_argument("--csv", action="append", default=[], help="OHLCV CSV (repeatable)")
    p.add_argument("--synthetic", action="store_true", help="Use synthetic data")
    p.add_argument(
        "--signal",
        choices=("strong", "weak", "none"),
        default="strong",
        help="Synthetic signal strength (default strong for harness smoke)",
    )
    p.add_argument("--synthetic-n", type=int, default=400)
    p.add_argument("--out-dir", default="results/bitnet/r25")
    p.add_argument("--run-name", default=None)
    p.add_argument("--epochs", type=int, default=25)
    p.add_argument("--lr", type=float, default=1e-2)
    p.add_argument("--hidden-dim", type=int, default=16)
    p.add_argument("--latent-dim", type=int, default=8)
    p.add_argument("--n-res", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-seeds", type=int, default=3)
    p.add_argument("--max-samples", type=int, default=None)
    p.add_argument("--holdout-fraction", type=float, default=0.25)
    p.add_argument("--print-thresholds", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.print_thresholds:
        print(json.dumps({
            "threshold_version": R25_THRESHOLD_VERSION,
            "thresholds": R25_THRESHOLDS,
        }, indent=2))
        return 0

    if not args.synthetic and not args.csv:
        # default synthetic strong for convenience
        args.synthetic = True

    trainer = TrainerConfig(
        epochs=args.epochs,
        lr=args.lr,
        hidden_dim=args.hidden_dim,
        latent_dim=args.latent_dim,
        n_residual_blocks=args.n_res,
        seed=args.seed,
        max_samples=args.max_samples,
        holdout_fraction=args.holdout_fraction,
        batch_size=32,
    )
    cfg = R25Config(
        trainer=trainer,
        n_seeds=args.n_seeds,
        synthetic=args.synthetic or not args.csv,
        synthetic_n=args.synthetic_n,
        synthetic_signal=args.signal,
        csv_paths=args.csv or None,
        out_dir=args.out_dir,
        run_name=args.run_name,
    )

    report = run_r25_kill_test(cfg)
    path = write_r25_report(report, cfg.out_dir, cfg.run_name)

    print(f"R2.5 status: {report['status']}")
    print(f"threshold_version: {report['threshold_version']}")
    print(f"report: {path}")
    for t in report["tests"]:
        mark = "PASS" if t["pass"] else "FAIL"
        print(f"  [{mark}] {t['id']}: {t.get('observed')}")
    print(report.get("authority"))
    if report["pass"]:
        print("NEXT: R3 offline comparison authorized (research only).")
        return 0
    print("NEXT: investigate pipeline; do NOT run R3.")
    return 2  # fail exit for CI/scripts


if __name__ == "__main__":
    raise SystemExit(main())
