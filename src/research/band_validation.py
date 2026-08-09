"""band_validation.py — do candidate band thresholds correspond to STABLE BEHAVIORAL REGIMES?

WHY THIS EXISTS (user directive 2026-07-24)
    Quantile edges partition a continuous feature by FREQUENCY. Frequency is not meaning: a cut at
    the 20th percentile is arbitrary unless the market actually BEHAVES differently on either side.
    This module decides whether a candidate partition's semantic labels ("StrongBull" ...) are
    earned by behavior — before any ontology freeze. The existing volatility_regime terciles
    (0.33/0.66) were only ever certified for computational parity, never behaviorally; this does
    not repeat that.

THREE BEHAVIORAL BATTERIES (per candidate partition)
    1. PERSISTENCE  — do band labels persist (k-bar stickiness) far above an i.i.d.-shuffle null?
                      A regime is temporally coherent; bar-to-bar flicker is not a regime.
    2. TRANSITION   — is the between-band transition matrix ADJACENCY-DOMINANT (ordered), i.e. the
                      mean band-distance of transitions is smaller than a shuffle null? An ordered
                      partition of a continuous process rarely jumps StrongBull->StrongBear.
    3. FORWARD-RET  — are per-band forward returns MONOTONE in band index, with adjacent-band CIs
                      SEPARATED at each claimed boundary, and the ordering STABLE across years?
                      Overlapping CIs at a boundary ⇒ that boundary is behaviorally empty ⇒ MERGE.

AUTHORITY (§6.5 — read before citing)
    DESCRIPTIVE ONLY, Authority-Ladder Level <= 1. A PASS licenses the semantic LABEL (naming
    honesty) — it is NOT an economic-edge claim and grants NO trading/production authority. Whether
    a band carries tradeable edge is a separate question owned by the M4 qualification gate.

FORWARD RETURN IS DIRECTION-AGNOSTIC ATR-UNIT DRIFT (not forward_walk SL/TP)
    Bands are bar-level descriptions with no declared trade direction; simulating a directional
    trade would invent policy. We measure signed forward drift (close[t+h]-close[t])/ATR_abs[t] —
    the same rationale shape_statistics.py documents — from the RAW price path, never
    opportunities.jsonl (F-022).

CONTRACT (no defaults, no fallbacks)
    Battery parameters are a required BandValidationParams. Unlabeled bars carry the label None and
    are excluded from every battery (never coerced). All permutation nulls are seeded → deterministic.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

from research.measurement.bootstrap import bootstrap_ci

AUTHORITY = "DESCRIPTIVE_ONLY_LEVEL_1_SEMANTIC_LABEL_VALIDATION_NOT_AN_EDGE_CLAIM"


# ── candidate partition ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BandSpec:
    """An ordered partition: `edges` (strictly increasing) cut the feature into len(edges)+1
    labels, given in ascending band-index order (index 0 = below the lowest edge)."""
    name: str
    edges: tuple[float, ...]
    labels: tuple[str, ...]

    def __post_init__(self):
        if list(self.edges) != sorted(self.edges) or len(set(self.edges)) != len(self.edges):
            raise ValueError(f"{self.name}: edges must be strictly increasing/unique: {self.edges}")
        if len(self.labels) != len(self.edges) + 1:
            raise ValueError(
                f"{self.name}: need {len(self.edges) + 1} labels for {len(self.edges)} edges, "
                f"got {len(self.labels)}"
            )


@dataclass(frozen=True)
class BandValidationParams:
    """All battery knobs — required, no silent defaults."""
    k_persist: int              # persistence horizon (bars unchanged)
    fwd_horizon: int            # forward-return horizon for the verdict (bars)
    n_perm: int                 # permutation-null iterations
    alpha: float                # significance for persistence/transition nulls
    rho_min: float              # min Spearman(band_index, band_mean_fwd) for monotonicity
    stab_min: float             # min Spearman(year_a_means, year_b_means) for stability
    min_cell: int               # per-band min sample floor (below ⇒ band unusable for the verdict)
    ci: "object"                # BootstrapSpec (n_boot/alpha/seed) — from shape_statistics
    seed: int                   # base seed for permutation nulls


def _seed_from_key(key: str) -> int:
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)


# ── feature/outcome preparation (PIT feature, forward-drift label) ─────────────

def prepare_fm030_series(raw, *, horizon: int):
    """From an OHLCV frame, return (fm030_values, fwd_ret, years) aligned to pipeline rows.

    - fm030 = ema_spread/close (dimensionless, PIT — the bar's own value; parity-proven == FM-030).
    - fwd_ret = (close[p+horizon]-close[p]) / ATR_abs[p] in ATR units (the forward OUTCOME; nan at
      the tail or where ATR<=0). Direction-agnostic drift — never opportunities.jsonl (F-022).
    - years = calendar year at each bar (for the cross-year stability battery).
    The `_bv_pos` carried column joins pipeline rows back to raw positions (FeaturePipeline drops
    ~78 warmup rows and resets the index — the same gotcha shape_statistics.py guards).
    """
    import numpy as _np
    import pandas as _pd
    from features.feature_pipeline import FeaturePipeline  # deferred: heavy import

    work = raw.reset_index(drop=True).copy()
    n_raw = len(work)
    work["_bv_pos"] = _np.arange(n_raw, dtype=_np.int64)
    df, _vectors = FeaturePipeline(work).run()
    if "_bv_pos" not in df.columns:
        raise RuntimeError("_bv_pos did not survive FeaturePipeline.run() — refusing to guess join")
    pos = df["_bv_pos"].to_numpy(dtype=_np.int64)

    close = df["close"].to_numpy(dtype=_np.float64)
    fm030 = df["ema_spread"].to_numpy(dtype=_np.float64) / close
    atr_abs = df["atr"].to_numpy(dtype=_np.float64) * close
    raw_close = work["close"].to_numpy(dtype=_np.float64)
    years = _pd.to_datetime(work["timestamp"]).dt.year.to_numpy()[pos]

    fwd = _np.full(len(pos), _np.nan, dtype=_np.float64)
    for i in range(len(pos)):
        p = int(pos[i])
        a = atr_abs[i]
        if a > 0.0 and p + horizon < n_raw:
            fwd[i] = (raw_close[p + horizon] - raw_close[p]) / a
    return fm030, fwd, years


def assign_bands(values: Sequence[float], spec: BandSpec) -> list[str | None]:
    """Map each finite value to its band label; non-finite -> None (excluded downstream)."""
    v = np.asarray(values, dtype=np.float64)
    edges = np.asarray(spec.edges, dtype=np.float64)
    out: list[str | None] = []
    for x in v:
        if not np.isfinite(x):
            out.append(None)
            continue
        out.append(spec.labels[int(np.searchsorted(edges, x, side="right"))])
    return out


# ── vectorized statistics (int-coded labels; None/unknown -> -1) ───────────────
# These reproduce research.candle_state.transition_target.persistence_target and the
# process_characterization transition counts, but as O(n) numpy so the permutation nulls are
# tractable on 47k bars. Parity with the canonical primitive is pinned by test_band_validation.

def _codes(labels: Sequence[str | None], order: Sequence[str]) -> np.ndarray:
    idx = {lab: i for i, lab in enumerate(order)}
    return np.array([idx.get(x, -1) for x in labels], dtype=np.int64)


def _persistence_rate(codes: np.ndarray, k: int) -> tuple[float, int]:
    """Fraction of valid bars whose label is unchanged across the next k bars. Matches
    persistence_target: base bar must be labelled (code != -1); any future != base ⇒ not persistent."""
    n = codes.size
    if n <= k:
        return float("nan"), 0
    base = codes[:n - k]
    valid = base != -1
    unchanged = np.ones(n - k, dtype=bool)
    for j in range(1, k + 1):
        unchanged &= (codes[j:n - k + j] == base)
    m = int(valid.sum())
    return (float(unchanged[valid].mean()) if m > 0 else float("nan")), m


def _trans_dist(codes: np.ndarray) -> tuple[float, float]:
    """(mean |i-j| over consecutive labelled transitions, adjacency fraction |i-j|<=1)."""
    a, b = codes[:-1], codes[1:]
    valid = (a != -1) & (b != -1)
    if not valid.any():
        return float("nan"), float("nan")
    dist = np.abs(a[valid] - b[valid])
    return float(dist.mean()), float((dist <= 1).mean())


# ── battery 1: persistence / dwell ─────────────────────────────────────────────

def _run_lengths(labels: Sequence[str | None]) -> dict[str, list[int]]:
    runs: dict[str, list[int]] = {}
    cur, length = None, 0
    for lab in list(labels) + [object()]:  # sentinel flush
        if lab == cur:
            length += 1
        else:
            if cur is not None and length > 0:
                runs.setdefault(cur, []).append(length)
            cur, length = lab, 1
    return runs


def persistence_battery(labels: Sequence[str | None], order: Sequence[str], *, k: int,
                        n_perm: int, seed: int) -> dict:
    """Real k-bar persistence rate vs an i.i.d.-shuffle null (destroys temporal order, keeps the
    marginal). p = P(null_rate >= real_rate); a low p means the bands are genuinely sticky."""
    lab = list(labels)
    codes = _codes(lab, order)
    real, m = _persistence_rate(codes, k)

    rng = np.random.default_rng(seed)
    ge = 0
    null_rates = []
    for _ in range(n_perm):
        r, _m = _persistence_rate(rng.permutation(codes), k)
        r = 0.0 if r != r else r                       # nan-safe
        null_rates.append(r)
        if r >= real:
            ge += 1
    p = (ge + 1) / (n_perm + 1)
    null_mean = float(np.mean(null_rates)) if null_rates else float("nan")
    runs = _run_lengths(lab)
    mean_dwell = {b: float(np.mean(v)) for b, v in runs.items()}
    return {"real_rate": real, "null_mean": null_mean, "p": p, "n_valid": int(m),
            "mean_dwell": mean_dwell}


# ── battery 2: transition structure (adjacency-dominance) ───────────────────────

def transition_battery(labels: Sequence[str | None], order: Sequence[str], *, n_perm: int,
                       seed: int) -> dict:
    """Real mean band-distance of transitions vs a shuffle null. Ordered/adjacency-dominant bands
    have SMALLER mean distance than chance ⇒ p = P(null_dist <= real_dist) is low."""
    codes = _codes(list(labels), order)
    real_dist, adj_frac = _trans_dist(codes)
    rng = np.random.default_rng(seed)
    le = 0
    null_dists = []
    for _ in range(n_perm):
        d, _a = _trans_dist(rng.permutation(codes))
        null_dists.append(d)
        if d <= real_dist:
            le += 1
    p = (le + 1) / (n_perm + 1)
    return {"real_mean_distance": real_dist, "null_mean_distance": float(np.mean(null_dists)),
            "adjacency_fraction": adj_frac, "p": p}


# ── battery 3: forward-return characteristics ──────────────────────────────────

def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average ranks (1-based), ties averaged."""
    a = np.asarray(a, dtype=np.float64)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=np.float64)
    ranks[order] = np.arange(1, len(a) + 1, dtype=np.float64)
    # average ties
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.zeros(len(counts))
    np.add.at(sums, inv, ranks)
    return (sums / counts)[inv]


