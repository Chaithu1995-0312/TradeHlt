"""IC-003B frozen constants — match h-ic003b experiment definition."""
from __future__ import annotations

PRIMARY_N: tuple[int, ...] = (4, 16)
DIAGNOSTIC_N: tuple[int, ...] = (8,)
K_GRID: tuple[int, ...] = (4, 6, 8, 12)
OOS_SPLIT: float = 0.3
SEED: int = 42
N_INIT: int = 10
SILHOUETTE_SUBSAMPLE: int = 8000

# Arm S — same G1–G5 bar as IC-003 v1 (fair representation comparison)
G1_SSE_RATIO_MAX: float = 0.85
G2_SILHOUETTE_MIN: float = 0.05
G3_OOS_Z_MAX: float = 2.0
G4_MIN_N_IS: int = 50
G4_MIN_N_OOS: int = 20

# Arm T
DTW_CHANNELS: tuple[str, ...] = ("body_ratio", "disp_strength", "rsi_14")
DTW_RADIUS_FRAC: float = 0.2
DTW_IS_SUBSAMPLE_MAX: int = 3000
G1_T_RATIO_MAX: float = 0.85
G2_T_SILHOUETTE_MIN: float = 0.05

# Arm C
PCA_N_COMP: int = 4
CONTINUUM_CUMVAR_MIN: float = 0.50
CONTINUUM_MAX_SIL: float = 0.05

STATS_PER_DIM: tuple[str, ...] = (
    "mean",
    "std",
    "first",
    "last",
    "min",
    "max",
    "slope",
)
