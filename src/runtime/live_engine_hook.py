"""
live_engine_hook.py
Subclass wrapper around LiveEngine - does NOT modify live_engine.py.
Calls EngineRunner -> ExecutionPlannerV1_2 -> UltronRiskGate after process() returns.

Sprint 6 additions (non-breaking):
  - StrategyOrchestrator runs all 10 strategies per candle; result merged into output.
  - KillSwitch gate: if tripped, blocks execution and sends Telegram alert.
  - TelegramBridge: sends signal alerts and kill-switch notifications.
  - MT5Bridge: places/closes orders in MetaTrader 5 (dry_run=True until live).
  - register_trade_outcome(pnl_inr): call when a position closes to update KillSwitch.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone

import core.collector as collector

from core.engine_runner import EngineRunner
from core.gate_intelligence import compute_crt_levels
from engines.live_engine import LiveEngine
from config_layer.execution_planner import ExecutionPlannerV1_2
from config_layer.production_config import get_prod_metadata, get_prod_section
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

try:
    from strategies.strategy_orchestrator import StrategyOrchestrator
    _ORCH_AVAILABLE = True
except Exception:
    StrategyOrchestrator = None  # type: ignore[assignment,misc]
    _ORCH_AVAILABLE = False

try:
    from uat.kill_switch import KillSwitch
    _KS_AVAILABLE = True
except Exception:
    KillSwitch = None  # type: ignore[assignment,misc]
    _KS_AVAILABLE = False

try:
    from live.telegram_bridge import TelegramBridge
    _TELEGRAM_AVAILABLE = True
except Exception:
    TelegramBridge = None  # type: ignore[assignment,misc]
    _TELEGRAM_AVAILABLE = False

try:
    from live.mt5_bridge import MT5Bridge
    _MT5_AVAILABLE = True
except Exception:
    MT5Bridge = None  # type: ignore[assignment,misc]
    _MT5_AVAILABLE = False

try:
    from regime.regime_classifier import RegimeClassifier
    from regime.config_router import ConfigRouter
    _REGIME_AVAILABLE = True
except Exception:
    RegimeClassifier = None  # type: ignore[assignment,misc]
    ConfigRouter = None      # type: ignore[assignment,misc]
    _REGIME_AVAILABLE = False

logger = get_flow_logger("LIVE_HOOK")

from config_layer.production_config import PROD_VERSION as _LIVE_PROD_VERSION
logger.info("Production config version: %s", _LIVE_PROD_VERSION)

_ENGINE_CONFIG_CACHE: dict | None = None
_feature_monitor = None  # initialized lazily from config
_feature_store = None    # FeatureStore singleton — canonical ingestion boundary

# Sprint 6 singletons — initialized lazily on first process() call
_orchestrator: "StrategyOrchestrator | None" = None
_kill_switch:  "KillSwitch | None"           = None
_telegram:     "TelegramBridge | None"       = None
_mt5:          "MT5Bridge | None"            = None
_live_cfg:          dict | None                   = None
_regime_classifier: "RegimeClassifier | None"    = None
_config_router:     "ConfigRouter | None"         = None


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _require_ohlcv_value(data: dict, field: str, *, source: str = "Live trade_data") -> float:
    """Strict accessor for a mandatory OHLCV field — no default, no substitution.

    Raises ValueError if the field is absent, None, non-numeric, or NaN/inf.
    """
    if field not in data or data[field] is None:
        raise ValueError(f"{source} missing required field: {field}")
    try:
        v = float(data[field])
    except (TypeError, ValueError):
        raise ValueError(f"{source} field '{field}' is not numeric: {data[field]!r}")
    if v != v or v in (float("inf"), float("-inf")):  # NaN/inf guard
        raise ValueError(f"{source} field '{field}' is NaN/inf")
    return v


def _require_feature_value(data: dict, field: str, *, source: str = "Live trade_data") -> float:
    """Strict accessor for a mandatory DERIVED feature — no default, no substitution.

    T-11 (2026-07-19), user rule: **no silent fallback**. Sibling of `_require_ohlcv_value`; the
    OHLCV six were already strict while every derived feature went through
    `_safe_float(get(x), <default>)`. Those defaults were not neutral:

      * `ema_fast`/`ema_slow` defaulted to `close` — a PRICE substituted for a moving average,
        which also drove `ema_spread`->0 and `trend_bias`->0. Three canonical features became
        plausible, wrong and mutually consistent — undetectable by any range check.
      * `atr` defaulted to 0.0, silently disabling every `if state.atr_abs > 0` CRT guard: the
        engine did not error, it quietly stopped applying its own logic.
      * `0.0` is a LEGITIMATE value for most structure flags, so a defaulted field was
        indistinguishable from a real one.

    Raises ValueError if the field is absent, None, non-numeric, or NaN/inf.
    """
    if field not in data or data[field] is None:
        raise ValueError(
            f"{source} missing required feature field: {field!r}. "
            "No default is substituted (T-11 no-silent-fallback rule) — the producer must "
            "supply every field in _REQUIRED_FEATURE_FIELDS."
        )
    try:
        v = float(data[field])
    except (TypeError, ValueError):
        raise ValueError(f"{source} feature field {field!r} is not numeric: {data[field]!r}")
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError(f"{source} feature field {field!r} is NaN/inf")
    return v


def _require_cfg(cfg: dict, key: str, section: str) -> object:
    """Strict CONFIG accessor — raises if the key is absent (T-22, CLAUDE.md Section 6.5).

    Section 6.5 hard rule: *"A missing key/section is an error (raise) — never
    `get_prod_section(...).get(key, literal)`."* Mirrors the ten sibling `_require`-style
    accessors already in this repo (`core/engine_runner._cfg_require`,
    `config_layer/config_validator._validator_require`, `features/feature_pipeline._require_fp_cfg`,
    the three `inout` fetchers, ...). A soft default here is worse than a missing key: it lets a
    silently-undeclared literal govern live behaviour while looking configured.
    """
    if not isinstance(cfg, dict) or key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from section '{section}'. "
            "Add it to the active production config (no silent config defaults)."
        )
    return cfg[key]


def _precision(symbol: str, exec_cfg: dict) -> int:
    """Return decimal precision for rounding prices for a given symbol.

    `precision_overrides` is an optional per-symbol MAP (absence means "no override for this
    symbol", not a missing value), so `.get(symbol, <default>)` is correct there — but the
    fallback itself is now a strict config read.
    """
    return int(
        exec_cfg.get("precision_overrides", {}).get(
            symbol, _require_cfg(exec_cfg, "precision_default", "execution_planner")
        )
    )


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
    # T-11: no silent fallback. `None` previously became "london" — fabricating a specific
    # trading session. Callers must not pass None (_derive_session already guards this).
    if value is None:
        raise ValueError(
            "_normalize_session received None — session cannot be defaulted "
            "(T-11 no-silent-fallback rule); it gates trade admission."
        )
    key = str(value).strip().lower()
    normalized = session_map.get(key, session_map.get(value))
    if normalized is None:
        raise ValueError(
            f"Unrecognised session value {value!r}. Expected one of "
            f"{sorted(set(session_map.values()))} or a known alias — not silently passed through."
        )
    return normalized


def _require_symbol(data: dict, *, source: str = "Live trade_data") -> str:
    """Strict accessor for the instrument symbol — no fabricated default (T-11).

    Two call sites previously defaulted to ``"EURUSD"``, which invents a specific instrument:
    orchestrator routing and downstream logging would then attribute a decision to the wrong
    market. ``"UNKNOWN"`` (used for pure log strings elsewhere) is at least honest; a concrete
    ticker is not.
    """
    v = data.get("symbol")
    if v is None or not str(v).strip():
        raise ValueError(
            f"{source} missing required field: 'symbol'. No default is substituted "
            "(T-11 no-silent-fallback rule) — a fabricated ticker misattributes the decision."
        )
    return str(v)


def _derive_session(trade_data: dict) -> str:
    """Resolve the session label. RAISES if the feeder supplies none (T-11).

    Previously this returned ``"london"`` when nothing was supplied — fabricating a specific
    trading session. That is a substantive claim about the world, not a neutral default, and
    session is decision-critical: it gates trade admission (the 2026-07-19 XAUUSD run had 100%
    of its candidates rejected by the session filter, `off_session:*`). A silently-invented
    "london" could therefore both admit and reject trades on fiction.

    The `is_asia`/`is_london`/`is_newyork` flags remain an accepted ALTERNATIVE encoding, not a
    fallback chain: one of them, or an explicit `session`, must be present.
    """
    if "session" in trade_data and trade_data.get("session") is not None:
        return _normalize_session(trade_data.get("session"))
    # Alternative boolean-flag encoding. Absent flags are treated as 0 ONLY to test which flag is
    # set — if none is set we raise rather than choosing a session.
    if _safe_float(trade_data.get("is_asia"), 0.0) > 0.5:
        return "asia"
    if _safe_float(trade_data.get("is_london"), 0.0) > 0.5:
        return "london"
    if _safe_float(trade_data.get("is_newyork"), 0.0) > 0.5:
        return "new_york"
    raise ValueError(
        "Live trade_data missing session: supply 'session', or exactly one of "
        "'is_asia'/'is_london'/'is_newyork'. No default is substituted "
        "(T-11 no-silent-fallback rule) — session gates trade admission."
    )


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

    # C3 (2026-07-29): crt_engine was ABSENT from this merge, so the SL/TP block in
    # process() read `engine_config.get("crt_engine", {})` -> always {}. Its strict
    # `_require_cfg(_crt_cfg, "sl_atr_buffer", "crt_engine")` therefore raised
    # KeyError on EVERY execute decision (before SL/TP/RR/size were set, with no
    # wrapping try), and the per-intent TP1 multipliers silently collapsed to the
    # 1.0 literal. Carried as a NESTED key deliberately: crt_engine shares key names
    # with the flattened engine_runner/decision_engine dicts above, so a flat
    # merge would silently overwrite unrelated live behaviour.
    crt_cfg = metadata.get("crt_engine")
    if not isinstance(crt_cfg, dict):
        raise RuntimeError(
            "LIVE_HOOK: 'crt_engine' section missing from production config. "
            "It supplies sl_atr_buffer and the per-intent TP multipliers to the "
            "live SL/TP block. Add it to the active production config."
        )

    # Merged flat config: engine_runner + decision_engine + nested sections
    # fusion_engine is kept as nested key so EngineRunner can access it correctly
    merged = {}
    merged.update(engine_cfg)
    merged.update(decision_cfg)
    merged["fusion_engine"] = fusion_cfg
    merged["ultron_risk_gate"] = ultron_cfg
    merged["execution_planner"] = exec_planner_cfg
    merged["crt_engine"] = crt_cfg

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
        _feature_monitor = FeatureMonitor(
            window_size=int(window_size),
            soft_threshold=float(_require_cfg(fm_cfg, "soft_drift_z", "feature_monitor")),
            hard_threshold=float(_require_cfg(fm_cfg, "hard_drift_z", "feature_monitor")),
        )

    # Initialize FeatureStore as canonical ingestion boundary.
    # Validates all CANONICAL_FEATURES (39 under schema v4.0), computes history-derived
    # double_sweep,
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

    # ── Per-session config dump ────────────────────────────────────────────
    try:
        from datetime import datetime as _dt, timezone as _tz
        from utils.config_dumper import dump_config as _dump_config
        from config_layer.production_config import get_full_config_dict, PRODUCTION_REGISTRY_DIR
        _run_id = _dt.now(_tz.utc).strftime("live_%Y%m%d_%H%M%S")
        _full_reg = get_full_config_dict()
        _dump_payload = {
            "mode":               "live",
            "config_version":     _LIVE_PROD_VERSION,
            "source_config_path": f"{PRODUCTION_REGISTRY_DIR}/{_LIVE_PROD_VERSION}.json",
            "overrides":          {},
            "engine_runner":      merged,
            "crt_engine":         _full_reg.get("crt_engine", {}),
            "execution_planner":  _full_reg.get("execution_planner", {}),
            "fusion_engine":      _full_reg.get("fusion_engine", {}),
            "ultron_risk_gate":   _full_reg.get("ultron_risk_gate", {}),
        }
        _dump_path = _dump_config(_dump_payload, instrument="LIVE", run_id=_run_id)
        logger.info("Full config dumped to: %s", _dump_path)
    except Exception as _dump_err:
        logger.warning("Config dump skipped: %s", _dump_err)

    return merged


def _build_engine_input(trade_data: dict) -> dict:
    """Strict engine input — every consumed field is mandatory (T-11).

    ONE uniform rule: no tiering, no "acceptable" silent default. A missing field raises rather
    than resolving to a plausible-looking number.
    """
    # Six OHLCV fields are mandatory — strict access, no cascade/default.
    close = _require_ohlcv_value(trade_data, "close")
    open_ = _require_ohlcv_value(trade_data, "open")
    high = _require_ohlcv_value(trade_data, "high")
    low = _require_ohlcv_value(trade_data, "low")
    # `disp_str` remains an accepted ALIAS for disp_strength (a naming variant, not a default):
    # if neither spelling is present the strict accessor still raises.
    if "disp_strength" not in trade_data and "disp_str" in trade_data:
        trade_data = {**trade_data, "disp_strength": trade_data["disp_str"]}

    return {
        "_data_integrity": "real",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": _require_ohlcv_value(trade_data, "volume"),
        "atr": _require_feature_value(trade_data, "atr"),
        "ema_fast": _require_feature_value(trade_data, "ema_fast"),
        "ema_slow": _require_feature_value(trade_data, "ema_slow"),
        "session": _derive_session(trade_data),
        "trend_bias": _require_feature_value(trade_data, "trend_bias"),
        "ema_spread": _require_feature_value(trade_data, "ema_spread"),
        "momentum_score": _require_feature_value(trade_data, "momentum_score"),
        "volatility_ratio": _require_feature_value(trade_data, "volatility_ratio"),
        "sweep_detected": _require_feature_value(trade_data, "sweep_detected"),
        "double_sweep": _require_feature_value(trade_data, "double_sweep"),
        "body_ratio": _require_feature_value(trade_data, "body_ratio"),
        "disp_strength": _require_feature_value(trade_data, "disp_strength"),
        "retest_depth": _require_feature_value(trade_data, "retest_depth"),
        "candles_since_retest": int(_require_feature_value(trade_data, "candles_since_retest")),
    }


def _build_ohlcv_and_auxiliary(trade_data: dict) -> tuple[dict, dict]:
    """
    Split trade_data into (ohlcv, auxiliary) for FeatureStore.process().

    ohlcv     — 5 core OHLCV fields required by FeatureStore._ensure_required().
    auxiliary — all remaining CANONICAL_FEATURES. T-11 (2026-07-19): every one is MANDATORY;
                a missing field raises rather than defaulting to 0.0/1.0/close. The sole
                exception is double_sweep, which is a placeholder overwritten by
                FeatureStore._compute_derived() with the history-correct value.
                _data_integrity is NOT included — FeatureStore adds it post-validation.

    Returns (ohlcv: dict, auxiliary: dict).
    """
    # Six OHLCV fields are mandatory — strict access, no cascade/default.
    close  = _require_ohlcv_value(trade_data, "close")
    open_  = _require_ohlcv_value(trade_data, "open")
    high   = _require_ohlcv_value(trade_data, "high")
    low    = _require_ohlcv_value(trade_data, "low")
    volume = _require_ohlcv_value(trade_data, "volume")

    ohlcv = {"open": open_, "high": high, "low": low, "close": close, "volume": volume}

    # Derived candle anatomy (computed here; FeatureStore does not derive these).
    # Phase-1 identity closure (2026-07-10, GD-001) bound the live math to
    # FEAT-BODY_TO_TOTAL_WICK_RATIO explicitly and dual-emitted both keys — lint-clean, but it
    # left the runtime KEY `body_ratio` carrying body/total_wick while the pipeline, the CRT
    # `Candle` property and the `body_ratio >= 0.70` gate all mean body/range.
    #
    # T-16 (2026-07-23): the runtime key now carries the CANONICAL identity
    # (FEAT-BODY_TO_RANGE_RATIO / FM-010), closing the last live-vs-batch formula divergence for
    # a real feature. Both identities stay dual-emitted under their own explicit names, so
    # nothing loses access to either. Behavior-changing on the live path by construction; per
    # F-047 V1-V10 the body_ratio flip reaches only the fused SCORE (reject-REASON), not the
    # execute/veto boundary. NOTE (F-048 RESOLVED 2026-07-24): the old "run() executes 0/70,002
    # because the RR gate compares polarity∈[0.5,1] vs rr_threshold=1.5" reasoning is SUPERSEDED —
    # that RR gate has been removed (DecisionEngine is semantic-only; economic RR = UltronRiskGate).
    # run() can now reach execute when the semantic gates pass, so the structural-inertness claim
    # for body_ratio must be re-derived, not assumed — this comment no longer asserts it.
    from features import candle_math as _cm
    body_size = _cm.body_size(open_, close)
    # Live legacy wick_size = total_wick (not pipeline candle_range) — FOLLOW_UP identity
    wick_size = max(0.0, _cm.total_wick(open_, high, low, close))
    # v4.0: the CANONICAL slot is `candle_range` = high - low, bound to the registered FM-002
    # identity. This is a DIFFERENT quantity from the live `wick_size` above (total_wick); the
    # rename made that distinction visible rather than creating it (GD-001/GD-002, F-047).
    candle_range = _cm.candle_range(high, low)
    body_to_total_wick_ratio = _cm.body_to_total_wick_ratio(open_, high, low, close)
    body_to_range_ratio = _cm.body_ratio(open_, high, low, close)
    # The runtime schema key `body_ratio` carries the CANONICAL body/range identity (FM-010),
    # matching the batch pipeline and crt_engine_v2's Candle.body_ratio property. The total_wick
    # quantity remains available under its own unambiguous name below.
    body_ratio = body_to_range_ratio

    # `disp_str` is an accepted ALIAS (naming variant), not a default — if neither spelling is
    # present the strict accessor below still raises.
    if "disp_strength" not in trade_data and "disp_str" in trade_data:
        trade_data = {**trade_data, "disp_strength": trade_data["disp_str"]}

    _req = _require_feature_value  # every field below is mandatory (T-11, one uniform rule)
    auxiliary = {
        # EMA / trend
        "atr":                  _req(trade_data, "atr"),
        "ema_fast":             _req(trade_data, "ema_fast"),
        "ema_slow":             _req(trade_data, "ema_slow"),
        "ema_spread":           _req(trade_data, "ema_spread"),
        "session":              _derive_session(trade_data),
        "trend_bias":           _req(trade_data, "trend_bias"),
        "trend_strength":       _req(trade_data, "trend_strength"),
        "momentum_score":       _req(trade_data, "momentum_score"),
        "volatility_ratio":     _req(trade_data, "volatility_ratio"),
        # Volume
        "volume_ratio":         _req(trade_data, "volume_ratio"),
        # Structure / sweep
        "sweep_detected":       _req(trade_data, "sweep_detected"),
        # NOT a default: FeatureStore._compute_derived() overwrites this with the
        # history-correct value, so the placeholder is never read as data.
        "double_sweep":         0.0,
        "liquidity_sweep":      _req(trade_data, "liquidity_sweep"),
        "break_of_structure":   _req(trade_data, "break_of_structure"),
        # Swing levels
        "swing_high":           _req(trade_data, "swing_high"),
        "swing_low":            _req(trade_data, "swing_low"),
        "higher_high":          _req(trade_data, "higher_high"),
        "lower_low":            _req(trade_data, "lower_low"),
        # Candle anatomy — identity-bound (Phase-1), computed here from strict OHLCV
        "body_size":            body_size,
        # v4.0 rename: the canonical slot is `candle_range` (high - low). NOTE the live path's
        # local `wick_size` variable is total_wick, NOT the range — the pre-existing GD-001/GD-002
        # divergence (F-047), unchanged here and still tracked separately. The canonical key now
        # carries the canonical quantity; the divergent live value keeps its own name.
        "candle_range":         candle_range,
        "wick_size":            wick_size,  # live total_wick — NON-canonical, GD-002 (F-047)
        "body_ratio":           body_ratio,  # CANONICAL body/range (FM-010) since T-16
        "body_to_total_wick_ratio": body_to_total_wick_ratio,
        "body_to_range_ratio":  body_to_range_ratio,
        # Regime / volatility
        "volatility_regime":    _req(trade_data, "volatility_regime"),
        # Indicators — MANDATORY. Previously "passed through if supplied, otherwise 0.0", which
        # made a defaulted indicator indistinguishable from a real zero reading.
        "rsi_14":               _req(trade_data, "rsi_14"),
        "macd_line":            _req(trade_data, "macd_line"),
        "macd_signal":          _req(trade_data, "macd_signal"),
        # v4.0 MACD split. The feeder supplies the value v3.0 called `macd_hist`, which was the
        # Z-SCORED one (compute_normalization overwrote it in place), so it maps to macd_hist_z.
        # macd_hist_raw is derived here from the two MACD legs — the declared FM-049 formula.
        "macd_hist_z":          _req(trade_data, "macd_hist"),
        "macd_hist_raw":        float(_req(trade_data, "macd_line")) - float(_req(trade_data, "macd_signal")),
        # Time
        "hour_of_day":          _req(trade_data, "hour_of_day"),
        # CRT trade-specific
        "disp_strength":        _req(trade_data, "disp_strength"),
        "retest_depth":         _req(trade_data, "retest_depth"),
        "candles_since_retest": int(_req(trade_data, "candles_since_retest")),
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


# ── Sprint 6: lazy singleton initialisation ────────────────────────────────────

def _get_live_cfg() -> dict:
    global _live_cfg
    if _live_cfg is None:
        _live_cfg = get_prod_section("live_integration") or {}
    return _live_cfg


def _get_orchestrator(pair: str, timeframe: str) -> "StrategyOrchestrator | None":
    global _orchestrator
    if _orchestrator is None and _ORCH_AVAILABLE and StrategyOrchestrator is not None:
        try:
            _orchestrator = StrategyOrchestrator(pair=pair, timeframe=timeframe)
            logger.info("LIVE_HOOK: StrategyOrchestrator initialised (%s/%s).", pair, timeframe)
        except Exception as exc:
            logger.warning("LIVE_HOOK: StrategyOrchestrator init failed (ignored): %s", exc)
    return _orchestrator


def _get_regime_classifier() -> "RegimeClassifier | None":
    global _regime_classifier, _config_router
    if _regime_classifier is None and _REGIME_AVAILABLE and RegimeClassifier is not None:
        try:
            _regime_classifier = RegimeClassifier()
            _config_router = ConfigRouter() if ConfigRouter is not None else None
            logger.info("LIVE_HOOK: RegimeClassifier initialised.")
        except Exception as exc:
            logger.warning("LIVE_HOOK: RegimeClassifier init failed (ignored): %s", exc)
    return _regime_classifier


def _get_kill_switch() -> "KillSwitch | None":
    global _kill_switch
    if _kill_switch is None and _KS_AVAILABLE and KillSwitch is not None:
        try:
            _kill_switch = KillSwitch.from_prod_config()
            logger.info("LIVE_HOOK: KillSwitch initialised.")
        except Exception as exc:
            logger.warning("LIVE_HOOK: KillSwitch init failed (ignored): %s", exc)
    return _kill_switch


def _get_telegram() -> "TelegramBridge | None":
    global _telegram
    if _telegram is None and _TELEGRAM_AVAILABLE and TelegramBridge is not None:
        try:
            _telegram = TelegramBridge.from_prod_config()
        except Exception as exc:
            logger.warning("LIVE_HOOK: TelegramBridge init failed (ignored): %s", exc)
    return _telegram


def _get_mt5() -> "MT5Bridge | None":
    global _mt5
    if _mt5 is None and _MT5_AVAILABLE and MT5Bridge is not None:
        try:
            _mt5 = MT5Bridge.from_prod_config()
            _mt5.connect()
        except Exception as exc:
            logger.warning("LIVE_HOOK: MT5Bridge init failed (ignored): %s", exc)
    return _mt5


def register_trade_outcome(pnl_inr: float) -> bool:
    """
    Call this when a position closes to update the KillSwitch loss accumulators.

    Returns True if the kill switch just tripped on this outcome.
    Safe to call even if KillSwitch is unavailable (returns False).
    """
    ks = _get_kill_switch()
    if ks is None:
        return False
    just_tripped = ks.register_trade(pnl_inr=pnl_inr)
    if just_tripped:
        tg = _get_telegram()
        if tg is not None:
            try:
                tg.send_kill_switch(
                    reason       = ks.trip_reason(),
                    daily_loss_inr  = ks.daily_loss_inr(),
                    weekly_loss_inr = ks.weekly_loss_inr(),
                )
            except Exception as exc:
                logger.warning("LIVE_HOOK: Telegram kill-switch alert failed: %s", exc)
    return just_tripped


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

        # Build raw engine input (fallback path and baseline for FeatureStore split).
        # _build_engine_input enforces the six OHLCV fields (fail-fast here, not
        # swallowed by the FeatureStore try-block below). timestamp is likewise
        # mandatory and must never be derived from the candle index.
        engine_input = _build_engine_input(trade_data)
        if "timestamp" not in trade_data or trade_data["timestamp"] is None:
            raise ValueError("Live trade_data missing required field: timestamp")

        # FeatureStore path — canonical ingestion boundary.
        # On success: engine_input is replaced by a validated FeatureFrame dict containing all
        #   CANONICAL_FEATURES + _data_integrity="real"; history-derived double_sweep is computed
        #   from the rolling sweep window.
        #
        # T-11 (2026-07-19) — FAIL CLOSED. This block previously caught every exception, logged a
        # WARNING and CONTINUED with the un-validated `_build_engine_input` dict. Because
        # FeatureStore._ensure_required() is the ONLY thing enforcing the canonical field
        # contract, catching its failure meant the validation failure was itself what disabled
        # the validation — the engine then scored a real decision on defaulted data with nothing
        # but a warning line. A validation failure must REJECT the tick, never downgrade it.
        # No kill-switch flag by deliberate decision: such a flag gets switched on under pressure
        # and left on.
        if _STORE_AVAILABLE and _feature_store is not None:
            _ohlcv, _auxiliary = _build_ohlcv_and_auxiliary(trade_data)
            _timestamp = trade_data["timestamp"]  # guaranteed present (checked above)
            _frame = _feature_store.process(candle_idx, _timestamp, _ohlcv, _auxiliary)
            engine_input = _frame.features  # dict: canonical keys + _data_integrity
            logger.debug(
                "FeatureStore: validated frame idx=%d sym=%s",
                candle_idx, trade_data.get("symbol", "UNKNOWN"),
            )

        _get_regime_classifier()  # ensure singleton initialised before context block

        # Direct indexing, no defaults: engine_input is now the STRICT/validated frame, so these
        # keys are guaranteed present. A `.get(k, 0.0)` here could only mask a contract break.
        drift_features = {
            "body_ratio": float(engine_input["body_ratio"]),
            "retest_depth": float(engine_input["retest_depth"]),
            "disp_strength": float(engine_input["disp_strength"]),
        }

        context = {
            "gaussian_score": float(result.get("confidence", 0.0)),
            "gaussian_p_win": float(
                max(result.get("probabilities") or [0.5]) if result.get("probabilities") else 0.5
            ),
            # Read from the VALIDATED engine_input, not raw trade_data. These three were
            # re-read from the feeder with defaults while the same fields were strict in
            # engine_input — the same value could be real in one path and defaulted in the
            # other. double_sweep in particular is history-derived by FeatureStore, so the
            # feeder's raw value was the wrong source regardless.
            "candles_since_retest": int(engine_input["candles_since_retest"]),
            "sweep_detected": bool(engine_input["sweep_detected"]),
            "double_sweep": bool(engine_input["double_sweep"]),
            "symbol": str(trade_data.get("symbol", "UNKNOWN")),
            "timeframe": str(trade_data.get("timeframe", timeframe)),
        }

        # Regime injection — classify market regime and inject into context so
        # EngineRunner can select regime-aware fusion weights via ConfigRouter.
        if _REGIME_AVAILABLE and _regime_classifier is not None:
            try:
                regime_label = _regime_classifier.classify(engine_input)
                context["regime"] = regime_label
                if _config_router is not None:
                    context["fusion_weights"] = _config_router.get_fusion_weights(regime_label)
                logger.debug(
                    "LIVE_HOOK: regime=%s for %s candle %d",
                    regime_label, trade_data.get("symbol", "UNKNOWN"), candle_idx,
                )
            except Exception as _regime_err:
                logger.debug("LIVE_HOOK: RegimeClassifier failed (ignored): %s", _regime_err)

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

        # ── 5th engine: StrategyOrchestrator consensus ──────────────────────────
        # Must run BEFORE EngineRunner.run() so the score can be injected into
        # the context dict and picked up by FusionEngine.compute() as a 5th
        # weighted input.  The parallel post-hoc call in Sprint 6 is removed.
        _orch_pair = _require_symbol(trade_data)
        _orch_tf   = str(trade_data.get("timeframe", timeframe))
        _orch_pre  = _get_orchestrator(pair=_orch_pair, timeframe=_orch_tf)
        _orch_result = None
        if _orch_pre is not None:
            try:
                _orch_candle = {
                    "open":   float(engine_input["open"]),
                    "high":   float(engine_input["high"]),
                    "low":    float(engine_input["low"]),
                    "close":  float(engine_input["close"]),
                    "volume": float(engine_input["volume"]),
                }
                # Phase A/B: inject CRT transition path so StrategyIntentBuilder
                # can use CRT-enriched evidence for S01/S10.
                # Live hook is request-based (no continuous CRT state machine here).
                # [] → builder falls back to generic feature-summary evidence (graceful).
                # TODO: when a live CRT state machine is wired, replace with:
                #   from config_layer.crt_engine_v2 import recent_transition_path
                #   engine_input["_transition_path"] = recent_transition_path(crt_state)
                engine_input.setdefault("_transition_path", [])
                _orch_result = _orch_pre.compute(engine_input, _orch_candle)
                # Inject consensus into context so EngineRunner forwards it to FusionEngine
                context["strategy_consensus_score"] = float(_orch_result.confidence)
                context["strategy_consensus_direction"] = (
                    1 if _orch_result.signal == "BUY"
                    else (-1 if _orch_result.signal == "SELL" else 0)
                )
                logger.debug(
                    "LIVE_HOOK: StrategyOrchestrator pre-run %s/%s signal=%s conf=%.2f",
                    _orch_pair, _orch_tf, _orch_result.signal, _orch_result.confidence,
                )
            except Exception as _orch_pre_err:
                logger.warning(
                    "LIVE_HOOK: StrategyOrchestrator pre-run failed (ignored): %s",
                    _orch_pre_err,
                )

        # Thread direction into engine_input so Gaussian engine scores direction-aware.
        # Mirrors backtest_v2.py lines 1639-1641 (direction / signal_dir / trade_direction).
        _dir_val = int(context.get("strategy_consensus_direction", 0))
        engine_input["direction"]        = _dir_val
        engine_input["signal_dir"]       = _dir_val
        engine_input["trade_direction"]  = _dir_val

        engine_outputs = EngineRunner(engine_config).run(engine_input, context)

        exec_planner_cfg = engine_config.get("execution_planner")
        if not isinstance(exec_planner_cfg, dict):
            raise RuntimeError(
                "LIVE_HOOK: 'execution_planner' section missing from engine_config. "
                "Ensure _load_engine_config() includes it from v1_multi_2026_03.json."
            )
        # Merge gate_intelligence config so GateIntelligence receives its thresholds
        exec_planner_cfg = {
            **exec_planner_cfg,
            **engine_config.get("gate_intelligence", {}),
        }
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
            "ExecutionPlanner: %s | intent=%s | gate_score=%s",
            trade_plan.get("decision"),
            trade_plan.get("trade_intent"),
            trade_plan.get("gate", {}).get("final_score"),
        )

        ultron_result = {"decision": "skipped", "risk_reason": "planner_did_not_execute"}
        if trade_plan.get("decision") == "execute":
            # ── CRT-style SL/TP (CRT engine is sole SL/TP authority) ─────────
            _crt_cfg  = engine_config.get("crt_engine", {})
            _intent   = trade_plan.get("trade_intent", "UNKNOWN").upper()
            _tp1_key  = f"tp1_atr_multiplier_{_intent.lower()}"
            # ── T-16 (2026-07-23) RESOLVED by C3 (2026-07-29). The config illusion this
            # block used to document is CLOSED: `_load_engine_config()` now carries the
            # `crt_engine` section (nested), so `_crt_cfg` is the real section rather than
            # an always-empty dict.
            #
            # What that changed, stated plainly (this was a LIVE BEHAVIOUR CHANGE, made by
            # explicit user decision, not a parity-safe refactor):
            #   * `sl_atr_buffer` below used to raise KeyError on EVERY execute — the strict
            #     read hit the empty dict — so the live path could never reach SL/TP at all.
            #   * the per-intent TP1 multipliers now GOVERN instead of collapsing to 1.0:
            #     breakout 1.0->1.5, liq_sweep 1.0->1.2, pullback 1.0->0.8
            #     (reversal 1.0 and tp2 2.0 are unchanged in value).
            #
            # The `.get(..., <literal>)` fallbacks are retained ONLY as a last-resort guard for
            # a config that omits an optional per-intent key; the section's presence is now
            # enforced upstream in _load_engine_config(). Floor:
            # tests/test_live_hook_crt_config_plumbing.py.
            _tp1_mult = float(_crt_cfg.get(_tp1_key, _crt_cfg.get("tp1_atr_multiplier", 1.0)))
            _tp2_mult = float(_crt_cfg.get("tp2_atr_multiplier", 2.0))
            _crt = compute_crt_levels(
                entry        = float(trade_plan["entry_price"]),
                direction    = int(trade_plan["direction"]),
                low          = float(engine_input["low"]),
                high         = float(engine_input["high"]),
                atr          = float(engine_input["atr"]),
                sl_atr_buffer= float(_require_cfg(_crt_cfg, "sl_atr_buffer", "crt_engine")),
                tp1_mult     = _tp1_mult,
                tp2_mult     = _tp2_mult,
            )
            _prec = _precision(trade_plan["symbol"], exec_planner_cfg)
            trade_plan["stop_loss"]        = round(_crt["sl"],  _prec)
            trade_plan["take_profit_1"]    = round(_crt["tp1"], _prec)
            trade_plan["take_profit_2"]    = round(_crt["tp2"], _prec)
            # Contract D — true economic RR from SL/TP geometry (not RREngine polarity).
            # Primary target = TP1; TP2 R stored for audit. UltronRiskGate.min_rr_ratio
            # consumes trade_plan["rr_ratio"] (post cost tax when configured).
            _entry_px = float(trade_plan["entry_price"])
            _sl_px = float(trade_plan["stop_loss"])
            _tp1_px = float(trade_plan["take_profit_1"])
            _tp2_px = float(trade_plan["take_profit_2"])
            _risk_px = abs(_entry_px - _sl_px)
            if _risk_px > 0:
                trade_plan["rr_ratio"] = round(abs(_tp1_px - _entry_px) / _risk_px, 6)
                trade_plan["rr_ratio_tp2"] = round(abs(_tp2_px - _entry_px) / _risk_px, 6)
            else:
                trade_plan["rr_ratio"] = 0.0
                trade_plan["rr_ratio_tp2"] = 0.0
            trade_plan["rr_source"] = "sl_tp_geometry"
            trade_plan["risk_percent"]     = float(_require_cfg(exec_planner_cfg, "risk_percent", "execution_planner"))
            _risk_dist = _crt["risk_dist"]
            _balance   = float(trade_data["account_balance"])
            trade_plan["position_size_hint"] = (
                round((_balance * trade_plan["risk_percent"] / 100.0) / _risk_dist, 4)
                if _risk_dist > 0 else None
            )
            logger.info(
                "CRT levels: sl=%.5f tp1=%.5f tp2=%.5f risk_dist=%.5f rr_tp1=%.4f rr_tp2=%.4f (D/SL-TP)",
                trade_plan["stop_loss"],
                trade_plan["take_profit_1"],
                trade_plan["take_profit_2"],
                _risk_dist,
                float(trade_plan.get("rr_ratio", 0.0)),
                float(trade_plan.get("rr_ratio_tp2", 0.0)),
            )

            # ── GAP-6 fix: Naked-order guard ──────────────────────────────────
            # compute_crt_levels() returns sl=0.0 / tp=0.0 when ATR=0 or the
            # direction is unknown.  UltronRiskGate's Check 6 handles sl==entry
            # but never validates TP — a broker order with tp=0 goes out naked.
            # Reject before touching portfolio state to keep the gate stateless.
            _sl_ok = bool(trade_plan.get("stop_loss"))
            _tp_ok = bool(trade_plan.get("take_profit_1"))
            if not _sl_ok or not _tp_ok:
                logger.error(
                    "LIVE_HOOK: SL/TP incomplete after CRT levels "
                    "(sl=%s tp1=%s risk_dist=%.5f) — rejecting to prevent naked order.",
                    trade_plan.get("stop_loss"), trade_plan.get("take_profit_1"), _risk_dist,
                )
                ultron_result = {
                    "decision":            "reject",
                    "risk_reason":         "MISSING_SL_TP",
                    "execution_id":        trade_plan.get("execution_id", "UNKNOWN"),
                    "final_position_size": 0.0,
                    "portfolio_state":     {},
                }
            else:
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
                    # T-16: strict — `debug_mode` is declared in the engine_runner section and
                    # IS present in the merged engine_config (verified), so the literal fallback
                    # was dead weight that would have masked a future config regression.
                    debug_mode=bool(_require_cfg(engine_config, "debug_mode", "engine_runner")),
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
            # ── BitNet adaptive-threshold audit (defaults preserve old shape) ──
            # Live path does not currently invoke BitNet inference; fields are
            # populated only if EngineRunner forwards a bitnet_score upstream.
            "bitnet_score_at_entry":    float(engine_outputs.get("bitnet_score", 0.0)),
            "bitnet_decision_at_entry": str(engine_outputs.get("bitnet_decision", "")),
        }
        collector.collect(trade_id, engine_input, engine_outputs, outcome, context=context)

        # ── Sprint 6: StrategyOrchestrator + KillSwitch + Telegram + MT5 ───────

        _pair = _require_symbol(trade_data)
        _tf   = str(trade_data.get("timeframe", timeframe))

        # 1. Kill switch pre-check — block if already tripped
        _ks = _get_kill_switch()
        _ks_blocked = False
        if _ks is not None and _ks.is_tripped():
            _ks_blocked = True
            logger.warning(
                "LIVE_HOOK: KillSwitch ACTIVE (%s) — blocking execution for %s.",
                _ks.trip_reason(), _pair,
            )
            result["ks_blocked"]  = True
            result["ks_reason"]   = _ks.trip_reason()
            result["drift_severity"] = _drift_severity
            return result

        # StrategyOrchestrator already ran as 5th engine before EngineRunner — see
        # pre-run block above.  Attach its result to output for callers/logging.
        if _orch_result is not None:
            result["orchestrator"] = _orch_result.to_dict()

        # 2. Send Telegram signal alert if ultron approved
        if ultron_result.get("decision") == "APPROVE" and not _ks_blocked:
            _tg = _get_telegram()
            if _tg is not None:
                try:
                    _sl_inr = float(trade_plan.get("sl_inr", 0.0))
                    _tp_inr = float(trade_plan.get("tp_inr", 0.0))
                    _rr     = float(trade_plan.get("rr_ratio", 0.0))
                    _sig    = str(trade_plan.get("trade_intent", "BUY"))
                    _entry  = float(engine_input["close"])
                    _conf   = float(engine_outputs.get("final_score", 0.0))
                    _scores = (
                        _orch_result.to_dict().get("strategy_scores", {})
                        if _orch_result is not None else {}
                    )
                    _tg.send_signal_alert(
                        pair=_pair, timeframe=_tf, signal=_sig,
                        confidence=_conf, entry_price=_entry,
                        sl_inr=_sl_inr, tp_inr=_tp_inr, rr_ratio=_rr,
                        strategy_scores=_scores,
                    )
                except Exception as exc:
                    logger.warning("LIVE_HOOK: Telegram signal alert failed (ignored): %s", exc)

        # 4. MT5 order — only when ultron APPROVE and not kill-switch blocked
        _mt5_ticket = None
        if ultron_result.get("decision") == "APPROVE" and not _ks_blocked:
            _mt5_bridge = _get_mt5()
            if _mt5_bridge is not None:
                try:
                    _lot  = float(ultron_result.get("final_position_size", 0.01))
                    _act  = str(trade_plan.get("trade_intent", "BUY"))
                    _sl_p = float(trade_plan.get("sl_price",  0.0))
                    _tp_p = float(trade_plan.get("tp_price",  0.0))
                    _mt5_ticket = _mt5_bridge.send_order(
                        symbol=_pair, action=_act,
                        lot_size=_lot, sl_price=_sl_p, tp_price=_tp_p,
                        comment=f"tradelatest_{_pair}_{_tf}",
                    )
                    if _mt5_ticket is not None:
                        logger.info(
                            "LIVE_HOOK: MT5 order placed — ticket=%s pair=%s action=%s lot=%.2f",
                            _mt5_ticket, _pair, _act, _lot,
                        )
                except Exception as exc:
                    logger.warning("LIVE_HOOK: MT5Bridge send_order failed (ignored): %s", exc)

        result["ks_blocked"]   = _ks_blocked
        result["ks_reason"]    = _ks.trip_reason() if _ks is not None else ""
        result["mt5_ticket"]   = _mt5_ticket
        result["drift_severity"] = _drift_severity

        # §13 item8 / §9 — ledger completeness, additive-only. Mirrors the backtest
        # path's TradeProvenanceV1 stamping (config version/hash, model pins,
        # strategy id) without touching trade_id generation or the collector.collect
        # call above: trade_id/TradeIdentityV1 canonicalization is a separate,
        # already-tracked initiative (journal.trade_identity_v1_0) and out of scope
        # for a config-authority change. Best-effort — never blocks the live result.
        try:
            from runtime.backtest_v2 import _build_provenance_base
            result["provenance"] = _build_provenance_base(_pair, "")
        except Exception as _prov_exc:  # noqa: BLE001
            logger.debug("LIVE_HOOK: provenance stamping failed: %s", _prov_exc)
            result["provenance"] = {}

        return result
