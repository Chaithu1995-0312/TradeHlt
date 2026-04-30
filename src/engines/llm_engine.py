"""
llm_engine.py
Parallel engine wrapper — calls llm_score_safe() from llama_gate.py.
"""
import json
import logging
import time
from pathlib import Path

from config_layer.llama_gate import llm_score_safe
from utils.logging_config import get_log_path

Path("logs").mkdir(exist_ok=True)
_log = logging.getLogger("llm_engine")
_handler = logging.FileHandler(get_log_path("llm_engine"))
_handler.setFormatter(logging.Formatter("%(message)s"))
_log.addHandler(_handler)
_log.setLevel(logging.INFO)
_log.propagate = False


def compute(trade_id: str, features: dict, context: dict) -> dict:
    try:
        score = float(llm_score_safe(features))
        out = {"score": round(score, 6)}
    except Exception as e:
        out = {"score": 1.0, "reason": str(e)}

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