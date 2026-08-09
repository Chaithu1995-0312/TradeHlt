"""
test_bitnet_composition.py
==========================
Spec v1.2.1 hierarchy: Encoder → Backbone → Heads → Adapter.

- Legacy composition parity with BitNetModel.forward / bitnet_score
- BitLinear residual family load + predict
- L2 custom dims accepted (self-describing)
- L1 violations rejected (layernorm, stage count)
"""
from __future__ import annotations

import json
import math
import os
import tempfile

import pytest

from bitnet.backbones import BitLinearResBackbone, build_default_backbone_envelope
from bitnet.bitnet_inference import BitNetModel, bitnet_score
from bitnet.composition import (
    build_synthetic_bitlinear_envelope,
    get_default_composition,
    load_bitlinear_composition,
    load_legacy_composition,
    reset_default_composition,
)
from bitnet.encoders import Legacy6Encoder, apply_crt_serve_aliases
from bitnet.layers import sigmoid


LEGACY_KEYS = [
    "body_ratio",
    "retest_depth",
    "disp_strength",
    "atr",
    "candles_since_retest",
    "double_sweep",
]


def _legacy_features(seed: float = 0.1) -> dict:
    return {
        "body_ratio": 0.55 + seed,
        "retest_depth": 0.2 + seed * 0.1,
        "disp_strength": 1.1 + seed,
        "atr": 12.5 + seed,
        "candles_since_retest": 3.0,
        "double_sweep": 0.0,
    }


@pytest.fixture
def legacy_model_path():
    """Prefer repo model.json; else write a tiny synthetic legacy model."""
    if os.path.exists("model.json"):
        yield "model.json"
        return
    # minimal 6→16→8→1
    import random

    rng = random.Random(0)

    def mat(r, c):
        return [[rng.uniform(-0.1, 0.1) for _ in range(c)] for _ in range(r)]

    model = {
        "schema": "legacy_6input",
        "architecture": "6->16->8->1",
        "feature_order": LEGACY_KEYS,
        "layer1_w": mat(16, 6),
        "layer1_b": [0.0] * 16,
        "layer2_w": mat(8, 16),
        "layer2_b": [0.0] * 8,
        "out_w": mat(1, 8),
        "out_b": [0.0],
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(model, f)
    yield path
    os.unlink(path)
    reset_default_composition()


def test_legacy_composition_matches_bitnet_model_forward(legacy_model_path):
    model = BitNetModel(legacy_model_path)
    comp = load_legacy_composition(legacy_model_path)
    feats = _legacy_features(0.2)
    x = [float(feats[k]) for k in LEGACY_KEYS]
    expected = model.forward(x)
    got = comp.predict(feats).confidence
    assert math.isclose(expected, got, rel_tol=0.0, abs_tol=1e-12)


def test_bitnet_score_matches_composition(legacy_model_path, monkeypatch):
    reset_default_composition()
    # Point default composition at the fixture path
    from bitnet import composition as comp_mod

    monkeypatch.setattr(
        comp_mod,
        "get_default_composition",
        lambda model_path=legacy_model_path: load_legacy_composition(legacy_model_path),
    )
    feats = _legacy_features(0.3)
    direct = load_legacy_composition(legacy_model_path).predict(feats).confidence
    via_facade = bitnet_score(feats)
    assert math.isclose(direct, via_facade, rel_tol=0.0, abs_tol=1e-12)


def test_legacy_encoder_fail_fast_missing_key():
    enc = Legacy6Encoder()
    with pytest.raises(KeyError):
        enc.encode({"body_ratio": 0.5})


def test_crt_serve_aliases():
    raw = {
        "body_ratio": 0.6,
        "displacement_retrace": 0.25,
        "displacement_atr_ratio": 1.5,
        "atr_abs": 10.0,
        "candles_since_retest": 2,
        "double_sweep": 1.0,
    }
    mapped = apply_crt_serve_aliases(raw)
    assert mapped["retest_depth"] == 0.25
    assert mapped["disp_strength"] == 1.5
    assert mapped["atr"] == 10.0


def test_bitlinear_defaults_profile_forward():
    env = build_synthetic_bitlinear_envelope(seed=7)
    comp = load_bitlinear_composition(env)
    # Build a feature dict for all encoder names
    names = comp.metadata().feature_names
    feats = {n: float(i) * 0.01 for i, n in enumerate(names)}
    pred = comp.predict(feats)
    assert 0.0 <= pred.confidence <= 1.0
    assert pred.backbone_id == "bb_bitlinear_res_v1"
    assert pred.encoder_id == "enc_canonical38_v1"
    assert comp.metadata().defaults_profile == "bitlinear_res_defaults_v1"


def test_bitlinear_custom_l2_dims_accepted():
    """L2 numerics are not laws — custom H/L/N_res must load if self-describing."""
    env = build_synthetic_bitlinear_envelope(
        input_dim=8,
        hidden_dim=16,
        latent_dim=8,
        n_residual_blocks=1,
        seed=3,
        feature_names=[f"f{i}" for i in range(8)],
    )
    comp = load_bitlinear_composition(env)
    feats = {f"f{i}": 0.1 * i for i in range(8)}
    pred = comp.predict(feats)
    assert 0.0 <= pred.confidence <= 1.0
    assert comp.backbone().latent_dim() == 8


def test_bitlinear_rejects_layernorm():
    bb = build_default_backbone_envelope(input_dim=4, hidden_dim=4, latent_dim=2, n_residual_blocks=0, seed=0)
    # n_res=0 → stages = in + lat only
    bb["input_dim"] = 4
    bb["hidden_dim"] = 4
    bb["latent_dim"] = 2
    bb["n_residual_blocks"] = 0
    bb["stages"] = [
        {
            "name": "in",
            "type": "bitlinear",
            "in": 4,
            "out": 4,
            "W_ternary": [[1, 0, -1, 0]] * 4,
            "scale": [1.0] * 4,
            "bias": [0.0] * 4,
        },
        {
            "name": "lat",
            "type": "bitlinear",
            "in": 4,
            "out": 2,
            "W_ternary": [[1, 0, 0, 0], [0, 1, 0, 0]],
            "scale": [1.0, 1.0],
            "bias": [0.0, 0.0],
        },
    ]
    bb["layernorm"] = True
    with pytest.raises(ValueError, match="layernorm"):
        BitLinearResBackbone.from_envelope(bb)


def test_bitlinear_rejects_stage_count_mismatch():
    bb = build_default_backbone_envelope(seed=1)
    bb["n_residual_blocks"] = 3  # stages still for N=2
    with pytest.raises(ValueError, match="stages length"):
        BitLinearResBackbone.from_envelope(bb)


def test_multi_head_research_adapter():
    env = build_synthetic_bitlinear_envelope(seed=9, multi_head=True)
    comp = load_bitlinear_composition(env)
    names = comp.metadata().feature_names
    feats = {n: 0.0 for n in names}
    pred = comp.predict(feats)
    assert "win_probability" in pred.heads
    assert "expected_rr" in pred.heads
    assert pred.adapter_id == "ad_research_full_v1"


def test_sigmoid_unit():
    assert math.isclose(sigmoid(0.0), 0.5, abs_tol=1e-12)
    assert sigmoid(100.0) > 0.99
    assert sigmoid(-100.0) < 0.01
