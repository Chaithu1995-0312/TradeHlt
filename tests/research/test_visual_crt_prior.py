"""Floor: SEM-032 sparse Visual CRT entries x trend prior is frozen before holdout y.

The sparse independent signal is the SEM-012 entry set, not every-bar and not SEM-026.
"""
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
from research.evidence.visual_crt_prior import (  # noqa: E402
    CONTRACT_ID,
    SEM_ID,
    VISUAL_ARMS,
    _arm_cells,
    split_rows,
    unit_rows,
    verdict,
)

_PKG = _SRC / "research" / "evidence"
FORBIDDEN = (
    "config_layer.crt_engine_v2",
    "runtime.backtest_v2",
    "core.engine_runner",
    "mother_range.driver",
    "visual_crt.measure",
    "TradeLib",
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


def test_measurer_does_not_import_spine_or_trade_ledger():
    src = (_PKG / "visual_crt_prior.py").read_text(encoding="utf-8")
    imported = _runtime_imports(ast.parse(src))
    hits = [m for m in FORBIDDEN if any(imp == m or imp.startswith(m + ".") for imp in imported)]
    assert hits == [], f"measurer must not import {hits}"


def test_contract_and_sem_ids():
    assert CONTRACT_ID == "MC-VCRTPRIOR-XAUUSD-M15-V1"
    assert SEM_ID == "SEM-032"
    assert VISUAL_ARMS == ("A", "B")


def test_unit_rows_empty_gracefully():
    assert unit_rows({}, []) == []


def test_arm_cells_contrast_and_agree_buckets():
    rows = (
        [{"agree": True, "y_mfe_r": 5.0}] * 40
        + [{"agree": False, "y_mfe_r": 3.0}] * 60
    )
    out = _arm_cells(rows, "y_mfe_r")
    assert out["agree"]["n"] == 40
    assert out["disagree"]["n"] == 60
    assert out["contrast"] == pytest.approx(2.0)
    assert out["n_trend_zero_or_unknown"] == 0


def test_split_matches_mc_asym_calendar_and_f086_unspent():
    rows = []
    for i, delta_days in enumerate(range(-40, 10)):
        ts = HOLDOUT_START + timedelta(days=delta_days)
        rows.append({
            "decision_ts": ts.isoformat(sep=" "),
            "ts": ts,
            "instrument": "XAUUSD",
            "side": "long",
            "visual_arm": "A",
            "trend_bias": 1,
            "agree": True,
            "y_mfe_r": 0.01 * i,
            "y_time_to_mfe": 1.0,
        })
    train, hold, man = split_rows(rows)
    assert man["f086_stride_spent"] is False
    assert man["f081_entry_fraction_oos_spent"] is False
    assert man["sparse_signal_is_sem012_entries"] is True
    assert man["sem030_not_retuned"] is True
    assert all(r["ts"] >= HOLDOUT_START for r in hold)
    assert all(r["ts"] < HOLDOUT_START for r in train)


def test_verdict_insufficient_when_holdout_agree_cell_is_small():
    train = {"agree": {"n": 100}, "disagree": {"n": 80}, "contrast": 0.5}
    hold_small = {"agree": {"n": 9}, "disagree": {"n": 55}, "contrast": 0.1}
    assert verdict(train, hold_small) == "INSUFFICIENT"


def test_verdict_pass_and_fail_on_sign_match():
    tr = {"agree": {"n": 100}, "disagree": {"n": 80}, "contrast": 1.0}
    ok = {"agree": {"n": 40}, "disagree": {"n": 40}, "contrast": 0.2}
    flip = {"agree": {"n": 40}, "disagree": {"n": 40}, "contrast": -0.2}
    assert verdict(tr, ok) == "DIAGNOSTIC_PASS"
    assert verdict(tr, flip) == "DIAGNOSTIC_FAIL"


def test_object_doc_forbids_f081_y_and_sem030_retune():
    text = (_REPO / "docs" / "research" / "visual_crt_prior_object.md").read_text(encoding="utf-8")
    low = text.lower()
    assert "sem-012" in low
    assert "sem-028" in low
    assert "f-081" in low
    assert "f-094" in low
    assert "every-bar" in low
    assert "p-goal-04" in low
    assert "f-086" in low
    assert "g001" in low
    assert "mother-range" in low
