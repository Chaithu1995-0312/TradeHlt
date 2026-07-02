"""Market-type CRT config profiles (crypto/forex) and the profile router."""

from dataclasses import dataclass
from typing import Dict
from config_layer.crt_engine_v2 import CRTConfig


# ─────────────────────────────────────────────
# 1. MARKET PROFILES
# ─────────────────────────────────────────────

CRYPTO_CONFIG = {
    "retest_depth_max": 0.25,
    "retest_atr_depth_fraction": 0.3,
    "body_ratio_min": 0.5,
    "atr_multiplier_min": 1.0,
    "expansion_atr_min_distance": 0.15,
}

FOREX_CONFIG = {
    "retest_depth_max": 0.35,
    "retest_atr_depth_fraction": 0.5,
    "body_ratio_min": 0.6,
    "atr_multiplier_min": 1.5,
    "expansion_atr_min_distance": 0.08,
}


# ─────────────────────────────────────────────
# 2. CLASSIFIER
# ─────────────────────────────────────────────

CRYPTO_SYMBOLS = {"BTCUSDT", "ETHUSDT"}
FOREX_SYMBOLS  = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCHF"}

def classify_market(instrument: str) -> str:
    if instrument in CRYPTO_SYMBOLS:
        return "CRYPTO"
    elif instrument in FOREX_SYMBOLS:
        return "FOREX"
    else:
        return "FOREX"  # safe default


# ─────────────────────────────────────────────
# 3. ROUTER
# ─────────────────────────────────────────────

def get_crt_config(instrument: str) -> CRTConfig:
    """
    INTERNAL USE ONLY — called exclusively by config_builder.ConfigBuilder.build().

    Direct calls from application code are FORBIDDEN.
    Use ConfigBuilder.build(instrument) instead.
    """
    import traceback
    stack = traceback.extract_stack()
    # Allow calls only from config_builder.py
    callers = [frame.filename for frame in stack]
    if not any("config_builder" in f for f in callers):
        raise RuntimeError(
            "Direct get_crt_config() usage is FORBIDDEN.\n"
            "Use: from config_builder import ConfigBuilder\n"
            "     cfg = ConfigBuilder.build(instrument)"
        )

    market_type = classify_market(instrument)

    if market_type == "CRYPTO":
        cfg = CRYPTO_CONFIG
    else:
        cfg = FOREX_CONFIG

    return CRTConfig(**cfg)
