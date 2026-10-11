"""Verifies the registered active Gaussian artifact is loadable, schema-exact and safe to call."""
import hashlib
import json
import math
from pathlib import Path

import pytest

from core.model_registry import get_active_gaussian
from features.dataset_builder import GAUSSIAN_FEATURE_SCHEMA
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


def test_artifact_loads_with_exact_schema_and_gives_valid_probabilities():
    _, e = _active()
    model, scaler, meta = trainer.load_gaussian_model(e["model_file"])
    assert model.n_features == len(GAUSSIAN_FEATURE_SCHEMA) == 35
    raw = json.loads((MODELS / e["model_file"]).read_text())
    x = scaler.transform([list(scaler._mean)])[0]
    probs = model.predict_proba(x) if hasattr(model, "predict_proba") else None
    if probs is not None:
        assert len(probs) == 4 and abs(sum(probs) - 1.0) < 1e-6
    exp_rr = model.predict_expected_rr(x)[0]
    assert math.isfinite(exp_rr)
    assert raw["feature_definition"]["structure_mode"] == "causal_v2"


def test_incompatible_input_and_missing_model_fail_explicitly():
    _, e = _active()
    model, scaler, _ = trainer.load_gaussian_model(e["model_file"])
    with pytest.raises(Exception):
        model.predict_expected_rr([0.0] * 34)
    with pytest.raises(FileNotFoundError):
        trainer.load_gaussian_model("does_not_exist.json")
