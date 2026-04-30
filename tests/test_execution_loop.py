"""
test_execution_loop.py
=======================
Phase E: Execution Loop + Alerts + Override tests.

Covers:
  AlertManager:
    - send() returns dict with 'sent' and 'message'
    - external_hook called with signal
    - hook failure doesn't crash

  OverrideHandler:
    - 'y' → EXECUTE
    - 'n' → SKIP
    - 'r' → REDUCE with factor
    - timeout → TIMEOUT_SKIP
    - AUTO_EXECUTE=True bypasses wait

  ExecutionLoop:
    - paused state skips processing
    - allocator REJECT → signal not executed
    - risk gate BLOCK → signal not executed
    - override SKIP → signal not executed
    - full happy path → signal executed and returned
    - max_ticks terminates loop
"""
import time
import pytest
from unittest.mock import MagicMock, patch

from src.execution.alert_manager import AlertManager
from src.execution.override_handler import OverrideHandler
from src.execution.loop import ExecutionLoop, SystemState


# ── AlertManager tests ────────────────────────────────────────────────────────

def test_alert_send_returns_dict():
    am = AlertManager()
    result = am.send({"symbol": "BTCUSDT", "action": "BUY", "confidence": 0.8, "rr": 2.5, "risk": 0.005})
    assert result["sent"] is True
    assert "BTCUSDT" in result["message"]
    assert result["symbol"] == "BTCUSDT"


def test_alert_external_hook_called():
    hook_calls = []
    def hook(signal, message):
        hook_calls.append((signal, message))

    am = AlertManager(external_hook=hook)
    am.send({"symbol": "ETHUSDT", "action": "BUY", "confidence": 0.7, "rr": 2.0, "risk": 0.003})
    assert len(hook_calls) == 1
    assert hook_calls[0][0]["symbol"] == "ETHUSDT"


def test_alert_hook_failure_doesnt_crash():
    def bad_hook(signal, message):
        raise RuntimeError("hook error")

    am = AlertManager(external_hook=bad_hook)
    result = am.send({"symbol": "X", "action": "BUY", "confidence": 0.5, "rr": 1.5, "risk": 0.002})
    assert result["sent"] is True  # alert still "sent" even if hook failed


def test_alert_stdout_print(capsys):
    am = AlertManager(print_to_stdout=True)
    am.send({"symbol": "SOLUSDT", "action": "BUY", "confidence": 0.75, "rr": 2.5, "risk": 0.005})
    captured = capsys.readouterr()
    assert "SOLUSDT" in captured.out


# ── OverrideHandler tests ─────────────────────────────────────────────────────

def test_override_execute_on_y():
    handler = OverrideHandler(input_fn=lambda _: "y")
    result = handler.wait_for_decision({"symbol": "BTC"})
    assert result["action"] == "EXECUTE"
    assert result["factor"] == 1.0


def test_override_skip_on_n():
    handler = OverrideHandler(input_fn=lambda _: "n")
    result = handler.wait_for_decision({"symbol": "BTC"})
    assert result["action"] == "SKIP"


def test_override_reduce_on_r():
    handler = OverrideHandler(input_fn=lambda _: "r", reduce_factor=0.5)
    result = handler.wait_for_decision({"symbol": "BTC"})
    assert result["action"] == "REDUCE"
    assert result["factor"] == pytest.approx(0.5)


def test_override_timeout_skip():
    """Immediate timeout (timeout=0) → TIMEOUT_SKIP."""
    call_count = [0]
    def input_fn(prompt):
        call_count[0] += 1
        time.sleep(0.01)
        raise EOFError("simulated timeout")

    handler = OverrideHandler(timeout=0, input_fn=input_fn)
    result = handler.wait_for_decision({"symbol": "BTC"})
    assert result["action"] == "TIMEOUT_SKIP"


def test_override_auto_execute_bypasses():
    handler = OverrideHandler()
    handler.AUTO_EXECUTE = True
    # input_fn never called
    result = handler.wait_for_decision({"symbol": "BTC"})
    assert result["action"] == "EXECUTE"


