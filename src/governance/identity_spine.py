"""
identity_spine.py — the canonical bar-clock bridge + identity hierarchy (Phase 3).

The single authority that turns the four index dialects and four timestamp dialects of this
repo's trace streams into ONE comparable clock: ``bar_open_ts``, feeding the frozen primary key::

    (instrument, timeframe, bar_open_ts, corpus_sha256)

WHY THIS EXISTS
---------------
Every stream in the identity chain names the same bar differently:

    stream                    index alias         timestamp alias
    bar_structure_snapshot    bar_index,          timestamp
                              engine_candle_index
    layer_trace               bar_idx             bar_ts
    crt_telemetry             candle_index        bar_ts (additive, this phase)
    trades.csv (journal)      candle_open         opened_at
    bar_matrix / labeler      _pos                timestamp

Joining on the wrong ``bar_idx``/``timestamp`` pair is the partial-join failure class this module
exists to close. ``normalize_bar_ts`` + ``resolve_bar`` collapse all dialects to the canonical
UTC ``YYYY-MM-DD HH:MM:SS`` string, and the per-run ``bar_identity.jsonl`` (written by
``runtime.bar_clock_bridge``) lets any consumer translate a local index into ``bar_open_ts``.

AUTHORITY
---------
Per CLAUDE.md 6.5 Authority Ladder: this module grants **information**, never economic value,
never production authority. Every value is an identity/join key or a string normalization of an
already-recorded timestamp — no market quantity is computed here. Pure functions + constants;
no I/O on import.
"""
from __future__ import annotations

from typing import Optional

# --------------------------------------------------------------------------- #
# Index dialects: which field each stream uses for the POSITION of the bar in
# its own walk. Precedence order is load-bearing (first-present-alias wins):
# snapshot rows carry BOTH bar_index and engine_candle_index by design.
# --------------------------------------------------------------------------- #
INDEX_ALIASES = (
    "bar_index",            # bar_structure_snapshot (gapless 0..N-1, warmup included)
    "engine_candle_index",  # bar_structure_snapshot (engine-owned counter)
    "bar_idx",              # layer_trace
    "candle_index",         # crt_telemetry (CANDIDATE_LIFECYCLE / DECISION_DISTANCE)
    "candle_open",          # trades.csv (TradeRecord.candle_open)
    "_pos",                 # bar_matrix / labeler raw-corpus position
)

#: The four timestamp dialects -> the canonical field. Precedence is load-bearing.
BAR_TS_ALIASES = (
    "timestamp",        # snapshot / telemetry RETEST_REPLAY / bar_matrix / labeler
    "bar_ts",           # layer_trace / telemetry (additive this phase)
    "opened_at",        # trades.csv (TradeRecord.opened_at)
    "first_seen_ts",    # telemetry CANDIDATE_LIFECYCLE (candidate birth)
)

#: The frozen primary-key fields every identity record must be resolvable to.
FROZEN_PK_FIELDS = ("instrument", "timeframe", "bar_open_ts", "corpus_sha256")

#: Canonical UTC string representation for bar-identity comparison.
BAR_TS_FORMAT = "%Y-%m-%d %H:%M:%S"

# --------------------------------------------------------------------------- #
# id-mint authority table: every durable identifier in the chain, who mints it,
# and at what moment. RECORDED, never collapsed — "JOIN, do not re-mint".
# --------------------------------------------------------------------------- #
ID_MINTS = (
    {
        "id": "run_id",
        "minted_by": "runtime.backtest_v2.BacktestRunner",
        "when": "once per run, UTC, before ReportWriter exists",
        "form": "run_YYYYMMDD_HHMMSS",
        "scope": "one backtest run",
    },
    {
        "id": "trade_id",
        "minted_by": "config_layer.crt_engine_v2.Trade (executor.build_trade)",
        "when": "at TRADE_OPENED, inside the engine",
        "form": "CRT-{seq:04d}",
        "scope": "the engine's trade row — stays the journal/CSV trade_id (Option A)",
    },
    {
        "id": "execution_intent_id",
        "minted_by": "journal.trade_identity_v1_0.mint_trade_id via TradeIdentityV1.new",
        "when": "at TRADE_OPENED, inside the runner (derived from trade_id)",
        "form": "uuid4().hex (32 hex chars, embeds nothing)",
        "scope": "the execution-intent identity — derived 1:1 from the engine trade_id",
    },
    {
        "id": "candidate_id",
        "minted_by": "config_layer.crt_engine_v2",
        "when": "at sweep/expansion detection (one candidate lifecycle at a time)",
        "form": "CAND-{candle_index}",
        "scope": "one candidate lifecycle — joins telemetry to trades.csv",
    },
    {
        "id": "layer_trace run_id",
        "minted_by": "runtime.layer_trace.LayerTraceEmitter",
        "when": "one per emitter instance (per run)",
        "form": "run_... (minted locally, recorded on run_manifest.json)",
        "scope": "LayerProof rows — recorded, never collapsed",
    },
)

# --------------------------------------------------------------------------- #
# Allowed vs illegal joins. The illegal terms are the *semantic key drift* the
# chain closes: never join two streams on a raw index unless one of them is
# resolved through the bridge (bar_identity.jsonl), and never join on position.
# --------------------------------------------------------------------------- #
ALLOW_JOIN_BAR_OPEN_TS = "ALLOW_JOIN_BAR_OPEN_TS"   # join only on the frozen PK clock
DENY_RAW_INDEX = "DENY_RAW_INDEX"                   # index-in-both-directions bypasses clock
DENY_POSITION_JOIN = "DENY_POSITION_JOIN"           # position-to-position cross-stream join

