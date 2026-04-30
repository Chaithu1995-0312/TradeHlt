"""
Centralized Logging Configuration for Trading System
Provides per-flow logging differentiation and aligned format across all modules.

Flows:
    FEATURE_PIPELINE  - Step 1: Feature computation pipeline
    ZONE_GATE         - Step 2: BitNet Zone Gate engine
    ENGINE_RUNNER     - Step 3: Engine fusion + decision
    EXECUTION_PLANNER - Step 4: Trade plan generation
    ULTRON_RISK_GATE  - Step 5: Final risk approval
    LIVE_HOOK         - Live execution hook layer
    COLLECTOR         - Structured data collector

All flows log to:
  1. Dedicated individual log file: logs/flow_{name}.log
  2. Aggregated system log: logs/trade_system.log
  3. Console with color coded flow prefix
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


def get_log_path(name: str, ext: str = "log") -> Path:
    """
    Return a run-stamped path: logs/{name}_{RUN_ID}.{ext}

    Use this everywhere instead of bare 'logs/foo.log' strings so that each
    process invocation writes to its own files.
    """
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
    "COLLECTOR": {
        "file": f"flow_collector_{RUN_ID}.log",
        "color": "\033[90m",  # Gray
        "level": logging.INFO
    }
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
    Get a configured logger for a specific system flow.
    Creates per-flow file handler + aggregated system handler + console handler.
    
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

    # 1. Dedicated per-flow file handler
    flow_file_handler = logging.FileHandler(LOG_DIR / config["file"], encoding="utf-8")
    flow_file_handler.setFormatter(logging.Formatter(BASE_FORMAT, DATE_FORMAT))
    logger.addHandler(flow_file_handler)

    # 2. Aggregated system log handler — stamped per run
    system_file_handler = logging.FileHandler(get_log_path("trade_system"), encoding="utf-8")
    system_file_handler.setFormatter(logging.Formatter(BASE_FORMAT, DATE_FORMAT))
    logger.addHandler(system_file_handler)

    # 3. Console handler with coloring
    console_handler = SafeStreamHandler()
    console_handler.setFormatter(ColoredFlowFormatter(flow_name, BASE_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)

    return logger


def setup_logging() -> None:
    """Initialize logging system. Call once at application startup."""
    logging.basicConfig(level=logging.WARNING, format=BASE_FORMAT, datefmt=DATE_FORMAT)

    # Pre-configure all flow loggers
    for flow_name in FLOWS:
        get_flow_logger(flow_name)

    # Root logger handler for non-flow logs — stamped per run
    root_logger = logging.getLogger()
    root_file_handler = logging.FileHandler(get_log_path("root"), encoding="utf-8")
    root_file_handler.setFormatter(logging.Formatter("[%(asctime)s] [ROOT] [%(levelname)s] %(message)s", DATE_FORMAT))
    root_logger.addHandler(root_file_handler)


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

