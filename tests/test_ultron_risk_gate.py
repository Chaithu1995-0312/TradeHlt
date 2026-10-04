"""
test_ultron_risk_gate.py
========================
Dedicated test suite for UltronRiskGate — the final capital-protection layer.

Covers (GAP-001):
    - Approval path (happy path)
    - Rejection paths: drawdown breach, exposure breach, RR floor,
      daily trade limit, expired TTL, malformed TTL, invalid SL distance,
      zero position size
    - Position sizing: hint capping, no-hint fallback, hint larger than max
    - Daily reset behaviour (trades_today boundary)
    - Config overrides
    - Portfolio state returned on approve vs reject

Run:
    python test_ultron_risk_gate.py
    pytest test_ultron_risk_gate.py -v
"""

from __future__ import annotations
import sys
from datetime import datetime, timedelta, timezone

import pytest
from config_layer.strict_config import ConfigKeyMissingError
from core.ultron_risk_gate import UltronRiskGate

# EPIC-84 STORY-84.2: no DEFAULT_CONFIG. Tests pass an explicit, complete ultron_risk_gate
# section (the values of the active config v2_htfcrt_2026_08) and override per test.
_CFG = {
    "disabled":               False,
    "max_risk_per_trade_pct": 1.0,
    "max_portfolio_risk_pct": 5.0,
    "max_trades_per_day":     10,
    "max_daily_loss_pct":     3.0,
    "min_rr_ratio":           1.5,
    "spread_pips":            0.0,
    "slippage_pips":          0.0,
    "pip_size":               0.0001,
    "min_sl_pips":            0.0,
}

# D11 (2026-09-30): sizing (Check 7) now converts an INR risk budget into broker LOTS
# via core.position_sizing.size_trade_lots, which needs an instrument spec + a USD/INR
# rate injected at construction. This test-only spec is an IDENTITY conversion
# (contract_size=1, rate=1.0, a lot_step fine enough not to perturb any pre-D11 test
# number) so every existing test's numeric assertion (e.g. "size = balance * risk% /
# risk_per_unit = 25.0") keeps meaning oz-for-oz — this suite is testing Ultron's risk
# arithmetic, not the lot-conversion arithmetic (that lives in test_position_sizing.py).
_TEST_SYMBOL = "TEST"
_TEST_INSTRUMENT_SPECS = {
    _TEST_SYMBOL: {"contract_size": 1.0, "lot_step": 0.0001, "lot_min": 0.0001, "lot_max": 1e9},
}
_TEST_USD_INR_RATE = 1.0


def _mk(overrides: dict | None = None, *, instrument_specs=_TEST_INSTRUMENT_SPECS,
        usd_inr_rate: float | None = _TEST_USD_INR_RATE) -> UltronRiskGate:
    return UltronRiskGate(
        {**_CFG, **(overrides or {})},
        instrument_specs=instrument_specs, usd_inr_rate=usd_inr_rate,
    )


# ── Kill-switch isolation fixture ─────────────────────────────────────────────
# The kill switch persists to disk (logs/kill_switch_state.json).
# Any test that trips it contaminates later tests that read persisted state.
# Reset before AND after each test to keep tests fully isolated.

@pytest.fixture(autouse=True)
def _reset_kill_switch():
    """Reset UltronRiskGate kill switch before and after every test in this file."""
    _gate = _mk()
    _gate.reset_kill_switch()
    yield
    _gate.reset_kill_switch()


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _future_ts(seconds: int = 300) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()

def _past_ts(seconds: int = 60) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()

BASE_TRADE = {
    "execution_id":       "EX_test001",
    "symbol":             _TEST_SYMBOL,
    "entry_price":        100.0,
    "stop_loss":          98.0,       # risk_per_unit = 2.0
    "take_profit_1":      104.0,
    "rr_ratio":           2.0,
    "risk_percent":       0.5,
    "position_size_hint": None,
    "expires_at":         None,       # overridden per test
}

