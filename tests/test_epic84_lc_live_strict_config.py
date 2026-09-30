"""EPIC-84 L-C (src/live): strict config reads, no defaults, no fallbacks.

User rule 2026-09-28: every value that affects behaviour is DECLARED in the
production config. This module proves, for the live/ modules:

  (1) removing each required key raises ``ConfigKeyMissingError`` naming it
      (parametrized over the key list), at load/construction time;
  (2) the value the code reads is the DECLARED value — for the three keys this
      lane newly declares (magic / deviation / slippage) that value is exactly the
      literal that ran before the migration, so parity is a value-equality fact,
      not a hope;
  (3) a missing PER-TRADE value does not raise: the trade is REJECTED with
      reason ``config_key_missing:<section>.<key>`` (the engine keeps running);
  (4) the Telegram environment path fails closed instead of substituting "".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from config_layer.strict_config import ConfigKeyMissingError  # noqa: E402
from live.mt5_bridge import MT5Bridge  # noqa: E402
from live.order_manager import OrderManager, PaperVenueExecutor  # noqa: E402
from live.telegram_bridge import TelegramBridge  # noqa: E402

PROD = _ROOT / "configs" / "production"
ACTIVE = (PROD / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()

#: The DECLARATIONS this lane adds for MT5Bridge (value = the literal that ran
#: before the migration; see the lane's DECLARATIONS table).
MT5_DECLARED = {"magic": 20260501, "deviation": 20, "slippage": 3}
MT5_KEYS = ("enabled", "dry_run", "magic", "deviation", "slippage", "lot_min", "lot_max")
TG_KEYS = ("enabled", "bot_token", "chat_id", "timeout_s", "dry_run")


def _live_integration() -> dict:
    """ACTIVE config's live_integration section, with this lane's declarations applied.

    Reading the real registry (plus the declared keys) keeps the test honest: it
    exercises the same section the runtime loads, not a hand-written stub.
    """
    data = json.loads((PROD / f"{ACTIVE}.json").read_text(encoding="utf-8"))
    section = dict(data["live_integration"])
    mt5 = dict(section["mt5"])
    for key, value in MT5_DECLARED.items():
        mt5.setdefault(key, value)
    section["mt5"] = mt5
    return section


def _patch_section(monkeypatch, section) -> None:
    monkeypatch.setattr("live.mt5_bridge.get_prod_section", lambda _name: section)
    monkeypatch.setattr("live.telegram_bridge.get_prod_section", lambda _name: section)


# ── MT5Bridge ─────────────────────────────────────────────────────────────────


def test_mt5_declared_values_are_the_pre_migration_literals(monkeypatch):
    """Parity proof: the declared values == the literals the old code substituted."""
    _patch_section(monkeypatch, _live_integration())
    bridge = MT5Bridge.from_prod_config()
    assert bridge._magic == MT5_DECLARED["magic"] == 20260501
    assert bridge._deviation == MT5_DECLARED["deviation"] == 20
    assert bridge._slippage == MT5_DECLARED["slippage"] == 3
    # Keys the registry already declared are read from the registry, not from code.
    section = _live_integration()["mt5"]
    assert bridge._lot_min == section["lot_min"]
    assert bridge._lot_max == section["lot_max"]
    assert bridge._enabled == section["enabled"]
    assert bridge._dry_run is True  # dry_run or not _MT5_AVAILABLE


@pytest.mark.parametrize("key", MT5_KEYS)
def test_mt5_missing_key_raises_naming_it(monkeypatch, key):
    section = _live_integration()
    section["mt5"] = {k: v for k, v in section["mt5"].items() if k != key}
    _patch_section(monkeypatch, section)
    with pytest.raises(ConfigKeyMissingError) as ei:
        MT5Bridge.from_prod_config()
    assert key in ei.value.missing
    assert ei.value.section == "live_integration.mt5"
    assert "MT5Bridge" in str(ei.value)


def test_mt5_all_keys_missing_lists_every_one(monkeypatch):
    section = _live_integration()
    section["mt5"] = {}
    _patch_section(monkeypatch, section)
    with pytest.raises(ConfigKeyMissingError) as ei:
        MT5Bridge.from_prod_config()
    assert set(ei.value.missing) == set(MT5_KEYS)


def test_mt5_missing_subsection_raises(monkeypatch):
    section = _live_integration()
    section.pop("mt5")
    _patch_section(monkeypatch, section)
    with pytest.raises(ConfigKeyMissingError) as ei:
        MT5Bridge.from_prod_config()
    assert ei.value.missing == ("mt5",)


# ── TelegramBridge ────────────────────────────────────────────────────────────


def test_telegram_reads_the_declared_section(monkeypatch):
    _patch_section(monkeypatch, _live_integration())
    tg = TelegramBridge.from_prod_config()
    section = _live_integration()["telegram"]
    assert tg._timeout == section["timeout_s"]
    assert tg._dry_run is section["dry_run"]
    # credentials come from the DECLARED value only ("" in the active config)
    assert tg._token == section["bot_token"]


@pytest.mark.parametrize("key", TG_KEYS)
def test_telegram_missing_key_raises_naming_it(monkeypatch, key):
    section = _live_integration()
    section["telegram"] = {k: v for k, v in section["telegram"].items() if k != key}
    _patch_section(monkeypatch, section)
    with pytest.raises(ConfigKeyMissingError) as ei:
        TelegramBridge.from_prod_config()
    assert key in ei.value.missing
    assert ei.value.section == "live_integration.telegram"


def test_telegram_from_env_fails_closed_when_absent(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(ConfigKeyMissingError) as ei:
        TelegramBridge.from_env()
    assert set(ei.value.missing) == {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"}
    assert ei.value.section == "env"


def test_telegram_from_env_uses_declared_env_values(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok-123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-9")
    tg = TelegramBridge.from_env(dry_run=True)
    assert tg._token == "tok-123"
    assert tg._chat_id == "chat-9"


def test_telegram_env_is_not_a_second_source_for_prod_config(monkeypatch):
    """from_prod_config reads the declared value even when the env var is set."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token-must-not-win")
    _patch_section(monkeypatch, _live_integration())
    expected = _live_integration()["telegram"]["bot_token"]
    assert TelegramBridge.from_prod_config()._token == expected


