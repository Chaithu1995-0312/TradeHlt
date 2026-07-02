"""
crt_engine.py
Parallel engine wrapper — calls compute_scores() from engines.scoring_engine.py
"""
import json
import logging
import time

from engines.scoring_engine import compute_scores

_log = logging.getLogger("crt_engine")
_log.setLevel(logging.INFO)
_log.propagate = False
# FileHandler attached by init_coin_logging(symbol) in BacktestRunner.__init__


def compute(trade_id: str, features: dict, context: dict) -> dict:
    try:
        _raw_weights = context.get("score_component_weights")
        _score_weights = tuple(_raw_weights) if _raw_weights else (0.35, 0.25, 0.20, 0.20)
        result = compute_scores(
            body_ratio=float(features["body_ratio"]),
            move=float(features["disp_strength"]),
            atr=float(features["atr"]),
            retest_depth=float(features["retest_depth"]),
            candles_since_retest=int(features.get("candles_since_retest", context.get("candles_since_retest", 0))),
            sweep_detected=bool(features.get("sweep_detected", context.get("sweep_detected", False))),
            double_sweep=bool(features["double_sweep"]),
            score_weights=_score_weights,
        )
        out = {"score": result.get("final", result.get("score", 0.0))}
    except Exception as e:
        out = {"score": 0.0, "reason": str(e)}

    _log.info(json.dumps(_json_serializable({
        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "id": trade_id,
        "engine": "crt",
        "in": {
            "body_ratio": features.get("body_ratio", 0.0),
            "retest_depth": features.get("retest_depth", 0.0),
            "displacement": features.get("displacement", 0.0),
        },
        "out": out,
    })))
    return out
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