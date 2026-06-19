"""Phase 4 — CandleProvider tests (fixture slicing + Bar mapping)."""
from __future__ import annotations

from conftest import M15, BASE_TIME, make_bar  # type: ignore

from mt5_analytics.engines.features._bars import Bar
from mt5_analytics.providers.candle_provider import CandleProvider
from mt5_analytics.providers.fixture_provider import FixtureProvider


def test_fixture_provider_time_slicing():
    bars = [make_bar(BASE_TIME + i * M15, 100, 101, 99, 100) for i in range(5)]
    prov = FixtureProvider({"EURUSD": bars})
    window = prov.get_window("EURUSD", BASE_TIME + 1 * M15, BASE_TIME + 3 * M15)
    assert [b.time for b in window] == [BASE_TIME + 1 * M15, BASE_TIME + 2 * M15,
                                        BASE_TIME + 3 * M15]


def test_fixture_provider_unknown_symbol_empty():
    prov = FixtureProvider({"EURUSD": [make_bar(BASE_TIME, 1, 1, 1, 1)]})
    assert prov.get_window("XAUUSD", 0, 10**12) == []


def test_fixture_provider_satisfies_protocol():
    prov = FixtureProvider({})
    assert isinstance(prov, CandleProvider)        # structural Protocol check


def test_bar_fields():
    b = Bar(index=3, time=BASE_TIME, open=1.0, high=2.0, low=0.5, close=1.5, volume=9)
    assert (b.index, b.high, b.low, b.close) == (3, 2.0, 0.5, 1.5)
