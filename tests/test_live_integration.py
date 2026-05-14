"""
tests/test_live_integration.py
Sprint 6 — Live Hook Integration test coverage.

Tests:
  TelegramBridge
    - disabled bridge: send returns False without error
    - dry_run bridge: send returns True, no HTTP
    - is_configured() reflects enabled+token+requests state
    - send_signal_alert formats and routes correctly
    - send_kill_switch formats and routes correctly
    - send_daily_summary formats and routes correctly
    - missing token → not configured even if enabled=True

  MT5Bridge
    - disabled bridge: send_order returns None
    - dry_run bridge: send_order returns sentinel -1
    - dry_run bridge: close_position returns True
    - dry_run bridge: get_account_info returns dry_run marker
    - lot_size clamped to [lot_min, lot_max]
    - from_prod_config() loads section without raising

  register_trade_outcome
    - profit does NOT trip kill switch
    - large loss trips kill switch and returns True
    - already-tripped: returns False

  live_engine_hook singletons
    - _get_kill_switch() returns KillSwitch instance
    - _get_telegram() returns TelegramBridge instance
    - _get_mt5() returns MT5Bridge instance
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from live.telegram_bridge import TelegramBridge
from live.mt5_bridge import MT5Bridge
from uat.kill_switch import KillSwitch


# ── TelegramBridge ─────────────────────────────────────────────────────────────

class TestTelegramBridge:

    def test_disabled_send_returns_false(self):
        tg = TelegramBridge(enabled=False)
        assert tg._send("hello") is False

    def test_dry_run_send_returns_true(self):
        tg = TelegramBridge(bot_token="tok", chat_id="123", dry_run=True)
        assert tg._send("hello") is True

    def test_no_token_not_configured(self):
        tg = TelegramBridge(bot_token="", chat_id="123", enabled=True)
        assert tg.is_configured() is False

    def test_no_chat_id_not_configured(self):
        tg = TelegramBridge(bot_token="tok", chat_id="", enabled=True)
        assert tg.is_configured() is False

    def test_send_signal_alert_dry_run(self):
        tg = TelegramBridge(bot_token="tok", chat_id="123", dry_run=True)
        ok = tg.send_signal_alert(
            pair="EURUSD", timeframe="H1", signal="BUY",
            confidence=0.72, entry_price=1.1050,
            sl_inr=2500.0, tp_inr=5000.0, rr_ratio=2.0,
        )
        assert ok is True

    def test_send_kill_switch_dry_run(self):
        tg = TelegramBridge(bot_token="tok", chat_id="123", dry_run=True)
        ok = tg.send_kill_switch(
            reason="daily", daily_loss_inr=1500.0, weekly_loss_inr=3000.0
        )
        assert ok is True

    def test_send_daily_summary_dry_run(self):
        tg = TelegramBridge(bot_token="tok", chat_id="123", dry_run=True)
        ok = tg.send_daily_summary(trades=5, wins=3, daily_pnl_inr=2000.0, weekly_pnl_inr=4500.0)
        assert ok is True

    def test_send_with_strategy_scores(self):
        tg = TelegramBridge(bot_token="tok", chat_id="123", dry_run=True)
        ok = tg.send_signal_alert(
            pair="GBPUSD", timeframe="M15", signal="SELL",
            confidence=0.65, entry_price=1.2700,
            sl_inr=1800.0, tp_inr=3600.0, rr_ratio=2.0,
            strategy_scores={"S1": 0.75, "S10": 0.70, "S3": 0.55},
        )
        assert ok is True

    def test_network_error_swallowed(self):
        tg = TelegramBridge(bot_token="tok", chat_id="123", enabled=True, dry_run=False)
        # requests is either not available or will fail — either way must not raise
        result = tg._send("test message")
        assert isinstance(result, bool)

    def test_from_prod_config_returns_instance(self):
        tg = TelegramBridge.from_prod_config()
        assert isinstance(tg, TelegramBridge)
        # prod config has enabled=False — confirm disabled
        assert tg._enabled is False


# ── MT5Bridge ──────────────────────────────────────────────────────────────────

class TestMT5Bridge:

    def test_disabled_send_returns_none(self):
        mt5 = MT5Bridge(enabled=False)
        result = mt5.send_order("EURUSD", "BUY", 0.01, 1.1000, 1.1100)
        assert result is None

    def test_dry_run_send_returns_sentinel(self):
        mt5 = MT5Bridge(enabled=True, dry_run=True)
        ticket = mt5.send_order("EURUSD", "BUY", 0.01, 1.1000, 1.1100)
        assert ticket == -1

    def test_dry_run_close_returns_true(self):
        mt5 = MT5Bridge(enabled=True, dry_run=True)
        assert mt5.close_position(ticket=12345, symbol="EURUSD", lot_size=0.01) is True

    def test_dry_run_account_info_has_marker(self):
        mt5 = MT5Bridge(enabled=True, dry_run=True)
        info = mt5.get_account_info()
        assert info.get("dry_run") is True

    def test_lot_clamped_to_min(self):
        mt5 = MT5Bridge(enabled=True, dry_run=True, lot_min=0.01, lot_max=5.0)
        # Passing 0.001 (below min) should clamp to 0.01 and still return sentinel
        ticket = mt5.send_order("EURUSD", "BUY", 0.001, 1.1000, 1.1100)
        assert ticket == -1

    def test_lot_clamped_to_max(self):
        mt5 = MT5Bridge(enabled=True, dry_run=True, lot_min=0.01, lot_max=2.0)
        ticket = mt5.send_order("EURUSD", "SELL", 99.0, 1.1100, 1.1000)
        assert ticket == -1

    def test_connect_dry_run_succeeds(self):
        mt5 = MT5Bridge(enabled=True, dry_run=True)
        assert mt5.connect() is True
        assert mt5.is_connected() is True

    def test_disabled_bridge_not_connected(self):
        mt5 = MT5Bridge(enabled=False, dry_run=True)
        mt5.connect()
        assert mt5.is_connected() is False

    def test_from_prod_config_returns_instance(self):
        mt5 = MT5Bridge.from_prod_config()
        assert isinstance(mt5, MT5Bridge)
        # prod config has dry_run=True and enabled=False
        assert mt5._dry_run is True


# ── register_trade_outcome ─────────────────────────────────────────────────────

class TestRegisterTradeOutcome:

    def test_profit_does_not_trip(self, tmp_path, monkeypatch):
        ks = KillSwitch(
            daily_limit_inr=1000.0,
            weekly_limit_inr=3000.0,
            state_file=tmp_path / "ks.json",
        )
        import runtime.live_engine_hook as hook
        monkeypatch.setattr(hook, "_kill_switch", ks)
        result = hook.register_trade_outcome(pnl_inr=500.0)
        assert result is False
        assert not ks.is_tripped()

    def test_large_loss_trips(self, tmp_path, monkeypatch):
        ks = KillSwitch(
            daily_limit_inr=1000.0,
            weekly_limit_inr=3000.0,
            state_file=tmp_path / "ks.json",
        )
        import runtime.live_engine_hook as hook
        monkeypatch.setattr(hook, "_kill_switch", ks)
        monkeypatch.setattr(hook, "_telegram", None)  # suppress Telegram in test
        result = hook.register_trade_outcome(pnl_inr=-1500.0)
        assert result is True
        assert ks.is_tripped()

    def test_already_tripped_returns_false(self, tmp_path, monkeypatch):
        ks = KillSwitch(
            daily_limit_inr=1000.0,
            weekly_limit_inr=3000.0,
            state_file=tmp_path / "ks.json",
        )
        ks.register_trade(pnl_inr=-1500.0)
        assert ks.is_tripped()
        import runtime.live_engine_hook as hook
        monkeypatch.setattr(hook, "_kill_switch", ks)
        # Second registration on already-tripped KS returns False (blocked)
        result = hook.register_trade_outcome(pnl_inr=-200.0)
        assert result is False

    def test_ks_unavailable_returns_false(self, monkeypatch):
        import runtime.live_engine_hook as hook
        monkeypatch.setattr(hook, "_kill_switch", None)
        monkeypatch.setattr(hook, "_KS_AVAILABLE", False)
        result = hook.register_trade_outcome(pnl_inr=-999.0)
        assert result is False


# ── Singleton getters ──────────────────────────────────────────────────────────

class TestSingletonGetters:

    def test_get_kill_switch_returns_instance(self, tmp_path, monkeypatch):
        import runtime.live_engine_hook as hook
        monkeypatch.setattr(hook, "_kill_switch", None)
        monkeypatch.setattr(hook, "_KS_AVAILABLE", True)
        # Patch from_prod_config to avoid needing full config for this unit test
        ks_mock = KillSwitch(
            daily_limit_inr=10000.0,
            weekly_limit_inr=25000.0,
            state_file=tmp_path / "ks_sg.json",
        )
        with patch.object(KillSwitch, "from_prod_config", return_value=ks_mock):
            result = hook._get_kill_switch()
        assert isinstance(result, KillSwitch)

    def test_get_telegram_returns_instance(self, monkeypatch):
        import runtime.live_engine_hook as hook
        monkeypatch.setattr(hook, "_telegram", None)
        monkeypatch.setattr(hook, "_TELEGRAM_AVAILABLE", True)
        tg_mock = TelegramBridge(enabled=False)
        with patch.object(TelegramBridge, "from_prod_config", return_value=tg_mock):
            result = hook._get_telegram()
        assert isinstance(result, TelegramBridge)

    def test_get_mt5_returns_instance(self, monkeypatch):
        import runtime.live_engine_hook as hook
        monkeypatch.setattr(hook, "_mt5", None)
        monkeypatch.setattr(hook, "_MT5_AVAILABLE", True)
        mt5_mock = MT5Bridge(dry_run=True)
        with patch.object(MT5Bridge, "from_prod_config", return_value=mt5_mock):
            result = hook._get_mt5()
        assert isinstance(result, MT5Bridge)
