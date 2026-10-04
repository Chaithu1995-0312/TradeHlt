"""Floor: SEM-027 pairing, split, and PRIMARY contrast are frozen before holdout y."""
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

from research.evidence.asymmetry_contract import (  # noqa: E402
    HOLDOUT_START,
    contrast_trend_bias,
    pair_rows,
    split_pairs,
    verdict,
)

_PKG = _SRC / "research" / "evidence"
FORBIDDEN = (
    "config_layer.crt_engine_v2",
    "runtime.backtest_v2",
    "TradeLib",
    "xgboost",
)


def _runtime_imports(tree: ast.Module) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def test_measurer_does_not_import_spine():
    src = (_PKG / "asymmetry_contract.py").read_text(encoding="utf-8")
    imported = _runtime_imports(ast.parse(src))
    hits = [m for m in FORBIDDEN if any(imp == m or imp.startswith(m + ".") for imp in imported)]
    assert hits == []


def test_pair_rows_requires_both_sides_and_uses_mfe_not_stream():
    cols = {
        "decision_ts": ["2024-06-01 00:00:00", "2024-06-01 00:00:00", "2024-06-01 00:15:00"],
        "side": ["long", "short", "long"],
        "y_mfe_r": [2.0, 0.5, 1.0],
        "outcome": ["SL_HIT", "SL_HIT", "SL_HIT"],
        "features.trend_bias": [1.0, 1.0, 1.0],
        "instrument": ["XAUUSD"] * 3,
    }
    pairs = pair_rows(cols)
    assert len(pairs) == 1
    assert pairs[0]["delta_mfe"] == pytest.approx(1.5)


def test_split_embargo_and_holdout_date():
    base = HOLDOUT_START
    rows = []
    for i, delta_days in enumerate(range(-40, 10)):
        ts = base + timedelta(days=delta_days)
        rows.append({
            "decision_ts": ts.isoformat(sep=" "),
            "ts": ts,
            "instrument": "XAUUSD",
            "delta_mfe": 0.1 * i,
            "trend_bias": 1.0,
            "session": 0.0,
            "volatility": 0.0,
        })
    train, hold, man = split_pairs(rows)
    assert man["f086_stride_spent"] is False
    assert all(r["ts"] >= HOLDOUT_START for r in hold)
    assert all(r["ts"] < HOLDOUT_START for r in train)
    gap = (min(r["ts"] for r in hold) - max(r["ts"] for r in train)).total_seconds() / 60
    assert gap >= 96 * 15


def test_verdict_sign_match_and_insufficient():
    train = {"plus": {"n": 100, "e_delta_mfe": 0.4}, "minus": {"n": 80, "e_delta_mfe": -0.1}, "contrast": 0.5}
    hold_ok = {"plus": {"n": 40, "e_delta_mfe": 0.2}, "minus": {"n": 40, "e_delta_mfe": 0.0}, "contrast": 0.2}
    hold_flip = {"plus": {"n": 40, "e_delta_mfe": -0.2}, "minus": {"n": 40, "e_delta_mfe": 0.1}, "contrast": -0.3}
    hold_small = {"plus": {"n": 10, "e_delta_mfe": 0.2}, "minus": {"n": 40, "e_delta_mfe": 0.0}, "contrast": 0.2}
    assert verdict(train, hold_ok, 80) == "DIAGNOSTIC_PASS"
    assert verdict(train, hold_flip, 80) == "DIAGNOSTIC_FAIL"
    assert verdict(train, hold_small, 50) == "INSUFFICIENT"


def test_trend_bias_contrast_arithmetic():
    rows = (
        [{"delta_mfe": 1.0, "trend_bias": 1.0}] * 30
        + [{"delta_mfe": -0.5, "trend_bias": -1.0}] * 30
    )
    c = contrast_trend_bias(rows)
    assert c["contrast"] == pytest.approx(1.5)
