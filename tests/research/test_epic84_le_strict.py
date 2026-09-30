"""EPIC-84 L-E: a missing required key raises ConfigKeyMissingError naming it.

Per-trade payload gaps return the module's existing reject (None + logged
reason) and do not raise. Fixtures are explicit. Nothing here reads a default
out of a missing key.
"""
from __future__ import annotations

import copy
import logging
from types import SimpleNamespace

import pytest

from config_layer.strict_config import ConfigKeyMissingError
from research.clean_labels.builder import BuildConfig
from research.clean_labels.protocol import COST_BPS, MAX_FORWARD
from research.config import ResearchConfig
from research.cross_sectional import XSQualConfig
from research.envelope_offline.shadow import ShadowConfig
from research.envelope_offline.train import TrainConfig
from research.episodes.events import _detect_be_eligible, _detect_reached_r, _detect_sl_threat
from research.evidence.driver import DriverConfig
from research.goal_alignment import attach_goal_reports
from research.mt5_cost_calibration import CostCalibrationConfig
from research.provenance import provenance_block
from research.regime_conditioning import RegimeConfig
from research.zone_mapping.historical_zone_mapper import ZoneMapConfig

_RESEARCH = {
    "job_kind": "unspecified",
    "harness": {"warmup": 20, "window_size": 64, "min_samples": 10},
    "forward_walk": {"max_forward": 20, "trail_mult": 0.5, "exit_model": "intrabar_fixed"},
    "signal": {"apply_signal_defaults": True, "sl_atr_mult": 1.0, "tp_atr_mult": 2.0},
    "costs": {"cost_model": "flat_bps", "round_trip_bps": 12.0},
    "qualification": {
        "min_samples": 30, "expectancy_min": 0.0, "pf_min": 1.0, "oos_split": 0.3,
        "oos_retention_min": 0.5, "n_permutations": 2000, "significance_alpha": 0.05,
    },
    "universe": {"data_dir": "data", "pattern": "*_M15.csv", "instruments": "ALL"},
}

_RESEARCH_KEYS = [
    (None, "job_kind"),
    ("harness", "warmup"),
    ("harness", "window_size"),
    ("harness", "min_samples"),
    ("forward_walk", "max_forward"),
    ("forward_walk", "trail_mult"),
    ("forward_walk", "exit_model"),
    ("signal", "apply_signal_defaults"),
    ("signal", "sl_atr_mult"),
    ("signal", "tp_atr_mult"),
    ("costs", "round_trip_bps"),
    ("costs", "cost_model"),
    ("qualification", "min_samples"),
    ("qualification", "expectancy_min"),
    ("qualification", "pf_min"),
    ("qualification", "oos_split"),
    ("qualification", "oos_retention_min"),
    ("qualification", "n_permutations"),
    ("qualification", "significance_alpha"),
    ("universe", "data_dir"),
    ("universe", "pattern"),
    ("universe", "instruments"),
]


def _drop(section, key):
    d = copy.deepcopy(_RESEARCH)
    if section is None:
        del d[key]
    else:
        del d[section][key]
    return d


@pytest.mark.parametrize("section,key", _RESEARCH_KEYS)
def test_research_config_missing_key_names_it(section, key):
    with pytest.raises(ConfigKeyMissingError) as ei:
        ResearchConfig.from_dict(_drop(section, key))
    assert key in ei.value.missing


def _assert_missing(factory, complete, key):
    d = dict(complete)
    del d[key]
    with pytest.raises(ConfigKeyMissingError) as ei:
        factory(d)
    assert key in ei.value.missing


