"""
pipeline_mode.py — Pipeline Orchestrator tool registrations
─────────────────────────────────────────────────────────────────────────────
Tools: tuner.run_multi, validator.validate, promotion.promote_from_checkpoint,
       backtest.run_v2, live_hook.dry_run, live_hook.enable

All write=True tools are confirmed per-call by Executor before execution.
Existing quality gates (ConfigValidator hard gates, ShadowPromotionGate)
are NOT bypassed — they run inside the handler as normal.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from ..tool_registry import register_tool

logger = logging.getLogger("PipelineMode")


# ── tuner.run_multi ────────────────────────────────────────────────────────────

@register_tool(
    name="tuner.run_multi",
    description="Run multi-instrument parameter grid search. Writes results/tuner/checkpoint_multi.json",
    write=True,
    args_schema={
        "data_dir":    {"type": "str", "required": True,  "desc": "Directory containing OHLCV CSV files"},
        "instruments": {"type": "str", "required": False, "desc": "Space-separated instruments (default: all in data_dir)"},
        "n_iter":      {"type": "int", "required": False, "desc": "Grid search iterations (default: 50)"},
    },
)
def _tuner_run_multi(data_dir: str = "data/", instruments: str = "", n_iter: int = 50) -> dict:
    cmd = [sys.executable, "scripts/training/auto_tuner_multi.py",
           "--data-dir", data_dir, "--n-iter", str(n_iter)]
    if instruments:
        cmd += ["--instruments"] + instruments.split()
    logger.info("Running tuner: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(f"Tuner failed (rc={proc.returncode}): {proc.stderr[-500:]}")
    checkpoint = Path("results/tuner/checkpoint_multi.json")
    if checkpoint.exists():
        with open(checkpoint) as f:
            return json.load(f)
    return {"status": "ok", "checkpoint": str(checkpoint)}


# ── validator.validate ─────────────────────────────────────────────────────────

@register_tool(
    name="validator.validate",
    description="Validate a candidate config via backtest quality gates. Returns ValidationReport dict.",
    write=False,
    args_schema={
        "checkpoint_path": {"type": "str", "required": False, "desc": "Tuner checkpoint JSON (default: results/tuner/checkpoint_multi.json)"},
        "data_dir":        {"type": "str", "required": False, "desc": "CSV directory (default: data/)"},
        "config_id":       {"type": "str", "required": False, "desc": "Config label for the report"},
    },
)
def _validator_validate(
    checkpoint_path: str = "results/tuner/checkpoint_multi.json",
    data_dir: str = "data/",
    config_id: str = "candidate",
) -> dict:
    try:
        from config_layer.config_validator import ConfigValidator
        cp = Path(checkpoint_path)
        if not cp.exists():
            return {"status": "error", "error": f"Checkpoint not found: {checkpoint_path}"}
        with open(cp) as f:
            checkpoint = json.load(f)
        params = checkpoint.get("params", checkpoint.get("best_params", {}))
        csv_paths = {
            p.stem.split("_M15")[0]: str(p)
            for p in Path(data_dir).glob("*_M15.csv")
        }
        report = ConfigValidator().validate(params, csv_paths, config_id)
        return report if isinstance(report, dict) else {"status": "ok", "report": str(report)}
    except Exception as exc:
        logger.error("validator.validate: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── promotion.promote_from_checkpoint ─────────────────────────────────────────

@register_tool(
    name="promotion.promote_from_checkpoint",
    description="Promote a validated config to configs/production/. Requires approved ValidationReport.",
    write=True,
    args_schema={
        "checkpoint_path": {"type": "str", "required": False, "desc": "Tuner checkpoint JSON"},
        "version":         {"type": "str", "required": True,  "desc": "New version string, e.g. v2_eurusd_20260418"},
        "data_dir":        {"type": "str", "required": False, "desc": "CSV directory"},
    },
)
def _promotion_promote(
    checkpoint_path: str = "results/tuner/checkpoint_multi.json",
    version: str = "",
    data_dir: str = "data/",
) -> dict:
    if not version:
        raise ValueError("version is required for promotion")
    try:
        from governance.promotion_manager import PromotionManager
        pm = PromotionManager()
        result = pm.promote_from_tuner_checkpoint(
            checkpoint_path=checkpoint_path,
            version=version,
            data_dir=data_dir,
        )
        return result if isinstance(result, dict) else {"status": "ok", "version": version}
    except Exception as exc:
        logger.error("promotion.promote: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── backtest.run_v2 ────────────────────────────────────────────────────────────

@register_tool(
    name="backtest.run_v2",
    description="Run deterministic candle-by-candle backtest. Returns metrics dict.",
    write=False,
    args_schema={
        "csv_path":   {"type": "str", "required": True,  "desc": "OHLCV CSV file path"},
        "instrument": {"type": "str", "required": False, "desc": "Instrument name (inferred from csv_path if omitted)"},
    },
)
def _backtest_run(csv_path: str, instrument: str = "") -> dict:
    try:
        from runtime.backtest_v2 import BacktestRunner
        from config_layer.production_config import get_prod_config
        inst = instrument or Path(csv_path).stem.split("_M15")[0]
        cfg  = get_prod_config(inst)
        runner = BacktestRunner(cfg)
        return runner.run(csv_path=csv_path)
    except Exception as exc:
        logger.error("backtest.run_v2: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── live_hook.dry_run ──────────────────────────────────────────────────────────

@register_tool(
    name="live_hook.dry_run",
    description=(
        "Paper one HookedLiveEngine.process call (hook_submit_orders=False). "
        "Requires bars_jsonl with warmup+1 OHLCV rows; refuses if the feeder is not ready. "
        "Does not place orders."
    ),
    write=False,
    args_schema={
        "instrument": {"type": "str", "required": True,  "desc": "Trading instrument"},
        "bars_jsonl": {"type": "str", "required": False, "desc": "JSONL of OHLCV bars (timestamp/open/high/low/close/volume)"},
        "tick_json":  {"type": "str", "required": False, "desc": "Optional last-bar JSON appended after bars_jsonl"},
        "timeframe":  {"type": "str", "required": False, "desc": "Bar timeframe (default M15)"},
    },
)
def _live_dry_run(
    instrument: str,
    bars_jsonl: str = "",
    tick_json: str = "",
    timeframe: str = "M15",
) -> dict:
    """Rewrite (PR-4d): feeder → HookedLiveEngine.process. Not a rename.

    HookedLiveEngine does not take a production-config dict and has no one-tick simulator.
    """
    from datetime import datetime, timedelta

    from config_layer.crt_engine_v2 import Candle
    from config_layer.production_config import get_prod_section
    from engines.live_engine import LiveEngineConfig
    from inout.live_rail.types import ClockBasis, ClosedBar, VenueName
    from runtime.live_engine_hook import HookedLiveEngine
    from runtime.live_rail_feeder import LiveRailFeeder

    def _parse_ts(raw: object) -> datetime:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            raise ValueError("naive timestamp refused (F-066)")
        return ts

    def _bar_from_row(row: dict, index: int) -> ClosedBar:
        ts = _parse_ts(row.get("ts") or row.get("timestamp"))
        candle = Candle(
            timestamp=ts,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0.0)),
            index=index,
        )
        return ClosedBar(
            candle=candle,
            extras={},
            symbol=instrument,
            clock_basis=ClockBasis.BROKER_LOCAL,
            venue=VenueName.TICKDB,
            n_ticks=1,
            period_start=ts,
            period_end=ts + timedelta(minutes=15),
        )

    rows: list[dict] = []
    if bars_jsonl:
        path = Path(bars_jsonl)
        if not path.is_file():
            return {"status": "error", "error": f"bars_jsonl not found: {bars_jsonl}"}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if tick_json:
        extra = json.loads(tick_json)
        if isinstance(extra, list):
            rows.extend(extra)
        else:
            rows.append(extra)
    if not rows:
        return {
            "status": "error",
            "error": "feeder_not_ready",
            "detail": "bars_jsonl or tick_json required; a single missing history is a refuse",
        }

    feeder = LiveRailFeeder(symbol=instrument, timeframe=timeframe or "M15")
    last: ClosedBar | None = None
    for i, row in enumerate(rows):
        last = _bar_from_row(row, i)
        feeder.push(last)
    if last is None or not feeder.ready():
        return {
            "status": "error",
            "error": "feeder_not_ready",
            "n_bars": len(rows),
            "warmup_rows": feeder.warmup_rows,
            "need": feeder.warmup_rows + 1,
        }

    ep = get_prod_section("execution_planner") or {}
    if "default_account_balance" not in ep:
        return {
            "status": "error",
            "error": "execution_planner.default_account_balance missing",
        }
    portfolio = {
        "account_balance": float(ep["default_account_balance"]),
        "total_open_risk_pct": 0.0,
        "trades_today": 0,
        "daily_loss_pct": 0.0,
        "open_positions": 0,
        "positions": {},
    }
    trade_data = feeder.as_trade_data(last, portfolio)
    hook = HookedLiveEngine(
        LiveEngineConfig(enabled=False),
        hook_submit_orders=False,
    )
    try:
        result = hook.process(
            trade_data,
            gaussian_model=None,
            scaler=None,
            candle_idx=int(last.candle.index),
            timeframe=timeframe or "M15",
        )
    except Exception as exc:
        logger.error("live_hook.dry_run process failed: %s", exc)
        return {"status": "error", "error": str(exc), "hook_submit_orders": False}
    if not isinstance(result, dict):
        return {"status": "error", "error": "process_returned_non_dict"}
    return {"status": "ok", "hook_submit_orders": False, "result": result}


# ── live_hook.enable ───────────────────────────────────────────────────────────

@register_tool(
    name="live_hook.enable",
    description="Toggle live trading on/off in production config (live_toggle key).",
    write=True,
    allowlist=False,    # must be explicitly added to write_tools_enabled
    args_schema={
        "enable": {"type": "bool", "required": True, "desc": "true to enable, false to disable"},
    },
)
def _live_enable(enable: bool = True) -> dict:
    cfg_path = Path("configs/production") / "live_toggle.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    state = {"live_toggle": enable}
    with open(cfg_path, "w") as f:
        json.dump(state, f)
    logger.info("live_toggle set to %s", enable)
    return {"status": "ok", "live_toggle": enable, "path": str(cfg_path)}
