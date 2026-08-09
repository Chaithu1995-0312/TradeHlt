"""IC-002 / RC-005 frozen schema — must match h-ic002 experiment definition JSON."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# Locked to docs/research-readiness/h-ic002-entry-evolution-experiment-definition.json
N_GRID: tuple[int, ...] = (4, 8, 16)

TRAJECTORY_FEATURE_IDS: tuple[str, ...] = (
    "body_ratio",
    "disp_strength",
    "retest_depth",
    "rsi_14",
    "atr",
    "volatility_ratio",
    "volume_ratio",
    "trend_bias",
    "momentum_score",
    "break_of_structure",
    "higher_high",
    "lower_low",
    "sweep_detected",
    "liquidity_distance",
    "candles_since_retest",
)

D: int = len(TRAJECTORY_FEATURE_IDS)
assert D == 15

EPS: float = 1e-9

LOGISTIC_C_IS_GRID: tuple[float, ...] = (0.1, 1.0, 10.0)
OOS_SPLIT: float = 0.3
MIN_N_OOS: int = 500
N_PERM: int = 500
AUC_PATH_MIN: float = 0.55
DELTA_AUC_MIN: float = 0.03
SHUFFLE_PATH_GAP_MIN: float = 0.02
SEED: int = 42


@dataclass(frozen=True)
class TrajectoryBatch:
    """In-memory batch for one N."""

    N: int
    feature_ids: tuple[str, ...]
    trade_ids: list[str]
    entry_indices: list[int]
    timestamps: list[str]
    families: list[str]
    directions: list[str]
    y: list[int]  # 1 = TP_HIT else 0
    outcomes: list[str]
    # shape (n_trades, N, D) path-relative
    Z: "object"  # numpy ndarray
    # shape (n_trades, D) entry snapshot (raw features at t=0)
    X0: "object"


def path_relative_row(x_k: Sequence[float], x_0: Sequence[float]) -> list[float]:
    """z_d = (x_k_d - x_0_d) / max(|x_0_d|, eps)."""
    out: list[float] = []
    for a, b in zip(x_k, x_0):
        scale = abs(float(b))
        if scale < EPS:
            scale = EPS
        out.append((float(a) - float(b)) / scale)
    return out


def flatten_Z(Z_row) -> list[float]:
    """M-FLAT: row-major N*D."""
    return [float(v) for step in Z_row for v in step]


def static_baseline_vector(x0, N: int) -> list[float]:
    """C-STATIC: entry vector repeated N times then flattened (same length as path)."""
    x0 = [float(v) for v in x0]
    # path-relative of constant path is zeros — use raw x0 repeated for a real baseline signal
    return x0 * N
