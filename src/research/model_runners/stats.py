"""Pure summary stats over collected numeric arrays (no fill / no imputation)."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np


def array_stats(values: Sequence[float]) -> dict[str, Any]:
    a = np.asarray(list(values), dtype=np.float64)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return {
            "n": int(a.size),
            "n_finite": 0,
            "n_non_finite": int(a.size),
        }
    return {
        "n": int(a.size),
        "n_finite": int(finite.size),
        "n_non_finite": int(a.size - finite.size),
        "mean": float(finite.mean()),
        "std": float(finite.std()),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "p50": float(np.percentile(finite, 50)),
    }
