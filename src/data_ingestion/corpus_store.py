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

# 2.0 (CH-corpus-clock-contract-v1): cached timestamps are canonical UTC (1.0 caches held the
# SOURCE clock) - a 1.0 manifest is STALE by version, never served.
MANIFEST_VERSION = "2.0"
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
    if manifest.get("manifest_version") != MANIFEST_VERSION:
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
    # Clock contract: the cache serves CANONICAL UTC, normalized once from the file's declared
    # (configured) clock - the parsed stamps above are SOURCE-clock wall times.
    import pandas as _pd
    from data_ingestion.clock_contract import to_utc_series as _to_utc
    from data_ingestion.clock_registry import resolve_clock as _resolve_clock
    _resolved = _resolve_clock(admitted)
    if not _resolved.clock.is_identity:
        rows["timestamp"] = [t.to_pydatetime() for t in
                             _to_utc(_pd.Series(_pd.to_datetime(rows["timestamp"])), _resolved.clock)]

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
        "timestamp_clock": "UTC",
        "clock_id": _resolved.clock.clock_id,
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
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise CorpusStoreError(
            f"corpus cache {ppath} has manifest_version {manifest.get('manifest_version')!r} != "
            f"{MANIFEST_VERSION!r}: it holds SOURCE-clock timestamps; rebuild it with build().")
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


# ─────────────────────────────────────────────────────────────────────────────────────────────
# CORPUS SSOT — the single authoritative in-memory corpus for an execution
# (CH-corpus-ssot, 2026-10-08).
#
# One admitted corpus, read ONCE: `load()` admits the requested path (dataset identity via
# `dataset_registry.admit_csv_path`, optional sequence validation via `corpus_gate.admit_corpus`),
# reads the admitted file's bytes into memory a single time, hashes THOSE bytes, checks them
# against the bound record (sha256, rows, time range), and returns an immutable `AdmittedCorpus`.
# Every consumer parses that same object (`records()`, `frame()`, `text`) — no consumer reopens
# the CSV, and every artifact takes `dataset_id` / `sha256` from the object, so the identity a
# run reports is by construction the identity of the exact bytes it consumed.
#
# Process cache: the same admitted file (same size + mtime) returns the SAME object, so all
# consumers inside one execution share one corpus.
#
# ONE SSOT, MANY IDENTIFIED CORPORA: the SSOT owns every corpus that can be identified — each
# registered dataset (dataset_id from docs/governance/dataset_identity_registry.json) and any
# other existing file (content-addressed identity `sha256:<hex>`, bound=False). An execution
# SELECTS one corpus and every consumer of that execution shares the same object.
#
# No silent substitution: the registry's legacy rule rewrites ANY `XAUUSD_M15*` request to the
# Phase-1 corpus. The SSOT honours that only for a missing file, the same file, or a path the
# record DECLARES as an alias (`forensic_paths`). Any other existing file (e.g. a newer fetch
# XAUUSD_M15_<range>.csv) resolves to ITS OWN identity — never to the older corpus.
# ─────────────────────────────────────────────────────────────────────────────────────────────

import csv as _csv
import io as _io
from functools import cached_property as _cached_property

from data_ingestion.clock_contract import (
    CANONICAL_TIMEZONE, CLOCK_STATE_CANONICAL, CLOCK_STATE_SOURCE, ClockDef,
    DoubleNormalizationError, normalize_view,
)
from data_ingestion.ohlcv_schema import ClockProvenanceError, OHLCV_TIMESTAMP_SINGLE_ALIASES


def _timestamp_column(columns: list) -> str:
    """The single timestamp column of a corpus header (fail-closed on split date/time files)."""
    low = {str(c).strip().lower(): c for c in columns}
    for alias in OHLCV_TIMESTAMP_SINGLE_ALIASES:
        if alias in low:
            return low[alias]
    raise CorpusStoreError(
        f"corpus has no single timestamp column (looked for {OHLCV_TIMESTAMP_SINGLE_ALIASES}); "
        f"split date+time files cannot be normalized to UTC by the clock contract")


