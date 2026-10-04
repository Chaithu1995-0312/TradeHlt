"""
label_contracts.py
==================
Versioned BitNet label definitions (CONTRACT-C).
"""
from __future__ import annotations

from typing import Any, Dict

# ── Registry ──────────────────────────────────────────────────────────────────

LABEL_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "BITNET_LABEL_ATR_RACE_BULL_V1": {
        "label_contract_id": "BITNET_LABEL_ATR_RACE_BULL_V1",
        "economic_authority": "DIAGNOSTIC_ONLY",
        "direction_scope": "bullish_only",
        "definition": (
            "Win if high reaches close+tp_atr_mult·ATR before low reaches "
            "close−sl_atr_mult·ATR within max_fwd bars; loss if SL first; "
            "timeouts dropped (no gradient)."
        ),
        "tp_atr_mult": 2.0,
        "sl_atr_mult": 1.0,
        "max_fwd": 40,
        "timeout_policy": "drop",
        "notes": (
            "Synthetic ATR race — not M4 journal expectancy; "
            "not CRT_ELIGIBLE_CANDIDATE without re-derive."
        ),
    },
}


def get_label_contract(label_contract_id: str) -> Dict[str, Any]:
    if label_contract_id not in LABEL_CONTRACTS:
        raise KeyError(
            f"Unknown label_contract_id={label_contract_id!r}. "
            f"Known: {sorted(LABEL_CONTRACTS)}"
        )
    return dict(LABEL_CONTRACTS[label_contract_id])
