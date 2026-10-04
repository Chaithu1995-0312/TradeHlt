"""REM-COST-04: L5 COST_MODEL_IDS includes production backtest stamp ids."""
from __future__ import annotations

from identity.tokens import COST_MODEL_IDS, L5_BASIS


def test_cost_model_ids_includes_backtest_g1g2_v2():
    assert "backtest_g1g2_v2" in COST_MODEL_IDS
    assert "backtest_zero_cost" in COST_MODEL_IDS  # reserve-only
    # prior research set preserved
    assert {"flat_12bps", "sem015_component_xauusd", "none_gross"} <= COST_MODEL_IDS


def test_fresh_stamp_id_is_l5_closed():
    """Stamp measured on run_20260916_225925_XAUUSD must be certifiable."""
    stamped = "backtest_g1g2_v2"
    assert stamped in COST_MODEL_IDS


def test_unknown_cost_model_rejected_by_membership():
    assert "metals_mt5_v1" not in COST_MODEL_IDS  # alias doc only until wiring
    assert "g1g2" not in COST_MODEL_IDS


def test_l5_basis_unchanged():
    assert L5_BASIS == ("walk_kernel", "cost_model_id", "fill_model_id")
