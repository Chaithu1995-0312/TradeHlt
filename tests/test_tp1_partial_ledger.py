"""TP1 partial must reach the ledger (net-R trace, 2026-10-01).

The runner closes a trade on the bar `process_candle` reports TRADE_TP2 / TRADE_STOPPED. By then
`ExecutionEngine.update_trade` has already overwritten `trade.status` (TP1 -> TP2/STOPPED), so
reading the status AFTER `process_candle` made `_resolve_exit`'s TP1 blend branches unreachable:
CRT-0003 (run_20260930_163142) was booked entirely at TP2 although the engine banked half at TP1.

Existing `_resolve_exit` unit tests passed `trade_status="TP1"` by hand and could not see this. So:
  (1) drive a REAL engine trade through TP1 then TP2 / trail stop and feed `_resolve_exit` the
      status the trade ENTERED the closing bar with -> blended exit;
  (2) show the post-update status would have produced the unblended (wrong) exit;
  (3) source-order guard: the runner captures that status BEFORE calling process_candle and passes
      it to `_resolve_exit`.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from config_layer.crt_engine_v2 import CRTState, Direction
from runtime.backtest_v2 import _resolve_exit
from tests.test_entry_chain import _APPROVE, _BENIGN, _RETEST_BAR, _c, _engine, _step

_SRC = Path(__file__).resolve().parents[1] / "src" / "runtime" / "backtest_v2.py"


def _open_legacy_trade():
    eng = _engine("approval_bar_legacy", approve=_APPROVE)
    _step(eng, _c(0, *_RETEST_BAR))
    assert _step(eng, _c(1, *_BENIGN))["action"] == "TRADE_OPENED"
    t = eng.state.active_trade
    assert t.direction == Direction.LONG
    return eng, t


def _to_tp1(eng, t):
    r = _step(eng, _c(2, 92.6, t.tp1_price + 0.05, 92.4, t.tp1_price - 0.1))
    assert r["action"] == "TRADE_TP1" and t.status == "TP1"


def test_tp1_then_tp2_books_the_blend_not_the_full_tp2():
    eng, t = _open_legacy_trade()
    _to_tp1(eng, t)
    pre = t.status                                            # what the runner now captures
    candle = _c(3, t.tp1_price, t.tp2_price + 0.1, t.tp1_price - 0.1, t.tp2_price)
    r = _step(eng, candle)
    assert r["action"] == "TRADE_TP2" and t.status == "TP2"   # engine overwrote the status
    exit_raw, reason = _resolve_exit(r["action"], t, pre, candle, True, 0.5)
    assert reason == "TP1_TP2"
    assert exit_raw == pytest.approx(0.5 * t.tp1_price + 0.5 * t.tp2_price)
    # the engine's own accounting agrees with the blended exit
    assert t.pnl == pytest.approx(exit_raw - t.entry_price)
    # the OLD call (post-update status) books the full TP2 -- the defect
    assert _resolve_exit(r["action"], t, t.status, candle, True, 0.5) == (t.tp2_price, "TP2")


def test_tp1_then_trail_stop_books_the_blend():
    eng, t = _open_legacy_trade()
    _to_tp1(eng, t)
    trail = t.sl_price                                        # half-way trail set at TP1
    pre = t.status
    candle = _c(3, t.tp1_price - 0.2, t.tp1_price - 0.1, trail - 0.3, trail - 0.2)
    r = _step(eng, candle)
    assert r["action"] == "TRADE_STOPPED"
    exit_raw, reason = _resolve_exit(r["action"], t, pre, candle, True, 0.5)
    assert reason == "TP1_BE_STOP"
    assert exit_raw == pytest.approx(0.5 * t.tp1_price + 0.5 * trail)
    assert _resolve_exit(r["action"], t, t.status, candle, True, 0.5) == (trail, "STOPPED")


def test_tp_hit_counters_count_blended_partial_reasons():
    """Source pin (MetricsEngine.compute needs a full journal/capital to call). The behaviour is
    proved end-to-end by the full-corpus rerun: CRT-0003 closes as TP1_TP2 and the summary still
    reports tp1_hits=1, tp2_hits=1."""
    import inspect

    from runtime.backtest_v2 import MetricsEngine

    src = inspect.getsource(MetricsEngine.compute)
    assert 't.exit_reason.startswith("TP1_")' in src
    assert 't.exit_reason in ("TP2", "TP1_TP2")' in src


def test_runner_captures_status_before_process_candle_and_passes_it():
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    run = next(n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "run")
    capture = call = resolve = None
    for node in ast.walk(run):
        if (isinstance(node, ast.Assign) and capture is None
                and any(getattr(t, "id", None) == "_pre_trade_status" for t in node.targets)):
            capture = node.lineno
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "process_candle" and call is None):
            call = node.lineno
        if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_resolve_exit"
                and resolve is None):
            resolve = node
    assert capture and call and resolve is not None
    assert capture < call, "status must be captured BEFORE process_candle overwrites it"
    status_arg = resolve.args[2]
    assert isinstance(status_arg, ast.Name) and status_arg.id == "_trade_status"
    seg = ast.get_source_segment(_SRC.read_text(encoding="utf-8"), run)
    assert "_pre_trade_status if _pre_trade_status is not None" in seg