# ── ExecutionLoop tests ───────────────────────────────────────────────────────

def _make_signal():
    return {"symbol": "BTCUSDT", "action": "BUY", "confidence": 0.8, "rr": 2.5, "zone": 0.7, "_score": 0.82}


def _build_loop(
    signals=None,
    allocate_action="ALLOCATE",
    risk_allow=True,
    override_action="EXECUTE",
    max_ticks=1,
):
    """Build ExecutionLoop with mocked components."""
    if signals is None:
        signals = [_make_signal()]

    scanner = MagicMock()
    scanner.scan.return_value = signals

    ranker = MagicMock()
    ranker.rank.return_value = signals  # pass through

    pool = MagicMock()
    pool.top_k.return_value = signals[:3]

    regime_clf = MagicMock()
    regime_clf.classify.return_value = "TRENDING"

    config_router = MagicMock()
    config_router.select_profile.return_value = "BALANCED"

    allocator = MagicMock()
    allocator.allocate.return_value = {"action": allocate_action, "risk": 0.005, "reason": "test"}

    risk_gate = MagicMock()
    risk_gate.return_value = {"allow": risk_allow, "reason": "test"}

    alert_manager = MagicMock()

    override_handler = MagicMock()
    override_handler.wait_for_decision.return_value = {"action": override_action, "factor": 1.0}

    trade_executor = MagicMock()

    loop = ExecutionLoop(
        scanner=scanner,
        ranker=ranker,
        pool=pool,
        regime_classifier=regime_clf,
        config_router=config_router,
        allocator=allocator,
        risk_gate=risk_gate,
        alert_manager=alert_manager,
        override_handler=override_handler,
        trade_executor=trade_executor,
        max_ticks=max_ticks,
    )
    return loop


def test_loop_happy_path_executes_signal():
    loop = _build_loop(max_ticks=1)
    executed = loop.run()
    assert len(executed) == 1
    assert executed[0]["symbol"] == "BTCUSDT"


def test_loop_paused_skips_processing():
    loop = _build_loop(max_ticks=2)
    state = SystemState()
    state.pause()
    # Run 2 ticks; both should be skipped
    # But paused loop will sleep(1) each tick → use max_ticks to bound
    # Override: patch _sleep to avoid actual wait
    with patch.object(loop, "_sleep", return_value=None):
        state.stop()  # stop after checking paused state
        state.running = True
        loop.max_ticks = 1
        # Paused → no processing, but loop terminates after max_ticks
        executed = loop.run(state)
    assert len(executed) == 0


def test_loop_allocator_reject_skips():
    loop = _build_loop(allocate_action="REJECT", max_ticks=1)
    executed = loop.run()
    assert len(executed) == 0


def test_loop_risk_gate_block_skips():
    loop = _build_loop(risk_allow=False, max_ticks=1)
    executed = loop.run()
    assert len(executed) == 0


def test_loop_override_skip_skips():
    loop = _build_loop(override_action="SKIP", max_ticks=1)
    executed = loop.run()
    assert len(executed) == 0


def test_loop_override_reduce_shrinks_risk():
    loop = _build_loop(override_action="EXECUTE", max_ticks=1)
    # Patch override to return REDUCE with factor=0.5
    loop.override_handler.wait_for_decision.return_value = {"action": "REDUCE", "factor": 0.5}
    executed = loop.run()
    assert len(executed) == 1
    # Initial risk was 0.005; REDUCE factor=0.5 → 0.0025
    assert executed[0]["risk"] == pytest.approx(0.0025)


def test_loop_no_signals_returns_empty():
    loop = _build_loop(signals=[], max_ticks=1)
    executed = loop.run()
    assert executed == []


def test_loop_max_ticks_terminates():
    loop = _build_loop(max_ticks=3)
    executed = loop.run()
    # 3 ticks × 1 signal = 3 executed
    assert len(executed) == 3


def test_system_state_pause_resume():
    state = SystemState()
    assert not state.paused
    state.pause()
    assert state.paused
    state.resume()
    assert not state.paused


def test_system_state_stop():
    state = SystemState()
    assert state.running
    state.stop()
    assert not state.running