"""CRTStateResolver EXPANSION TTL boundary — engine parity.

Engine (crt_engine_v2 Phase 3b `_ttl_exceeded`) expires EXPANSION when the TTL is
*exceeded*: age > max_expansion_age_candles, hours > max_expansion_age_hours.
The resolver used ">=" and expired one bar / at the exact hour mark early.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features.crt_state_resolver import CRTStateResolver  # noqa: E402

ENTRY_IDX = 10
ENTRY_TS = datetime(2024, 7, 16, 3, 45)


def _resolver(max_candles: int, max_hours: float) -> CRTStateResolver:
    r = CRTStateResolver(instrument="XAUUSD")
    r._config["thresholds"]["max_expansion_age_candles"] = max_candles
    r._config["thresholds"]["max_expansion_age_hours"] = max_hours
    r._memory.current_state = "EXPANSION"
    r._memory.expansion_entry_index = ENTRY_IDX
    r._memory.expansion_entry_ts = ENTRY_TS
    return r


def test_candle_ttl_at_max_is_not_expired():
    r = _resolver(max_candles=495, max_hours=0)
    r._memory.candle_index = ENTRY_IDX + 495
    assert r._check_expired() is False


def test_candle_ttl_past_max_is_expired():
    r = _resolver(max_candles=495, max_hours=0)
    r._memory.candle_index = ENTRY_IDX + 496
    assert r._check_expired() is True


def test_hour_ttl_at_max_is_not_expired():
    r = _resolver(max_candles=0, max_hours=124)
    assert r._check_expired(ENTRY_TS + timedelta(hours=124)) is False


def test_hour_ttl_past_max_is_expired():
    r = _resolver(max_candles=0, max_hours=124)
    assert r._check_expired(ENTRY_TS + timedelta(hours=124, minutes=15)) is True


def test_zero_ttl_disables_both_checks():
    r = _resolver(max_candles=0, max_hours=0)
    r._memory.candle_index = ENTRY_IDX + 100_000
    assert r._check_expired(ENTRY_TS + timedelta(days=365)) is False
