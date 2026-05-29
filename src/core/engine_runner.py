"""
EngineRunner — orchestrates the full pipeline.

PIPELINE ORDER (strict):
  1. Adapter gating (TrapValidatorEngine) — MUST pass; score <= 0.0 → hard reject
  2. All four engines run unconditionally (CRT, Gaussian, BitNet, RR)
  3. Engine completeness check — if ANY expected engine is absent → hard reject
  4. Fusion — combines all engine outputs into final_score
  5. Decision — threshold applied to final_score
  6. Collector — structured logging of every decision path

ENGINE COMPLETENESS POLICY:
  Fusion silently re-normalizes if engines are missing. To prevent a partial
  engine set from producing an ACCEPT, engine_runner enforces that ALL four
  engines must be present in engine_results before fusion is called.
"""

import logging
import math
import os
import json as _json
from pathlib import Path as _Path
from typing import Optional
from engines.trap_validator_engine import TrapValidatorEngine
from engines.crt_engine import compute as crt_compute
from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
from engines.ml_gaussian_engine import MLGaussianEngine
from engines.zone_gate_engine import run_zone_gate_engine, _compute_soft_zone_score, compute_weighted_cluster_score
from engines.rr_engine import RREngine
from core.fusion_engine import FusionEngine, GaussianAdapter
from core.decision_engine import DecisionEngine
from core.signal_audit import SignalAuditRecorder
from core.acceptance_controller import AcceptanceController
from core.convergence_controller import ConvergenceController
from core.collector import Collector
from engines.live_engine import get_zone_gate
from utils.logging_config import get_flow_logger
# RegimeGovernor = Step-6 signal-quality filter (canonical name).
# UltronGovernor = backward-compat alias for the same class.
# NOT the capital-protection layer — that is UltronRiskGate (ultron_risk_gate.py).
from core.regime_governor import UltronGovernor, RegimeGovernor  # noqa: F401  both exported for callers

try:
    from config_layer.rr.rr_fusion import RRFusionLayer
    _RR_FUSION_IMPORT_ERROR = None
except Exception as _rr_fusion_import_exc:  # pragma: no cover - defensive import guard
    RRFusionLayer = None
    _RR_FUSION_IMPORT_ERROR = _rr_fusion_import_exc

logger = get_flow_logger("ENGINE_RUNNER")

EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}

# M2 — curated enveloped telemetry streams (additive; observation-only; mirrors M1 idiom).
_FEATURE_SNAPSHOT_LOG      = _Path("logs/feature_snapshots.jsonl")
_REGIME_CLASSIFICATION_LOG = _Path("logs/regime_classifications.jsonl")


