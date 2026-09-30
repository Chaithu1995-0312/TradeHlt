"""EPIC-84 L-C (src/engines): LiveEngineConfig.from_env() + LiveEngine.process()
trade-time REJECT.

LiveEngineConfig's dataclass field defaults are KEPT (several out-of-lane
callers construct `LiveEngineConfig(enabled=False)` for an inert/disabled
engine — see the class's own EPIC-84 comment) but from_env(), the one path
that loads REAL values, no longer substitutes a magic-number literal for a
missing behavioural env var. TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID stay
genuinely optional (validate() already documents their absence as non-fatal).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from config_layer.strict_config import ConfigKeyMissingError  # noqa: E402
from engines.live_engine import LiveEngine, LiveEngineConfig  # noqa: E402

_ALL_ENV = {
    "LIVE_ENGINE_ENABLED": "1",
    "LIVE_RR_THRESHOLD": "1.5",
    "LIVE_CONF_MIN": "0.55",
    "LIVE_CONF_STRONG": "0.60",
    "LIVE_ML_OVERRIDE": "0.75",
    "LIVE_COOLDOWN_SECONDS": "60",
    "LIVE_DEDUP_CANDLES": "4",
}


def _set_env(monkeypatch, env: dict) -> None:
    for key in LiveEngineConfig._ENV_REQUIRED:
        monkeypatch.delenv(key, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_from_env_reads_declared_values(monkeypatch):
    _set_env(monkeypatch, _ALL_ENV)
    cfg = LiveEngineConfig.from_env()
    assert cfg.enabled is True
    assert cfg.rr_threshold == 1.5
    assert cfg.dedup_candles == 4


@pytest.mark.parametrize("key", sorted(LiveEngineConfig._ENV_REQUIRED))
def test_from_env_missing_var_raises_naming_it(monkeypatch, key):
    env = {k: v for k, v in _ALL_ENV.items() if k != key}
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigKeyMissingError) as ei:
        LiveEngineConfig.from_env()
    assert key in ei.value.missing
    assert ei.value.section == "env"


def test_from_env_telegram_credentials_stay_optional(monkeypatch):
    """bot_token/chat_id absence is non-fatal per validate() — from_env() must
    not raise for them."""
    _set_env(monkeypatch, _ALL_ENV)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    cfg = LiveEngineConfig.from_env()
    assert cfg.bot_token == ""
    assert cfg.chat_id == ""
    assert "TELEGRAM_BOT_TOKEN not set — alerts will be logged only" in cfg.validate()


def test_disabled_construction_still_works_without_env():
    """The widely-used LiveEngineConfig(enabled=False) convenience
    construction (tests/orchestrator wiring outside this lane) must keep
    working without any env vars declared."""
    cfg = LiveEngineConfig(enabled=False)
    assert cfg.rr_threshold == 1.5  # class-level default, unchanged


# ── LiveEngine.process() trade-time REJECT ────────────────────────────────


def test_process_rejects_trade_data_missing_symbol():
    engine = LiveEngine(LiveEngineConfig(enabled=False))
    result = engine.process({"session": "asia"}, gaussian_model=None, scaler=None)
    assert result["decision"] == "BLOCK"
    assert result["reason"] == "config_key_missing:trade_data.symbol"
    assert result["symbol"] == ""


def test_process_rejects_trade_data_missing_session():
    engine = LiveEngine(LiveEngineConfig(enabled=False))
    result = engine.process({"symbol": "XAUUSD"}, gaussian_model=None, scaler=None)
    assert result["decision"] == "BLOCK"
    assert result["reason"] == "config_key_missing:trade_data.session"
    assert result["symbol"] == "XAUUSD"


def test_process_missing_trade_data_reports_kill_switch_first_if_disabled():
    """Kill-switch check runs AFTER the symbol/session REJECT — with enabled=
    False and a complete trade_data, the kill switch (not the REJECT path)
    is what stops processing."""
    engine = LiveEngine(LiveEngineConfig(enabled=False))
    result = engine.process({"symbol": "XAUUSD", "session": "asia"}, gaussian_model=None, scaler=None)
    assert result["suppressed_reason"] == "kill_switch_disabled"
