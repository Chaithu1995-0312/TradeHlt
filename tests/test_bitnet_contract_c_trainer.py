"""
CONTRACT-C trainer R1: bundle completeness, load-back, reproducibility seed.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from bitnet.contract_c_trainer import TrainerConfig, train_and_export
from bitnet.model_bundle import load_composition_from_bundle, validate_model_bundle
from bitnet.label_contracts import get_label_contract


def test_label_contract_registry():
    c = get_label_contract("BITNET_LABEL_ATR_RACE_BULL_V1")
    assert c["economic_authority"] == "DIAGNOSTIC_ONLY"
    assert c["label_contract_id"] == "BITNET_LABEL_ATR_RACE_BULL_V1"


def test_train_synthetic_bundle_contract_c(tmp_path: Path):
    cfg = TrainerConfig(
        epochs=4,
        hidden_dim=8,
        latent_dim=4,
        n_residual_blocks=1,
        batch_size=32,
        seed=7,
        holdout_fraction=0.25,
    )
    result = train_and_export(
        out_dir=tmp_path,
        cfg=cfg,
        synthetic=True,
        synthetic_n=120,
        bundle_name="test_bundle_c",
    )
    root = result.bundle_path
    assert root.is_dir()
    for name in (
        "envelope.json",
        "metadata.json",
        "feature_schema.json",
        "label_contract.json",
        "metrics.json",
        "training_manifest.json",
        "evaluation_report.json",
        "sha256.txt",
    ):
        assert (root / name).exists(), name

    envelope = validate_model_bundle(root)
    assert envelope["backbone"]["id"] == "bb_bitlinear_res_v1"
    assert envelope["backbone"]["hidden_dim"] == 8
    assert envelope["backbone"]["n_residual_blocks"] == 1

    label = json.loads((root / "label_contract.json").read_text(encoding="utf-8"))
    assert label["economic_authority"] == "DIAGNOSTIC_ONLY"

    schema = json.loads((root / "feature_schema.json").read_text(encoding="utf-8"))
    assert schema["train_feature_identities"]
    assert len(schema["feature_names"]) == 38

    manifest = json.loads((root / "training_manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == 7
    assert "dataset" in manifest

    ev = json.loads((root / "evaluation_report.json").read_text(encoding="utf-8"))
    assert ev["stage"] == "R1"
    assert ev["pass"] is True

    # Load-back through composition
    comp = load_composition_from_bundle(root)
    names = comp.metadata().feature_names
    feats = {n: 0.01 * i for i, n in enumerate(names)}
    pred = comp.predict(feats)
    assert 0.0 <= pred.confidence <= 1.0
    assert pred.backbone_id == "bb_bitlinear_res_v1"


def test_train_reproducible_seed(tmp_path: Path):
    def run(seed: int, name: str):
        cfg = TrainerConfig(
            epochs=3,
            hidden_dim=6,
            latent_dim=3,
            n_residual_blocks=0,
            batch_size=16,
            seed=seed,
            holdout_fraction=0.2,
        )
        return train_and_export(
            out_dir=tmp_path,
            cfg=cfg,
            synthetic=True,
            synthetic_n=64,
            bundle_name=name,
        )

    r1 = run(11, "a")
    r2 = run(11, "b")
    # Same seed → same train mse history
    h1 = r1.metrics["history"]
    h2 = r2.metrics["history"]
    assert h1[-1]["train_mse"] == pytest.approx(h2[-1]["train_mse"], rel=0, abs=1e-12)


def test_missing_label_contract_rejected():
    with pytest.raises(KeyError):
        get_label_contract("NOT_A_REAL_CONTRACT")
