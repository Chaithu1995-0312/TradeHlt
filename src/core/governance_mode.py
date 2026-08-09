"""
governance_mode.py — Trd-M5 LLM-layer hardening: the GOVERNANCE_MODE switch.

Two modes:
  - "advisory" (default) — decision-path isolation assertions log a WARNING and
    continue (preserves the fail-open doctrine: the LLM is a tie-breaker, never a
    hot-path dependency).
  - "strict" — the same assertions raise, surfacing any violation of "execution
    authority is isolated" (the 5th Governance Question) loudly. Intended for CI /
    pre-promotion runs.

Resolution order (read lazily at call time — never at import, so this module adds
no import-time config dependency):
  1. env var ``GOVERNANCE_MODE`` (``strict`` | ``advisory``), else
  2. production config ``governance.governance_mode``, else
  3. ``"advisory"``.
"""
from __future__ import annotations

import os

_VALID = ("strict", "advisory")
_CONFIG_MODE_CACHE: str | None = None


def governance_mode() -> str:
    """Return the active governance mode ("strict" | "advisory"). Fail-open to advisory."""
    env = os.environ.get("GOVERNANCE_MODE", "").strip().lower()
    if env in _VALID:
        return env
    global _CONFIG_MODE_CACHE
    if _CONFIG_MODE_CACHE is None:
        try:
            from config_layer.production_config import get_prod_section
            gov = get_prod_section("governance") or {}
            mode = str(gov.get("governance_mode", "advisory")).strip().lower()
            _CONFIG_MODE_CACHE = mode if mode in _VALID else "advisory"
        except Exception:
            _CONFIG_MODE_CACHE = "advisory"
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
