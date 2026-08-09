"""Floor for the Historical Statistics layer (src/research/shape_statistics.py).

The load-bearing assertion is JOIN CORRECTNESS: FeaturePipeline drops warmup rows and resets the
index, so statistics must be computed at the carried RAW position, not the pipeline row number.
A one-off-by-warmup bug here silently attributes every outcome to the wrong bar — these tests
recompute sampled cells by hand from the raw arrays to prove the join.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.measurement.bootstrap import bootstrap_ci, seed_from_key
from research.shape_statistics import BootstrapSpec, ShapeStatisticsBuilder, UNNAMED


def _synthetic(n: int = 420, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    body_top = np.maximum(open_, close)
    body_bot = np.minimum(open_, close)
    high = body_top + rng.uniform(0.05, 0.8, n)
    low = body_bot - rng.uniform(0.05, 0.8, n)
    volume = rng.uniform(100, 1000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": volume})


@pytest.fixture(scope="module")
def builder() -> ShapeStatisticsBuilder:
    return ShapeStatisticsBuilder()


@pytest.fixture(scope="module")
def profile(builder):
    return builder.profile(_synthetic(), horizons=(4, 8), min_samples=30)


# ── strict inputs ────────────────────────────────────────────────────────────

def test_horizons_and_min_samples_are_required_keywords(builder):
    with pytest.raises(TypeError):
        builder.profile(_synthetic())                      # nothing supplied
    with pytest.raises(TypeError):
        builder.profile(_synthetic(), (4, 8), 30)          # positional not accepted


@pytest.mark.parametrize("horizons", [(), (0,), (4, 4), (8, 4), (-1,)])
def test_bad_horizons_raise(builder, horizons):
    with pytest.raises(ValueError):
        builder.profile(_synthetic(), horizons=horizons, min_samples=30)


def test_bad_min_samples_raises(builder):
    with pytest.raises(ValueError):
        builder.profile(_synthetic(), horizons=(4,), min_samples=0)


# ── exclusion accounting: nothing silently skipped ───────────────────────────

def test_exclusions_are_counted_and_reconcile(profile):
    ex = profile.excluded
    assert ex["warmup_dropped"] > 0                          # the ~78-row canonical warmup
    assert profile.bars_raw == 420
    assert profile.bars_usable == (profile.bars_raw - ex["warmup_dropped"]
                                   - ex["non_positive_atr"])
    # per horizon: family cell sizes + tail exclusions == usable rows
    for h in profile.horizons:
        total_in_cells = sum(cells[h].n for cells in profile.by_family.values() if h in cells)
        assert total_in_cells + ex["tail_no_horizon"][h] == profile.bars_usable
    # longer horizon excludes at least as many tail bars
    assert ex["tail_no_horizon"][8] >= ex["tail_no_horizon"][4]


def test_family_and_name_groupings_cover_the_same_bars(profile):
    for h in profile.horizons:
        fam_total = sum(c[h].n for c in profile.by_family.values() if h in c)
        name_total = sum(c[h].n for c in profile.by_name.values() if h in c)
        assert fam_total == name_total


# ── join correctness: the _pos gotcha, proven by hand ────────────────────────

def test_statistics_are_computed_at_raw_positions_not_pipeline_rows(builder):
    """Recompute the full UNNAMED+named population for one horizon by hand, joining through the
    carried position column, and require exact equality with the profile's aggregate. If the
    implementation ever regressed to pipeline-row indexing, the warmup offset (~78 bars) would
    shift every window and this reconciliation would fail immediately."""
    from features.feature_pipeline import FeaturePipeline
    from features.market_shape import MarketShapeClassifier

    raw = _synthetic()
    h = 4
    prof = builder.profile(raw, horizons=(h,), min_samples=30)

    work = raw.reset_index(drop=True).copy()
    work["_check_pos"] = np.arange(len(work))
    df, vectors = FeaturePipeline(work).run()
    pos = df["_check_pos"].to_numpy(dtype=np.int64)
    close = work["close"].to_numpy(); high = work["high"].to_numpy(); low = work["low"].to_numpy()
    atr_abs = df["atr"].to_numpy() * df["close"].to_numpy()
    clf = MarketShapeClassifier()

    triples = []
    for i in range(len(pos)):
        a = atr_abs[i]
        p = int(pos[i])
        if not (a > 0) or p + h >= len(work):
            continue
        clf.classify_vector(vectors[i])  # shape assignment exercised identically
        fwd = (close[p + h] - close[p]) / a
        triples.append(fwd)
    triples = np.asarray(triples)

    got_total = sum(c[h].n for c in prof.by_family.values() if h in c)
    assert got_total == len(triples)
    weighted_mean = sum(c[h].fwd_ret_mean * c[h].n for c in prof.by_family.values() if h in c)
    np.testing.assert_allclose(weighted_mean / got_total, triples.mean(), rtol=1e-12)


def test_first_pipeline_row_maps_to_the_warmup_offset():
    from features.feature_pipeline import FeaturePipeline

    raw = _synthetic()
    work = raw.reset_index(drop=True).copy()
    work["_check_pos"] = np.arange(len(work))
    df, _v = FeaturePipeline(work).run()
    pos = df["_check_pos"].to_numpy(dtype=np.int64)
    assert pos[0] == len(work) - len(df), "warmup drop must be entirely at the head"
    assert (np.diff(pos) == 1).all(), "surviving rows must be contiguous raw positions"


# ── statistical semantics ────────────────────────────────────────────────────

def test_excursions_bound_the_forward_return(profile):
    """up_exc ≥ fwd_ret and −down_exc ≤ fwd_ret hold per bar, hence for means."""
    for cells in profile.by_family.values():
        for c in cells.values():
            assert c.up_exc_mean >= c.fwd_ret_mean - 1e-12
            assert -c.down_exc_mean <= c.fwd_ret_mean + 1e-12
            assert c.up_exc_mean >= 0 and c.down_exc_mean >= 0


def test_insufficient_flag_reflects_min_samples(builder):
    prof = builder.profile(_synthetic(), horizons=(4,), min_samples=10_000)
    assert all(c[4].insufficient for c in prof.by_family.values())
    prof2 = builder.profile(_synthetic(), horizons=(4,), min_samples=1)
    assert not all(c[4].insufficient for c in prof2.by_family.values())


def test_profile_is_deterministic(builder):
    a = builder.profile(_synthetic(), horizons=(4,), min_samples=30).to_dict()
    b = builder.profile(_synthetic(), horizons=(4,), min_samples=30).to_dict()
    assert a == b


def test_unnamed_bucket_and_authority_marker(profile):
    assert UNNAMED in profile.by_family
    d = profile.to_dict()
    assert d["authority"] == "DESCRIPTIVE_ONLY_LEVEL_1_INFORMATION"
    assert profile.x_marker_bars == 0


# ── bootstrap CI primitive (research.measurement.bootstrap) ──────────────────

def test_bootstrap_ci_is_deterministic_and_ordered():
    vals = list(np.random.default_rng(3).normal(0.2, 1.0, 200))
    a = bootstrap_ci(vals, n_boot=500, alpha=0.05, seed=7)
    b = bootstrap_ci(vals, n_boot=500, alpha=0.05, seed=7)
    assert a == b                                   # byte-reproducible
    assert a[0] <= a[1]                             # lo <= hi
    # a different seed gives a (generally) different interval, still ordered
    c = bootstrap_ci(vals, n_boot=500, alpha=0.05, seed=8)
    assert c[0] <= c[1]


def test_bootstrap_ci_brackets_mean_for_large_n():
    vals = list(np.random.default_rng(5).normal(0.5, 1.0, 2000))
    lo, hi = bootstrap_ci(vals, n_boot=800, alpha=0.05, seed=1)
    assert lo <= float(np.mean(vals)) <= hi


def test_bootstrap_ci_single_point_is_degenerate():
    assert bootstrap_ci([1.23], n_boot=100, alpha=0.1, seed=1) == (1.23, 1.23)


@pytest.mark.parametrize("kwargs", [
    {"n_boot": 0, "alpha": 0.05, "seed": 1},        # non-positive n_boot
    {"n_boot": 100, "alpha": 0.0, "seed": 1},       # alpha out of (0,1)
    {"n_boot": 100, "alpha": 1.0, "seed": 1},
])
def test_bootstrap_ci_bad_params_raise(kwargs):
    with pytest.raises(ValueError):
        bootstrap_ci([0.1, 0.2, 0.3], **kwargs)


def test_bootstrap_ci_empty_raises():
    with pytest.raises(ValueError):
        bootstrap_ci([], n_boot=100, alpha=0.05, seed=1)


# ── CI integration into the shape profile ────────────────────────────────────

def test_ci_omitted_by_default_is_explicit_optout(profile):
    """ci=None must leave CI fields as an explicit absent marker, never a silent number."""
    for cells in profile.by_family.values():
        for c in cells.values():
            assert c.ci_method is None
            assert c.ci_n_boot is None and c.ci_alpha is None and c.ci_seed is None
            assert c.fwd_ret_ci_lo is None and c.fwd_ret_ci_hi is None


def test_ci_populated_when_requested(builder):
    spec = BootstrapSpec(n_boot=300, alpha=0.05, seed=42)
    prof = builder.profile(_synthetic(), horizons=(4,), min_samples=30, ci=spec)
    seeds = set()
    for cells in prof.by_family.values():
        c = cells[4]
        assert c.ci_method == "percentile_bootstrap_v1.0"
        assert c.ci_n_boot == 300 and c.ci_alpha == 0.05
        assert c.fwd_ret_ci_lo <= c.fwd_ret_ci_hi
        # CI is a description, not a claim — insufficient cells still carry one
        assert c.ci_seed is not None
        seeds.add(c.ci_seed)
    assert len(seeds) >= 1                           # per-cell seeds are derived, not shared blindly


def test_ci_cells_are_independently_seeded(builder):
    """Distinct cell identities must derive distinct seeds (family|name|horizon key)."""
    spec = BootstrapSpec(n_boot=100, alpha=0.1, seed=9)
    prof = builder.profile(_synthetic(), horizons=(4, 8), min_samples=30, ci=spec)
    seeds = [cells[h].ci_seed
             for cells in prof.by_family.values() for h in prof.horizons if h in cells]
    assert len(set(seeds)) == len(seeds), "each (family,horizon) cell must be uniquely seeded"
    # the derivation is the documented one
    for fam, cells in prof.by_family.items():
        assert cells[4].ci_seed == seed_from_key(f"{spec.seed}|family|{fam}|4")


def test_profile_with_ci_is_deterministic(builder):
    spec = BootstrapSpec(n_boot=200, alpha=0.05, seed=13)
    a = builder.profile(_synthetic(), horizons=(4,), min_samples=30, ci=spec).to_dict()
    b = builder.profile(_synthetic(), horizons=(4,), min_samples=30, ci=spec).to_dict()
    assert a == b
    # authority stamp survives the CI extension
    assert a["authority"] == "DESCRIPTIVE_ONLY_LEVEL_1_INFORMATION"