BASE_PORTFOLIO = {
    "account_balance":     10_000.0,
    "total_open_risk_pct": 1.0,
    "trades_today":        2,
    "daily_loss_pct":      0.5,
    "open_positions":      2,
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _trade(**overrides) -> dict:
    return {**BASE_TRADE, **overrides}

def _portfolio(**overrides) -> dict:
    return {**BASE_PORTFOLIO, **overrides}


# ── 1. APPROVAL PATH ─────────────────────────────────────────────────────────

def test_happy_path_approve():
    """All checks pass → approve with correct position size."""
    gate = _mk()
    trade = _trade(expires_at=_future_ts(), risk_percent=0.5, position_size_hint=None)
    result = gate.evaluate(trade, _portfolio())

    assert result["decision"] == "approve", result
    assert result["risk_reason"] == "ok"
    assert result["final_position_size"] > 0

    # size = balance * risk% / risk_per_unit = 10000 * 0.005 / 2 = 25.0
    assert abs(result["final_position_size"] - 25.0) < 1e-4

def test_approve_updates_portfolio_state():
    """Returned portfolio_state reflects new total_risk."""
    gate = _mk()
    trade = _trade(expires_at=_future_ts(), risk_percent=0.5)
    ps = _portfolio(total_open_risk_pct=1.0)
    result = gate.evaluate(trade, ps)

    assert result["decision"] == "approve"
    assert abs(result["portfolio_state"]["total_risk"] - 1.5) < 1e-4

def test_approve_no_expires_at():
    """Missing expires_at skips TTL check — should still approve."""
    gate = _mk()
    trade = _trade(expires_at=None)
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "approve"

def test_approve_execution_id_propagated():
    gate = _mk()
    trade = _trade(execution_id="EX_unique_XYZ")
    result = gate.evaluate(trade, _portfolio())
    assert result["execution_id"] == "EX_unique_XYZ"


# ── 2. TTL ENFORCEMENT ────────────────────────────────────────────────────────

def test_reject_expired_signal():
    gate = _mk()
    trade = _trade(expires_at=_past_ts(60))
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "expired_signal"

def test_reject_malformed_expires_at():
    """Unparseable timestamp is treated as expired for safety."""
    gate = _mk()
    trade = _trade(expires_at="not-a-date")
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "malformed_expires_at"

def test_approve_signal_just_not_expired():
    """Signal expiring in 1 second should pass."""
    gate = _mk()
    trade = _trade(expires_at=_future_ts(1))
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "approve"

def test_naive_datetime_treated_as_utc():
    """Naive ISO timestamp (no tz suffix) is accepted as UTC."""
    gate = _mk()
    future_naive = (datetime.utcnow() + timedelta(hours=1)).isoformat()  # no tz suffix
    trade = _trade(expires_at=future_naive)
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "approve"


# ── 3. RR FLOOR ──────────────────────────────────────────────────────────────

def test_reject_rr_below_minimum():
    gate = _mk()
    trade = _trade(rr_ratio=1.0)  # default min is 1.5
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] in ("rr_too_low", "rr_too_low_after_costs")

def test_reject_rr_exactly_below_minimum():
    gate = _mk({"min_rr_ratio": 2.0})
    trade = _trade(rr_ratio=1.99)
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] in ("rr_too_low", "rr_too_low_after_costs")

def test_approve_rr_exactly_at_minimum():
    gate = _mk({"min_rr_ratio": 2.0})
    trade = _trade(rr_ratio=2.0)
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "approve"

def test_approve_rr_above_minimum():
    gate = _mk()
    trade = _trade(rr_ratio=3.5)
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "approve"


# ── 4. DAILY TRADE LIMIT ─────────────────────────────────────────────────────

def test_reject_daily_limit_reached():
    gate = _mk({"max_trades_per_day": 5})
    ps = _portfolio(trades_today=5)   # at the limit
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "daily_limit"

def test_reject_daily_limit_exceeded():
    gate = _mk({"max_trades_per_day": 5})
    ps = _portfolio(trades_today=10)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "daily_limit"