def _spearman(x: Sequence[float], y: Sequence[float]) -> float:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 2 or np.all(x == x[0]) or np.all(y == y[0]):
        return float("nan")
    rx, ry = _rankdata(x), _rankdata(y)
    rx -= rx.mean(); ry -= ry.mean()
    denom = float(np.sqrt(np.dot(rx, rx) * np.dot(ry, ry)))
    return float(np.dot(rx, ry) / denom) if denom > 0 else float("nan")


def forward_return_battery(labels: Sequence[str | None], fwd_ret: Sequence[float],
                           years: Sequence[int], order: Sequence[str], *, ci, min_cell: int,
                           rho_min: float, stab_min: float, seed: int) -> dict:
    """Per-band forward-return mean + bootstrap CI; monotonicity in band index; adjacent-boundary
    CI separation; and cross-year rank stability. All descriptive."""
    lab = np.asarray(labels, dtype=object)
    fr = np.asarray(fwd_ret, dtype=np.float64)
    yr = np.asarray(years)
    order = list(order)

    per_band: dict[str, dict] = {}
    means_by_index: list[float] = []
    usable_index: list[int] = []
    for i, b in enumerate(order):
        mask = np.array([lab[t] == b and np.isfinite(fr[t]) for t in range(len(lab))])
        vals = fr[mask]
        n = int(vals.size)
        if n >= 1:
            lo, hi = bootstrap_ci(vals, n_boot=ci.n_boot, alpha=ci.alpha,
                                  seed=_seed_from_key(f"{seed}|{ci.seed}|{b}"))
            mean = float(vals.mean())
        else:
            lo = hi = mean = float("nan")
        per_band[b] = {"n": n, "insufficient": n < min_cell, "mean": mean, "ci_lo": lo, "ci_hi": hi}
        if n >= min_cell:
            means_by_index.append(mean)
            usable_index.append(i)

    # monotonicity across usable bands (band index vs forward-return mean)
    rho = _spearman(usable_index, means_by_index) if len(usable_index) >= 2 else float("nan")
    monotonic_pass = bool(np.isfinite(rho) and rho >= rho_min)

    # adjacent-boundary CI separation (ascending: lower band CI-hi < higher band CI-lo)
    boundaries = []
    for i in range(len(order) - 1):
        lo_b, hi_b = order[i], order[i + 1]
        a, b = per_band[lo_b], per_band[hi_b]
        if a["insufficient"] or b["insufficient"]:
            sep = False
            reason = "insufficient"
        else:
            sep = bool(a["ci_hi"] < b["ci_lo"])
            reason = "separated" if sep else "ci_overlap"
        boundaries.append({"between": (lo_b, hi_b), "edge_index": i, "separated": sep,
                           "reason": reason})
    supported_edges = [bd["edge_index"] for bd in boundaries if bd["separated"]]

    # cross-year stability: per-band mean per year, Spearman across bands
    uniq_years = sorted(set(int(y) for y in yr.tolist()))
    stability_rho = float("nan")
    if len(uniq_years) >= 2:
        ya, yb = uniq_years[0], uniq_years[-1]
        def _year_means(y0):
            out = []
            for b in order:
                mask = np.array([lab[t] == b and np.isfinite(fr[t]) and int(yr[t]) == y0
                                 for t in range(len(lab))])
                out.append(float(fr[mask].mean()) if mask.sum() >= min_cell else np.nan)
            return out
        ma, mb = _year_means(ya), _year_means(yb)
        pairs = [(x, y) for x, y in zip(ma, mb) if np.isfinite(x) and np.isfinite(y)]
        if len(pairs) >= 2:
            stability_rho = _spearman([p[0] for p in pairs], [p[1] for p in pairs])
    stability_pass = bool(np.isfinite(stability_rho) and stability_rho >= stab_min)

    return {"per_band": per_band, "spearman_rho": rho, "monotonic_pass": monotonic_pass,
            "boundaries": boundaries, "supported_edges": supported_edges,
            "stability_rho": stability_rho, "stability_pass": stability_pass,
            "years": uniq_years}


