"""
execution_planner.py
====================
Execution Planner v1.2 — converts an EngineRunner "execute" decision into a
concrete, deterministic trade plan (entry, SL, TP, RR, TTL, position size hint).

Architecture position:
    Layer 1 (Intelligence) → EngineRunner.run()  → decision + score + regime
    Layer 2 (This module)  → ExecutionPlannerV1_2.plan() → entry/SL/TP/RR
    Layer 3 (Risk Gate)    → UltronRiskGate.evaluate()   → final approval + size
    Layer 4 (Executor)     → broker stub (offline)

Design principles:
    - Pure functions, no global state.
    - No external dependencies beyond standard library.
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

# ── ATR multiplier config keys per intent ─────────────────────────────────────
_TP_MULT_MAP: dict[str, str] = {
    "BREAKOUT": "atr_mult_breakout_tp",
    "PULLBACK": "atr_mult_pullback_tp",
    "REVERSAL": "atr_mult_reversal_tp",
    "LIQ_SWEEP": "atr_mult_sweep_tp",
    "UNKNOWN": "atr_mult_breakout_tp",  # not used — UNKNOWN is rejected
}

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
    "min_rr_ratio",
    "atr_mult_breakout_tp",
    "atr_mult_pullback_tp",
    "atr_mult_reversal_tp",
    "atr_mult_sweep_tp",
    "ttl_breakout_sec",
    "ttl_pullback_sec",
    "ttl_reversal_sec",
    "ttl_liq_sweep_sec",
    "ttl_unknown_sec",
    "default_sl_atr_mult",
    "risk_percent",
    "precision_default",
    "precision_overrides",
    "lookback_candles_sl",
    "liquidity_lookback",
    "liquidity_volume_threshold",
    "liquidity_touch_count",
    "default_account_balance",
    "reject_unknown_intent",
)

# ── Default config (mirrors configs/production/v1_multi_2026_03.json values) ─
DEFAULT_CONFIG: dict = {
    "min_rr_ratio":                 1.5,
    "atr_mult_breakout_tp":         2.0,
    "atr_mult_pullback_tp":         1.5,
    "atr_mult_reversal_tp":         1.0,
    "atr_mult_sweep_tp":            1.2,
    "ttl_breakout_sec":             180,
    "ttl_pullback_sec":             300,
    "ttl_reversal_sec":             120,
    "ttl_liq_sweep_sec":            240,
    "ttl_unknown_sec":              180,
    "default_sl_atr_mult":          1.0,
    "risk_percent":                 0.5,
    "precision_default":            8,
    "precision_overrides":          {"XAUUSD": 2, "BTCUSDT": 2, "ETHUSDT": 2},
    "lookback_candles_sl":          5,
    "liquidity_lookback":           20,
    "liquidity_volume_threshold":   1.5,
    "liquidity_touch_count":        2,
    "default_account_balance":      10_000.0,
    "reject_unknown_intent":        True,
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
        dict with decision, execution_id, trade_intent, entry/SL/TP, RR, trace, etc.

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

        # Step 5: Stop loss
        sl, sl_method, sl_reason = self._compute_sl(intent, features, direction, entry_price)
        trace["sl_reason"] = sl_reason
        trace["sl_fallback_used"] = sl_method in ("atr_fallback", "structure_current_bar")

        # Step 6: Take profit
        tp1, tp2, tp3, tp_method, tp_reason = self._compute_tp(
            intent, features, entry_price, direction
        )
        trace["tp_reason"] = tp_reason
        trace["liquidity_method"] = "hybrid_liquidity" if "liquidity" in tp_method else "atr_only"

        # Step 7: SL/TP sanity check
        if direction == 1 and not (sl < entry_price < tp1):
            err = f"sl_tp_order_invalid: entry={entry_price}, sl={sl}, tp1={tp1}"
            logger.error(f"ExecutionPlanner: {err}")
            return {"decision": "reject_invalid", "trace": {"error": err}}
        if direction == -1 and not (tp1 < entry_price < sl):
            err = f"sl_tp_order_invalid_short: entry={entry_price}, sl={sl}, tp1={tp1}"
            logger.error(f"ExecutionPlanner: {err}")
            return {"decision": "reject_invalid", "trace": {"error": err}}

        # Step 8: RR calculation
        risk_amount = abs(entry_price - sl)
        reward_amount = abs(tp1 - entry_price)
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0.0
        trace["rr_calc"] = {
            "risk_amount": risk_amount,
            "reward_amount": reward_amount,
            "ratio": rr_ratio,
        }
        logger.info(f"ExecutionPlanner: RR={rr_ratio:.3f} (min={self.config['min_rr_ratio']})")

        # Step 9: RR gate
        if rr_ratio < self.config["min_rr_ratio"]:
            logger.info(f"ExecutionPlanner: reject_rr (ratio={rr_ratio:.3f})")
            return {
                "decision": "reject_rr",
                "rr_ratio": round(rr_ratio, 4),
                "trade_intent": intent,
                "trace": trace,
            }

        # Step 10: Timestamps and TTL
        now_utc = datetime.now(timezone.utc)
        ttl_key = _TTL_MAP.get(intent, "ttl_unknown_sec")
        ttl = int(_planner_require(self.config, ttl_key))
        expires_at = now_utc + timedelta(seconds=ttl)

        # Step 11: Position size hint (stub for Ultron)
        account_balance = float(
            context.get("account_balance", _planner_require(self.config, "default_account_balance"))
        )
        risk_percent = float(self.config["risk_percent"])
        risk_usd = account_balance * (risk_percent / 100.0)
        position_size_hint: float | None = None
        if risk_amount > 0:
            position_size_hint = round(risk_usd / risk_amount, 4)
            if position_size_hint <= 0:
                logger.warning("ExecutionPlanner: position_size_hint <= 0, set to None")
                position_size_hint = None
        else:
            logger.warning("ExecutionPlanner: risk_amount=0, position_size_hint=None")

        # Step 12: Precision rounding
        symbol = str(context.get("symbol", "UNKNOWN"))
        precision = int(
            _planner_require(self.config, "precision_overrides").get(
                symbol, _planner_require(self.config, "precision_default")
            )
        )
        entry_price = round(entry_price, precision)
        sl = round(sl, precision)
        tp1 = round(tp1, precision)
        tp2 = round(tp2, precision) if tp2 is not None else None

        # Step 13: Deterministic execution ID (no timestamp)
        id_str = f"{symbol}_{intent}_{round(entry_price, 4)}_{round(sl, 4)}"
        exec_hash = hashlib.md5(id_str.encode()).hexdigest()[:12]
        execution_id = f"EX_{exec_hash}"

        # Step 14: HTF context stub (future use)
        trace["context_regime"] = engine_result.get("context_regime", {})

        return {
            "decision": "execute",
            "execution_id": execution_id,
            "trade_intent": intent,
            "direction": direction,
            "entry_type": entry_type,
            "entry_price": entry_price,
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "take_profit_3": tp3,
            "rr_ratio": round(rr_ratio, 4),
            "risk_percent": risk_percent,
            "position_size_hint": position_size_hint,
            "risk_source": "local_estimate",
            "validity_ttl_sec": ttl,
            "created_at": now_utc.isoformat(),
            "expires_at": expires_at.isoformat(),
            "sl_method": sl_method,
            "tp_method": tp_method,
            "confidence": engine_result.get("confidence"),
            "regime": engine_result.get("regime"),
            "symbol": symbol,
            "signal": context.get("signal"),
            "score": context.get("score"),
            "trace": trace,
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

    # ── Stop loss computation ─────────────────────────────────────────────────

    def _compute_sl(
        self,
        intent: str,
        features: dict[str, Any],
        direction: int,
        entry_price: float,
    ) -> tuple[float, str, str]:
        """
        Returns (stop_loss, sl_method, sl_reason).
        """
        atr = float(features["atr"])
        low = float(features["low"])
        high = float(features["high"])

        if intent == "LIQ_SWEEP":
            if direction == 1:
                sl = low - 0.2 * atr
                return sl, "beyond_sweep", f"SL beyond sweep low - 0.2 ATR ({sl:.5f})"
            else:
                sl = high + 0.2 * atr
                return sl, "beyond_sweep", f"SL beyond sweep high + 0.2 ATR ({sl:.5f})"

        if intent == "PULLBACK":
            lookback = int(_planner_require(self.config, "lookback_candles_sl"))
            low_key = f"lowest_low_{lookback}"
            high_key = f"highest_high_{lookback}"
            if low_key in features and high_key in features:
                sl = float(features[low_key] if direction == 1 else features[high_key])
                return (
                    sl,
                    "structure_last_N",
                    f"SL at {lookback}-candle {'low' if direction==1 else 'high'} ({sl:.5f})",
                )
            else:
                logger.warning(
                    f"ExecutionPlanner: missing {low_key}/{high_key}, fallback to current bar"
                )
                sl = low if direction == 1 else high
                return (
                    sl,
                    "structure_current_bar",
                    f"fallback SL at current bar {'low' if direction==1 else 'high'} ({sl:.5f})",
                )

        if intent == "BREAKOUT":
            sl = low if direction == 1 else high
            return sl, "breakout_candle", f"SL at breakout candle {'low' if direction==1 else 'high'} ({sl:.5f})"

        if intent == "REVERSAL":
            # Use 3-candle swing if available, else current bar
            low_key = "lowest_low_3"
            high_key = "highest_high_3"
            if low_key in features and high_key in features:
                sl = float(features[low_key] if direction == 1 else features[high_key])
                return sl, "swing_reversal", f"SL at 3-candle swing {'low' if direction==1 else 'high'} ({sl:.5f})"
            else:
                sl = low if direction == 1 else high
                return (
                    sl,
                    "swing_reversal_fallback",
                    f"fallback SL at current bar ('no 3-candle agg') ({sl:.5f})",
                )

        # Fallback: ATR-based
        if direction == 1:
            sl = entry_price - self.config["default_sl_atr_mult"] * atr
        else:
            sl = entry_price + self.config["default_sl_atr_mult"] * atr
        return sl, "atr_fallback", f"ATR-based fallback SL ({sl:.5f})"

    # ── Take profit computation ───────────────────────────────────────────────

    def _compute_tp(
        self,
        intent: str,
        features: dict[str, Any],
        entry_price: float,
        direction: int,
    ) -> tuple[float, float | None, None, str, str]:
        """
        Returns (tp1, tp2, tp3, method, reason).

        v1.2: Hybrid ATR base + liquidity detection (volume spike + touch count).
        """
        atr = float(features["atr"])
        tp_mult_key = _TP_MULT_MAP.get(intent, "atr_mult_breakout_tp")
        tp_mult = float(_planner_require(self.config, tp_mult_key))

        if direction == 1:
            tp1_base = entry_price + tp_mult * atr
            tp2 = entry_price + tp_mult * atr * 2
        else:
            tp1_base = entry_price - tp_mult * atr
            tp2 = entry_price - tp_mult * atr * 2

        base_reason = f"ATR × {tp_mult:.1f} ({tp1_base:.5f})"
        tp1 = tp1_base
        tp_method = "atr_only"
        tp_reason = base_reason

        # Liquidity detection (improved in v1.2: volume spike + multiple touches)
        lookback = int(_planner_require(self.config, "liquidity_lookback"))
        min_touches = int(_planner_require(self.config, "liquidity_touch_count"))
        volume_threshold = float(_planner_require(self.config, "liquidity_volume_threshold"))

        recent_high_key = f"highest_high_{lookback}"
        recent_low_key = f"lowest_low_{lookback}"
        touches_high_key = f"touches_high_{lookback}"
        touches_low_key = f"touches_low_{lookback}"
        volume_ma_key = "volume_ma20"

        if (
            direction == 1
            and recent_high_key in features
            and touches_high_key in features
            and volume_ma_key in features
        ):
            recent_high = float(features[recent_high_key])
            touches = float(features[touches_high_key])
            vol_ma = float(features[volume_ma_key])
            vol = float(features.get("volume", 0.0))
            vol_ratio = vol / vol_ma if vol_ma > 0 else 0.0
            if touches >= min_touches and vol_ratio >= volume_threshold:
                tp1 = recent_high
                tp_method = "hybrid_liquidity"
                tp_reason = (
                    f"liquidity level at recent high (touches={touches:.0f}, "
                    f"vol_ratio={vol_ratio:.1f}) → {tp1:.5f}"
                )

        elif (
            direction == -1
            and recent_low_key in features
            and touches_low_key in features
            and volume_ma_key in features
        ):
            recent_low = float(features[recent_low_key])
            touches = float(features[touches_low_key])
            vol_ma = float(features[volume_ma_key])
            vol = float(features.get("volume", 0.0))
            vol_ratio = vol / vol_ma if vol_ma > 0 else 0.0
            if touches >= min_touches and vol_ratio >= volume_threshold:
                tp1 = recent_low
                tp_method = "hybrid_liquidity"
                tp_reason = (
                    f"liquidity level at recent low (touches={touches:.0f}, "
                    f"vol_ratio={vol_ratio:.1f}) → {tp1:.5f}"
                )

        return tp1, tp2, None, tp_method, tp_reason


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
    print(f"  stop_loss:    {result.get('stop_loss')}")
    print(f"  take_profit_1:{result.get('take_profit_1')}")
    print(f"  rr_ratio:     {result.get('rr_ratio')}")
    print(f"  execution_id: {result.get('execution_id')}")
    assert result["decision"] == "execute", f"Expected execute, got {result['decision']}"
    assert result["trade_intent"] == "BREAKOUT"
    assert result["rr_ratio"] >= 1.5
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

    # ── Test 4: Low RR → reject_rr ───────────────────────────────────────────
    features_low_rr = {
        **features,
        "atr": 0.1,  # tiny ATR → tiny TP → low RR against breakout candle SL
    }
    result4 = planner.plan(engine_result, features_low_rr, context)
    print("\n=== Test 4: Low RR rejection ===")
    # ATR=0.1, entry=100, sl=low=98 (breakout), tp1=100+0.1*2=100.2
    # risk=2, reward=0.2, rr=0.1 < 1.5 → reject_rr
    assert result4["decision"] == "reject_rr", f"Got {result4['decision']}"
    print(f"  decision: {result4['decision']} ✅ PASS")

    print("\n=== All tests passed ===\n")