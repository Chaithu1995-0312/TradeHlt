"""corpus_store.py — Parquet READ-CACHE over an admitted OHLCV corpus.

RESOLUTION (2026-09-09, user-directed): `docs/governance/CORPUS_AUTHORITY.md` is FROZEN
v1.0.0 and its frozen sentence is unambiguous — "one admitted artifact, projections are
functions" — and further: "A stored derived CSV, if ever written, is a cache whose hash is
checked against a rebuild. Never a second admitted corpus." This module IS that cache,
generalized from CSV-derivative to a typed Parquet sidecar. The admitted CSV (resolved
through `corpus_gate.admit_corpus`) stays the sole L0 identity anchor. This module trusts
no other bytes: the Parquet payload is disposable and rebuildable from the CSV at any time,
and every read re-verifies the cache against the CSV's sha256 before serving a single candle.
No new identity family, no doctrine edit, no CLOSED contract touched.

Sibling of `utils.parquet_store` — same FRESH/STALE/ABSENT/UNAVAILABLE freshness contract,
same size+mtime+sha256 manifest shape, same optional-pyarrow-import guard — generalized from
sparse/heterogeneous JSONL to a fixed 6-column OHLCV table. It does not reuse that module's
columnar flatten/type-inference machinery, because OHLCV needs none of it.

Why the CSV is parsed via `dataset_integrity._stream_candles`, not a fresh `pd.read_csv`:
that is the SAME parser `validate_dataset` (called inside `admit_corpus`) already streamed
the file through to validate it. A second, independently-coded parse could silently diverge
(different date-format fallback order, different NaN handling) from the bytes that were just
approved — reusing it means the Parquet payload is provably what was validated, not a
re-interpretation of it.

Public API
----------
build(instrument, timeframe="M15", *, csv_path=None) -> BuildResult
    The ONLY legitimate corpus CSV read in this module (and the only one this program
    condones outside `admit_corpus` itself). Admits the CSV, writes the Parquet sidecar +
    manifest keyed by the ADMITTED file's sha256.

read(instrument, timeframe="M15", *, start=None, end=None, warmup_bars=0, strict=True)
        -> CorpusRead
    Never touches the CSV's row bytes. Re-verifies the cache's manifest against the CSV's
    current fingerprint first (`strict=True` re-hashes; STALE raises, it never silently
    falls back to serving old Parquet data). Returns `Candle` objects
    (`config_layer.crt_engine_v2.Candle`, the type both `backtest_v2.py` and the research
    trace scripts already use) with `index` re-stamped 0-based over the returned slice.

Deliberate non-goals: this module does not decide WHICH corpus is canonical (that is
`dataset_registry`/`xauusd_phase1_candidate`), does not implement HTF projections (that is
`features.parent_candle.ParentCandleBuilder`, per `CORPUS_AUTHORITY.md` section 3 — do not
reimplement resampling here), and grants no economic or production authority (CLAUDE.md 6.5).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from data_ingestion.corpus_gate import admit_corpus
from data_ingestion.dataset_integrity import _stream_candles
from data_ingestion.dataset_registry import DatasetAdmissionError
from data_ingestion.xauusd_phase1_candidate import Phase1CandidateError

logger = logging.getLogger("CRT.CorpusStore")

try:  # optional-import guard (conventions.md 3.2), same shape as utils.parquet_store
    import pyarrow as pa
    import pyarrow.parquet as pq

    _PARQUET_AVAILABLE = True
    _PARQUET_IMPORT_ERROR: Optional[Exception] = None
except Exception as _exc:  # noqa: BLE001 - absence is a supported state, not an error
    pa = None  # type: ignore[assignment]
    pq = None  # type: ignore[assignment]
    _PARQUET_AVAILABLE = False
    _PARQUET_IMPORT_ERROR = _exc

MANIFEST_VERSION = "1.0"
_HASH_CHUNK = 4 << 20

# Freshness states — same vocabulary as utils.parquet_store, applied to this store's own
# sidecar naming (kept as a distinct module rather than importing those constants, since
# this module's ABSENT/STALE conditions are checked against different fields — this store's
# manifest keys on the ADMITTED path, which may differ from the requested path).
FRESH = "FRESH"
STALE = "STALE"
ABSENT = "ABSENT"
UNAVAILABLE = "UNAVAILABLE"

_STORE_COLUMNS = ("symbol", "timestamp", "open", "high", "low", "close", "volume")


class CorpusStoreError(RuntimeError):
    """Fail-closed: cache absent, stale, unavailable, or the requested window is
    outside the admitted corpus's range. Never silently degrades to stale data."""


