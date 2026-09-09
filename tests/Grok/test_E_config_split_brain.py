"""E. Config split-brain — authoritative A vs used B.

Semantic invariant: the ACTIVE production config must be the object that
reaches session windows, allowed_sessions, and sl_atr_buffer at runtime.
Ordinary tests check that a builder stamps provenance, not that two session
lists / two ATR names cannot be swapped.
"""
from __future__ import annotations

from datetime import datetime, time

import pytest

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_config_provenance import ConstructionMode, fingerprint, get_provenance
from config_layer.production_config import (
    get_active_version,
    get_prod_section,
    load_prod_config_from_registry,
    resolve_allowed_sessions,
)
from config_layer.state_identity import CRTConfig
from config_layer.crt_engine_v2 import UltronRiskEngine

from tests.Grok._fixtures import filter_session_name


def test_active_version_is_the_tier0_pointer():
    # v2_htfcrt_2026_08 (CH-htfcrt-parent-candle-smc-v1, 2026-08-15) — was v2_multi_2026_04.
    assert get_active_version() == "v2_htfcrt_2026_08"


def test_bare_builder_is_not_the_production_runtime_object():
    """F-057 class: ConfigBuilder.build ≠ production merge.

    Source: production_config.load_prod_config_from_registry vs ConfigBuilder.build
    Already visible via fingerprint; this test requires the *session* surface to differ
    or be proven equal — session is the decision-facing field.
    """
    router = ConfigBuilder.build("XAUUSD")
    prod = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    assert get_provenance(router).mode == ConstructionMode.ROUTER_BASE
    assert get_provenance(prod).mode == ConstructionMode.PRODUCTION_MERGED
    assert fingerprint(router) != fingerprint(prod)


def test_production_allowed_sessions_are_canonical_uppercase():
    """engine_runner JSON uses london/new_york/overlap; runtime must be LONDON/NEWYORK/OVERLAP.

    Source: production_config._canon_session + resolve_allowed_sessions
    Failure mode: filter compares 'LONDON' to 'london' and rejects every bar.
    """
    er = get_prod_section("engine_runner")
    assert er["allowed_sessions"] == ["london", "new_york", "overlap"]
    resolved = resolve_allowed_sessions(er, "XAUUSD")
    assert resolved == ("LONDON", "NEWYORK", "OVERLAP")
    prod = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    assert prod.allowed_sessions == ("LONDON", "NEWYORK", "OVERLAP")


def test_session_windows_override_also_moves_time_score():
    """A3 confound: opening session_windows is not a session-gate-only change.

    Source: UltronRiskEngine.score_time reads the same session_windows.
    Trace: time_score 0.0 → 0.8 when windows are opened.
    """
    closed = CRTConfig()  # 19:15 is outside default bands
    opened = CRTConfig(
        session_windows={
            "ASIA": (time(0, 0), time(9, 0)),
            "LONDON": (time(7, 0), time(16, 0)),
            "NEWYORK": (time(12, 0), time(21, 0)),
        }
    )
    ts = datetime(2026, 7, 22, 19, 15, 0)
    assert UltronRiskEngine(closed).score_time(ts) == pytest.approx(0.0)
    assert UltronRiskEngine(opened).score_time(ts) == pytest.approx(0.8)
    assert filter_session_name(closed, ts.time()) == "OFF_SESSION"
    assert filter_session_name(opened, ts.time()) == "NEWYORK"


def test_sl_atr_buffer_on_production_merge_is_the_runtime_value():
    prod = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    crt_section = get_prod_section("crt_engine")
    assert prod.sl_atr_buffer == pytest.approx(float(crt_section["sl_atr_buffer"]))
    assert prod.sl_atr_buffer == pytest.approx(0.2)
