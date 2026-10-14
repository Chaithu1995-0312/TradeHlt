"""K23 F2: exact per-date exchange-session windows (default off; legacy byte-identical).

CH-corpus-clock-contract-v1: timestamps are canonical UTC (the corpus SSOT normalized the broker
clock once), so `exchange_sessions_at` takes UTC. Each session is defined in its OWN exchange
zone, so London's open sits at 07:00 UTC in BST summer and 08:00 UTC in GMT weeks (including the
US/EU DST-mismatch weeks), New York's at 12:00 UTC in EDT and 13:00 UTC in EST, Tokyo's (no DST)
at 00:00 UTC.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from features.broker_clock import (
    exchange_sessions_at, parse_exchange_session_windows,
)
from tests.helpers.crt_config import crt_config_for_test
from tests.helpers.crt_config import crt_engine_for_test, execution_engine_for_test, reset_logic_for_test  # noqa: F401

RAW = {
    "TOKYO":   {"tz": "Asia/Tokyo",       "open": "09:00", "close": "18:00"},
    "LONDON":  {"tz": "Europe/London",    "open": "08:00", "close": "17:00"},
    "NEWYORK": {"tz": "America/New_York", "open": "08:00", "close": "17:00"},
}
W = parse_exchange_session_windows(RAW)


def _at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm)


def _first_hour(y, m, d, name):
    """First UTC hour (15-min grid) on that date at which `name` is active."""
    for q in range(96):
        if name in exchange_sessions_at(_at(y, m, d, q // 4, (q % 4) * 15), W):
            return q / 4
    return None


@pytest.mark.parametrize("date,london_open_utc", [
    ((2025, 1, 15), 8.0),    # winter: London GMT
    ((2025, 7, 16), 7.0),    # summer: London BST
    ((2025, 3, 12), 8.0),    # US already on DST, London still GMT -> 08:00 UTC
    ((2025, 10, 29), 8.0),   # EU already back on GMT, US still EDT
])
def test_london_open_lands_on_the_exact_utc_hour_per_date(date, london_open_utc):
    assert _first_hour(*date, "LONDON") == london_open_utc


@pytest.mark.parametrize("date,newyork_open_utc", [
    ((2025, 1, 15), 13.0),   # EST
    ((2025, 7, 16), 12.0),   # EDT
    ((2025, 3, 12), 12.0),
    ((2025, 10, 29), 12.0),
])
def test_newyork_open_follows_its_own_dst(date, newyork_open_utc):
    assert _first_hour(*date, "NEWYORK") == newyork_open_utc


@pytest.mark.parametrize("date", [(2025, 1, 15), (2025, 7, 16)])
def test_tokyo_has_no_dst_so_it_opens_at_0000_utc(date):
    assert _first_hour(*date, "TOKYO") == 0.0


def test_window_is_half_open_bar_opening_at_close_is_excluded():
    # Summer London close 17:00 BST = 16:00 UTC.
    assert "LONDON" in exchange_sessions_at(_at(2025, 7, 16, 15, 45), W)
    assert "LONDON" not in exchange_sessions_at(_at(2025, 7, 16, 16, 0), W)


def test_declared_order_is_preserved_and_overlap_lists_both():
    hits = exchange_sessions_at(_at(2025, 7, 16, 12, 30), W)   # 12:30 UTC
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
    return crt_engine_for_test(cfg, exchange_session_windows=windows)


def test_default_engine_is_legacy_static():
    from config_layer.crt_engine_v2 import CRTEngine
    eng = crt_engine_for_test(crt_config_for_test())
    assert eng._exchange_windows is None and eng.risk.exchange_windows is None


def test_flag_off_score_time_is_the_legacy_static_computation():
    from config_layer.crt_engine_v2 import CRTEngine
    cfg = crt_config_for_test()
    eng = crt_engine_for_test(cfg)
    for h in range(24):
        ts = _at(2025, 7, 16, h, 30)
        n = sum(1 for s, e in cfg.session_windows.values() if s <= ts.time() <= e)
        want = 1.0 if n >= 2 else (0.8 if n == 1 else 0.0)
        assert eng.risk.score_time(ts) == want


def test_exchange_mode_score_time_uses_exact_windows():
    eng = _engine(RAW)
    assert eng.risk.score_time(_at(2025, 7, 16, 12, 30)) == 1.0   # London + NY (UTC)
    assert eng.risk.score_time(_at(2025, 7, 16, 10, 0)) == 0.8    # London only
    # 22:00 UTC = 07:00 JST / 23:00 BST / 18:00 EDT -> all three closed.
    assert eng.risk.score_time(_at(2025, 7, 16, 22, 0)) == 0.0


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
    return BacktestConfig.from_prod_config("XAUUSD", crt_config=crt_config_for_test(), pip_size=0.0001, scorer_mode="calibrated", allow_router_crt_config=False, strategy_id="")


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
