"""
config_builder.py
═══════════════════════════════════════════════════════════════════════════════
SINGLE SOURCE OF TRUTH for CRTConfig creation.

Architecture contract (EPIC-84, user rule 2026-09-28: no defaults, no fallbacks):
    Declared config (production registry / explicit field set) -> CRTConfig (frozen)
    A CRTConfig is built ONLY from a complete, declared field set. There is no router base
    filling unspecified fields from code any more: CRTConfig fields carry no defaults, and
    the market_router class profiles are partial, so they cannot be a base.

Rules enforced here:
  1. ALL config creation MUST go through ConfigBuilder (build / from_production / from_existing)
  2. Direct CRTConfig(...) instantiation is FORBIDDEN in application code
  3. CRTConfig is frozen after creation — no mutation allowed
  4. A missing field raises ConfigKeyMissingError naming every missing field
  5. Unknown instruments raise UnknownInstrumentError (market_router.classify_market)

Usage:
    from config_layer.config_builder import ConfigBuilder

    # Production config for an instrument, optionally with declared overrides (sweeps)
    cfg = ConfigBuilder.from_production("XAUUSD", overrides={"score_threshold": 0.50})

    # Complete explicit field set (the production loader's own path)
    cfg = ConfigBuilder.build("XAUUSD", overrides=every_field)

    # From an existing CRTConfig's fields (backtest replay pattern)
    cfg = ConfigBuilder.from_existing("EURUSD", existing_cfg)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from typing import Optional

from config_layer.state_identity import CRTConfig
from config_layer.market_router import classify_market
from config_layer.crt_config_provenance import ConstructionMode, stamp
from config_layer.strict_config import ConfigKeyMissingError


# ─────────────────────────────────────────────────────────────────────────────
# ALLOWED OVERRIDE KEYS
# Locked set — prevents typos and unknown-field injection.
# ─────────────────────────────────────────────────────────────────────────────

_ALLOWED_OVERRIDE_KEYS: frozenset[str] = frozenset(
    f.name for f in dataclasses.fields(CRTConfig)
)


class ConfigBuilder:
    """
    Central factory for CRTConfig.

    All application code must use this class.
    Direct CRTConfig(...) calls are forbidden outside this module.
    """

    @staticmethod
    def _complete(instrument: str, fields: dict, consumer: str) -> CRTConfig:
        """Fail closed: validate the instrument, require every CRTConfig field, construct."""
        classify_market(instrument)          # unknown instrument -> UnknownInstrumentError
        _validate_override_keys(fields)
        missing = sorted(_ALLOWED_OVERRIDE_KEYS - set(fields))
        if missing:
            raise ConfigKeyMissingError(
                missing, section="CRTConfig", consumer=consumer,
                source=f"instrument={instrument}",
            )
        return CRTConfig(**fields)

    @staticmethod
    def build(
        instrument: str,
        overrides: Optional[dict] = None,
        *,
        stamp_mode: ConstructionMode = ConstructionMode.ROUTER_BASE,
        stamp_version: Optional[str] = None,
        stamp_note: str = "ConfigBuilder.build → market_router class profile ± overrides",
    ) -> CRTConfig:
        """
        Build a validated, immutable CRTConfig from a COMPLETE declared field set.

        Parameters
        ----------
        instrument : str
            Trading instrument symbol (e.g. "EURUSD", "BTCUSDT"). Must be declared in
            market_router.symbol_map (UnknownInstrumentError otherwise).
        overrides : dict
            Every CRTConfig field (EPIC-84: no router base, no defaults). A missing field
            raises ConfigKeyMissingError; an unknown key raises ValueError. To start from the
            production config instead, use ConfigBuilder.from_production.
        stamp_mode : ConstructionMode
            P1 observe provenance (default ROUTER_BASE). Production loader passes
            PRODUCTION_MERGED so there is no intermediate false ROUTER warning.

        Returns
        -------
        CRTConfig
            Frozen, immutable config. Mutation attempts will raise FrozenInstanceError.

        Raises
        ------
        ValueError
            If any override key is not a valid CRTConfig field name.
        ConfigKeyMissingError
            If any CRTConfig field is not declared.
        """
        fields = dict(overrides or {})
        okeys: list[str] = list(fields.keys())
        base = ConfigBuilder._complete(instrument, fields, "ConfigBuilder.build")

        # P1 observe stamp (see CRT_CONFIG_CONSTRUCTION_PROTOCOL.md)
        stamp(
            base,
            stamp_mode,
            instrument=instrument,
            version=stamp_version,
            override_keys=okeys,
            note=stamp_note,
        )
        return base

    @staticmethod
    def from_existing(
        instrument: str,
        existing: CRTConfig,
        extra_overrides: Optional[dict] = None,
    ) -> CRTConfig:
        """
        Build a config starting from the router base, then layering in all
        non-default fields from an existing CRTConfig, then any extra overrides.

        Use this when replaying a backtest that stored its original config
        and you want to re-root it through the router.

        Parameters
        ----------
        instrument : str
            Target instrument — determines FOREX vs CRYPTO base.
        existing : CRTConfig
            Previously used config whose field values are carried forward
            as overrides on top of the router base.
        extra_overrides : dict | None
            Additional field overrides applied last (highest priority).
        """
        # Carry forward all fields from existing config as overrides
        existing_overrides = dataclasses.asdict(existing)

        # Strip keys not present in the current CRTConfig schema to guard
        # against TypeError when replaying checkpoints from older schema versions
        valid_fields = {f.name for f in dataclasses.fields(CRTConfig)}
        existing_overrides = {k: v for k, v in existing_overrides.items() if k in valid_fields}

        # Merge: existing fields first, then extra_overrides win
        if extra_overrides:
            _validate_override_keys(extra_overrides)
            existing_overrides.update(extra_overrides)

        # EPIC-84: the existing config is complete; construct from it (no router base).
        out = ConfigBuilder._complete(instrument, existing_overrides, "ConfigBuilder.from_existing")
        stamp(
            out,
            ConstructionMode.EXPLICIT,
            instrument=instrument,
            override_keys=list(existing_overrides.keys()),
            note="ConfigBuilder.from_existing — caller-owned complete field set",
        )
        return out

    @staticmethod
    def from_production(
        instrument: str,
        version: Optional[str] = None,
        overrides: Optional[dict] = None,
    ) -> CRTConfig:
        """Production config for ``instrument`` (``version`` or ACTIVE_VERSION), with optional
        declared overrides on top. The base is a declared config file, never code.

        Replaces the old bare ``ConfigBuilder.build(instrument)`` router-base path (EPIC-84).
        """
        from config_layer.production_config import (
            get_active_version,
            load_prod_config_from_registry,
        )

        ver = version or get_active_version()
        prod = load_prod_config_from_registry(ver, instrument)
        if not overrides:
            return prod
        _validate_override_keys(overrides)
        out = replace(prod, **overrides)
        stamp(
            out,
            ConstructionMode.EXPLICIT,
            instrument=instrument,
            version=ver,
            override_keys=list(overrides.keys()),
            note="ConfigBuilder.from_production — production config ± declared overrides",
        )
        return out

    @staticmethod
    def market_type(instrument: str) -> str:
        """Return the market classification for an instrument ('FOREX' or 'CRYPTO')."""
        return classify_market(instrument)

    @staticmethod
    def validate_divergence(
        forex_instrument: str = "EURUSD",
        crypto_instrument: str = "BTCUSDT",
    ) -> dict:
        """
        Build configs for one FOREX and one CRYPTO instrument and return
        a comparison dict. Used for validation / smoke-testing.

        Returns
        -------
        dict with keys: forex_cfg, crypto_cfg, divergence_fields
            divergence_fields is a dict of field_name → (forex_val, crypto_val)
            for every field that differs between the two configs.
        """
        forex_cfg  = ConfigBuilder.from_production(forex_instrument)
        crypto_cfg = ConfigBuilder.from_production(crypto_instrument)

        forex_dict  = dataclasses.asdict(forex_cfg)
        crypto_dict = dataclasses.asdict(crypto_cfg)

        divergence = {
            k: (forex_dict[k], crypto_dict[k])
            for k in forex_dict
            if forex_dict[k] != crypto_dict[k]
        }

        return {
            "forex_instrument":  forex_instrument,
            "crypto_instrument": crypto_instrument,
            "forex_cfg":         forex_cfg,
            "crypto_cfg":        crypto_cfg,
            "divergence_fields": divergence,
        }


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _validate_override_keys(overrides: dict) -> None:
    """Raise ValueError if any key is not a known CRTConfig field."""
    unknown = set(overrides.keys()) - _ALLOWED_OVERRIDE_KEYS
    if unknown:
        raise ValueError(
            f"ConfigBuilder: unknown override key(s): {sorted(unknown)}. "
            f"Valid keys: {sorted(_ALLOWED_OVERRIDE_KEYS)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION ENTRYPOINT (run directly to verify divergence)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("  ConfigBuilder — Forex vs Crypto Divergence Proof")
    print("═" * 60)

    result = ConfigBuilder.validate_divergence("EURUSD", "BTCUSDT")

    print(f"\n  FOREX  instrument : {result['forex_instrument']}")
    print(f"  CRYPTO instrument : {result['crypto_instrument']}")
    print(f"\n  {'Field':<35} {'FOREX':>12}  {'CRYPTO':>12}")
    print(f"  {'─'*35} {'─'*12}  {'─'*12}")

    for field_name, (forex_val, crypto_val) in sorted(result["divergence_fields"].items()):
        print(f"  {field_name:<35} {str(forex_val):>12}  {str(crypto_val):>12}")

    print(f"\n  ✅ expansion_atr_min_distance:")
    print(f"     EURUSD  → {result['forex_cfg'].expansion_atr_min_distance}")
    print(f"     BTCUSDT → {result['crypto_cfg'].expansion_atr_min_distance}")
    assert result["forex_cfg"].expansion_atr_min_distance != \
           result["crypto_cfg"].expansion_atr_min_distance, \
        "DIVERGENCE FAILURE — Forex and Crypto configs are identical!"

    print(f"\n  ✅ Immutability check:")
    try:
        import dataclasses as _dc
        cfg = ConfigBuilder.from_production("EURUSD")
        cfg.score_threshold = 0.99          # real application-code mutation attempt
        print("  ❌ FAILED — config is mutable!")
    except (_dc.FrozenInstanceError, AttributeError):
        frozen_ok = cfg.__dataclass_params__.frozen
        print(f"  ✅ PASSED — FrozenInstanceError raised (frozen={frozen_ok})")

    print(f"\n  ✅ Unknown override key guard:")
    try:
        ConfigBuilder.from_production("EURUSD", overrides={"nonexistent_param": 99})
        print("  ❌ FAILED — unknown key accepted!")
    except ValueError as e:
        print(f"  ✅ PASSED — ValueError: {e}")

    print("\n" + "═" * 60 + "\n")
