# tests/test_volatility_window_candidates.py
"""Frozen-rule candidates for the volatility-window comparison (bar-based A, time-based B/C)."""

import os
import sys

import numpy as np
import pandas as pd
import pytest

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_ROOT, "scripts", "analysis"))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import volatility_window_comparison as vw  # noqa: E402
from features.feature_pipeline import trailing_atr_percentile  # noqa: E402


def test_frozen_constants():
    assert vw.BAR_WINDOW == 200 and vw.N_MIN == 100
    assert (vw.LOW_PCT, vw.HIGH_PCT) == (0.33, 0.66)
    assert vw.TIME_WINDOWS["H1"] == pd.Timedelta(days=9) and vw.TIME_WINDOWS["M15"] == pd.Timedelta(days=2)


def test_candidate_a_is_the_production_function():
    x = np.abs(np.random.default_rng(1).normal(1, 0.3, 450))
    np.testing.assert_array_equal(vw.bar_window_percentile(x, 200), trailing_atr_percentile(x, 200))


def _hourly(n, start="2025-03-03 01:00"):
    return pd.Series(pd.date_range(start, periods=n, freq="h"))


def test_time_window_reference_is_half_open_and_excludes_current():
    ts = _hourly(60); v = np.arange(60, dtype=float)
    p, nref = vw.time_window_percentile(v, ts, pd.Timedelta(hours=10), n_min=5)
    i = 30
    assert nref[i] == 10                              # bars t-10h .. t-1h : boundary bar included, current excluded
    assert p[i] == 1.0                                # strictly rising values: current above all 10 references


def test_time_window_requires_full_elapsed_coverage_and_min_count():
    ts = _hourly(40); v = np.ones(40)
    p, nref = vw.time_window_percentile(v, ts, pd.Timedelta(hours=10), n_min=5)
    assert np.isnan(p[:10]).all()                     # window would start before the first bar
    assert not np.isnan(p[10:]).any()
    p2, _ = vw.time_window_percentile(v, ts, pd.Timedelta(hours=10), n_min=11)
    assert np.isnan(p2).all()                         # never 11 bars inside a 10h window


def test_closures_are_not_filled_and_shrink_the_window():
    # weekdays only: Fri evening -> Mon morning gap. 2-day window on Monday sees almost no bars.
    days = pd.bdate_range("2025-03-03", periods=10)
    ts = pd.Series([d + pd.Timedelta(hours=h) for d in days for h in range(1, 24)])
    v = np.ones(len(ts))
    p, nref = vw.time_window_percentile(v, ts, pd.Timedelta(days=2), n_min=40)
    mon_early = ts[(ts.dt.dayofweek == 0) & (ts.dt.hour == 3) & (ts > ts.iloc[40])].index[0]
    assert nref[mon_early] < 10 and np.isnan(p[mon_early])           # Saturday+Sunday contribute nothing
    wed = ts[(ts.dt.dayofweek == 2) & (ts.dt.hour == 12) & (ts > ts.iloc[40])].index[0]
    assert nref[wed] == 46 and not np.isnan(p[wed])      # 2 full days of 23 hourly bars


def test_invalid_atr_inside_window_gives_nan_and_clears_after_it_leaves():
    ts = _hourly(60); v = np.ones(60); v[20] = np.nan
    p, _ = vw.time_window_percentile(v, ts, pd.Timedelta(hours=10), n_min=5)
    assert np.isnan(p[21:31]).all()                   # windows containing bar 20
    assert not np.isnan(p[31:]).any()
    assert np.isnan(p[20])                            # current bar invalid


def test_ties_use_mid_rank():
    ts = _hourly(30); v = np.full(30, 2.0)
    p, _ = vw.time_window_percentile(v, ts, pd.Timedelta(hours=10), n_min=5)
    assert p[15] == 0.5


def test_non_monotonic_timestamps_rejected():
    ts = pd.Series(pd.to_datetime(["2025-01-01 01:00", "2025-01-01 01:00", "2025-01-01 02:00"]))
    with pytest.raises(ValueError):
        vw.time_window_percentile([1.0, 2.0, 3.0], ts, pd.Timedelta(hours=1), n_min=1)


def test_prefix_invariance_and_replay_for_time_window():
    rng = np.random.default_rng(5)
    ts = _hourly(300); v = np.abs(rng.normal(1, 0.3, 300))
    full, _ = vw.time_window_percentile(v, ts, pd.Timedelta(hours=24), n_min=10)
    for cut in (80, 150, 299):
        part, _ = vw.time_window_percentile(v[: cut + 1], ts[: cut + 1], pd.Timedelta(hours=24), n_min=10)
        np.testing.assert_array_equal(part, full[: cut + 1])
    again, _ = vw.time_window_percentile(v, ts, pd.Timedelta(hours=24), n_min=10)
    np.testing.assert_array_equal(full, again)


def test_future_mutation_cannot_change_past_values_for_either_window():
    rng = np.random.default_rng(6)
    ts = _hourly(300); v = np.abs(rng.normal(1, 0.3, 300)); w = v.copy(); w[181:] = rng.uniform(5, 9, 119)
    a, b = vw.time_window_percentile(v, ts, pd.Timedelta(hours=24), 10)[0], vw.time_window_percentile(w, ts, pd.Timedelta(hours=24), 10)[0]
    np.testing.assert_array_equal(a[:181], b[:181])
    np.testing.assert_array_equal(vw.bar_window_percentile(v)[:181], vw.bar_window_percentile(w)[:181])


def test_cur_override_defaults_to_the_series():
    ts = _hourly(300); v = np.abs(np.random.default_rng(7).normal(1, 0.3, 300))
    np.testing.assert_array_equal(vw.bar_window_percentile(v, 50, cur=v), vw.bar_window_percentile(v, 50))
    np.testing.assert_array_equal(vw.time_window_percentile(v, ts, pd.Timedelta(hours=24), 10, cur=v)[0],
                                  vw.time_window_percentile(v, ts, pd.Timedelta(hours=24), 10)[0])


def test_class_edges_and_nan_pass_through():
    c = vw.to_class(np.array([0.0, 0.329, 0.33, 0.659, 0.66, 1.0, np.nan]))
    np.testing.assert_array_equal(c[:6], [0, 0, 1, 1, 2, 2]); assert np.isnan(c[6])
