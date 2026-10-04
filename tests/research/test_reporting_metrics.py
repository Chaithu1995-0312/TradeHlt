"""Tests for reporting-only metrics. Pins correctness AND the doctrine guarantee that these
helpers are pure reporting — they expose no path to the QualificationGate verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.candle_state import reporting   # noqa: E402


def test_win_rate():
    assert reporting.win_rate([1.0, -1.0, 2.0, -0.5]) == 0.5
    assert reporting.win_rate([]) == 0.0


def test_streak_metrics():
    rrs = [1, 1, -1, -1, -1, 1, -1]            # max losing run = 3
    m = reporting.streak_metrics(rrs)
    assert m["max_losing_streak"] == 3
    assert m["max_winning_streak"] == 2
    assert m["max_losing_streak_ok"] is True
    worse = [-1, -1, -1, -1]                     # 4 → not ok
    assert reporting.streak_metrics(worse)["max_losing_streak_ok"] is False


def test_rolling_window_metrics():
    rrs = [1] * 7 + [-1] * 3                     # exactly one window, 7 wins
    r = reporting.rolling_window_metrics(rrs, window=10, min_wins=7)
    assert r["n_windows"] == 1 and r["worst_window_wins"] == 7 and r["all_windows_ok"] is True
    rrs2 = [1] * 6 + [-1] * 4                    # 6 wins → below 7
    assert reporting.rolling_window_metrics(rrs2)["all_windows_ok"] is False
    assert reporting.rolling_window_metrics([1, 1, 1])["n_windows"] == 0   # too few trades


def test_report_rollup():
    rrs = [1.0] * 8 + [-1.0] * 2
    rep = reporting.report(rrs)
    assert rep["n"] == 10 and rep["win_rate"] == 0.8 and rep["win_rate_ge_70pct"] is True
    assert "rolling_10" in rep and "max_losing_streak" in rep


def test_reporting_module_has_no_qualification_dependency():
    """Doctrine guard: reporting must never reach the promote authority. Assert the module
    does not import research.qualification (directly or transitively at module scope)."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(reporting))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("qualification" in m for m in imported), imported
    assert not any("runner" in m for m in imported), imported


def test_report_is_deterministic():
    rrs = [0.5, -1.0, 2.0, -1.0, 1.0, 1.0, -1.0, 3.0, -1.0, 0.2, 1.0]
    assert reporting.report(rrs) == reporting.report(rrs)
