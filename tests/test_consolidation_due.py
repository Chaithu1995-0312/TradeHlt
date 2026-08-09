"""Unit tests for the consolidation advisory (scripts/maintenance/check_consolidation_due.py).

Exercises the pure evaluate() decision (git/IO-free) + a smoke test that the advisory main()
never blocks (exit 0) on the real repo.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SRC = Path("scripts/maintenance/check_consolidation_due.py")
_spec = importlib.util.spec_from_file_location("check_consolidation_due", _SRC)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

_THR = {"session_log": 25, "findings": 30, "memory": 45, "archive": 12}


def _by_name(signals):
    return {s.name: s for s in signals}


def test_none_due_when_all_under_threshold() -> None:
    counts = {"session_log": 20, "findings": 25, "memory": 37, "archive": 1}
    signals = cc.evaluate(counts, _THR)
    assert not any(s.due for s in signals)


def test_due_signals_carry_a_remedy() -> None:
    counts = {"session_log": 99, "findings": 99, "memory": 99, "archive": 99}
    for s in cc.evaluate(counts, _THR):
        assert s.due and s.remedy.strip(), f"{s.name} should be due with a non-empty remedy"


def test_boundary_is_strictly_greater() -> None:
    # exactly at threshold → NOT due; one over → due
    at = _by_name(cc.evaluate({"findings": 30}, _THR))["findings"]
    over = _by_name(cc.evaluate({"findings": 31}, _THR))["findings"]
    assert at.due is False and over.due is True


def test_unmeasurable_count_is_not_due() -> None:
    # memory dir absent (count None) must never be DUE
    s = _by_name(cc.evaluate({"memory": None}, _THR))["memory"]
    assert s.count is None and s.due is False


def test_advisory_main_never_blocks_on_real_repo() -> None:
    # default (non-strict) always exits 0 regardless of counts
    assert cc.main([]) == 0
