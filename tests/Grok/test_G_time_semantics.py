"""G. Time semantics — timezone, session bounds, candle age, DST, broker vs UTC.

Semantic invariant: a session decision must name which clock it used.
Ordinary tests pin broker_local as the default; they do not walk DST
boundaries against the CRT filter's inclusive windows.
"""
from __future__ import annotations

from datetime import time, timedelta

from config_layer.state_identity import CRTConfig
from features.broker_clock import mt5_server_offset_hours, mt5_server_to_utc
from features.session_classifier import SessionOrdinal, classify_session_feature

from tests.Grok._fixtures import filter_session_name


def test_filter_window_is_inclusive_on_both_ends():
    """Source: crt_engine_v2.py:3113  `start <= t <= end`

    10:00:00 is still LONDON; 10:00:01 is not.
    """
    cfg = CRTConfig()
    assert filter_session_name(cfg, time(7, 0)) == "LONDON"
    assert filter_session_name(cfg, time(10, 0)) == "LONDON"
    assert filter_session_name(cfg, time(10, 0, 1)) == "OFF_SESSION"


def test_feature_window_is_half_open_on_the_hour():
    """Source: session_classifier.classify_session_feature  `start <= h < end`

    Feature uses the hour integer, so 10:59 is still hour=10 = LONDON,
    even though the FILTER left LONDON at 10:00:01.
    """
    from config_layer.production_config import get_prod_section

    cfg = get_prod_section("feature_pipeline")
    assert classify_session_feature(9, cfg) == int(SessionOrdinal.LONDON)
    assert classify_session_feature(10, cfg) == int(SessionOrdinal.LONDON)
    # FILTER at 10:59
    assert filter_session_name(CRTConfig(), time(10, 59)) == "OFF_SESSION"


def test_broker_summer_offset_is_minus_three_hours():
    """DST: NY DST date → broker UTC+3. Source: broker_clock.mt5_server_offset_hours"""
    import pandas as pd

    summer = pd.to_datetime(pd.Series(["2026-07-22 19:15:00"]))
    winter = pd.to_datetime(pd.Series(["2026-01-15 19:15:00"]))
    assert int(mt5_server_offset_hours(summer).iloc[0]) == 3
    assert int(mt5_server_offset_hours(winter).iloc[0]) == 2


def test_utc_corrected_can_move_a_bar_across_the_filter_boundary():
    """A broker-local 19:15 (OFF) is 16:15 UTC in July (still OFF under default
    NEWYORK 13:00-16:00 — 16:15 is past 16:00). A broker-local 16:15 (OFF) is
    13:15 UTC and becomes NEWYORK.

    Source: broker_clock.mt5_server_to_utc + CRTConfig.session_windows
    """
    import pandas as pd

    cfg = CRTConfig()
    broker = pd.to_datetime(pd.Series(["2026-07-22 16:15:00"]))
    utc = mt5_server_to_utc(broker).iloc[0]
    assert utc.hour == 13
    assert utc.minute == 15
    assert filter_session_name(cfg, time(16, 15)) == "OFF_SESSION"
    assert filter_session_name(cfg, time(utc.hour, utc.minute)) == "NEWYORK"


def test_candle_age_ttl_is_a_count_not_a_timestamp_delta():
    """pending_displacement_ttl_candles is a bar count (default 4), not 4 hours.

    Source: CRTConfig.pending_displacement_ttl_candles
    Failure mode: treating TTL as wall-clock on a weekend gap.
    """
    cfg = CRTConfig()
    assert cfg.pending_displacement_ttl_candles == 4
    # 4 M15 bars = 60 minutes only if the stream is gap-free
    m15 = timedelta(minutes=15)
    assert cfg.pending_displacement_ttl_candles * m15 == timedelta(hours=1)
    weekend_gap = timedelta(hours=48)
    assert weekend_gap != cfg.pending_displacement_ttl_candles * m15


def test_filter_lookup_is_a_function_of_time_of_day_only():
    """Class C: the filter names a clock time, not a bar identity.

    Source: crt_engine_v2.py:3110-3115 uses `_ts_time = candle.timestamp.time()`.
    """
    assert filter_session_name(CRTConfig(), time(8, 0)) == "LONDON"
