"""IC-003 frozen constants — match h-ic003 experiment definition (v1 scientific bar).

G1 = 0.85 is the AUTHORITATIVE preregistered gate (v1).
Amendment A1 (G1→0.90) was executed historically but is SUPERSEDED for scientific
authority — see docs/research-readiness/ic-003-lessons-learned.md.
"""
from __future__ import annotations

PRIMARY_N: tuple[int, ...] = (4, 16)
DIAGNOSTIC_N: tuple[int, ...] = (8,)
K_GRID: tuple[int, ...] = (4, 6, 8, 12)
OOS_SPLIT: float = 0.3
SEED: int = 42
SILHOUETTE_SUBSAMPLE: int = 8000
N_INIT: int = 10

# v1 frozen scientific bar (authoritative)
G1_SSE_RATIO_MAX: float = 0.85
G2_SILHOUETTE_MIN: float = 0.05
G4_MIN_N_IS: int = 50
G4_MIN_N_OOS: int = 20
PURITY_DELTA_PP: float = 10.0
PURITY_MIN_N_OOS: int = 50

# Key dims for mean-path summary (names from IC-002 feature order)
KEY_FEATURE_NAMES: tuple[str, ...] = (
    "body_ratio",
    "disp_strength",
    "rsi_14",
    "atr",
)
