"""PR-4c slice: UltronLiveAdapter read-only preflight."""
from __future__ import annotations

from core.ultron_live_adapter import LivePosition, UltronLiveAdapter
from core.ultron_risk_gate import UltronRiskGate


def _gate() -> UltronRiskGate:
    g = UltronRiskGate({
        "max_risk_per_trade_pct": 1.0,
        "max_portfolio_risk_pct": 5.0,
        "max_trades_per_day": 2,
        "max_daily_loss_pct": 3.0,
        "min_rr_ratio": 1.5,
        "disabled": False,
    })
    g._kill_switch_tripped = False
    g._load_ks_state = lambda: False  # type: ignore[method-assign]
    return g


def test_preflight_pass() -> None:
    ad = UltronLiveAdapter(_gate(), paper_balance=10_000.0)
    assert ad.preflight("XAUUSD")["decision"] == "pass"


def test_preflight_kill_switch() -> None:
    g = _gate()
    g._kill_switch_tripped = True
    ad = UltronLiveAdapter(g, paper_balance=10_000.0)
    out = ad.preflight("XAUUSD")
    assert out["decision"] == "reject"
    assert out["risk_reason"] == "kill_switch_active"


def test_preflight_duplicate_and_daily_limit() -> None:
    ad = UltronLiveAdapter(_gate(), paper_balance=10_000.0)
    from datetime import datetime, timezone
    pos = LivePosition(
        symbol="XAUUSD", direction=1, qty=0.1, entry=2000.0,
        stop_loss=1999.0, take_profit_1=2002.0, risk_pct=0.5,
        ticket=-1, opened_at=datetime.now(timezone.utc),
    )
    ad.register_fill(pos, 0.5)
    assert ad.preflight("XAUUSD")["risk_reason"] == "position_already_open"
    ad2 = UltronLiveAdapter(_gate(), paper_balance=10_000.0)
    ad2.register_fill(pos, 0.5)
    other = LivePosition(
        symbol="EURUSD", direction=1, qty=0.1, entry=1.1,
        stop_loss=1.09, take_profit_1=1.12, risk_pct=0.5,
        ticket=-1, opened_at=datetime.now(timezone.utc),
    )
    ad2.register_fill(other, 0.5)
    assert ad2.preflight("GBPUSD")["risk_reason"] == "daily_limit"
