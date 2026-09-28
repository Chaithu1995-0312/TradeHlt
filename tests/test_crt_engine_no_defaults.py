"""EPIC-84 A3a: CRT engine behaviour arguments have no defaults; Setup is strict."""
import json
from pathlib import Path

import pytest

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_engine_v2 import CRTEngine, ExecutionEngine, ResetLogic
from config_layer.setup import Setup
from config_layer.strict_config import ConfigKeyMissingError
from tests.helpers.crt_config import crt_config_for_test, crt_engine_for_test

REPO = Path(__file__).resolve().parents[1]
ACTIVE = (REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()


def test_constructors_require_behaviour_arguments():
    cfg = crt_config_for_test()
    with pytest.raises(TypeError):
        CRTEngine(cfg)
    with pytest.raises(TypeError):
        ExecutionEngine(cfg)
    with pytest.raises(TypeError):
        ResetLogic(cfg)


def test_from_production_uses_the_declared_setup():
    d = json.loads((REPO / "configs" / "production" / f"{ACTIVE}.json").read_text(encoding="utf-8"))
    e = CRTEngine.from_production(ConfigBuilder.from_production("XAUUSD"))
    assert e.executor.sl_anchor == d["backtest"]["sl_anchor"]
    assert e.reset_lg.htf_reset_exempt_sweep == d["backtest"]["htf_reset_exempt_sweep"]
    assert e.executor.target_policy == d["setup"]["target_policy"]
    assert e.trade_ttl_candles == d["setup"]["trade_ttl_candles"]
    assert e.decider == d["setup"]["decider"]


@pytest.mark.parametrize("section,key", [
    ("setup", "target_policy"), ("setup", "trade_ttl_candles"), ("setup", "decider"),
    ("backtest", "sl_anchor"), ("backtest", "session_window_basis"),
    ("backtest", "htf_reset_exempt_sweep"), ("crt_engine", "retrace_reset_pct"),
])
def test_setup_missing_key_fails_closed(monkeypatch, section, key):
    import config_layer.production_config as pc

    real = pc.get_prod_section

    def fake(name, version=None):
        sec = dict(real(name, version=version))
        if name == section:
            sec.pop(key)
        return sec

    monkeypatch.setattr(pc, "get_prod_section", fake)
    with pytest.raises(ConfigKeyMissingError) as ei:
        Setup.from_prod_config(ACTIVE)
    assert ei.value.missing == (key,)


def test_setup_exchange_local_requires_windows(monkeypatch):
    import config_layer.production_config as pc

    real = pc.get_prod_section

    def fake(name, version=None):
        sec = dict(real(name, version=version))
        if name == "backtest":
            sec["session_window_basis"] = "exchange_local"
            sec.pop("exchange_session_windows", None)
        return sec

    monkeypatch.setattr(pc, "get_prod_section", fake)
    with pytest.raises(ConfigKeyMissingError):
        Setup.from_prod_config(ACTIVE)


def test_journal_reports_none_before_first_retest():
    eng = crt_engine_for_test()
    snap = eng.get_live_metrics()
    for k in ("cached_displacement_retrace", "cached_body_ratio", "cached_session",
              "cached_double_sweep"):
        assert snap[k] is None
