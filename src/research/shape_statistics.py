"""
Historical Statistics layer — Layer 6 of the semantic pipeline (roadmap Phase 5, statistics).

"Statistics summarize." For every Market Shape (Layer 5), this module measures how the market
historically behaved AFTER bars carrying that shape: forward return and path excursions over
explicit horizons, in ATR units.

WHY THIS LIVES IN research/ AND NOT features/
    The computation is FORWARD-LOOKING BY DESIGN — bar t's statistics read bars t+1..t+h. That is
    outcome measurement (a label), never a feature. Keeping it out of src/features/ makes the
    no-lookahead boundary structural: nothing on the feature path can import "just a helper" from
    here by accident.

WHY DIRECTION-AGNOSTIC HORIZON STATS AND NOT forward_walk SL/TP OUTCOMES
    research.measurement.forward_walk simulates a TRADE and therefore requires a direction and an
    exit geometry. Shapes are bar-level descriptions with no declared trade direction; assigning
    one per shape would be policy invention. The profile instead reports, per (shape, horizon):
        fwd_ret   — (close[t+h] − close[t]) / ATR_abs[t]      signed drift
        up_exc    — (max(high[t+1..t+h]) − close[t]) / ATR_abs[t]   best upside reached
        down_exc  — (close[t] − min(low[t+1..t+h])) / ATR_abs[t]    worst downside reached
    All in ATR units, so cells are comparable across instruments and volatility regimes.
    Outcomes are derived from the RAW PRICE PATH — never from opportunities.jsonl labels (F-022).

AUTHORITY (E-001 / §6.5 — read before citing numbers from this module)
    DESCRIPTIVE ONLY, Authority-Ladder Level ≤ 1 (information). No significance testing lives
    here — qualification is the M4 gate's job, and a well-populated cell is NOT evidence of an
    edge. Cells below `min_samples` carry insufficient=True and support NO claim of any kind.
    The optional bootstrap CI (BootstrapSpec) describes SAMPLING UNCERTAINTY on a cell mean; it
    is still a description — a CI excluding zero is NOT a significance test and NOT an edge claim,
    and `insufficient` continues to govern whether any claim is licensed.

CONTRACT (no defaults, no fallbacks)
    `horizons` and `min_samples` are required keyword arguments. Bars are EXCLUDED only for
    explicit, counted reasons (pipeline warmup drop, non-positive ATR, tail short of horizon);
    every exclusion is reported in the profile, nothing is silently skipped.

JOIN CORRECTNESS (the _pos gotcha)
    FeaturePipeline.run() drops ~78 warmup rows and RESETS the index, so pipeline row i is NOT
    raw bar i. A carried position column written BEFORE the run is the only safe join key
    (project memory: trace-corpus gotcha). Enforced by test_shape_statistics.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from features.market_shape import MarketShapeClassifier
from research.measurement.bootstrap import (
    BOOTSTRAP_METHOD_VERSION, bootstrap_ci, seed_from_key,
)

_POS_COL = "_shape_stats_pos"          # carried raw-position join key (see module docstring)
UNNAMED = "UNNAMED"                    # aggregation bucket for unmatched fine shapes


@dataclass(frozen=True)
class BootstrapSpec:
    """A caller's explicit request for bootstrap CIs on cell means (no defaults — all required).

    Passed to ``profile(..., ci=BootstrapSpec(...))``. Absence (``ci=None``) means CIs are
    OMITTED BY DESIGN — an explicit opt-out, never a silently-defaulted numeric interval. Each
    cell is seeded independently from ``seed`` and the cell's identity, so CIs are byte-
    reproducible per cell and stable under reordering.
    """
    n_boot: int
    alpha: float                        # central coverage is (1 - alpha)
    seed: int                           # base seed; per-cell seed derives from this + cell key


@dataclass(frozen=True)
class CellStats:
    """Descriptive statistics for one (shape, horizon) cell. ATR units throughout.

    The bootstrap CI (when requested) describes sampling uncertainty on ``fwd_ret_mean`` only;
    it is NOT a significance test (that is the M4 gate's job) and a CI that excludes zero is NOT
    evidence of an edge. ``insufficient`` still governs interpretation regardless of CI width.
    """
    n: int
    insufficient: bool                  # n < min_samples — supports NO claim
    fwd_ret_mean: float
    fwd_ret_median: float
    fwd_ret_std: float                  # ddof=1; nan when n < 2
    pct_positive: float                 # share of fwd_ret > 0
    up_exc_mean: float
    down_exc_mean: float
    # Bootstrap CI on fwd_ret_mean — None (uniformly) when ci was not requested (explicit
    # opt-out). None, never nan: nan would break dict/determinism equality and muddle "absent"
    # with "computed but undefined".
    fwd_ret_ci_lo: float | None = None
    fwd_ret_ci_hi: float | None = None
    ci_method: str | None = None
    ci_n_boot: int | None = None
    ci_alpha: float | None = None
    ci_seed: int | None = None          # the effective per-cell seed (reproduction handle)

    def to_dict(self) -> dict:
        return {
            "n": self.n, "insufficient": self.insufficient,
            "fwd_ret_mean": self.fwd_ret_mean, "fwd_ret_median": self.fwd_ret_median,
            "fwd_ret_std": self.fwd_ret_std, "pct_positive": self.pct_positive,
            "up_exc_mean": self.up_exc_mean, "down_exc_mean": self.down_exc_mean,
            "fwd_ret_ci_lo": self.fwd_ret_ci_lo, "fwd_ret_ci_hi": self.fwd_ret_ci_hi,
            "ci_method": self.ci_method, "ci_n_boot": self.ci_n_boot,
            "ci_alpha": self.ci_alpha, "ci_seed": self.ci_seed,
        }


@dataclass(frozen=True)
class ShapeProfile:
    """The full historical profile of a corpus, grouped by shape family and shape name."""
    bars_raw: int
    bars_usable: int                    # pipeline rows with positive ATR (pre-horizon)
    excluded: dict                      # {"warmup_dropped": int, "non_positive_atr": int,
                                        #  "tail_no_horizon": {h: int}}
    x_marker_bars: int                  # bars whose shape carried domain-drift markers
    horizons: tuple[int, ...]
    min_samples: int
    by_family: dict                     # family -> {h: CellStats}
    by_name: dict                       # shape name (or UNNAMED) -> {h: CellStats}

    def to_dict(self) -> dict:
        return {
            "authority": "DESCRIPTIVE_ONLY_LEVEL_1_INFORMATION",
            "bars_raw": self.bars_raw, "bars_usable": self.bars_usable,
            "excluded": self.excluded, "x_marker_bars": self.x_marker_bars,
            "horizons": list(self.horizons), "min_samples": self.min_samples,
            "by_family": {k: {h: c.to_dict() for h, c in v.items()}
                          for k, v in self.by_family.items()},
            "by_name": {k: {h: c.to_dict() for h, c in v.items()}
                        for k, v in self.by_name.items()},
        }


def _cell(values: list[tuple[float, float, float]], min_samples: int,
          *, ci: "BootstrapSpec | None", seed_key: str) -> CellStats:
    """Aggregate (fwd_ret, up_exc, down_exc) triples into one CellStats.

    When ``ci`` is given, a percentile bootstrap CI is computed on ``fwd_ret_mean`` using a
    per-cell seed derived from ``ci.seed`` and ``seed_key`` (the cell identity), so every cell
    is independently yet reproducibly seeded. Insufficient cells still get a CI — the CI
    describes uncertainty; ``insufficient`` still governs whether any claim is licensed.
    """
    n = len(values)
    arr = np.asarray(values, dtype=np.float64)
    fwd, up, down = arr[:, 0], arr[:, 1], arr[:, 2]

    ci_lo = ci_hi = None
    ci_method = ci_n_boot = ci_alpha = ci_seed = None
    if ci is not None:
        cell_seed = seed_from_key(f"{ci.seed}|{seed_key}")
        ci_lo, ci_hi = bootstrap_ci(fwd, n_boot=ci.n_boot, alpha=ci.alpha, seed=cell_seed)
        ci_method = f"percentile_bootstrap_v{BOOTSTRAP_METHOD_VERSION}"
        ci_n_boot, ci_alpha, ci_seed = ci.n_boot, ci.alpha, cell_seed

    return CellStats(
        n=n,
        insufficient=n < min_samples,
        fwd_ret_mean=float(fwd.mean()),
        fwd_ret_median=float(np.median(fwd)),
        fwd_ret_std=float(fwd.std(ddof=1)) if n > 1 else float("nan"),
        pct_positive=float((fwd > 0).mean()),
        up_exc_mean=float(up.mean()),
        down_exc_mean=float(down.mean()),
        fwd_ret_ci_lo=ci_lo, fwd_ret_ci_hi=ci_hi,
        ci_method=ci_method, ci_n_boot=ci_n_boot, ci_alpha=ci_alpha, ci_seed=ci_seed,
    )


class ShapeStatisticsBuilder:
    """Joins Layer-5 shapes to raw-path forward statistics over explicit horizons."""

    def __init__(self, classifier: MarketShapeClassifier | None = None):
        self._clf = classifier if classifier is not None else MarketShapeClassifier()

    def profile(self, raw: pd.DataFrame, *, horizons: Sequence[int],
                min_samples: int, ci: BootstrapSpec | None = None) -> ShapeProfile:
        """Build the historical profile of one OHLCV corpus.

        Args:
            raw: OHLCV frame with a `timestamp` column (the FeaturePipeline input contract).
            horizons: forward horizons in bars — required, positive, strictly increasing.
            min_samples: cell-size floor below which insufficient=True — required, positive.
            ci: optional bootstrap-CI request. ``None`` (default) OMITS CIs by design (an
                explicit opt-out, not a silent numeric default); pass a fully-specified
                ``BootstrapSpec`` to attach a reproducible CI on every cell's fwd_ret_mean.
        """
        horizons = tuple(int(h) for h in horizons)
        if not horizons or any(h <= 0 for h in horizons):
            raise ValueError(f"horizons must be non-empty positive ints, got {horizons}")
        if list(horizons) != sorted(set(horizons)):
            raise ValueError(f"horizons must be strictly increasing/unique, got {horizons}")
        if int(min_samples) <= 0:
            raise ValueError(f"min_samples must be positive, got {min_samples}")
        min_samples = int(min_samples)

        # ── run the pipeline with a carried raw-position join key ────────────
        from features.feature_pipeline import FeaturePipeline  # deferred: heavy import

        work = raw.reset_index(drop=True).copy()
        n_raw = len(work)
        work[_POS_COL] = np.arange(n_raw, dtype=np.int64)
        df, vectors = FeaturePipeline(work).run()
        if _POS_COL not in df.columns:
            raise RuntimeError(
                f"{_POS_COL} did not survive FeaturePipeline.run() — the raw-position join "
                "contract broke; refusing to guess row alignment"
            )
        pos = df[_POS_COL].to_numpy(dtype=np.int64)
        if len(pos) != len(vectors):
            raise RuntimeError(
                f"pipeline frame ({len(pos)}) and vector matrix ({len(vectors)}) disagree"
            )

        raw_high = work["high"].to_numpy(dtype=np.float64)
        raw_low = work["low"].to_numpy(dtype=np.float64)
        raw_close = work["close"].to_numpy(dtype=np.float64)
        # ATR in absolute price units at the signal bar (PIT: the bar's own value).
        atr_abs = (df["atr"].to_numpy(dtype=np.float64)
                   * df["close"].to_numpy(dtype=np.float64))

        # ── per-bar shape + forward path, explicit exclusions only ───────────
        warmup_dropped = n_raw - len(pos)
        non_positive_atr = 0
        tail_no_horizon: dict[int, int] = {h: 0 for h in horizons}
        x_marker_bars = 0

        fam_cells: dict[str, dict[int, list]] = {}
        name_cells: dict[str, dict[int, list]] = {}

        for i in range(len(pos)):
            a = atr_abs[i]
            if not (a > 0.0):
                non_positive_atr += 1
                continue
            shape = self._clf.classify_vector(vectors[i])
            if shape.x_markers:
                x_marker_bars += 1
            family = shape.family if shape.family is not None else UNNAMED
            name = shape.name if shape.name is not None else UNNAMED

            p = int(pos[i])
            c0 = raw_close[p]
            for h in horizons:
                if p + h >= n_raw:
                    tail_no_horizon[h] += 1
                    continue
                fwd = (raw_close[p + h] - c0) / a
                window_hi = raw_high[p + 1: p + h + 1].max()
                window_lo = raw_low[p + 1: p + h + 1].min()
                triple = (fwd, (window_hi - c0) / a, (c0 - window_lo) / a)
                fam_cells.setdefault(family, {}).setdefault(h, []).append(triple)
                name_cells.setdefault(name, {}).setdefault(h, []).append(triple)

        by_family = {fam: {h: _cell(vals, min_samples, ci=ci, seed_key=f"family|{fam}|{h}")
                           for h, vals in per_h.items()}
                     for fam, per_h in fam_cells.items()}
        by_name = {nm: {h: _cell(vals, min_samples, ci=ci, seed_key=f"name|{nm}|{h}")
                        for h, vals in per_h.items()}
                   for nm, per_h in name_cells.items()}

        return ShapeProfile(
            bars_raw=n_raw,
            bars_usable=len(pos) - non_positive_atr,
            excluded={
                "warmup_dropped": warmup_dropped,
                "non_positive_atr": non_positive_atr,
                "tail_no_horizon": tail_no_horizon,
            },
            x_marker_bars=x_marker_bars,
            horizons=horizons,
            min_samples=min_samples,
            by_family=by_family,
            by_name=by_name,
        )
