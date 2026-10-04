"""
log_query.py
═══════════════════════════════════════════════════════════════════════════════
Agent-readable query interface over the execution memory layer.

Reads from (in priority order)
───────────────────────────────
  1. logs/index/run_index.jsonl        — index of runs
  2. logs/index/instrument_index.jsonl — index of instruments per run
  3. logs/index/trade_index.jsonl      — index of trades + byte offsets
  4. logs/run_{RUN_ID}/{instr}/{instr}_fusion.jsonl — primary source of truth

Query hierarchy (most → least specific)
────────────────────────────────────────
  trade_id  → return exactly that ENTRY record
  run_id    → return all ENTRY records for that run
  instrument→ return all ENTRY records for that instrument (all runs)
  (none)    → return most recent N ENTRY records across all runs

Design rules
────────────
  * Index first; fallback to one-level path scan on index miss
  * Stream reads — never load full files into memory
  * Never scan folders recursively (one glob level at most)
  * All public functions return [] / None on miss, never raise
  * Read-only — no writes from this module
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger("LogQuery")

_LOGS_DIR              = Path("logs")
_INDEX_DIR             = _LOGS_DIR / "index"
_RUN_INDEX_PATH        = _INDEX_DIR / "run_index.jsonl"
_INSTRUMENT_INDEX_PATH = _INDEX_DIR / "instrument_index.jsonl"
_TRADE_INDEX_PATH      = _INDEX_DIR / "trade_index.jsonl"


# ─────────────────────────────────────────────────────────────────────────────
# Internal streaming primitives
# ─────────────────────────────────────────────────────────────────────────────

def _iter_jsonl(path: Path) -> Iterator[dict]:
    """
    Stream JSONL records one at a time.
    Skips blank lines and malformed JSON. Never raises.
    """
    if not path.is_file():
        return
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _iter_jsonl_from_offset(path: Path, offset: int) -> Iterator[dict]:
    """
    Stream JSONL from a byte offset.
    Degrades to full scan if seek fails (e.g. offset is stale or 0).
    Never raises.
    """
    if not path.is_file():
        return
    try:
        with path.open("r", encoding="utf-8") as fh:
            if offset > 0:
                try:
                    fh.seek(offset)
                except OSError:
                    fh.seek(0)
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


# ─────────────────────────────────────────────────────────────────────────────
# Path-scan fallback (single-level glob only, no recursion)
# ─────────────────────────────────────────────────────────────────────────────

def _scan_fusion_paths(
    instrument: Optional[str],
    run_id: Optional[str],
) -> list[Path]:
    """
    Locate fusion JSONL files without recursive scanning.

    Pattern: logs/run_{run_id}/{instrument}/{instrument}_fusion.jsonl

    One glob level: logs/run_*/  — then one iterdir() inside.
    """
    results: list[Path] = []
    if not _LOGS_DIR.is_dir():
        return results

    if run_id:
        run_dirs = [_LOGS_DIR / f"run_{run_id}"]
    else:
        # Single glob — not recursive
        run_dirs = [d for d in _LOGS_DIR.glob("run_*") if d.is_dir()]

    for rd in run_dirs:
        if not rd.is_dir():
            continue
        if instrument:
            candidate = rd / instrument / f"{instrument}_fusion.jsonl"
            if candidate.is_file():
                results.append(candidate)
        else:
            # One iterdir() level — no further recursion
            for instr_dir in rd.iterdir():
                if not instr_dir.is_dir():
                    continue
                candidate = instr_dir / f"{instr_dir.name}_fusion.jsonl"
                if candidate.is_file():
                    results.append(candidate)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_run(run_id: str) -> Optional[dict]:
    """
    Return the run index record for *run_id*, or ``None`` if not found.

    Reads ``logs/index/run_index.jsonl`` only — no file scanning.

    Returns the most recent entry when the same run_id appears more than once
    (can happen if BacktestRunner is instantiated multiple times in one process).
    """
    if not run_id:
        return None
    result = None
    for rec in _iter_jsonl(_RUN_INDEX_PATH):
        if rec.get("run_id") == run_id:
            result = rec  # keep latest
    return result


def get_instrument(
    instrument: str,
    run_id: Optional[str] = None,
) -> list[dict]:
    """
    Return instrument index records for *instrument* (optionally filtered by *run_id*).

    Index first; falls back to a path scan and reconstructs minimal index records
    if the instrument_index has no entries for this instrument.

    Returns a list of index records — not trade records.
    Use ``query(instrument=...)`` to get trade ENTRY records.
    """
    if not instrument:
        return []

    # Index first
    results = [
        rec for rec in _iter_jsonl(_INSTRUMENT_INDEX_PATH)
        if rec.get("instrument") == instrument
        and (run_id is None or rec.get("run_id") == run_id)
    ]
    if results:
        return results

    # Fallback: one-level path scan
    paths = _scan_fusion_paths(instrument, run_id)
    fallback: list[dict] = []
    for p in paths:
        try:
            inferred_run_id = p.parent.parent.name.removeprefix("run_")
        except Exception:  # noqa: BLE001
            inferred_run_id = ""
        fallback.append({
            "instrument":  instrument,
            "run_id":      inferred_run_id,
            "log_dir":     str(p.parent),
            "trade_count": 0,
            "offset":      0,
        })
    return fallback


def get_trade(trade_id: str) -> Optional[dict]:
    """
    Return the ENTRY record for *trade_id*, or ``None`` if not found.

    Strategy
    --------
    1. Look up the trade in ``logs/index/trade_index.jsonl``
       → seek to the stored byte offset in the fusion JSONL
       → return the first ENTRY record whose trade_id matches.
    2. On index miss (or seek miss), fall back to a one-level path scan
       across all fusion JSONL files.

    Returns the full ENTRY record dict, including the ``_ctx`` envelope if
    the record was written after the Phase M enhancement.
    """
    if not trade_id:
        return None

    # Index first
    for idx_rec in _iter_jsonl(_TRADE_INDEX_PATH):
        if idx_rec.get("trade_id") != trade_id:
            continue
        log_path = Path(idx_rec.get("log_path", ""))
        offset   = int(idx_rec.get("offset", 0))
        # Try seek-then-scan from stored offset
        for record in _iter_jsonl_from_offset(log_path, offset):
            if record.get("trade_id") == trade_id and record.get("event") == "ENTRY":
                return record
        # Seek may have overshot — full scan of that specific file
        for record in _iter_jsonl(log_path):
            if record.get("trade_id") == trade_id and record.get("event") == "ENTRY":
                return record
        return None  # index pointed to a real path but trade not found there

    # Fallback: scan all known fusion files (no recursion)
    for path in _scan_fusion_paths(None, None):
        for record in _iter_jsonl(path):
            if record.get("trade_id") == trade_id and record.get("event") == "ENTRY":
                return record

    return None


def query(
    instrument: Optional[str] = None,
    run_id: Optional[str] = None,
    trade_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Query ENTRY records across the execution memory layer.

    Hierarchy (most specific wins)
    ───────────────────────────────
    trade_id   → return exactly that one trade (delegates to get_trade)
    run_id     → all ENTRY records for that run
    instrument → all ENTRY records for that instrument across all runs
    (none)     → most recent ``limit`` ENTRY records across all runs

    Returns
    -------
    list[dict]
        ENTRY records sorted by ``timestamp`` descending (most recent first),
        capped at *limit*. EXIT and REJECT records are never returned here;
        use ``get_trade(trade_id)`` and then stream the fusion JSONL for the
        full lifecycle.

    Notes
    -----
    * Streams line-by-line; stops each file as soon as *limit* is reached.
    * Never loads full files into memory.
    * Capped at 500 even if a higher limit is requested.
    """
    limit = max(1, min(limit, 500))

    if trade_id:
        rec = get_trade(trade_id)
        return [rec] if rec is not None else []

    # Resolve fusion JSONL paths ─────────────────────────────────────────────
    if instrument or run_id:
        instr_records = get_instrument(instrument or "", run_id) if instrument else []

        # run_id-only: look up instrument via run_index
        if not instr_records and run_id:
            run_rec = get_run(run_id)
            if run_rec:
                instr_records = [{
                    "instrument":  run_rec.get("instrument", ""),
                    "run_id":      run_id,
                    "log_dir":     run_rec.get("log_dir", ""),
                    "trade_count": 0,
                    "offset":      0,
                }]

        # Resolve index records → actual JSONL paths
        paths: list[Path] = []
        for ir in instr_records:
            log_dir = ir.get("log_dir", "")
            instr   = ir.get("instrument", "")
            if log_dir and instr:
                p = Path(log_dir) / f"{instr}_fusion.jsonl"
                if p.is_file():
                    paths.append(p)

        if not paths:
            # Final fallback: one-level scan
            paths = _scan_fusion_paths(instrument, run_id)
    else:
        paths = _scan_fusion_paths(None, None)

    # Stream ENTRY records ────────────────────────────────────────────────────
    results: list[dict] = []
    for path in paths:
        if len(results) >= limit:
            break
        for record in _iter_jsonl(path):
            if record.get("event") != "ENTRY":
                continue
            # Post-filter by instrument / run_id if they came in as constraints
            if instrument and record.get("instrument") != instrument:
                ctx = record.get("_ctx", {})
                if ctx.get("instrument") != instrument:
                    continue
            if run_id:
                ctx = record.get("_ctx", {})
                if ctx.get("run_id") != run_id:
                    continue
            results.append(record)
            if len(results) >= limit:
                break

    # Sort descending by timestamp and cap
    results.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return results[:limit]