#: (left_stream, left_key, right_stream, right_key, verdict, reason) — the join table.
JOIN_TABLE = (
    ("snapshot", "bar_index", "layer_trace", "bar_idx", DENY_RAW_INDEX,
     "different warmup/offset semantics — resolve through bridge"),
    ("snapshot", "engine_candle_index", "layer_trace", "bar_idx", DENY_RAW_INDEX,
     "domain-specific counters — resolve through bridge"),
    ("telemetry", "candle_index", "trades.csv", "candle_open", DENY_RAW_INDEX,
     "engine candles vs loop candles (warmup differs) — resolve through bridge"),
    ("bar_matrix", "_pos", "trades.csv", "candle_open", DENY_POSITION_JOIN,
     "position-to-position joins are the labeler<->journal drift — resolve through timestamp"),
    ("ANY", "bar_open_ts", "ANY", "bar_open_ts", ALLOW_JOIN_BAR_OPEN_TS,
     "the canonical clock join (also requires the rest of the frozen PK to agree)"),
)


def normalize_bar_ts(value) -> str:
    """Canonicalize ANY timestamp dialect to UTC ``YYYY-MM-DD HH:MM:SS`` (str).

    Accepts ``datetime``, ISO-8601 strings, plain ``YYYY-MM-DD HH:MM:SS`` strings and numeric
    epoch seconds. Comparisons and joins ALWAYS use the returned string, so two dialects differ
    only in representation, never in meaning.
    """
    from datetime import datetime as _dt

    if value is None:
        raise ValueError("normalize_bar_ts: None is not a bar timestamp")
    if isinstance(value, (int, float)):
        from datetime import timezone as _tz
        return _dt.fromtimestamp(float(value), tz=_tz.utc).strftime(BAR_TS_FORMAT)
    if isinstance(value, _dt):
        if value.tzinfo is not None:
            return value.astimezone(_dt.now().astimezone().tzinfo).strftime(BAR_TS_FORMAT)
        return value.strftime(BAR_TS_FORMAT)
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1]
        try:
            if "+" in s:
                aware = _dt.fromisoformat(s)
                if aware.tzinfo is not None:
                    return aware.astimezone(_dt.now().astimezone().tzinfo).strftime(BAR_TS_FORMAT)
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return _dt.strptime(s, fmt).strftime(BAR_TS_FORMAT)
                except ValueError:
                    continue
        except ValueError:
            pass
        raise ValueError(
            f"normalize_bar_ts: cannot parse {value!r} (expected datetime, ISO-8601, "
            f"'YYYY-MM-DD HH:MM:SS' or epoch seconds)"
        )
    iso = getattr(value, "isoformat", None)      # numpy/pandas Timestamp fallback
    if iso is not None:
        return normalize_bar_ts(iso())
    raise ValueError(f"normalize_bar_ts: unsupported type {type(value).__name__}")


def resolve_bar(
    rec: dict,
    *,
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    corpus_sha256: Optional[str] = None,
) -> Optional[tuple]:
    """Resolve one trace dict to its frozen-PK key ``(instrument, timeframe, bar_open_ts, corpus_sha256)``.

    First-present-alias for both the index and the timestamp field. Returns ``None`` for records
    without a recognizable timestamp (e.g. run-scoped layer rows with bar_ts=None) — such a row
    is NOT a bar and must never join on one. Raises ``ValueError`` when a timestamp IS present
    but unparseable (fail-loud: a record that LOOKS like a bar must be a real bar).
    """
    ts_field = next(
        (k for k in BAR_TS_ALIASES if rec.get(k) is not None and str(rec.get(k)).strip() != ""),
        None,
    )
    if ts_field is None:
        return None
    bar_ts = normalize_bar_ts(rec[ts_field])
    return (
        str(rec.get("instrument") or instrument or ""),
        str(rec.get("timeframe") or timeframe or "M15"),
        bar_ts,
        str(rec.get("corpus_sha256") or corpus_sha256 or ""),
    )


def index_field(rec: dict) -> Optional[str]:
    """Which index dialect this record speaks (first-present alias), or None."""
    return next((k for k in INDEX_ALIASES if rec.get(k) is not None), None)


def is_frozen_pk_complete(pk: Optional[tuple]) -> bool:
    """A frozen PK is complete only when every component is non-empty."""
    return bool(pk) and all(str(v).strip() != "" for v in pk)


def stamp_telemetry_envelope(
    records: list[dict],
    *,
    run_id: str,
    instrument: str,
    timeframe: str = "M15",
    corpus_sha256: str = "",
) -> list[dict]:
    """Return the records with the uniform identity envelope stamped on each (invariant I1).

    The runner writes ONLY these stamped records to crt_telemetry.jsonl, so every telemetry
    record — CANDIDATE_LIFECYCLE, DECISION_DISTANCE, RETEST_REPLAY, integrity events — carries
    the frozen-PK components (instrument/timeframe/corpus_sha256) plus the canonical run_id,
    making the file self-joining without reaching back into the runner.
    """
    return [
        dict(
            r,
            run_id=run_id,
            instrument=instrument,
            timeframe=timeframe,
            corpus_sha256=corpus_sha256,
        )
        for r in records
    ]