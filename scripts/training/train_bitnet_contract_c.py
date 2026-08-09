"""
train_bitnet_contract_c.py
==========================
Thin CLI for CONTRACT-C BitNet trainer (Spec R1).

Emits a self-contained model.bundle under results/bitnet/bundles/ by default.
Does NOT enable use_bitnet or grant economic authority.

Examples
--------
  python scripts/training/train_bitnet_contract_c.py --synthetic --epochs 5
  python scripts/training/train_bitnet_contract_c.py --csv data/BNBUSDT_M15.csv --epochs 20
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from bitnet.contract_c_trainer import TrainerConfig, train_and_export  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CONTRACT-C BitNet trainer → model.bundle")
    p.add_argument("--csv", action="append", default=[], help="OHLCV CSV (repeatable)")
    p.add_argument("--synthetic", action="store_true", help="Use synthetic data (tests/smoke)")
    p.add_argument("--synthetic-n", type=int, default=256)
    p.add_argument("--out-dir", default="results/bitnet/bundles")
    p.add_argument("--bundle-name", default=None)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--hidden-dim", type=int, default=64)
    p.add_argument("--latent-dim", type=int, default=32)
    p.add_argument("--n-res", type=int, default=2)
    p.add_argument("--max-samples", type=int, default=None)
    p.add_argument("--holdout-fraction", type=float, default=0.2)
    p.add_argument(
        "--label-contract",
        default="BITNET_LABEL_ATR_RACE_BULL_V1",
        help="label_contract_id (default DIAGNOSTIC_ONLY ATR race)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if not args.synthetic and not args.csv:
        p.error("Provide --csv PATH and/or --synthetic")

    cfg = TrainerConfig(
        label_contract_id=args.label_contract,
        hidden_dim=args.hidden_dim,
        latent_dim=args.latent_dim,
        n_residual_blocks=args.n_res,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        seed=args.seed,
        max_samples=args.max_samples,
        holdout_fraction=args.holdout_fraction,
    )
    # Custom L2 dims for synthetic small models
    if args.synthetic and args.hidden_dim != 64:
        pass
    if args.synthetic and cfg.input_dim == 38 and args.hidden_dim <= 16:
        # keep 38 unless user wants tiny - for smoke allow smaller via flags
        pass

    result = train_and_export(
        csv_paths=args.csv or None,
        out_dir=args.out_dir,
        cfg=cfg,
        synthetic=args.synthetic,
        synthetic_n=args.synthetic_n,
        bundle_name=args.bundle_name,
    )
    print(f"CONTRACT-C model.bundle → {result.bundle_path}")
    print(f"n_train={result.n_train} n_holdout={result.n_holdout}")
    print(f"train_metrics={result.metrics.get('train')}")
    print(f"holdout_metrics={result.metrics.get('holdout')}")
    print("economic_authority=DIAGNOSTIC_ONLY (no enable authority)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