_BUILD = {
    "instrument": "TEST", "max_forward": MAX_FORWARD, "cost_bps": COST_BPS,
    "max_units": None, "source_path": "", "candle_path": "",
    "builder_entrypoint": "scripts/research/build_clean_labels_tn_env.py",
}
_TRAIN = {
    "dataset_path": "d.jsonl", "out_dir": "out", "instrument": "BNBUSDT",
    "max_rows": None, "train_frac": 0.60, "val_frac": 0.20, "seed": 42,
    "max_depth": 6, "max_iter": 100, "learning_rate": 0.08, "min_samples_leaf": 40,
}
_SHADOW = {
    "bundle_dir": "b", "dataset_path": "d", "out_dir": "o",
    "instrument": "BNBUSDT", "max_rows": None,
}
_XS = {
    "k": 2, "min_samples": 10, "expectancy_min": 0.0, "pf_min": 1.0,
    "oos_split": 0.3, "oos_retention_min": 0.5, "n_permutations": 10,
    "significance_alpha": 0.05, "round_trip_bps": 12.0, "warmup": 0,
}
_DRIVER = {"out_dir": "results/x", "question": None, "atlas": None, "max_rows": None}
_COSTCAL = {
    "symbol": "XAUUSD", "tick_lookback_days": 14, "history_lookback_days": 90,
    "tick_chunk_days": 1, "min_stop_fills_for_confidence": 5,
    "out_dir": "results/research/xauusd_mt5_cost_calibration",
    "server_utc_offset_hours": None,
}
_ZONE = {
    "registry_path": "models/zone_registry.json", "feature_cluster_similarity_cluster_threshold": 0.0,
    "top_k": 3, "cluster_min_n": 1, "cluster_spread_max": 1.0,
    "feature_cluster_similarity_min_samples": 50, "execution_mode": "normal",
}
_REGIME = {
    "regime": {
        "atr_period": 14, "tercile_window": 480, "lag_k": 50,
        "min_cell_samples": 30, "harmful_margin": 0.05,
        "redundant_tol": 0.05, "null_relabelings": 200,
    }
}


@pytest.mark.parametrize("key", list(_BUILD))
def test_build_config_missing_key(key):
    _assert_missing(BuildConfig.from_dict, _BUILD, key)


@pytest.mark.parametrize("key", list(_TRAIN))
def test_train_config_missing_key(key):
    _assert_missing(TrainConfig.from_dict, _TRAIN, key)


@pytest.mark.parametrize("key", list(_SHADOW))
def test_shadow_config_missing_key(key):
    _assert_missing(ShadowConfig.from_dict, _SHADOW, key)


@pytest.mark.parametrize("key", list(_XS))
def test_xs_qual_config_missing_key(key):
    _assert_missing(XSQualConfig.from_dict, _XS, key)


@pytest.mark.parametrize("key", list(_DRIVER))
def test_driver_config_missing_key(key):
    _assert_missing(DriverConfig.from_dict, _DRIVER, key)


@pytest.mark.parametrize("key", list(_COSTCAL))
def test_cost_calibration_config_missing_key(key):
    _assert_missing(CostCalibrationConfig.from_dict, _COSTCAL, key)


@pytest.mark.parametrize("key", list(_ZONE))
def test_zone_map_config_missing_key(key):
    _assert_missing(ZoneMapConfig.from_dict, _ZONE, key)


@pytest.mark.parametrize(
    "key",
    ["atr_period", "tercile_window", "lag_k", "min_cell_samples",
     "harmful_margin", "redundant_tol", "null_relabelings"],
)
def test_regime_config_missing_key(key):
    d = copy.deepcopy(_REGIME)
    del d["regime"][key]
    with pytest.raises(ConfigKeyMissingError) as ei:
        RegimeConfig.from_dict(d)
    assert key in ei.value.missing


def test_replay_record_missing_direction_is_rejected(caplog):
    from replay.replay_memory_engine import ReplayMemoryEngine
    eng = ReplayMemoryEngine.__new__(ReplayMemoryEngine)
    rec = {"features": {"atr": 1.0}, "rr_achieved": 0.0}
    with caplog.at_level(logging.INFO):
        assert eng._record_from(rec, 0.0) is None
    assert "config_key_missing:replay.record.direction" in caplog.text


def test_spine_env_missing_raises(monkeypatch):
    from research.adapters.spine_signal_source import ProductionSpineSource
    monkeypatch.delenv("RESEARCH_SPINE_CONFIG", raising=False)
    with pytest.raises(ConfigKeyMissingError) as ei:
        ProductionSpineSource()
    assert "RESEARCH_SPINE_CONFIG" in ei.value.missing


def test_router_map_without_default_raises():
    from regime.config_router import ConfigRouter
    with pytest.raises(ConfigKeyMissingError) as ei:
        ConfigRouter(regime_map={"TRENDING": "BALANCED"})
    assert "DEFAULT" in ei.value.missing


def test_regime_classifier_missing_atr():
    from regime.regime_classifier import RegimeClassifier
    with pytest.raises(ConfigKeyMissingError) as ei:
        RegimeClassifier().classify({"trend_score": 0.1})
    assert "atr" in ei.value.missing


