"""
FeatureBuilder — constructs the canonical input_data dict from raw tick/row data.

DATA INTEGRITY POLICY (enforced):
- Raw OHLCV fields are mandatory; ValueError raised if missing.
- Derived fields (atr, ema_fast, ema_slow, rsi) are mandatory; NO synthetic
  defaults are injected. Missing derived fields raise ValueError.
- session defaults to "unknown" so the adapter's session-whitelist check will
  reject it rather than silently accepting it.
- A sentinel field "_data_integrity" = "real" is added only when all required
  fields are confirmed present from the raw input.
"""

import logging

logger = logging.getLogger(__name__)


def feature_dict_to_vector(features: dict) -> list:
    """
    Convert a canonical feature dict to a CANONICAL_FEATURE_DIM-length float vector.

    COMPATIBILITY SHIM — the canonical implementation lives in
    dataset_builder.extract_feature_vector(). Use that directly for new code.

    Parameters
    ----------
    features : dict with all CANONICAL_FEATURES keys present as floats

    Returns
    -------
    list of CANONICAL_FEATURE_DIM floats in CANONICAL_FEATURE_ORDER
    (48 under schema v5.0, F-076; this docstring said "32" from the v2.0 era — the length is
    whatever the schema declares, never a literal in a caller.)
    """
    from features.dataset_builder import extract_feature_vector
    return extract_feature_vector(features)


REQUIRED_RAW_FIELDS = ["close", "high", "low", "open", "volume"]
REQUIRED_DERIVED_FIELDS = ["atr", "ema_fast", "ema_slow", "rsi"]


class FeatureBuilder:
    def __init__(self, config: dict):
        self.config = config
        # T-8 (2026-07-20): removed dead soft-default attrs
        #   self.ema_fast_period = config.get("ema_fast_period", 9)
        #   self.ema_slow_period = config.get("ema_slow_period", 21)
        # Those attributes were NEVER read by build() or any caller (module is a
        # validation shim only — it accepts pre-computed ema_fast/ema_slow values).
        # Soft defaults under the non-canonical key names `ema_fast_period` /
        # `ema_slow_period` were a latent trap next to the live HOW keys
        # feature_pipeline.ema_fast_span / ema_slow_span (T-1). Period authority
        # lives only in configs/production feature_pipeline.*; this builder must
        # not invent a second source.

    def build(self, raw: dict) -> dict:
        # --- Step 1: Validate raw OHLCV fields ---
        missing_raw = [f for f in REQUIRED_RAW_FIELDS if f not in raw]
        if missing_raw:
            raise ValueError(f"FeatureBuilder: missing raw fields {missing_raw}")

        result = {k: raw[k] for k in REQUIRED_RAW_FIELDS}

        # --- Step 2: Validate derived / indicator fields (NO DEFAULTS) ---
        missing_derived = [f for f in REQUIRED_DERIVED_FIELDS if f not in raw]
        if missing_derived:
            raise ValueError(
                f"FeatureBuilder: missing required feature(s) {missing_derived}. "
                "Synthetic defaults are not permitted — supply pre-computed indicators."
            )

        result["atr"] = raw["atr"]
        result["ema_fast"] = raw["ema_fast"]
        result["ema_slow"] = raw["ema_slow"]
        result["rsi"] = raw["rsi"]

        # --- Step 3: Session — intentionally NO safe default ---
        # "unknown" is NOT in the adapter's allowed_sessions list, so the adapter
        # will reject rows where session is absent rather than silently accepting.
        result["session"] = raw.get("session", "unknown")

        # symbol is used by BitNet zone lookup; "default" is unlikely in registry.
        result["symbol"] = raw.get("symbol", "default")

        # --- Step 4: Data integrity sentinel ---
        result["_data_integrity"] = "real"

        return result