@dataclass(frozen=True, eq=False)
class AdmittedCorpus:
    """The authoritative corpus of one execution: identity + the exact bytes consumed."""

    dataset_id: Optional[str]
    bound: bool
    sha256: str
    path: str               # admitted physical file the bytes came from
    requested_path: str     # what the caller asked for
    rewritten: bool         # registry resolved the request to a different (declared) path
    instrument: str
    timeframe: str
    n_rows: int
    start: str              # first timestamp cell, as written in the file
    end: str                # last timestamp cell, as written in the file
    sequence_checked: bool  # True when corpus_gate.admit_corpus validated sequence/integrity
    data: bytes = field(repr=False)   # the SOURCE bytes exactly as read (identity = sha256 of these)
    admission_decision: str = "IDENTITY_ONLY"   # corpus_gate decision (APPROVE/WARN) when sequence-checked
    # CH-corpus-clock-contract-v1: the configured clock this corpus's SOURCE timestamps are on.
    # `start`/`end` above are canonical UTC (what consumers receive); `source_start`/`source_end`
    # are the cells as written in the file (what the file and its registry records say).
    clock: Optional[ClockDef] = None
    clock_origin: str = ""           # registry | in_process | inherited_parent
    source_start: str = ""
    source_end: str = ""

    @property
    def identity(self) -> str:
        """The corpus identity an artifact records: the registered dataset_id, else the
        content address `sha256:<hex>` (an identified, unregistered corpus)."""
        return self.dataset_id or f"sha256:{self.sha256}"

    #: every view this object hands out (text / records / frame) is on this clock
    clock_state = CLOCK_STATE_CANONICAL

    @_cached_property
    def canonical_data(self) -> bytes:
        """The corpus as consumers see it: `timestamp` = canonical UTC, `source_timestamp` = the
        cell as written in the file (audit / broker-time comparison only). Built ONCE from the
        source bytes by the one normalizer (`clock_contract.normalize_view`).

        The rebuild is LINE-PRESERVING: blank lines, malformed rows and unparseable timestamp
        cells pass through untouched, so every integrity defect the source has is still visible
        to the downstream readers' own fail-closed checks (a pandas round-trip would silently
        drop a mid-file blank line or normalize away a short row)."""
        import pandas as pd

        if self.clock is None:
            raise ClockProvenanceError(
                f"{self.path}: corpus was admitted without a clock; refusing to expose timestamps")
        text = self.data.decode("utf-8-sig").replace("\r\n", "\n")
        lines = text.split("\n")
        hdr_i = next((i for i, ln in enumerate(lines) if ln.strip()), None)
        if hdr_i is None:
            raise CorpusStoreError(f"{self.path}: corpus has no header")

        def _fields(ln: str) -> list:
            return next(_csv.reader([ln]))

        def _join(fs: list) -> str:
            if any('"' in f or "," in f for f in fs):
                buf = _io.StringIO()
                _csv.writer(buf, lineterminator="").writerow(fs)
                return buf.getvalue()
            return ",".join(fs)

        header = _fields(lines[hdr_i])
        tcol = _timestamp_column(header)
        tidx = header.index(tcol)
        rows: list = []          # (line index, fields) for well-shaped data rows
        for i in range(hdr_i + 1, len(lines)):
            if not lines[i].strip():
                continue
            fs = _fields(lines[i])
            if len(fs) == len(header):
                rows.append((i, fs))
        out_lines = list(lines)
        out_lines[hdr_i] = _join(header + ["source_timestamp"])
        cells = pd.Series([fs[tidx] for _, fs in rows], dtype=str)
        if self.clock.is_identity or cells.empty:
            canon = list(cells)                   # identity clock: values unchanged, never re-parsed
        else:
            parsed = pd.to_datetime(cells.str.strip(), errors="coerce")
            good = parsed.notna()
            conv = normalize_view(CLOCK_STATE_SOURCE, self.clock, parsed[good]).dt.strftime("%Y-%m-%d %H:%M:%S")
            canon_s = cells.copy()
            canon_s[good] = conv                  # unparseable cells stay as written -> downstream raises
            canon = list(canon_s)
        for (i, fs), c in zip(rows, canon):
            out_lines[i] = _join(fs[:tidx] + [c] + fs[tidx + 1:] + [fs[tidx]])
        return "\n".join(out_lines).encode("utf-8")

    @_cached_property
    def text(self) -> str:
        return self.canonical_data.decode("utf-8")

    @_cached_property
    def source_text(self) -> str:
        """The file exactly as written (SOURCE clock). Audit / integrity-on-the-artifact only."""
        return self.data.decode("utf-8-sig")

    @_cached_property
    def _records(self) -> tuple:
        return tuple(_csv.DictReader(_io.StringIO(self.text, newline="")))

    def records(self) -> list:
        """Rows as csv.DictReader dicts (string cells). `timestamp` is canonical UTC;
        `source_timestamp` is the cell as written in the file."""
        return list(self._records)

    def frame(self, **read_csv_kwargs):
        """A fresh pandas DataFrame parsed from the canonical bytes (kwargs -> pd.read_csv).
        Carries `attrs`: timestamp_clock='UTC', clock_id, corpus identity."""
        import pandas as pd

        df = pd.read_csv(_io.BytesIO(self.canonical_data), **read_csv_kwargs)
        df.attrs["timestamp_clock"] = CANONICAL_TIMEZONE
        df.attrs["clock_id"] = self.clock.clock_id if self.clock else None
        df.attrs["corpus_identity"] = self.identity
        df.attrs["instrument"] = self.instrument
        return df

    def to_source_rows(self, df):
        """Re-express a (possibly filtered) canonical frame in SOURCE representation: the
        `timestamp` column becomes the original cells and `source_timestamp` is dropped. This is
        how a derived window is written so its bytes stay a true sub-range of the parent
        (lineage, contract §13). Refuses frames that are not this corpus's canonical frame."""
        if df.attrs.get("timestamp_clock") != CANONICAL_TIMEZONE or "source_timestamp" not in df.columns:
            raise DoubleNormalizationError(
                "to_source_rows expects a canonical frame produced by AdmittedCorpus.frame()")
        tcol = _timestamp_column([c for c in df.columns if c != "source_timestamp"])
        out = df.drop(columns=[tcol]).rename(columns={"source_timestamp": tcol})
        cols = [tcol] + [c for c in out.columns if c != tcol]
        return out[cols]

    def normalize_source_frame(self, df):
        """The once-only guard, made reachable: a frame that is already canonical UTC cannot be
        pushed through source-clock normalization again."""
        if df.attrs.get("timestamp_clock") == CANONICAL_TIMEZONE:
            raise DoubleNormalizationError(
                "frame is already canonical UTC; it cannot be normalized from the source clock again")
        tcol = _timestamp_column(list(df.columns))
        import pandas as pd

        out = df.copy()
        out[tcol] = normalize_view(CLOCK_STATE_SOURCE, self.clock, pd.to_datetime(out[tcol]))
        out.attrs["timestamp_clock"] = CANONICAL_TIMEZONE
        return out

    @property
    def calendar(self):
        """The market calendar for this corpus's INSTRUMENT (not its broker): day/week/HTF grid."""
        from features.market_calendar import calendar_for_instrument
        return calendar_for_instrument(self.instrument)

    def provenance(self) -> dict:
        """The identity block every artifact derived from this corpus should carry."""
        return {
            "corpus_identity": self.identity,
            "dataset_id": self.dataset_id,
            "corpus_sha256": self.sha256,
            "corpus_path": Path(self.path).as_posix(),
            "requested_path": Path(self.requested_path).as_posix(),
            "rewritten": self.rewritten,
            "bound": self.bound,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "n_rows": self.n_rows,
            "start": self.start,
            "end": self.end,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "timestamp_clock": CANONICAL_TIMEZONE,
            "clock": ({**self.clock.describe(), "origin": self.clock_origin}
                      if self.clock else None),
            "sequence_checked": self.sequence_checked,
            "admission_decision": self.admission_decision,
            "authority": "data_ingestion.corpus_store.load",
        }


