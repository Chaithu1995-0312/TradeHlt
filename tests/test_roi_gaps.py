"""ROI gap implementation tests.

Covers:
- funnel_counts field exists in BacktestMetrics and to_dict (Step 1)
- TP3 CRTConfig fields + Trade.tp3_price default (Step 3)
- TP3 exit logic: hit detection, pnl math, status progression
- TP3 disabled by default: zero behavior change on existing flow
- frequency_boost_mode branch in _compute_base_score (Step 2)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import dataclasses
import importlib

import pytest

from runtime.backtest_v2 import BacktestMetrics
from config_layer.crt_engine_v2 import CRTConfig, Trade, Direction, ExecutionEngine


# ─────────────────────────────────────────────────────────────────
# Branch-lineage fencing (F-016). TP3 + frequency-boost are post-TP3 code-line
# features; on `patch` (active = v2_multi_2026_04) the supporting APIs are absent.
# These tests assert that other lineage — capability-probe skipif (NOT a silent hide)
# so a red means broken reality, not broken archaeology, and they auto-activate on the
# code line that actually has the feature.
# ─────────────────────────────────────────────────────────────────
_HAS_TP3 = "tp3_enabled" in {f.name for f in dataclasses.fields(CRTConfig)}
requires_tp3 = pytest.mark.skipif(
    not _HAS_TP3,
    reason="requires post-TP3 lineage: CRTConfig.tp3_enabled absent on the patch code line (F-016)",
)


def _has_freq_boost() -> bool:
    try:
        return hasattr(importlib.import_module("training.auto_tuner_multi"), "_FREQ_BOOST")
    except Exception:
        return False


requires_freq_boost = pytest.mark.skipif(
    not _has_freq_boost(),
    reason="requires post-TP3 lineage: auto_tuner_multi._FREQ_BOOST absent on the patch code line (F-016)",
)


# ─────────────────────────────────────────────────────────────────
# Step 1 — funnel_counts telemetry
# ─────────────────────────────────────────────────────────────────

def test_funnel_counts_field_exists():
    m = BacktestMetrics()
    assert isinstance(m.funnel_counts, dict)
    assert "funnel_counts" in m.to_dict()


def test_funnel_counts_populated_from_external_dict():
    m = BacktestMetrics()
    m.funnel_counts = {"RANGE": 1000, "SWEEP": 200, "DISPLACEMENT": 50}
    d = m.to_dict()
    assert d["funnel_counts"]["SWEEP"] == 200


# ─────────────────────────────────────────────────────────────────
# Step 3 — TP3 CRTConfig defaults
# ─────────────────────────────────────────────────────────────────

@requires_tp3
def test_crt_config_tp3_defaults_off():
    cfg = CRTConfig()
    assert cfg.tp3_enabled is False
    assert cfg.tp3_atr_multiplier == 3.0


@requires_tp3
def test_trade_tp3_price_default_zero():
    t = Trade(
        id="T1",
        direction=Direction.LONG,
        entry_price=100.0,
        sl_price=99.0,
        tp1_price=101.0,
        tp2_price=102.0,
    )
    assert t.tp3_price == 0.0


# ─────────────────────────────────────────────────────────────────
# Step 3 — TP3 exit logic via ExecutionEngine
# ─────────────────────────────────────────────────────────────────

def _make_executor(tp3_enabled: bool = False) -> ExecutionEngine:
    cfg = CRTConfig(tp3_enabled=tp3_enabled, tp3_atr_multiplier=3.0)
    return ExecutionEngine(cfg)


def _long_trade(tp3_price: float = 0.0) -> Trade:
    t = Trade(
        id="T1",
        direction=Direction.LONG,
        entry_price=100.0,
        sl_price=98.0,   # 2R risk distance
        tp1_price=102.0,  # +1R
        tp2_price=104.0,  # +2R
        tp3_price=tp3_price,
    )
    t.status = "OPEN"
    return t


@requires_tp3
def test_tp3_disabled_standard_tp2_close():
    """With tp3_enabled=False, TP2 still closes the runner normally."""
    ex = _make_executor(tp3_enabled=False)
    t = _long_trade()
    # Move to TP1 status first
    r1 = ex.update_trade(t, 102.1)
    assert r1 == "TP1"
    assert t.status == "TP1"
    # Hit TP2 — should fully close
    r2 = ex.update_trade(t, 104.1)
    assert r2 == "TP2"
    assert t.status == "TP2"


@requires_tp3
def test_tp3_enabled_tp2_is_partial():
    """With tp3_enabled=True, TP2 is a partial; runner continues to TP3."""
    ex = _make_executor(tp3_enabled=True)
    t = _long_trade(tp3_price=106.0)  # +3R
    # TP1 partial
    r1 = ex.update_trade(t, 102.1)
    assert r1 == "TP1"
    # TP2 partial — runner continues
    r2 = ex.update_trade(t, 104.1)
    assert r2 == "TP2"
    assert t.status == "TP2"   # runner still alive
    # TP3 full close
    r3 = ex.update_trade(t, 106.1)
    assert r3 == "TP3"
    assert t.status == "TP3"


@requires_tp3
def test_tp3_pnl_greater_than_tp2():
    """TP3 exit produces higher total PnL than standard TP2 exit on same trade."""
    ex2 = _make_executor(tp3_enabled=False)
    ex3 = _make_executor(tp3_enabled=True)

    t2 = _long_trade(tp3_price=0.0)
    t3 = _long_trade(tp3_price=106.0)

    # Standard TP2 run
    ex2.update_trade(t2, 102.1)  # TP1
    ex2.update_trade(t2, 104.1)  # TP2 close

    # TP3 run
    ex3.update_trade(t3, 102.1)  # TP1
    ex3.update_trade(t3, 104.1)  # TP2 partial
    ex3.update_trade(t3, 106.1)  # TP3 close

    assert t3.pnl > t2.pnl


@requires_tp3
def test_tp3_runner_sl_stops_at_tp1_level():
    """In TP3 mode, SL after TP2 partial should be at TP1 level — runner is protected."""
    ex = _make_executor(tp3_enabled=True)
    t = _long_trade(tp3_price=106.0)
    ex.update_trade(t, 102.1)  # TP1
    ex.update_trade(t, 104.1)  # TP2 partial
    # SL should now be at TP1 level (102.0) not entry
    assert t.sl_price == 102.0


@requires_tp3
def test_tp3_diverted_sl_gives_locked_pnl():
    """If price retreats after TP2 partial, SL stops at TP1 level locking partial PnL."""
    ex = _make_executor(tp3_enabled=True)
    t = _long_trade(tp3_price=106.0)
    ex.update_trade(t, 102.1)  # TP1
    ex.update_trade(t, 104.1)  # TP2 partial
    result = ex.update_trade(t, 101.9)  # SL hit at TP1 level (102.0)
    assert result == "STOPPED"
    # partial_pnl should be > 0 (both TP1 + TP2 partials are locked)
    assert t.pnl > 0


# ─────────────────────────────────────────────────────────────────
# Step 2 — frequency_boost_mode in _compute_base_score
# ─────────────────────────────────────────────────────────────────

@requires_freq_boost
def test_frequency_boost_mode_disabled_by_default():
    """_FREQ_BOOST is False by default in module scope."""
    import training.auto_tuner_multi as _atm
    # If not patched, the production config has frequency_boost_mode=false
    assert _atm._FREQ_BOOST is False


@requires_freq_boost
def test_frequency_boost_mode_up_weights_trade_count(monkeypatch):
    import training.auto_tuner_multi as _atm
    monkeypatch.setattr(_atm, "_FREQ_BOOST", True)
    monkeypatch.setattr(_atm, "_FREQ_BOOST_FW", {
        "expectancy_rr": 0.3, "win_rate": 0.15, "trade_count_norm": 0.45, "drawdown": 0.10,
    })
    monkeypatch.setattr(_atm, "_FREQ_BOOST_MIN_EXP", 0.10)
    monkeypatch.setattr(_atm, "TRADE_COUNT_FLOOR", 3)
    monkeypatch.setattr(_atm, "TRADE_COUNT_TARGET", 30)

    # High-freq, low-expectancy above floor: should NOT be rejected
    score_hf = _atm._compute_base_score({
        "approved_trades": 25, "win_rate": 0.5, "expectancy_rr": 0.15,
        "max_drawdown_pct": 0.05, "expansions": 10, "retests": 2,
    })
    assert score_hf > 0.0

    # Low expectancy (below floor): rejected
    score_low = _atm._compute_base_score({
        "approved_trades": 25, "win_rate": 0.5, "expectancy_rr": 0.05,
        "max_drawdown_pct": 0.05, "expansions": 10, "retests": 2,
    })
    assert score_low == -999.0


@requires_freq_boost
def test_frequency_boost_mode_off_ignores_floor(monkeypatch):
    import training.auto_tuner_multi as _atm
    monkeypatch.setattr(_atm, "_FREQ_BOOST", False)
    monkeypatch.setattr(_atm, "TRADE_COUNT_FLOOR", 3)
    monkeypatch.setattr(_atm, "TRADE_COUNT_TARGET", 50)

    # Standard mode: low expectancy is allowed (not rejected by floor)
    score = _atm._compute_base_score({
        "approved_trades": 10, "win_rate": 0.5, "expectancy_rr": 0.05,
        "max_drawdown_pct": 0.05, "expansions": 10, "retests": 2,
    })
    assert score != -999.0
