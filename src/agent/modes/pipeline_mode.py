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
    description="Simulate one live tick through the engine without placing orders.",
    write=False,
    args_schema={
        "instrument": {"type": "str", "required": True,  "desc": "Trading instrument"},
        "tick_json":  {"type": "str", "required": False, "desc": "JSON tick dict (uses latest bar if omitted)"},
    },
)
def _live_dry_run(instrument: str, tick_json: str = "") -> dict:
    try:
        from runtime.live_engine_hook import LiveEngineHook
        from config_layer.production_config import get_prod_config
        cfg  = get_prod_config(instrument)
        hook = LiveEngineHook(cfg)
        tick = json.loads(tick_json) if tick_json else {}
        result = hook.simulate_one(tick) if hasattr(hook, "simulate_one") else {"status": "dry_run_ok"}
        return result if isinstance(result, dict) else {"status": "ok"}
    except Exception as exc:
        logger.error("live_hook.dry_run: %s", exc)
        return {"status": "error", "error": str(exc)}


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
