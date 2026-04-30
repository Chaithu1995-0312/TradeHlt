"""
config_builder.py
═══════════════════════════════════════════════════════════════════════════════
SINGLE SOURCE OF TRUTH for CRTConfig creation.

Architecture contract:
    Instrument → market_router.get_crt_config() → Base CRTConfig
              → Optional Override Layer (via dataclasses.replace)
              → Final CRTConfig (immutable — frozen=True)

Rules enforced here:
  1. ALL config creation MUST go through ConfigBuilder.build()
  2. Direct CRTConfig(...) instantiation is FORBIDDEN in application code
  3. CRTConfig is frozen after creation — no mutation allowed
  4. Overrides are applied via dataclasses.replace (type-safe, immutable-safe)
  5. Unknown instruments default to FOREX profile (safe default in router)

Usage:
    from config_builder import ConfigBuilder

    # Instrument-only (router picks Forex vs Crypto automatically)
    cfg = ConfigBuilder.build("EURUSD")

    # With selective overrides (adds on top of router base)
    cfg = ConfigBuilder.build(
        "BTCUSDT",
        overrides={"score_threshold": 0.80, "max_sweep_age_candles": 25}
    )

    # From an existing CRTConfig's fields (backtest replay pattern)
    cfg = ConfigBuilder.from_existing("EURUSD", existing_cfg)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from typing import Optional

from config_layer.crt_engine_v2 import CRTConfig
from config_layer.market_router import get_crt_config, classify_market


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
    Direct CRTConfig(...) calls are forbidden outside market_router and this module.
    """

    @staticmethod
    def build(
        instrument: str,
        overrides: Optional[dict] = None,
    ) -> CRTConfig:
        """
        Build a validated, immutable CRTConfig for the given instrument.

        Parameters
        ----------
        instrument : str
            Trading instrument symbol (e.g. "EURUSD", "BTCUSDT").
            Unknown symbols default to FOREX profile.
        overrides : dict | None
            Optional field overrides applied on top of the router base config.
            Keys must be valid CRTConfig field names — unknown keys raise ValueError.

        Returns
        -------
        CRTConfig
            Frozen, immutable config. Mutation attempts will raise FrozenInstanceError.

        Raises
        ------
        ValueError
            If any override key is not a valid CRTConfig field name.
        """
        # Step 1 — Get market-correct base from router (FOREX or CRYPTO profile)
        base: CRTConfig = get_crt_config(instrument)

        # Step 2 — Validate and apply overrides
        if overrides:
            _validate_override_keys(overrides)
            base = replace(base, **overrides)

        # Step 3 — Return frozen config (already frozen by @dataclass(frozen=True))
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

        # Merge: existing fields first, then extra_overrides win
        if extra_overrides:
            _validate_override_keys(extra_overrides)
            existing_overrides.update(extra_overrides)

        # Re-root through router base, apply merged overrides
        base: CRTConfig = get_crt_config(instrument)
        return replace(base, **existing_overrides)

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
        forex_cfg  = ConfigBuilder.build(forex_instrument)
        crypto_cfg = ConfigBuilder.build(crypto_instrument)

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
        cfg = ConfigBuilder.build("EURUSD")
        cfg.score_threshold = 0.99          # real application-code mutation attempt
        print("  ❌ FAILED — config is mutable!")
    except (_dc.FrozenInstanceError, AttributeError):
        frozen_ok = cfg.__dataclass_params__.frozen
        print(f"  ✅ PASSED — FrozenInstanceError raised (frozen={frozen_ok})")

    print(f"\n  ✅ Unknown override key guard:")
    try:
        ConfigBuilder.build("EURUSD", overrides={"nonexistent_param": 99})
        print("  ❌ FAILED — unknown key accepted!")
    except ValueError as e:
        print(f"  ✅ PASSED — ValueError: {e}")

    print("\n" + "═" * 60 + "\n")
