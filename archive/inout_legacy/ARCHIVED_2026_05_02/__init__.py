"""
inout — INOUT Strategy Module
═══════════════════════════════════════════════════════════════════════════════

Event-driven micro-cycle extraction system for fast explosive moves.
Runs PARALLEL to the main EngineRunner pipeline — zero shared state.

Architecture
------------
    INOUTScanner      — explosive move detection (M1/M5)
    INOUTController   — signal acceptance + trade lifecycle
    INOUTStateMachine — SEP-01 state transitions
    INOUTExecutor     — broker interaction (stub → Phase 2 Binance)
    INOUTDatabase     — SQLite persistence (WAL, atomic)
    INOUTConfig       — config-driven parameters
    INOUTRunner       — standalone event loop (do NOT share with EngineRunner)

Existing system boundaries (HARD — zero modifications):
    EngineRunner         → READ ONLY (not imported by INOUT)
    FusionEngine         → READ ONLY (not imported by INOUT)
    UltronRiskGate       → imported READ ONLY by controller.py
    ExecutionPlannerV1_2 → NOT USED (INOUT builds its own plans)
    live_engine_hook.py  → NOT TOUCHED (INOUT has its own runner)

Quick start
-----------
    # Dry-run test (Phase 1):
    python -m inout.runner --cycles 5

    # With custom config:
    INOUT_CONFIG_PATH=production_configs/v1_multi_2026_03.json python -m inout.runner

Extension points (left clear for Phase 2 / Phase 3)
-----------------------------------------------------
    scanner.py     → _compute_composite_score()   replace with probability engine
    scanner.py     → _fetch_candles() in runner    replace with Binance websocket
    executor.py    → _place_market_order()         replace with real Binance API
    config.py      → time section                  replace with P50/P75/P90 distribution
    controller.py  → on_signal()                   add Gemini context layer
    db.py          → prob_snapshot column           populate with probability engine
"""

from .config import INOUTConfig, INOUT_DEFAULTS
from .db import INOUTDatabase
from .scanner import INOUTScanner, INOUTSignal
from .state_machine import INOUTStateMachine, ActionInstruction, ActionType
from .executor import INOUTExecutor, FillResult
from .controller import INOUTController
# INOUTRunner and ProbabilityEngine are intentionally NOT eagerly imported here.
# Eager import caused a RuntimeWarning when running `python -m inout.runner`
# because __init__ would import runner before __main__ executed it.
# Import them explicitly at call sites: `from inout.runner import INOUTRunner`

__all__ = [
    "INOUTConfig",
    "INOUT_DEFAULTS",
    "INOUTDatabase",
    "INOUTScanner",
    "INOUTSignal",
    "INOUTStateMachine",
    "ActionInstruction",
    "ActionType",
    "INOUTExecutor",
    "FillResult",
    "INOUTController",
    # INOUTRunner and ProbabilityEngine omitted — import from submodules directly
]

__version__ = "1.1.0-phase2"