# ── OrderManager (trade-time REJECT, never a literal) ─────────────────────────


def _om() -> OrderManager:
    return OrderManager(
        PaperVenueExecutor(), dry_run=True, fill_timeout_s=5.0, allow_partial=False,
    )


_PLAN = {
    "execution_id": "e1",
    "symbol": "XAUUSD",
    "direction": 1,
    "entry_price": 2000.0,
    "stop_loss": 1999.0,
    "take_profit_1": 2002.0,
}


@pytest.mark.parametrize("key", ["decision", "final_position_size"])
def test_order_manager_missing_ultron_value_rejects(key):
    ultron = {"decision": "approve", "final_position_size": 0.1}
    ultron.pop(key)
    fill = _om().submit(dict(_PLAN), ultron)
    assert fill.status == "REJECTED"
    assert fill.reason == f"config_key_missing:ultron_result.{key}"


def test_order_manager_missing_execution_id_rejects():
    plan = {k: v for k, v in _PLAN.items() if k != "execution_id"}
    fill = _om().submit(plan, {"decision": "approve", "final_position_size": 0.1})
    assert fill.status == "REJECTED"
    assert fill.reason == "config_key_missing:trade_plan.execution_id"
    # the REJECT report echoes what it was given — no placeholder identity
    assert fill.execution_id == ""


def test_order_manager_none_size_is_a_declared_reject_not_a_default():
    fill = _om().submit(dict(_PLAN), {"decision": "approve", "final_position_size": None})
    assert fill.status == "REJECTED"
    assert fill.reason == "size_not_approved"


def test_order_manager_approved_trade_still_fills():
    fill = _om().submit(dict(_PLAN), {"decision": "approve", "final_position_size": 0.1})
    assert fill.status == "FILLED"
    assert fill.execution_id == "e1"
    assert fill.symbol == "XAUUSD"
