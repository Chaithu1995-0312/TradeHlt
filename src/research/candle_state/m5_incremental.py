"""m5_incremental.py — Program-9 Stage-1 kernels: M5-base keys + the incremental gate.

Program 9 (docs/research/preregistration-program-9.md) asks two Stage-1 questions:

  Gate A (raw)         — does the M5-base conjunction K5 = "M5=…|M15=…|H1=…|H4=…" carry
                         information about the forward target? (Program-4 machinery,
                         wall-clock-rescaled thresholds.)
  Gate B (incremental) — does K5 carry information BEYOND the coarse key K15 (= K5 with
                         the M5 component stripped — the M15-base information causally
                         available at the same M5 instant)?

Gate B is the F-043 lesson made structural: a statistically real signal that is fully
explained by already-known information earns the first-class FAIL verdict
`M15_REDUNDANT`, never a PASS. The null is a WITHIN-K15-CELL permutation of the target:
it preserves every K15-level association exactly and destroys only the M5 refinement —
conditional-MI significance by stratified permutation (mirrors the Program-4b/F-043
within-tercile 5th control pattern).

Pure & deterministic: numpy + the audited IG/permutation primitives
(`conditional_entropy_grid.partition_stat` / `seed_for`, same as `info_robustness`).
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from research.conditional_entropy_grid import (
    _entropy_bits,
    _partition_entropy_from_ids,
    seed_for,
)
from research.candle_state.info_robustness import SIGNIFICANCE_ALPHA

# ── FROZEN Program-9 constants (wall-clock-matched to Program 4's M15 values;
#    mirrored in docs/research/preregistration-program-9.md — no post-hoc changes) ──
M5_BASE_LABEL = "M5"
M5_RULES = ("M15", "H1", "H4")
M5_HORIZONS = [3, 6, 12, 24]        # 15m / 30m / 1h / 2h at M5
M5_K_DECISION = 12                  # decision horizon = 1 hour (Program 4: k=4 M15 bars)
M5_HALF_LIFE_MIN_BARS = 12          # >= 1 hour     (Program 4: >= 4 M15 bars)
M5_ENTRY_TTL = 12                   # Stage-2 straddle fill window = 1 hour
M5_MAX_FORWARD = 120                # Stage-2 horizon = 10 hours (Program 4: 40 M15 bars)

# Verdict vocabulary (D6): M15_REDUNDANT is a first-class Stage-1 FAIL.
VERDICT_PASS = "PASS"
VERDICT_M15_REDUNDANT = "M15_REDUNDANT"
VERDICT_FAIL = "FAIL"


def coarse_key(key: str) -> str:
    """Project a fine key "M5=…|M15=…|H1=…|H4=…" onto its coarse remainder
    "M15=…|H1=…|H4=…" (drop the leading base component)."""
    return key.split("|", 1)[1] if "|" in key else ""


def within_coarse_permutation_p(
    cells_fine: Sequence[str],
    cells_coarse: Sequence[str],
    target: np.ndarray,
    valid: np.ndarray,
    *,
    n_permutations: int,
    name: str,
) -> float:
    """Add-one p-value of IG(target | fine) under the WITHIN-coarse-cell shuffle null.

    Shuffling the target only among bars sharing the same coarse cell preserves every
    coarse-level association byte-exactly and destroys only the fine refinement, so a
    small p means the fine partition carries information the coarse one does not
    (conditional-MI significance by stratified permutation). Seeded via `seed_for(name)`
    — deterministic across runs. Returns 1.0 on degenerate input.
    """
    fine = [c for c, v in zip(cells_fine, valid.tolist()) if v]
    coarse = [c for c, v in zip(cells_coarse, valid.tolist()) if v]
    ups = np.asarray([int(t) for t, v in zip(target.tolist(), valid.tolist()) if v],
                     dtype=np.int64)
    total = int(ups.size)
    if total == 0 or n_permutations <= 0:
        return 1.0

    # Fine partition as contiguous ids (the audited `permutation_pvalue` pattern —
    # `_partition_entropy_from_ids` is vectorised; string recounts per draw would be
    # O(n) Python per permutation). Cell memberships never change under the shuffle,
    # so per-cell totals and H_unconditional are computed once.
    f_uniq = sorted(set(fine))
    f_map = {c: i for i, c in enumerate(f_uniq)}
    fids = np.fromiter((f_map[c] for c in fine), dtype=np.int64, count=total)
    fk = len(f_uniq)
    f_cell_total = np.bincount(fids, minlength=fk).astype(float)
    total_up = int(ups.sum())
    h_uncond = _entropy_bits([[total_up, total - total_up]])
    up_f = ups.astype(float)
    ig_obs = h_uncond - _partition_entropy_from_ids(fids, up_f, f_cell_total, fk)
    if ig_obs != ig_obs:                       # NaN-guard (degenerate partition)
        return 1.0

    # Integer group ids for the coarse strata (sorted-unique => deterministic).
    g_uniq = sorted(set(coarse))
    g_map = {c: i for i, c in enumerate(g_uniq)}
    gids = np.fromiter((g_map[c] for c in coarse), dtype=np.int64, count=total)
    # Positions grouped by stratum, original order within each stratum.
    group_order = np.argsort(gids, kind="stable")

    rng = np.random.default_rng(seed_for(name))
    ge = 0
    perm = np.empty_like(up_f)
    for _ in range(n_permutations):
        # Random order WITHIN each stratum: sort by (gid, random key). Assigning the
        # values at `perm_order` onto the positions at `group_order` shuffles the
        # target uniformly within every coarse cell and never across cells.
        r = rng.random(total)
        perm_order = np.lexsort((r, gids))
        perm[group_order] = up_f[perm_order]
        ig = h_uncond - _partition_entropy_from_ids(fids, perm, f_cell_total, fk)
        if ig >= ig_obs:
            ge += 1
    return (ge + 1) / (n_permutations + 1)


def stage1_verdict(gate_a_pass: bool, incremental_p: float,
                   *, alpha: float = SIGNIFICANCE_ALPHA) -> str:
    """Combine Gate A (raw information) and Gate B (incremental beyond M15) into the
    frozen Stage-1 verdict: PASS / M15_REDUNDANT / FAIL (pre-reg D6)."""
    if not gate_a_pass:
        return VERDICT_FAIL
    if incremental_p > alpha:
        return VERDICT_M15_REDUNDANT
    return VERDICT_PASS
