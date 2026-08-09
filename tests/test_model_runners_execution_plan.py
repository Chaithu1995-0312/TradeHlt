"""Floor: the execution_plan adapter emits a COMPLETE executable trade plan (A5).

Context — this adapter is a RETRACTION. It was previously registered
BLOCKED_BY_DESIGN on the claim "ExecutionPlanner does not produce SL/TP/RR". That
is true of ``plan()`` alone but described a COMPONENT as if it were the PIPELINE:
``live_engine_hook.process()`` composes plan() -> compute_crt_levels -> geometric
RR -> position sizing, and THAT chain does produce a full executable trade. These
tests pin that the adapter reproduces the chain rather than a fragment of it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research.model_runners.adapters import build_adapter  # noqa: E402
from research.model_runners.contracts import get_contract  # noqa: E402

CONFIG_PATH = ROOT / "configs" / "production" / "v2_multi_2026_04.json"

# Fields that only a COMPLETE trade plan carries.
_EXECUTABLE_FIELDS = (
    "entry_price",
    "stop_loss",
    "take_profit_1",
    "take_profit_2",
    "rr_ratio",
    "rr_ratio_tp2",
    "rr_source",
    "position_size_hint",
)


@pytest.fixture(scope="module")
def prod_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def adapter(prod_config):
    return build_adapter(
        "execution_plan",
        prod_config=prod_config,
        instrument="XAUUSD",
        repo_root=ROOT,
    )


# ── registration ─────────────────────────────────────────────────────────────

def test_execution_plan_is_runnable_not_blocked():
    """The BLOCKED_BY_DESIGN classification was retracted — pin that."""
    c = get_contract("execution_plan")
    assert c.runnable is True
    assert c.audit_status != "BLOCKED_BY_DESIGN"
    assert c.input_mode == "compose"


# ── strict config sourcing (no silent defaults) ──────────────────────────────

def test_balance_comes_from_config_not_an_invented_default(adapter, prod_config):
    expected = float(prod_config["execution_planner"]["default_account_balance"])
    assert adapter.artifact_info["account_balance_value"] == expected
    assert (
        adapter.artifact_info["account_balance_source"]
        == "execution_planner.default_account_balance"
    )


def test_fails_closed_when_balance_key_absent(prod_config):
    broken = json.loads(json.dumps(prod_config))
    del broken["execution_planner"]["default_account_balance"]
    with pytest.raises(KeyError, match="default_account_balance"):
        build_adapter(
            "execution_plan",
            prod_config=broken,
            instrument="XAUUSD",
            repo_root=ROOT,
        )


def test_divergences_from_live_are_declared_not_silent(adapter):
    info = adapter.artifact_info
    assert info["ultron_risk_gate_invoked"] is False
    assert info["regime_governor_allow_gate_applied"] is False
    assert len(info["declared_divergences"]) >= 4


# ── per-intent TP multipliers (depend on the C3 crt_engine plumbing) ─────────

def test_per_intent_tp_multipliers_resolve(adapter):
    """Before C3 every intent collapsed to 1.0; they must now differ."""
    assert adapter._tp_multipliers("BREAKOUT")[0] == 1.5
    assert adapter._tp_multipliers("LIQ_SWEEP")[0] == 1.2
    assert adapter._tp_multipliers("PULLBACK")[0] == 0.8
    assert adapter._tp_multipliers("REVERSAL")[0] == 1.0
    assert adapter._tp_multipliers("BREAKOUT")[1] == 2.0


# ── the composition itself ───────────────────────────────────────────────────

def _run_bars(adapter, limit: int = 400) -> list[dict]:
    from research.model_runners.substrate import (
        build_feature_substrate,
        iter_bar_contexts,
        select_window,
    )

    csv = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
    if not csv.is_file():
        pytest.skip(f"XAUUSD corpus absent: {csv}")
    sub = build_feature_substrate(csv)
    window = select_window(sub.enriched, start=None, end=None, limit=limit)
    return [adapter.score_bar(bar) for bar in iter_bar_contexts(window)]


@pytest.mark.slow
def test_executing_bars_carry_a_complete_trade_plan(adapter):
    outs = _run_bars(adapter)
    assert outs, "no bars scored"
    executed = [o for o in outs if o.get("levels_computed")]
    if not executed:
        pytest.skip("no execute decision in the sampled window")
    for o in executed:
        for field in _EXECUTABLE_FIELDS:
            assert field in o, f"executable plan missing {field}"
        assert o["rr_source"] == "sl_tp_geometry"
        assert o["position_size_hint"] is None or o["position_size_hint"] > 0


@pytest.mark.slow
def test_rr_ratio_is_true_sl_tp_geometry(adapter):
    """RR must equal |TP1-entry| / |entry-SL| recomputed independently."""
    outs = _run_bars(adapter)
    executed = [o for o in outs if o.get("levels_computed")]
    if not executed:
        pytest.skip("no execute decision in the sampled window")
    for o in executed:
        entry = float(o["entry_price"])
        risk = abs(entry - float(o["stop_loss"]))
        assert risk > 0
        expected = round(abs(float(o["take_profit_1"]) - entry) / risk, 6)
        assert o["rr_ratio"] == pytest.approx(expected, abs=1e-6)
        expected2 = round(abs(float(o["take_profit_2"]) - entry) / risk, 6)
        assert o["rr_ratio_tp2"] == pytest.approx(expected2, abs=1e-6)


@pytest.mark.slow
def test_non_executing_bars_do_not_fabricate_levels(adapter):
    """A rejected plan must NOT carry SL/TP/RR — exactly as live gates it."""
    outs = _run_bars(adapter)
    rejected = [o for o in outs if not o.get("levels_computed")]
    assert rejected, "expected some rejected bars"
    for o in rejected:
        assert "stop_loss" not in o
        assert "take_profit_1" not in o
        assert "rr_ratio" not in o


# ── config-coherence consequence of C3 (documented, not asserted as desired) ──

def test_rr_equals_tp1_multiplier_by_construction(prod_config):
    """compute_crt_levels sets tp1 = entry + dir*tp1_mult*risk_dist.

    Therefore |TP1-entry|/risk_dist == tp1_mult exactly, i.e. the emitted RR for
    an intent IS that intent's configured multiplier. Pinned because it makes the
    min_rr_ratio comparison below a pure config question.
    """
    from core.gate_intelligence import compute_crt_levels

    crt = compute_crt_levels(
        entry=100.0, direction=1, low=99.0, high=101.0, atr=1.0,
        sl_atr_buffer=0.2, tp1_mult=1.5, tp2_mult=2.0,
    )
    rr = abs(crt["tp1"] - 100.0) / abs(100.0 - crt["sl"])
    assert rr == pytest.approx(1.5, abs=1e-9)


def test_only_breakout_clears_min_rr_ratio_under_current_config(prod_config):
    """CONFIG-COHERENCE FINDING surfaced by the C3 fix (documents, does not bless).

    Because RR == tp1_mult, and ultron_risk_gate.min_rr_ratio == 1.5, only the
    breakout intent can produce an Ultron-approvable plan; liq_sweep (1.2),
    pullback (0.8) and reversal (1.0) are all below the gate. Before C3 every
    intent was 1.0 and the path crashed before Ultron anyway. If these
    multipliers are later retuned, this test should be updated deliberately.
    """
    crt = prod_config["crt_engine"]
    min_rr = float(prod_config["ultron_risk_gate"]["min_rr_ratio"])
    resolved = {
        intent: float(
            crt.get(f"tp1_atr_multiplier_{intent}", crt["tp1_atr_multiplier"])
        )
        for intent in ("breakout", "liq_sweep", "pullback", "reversal")
    }
    clears = {k: v >= min_rr for k, v in resolved.items()}
    assert clears["breakout"] is True
    assert clears["liq_sweep"] is False
    assert clears["pullback"] is False
    assert clears["reversal"] is False