def _emit_enveloped_jsonl(event_type_name: str, instrument: str, payload: dict, path: "_Path") -> None:
    """M2 curated telemetry: append one canonical envelope to `path`. Observation only —
    never gates a decision. Fail-open: any error (incl. absent event fabric) is swallowed
    so the decision path is never disrupted."""
    try:
        from events.event_fabric import make_event_envelope, EventType  # noqa: PLC0415
        env = make_event_envelope(
            event_type = EventType[event_type_name].value,
            instrument = instrument,
            source     = "EngineRunner",
            payload    = payload,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(_json.dumps(env) + "\n")
    except Exception:  # noqa: BLE001
        pass

# Default dual-engine thresholds (mirrors production config values)
DUAL_ENGINE_DEFAULTS: dict = {
    "trend_strength_threshold": 0.15,
    "momentum_threshold":       0.30,
    "range_volatility_threshold": 0.80,
    "breakout_min_score":       0.30,
    "trap_min_score":           0.32,
    "neutral_min_score":        0.32,
    "fusion_min_score":         0.25,
}

# Default engine runner config (used in tests; mirrors production values)
ENGINE_RUNNER_DEFAULTS: dict = {
    "model_path":               "model_export_format.json",
    "min_atr":                  0.0003,
    "allowed_sessions":         ["london", "new_york", "overlap"],
    "bitnet_zone_threshold":    0.25,
    "zone_registry_path":       "models/zone_registry.json",
    "zone_gate_execution_mode": "normal",
    "zone_mode":                "hard",
    "zone_min_samples":         50,
    "debug_mode":               False,
    "gaussian_impl":            "heuristic",
    "convergence_window":       500,
    "fusion_compare_evaluate":  True,
    "fusion_use_evaluate":      False,
    "dual_engine":              DUAL_ENGINE_DEFAULTS,
    "rr_fusion":                {"enabled": False, "model_path": "", "threshold": 0.5},
    "fusion_engine": {
        "weight_crt": 0.4, "weight_gaussian": 0.3,
        "weight_zone_gate": 0.2, "weight_rr": 0.1,
    },
}


def _cfg_require(cfg: dict, key: str, section: str = "") -> object:
    """Strict config accessor — raises KeyError if key is absent.

    All config values must be present in v1_multi_2026_03.json.
    No silent fallbacks are permitted.
    """
    if not isinstance(cfg, dict) or key not in cfg:
        loc = f"section '{section}'" if section else "config"
        raise KeyError(
            f"Required config key '{key}' missing from {loc}. "
            f"Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg[key]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _signed_direction(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def detect_regime(features: dict, cfg: dict) -> str:
    trend_strength = abs(_safe_float(features.get("ema_spread"), 0.0))
    momentum = abs(_safe_float(features.get("momentum_score"), 0.0))
    volatility = _safe_float(features.get("volatility_ratio"), 1.0)

    if (
        trend_strength >= _safe_float(_cfg_require(cfg, "trend_strength_threshold", "dual_engine"), 0.0)
        and momentum >= _safe_float(_cfg_require(cfg, "momentum_threshold", "dual_engine"), 0.0)
    ):
        return "trend"
    if volatility <= _safe_float(_cfg_require(cfg, "range_volatility_threshold", "dual_engine"), 0.0):
        return "range"
    return "neutral"


def breakout_engine(features: dict, cfg: dict) -> dict:
    trend = _safe_float(features.get("trend_bias"), 0.0)
    momentum = abs(_safe_float(features.get("momentum_score"), 0.0))
    spread = abs(_safe_float(features.get("ema_spread"), 0.0))
    min_score = _safe_float(_cfg_require(cfg, "breakout_min_score", "dual_engine"), 0.0)

    score = min(1.0, max(0.0, (spread + momentum) / 2.0))
    direction = _signed_direction(trend)
    if score < min_score:
        direction = 0

    return {
        "engine": "breakout",
        "score": float(score),
        "direction": int(direction),
        "reason": "trend_follow" if direction != 0 else "weak_breakout",
        "meta": {
            "trend_bias": float(trend),
            "momentum": float(momentum),
            "ema_spread": float(spread),
        },
    }


def trap_engine(features: dict, cfg: dict) -> dict:
    sweep = _safe_float(features.get("sweep_detected"), 0.0)
    disp = max(0.0, _safe_float(features.get("disp_strength"), 0.0))
    trend = _safe_float(features.get("trend_bias"), 0.0)
    min_score = _safe_float(_cfg_require(cfg, "trap_min_score", "dual_engine"), 0.0)

    if sweep <= 0:
        return {
            "engine": "trap",
            "score": 0.0,
            "direction": 0,
            "reason": "no_sweep",
            "meta": {"trend_bias": float(trend)},
        }

    score = min(1.0, disp)
    direction = -_signed_direction(trend)
    if score < min_score:
        direction = 0

    return {
        "engine": "trap",
        "score": float(score),
        "direction": int(direction),
        "reason": "liquidity_trap" if direction != 0 else "weak_trap",
        "meta": {
            "sweep_detected": int(sweep),
            "disp_strength": float(disp),
            "trend_bias": float(trend),
        },
    }


def _regime_governor_legacy(regime: str, dual_results: dict, cfg: dict) -> dict:
    # LEGACY free-function version of RegimeGovernor.
    # Used by EngineRunner when ultron_gate_enabled=false (backtest/training path).
    # No percentile gate, no daily quota. Prefer RegimeGovernor class for live trading.
    breakout = dual_results.get("breakout", {})
    trap = dual_results.get("trap", {})
    neutral_min = _safe_float(_cfg_require(cfg, "neutral_min_score", "dual_engine"), 0.0)

    if regime == "trend":
        selected = breakout
        gate_reason = "regime_trend"
    elif regime == "range":
        selected = trap
        gate_reason = "regime_range"
    else:
        b_score = _safe_float(breakout.get("score"), 0.0)
        t_score = _safe_float(trap.get("score"), 0.0)
        b_dir = int(breakout.get("direction", 0))
        t_dir = int(trap.get("direction", 0))

        if b_score < neutral_min and t_score < neutral_min:
            return {"allow": False, "reason": "neutral_low_confidence", "selected": None}

        # PRIORITY RESOLUTION: Both engines passed - select highest score
        if b_score > t_score:
            selected = {
                "engine": "breakout",
                "score": b_score,
                "direction": b_dir
            }
            resolution_reason = "breakout_higher_score"

        elif t_score > b_score:
            selected = {
                "engine": "trap",
                "score": t_score,
                "direction": t_dir
            }
            resolution_reason = "trap_higher_score"

        else:
            selected = {
                "engine": "trap",
                "score": t_score,
                "direction": t_dir
            }
            resolution_reason = "equal_score_trap_default"

        confidence = max(b_score, t_score)

        logger.info(
            f"ULTRON_RESOLUTION: breakout={b_score:.4f} "
            f"trap={t_score:.4f} selected={selected['engine']} "
            f"reason={resolution_reason} "
            f"direction_conflict={b_dir != t_dir} "
            f"confidence={confidence:.4f}"
        )

        gate_reason = "regime_neutral_resolved"

    direction = int(selected.get("direction", 0))
    if direction == 0:
        return {"allow": False, "reason": f"{gate_reason}_no_direction", "selected": selected}

    return {
        "allow": True,
        "reason": gate_reason,
        "selected": selected,
    }


class EngineRunner:

    @staticmethod
    def _get_gaussian_engine(config: dict):
        """
        Instantiate primary Gaussian engine from config["gaussian_impl"] only.

        GAUSSIAN_IMPL env var removed — config is the single source of truth.

        Values:
          "heuristic"  → HeuristicGaussianEngine (EMA/momentum kernel)
          "ml"         → MLGaussianEngine (GaussianNBModel)
          "shadow_ml"  → HeuristicGaussianEngine (production score);
                         MLGaussianEngine runs as shadow via _get_shadow_gaussian_engine()
        """
        cfg_impl = config.get("gaussian_impl", "heuristic") if isinstance(config, dict) else "heuristic"
        impl = cfg_impl.lower()

        if impl == "ml":
            logger.info("EngineRunner: using MLGaussianEngine (config: gaussian_impl=ml)")
            return MLGaussianEngine(config)
        elif impl == "shadow_ml":
            logger.info(
                "EngineRunner: using HeuristicGaussianEngine + MLGaussianEngine shadow "
                "(config: gaussian_impl=shadow_ml)"
            )
            return HeuristicGaussianEngine(config)
        else:
            logger.info("EngineRunner: using HeuristicGaussianEngine (config: gaussian_impl=%s)", impl)
            return HeuristicGaussianEngine(config)

    @staticmethod
    def _get_shadow_gaussian_engine(config: dict):
        """
        Return MLGaussianEngine shadow when gaussian_impl=shadow_ml, else None.

        The shadow engine's score is logged to engines_raw["gaussian"]["shadow"] but
        never enters engine_results["gaussian"]["score"] — FusionEngine is unaffected.
        """
        cfg_impl = config.get("gaussian_impl", "") if isinstance(config, dict) else ""
        if cfg_impl.lower() == "shadow_ml":
            logger.info("EngineRunner: shadow MLGaussianEngine instantiated (shadow_ml mode)")
            return MLGaussianEngine(config)
        return None

    def __init__(self, config: dict):
        if not isinstance(config, dict):
            raise TypeError("EngineRunner requires a dict config. Got: %s" % type(config))
        self.config = config

        self.adapter = TrapValidatorEngine(config)
        self.gaussian = self._get_gaussian_engine(config)
        self.gaussian_shadow = self._get_shadow_gaussian_engine(config)  # None unless shadow_ml
        self.rr = RREngine(config)
        self.rr_fusion = None
        self._rr_fusion_enabled = False

        rr_fusion_cfg = _cfg_require(config, "rr_fusion", "engine_runner")
        if bool(_cfg_require(rr_fusion_cfg, "enabled", "engine_runner.rr_fusion")):
            if RRFusionLayer is None:
                logger.warning("EngineRunner: rr_fusion requested but import failed: %s", _RR_FUSION_IMPORT_ERROR)
            else:
                try:
                    self.rr_fusion = RRFusionLayer(
                        model_path=str(_cfg_require(rr_fusion_cfg, "model_path", "engine_runner.rr_fusion")),
                        threshold=float(_cfg_require(rr_fusion_cfg, "threshold", "engine_runner.rr_fusion")),
                        enabled=True,
                    )
                    self._rr_fusion_enabled = bool(self.rr_fusion.is_loaded)
                    if self.rr_fusion.is_loaded:
                        logger.info("EngineRunner: rr_fusion enabled")
                    else:
                        logger.warning(
                            "EngineRunner: rr_fusion configured but model not loaded: %s",
                            self.rr_fusion.load_error,
                        )
                except Exception as exc:
                    logger.warning("EngineRunner: rr_fusion initialization failed: %s", exc)
                    self.rr_fusion = None

        # Wrap GaussianEngine in GaussianAdapter so FusionEngine.evaluate()
        # uses a real scorer instead of a neutral 0.5 stub.
        self._gaussian_adapter = GaussianAdapter(self.gaussian)

        # Convergence layer — injected into FusionEngine.compute()
        convergence_window = int(_cfg_require(config, "convergence_window", "engine_runner"))
        self._convergence = ConvergenceController(window_size=convergence_window)

        _fusion_cfg_dict = _cfg_require(config, "fusion_engine", "engine_runner")
        from core.fusion_engine import FusionConfig
        _fusion_config = FusionConfig(
            weight_crt=float(_cfg_require(_fusion_cfg_dict, "weight_crt", "fusion_engine")),
            weight_gaussian=float(_cfg_require(_fusion_cfg_dict, "weight_gaussian", "fusion_engine")),
            weight_zone_gate=float(_cfg_require(_fusion_cfg_dict, "weight_zone_gate", "fusion_engine")),
            weight_rr=float(_cfg_require(_fusion_cfg_dict, "weight_rr", "fusion_engine")),
            conflict_resolution_policy=str(_cfg_require(_fusion_cfg_dict, "conflict_resolution_policy", "fusion_engine")),
            gaussian_weight=float(_cfg_require(_fusion_cfg_dict, "gaussian_weight", "fusion_engine")),
            neural_weight=float(_cfg_require(_fusion_cfg_dict, "neural_weight", "fusion_engine")),
            llm_weight=float(_cfg_require(_fusion_cfg_dict, "llm_weight", "fusion_engine")),
            llm_lower_band=float(_cfg_require(_fusion_cfg_dict, "llm_lower_band", "fusion_engine")),
            llm_upper_band=float(_cfg_require(_fusion_cfg_dict, "llm_upper_band", "fusion_engine")),
            enable_llm=bool(_cfg_require(_fusion_cfg_dict, "enable_llm", "fusion_engine")),
            tier_full=float(_cfg_require(_fusion_cfg_dict, "tier_full", "fusion_engine")),
            tier_half=float(_cfg_require(_fusion_cfg_dict, "tier_half", "fusion_engine")),
            tier_quarter=float(_cfg_require(_fusion_cfg_dict, "tier_quarter", "fusion_engine")),
        )
        self.fusion = FusionEngine(
            gaussian_adapter=self._gaussian_adapter,
            convergence_controller=self._convergence,
            config=_fusion_config,
        )

        self.decision = DecisionEngine(config)
        self.collector = Collector()

        from config_layer.production_config import PROD_VERSION as _pv
        logger.info("Production config version: %s", _pv)

        dual_cfg = _cfg_require(config, "dual_engine", "engine_runner")
        self.dual_cfg = dual_cfg  # no fallback — all keys must be in JSON

        self._fusion_use_evaluate = bool(_cfg_require(config, "fusion_use_evaluate", "engine_runner"))
        self._fusion_compare_evaluate = bool(_cfg_require(config, "fusion_compare_evaluate", "engine_runner"))

        # BitNet zone gate — lazy-loaded singleton; fail-open if registry missing
        zone_registry_path = str(_cfg_require(config, "zone_registry_path", "engine_runner"))
        _zone_min_samples  = int(config.get("zone_min_samples", 50))
        self._zone_gate = get_zone_gate(zone_registry_path, min_samples=_zone_min_samples)

        # Observability + adaptive control
        debug_mode = bool(_cfg_require(config, "debug_mode", "engine_runner"))
        self._audit      = SignalAuditRecorder(debug_mode=debug_mode)
        self._acceptance = AcceptanceController(config)
        # RegimeGovernor = Step-6 signal-quality filter (canonical name; class is UltronGovernor).
        # ultron_gate_enabled controls RegimeGovernor, NOT UltronRiskGate (capital protection layer).
        self._regime_governor = RegimeGovernor()
        self._regime_governor_enabled = bool(_cfg_require(config, "ultron_gate_enabled", "engine_runner"))

        # SignalBeliefTracker gate — accumulates post-fusion conviction over consecutive candles.
        # Registry injected by BacktestRunner/LiveRunner — EngineRunner reads only, never owns.
        _belief_cfg = config.get("signal_belief", {})
        self._belief_enabled = bool(_belief_cfg.get("enabled", False))

        # ── Cognitive Bus (async, advisory only — steps 8-10) ─────────────────
        # Runs in a background daemon thread. NEVER blocks the execution path.
        # Cognitive output is written to logs/cognitive_telemetry.jsonl only.
        # The "cognitive" key is NOT in the run() return dict.
        self._cognitive_bus: Optional["CognitiveBus"] = None
        # M2 — last emitted regime, for on-change REGIME_CLASSIFICATION telemetry.
        self._last_regime: Optional[str] = None
        _cognitive_cfg = config.get("cognitive_layer", {})
        if bool(_cognitive_cfg.get("enabled", False)):
            try:
                from cognitive.cognitive_bus import CognitiveBus as _CognitiveBus  # noqa
                self._cognitive_bus = _CognitiveBus(config)
                self._cognitive_bus.start()
                logger.info("EngineRunner: CognitiveBus started")
            except Exception as _cbus_exc:
                logger.warning(
                    "EngineRunner: CognitiveBus init failed (non-blocking): %s",
                    _cbus_exc,
                )

    def _reject(
        self,
        reason: str,
        input_data: dict = None,
        actual_pnl: float | None = None,
        adapter_result: dict = None,
        engine_results: dict = None,
        fusion_result: dict | None = None,
        dual_results: dict | None = None,
        gate_result: dict | None = None,
    ) -> dict:
        """Build a standardised REJECT record and log it."""
        def _infer_stage(reject_reason: str) -> str:
            r = str(reject_reason or "")
            if r.startswith("adapter_") or r.startswith("data_integrity") or r.startswith("missing_fields") \
               or r.startswith("invalid_session") or r.startswith("low_atr") or r.startswith("non_positive_atr"):
                return "adapter"
            if r.startswith("zone_gate"):
                return "zone_gate"
            if r.startswith("ultron_gate"):
                return "ultron"
            if r.startswith("incomplete_engine_execution") or r.startswith("fusion_missing_engines") \
               or r.startswith("low_fusion_score"):
                return "fusion"
            if r in {"low_score", "low_probability", "low_rr", "weak_setup"}:
                return "decision"
            return "unknown"

        reject_stage = _infer_stage(reason)
        record = {
            "adapter": adapter_result or {},
            "engines": engine_results or {},
            "fusion": fusion_result or {},
            "dual_engines": dual_results or {},
            "gate": gate_result or {},
            "final_score": _safe_float((fusion_result or {}).get("final_score"), 0.0),
            "decision": "REJECT",
            "reason": reason,
            "reject_stage": reject_stage,
            "features": input_data or {},
            "pnl": actual_pnl,
        }
        self.collector.log(record)
        return {
            "decision": "REJECT",
            "reason": reason,
            "score": _safe_float((fusion_result or {}).get("final_score"), 0.0),
            "regime": (gate_result or {}).get("regime"),
            "selected_engine": ((gate_result or {}).get("selected") or {}).get("engine"),
            "reject_stage": reject_stage,
        }

    # ------------------------------------------------------------------
    # Helper: weighted engine vote (advisory — does not replace fusion)
    # ------------------------------------------------------------------

    def _compute_weighted_vote(self, engine_results: dict) -> float:
        """
        Weighted directional vote: Σ(w_i * direction_i * confidence_i).
        Maps [-1, 1] → [0, 1]. Advisory only — logged but does not override
        fusion result unless config["use_weighted_vote"] is True.
        Weights are read from FusionConfig so they stay in sync with compute().
        """
        cfg = getattr(self.fusion, "cfg", None)
        weights = {
            "crt": _safe_float(getattr(cfg, "weight_crt", 0.30), 0.30),
            "gaussian": _safe_float(getattr(cfg, "weight_gaussian", 0.25), 0.25),
            "zone_gate": _safe_float(getattr(cfg, "weight_zone_gate", 0.25), 0.25),
            "rr": _safe_float(getattr(cfg, "weight_rr", 0.20), 0.20),
        }
        total = 0.0
        for name, w in weights.items():
            s = float((engine_results.get(name) or {}).get("score", 0.5))
            direction  = 1 if s >= 0.5 else -1
            confidence = abs(s - 0.5) * 2.0
            total += w * direction * confidence
        return max(0.0, min(1.0, (total + 1.0) / 2.0))

    def _evaluate_fusion_path(self, input_data: dict, context: dict) -> dict:
        """
        Optional evaluate() path adapter.
        Returns a dict contract so callers can merge it into compute() payloads.
        """
        raw_idx = (context or {}).get("candle_idx", input_data.get("candle_idx", 0))
        try:
            candle_idx = int(raw_idx)
        except (TypeError, ValueError):
            candle_idx = 0

        eval_result = self.fusion.evaluate(
            features=input_data,
            signal=context or {},
            candle_idx=candle_idx,
        )
        eval_dict = eval_result.to_dict()
        eval_dict["missing_engines"] = []
        return eval_dict

    def run(self, input_data: dict, context: dict, actual_pnl: float | None = None) -> dict:
        # ------------------------------------------------------------------ #
        # Step 1: Adapter gating                                              #
        # ------------------------------------------------------------------ #
        merged = {**input_data, **(context or {})}
        adapter_result = self.adapter.compute(merged)

        # Audit: start bar record (no-op when debug_mode=False)
        bar_id    = str(input_data.get("bar_id", id(input_data)))
        timestamp = str(input_data.get("timestamp", ""))
        price     = float(input_data.get("close", input_data.get("price", 0.0)))
        self._audit.start_bar(bar_id, timestamp, price)

        # Use <= 0.0 to guard against floating-point values like -0.0 or tiny
        # negatives from future adapter extensions, without relying on == 0.0.
        if adapter_result.get("score", 1.0) <= 0.0:
            reason = adapter_result.get("reason", "adapter_rejected")
            self._audit.finalize("REJECT", reason)
            self._audit.flush()
            return self._reject(
                reason,
                input_data=input_data,
                actual_pnl=actual_pnl,
                adapter_result=adapter_result,
            )

        # ------------------------------------------------------------------ #
        # Step 2: Run ALL engines unconditionally                             #
        # ------------------------------------------------------------------ #
        
        zonegate_input = {**input_data, **(context or {})}

        _zone_threshold = float(_cfg_require(self.config, "bitnet_zone_threshold", "engine_runner"))
        _exec_mode = str(_cfg_require(self.config, "zone_gate_execution_mode", "engine_runner"))
        _debug_mode = bool(_cfg_require(self.config, "debug_mode", "engine_runner"))
        _zone_debug_config = {
            "zones_loaded_count": len(getattr(self._zone_gate, "_zones", []) or []),
            "inside_zone":        False,
            "zone_strength":      float(zonegate_input.get("zone_strength",  0.0)),
            "zone_freshness":     float(zonegate_input.get("zone_freshness", 0.0)),
            "distance_to_nearest":zonegate_input.get("zone_distance"),
        } if _debug_mode else None

        def _zone_model_fn(vector: list) -> float:
            """Score via BitNetZoneGate using weighted cluster score (top-3 zones).
            Returns 0.5 on any error (neutral, non-blocking)."""
            try:
                result = self._zone_gate.check(vector)
                top_scores = result.get("top_scores")
                if top_scores and len(top_scores) >= 2:
                    return compute_weighted_cluster_score(top_scores)
                return float(result.get("score", 0.5))
            except Exception as _e:
                logger.debug(f"ZoneGate scoring fallback (0.5): {_e}")
                return 0.5

        zone_raw = run_zone_gate_engine(
            raw_features=zonegate_input,
            model_fn=_zone_model_fn,
            threshold=_zone_threshold,
            execution_mode=_exec_mode,
            zone_debug_config=_zone_debug_config,
        )

        # Soft zone scoring (optional override of score only — pass/fail still from hard gate)
        _zone_mode = str(_cfg_require(self.config, "zone_mode", "engine_runner"))
        if _zone_mode == "soft":
            soft_score = _compute_soft_zone_score(zonegate_input)
            zone_raw = {**zone_raw, "score": soft_score}

        # Audit: record zone result
        self._audit.record_zone(zone_raw)

        zone_result = {
            "engine": "zone_gate",
            "score": float(zone_raw.get("score", 0.0)),
            "direction": 1 if zone_raw.get("passed") else 0,
            "meta": zone_raw,
        }
        crt_result = crt_compute(trade_id="Test:", features=input_data, context={})
        # Extract CRT-determined direction so the gaussian engine can apply
        # feature mirroring for short trades (MLGaussianEngine / direction-aware path).
        # input_data["direction"] is an int (1=LONG, -1=SHORT) set by backtest_v2.py
        # lines 1639-1641 before calling engine_runner.run().  Falls back to "long"
        # when direction is absent (live path without explicit direction injection).
        try:
            _dir_raw = int(input_data.get("direction", input_data.get("signal_dir", 1)) or 1)
        except (TypeError, ValueError):
            _dir_raw = 1
        _gauss_dir = "short" if _dir_raw < 0 else "long"
        gaussian_result = self.gaussian.compute(input_data, direction=_gauss_dir)

        # Shadow ML comparison (shadow_ml mode only).
        # Heuristic score already in gaussian_result["score"] → enters fusion unchanged.
        # ML score attached under ["shadow"] → logged to engines_raw, never in fusion.
        if self.gaussian_shadow is not None:
            try:
                _sh = self.gaussian_shadow.compute(input_data, direction=_gauss_dir)
                gaussian_result["shadow"] = {
                    "score":     _sh["score"],
                    "reason":    _sh.get("reason", "shadow_ml"),
                    "meta":      _sh.get("meta", {}),
                    "delta":     round(_sh["score"] - gaussian_result["score"], 4),
                    "agreement": bool((_sh["score"] >= 0.5) == (gaussian_result["score"] >= 0.5)),
                }
            except Exception as _se:
                logger.debug("EngineRunner: shadow gaussian compute failed — %s", _se)

        rr_result = self.rr.compute(input_data)
        base_rr_score = _safe_float(rr_result.get("score"), 0.0)

        # Optional RR enhancement layer: after RREngine, before FusionEngine.
        if self.rr_fusion and self.rr_fusion.is_loaded:
            try:
                rr_fusion_result = self.rr_fusion.score_dict(
                    depth=_safe_float(input_data.get("retest_depth"), 0.0),
                    body=_safe_float(input_data.get("body_ratio"), 0.0),
                    disp=_safe_float(input_data.get("disp_strength"), 0.0),
                    gaussian_score=_safe_float(gaussian_result.get("score"), 0.5),
                    gaussian_p_win=_safe_float(gaussian_result.get("score"), 0.5),
                    is_asia=_safe_float(input_data.get("is_asia"), 0.0),
                    is_london=_safe_float(input_data.get("is_london"), 0.0),
                    is_newyork=_safe_float(input_data.get("is_newyork"), 0.0),
                    hour=int(_safe_float(input_data.get("hour"), _safe_float((context or {}).get("hour"), 0.0))),
                    threshold=float(_cfg_require(
                        _cfg_require(self.config, "rr_fusion", "engine_runner"),
                        "threshold", "engine_runner.rr_fusion"
                    )),
                )
                fused_rr_score = float(rr_fusion_result.get("final_score", rr_result.get("score", 0.0)))
                if not math.isfinite(fused_rr_score):
                    raise ValueError("rr_fusion produced non-finite final_score")
                rr_result = {
                    **rr_result,
                    "score": max(0.0, min(1.0, fused_rr_score)),
                    "rr_fusion": rr_fusion_result,
                }
                logger.debug(
                    "EngineRunner: rr_fusion applied base_rr=%.4f fused_rr=%.4f status=%s",
                    base_rr_score,
                    _safe_float(rr_result.get("score"), 0.0),
                    str(rr_fusion_result.get("status", "unknown")),
                )
            except Exception as exc:
                logger.warning("EngineRunner: rr_fusion failed, using base RR: %s", exc)

        engine_results = {
            "crt": crt_result,
            "gaussian": gaussian_result,
            "zone_gate": zone_result,
            "rr": rr_result,
        }

        # 5th engine — StrategyOrchestrator consensus (injected via context dict).
        # live_engine_hook calls StrategyOrchestrator BEFORE EngineRunner and injects
        # the consensus score under context["strategy_consensus_score"].
        # FusionEngine picks it up only when FusionConfig.weight_strategy_consensus > 0.
        _consensus_score = _safe_float(
            (context or {}).get("strategy_consensus_score"), -1.0
        )
        if _consensus_score >= 0.0:
            engine_results["strategy_consensus"] = {
                "score": max(0.0, min(1.0, _consensus_score)),
                "direction": int((context or {}).get("strategy_consensus_direction", 0)),
            }

        # Audit: record all engine scores
        self._audit.record_engines(engine_results)

        # ------------------------------------------------------------------ #
        # Step 3: Engine completeness check                                   #
        # ------------------------------------------------------------------ #
        missing_engines = EXPECTED_ENGINES - engine_results.keys()
        if missing_engines:
            reason = f"incomplete_engine_execution:{sorted(missing_engines)}"
            logger.error(f"EngineRunner: {reason}")
            return self._reject(
                reason,
                input_data=input_data,
                actual_pnl=actual_pnl,
                adapter_result=adapter_result,
                engine_results=engine_results,
            )

        # ------------------------------------------------------------------ #
        # Step 4: Fusion                                                      #
        # ------------------------------------------------------------------ #
        # Detect regime up-front so fusion weights can adapt to it. Same value
        # is reused at Step 6 by RegimeGovernor — avoids a second computation.
        current_regime = detect_regime(input_data, self.dual_cfg)
        # M2 — emit REGIME_CLASSIFICATION on change only (regime is a deterministic
        # function of features and stable across many bars; per-bar emission would be
        # noise). Observation-only; does not feed fusion.
        if current_regime != self._last_regime:
            _emit_enveloped_jsonl(
                "REGIME_CLASSIFICATION",
                str(input_data.get("instrument", "")),
                {"regime": current_regime, "prev_regime": self._last_regime},
                _REGIME_CLASSIFICATION_LOG,
            )
            self._last_regime = current_regime
        fusion_result = self.fusion.compute(engine_results, regime=current_regime)
        use_evaluate = bool(getattr(self, "_fusion_use_evaluate", False))
        compare_evaluate = bool(getattr(self, "_fusion_compare_evaluate", False))
        if use_evaluate or compare_evaluate:
            try:
                eval_fusion = self._evaluate_fusion_path(input_data, context)
                if compare_evaluate:
                    fusion_result["evaluate_shadow"] = eval_fusion
                if use_evaluate:
                    fusion_result = {
                        **fusion_result,
                        "final_score": _safe_float(eval_fusion.get("final_score"), 0.0),
                        "evaluate_used": True,
                        "evaluate_action": eval_fusion.get("action"),
                        "evaluate_risk_mult": _safe_float(eval_fusion.get("risk_mult"), 0.0),
                        "evaluate_llm_fired": bool(eval_fusion.get("llm_fired", False)),
                    }
            except Exception as exc:
                logger.warning("EngineRunner: fusion.evaluate path failed, falling back to compute(): %s", exc)

        # Audit: record fusion result
        self._audit.record_fusion(fusion_result)

        # Advisory: weighted engine vote (logged but advisory only)
        _weighted_vote = self._compute_weighted_vote(engine_results)
        if _debug_mode:
            logger.debug("EngineRunner weighted_vote=%.4f", _weighted_vote)

        # Also reject if fusion itself detected missing engines (defensive)
        if fusion_result.get("missing_engines"):
            reason = f"fusion_missing_engines:{fusion_result['missing_engines']}"
            logger.error(f"EngineRunner: {reason}")
            self._audit.finalize("REJECT", reason)
            self._audit.flush()
            return self._reject(
                reason,
                input_data=input_data,
                actual_pnl=actual_pnl,
                adapter_result=adapter_result,
                engine_results=engine_results,
            )

        # ------------------------------------------------------------------ #
        # Step 5: Fusion baseline decision                                    #
        # ------------------------------------------------------------------ #
        final_score = _safe_float(fusion_result.get("final_score"), 0.0)
        fusion_threshold = _safe_float(_cfg_require(self.dual_cfg, "fusion_min_score", "engine_runner.dual_engine"), 0.0)
        fusion_rejected = final_score < fusion_threshold

        logger.info(
            f"FUSION_GATE: score={final_score:.4f} threshold={fusion_threshold:.4f} "
            f"rejected={fusion_rejected} reached_ultron={not fusion_rejected}"
        )

        if fusion_rejected:
            reason = "low_fusion_score"
            return self._reject(
                reason,
                input_data=input_data,
                actual_pnl=actual_pnl,
                adapter_result=adapter_result,
                engine_results=engine_results,
                fusion_result=fusion_result,
            )

        # ------------------------------------------------------------------ #
        # Step 5b: Belief gate — temporal conviction accumulator              #
        # Accumulates post-fusion score over consecutive same-direction        #
        # candles before allowing DecisionEngine to proceed.                  #
        # Gate: abs(belief) >= HIGH_CONVICTION OR confirm_count >= MIN_CONFS  #
        # Registry injected by BacktestRunner/LiveRunner — never owned here.  #
        # ------------------------------------------------------------------ #
        _belief_registry = context.get("belief_registry")
        _fusion_dir = int(context.get("strategy_consensus_direction", 0))
        if _belief_registry is not None and self._belief_enabled:
            _instrument   = str(context.get("instrument", "UNKNOWN"))
            _timeframe    = str(context.get("timeframe", "M15"))
            _tracker      = _belief_registry.get(_instrument, _timeframe)
            _belief_state = _tracker.update(final_score, _fusion_dir)
            logger.debug(
                "BELIEF_GATE: instrument=%s tf=%s belief=%.4f direction=%d "
                "confirm_count=%d approved=%s reason=%s",
                _instrument, _timeframe, _belief_state.belief, _fusion_dir,
                _belief_state.confirm_count, _belief_state.approved, _belief_state.reason,
            )
            if not _belief_state.approved:
                return {
                    "decision":      "HOLD",
                    "stage":         "BELIEF_GATE",
                    "reason":        _belief_state.reason,
                    "belief":        round(_belief_state.belief, 4),
                    "confirm_count": _belief_state.confirm_count,
                }

        # ------------------------------------------------------------------ #
        # Step 6: Dual-engine regime gate (RegimeGovernor)                    #
        # Controlled by engine_runner.ultron_gate_enabled in production JSON. #
        # false → training/backtest path (no quota or percentile filtering).  #
        # true  → live trading path (full RegimeGovernor active).             #
        # ------------------------------------------------------------------ #
        regime = current_regime  # already computed before Step 4 fusion
        dual_results = {
            "breakout": breakout_engine(input_data, self.dual_cfg),
            "trap":     trap_engine(input_data, self.dual_cfg),
        }

        if getattr(self, "_regime_governor_enabled", False):
            # Extract candle date for daily quota boundary
            from datetime import datetime as _dt, date as _date
            _ts_raw = input_data.get("timestamp", "")
            try:
                _candle_date = _dt.fromisoformat(str(_ts_raw)).date() if _ts_raw else _date.today()
            except (ValueError, TypeError):
                _candle_date = _date.today()
            # Lazy-init guard (supports test runners created via __new__)
            if not hasattr(self, "_regime_governor"):
                self._regime_governor = RegimeGovernor()
            gate_result = self._regime_governor.evaluate(
                regime, dual_results, self.dual_cfg, _candle_date
            )
            gate_result["regime"] = regime

            if not gate_result.get("allow", False):
                reason = f"ultron_gate:{gate_result.get('reason', 'blocked')}"
                return self._reject(
                    reason,
                    input_data=input_data,
                    actual_pnl=actual_pnl,
                    adapter_result=adapter_result,
                    engine_results=engine_results,
                    fusion_result=fusion_result,
                    dual_results=dual_results,
                    gate_result=gate_result,
                )
        else:
            # Training / backtest pass-through — no quota cap, no percentile gate.
            # Still respects regime-aware selection and low-confidence neutral rejection
            # via _regime_governor_legacy() so downstream metadata stays consistent with live.
            gate_result = _regime_governor_legacy(regime, dual_results, self.dual_cfg)
            gate_result["regime"] = regime

            if not gate_result.get("allow", False):
                reason = f"ultron_gate:{gate_result.get('reason', 'blocked')}"
                return self._reject(
                    reason,
                    input_data=input_data,
                    actual_pnl=actual_pnl,
                    adapter_result=adapter_result,
                    engine_results=engine_results,
                    fusion_result=fusion_result,
                    dual_results=dual_results,
                    gate_result=gate_result,
                )

        # ------------------------------------------------------------------ #
        # Step 7: DecisionEngine — FINAL authority (Issue 5 fix)             #
        # DecisionEngine.evaluate() is the ONLY place that emits             #
        # "execute" or "reject". EngineRunner NEVER returns "Approved".      #
        # ------------------------------------------------------------------ #
        selected = gate_result.get("selected", {})
        p_win = _safe_float(
            engine_results.get("gaussian", {}).get("score"), 0.5
        )
        zone_gate_ctx = {
            "valid": bool(zone_result.get("passed", False)),
            "score": _safe_float(zone_result.get("score"), 0.0),
        }
        fusion_ctx = {
            # DecisionEngine expects a true RR ratio (e.g. >= 1.2),
            # not the normalized RR score used by fusion averaging.
            "rr": _safe_float(
                engine_results.get("rr", {}).get("rr_ratio"),
                _safe_float(engine_results.get("rr", {}).get("score"), 0.0),
            ),
            "weak_component": max(
                0.0,
                1.0 - _safe_float(fusion_result.get("final_score"), 0.0),
            ),
        }

        # Inject adaptive thresholds into config — DecisionEngine reads from config
        adaptive_thresholds = self._acceptance.get_thresholds()
        effective_config = {**(self.config or {}), **adaptive_thresholds}

        decision_result = self.decision.evaluate(
            score=final_score,
            p_win=p_win,
            zone_gate=zone_gate_ctx,
            fusion=fusion_ctx,
            config=effective_config,
        )
        # Attach routing metadata (read-only — does NOT change the decision)
        decision_result["regime"] = regime
        decision_result["selected_engine"] = selected.get("engine")
        decision_result["selected_direction"] = selected.get("direction", 0)
        decision_result["dual_score"] = _safe_float(selected.get("score"), 0.0)
        decision_result["gate_reason"] = gate_result.get("reason", "")
        decision_result["final_score"] = final_score
        decision_result["reject_stage"] = (
            "decision" if str(decision_result.get("decision", "")).lower() == "reject" else "none"
        )

        # ------------------------------------------------------------------ #
        # Step 8: Log full record                                             #
        # ------------------------------------------------------------------ #
        self.collector.log({
            "adapter": adapter_result,
            "engines": engine_results,
            "fusion": fusion_result,
            "dual_engines": dual_results,
            "gate": gate_result,
            "final_score": final_score,
            "decision": decision_result.get("decision", "UNKNOWN"),
            "reason": decision_result.get("reason", ""),
            "reject_stage": decision_result.get("reject_stage", "none"),
            "missing_engines": [],
            "features": input_data,
            "pnl": actual_pnl,
        })

        # Update adaptive controllers (per-bar, stateful per session)
        accepted = str(decision_result.get("decision", "")).lower() == "execute"
        self._acceptance.update_metrics(
            engine_scores={
                name: float((result or {}).get("score", 0.0))
                for name, result in engine_results.items()
            },
            fusion_score=final_score,
            accepted=accepted,
        )
        self._acceptance.adjust_thresholds()
        self._convergence.record_outcome(accepted)

        # Finalize audit (no-op when debug_mode=False)
        self._audit.finalize(
            decision=str(decision_result.get("decision", "UNKNOWN")),
            reason=str(decision_result.get("reason", "")),
        )
        self._audit.flush()

        # M2 — FEATURE_SNAPSHOT on decision bars (one per scored decision; same cadence
        # as DECISION_SNAPSHOT below). Curated, not per-bar: this point is reached only
        # after fusion + decision, so the feature vector is complete and was scored.
        # Observation-only; never feeds a decision.
        _emit_enveloped_jsonl(
            "FEATURE_SNAPSHOT",
            str(input_data.get("instrument", "")),
            {
                "decision": str(decision_result.get("decision", "")),
                "regime":   current_regime,
                "features": dict(input_data),
            },
            _FEATURE_SNAPSHOT_LOG,
        )

        # ── Fire-and-forget: emit decision snapshot to async CognitiveBus ─────
        # Executes AFTER all decision logic is complete. Non-blocking.
        # Drops silently on queue full. cognitive key is NOT in return dict.
        if getattr(self, "_cognitive_bus", None) is not None:
            try:
                import uuid as _uuid  # noqa
                import time as _t      # noqa
                from cognitive.cognitive_bus import DecisionSnapshot as _DS  # noqa
                from events.event_fabric import make_event_envelope, EventType  # noqa
                _did = _uuid.uuid4().hex[:8]
                _env = make_event_envelope(
                    event_type = EventType.DECISION_SNAPSHOT,
                    instrument = str(input_data.get("instrument", "")),
                    source     = "EngineRunner",
                    payload    = {
                        "decision_id": _did,
                        "decision":    str(decision_result.get("decision", "")),
                        "score":       round(float(decision_result.get("final_score", 0.0)), 4),
                        "cluster_id":  int(
                            engine_results.get("zone_gate", {}).get("cluster_id", -1)
                            if isinstance(engine_results.get("zone_gate"), dict) else -1
                        ),
                    },
                )
                _zone_r = engine_results.get("zone_gate") or {}
                _gauss_r = engine_results.get("gaussian") or {}
                _rr_r   = engine_results.get("rr") or {}
                self._cognitive_bus.emit(_DS(
                    decision_id     = _did,
                    event_id        = _env["event_id"],
                    generation      = _env["generation"],
                    timestamp       = _env["timestamp"],
                    instrument      = str(input_data.get("instrument", "")),
                    schema_hash     = _env["schema_hash"],
                    features        = dict(input_data),
                    zone_result     = dict(_zone_r) if isinstance(_zone_r, dict) else {},
                    gaussian_result = dict(_gauss_r) if isinstance(_gauss_r, dict) else {},
                    rr_result       = dict(_rr_r)   if isinstance(_rr_r, dict) else {},
                    fusion_result   = dict(fusion_result) if isinstance(fusion_result, dict) else {},
                    decision        = str(decision_result.get("decision", "")),
                    cluster_id      = int(
                        _zone_r.get("cluster_id", -1) if isinstance(_zone_r, dict) else -1
                    ),
                ))
            except Exception:
                pass  # cognitive bus emit never blocks or raises

        return decision_result
