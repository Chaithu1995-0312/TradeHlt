# tests/test_week_feature_trace.py
"""Pure helpers of the weekly feature trace: sign symbols, exact binomial, range labels, flips."""

import math
import os
import sys

import pandas as pd
import pytest

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_ROOT, "scripts", "analysis"))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import week_feature_trace as t  # noqa: E402


def test_sym_uses_centre():
    assert t.sym(0.5, 0.0) == "+" and t.sym(-0.5, 0.0) == "-" and t.sym(0.0, 0.0) == "0"
    assert t.sym(60.0, 50.0) == "+" and t.sym(40.0, 50.0) == "-"


def test_binom_p_known_values():
    assert t.binom_p(5, 10) == pytest.approx(1.0)
    assert t.binom_p(10, 10) == pytest.approx(2 / 2 ** 10)
    assert math.isnan(t.binom_p(0, 0))


def _week():
    ts = pd.date_range("2025-07-21 01:00", periods=6, freq="h")
    return pd.DataFrame({
        "timestamp": ts,
        "open":  [10, 11, 12, 13, 12, 11], "close": [11, 12, 13, 12, 11, 10],
        "high":  [11, 12, 14, 13, 12, 11], "low":   [10, 11, 12, 12, 11, 10],
    })


def test_week_slice_labels_peak_bar_as_long_and_rest_as_sell():
    df = _week()
    w = t.week_slice(df, "2025-07-21", "2025-07-21")
    assert list(w["range"]) == ["LONG", "LONG", "LONG", "SELL", "SELL", "SELL"]
    assert list(w["bar_dir"]) == [1, 1, 1, -1, -1, -1]
    assert w["next_dir"].iloc[:-1].tolist() == [1, 1, -1, -1, -1]
    assert math.isnan(w["next_dir"].iloc[-1])


def test_flips_reports_sign_changes_only():
    df = _week()
    df["f"] = [1, 1, 0, -1, -1, 1]       # zero is skipped, flips at bar 4 (+→-) and bar 6 (-→+)
    fl = t.flips(df, "f", 0.0)
    assert [d for _, d in fl] == ["+→-", "-→+"]
