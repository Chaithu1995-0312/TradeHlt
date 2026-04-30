"""
live_engine_hook.py
Subclass wrapper around LiveEngine - does NOT modify live_engine.py.
Calls EngineRunner -> ExecutionPlannerV1_2 -> UltronRiskGate after process() returns.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone

import core.collector as collector

from core.engine_runner import EngineRunner
from engines.live_engine import LiveEngine
from config_layer.execution_planner import ExecutionPlannerV1_2
from config_layer.production_config import get_prod_metadata
from core.ultron_risk_gate import UltronRiskGate
from core.ultron_risk_gate_wrapper import UltronRiskGateWrapper
from utils.logging_config import get_flow_logger

try:
    from features.feature_monitor import FeatureMonitor
    _MONITOR_AVAILABLE = True
except Exception:
    FeatureMonitor = None
    _MONITOR_AVAILABLE = False

try:
    from core.feature_store import FeatureStore
    _STORE_AVAILABLE = True
except Exception:
    FeatureStore = None  # type: ignore[assignment,misc]
    _STORE_AVAILABLE = False

logger = get_flow_logger("LIVE_HOOK")

_ENGINE_CONFIG_CACHE: dict | None = None
_feature_monitor = None  # initialized lazily from config
_feature_store = None    # FeatureStore singleton — canonical ingestion boundary


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_session(value) -> str:
    session_map = {
        0: "asia",
        1: "london",
        2: "new_york",
        3: "overlap",
        "0": "asia",
        "1": "london",
        "2": "new_york",
        "3": "overlap",
        "asia": "asia",
        "asian": "asia",
        "london": "london",
        "newyork": "new_york",
        "new_york": "new_york",
        "ny": "new_york",
        "overlap": "overlap",
    }
    if value is None:
        return "london"
    key = str(value).strip().lower()
    return session_map.get(key, session_map.get(value, key))


def _derive_session(trade_data: dict) -> str:
    if "session" in trade_data and trade_data.get("session") is not None:
        return _normalize_session(trade_data.get("session"))
    if _safe_float(trade_data.get("is_asia"), 0.0) > 0.5:
        return "asia"
    if _safe_float(trade_data.get("is_london"), 0.0) > 0.5:
        return "london"
    if _safe_float(trade_data.get("is_newyork"), 0.0) > 0.5:
        return "new_york"
    return "london"


def _load_engine_config() -> dict:
    """
    Load the full production config and build the merged EngineRunner config dict.

    Raises RuntimeError if the production config is missing or malformed.
    No default fallbacks permitted — all values must come from v1_multi_2026_03.json.
    """
    global _ENGINE_CONFIG_CACHE, _feature_monitor
    if _ENGINE_CONFIG_CACHE is not None:
        return deepcopy(_ENGINE_CONFIG_CACHE)

    metadata = get_prod_metadata()
    if not metadata:
        raise RuntimeError(
            "LIVE_HOOK: production metadata is empty. "
            "Ensure configs/production/v1_multi_2026_03.json exists and is valid."
        )

    engine_cfg = metadata.get("engine_runner")
    if not isinstance(engine_cfg, dict):
        raise RuntimeError(
            "LIVE_HOOK: 'engine_runner' section missing from production config. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )

    decision_cfg = metadata.get("decision_engine")
    if not isinstance(decision_cfg, dict):
        raise RuntimeError(
            "LIVE_HOOK: 'decision_engine' section missing from production config. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )

    fusion_cfg = metadata.get("fusion_engine")
    if not isinstance(fusion_cfg, dict):
        raise RuntimeError(
            "LIVE_HOOK: 'fusion_engine' section missing from production config. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )

    ultron_cfg = metadata.get("ultron_risk_gate")
    if not isinstance(ultron_cfg, dict):
        raise RuntimeError(
            "LIVE_HOOK: 'ultron_risk_gate' section missing from production config. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )

    # Normalize session strings in allowed_sessions
    raw_sessions = engine_cfg.get("allowed_sessions", [])
    if isinstance(raw_sessions, list) and raw_sessions:
        engine_cfg = dict(engine_cfg)
        engine_cfg["allowed_sessions"] = [_normalize_session(s) for s in raw_sessions]

    exec_planner_cfg = metadata.get("execution_planner")
    if not isinstance(exec_planner_cfg, dict):
        raise RuntimeError(
            "LIVE_HOOK: 'execution_planner' section missing from production config. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )

    # Merged flat config: engine_runner + decision_engine + nested sections
    # fusion_engine is kept as nested key so EngineRunner can access it correctly
    merged = {}
    merged.update(engine_cfg)
    merged.update(decision_cfg)
    merged["fusion_engine"] = fusion_cfg
    merged["ultron_risk_gate"] = ultron_cfg
    merged["execution_planner"] = exec_planner_cfg

    # Initialize FeatureMonitor from config
    if _MONITOR_AVAILABLE and FeatureMonitor is not None:
        fm_cfg = metadata.get("feature_monitor")
        if not isinstance(fm_cfg, dict):
            raise RuntimeError(
                "LIVE_HOOK: 'feature_monitor' section missing from production config. "
                "Add it to configs/production/v1_multi_2026_03.json."
            )
        window_size = fm_cfg.get("window_size")
        if window_size is None:
            raise KeyError(
                "Required key 'window_size' missing from feature_monitor config. "
                "Add it to configs/production/v1_multi_2026_03.json."
            )
        _feature_monitor = FeatureMonitor(window_size=int(window_size))

    # Initialize FeatureStore as canonical ingestion boundary.
    # Validates all 35 CANONICAL_FEATURES, computes history-derived double_sweep,
    # and injects _data_integrity="real" sentinel before EngineRunner receives the dict.
    if _STORE_AVAILABLE and FeatureStore is not None:
        fs_cfg = metadata.get("feature_store")
        if not isinstance(fs_cfg, dict):
            raise RuntimeError(
                "LIVE_HOOK: 'feature_store' section missing from production config. "
                "Add it to configs/production/v1_multi_2026_03.json."
            )
        max_history = fs_cfg.get("max_history")
        if max_history is None:
            raise KeyError(
                "Required key 'max_history' missing from feature_store config. "
                "Add it to configs/production/v1_multi_2026_03.json."
            )
        _feature_store = FeatureStore(max_history=int(max_history))

    _ENGINE_CONFIG_CACHE = deepcopy(merged)
    return merged


def _build_engine_input(trade_data: dict) -> dict:
    close = _safe_float(trade_data.get("close"), 0.0)
    open_ = _safe_float(trade_data.get("open"), close)
    high = _safe_float(trade_data.get("high"), max(open_, close))
    low = _safe_float(trade_data.get("low"), min(open_, close))
    ema_fast = _safe_float(trade_data.get("ema_fast"), close)
    ema_slow = _safe_float(trade_data.get("ema_slow"), close)
    disp_strength = _safe_float(
        trade_data.get("disp_strength", trade_data.get("disp_str")),
        0.0,
    )

    return {
        "_data_integrity": "real",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": _safe_float(trade_data.get("volume"), 1.0),
        "atr": max(0.0, _safe_float(trade_data.get("atr"), 0.0)),
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "session": _derive_session(trade_data),
        "trend_bias": _safe_float(trade_data.get("trend_bias"), 0.0),
        "ema_spread": _safe_float(trade_data.get("ema_spread"), ema_fast - ema_slow),
        "momentum_score": _safe_float(trade_data.get("momentum_score"), 0.0),
        "volatility_ratio": max(0.0, _safe_float(trade_data.get("volatility_ratio"), 1.0)),
        "sweep_detected": _safe_float(trade_data.get("sweep_detected"), 0.0),
        "double_sweep": _safe_float(trade_data.get("double_sweep"), 0.0),
        "body_ratio": _safe_float(trade_data.get("body_ratio"), 0.0),
        "disp_strength": disp_strength,
        "retest_depth": _safe_float(trade_data.get("retest_depth"), 0.0),
        "candles_since_retest": int(_safe_float(trade_data.get("candles_since_retest"), 0.0)),
    }


def _build_ohlcv_and_auxiliary(trade_data: dict) -> tuple[dict, dict]:
    """
    Split trade_data into (ohlcv, auxiliary) for FeatureStore.process().

    ohlcv     — 5 core OHLCV fields required by FeatureStore._ensure_required().
    auxiliary — all remaining 30 CANONICAL_FEATURES (unknowns default to 0.0).
                double_sweep is passed as 0.0 — FeatureStore._compute_derived()
                overwrites it with the history-correct value.
                _data_integrity is NOT included — FeatureStore adds it post-validation.

    Returns (ohlcv: dict, auxiliary: dict).
    """
    close  = _safe_float(trade_data.get("close"), 0.0)
    open_  = _safe_float(trade_data.get("open"), close)
    high   = _safe_float(trade_data.get("high"), max(open_, close))
    low    = _safe_float(trade_data.get("low"), min(open_, close))
    volume = _safe_float(trade_data.get("volume"), 1.0)

    ohlcv = {"open": open_, "high": high, "low": low, "close": close, "volume": volume}

    # Derived candle anatomy (computed here; FeatureStore does not derive these)
    body_size = abs(close - open_)
    wick_size = max(0.0, (high - low) - body_size)
    body_ratio = body_size / wick_size if wick_size > 1e-8 else 0.0

    ema_fast = _safe_float(trade_data.get("ema_fast"), close)
    ema_slow = _safe_float(trade_data.get("ema_slow"), close)
    disp_strength = _safe_float(
        trade_data.get("disp_strength", trade_data.get("disp_str")), 0.0
    )

    auxiliary = {
        # EMA / trend
        "atr":                  max(0.0, _safe_float(trade_data.get("atr"), 0.0)),
        "ema_fast":             ema_fast,
        "ema_slow":             ema_slow,
        "ema_spread":           _safe_float(trade_data.get("ema_spread"), ema_fast - ema_slow),
        "session":              _derive_session(trade_data),
        "trend_bias":           _safe_float(trade_data.get("trend_bias"), 0.0),
        "trend_strength":       _safe_float(trade_data.get("trend_strength"), 0.0),
        "momentum_score":       _safe_float(trade_data.get("momentum_score"), 0.0),
        "volatility_ratio":     max(0.0, _safe_float(trade_data.get("volatility_ratio"), 1.0)),
        # Volume
        "volume_ratio":         max(0.0, _safe_float(trade_data.get("volume_ratio"), 1.0)),
        # Structure / sweep
        "sweep_detected":       _safe_float(trade_data.get("sweep_detected"), 0.0),
        "double_sweep":         0.0,  # overwritten by FeatureStore._compute_derived()
        "liquidity_sweep":      _safe_float(trade_data.get("liquidity_sweep"), 0.0),
        "break_of_structure":   _safe_float(trade_data.get("break_of_structure"), 0.0),
        # Swing levels
        "swing_high":           _safe_float(trade_data.get("swing_high"), 0.0),
        "swing_low":            _safe_float(trade_data.get("swing_low"), 0.0),
        "higher_high":          _safe_float(trade_data.get("higher_high"), 0.0),
        "lower_low":            _safe_float(trade_data.get("lower_low"), 0.0),
        # Candle anatomy
        "body_size":            body_size,
        "wick_size":            wick_size,
        "body_ratio":           body_ratio,
        # Regime / volatility
        "volatility_regime":    _safe_float(trade_data.get("volatility_regime"), 0.0),
        # Indicators — passed through if supplied by upstream, otherwise 0.0
        "rsi_14":               _safe_float(trade_data.get("rsi_14"), 0.0),
        "macd_line":            _safe_float(trade_data.get("macd_line"), 0.0),
        "macd_signal":          _safe_float(trade_data.get("macd_signal"), 0.0),
        "macd_hist":            _safe_float(trade_data.get("macd_hist"), 0.0),
        # Time
        "hour_of_day":          _safe_float(trade_data.get("hour_of_day"), 0.0),
        # CRT trade-specific
        "disp_strength":        disp_strength,
        "retest_depth":         _safe_float(trade_data.get("retest_depth"), 0.0),
        "candles_since_retest": int(_safe_float(trade_data.get("candles_since_retest"), 0.0)),
    }
    return ohlcv, auxiliary


class _DailyResetTracker:
    """Forces trades_today and daily_loss_pct to 0 on UTC day rollover (GAP-006)."""

    def __init__(self) -> None:
        self._last_reset_date: date | None = None

    def apply_reset_if_new_day(self, portfolio_state: dict) -> bool:
        today = datetime.now(timezone.utc).date()
        if self._last_reset_date == today:
            return False
        portfolio_state["trades_today"] = 0
        portfolio_state["daily_loss_pct"] = 0.0
        self._last_reset_date = today
        logger.warning(
            "DailyResetTracker: new UTC day %s — reset trades_today=0, daily_loss_pct=0.0",
            today,
        )
        return True


_daily_reset_tracker = _DailyResetTracker()


class HookedLiveEngine(LiveEngine):
    def process(
        self,
        trade_data: dict,
        gaussian_model,
        scaler,
        neural_fn=None,
        candle_idx: int = 0,
        timeframe: str = "M15",
    ) -> dict:
        result = super().process(
            trade_data, gaussian_model, scaler, neural_fn, candle_idx, timeframe
        )

        trade_id = str(trade_data.get("symbol", "UNKNOWN")) + "_" + str(candle_idx)

        # Build raw engine input (fallback path and baseline for FeatureStore split)
        engine_input = _build_engine_input(trade_data)

        # FeatureStore path — canonical ingestion boundary.
        # On success: engine_input is replaced by a validated FeatureFrame dict
        #   containing all 35 CANONICAL_FEATURES + _data_integrity="real".
        #   history-derived double_sweep is computed from the rolling sweep window.
        # On failure: WARNING logged; raw dict from _build_engine_input is used as-is.
        if _STORE_AVAILABLE and _feature_store is not None:
            try:
                _ohlcv, _auxiliary = _build_ohlcv_and_auxiliary(trade_data)
                _timestamp = trade_data.get("timestamp", candle_idx)
                _frame = _feature_store.process(candle_idx, _timestamp, _ohlcv, _auxiliary)
                engine_input = _frame.features  # dict: 35 canonical keys + _data_integrity
                logger.debug(
                    "FeatureStore: validated frame idx=%d sym=%s",
                    candle_idx, trade_data.get("symbol", "UNKNOWN"),
                )
            except Exception as _fs_err:
                logger.warning(
                    "FeatureStore: validation failed for %s candle %d — "
                    "using raw dict fallback: %s",
                    trade_data.get("symbol", "UNKNOWN"), candle_idx, _fs_err,
                )

        drift_features = {
            "body_ratio": float(engine_input.get("body_ratio", 0.0)),
            "retest_depth": float(engine_input.get("retest_depth", 0.0)),
            "disp_strength": float(engine_input.get("disp_strength", 0.0)),
        }

        context = {
            "gaussian_score": float(result.get("confidence", 0.0)),
            "gaussian_p_win": float(
                max(result.get("probabilities") or [0.5]) if result.get("probabilities") else 0.5
            ),
            "candles_since_retest": int(trade_data.get("candles_since_retest", 0)),
            "sweep_detected": bool(trade_data.get("sweep_detected", False)),
            "double_sweep": bool(trade_data.get("double_sweep", False)),
            "symbol": str(trade_data.get("symbol", "UNKNOWN")),
        }

        engine_config = _load_engine_config()

        # Drift detection (FeatureMonitor)
        _drift_severity = "none"
        if _MONITOR_AVAILABLE and _feature_monitor is not None:
            try:
                _feature_monitor.update(drift_features)
                _drift_severity = _feature_monitor.detect_drift_severity(drift_features)
                if _drift_severity == "hard":
                    logger.error(
                        "FeatureMonitor: HARD drift for %s at candle %d - "
                        "features strongly out-of-distribution (Z > 3.0). "
                        "Trade signal unreliable.",
                        trade_data.get("symbol", "UNKNOWN"),
                        candle_idx,
                    )
                elif _drift_severity == "soft":
                    logger.warning(
                        "FeatureMonitor: soft drift for %s at candle %d - "
                        "features mildly out-of-distribution (Z > 2.5).",
                        trade_data.get("symbol", "UNKNOWN"),
                        candle_idx,
                    )
            except Exception as _drift_err:
                logger.debug("FeatureMonitor update/detect failed (ignored): %s", _drift_err)

        engine_outputs = EngineRunner(engine_config).run(engine_input, context)

        exec_planner_cfg = engine_config.get("execution_planner")
        if not isinstance(exec_planner_cfg, dict):
            raise RuntimeError(
                "LIVE_HOOK: 'execution_planner' section missing from engine_config. "
                "Ensure _load_engine_config() includes it from v1_multi_2026_03.json."
            )
        # account_balance must be supplied by caller; no inline default
        if "account_balance" not in trade_data:
            raise KeyError(
                "LIVE_HOOK: 'account_balance' missing from trade_data. "
                "Caller must supply portfolio balance."
            )
        trade_context = {
            "symbol": str(trade_data.get("symbol", "UNKNOWN")),
            "signal": int(trade_data.get("signal", 0)),
            "score": float(engine_outputs.get("final_score", 0.0)),
            "account_balance": float(trade_data["account_balance"]),
        }
        planner = ExecutionPlannerV1_2(exec_planner_cfg)
        trade_plan = planner.plan(engine_outputs, engine_input, trade_context)
        logger.info(
            "ExecutionPlanner: %s | intent=%s | rr=%s",
            trade_plan.get("decision"),
            trade_plan.get("trade_intent"),
            trade_plan.get("rr_ratio"),
        )

        ultron_result = {"decision": "skipped", "risk_reason": "planner_did_not_execute"}
        if trade_plan.get("decision") == "execute":
            # Portfolio state keys must all be present in trade_data — no defaults
            required_portfolio_keys = (
                "account_balance", "total_open_risk_pct",
                "trades_today", "daily_loss_pct", "open_positions"
            )
            missing_ps = [k for k in required_portfolio_keys if k not in trade_data]
            if missing_ps:
                raise KeyError(
                    f"LIVE_HOOK: missing portfolio state keys in trade_data: {missing_ps}. "
                    "Caller must supply all portfolio state fields."
                )
            portfolio_state = {
                "account_balance":      float(trade_data["account_balance"]),
                "total_open_risk_pct":  float(trade_data["total_open_risk_pct"]),
                "trades_today":         int(trade_data["trades_today"]),
                "daily_loss_pct":       float(trade_data["daily_loss_pct"]),
                "open_positions":       int(trade_data["open_positions"]),
            }
            _daily_reset_tracker.apply_reset_if_new_day(portfolio_state)  # GAP-006
            ultron_cfg = engine_config.get("ultron_risk_gate")
            if not isinstance(ultron_cfg, dict):
                raise RuntimeError(
                    "LIVE_HOOK: 'ultron_risk_gate' missing from engine_config. "
                    "Ensure _load_engine_config() includes it."
                )
            # Regime-aware risk pre-scaling via UltronRiskGateWrapper (SR-1 compliant:
            # wrapper never bypasses UltronRiskGate — it only pre-scales risk_percent
            # by regime factor before delegating unconditionally to gate.evaluate()).
            # regime is set by EngineRunner.run() Step 6/7 and is always present.
            _regime = str(engine_outputs.get("regime", "neutral"))
            gate = UltronRiskGate(ultron_cfg)
            wrapper = UltronRiskGateWrapper(
                gate,
                regime_factors=ultron_cfg.get("regime_factors"),  # from ultron_risk_gate config
                debug_mode=bool(engine_config.get("debug_mode", False)),
            )
            ultron_result = wrapper.evaluate(trade_plan, portfolio_state, regime=_regime)
            logger.info(
                "UltronRiskGate: %s | reason=%s | size=%s | regime=%s | risk_factor=%s",
                ultron_result.get("decision"),
                ultron_result.get("risk_reason"),
                ultron_result.get("final_position_size"),
                _regime,
                wrapper._factors.get(_regime, 1.0),
            )

        outcome = {
            "win": False,
            "rr": float(trade_plan.get("rr_ratio", 0.0)),
            "gaussian_rr": float(result.get("expected_rr", 0.0)),
            "rr_fusion": float((engine_outputs.get("rr") or {}).get("rr", 0.0)),
            "p_win": float(context["gaussian_p_win"]),
            "trade_plan": trade_plan,
            "ultron": ultron_result,
            "drift_severity": _drift_severity,
        }
        collector.collect(trade_id, engine_input, engine_outputs, outcome, context=context)

        # Surface drift severity so upstream callers can decide whether to gate.
        result["drift_severity"] = _drift_severity
        return result