def test_market_state_missing_feature_and_replay():
    from regime.market_state_cluster_engine import MarketStateClusterEngine
    eng = MarketStateClusterEngine(min_cluster_samples=5, cooldown_bars=0)
    features = {
        "volatility_ratio": 1.0, "sweep_detected": 0.0, "double_sweep": 0.0,
        "break_of_structure": 0.0, "disp_strength": 0.0, "liquidity_distance": 1.0,
        "liquidity_pressure_score": 0.0, "volume_spike": 0.0, "atr": 0.1,
        "candles_since_sweep": 1.0,
    }
    broken = dict(features)
    del broken["atr"]
    with pytest.raises(ConfigKeyMissingError) as ei:
        eng.classify(broken)
    assert "atr" in ei.value.missing
    stats = SimpleNamespace(
        cluster_id=0, n_samples=50, win_rate=0.5, mean_rr=0.0, std_rr=0.5,
        trap_frequency=0.2, staleness_days=1.0,
    )
    with pytest.raises(ConfigKeyMissingError) as ei:
        eng.classify(features, cluster_stats=stats, replay_features={})
    assert "market_state_entropy" in ei.value.missing
    assert "transition_probability" in ei.value.missing


def test_timing_missing_body_ratio():
    from replay.timing_advisor import geometry_bucket
    with pytest.raises(ConfigKeyMissingError) as ei:
        geometry_bucket({})
    assert "body_ratio" in ei.value.missing


def test_episode_rulepack_keys():
    entry = SimpleNamespace(risk_distance=1.0)
    with pytest.raises(ConfigKeyMissingError) as ei:
        _detect_reached_r(entry, [], [], {})
    assert "r_thresholds" in ei.value.missing
    with pytest.raises(ConfigKeyMissingError) as ei:
        _detect_be_eligible(entry, [], [], {})
    assert "be_mfe_r" in ei.value.missing
    with pytest.raises(ConfigKeyMissingError) as ei:
        _detect_sl_threat(entry, [], [], {})
    assert "sl_threat_r" in ei.value.missing


def test_provenance_cost_model_id_required():
    with pytest.raises(ConfigKeyMissingError) as ei:
        provenance_block("intrabar_fixed", 12.0, tie_break="production", cost_model={})
    assert "cost_model_id" in ei.value.missing


def test_edge_report_missing_key_rejects():
    with pytest.raises(ConfigKeyMissingError) as ei:
        attach_goal_reports({"pooled": {"hypothesis": "h"}}, spec=object())
    assert "n" in ei.value.missing


def test_spine_hypothesis_missing_instrument():
    from research.hypotheses.spine_hypothesis import SpineHypothesis
    bar = SimpleNamespace(index=0, timestamp="t", close=1.0, high=1.0, low=1.0)
    with pytest.raises(ConfigKeyMissingError) as ei:
        SpineHypothesis(source=object()).detect([bar], {}, {})
    assert "instrument" in ei.value.missing


def test_interpreter_hypothesis_missing_instrument():
    from interpreters.adapter import InterpreterHypothesis

    class _Interp:
        name = "t"

        def observe(self, window, features, ctx):
            return SimpleNamespace(events=[])

    bar = SimpleNamespace(index=1, timestamp="t")
    with pytest.raises(ConfigKeyMissingError) as ei:
        InterpreterHypothesis(_Interp()).detect([bar], {}, {})
    assert "instrument" in ei.value.missing


def test_capture_negative_threshold_required():
    from research.band_tables import classify_capture
    table = {
        "table_kind": "guarded_two_stage",
        "guards": [
            {"name": "CAPTURE_UNDEFINED", "priority": 1, "params": {"epsilon": 1e-9}},
            {"name": "CAPTURE_UNSTABLE", "priority": 2, "params": {"unstable_threshold": 0.05}},
            {"name": "CAPTURE_NEGATIVE", "priority": 3, "params": {}},
            {"name": "CAPTURE_VIOLATION", "priority": 4, "params": {"violation_threshold": 1.0}},
        ],
    }
    with pytest.raises(ConfigKeyMissingError) as ei:
        classify_capture(0.3, -0.1, table)
    assert "unstable_threshold" in ei.value.missing
