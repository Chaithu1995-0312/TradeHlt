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

# Indices (0-based) of absolute-price / size features in CANONICAL_FEATURES order
# (schema v4.0, CANONICAL_FEATURE_DIM=39). Zeroing at train+predict prevents Ridge
# from anchoring on instrument price level.
#   open=0  high=1  low=2  close=3  volume=4
#   ema_fast=7  ema_slow=8  macd_line=16  macd_signal=17
#   body_size=27  candle_range=28  (v3 had body_size=26 wick_size=27)
_PRICE_FEATURE_INDICES: list = [0, 1, 2, 3, 4, 7, 8, 16, 17, 27, 28]


def _load_dataset_self_described(path: str) -> tuple[list, list, list]:
    """Load an rr_dataset.json validating rows against its OWN stored n_features.

    Opt-in sibling of rr_dataset_builder.load_dataset() for legacy 38-dim clean-label
    datasets. The shared loader pins width/hash to the live canonical schema (39);
    this one trusts the file's self-declared width, so a documented-subset dataset
    loads without mutating the shared production module. Still fails closed on a
    missing/incoherent declaration or ragged rows.
    """
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"dataset not found: {p}")

    payload = json.loads(p.read_text(encoding="utf-8"))
    X = payload.get("X") or []
    y_rr = payload.get("y_rr") or []
    y_win = payload.get("y_win") or []

    declared = payload.get("n_features")
    if not isinstance(declared, int) or declared <= 0:
        raise SystemExit(
            f"--legacy-38-dim: {p} has no usable 'n_features' declaration "
            f"(got {declared!r}); refusing to guess the width."
        )

    names = payload.get("feature_names") or []
    if names and len(names) != declared:
        raise SystemExit(
            f"--legacy-38-dim: {p} declares n_features={declared} but carries "
            f"{len(names)} feature_names — incoherent, refusing to load."
        )

    if len(X) != len(y_rr) or len(X) != len(y_win):
        raise SystemExit(
            f"--legacy-38-dim: inconsistent lengths X={len(X)} "
            f"y_rr={len(y_rr)} y_win={len(y_win)}"
        )

    for i, vec in enumerate(X):
        if not isinstance(vec, list) or len(vec) != declared:
            raise SystemExit(
                f"--legacy-38-dim: row {i} width "
                f"{len(vec) if isinstance(vec, list) else type(vec).__name__} "
                f"!= declared n_features {declared}"
            )

    print(f"  [legacy-38-dim] loaded self-described dataset: n_features={declared}")
    return X, y_rr, y_win


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
    ap.add_argument(
        "--zero-price-features", action="store_true", default=False,
        help=(
            "Zero absolute price/size features before training "
            "(open, high, low, close, volume, ema_fast, ema_slow, "
            "macd_line, macd_signal, body_size, wick_size — indices 0-4,7-8,16-17,26-27). "
            "Removes price-level anchoring so the model generalises across price regimes."
        ),
    )
    ap.add_argument(
        "--instrument", default="",
        help="Instrument label (e.g. ETHUSDT). When given with --run-id/--run and no "
             "--dataset, auto-resolves models/{instrument}/{run_id}/rr_dataset.json.",
    )
    ap.add_argument(
        "--run-id", "--run", dest="run_id", default=None,
        help="Run ID (e.g. 20260519_113806). With --instrument auto-resolves both "
             "input dataset and output model paths to the run-scoped directory.",
    )
    ap.add_argument(
        "--legacy-38-dim", action="store_true", default=False,
        help=(
            "Load a legacy 38-dim dataset (macd_hist_raw excluded) by validating rows "
            "against the file's OWN stored n_features instead of the live canonical dim. "
            "Use with datasets from build_rr_dataset_from_clean_labels.py. The default "
            "(unset) path is unchanged and still uses the strict shared load_dataset()."
        ),
    )
    args = ap.parse_args()

    # ── Resolve dataset path ─────────────────────────────────────────────────
    dataset_path = args.dataset
    if not dataset_path:
        if args.instrument and args.run_id:
            # Run-scoped: pick canonical rr_dataset.json from the run directory
            run_dir = Path("models") / args.instrument / args.run_id
            auto_ds = run_dir / "rr_dataset.json"
            if not auto_ds.exists():
                # Fallback: first versioned file in run dir
                candidates = sorted(run_dir.glob("rr_dataset_*.json"))
                if candidates:
                    auto_ds = candidates[-1]
                else:
                    raise SystemExit(
                        f"No rr_dataset*.json found in {run_dir}. "
                        f"Run build_rr_dataset.py first."
                    )
            dataset_path = str(auto_ds)
            print(f"Auto-resolved dataset: {dataset_path}")
        else:
            entry = get_active_rr_entry()
            if entry and entry.get("dataset_file"):
                dataset_path = entry["dataset_file"]
            else:
                dataset_path = "models/rr_dataset.json"
    print(f"Loading dataset: {dataset_path}")

    if args.legacy_38_dim:
        # Opt-in: validate against the file's OWN stored n_features rather than the
        # live canonical dim. Used for clean-label datasets built at the legacy
        # 38-dim layout (macd_hist_raw deferred). Never reached by default.
        X, y_rr, y_win = _load_dataset_self_described(dataset_path)
    else:
        X, y_rr, y_win = load_dataset(dataset_path)
    n_samples  = len(X)
    n_features = len(X[0]) if X else 0
    print(f"  {n_samples} samples, {n_features} features")

    # ── Feature zeroing (price-level de-anchoring) ───────────────────────────
    zero_indices: list = _PRICE_FEATURE_INDICES if args.zero_price_features else []
    if zero_indices:
        for row in X:
            for idx in zero_indices:
                if idx < len(row):
                    row[idx] = 0.0
        print(f"  Zeroed {len(zero_indices)} price-level features at indices: {zero_indices}")

    # ── Train ────────────────────────────────────────────────────────────────
    trainer = RRPatternTrainer()
    state   = trainer.train(X, y_rr, y_win)
    n_train = state.get("n_train", n_samples)
    # Persist zero_indices in the model state so NanoInferenceEngine can apply
    # the same mask at predict-time — zero_indices=[] means no masking (backward compat).
    state["zero_indices"] = zero_indices
    print(f"Training complete — n_train={n_train}")

    # ── Version + output path ────────────────────────────────────────────────
    version = args.version or time.strftime("%Y%m_v1")
    if args.output:
        output = args.output
    elif args.instrument and args.run_id:
        # Run-scoped output alongside the dataset
        output = str(Path("models") / args.instrument / args.run_id
                     / f"rr_model_{version}.json")
    else:
        output = f"models/rr_model_{version}.json"

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    trainer.save(output)
    print(f"Saved model -> {output}")
    print(f"OUTPUT:rr_model:{Path(output).resolve()}")

    # ── Register ─────────────────────────────────────────────────────────────
    metrics = {
        "n_train":     n_train,
        "ridge_alpha": state.get("ridge_alpha", 1.0),
    }
    # Instrument-scoped registry key prevents collision across instruments
    reg_version = f"{version}_{args.instrument.lower()}" if args.instrument else version
    register_rr_model(reg_version, output, metrics)
    print(f"Registered in rr_registry: {reg_version}")

    # ── Promote ──────────────────────────────────────────────────────────────
    if args.promote:
        ok, reason = promote_rr(reg_version)
        print(f"Promote: {reason}")
        # Also write to canonical rr_model.json so engine_runner path still works
        shutil.copy2(output, "models/rr_model.json")
        print("Canonical models/rr_model.json updated")
    else:
        instr_flag = f" --instrument {args.instrument} --run-id {args.run_id}" if args.instrument else ""
        print(f"To promote: python train_rr_model.py{instr_flag} --version {version} --promote")


if __name__ == "__main__":
    main()
