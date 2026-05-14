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
        # Canonical: 0=ASIA, 1=LONDON, 2=NEWYORK
        # Legacy: "asia", "london", "new_york"
        session_map = {
            0: "asia",
            1: "london",
            2: "new_york",
            "asia": "asia",
            "london": "london",
            "new_york": "new_york",
            "newyork": "new_york",
        }

        # Handle numeric session values that may arrive as floats (e.g. 0.0).
        if isinstance(session, (int, float)):
            try:
                s_int = int(session)
                session_key = session_map.get(s_int, session)
            except Exception:
                session_key = session
        else:
            session_key = session_map.get(session, str(session).strip().lower())
        
        if session_key not in self.allowed_sessions:
            return {"score": 0.0, "reason": f"invalid_session:{session}"}

        return {"score": 1.0, "reason": "pass"}
