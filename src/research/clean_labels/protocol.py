"""Frozen experiment identity for the dual TradeNet + EnvelopeNet clean-label builder.

Changing any field in FREEZE requires a new protocol_id (non-transferable GATE-O evidence).

Epoch history:
  TN_ENV_CLEAN_L1 — SURROGATE_2R_BEFORE_SL (SUPERSEDED for new work: unit TP≡2R on BNB → TP1≡TP2)
  TN_ENV_CLEAN_L2 — STRETCH_3R_BEFORE_SL (TP2 = hit +3R before SL; unit TP remains y_tp1)
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

PROTOCOL_ID = "TN_ENV_CLEAN_L2"
"""Shared GATE-L / ENV-L clean-label epoch after TP2 repair."""

PROTOCOL_ID_SUPERSEDED = "TN_ENV_CLEAN_L1"

# ── TP2 policy freeze ───────────────────────────────────────────────────────
# Population has no tp2 field; unit TP on BNBUSDT opportunities is exactly 2R
# (measured 2026-07-22). L1 SURROGATE_2R therefore collapsed onto y_tp1.
# L2: y_tp2 = governing walk with TP=+3R (stretch beyond unit target).
TP2_POLICY = "STRETCH_3R_BEFORE_SL"
TP2_ATR_MULT = 3.0

EXIT_MODEL = "intrabar_fixed"
MAX_FORWARD = 40
COST_BPS = 12.0  # round-trip; used only for diagnostic y_R_net
MIN_SAMPLES_TRAIN_ELIGIBLE = 500
PIT_STATUS = "PIT_UNCLEAN_STORED_FEATURES"
# Stored opportunity features may predate FC1-A causal swings (F-051). Declared
# honestly: GATE-P forbidden on this pit_status until re-emit path is proven.

FEATURE_DIM = 38
TIMEFRAME = "M15"

# Inference composite (not a train head) — frozen weights match TradeNetV2 shape.
# Meanings under L2: p_tp1=unit TP, p_tp2=stretch 3R, p_survives_be=path ≥1R MFE.
COMPOSITE_WEIGHTS = (0.4, 0.4, 0.2)  # p_tp1, p_tp2, p_survives_be


def freeze_block() -> dict[str, Any]:
    """Machine-readable freeze payload (hashed into protocol_hash)."""
    return {
        "protocol_id": PROTOCOL_ID,
        "supersedes": PROTOCOL_ID_SUPERSEDED,
        "tp2_policy": TP2_POLICY,
        "tp2_atr_mult": TP2_ATR_MULT,
        "exit_model": EXIT_MODEL,
        "max_forward": MAX_FORWARD,
        "cost_bps": COST_BPS,
        "min_samples_train_eligible": MIN_SAMPLES_TRAIN_ELIGIBLE,
        "pit_status": PIT_STATUS,
        "feature_dim": FEATURE_DIM,
        "timeframe": TIMEFRAME,
        "composite_weights": list(COMPOSITE_WEIGHTS),
        "label_defs": {
            "y_tp1": "forward_walk(intrabar_fixed) with unit TP geometry → TP_HIT",
            "y_tp2": "forward_walk(intrabar_fixed) with TP=+3R (STRETCH_3R_BEFORE_SL) → TP_HIT",
            "y_survives_be": "primary walk Outcome.reached_1r (path MFE >= 1R before/at exit)",
            "y_R_net": "primary walk rr_achieved - cost_r (diagnostic)",
            "y_mfe_r": "horizon_excursion mfe_r (exit-agnostic)",
            "y_mae_r_heat": "abs(horizon_excursion mae_r)",
            "y_holding_bars": "primary walk duration_candles",
            "y_time_to_mfe": "bars until primary-path MFE first attained (within max_forward)",
            "y_time_to_1r": "horizon_excursion bars_to_first_1r",
            "y_expired_timeout": "1 if primary walk outcome == TIMEOUT",
            "tp1_reward_mult": "diagnostic: |tp1-entry|/risk (expected ≈2.0 on BNBUSDT stream)",
        },
        "forbidden_primary_y": [
            "stream.outcome",
            "stream.rr_achieved",
            "stream.mfe as sole survives_be",
        ],
        "tp2_repair": {
            "reason": "L1 SURROGATE_2R identical to unit TP (always 2R on BNB opportunities)",
            "evidence": "docs/governance/tp2_label_repair_report.md",
        },
        "authority": "research_dataset_only",
    }


def compute_protocol_hash(extra: dict[str, Any] | None = None) -> str:
    """Stable SHA-256 over freeze_block (+ optional instrument scope)."""
    payload = freeze_block()
    if extra:
        payload = {**payload, "extra": extra}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