# ── partition verdict + report ─────────────────────────────────────────────────

@dataclass(frozen=True)
class PartitionVerdict:
    name: str
    verdict: str                     # FROZEN_ELIGIBLE | MERGE_RECOMMENDED | NOT_SUPPORTED
    persistence: dict
    transition: dict
    forward_return: dict
    supported_edges: tuple           # ordered edge indices whose boundary is behaviorally real
    reason: str

    def to_dict(self) -> dict:
        return {"name": self.name, "verdict": self.verdict, "reason": self.reason,
                "supported_edges": list(self.supported_edges),
                "persistence": self.persistence, "transition": self.transition,
                "forward_return": self.forward_return}


def evaluate_partition(values: Sequence[float], fwd_ret: Sequence[float], years: Sequence[int],
                       spec: BandSpec, params: BandValidationParams) -> PartitionVerdict:
    labels = assign_bands(values, spec)
    order = list(spec.labels)
    pb = persistence_battery(labels, order, k=params.k_persist, n_perm=params.n_perm,
                             seed=_seed_from_key(f"{params.seed}|persist|{spec.name}"))
    tb = transition_battery(labels, order, n_perm=params.n_perm,
                            seed=_seed_from_key(f"{params.seed}|trans|{spec.name}"))
    fb = forward_return_battery(labels, fwd_ret, years, order, ci=params.ci,
                                min_cell=params.min_cell, rho_min=params.rho_min,
                                stab_min=params.stab_min,
                                seed=_seed_from_key(f"{params.seed}|fwd|{spec.name}"))

    persistence_pass = bool(np.isfinite(pb["p"]) and pb["p"] < params.alpha
                            and pb["real_rate"] > pb["null_mean"])
    transition_pass = bool(np.isfinite(tb["p"]) and tb["p"] < params.alpha
                           and tb["real_mean_distance"] < tb["null_mean_distance"])

    supported = tuple(fb["supported_edges"])
    n_edges = len(spec.edges)
    core_pass = persistence_pass and transition_pass and fb["monotonic_pass"] and fb["stability_pass"]

    if not core_pass:
        fails = [n for n, ok in (("persistence", persistence_pass), ("transition", transition_pass),
                                 ("monotonic", fb["monotonic_pass"]),
                                 ("stability", fb["stability_pass"])) if not ok]
        verdict, reason = "NOT_SUPPORTED", f"failed: {','.join(fails)}"
    elif len(supported) == n_edges:
        verdict, reason = "FROZEN_ELIGIBLE", "all boundaries behaviorally separated"
    elif len(supported) >= 1:
        verdict, reason = "MERGE_RECOMMENDED", (
            f"{len(supported)}/{n_edges} boundaries separated; merge the rest")
    else:
        verdict, reason = "NOT_SUPPORTED", "no boundary separates forward return (all CIs overlap)"

    return PartitionVerdict(spec.name, verdict, pb, tb, fb, supported, reason)


