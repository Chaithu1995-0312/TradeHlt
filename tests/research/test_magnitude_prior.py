"""Floor: SEM-028 agree rule, split, and both PRIMARYs are frozen before holdout y."""
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
from research.evidence.magnitude_prior import (  # noqa: E402
    OVERLAY_K,
    _agree,
    overlay_weighted_mean,
    split_rows,
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
    src = (_PKG / "magnitude_prior.py").read_text(encoding="utf-8")
    imported = _runtime_imports(ast.parse(src))
    hits = [m for m in FORBIDDEN if any(imp == m or imp.startswith(m + ".") for imp in imported)]
    assert hits == []


def test_agree_is_side_given_not_side_picker():
    assert _agree("long", 1) is True
    assert _agree("long", -1) is False
    assert _agree("short", -1) is True
    assert _agree("short", 1) is False
    assert _agree("long", 0) is None
    assert _agree("flat", 1) is None


def test_unit_rows_keep_side_and_drop_null_mfe():
    cols = {
        "decision_ts": [
            "2024-06-01 00:00:00",
            "2024-06-01 00:00:00",
            "2024-06-01 00:15:00",
            "2024-06-01 00:15:00",
        ],
        "side": ["long", "short", "long", "short"],
        "y_mfe_r": [2.0, 0.5, None, 1.0],
        "y_time_to_mfe": [3.0, 4.0, 5.0, 6.0],
        "features.trend_bias": [1.0, 1.0, 1.0, -1.0],
        "instrument": ["XAUUSD"] * 4,
        "outcome": ["SL_HIT"] * 4,
    }
    rows = unit_rows(cols)
    assert len(rows) == 3
    first = {r["side"]: r for r in rows if r["decision_ts"] == "2024-06-01 00:00:00"}
    assert first["long"]["agree"] is True
    assert first["long"]["y_mfe_r"] == pytest.approx(2.0)
    assert first["short"]["agree"] is False
    later = [r for r in rows if r["decision_ts"] == "2024-06-01 00:15:00"]
    assert len(later) == 1
    assert later[0]["side"] == "short"
    assert later[0]["agree"] is True


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
            "y_mfe_r": 0.1 * i,
            "y_time_to_mfe": 2.0,
        })
    train, hold, man = split_rows(rows)
    assert man["f086_stride_spent"] is False
    assert man["sem027_primary_not_retuned"] is True
    assert man["overlay_k_not_primary"] == OVERLAY_K
    assert all(r["ts"] >= HOLDOUT_START for r in hold)
    assert all(r["ts"] < HOLDOUT_START for r in train)
    gap = (min(r["ts"] for r in hold) - max(r["ts"] for r in train)).total_seconds() / 60
    assert gap >= 96 * 15


def test_verdict_independent_arms():
    train = {"agree": {"n": 100, "mean": 4.0}, "disagree": {"n": 80, "mean": 3.0}, "contrast": 1.0}
    hold_ok = {"agree": {"n": 40, "mean": 3.5}, "disagree": {"n": 40, "mean": 3.0}, "contrast": 0.5}
    hold_flip = {"agree": {"n": 40, "mean": 2.0}, "disagree": {"n": 40, "mean": 3.0}, "contrast": -1.0}
    hold_small = {"agree": {"n": 10, "mean": 4.0}, "disagree": {"n": 40, "mean": 3.0}, "contrast": 1.0}
    assert verdict(train, hold_ok) == "DIAGNOSTIC_PASS"
    assert verdict(train, hold_flip) == "DIAGNOSTIC_FAIL"
    assert verdict(train, hold_small) == "INSUFFICIENT"


def test_overlay_k_is_frozen_and_mean_preserving_when_balanced():
    assert OVERLAY_K == 0.5
    rows = (
        [{"agree": True, "y_mfe_r": 2.0}] * 50
        + [{"agree": False, "y_mfe_r": 2.0}] * 50
    )
    out = overlay_weighted_mean(rows)
    assert out["e_y"] == pytest.approx(2.0)
    assert out["e_w_y"] == pytest.approx(2.0)


def test_object_doc_forbids_side_picker():
    text = (_REPO / "docs" / "research" / "magnitude_prior_object.md").read_text(encoding="utf-8")
    assert "not a classifier of which side" in text.lower() or "not used to choose the side" in text.lower()
    assert "SEM-027" in text
    assert "P-GOAL-04" in text
    assert "k=0.5" in text
