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


def _frame(signs, closes=None):
    n = len(signs)
    closes = closes or [10 + i for i in range(n)]
    return pd.DataFrame({"f": signs, "open": [closes[0]] + closes[:-1], "close": closes})


def test_week_direction_and_whole_week_agreement():
    w = _frame([1, 1, -1, 1], closes=[10, 11, 12, 13])
    assert t.week_direction(w) == 1
    assert t.whole_week_agreement(w, "f", 0.0) == pytest.approx(0.75)
    d = _frame([-1, -1, -1], closes=[10, 9, 8])
    assert t.week_direction(d) == -1 and t.whole_week_agreement(d, "f", 0.0) == 1.0


def test_first_agreement_lag_and_move_made():
    # week rises 10 -> 14; sign agrees for good from bar 2 (index) onward
    w = _frame([-1, 1, -1, 1, 1], closes=[10, 11, 12, 13, 14])
    r = t.first_agreement(w, "f", 0.0)
    assert r["bar"] == 3 and r["moved_frac"] == pytest.approx((13 - 10) / (14 - 10))
    assert t.first_agreement(_frame([1, 1, 1]), "f", 0.0)["bar"] == 0
    assert t.first_agreement(_frame([1, 1, -1]), "f", 0.0)["bar"] is None


def test_longest_counter_run():
    w = _frame([1, -1, -1, 0, -1, 1, -1], closes=[10, 11, 12, 13, 14, 15, 16])
    assert t.longest_counter_run(w, "f", 0.0) == 2     # zero does not extend a run (it breaks it)


def test_compare_dirs_reads_stats_and_uses_dominant_range(tmp_path):
    import json
    def mk(name, week_dir, agree_long, agree_sell):
        d = tmp_path / name; d.mkdir()
        feats = {f: {"range": {"LONG": {"agree": agree_long}, "SELL": {"agree": agree_sell}},
                     "longest_counter_run": 3, "next": {"hit": 6, "n": 10, "rate": 0.6, "p": 0.75}}
                 for f in t.SIGNED}
        (d / "stats.json").write_text(json.dumps({"label": name, "week_dir": week_dir, "features": feats}))
        return str(d)
    a, b = mk("A", 1, 1.0, 0.8), mk("B", -1, 0.0, 0.9)
    out = t.compare_dirs(a, b)
    assert "B (B) SELL week matches" in out
    first = [ln for ln in out.splitlines() if ln.startswith("| trend_bias")][0]
    assert "| 100% | 80% | 90% | 3 |" in first
