# tests/test_volatility_horizon_candidates.py
"""Candidate D (shared observation horizon): H1 200 bars, M15 800 bars; A unchanged."""

import os
import sys

import numpy as np
import pandas as pd
import pytest

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_ROOT, "scripts", "analysis"))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import volatility_horizon_comparison as vh  # noqa: E402
from features.feature_pipeline import trailing_atr_percentile  # noqa: E402


def test_frozen_windows():
    assert vh.WINDOW_A == {"H1": 200, "M15": 200}
    assert vh.WINDOW_D == {"H1": 200, "M15": 800}
    # 200 H1 bars and 800 M15 bars are the same nominal bar time
    assert 200 * 60 == 800 * 15


def test_d_equals_a_on_h1_and_production_function_on_m15():
    x = np.abs(np.random.default_rng(2).normal(1, 0.3, 1200))
    h = vh.candidates_v2("H1", x)
    np.testing.assert_array_equal(h["A"], h["D"])
    m = vh.candidates_v2("M15", x)
    np.testing.assert_array_equal(m["A"], trailing_atr_percentile(x, 200))
    np.testing.assert_array_equal(m["D"], trailing_atr_percentile(x, 800))
    assert np.isnan(m["D"][:800]).all() and not np.isnan(m["D"][800:]).any()
    assert not np.isnan(m["A"][200:]).any()


def test_d_is_causal_prefix_and_mutation():
    rng = np.random.default_rng(3); x = np.abs(rng.normal(1, 0.3, 1500)); y = x.copy(); y[1100:] = rng.uniform(4, 9, 400)
    full = vh.candidates_v2("M15", x)["D"]
    for cut in (850, 1000, 1499):
        np.testing.assert_array_equal(vh.candidates_v2("M15", x[: cut + 1])["D"], full[: cut + 1])
    np.testing.assert_array_equal(vh.candidates_v2("M15", y)["D"][:1100], full[:1100])


def test_closure_and_missing_bar_definitions():
    base = pd.Timestamp("2025-03-03 01:00")
    ts = pd.Series([base + pd.Timedelta(minutes=m) for m in (0, 15, 30, 60, 75, 90, 150, 165)])   # gaps: 15,15,30,15,15,60,15
    closure, missing = vh.gap_flags(ts, "M15")
    assert closure.tolist() == [False, False, False, False, False, False, True, False]    # 60 min > 45 min
    assert missing.tolist() == [False, False, False, True, False, False, False, False]    # 30 min: missing bar(s)
    h1 = pd.Series([base + pd.Timedelta(hours=h) for h in (0, 1, 3, 7)])                  # gaps 1h, 2h (missing), 4h (closure)
    c1, m1 = vh.gap_flags(h1, "H1")
    assert c1.tolist() == [False, False, False, True] and m1.tolist() == [False, False, True, False]


def test_closures_in_window_counts_gaps_between_the_window_bars():
    closure = np.zeros(30, dtype=bool); closure[10] = True; closure[20] = True
    cw = vh.closures_in_window(closure, 5)
    assert cw[:5].tolist() == [-1] * 5
    assert cw[10] == 0 and cw[11] == 1     # the gap on bar 10 lies between bar 9 and the current bar 10: not inside bars 5..9; bars 6..10 contain it
    assert cw[14] == 1 and cw[15] == 0     # bar 10 leaves the window of 5 bars after bar 14
    assert cw[20] == 0 and cw[21] == 1
