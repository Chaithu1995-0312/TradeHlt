"""
scripts/training/train_pipeline.py
─────────────────────────────────────────────────────────────────────────────
CLI entry point — thin wrapper only. All business logic lives in:
  src/training/train_pipeline.py

Usage (TradeNet):
  python scripts/training/train_pipeline.py --data data/training.json \
      --output results/training_result.json

Usage (Gaussian update):
  python scripts/training/train_pipeline.py --gaussian \
      --logs logs/GBPUSD_fusion.jsonl logs/EURUSD_fusion.jsonl \
      --version gaussian_v2_2026_04
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Bootstrap src/ onto the path when invoked directly.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Re-export the public API so any existing callers that did
#   from scripts.training.train_pipeline import run_training_pipeline
# continue to work without modification.
from training.train_pipeline import (          # noqa: F401  (re-export)
    run_training_pipeline,
    run_gaussian_update,
    validate_training_record,
    load_training_data,
    prepare_training_vectors,
    validate_training_dataset,
)

log = logging.getLogger("train_pipeline_cli")


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Tradelatest training pipeline CLI"
    )
    sub = parser.add_subparsers(dest="command")

    # ── tradenet subcommand ──────────────────────────────────────────────────
    tn = sub.add_parser("tradenet", help="Run TradeNet binary training")
    tn.add_argument("--data",   required=True, help="Path to training data JSON")
    tn.add_argument("--output", default=None,  help="Path to save results JSON")

    # ── gaussian subcommand ──────────────────────────────────────────────────
    gn = sub.add_parser("gaussian", help="Run Gaussian model update")
    gn.add_argument(
        "--logs", nargs="+", required=True,
        help="One or more *_fusion.jsonl paths",
    )
    gn.add_argument("--version", required=True, help="Registry version key")
    gn.add_argument(
        "--no-promote", action="store_true",
        help="Register but skip automatic promotion",
    )
    gn.add_argument(
        "--force-promote", action="store_true",
        help="Bypass regression guard in promote_gaussian()",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )

    if args.command == "tradenet":
        result = run_training_pipeline(data_path=args.data, model_fn=_real_tradenet_fn,
                                       output_path=args.output)
        print(f"\nTradeNet pipeline complete. Valid records: "
              f"{result.get('dataset_validation', {}).get('valid', '?')}")

    elif args.command == "gaussian":
        result = run_gaussian_update(
            log_paths     = args.logs,
            version       = args.version,
            promote       = not args.no_promote,
            force_promote = args.force_promote,
        )
        print(f"\nGaussian update: approved={result['approved']} "
              f"promoted={result['promoted']} verdict={result['verdict']}")

    else:
        parser.print_help()
        sys.exit(1)


def _real_tradenet_fn(X: list, y: list) -> dict:
    """
    Gap-5 fix: real TradeNet model_fn wired to training.trainer.train().

    Requires torch (Python 3.12).  Fails hard with a clear error if torch is
    not available so the caller knows to use  py -3.12  (see Gap-6 fix).
    """
    # ── torch pre-flight ─────────────────────────────────────────────────────
    try:
        import torch
    except ImportError:
        sys.exit(
            "\n"
            "====================================================================\n"
            "  FATAL: torch not found in this Python environment\n"
            "\n"
            "  Re-run with:\n"
            "    py -3.12 scripts/training/train_pipeline.py tradenet ...\n"
            "====================================================================\n"
        )

    # ── train ─────────────────────────────────────────────────────────────────
    from training.trainer import train, save_model
    model = train(X, y, verbose=True)

    # ── evaluate (quick binary accuracy on training set) ─────────────────────
    import torch as _th
    X_t = _th.tensor(X, dtype=_th.float32)
    with _th.no_grad():
        preds = model(X_t).squeeze(1).numpy()
    preds_bin = (preds >= 0.5).astype(int)
    y_arr     = [int(v) for v in y]
    accuracy  = float(sum(p == t for p, t in zip(preds_bin, y_arr)) / len(y_arr))

    # ── save + register via trainer.save_model ───────────────────────────────
    import time as _time
    version = f"cli_{_time.strftime('%Y%m%dT%H%M%S')}"
    metrics = {"accuracy": round(accuracy, 4), "n_train": len(X)}
    save_model(model, f"tradenet_{version}.pth", metrics=metrics, version=version)

    log.info("_real_tradenet_fn: trained n=%d  accuracy=%.4f  version=%s",
             len(X), accuracy, version)
    return {"n_samples": len(X), "accuracy": round(accuracy, 4), "version": version}


if __name__ == "__main__":
    _cli()