@dataclass(frozen=True)
class BandValidationReport:
    n_bars: int
    fwd_horizon: int
    partitions: tuple                 # PartitionVerdict, input order
    recommended: str | None           # name of the behaviorally-best partition, or None
    params: dict

    def to_dict(self) -> dict:
        return {"authority": AUTHORITY, "n_bars": self.n_bars, "fwd_horizon": self.fwd_horizon,
                "recommended": self.recommended, "params": dict(self.params),
                "partitions": [p.to_dict() for p in self.partitions]}


def validate_partitions(values: Sequence[float], fwd_ret: Sequence[float], years: Sequence[int],
                        specs: Sequence[BandSpec], params: BandValidationParams) -> BandValidationReport:
    """Run every candidate partition; recommend the behaviorally-best (most supported boundaries,
    tie-broken by monotonicity), or None if all NOT_SUPPORTED."""
    if not (len(values) == len(fwd_ret) == len(years)):
        raise ValueError(
            f"length mismatch: values={len(values)} fwd_ret={len(fwd_ret)} years={len(years)}")
    verdicts = [evaluate_partition(values, fwd_ret, years, s, params) for s in specs]

    eligible = [v for v in verdicts if v.verdict in ("FROZEN_ELIGIBLE", "MERGE_RECOMMENDED")]
    recommended = None
    if eligible:
        best = max(eligible, key=lambda v: (len(v.supported_edges),
                                            v.forward_return.get("spearman_rho") or 0.0))
        recommended = best.name

    return BandValidationReport(
        n_bars=len(values), fwd_horizon=params.fwd_horizon, partitions=tuple(verdicts),
        recommended=recommended,
        params={"k_persist": params.k_persist, "fwd_horizon": params.fwd_horizon,
                "n_perm": params.n_perm, "alpha": params.alpha, "rho_min": params.rho_min,
                "stab_min": params.stab_min, "min_cell": params.min_cell, "seed": params.seed,
                "ci": {"n_boot": params.ci.n_boot, "alpha": params.ci.alpha, "seed": params.ci.seed}},
    )