@dataclass(frozen=True)
class BuildResult:
    instrument: str
    timeframe: str
    parquet_path: str
    manifest_path: str
    rows: int
    csv_path: str
    csv_sha256: str
    dataset_id: Optional[str]
    admission_decision: str


@dataclass(frozen=True)
class CorpusRead:
    """Everything a caller needs to consume a window AND to attribute what it read —
    the provenance pair (`csv_sha256`, `dataset_id`) is what a run manifest should record,
    per the same discipline `corpus_gate.CorpusAdmission` states for the CSV path."""

    candles: list  # list[config_layer.crt_engine_v2.Candle]
    in_window: list  # list[bool], same length as candles
    window_start_idx: int
    lead_in_bars: int
    tail_bars: int  # bars actually served after the window end (<= requested tail_bars)
    requested: tuple  # (start, end) as given, or (None, None)
    resolved: tuple  # (first candle ts, last candle ts) actually returned
    instrument: str
    timeframe: str
    csv_path: str
    csv_sha256: str
    dataset_id: Optional[str]
    parquet_path: str


def parquet_available() -> bool:
    return _PARQUET_AVAILABLE


def _default_csv_path(instrument: str, timeframe: str) -> str:
    return f"data/mt5/{instrument}_{timeframe}.csv"


def _parquet_path(csv_path: Path) -> Path:
    return csv_path.with_suffix(".parquet")


def _manifest_path(csv_path: Path) -> Path:
    return Path(str(_parquet_path(csv_path)) + ".manifest.json")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(_HASH_CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _fingerprint(path: Path, *, with_hash: bool) -> dict:
    st = path.stat()
    fp = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
    if with_hash:
        fp["sha256"] = _sha256_file(path)
    return fp


def status(instrument: str, timeframe: str = "M15", *, csv_path: Optional[str] = None,
           strict: bool = False) -> str:
    """FRESH / STALE / ABSENT / UNAVAILABLE, without building or reading anything."""
    if not _PARQUET_AVAILABLE:
        return UNAVAILABLE
    csv = Path(csv_path or _default_csv_path(instrument, timeframe))
    ppath, mpath = _parquet_path(csv), _manifest_path(csv)
    if not csv.exists() or not ppath.exists() or not mpath.exists():
        return ABSENT
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return STALE
    recorded = manifest.get("source", {})
    current = _fingerprint(csv, with_hash=strict)
    if recorded.get("size") != current["size"] or recorded.get("mtime_ns") != current["mtime_ns"]:
        return STALE
    if strict and recorded.get("sha256") != current.get("sha256"):
        return STALE
    return FRESH


def build(
    instrument: str,
    timeframe: str = "M15",
    *,
    csv_path: Optional[str] = None,
    log: Optional[logging.Logger] = None,
) -> BuildResult:
    """Admit the CSV, stream it through the SAME parser `validate_dataset` used, and
    write the Parquet cache + manifest. The one legitimate CSV read in this module."""
    log = log or logger
    if not _PARQUET_AVAILABLE:
        raise CorpusStoreError(
            f"pyarrow required to build a corpus Parquet cache: {_PARQUET_IMPORT_ERROR}. "
            "Install it with `pip install tradelatest[parquet]`."
        )
    requested = csv_path or _default_csv_path(instrument, timeframe)
    try:
        admission = admit_corpus(requested, instrument, write_report=False)
    except (DatasetAdmissionError, Phase1CandidateError) as exc:
        raise CorpusStoreError(f"corpus admission failed (R3 fail-closed): {exc}") from exc

    admitted = Path(admission.filepath)
    symbol_col = admission.dataset_id or instrument.upper()

    rows: dict[str, list] = {c: [] for c in _STORE_COLUMNS}
    for _line_num, ts, o, h, l, c, v in _stream_candles(admitted):
        rows["symbol"].append(symbol_col)
        rows["timestamp"].append(ts)
        rows["open"].append(o)
        rows["high"].append(h)
        rows["low"].append(l)
        rows["close"].append(c)
        rows["volume"].append(v)
    n = len(rows["timestamp"])
    if n == 0:
        raise CorpusStoreError(f"{admitted}: zero rows parsed — refusing to write an empty cache")

    table = pa.table({
        "symbol": pa.array(rows["symbol"], type=pa.string()),
        "timestamp": pa.array(rows["timestamp"], type=pa.timestamp("us")),
        "open": pa.array(rows["open"], type=pa.float64()),
        "high": pa.array(rows["high"], type=pa.float64()),
        "low": pa.array(rows["low"], type=pa.float64()),
        "close": pa.array(rows["close"], type=pa.float64()),
        "volume": pa.array(rows["volume"], type=pa.float64()),
    })

    ppath, mpath = _parquet_path(admitted), _manifest_path(admitted)
    ppath.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, ppath)

    # `_fingerprint(..., with_hash=True)` computes the freshness-check sha256 with THIS
    # module's own `_sha256_file` (bare hex digest). `admission.file_hash` is a SEPARATE
    # value from `dataset_integrity._sha256_file`, which prefixes "sha256:" — a different
    # string format for the same bytes. Comparing across the two formats on a later `read()`
    # would report a spurious STALE on every build, so the freshness field always uses this
    # module's own hash; the admission's hash is recorded only as separate provenance.
    source_fp = _fingerprint(admitted, with_hash=True)
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "symbol": symbol_col,
        "rows": n,
        "source": {
            "path": str(admitted),
            **source_fp,  # size, mtime_ns, sha256 (bare hex) — the freshness-check triple
        },
        "admission_file_hash": admission.file_hash,  # provenance only, DIFFERENT format
        "dataset_id": admission.dataset_id,
        "bound": admission.bound,
        "rewritten": admission.rewritten,
        "requested_path": requested,
        "admission_decision": admission.decision,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    mpath.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    log.info(
        "[corpus_store] built %s (%d rows) from %s -> %s",
        symbol_col, n, admitted, ppath,
    )
    return BuildResult(
        instrument=instrument.upper(), timeframe=timeframe,
        parquet_path=str(ppath), manifest_path=str(mpath), rows=n,
        csv_path=str(admitted), csv_sha256=source_fp["sha256"],
        dataset_id=admission.dataset_id, admission_decision=admission.decision,
    )


