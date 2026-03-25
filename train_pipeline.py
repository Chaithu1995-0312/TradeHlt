"""
train_pipeline.py
═══════════════════════════════════════════════════════════════════════════════
Full self-improvement pipeline:

  Logs → Validate → Time-split → Train (past) → Evaluate (future)
       → Register → Promote if better → Load into FusionEngine

Usage:
  python train_pipeline.py                         # train from default logs
  python train_pipeline.py --log-dir logs/         # specific dir
  python train_pipeline.py --force-promote         # skip margin check
  python train_pipeline.py --dry-run               # validate + eval only
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from dataset_validator import validate_logs_multi_instrument, MIN_RECORDS_TO_TRAIN
from dataset_builder   import (
    build_splits, build_full,
    build_gaussian_dataset, GAUSSIAN_FEATURE_SCHEMA, validate_dataset_quality,
)
from trainer           import (
    train, save_model, load_model, make_neural_fn,
    train_gaussian, save_gaussian_model, load_gaussian_model,
    cross_val_gaussian,
    GaussianNBModel, StandardScaler,
)
from evaluator         import evaluate, evaluate_gaussian, should_update
from model_registry    import (
    register, try_promote, get_active, print_leaderboard,
    register_gaussian, promote_gaussian, get_active_gaussian, print_gaussian_leaderboard,
)

log = logging.getLogger("TrainPipeline")
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run(
    log_dir:       str  = "logs",
    train_ratio:   float = 0.70,
    epochs:        int   = 100,
    dry_run:       bool  = False,
    force_promote: bool  = False,
) -> None:

    print(f"\n{'═'*60}")
    print(f"  CRT FUSION — TRAINING PIPELINE")
    print(f"{'═'*60}\n")

    # ── Step 1: Validate logs ─────────────────────────────────────────────────
    print("  Step 1/5: Validating logs...")
    records, report = validate_logs_multi_instrument(log_dir=log_dir, verbose=True)

    if not report.is_trainable:
        print(
            f"\n  ❌ Aborting: only {report.valid_for_training} valid records "
            f"(minimum: {MIN_RECORDS_TO_TRAIN}).\n"
            f"  Run more backtests or live sessions to accumulate trade history.\n"
        )
        return

    if dry_run:
        print("  [DRY RUN] Validation complete. Skipping training.\n")
        return

    # ── Step 2: Build time-split ──────────────────────────────────────────────
    print("  Step 2/5: Building time-ordered splits...")
    splits = build_splits(records, train_ratio=train_ratio)

    if splits.n_val < 30:
        print(
            f"\n  ⚠  Only {splits.n_val} validation records — results unreliable.\n"
            f"  Consider collecting more data before trusting this model.\n"
        )

    # ── Step 3: Train on past data only ──────────────────────────────────────
    print(f"  Step 3/5: Training on {splits.n_train} records...")
    t0    = time.perf_counter()
    model = train(splits.X_train, splits.y_train, epochs=epochs, verbose=True)
    elapsed = time.perf_counter() - t0
    print(f"  Training complete in {elapsed:.1f}s")

    # ── Step 4: Evaluate on future (held-out) data ────────────────────────────
    print(f"\n  Step 4/5: Evaluating on {splits.n_val} validation records...")
    result = evaluate(model, splits.X_val, splits.y_val)
    result.print(label="Validation")

    # Save model with timestamp
    model_name = f"tradenet_{int(time.time())}.pth"
    save_model(model, model_name)

    # Register
    entry = register(model_name, result)

    # ── Step 5: Try promotion ─────────────────────────────────────────────────
    print("  Step 5/5: Checking promotion...")
    if force_promote:
        from pathlib import Path as _P
        (_P("models")).mkdir(exist_ok=True)
        (_P("models/active.txt")).write_text(model_name)
        print(f"  [FORCE] Promoted {model_name}\n")
    else:
        promoted, reason = try_promote(model_name)

    print_leaderboard()

    # ── Summary ───────────────────────────────────────────────────────────────
    active = get_active()
    print(f"  Active model: {active or 'none'}")
    print(f"\n{'═'*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN UPDATE PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_gaussian_update(
    trades: list,
    version_tag: str = None,
    lambda_decay: float = 0.05,
    corr_margin: float = 0.02,
    force_promote: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Self-improvement pipeline for the Gaussian scoring layer.

    Flow:
      trades → build_gaussian_dataset → validate → train_gaussian
           → evaluate_gaussian → should_update gate
           → save + register + (optional) promote

    Parameters
    ----------
    trades        : list of TradeRecord objects or dicts with pnl_rr_net
    version_tag   : version string (default = timestamp-based)
    lambda_decay  : time decay constant for time_decay_feature
    corr_margin   : minimum improvement margin for gate
    force_promote : skip gate and always promote (for testing only)
    dry_run       : build + validate but skip training

    Returns
    -------
    dict with pipeline results
    """
    print(f"\n{'═'*60}")
    print(f"  GAUSSIAN UPDATE PIPELINE")
    print(f"{'═'*60}\n")

    # ── Step 1: Build dataset ─────────────────────────────────────
    print("  Step 1/5: Building Gaussian dataset...")
    try:
        X, y_rr = build_gaussian_dataset(trades, lambda_decay=lambda_decay)
    except ValueError as e:
        print(f"\n  ❌ Dataset error: {e}\n")
        return {"success": False, "reason": str(e)}

    print(f"  Dataset: {len(X)} samples, {len(GAUSSIAN_FEATURE_SCHEMA)} features")

    # ── Step 2: Validate dataset quality ─────────────────────────
    print("  Step 2/5: Validating dataset quality...")
    quality = validate_dataset_quality(X, y_rr)
    if quality.get("issues"):
        print("  ⚠ Dataset quality issues:")
        for issue in quality["issues"]:
            print(f"    • {issue}")
    else:
        print("  ✅ Dataset quality checks passed")

    if dry_run:
        print("  [DRY RUN] Skipping training.\n")
        return {"success": True, "dry_run": True, "quality": quality}

    # ── Step 3: Cross-validate for stability (FIX 4) then train ──
    print("  Step 3/5: Cross-validating stability + training Gaussian model...")
    t0 = time.perf_counter()

    # FIX 4: 3-fold time-series CV for stable metric estimate
    cv_result = cross_val_gaussian(X, y_rr, n_folds=3)
    print(f"  Cross-val (3-fold): corr={cv_result['corr_mean']:+.4f}±{cv_result['corr_std']:.4f}  "
          f"cal={cv_result['cal_mean']:.4f}±{cv_result['cal_std']:.4f}  "
          f"stable={cv_result['stable']}")
    if not cv_result["stable"]:
        print("  ⚠ Warning: High variance across CV folds — model may be unstable. "
              "Collect more trades before trusting this version.")

    new_model, new_scaler, train_metrics = train_gaussian(X, y_rr)
    elapsed = time.perf_counter() - t0
    print(f"  Training complete in {elapsed:.1f}s")
    print(f"  Full-data metrics: corr={train_metrics['corr_expected_rr']:+.4f}  "
          f"cal_err={train_metrics['calibration_error']:.4f}")

    # ── Step 4: Evaluate and compare against current active ──────
    print("  Step 4/5: Evaluating vs current Gaussian...")

    split_idx = max(1, int(len(X) * 0.70))
    X_val, y_val_rr = X[split_idx:], y_rr[split_idx:]

    new_eval = evaluate_gaussian(new_model, new_scaler, X_val, y_val_rr)
    new_eval.print(label="New Gaussian")

    current_version = get_active_gaussian()
    if current_version:
        try:
            cur_model, cur_scaler, cur_meta = load_gaussian_model(f"{current_version}.json")
            cur_eval = evaluate_gaussian(cur_model, cur_scaler, X_val, y_val_rr)
            cur_eval.print(label=f"Current ({current_version})")
            current_metrics = {
                "corr_expected_rr":  cur_eval.corr_expected_rr,
                "calibration_error": cur_eval.calibration_error,
            }
        except Exception as e:
            log.warning(f"Could not load current Gaussian model: {e}")
            current_metrics = {"corr_expected_rr": 0.0, "calibration_error": 1.0}
    else:
        print("  No active Gaussian — treating as first deployment")
        current_metrics = {"corr_expected_rr": -1.0, "calibration_error": 1.0}

    # Use CV mean metrics for gate decision (FIX 4 — more stable than single split)
    new_metrics = {
        "corr_expected_rr":  cv_result["corr_mean"],   # FIX 4: use cross-val mean
        "calibration_error": cv_result["cal_mean"],
        "corr_std":          cv_result["corr_std"],
        "stable":            cv_result["stable"],
    }

    # ── Step 5: Update gate ───────────────────────────────────────
    print("  Step 5/5: Running update gate...")
    gate_pass, gate_reason = should_update(new_metrics, current_metrics, corr_margin)
    print(f"\n  Gate verdict: {'✅ PASS' if gate_pass else '❌ BLOCK'}")
    print(f"  Reason: {gate_reason}\n")

    if gate_pass or force_promote:
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        version = version_tag or f"v_gaussian_{ts}"
        model_file = f"{version}.json"

        save_gaussian_model(
            new_model, new_scaler,
            metrics={**train_metrics, **new_metrics},
            name=model_file,
            feature_schema=GAUSSIAN_FEATURE_SCHEMA,
        )
        register_gaussian(
            version=version,
            model_file=model_file,
            feature_schema=GAUSSIAN_FEATURE_SCHEMA,
            metrics={**train_metrics, **new_metrics},
        )
        promoted, p_reason = promote_gaussian(version)
        if promoted:
            print(f"  ✅ Promoted: {version}")
        else:
            print(f"  ⚠  Promotion result: {p_reason}")

        print_gaussian_leaderboard()
        return {
            "success":     True,
            "version":     version,
            "gate_passed": gate_pass,
            "promoted":    promoted,
            "metrics":     new_metrics,
            "quality":     quality,
        }
    else:
        print(f"  Model NOT saved (gate blocked).")
        return {
            "success":     False,
            "gate_passed": False,
            "reason":      gate_reason,
            "metrics":     new_metrics,
        }


