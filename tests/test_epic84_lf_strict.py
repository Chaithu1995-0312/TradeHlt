"""EPIC-84 L-F: missing config keys raise, they do not fall back to literals."""
from __future__ import annotations

import pytest

from agent.groq_client import GroqClient, _GROQ_KEYS
from bitnet.composition import build_synthetic_bitlinear_envelope, load_bitlinear_composition
from config_layer.strict_config import ConfigKeyMissingError
from portfolio.correlation_engine import CorrelationEngine
from strategies.strategy_orchestrator import StrategyOrchestrator, _ORCH_KEYS


def _groq_cfg() -> dict:
    cfg = {
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.1-70b-versatile",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "request_timeout_s": 8.0,
        "max_tokens": 1024,
        "fail_count_disable": 5,
        "temperature": 0.1,
        "_redact_patterns": ("api_key",),
    }
    return cfg


@pytest.mark.parametrize("key", list(_GROQ_KEYS))
def test_groq_client_missing_key_raises(key):
    cfg = _groq_cfg()
    del cfg[key]
    with pytest.raises(ConfigKeyMissingError) as exc:
        GroqClient(cfg)
    assert key in exc.value.missing
    assert f"agent.groq.{key}" in str(exc.value)


def test_groq_client_missing_redact_patterns_raises():
    cfg = _groq_cfg()
    del cfg["_redact_patterns"]
    with pytest.raises(ConfigKeyMissingError) as exc:
        GroqClient(cfg)
    assert "redact_patterns" in exc.value.missing


_CORR = {
    "lookback_days": 20,
    "cache_ttl_secs": 3600,
    "min_observations": 10,
    "max_staleness_days": 3,
}


@pytest.mark.parametrize("key", list(_CORR))
def test_correlation_missing_key_raises(key):
    section = dict(_CORR)
    del section[key]
    with pytest.raises(ConfigKeyMissingError) as exc:
        CorrelationEngine(config={"correlation": section}, fetcher=object())
    assert key in exc.value.missing
    assert f"portfolio.correlation.{key}" in str(exc.value)


def _orch() -> dict:
    return {
        "fail_open": True,
        "min_signal_strategies": 2,
        "min_agreement_ratio": 0.60,
        "weights": {},
        "enabled_strategies": [],
    }


@pytest.mark.parametrize("key", list(_ORCH_KEYS))
def test_orchestrator_missing_key_raises(key):
    cfg = _orch()
    del cfg[key]
    with pytest.raises(ConfigKeyMissingError) as exc:
        StrategyOrchestrator("EURUSD", "M15", config=cfg)
    assert key in exc.value.missing
    assert f"strategy_orchestrator.{key}" in str(exc.value)


def test_bitlinear_envelope_missing_feature_order_hash_raises():
    env = build_synthetic_bitlinear_envelope(input_dim=4, feature_names=["a", "b", "c", "d"])
    del env["encoder"]["feature_order_hash"]
    with pytest.raises(ConfigKeyMissingError) as exc:
        load_bitlinear_composition(env)
    assert "feature_order_hash" in exc.value.missing


def test_bitlinear_envelope_missing_defaults_profile_raises():
    env = build_synthetic_bitlinear_envelope(input_dim=4, feature_names=["a", "b", "c", "d"])
    del env["backbone"]["defaults_profile"]
    with pytest.raises(ConfigKeyMissingError) as exc:
        load_bitlinear_composition(env)
    assert "defaults_profile" in exc.value.missing


def _probe_cls(bs):
    class _Probe(bs.BaseStrategy):
        @property
        def strategy_id(self) -> str:
            return "PROBE"

        def compute(self, features, candle):  # noqa: ANN001
            raise NotImplementedError

    return _Probe


def test_unknown_pair_pip_value_missing_raises(monkeypatch):
    import strategies.base_strategy as bs
    monkeypatch.setattr(bs, "_PIP_VALUE_PER_LOT", {})
    monkeypatch.setattr(bs, "_CAPITAL_CFG", {"total_capital_inr": 1})
    with pytest.raises(ConfigKeyMissingError) as exc:
        _probe_cls(bs)("XAUUSD", "M15")
    assert "unknown_pair_pip_value" in exc.value.missing
    assert "capital_management.unknown_pair_pip_value" in str(exc.value)


def test_unknown_pair_pip_value_declared_is_used(monkeypatch):
    import strategies.base_strategy as bs
    monkeypatch.setattr(bs, "_PIP_VALUE_PER_LOT", {})
    monkeypatch.setattr(bs, "_CAPITAL_CFG", {"unknown_pair_pip_value": 10.0})
    strat = _probe_cls(bs)("XAUUSD", "M15")
    assert strat._pip_value == 10.0


