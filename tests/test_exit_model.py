"""
test_exit_model.py — [trust-layer F2] governed intrabar exit model + dual-bound band.

Run: python -m pytest tests/test_exit_model.py -q
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_engine_v2 import CRTEngine, Direction
from runtime.exit_model_band import _band_from_models


def _cfg(exit_model: str = "intrabar_touch"):
    base = ConfigBuilder.build("BNBUSDT")
    return dataclasses.replace(base, exit_model=exit_model)


# ── intrabar trigger fires on a wick the close does not cross ────────────────
def test_intrabar_trigger_sl_on_wick():
    # LONG: SL=99. Bar low 98.5 touches SL intrabar, but close 100 does NOT cross it.
    trade = SimpleNamespace(direction=Direction.LONG, sl_price=99.0,
                            tp1_price=105.0, tp2_price=110.0, status="OPEN")
    candle = SimpleNamespace(high=101.0, low=98.5, close=100.0)
    # Intrabar model exits at the SL level; close-only (candle.close=100) would not.
    assert CRTEngine._intrabar_trigger_price(trade, candle) == 99.0


def test_intrabar_trigger_no_touch_returns_close():
    trade = SimpleNamespace(direction=Direction.LONG, sl_price=95.0,
                            tp1_price=110.0, tp2_price=120.0, status="OPEN")
    candle = SimpleNamespace(high=101.0, low=99.0, close=100.0)  # nothing touched
    assert CRTEngine._intrabar_trigger_price(trade, candle) == 100.0


# ── exit-model resolution precedence: arg > env > config > default ───────────
def test_exit_model_default_is_intrabar(monkeypatch):
    monkeypatch.delenv("TRUST_INTRABAR_TOUCH", raising=False)
    assert CRTEngine(_cfg("intrabar_touch"))._intrabar_exits is True


def test_exit_model_config_close_only(monkeypatch):
    monkeypatch.delenv("TRUST_INTRABAR_TOUCH", raising=False)
    assert CRTEngine(_cfg("close_only"))._intrabar_exits is False


def test_exit_model_explicit_arg_wins(monkeypatch):
    monkeypatch.setenv("TRUST_INTRABAR_TOUCH", "0")
    # explicit arg beats env and config
    assert CRTEngine(_cfg("close_only"), intrabar_exits=True)._intrabar_exits is True


def test_exit_model_env_overrides_config(monkeypatch):
    monkeypatch.setenv("TRUST_INTRABAR_TOUCH", "0")
    assert CRTEngine(_cfg("intrabar_touch"))._intrabar_exits is False
    monkeypatch.setenv("TRUST_INTRABAR_TOUCH", "1")
    assert CRTEngine(_cfg("close_only"))._intrabar_exits is True


# ── dual-bound band: structure + guarded inflation_ratio ─────────────────────
def _m(pf: float) -> dict:
    return {"pf": pf, "expectancy": 0.1, "win_rate": 0.5,
            "trade_count": 10, "max_drawdown": 0.1, "total_return": 0.05}


def test_band_full_metric_set_and_ratio():
    b = _band_from_models(_m(0.94), _m(0.46), "BNBUSDT")
    assert b["inflation_ratio"] == round(0.94 / 0.46, 4)
    assert b["inflation_ratio"] >= 1.0
    assert b["exit_model_governing"] == "intrabar_touch"
    for key in ("pf", "expectancy", "win_rate", "trade_count",
                "max_drawdown", "total_return"):
        assert f"{key}_close_only" in b and f"{key}_intrabar" in b


def test_band_inflation_ratio_guard_intrabar_zero():
    b = _band_from_models(_m(0.94), _m(0.0), "X")
    assert b["inflation_ratio"] is None
    assert b["note"] == "intrabar PF zero"


def test_band_inflation_ratio_guard_both_zero():
    b = _band_from_models(_m(0.0), _m(0.0), "X")
    assert b["inflation_ratio"] is None
    assert b["note"] == "both PF zero"
