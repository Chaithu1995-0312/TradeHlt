"""Fail-closed compatibility gates: trainer.load_gaussian_model and GaussianModelRegistry.promote_gaussian."""
import json
from unittest.mock import patch

import numpy as np
import pytest

from core.model_registry import GaussianModelRegistry
from features.feature_contract import ContractMismatchError, contract_hash
from features.feature_schema import CANONICAL_FEATURES
from training import trainer


def _trained(n=60, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, len(CANONICAL_FEATURES))).tolist()
    y = rng.normal(0.3, 1.2, n).tolist()
    return trainer.train_gaussian(X, y)


@pytest.fixture()
def saved(tmp_path):
    model, scaler, metrics = _trained()
    with patch("training.trainer.MODELS_DIR", tmp_path):
        trainer.save_gaussian_model(model, scaler, metrics, name="ok.json")
    return tmp_path, model, scaler, metrics


def _edit(tmp_path, name, fn):
    p = tmp_path / name
    b = json.loads(p.read_text()); fn(b); p.write_text(json.dumps(b))


# ------------------------------------------------------------------ loader
def test_save_stamps_contract_and_load_verifies(saved):
    tmp_path, *_ = saved
    b = json.loads((tmp_path / "ok.json").read_text())
    assert b["feature_contract_hash"] == contract_hash() and b["feature_contract_version"]
    with patch("training.trainer.MODELS_DIR", tmp_path):
        model, scaler, meta = trainer.load_gaussian_model("ok.json")
    assert meta["contract_status"] == "verified" and model.n_features == 35


def test_wrong_hash_is_rejected_even_when_legacy_allowed(saved):
    tmp_path, *_ = saved
    _edit(tmp_path, "ok.json", lambda b: b.update(feature_contract_hash="0" * 64))
    with patch("training.trainer.MODELS_DIR", tmp_path):
        for legacy in (False, True):
            with pytest.raises(ContractMismatchError, match="mismatch"):
                trainer.load_gaussian_model("ok.json", allow_legacy=legacy)


def test_missing_hash_is_rejected_by_default_and_labelled_when_allowed(saved):
    tmp_path, *_ = saved
    _edit(tmp_path, "ok.json", lambda b: b.pop("feature_contract_hash"))
    with patch("training.trainer.MODELS_DIR", tmp_path):
        with pytest.raises(ContractMismatchError, match="legacy"):
            trainer.load_gaussian_model("ok.json")
        _, _, meta = trainer.load_gaussian_model("ok.json", allow_legacy=True)
    assert meta["contract_status"] == "legacy_unverified"


def test_noncanonical_schema_is_never_stamped(tmp_path):
    model, scaler, metrics = _trained()
    with patch("training.trainer.MODELS_DIR", tmp_path):
        trainer.save_gaussian_model(model, scaler, metrics, name="bad.json", feature_schema=["a", "b"])
        assert "feature_contract_hash" not in json.loads((tmp_path / "bad.json").read_text())
        with pytest.raises(ValueError, match="schema mismatch"):
            trainer.load_gaussian_model("bad.json")


def test_dimension_tampering_is_rejected(saved):
    tmp_path, *_ = saved
    _edit(tmp_path, "ok.json", lambda b: b["model"].update(n_features=34))
    with patch("training.trainer.MODELS_DIR", tmp_path):
        with pytest.raises(ValueError, match="n_features"):
            trainer.load_gaussian_model("ok.json")


def test_stale_32_and_33_feature_artifacts_in_repo_are_rejected():
    from pathlib import Path
    repo_models = Path(__file__).resolve().parents[1] / "models"
    files = sorted(repo_models.glob("gaussian_p5_*.json"))
    assert files, "repository p5 artifacts expected"
    for f in files:
        for legacy in (False, True):
            with pytest.raises(ValueError):
                trainer.load_gaussian_model(f.name, allow_legacy=legacy)   # schema check precedes the contract check


# ------------------------------------------------------------------ registry promotion gate
def _reg(tmp_path):
    return GaussianModelRegistry(models_dir=tmp_path)


def _metrics():
    return {"corr_expected_rr": 0.1, "calibration_error": 0.1, "n_train": 10, "n_val": 5}


def test_legacy_artifact_cannot_be_promoted_even_with_force(tmp_path):
    (tmp_path / "legacy.json").write_text(json.dumps({"feature_schema": list(CANONICAL_FEATURES)}))
    reg = _reg(tmp_path)
    entry = reg.register_gaussian("legacy", "legacy.json", list(CANONICAL_FEATURES), _metrics())
    assert entry["feature_contract_hash"] is None
    ok, reason = reg.promote_gaussian("legacy", force=True)
    assert not ok and "feature contract" in reason
    assert reg.get_active_gaussian() is None


def test_missing_artifact_cannot_be_promoted(tmp_path):
    reg = _reg(tmp_path)
    reg.register_gaussian("ghost", "ghost.json", list(CANONICAL_FEATURES), _metrics())
    ok, _ = reg.promote_gaussian("ghost", force=True)
    assert not ok


def test_contract_artifact_promotes_and_tampering_after_registration_blocks(tmp_path):
    model, scaler, metrics = _trained()
    with patch("training.trainer.MODELS_DIR", tmp_path):
        trainer.save_gaussian_model(model, scaler, metrics, name="m1.json")
        trainer.save_gaussian_model(model, scaler, metrics, name="m2.json")
    reg = _reg(tmp_path)
    reg.register_gaussian("v1", "m1.json", list(CANONICAL_FEATURES), _metrics())
    reg.register_gaussian("v2", "m2.json", list(CANONICAL_FEATURES), _metrics())
    ok, _ = reg.promote_gaussian("v1", force=True)
    assert ok and reg.get_active_gaussian() == "v1"
    _edit(tmp_path, "m2.json", lambda b: b.update(feature_contract_hash="f" * 64))      # artifact changed after registration
    ok2, reason2 = reg.promote_gaussian("v2", force=True)
    assert not ok2 and "feature contract" in reason2 and reg.get_active_gaussian() == "v1"


def test_edited_registry_entry_hash_blocks_promotion(tmp_path):
    model, scaler, metrics = _trained()
    with patch("training.trainer.MODELS_DIR", tmp_path):
        trainer.save_gaussian_model(model, scaler, metrics, name="m1.json")
    reg = _reg(tmp_path)
    reg.register_gaussian("v1", "m1.json", list(CANONICAL_FEATURES), _metrics())
    raw = json.loads((tmp_path / "gaussian_registry.json").read_text()); raw["v1"]["feature_contract_hash"] = "0" * 64
    (tmp_path / "gaussian_registry.json").write_text(json.dumps(raw))
    ok, _ = _reg(tmp_path).promote_gaussian("v1", force=True)
    assert not ok
