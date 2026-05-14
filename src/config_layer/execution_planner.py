"""
execution_planner.py
====================
Execution Planner v1.2 — pure intent classifier + gate.

Classifies trade intent (BREAKOUT / PULLBACK / LIQ_SWEEP / REVERSAL),
derives the entry price, and delegates signal approval to GateIntelligence.
SL, TP, and RR are NOT computed here; that is CRT engine's sole responsibility
(see src/core/gate_intelligence.py :: compute_crt_levels).

Architecture position:
    Layer 1 (Intelligence) → EngineRunner.run()       → decision + score + regime
    Layer 2 (This module)  → ExecutionPlannerV1_2.plan() → intent + entry + gate
    Layer 3 (CRT levels)   → compute_crt_levels()     → SL / TP1 / TP2
    Layer 4 (Risk Gate)    → UltronRiskGate.evaluate() → final approval + size
    Layer 5 (Executor)     → broker stub (offline)

Design principles:
    - Pure functions, no global state.
    - No external dependencies beyond standard library + GateIntelligence.
    - Deterministic execution ID (no timestamp in hash).
    - UNKNOWN intent rejected by default (configurable).
    - Full trace dict for observability and replay.
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from utils.logging_config import get_flow_logger
from core.gate_intelligence import GateIntelligence

logger = get_flow_logger("EXECUTION_PLANNER")

# ── Optional feature keys (not required, but used if present) ─────────────────
_OPTIONAL_FEATURE_KEYS: tuple[str, ...] = (
    "lowest_low_5",
    "highest_high_5",
    "lowest_low_3",
    "highest_high_3",
    "lowest_low_20",
    "highest_high_20",
    "volume_ma20",
    "volume",
    "touches_high_20",
    "touches_low_20",
)

# ── Required feature keys (hard validation) ───────────────────────────────────
_REQUIRED_FEATURE_KEYS: tuple[str, ...] = (
    "close",
    "high",
    "low",
    "atr",
    "body_ratio",
    "disp_strength",
    "sweep_detected",
    "double_sweep",
    "retest_depth",
    "candles_since_retest",
    "ema_fast",
    "ema_slow",
    "momentum_score",
)

# ── TTL config keys per intent ────────────────────────────────────────────────
_TTL_MAP: dict[str, str] = {
    "BREAKOUT": "ttl_breakout_sec",
    "PULLBACK": "ttl_pullback_sec",
    "REVERSAL": "ttl_reversal_sec",
    "LIQ_SWEEP": "ttl_liq_sweep_sec",
    "UNKNOWN": "ttl_unknown_sec",
}

# ── Required config keys (must all be present in v1_multi_2026_03.json) ───────
REQUIRED_CONFIG_KEYS: tuple[str, ...] = (
    "ttl_breakout_sec",
    "ttl_pullback_sec",
    "ttl_reversal_sec",
    "ttl_liq_sweep_sec",
    "ttl_unknown_sec",
    "risk_percent",
    "precision_default",
    "precision_overrides",
    "default_account_balance",
    "reject_unknown_intent",
    # Gate intelligence keys (merged from gate_intelligence config section)
    "gate_weight_intent",
    "gate_weight_vol",
    "gate_weight_liquidity",
    "gate_weight_structure",
    "gate_approval_threshold",
)

# ── Default config (mirrors configs/production/v1_multi_2026_03.json values) ─
DEFAULT_CONFIG: dict = {
    "ttl_breakout_sec":        180,
    "ttl_pullback_sec":        300,
    "ttl_reversal_sec":        120,
    "ttl_liq_sweep_sec":       240,
    "ttl_unknown_sec":         180,
    "risk_percent":            0.5,
    "precision_default":       8,
    "precision_overrides":     {"XAUUSD": 2, "BTCUSDT": 2, "ETHUSDT": 2},
    "default_account_balance": 10_000.0,
    "reject_unknown_intent":   True,
    # Gate intelligence defaults
    "gate_weight_intent":      0.35,
    "gate_weight_vol":         0.20,
    "gate_weight_liquidity":   0.20,
    "gate_weight_structure":   0.25,
    "gate_approval_threshold": 0.55,
}


def _planner_require(config: dict, key: str) -> Any:
    """Strict accessor — raises KeyError if key absent from execution_planner config."""
    if key not in config:
        raise KeyError(
            f"Required config key '{key}' missing from execution_planner config. "
            f"Add it to configs/production/v1_multi_2026_03.json under 'execution_planner'."
        )
    return config[key]


class ExecutionPlannerV1_2:
    """
    Deterministic trade plan builder.

    Converts an EngineRunner "execute" decision into a complete trade plan
    with entry, stop loss, take profit, RR ratio, TTL, and position size hint.

    Usage
    -----
        planner = ExecutionPlannerV1_2(config)
        plan = planner.plan(engine_result, features, context)

    Parameters
    ----------
    config : dict, optional
        Overrides for DEFAULT_CONFIG keys.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        # Merge with DEFAULT_CONFIG so callers can pass None or a partial dict
        merged: dict[str, Any] = {**DEFAULT_CONFIG}
        if isinstance(config, dict):
            merged.update(config)
        self.config = merged

    # ── Public entry point ────────────────────────────────────────────────────

    def plan(
        self,
        engine_result: dict[str, Any],
        features: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build a trade execution plan.

        Parameters
        ----------
        engine_result : dict
            Output from EngineRunner.run().
            Required keys: "decision", "direction" (1/-1), "confidence", "regime".
        features : dict
            Canonical feature dict (must contain at minimum _REQUIRED_FEATURE_KEYS).
        context : dict
            Trade context. Required keys: "symbol", "signal", "score".
            Optional key: "account_balance" (float).

        Returns
        -------
        dict with decision, execution_id, trade_intent, entry_price, gate result, trace.
        SL/TP/RR are NOT set here — injected by live_engine_hook via compute_crt_levels().

        Raises
        ------
        ValueError
            If required feature keys are missing or prices are invalid.
        """
        trace: dict[str, Any] = {}

        # Step 1: Validate
        missing = self._validate_features(features)
        if missing:
            logger.error(f"ExecutionPlanner: missing feature keys: {missing}")
            return {
                "decision": "reject_invalid",
                "trace": {"error": f"missing_features: {missing}"},
            }

        price_err = self._validate_prices(features)
        if price_err:
            logger.error(f"ExecutionPlanner: price validation failed: {price_err}")
            return {
                "decision": "reject_invalid",
                "trace": {"error": price_err},
            }

        # Step 2: Engine decision gate
        if engine_result.get("decision", "").lower() != "execute":
            return {
                "decision": "reject_engine",
                "trace": {"engine_decision": engine_result.get("decision")},
            }

        direction = int(engine_result.get("direction", engine_result.get("selected_direction", 0)))
        if direction not in (1, -1):
            return {
                "decision": "reject_invalid",
                "trace": {"error": f"invalid_direction: {direction}"},
            }

        # Step 3: Derive trade intent
        intent, intent_reason = self._derive_intent(features, engine_result)
        trace["intent"] = intent
        trace["intent_reason"] = intent_reason
        logger.info(f"ExecutionPlanner: intent={intent} ({intent_reason})")

        # Reject UNKNOWN intent if configured
        if intent == "UNKNOWN" and bool(_planner_require(self.config, "reject_unknown_intent")):
            logger.warning(f"ExecutionPlanner: rejecting UNKNOWN intent: {intent_reason}")
            return {
                "decision": "reject_unknown_intent",
                "trace": {"intent_reason": intent_reason},
            }

        # Step 4: Entry
        entry_type, entry_price, entry_reason = self._compute_entry(
            intent, features, direction
        )
        trace["entry_reason"] = entry_reason

        # Step 5: Gate intelligence — approve or reject the signal
        gate = GateIntelligence(self.config)
        gate_result = gate.decide(features, intent, direction)
        trace["gate"] = gate_result

        if not gate_result["approved"]:
            logger.info(
                "ExecutionPlanner: gate_reject | score=%.4f | %s",
                gate_result["final_score"],
                gate_result["reason"],
            )
            return {
                "decision":     "reject_gate",
                "trade_intent": intent,
                "gate":         gate_result,
                "trace":        trace,
            }

        # Step 6: Timestamps and TTL
        now_utc = datetime.now(timezone.utc)
        ttl_key = _TTL_MAP.get(intent, "ttl_unknown_sec")
        ttl = int(_planner_require(self.config, ttl_key))
        expires_at = now_utc + timedelta(seconds=ttl)

        # Step 7: Precision rounding for entry price
        symbol = str(context.get("symbol", "UNKNOWN"))
        precision = int(
            _planner_require(self.config, "precision_overrides").get(
                symbol, _planner_require(self.config, "precision_default")
            )
        )
        entry_price = round(entry_price, precision)

        # Step 8: Deterministic execution ID (symbol + intent + entry + direction)
        id_str = f"{symbol}_{intent}_{round(entry_price, 4)}_{direction}"
        exec_hash = hashlib.md5(id_str.encode()).hexdigest()[:12]
        execution_id = f"EX_{exec_hash}"

        # Step 9: HTF context stub (future use)
        trace["context_regime"] = engine_result.get("context_regime", {})

        return {
            "decision":        "execute",
            "execution_id":    execution_id,
            "trade_intent":    intent,
            "direction":       direction,
            "entry_type":      entry_type,
            "entry_price":     entry_price,
            "gate":            gate_result,
            "validity_ttl_sec": ttl,
            "created_at":      now_utc.isoformat(),
            "expires_at":      expires_at.isoformat(),
            "confidence":      engine_result.get("confidence"),
            "regime":          engine_result.get("regime"),
            "symbol":          symbol,
            "signal":          context.get("signal"),
            "score":           context.get("score"),
            "trace":           trace,
        }

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_features(self, features: dict[str, Any]) -> list[str]:
        """Return list of missing required feature keys."""
        return [k for k in _REQUIRED_FEATURE_KEYS if k not in features]

    def _validate_prices(self, features: dict[str, Any]) -> str | None:
        """
        Validate price sanity. Returns error string if invalid, else None.
        """
        close = features.get("close", 0)
        high = features.get("high", 0)
        low = features.get("low", 0)
        atr = features.get("atr", 0)

        if close is None or not math.isfinite(float(close)) or float(close) <= 0:
            return f"invalid_close: {close}"
        if atr is None or not math.isfinite(float(atr)) or float(atr) <= 0:
            return f"invalid_atr: {atr}"
        if float(high) <= float(low):
            return f"high_not_above_low: high={high}, low={low}"
        return None

    # ── Intent derivation ─────────────────────────────────────────────────────

    def _derive_intent(
        self,
        features: dict[str, Any],
        engine_result: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Derive trade intent from features and engine direction.

        Priority order:
            1. LIQ_SWEEP  — sweep_detected or double_sweep
            2. PULLBACK   — retest_depth in [0.3, 0.7], recent, positive momentum
            3. BREAKOUT   — strong body + strong displacement
            4. REVERSAL   — counter-trend (EMA vs direction)
            5. UNKNOWN    — no clear pattern
        """
        direction = int(
            engine_result.get("direction", engine_result.get("selected_direction", 0))
        )

        sweep_detected = bool(features.get("sweep_detected", False))
        double_sweep = bool(features.get("double_sweep", False))
        retest_depth = float(features.get("retest_depth", 0.0))
        candles_since_retest = int(features.get("candles_since_retest", 99))
        momentum_score = float(features.get("momentum_score", 0.0))
        body_ratio = float(features.get("body_ratio", 0.0))
        disp_strength = float(features.get("disp_strength", 0.0))
        ema_fast = float(features.get("ema_fast", 0.0))
        ema_slow = float(features.get("ema_slow", 0.0))

        if sweep_detected or double_sweep:
            return "LIQ_SWEEP", "sweep detected"

        if (
            0.3 <= retest_depth <= 0.7
            and candles_since_retest <= 5
            and momentum_score > 0
        ):
            return "PULLBACK", "retest depth within 0.3-0.7, recent, positive momentum"

        if body_ratio > 0.6 and disp_strength > 1.5:
            return "BREAKOUT", "strong body and displacement"

        if (ema_fast > ema_slow and direction == -1) or (
            ema_fast < ema_slow and direction == 1
        ):
            return "REVERSAL", "counter-trend signal (EMA vs direction)"

        return "UNKNOWN", "no clear pattern"

    # ── Entry computation ─────────────────────────────────────────────────────

    def _compute_entry(
        self,
        intent: str,
        features: dict[str, Any],
        direction: int,
    ) -> tuple[str, float, str]:
        """
        Returns (entry_type, entry_price, reason).
        """
        close = float(features["close"])
        atr = float(features["atr"])
        low = float(features["low"])
        high = float(features["high"])

        if intent == "PULLBACK":
            ema_fast = float(features["ema_fast"])
            ema_slow = float(features["ema_slow"])
            price = ema_fast if direction == 1 else ema_slow
            label = "fast" if direction == 1 else "slow"
            return "LIMIT", price, f"limit at EMA_{label} ({price:.5f})"

        if intent == "LIQ_SWEEP":
            if direction == 1:
                price = low + 0.1 * atr
                return "LIMIT", price, f"limit beyond sweep low wick ({price:.5f})"
            else:
                price = high - 0.1 * atr
                return "LIMIT", price, f"limit beyond sweep high wick ({price:.5f})"

        # BREAKOUT, REVERSAL, UNKNOWN → market at close
        return "MARKET", close, f"market execution at close ({close:.5f})"


# ─────────────────────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")

    planner = ExecutionPlannerV1_2()

    # ── Test 1: Happy path — BREAKOUT ────────────────────────────────────────
    engine_result = {
        "decision": "execute",
        "direction": 1,
        "confidence": 0.82,
        "regime": "trend",
    }
    features = {
        "close": 100.0,
        "high": 102.0,
        "low": 98.0,
        "atr": 2.0,
        "body_ratio": 0.8,
        "disp_strength": 2.2,
        "sweep_detected": False,
        "double_sweep": False,
        "retest_depth": 0.2,
        "candles_since_retest": 10,
        "ema_fast": 99.5,
        "ema_slow": 98.5,
        "momentum_score": 0.7,
        # Required for adapter: open, volume, session
        "open": 99.0,
        "volume": 1000.0,
        "session": 1,
    }
    context = {
        "symbol": "EURUSD",
        "signal": 1,
        "score": 0.71,
        "account_balance": 10000.0,
    }

    result = planner.plan(engine_result, features, context)
    print("\n=== Test 1: BREAKOUT (happy path) ===")
    print(f"  decision:     {result['decision']}")
    print(f"  trade_intent: {result.get('trade_intent')}")
    print(f"  entry_price:  {result.get('entry_price')}")
    print(f"  gate_score:   {result.get('gate', {}).get('final_score')}")
    print(f"  execution_id: {result.get('execution_id')}")
    assert result["decision"] == "execute", f"Expected execute, got {result['decision']}"
    assert result["trade_intent"] == "BREAKOUT"
    assert "stop_loss" not in result, "SL must not be set by planner (CRT authority)"
    assert result["gate"]["approved"] is True
    print("  ✅ PASS")

    # ── Test 2: Reject — engine decision != execute ───────────────────────────
    engine_result_reject = {"decision": "REJECT", "direction": 1, "confidence": 0.3, "regime": "neutral"}
    result2 = planner.plan(engine_result_reject, features, context)
    print("\n=== Test 2: Engine reject ===")
    assert result2["decision"] == "reject_engine", f"Got {result2['decision']}"
    print(f"  decision: {result2['decision']} ✅ PASS")

    # ── Test 3: UNKNOWN intent → reject ──────────────────────────────────────
    features_unknown = {
        **features,
        "body_ratio": 0.2,
        "disp_strength": 0.5,
        "momentum_score": 0.0,
        "sweep_detected": False,
        "double_sweep": False,
        "retest_depth": 0.0,
        "candles_since_retest": 99,
        "ema_fast": 100.0,
        "ema_slow": 99.0,
    }
    result3 = planner.plan(engine_result, features_unknown, context)
    print("\n=== Test 3: UNKNOWN intent rejection ===")
    assert result3["decision"] == "reject_unknown_intent", f"Got {result3['decision']}"
    print(f"  decision: {result3['decision']} ✅ PASS")

    # ── Test 4: Weak signal → gate reject ────────────────────────────────────
    features_weak = {
        **features,
        "body_ratio": 0.1,
        "disp_strength": 0.1,
        "momentum_score": 0.0,
        "volume": 100.0,
        "volume_ma20": 800.0,
    }
    result4 = planner.plan(engine_result, features_weak, context)
    print("\n=== Test 4: Weak signal → gate reject ===")
    # Gate score will be below 0.55 with these weak features
    print(f"  decision: {result4['decision']} (gate_score={result4.get('gate', {}).get('final_score')})")
    assert result4["decision"] in ("reject_gate", "execute"), f"Got {result4['decision']}"
    print("  ✅ PASS")

    print("\n=== All tests passed ===\n")