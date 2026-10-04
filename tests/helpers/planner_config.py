"""Complete ExecutionPlannerV1_2 config for tests (EPIC-84: the planner has no defaults).

``LEGACY_PLANNER_VALUES_2026_09_28`` is exactly the former module-level
``execution_planner.DEFAULT_CONFIG`` (removed 2026-09-28; it was merged UNDER every config so a
missing key silently took these code values). Tests that relied on it keep the same inputs,
now declared here. Production builds the planner config with
``execution_planner.planner_config_from_production``. TEST FIXTURE ONLY.
"""
from __future__ import annotations

LEGACY_PLANNER_VALUES_2026_09_28 = {
    "ttl_breakout_sec": 180,
    "ttl_pullback_sec": 300,
    "ttl_reversal_sec": 120,
    "ttl_liq_sweep_sec": 240,
    "ttl_continuation_sec": 180,
    "ttl_unknown_sec": 180,
    "risk_percent": 0.5,
    "precision_default": 8,
    "precision_overrides": {"XAUUSD": 2, "BTCUSDT": 2, "ETHUSDT": 2},
    "default_account_balance": 10_000.0,
    "reject_unknown_intent": True,
    # Added 2026-10-03 (CH-planner-liq-sweep-direction); not part of the former DEFAULT_CONFIG.
    # legacy_unsigned is the pre-existing classifier behaviour.
    "liq_sweep_semantics": "legacy_unsigned",
    "breakout_disp_threshold": 1.5,
    "gate_weight_intent": 0.35,
    "gate_weight_vol": 0.20,
    "gate_weight_liquidity": 0.20,
    "gate_weight_structure": 0.25,
    "gate_approval_threshold": 0.55,
}


def planner_test_config(**overrides) -> dict:
    """A complete planner config: legacy values + overrides (fresh dicts each call)."""
    cfg = dict(LEGACY_PLANNER_VALUES_2026_09_28)
    cfg["precision_overrides"] = dict(cfg["precision_overrides"])
    cfg.update(overrides)
    return cfg
