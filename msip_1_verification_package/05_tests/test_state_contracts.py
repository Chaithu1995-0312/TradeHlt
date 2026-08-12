"""
Phase-1 state contract loading — positive + negative validation suite.

Contracts live in active_models.yaml; runtime objects are produced only by
StateContractLoader. No parallel Python STATE_REQUIRED_FM constants.
"""
from __future__ import annotations

import copy
import dataclasses
import textwrap
from pathlib import Path

import pytest
import yaml

from config_layer.crt_engine_v2 import (
    CRTConfig,
    CRTEngine,
    CRTState,
    VALID_TRANSITIONS,
)
from config_layer.state_contract import (
    ALLOWED_STATE_CONTRACT_FIELDS,
    SCHEMA_VERSION,
    StateContract,
    parse_state_contract,
)
from config_layer.state_contract_loader import (
    StateContractError,
    clear_state_contract_cache,
    load_and_validate_state_contracts,
)

_ROOT = Path(__file__).resolve().parents[1]
_AM = _ROOT / "active_models.yaml"


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_state_contract_cache()
    yield
    clear_state_contract_cache()


@pytest.fixture
def am_doc() -> dict:
    return yaml.safe_load(_AM.read_text(encoding="utf-8"))


def _write_am(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "active_models.yaml"
    p.write_text(yaml.dump(doc, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return p


def _minimal_valid_doc(base: dict) -> dict:
    """Deep-copy production active_models for mutation tests."""
    return copy.deepcopy(base)


# ── Positive path ────────────────────────────────────────────────────────────

def test_load_production_active_models_succeeds():
    bundle = load_and_validate_state_contracts()
    assert bundle.schema_version == SCHEMA_VERSION
    assert len(bundle.contracts) == 9
    assert set(bundle.contracts) == {s.name for s in CRTState}


def test_state_set_parity_with_crtstate():
    bundle = load_and_validate_state_contracts()
    assert set(bundle.contracts) == {s.name for s in CRTState}


def test_transition_graph_parity_with_valid_transitions():
    bundle = load_and_validate_state_contracts()
    code = {s.name: {t.name for t in ts} for s, ts in VALID_TRANSITIONS.items()}
    declared = {k: set(v) for k, v in bundle.transitions.items()}
    assert declared == code


def test_fm_ids_resolve():
    bundle = load_and_validate_state_contracts()
    declared = sorted({fm for c in bundle.contracts.values() for fm in c.required_fm})
    assert declared == ["FM-002", "FM-010", "FM-027", "FM-028"]
    # SWEEP / EXPANSION / RETEST census
    assert set(bundle.get("SWEEP").required_fm) == {"FM-002", "FM-010"}
    assert set(bundle.get("EXPANSION").required_fm) == {"FM-010", "FM-028"}
    assert set(bundle.get("RETEST").required_fm) == {"FM-010", "FM-027", "FM-028"}


def test_config_keys_are_crtconfig_fields():
    bundle = load_and_validate_state_contracts()
    fields = {f.name for f in dataclasses.fields(CRTConfig)}
    for sc in bundle.contracts.values():
        for k in sc.config_keys:
            assert k in fields, f"{sc.state_id}: {k} not on CRTConfig"


def test_eligible_models_only_bitnet_on_retest():
    bundle = load_and_validate_state_contracts()
    for sid, sc in bundle.contracts.items():
        if sid == "RETEST":
            assert sc.eligible_models == ("bitnet",)
        else:
            assert sc.eligible_models == ()


def test_no_numeric_thresholds_in_contracts():
    bundle = load_and_validate_state_contracts()
    for sc in bundle.contracts.values():
        for seq in (sc.required_fm, sc.config_keys, sc.eligible_models):
            for v in seq:
                assert isinstance(v, str)
                # bare numeric thresholds must not appear as contract values
                with pytest.raises(ValueError):
                    float(v)


def test_contracts_immutable():
    bundle = load_and_validate_state_contracts()
    sc = bundle.get("SWEEP")
    assert isinstance(sc, StateContract)
    with pytest.raises(dataclasses.FrozenInstanceError):
        sc.state_id = "X"  # type: ignore[misc]
    with pytest.raises(TypeError):
        bundle.contracts["SWEEP"] = sc  # MappingProxyType


def test_exactly_one_contract_per_state():
    bundle = load_and_validate_state_contracts()
    assert len(bundle.contracts) == len(set(bundle.contracts))
    assert len(bundle.contracts) == 9


def test_stale_legacy_cache_names_not_in_required_fm(am_doc: dict):
    """required_fm must not use pre-CH-002 collision names as FM ids."""
    bundle = load_and_validate_state_contracts()
    all_fm = {fm for c in bundle.contracts.values() for fm in c.required_fm}
    assert "retest_depth" not in all_fm
    assert "disp_strength" not in all_fm
    # WHO cached_features block should use FM emission names
    cached = am_doc["crt"]["runtime"]["cached_features_at_retest"]
    names = {row["feature"] for row in cached if "feature" in row}
    assert "displacement_retrace" in names
    assert "displacement_atr_ratio" in names
    assert "retest_depth" not in names
    assert "disp_strength" not in names


def test_no_parallel_python_state_contract_constants():
    """Guard: no STATE_REQUIRED_FM / STATE_ELIGIBLE_MODELS / STATE_CONFIG_KEYS modules."""
    import config_layer.state_contract as sc
    import config_layer.state_contract_loader as scl
    for mod in (sc, scl):
        for banned in (
            "STATE_REQUIRED_FM",
            "STATE_ELIGIBLE_MODELS",
            "STATE_CONFIG_KEYS",
        ):
            assert not hasattr(mod, banned), f"{mod.__name__} must not define {banned}"


def test_crt_engine_loads_contracts_non_mutating():
    cfg = CRTConfig()
    eng = CRTEngine(config=cfg)
    assert eng.state_contracts is not None
    assert len(eng.state_contracts.contracts) == 9
    c = eng.get_state_contract("RETEST")
    assert c.required_fm == ("FM-010", "FM-027", "FM-028")
    c2 = eng.get_state_contract()  # current state RANGE at init
    assert c2.state_id == "RANGE"


def test_process_candle_dual_run_behavior_parity():
    """Phase-1 wiring must not alter SM decisions (byte-identical action stream)."""
    import hashlib
    import json
    from datetime import datetime, timedelta
    from config_layer.crt_engine_v2 import Candle

    def _fingerprint() -> str:
        clear_state_contract_cache()
        eng = CRTEngine(config=CRTConfig())
        base = datetime(2024, 1, 1, 0, 0, 0)
        candles = [
            Candle(
                timestamp=base + timedelta(minutes=15 * i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.2,
                volume=1.0,
                index=i,
            )
            for i in range(50)
        ]
        eng.initialise_range(candles[:10], htf_candle_id="H0", session="LONDON")
        actions = []
        for c in candles[10:]:
            a = eng.process_candle(c, htf_candle_id="H0")
            actions.append(
                {k: a.get(k) for k in ("action", "state", "state_after", "reason")}
            )
        return hashlib.sha256(json.dumps(actions, default=str).encode()).hexdigest()

    assert _fingerprint() == _fingerprint()


def test_allowed_fields_only():
    assert ALLOWED_STATE_CONTRACT_FIELDS == frozenset(
        {"required_fm", "config_keys", "eligible_models"}
    )


# ── Negative path ────────────────────────────────────────────────────────────

def test_missing_state(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    del doc["crt"]["runtime"]["state_contracts"]["EXPIRED"]
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="state-set parity"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_extra_state(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["CANCELLED"] = {
        "required_fm": [],
        "config_keys": [],
        "eligible_models": [],
    }
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="state-set parity"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_unknown_state_in_contracts_only(tmp_path, am_doc):
    # same as extra state
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["NOT_A_STATE"] = {
        "required_fm": [],
        "config_keys": [],
        "eligible_models": [],
    }
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="state-set parity"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_missing_contract_field(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    del doc["crt"]["runtime"]["state_contracts"]["SWEEP"]["required_fm"]
    p = _write_am(tmp_path, doc)
    with pytest.raises((StateContractError, ValueError), match="missing required field"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_unknown_contract_field(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["SWEEP"]["threshold"] = 0.7
    p = _write_am(tmp_path, doc)
    with pytest.raises((StateContractError, ValueError), match="unknown field"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_duplicate_fm_id(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["SWEEP"]["required_fm"] = [
        "FM-002",
        "FM-002",
    ]
    p = _write_am(tmp_path, doc)
    with pytest.raises((StateContractError, ValueError), match="duplicate"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_unknown_fm_id(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["SWEEP"]["required_fm"] = ["FM-999"]
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="FM ID not found"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_nonexistent_config_key(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["RANGE"]["config_keys"] = [
        "not_a_real_crt_field_xyz"
    ]
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="CONFIG_KEY_MISSING"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_unknown_model_id(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["RETEST"]["eligible_models"] = [
        "not_a_model"
    ]
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="unknown model ID"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_duplicate_model_id(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["RETEST"]["eligible_models"] = [
        "bitnet",
        "bitnet",
    ]
    p = _write_am(tmp_path, doc)
    with pytest.raises((StateContractError, ValueError), match="duplicate"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_transition_graph_mismatch(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["valid_transitions"]["RANGE"] = ["SWEEP"]  # drop SHADOW_PENDING
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="transition graph parity"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_malformed_yaml_type_state_block(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["RANGE"] = "not-a-map"
    p = _write_am(tmp_path, doc)
    with pytest.raises((StateContractError, TypeError), match="mapping"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_numeric_threshold_in_state_contract(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["SWEEP"]["config_keys"] = [0.70]
    p = _write_am(tmp_path, doc)
    with pytest.raises((StateContractError, ValueError, TypeError), match="numeric|string"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_formula_string_in_state_contract(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["SWEEP"]["required_fm"] = [
        "body / range"
    ]
    p = _write_am(tmp_path, doc)
    with pytest.raises((StateContractError, ValueError), match="expression|formula|FM ID"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_import_expression_rejected(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contracts"]["RANGE"]["config_keys"] = [
        "import(os)"
    ]
    p = _write_am(tmp_path, doc)
    with pytest.raises((StateContractError, ValueError), match="expression|formula|CONFIG_KEY"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_missing_schema_version(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    del doc["crt"]["runtime"]["state_contract_schema_version"]
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="state_contract_schema_version"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_wrong_schema_version(tmp_path, am_doc):
    doc = _minimal_valid_doc(am_doc)
    doc["crt"]["runtime"]["state_contract_schema_version"] = "9.9"
    p = _write_am(tmp_path, doc)
    with pytest.raises(StateContractError, match="unsupported"):
        load_and_validate_state_contracts(p, force_reload=True)


def test_parse_state_contract_rejects_unknown_field():
    with pytest.raises(ValueError, match="unknown field"):
        parse_state_contract(
            "RANGE",
            {"required_fm": [], "config_keys": [], "eligible_models": [], "formula": "x"},
        )