def load_active_gaussian_scorer():
    """
    Load the active Gaussian model bundle for inference.
    Returns (model, scaler) or (None, None) if not available.
    """
    version = get_active_gaussian()
    if not version:
        log.warning("No active Gaussian model. Run run_gaussian_update() first.")
        return None, None
    try:
        model, scaler, _ = load_gaussian_model(f"{version}.json")
        log.info(f"Loaded active Gaussian: {version}")
        return model, scaler
    except Exception as e:
        log.error(f"Failed to load Gaussian model {version}: {e}")
        return None, None


def load_active_neural_fn():
    """
    Load the currently active model and return a neural_fn callable
    suitable for FusionEngine(neural_fn=...).

    Returns None if no active model is registered yet.
    """
    active = get_active()
    if not active:
        log.warning("No active model registered. Train first with train_pipeline.py.")
        return None
    try:
        model = load_model(active)
        fn    = make_neural_fn(model)
        log.info(f"Loaded active model: {active}")
        return fn
    except Exception as e:
        log.error(f"Failed to load active model {active}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="CRT Fusion — Training Pipeline")
    ap.add_argument("--log-dir",       default="logs",  help="Directory containing *_fusion.jsonl logs")
    ap.add_argument("--train-ratio",   type=float, default=0.70)
    ap.add_argument("--epochs",        type=int,   default=100)
    ap.add_argument("--dry-run",       action="store_true", help="Validate only, skip training")
    ap.add_argument("--force-promote", action="store_true", help="Promote regardless of margin")
    args = ap.parse_args()

    run(
        log_dir       = args.log_dir,
        train_ratio   = args.train_ratio,
        epochs        = args.epochs,
        dry_run       = args.dry_run,
        force_promote = args.force_promote,
    )


if __name__ == "__main__":
    main()
