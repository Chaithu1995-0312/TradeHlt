"""Tests for CRT session filter (mirrors engine_runner.allowed_sessions)."""
from datetime import time

import pytest

from config_layer.crt_engine_v2 import CRTConfig


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
