"""K23 F2: exact per-date exchange-session windows (default off; legacy byte-identical).

Broker (MT5 server) time tracks America/New_York DST: UTC+3 while NY is on EDT, UTC+2 on EST
(features.broker_clock). Each session is defined in its OWN exchange zone, so London's open
sits at 10:00 broker in normal weeks but 11:00 broker in the US/EU DST-mismatch weeks.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from features.broker_clock import (
    exchange_sessions_at, parse_exchange_session_windows,
)
from tests.helpers.crt_config import crt_config_for_test

RAW = {
    "TOKYO":   {"tz": "Asia/Tokyo",       "open": "09:00", "close": "18:00"},
    "LONDON":  {"tz": "Europe/London",    "open": "08:00", "close": "17:00"},
    "NEWYORK": {"tz": "America/New_York", "open": "08:00", "close": "17:00"},
}
W = parse_exchange_session_windows(RAW)


def _at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm)


def _first_hour(y, m, d, name):
    """First broker hour (15-min grid) on that date at which `name` is active."""
    for q in range(96):
        if name in exchange_sessions_at(_at(y, m, d, q // 4, (q % 4) * 15), W):
            return q / 4
    return None


@pytest.mark.parametrize("date,london_open_broker", [
    ((2025, 1, 15), 10.0),   # winter: NY EST + London GMT -> broker UTC+2
    ((2025, 7, 16), 10.0),   # summer: NY EDT + London BST -> broker UTC+3
    ((2025, 3, 12), 11.0),   # US on DST (broker +3), London still GMT -> 08:00 UTC = 11:00
    ((2025, 10, 29), 11.0),  # EU already back on GMT, US still EDT (broker +3)
])
def test_london_open_lands_on_the_exact_broker_hour_per_date(date, london_open_broker):
    assert _first_hour(*date, "LONDON") == london_open_broker


@pytest.mark.parametrize("date", [(2025, 1, 15), (2025, 7, 16), (2025, 3, 12), (2025, 10, 29)])
def test_newyork_open_is_always_1500_broker(date):
    # Broker tracks NY DST, so NY's own 08:00 is a constant 15:00 broker.
    assert _first_hour(*date, "NEWYORK") == 15.0


@pytest.mark.parametrize("date,tokyo_open_broker", [
    ((2025, 1, 15), 2.0),    # JST no DST: 00:00 UTC = 02:00 broker (UTC+2)
    ((2025, 7, 16), 3.0),    # 00:00 UTC = 03:00 broker (UTC+3)
])
def test_tokyo_moves_only_through_the_broker_offset(date, tokyo_open_broker):
    assert _first_hour(*date, "TOKYO") == tokyo_open_broker


def test_window_is_half_open_bar_opening_at_close_is_excluded():
    # Summer London close 17:00 BST = 16:00 UTC = 19:00 broker.
    assert "LONDON" in exchange_sessions_at(_at(2025, 7, 16, 18, 45), W)
    assert "LONDON" not in exchange_sessions_at(_at(2025, 7, 16, 19, 0), W)


def test_declared_order_is_preserved_and_overlap_lists_both():
    hits = exchange_sessions_at(_at(2025, 7, 16, 15, 30), W)   # 12:30 UTC
    assert hits == ("LONDON", "NEWYORK")


@pytest.mark.parametrize("bad", [
    {}, None,
    {"X": {"tz": "Nowhere/Land", "open": "08:00", "close": "17:00"}},
    {"X": {"tz": "Europe/London", "open": "8am", "close": "17:00"}},
    {"X": {"tz": "Europe/London", "open": "17:00", "close": "08:00"}},
    {"X": {"tz": "Europe/London", "open": "08:00"}},
])
def test_bad_windows_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_exchange_session_windows(bad)


# ── engine wiring ───────────────────────────────────────────────────────────
def _engine(windows, allowed=("LONDON", "NEWYORK", "TOKYO")):
    from config_layer.crt_engine_v2 import CRTEngine
    cfg = dataclasses.replace(crt_config_for_test(), allowed_sessions=allowed)
    return CRTEngine(cfg, exchange_session_windows=windows)


def test_default_engine_is_legacy_static():
    from config_layer.crt_engine_v2 import CRTEngine
    eng = CRTEngine(crt_config_for_test())
    assert eng._exchange_windows is None and eng.risk.exchange_windows is None


def test_flag_off_score_time_is_the_legacy_static_computation():
    from config_layer.crt_engine_v2 import CRTEngine
    cfg = crt_config_for_test()
    eng = CRTEngine(cfg)
    for h in range(24):
        ts = _at(2025, 7, 16, h, 30)
        n = sum(1 for s, e in cfg.session_windows.values() if s <= ts.time() <= e)
        want = 1.0 if n >= 2 else (0.8 if n == 1 else 0.0)
        assert eng.risk.score_time(ts) == want


def test_exchange_mode_score_time_uses_exact_windows():
    eng = _engine(RAW)
    assert eng.risk.score_time(_at(2025, 7, 16, 15, 30)) == 1.0   # London + NY
    assert eng.risk.score_time(_at(2025, 7, 16, 13, 0)) == 0.8    # London only
    # 01:00 broker = 22:00 UTC = 07:00 JST / 23:00 BST / 18:00 EDT -> all three closed.
    assert eng.risk.score_time(_at(2025, 7, 16, 1, 0)) == 0.0


def test_allowed_session_without_a_window_fails_closed():
    with pytest.raises(ValueError, match="never be admitted"):
        _engine(RAW, allowed=("LONDON", "SYDNEY"))


def test_overlap_is_exempt_from_the_fail_closed_check():
    _engine(RAW, allowed=("LONDON", "OVERLAP"))   # derived name, inert in both modes


# ── BacktestConfig ──────────────────────────────────────────────────────────
def _bt_cfg(monkeypatch, **extra):
    import config_layer.production_config as pc
    from runtime.backtest_v2 import BacktestConfig
    base = dict(pc.get_prod_section("backtest"))
    for k in ("session_window_basis", "exchange_session_windows"):
        base.pop(k, None)
    base.update(extra)
    monkeypatch.setattr(pc, "get_prod_section", lambda n: base if n == "backtest" else {})
    return BacktestConfig.from_prod_config("XAUUSD", crt_config=crt_config_for_test())


def test_backtest_config_default_is_broker_static(monkeypatch):
    c = _bt_cfg(monkeypatch)
    assert c.session_window_basis == "broker_static" and c.exchange_session_windows is None


def test_backtest_config_exchange_local_round_trips(monkeypatch):
    c = _bt_cfg(monkeypatch, session_window_basis="exchange_local", exchange_session_windows=RAW)
    assert c.session_window_basis == "exchange_local"
    assert set(c.exchange_session_windows) == {"TOKYO", "LONDON", "NEWYORK"}


def test_backtest_config_errors(monkeypatch):
    with pytest.raises(ValueError, match="session_window_basis"):
        _bt_cfg(monkeypatch, session_window_basis="bogus")
    with pytest.raises(KeyError, match="exchange_session_windows"):
        _bt_cfg(monkeypatch, session_window_basis="exchange_local")
    with pytest.raises(ValueError, match="time zone"):
        _bt_cfg(monkeypatch, session_window_basis="exchange_local",
                exchange_session_windows={"X": {"tz": "Nowhere/Land", "open": "08:00", "close": "17:00"}})
