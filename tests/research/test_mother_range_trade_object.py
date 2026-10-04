"""Floor: SEM-026 geometry is causal, isolated, and frozen before outcomes."""
from __future__ import annotations

import ast
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.mother_range.geometry import (  # noqa: E402
    Bar,
    detect_inside_close_entries,
)

_PKG = _SRC / "research" / "mother_range"
FORBIDDEN_RUNTIME_MODULES = (
    "config_layer.crt_engine_v2",
    "config_layer.m15_structural_range",
    "runtime.backtest_v2",
    "TradeLib",
    "trade_lib",
)
BASE = datetime(2024, 1, 1, 0, 0)


def _runtime_imports(tree: ast.Module):
    type_only: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        guarded = (
            (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
            or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
        )
        if guarded:
            for inner in node.body:
                type_only.add(id(inner))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in type_only:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


@pytest.mark.parametrize("rel", ["geometry.py", "driver.py", "__init__.py"])
def test_no_crt_engine_import(rel: str):
    src = (_PKG / rel).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = _runtime_imports(tree)
    hits = [m for m in FORBIDDEN_RUNTIME_MODULES if any(
        imp == m or imp.startswith(m + ".") for imp in imported
    )]
    assert hits == [], f"{rel} imports forbidden producers: {hits}"


def _bar(idx: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(
        timestamp=BASE + timedelta(minutes=15 * idx),
        open=o, high=h, low=l, close=c, volume=1.0, index=idx,
    )


def _block(block_i: int, high: float, low: float, last_close: float) -> list[Bar]:
    """16 bars in one 4H calendar window starting at block_i * 16."""
    start = block_i * 16
    bars = []
    mid = (high + low) / 2
    for j in range(16):
        close = last_close if j == 15 else mid
        bars.append(_bar(start + j, mid, high, low, close))
    return bars


def test_inside_lower_half_is_long():
    # 21 prior wide blocks so lookback=20 is satisfied, then mother+test.
    bars: list[Bar] = []
    for i in range(21):
        bars.extend(_block(i, 110.0, 100.0, 105.0))
    # mother block 21: range 20
    bars.extend(_block(21, 120.0, 100.0, 110.0))
    # test block 22: close inside lower half (102)
    bars.extend(_block(22, 108.0, 101.0, 102.0))
    found = detect_inside_close_entries(bars)
    assert found, "expected an inside-close long"
    last = found[-1]
    assert last.direction == "long"
    assert last.entry == 102.0
    assert last.sl == 100.0
    assert last.tp == 120.0


def test_outside_close_is_not_an_entry():
    bars: list[Bar] = []
    for i in range(21):
        bars.extend(_block(i, 110.0, 100.0, 105.0))
    bars.extend(_block(21, 120.0, 100.0, 110.0))
    bars.extend(_block(22, 130.0, 125.0, 128.0))  # C2 outside mother
    found = detect_inside_close_entries(bars)
    assert all(ev.entry_index != 22 * 16 + 15 for ev in found)


def test_small_mother_is_not_an_entry():
    bars: list[Bar] = []
    for i in range(21):
        bars.extend(_block(i, 130.0, 100.0, 115.0))  # prior ranges 30
    bars.extend(_block(21, 101.0, 100.0, 100.5))  # tiny mother
    bars.extend(_block(22, 100.8, 100.2, 100.3))
    found = detect_inside_close_entries(bars)
    assert not any(ev.entry_index == 22 * 16 + 15 for ev in found)
