"""
pattern_hasher.py
================================================================================
Stable pattern identification utilities for CRT trade replay and memory.

Exports
-------
compute_pattern_hash   SHA-256[:16] from key decision inputs at RETEST time.
encode_crt_path        Compress list[CRTTransitionEvent] to compact char codes.
decode_crt_path        Expand compact char codes back to full state names.
_CRT_PATH_CODES        Single source of truth for state → char mapping.

Ownership
---------
Single import point for TradeRecord (at close), ReplayRecord (on load),
Collector (in strategy dict), and analytics / UI.
No dependency on BacktestRunner, strategy files, or runtime context.
================================================================================
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import CRTTransitionEvent  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# State → compact char mapping — single source of truth
# ─────────────────────────────────────────────────────────────────────────────

_CRT_PATH_CODES: dict[str, str] = {
    "RANGE":        "R",
    "SWEEP":        "S",
    "DISPLACEMENT": "D",
    "EXPANSION":    "E",
    "RETEST":       "T",
    "EXECUTION":    "X",
    "RESOLUTION":   "Z",
}

_CRT_PATH_DECODE: dict[str, str] = {v: k for k, v in _CRT_PATH_CODES.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Path encoding / decoding
# ─────────────────────────────────────────────────────────────────────────────

def encode_crt_path(path: "List[CRTTransitionEvent]") -> List[str]:
    """Compress a list of CRTTransitionEvent to compact single-char codes.

    Example output: ["S", "D", "T", "X"]
    Unknown state names fall back to the first character of `to_state`.

    Parameters
    ----------
    path    Output of `recent_transition_path(engine.state)`.

    Returns
    -------
    List of single-character strings, one per transition.
    """
    return [
        _CRT_PATH_CODES.get(t.to_state, t.to_state[:1] if t.to_state else "?")
        for t in path
    ]


def decode_crt_path(codes: List[str]) -> List[str]:
    """Expand compact char codes back to full state names.

    Example input:  ["S", "D", "T", "X"]
    Example output: ["SWEEP", "DISPLACEMENT", "RETEST", "EXECUTION"]

    Unknown codes are returned unchanged.
    """
    return [_CRT_PATH_DECODE.get(c, c) for c in codes]


# ─────────────────────────────────────────────────────────────────────────────
# Pattern hash
# ─────────────────────────────────────────────────────────────────────────────

def compute_pattern_hash(
    features: dict,
    sweep_type: Optional[str] = None,
) -> str:
    """Stable SHA-256[:16] fingerprint from CRT decision inputs at RETEST.

    Design choices
    --------------
    - `regime` is included so the same geometric setup in TRENDING vs RANGING
      is treated as distinct populations in the expectancy table.
    - `pattern_schema: "v1"` is a version stamp — future field additions will
      not corrupt existing cluster memberships (bump to "v2" when fields change).
    - Fields are rounded to reduce hash churn from floating-point noise.
    - `sort_keys=True` ensures deterministic JSON serialisation.

    Parameters
    ----------
    features    Feature dict at RETEST time (subset of CANONICAL_FEATURES).
                Missing keys fall back to safe defaults — backward compatible.
    sweep_type  Optional sweep type string ("TYPE-A" | "TYPE-B" | ...).
                If None, falls back to `features.get("sweep_type", "")`.

    Returns
    -------
    16-character lowercase hex string (64-bit collision resistance).
    """
    _sweep = sweep_type or str(features.get("sweep_type") or "")
    key_fields = {
        "pattern_schema": "v1",
        "body_ratio":     round(float(features.get("body_ratio",    0.0)), 2),
        "retest_depth":   round(float(features.get("retest_depth",  0.0)), 2),
        "disp_strength":  round(float(features.get("disp_strength", 0.0)), 1),
        "session":        str(features.get("session",    "UNKNOWN")),
        "sweep_type":     _sweep,
        "double_sweep":   bool(features.get("double_sweep", False)),
        "regime":         str(features.get("_regime",    "UNKNOWN")),
    }
    return hashlib.sha256(
        json.dumps(key_fields, sort_keys=True).encode()
    ).hexdigest()[:16]
