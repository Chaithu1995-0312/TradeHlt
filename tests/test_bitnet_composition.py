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
from bitnet.encoders import Canonical38Encoder, Legacy6Encoder, apply_crt_serve_aliases
from features.feature_schema import CANONICAL_FEATURES
from bitnet.layers import sigmoid


LEGACY_KEYS = [
    "body_ratio",
    "retest_depth",
    "disp_strength",
    "atr",
    "candles_since_sweep",
    "double_sweep",
]


def _legacy_features(seed: float = 0.1) -> dict:
    return {
        "body_ratio": 0.55 + seed,
        "retest_depth": 0.2 + seed * 0.1,
        "disp_strength": 1.1 + seed,
        "atr": 12.5 + seed,
        "candles_since_sweep": 3.0,
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
        "candles_since_sweep": 2,
        "double_sweep": 1.0,
    }
    mapped = apply_crt_serve_aliases(raw)
    assert mapped["retest_depth"] == 0.25
    assert mapped["disp_strength"] == 1.5
    assert mapped["atr"] == 10.0


def test_crt_serve_aliases_fm070_candles_since_retest_state():
    """The 4th rename (2026-09-23 fix): FM-070's emitted key is
    ``candles_since_retest_state`` (see crt_engine_v2.py), not ``candles_since_sweep``
    (LEGACY6_KEYS). Before this fix, apply_crt_serve_aliases silently dropped this
    rename and Legacy6Encoder.encode raised KeyError('candles_since_sweep')."""
    raw = {
        "body_ratio": 0.6,
        "displacement_retrace": 0.25,
        "displacement_atr_ratio": 1.5,
        "atr_abs": 10.0,
        "candles_since_retest_state": 4.0,
        "double_sweep": 1.0,
    }
    mapped = apply_crt_serve_aliases(raw)
    assert mapped["candles_since_sweep"] == 4.0


def test_crt_serve_aliases_does_not_overwrite_existing_candles_since_sweep():
    """If a caller already supplies the canonical key directly, the FM-070 alias
    must not clobber it (same not-in-out guard as the other three renames)."""
    raw = {
        "candles_since_sweep": 9.0,
        "candles_since_retest_state": 4.0,
    }
    mapped = apply_crt_serve_aliases(raw)
    assert mapped["candles_since_sweep"] == 9.0


def test_use_bitnet_true_end_to_end_no_keyerror(legacy_model_path, monkeypatch):
    """End-to-end use_bitnet=true serve path (the missing test that let the FM-070
    KeyError through, per the 2026-09-23 gap audit). Builds the feature dict exactly
    as crt_engine_v2.py's compute_score/approve BitNet call sites do — state.cached_features
    plus atr_abs and the FM-070 bars-since-sweep quantity under its real emitted key —
    and drives it through the production facade (bitnet_score -> get_default_composition
    -> Legacy6Encoder, with apply_crt_serve_aliases applied by the composition itself).
    Asserts no KeyError and a finite [0, 1] confidence. Grants no authority — use_bitnet
    stays false on every production config; this only proves the enable path no longer
    crashes if ever flipped on."""
    reset_default_composition()
    from bitnet import composition as comp_mod

    monkeypatch.setattr(
        comp_mod,
        "get_default_composition",
        lambda model_path=legacy_model_path: load_legacy_composition(legacy_model_path),
    )

    # Shape matches crt_engine_v2.py:2170-2190 / :2252-2262 exactly:
    #   features = state.cached_features.copy(); features["atr"] = state.atr_abs;
    #   features["candles_since_retest_state"] = FM-070(...)
    # cached_features carries the canonical (pre-v6.0-rename-agnostic) engine names.
    crt_cached_features = {
        "body_ratio": 0.62,
        "double_sweep": 0.0,
        "displacement_retrace": 0.30,
        "displacement_atr_ratio": 1.1,
    }
    features = dict(crt_cached_features)
    features["atr"] = 12.5  # state.atr_abs
    features["candles_since_retest_state"] = 3.0  # FM-070(...)

    score = bitnet_score(features)
    assert 0.0 <= score <= 1.0
    reset_default_composition()


def test_canonical38_encoder_dim_pinned_to_live_schema():
    """Gap 2 guard (2026-09-23): enc_canonical38_v1's id says 38 but Canonical38Encoder()
    (default feature_names=None) must always resolve to the LIVE canonical schema, so a future
    schema bump that silently breaks this id<->dim binding fails loudly here instead of
    re-drifting the way the id itself already has (P3: identity by name, not by hope)."""
    enc = Canonical38Encoder()
    assert enc.dim() == len(CANONICAL_FEATURES)
    assert enc.id() == "enc_canonical38_v1"  # id is pinned (misleading, documented), not renamed


def test_canonical38_encoder_explicit_38dim_bundle_still_binds_at_38():
    """An old R2.5-style bundle that declares its OWN 38-length feature_names must still bind
    at exactly 38 (never silently widened to the live 48-dim schema) — this is what makes the
    fail-closed width check in load_bitlinear_composition meaningful."""
    names_38 = [f"f{i}" for i in range(38)]
    enc = Canonical38Encoder(feature_names=names_38)
    assert enc.dim() == 38
    feats = {n: float(i) for i, n in enumerate(names_38)}
    out = enc.encode(feats)
    assert out.dim == 38


def test_r25_38dim_bundle_still_fails_closed_on_backbone_width_mismatch():
    """Gap 2 regression guard: an explicit 38-dim R2.5-style encoder against a differently-sized
    backbone must still refuse at composition.py's encoder.dim() != backbone.input_dim check —
    never silently padded or truncated to make the dims agree.

    build_synthetic_bitlinear_envelope() auto-corrects a feature_names/input_dim length
    mismatch (test-helper convenience), so the envelope is built by hand here to actually reach
    load_bitlinear_composition's real fail-closed check rather than the helper's silent repair.
    """
    env = build_synthetic_bitlinear_envelope(input_dim=8, feature_names=[f"f{i}" for i in range(8)])
    env["encoder"]["feature_names"] = [f"f{i}" for i in range(38)]  # deliberate mismatch vs backbone's input_dim=8
    with pytest.raises(ValueError, match="encoder dim"):
        load_bitlinear_composition(env)


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
