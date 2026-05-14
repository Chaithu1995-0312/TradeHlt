"""
collector.py
Stores structured records to logs/collector.jsonl.
"""
import json
import logging
import os
import time
from pathlib import Path

Path("logs").mkdir(exist_ok=True)
from utils.logging_config import get_flow_logger
from config_layer.production_config import PROD_VERSION as _COLLECTOR_PROD_VERSION
_log = get_flow_logger("COLLECTOR")


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        norm = value.strip().lower()
        if norm in {"1", "true", "yes", "y", "on"}:
            return True
        if norm in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _engine_value(engine_payload, keys: tuple[str, ...], default: float = 0.0) -> float:
    if isinstance(engine_payload, dict):
        for key in keys:
            if key in engine_payload:
                return _to_float(engine_payload.get(key), default)
    return default


def _zonegate_value_keys() -> tuple[str, str]:
    preferred = str(os.environ.get("COLLECTOR_ZONEGATE_SCORE_KEY", "zone")).strip().lower()
    if preferred in {"score", "zonegate.score"}:
        return ("score", "zone")
    return ("zone", "score")
import numpy as np

def _json_serializable(obj):
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_serializable(i) for i in obj]
    return obj

def collect(
    trade_id: str,
    features: dict,
    engine_outputs: dict,
    outcome: dict,
    context: dict | None = None,
    fusion_output: dict | None = None,
) -> None:
    features = features or {}
    engine_outputs = engine_outputs or {}
    outcome = outcome or {}
    context = context or {}
    fusion_output = fusion_output or {}

    p_win = _to_float(
        context.get("gaussian_p_win", context.get("p_win", outcome.get("p_win", 0.0))),
        0.0,
    )
    gaussian_rr = _to_float(outcome.get("gaussian_rr", 0.0), 0.0)
    rr_fusion = _to_float(outcome.get("rr_fusion", 0.0), 0.0)
    actual_rr = _to_float(outcome.get("rr", 0.0), 0.0)

    engines_flat = {
        "crt": _engine_value(engine_outputs.get("crt"), ("score",)),
        "gaussian": _engine_value(engine_outputs.get("gaussian"), ("score",)),
        "adapter": _engine_value(engine_outputs.get("adapter"), ("score",)),
        "rr": _engine_value(engine_outputs.get("rr"), ("score",)),
        "zone_gate": _engine_value(engine_outputs.get("zone_gate"), _zonegate_value_keys()),
        "llm": _engine_value(engine_outputs.get("llm"), ("score",)),
    }
    gaussian_score = _to_float(
        context.get("gaussian_score", context.get("score", engines_flat.get("gaussian", 0.0))),
        0.0,
    )

    record = {
        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_version": _COLLECTOR_PROD_VERSION,
        "id": trade_id,
        "features": {
            "body_ratio": _to_float(features.get("body_ratio", 0.0), 0.0),
            "retest_depth": _to_float(features.get("retest_depth", 0.0), 0.0),
            "displacement": _to_float(features.get("displacement", 0.0), 0.0),
        },
        "context": {
            "gaussian_score": gaussian_score,
            "p_win": p_win,
            "candles_since_retest": _to_int(
                context.get(
                    "candles_since_retest",
                    features.get("candles_since_retest", 0),
                ),
                0,
            ),
            "sweep_detected": _to_bool(
                context.get("sweep_detected", features.get("sweep_detected", False)),
                False,
            ),
            "double_sweep": _to_bool(
                context.get("double_sweep", features.get("double_sweep", False)),
                False,
            ),
        },
        "engines": engines_flat,
        "engines_raw": engine_outputs,
        "fusion": fusion_output,
        "outcome": {
            "rr": actual_rr,
            "predicted_rr": {
                "gaussian_rr": gaussian_rr,
                "rr_fusion": rr_fusion,
            },
            "gaussian_rr": gaussian_rr,
            "rr_fusion": rr_fusion,
            "actual": {
                "win": _to_bool(outcome.get("win", False), False),
                "rr": actual_rr,
            },
            "predicted": {
                "gaussian_rr": gaussian_rr,
                "rr_fusion": rr_fusion,
                "p_win": p_win,
            },
        },
    }
    _log.info(json.dumps(_json_serializable(record)))
class Collector:
    def __init__(self):
        pass

    def log(self, record: dict):
        try:
            # Extract fields safely
            trade_id = record.get("features", {}).get("id", "unknown")

            features = record.get("features", {})

            engine_outputs = record.get("engines", {})

            outcome = {
                "rr": record.get("pnl", 0.0),
                "win": record.get("decision") == "ACCEPT",
            }

            context = {}
            fusion_output = record.get("fusion", {})

            collect(
                trade_id=trade_id,
                features=features,
                engine_outputs=engine_outputs,
                outcome=outcome,
                context=context,
                fusion_output=fusion_output,
            )

        except Exception as e:
            _log.info(json.dumps({
                "error": str(e),
                "raw_record": record
            }))
