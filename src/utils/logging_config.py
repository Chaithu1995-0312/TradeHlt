"""
Centralized Logging Configuration for Trading System
Provides per-flow logging differentiation and aligned format across all modules.

Flows active in every standard backtest (no env flags required):
    FEATURE_PIPELINE  - Step 1: Feature computation pipeline
    ZONE_GATE         - Step 2: BitNet Zone Gate engine

Flows active only when BACKTEST_ENGINE_GATE=1:
    ENGINE_RUNNER     - Step 3: Engine fusion + decision
    EXECUTION_PLANNER - Step 4: Trade plan generation
    ULTRON_RISK_GATE  - Step 5: Final risk approval (also needs disabled=False in config)
    COLLECTOR         - Structured data collector (called by EngineRunner)
    COGNITIVE_BUS     - Async cognitive layer (also needs cognitive_layer.enabled=True)
    crt_engine / llm_engine loggers (parallel engine wrappers via EngineRunner)

Live-mode only:
    LIVE_HOOK         - Live execution hook layer
    LIVE_RAIL         - TickDB / BarBuilder / live-rail adapters (PR-1; unwired)

All coin-scoped flows log to:
  1. Dedicated per-flow file: logs/run_{RUN_ID}/{symbol}/flow_{name}.log
  2. Aggregated system log:  logs/run_{RUN_ID}/{symbol}/trade_system.log
     (populated by modules that use logging.getLogger("trade_system"))
  3. Console with color coded flow prefix

File handlers are created lazily (delay=True) — files only appear on first write.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.console_safe import SafeStreamHandler, safe_print

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True, parents=True)

# ── RUN_ID — unique per process invocation ────────────────────────────────────
# Generated once at module import.  Every log file for this run carries the
# same stamp so you can correlate flow_engine_runner, trade_system, and
# crt_engine files across a single run without ambiguity.
RUN_ID: str = datetime.now().strftime("%Y%m%d_%H%M%S")


def get_log_path(name: str, ext: str = "log", symbol: Optional[str] = None) -> Path:
    """
    Return a run-stamped log path.

    With symbol → logs/run_{RUN_ID}/{symbol}/{name}.{ext}  (coin-scoped run dir)
    Without     → logs/{name}_{RUN_ID}.{ext}               (legacy flat path)
    """
    if symbol:
        run_dir = LOG_DIR / f"run_{RUN_ID}" / symbol
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir / f"{name}.{ext}"
    return LOG_DIR / f"{name}_{RUN_ID}.{ext}"


# Flow definitions — file names are resolved at runtime via get_log_path()
FLOWS = {
    "FEATURE_PIPELINE": {
        "file": f"flow_feature_pipeline_{RUN_ID}.log",
        "color": "\033[94m",  # Blue
        "level": logging.INFO
    },
    "ZONE_GATE": {
        "file": f"flow_zone_gate_{RUN_ID}.log",
        "color": "\033[96m",  # Cyan
        "level": logging.INFO
    },
    "ENGINE_RUNNER": {
        "file": f"flow_engine_runner_{RUN_ID}.log",
        "color": "\033[92m",  # Green
        "level": logging.INFO
    },
    "EXECUTION_PLANNER": {
        "file": f"flow_execution_planner_{RUN_ID}.log",
        "color": "\033[93m",  # Yellow
        "level": logging.INFO
    },
    "ULTRON_RISK_GATE": {
        "file": f"flow_ultron_risk_gate_{RUN_ID}.log",
        "color": "\033[91m",  # Red
        "level": logging.INFO
    },
    "LIVE_HOOK": {
        "file": f"flow_live_hook_{RUN_ID}.log",
        "color": "\033[95m",  # Magenta
        "level": logging.INFO
    },
    "LIVE_RAIL": {
        "file": f"flow_live_rail_{RUN_ID}.log",
        "color": "\033[95m",  # Magenta
        "level": logging.INFO
    },
    "COLLECTOR": {
        "file": f"flow_collector_{RUN_ID}.log",
        "color": "\033[90m",  # Gray
        "level": logging.INFO
    },
    "STRATEGY_ENGINE": {
        "file": f"flow_strategy_engine_{RUN_ID}.log",
        "color": "\033[36m",   # Teal
        "level": logging.INFO
    },
    "DATA_INGESTION": {
        "file": f"flow_data_ingestion_{RUN_ID}.log",
        "color": "\033[35m",   # Purple
        "level": logging.INFO
    },
    "GATE_INTELLIGENCE": {
        "file": f"flow_gate_intelligence_{RUN_ID}.log",
        "color": "\033[93m",   # Yellow
        "level": logging.INFO
    },
    # ── Cognitive / Replay / Regime flows (Part 11 additions) ─────────────
    "REPLAY_MEMORY": {
        "file": f"flow_replay_memory_{RUN_ID}.log",
        "color": "\033[34m",   # Blue
        "level": logging.INFO
    },
    "REPLAY_DRIFT_GOVERNOR": {
        "file": f"flow_replay_drift_{RUN_ID}.log",
        "color": "\033[34m",   # Blue
        "level": logging.INFO
    },
    "MARKET_STATE_CLUSTER": {
        "file": f"flow_market_state_{RUN_ID}.log",
        "color": "\033[35m",   # Purple
        "level": logging.INFO
    },
    "TRADENET_META": {
        "file": f"flow_tradenet_meta_{RUN_ID}.log",
        "color": "\033[36m",   # Teal
        "level": logging.INFO
    },
    "HIERARCHICAL_META_FUSION": {
        "file": f"flow_hmf_{RUN_ID}.log",
        "color": "\033[33m",   # Orange/Brown
        "level": logging.INFO
    },
    "COGNITIVE_BUS": {
        "file": f"flow_cognitive_bus_{RUN_ID}.log",
        "color": "\033[35m",   # Purple
        "level": logging.INFO
    },
}

BASE_FORMAT = "[%(asctime)s] [FLOW:%(flow_name)s] [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
COLOR_RESET = "\033[0m"


class FlowLogFilter(logging.Filter):
    """Filter that injects flow_name into log records"""
    def __init__(self, flow_name: str):
        super().__init__()
        self.flow_name = flow_name

    def filter(self, record):
        record.flow_name = self.flow_name
        return True


class ColoredFlowFormatter(logging.Formatter):
    """Format log lines with color coding per flow"""
    def __init__(self, flow_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = FLOWS[flow_name]["color"] if flow_name in FLOWS else ""

    def format(self, record):
        formatted = super().format(record)
        if self.color:
            return f"{self.color}{formatted}{COLOR_RESET}"
        return formatted


def get_flow_logger(flow_name: str) -> logging.Logger:
    """
    Get a logger for a specific system flow (console output only).
    File handlers are attached lazily by init_coin_logging(symbol) when a
    BacktestRunner is started, keeping log files coin-scoped under
    logs/run_{RUN_ID}/{symbol}/.

    Args:
        flow_name: One of the predefined flow names from FLOWS dict
    Returns:
        Configured logging.Logger instance
    """
    if flow_name not in FLOWS:
        raise ValueError(f"Unknown flow name: {flow_name}. Valid flows: {list(FLOWS.keys())}")

    logger = logging.getLogger(f"flow.{flow_name.lower()}")
    logger.propagate = False

    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    config = FLOWS[flow_name]
    logger.setLevel(config["level"])
    logger.addFilter(FlowLogFilter(flow_name))

    # Console handler only — file handlers added by init_coin_logging()
    console_handler = SafeStreamHandler()
    console_handler.setFormatter(ColoredFlowFormatter(flow_name, BASE_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)

    return logger


# ── Coin-level log management ─────────────────────────────────────────────────
# Maps symbol → list of (logger, handler) pairs attached during init_coin_logging.
_coin_file_handlers: dict[str, list[tuple[logging.Logger, logging.Handler]]] = {}


def init_coin_logging(symbol: str) -> None:
    """Attach per-coin file handlers to all flow loggers and engine loggers.

    Creates logs/run_{RUN_ID}/{symbol}/ and writes each flow's log there.
    Safe to call multiple times for the same symbol (idempotent).
    For multi-coin sequential runs, call close_coin_logging(prev_symbol) first.
    """
    if symbol in _coin_file_handlers:
        return

    run_dir = LOG_DIR / f"run_{RUN_ID}" / symbol
    run_dir.mkdir(parents=True, exist_ok=True)

    pairs: list[tuple[logging.Logger, logging.Handler]] = []
    fmt = logging.Formatter(BASE_FORMAT, DATE_FORMAT)

    for flow_name, config in FLOWS.items():
        # get_flow_logger ensures FlowLogFilter is on the logger before the
        # FileHandler is attached — without it %(flow_name)s in BASE_FORMAT
        # raises a KeyError that Python's logging swallows silently, producing
        # 0-byte files even when records DO arrive.
        logger = get_flow_logger(flow_name)
        stem = config["file"].replace(f"_{RUN_ID}.log", "")
        # delay=True: file is only created on first actual write — no 0-byte ghosts
        fh = logging.FileHandler(run_dir / f"{stem}.log", encoding="utf-8", delay=True)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        pairs.append((logger, fh))

    # Engine loggers that manage their own named loggers (JSON-only format)
    for eng_name in ("crt_engine", "llm_engine"):
        eng_logger = logging.getLogger(eng_name)
        if not eng_logger.propagate:
            eh = logging.FileHandler(run_dir / f"{eng_name}.log", encoding="utf-8", delay=True)
            eh.setFormatter(logging.Formatter("%(message)s"))
            eng_logger.addHandler(eh)
            pairs.append((eng_logger, eh))

    # Aggregated trade_system.log — a single file capturing records from any
    # module that uses logging.getLogger("trade_system").  Populated only when
    # those modules explicitly log; delay=True prevents a 0-byte ghost file.
    ts_logger = logging.getLogger("trade_system")
    ts_logger.setLevel(logging.DEBUG)
    ts_logger.propagate = False
    if not any(isinstance(h, logging.FileHandler) for h in ts_logger.handlers):
        ts_fh = logging.FileHandler(run_dir / "trade_system.log", encoding="utf-8", delay=True)
        ts_fh.setFormatter(fmt)
        ts_logger.addHandler(ts_fh)
        pairs.append((ts_logger, ts_fh))

    _coin_file_handlers[symbol] = pairs


def close_coin_logging(symbol: str) -> None:
    """Flush and remove per-coin file handlers (call between coins in multi-coin runs)."""
    for logger, handler in _coin_file_handlers.pop(symbol, []):
        try:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)
        except Exception:
            pass


def setup_logging() -> None:
    """Initialize console logging for all flows (non-backtest entry points).

    Backtest runs should call init_coin_logging(symbol) instead to get
    coin-scoped file output under logs/run_{RUN_ID}/{symbol}/.
    """
    logging.basicConfig(level=logging.WARNING, format=BASE_FORMAT, datefmt=DATE_FORMAT)
    for flow_name in FLOWS:
        get_flow_logger(flow_name)


if __name__ == "__main__":
    # Self test
    setup_logging()
    safe_print("=== Testing Logging Configuration ===")

    # Test all flows
    for flow in FLOWS:
        logger = get_flow_logger(flow)
        logger.info(f"Configuration test log for {flow}")

    safe_print(f"\nLog files created in: {LOG_DIR.absolute()}")
    safe_print("âœ… Logging configuration initialized successfully")

