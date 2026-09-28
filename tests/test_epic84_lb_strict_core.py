"""EPIC-84 L-B STORY-84.2 — strict config reads in src/core (no literal defaults).

For every touched class: removing each required key raises ConfigKeyMissingError naming it.
Per-trade missing values (UltronRiskGate / EngineRunner direction) are REJECT tests in
tests/test_ultron_risk_gate.py, tests/test_ultron_wrapper.py and
tests/test_engine_runner_dual_gate.py.

Fixture values below are the values that run today on the active config
v2_htfcrt_2026_08 (plus the declared defaults listed in the L-B DECLARATIONS table).
"""
from __future__ import annotations

import pytest

import config_layer.production_config as _pc
from config_layer.strict_config import ConfigKeyMissingError

# ── fixtures: complete sections ───────────────────────────────────────────────

DECISION_CFG = {
    "score_threshold": 0.45,
    "p_win_threshold": 0.4,
    "weak_link_weight": 0.3,
    "weak_component_threshold": 0.4,
    "threshold_percentile": 85,
    "threshold_min": 0.45,
    "threshold_max": 0.65,
    "threshold_window": 1000,
    "fallback_top_n": 3,
}

ACCEPTANCE_SECTION = {
    "theta_min": 0.5,
    "theta_max": 0.95,
    "min_history": 10,
    "fusion_percentile": 85,
    "acceptance_alpha": 0.01,
    "acceptance_target_low": 0.05,
    "acceptance_target_high": 0.15,
    "acceptance_k_sigma": 1.0,
    "acceptance_window": 200,
    "engine_threshold": 0.60,
    "fusion_threshold": 0.65,
}
ACCEPTANCE_CFG = {**ACCEPTANCE_SECTION, "score_threshold": 0.45}

REGIME_FUSION_WEIGHTS = {
    "TRENDING": {"crt": 0.38, "gaussian": 0.20, "zone_gate": 0.12, "rr": 0.20, "strategy_consensus": 0.10},
    "RANGING":  {"crt": 0.18, "gaussian": 0.32, "zone_gate": 0.15, "rr": 0.25, "strategy_consensus": 0.10},
    "VOLATILE": {"crt": 0.28, "gaussian": 0.14, "zone_gate": 0.12, "rr": 0.16, "strategy_consensus": 0.30},
    "UNKNOWN":  {"crt": 0.30, "gaussian": 0.25, "zone_gate": 0.25, "rr": 0.20, "strategy_consensus": 0.00},
}
FUSION_SECTION = {
    "gaussian_weight": 0.6, "neural_weight": 0.4, "llm_weight": 0.2,
    "llm_lower_band": 0.45, "llm_upper_band": 0.65, "enable_llm": True,
    "tier_full": 0.75, "tier_half": 0.6, "tier_quarter": 0.5,
    "weight_crt": 0.4, "weight_gaussian": 0.2, "weight_zone_gate": 0.2, "weight_rr": 0.2,
    "weight_strategy_consensus": 0.0,
    "regime_fusion_weights": REGIME_FUSION_WEIGHTS,
    "min_consensus_signals": 2, "min_consensus_agreement": 0.6,
    "conflict_resolution_policy": "conservative",
}

BELIEF_SECTION = {"enabled": False, "decay": 0.7, "high_conviction_threshold": 0.65,
                  "min_confirmations": 2}


def _drop(d: dict, key: str) -> dict:
    return {k: v for k, v in d.items() if k != key}


def _assert_names(exc: ConfigKeyMissingError, key: str, section: str) -> None:
    assert key in exc.missing
    assert exc.section == section
    assert f"{section}.{key}" in str(exc)


# ── DecisionEngine ────────────────────────────────────────────────────────────

def test_decision_engine_complete_config_constructs():
    from core.decision_engine import DecisionEngine
    de = DecisionEngine(config=dict(DECISION_CFG))
    assert de._fallback_n == 3
    assert de._dynamic_threshold is not None


@pytest.mark.parametrize("key", DECISION_CFG.keys())
def test_decision_engine_missing_key_raises(key):
    from core.decision_engine import DecisionEngine
    with pytest.raises(ConfigKeyMissingError) as ei:
        DecisionEngine(config=_drop(DECISION_CFG, key))
    _assert_names(ei.value, key, "decision_engine")


def test_decision_engine_fallback_n_arg_still_overrides_config():
    from core.decision_engine import DecisionEngine
    assert DecisionEngine(config=dict(DECISION_CFG), fallback_n=2)._fallback_n == 2


# ── AcceptanceController ──────────────────────────────────────────────────────

def test_acceptance_controller_complete_config():
    from core.acceptance_controller import AcceptanceController
    c = AcceptanceController(dict(ACCEPTANCE_CFG))
    assert c.get_thresholds() == {"score_threshold": 0.45, "engine_threshold": 0.60,
                                  "fusion_threshold": 0.65}