def test_approve_one_below_daily_limit():
    """trades_today = limit - 1 should pass."""
    gate = _mk({"max_trades_per_day": 5})
    ps = _portfolio(trades_today=4)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "approve"

def test_daily_reset_zero_trades():
    """At start of day (trades_today=0) should never reject on this check alone."""
    gate = _mk()
    ps = _portfolio(trades_today=0)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "approve"


# ── 5. KILL SWITCH — DRAWDOWN BREACH ─────────────────────────────────────────

def test_reject_kill_switch_exact_threshold():
    gate = _mk({"max_daily_loss_pct": 3.0})
    ps = _portfolio(daily_loss_pct=3.0)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "kill_switch"

def test_reject_kill_switch_above_threshold():
    gate = _mk()
    ps = _portfolio(daily_loss_pct=5.0)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "kill_switch"

def test_approve_daily_loss_below_threshold():
    gate = _mk({"max_daily_loss_pct": 3.0})
    ps = _portfolio(daily_loss_pct=2.99)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "approve"

def test_approve_zero_daily_loss():
    gate = _mk()
    ps = _portfolio(daily_loss_pct=0.0)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "approve"


# ── 6. PORTFOLIO EXPOSURE CAP ─────────────────────────────────────────────────

def test_reject_over_exposure_exact():
    """open_risk + allowed_risk > max_portfolio_risk_pct → reject."""
    gate = _mk({"max_portfolio_risk_pct": 5.0})
    ps = _portfolio(total_open_risk_pct=4.8)
    trade = _trade(risk_percent=0.5)  # 4.8 + 0.5 = 5.3 > 5.0
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "over_exposure"

def test_reject_over_exposure_already_at_cap():
    gate = _mk({"max_portfolio_risk_pct": 5.0})
    ps = _portfolio(total_open_risk_pct=5.0)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "over_exposure"

def test_approve_exposure_just_under_cap():
    gate = _mk({"max_portfolio_risk_pct": 5.0})
    ps = _portfolio(total_open_risk_pct=4.4)
    trade = _trade(risk_percent=0.5)  # 4.4 + 0.5 = 4.9 <= 5.0
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "approve"

def test_exposure_risk_capped_at_per_trade_max():
    """risk_percent > max_risk_per_trade_pct → allowed_risk is capped."""
    gate = _mk({"max_risk_per_trade_pct": 1.0, "max_portfolio_risk_pct": 5.0})
    ps = _portfolio(total_open_risk_pct=4.2)
    # risk_percent=2.0 but cap is 1.0 → allowed=1.0; 4.2+1.0=5.2 > 5.0
    trade = _trade(risk_percent=2.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "over_exposure"

def test_exposure_cap_allows_capped_risk():
    gate = _mk({"max_risk_per_trade_pct": 1.0, "max_portfolio_risk_pct": 5.0})
    ps = _portfolio(total_open_risk_pct=3.5)
    # risk_percent=3.0 capped to 1.0 → 3.5+1.0=4.5 <= 5.0
    trade = _trade(risk_percent=3.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "approve"


# ── 7. INVALID SL DISTANCE ───────────────────────────────────────────────────

def test_reject_entry_equals_stop_loss():
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=100.0)
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "invalid_sl_distance"

def test_accept_sl_below_entry():
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=97.0)
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "approve"

def test_accept_sl_above_entry_short():
    """For short trades SL is above entry; abs() should handle correctly."""
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=103.0)
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "approve"


# ── 8. POSITION SIZING ────────────────────────────────────────────────────────

def test_position_size_no_hint():
    """No hint → final_size = balance * risk% / risk_per_unit."""
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=98.0, risk_percent=1.0,
                   position_size_hint=None)
    ps = _portfolio(account_balance=10_000.0)
    result = gate.evaluate(trade, ps)
    # 10000 * 0.01 / 2 = 50.0
    assert result["decision"] == "approve"
    assert abs(result["final_position_size"] - 50.0) < 1e-4

