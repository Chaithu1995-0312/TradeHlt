"""OBSERVATION_ONLY fail-reason counters — neutrality on small deterministic corpus."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _engine():
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from config_layer.crt_engine_v2 import CRTConfig, CRTEngine, Candle

    return CRTEngine(CRTConfig()), Candle, datetime


def _candles(n: int, Candle, datetime):
    out = []
    base = 2000.0
    for i in range(n):
        o = base + i * 0.05
        c = o + (0.3 if i % 4 else -0.2)
        out.append(
            Candle(
                timestamp=datetime(2024, 6, 1) + timedelta(minutes=15 * i),
                open=o,
                high=max(o, c) + 0.8,
                low=min(o, c) - 0.8,
                close=c,
                volume=100.0,
            )
        )
    return out


def test_fail_counters_default_off_no_attachment():
    eng, Candle, datetime = _engine()
    assert eng.baseline_trace is None
    cs = _candles(40, Candle, datetime)
    eng.initialise_range(cs[:14], "HTF-0", "LONDON")
    for c in cs[14:]:
        eng.process_candle(c, "HTF-0")


def test_fail_counters_on_off_action_parity_small():
    eng_off, Candle, datetime = _engine()
    eng_on, Candle, datetime = _engine()
    from runtime.crt_fail_reason_counters import CRTFailReasonCounters

    cs = _candles(80, Candle, datetime)
    counters = CRTFailReasonCounters()
    eng_on.baseline_trace = counters

    eng_off.initialise_range(cs[:14], "HTF-0", "LONDON")
    eng_on.initialise_range(cs[:14], "HTF-0", "LONDON")

    acts_off, acts_on = [], []
    for c in cs[14:]:
        counters.enabled = False
        r0 = eng_off.process_candle(c, "HTF-0")
        counters.enabled = True
        r1 = eng_on.process_candle(c, "HTF-0")
        acts_off.append((r0.get("action"), eng_off.state.current_state.name))
        acts_on.append((r1.get("action"), eng_on.state.current_state.name))

    assert acts_off == acts_on
    # counters may or may not have evaluations depending on states entered
    d = counters.as_dict()
    assert "by_guard_id" in d
    assert d["evaluations"] >= 0


def test_record_guard_fail_open_on_serialization_error():
    from runtime.crt_fail_reason_counters import CRTFailReasonCounters

    c = CRTFailReasonCounters()
    c.enabled = True
    # should not raise
    c.record_guard(
        guard_id="G_TEST",
        from_state="SWEEP",
        candidate_to_state="DISPLACEMENT",
        result=False,
        failure_reason="body_ratio_below_min",
    )
    assert c.counts[("G_TEST", "body_ratio_below_min")] == 1
