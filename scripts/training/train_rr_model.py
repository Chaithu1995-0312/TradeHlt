"""
train_rr_model.py
=================
Train the RR Pattern Miner model from an existing RR dataset.

Uses the active dataset from rr_registry.json by default, or an explicit path.
Saves a versioned model file (models/rr_model_{version}.json) and registers it
in rr_registry.json.

Usage:
    # Train from active dataset, auto-version, do NOT promote
    py train_rr_model.py

    # Train from specific versioned dataset, explicit version, promote after
    py train_rr_model.py --dataset models/rr_dataset_202505_v1.json \\
                          --version 202505_v1 --promote

    # Train from legacy canonical dataset
    py train_rr_model.py --dataset models/rr_dataset.json --version legacy_2026_05
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.rr.rr_dataset_builder import load_dataset
from config_layer.rr.rr_pattern_miner import RRPatternTrainer
from core.model_registry import (
    register_rr_model,
    promote_rr,
    get_active_rr,
    get_active_rr_entry,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Train the RR Pattern Miner from a versioned RR dataset. "
            "Saves a uniquely-versioned model file and registers it in rr_registry.json."
        )
    )
    ap.add_argument(
        "--dataset", default=None,
        help="Path to rr_dataset_*.json (default: active version from rr_registry)",
    )
    ap.add_argument(
        "--version", default=None,
        help="Version key for rr_registry (auto-generates YYYYMM_v1 if omitted)",
    )
    ap.add_argument(
        "--output", default=None,
        help="Output model path (default: models/rr_model_{version}.json)",
    )
    ap.add_argument(
        "--promote", action="store_true", default=False,
        help="Set this version as active after training (also writes canonical rr_model.json)",
    )
    args = ap.parse_args()

    # ── Resolve dataset path ─────────────────────────────────────────────────
    dataset_path = args.dataset
    if not dataset_path:
        entry = get_active_rr_entry()
        if entry and entry.get("dataset_file"):
            dataset_path = entry["dataset_file"]
        else:
            dataset_path = "models/rr_dataset.json"
    print(f"Loading dataset: {dataset_path}")

    X, y_rr, y_win = load_dataset(dataset_path)
    n_samples  = len(X)
    n_features = len(X[0]) if X else 0
    print(f"  {n_samples} samples, {n_features} features")

    # ── Train ────────────────────────────────────────────────────────────────
    trainer = RRPatternTrainer()
    state   = trainer.train(X, y_rr, y_win)
    n_train = state.get("n_train", n_samples)
    print(f"Training complete — n_train={n_train}")

    # ── Version + output path ────────────────────────────────────────────────
    version = args.version or time.strftime("%Y%m_v1")
    output  = args.output  or f"models/rr_model_{version}.json"

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    trainer.save(output)
    print(f"Saved model -> {output}")

    # ── Register ─────────────────────────────────────────────────────────────
    metrics = {
        "n_train":    n_train,
        "ridge_alpha": state.get("ridge_alpha", 1.0),
    }
    register_rr_model(version, output, metrics)
    print(f"Registered in rr_registry: {version}")

    # ── Promote ──────────────────────────────────────────────────────────────
    if args.promote:
        ok, reason = promote_rr(version)
        print(f"Promote: {reason}")
        # Also write to canonical rr_model.json so engine_runner path still works
        shutil.copy2(output, "models/rr_model.json")
        print("Canonical models/rr_model.json updated")
    else:
        print(f"To promote: python train_rr_model.py --version {version} ... --promote")


if __name__ == "__main__":
    main()