def ensure_fresh(
    instrument: str,
    timeframe: str = "M15",
    *,
    csv_path: Optional[str] = None,
    strict: bool = True,
    log: Optional[logging.Logger] = None,
) -> str:
    """`build()` only if the cache is not already FRESH; returns the resulting `status()`
    value (always FRESH on success — never returns having left the cache STALE/ABSENT).

    Convenience for the common "read this corpus, building the cache the first time" call
    site shape — every caller doing this by hand as `if status(...) != FRESH: build(...)`
    is the same four lines repeated; this is that, named once. Never silently masks a build
    failure: `build()`'s own exceptions propagate unchanged.
    """
    log = log or logger
    current = status(instrument, timeframe, csv_path=csv_path, strict=strict)
    if current == FRESH:
        return FRESH
    log.info("[corpus_store] cache %s for %s %s -- building", current, instrument, timeframe)
    build(instrument, timeframe, csv_path=csv_path, log=log)
    rebuilt = status(instrument, timeframe, csv_path=csv_path, strict=strict)
    if rebuilt != FRESH:
        raise CorpusStoreError(
            f"ensure_fresh({instrument}, {timeframe}): status is {rebuilt!r} immediately "
            "after build() — build() should always leave the cache FRESH; this indicates a "
            "bug in build()/status(), not a transient condition to retry."
        )
    return rebuilt


