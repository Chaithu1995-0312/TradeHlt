"""CH-feature-semantic-fixes-v7 (2026-10-08): floor for the four feature semantic fixes.

1. FM-096 displacement_retrace_signed is the retracement FM-027 is named for; FM-027 stays as the
   byte-identical legacy arm, selected by the strict key setup.retrace_semantics.
2/3. sweep_semantics / session_timestamp_basis activations live in config (pinned by the
   freeze pin); here only the declared-key discipline is checked.
4. Schema v7.0 presence flags: each *_present is decided by the same finder its *_distance
   measures to, so present == 0 implies distance == 0, and present separates "no zone" from
   "price on the zone edge" (both 0.0 in the distance).
"""
from __future__ import annotations

import glob
import json

import numpy as np
import pandas as pd
import pytest

from features import derived_math as dm

PRESENCE = {
    "order_block_present": "order_block_distance",
    "fvg_present": "fvg_distance",
    "breaker_present": "breaker_distance",
    "mitigation_block_present": "mitigation_block_distance",
    "eqh_present": "eqh_distance",
    "eql_present": "eql_distance",
}


# ── 1. FM-096 vs FM-027 ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("o,c", [(100.0, 110.0), (110.0, 100.0)])   # bullish, bearish displacement
@pytest.mark.parametrize("frac_given_back,expected", [
    (0.0, 0.0),      # retest closed at the displacement close: nothing retraced
    (0.3, 0.3),
    (0.5, 0.5),
    (1.0, 1.0),      # back to the displacement open
    (1.5, 1.5),      # closed beyond the open: the displacement failed
    (-0.5, -0.5),    # extended past the displacement close
])
def test_fm096_is_the_signed_retracement(o, c, frac_given_back, expected):
    retest = c - frac_given_back * (c - o)
    assert dm.displacement_retrace_signed(retest, o, c) == pytest.approx(expected)


def test_fm096_zero_body_is_zero():
    assert dm.displacement_retrace_signed(101.0, 100.0, 100.0) == 0.0


def test_fm027_legacy_arm_is_unchanged_and_shows_the_defect():
    # FM-027 = share KEPT, abs-folded: 30% retraced reads 0.7; a 150% retrace (closed beyond the
    # open, setup failed) folds back to 0.5 -- inside the trade-intent pullback band 0.3-0.7.
    assert dm.displacement_retrace(107.0, 100.0, 110.0) == pytest.approx(0.7)
    assert dm.displacement_retrace(95.0, 100.0, 110.0) == pytest.approx(0.5)
    assert dm.displacement_retrace_signed(95.0, 100.0, 110.0) == pytest.approx(1.5)


def test_retrace_semantics_mapping_is_strict():
    from config_layer.crt_engine_v2 import retrace_fm_for
    assert retrace_fm_for("legacy_kept_fraction") == "FM-027"
    assert retrace_fm_for("signed_retrace") == "FM-096"
    with pytest.raises(ValueError):
        retrace_fm_for("kept")


def test_fm096_resolves_through_the_registry():
    from features.fm_resolve import bind_phase2_crt_callables
    assert bind_phase2_crt_callables()["FM-096"] is dm.displacement_retrace_signed


def test_every_setup_section_declares_retrace_semantics():
    from config_layer.crt_engine_v2 import RETRACE_SEMANTICS
    seen = 0
    for path in glob.glob("configs/production/*.json"):
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        if "setup" not in cfg:
            continue
        seen += 1
        assert cfg["setup"].get("retrace_semantics") in RETRACE_SEMANTICS, path
    assert seen >= 13


# ── 4. presence flags (schema v7.0) ──────────────────────────────────────────────────────────
def test_presence_flags_are_the_v7_tail():
    # v8.0 (CH-candle-pattern-observations-v8) appended slots 54-70; 48-53 keep the v7.0 flags.
    from features.feature_schema import CANONICAL_FEATURES
    assert tuple(CANONICAL_FEATURES[48:54]) == tuple(PRESENCE)


@pytest.fixture(scope="module")
def synthetic_features():
    """Seeded random-walk OHLC long enough for OB/FVG/breaker/mitigation/EQH/EQL to appear."""
    from features.feature_pipeline import FeaturePipeline
    rng = np.random.default_rng(20261008)
    n = 700
    close = 2000.0 + np.cumsum(rng.normal(0, 1.5, n))
    open_ = np.r_[close[0], close[:-1]] + rng.normal(0, 0.3, n)
    high = np.maximum(open_, close) + rng.uniform(0.1, 2.0, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 2.0, n)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-05 01:00", periods=n, freq="15min"),
        "open": open_, "high": high, "low": low, "close": close,
        "volume": rng.integers(100, 1000, n).astype(float),
    })
    enriched, _ = FeaturePipeline(df).run()
    return enriched


@pytest.mark.parametrize("flag,dist", list(PRESENCE.items()))
def test_absent_zone_means_zero_distance(synthetic_features, flag, dist):
    f = synthetic_features
    assert set(np.unique(f[flag])) <= {0.0, 1.0}
    assert (f.loc[f[flag] == 0.0, dist] == 0.0).all()


@pytest.mark.parametrize("flag", list(PRESENCE))
def test_presence_flags_take_both_values(synthetic_features, flag):
    vals = set(np.unique(synthetic_features[flag]))
    assert vals == {0.0, 1.0}, f"{flag} never varies on the synthetic walk: {vals}"
