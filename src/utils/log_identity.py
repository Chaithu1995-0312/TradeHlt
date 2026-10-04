"""
log_identity.py
═══════════════════════════════════════════════════════════════════════════════
Minimal metadata context helper for the agent-readable execution memory layer.

build_log_context() returns a ``_ctx`` envelope dict that is additively
injected into JSONL payloads. Pure function — no I/O, no side effects,
thread-safe, no external dependencies.

Schema version v1
─────────────────
  {instrument, run_id, trade_id, strategy, phase, schema_version}

Usage
─────
  from utils.log_identity import build_log_context
  record["_ctx"] = build_log_context(
      instrument="BTCUSDT",
      run_id=self._run_id,
      trade_id=trade_id,
      phase="ENTRY",
  )

Agents can correlate coin → run → trade → replay → training using these
metadata fields alone, without scanning directory structures.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from typing import Optional


def build_log_context(
    instrument: str,
    run_id: str,
    trade_id: Optional[str] = None,
    strategy: Optional[str] = None,
    phase: Optional[str] = None,
) -> dict:
    """
    Build a ``_ctx`` envelope for JSONL records.

    Parameters
    ----------
    instrument : str
        Canonical symbol, e.g. ``"BTCUSDT"``.
    run_id : str
        Session identity from ``utils.logging_config.RUN_ID``.
    trade_id : str | None
        Present on trade-scoped records (ENTRY / EXIT). ``None`` for
        signal-level records (REJECT) where the trade was never opened.
    strategy : str | None
        Winning strategy ID from the CRT/Fusion pipeline, or ``None``.
    phase : str | None
        ``"ENTRY"`` | ``"EXIT"`` | ``"REJECT"`` | ``"TRADE"`` | ``None``.

    Returns
    -------
    dict
        Six-key envelope with ``schema_version="v1"``.
    """
    return {
        "instrument":     instrument,
        "run_id":         run_id,
        "trade_id":       trade_id,
        "strategy":       strategy,
        "phase":          phase,
        "schema_version": "v1",
    }