def test_position_size_hint_smaller_than_max():
    """Hint smaller than max_by_risk → hint wins."""
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=98.0, risk_percent=1.0,
                   position_size_hint=10.0)   # max would be 50.0
    ps = _portfolio(account_balance=10_000.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "approve"
    assert abs(result["final_position_size"] - 10.0) < 1e-4

def test_position_size_hint_larger_than_max():
    """Hint larger than max_by_risk → max_by_risk wins (risk cap enforced)."""
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=98.0, risk_percent=1.0,
                   position_size_hint=200.0)  # max is 50.0
    ps = _portfolio(account_balance=10_000.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "approve"
    assert abs(result["final_position_size"] - 50.0) < 1e-4

def test_reject_position_size_zero_from_zero_balance():
    """account_balance=0 → risk_usd=0 → size=0 → reject."""
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=98.0, risk_percent=1.0)
    ps = _portfolio(account_balance=0.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "position_size_zero"

def test_reject_negative_hint_produces_size_zero():
    """Negative hint → min(negative, positive) < 0 → size_zero reject."""
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=98.0, risk_percent=1.0,
                   position_size_hint=-5.0)
    ps = _portfolio(account_balance=10_000.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "position_size_zero"

def test_reject_hint_size_zero():
    gate = _mk()
    trade = _trade(entry_price=100.0, stop_loss=98.0, risk_percent=1.0,
                   position_size_hint=0.0)
    ps = _portfolio(account_balance=10_000.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "position_size_zero"


# ── 8b. SIZING BRIDGE (D11, 2026-09-30) ──────────────────────────────────────
# core.position_sizing.size_trade_lots is exercised directly in
# tests/test_position_sizing.py; these cover its wiring INTO UltronRiskGate.

def test_reject_size_below_broker_min_lot():
    """A risk budget too small to buy even lot_min -> reject, never rounded up."""
    gate = _mk(instrument_specs={
        _TEST_SYMBOL: {"contract_size": 1.0, "lot_step": 0.01, "lot_min": 1.0, "lot_max": 1e9},
    })
    # risk_capital_inr = 4.0 * 0.5% = 0.02 -> risk_usd 0.02 (rate 1.0) -> size_units
    # 0.02/2.0 = 0.01 -> floored lots 0.01, which is below this spec's lot_min=1.0.
    trade = _trade(entry_price=100.0, stop_loss=98.0, risk_percent=0.5, position_size_hint=None)
    ps = _portfolio(account_balance=4.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "size_below_min_lot"
    assert result["final_position_size"] == 0.0

def test_reject_undeclared_instrument_never_guesses_a_size():
    """An instrument with no declared instrument_specs entry fails CLOSED."""
    gate = _mk()
    trade = _trade(symbol="UNDECLARED_SYM")
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "config_key_missing:instrument_specs.UNDECLARED_SYM"

def test_reject_missing_usd_inr_rate_at_construction():
    """usd_inr_rate not injected (instrument_specs present) -> fails closed on the rate."""
    gate = _mk(usd_inr_rate=None)
    result = gate.evaluate(_trade(), _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "config_key_missing:sizing.usd_inr_rate"

def test_reject_no_instrument_specs_at_construction():
    """instrument_specs not injected at all -> fails closed before any lookup."""
    gate = _mk(instrument_specs=None)
    result = gate.evaluate(_trade(), _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] == "config_key_missing:sizing.instrument_specs"


# ── 9. REJECTION RESPONSE STRUCTURE ─────────────────────────────────────────

def test_reject_returns_zero_size():
    gate = _mk()
    trade = _trade(rr_ratio=0.5)   # RR too low
    result = gate.evaluate(trade, _portfolio())
    assert result["decision"] == "reject"
    assert result["final_position_size"] == 0.0
    assert result["allowed_risk_pct"] == 0.0

def test_reject_preserves_portfolio_state():
    """On reject, portfolio_state returned is the input (unchanged)."""
    gate = _mk()
    ps = _portfolio(total_open_risk_pct=4.9)
    trade = _trade(rr_ratio=0.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "reject"
    # portfolio_state on reject is the original dict, not modified
    assert result["portfolio_state"] is ps


# ── 10. CONFIG OVERRIDES ─────────────────────────────────────────────────────

def test_custom_config_overrides_defaults():
    gate = _mk({
        "max_risk_per_trade_pct": 2.0,
        "max_portfolio_risk_pct": 10.0,
        "max_trades_per_day": 20,
        "max_daily_loss_pct": 5.0,
        "min_rr_ratio": 1.0,
    })
    # With these loose limits, a normally-borderline trade passes
    trade = _trade(rr_ratio=1.0, risk_percent=2.0)
    ps = _portfolio(trades_today=15, daily_loss_pct=4.9, total_open_risk_pct=7.0)
    result = gate.evaluate(trade, ps)
    assert result["decision"] == "approve"

def test_no_config_raises():
    """Rewritten (EPIC-84): no config no longer yields defaults — it fails closed."""
    with pytest.raises(ConfigKeyMissingError):
        UltronRiskGate(None)

def test_partial_config_raises_naming_missing():
    """Rewritten (EPIC-84): a partial config no longer fills in defaults — it raises
    ConfigKeyMissingError listing every absent key."""
    with pytest.raises(ConfigKeyMissingError) as ei:
        UltronRiskGate({"max_trades_per_day": 3})
    missing = set(ei.value.missing)
    assert missing == set(_CFG) - {"max_trades_per_day"}


@pytest.mark.parametrize("key", sorted(_CFG))
def test_missing_required_config_key_raises(key):
    cfg = {k: v for k, v in _CFG.items() if k != key}
    with pytest.raises(ConfigKeyMissingError) as ei:
        UltronRiskGate(cfg)
    assert ei.value.missing == (key,)
    assert ei.value.section == "ultron_risk_gate"
    assert f"ultron_risk_gate.{key}" in str(ei.value)


# ── 10b. PER-TRADE MISSING VALUES -> REJECT (never a literal) ────────────────

@pytest.mark.parametrize("key", sorted(UltronRiskGate._REQUIRED_TRADE_KEYS))
def test_missing_trade_value_rejects(key):
    """risk_percent (was 0.5), rr_ratio/entry/stop (was 0.0) absent -> REJECT, engine keeps running."""
    trade = {k: v for k, v in _trade().items() if k != key}
    result = _mk().evaluate(trade, _portfolio())
    assert result["decision"] == "reject"
    assert result["risk_reason"] == f"config_key_missing:trade.{key}"
    assert result["final_position_size"] == 0.0

@pytest.mark.parametrize("key", sorted(UltronRiskGate._REQUIRED_PORTFOLIO_KEYS))
def test_missing_portfolio_value_rejects(key):
    """account_balance (was 10000.0) and the counters (were 0) absent -> REJECT."""
    ps = {k: v for k, v in _portfolio().items() if k != key}
    result = _mk().evaluate(_trade(), ps)
    assert result["decision"] == "reject"
    assert result["risk_reason"] == f"config_key_missing:portfolio_state.{key}"
    assert result["risk_reason"].startswith("config_key_missing")

def test_missing_values_reject_lists_all_and_gate_keeps_running():
    gate = _mk()
    trade = {k: v for k, v in _trade().items() if k not in ("risk_percent", "rr_ratio")}
    r1 = gate.evaluate(trade, _portfolio())
    assert r1["decision"] == "reject"
    assert r1["risk_reason"] == "config_key_missing:trade.rr_ratio,trade.risk_percent"
    # the next complete trade is still approved — no raise, no stuck state
    r2 = gate.evaluate(_trade(), _portfolio())
    assert r2["decision"] == "approve"

def test_disabled_gate_missing_position_size_rejects():
    gate = _mk({"disabled": True})
    r = gate.evaluate(_trade(), _portfolio())
    assert r["decision"] == "reject"
    assert r["risk_reason"] == "config_key_missing:trade.position_size"
    r2 = gate.evaluate(_trade(position_size=3.0), _portfolio())
    assert r2["decision"] == "approve" and r2["final_position_size"] == 3.0


# ── 11. ORDERING: FIRST FAILURE WINS ─────────────────────────────────────────

def test_ttl_check_before_rr_check():
    """Expired signal rejects before RR is evaluated."""
    gate = _mk()
    trade = _trade(expires_at=_past_ts(60), rr_ratio=0.0)
    result = gate.evaluate(trade, _portfolio())
    assert result["risk_reason"] == "expired_signal"

def test_rr_check_before_daily_limit():
    """Low RR rejects before daily limit is evaluated."""
    gate = _mk()
    trade = _trade(rr_ratio=0.5)
    ps = _portfolio(trades_today=99)
    result = gate.evaluate(trade, ps)
    assert result["risk_reason"] in ("rr_too_low", "rr_too_low_after_costs")

def test_daily_limit_before_kill_switch():
    """Daily limit rejects before kill switch is evaluated."""
    gate = _mk({"max_trades_per_day": 5})
    ps = _portfolio(trades_today=5, daily_loss_pct=99.0)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["risk_reason"] == "daily_limit"

def test_kill_switch_before_exposure():
    """Kill switch rejects before exposure check."""
    gate = _mk({"max_daily_loss_pct": 3.0})
    ps = _portfolio(daily_loss_pct=3.5, total_open_risk_pct=0.0)
    result = gate.evaluate(BASE_TRADE, ps)
    assert result["risk_reason"] == "kill_switch"


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [
        # approval
        test_happy_path_approve,
        test_approve_updates_portfolio_state,
        test_approve_no_expires_at,
        test_approve_execution_id_propagated,
        # TTL
        test_reject_expired_signal,
        test_reject_malformed_expires_at,
        test_approve_signal_just_not_expired,
        test_naive_datetime_treated_as_utc,
        # RR
        test_reject_rr_below_minimum,
        test_reject_rr_exactly_below_minimum,
        test_approve_rr_exactly_at_minimum,
        test_approve_rr_above_minimum,
        # daily limit
        test_reject_daily_limit_reached,
        test_reject_daily_limit_exceeded,
        test_approve_one_below_daily_limit,
        test_daily_reset_zero_trades,
        # kill switch
        test_reject_kill_switch_exact_threshold,
        test_reject_kill_switch_above_threshold,
        test_approve_daily_loss_below_threshold,
        test_approve_zero_daily_loss,
        # exposure
        test_reject_over_exposure_exact,
        test_reject_over_exposure_already_at_cap,
        test_approve_exposure_just_under_cap,
        test_exposure_risk_capped_at_per_trade_max,
        test_exposure_cap_allows_capped_risk,
        # SL distance
        test_reject_entry_equals_stop_loss,
        test_accept_sl_below_entry,
        test_accept_sl_above_entry_short,
        # sizing
        test_position_size_no_hint,
        test_position_size_hint_smaller_than_max,
        test_position_size_hint_larger_than_max,
        test_reject_position_size_zero_from_zero_balance,
        test_reject_negative_hint_produces_size_zero,
        test_reject_hint_size_zero,
        # reject structure
        test_reject_returns_zero_size,
        test_reject_preserves_portfolio_state,
        # config
        test_custom_config_overrides_defaults,
        test_no_config_raises,
        test_partial_config_raises_naming_missing,
        # ordering
        test_ttl_check_before_rr_check,
        test_rr_check_before_daily_limit,
        test_daily_limit_before_kill_switch,
        test_kill_switch_before_exposure,
    ]

    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*55}")
    print(f"  {passed} passed / {failed} failed  ({len(tests)} total)")
    print(f"{'='*55}")
    sys.exit(1 if failed else 0)
