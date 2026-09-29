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
        if _raw_weights is None:
            raise KeyError(
                "score_component_weights missing from context — PLAN-002 requires explicit HOW weights. "
                "Callers must pass context={'score_component_weights': [w1,w2,w3,w4]}"
            )
        _score_weights = tuple(_raw_weights)
        # EPIC-84: candles_since_sweep/sweep_detected keep their existing
        # features-then-context lookup priority, but a value absent from BOTH
        # now raises (caught by the except below -> score=0.0 REJECT with the
        # reason) instead of silently assuming 0 / False, matching every
        # other required field in this call which already uses bare indexing.
        if "candles_since_sweep" in features:
            _candles_since_sweep = features["candles_since_sweep"]
        elif "candles_since_sweep" in context:
            _candles_since_sweep = context["candles_since_sweep"]
        else:
            raise KeyError("candles_since_sweep missing from features and context")
        if "sweep_detected" in features:
            _sweep_detected = features["sweep_detected"]
        elif "sweep_detected" in context:
            _sweep_detected = context["sweep_detected"]
        else:
            raise KeyError("sweep_detected missing from features and context")
        result = compute_scores(
            body_ratio=float(features["body_ratio"]),
            move=float(features["disp_strength"]),
            atr=float(features["atr"]),
            retest_depth=float(features["retest_depth"]),
            candles_since_sweep=int(_candles_since_sweep),
            sweep_detected=bool(_sweep_detected),
            double_sweep=bool(features["double_sweep"]),
            score_weights=_score_weights,
        )
        # EPIC-84 KEPT: compute_scores() always returns both "final" and
        # "score" (see engines.scoring_engine.compute_scores) — unreachable
        # default, not a live fallback.
        out = {"score": result.get("final", result.get("score", 0.0))}
    except Exception as e:
        out = {"score": 0.0, "reason": str(e)}

    # EPIC-84 KEPT: diagnostic log only, always runs (even after the except
    # branch above, when features may genuinely lack these keys) — must not
    # itself raise on the same malformed input the try/except already REJECTED.
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