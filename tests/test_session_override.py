"""
Tests for per-instrument allowed_sessions override (B1).

Covers the additive `engine_runner.allowed_sessions_overrides` resolver in
production_config.load_prod_config_from_registry and the `_canon_session`
canonicalizer that preserves the engine-facing "OFF_SESSION" literal.

See plan: trd-m6-stays-downstream — instrument-scoped session expansion lets
BNBUSDT run +ASIA +OFF_SESSION without touching ETH/BTC.
"""
import json

import pytest

from config_layer.production_config import (
    _canon_session,
    load_prod_config_from_registry,
    resolve_allowed_sessions,
)


# ── resolve_allowed_sessions: the extracted single-source-of-truth helper ───
# Reused by both load_prod_config_from_registry and ConfigValidator.

def test_resolve_global_only_canonicalizes():
    er = {"allowed_sessions": ["london", "new_york", "off_session"]}
    assert resolve_allowed_sessions(er, "ETHUSDT") == ("LONDON", "NEWYORK", "OFF_SESSION")


def test_resolve_override_wins_case_insensitive():
    er = {
        "allowed_sessions": ["london", "new_york", "overlap"],
        "allowed_sessions_overrides": {"bnbusdt": ["london", "asia", "off_session"]},
    }
    assert resolve_allowed_sessions(er, "BNBUSDT") == ("LONDON", "ASIA", "OFF_SESSION")


def test_resolve_unlisted_instrument_falls_back_to_global():
    er = {
        "allowed_sessions": ["london", "new_york", "overlap"],
        "allowed_sessions_overrides": {"BNBUSDT": ["asia"]},
    }
    assert resolve_allowed_sessions(er, "ETHUSDT") == ("LONDON", "NEWYORK", "OVERLAP")


def test_resolve_returns_none_when_nothing_applies():
    assert resolve_allowed_sessions(None, "BNBUSDT") is None
    assert resolve_allowed_sessions({}, "BNBUSDT") is None
    # override map present but no match and no global → None (leave untouched)
    assert resolve_allowed_sessions(
        {"allowed_sessions_overrides": {"SOLUSDT": ["asia"]}}, "BNBUSDT"
    ) is None


# ── _canon_session: the bug-fix core ───────────────────────────────────────
# The engine compares against session_windows keys ("LONDON"/"NEWYORK"/"ASIA")
# and the off-session literal "OFF_SESSION". Underscores must be stripped for
# the window keys, but PRESERVED for off-session ("OFFSESSION" would never
# match and off-session trades would stay silently rejected).
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("london", "LONDON"),
        ("new_york", "NEWYORK"),
        ("NEWYORK", "NEWYORK"),
        ("asia", "ASIA"),
        ("overlap", "OVERLAP"),
        ("off_session", "OFF_SESSION"),
        ("OFF_SESSION", "OFF_SESSION"),
        ("offsession", "OFF_SESSION"),
    ],
)
def test_canon_session(raw, expected):
    assert _canon_session(raw) == expected


def _write_registry(tmp_path, allowed, overrides=None):
    """Write a minimal, hash-free registry file and return its dir."""
    engine_runner = {"allowed_sessions": allowed}
    if overrides is not None:
        engine_runner["allowed_sessions_overrides"] = overrides
    reg = {
        # params must be truthy and contain only valid CRTConfig field names.
        "params": {"tier_1_threshold": 0.75},
        "engine_runner": engine_runner,
    }
    (tmp_path / "v_test.json").write_text(json.dumps(reg), encoding="utf-8")
    return str(tmp_path)


def _load(tmp_path, instrument):
    return load_prod_config_from_registry(
        "v_test", instrument, registry_dir=tmp_path, verify_hash=False
    )


def test_override_applies_for_named_instrument(tmp_path):
    reg_dir = _write_registry(
        tmp_path,
        ["london", "new_york", "overlap"],
        {"BNBUSDT": ["london", "new_york", "overlap", "asia", "off_session"]},
    )
    cfg = _load(reg_dir, "BNBUSDT")
    assert "ASIA" in cfg.allowed_sessions
    assert "OFF_SESSION" in cfg.allowed_sessions
    assert "NEWYORK" in cfg.allowed_sessions


def test_global_fallback_for_unlisted_instrument(tmp_path):
    """An instrument with no override key keeps the global allowed_sessions."""
    reg_dir = _write_registry(
        tmp_path,
        ["london", "new_york", "overlap"],
        {"BNBUSDT": ["london", "new_york", "overlap", "asia", "off_session"]},
    )
    cfg = _load(reg_dir, "ETHUSDT")
    assert cfg.allowed_sessions == ("LONDON", "NEWYORK", "OVERLAP")
    assert "ASIA" not in cfg.allowed_sessions
    assert "OFF_SESSION" not in cfg.allowed_sessions


def test_override_lookup_is_case_insensitive_on_instrument(tmp_path):
    reg_dir = _write_registry(tmp_path, ["london"], {"bnbusdt": ["london", "asia"]})
    cfg = _load(reg_dir, "BNBUSDT")
    assert "ASIA" in cfg.allowed_sessions


def test_absent_override_map_is_noop(tmp_path):
    """No allowed_sessions_overrides key → global behavior unchanged (regression)."""
    reg_dir = _write_registry(tmp_path, ["london", "new_york", "overlap"])
    cfg = _load(reg_dir, "BNBUSDT")
    assert cfg.allowed_sessions == ("LONDON", "NEWYORK", "OVERLAP")
