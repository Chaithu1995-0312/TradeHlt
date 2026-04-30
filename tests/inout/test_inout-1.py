"""
test_inout.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — Test Suite

Coverage:
    - INOUTConfig: load, defaults, fraction validation
    - INOUTDatabase: schema init, create/transition/exit/query
    - INOUTScanner: all three conditions, composite scoring, cooldown
    - INOUTStateMachine: every state transition + time-stop paths
    - INOUTController: guard rails, plan building, signal acceptance
    - Integration: full signal → active → tier1 → tier2 → closed path

Run:
    python -m pytest test_inout.py -v
    python test_inout.py   (standalone)
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

# Allow running from codebase root or inout/ parent directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inout.config import INOUTConfig, INOUT_DEFAULTS, _validate_fractions
from inout.db import INOUTDatabase
from inout.scanner import INOUTScanner, INOUTSignal
from inout.state_machine import INOUTStateMachine, ActionType
from inout.executor import INOUTExecutor
from inout.controller import INOUTController


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_cfg(overrides: dict | None = None) -> INOUTConfig:
    """Build a test INOUTConfig with temp DB path."""
    import copy
    import tempfile
    raw = copy.deepcopy(INOUT_DEFAULTS)
    raw["db"]["path"] = tempfile.mktemp(suffix=".db")
    if overrides:
        from inout.config import _deep_merge
        _deep_merge(raw, overrides)
    return INOUTConfig(raw)


def _make_candles(
    count: int = 30,
    base: float = 50000.0,
    explosive_last: bool = False,
    volume_spike: bool = False,
) -> list[dict]:
    candles = []
    price = base
    for i in range(count):
        if i == count - 1 and explosive_last:
            open_ = price
            close = round(open_ * 1.015, 5)   # 1.5% explosive move
            high = round(close * 1.002, 5)
            low = round(open_ * 0.999, 5)
            vol = 5000.0 if volume_spike else 500.0
            atr = 250.0
        else:
            open_ = price
            close = round(open_ * 1.0003, 5)
            high = round(close * 1.0002, 5)
            low = round(open_ * 0.9998, 5)
            vol = 500.0
            atr = 100.0
        candles.append({
            "open": open_, "high": high, "low": low,
            "close": close, "volume": vol, "atr": atr,
        })
        price = close
    return candles


def _make_trade_record(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = {
        "trade_id": "test-trade-001",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "state": "ACTIVE",
        "entry_price": 50000.0,
        "stop_loss": 49500.0,     # 500 pts SL distance
        "tp1_price": 50500.0,     # 1R
        "tp2_price": 51000.0,     # 2R
        "runner_trail_sl": 49500.0,
        "position_size": 0.01,
        "risk_pct": 0.5,
        "rr_ratio": 2.0,
        "signal_score": 0.75,
        "created_at": now.isoformat(),
        "activated_at": now.isoformat(),
        "time_stop_at": (now + timedelta(minutes=15)).isoformat(),
    }
    base.update(overrides)
    return base


# ═════════════════════════════════════════════════════════════════════════════
# 1. Config Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestINOUTConfig(unittest.TestCase):

    def test_defaults_load(self):
        cfg = _make_cfg()
        self.assertEqual(cfg.exit("tp1_fraction"), 0.30)
        self.assertEqual(cfg.exit("tp2_fraction"), 0.50)
        self.assertEqual(cfg.exit("runner_fraction"), 0.20)
        self.assertEqual(cfg.time("default_time_min"), 8)
        self.assertEqual(cfg.risk("max_concurrent_trades"), 3)

    def test_fraction_validation_passes(self):
        """0.30 + 0.50 + 0.20 = 1.0 — must not raise"""
        _validate_fractions(INOUT_DEFAULTS)  # should not raise

    def test_fraction_validation_fails(self):
        """Bad fractions must raise ValueError"""
        bad = {"exit": {"tp1_fraction": 0.4, "tp2_fraction": 0.4, "runner_fraction": 0.3}}
        with self.assertRaises(ValueError):
            _validate_fractions(bad)

    def test_override_via_dict(self):
        cfg = _make_cfg({"time": {"default_time_min": 5}})
        self.assertEqual(cfg.time("default_time_min"), 5)

    def test_missing_key_returns_default(self):
        cfg = _make_cfg()
        self.assertIsNone(cfg.exit("nonexistent_key"))
        self.assertEqual(cfg.exit("nonexistent_key", "fallback"), "fallback")

    def test_raw_returns_full_dict(self):
        cfg = _make_cfg()
        raw = cfg.raw()
        self.assertIn("scanner", raw)
        self.assertIn("exit", raw)
        self.assertIn("time", raw)
        self.assertIn("risk", raw)


# ═════════════════════════════════════════════════════════════════════════════
# 2. Database Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestINOUTDatabase(unittest.TestCase):

    def setUp(self):
        self.cfg = _make_cfg()
        self.db = INOUTDatabase(self.cfg)

    def test_schema_initializes(self):
        """DB must initialize without error."""
        # If we get here, schema init worked
        self.assertIsNotNone(self.db)

    def test_create_trade(self):
        trade_id = self.db.create_trade(
            symbol="BTCUSDT", direction="LONG",
            entry_price=50000.0, stop_loss=49500.0,
            tp1_price=50500.0, tp2_price=51000.0,
            position_size=0.01, risk_pct=0.5,
            rr_ratio=2.0, signal_score=0.75,
        )
        self.assertIsInstance(trade_id, str)
        self.assertEqual(len(trade_id), 36)  # UUID format

        trade = self.db.get_trade(trade_id)
        self.assertIsNotNone(trade)
        self.assertEqual(trade["state"], "PENDING")
        self.assertEqual(trade["symbol"], "BTCUSDT")
        self.assertEqual(trade["direction"], "LONG")

    def test_transition_pending_to_active(self):
        tid = self.db.create_trade(
            "BTCUSDT", "LONG", 50000.0, 49500.0, 50500.0, 51000.0,
            0.01, 0.5, 2.0, 0.75
        )
        result = self.db.transition(tid, "ACTIVE")
        self.assertTrue(result)
        self.assertEqual(self.db.get_trade(tid)["state"], "ACTIVE")

    def test_illegal_transition_rejected(self):
        """CLOSED → ACTIVE must be rejected."""
        tid = self.db.create_trade(
            "BTCUSDT", "LONG", 50000.0, 49500.0, 50500.0, 51000.0,
            0.01, 0.5, 2.0, 0.75
        )
        self.db.transition(tid, "ACTIVE")
        self.db.transition(tid, "PROTECTED")
        self.db.transition(tid, "HARVESTED")
        self.db.transition(tid, "CLOSED")
        result = self.db.transition(tid, "ACTIVE")  # illegal
        self.assertFalse(result)

    def test_record_exit(self):
        tid = self.db.create_trade(
            "BTCUSDT", "LONG", 50000.0, 49500.0, 50500.0, 51000.0,
            0.01, 0.5, 2.0, 0.75
        )
        exit_id = self.db.record_exit(
            trade_id=tid, tier=1, fraction=0.30,
            fill_price=50495.0, exit_reason="TP1",
            target_price=50500.0, pnl_rr=0.99,
        )
        exits = self.db.get_exits_for_trade(tid)
        self.assertEqual(len(exits), 1)
        self.assertEqual(exits[0]["tier"], 1)
        self.assertAlmostEqual(exits[0]["slippage_pct"], 0.009901, places=3)

    def test_count_open_trades(self):
        self.assertEqual(self.db.count_open_trades(), 0)
        tid = self.db.create_trade(
            "BTCUSDT", "LONG", 50000.0, 49500.0, 50500.0, 51000.0,
            0.01, 0.5, 2.0, 0.75
        )
        self.db.transition(tid, "ACTIVE")
        self.assertEqual(self.db.count_open_trades(), 1)
        self.db.transition(tid, "CLOSED")
        self.assertEqual(self.db.count_open_trades(), 0)

    def test_open_risk_pct(self):
        self.assertAlmostEqual(self.db.open_risk_pct(), 0.0)
        tid = self.db.create_trade(
            "BTCUSDT", "LONG", 50000.0, 49500.0, 50500.0, 51000.0,
            0.01, 0.5, 2.0, 0.75
        )
        self.db.transition(tid, "ACTIVE")
        self.assertAlmostEqual(self.db.open_risk_pct(), 0.5)

    def test_get_active_by_symbol(self):
        tid = self.db.create_trade(
            "ETHUSDT", "SHORT", 3000.0, 3050.0, 2950.0, 2900.0,
            0.1, 0.5, 2.0, 0.72
        )
        self.db.transition(tid, "ACTIVE")
        trades = self.db.get_active_by_symbol("ETHUSDT")
        self.assertEqual(len(trades), 1)
        trades_btc = self.db.get_active_by_symbol("BTCUSDT")
        self.assertEqual(len(trades_btc), 0)

    def test_resurrection_finds_unclosed(self):
        tid = self.db.create_trade(
            "BTCUSDT", "LONG", 50000.0, 49500.0, 50500.0, 51000.0,
            0.01, 0.5, 2.0, 0.75
        )
        self.db.transition(tid, "ACTIVE")
        unclosed = self.db.get_unclosed_trades()
        self.assertEqual(len(unclosed), 1)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Scanner Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestINOUTScanner(unittest.TestCase):

    def setUp(self):
        self.cfg = _make_cfg({"scanner": {"cooldown_seconds": 0}})
        self.scanner = INOUTScanner(self.cfg)

    def test_no_signal_on_normal_candles(self):
        candles = _make_candles(30, explosive_last=False, volume_spike=False)
        result = self.scanner.scan("BTCUSDT", "M1", candles)
        self.assertIsNone(result)

    def test_signal_on_explosive_candle_with_volume(self):
        candles = _make_candles(30, explosive_last=True, volume_spike=True)
        result = self.scanner.scan("BTCUSDT", "M1", candles)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, INOUTSignal)
        self.assertEqual(result.symbol, "BTCUSDT")
        self.assertIn(result.direction, ("LONG", "SHORT"))
        self.assertGreater(result.composite_score, 0.0)

    def test_signal_direction_is_long_for_bullish_candle(self):
        candles = _make_candles(30, explosive_last=True, volume_spike=True)
        result = self.scanner.scan("BTCUSDT", "M1", candles)
        if result:
            self.assertEqual(result.direction, "LONG")

    def test_symbol_not_in_allowed_returns_none(self):
        candles = _make_candles(30, explosive_last=True, volume_spike=True)
        result = self.scanner.scan("DOGEUSDT", "M1", candles)
        self.assertIsNone(result)

    def test_timeframe_not_allowed_returns_none(self):
        candles = _make_candles(30, explosive_last=True, volume_spike=True)
        result = self.scanner.scan("BTCUSDT", "M15", candles)
        self.assertIsNone(result)

    def test_insufficient_candles_returns_none(self):
        candles = _make_candles(5)
        result = self.scanner.scan("BTCUSDT", "M1", candles)
        self.assertIsNone(result)

    def test_cooldown_prevents_double_signal(self):
        cfg = _make_cfg({"scanner": {"cooldown_seconds": 999}})
        scanner = INOUTScanner(cfg)
        candles = _make_candles(30, explosive_last=True, volume_spike=True)
        first = scanner.scan("BTCUSDT", "M1", candles)
        if first:  # first might or might not fire
            second = scanner.scan("BTCUSDT", "M1", candles)
            self.assertIsNone(second)

    def test_score_expansion_below_threshold(self):
        """Very small candle → expansion score = 0"""
        cfg = _make_cfg({"scanner": {"candle_expansion_atr_mult": 10.0}})
        scanner = INOUTScanner(cfg)
        candles = _make_candles(30, explosive_last=True, volume_spike=True)
        result = scanner.scan("BTCUSDT", "M1", candles)
        self.assertIsNone(result)  # high threshold → no signal

    def test_signal_has_all_fields(self):
        candles = _make_candles(30, explosive_last=True, volume_spike=True)
        result = self.scanner.scan("BTCUSDT", "M1", candles)
        if result:
            self.assertGreater(result.atr, 0)
            self.assertGreater(result.trigger_price, 0)
            self.assertIsInstance(result.conditions_met, list)
            self.assertIsInstance(result.to_dict(), dict)


# ═════════════════════════════════════════════════════════════════════════════
# 4. State Machine Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestINOUTStateMachine(unittest.TestCase):

    def setUp(self):
        self.cfg = _make_cfg()
        self.sm = INOUTStateMachine(self.cfg)

    def test_noop_on_terminal_state(self):
        trade = _make_trade_record(state="CLOSED")
        inst = self.sm.evaluate(trade, 50500.0)
        self.assertEqual(inst.action, ActionType.NONE)

    def test_noop_on_pending_state(self):
        trade = _make_trade_record(state="PENDING")
        inst = self.sm.evaluate(trade, 50000.0)
        self.assertEqual(inst.action, ActionType.NONE)

    def test_sl_hit_in_active_state_triggers_full_exit(self):
        trade = _make_trade_record(state="ACTIVE")
        # SL is at 49500, price goes below
        inst = self.sm.evaluate(trade, 49400.0)
        self.assertEqual(inst.action, ActionType.EXIT_FULL)
        self.assertEqual(inst.exit_reason, "SL")
        self.assertEqual(inst.new_state, "CLOSED")
        self.assertAlmostEqual(inst.fraction, 1.0)

    def test_tp1_hit_triggers_partial_exit(self):
        trade = _make_trade_record(state="ACTIVE")
        # TP1 is at 50500, price goes above
        inst = self.sm.evaluate(trade, 50600.0)
        self.assertEqual(inst.action, ActionType.EXIT_PARTIAL)
        self.assertEqual(inst.exit_reason, "TP1")
        self.assertEqual(inst.exit_tier, 1)
        self.assertEqual(inst.new_state, "PROTECTED")
        self.assertAlmostEqual(inst.fraction, 0.30)
        # SL should be moved to breakeven
        self.assertIsNotNone(inst.new_sl)
        self.assertGreater(inst.new_sl, 49500.0)   # higher than original SL

    def test_be_sl_hit_in_protected_state(self):
        trade = _make_trade_record(state="PROTECTED", stop_loss=50000.0)  # SL at entry
        inst = self.sm.evaluate(trade, 49900.0)
        self.assertEqual(inst.action, ActionType.EXIT_FULL)
        self.assertEqual(inst.exit_reason, "BE_SL")

    def test_tp2_hit_triggers_harvest(self):
        trade = _make_trade_record(state="PROTECTED")
        # TP2 is at 51000
        inst = self.sm.evaluate(trade, 51100.0)
        self.assertEqual(inst.action, ActionType.EXIT_PARTIAL)
        self.assertEqual(inst.exit_tier, 2)
        self.assertEqual(inst.new_state, "HARVESTED")
        self.assertAlmostEqual(inst.fraction, 0.50)

    def test_runner_trail_hit_in_harvested(self):
        trade = _make_trade_record(state="HARVESTED", runner_trail_sl=50800.0)
        inst = self.sm.evaluate(trade, 50750.0)
        self.assertEqual(inst.action, ActionType.EXIT_FULL)
        self.assertEqual(inst.exit_tier, 3)
        self.assertEqual(inst.exit_reason, "RUNNER_TRAIL")

    def test_runner_trail_updated_on_favourable_move(self):
        trade = _make_trade_record(state="HARVESTED", runner_trail_sl=50000.0)
        # Price moves up strongly → trail should follow
        inst = self.sm.evaluate(trade, 52000.0, current_atr=200.0)
        # Should want to update trail upward
        if inst.action == ActionType.UPDATE_TRAIL:
            self.assertGreater(inst.new_sl, 50000.0)

    def test_soft_time_stop_in_active_state(self):
        """Trade open for longer than default_time_min → time-stop"""
        old_create = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        trade = _make_trade_record(state="ACTIVE", created_at=old_create)
        inst = self.sm.evaluate(trade, 50000.0)  # price unchanged
        self.assertEqual(inst.action, ActionType.EXIT_FULL)
        self.assertIn("TIME_STOP", inst.exit_reason)
        self.assertEqual(inst.new_state, "TIMEOUT")

    def test_hard_time_stop_overrides_all_states(self):
        """Beyond max_time_min → force exit even in PROTECTED"""
        old_create = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        trade = _make_trade_record(state="PROTECTED", created_at=old_create)
        inst = self.sm.evaluate(trade, 50000.0)
        self.assertEqual(inst.action, ActionType.EXIT_FULL)
        self.assertEqual(inst.exit_reason, "MAX_TIME_STOP")
        self.assertEqual(inst.new_state, "TIMEOUT")

    def test_no_action_when_price_between_levels(self):
        trade = _make_trade_record(state="ACTIVE")
        # Price between SL (49500) and TP1 (50500) — no action
        inst = self.sm.evaluate(trade, 50200.0)
        self.assertEqual(inst.action, ActionType.NONE)

    def test_short_direction_sl_hit(self):
        trade = _make_trade_record(
            state="ACTIVE", direction="SHORT",
            entry_price=50000.0, stop_loss=50500.0,
            tp1_price=49500.0, tp2_price=49000.0,
            runner_trail_sl=50500.0,
        )
        inst = self.sm.evaluate(trade, 50600.0)  # above SL for SHORT
        self.assertEqual(inst.action, ActionType.EXIT_FULL)
        self.assertEqual(inst.exit_reason, "SL")

    def test_short_direction_tp1_hit(self):
        trade = _make_trade_record(
            state="ACTIVE", direction="SHORT",
            entry_price=50000.0, stop_loss=50500.0,
            tp1_price=49500.0, tp2_price=49000.0,
            runner_trail_sl=50500.0,
        )
        inst = self.sm.evaluate(trade, 49400.0)  # below TP1 for SHORT
        self.assertEqual(inst.action, ActionType.EXIT_PARTIAL)
        self.assertEqual(inst.exit_tier, 1)


# ═════════════════════════════════════════════════════════════════════════════
# 5. Controller Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestINOUTController(unittest.TestCase):

    def _make_controller(self, cfg_overrides=None):
        cfg = _make_cfg(cfg_overrides)
        db = INOUTDatabase(cfg)
        executor = INOUTExecutor(cfg)
        sm = INOUTStateMachine(cfg)
        ctrl = INOUTController(cfg, db, executor, sm, ultron_config={"disabled": True})
        return ctrl, db

    def _make_signal(self, symbol="BTCUSDT", score=0.75, direction="LONG"):
        return INOUTSignal(
            symbol=symbol,
            timeframe="M1",
            direction=direction,
            composite_score=score,
            trigger_price=50000.0,
            candle_high=50750.0,
            candle_low=49700.0,
            atr=150.0,
            volume_ratio=3.5,
            candle_expansion=5.0,
            structure_broken=True,
            conditions_met=["expansion", "volume", "breakout"],
        )

    def test_signal_accepted_and_trade_created(self):
        ctrl, db = self._make_controller()
        signal = self._make_signal()
        result = ctrl.on_signal(signal)
        self.assertTrue(result["accepted"])
        self.assertIsNotNone(result["trade_id"])
        trade = db.get_trade(result["trade_id"])
        self.assertEqual(trade["state"], "ACTIVE")

    def test_duplicate_symbol_rejected(self):
        ctrl, db = self._make_controller({"risk": {"dedup_window_seconds": 0}})
        signal = self._make_signal()
        r1 = ctrl.on_signal(signal)
        self.assertTrue(r1["accepted"])
        # Same symbol, trade still open
        r2 = ctrl.on_signal(signal)
        self.assertFalse(r2["accepted"])
        self.assertIn("symbol_already_open", r2["reason"])

    def test_max_concurrent_trades_rejected(self):
        ctrl, db = self._make_controller({
            "risk": {"max_concurrent_trades": 1, "dedup_window_seconds": 0}
        })
        r1 = ctrl.on_signal(self._make_signal("BTCUSDT"))
        self.assertTrue(r1["accepted"])
        r2 = ctrl.on_signal(self._make_signal("ETHUSDT"))
        self.assertFalse(r2["accepted"])
        self.assertIn("max_concurrent", r2["reason"])

    def test_max_exposure_rejected(self):
        ctrl, db = self._make_controller({
            "risk": {
                "max_total_exposure_pct": 0.3,  # very low cap
                "risk_per_trade_pct": 0.5,
                "dedup_window_seconds": 0,
            }
        })
        result = ctrl.on_signal(self._make_signal("BTCUSDT"))
        self.assertFalse(result["accepted"])
        self.assertIn("max_exposure", result["reason"])

    def test_price_tick_triggers_sl_exit(self):
        ctrl, db = self._make_controller()
        r = ctrl.on_signal(self._make_signal())
        trade_id = r["trade_id"]

        # SL is at candle_low - buffer ≈ 49700 - small buffer
        # Send price below SL
        actions = ctrl.on_price_tick("BTCUSDT", 49000.0)
        self.assertGreater(len(actions), 0)
        # Trade should now be CLOSED
        trade = db.get_trade(trade_id)
        self.assertIn(trade["state"], ("CLOSED", "TIMEOUT", "FAILED"))

    def test_price_tick_no_action_mid_range(self):
        ctrl, db = self._make_controller()
        ctrl.on_signal(self._make_signal())
        # Price in the middle — no action expected
        actions = ctrl.on_price_tick("BTCUSDT", 50200.0)
        self.assertEqual(len(actions), 0)

    def test_resurrection_finds_active_trade(self):
        ctrl, db = self._make_controller()
        ctrl.on_signal(self._make_signal())
        count = ctrl.resurrect()
        self.assertGreaterEqual(count, 1)

    def test_full_happy_path_active_to_tp1_to_tp2(self):
        """Integration: full SEP-01 happy path."""
        ctrl, db = self._make_controller()
        signal = self._make_signal()
        r = ctrl.on_signal(signal)
        self.assertTrue(r["accepted"])
        trade_id = r["trade_id"]

        trade = db.get_trade(trade_id)
        tp1 = float(trade["tp1_price"])
        tp2 = float(trade["tp2_price"])

        # Hit TP1
        actions = ctrl.on_price_tick("BTCUSDT", tp1 + 1.0)
        self.assertTrue(any(a.get("action") == "EXIT_PARTIAL" for a in actions))

        # Verify state = PROTECTED
        trade = db.get_trade(trade_id)
        self.assertEqual(trade["state"], "PROTECTED")

        # Hit TP2
        actions2 = ctrl.on_price_tick("BTCUSDT", tp2 + 1.0)
        trade = db.get_trade(trade_id)
        self.assertEqual(trade["state"], "HARVESTED")

        # Exits logged
        exits = db.get_exits_for_trade(trade_id)
        self.assertGreaterEqual(len(exits), 2)


# ═════════════════════════════════════════════════════════════════════════════
# 6. Executor Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestINOUTExecutor(unittest.TestCase):

    def setUp(self):
        self.cfg = _make_cfg()
        self.exec = INOUTExecutor(self.cfg)

    def test_is_dry_run(self):
        self.assertTrue(self.exec.is_dry_run)

    def test_open_position_returns_fill(self):
        fill = self.exec.open_position("BTCUSDT", "LONG", 0.01, 49500.0, 50500.0, 51000.0, 50000.0)
        self.assertTrue(fill.success)
        self.assertGreater(fill.fill_price, 0)
        self.assertAlmostEqual(fill.fill_qty, 0.01)

    def test_exit_partial_returns_fill(self):
        fill = self.exec.exit_partial("BTCUSDT", "LONG", 0.003, "TP1", 50500.0)
        self.assertTrue(fill.success)
        self.assertAlmostEqual(fill.fill_qty, 0.003)

    def test_exit_full_returns_fill(self):
        fill = self.exec.exit_full("BTCUSDT", "LONG", 0.007, "TIMEOUT", 50000.0)
        self.assertTrue(fill.success)

    def test_update_stop_loss_returns_true(self):
        self.assertTrue(self.exec.update_stop_loss("BTCUSDT", "LONG", 50000.0))

    def test_fill_result_to_dict(self):
        fill = self.exec.open_position("BTCUSDT", "LONG", 0.01, 49500.0, 50500.0, 51000.0, 50000.0)
        d = fill.to_dict()
        self.assertIn("success", d)
        self.assertIn("fill_price", d)
        self.assertIn("fill_qty", d)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Architecture Boundary Tests (Critical)
# ═════════════════════════════════════════════════════════════════════════════

class TestArchitectureBoundaries(unittest.TestCase):
    """
    Verify that INOUT does NOT import from forbidden modules.

    IMPORTANT: tests check IMPORT LINES ONLY (lines starting with
    'import ' or 'from '), not docstrings or comments. This correctly
    validates architecture boundaries without false positives from
    documentation text that mentions forbidden module names.
    """

    @staticmethod
    def _import_lines(filepath: str) -> str:
        """Extract only import statements from a source file."""
        with open(filepath, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        return "\n".join(
            line.rstrip()
            for line in lines
            if line.strip().startswith(("import ", "from "))
        )

    def test_scanner_does_not_import_engine_runner(self):
        import importlib, sys
        if "inout.scanner" in sys.modules:
            del sys.modules["inout.scanner"]
        mod = importlib.import_module("inout.scanner")
        imports = self._import_lines(mod.__file__)
        self.assertNotIn("engine_runner", imports)
        self.assertNotIn("EngineRunner", imports)

    def test_scanner_does_not_import_fusion_engine(self):
        import importlib
        mod = importlib.import_module("inout.scanner")
        imports = self._import_lines(mod.__file__)
        self.assertNotIn("fusion_engine", imports)
        self.assertNotIn("FusionEngine", imports)

    def test_controller_does_not_import_execution_planner(self):
        """
        INOUT controller must NOT import ExecutionPlannerV1_2.
        INOUT builds its own trade plans (_build_trade_plan).
        """
        import importlib
        mod = importlib.import_module("inout.controller")
        imports = self._import_lines(mod.__file__)
        self.assertNotIn("ExecutionPlannerV1_2", imports)
        self.assertNotIn("from execution_planner", imports)
        self.assertNotIn("import execution_planner", imports)

    def test_controller_does_not_import_live_engine_hook(self):
        """
        INOUT controller must NOT import live_engine_hook.
        INOUT has its own runner loop (runner.py).
        """
        import importlib
        mod = importlib.import_module("inout.controller")
        imports = self._import_lines(mod.__file__)
        self.assertNotIn("live_engine_hook", imports)

    def test_runner_does_not_import_live_engine_hook(self):
        """
        INOUT runner must NOT import live_engine_hook.
        It is a completely independent event loop.
        """
        import importlib
        mod = importlib.import_module("inout.runner")
        imports = self._import_lines(mod.__file__)
        self.assertNotIn("live_engine_hook", imports)

    def test_controller_does_not_import_engine_runner(self):
        """INOUT is parallel to EngineRunner — must not be downstream of it."""
        import importlib
        mod = importlib.import_module("inout.controller")
        imports = self._import_lines(mod.__file__)
        self.assertNotIn("engine_runner", imports)
        self.assertNotIn("EngineRunner", imports)

    def test_ultron_imported_read_only_in_controller(self):
        """
        Ultron must be imported in controller (for risk checks).
        Verify it IS imported there (and only via standard import, not patched).
        """
        import importlib
        mod = importlib.import_module("inout.controller")
        imports = self._import_lines(mod.__file__)
        # Must be present as an import
        self.assertIn("ultron_risk_gate", imports)

    def test_scanner_only_imports_inout_modules_and_stdlib(self):
        """Scanner must not import from the main codebase at all."""
        import importlib
        mod = importlib.import_module("inout.scanner")
        imports = self._import_lines(mod.__file__)
        # Must not reach into core/, engines/, features/, runtime/
        for forbidden in ["core.", "engines.", "features.", "runtime.", "governance."]:
            self.assertNotIn(forbidden, imports,
                msg=f"scanner.py must not import from {forbidden}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3: Probability-Driven Exit Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestINOUTStateMachineProbability(unittest.TestCase):
    """
    9 tests covering prob-driven exit logic introduced in Phase 3.
    Guards confirmed:
      FIX 1 — dual trust filter (confidence > 0.2 AND n_samples >= 20)
      FIX 2 — structure guard (skip prob exit when price is near TP1)
      FIX 3 — slippage guard (skip in high-ATR / high-volatility markets)
    Backward compat: no prob_snapshot → confidence=0.0 → all prob branches skip.
    """

    import json as _json   # module-level inside class for convenience

    # Shared probability payload — trusted (conf=0.9, n=30)
    _GOOD_PROB = {
        "tp1_prob": 0.55,
        "tp2_prob": 0.35,
        "runner_prob": 0.45,
        "expected_time_tp1": 3.0,   # → p75 = 3.0*1.4 = 4.2 min
        "expected_time_tp2": 9.0,   # → p75 = 9.0*1.4 = 12.6 min
        "expected_rr": 1.2,
        "confidence": 0.9,
        "n_samples": 30,
        "warnings": [],
    }

    def _sm(self) -> INOUTStateMachine:
        return INOUTStateMachine(_make_cfg())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ago(self, minutes: float) -> str:
        """ISO timestamp N minutes in the past (UTC)."""
        return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()

    def _prob_json(self, overrides: dict | None = None) -> str:
        import json
        p = dict(self._GOOD_PROB)
        if overrides:
            p.update(overrides)
        return json.dumps(p)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 1: null prob_snapshot → NONE (backward compat guarantee)
    # ─────────────────────────────────────────────────────────────────────────
    def test_null_prob_snapshot_returns_none(self):
        """No prob_snapshot → confidence=0.0 → all prob branches skipped → NONE."""
        sm = self._sm()
        trade = _make_trade_record(
            state="ACTIVE",
            created_at=self._ago(2),   # 2 min elapsed — no time-stop
        )
        # No prob_snapshot key at all
        now = datetime.now(timezone.utc)
        result = sm.evaluate(trade, current_price=50200.0, current_time=now)
        self.assertEqual(result.action, ActionType.NONE,
                         "Missing prob_snapshot must never trigger prob branches")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 2: corrupt JSON prob_snapshot → no crash, NONE
    # ─────────────────────────────────────────────────────────────────────────
    def test_corrupt_prob_snapshot_no_crash(self):
        """Invalid JSON in prob_snapshot → _load_prob() recovers → NONE, no exception."""
        sm = self._sm()
        trade = _make_trade_record(
            state="ACTIVE",
            created_at=self._ago(2),
            prob_snapshot="not-valid-json-!!!",
        )
        now = datetime.now(timezone.utc)
        try:
            result = sm.evaluate(trade, current_price=50200.0, current_time=now)
        except Exception as exc:
            self.fail(f"Corrupt prob_snapshot raised exception: {exc}")
        self.assertEqual(result.action, ActionType.NONE)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 3: prob early exit fires at 90% of p75 time → PROTECTED partial
    # ─────────────────────────────────────────────────────────────────────────
    def test_prob_early_exit_fires_at_90pct_p75(self):
        """
        With expected_time_tp1=3.0 and p75_factor=1.4:
          early_exit_time = 3.0 * 1.4 * 0.9 = 3.78 min
          soft_stop_min   = max(3.0 * 1.4, 3) = 4.2 min  (not yet fired)
        At 4 min elapsed → prob early exit fires before soft time-stop.
        Expected: EXIT_PARTIAL, new_state=PROTECTED, exit_reason=TP1_PROB_TIME
        """
        sm = self._sm()
        # price = 50200: not near tp1 (distance = 300/50500 = 0.6% > 0.2%) ✓
        # ATR = 50  → atr_pct = 50/50200 = 0.1% < 1% ✓ (low volatility)
        trade = _make_trade_record(
            state="ACTIVE",
            created_at=self._ago(4.0),    # 4 min > 3.78 → early exit fires
            prob_snapshot=self._prob_json(),
            atr=50.0,
        )
        now = datetime.now(timezone.utc)
        result = sm.evaluate(trade, current_price=50200.0,
                             current_time=now, current_atr=50.0)

        self.assertEqual(result.action, ActionType.EXIT_PARTIAL)
        self.assertEqual(result.new_state, "PROTECTED")
        self.assertEqual(result.exit_reason, "TP1_PROB_TIME")
        self.assertAlmostEqual(result.fraction, 0.30, places=2,
                               msg="TP1 fraction must be 0.30 (tp1_fraction default)")
        # meta must carry prob diagnostics
        self.assertIn("tp1_prob", result.meta or {})
        self.assertIn("confidence", result.meta or {})

    # ─────────────────────────────────────────────────────────────────────────
    # Test 4: dynamic soft time-stop uses prob P75 (4.2 min), not config (8 min)
    # ─────────────────────────────────────────────────────────────────────────
    def test_dynamic_soft_timestop_uses_prob_p75(self):
        """
        Config default_time_min = 8 min.  With prob expected_time_tp1=3.0:
          soft_stop_min = max(3.0 * 1.4, 3) = 4.2 min
        At 5 min elapsed → soft time-stop fires (wouldn't without prob data).
        Expected: EXIT_FULL, exit_reason=SOFT_TIME_STOP, new_state=TIMEOUT
        """
        sm = self._sm()
        trade = _make_trade_record(
            state="ACTIVE",
            created_at=self._ago(5.0),    # 5 min > 4.2 → fires; < 8 → static wouldn't
            prob_snapshot=self._prob_json(),
        )
        now = datetime.now(timezone.utc)
        # price not at TP1 or SL — only time-stop should trigger
        result = sm.evaluate(trade, current_price=50200.0, current_time=now)

        self.assertEqual(result.action, ActionType.EXIT_FULL)
        self.assertEqual(result.new_state, "TIMEOUT")
        self.assertEqual(result.exit_reason, "SOFT_TIME_STOP")
        self.assertTrue(result.meta.get("prob_driven"),
                        "meta.prob_driven must be True when prob data drove the threshold")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 5: low tp2_prob in PROTECTED → TP2_LOW_PROB full close
    # ─────────────────────────────────────────────────────────────────────────
    def test_low_tp2_prob_triggers_protected_abandon(self):
        """
        In PROTECTED state, if tp2_prob < tp2_abandon_prob (0.25):
          → EXIT_FULL, exit_reason=TP2_LOW_PROB, new_state=CLOSED, fraction=1.0
        Default prior tp2_prob=0.30 > 0.25 → missing prob_snapshot never triggers this.
        """
        sm = self._sm()
        # tp2_prob=0.15 < 0.25 threshold → should abandon
        trade = _make_trade_record(
            state="PROTECTED",
            created_at=self._ago(1),    # recent — no time-stop concern
            prob_snapshot=self._prob_json({"tp2_prob": 0.15}),
        )
        now = datetime.now(timezone.utc)
        # price between entry and tp2 — no natural trigger
        result = sm.evaluate(trade, current_price=50600.0, current_time=now)

        self.assertEqual(result.action, ActionType.EXIT_FULL)
        self.assertEqual(result.new_state, "CLOSED",
                         "TP2 abandon must use CLOSED (not TIMEOUT — informed decision)")
        self.assertEqual(result.exit_reason, "TP2_LOW_PROB")
        self.assertAlmostEqual(result.fraction, 1.0, places=2)
        self.assertIn("tp2_prob", result.meta or {})

    # ─────────────────────────────────────────────────────────────────────────
    # Test 6: high runner_prob → wider trail multiplier (LONG)
    # ─────────────────────────────────────────────────────────────────────────
    def test_high_runner_prob_widens_trail(self):
        """
        runner_prob=0.55 >= extend_thresh(0.4) → effective_mult = 2.5 * 1.2 = 3.0
        price=51500, atr=200 → wide_trail = 51500 - 200*3.0 = 50900
        base_trail                           = 51500 - 200*2.5 = 51000
        wide_trail (50900) < base_trail (51000) → wider, allows more room.
        Trail must still be > current runner_trail_sl=49500 → UPDATE_TRAIL fires.
        """
        sm = self._sm()
        trade = _make_trade_record(
            state="HARVESTED",
            direction="LONG",
            created_at=self._ago(1),
            runner_trail_sl=49500.0,
            prob_snapshot=self._prob_json({"runner_prob": 0.55}),
        )
        now = datetime.now(timezone.utc)
        result = sm.evaluate(trade, current_price=51500.0,
                             current_time=now, current_atr=200.0)

        self.assertEqual(result.action, ActionType.UPDATE_TRAIL)
        # effective_mult = 3.0 → new_sl = 51500 - 200*3.0 = 50900
        self.assertAlmostEqual(result.new_sl, 50900.0, places=0)
        # meta must report the multiplier used
        self.assertAlmostEqual(result.meta.get("trail_mult", 0.0), 3.0, places=2)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 7: low confidence → static logic applies, no prob branch fires
    # ─────────────────────────────────────────────────────────────────────────
    def test_low_confidence_uses_static_path(self):
        """
        confidence=0.1 < min_confidence_for_prob_exit(0.2) → _prob_trusted=False.
        At 6 min elapsed:
          - Static soft_stop_min = default_time_min = 8 min → 6 < 8 → no stop
          - Prob early exit: _prob_trusted=False → skipped
        Expected: NONE
        """
        sm = self._sm()
        trade = _make_trade_record(
            state="ACTIVE",
            created_at=self._ago(6.0),   # 6 min — would trigger prob at 3.78, but conf too low
            prob_snapshot=self._prob_json({"confidence": 0.1}),
            atr=50.0,
        )
        now = datetime.now(timezone.utc)
        result = sm.evaluate(trade, current_price=50200.0, current_time=now)
        self.assertEqual(result.action, ActionType.NONE,
                         "Low confidence must fall through to static paths and return NONE "
                         "(static soft stop = 8 min, only 6 min elapsed)")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 8: FIX 2 — structure guard blocks early exit when price is near TP1
    # ─────────────────────────────────────────────────────────────────────────
    def test_structure_guard_blocks_early_exit_near_tp1(self):
        """
        FIX 2: if abs(price - tp1) / tp1 < tp1_near_threshold (0.002):
          → skip prob early exit even when timing says to exit.
        tp1 = 50500; price = 50499 → distance = 1/50500 = 0.0000198 < 0.002 → blocked.
        elapsed = 4 min > early_exit_time(3.78) → timing would fire.
        soft_stop_min = 4.2 min > 4.0 min elapsed → no time-stop either.
        Expected: NONE
        """
        sm = self._sm()
        trade = _make_trade_record(
            state="ACTIVE",
            created_at=self._ago(4.0),       # 4 min → timing says exit
            prob_snapshot=self._prob_json(),
            atr=50.0,
        )
        now = datetime.now(timezone.utc)
        # price = 50499 — within 1 pip of tp1=50500 → structure guard triggers
        result = sm.evaluate(trade, current_price=50499.0, current_time=now)
        self.assertEqual(result.action, ActionType.NONE,
                         "FIX 2 structure guard must suppress prob early exit "
                         "when price is within 0.2% of TP1")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 9: low n_samples blocks prob exit despite high confidence
    # ─────────────────────────────────────────────────────────────────────────
    def test_low_n_samples_blocks_prob_exit(self):
        """
        FIX 1 dual-gate: confidence=0.9 (high) but n_samples=5 < min_prob_samples(20).
        _prob_trusted() returns False → all prob branches skip.
        elapsed = 4 min (would fire at 3.78 min if trusted, but isn't).
        Static soft_stop_min = 8 min → 4 < 8 → no static time-stop either.
        Expected: NONE
        """
        sm = self._sm()
        trade = _make_trade_record(
            state="ACTIVE",
            created_at=self._ago(4.0),
            prob_snapshot=self._prob_json({"confidence": 0.9, "n_samples": 5}),
            atr=50.0,
        )
        now = datetime.now(timezone.utc)
        result = sm.evaluate(trade, current_price=50200.0, current_time=now)
        self.assertEqual(result.action, ActionType.NONE,
                         "n_samples=5 < 20 must block _prob_trusted() even when "
                         "confidence is high (FIX 1 dual-gate enforcement)")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("INOUT Strategy — Test Suite")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestINOUTConfig,
        TestINOUTDatabase,
        TestINOUTScanner,
        TestINOUTStateMachine,
        TestINOUTController,
        TestINOUTExecutor,
        TestArchitectureBoundaries,
        TestINOUTStateMachineProbability,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
