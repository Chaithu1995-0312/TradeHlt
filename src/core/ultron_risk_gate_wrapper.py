"""
core/ultron_risk_gate_wrapper.py — UltronRiskGateWrapper

CANONICAL ROLE: External utility used to pre-scale risk percentages by regime
before passing them to UltronRiskGate. Called at the live/execution layer AFTER
EngineRunner.run() returns a regime value.

CANONICAL NAMING CONTEXT:
  UltronRiskGateWrapper (this file) = EXTERNAL REGIME PRE-SCALER.
                    Multiplies trade.risk_percent by a regime-specific factor
                    before delegating unconditionally to UltronRiskGate.evaluate().
  UltronRiskGate  (ultron_risk_gate.py) = CAPITAL PROTECTION LAYER (never bypassed).
  RegimeGovernor  (regime_governor.py)  = SIGNAL-QUALITY FILTER inside EngineRunner Step 6.

SR-1 COMPLIANCE: UltronRiskGate is NEVER bypassed or modified.
This wrapper only pre-scales risk_percent; the gate's evaluate() is ALWAYS called.

Usage (at caller level — NOT inside EngineRunner):
    from core.ultron_risk_gate import UltronRiskGate
    from core.ultron_risk_gate_wrapper import UltronRiskGateWrapper

    gate    = UltronRiskGate(config)
    wrapper = UltronRiskGateWrapper(gate, regime_factors=config["regime_factors"],
                                    debug_mode=debug_mode)

    # In the decision loop (regime comes from EngineRunner.run() return value):
    result  = wrapper.evaluate(trade, portfolio_state, regime="range")
    # result schema is IDENTICAL to UltronRiskGate.evaluate() output

Regime factors come from the declared ultron_risk_gate.regime_factors mapping (required;
EPIC-84 STORY-84.2 removed the in-code default table). Active-config values:
    "trend":     1.0   (no change — full risk)
    "range":     0.8   (slight reduction in ranging markets)
    "neutral":   0.6   (moderate reduction in uncertain markets)
    "uncertain": 0.5   (significant reduction)

Warning: if regime is not explicitly passed, "neutral" is used (0.6×).
A one-time WARNING is logged per session to surface accidental defaults.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

from config_layer.strict_config import ConfigKeyMissingError

_LOG = logging.getLogger("ULTRON_WRAPPER")

# EPIC-84 STORY-84.2: the module-level _DEFAULT_REGIME_FACTORS merge is gone. The factors
# are the declared ``ultron_risk_gate.regime_factors`` mapping; absent -> ConfigKeyMissingError.

_DEFAULT_REGIME = "neutral"


class UltronRiskGateWrapper:
    """
    Thin pre-scaling wrapper around UltronRiskGate.

    SR-1 invariant: self._gate.evaluate() is unconditionally called on
    every invocation. The wrapper has NO reject path of its own.
    """

    def __init__(
        self,
        gate: Any,
        regime_factors: dict[str, float] | None,
        debug_mode: bool = False,
    ) -> None:
        if regime_factors is None:
            raise ConfigKeyMissingError(
                ["regime_factors"], section="ultron_risk_gate",
                consumer="UltronRiskGateWrapper",
            )
        if not isinstance(regime_factors, dict):
            raise TypeError(
                "ultron_risk_gate.regime_factors must be a mapping, got "
                f"{type(regime_factors).__name__}"
            )
        self._gate           = gate
        self._factors        = dict(regime_factors)
        self.debug_mode      = debug_mode
        # One-time warning flag: alert if regime defaults are used without explicit setting
        self._warned_default = False

    # ------------------------------------------------------------------
    # Main method — schema is identical to UltronRiskGate.evaluate()
    # ------------------------------------------------------------------

    def evaluate(
        self,
        trade:           dict[str, Any],
        portfolio_state: dict[str, Any],
        regime:          str = _DEFAULT_REGIME,
    ) -> dict[str, Any]:
        """
        1. Warn (once per session) if regime was not explicitly passed.
        2. Deep-copy trade dict to avoid mutating caller's dict.
        3. Apply regime_factor to risk_percent in the copy.
        4. Unconditionally call self._gate.evaluate() and return its result.
        5. Optionally log scaling decision as structured JSON (debug_mode).

        The returned dict is the gate's output verbatim — no fields added,
        removed, or modified.
        """
        # --- Warn on accidental defaults ---
        if regime == _DEFAULT_REGIME and not self._warned_default:
            _LOG.warning(
                "UltronRiskGateWrapper: regime not explicitly passed — "
                "defaulting to '%s' (factor=%.2f). "
                "Check EngineRunner.run() return value for 'regime' key.",
                _DEFAULT_REGIME,
                self._factors.get(_DEFAULT_REGIME, 1.0),
            )
            self._warned_default = True

        # --- Regime pre-scaling (never mutates caller's dict) ---
        factor       = self._factors.get(regime, 1.0)
        trade_copy   = copy.deepcopy(trade)
        # risk_percent is a per-trade value: when absent it is NOT invented (was 0.0) — the copy
        # is forwarded unchanged and UltronRiskGate REJECTs it with
        # config_key_missing:trade.risk_percent (SR-1: the wrapper has no reject path).
        if "risk_percent" in trade_copy:
            original_risk = float(trade_copy["risk_percent"])
            scaled_risk   = original_risk * factor
            trade_copy["risk_percent"] = scaled_risk
        else:
            original_risk = None
            scaled_risk   = None

        # --- Debug logging ---
        if self.debug_mode:
            _LOG.debug(json.dumps({
                "event":          "risk_gate_pre_scaling",
                "regime":         regime,
                "factor":         factor,
                "original_risk":  original_risk,
                "scaled_risk":    scaled_risk,
                "execution_id":   trade.get("execution_id", ""),
            }))

        # --- SR-1: Unconditionally delegate to real gate ---
        return self._gate.evaluate(trade_copy, portfolio_state)
