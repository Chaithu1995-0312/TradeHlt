"""
defaults.py
===========
Versioned numeric defaults for BitNet backbone family (Spec v1.2.1 L2).

These are NOT architectural laws. Artifacts must self-describe actual dims.
"""
from __future__ import annotations

# Architecture family (L1)
BACKBONE_FAMILY_ID = "bb_bitlinear_res_v1"
DEFAULTS_PROFILE = "bitlinear_res_defaults_v1"

# Encoder / input
ENC_LEGACY6_ID = "enc_legacy6_v1"
ENC_CANONICAL38_ID = "enc_canonical38_v1"
LEGACY6_KEYS = (
    "body_ratio",
    "retest_depth",
    "disp_strength",
    "atr",
    "candles_since_retest",
    "double_sweep",
)

# Backbone defaults (L2)
DEFAULT_INPUT_DIM = 38
DEFAULT_HIDDEN_DIM = 64
DEFAULT_LATENT_DIM = 32
DEFAULT_N_RESIDUAL_BLOCKS = 2
DEFAULT_BIAS = True
DEFAULT_EMBEDDING_DIM = 0  # off

# Component ids
BB_LEGACY_MLP_ID = "bb_legacy_mlp_6_16_8_v1"
BB_BITLINEAR_RES_ID = BACKBONE_FAMILY_ID
HD_CONFIDENCE_ID = "hd_confidence_sigmoid_v1"
HD_MULTI_ID = "hd_multi_conf_win_rr_emb_v1"
AD_CRT_GATE_ID = "ad_crt_gate_v1"
AD_IDENTITY_ID = "ad_identity_v1"
AD_RESEARCH_ID = "ad_research_full_v1"

# CRT serve map keys (adapter documentation; values remapped into legacy names)
CRT_SERVE_MAP = (
    ("displacement_retrace", "retest_depth", "FM-027", "legacy"),
    ("displacement_atr_ratio", "disp_strength", "FM-028", "legacy"),
)

ACTIVATION_ID = "hardtanh_m1_p1"
RESIDUAL_ID = "post_act_add"
QUANTIZATION_ID = "ternary_per_out_scale"
