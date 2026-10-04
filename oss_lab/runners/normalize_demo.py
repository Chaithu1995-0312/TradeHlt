"""Demo runner: normalize synthetic Tradelatest-like rows and compute canonical metrics.

Does not invoke backtest_v2 or any external OSS. Useful as a smoke path for the lab.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oss_lab.adapters.tradelatest import TradelatestBaselineAdapter
from oss_lab.contracts.dataset_manifest import XAUUSD_M15_PHASE1_PRIMARY
from oss_lab.metrics.canonical import compute_canonical_metrics


def demo_rows() -> list[dict[str, Any]]:
    return [
        {
            "instrument": "XAUUSD",
            "direction": "long",
            "entry": 2300.0,
            "sl": 2290.0,
            "tp": 2320.0,
            "exit": 2320.0,
            "exit_reason": "TP_HIT",
            "net_pnl": 20.0,
            "gross_pnl": 20.0,
            "initial_risk": 10.0,
            "mfe": 22.0,
            "mae": -3.0,
            "mfe_r": 2.2,
            "mae_r": -0.3,
            "fees": 0.0,
            "spread_cost": 0.0,
            "slippage_cost": 0.0,
        },
        {
            "instrument": "XAUUSD",
            "direction": "short",
            "entry": 2310.0,
            "sl": 2320.0,
            "tp": 2290.0,
            "exit": 2320.0,
            "exit_reason": "SL_HIT",
            "net_pnl": -10.0,
            "gross_pnl": -10.0,
            "initial_risk": 10.0,
            "mfe": 4.0,
            "mae": -10.0,
            "mfe_r": 0.4,
            "mae_r": -1.0,
        },
    ]


def run_demo() -> dict[str, Any]:
    adapter = TradelatestBaselineAdapter()
    adapter.bind_dataset(XAUUSD_M15_PHASE1_PRIMARY)
    trades = adapter.normalize_trades(demo_rows(), run_id="demo-run-001")
    metrics = compute_canonical_metrics(trades, n_signals=2, n_orders=2, n_fills=2)
    return {
        "dataset_id": XAUUSD_M15_PHASE1_PRIMARY.dataset_id,
        "n_normalized": len(trades),
        "metrics": metrics.to_dict(),
        "fill_model": adapter.declare_fill_model().to_dict(),
        "authority": "RESEARCH_LAB_ONLY",
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, default=str))
