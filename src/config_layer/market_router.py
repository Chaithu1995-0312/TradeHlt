"""Market-type CRT config profiles (crypto/forex) and the profile router.

Config-driven (2026-07-29, target-strategy-architecture.md §13 item 1 / F-057).
Class profiles + the instrument -> class map used to live as Python literals
here; they now live in the active production config's `market_router` section
(configs/production/<ACTIVE_VERSION>.json). Two problems this closes:

  1. Any truly-unmapped instrument used to silently fall back to the FOREX
     profile ("safe default") — a class of bug docs/governance/
     crt_config_reachability.json already caught for BNBUSDT/SOLUSDT
     (`bnb_market_class_bug`, MED — crypto majors misclassified FOREX).
     `classify_market()` now raises `UnknownInstrumentError` instead.
  2. The class profiles themselves were hardcoded, so retuning them required
     a code edit + redeploy instead of a config change (CLAUDE.md §6.5
     Config-First doctrine — these are BEHAVIORAL thresholds, not structure).

`_leading_symbol_token()` tolerates filename-derived instrument hints (e.g.
"XAUUSD_M15", "XAUUSD_W2026-03-23-to-2026-05-21" — see backtest_v2.py's
`cfg.instrument = csv_path.stem.upper()` and
runtime.unified_replay_harness._derive_symbol_from_data_path) by matching on
the token before the first underscore. This is NOT a safe-default fallback:
if neither the raw token nor the leading token resolves, classify_market
still raises. No silent Fall Back (CLAUDE.md §11.3 doctrine).

Deferred import of production_config avoids a circular import
(production_config -> config_builder -> market_router -> production_config).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from config_layer.state_identity import CRTConfig


class UnknownInstrumentError(ValueError):
    """Raised when an instrument has no entry (direct or leading-symbol-token)
    in the active config's `market_router.symbol_map`. There is no safe
    default — add the instrument to
    configs/production/<ACTIVE_VERSION>.json `market_router.symbol_map`."""


def _load_router_cfg() -> dict:
    from config_layer.production_config import get_prod_section
    return get_prod_section("market_router")


def _leading_symbol_token(instrument: str) -> str:
    """Return the symbol before the first underscore, uppercased.

    Filename-derived instrument hints carry the real symbol before the first
    underscore (e.g. "XAUUSD_M15" -> "XAUUSD"). Returns the whole token
    unchanged when there is no underscore.
    """
    token = str(instrument).strip().upper()
    return token.split("_", 1)[0] if "_" in token else token


def classify_market(instrument: str) -> str:
    """Return the market class (e.g. "FOREX" / "CRYPTO") for `instrument`.

    Raises UnknownInstrumentError if the instrument (or its leading symbol
    token) is not declared in market_router.symbol_map.
    """
    cfg = _load_router_cfg()
    symbol_map: Dict[str, str] = cfg["symbol_map"]

    token = str(instrument).strip().upper()
    if token in symbol_map:
        return symbol_map[token]

    base = _leading_symbol_token(instrument)
    if base in symbol_map:
        return symbol_map[base]

    raise UnknownInstrumentError(
        f"classify_market: instrument {instrument!r} (token={token!r}, "
        f"leading_symbol={base!r}) has no entry in market_router.symbol_map. "
        f"Known symbols: {sorted(symbol_map)}. Add it to "
        "configs/production/<ACTIVE_VERSION>.json market_router.symbol_map — "
        "no safe default is applied (F-057)."
    )


# ─────────────────────────────────────────────
# ROUTER
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
    cfg = _load_router_cfg()
    classes: Dict[str, dict] = cfg["classes"]
    if market_type not in classes:
        raise UnknownInstrumentError(
            f"market_router.classes has no profile for class {market_type!r} "
            f"(instrument={instrument!r}). Known classes: {sorted(classes)}. "
            "Add it to configs/production/<ACTIVE_VERSION>.json market_router.classes."
        )
    return CRTConfig(**classes[market_type])
