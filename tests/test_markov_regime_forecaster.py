"""Program 4b — MarkovRegimeForecaster tests.

Load-bearing properties: determinism, strict no-lookahead (truncation invariance + no
global-rank leak, the same F-029 trap `RegimeLabeler` already guards against), correct
trailing-window-only transition counting, the uniform-1/3 fallback for unobserved rows, and
H-step projection correctness against a hand-computable deterministic cycle.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from unittest.mock import patch

from interpreters.regime_observer import REGIMES, MarkovRegimeForecaster, RegimeLabeler


@dataclass
class _C:
    high: float
    low: float
    close: float
    timestamp: datetime
    index: int = 0


def _mk(ranges: list[float]) -> list[_C]:
    """Candles with close fixed at 100 and a controlled high-low range -> ATR ~= range."""
    t0 = datetime(2026, 1, 1)
    out = []
    for i, r in enumerate(ranges):
        out.append(_C(high=100.0 + r / 2.0, low=100.0 - r / 2.0, close=100.0,
                      timestamp=t0 + timedelta(minutes=15 * i), index=i))
    return out


_RANGES = [1.0, 1.2, 0.8, 2.0, 0.5, 3.0, 1.1, 0.9, 2.5, 0.7,
           1.3, 0.6, 2.2, 1.0, 0.8, 3.1, 0.9, 1.5, 0.4, 2.8] * 3


def _with_fixed_states(states: list):
    """Patch RegimeLabeler.label_series to return an exact, hand-specified state sequence,
    so the Markov transition/projection math can be tested independently of the ATR-tercile
    classifier's own behavior (already covered by tests/test_regime_observer.py)."""
    return patch.object(RegimeLabeler, "label_series", lambda self, candles: list(states))


# ── determinism / no-lookahead (real candles, via RegimeLabeler as normally wired) ─────────
def test_forecast_series_deterministic():
    candles = _mk(_RANGES)
    f = MarkovRegimeForecaster(atr_period=3, tercile_window=10, w_markov=10, h=2)
    a = f.forecast_series(candles)
    b = f.forecast_series(candles)
    assert a == b


def test_forecasts_are_valid_or_none():
    f = MarkovRegimeForecaster(atr_period=3, tercile_window=10, w_markov=10, h=2)
    forecasts = f.forecast_series(_mk(_RANGES))
    for x in forecasts:
        assert x in REGIMES or x is None
    assert any(x in REGIMES for x in forecasts)   # some bars must classify


def test_no_lookahead_truncation_stable():
    """forecast at index k must depend ONLY on candles[:k+1] -- truncating the future leaves
    it unchanged (mirrors test_regime_observer.test_no_lookahead_truncation_stable)."""
    candles = _mk(_RANGES)
    f = MarkovRegimeForecaster(atr_period=3, tercile_window=10, w_markov=10, h=2)
    full = f.forecast_series(candles)
    k = 40
    truncated = f.forecast_series(candles[:k + 1])
    assert truncated[k] == full[k]
    assert truncated == full[:k + 1]


def test_no_global_rank_leak():
    """Appending future high-volatility bars must NOT change earlier forecasts."""
    base = _mk(_RANGES)
    extended = _mk(_RANGES + [50.0] * 25)   # huge future vol
    f = MarkovRegimeForecaster(atr_period=3, tercile_window=10, w_markov=10, h=2)
    assert f.forecast_series(extended)[:len(base)] == f.forecast_series(base)


def test_confidence_series_aligned_and_bounded():
    f = MarkovRegimeForecaster(atr_period=3, tercile_window=10, w_markov=10, h=2)
    candles = _mk(_RANGES)
    forecasts = f.forecast_series(candles)
    confidences = f.confidence_series(candles)
    assert len(confidences) == len(forecasts)
    for lab, conf in zip(forecasts, confidences):
        if lab is None:
            assert conf is None
        else:
            assert 0.0 <= conf <= 1.0


# ── exact transition/projection math (fixed, hand-computable state sequences) ──────────────
def test_deterministic_cycle_one_step_projection():
    """A perfectly deterministic C->N->E->C->... cycle: the trailing transition matrix is
    exact (P(C->N)=1, P(N->E)=1, P(E->C)=1), so a 1-step forecast must equal the cycle's
    actual next state at every bar past warmup."""
    cycle = ["C", "N", "E"]
    states = cycle * 20   # 60 states
    with _with_fixed_states(states):
        f = MarkovRegimeForecaster(w_markov=10, h=1)
        forecasts = f.forecast_series([None] * len(states))
    for t in range(15, len(states) - 1):
        expected_next = cycle[(cycle.index(states[t]) + 1) % 3]
        assert forecasts[t] == expected_next


def test_deterministic_cycle_two_step_projection():
    """Same deterministic cycle, h=2: two transitions ahead in a 3-cycle lands on the state
    two positions forward (C->E, N->C, E->N)."""
    cycle = ["C", "N", "E"]
    states = cycle * 20
    with _with_fixed_states(states):
        f = MarkovRegimeForecaster(w_markov=10, h=2)
        forecasts = f.forecast_series([None] * len(states))
    for t in range(15, len(states) - 1):
        expected = cycle[(cycle.index(states[t]) + 2) % 3]
        assert forecasts[t] == expected


def test_uniform_fallback_for_unobserved_row():
    """Exactly one observed transition (C->N); the current state 'N' has ZERO observed
    outgoing transitions -> its row falls back to uniform 1/3 each -> np.argmax ties on the
    FIRST index, i.e. REGIMES[0] == 'C'."""
    states = ["C", "N"]
    with _with_fixed_states(states):
        f = MarkovRegimeForecaster(w_markov=10, h=1)
        forecasts = f.forecast_series([None, None])
    assert forecasts[1] == REGIMES[0]


def test_trailing_window_only_recent_transitions_count():
    """The transition-count window only ever holds the last `w_markov` COMPLETED
    transitions: an early C<->E history must be fully aged out once enough recent C<->N
    transitions accumulate, so the forecast reflects only the recent regime."""
    early = ["C", "E"] * 10     # 20 states, alternating C<->E
    recent = ["C", "N"] * 10    # 20 states, alternating C<->N
    states = early + recent
    with _with_fixed_states(states):
        f = MarkovRegimeForecaster(w_markov=4, h=1)
        forecasts = f.forecast_series([None] * len(states))
    t = len(states) - 2
    assert states[t] == "C"
    assert forecasts[t] == "N"   # NOT "E" -- the old C->E history has aged out


def test_no_forecast_before_any_completed_transition():
    """With only ONE labeled bar, no transition has ever completed -> forecast is None even
    though the current state itself is labeled."""
    states = ["C"]
    with _with_fixed_states(states):
        f = MarkovRegimeForecaster(w_markov=10, h=1)
        forecasts = f.forecast_series([None])
    assert forecasts == [None]
