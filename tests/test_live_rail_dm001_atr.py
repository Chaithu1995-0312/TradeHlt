"""PR-4a: FM-074 atr*close at the hook's compute_crt_levels site (was DM-001)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.gate_intelligence import compute_crt_levels

_HOOK = Path(__file__).resolve().parents[1] / "src" / "runtime" / "live_engine_hook.py"


def test_hook_crt_levels_arg_is_price_unit() -> None:
    """Lint heuristic: the atr= keyword must be _atr_abs (or atr * close), not engine_input['atr']."""
    tree = ast.parse(_HOOK.read_text(encoding="utf-8"))
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = None
        if isinstance(node.func, ast.Name):
            fname = node.func.id
        elif isinstance(node.func, ast.Attribute):
            fname = node.func.attr
        if fname != "compute_crt_levels":
            continue
        for kw in node.keywords:
            if kw.arg == "atr":
                calls.append(ast.unparse(kw.value))
    assert calls, "hook must still call compute_crt_levels(atr=...)"
    for text in calls:
        assert "engine_input['atr']" not in text or "*" in text
        assert "_atr_abs" in text or ("*" in text and "close" in text)


def test_xauusd_sl_buffer_uses_absolute_atr() -> None:
    """F-072 magnitude: close=2000, close-relative atr=0.0025 → atr_abs=5, 0.2*5=1.0 not 0.0005."""
    close = 2000.0
    atr_rel = 0.0025
    atr_abs = atr_rel * close
    assert atr_abs == 5.0
    entry = 2000.0
    low = 1998.0
    wrong = compute_crt_levels(
        entry=entry, direction=1, low=low, high=2001.0,
        atr=atr_rel, sl_atr_buffer=0.2, tp1_mult=1.0, tp2_mult=2.0,
    )
    right = compute_crt_levels(
        entry=entry, direction=1, low=low, high=2001.0,
        atr=atr_abs, sl_atr_buffer=0.2, tp1_mult=1.0, tp2_mult=2.0,
    )
    # Relative ATR: sl ≈ 1998 - 0.0005 = 1997.9995 (buffer vanishes).
    assert abs((low - wrong["sl"]) - 0.0005) < 1e-9
    # Absolute ATR: sl = 1998 - 1.0 = 1997.
    assert right["sl"] == 1997.0
    assert (low - right["sl"]) / (low - wrong["sl"]) == pytest.approx(2000.0)
