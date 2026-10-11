"""The registered active Gaussian artifact: identity, fail-closed loading, and safe failure modes.

The active artifact (experimental, 9 trades) predates the feature-definition contract, so the default loader
must refuse it; it can only be inspected with allow_legacy=True.
"""
import hashlib
import json
import math
from pathlib import Path

import pytest

from core.model_registry import get_active_gaussian
from features.dataset_builder import GAUSSIAN_FEATURE_SCHEMA
from features.feature_contract import ContractMismatchError
from training import trainer

MODELS = Path(__file__).resolve().parents[1] / "models"


def _active():
    reg = json.loads((MODELS / "gaussian_registry.json").read_text())
    v = get_active_gaussian()
    return v, reg[v]


def test_active_entry_resolves_to_existing_file_with_matching_checksum():
    v, e = _active()
    f = MODELS / e["model_file"]
    assert f.exists()
    assert hashlib.sha256(f.read_bytes()).hexdigest() == e["artifact_sha256"]
    assert e["feature_schema"] == list(GAUSSIAN_FEATURE_SCHEMA)


def test_default_loader_rejects_legacy_active_artifact():
    _, e = _active()
    with pytest.raises(ContractMismatchError, match="legacy"):
        trainer.load_gaussian_model(e["model_file"])


def test_legacy_artifact_loads_only_when_explicitly_allowed_and_is_labelled():
    _, e = _active()
    model, scaler, meta = trainer.load_gaussian_model(e["model_file"], allow_legacy=True)
    assert meta["contract_status"] == "legacy_unverified"
    assert model.n_features == len(GAUSSIAN_FEATURE_SCHEMA) == 35
    x = scaler.transform([list(scaler._mean)])[0]
    assert math.isfinite(model.predict_expected_rr(x)[0])


def test_incompatible_input_and_missing_model_fail_explicitly():
    _, e = _active()
    model, scaler, _ = trainer.load_gaussian_model(e["model_file"], allow_legacy=True)
    with pytest.raises(Exception):
        model.predict_expected_rr([0.0] * 34)
    with pytest.raises(FileNotFoundError):
        trainer.load_gaussian_model("does_not_exist.json")
