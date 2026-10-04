"""
test_interpreter_contract.py — Interpreter Contract Layer (Plan 3, Phase B).

Proves: conformance + guards, determinism / no-lookahead, identity-blind adapter,
and the KEY round-trip — interpreter → InterpreterHypothesis → forward_walk →
EdgeReport — i.e. an interpreter is measurable through the EXISTING oracle with zero
new measurement code.

Run: python -m pytest tests/interpreters/test_interpreter_contract.py -q
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle, Direction
from research.contracts import Hypothesis
from research.measurement.forward_walk import forward_walk
from research.measurement.metrics import EdgeAggregator

from interpreters.adapter import InterpreterHypothesis
from interpreters.contract import (
    BaseInterpreter, EventKind, Interpreter, InterpreterError, InterpreterEvent,
)
from interpreters.reference import ConstantDirectionInterpreter, NullInterpreter

_BASE = datetime(2025, 1, 1, 0, 0, 0)


def _rising(n: int) -> list[Candle]:
    # Deterministic uptrend so a constant-long signal resolves (TP or timeout).
    out = []
    for i in range(n):
        base = 100.0 + i * 0.5
        out.append(Candle(timestamp=_BASE + timedelta(minutes=15 * i),
                          open=base, high=base + 1.0, low=base - 0.5,
                          close=base + 0.5, volume=1.0, index=i))
    return out


# ── conformance + guards ──────────────────────────────────────────────────────
def test_reference_interpreters_satisfy_protocol():
    assert isinstance(ConstantDirectionInterpreter(), Interpreter)
    assert isinstance(NullInterpreter(), Interpreter)


def test_base_defaults_and_version():
    interp = ConstantDirectionInterpreter(cadence=5)
    reading = interp.observe(_rising(6), {}, {"instrument": "X"})  # idx 5 → emits
    assert interp.version() == "1.0"
    assert reading.schema_version == "1.0"
    assert reading.unknowns == []
    assert reading.failure_conditions == {}
    assert set(interp.explain()) >= {"observation", "reasoning", "unknowns"}


def test_observation_time_is_last_bar_and_trace_id_deterministic():
    window = _rising(6)
    interp = ConstantDirectionInterpreter(cadence=5)
    r1 = interp.observe(window, {}, {"instrument": "X"})
    r2 = interp.observe(window, {}, {"instrument": "X"})
    assert r1.observation_time == window[-1].timestamp        # last bar, not wall-clock
    assert r1.trace_id == r2.trace_id                          # deterministic (same window)
    assert "20250101" in r1.trace_id and r1.trace_id.startswith("CONST_LONG-v1.0-")


def test_determinism_same_window_identical_reading():
    window = _rising(11)   # idx 10 → emits
    interp = ConstantDirectionInterpreter(cadence=5)
    r1 = interp.observe(window, {}, {"instrument": "X"})
    r2 = interp.observe(window, {}, {"instrument": "X"})
    assert r1 == r2


class _BadConfidence(BaseInterpreter):
    name = "bad_conf"
    def _observe(self, window, features, ctx):
        return [], 1.5                       # reading confidence out of range


class _BadEventStrength(BaseInterpreter):
    name = "bad_strength"
    def _observe(self, window, features, ctx):
        ev = InterpreterEvent(kind=EventKind.OBSERVATION, confidence=0.5, strength=9.0)
        return [ev], 0.5


class _BadKind(BaseInterpreter):
    name = "bad_kind"
    def _observe(self, window, features, ctx):
        ev = InterpreterEvent(kind="breakout", confidence=0.5, strength=0.5)  # type: ignore
        return [ev], 0.5


class _BadDirection(BaseInterpreter):
    name = "bad_dir"
    def _observe(self, window, features, ctx):
        ev = InterpreterEvent(kind=EventKind.BREAKOUT, confidence=0.5, strength=0.5,
                              direction="LONG")  # type: ignore  — must be Direction|None
        return [ev], 0.5


@pytest.mark.parametrize("cls", [_BadConfidence, _BadEventStrength, _BadKind, _BadDirection])
def test_base_validation_rejects_violations(cls):
    with pytest.raises(InterpreterError):
        cls().observe(_rising(3), {}, {"instrument": "X"})


def test_empty_window_raises():
    with pytest.raises(InterpreterError):
        ConstantDirectionInterpreter().observe([], {}, {"instrument": "X"})


# ── adapter is a Hypothesis + identity-blind ───────────────────────────────────
def test_adapter_is_hypothesis():
    adapter = InterpreterHypothesis(ConstantDirectionInterpreter(cadence=5))
    assert isinstance(adapter, Hypothesis)            # satisfies the frozen Protocol
    assert adapter.name == "interp:const_long"


def test_adapter_signal_is_identity_blind():
    # Two interpreters with IDENTICAL events but different identity → identical
    # decision-relevant Signal fields. detect() must not branch on name/meta.
    window = _rising(6)
    ctx = {"instrument": "X"}
    i1 = ConstantDirectionInterpreter(cadence=5)
    i2 = ConstantDirectionInterpreter(cadence=5)
    i2.name = "totally_different_name"
    s1 = InterpreterHypothesis(i1).detect(window, {}, ctx)
    s2 = InterpreterHypothesis(i2).detect(window, {}, ctx)
    assert len(s1) == 1 and len(s2) == 1
    a, b = s1[0], s2[0]
    assert (a.direction, a.entry, a.sl_atr_mult, a.tp_atr_mult, a.atr) == \
           (b.direction, b.entry, b.sl_atr_mult, b.tp_atr_mult, b.atr)


def test_fusion_is_identity_blind():
    # The adapter source must reference no concrete interpreter class and read no
    # interpreter-specific identity/meta for its signal logic.
    src = (Path(_SRC) / "interpreters" / "adapter.py").read_text(encoding="utf-8")
    assert "ConstantDirectionInterpreter" not in src
    assert "NullInterpreter" not in src
    # detect() builds Signals from events only — no `.name`/`.family` of the interp,
    # no reading-event `.meta` access in the signal-construction path.
    assert "ev.meta" not in src and "interpreter.name" not in src


# ── the KEY proof: round-trip through the existing oracle ───────────────────────
def test_adapter_roundtrip_through_forward_walk_and_edgereport():
    candles = _rising(60)
    window = candles[:6]                       # ends at idx 5 (cadence hit)
    adapter = InterpreterHypothesis(ConstantDirectionInterpreter(cadence=5))
    signals = adapter.detect(window, {}, {"instrument": "X"})
    assert len(signals) == 1
    sig = signals[0]
    assert sig.direction == "long"             # Direction.LONG → "long"

    future = candles[sig.entry_index + 1: sig.entry_index + 1 + 40]
    outcome = forward_walk(sig, future, max_forward=40, exit_model="intrabar_fixed")
    report = EdgeAggregator().aggregate(adapter.name, ["X"], [outcome])
    assert report.n == 1
    assert report.hypothesis == "interp:const_long"


def test_null_interpreter_emits_no_signals():
    adapter = InterpreterHypothesis(NullInterpreter())
    signals = adapter.detect(_rising(6), {}, {"instrument": "X"})
    assert signals == []
    report = EdgeAggregator().aggregate(adapter.name, ["X"], [])
    assert report.n == 0