_SSOT_CACHE: dict = {}


def _norm_ts(s: str) -> str:
    return s.strip().replace("T", " ")


def _declared_aliases(dataset_id: str) -> set:
    from data_ingestion.dataset_registry import _REPO_ROOT, load_bound_datasets

    rec = load_bound_datasets(repo_root=_REPO_ROOT).get(dataset_id) or {}
    return {str((_REPO_ROOT / p).resolve()) for p in (rec.get("forensic_paths") or [])}


def _bound_record(dataset_id: str) -> dict:
    from data_ingestion.dataset_registry import _REPO_ROOT, load_bound_datasets

    return load_bound_datasets(repo_root=_REPO_ROOT).get(dataset_id) or {}


def load(
    path: "str | Path",
    instrument: str = "",
    timeframe: str = "M15",
    *,
    sequence_check: bool = True,
    plausibility: bool = False,
) -> AdmittedCorpus:
    """Return THE authoritative corpus for `path` (see the block comment above).

    sequence_check=True runs corpus_gate.admit_corpus (identity + sequence/integrity, REJECT
    raises); False admits identity only (dataset_registry.admit_csv_path), the level the
    backtest CandleLoader has always used — its run-level preflight does the sequence check.
    """
    from data_ingestion.dataset_registry import admit_csv_path

    requested = str(path)
    if not instrument:
        # No caller hint: take the symbol from the filename (`{SYMBOL}_{TF}...csv`). An empty
        # instrument makes the registry judge every file against the XAUUSD record (it would
        # treat EURUSD_M15.csv as a native-HTF forensic request).
        instrument = Path(requested).stem.split("_")[0].upper()
    try:
        adm = admit_csv_path(requested, instrument)
    except Phase1CandidateError as exc:
        raise DatasetAdmissionError(str(exc)) from exc
    admitted = Path(adm.filepath)
    req = Path(requested)
    dataset_id, bound, rewritten = adm.dataset_id, adm.bound, bool(adm.rewritten)
    own_identity = (
        rewritten and req.exists() and req.resolve() != admitted.resolve()
        and (adm.dataset_id is None or str(req.resolve()) not in _declared_aliases(adm.dataset_id))
    )
    if own_identity:
        # An existing, different, undeclared file is its OWN corpus — not the rewrite target.
        logger.warning("corpus SSOT: %s is its own corpus (not rewritten to %s)", requested, admitted)
        admitted, dataset_id, bound, rewritten = req, None, False, False
    elif rewritten:
        logger.warning("corpus SSOT: %s resolved to declared %s (%s)", requested, admitted, dataset_id)

    from dataclasses import replace as _replace

    def _view(c: AdmittedCorpus) -> AdmittedCorpus:
        """Same bytes/identity; per-request fields reflect THIS request."""
        if c.requested_path == requested and c.rewritten == rewritten:
            return c
        return _replace(c, requested_path=requested, rewritten=rewritten)

    st = admitted.stat()
    key = (str(admitted.resolve()), st.st_size, st.st_mtime_ns)
    hit = _SSOT_CACHE.get(key)
    if hit is not None and (hit.sequence_checked or not sequence_check) and not plausibility:
        return _view(hit)

    decision = "IDENTITY_ONLY"
    if sequence_check or plausibility:
        if own_identity:
            # admit_corpus would follow the legacy rewrite; validate THIS file's own contract.
            from data_ingestion.dataset_integrity import validate_dataset
            from data_ingestion.ohlcv_schema import DatasetIntegrityError

            rep = validate_dataset(str(admitted), instrument=instrument or None,
                                   raise_on_fail=False, write_report=False)
            decision = rep.get("decision", "UNKNOWN")
            if decision == "REJECT":
                raise DatasetIntegrityError(
                    f"{admitted}: own-identity corpus REJECTED by validate_dataset: "
                    f"{rep.get('hard_failures')}"
                )
        else:
            decision = admit_corpus(
                requested, instrument, write_report=False, check_plausibility=plausibility
            ).decision
        sequence_check = True
        if hit is not None:   # same bytes already in memory: only the check level is upgraded
            if not hit.sequence_checked:
                hit = _replace(hit, sequence_checked=True, admission_decision=decision)
                _SSOT_CACHE[key] = hit
            return _view(hit)

    data = admitted.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise CorpusStoreError(f"admitted corpus is empty: {admitted}")
    header = [h.strip().strip('"').lower() for h in lines[0].split(",")]
    ts_col = header.index("timestamp") if "timestamp" in header else 0
    n_rows = len(lines) - 1
    start = lines[1].split(",")[ts_col].strip() if n_rows else ""
    end = lines[-1].split(",")[ts_col].strip() if n_rows else ""

    if bound and dataset_id:
        art = _bound_record(dataset_id).get("canonical_artifact") or {}
        if art.get("sha256") and art["sha256"] != sha:
            raise CorpusStoreError(
                f"{dataset_id}: bytes read hash {sha[:16]}.. != registered {art['sha256'][:16]}.."
            )
        if art.get("rows") is not None and int(art["rows"]) != n_rows:
            raise CorpusStoreError(f"{dataset_id}: {n_rows} rows read != registered {art['rows']}")
        for k, v in (("start", start), ("end", end)):
            if art.get(k) and _norm_ts(art[k]) != _norm_ts(v):
                raise CorpusStoreError(f"{dataset_id}: {k} {v!r} != registered {art[k]!r}")

    # CH-corpus-clock-contract-v1: a corpus without an explicit, configured clock identity cannot
    # enter the research system. The registry record (and, for a bound dataset, the dataset
    # record) must name the same provider/broker/clock_id as the configured clock.
    from data_ingestion.clock_registry import resolve_clock
    from data_ingestion.clock_contract import to_utc_scalar
    from data_ingestion.ohlcv_schema import parse_ohlcv_timestamp

    resolved = resolve_clock(admitted, dataset=_bound_record(dataset_id) if (bound and dataset_id) else None)

    def _utc_cell(cell: str) -> str:
        if not cell or resolved.clock.is_identity:
            return cell
        return to_utc_scalar(parse_ohlcv_timestamp(cell), resolved.clock).strftime("%Y-%m-%d %H:%M:%S")

    corpus = AdmittedCorpus(
        dataset_id=dataset_id, bound=bound, sha256=sha, path=str(admitted),
        requested_path=requested, rewritten=rewritten,
        instrument=instrument or (dataset_id or ""), timeframe=timeframe,
        n_rows=n_rows, start=_utc_cell(start), end=_utc_cell(end),
        sequence_checked=sequence_check, data=data,
        admission_decision=decision,
        clock=resolved.clock, clock_origin=resolved.origin,
        source_start=start, source_end=end,
    )
    _SSOT_CACHE[key] = corpus
    return corpus


def corpus_sha256(path: "str | Path", instrument: str = "") -> str:
    """sha256 of the authoritative corpus for `path` (SSOT; never a separate file read)."""
    return load(path, instrument, sequence_check=False).sha256
