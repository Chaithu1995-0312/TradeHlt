"""
log_query_mode.py — Read-only log query tool registrations
─────────────────────────────────────────────────────────────────────────────
Tools: log.get_run, log.get_trade, log.query

All three are write=False (read-only). If log_query is not importable,
handlers return an error dict rather than raising.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..tool_registry import register_tool

logger = logging.getLogger("LogQueryMode")

# Optional import guard — fail-open
try:
    from .. import log_query as _log_query
    _LQ_AVAILABLE = True
except ImportError as _lq_err:
    _log_query = None  # type: ignore[assignment]
    _LQ_AVAILABLE = False
    logger.warning("log_query not importable — log.* tools will return errors: %s", _lq_err)


# ── log.get_run ───────────────────────────────────────────────────────────────

@register_tool(
    name="log.get_run",
    description="Return the run index record for a run_id. Read-only.",
    write=False,
    args_schema={
        "run_id": {"type": "str", "required": True, "desc": "Run ID from run_index"},
    },
)
def _log_get_run(run_id: str) -> dict:
    if not _LQ_AVAILABLE:
        return {"status": "error", "error": "log_query module not available"}
    result = _log_query.get_run(run_id)
    if result is None:
        return {"status": "not_found", "run_id": run_id}
    return result


# ── log.get_trade ─────────────────────────────────────────────────────────────

@register_tool(
    name="log.get_trade",
    description="Return the ENTRY record for a trade_id. Read-only.",
    write=False,
    args_schema={
        "trade_id": {"type": "str", "required": True, "desc": "Trade ID from fusion JSONL"},
    },
)
def _log_get_trade(trade_id: str) -> dict:
    if not _LQ_AVAILABLE:
        return {"status": "error", "error": "log_query module not available"}
    result = _log_query.get_trade(trade_id)
    if result is None:
        return {"status": "not_found", "trade_id": trade_id}
    return result


# ── log.query ─────────────────────────────────────────────────────────────────

@register_tool(
    name="log.query",
    description="Query ENTRY records across the execution memory layer. Read-only.",
    write=False,
    args_schema={
        "instrument": {"type": "str", "required": False, "desc": "Filter by instrument"},
        "run_id":     {"type": "str", "required": False, "desc": "Filter by run ID"},
        "trade_id":   {"type": "str", "required": False, "desc": "Return exactly this trade"},
        "limit":      {"type": "int", "required": False, "desc": "Max records to return (default 50, max 500)"},
    },
)
def _log_query_fn(
    instrument: Optional[str] = None,
    run_id: Optional[str] = None,
    trade_id: Optional[str] = None,
    limit: int = 50,
) -> dict:
    if not _LQ_AVAILABLE:
        return {"status": "error", "error": "log_query module not available"}
    records = _log_query.query(
        instrument=instrument,
        run_id=run_id,
        trade_id=trade_id,
        limit=limit,
    )
    return {"status": "ok", "count": len(records), "records": records}
