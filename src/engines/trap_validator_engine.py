"""
TrapValidatorEngine — data integrity validator and pre-gating layer.

Validates whether market conditions meet the structural preconditions
for a trade to be considered. Returns score=0.0 to block, score=1.0 to pass.

DATA INTEGRITY POLICY (enforced):
- Rejects any input_data dict that was NOT produced by FeatureBuilder with
  real data (checked via the "_data_integrity" sentinel field).
- Rejects if atr <= 0 (catches both zero and negative values, not just < min_atr).
- All required fields must be present; missing fields are an immediate hard reject.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# CANONICAL-FIRST: Accept both canonical (int) and legacy (string) session
# Canonical session: 0=ASIA, 1=LONDON, 2=NEWYORK
# Legacy session: "asia", "london", "new_york"
CANONICAL_REQUIRED = [
    "close", "high", "low", "open", "volume",
    "atr", "ema_fast", "ema_slow", "session",
]
# Optional CRT features (used by ZoneGate/CRT scoring but not required for gating)
CRT_OPTIONAL = ["body_ratio", "disp_strength", "retest_depth"]


class TrapValidatorEngine:
    def __init__(self, config: dict):
        self.config = config
        self.min_atr = config.get("min_atr", 0.0005)
        self.allowed_sessions = config.get("allowed_sessions", ["asia", "london", "new_york"])

    def compute(self, input_data: dict) -> dict:
        # --- Gate 0: Data integrity sentinel ---
        if input_data.get("_data_integrity") != "real":
            return {"score": 0.0, "reason": "data_integrity_failed"}

        # --- Gate 1: Required field presence (canonical) ---
        missing = [f for f in CANONICAL_REQUIRED if f not in input_data]
        if missing:
            logger.warning(f"TrapValidator: missing fields {missing}")
            return {"score": 0.0, "reason": f"missing_fields:{missing}"}

        atr = input_data["atr"]
        session = input_data["session"]

        # --- Gate 2: ATR must be positive and meet minimum ---
        if atr <= 0:
            return {"score": 0.0, "reason": f"non_positive_atr:{atr}"}

        if atr < self.min_atr:
            return {"score": 0.0, "reason": f"low_atr:{atr}"}

        # --- Gate 3: Session whitelist (accept both int and string) ---
        # Routed through features.session_classifier — the single owner of session semantics.
        #
        # v4.0 FIX (2026-07-22). This gate carried its own private map:
        #     {0: "asia", 1: "london", 2: "new_york", "newyork": "new_york", ...}
        # which knew only the three v3.0 ordinals. When FM-052 gained OVERLAP(3) and CLOSED(4),
        # `session_map.get(3, 3)` fell through to the raw `3`, which is not in `allowed_sessions`,
        # so every OVERLAP bar was rejected as `invalid_session:3.0` — even though "overlap" IS an
        # allowed session. That silently cost 6 of 13 BNBUSDT setups before a ledger diff caught it.
        #
        # Comparing CANONICAL NAMES on both sides also removes the spelling trap this map encoded:
        # the config says "new_york", the enum says NEWYORK, and older records say "newyork".
        # Normalising both sides means a spelling can never again decide a trade.
        from features.session_classifier import canonical_session_name, decode_session_ordinal

        if isinstance(session, (int, float)) and not isinstance(session, bool):
            try:
                session_key = decode_session_ordinal(session)
            except ValueError:
                # Out-of-domain ordinal (a v3 record replayed under v4, or a future value).
                # Reject loudly rather than guess, and say WHY — this is a schema problem, not a
                # session-policy block, and the two must not look alike in the rejection stream.
                return {"score": 0.0, "reason": f"unknown_session_ordinal:{session}"}
        else:
            session_key = canonical_session_name(session)

        allowed = {canonical_session_name(s) for s in self.allowed_sessions}
        allowed.discard(None)

        if session_key is None or session_key not in allowed:
            return {"score": 0.0, "reason": f"invalid_session:{session}"}

        return {"score": 1.0, "reason": "pass"}
