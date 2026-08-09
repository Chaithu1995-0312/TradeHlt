"""Tests for CRT session filter (mirrors engine_runner.allowed_sessions)."""
from datetime import datetime, time

import pytest

from config_layer.state_identity import CRTConfig


def test_crtconfig_default_allowed_sessions():
    """CRTConfig default mirrors v2_multi_2026_04 production allowed_sessions."""
    cfg = CRTConfig()
    assert "LONDON" in cfg.allowed_sessions
    assert "NEWYORK" in cfg.allowed_sessions
    assert "ASIA" not in cfg.allowed_sessions


def test_session_resolution_london():
    """A 08:30 UTC timestamp resolves to LONDON via session_windows lookup."""
    cfg = CRTConfig()
    t = time(8, 30)
    matched = next(
        (name for name, (s, e) in cfg.session_windows.items() if s <= t <= e),
        "OFF_SESSION",
    )
    assert matched == "LONDON"
    assert matched in cfg.allowed_sessions


def test_session_resolution_asia_blocked():
    """A 02:00 UTC timestamp resolves to ASIA, which is NOT in allowed_sessions."""
    cfg = CRTConfig()
    t = time(2, 0)
    matched = next(
        (name for name, (s, e) in cfg.session_windows.items() if s <= t <= e),
        "OFF_SESSION",
    )
    assert matched == "ASIA"
    assert matched not in cfg.allowed_sessions


def test_session_resolution_off_session_blocked():
    """A 11:30 UTC timestamp falls outside all windows → OFF_SESSION → blocked."""
    cfg = CRTConfig()
    t = time(11, 30)
    matched = next(
        (name for name, (s, e) in cfg.session_windows.items() if s <= t <= e),
        "OFF_SESSION",
    )
    assert matched == "OFF_SESSION"
    assert matched not in cfg.allowed_sessions


def test_allowed_sessions_normalization_via_dataclass_replace():
    """allowed_sessions field accepts tuple of uppercase strings via dataclass replace."""
    from dataclasses import replace
    cfg = CRTConfig()
    new_cfg = replace(cfg, allowed_sessions=("LONDON",))
    assert new_cfg.allowed_sessions == ("LONDON",)
    assert "NEWYORK" not in new_cfg.allowed_sessions


# ── F-066 session-filter fix: session_timestamp_basis gates the filter's clock ────────────────
# CRTEngine.process_candle's session-filter block (crt_engine_v2.py, "Session filter" comment)
# converts candle.timestamp via broker_clock.mt5_server_to_utc_scalar before this same window
# lookup, but ONLY when feature_pipeline.session_timestamp_basis == "utc_corrected". These tests
# mirror that block exactly, the same way the tests above mirror the plain lookup, rather than
# driving a full CRTEngine + state machine to reach the block.

def test_session_filter_basis_default_is_broker_local_unchanged():
    """Parity guard: the active config stays 'broker_local', so CRTEngine.__init__'s resolved
    `_session_ts_basis` takes the byte-identical, unconverted branch by default — the F-066 fix
    is opt-in, not a silent behavior change."""
    from config_layer.production_config import get_prod_section
    assert get_prod_section("feature_pipeline")["session_timestamp_basis"] == "broker_local"


def test_session_filter_utc_corrected_can_disagree_with_broker_local():
    """The two bases must be able to disagree, or the fix has no observable effect.

    Summer (EEST, MT5 broker +3h): a broker-local 13:00 candle matches NEWYORK (13:00-16:00)
    verbatim under the legacy 'broker_local' comparison. Its true UTC time is 10:00, which
    instead matches LONDON (07:00-10:00, inclusive upper bound) under 'utc_corrected' — a
    genuine session misclassification the fix corrects, not just a shift into OFF_SESSION.
    """
    from features import broker_clock as bc

    cfg = CRTConfig()

    def resolve(t):
        return next(
            (name for name, (s, e) in cfg.session_windows.items() if s <= t <= e),
            "OFF_SESSION",
        )

    broker_ts = datetime(2024, 7, 15, 13, 0, 0)
    broker_local_match = resolve(broker_ts.time())
    utc_corrected_match = resolve(bc.mt5_server_to_utc_scalar(broker_ts).time())

    assert broker_local_match == "NEWYORK"
    assert utc_corrected_match == "LONDON"


def test_crtengine_resolves_session_ts_basis_from_feature_pipeline_config():
    """CRTEngine.__init__ reads the SAME feature_pipeline.session_timestamp_basis key the FM-052
    feature already uses (no duplicate config key), and stores it once (not re-read per candle)."""
    from unittest.mock import patch

    from config_layer.config_builder import ConfigBuilder
    from config_layer.crt_engine_v2 import CRTEngine

    cfg = ConfigBuilder.build("XAUUSD")

    engine_default = CRTEngine(cfg)
    assert engine_default._session_ts_basis == "broker_local"

    from config_layer.production_config import get_prod_section as _real_gps

    def _gps_utc_corrected(section, *a, **kw):
        result = dict(_real_gps(section, *a, **kw))
        if section == "feature_pipeline":
            result["session_timestamp_basis"] = "utc_corrected"
        return result

    # crt_engine_v2.__init__ does a LOCAL `from config_layer.production_config import
    # get_prod_section` (resolved once at construction, not a module-level name in
    # crt_engine_v2) — patch the source module so the fresh import picks up the override.
    with patch("config_layer.production_config.get_prod_section", _gps_utc_corrected):
        engine_utc = CRTEngine(cfg)
    assert engine_utc._session_ts_basis == "utc_corrected"
