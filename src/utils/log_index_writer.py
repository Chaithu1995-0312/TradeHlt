"""
log_index_writer.py
═══════════════════════════════════════════════════════════════════════════════
Append-only writers for the supplemental index layer at ``logs/index/``.

Rules
─────
* Never raises — all writes are fail-open (silent except on debug logging).
* Never a source of truth — the primary JSONL files remain canonical.
* Append-safe on a single process (no lock needed for JSONL append).
* No external dependencies beyond stdlib.

Index files
───────────
  logs/index/run_index.jsonl         — one line per run start
  logs/index/instrument_index.jsonl  — one line per instrument per run
  logs/index/trade_index.jsonl       — one line per completed trade (at EXIT)

Populated by
────────────
  run_index / instrument_index  ← BacktestRunner.__init__ (backtest_v2.py)
  trade_index                   ← TradeLogger.log_exit()  (trade_logger.py)

Consumed by
───────────
  src/agent/log_query.py        — index-first lookup with path-scan fallback
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time
from pathlib import Path

_INDEX_DIR             = Path("logs/index")
_RUN_INDEX_PATH        = _INDEX_DIR / "run_index.jsonl"
_INSTRUMENT_INDEX_PATH = _INDEX_DIR / "instrument_index.jsonl"
_TRADE_INDEX_PATH      = _INDEX_DIR / "trade_index.jsonl"


# ─────────────────────────────────────────────────────────────────────────────
# Internal primitive
# ─────────────────────────────────────────────────────────────────────────────

def _append_index(path: Path, record: dict) -> None:
    """Append one JSON record to *path*. Silent on any error."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:  # noqa: BLE001
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Public writers
# ─────────────────────────────────────────────────────────────────────────────

def write_run_index(run_id: str, instrument: str, log_dir: str) -> None:
    """
    Record a run start in ``logs/index/run_index.jsonl``.

    Called once per ``BacktestRunner.__init__`` after the run directory
    is created.

    Schema
    ------
    ``{"run_id", "instrument", "start_ts", "log_dir", "offset"}``
    """
    _append_index(_RUN_INDEX_PATH, {
        "run_id":     run_id,
        "instrument": instrument,
        "start_ts":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "log_dir":    log_dir,
        "offset":     0,
    })


def write_instrument_index(run_id: str, instrument: str, log_dir: str) -> None:
    """
    Record an instrument–run pairing in ``logs/index/instrument_index.jsonl``.

    Called alongside ``write_run_index`` from ``BacktestRunner.__init__``.

    Schema
    ------
    ``{"instrument", "run_id", "log_dir", "trade_count", "offset"}``

    Note: ``trade_count`` starts at 0; it is not updated per trade to avoid
    hot-loop overhead.  Use ``log_query.get_instrument()`` for the full list.
    """
    _append_index(_INSTRUMENT_INDEX_PATH, {
        "instrument":  instrument,
        "run_id":      run_id,
        "log_dir":     log_dir,
        "trade_count": 0,
        "offset":      0,
    })


def write_trade_index(
    instrument: str,
    run_id: str,
    trade_id: str,
    log_path: str,
    offset: int = 0,
) -> None:
    """
    Record a completed trade in ``logs/index/trade_index.jsonl``.

    Called from ``TradeLogger.log_exit()`` so the index entry is written
    only for trades that have a corresponding EXIT record.

    Parameters
    ----------
    instrument : str   — canonical symbol, e.g. ``"BTCUSDT"``
    run_id     : str   — matches ``run_index`` entry
    trade_id   : str   — matches ``_ctx.trade_id`` in the fusion JSONL
    log_path   : str   — path to the fusion JSONL file
    offset     : int   — byte offset of the ENTRY record in *log_path*
                         (0 if not tracked; log_query falls back to full scan)

    Schema
    ------
    ``{"instrument", "run_id", "trade_id", "log_path", "offset"}``
    """
    _append_index(_TRADE_INDEX_PATH, {
        "instrument": instrument,
        "run_id":     run_id,
        "trade_id":   trade_id,
        "log_path":   log_path,
        "offset":     offset,
    })
