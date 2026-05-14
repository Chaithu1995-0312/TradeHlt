"""
train_bitnet.py
================
Trains model.json (legacy 6-input BitNet) from historical CSV data.

Labels
------
  Each candle where a CRT signal fires is a training sample.
  Label = 1.0 (win) if price hits TP before SL in next 40 bars.
  Label = 0.0 (loss) if price hits SL first or times out.

Features (6)
------------
  body_ratio, retest_depth, disp_strength,
  atr, candles_since_retest, double_sweep

Training
--------
  Gradient descent with MSE loss, sigmoid output.
  No external ML library required — pure Python + numpy.

Usage
-----
    python scripts/training/train_bitnet.py
    python scripts/training/train_bitnet.py --epochs 300 --lr 0.001 --csv data/EURUSD_M15.csv
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np
import pandas as pd
from features.feature_pipeline import FeaturePipeline


# ── Architecture ───────────────────────────────────────────────────────────────

IN_DIM   = 6
H1       = 16
H2       = 8
OUT      = 1
WARMUP   = 60
MAX_FWD  = 40

FEATURE_KEYS = [
    "body_ratio", "retest_depth", "disp_strength",
    "atr", "candles_since_retest", "double_sweep",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-500, min(500, x))))


def _relu(x: float) -> float:
    return max(0.0, x)


def _forward(x: list[float], w1, b1, w2, b2, wo, bo) -> tuple[list, list, float]:
    h1 = [_relu(sum(xi * wij for xi, wij in zip(x, row)) + bj)
          for row, bj in zip(w1, b1)]
    h2 = [_relu(sum(hi * wij for hi, wij in zip(h1, row)) + bj)
          for row, bj in zip(w2, b2)]
    raw = sum(hi * wij for hi, wij in zip(h2, wo[0])) + bo[0]
    out = _sigmoid(raw)
    return h1, h2, out


def _mse_grad(pred: float, label: float) -> float:
    return 2.0 * (pred - label)


# ── Dataset builder ────────────────────────────────────────────────────────────

def build_dataset(csv_paths: list[str]) -> tuple[list[list[float]], list[float]]:
    X, y = [], []
    for csv_path in csv_paths:
        if not Path(csv_path).exists():
            print(f"  [SKIP] {csv_path} not found")
            continue
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        if len(df) < WARMUP + MAX_FWD + 20:
            continue
        try:
            pipe = FeaturePipeline(df)
            feat_df, _ = pipe.run()
        except Exception as exc:
            print(f"  [SKIP] FeaturePipeline failed for {csv_path}: {exc}")
            continue

        highs  = feat_df["high"].values
        lows   = feat_df["low"].values
        closes = feat_df["close"].values
        atrs   = feat_df["atr"].values
        n      = len(feat_df)

        for i in range(WARMUP, n - MAX_FWD):
            row = feat_df.iloc[i]
            atr = float(row.get("atr", 0.0))
            if atr <= 0:
                continue

            # Only train on candles where sweep+retest pattern present
            retest_depth = float(row.get("retest_depth", 0.0))
            if retest_depth <= 0.05:
                continue

            feat = [
                float(row.get("body_ratio",          0.0)),
                float(row.get("retest_depth",         0.0)),
                float(row.get("disp_strength",        0.0)),
                atr,
                float(row.get("candles_since_retest", 0.0)),
                float(bool(float(row.get("double_sweep", 0.0)) > 0.5)),
            ]

            # Simulate: bullish CRT → check if next 40 bars go up TP=atr*2 or down SL=atr
            close = closes[i]
            tp = close + atr * 2.0
            sl = close - atr * 1.0
            label = None  # timeout → excluded (ambiguous gradient)
            for j in range(i + 1, min(i + MAX_FWD + 1, n)):
                if highs[j] >= tp:
                    label = 1.0; break
                if lows[j] <= sl:
                    label = 0.0; break

            if label is None:
                continue  # drop timeouts — no clear win/loss signal

            X.append(feat)
            y.append(label)

    print(f"  Dataset: {len(X)} samples from {len(csv_paths)} CSV(s)")
    return X, y


# ── Training loop ──────────────────────────────────────────────────────────────

def train(
    X: list[list[float]],
    y: list[float],
    epochs: int = 100,
    lr: float = 0.005,
    seed: int = 42,
) -> dict:
    if not X:
        raise ValueError("Empty dataset — no training samples found.")

    rng = random.Random(seed)
    nprng = np.random.RandomState(seed)

    # Xavier init
    def _xavier(fan_in, fan_out):
        lim = math.sqrt(6.0 / (fan_in + fan_out))
        return [[rng.uniform(-lim, lim) for _ in range(fan_in)] for _ in range(fan_out)]

    w1 = _xavier(IN_DIM, H1); b1 = [0.0] * H1
    w2 = _xavier(H1, H2);     b2 = [0.0] * H2
    wo = _xavier(H2, OUT);    bo = [0.0] * OUT

    n = len(X)
    indices = list(range(n))
    best_loss = float("inf")
    patience_count = 0
    PATIENCE = 20  # stop if no improvement for 20 epochs

    for epoch in range(1, epochs + 1):
        rng.shuffle(indices)
        total_loss = 0.0

        for idx in indices:
            xi, yi = X[idx], y[idx]
            h1, h2, pred = _forward(xi, w1, b1, w2, b2, wo, bo)
            loss = (pred - yi) ** 2
            total_loss += loss

            # Output layer grad (BCE-style: d(sigmoid)/d(z) = pred*(1-pred))
            d_out = _mse_grad(pred, yi) * pred * (1.0 - pred)
            for j in range(H2):
                wo[0][j] -= lr * d_out * h2[j]
            bo[0]     -= lr * d_out

            # H2 grad
            d_h2 = [d_out * wo[0][j] * (1.0 if h2[j] > 0 else 0.0) for j in range(H2)]
            for j in range(H2):
                for k in range(H1):
                    w2[j][k] -= lr * d_h2[j] * h1[k]
                b2[j] -= lr * d_h2[j]

            # H1 grad
            d_h1 = [
                sum(d_h2[j] * w2[j][k] for j in range(H2)) * (1.0 if h1[k] > 0 else 0.0)
                for k in range(H1)
            ]
            for k in range(H1):
                for m in range(IN_DIM):
                    w1[k][m] -= lr * d_h1[k] * xi[m]
                b1[k] -= lr * d_h1[k]

        mse = total_loss / n
        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{epochs}  MSE={mse:.4f}")

        # Early stopping
        if mse < best_loss - 1e-5:
            best_loss = mse
            patience_count = 0
        else:
            patience_count += 1
            if patience_count >= PATIENCE:
                print(f"  Early stop at epoch {epoch} (no improvement for {PATIENCE} epochs)")
                break

    return {
        "schema":       "legacy_6input",
        "architecture": f"{IN_DIM}->{H1}->{H2}->{OUT}",
        "trained_on":   n,
        "epochs":       epochs,
        "feature_order": FEATURE_KEYS,
        "layer1_w": w1, "layer1_b": b1,
        "layer2_w": w2, "layer2_b": b2,
        "out_w":    wo, "out_b":    bo,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Train model.json for bitnet_score()")
    parser.add_argument("--csv", nargs="+",
                        default=["data/EURUSD_M15.csv",
                                 "data/GBPUSD_M15.csv",
                                 "data/AUDUSD_M15.csv"])
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--lr",     type=float, default=0.001)
    parser.add_argument("--out",    default="model.json")
    args = parser.parse_args()

    print(f"\nBitNet Training — {IN_DIM}->{H1}->{H2}->{OUT}")
    print(f"CSVs: {args.csv}")

    X, y = build_dataset(args.csv)
    if not X:
        print("ERROR: No training samples — check CSV paths.")
        sys.exit(1)

    # Balance classes by oversampling wins to match loss count
    wins   = [(xi, yi) for xi, yi in zip(X, y) if yi == 1.0]
    losses = [(xi, yi) for xi, yi in zip(X, y) if yi == 0.0]
    print(f"  Class split — wins: {len(wins)}, losses: {len(losses)}")
    if wins and losses:
        import random as _rnd
        _rnd.seed(42)
        if len(wins) < len(losses):
            wins = [_rnd.choice(wins) for _ in range(len(losses))]  # oversample wins
        else:
            losses = [_rnd.choice(losses) for _ in range(len(wins))]
        balanced = wins + losses
        _rnd.shuffle(balanced)
        X = [b[0] for b in balanced]
        y = [b[1] for b in balanced]
        print(f"  Balanced dataset: {len(X)} samples (50/50)")

    # Normalize features
    arr = np.array(X, dtype=np.float64)
    means = arr.mean(axis=0)
    stds  = arr.std(axis=0) + 1e-8
    X_norm = ((arr - means) / stds).tolist()

    print(f"\nTraining ({args.epochs} epochs, lr={args.lr})...")
    model = train(X_norm, y, epochs=args.epochs, lr=args.lr)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(model, indent=2))
    print(f"\nSaved: {out_path}  ({len(X)} samples, {args.epochs} epochs)")
    print("Run 'python scripts/export/generate_bootstrap_model.py' to reset to random weights.\n")


if __name__ == "__main__":
    main()
