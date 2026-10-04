"""bootstrap.py — deterministic percentile bootstrap confidence interval.

The research platform's uncertainty machinery is otherwise permutation + Benjamini-Hochberg
(qualification.py). This adds the one missing primitive: a confidence interval on a cell MEAN,
for the DESCRIPTIVE Historical-Statistics layer (shape_statistics.py). It is a *description*
of sampling uncertainty, never a significance test and never an edge claim.

ISOLATION: numpy + stdlib only; no live-spine imports, no research.contracts coupling.
DESCRIPTIVE ONLY (§6.5 Authority-Ladder Level <= 1) — a CI narrows or widens a description; it
grants no authority.

DETERMINISM: the tuple (values, n_boot, alpha, seed) fully determines (lo, hi). The RNG is a
seeded numpy Generator drawn in a fixed order, so verdicts are byte-reproducible across runs and
machines. `seed_from_key` mirrors qualification._seed_for (sha256[:8] -> int) so callers can
derive a stable per-cell seed from the cell identity.

CONTRACT (no defaults, no fallbacks — same discipline as shape_statistics.py):
    n_boot, alpha, seed are REQUIRED. Empty input, n_boot <= 0, or alpha outside (0, 1) RAISE.
    n == 1 is well-defined and returns (v, v) (every resample is the single point).
"""
from __future__ import annotations

import hashlib

import numpy as np

BOOTSTRAP_METHOD_VERSION = "1.0"


def seed_from_key(key: str) -> int:
    """Stable 32-bit seed from a string key. Mirrors qualification._seed_for."""
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)


def bootstrap_ci(values, *, n_boot: int, alpha: float, seed: int) -> tuple[float, float]:
    """Percentile bootstrap CI for the MEAN of ``values`` at central (1 - alpha) coverage.

    Returns ``(lo, hi)`` — the ``100*alpha/2`` and ``100*(1 - alpha/2)`` percentiles of the
    bootstrap distribution of the resample mean (resampling with replacement, n draws per
    resample). ``lo <= hi`` always.

    Memory-bounded: resamples are drawn one at a time (O(n) transient), so a 20k-sample cell at
    n_boot=2000 stays cheap instead of materialising a 40M-element index matrix.
    """
    arr = np.asarray(values, dtype=np.float64).ravel()
    n = arr.size
    if n == 0:
        raise ValueError("bootstrap_ci: values is empty")
    if int(n_boot) <= 0:
        raise ValueError(f"bootstrap_ci: n_boot must be positive, got {n_boot}")
    if not (0.0 < float(alpha) < 1.0):
        raise ValueError(f"bootstrap_ci: alpha must be in (0, 1), got {alpha}")
    n_boot = int(n_boot)
    if n == 1:
        v = float(arr[0])
        return (v, v)

    rng = np.random.default_rng(seed)
    means = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        means[b] = arr[rng.integers(0, n, size=n)].mean()
    lo = float(np.percentile(means, 100.0 * (alpha / 2.0)))
    hi = float(np.percentile(means, 100.0 * (1.0 - alpha / 2.0)))
    return (lo, hi)
