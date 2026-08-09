"""
exit_model_band.py
================================================================================
[trust-layer F2, 2026-06-10] Dual-bound exit-model report.

Runs the SAME config's backtest under BOTH exit models and reports the
optimistic (close-only) vs conservative (intrabar-touch) bounds side by side,
with an `inflation_ratio = pf_close_only / pf_intrabar`. The GOVERNING model is
intrabar (see CRTConfig.exit_model); this report is visibility-only — promotion
gates run on the conservative metric.

Every metric is recomputed from the trade ledger by the INDEPENDENT
`analytics/metrics_oracle.py` (not the backtest's self-reported numbers), so the
band is oracle-verified. Capital % metrics use the run's initial/final capital.

This is an on-demand reporting path (runs the backtest twice) — NOT on the
validation hot path.
================================================================================
"""

from __future__ import annotations

import csv
import glob
import os
from pathlib import Path
from typing import Optional

from analytics import metrics_oracle as mo

# Exit model → TRUST_INTRABAR_TOUCH env value (overrides config for a forced run).
_MODELS = {"close_only": "0", "intrabar_touch": "1"}


def _read_rr(trades_csv: str) -> list[float]:
    """Extract the per-trade net R-multiple ledger from a BacktestRunner trades CSV."""
    rr: list[float] = []
    with open(trades_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row.get("pnl_rr_net") or row.get("pnl_rr_raw") or ""
            if str(raw).strip():
                try:
                    rr.append(float(raw))
                except ValueError:
                    pass
    return rr


def _run_one(csv_path: str, instrument: str, env_val: str, tmp_dir: str) -> dict:
    """Run one backtest under a forced exit model (via TRUST_INTRABAR_TOUCH) and
    return oracle-recomputed metrics. Restores the prior env afterwards."""
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader

    prev = os.environ.get("TRUST_INTRABAR_TOUCH")
    os.environ["TRUST_INTRABAR_TOUCH"] = env_val
    try:
        bt_cfg = BacktestConfig.from_prod_config(instrument=instrument)
        loader = CandleLoader(csv_path, instrument)
        n = loader.count()
        runner = BacktestRunner(bt_cfg, csv_path=csv_path)
        m = runner.run(loader.stream(), n, output_dir=tmp_dir)
    finally:
        if prev is None:
            os.environ.pop("TRUST_INTRABAR_TOUCH", None)
        else:
            os.environ["TRUST_INTRABAR_TOUCH"] = prev

    pattern = str(Path(tmp_dir) / "**" / f"{instrument}_trades.csv")
    matches = sorted(glob.glob(pattern, recursive=True),
                     key=lambda p: Path(p).stat().st_mtime)
    rr = _read_rr(matches[-1]) if matches else []
    cap = m.capital_curve or {}
    res = mo.recompute(
        rr,
        initial_capital=cap.get("initial_capital"),
        final_capital=cap.get("final_capital"),
        total_candles=m.total_candles,
    )
    return {
        "pf": res.profit_factor,
        "expectancy": res.expectancy_mean,
        "win_rate": res.win_rate,
        "trade_count": res.trades,
        "max_drawdown": m.max_drawdown_pct,   # compounded DD from the run's equity curve
        "total_return": res.total_return_pct,
    }


def _band_from_models(co: dict, ib: dict, instrument: str) -> dict:
    """Pure: assemble the flat dual-bound band from two per-model metric dicts.
    Guards inflation_ratio against divide-by-zero. (Unit-testable without a run.)"""
    band = {
        "instrument": instrument,
        "exit_model_governing": "intrabar_touch",
        "pf_close_only": co["pf"], "pf_intrabar": ib["pf"],
        "expectancy_close_only": co["expectancy"], "expectancy_intrabar": ib["expectancy"],
        "win_rate_close_only": co["win_rate"], "win_rate_intrabar": ib["win_rate"],
        "trade_count_close_only": co["trade_count"], "trade_count_intrabar": ib["trade_count"],
        "max_drawdown_close_only": co["max_drawdown"], "max_drawdown_intrabar": ib["max_drawdown"],
        "total_return_close_only": co["total_return"], "total_return_intrabar": ib["total_return"],
    }
    pf_co, pf_ib = co["pf"], ib["pf"]
    if pf_ib == 0:
        band["inflation_ratio"] = None
        band["note"] = "both PF zero" if pf_co == 0 else "intrabar PF zero"
    else:
        band["inflation_ratio"] = round(pf_co / pf_ib, 4)
    return band


def compute_exit_model_band(
    csv_path: str,
    instrument: str,
    *,
    tmp_dir: str = "results/exit_model_band_tmp",
) -> dict:
    """Run the backtest under both exit models and return the oracle-verified band."""
    co = _run_one(csv_path, instrument, _MODELS["close_only"], tmp_dir)
    ib = _run_one(csv_path, instrument, _MODELS["intrabar_touch"], tmp_dir)
    return _band_from_models(co, ib, instrument)
