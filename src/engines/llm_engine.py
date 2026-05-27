"""
llm_engine.py
Parallel engine wrapper — calls llm_score_safe() from llm_scorer.py.
"""
import json
import logging
import time

from config_layer.llm_scorer import llm_score_safe

_log = logging.getLogger("llm_engine")
_log.setLevel(logging.INFO)
_log.propagate = False
# FileHandler attached by init_coin_logging(symbol) in BacktestRunner.__init__


def compute(trade_id: str, features: dict, context: dict) -> dict:
    try:
        score = float(llm_score_safe(features))
        out = {"score": round(score, 6)}
    except Exception as e:
        out = {"score": 0.5, "reason": str(e)}

    _log.info(json.dumps({
        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "id": trade_id,
        "engine": "llm",
        "in": {
            "body_ratio": features.get("body_ratio", 0.0),
            "retest_depth": features.get("retest_depth", 0.0),
            "displacement": features.get("displacement", 0.0),
        },
        "out": out,
    }))
    return out