@pytest.mark.parametrize("key", ACCEPTANCE_CFG.keys())
def test_acceptance_controller_missing_key_raises(key):
    from core.acceptance_controller import AcceptanceController
    with pytest.raises(ConfigKeyMissingError) as ei:
        AcceptanceController(_drop(ACCEPTANCE_CFG, key))
    _assert_names(ei.value, key, "acceptance_controller")


def test_acceptance_controller_no_config_raises():
    from core.acceptance_controller import AcceptanceController
    with pytest.raises(ConfigKeyMissingError):
        AcceptanceController(None)


@pytest.mark.parametrize("key", ACCEPTANCE_SECTION.keys())
def test_acceptance_from_prod_config_missing_section_key_raises(monkeypatch, key):
    from core.acceptance_controller import AcceptanceController
    monkeypatch.setattr(_pc, "get_prod_section",
                        lambda name, *a, **k: _drop(ACCEPTANCE_SECTION, key))
    with pytest.raises(ConfigKeyMissingError) as ei:
        AcceptanceController.from_prod_config({"score_threshold": 0.45})
    _assert_names(ei.value, key, "acceptance_controller")


# ── FusionConfig / FusionEngine ───────────────────────────────────────────────

def test_fusion_config_from_section_values_unchanged():
    from core.fusion_engine import FusionConfig
    cfg = FusionConfig.from_section(dict(FUSION_SECTION))
    assert cfg.weight_crt == 0.4 and cfg.weight_strategy_consensus == 0.0
    assert cfg.regime_fusion_weights == REGIME_FUSION_WEIGHTS
    assert set(FusionConfig.REQUIRED_KEYS) == set(FUSION_SECTION)


@pytest.mark.parametrize("key", FUSION_SECTION.keys())
def test_fusion_config_missing_key_raises(key):
    from core.fusion_engine import FusionConfig
    with pytest.raises(ConfigKeyMissingError) as ei:
        FusionConfig.from_section(_drop(FUSION_SECTION, key))
    _assert_names(ei.value, key, "fusion_engine")


def test_fusion_config_has_no_field_defaults():
    """Rewritten default test: FusionConfig() no longer yields a default config."""
    from core.fusion_engine import FusionConfig
    with pytest.raises(TypeError):
        FusionConfig()  # type: ignore[call-arg]


def test_fusion_engine_without_config_raises():
    from core.fusion_engine import FusionEngine
    with pytest.raises(ConfigKeyMissingError) as ei:
        FusionEngine(gaussian_adapter=None)
    assert ei.value.section == "fusion_engine"


# ── SignalBeliefTracker / BeliefRegistry ──────────────────────────────────────

@pytest.mark.parametrize("key", ["decay", "high_conviction_threshold", "min_confirmations"])
def test_signal_belief_tracker_missing_key_raises(key):
    from core.signal_belief_tracker import SignalBeliefTracker
    with pytest.raises(ConfigKeyMissingError) as ei:
        SignalBeliefTracker(_drop(BELIEF_SECTION, key))
    _assert_names(ei.value, key, "engine_runner.signal_belief")


@pytest.mark.parametrize("key", BELIEF_SECTION.keys())
def test_belief_registry_missing_key_raises_on_get(key):
    from core.signal_belief_tracker import BeliefRegistry
    reg = BeliefRegistry(_drop(BELIEF_SECTION, key))  # construction is lazy by design
    with pytest.raises(ConfigKeyMissingError) as ei:
        reg.get("XAUUSD", "M15")
    _assert_names(ei.value, key, "engine_runner.signal_belief")


@pytest.mark.parametrize("key", ["decay", "high_conviction_threshold", "min_confirmations"])
def test_signal_belief_from_prod_config_missing_key_raises(monkeypatch, key):
    from core.signal_belief_tracker import SignalBeliefTracker
    monkeypatch.setattr(_pc, "get_prod_section",
                        lambda name, *a, **k: {"signal_belief": _drop(BELIEF_SECTION, key)})
    with pytest.raises(ConfigKeyMissingError) as ei:
        SignalBeliefTracker.from_prod_config()
    _assert_names(ei.value, key, "engine_runner.signal_belief")


def test_signal_belief_from_prod_config_missing_section_raises(monkeypatch):
    from core.signal_belief_tracker import SignalBeliefTracker
    monkeypatch.setattr(_pc, "get_prod_section", lambda name, *a, **k: {})
    with pytest.raises(ConfigKeyMissingError) as ei:
        SignalBeliefTracker.from_prod_config()
    assert "signal_belief" in ei.value.missing


# ── EngineRunner (construction-time keys) ─────────────────────────────────────

def _engine_runner_keys():
    from core.engine_runner import _ENGINE_RUNNER_REQUIRED_KEYS
    return _ENGINE_RUNNER_REQUIRED_KEYS


