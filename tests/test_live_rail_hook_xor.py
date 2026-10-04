"""PR-4a: XOR-as-code on HookedLiveEngine. No OrderManager count (that is PR-4c)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from engines.live_engine import LiveEngineConfig
from runtime.live_engine_hook import HookedLiveEngine, _decision_is_approve


def test_decision_is_approve_is_case_insensitive() -> None:
    assert _decision_is_approve({"decision": "approve"}) is True
    assert _decision_is_approve({"decision": "APPROVE"}) is True
    assert _decision_is_approve({"decision": "Approve"}) is True
    assert _decision_is_approve({"decision": "reject"}) is False
    assert _decision_is_approve({}) is False


def test_default_hook_submit_orders_is_false() -> None:
    eng = HookedLiveEngine(LiveEngineConfig(enabled=False))
    assert eng._hook_submit_orders is False
    assert eng._may_submit({"decision": "approve"}, ks_blocked=False) is False
    assert eng._may_submit({"decision": "APPROVE"}, ks_blocked=False) is False


def test_xor_on_submits_when_approve_any_case() -> None:
    eng = HookedLiveEngine(LiveEngineConfig(enabled=False), hook_submit_orders=True)
    assert eng._may_submit({"decision": "approve"}, ks_blocked=False) is True
    assert eng._may_submit({"decision": "APPROVE"}, ks_blocked=False) is True
    assert eng._may_submit({"decision": "reject"}, ks_blocked=False) is False
    assert eng._may_submit({"decision": "approve"}, ks_blocked=True) is False


def test_emit_live_io_xor_off_sends_nothing() -> None:
    eng = HookedLiveEngine(LiveEngineConfig(enabled=False), hook_submit_orders=False)
    mt5 = MagicMock()
    tg = MagicMock()
    with patch("runtime.live_engine_hook._get_mt5", return_value=mt5), patch(
        "runtime.live_engine_hook._get_telegram", return_value=tg
    ):
        ticket = eng._emit_live_io(
            ultron_result={"decision": "approve", "final_position_size": 0.1},
            ks_blocked=False,
            trade_plan={
                "trade_intent": "BREAKOUT",
                "stop_loss": 1999.0,
                "take_profit_1": 2002.0,
                "rr_ratio": 2.0,
            },
            pair="XAUUSD",
            timeframe="M15",
            close=2000.0,
            confidence=0.7,
            orch_result=None,
        )
    assert ticket is None
    assert mt5.send_order.call_count == 0
    assert tg.send_signal_alert.call_count == 0


def test_emit_live_io_xor_on_sends_once_even_after_approve_lowercased() -> None:
    eng = HookedLiveEngine(LiveEngineConfig(enabled=False), hook_submit_orders=True)
    mt5 = MagicMock()
    mt5.send_order.return_value = 42
    tg = MagicMock()
    with patch("runtime.live_engine_hook._get_mt5", return_value=mt5), patch(
        "runtime.live_engine_hook._get_telegram", return_value=tg
    ):
        ticket = eng._emit_live_io(
            ultron_result={"decision": "approve", "final_position_size": 0.1},
            ks_blocked=False,
            trade_plan={
                "trade_intent": "BREAKOUT",
                "stop_loss": 1999.0,
                "take_profit_1": 2002.0,
                "rr_ratio": 2.0,
            },
            pair="XAUUSD",
            timeframe="M15",
            close=2000.0,
            confidence=0.7,
            orch_result=None,
        )
    assert ticket == 42
    assert mt5.send_order.call_count == 1
    assert tg.send_signal_alert.call_count == 1