def read(
    instrument: str,
    timeframe: str = "M15",
    *,
    csv_path: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    warmup_bars: int = 0,
    tail_bars: int = 0,
    strict: bool = True,
) -> CorpusRead:
    """Serve candles from the Parquet cache. Fails closed on ABSENT/STALE/UNAVAILABLE —
    never silently rebuilds and never silently serves data that no longer matches the
    admitted CSV's fingerprint. Caller decides when to call `build()` again.

    `warmup_bars`/`tail_bars` extend the returned slice OUTWARD from [start, end) so a
    consumer that needs history before the window (e.g. a rolling detect window) or future
    bars after it (e.g. a forward-walk) doesn't get a value silently truncated or empty right
    at the boundary. Lead-in/tail candles are included in `candles` but flagged `False` in
    `in_window`; the window itself failing to contain even one bar is always an error,
    independent of how much lead-in/tail is available."""
    if not _PARQUET_AVAILABLE:
        raise CorpusStoreError(
            f"pyarrow required to read a corpus Parquet cache: {_PARQUET_IMPORT_ERROR}"
        )
    from config_layer.crt_engine_v2 import Candle  # local import: avoid a hard top-level
                                                     # dependency on the CRT engine package
                                                     # for a module that only builds/reads data

    csv = Path(csv_path or _default_csv_path(instrument, timeframe))
    ppath, mpath = _parquet_path(csv), _manifest_path(csv)
    if not mpath.exists() or not ppath.exists():
        raise CorpusStoreError(
            f"no Parquet cache for {instrument} {timeframe} — call corpus_store.build() first "
            f"(expected {ppath})"
        )
    if not csv.exists():
        raise CorpusStoreError(f"admitted source CSV missing: {csv} — cache cannot be trusted")

    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    recorded = manifest.get("source", {})
    current = _fingerprint(csv, with_hash=strict)
    if recorded.get("size") != current["size"] or recorded.get("mtime_ns") != current["mtime_ns"]:
        raise CorpusStoreError(
            f"STALE: {csv} changed size/mtime since the cache was built — "
            "run corpus_store.build() again before reading"
        )
    if strict and recorded.get("sha256") != current.get("sha256"):
        raise CorpusStoreError(
            f"STALE: {csv} content hash no longer matches the cache manifest "
            f"(recorded {recorded.get('sha256')!r} != current {current.get('sha256')!r}) — "
            "run corpus_store.build() again before reading"
        )

    table = pq.read_table(ppath)
    ts_col = table.column("timestamp").to_pylist()
    o_col = table.column("open").to_pylist()
    h_col = table.column("high").to_pylist()
    l_col = table.column("low").to_pylist()
    c_col = table.column("close").to_pylist()
    v_col = table.column("volume").to_pylist()
    n = len(ts_col)

    # `first_in_window` = index of the first bar with ts >= start (or 0 if start is None).
    # `hi_window` = index one past the last bar with ts <= end (or n if end is None) — the
    # boundary of the WINDOW ITSELF, before any tail extension. `lo`/`hi` then step OUTWARD
    # from [first_in_window, hi_window) by warmup_bars/tail_bars for lead-in/tail buffers.
    # `window_start_idx` (relative to `lo`) is exactly how many lead-in bars actually made
    # it in, which is what a caller needs to know `warmup_complete` truthfully rather than
    # assuming the full buffer was available.
    first_in_window = 0 if start is None else next(
        (i for i, t in enumerate(ts_col) if t >= start), n
    )
    hi_window = n if end is None else next((i for i, t in enumerate(ts_col) if t > end), n)
    # The window itself must be non-empty regardless of how much lead-in/tail is available —
    # checking `lo >= hi` (the outward-stepped bounds) would let an EMPTY window through
    # silently whenever a tail buffer happens to reach past it. This checks the window's own
    # boundary, not the buffered one.
    if first_in_window >= hi_window:
        raise CorpusStoreError(
            f"requested window [{start}, {end}] yields zero bars in {instrument} {timeframe} "
            f"(cache spans {ts_col[0] if n else None} .. {ts_col[-1] if n else None})"
        )
    lo = max(0, first_in_window - warmup_bars)
    hi = min(n, hi_window + tail_bars)
    window_start_idx = first_in_window - lo

    if start is not None and window_start_idx < warmup_bars and lo == 0:
        logger.warning(
            "[corpus_store] requested warmup_bars=%d but only %d bars available before "
            "the window start (corpus boundary) — proceeding with the short lead-in, "
            "never silently padding it",
            warmup_bars, window_start_idx,
        )
    tail_available = hi - hi_window
    if end is not None and tail_available < tail_bars and hi == n:
        logger.warning(
            "[corpus_store] requested tail_bars=%d but only %d bars available after "
            "the window end (corpus boundary) — proceeding with the short tail, "
            "never silently padding it",
            tail_bars, tail_available,
        )

    candles = []
    in_window = []
    for idx, i in enumerate(range(lo, hi)):
        candles.append(Candle(
            timestamp=ts_col[i], open=o_col[i], high=h_col[i], low=l_col[i],
            close=c_col[i], volume=v_col[i], index=idx,
        ))
        ts = ts_col[i]
        in_window.append((start is None or ts >= start) and (end is None or ts <= end))

    return CorpusRead(
        candles=candles,
        in_window=in_window,
        window_start_idx=window_start_idx,
        lead_in_bars=window_start_idx,
        tail_bars=tail_available,
        requested=(start, end),
        resolved=(candles[0].timestamp if candles else None,
                  candles[-1].timestamp if candles else None),
        instrument=instrument.upper(),
        timeframe=timeframe,
        csv_path=str(csv),
        csv_sha256=recorded.get("sha256", ""),
        dataset_id=manifest.get("dataset_id"),
        parquet_path=str(ppath),
    )
