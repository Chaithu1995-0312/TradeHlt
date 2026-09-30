"""EPIC-84 STORY-84.4: every runtime default removed has a missing-key test."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer import production_config as pc  # noqa: E402
from config_layer.strict_config import ConfigKeyMissingError  # noqa: E402

_KW = dict(scorer_mode="calibrated", allow_router_crt_config=False, strategy_id="")


def _patch_sections(monkeypatch, *, drop_backtest=(), drop_setup=(), drop_parent=()):
    real_sec, real_full = pc.get_prod_section, pc.get_full_config_dict

    def _sec(name, *a, **kw):
        sec = copy.deepcopy(real_sec(name, *a, **kw))
        drop = {"backtest": drop_backtest, "parent_crt": drop_parent}.get(name, ())
        for k in drop:
            sec.pop(k)
        return sec

    def _full(*a, **kw):
        cfg = copy.deepcopy(real_full(*a, **kw))
        for k in drop_setup:
            cfg["setup"].pop(k)
        return cfg

    monkeypatch.setattr(pc, "get_prod_section", _sec)
    monkeypatch.setattr(pc, "get_full_config_dict", _full)


def test_backtest_config_builds_from_active_config():
    from runtime.backtest_v2 import BacktestConfig
    cfg = BacktestConfig.from_prod_config("XAUUSD", 0.01, **_KW)
    assert cfg.timeframe == "M15"
    assert (cfg.sl_anchor, cfg.decider, cfg.target_policy) == ("displacement", "engine", "fixed_r")


@pytest.mark.parametrize("key", [
    "htf_clock_basis", "htf_reset_exempt_sweep", "sl_anchor", "session_window_basis", "timeframe",
])
def test_backtest_key_required(monkeypatch, key):
    from runtime.backtest_v2 import BacktestConfig
    _patch_sections(monkeypatch, drop_backtest=(key,))
    with pytest.raises(ConfigKeyMissingError, match=key):
        BacktestConfig.from_prod_config("XAUUSD", 0.01, **_KW)


@pytest.mark.parametrize("key", ["target_policy", "trade_ttl_candles", "decider"])
def test_setup_key_required(monkeypatch, key):
    from runtime.backtest_v2 import BacktestConfig
    _patch_sections(monkeypatch, drop_setup=(key,))
    with pytest.raises(ConfigKeyMissingError, match=key):
        BacktestConfig.from_prod_config("XAUUSD", 0.01, **_KW)


@pytest.mark.parametrize("missing", ["instrument", "pip_size", "scorer_mode",
                                     "allow_router_crt_config", "strategy_id"])
def test_instance_args_required(missing):
    from runtime.backtest_v2 import BacktestConfig
    kw = dict(instrument="XAUUSD", pip_size=0.01, **_KW)
    kw.pop(missing)
    with pytest.raises(TypeError):
        BacktestConfig.from_prod_config(**kw)


def test_empty_instrument_refused():
    from runtime.backtest_v2 import BacktestConfig
    with pytest.raises(ValueError, match="instrument"):
        BacktestConfig.from_prod_config("", 0.01, **_KW)


def test_parent_crt_enabled_required(monkeypatch, tmp_path):
    import logging
    from runtime.backtest_v2 import BacktestConfig, _validate_htf_clock
    cfg = BacktestConfig.from_prod_config("XAUUSD", 0.01, **_KW)
    _patch_sections(monkeypatch, drop_parent=("enabled",))
    with pytest.raises(ConfigKeyMissingError, match="enabled"):
        _validate_htf_clock(cfg, str(tmp_path / "x.csv"), logging.getLogger("t"))


def test_live_hook_tp_multiplier_declared_passes():
    from runtime.live_engine_hook import _tp_multiplier_reject
    crt = {"tp1_atr_multiplier_reversal": 1.0, "tp2_atr_multiplier": 2.0}
    assert _tp_multiplier_reject(crt, "REVERSAL", "e1") is None


@pytest.mark.parametrize("intent,crt,reason", [
    ("CONTINUATION", {"tp1_atr_multiplier": 1.0, "tp2_atr_multiplier": 2.0},
     "config_key_missing:crt_engine.tp1_atr_multiplier_continuation"),
    ("REVERSAL", {"tp1_atr_multiplier_reversal": 1.0},
     "config_key_missing:crt_engine.tp2_atr_multiplier"),
])
def test_live_hook_undeclared_tp_multiplier_rejects_trade(intent, crt, reason):
    from runtime.live_engine_hook import _tp_multiplier_reject
    res = _tp_multiplier_reject(crt, intent, "e1")
    assert res["decision"] == "reject"
    assert res["risk_reason"] == reason
    assert res["final_position_size"] == 0.0


@pytest.mark.parametrize("section,consumer_mod,func_name", [
    ("params", "runtime.unified_replay_harness", "_build_backtest_v2_config"),
])
def test_unified_replay_requires_params(section, consumer_mod, func_name):
    import importlib
    fn = getattr(importlib.import_module(consumer_mod), func_name)
    with pytest.raises(ConfigKeyMissingError, match=section):
        fn({}, "XAUUSD")
