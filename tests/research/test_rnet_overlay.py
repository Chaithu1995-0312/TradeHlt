"""Floor: SEM-029 overlay k, independent entry, and PRIMARY are frozen before holdout y."""
from __future__ import annotations

import ast
import sys
from datetime import timedelta
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.evidence.asymmetry_contract import HOLDOUT_START  # noqa: E402
from research.evidence.magnitude_prior import OVERLAY_K, split_rows  # noqa: E402
from research.evidence.rnet_overlay import (  # noqa: E402
    K,
    overlay,
    unit_rows,
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
    src = (_PKG / "rnet_overlay.py").read_text(encoding="utf-8")
    imported = _runtime_imports(ast.parse(src))
    hits = [m for m in FORBIDDEN if any(imp == m or imp.startswith(m + ".") for imp in imported)]
    assert hits == []


def test_k_is_frozen_and_is_primary():
    assert K == 0.5
    assert K == OVERLAY_K


def test_unit_rows_require_y_r_net_not_mfe():
    cols = {
        "decision_ts": ["2024-06-01 00:00:00", "2024-06-01 00:00:00", "2024-06-01 00:15:00"],
        "side": ["long", "short", "long"],
        "y_R_net": [0.2, -1.0, None],
        "y_mfe_r": [9.0, 9.0, 9.0],
        "features.trend_bias": [1.0, 1.0, 1.0],
        "instrument": ["XAUUSD"] * 3,
        "outcome": ["SL_HIT"] * 3,
    }
    rows = unit_rows(cols)
    assert len(rows) == 2
    by_side = {r["side"]: r for r in rows}
    assert by_side["long"]["y_R_net"] == pytest.approx(0.2)
    assert by_side["long"]["agree"] is True
    assert by_side["short"]["agree"] is False
    assert "y_mfe_r" not in by_side["long"]


def test_overlay_delta_is_quarter_contrast_when_balanced():
    rows = (
        [{"agree": True, "y_R_net": 1.0}] * 50
        + [{"agree": False, "y_R_net": -1.0}] * 50
    )
    out = overlay(rows)
    assert out["contrast"] == pytest.approx(2.0)
    assert out["delta"] == pytest.approx(0.5)
    assert out["e_y"] == pytest.approx(0.0)
    assert out["e_w_y"] == pytest.approx(0.5)


def test_split_matches_mc_asym_calendar():
    rows = []
    for i, delta_days in enumerate(range(-40, 10)):
        ts = HOLDOUT_START + timedelta(days=delta_days)
        rows.append({
            "decision_ts": ts.isoformat(sep=" "),
            "ts": ts,
            "instrument": "XAUUSD",
            "side": "long",
            "trend_bias": 1,
            "agree": True,
            "y_R_net": 0.01 * i,
        })
    train, hold, man = split_rows(rows)
    assert man["f086_stride_spent"] is False
    assert all(r["ts"] >= HOLDOUT_START for r in hold)
    assert all(r["ts"] < HOLDOUT_START for r in train)


def test_verdict_on_overlay_delta_not_expectancy():
    train = {
        "delta": 0.05,
        "agree": {"n": 100},
        "disagree": {"n": 80},
        "e_y": -0.4,
    }
    hold_ok = {
        "delta": 0.02,
        "agree": {"n": 40},
        "disagree": {"n": 40},
        "e_y": -0.5,
    }
    hold_flip = {
        "delta": -0.02,
        "agree": {"n": 40},
        "disagree": {"n": 40},
        "e_y": -0.5,
    }
    hold_small = {
        "delta": 0.02,
        "agree": {"n": 10},
        "disagree": {"n": 40},
        "e_y": -0.5,
    }
    assert verdict(train, hold_ok) == "DIAGNOSTIC_PASS"
    assert verdict(train, hold_flip) == "DIAGNOSTIC_FAIL"
    assert verdict(train, hold_small) == "INSUFFICIENT"


def test_object_doc_forbids_side_picker_and_cost_retune():
    text = (_REPO / "docs" / "research" / "rnet_size_overlay_object.md").read_text(encoding="utf-8")
    low = text.lower()
    assert "does not choose the entry" in low or "not choose the side" in low
    assert "sem-015" in low
    assert "p-goal-04" in low
    assert "e>0" in low
    assert "k=0.5" in low