_TRIGGER = {
    "min_new_samples": 500,
    "drift_window_hours": 24,
    "drift_event_threshold": 5,
    "cooldown_hours": 6.0,
    "marker_path": "results/training_trigger.json",
    "opportunity_glob": "logs/**/opportunities.jsonl",
    "integrity_log": "logs/integrity_events.jsonl",
    "drift_event_kinds": ["RR_BYPASS", "RR_LLM_FALLBACK", "PROMOTION_FAILED"],
}


@pytest.mark.parametrize("key", list(_TRIGGER))
def test_training_trigger_missing_key_raises(key):
    from training.training_trigger import TrainingTriggerConfig
    section = dict(_TRIGGER)
    del section[key]
    with pytest.raises(ConfigKeyMissingError) as exc:
        TrainingTriggerConfig.from_section(section)
    assert key in exc.value.missing
    assert f"training_trigger.{key}" in str(exc.value)


_KILL = {
    "daily_loss_limit_inr": 10000.0,
    "weekly_loss_limit_inr": 25000.0,
    "state_file": "logs/kill_switch_state.json",
}


@pytest.mark.parametrize("key", list(_KILL))
def test_kill_switch_missing_key_raises(monkeypatch, key):
    import uat.kill_switch as ks
    section = {"kill_switch": dict(_KILL)}
    del section["kill_switch"][key]
    monkeypatch.setattr(ks, "get_prod_section", lambda _name: section)
    with pytest.raises(ConfigKeyMissingError) as exc:
        ks.KillSwitch.from_prod_config()
    assert key in exc.value.missing
    assert f"uat.kill_switch.{key}" in str(exc.value)


_MC = {
    "n_simulations": 1000,
    "initial_capital_inr": 100000.0,
    "ruin_threshold_pct": 0.5,
    "random_seed": 42,
}


@pytest.mark.parametrize("key", list(_MC))
def test_monte_carlo_missing_key_raises(monkeypatch, key):
    import uat.monte_carlo as mc
    section = {"monte_carlo": dict(_MC)}
    del section["monte_carlo"][key]
    monkeypatch.setattr(mc, "get_prod_section", lambda _name: section)
    with pytest.raises(ConfigKeyMissingError) as exc:
        mc.MonteCarloEngine.from_prod_config()
    assert key in exc.value.missing
    assert f"uat.monte_carlo.{key}" in str(exc.value)


def test_retrieval_config_zero_arg_raises():
    from retrieval.config import RetrievalConfig, build_default_config
    with pytest.raises(TypeError):
        RetrievalConfig()
    cfg = build_default_config()
    assert cfg.short_chunk_max_tokens == 8
    assert cfg.candidate_n == 600
    assert cfg.file_agg_boost == 0.35


_STRATS = (
    ("strategies.s01_crt_wrapper", "S01CRTWrapper", "_S01CRTWrapper_KEYS"),
    ("strategies.s02_mean_reversion", "S02MeanReversion", "_S02MeanReversion_KEYS"),
    ("strategies.s03_breakout", "S03Breakout", "_S03Breakout_KEYS"),
    ("strategies.s04_stat_arb", "S04StatArb", "_S04StatArb_KEYS"),
    ("strategies.s05_grid", "S05Grid", "_S05Grid_KEYS"),
    ("strategies.s06_scalping", "S06Scalping", "_S06Scalping_KEYS"),
    ("strategies.s07_news_sentiment", "S07NewsSentiment", "_S07NewsSentiment_KEYS"),
    ("strategies.s08_ml_ensemble", "S08MLEnsemble", "_S08MLEnsemble_KEYS"),
    ("strategies.s09_pattern_recog", "S09PatternRecog", "_S09PatternRecog_KEYS"),
    ("strategies.s10_trap_strategy", "S10TrapStrategy", "_S10TrapStrategy_KEYS"),
)


def _strategy_cases():
    import importlib
    cases = []
    for mod_name, cls_name, keys_name in _STRATS:
        mod = importlib.import_module(mod_name)
        for key in getattr(mod, keys_name):
            cases.append((mod_name, cls_name, keys_name, key))
    return cases


@pytest.mark.parametrize("mod_name,cls_name,keys_name,key", _strategy_cases())
def test_strategy_missing_key_raises(mod_name, cls_name, keys_name, key):
    import importlib
    mod = importlib.import_module(mod_name)
    cfg = {name: 1 for name in getattr(mod, keys_name)}
    del cfg[key]
    with pytest.raises(ConfigKeyMissingError) as exc:
        getattr(mod, cls_name)("EURUSD", "M15", config=cfg)
    assert key in exc.value.missing
    assert "strategy_engine." in str(exc.value)
