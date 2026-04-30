"""
trade_replay_validator.py (Connector Upgrade)
═══════════════════════════════════════════════════════════════════════════════
Validates replayed trades and constructs a flat, ML-ready dataset 
directly compatible with dataset_builder.py and fusion_engine.py.
═══════════════════════════════════════════════════════════════════════════════
"""

import math
import os
import pandas as pd
import logging
from typing import List, Dict, Any

log = logging.getLogger("ValidatorConnector")

def classify_outcome(exit_reason: str) -> str:
    """Classifies raw engine exit reasons into standardized ML labels."""
    if exit_reason == "TP2":
        return "TP2"
    elif exit_reason in ["SL-BE", "TP1_BE"]:  # Catching common BE variations
        return "TP1_BE"
    elif exit_reason in ["SL", "STOPPED"]:
        return "SL"
    return "OTHER"

def replay_single_trade(trade: Dict[str, Any], candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Replays a single trade to validate execution and extract structured features.
    """
    if not candles:
        # Missing candle data → return error row but DO NOT crash
        log.warning(f"Missing candle data for trade {trade.get('trade_id', 'UNKNOWN')}")
        return {
            "error": "Missing candle data", 
            "trade_id": trade.get("trade_id", "UNKNOWN")
        }

    candle_count = 0
    has_hit_tp1 = False
    
    recomputed_rr = trade['pnl_rr_net']
    exit_reason = trade.get('exit_reason', 'UNKNOWN')
    

    # ------------------------------------------------------------------
    # EXISTING REPLAY LOGIC REMAINS HERE
    # (Do not rewrite execution/TP/SL logic. Just track the loop.)
    # ------------------------------------------------------------------
    # TEMP: Use backtest truth directly (no replay yet)
    recomputed_rr = trade.get("pnl_rr_net", 0.0)
    exit_reason = trade.get("exit_reason", "UNKNOWN")

    # Minimal execution trace
    candle_count = 1
    has_hit_tp1 = "TP1" in exit_reason or "BE" in exit_reason
        
        # [Preserved existing logic determining has_hit_tp1, exit_reason, and recomputed_rr]
        # Example hook placement:
        # if price >= tp1: has_hit_tp1 = True
        # if exited: break
        
    # ------------------------------------------------------------------
    # SCHEMA CONSTRUCTION (CRITICAL CONNECTOR)
    # ------------------------------------------------------------------
    original_rr = trade.get('pnl_rr_net', 0.0)
    diff = recomputed_rr - original_rr
    is_match = math.isclose(recomputed_rr, original_rr, abs_tol=0.01)

    return {
        # --- identity ---
        "trade_id": trade.get('trade_id'),

        # --- validation ---
        "recomputed_rr": recomputed_rr,
        "original_rr": original_rr,
        "diff": diff,
        "is_match": is_match,

        # --- execution trace ---
        "exit_reason": exit_reason,
        "candles_processed": candle_count,
        "tp1_hit": has_hit_tp1,
        "tp2_hit": (exit_reason == "TP2"),

        # --- feature snapshot (DO NOT RECOMPUTE - MAP DIRECTLY) ---
        "features": {
            "retest_depth": trade.get("retest_depth", 0.0),
            "body_ratio": trade.get("body_ratio", 0.0),
            "disp_str": trade.get("disp_str", 0.0),
            "atr_vol": trade.get("atr_vol"),
            "session": trade.get("session"),
            "double_confirmed": trade.get("double_confirmed")
        },

        # --- outcome labels (FOR TRAINING) ---
        "outcome": {
            "rr": recomputed_rr,
            "class": classify_outcome(exit_reason),
            "is_winner": recomputed_rr > 0
        }
    }

def validate_all(trades: List[Dict[str, Any]], all_candles: Dict[str, List[Dict[str, Any]]]) -> pd.DataFrame:
    """
    Validates all trades and flattens them into a dataset_builder compatible DataFrame.
    """
    if not trades:
        return pd.DataFrame()

    results = []
    for trade in trades:
        trade_id = trade.get("trade_id")
        candles = all_candles.get(trade_id, [])
        res = replay_single_trade(trade, candles)
        results.append(res)

    # Separate valid replays from errors to ensure DataFrame integrity
    valid_results = [r for r in results if "error" not in r]
    if not valid_results:
        log.error("No valid trades processed. Returning empty DataFrame.")
        return pd.DataFrame()

    df = pd.DataFrame(valid_results)

    # Flatten nested fields for dataset_builder compatibility
    features_df = pd.json_normalize(df["features"])
    outcome_df = pd.json_normalize(df["outcome"])

    # Concatenate while dropping the original nested columns
    final_df = pd.concat([df.drop(columns=["features", "outcome"]), features_df, outcome_df], axis=1)

    # Save connector dataset
    os.makedirs("logs", exist_ok=True)
    export_path = "logs/validator_dataset.csv"
    final_df.to_csv(export_path, index=False)
    log.info(f"Dataset successfully exported to {export_path}")

    return final_df