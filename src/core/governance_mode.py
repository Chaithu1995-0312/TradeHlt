"""
governance_mode.py — Trd-M5 LLM-layer hardening: the GOVERNANCE_MODE switch.

Two modes:
  - "advisory" — decision-path isolation assertions log a WARNING and
    continue (preserves the fail-open doctrine: the LLM is a tie-breaker, never a
    hot-path dependency).
  - "strict" — the same assertions raise, surfacing any violation of "execution
    authority is isolated" (the 5th Governance Question) loudly. Intended for CI /
    pre-promotion runs.

Resolution order (read lazily at call time — never at import, so this module adds
no import-time config dependency):
  1. env var ``GOVERNANCE_MODE`` (``strict`` | ``advisory``) when SET — an explicit
     operator override, else
  2. production config ``governance.governance_mode`` — REQUIRED (EPIC-84 STORY-84.2:
     the literal "advisory" fallbacks and the fail-open except are gone; a missing
     section/key raises ConfigKeyMissingError, an invalid value raises ValueError).
"""
from __future__ import annotations

import os

from config_layer.strict_config import ConfigKeyMissingError, require

_VALID = ("strict", "advisory")
_CONFIG_MODE_CACHE: str | None = None


def governance_mode() -> str:
    """Return the active governance mode ("strict" | "advisory"). Fails closed (EPIC-84)."""
    env = os.environ.get("GOVERNANCE_MODE")
    if env is not None and env.strip().lower() in _VALID:
        return env.strip().lower()
    global _CONFIG_MODE_CACHE
    if _CONFIG_MODE_CACHE is None:
        from config_layer.production_config import get_prod_section
        try:
            gov = get_prod_section("governance")
        except RuntimeError as exc:  # section absent from the production config
            raise ConfigKeyMissingError(
                ["governance"], section="<root>", consumer="governance_mode",
            ) from exc
        mode = str(require(
            gov, "governance_mode", section_name="governance", consumer="governance_mode",
        )).strip().lower()
        if mode not in _VALID:
            raise ValueError(
                f"governance.governance_mode must be one of {_VALID}, got {mode!r}"
            )
        _CONFIG_MODE_CACHE = mode
    return _CONFIG_MODE_CACHE


def is_strict() -> bool:
    return governance_mode() == "strict"


def assert_isolated(condition: bool, message: str, logger=None) -> None:
    """
    Decision-path guard asserting execution-authority isolation.

    In ``strict`` mode a False ``condition`` raises ``AssertionError``; in
    ``advisory`` mode it logs a WARNING and continues. Use this to assert that the
    advisory LLM never gains execution authority on the decision spine.
    """
    if condition:
        return
    if is_strict():
        raise AssertionError(f"GOVERNANCE(strict): {message}")
    if logger is not None:
        logger.warning("GOVERNANCE(advisory): %s", message)
