"""Tests for CRT session filter (mirrors engine_runner.allowed_sessions)."""
from datetime import datetime, time

import pytest

from config_layer.state_identity import CRTConfig
from tests.helpers.crt_config import crt_config_for_test
from tests.helpers.crt_config import crt_engine_for_test, execution_engine_for_test, reset_logic_for_test  # noqa: F401


def test_crtconfig_default_allowed_sessions():
    """CRTConfig default mirrors v2_multi_2026_04 production allowed_sessions."""
    cfg = crt_config_for_test()
    assert "LONDON" in cfg.allowed_sessions
    assert "NEWYORK" in cfg.allowed_sessions
    assert "ASIA" not in cfg.allowed_sessions


def test_session_resolution_london():
    """A 08:30 UTC timestamp resolves to LONDON via session_windows lookup."""
    cfg = crt_config_for_test()
    t = time(8, 30)
    matched = next(
        (name for name, (s, e) in cfg.session_windows.items() if s <= t <= e),
        "OFF_SESSION",
    )
    assert matched == "LONDON"
    assert matched in cfg.allowed_sessions


def test_session_resolution_asia_blocked():
    """A 02:00 UTC timestamp resolves to ASIA, which is NOT in allowed_sessions."""
    cfg = crt_config_for_test()
    t = time(2, 0)
    matched = next(
        (name for name, (s, e) in cfg.session_windows.items() if s <= t <= e),
        "OFF_SESSION",
    )
    assert matched == "ASIA"
    assert matched not in cfg.allowed_sessions


def test_session_resolution_off_session_blocked():
    """A 11:30 UTC timestamp falls outside all windows → OFF_SESSION → blocked."""
    cfg = crt_config_for_test()
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
    cfg = crt_config_for_test()
    new_cfg = replace(cfg, allowed_sessions=("LONDON",))
    assert new_cfg.allowed_sessions == ("LONDON",)
    assert "NEWYORK" not in new_cfg.allowed_sessions


# ── Clock contract (CH-corpus-clock-contract-v1): the session filter compares UTC directly ───────
# `session_timestamp_basis` is RETIRED. Candle timestamps are canonical UTC (the corpus SSOT
# normalized the declared source clock once) and `CRTConfig.session_windows` is UTC-authored, so
# CRTEngine._session_name_at compares them as-is — no basis switch, no per-candle conversion.

def test_session_filter_basis_key_is_retired():
    from config_layer.production_config import get_prod_section
    assert "session_timestamp_basis" not in get_prod_section("feature_pipeline")


def test_session_filter_compares_canonical_utc_directly():
    """UTC 10:00 is LONDON (07:00-10:00 inclusive), UTC 13:00 is NEWYORK (13:00-16:00); the same
    wall times the old broker-label reading would have mapped 2-3h later."""
    from types import SimpleNamespace

    cfg = crt_config_for_test()
    engine = crt_engine_for_test(cfg)
    at = lambda h, m=0: engine._session_name_at(SimpleNamespace(timestamp=datetime(2024, 7, 15, h, m)))
    assert at(10, 0) == "LONDON"
    assert at(13, 0) == "NEWYORK"
    assert at(11, 0) == "OFF_SESSION"
    assert at(0, 0) == "ASIA"


def test_crtengine_has_no_session_basis_state():
    """The engine neither reads feature_pipeline.session_timestamp_basis nor stores a basis."""
    cfg = crt_config_for_test()
    engine = crt_engine_for_test(cfg)
    assert not hasattr(engine, "_session_ts_basis")
