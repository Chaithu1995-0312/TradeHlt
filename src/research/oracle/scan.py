"""scan.py — effect sizes, controls and partitioning for the oracle pattern search.

THE ONE STATISTICAL FACT THAT GOVERNS THIS FILE
-----------------------------------------------
Oracle labels OVERLAP. A label at bar t and a label at bar t+1 share 39 of their 40
forward bars, so 47,000 rows are nowhere near 47,000 independent observations — the
effective count is about bars/horizon, roughly 1,180 per direction. Every interval here
is therefore a BLOCK bootstrap over `_pos // horizon`, never an i.i.d. one. Using a naive
standard error would overstate confidence by roughly sqrt(horizon) and would manufacture
"significant" patterns out of nothing. This is the single largest false-discovery risk in
the program and it is handled at the lowest level so no caller can forget it.

WHAT A CELL MUST BEAT
---------------------
Not zero. A cell must beat the DIRECTION-MATCHED base rate (long and short have
different base rates because the instrument drifts), and it must beat the `long_only`
control, which on a corpus with a strong up-drift is the binding one. A pattern that
merely has positive expectancy while losing to passive long exposure is drift, not
information.

Research-only. Produces numbers, never verdicts: promotion, fusion weight and G001 are
all out of scope (Authority Ladder).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_HORIZON = 40


# ─────────────────────────────────────────────────────────────────────────────
# Partitioning
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Partition:
    train: pd.DataFrame
    test_stride: pd.DataFrame
    meta: dict


def partition(
    df: pd.DataFrame,
    *,
    oos_fraction: float = 0.2,
    embargo_bars: int = 96,
    horizon: int = DEFAULT_HORIZON,
) -> Partition:
    """Chronological split with an embargo, a purge, and a non-overlapping test set.

    * TRAIN is the first (1 - oos_fraction) of bars.
    * A row is PURGED from train when its forward horizon reaches into the test region,
      which is what stops a train label from being partly computed on test bars.
    * EMBARGO drops a further `embargo_bars` between the two.
    * TEST_STRIDE keeps every `horizon`-th bar of the test region, so no two test labels
      share a forward bar. This is the only surface a forward claim may be evaluated on.
    """
    positions = np.sort(df["_pos"].unique())
    n = len(positions)
    cut_idx = int(n * (1.0 - oos_fraction))
    test_start_pos = int(positions[cut_idx])

    train_cutoff = test_start_pos - embargo_bars - horizon
    train = df[df["_pos"] < train_cutoff].copy()

    test_positions = positions[positions >= test_start_pos]
    stride_positions = set(test_positions[::horizon].tolist())
    test_stride = df[df["_pos"].isin(stride_positions)].copy()

    meta = {
        "bars_total": int(n),
        "test_start_pos": test_start_pos,
        "train_cutoff_pos": int(train_cutoff),
        "embargo_bars": embargo_bars,
        "purge_horizon": horizon,
        "train_bars": int(train["_pos"].nunique()),
        "test_bars_dense": int(len(test_positions)),
        "test_bars_stride": int(len(stride_positions)),
        "stride": horizon,
        "oos_fraction": oos_fraction,
    }
    return Partition(train=train, test_stride=test_stride, meta=meta)


def effective_n(df: pd.DataFrame, *, horizon: int = DEFAULT_HORIZON) -> int:
    """Independent-observation count: distinct non-overlapping blocks, not row count."""
    if len(df) == 0:
        return 0
    return int(pd.unique(df["_pos"] // horizon).size)


# ─────────────────────────────────────────────────────────────────────────────
# Block bootstrap
# ─────────────────────────────────────────────────────────────────────────────
def block_bootstrap_mean_ci(
    values: np.ndarray,
    blocks: np.ndarray,
    *,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 20260820,
) -> tuple[float, float, float]:
    """(mean, lo, hi) of `values`, resampling whole BLOCKS with replacement.

    Blocks, not rows: overlapping labels inside a block are not independent of each
    other, so resampling rows would treat one piece of information as `horizon` pieces.
    """
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return float("nan"), float("nan"), float("nan")
    mean = float(values.mean())
    uniq = np.unique(blocks)
    if uniq.size < 2:
        return mean, float("nan"), float("nan")

    order = np.argsort(blocks, kind="stable")
    sorted_blocks = blocks[order]
    sorted_vals = values[order]
    starts = np.searchsorted(sorted_blocks, uniq, side="left")
    ends = np.searchsorted(sorted_blocks, uniq, side="right")
    sums = np.add.reduceat(sorted_vals, starts)
    counts = (ends - starts).astype(float)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, uniq.size, size=(n_boot, uniq.size))
    boot_sums = sums[idx].sum(axis=1)
    boot_counts = counts[idx].sum(axis=1)
    boot_means = np.divide(boot_sums, boot_counts, out=np.full(n_boot, np.nan),
                           where=boot_counts > 0)
    lo, hi = np.nanpercentile(boot_means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return mean, float(lo), float(hi)


def _blocks_of(df: pd.DataFrame, horizon: int) -> np.ndarray:
    return (df["_pos"].to_numpy() // horizon).astype(np.int64)


# ─────────────────────────────────────────────────────────────────────────────
# Effect sizes
# ─────────────────────────────────────────────────────────────────────────────
def rank_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """AUC of `scores` separating `labels` (1/0), by the rank identity. 0.5 = nothing.

    Ties get midranks, so a constant feature scores exactly 0.5 rather than an artefact.
    """
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels).astype(int)
    n_pos = int(labels.sum())
    n_neg = int(labels.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="stable")
    ranks = np.empty(scores.size, dtype=float)
    ranks[order] = np.arange(1, scores.size + 1, dtype=float)
    # midranks for ties
    s = scores[order]
    i = 0
    while i < s.size:
        j = i
        while j + 1 < s.size and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return float((ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def l1_marginal(
    df: pd.DataFrame,
    feature_cols: list[str],
    *,
    y_binary: str = "y_win",
    y_value: str = "y_R_net",
    horizon: int = DEFAULT_HORIZON,
    n_boot: int = 1000,
    seed: int = 20260820,
) -> pd.DataFrame:
    """Per-feature separation of profitable from unprofitable bars.

    `auc` answers "does this feature order the outcome at all"; `top_decile_*` answers
    "and is that ordering worth anything", which are different questions — a feature can
    order weakly across the whole range yet carry the entire effect in one tail.
    """
    labels = df[y_binary].to_numpy().astype(int)
    values = df[y_value].to_numpy(dtype=float)
    blocks = _blocks_of(df, horizon)
    base_mean, base_lo, base_hi = block_bootstrap_mean_ci(
        values, blocks, n_boot=n_boot, seed=seed)

    rows = []
    for col in feature_cols:
        x = df[col].to_numpy(dtype=float)
        finite = np.isfinite(x)
        if finite.sum() < 100 or np.unique(x[finite]).size < 3:
            rows.append({"feature": col, "auc": np.nan, "note": "degenerate_or_sparse"})
            continue
        auc = rank_auc(x[finite], labels[finite])
        thr = np.nanpercentile(x[finite], 90)
        top = finite & (x >= thr)
        bot = finite & (x <= np.nanpercentile(x[finite], 10))
        top_mean, top_lo, top_hi = block_bootstrap_mean_ci(
            values[top], blocks[top], n_boot=n_boot, seed=seed)
        bot_mean, _, _ = block_bootstrap_mean_ci(
            values[bot], blocks[bot], n_boot=n_boot, seed=seed)
        rows.append({
            "feature": col,
            "auc": round(auc, 5),
            "auc_abs_lift": round(abs(auc - 0.5), 5),
            "n": int(finite.sum()),
            "eff_n": int(np.unique(blocks[finite]).size),
            "top_decile_mean_R": round(top_mean, 5),
            "top_decile_lo": round(top_lo, 5),
            "top_decile_hi": round(top_hi, 5),
            "bottom_decile_mean_R": round(bot_mean, 5),
            "decile_spread_R": round(top_mean - bot_mean, 5),
            "base_mean_R": round(base_mean, 5),
            "top_beats_base": bool(top_lo > base_mean),
            "note": "",
        })
    out = pd.DataFrame(rows)
    out.attrs["base_mean_R"] = base_mean
    out.attrs["base_ci"] = (base_lo, base_hi)
    return out.sort_values("auc_abs_lift", ascending=False, na_position="last")


def l2_state_cells(
    df: pd.DataFrame,
    state_cols: list[str],
    *,
    y_binary: str = "y_win",
    y_value: str = "y_R_net",
    horizon: int = DEFAULT_HORIZON,
    min_eff_n: int = 30,
    n_boot: int = 1000,
    seed: int = 20260820,
) -> pd.DataFrame:
    """One row per (state family, cell): rate, expectancy, and lift over the base rate.

    Cells below `min_eff_n` independent blocks are kept but flagged INSUFFICIENT. They
    are not evidence of absence; dropping them silently would be the same mistake as
    reporting them as findings.
    """
    values = df[y_value].to_numpy(dtype=float)
    blocks = _blocks_of(df, horizon)
    base_mean, _, _ = block_bootstrap_mean_ci(values, blocks, n_boot=n_boot, seed=seed)
    base_rate = float(df[y_binary].mean())

    rows = []
    for col in state_cols:
        series = df[col]
        for cell, idx in series.groupby(series, dropna=False).groups.items():
            mask = df.index.isin(idx)
            v, b = values[mask], blocks[mask]
            eff = int(np.unique(b).size) if b.size else 0
            m, lo, hi = block_bootstrap_mean_ci(v, b, n_boot=n_boot, seed=seed)
            rows.append({
                "family": col,
                "cell": str(cell),
                "n": int(mask.sum()),
                "eff_n": eff,
                "win_rate": round(float(df.loc[mask, y_binary].mean()), 5) if mask.sum() else np.nan,
                "base_win_rate": round(base_rate, 5),
                "mean_R": round(m, 5),
                "ci_lo": round(lo, 5),
                "ci_hi": round(hi, 5),
                "base_mean_R": round(base_mean, 5),
                "lift_R": round(m - base_mean, 5),
                "beats_base": bool(lo > base_mean),
                "beats_zero": bool(lo > 0.0),
                "status": "OK" if eff >= min_eff_n else "INSUFFICIENT",
            })
    return pd.DataFrame(rows).sort_values("lift_R", ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
# L3 conjunctions (apriori-pruned)
# ─────────────────────────────────────────────────────────────────────────────
def l3_conjunctions(
    df: pd.DataFrame,
    state_cols: list[str],
    *,
    y_value: str = "y_R_net",
    y_binary: str = "y_win",
    horizon: int = DEFAULT_HORIZON,
    max_depth: int = 3,
    min_eff_n: int = 30,
    n_boot: int = 500,
    seed: int = 20260820,
    top_k: int = 40,
) -> pd.DataFrame:
    """Conjunctions of declared state literals, pruned by minimum EFFECTIVE support.

    Support is counted in independent blocks, not rows — a conjunction holding on 400
    consecutive bars is one piece of evidence, not 400. Pruning on effective support is
    what stops the search from drowning in patterns that are a single afternoon.
    """
    values = df[y_value].to_numpy(dtype=float)
    blocks = _blocks_of(df, horizon)
    base_mean, _, _ = block_bootstrap_mean_ci(values, blocks, n_boot=n_boot, seed=seed)

    literals: list[tuple[str, np.ndarray]] = []
    for col in state_cols:
        s = df[col]
        for cell in s.dropna().unique():
            mask = (s == cell).to_numpy()
            if np.unique(blocks[mask]).size >= min_eff_n:
                literals.append((f"{col}={cell}", mask))

    frontier = [((name,), mask) for name, mask in literals]
    results = []
    for depth in range(1, max_depth + 1):
        scored = []
        for names, mask in frontier:
            v, b = values[mask], blocks[mask]
            eff = int(np.unique(b).size)
            if eff < min_eff_n:
                continue
            m, lo, hi = block_bootstrap_mean_ci(v, b, n_boot=n_boot, seed=seed)
            scored.append({
                "depth": depth,
                "pattern": " AND ".join(names),
                "n": int(mask.sum()),
                "eff_n": eff,
                "mean_R": round(m, 5),
                "ci_lo": round(lo, 5),
                "ci_hi": round(hi, 5),
                "win_rate": round(float(df.loc[mask, y_binary].mean()), 5),
                "lift_R": round(m - base_mean, 5),
                "beats_base": bool(lo > base_mean),
                "beats_zero": bool(lo > 0.0),
            })
        results.extend(scored)
        if depth == max_depth:
            break
        # Extend only surviving conjunctions, and only with literals not already used.
        nxt = []
        seen = set()
        for names, mask in frontier:
            if np.unique(blocks[mask]).size < min_eff_n:
                continue
            used_families = {n.split("=")[0] for n in names}
            for lname, lmask in literals:
                if lname.split("=")[0] in used_families:
                    continue
                combo = tuple(sorted(names + (lname,)))
                if combo in seen:
                    continue
                m2 = mask & lmask
                if np.unique(blocks[m2]).size < min_eff_n:
                    continue
                seen.add(combo)
                nxt.append((combo, m2))
        frontier = nxt
        if not frontier:
            break

    out = pd.DataFrame(results)
    total_scored = int(len(out))
    n_beat_zero = int(out["beats_zero"].sum()) if total_scored else 0
    n_beat_base = int(out["beats_base"].sum()) if total_scored else 0
    if total_scored:
        out = out.sort_values("lift_R", ascending=False).head(top_k)
    out.attrs["base_mean_R"] = base_mean
    out.attrs["total_scored"] = total_scored
    out.attrs["total_beating_zero"] = n_beat_zero
    out.attrs["total_beating_base"] = n_beat_base
    # The chance expectation applies to BEATING THE BASE, not to beating zero. Under the
    # null that a conjunction is just an arbitrary subset of bars, its expected mean is
    # the base rate, so ~2.5% of scored patterns clear the base on the upper tail of a
    # 95% interval. Comparing the beats-ZERO count against that same 2.5% would be wrong
    # whenever the base is far from zero — here the base is about -0.29R, so almost
    # nothing clears zero regardless of whether any signal exists, and a small count is
    # not evidence of a strong null.
    out.attrs["expected_beating_base_by_chance"] = round(0.025 * total_scored, 1)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Controls
# ─────────────────────────────────────────────────────────────────────────────
def controls(
    df: pd.DataFrame,
    *,
    y_value: str = "y_R_net",
    horizon: int = DEFAULT_HORIZON,
    n_boot: int = 1000,
    seed: int = 20260820,
) -> dict:
    """The benchmarks a candidate pattern has to clear.

    `long_only` is the binding one on a drifting instrument: a directional pattern that
    beats zero but loses to passive long exposure has found the drift, not information.
    `shuffled` must land on the base rate — if it does not, the harness itself is
    manufacturing signal and nothing downstream can be believed.
    """
    rng = np.random.default_rng(seed)
    blocks = _blocks_of(df, horizon)
    out = {}

    v = df[y_value].to_numpy(dtype=float)
    m, lo, hi = block_bootstrap_mean_ci(v, blocks, n_boot=n_boot, seed=seed)
    out["all_units"] = {"n": int(len(df)), "eff_n": int(np.unique(blocks).size),
                        "mean_R": round(m, 5), "ci_lo": round(lo, 5), "ci_hi": round(hi, 5)}

    for direction in ("long", "short"):
        mask = (df["direction"] == direction).to_numpy()
        if mask.sum() == 0:
            continue
        m, lo, hi = block_bootstrap_mean_ci(v[mask], blocks[mask], n_boot=n_boot, seed=seed)
        out[f"{direction}_only"] = {
            "n": int(mask.sum()), "eff_n": int(np.unique(blocks[mask]).size),
            "mean_R": round(m, 5), "ci_lo": round(lo, 5), "ci_hi": round(hi, 5)}

    # random_entry: a same-sized draw of bars, direction mix preserved.
    n_draw = min(len(df), max(200, int(len(df) * 0.1)))
    pick = rng.choice(len(df), size=n_draw, replace=False)
    m, lo, hi = block_bootstrap_mean_ci(v[pick], blocks[pick], n_boot=n_boot, seed=seed)
    out["random_entry"] = {"n": int(n_draw), "mean_R": round(m, 5),
                           "ci_lo": round(lo, 5), "ci_hi": round(hi, 5)}

    shuffled = v.copy()
    rng.shuffle(shuffled)
    m, lo, hi = block_bootstrap_mean_ci(shuffled, blocks, n_boot=n_boot, seed=seed)
    out["shuffled_label"] = {"mean_R": round(m, 5), "ci_lo": round(lo, 5),
                             "ci_hi": round(hi, 5)}
    return out


def state_columns(df: pd.DataFrame) -> list[str]:
    """Every declared state family carried on the bar matrix."""
    cols = [c for c in df.columns if c.startswith("state__")]
    for extra in ("crt_state_resolved", "parent_track_state", "parent_bias", "htf_state",
                  "objective_status", "candle_direction", "candle_vol", "candle_structure",
                  "candle_trend", "regime_label", "trade_intent"):
        if extra in df.columns:
            cols.append(extra)
    return cols


# ─────────────────────────────────────────────────────────────────────────────
# Permutation null for the conjunction search
# ─────────────────────────────────────────────────────────────────────────────
def l3_permutation_null(
    df: pd.DataFrame,
    state_cols: list[str],
    *,
    y_value: str = "y_R_net",
    y_binary: str = "y_win",
    horizon: int = DEFAULT_HORIZON,
    max_depth: int = 3,
    min_eff_n: int = 30,
    n_perm: int = 3,
    n_boot: int = 200,
    seed: int = 20260820,
) -> dict:
    """How many conjunctions clear the base when the labels carry NO information.

    The analytic "2.5% of scored" expectation assumes independent tests. Conjunctions
    built from a few dozen literals overlap heavily, so that expectation is wrong and
    can be wrong by a large factor in either direction. This measures the null instead
    of assuming it: labels are permuted WHOLE BLOCKS AT A TIME, which destroys any
    relationship to the states while preserving the within-block autocorrelation that
    makes the intervals what they are. Shuffling rows would break that structure and
    produce an optimistic null.

    Returns the real count alongside the permuted counts, which is the comparison that
    licenses (or refuses) a statement about conditional structure.
    """
    rng = np.random.default_rng(seed)
    blocks = _blocks_of(df, horizon)
    uniq = np.unique(blocks)

    real = l3_conjunctions(df, state_cols, y_value=y_value, y_binary=y_binary,
                           horizon=horizon, max_depth=max_depth, min_eff_n=min_eff_n,
                           n_boot=n_boot, seed=seed, top_k=1)
    real_scored = int(real.attrs.get("total_scored", 0))
    real_base = int(real.attrs.get("total_beating_base", 0))
    real_zero = int(real.attrs.get("total_beating_zero", 0))

    perm_base, perm_zero, perm_scored = [], [], []
    for i in range(n_perm):
        shuffled_blocks = rng.permutation(uniq)
        mapping = dict(zip(uniq, shuffled_blocks))
        # Reassign each row's LABEL to the label of a randomly matched block, keeping
        # block-internal ordering intact.
        order = np.argsort([mapping[b] for b in blocks], kind="stable")
        perm_df = df.copy()
        perm_df[y_value] = df[y_value].to_numpy()[order]
        perm_df[y_binary] = df[y_binary].to_numpy()[order]
        out = l3_conjunctions(perm_df, state_cols, y_value=y_value, y_binary=y_binary,
                              horizon=horizon, max_depth=max_depth, min_eff_n=min_eff_n,
                              n_boot=n_boot, seed=seed + 1 + i, top_k=1)
        perm_scored.append(int(out.attrs.get("total_scored", 0)))
        perm_base.append(int(out.attrs.get("total_beating_base", 0)))
        perm_zero.append(int(out.attrs.get("total_beating_zero", 0)))

    return {
        "n_perm": n_perm,
        "real_scored": real_scored,
        "real_beating_base": real_base,
        "real_beating_zero": real_zero,
        "perm_scored": perm_scored,
        "perm_beating_base": perm_base,
        "perm_beating_zero": perm_zero,
        "perm_beating_base_mean": round(float(np.mean(perm_base)), 1) if perm_base else None,
        "perm_beating_zero_mean": round(float(np.mean(perm_zero)), 1) if perm_zero else None,
        "excess_ratio_base": (
            round(real_base / np.mean(perm_base), 2)
            if perm_base and np.mean(perm_base) > 0 else None),
        "interpretation": (
            "A real count comfortably above the permuted counts means the declared state "
            "vocabulary carries conditional information about the outcome. It says nothing "
            "about whether that information is economically consumable — that is the "
            "separate beats-ZERO question."),
    }