@pytest.mark.parametrize("key", [
    "gaussian_impl", "rr_fusion", "convergence_window", "fusion_engine", "dual_engine",
    "fusion_use_evaluate", "fusion_compare_evaluate", "zone_registry_path", "zone_min_samples",
    "zone_gate", "zone_cluster_threshold", "zone_gate_execution_mode", "zone_mode",
    "debug_mode", "ultron_gate_enabled", "signal_belief", "cognitive_layer",
])
def test_engine_runner_missing_key_raises(key):
    from core.engine_runner import EngineRunner
    assert key in _engine_runner_keys()
    cfg = {k: object() for k in _engine_runner_keys() if k != key}
    with pytest.raises(ConfigKeyMissingError) as ei:
        EngineRunner(cfg)
    assert ei.value.missing == (key,)
    _assert_names(ei.value, key, "engine_runner")


def test_engine_runner_gaussian_impl_has_no_default():
    """Rewritten: gaussian_impl absent no longer means 'heuristic'."""
    from core.engine_runner import EngineRunner
    with pytest.raises(ConfigKeyMissingError):
        EngineRunner._get_gaussian_engine({})
    with pytest.raises(ConfigKeyMissingError):
        EngineRunner._get_shadow_gaussian_engine({})


def test_engine_runner_weighted_vote_reads_fusion_cfg_strictly():
    from core import engine_runner as er
    from core.fusion_engine import FusionConfig
    runner = er.EngineRunner.__new__(er.EngineRunner)
    runner.fusion = type("_F", (), {"cfg": FusionConfig.from_section(dict(FUSION_SECTION))})()
    vote = runner._compute_weighted_vote({n: {"score": 0.5} for n in ("crt", "gaussian", "zone_gate", "rr")})
    assert 0.0 <= vote <= 1.0


# ── governance_mode ───────────────────────────────────────────────────────────

@pytest.fixture
def _gov(monkeypatch):
    import core.governance_mode as gm
    monkeypatch.setattr(gm, "_CONFIG_MODE_CACHE", None)
    monkeypatch.delenv("GOVERNANCE_MODE", raising=False)
    return gm


def test_governance_mode_missing_key_raises(_gov, monkeypatch):
    monkeypatch.setattr(_pc, "get_prod_section", lambda name, *a, **k: {"min_shadow_trades": 30})
    with pytest.raises(ConfigKeyMissingError) as ei:
        _gov.governance_mode()
    _assert_names(ei.value, "governance_mode", "governance")


def test_governance_mode_missing_section_raises(_gov, monkeypatch):
    def _absent(name, *a, **k):
        raise RuntimeError("Section 'governance' not found")
    monkeypatch.setattr(_pc, "get_prod_section", _absent)
    with pytest.raises(ConfigKeyMissingError) as ei:
        _gov.governance_mode()
    assert ei.value.missing == ("governance",)


def test_governance_mode_reads_declared_value(_gov, monkeypatch):
    monkeypatch.setattr(_pc, "get_prod_section", lambda name, *a, **k: {"governance_mode": "advisory"})
    assert _gov.governance_mode() == "advisory"


def test_governance_mode_invalid_value_raises(_gov, monkeypatch):
    monkeypatch.setattr(_pc, "get_prod_section", lambda name, *a, **k: {"governance_mode": "loose"})
    with pytest.raises(ValueError):
        _gov.governance_mode()


def test_governance_mode_env_override_when_set(_gov, monkeypatch):
    monkeypatch.setenv("GOVERNANCE_MODE", "strict")
    monkeypatch.setattr(_pc, "get_prod_section",
                        lambda name, *a, **k: pytest.fail("config must not be read"))
    assert _gov.governance_mode() == "strict"


# ── collector (COLLECTOR_ZONEGATE_SCORE_KEY) ─────────────────────────────────

@pytest.fixture
def _coll(monkeypatch):
    import core.collector as c
    monkeypatch.setattr(c, "_ZONEGATE_SCORE_KEY_CACHE", None)
    monkeypatch.delenv("COLLECTOR_ZONEGATE_SCORE_KEY", raising=False)
    return c


def test_collector_zonegate_key_missing_raises(_coll, monkeypatch):
    monkeypatch.setattr(_pc, "get_prod_section", lambda name, *a, **k: {})
    with pytest.raises(ConfigKeyMissingError) as ei:
        _coll._zonegate_value_keys()
    _assert_names(ei.value, "zonegate_score_key", "collector")


def test_collector_zonegate_section_missing_raises(_coll, monkeypatch):
    def _absent(name, *a, **k):
        raise RuntimeError("Section 'collector' not found")
    monkeypatch.setattr(_pc, "get_prod_section", _absent)
    with pytest.raises(ConfigKeyMissingError) as ei:
        _coll._zonegate_value_keys()
    assert ei.value.missing == ("collector",)


def test_collector_zonegate_declared_value(_coll, monkeypatch):
    monkeypatch.setattr(_pc, "get_prod_section", lambda name, *a, **k: {"zonegate_score_key": "zone"})
    assert _coll._zonegate_value_keys() == ("zone", "score")


def test_collector_zonegate_env_override(_coll, monkeypatch):
    monkeypatch.setenv("COLLECTOR_ZONEGATE_SCORE_KEY", "score")
    monkeypatch.setattr(_pc, "get_prod_section",
                        lambda name, *a, **k: pytest.fail("config must not be read"))
    assert _coll._zonegate_value_keys() == ("score", "zone")

