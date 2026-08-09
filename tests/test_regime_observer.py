"""Program 4 — RegimeLabeler / RegimeObserver tests.

Load-bearing properties: determinism, strict no-lookahead, NO global-rank leak (the
F-029 trap the production volatility_regime falls into), and the non-directional
OBSERVATION event schema (direction=None so the adapter skips it for trades).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from interpreters.contract import EventKind
from interpreters.regime_observer import REGIMES, RegimeLabeler, RegimeObserver


@dataclass
class _C:
    high: float
    low: float
    close: float
    timestamp: datetime
    index: int = 0


def _mk(ranges: list[float]) -> list[_C]:
    """Candles with close fixed at 100 and a controlled high-low range → ATR ≈ range."""
    t0 = datetime(2026, 1, 1)
    out = []
    for i, r in enumerate(ranges):
        out.append(_C(high=100.0 + r / 2.0, low=100.0 - r / 2.0, close=100.0,
                      timestamp=t0 + timedelta(minutes=15 * i), index=i))
    return out


_RANGES = [1.0, 1.2, 0.8, 2.0, 0.5, 3.0, 1.1, 0.9, 2.5, 0.7,
           1.3, 0.6, 2.2, 1.0, 0.8, 3.1, 0.9, 1.5, 0.4, 2.8] * 3


def test_label_series_deterministic():
    candles = _mk(_RANGES)
    a = RegimeLabeler(atr_period=3, tercile_window=10).label_series(candles)
    b = RegimeLabeler(atr_period=3, tercile_window=10).label_series(candles)
    assert a == b


def test_labels_are_valid_or_none():
    labels = RegimeLabeler(atr_period=3, tercile_window=10).label_series(_mk(_RANGES))
    for x in labels:
        assert x in REGIMES or x is None
    # warmup bars (trailing window not yet full) must be None; later bars must classify
    assert labels[0] is None
    assert any(x in REGIMES for x in labels)


def test_no_lookahead_truncation_stable():
    """label at index k must depend ONLY on candles[:k+1] — truncating the future leaves it
    unchanged."""
    candles = _mk(_RANGES)
    lab = RegimeLabeler(atr_period=3, tercile_window=10)
    full = lab.label_series(candles)
    k = 40
    truncated = lab.label_series(candles[:k + 1])
    assert truncated[k] == full[k]
    assert truncated == full[:k + 1]


def test_no_global_rank_leak():
    """Appending future high-volatility bars must NOT change earlier labels. A global
    percentile rank (the F-029 production trap) would shift them; a trailing window cannot."""
    base = _mk(_RANGES)
    extended = _mk(_RANGES + [50.0] * 25)   # huge future vol
    lab = RegimeLabeler(atr_period=3, tercile_window=10)
    assert lab.label_series(extended)[:len(base)] == lab.label_series(base)


def test_observer_emits_nondirectional_observation():
    obs = RegimeObserver(atr_period=3, tercile_window=10)
    reading = obs.observe(_mk(_RANGES), {}, {"instrument": "T"})
    assert len(reading.events) == 1
    ev = reading.events[0]
    assert ev.kind is EventKind.OBSERVATION
    assert ev.direction is None
    assert not ev.is_directional          # adapter will skip it for trade generation
    assert 0.0 <= ev.confidence <= 1.0 and 0.0 <= ev.strength <= 1.0
    assert ev.meta.get("regime") in REGIMES


def test_observer_reading_deterministic():
    obs = RegimeObserver(atr_period=3, tercile_window=10)
    w = _mk(_RANGES)
    r1, r2 = obs.observe(w, {}, {}), obs.observe(w, {}, {})
    assert r1.trace_id == r2.trace_id
    assert r1.events[0].meta == r2.events[0].meta
