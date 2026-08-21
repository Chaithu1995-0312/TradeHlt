"""
ohlcv_schema.py
================================================================================
Single source of truth for the historical-data column contract.

Every historical OHLCV ingestion path (DataFrame loaders, CSV/row loaders, live
intake, strategy plugins) must enforce this contract BEFORE any feature
computation or backtesting. There are no defaults, no auto-generation, no column
substitution, and no zero/one-fill for the six mandatory fields. A dataset that
is missing a column — or that carries NaN/non-numeric/negative/inconsistent
values in the six fields — is a schema violation and must fail fast.

Three enforcement phases:
  1. PRESENCE   — `require_ohlcv_columns(columns)`  (the six columns must exist).
  2. INTEGRITY  — `validate_ohlcv_frame(df)` / `validate_ohlcv_row(...)`
                  (no NaN/non-numeric, volume >= 0, candle high/low consistent).
  3. PROVENANCE — `require_reviewed_clock(path)`    (the corpus's timezone must be DECLARED and
                  human-REVIEWED). Phases 1-2 validate the numbers; phase 3 validates what the
                  timestamps MEAN. `mt5_candle_fetcher.py:186` labels MT5 broker-server time as
                  UTC, so a file's own claim about its clock is not evidence (F-066). Fail-closed:
                  no record, a stale SHA, or `user_reviewed:false` raises `ClockProvenanceError`.
                  Phase 3 applies to FILE-BACKED reads only — an in-memory/synthetic frame has no
                  corpus to review, and the loader that produced it is itself gated.

Header aliasing (e.g. ``Open`` -> ``open``, ``tick_volume`` -> ``volume``) is the
caller's responsibility and is permitted normalization — it maps an existing
column to its canonical name. What is forbidden is inventing a column that has no
source, or sourcing ``timestamp`` from the row index. The timestamp-from-index ban
is enforced structurally: every loader resolves a real timestamp header (or a
split date+time pair) and then calls ``require_ohlcv_columns(resolved, ...)``,
which raises if no timestamp header is present — so a loader can never silently
fall back to the row index (see ``CandleLoader.stream`` in ``runtime/backtest_v2.py``).
================================================================================
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Iterable, Optional


# Sequence/dataset-integrity violations (duplicate/out-of-order/future timestamps,
# corrupt gaps). Defined here — the single source of truth for the data contract —
# and re-exported by ``data_ingestion.dataset_integrity`` so the streaming loader
# (which already imports from this module) can raise it without an import cycle.
class DatasetIntegrityError(ValueError):
    """Raised when a dataset violates whole-sequence integrity rules."""


class FeatureAlignmentError(DatasetIntegrityError):
    """Raised when the candle stream and the feature-vector frame cannot be aligned.

    Two distinct failures, both previously SILENT (T-16, 2026-07-23):

    1. **Configured warmup shorter than the pipeline's** — `FeaturePipeline.finalize()` drops
       `required_warmup_rows()` leading rows, so any candle before that index has no feature row.
       `backtest.warmup_candles` used to be an unrelated literal, leaving a window of bars that ran
       through the CRT state machine with nothing behind them.
    2. **A timestamp lookup miss** — `backtest_v2` used to substitute `[0.0] * len(CANONICAL_FEATURES)`
       and log at most three warnings, so a mid-file NaN drop or a timestamp-format break produced a
       confidently-scored ZERO vector instead of an error.

    Subclasses `DatasetIntegrityError` so existing `except DatasetIntegrityError` handlers on the
    loader paths keep catching it — the alignment failure is a data-contract failure.
    """


class ClockProvenanceError(DatasetIntegrityError):
    """Raised when a corpus is read without a human-reviewed timezone declaration (Phase 3).

    A corpus whose clock is undeclared is a data-contract failure in exactly the same sense as a
    missing column: the six mandatory fields say WHAT the numbers are, the clock record says WHAT
    THE TIMESTAMPS MEAN. `mt5_candle_fetcher.py:186` labels MT5 broker-server time as UTC, so
    "the file says UTC" is not evidence (F-066) — only a reviewed record is.

    Subclasses `DatasetIntegrityError` so existing loader handlers keep catching it.
    """


# The six mandatory historical-data columns. Load-bearing — do not re-declare
# this set anywhere else; import it from here.
REQUIRED_OHLCV_COLUMNS = frozenset(
    {"timestamp", "open", "high", "low", "close", "volume"}
)

# Numeric price fields (timestamp/volume validated separately).
_OHLC = ("open", "high", "low", "close")
_REQUIRED_ORDER = ("timestamp", "open", "high", "low", "close", "volume")

# Permitted header synonyms per canonical field. Aliasing maps an EXISTING
# column to its canonical name (e.g. ``tick_volume`` -> ``volume``); it never
# invents a missing column. Split date+time timestamps are handled by callers.
OHLCV_HEADER_ALIASES = {
    "timestamp": ("timestamp", "datetime", "date time", "open time", "time", "date"),
    "open":      ("open", "o"),
    "high":      ("high", "h"),
    "low":       ("low", "l"),
    "close":     ("close", "c", "adj close"),
    "volume":    ("volume", "vol", "tickvol", "tick volume", "tick_volume"),
}

# ── SSOT column-INDEX resolution for streaming loaders (B1, 2026-07-24) ─────────────────────────
# `OHLCV_HEADER_ALIASES` above folds `date`/`time` INTO `timestamp` — correct for the frame-level
# `resolve_ohlcv_headers` (which only needs A timestamp source), but it CANNOT express a SPLIT
# date+time pair that must be COMBINED. `CandleLoader` historically kept its own private alias
# table to model that split, which drifted (it was missing `tick_volume`). These two constants +
# `resolve_ohlcv_column_indices` are the single authority the streaming loader now delegates to, so
# the split capability lives here (first-class) and no second table can drift again.
#
# SINGLE timestamp column aliases — deliberately EXCLUDE bare `date`/`time`, which are the split
# pair below. A file with only a `time` column and no date is not a valid single timestamp here.
OHLCV_TIMESTAMP_SINGLE_ALIASES = ("timestamp", "datetime", "date time", "open time")
# SPLIT date+time pair — two columns concatenated into one timestamp string ("<date> <time>").
OHLCV_TIMESTAMP_SPLIT_ALIASES = {"date": ("date",), "time": ("time",)}


def resolve_ohlcv_column_indices(
    fieldnames: Iterable[str], *, source: str = "Historical dataset"
) -> dict:
    """SSOT column-index resolver for row-streaming OHLCV loaders (B1).

    Returns a dict of canonical field -> 0-based column index:
        {'open': i, 'high': i, 'low': i, 'close': i, 'volume': i, **ts}
    where ``ts`` is EITHER ``{'timestamp': i}`` (a single timestamp column) OR
    ``{'date': i, 'time': i}`` (a split pair the caller must concatenate).

    Enforces the same two contracts the loader used to enforce piecemeal:
      * no duplicate headers (``require_unique_ohlcv_headers``);
      * all six mandatory columns present, a split date+time pair satisfying "timestamp"
        (``require_ohlcv_columns``).
    Raises ``ValueError`` on either violation — the streaming loader converts nothing to a
    silent skip. Header matching is case-insensitive after strip, via the shared alias tables,
    so ``tick_volume`` / ``Open`` / ``TickVol`` all resolve without a second table to maintain.
    """
    headers = [str(h).strip() for h in fieldnames]
    require_unique_ohlcv_headers(headers, source=source)
    lower_to_idx = {h.lower(): idx for idx, h in enumerate(headers)}

    def _find(aliases: Iterable[str]) -> Optional[int]:
        for alias in aliases:
            if alias in lower_to_idx:
                return lower_to_idx[alias]
        return None

    out: dict = {}
    for field in ("open", "high", "low", "close", "volume"):
        idx = _find(OHLCV_HEADER_ALIASES[field])
        if idx is not None:
            out[field] = idx

    # Timestamp: a single column wins; otherwise a split date+time pair (both required).
    ts_single = _find(OHLCV_TIMESTAMP_SINGLE_ALIASES)
    if ts_single is not None:
        out["timestamp"] = ts_single
    else:
        d_idx = _find(OHLCV_TIMESTAMP_SPLIT_ALIASES["date"])
        t_idx = _find(OHLCV_TIMESTAMP_SPLIT_ALIASES["time"])
        if d_idx is not None and t_idx is not None:
            out["date"] = d_idx
            out["time"] = t_idx

    resolved = set(out)
    if "date" in out and "time" in out:
        resolved.add("timestamp")   # the split pair satisfies the mandatory timestamp column
    require_ohlcv_columns(resolved, source=source)
    return out


# Canonical timestamp parse formats — the single source of truth shared by every
# OHLCV loader (CSV streaming loader, dataset-integrity pre-flight gate). Do not
# re-declare this list elsewhere; import it from here.
OHLCV_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M",
    "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
)


def parse_ohlcv_timestamp(raw: str) -> datetime:
    """Parse a raw timestamp string against the canonical formats. Raises
    ValueError if none match (an invalid/unparseable timestamp is a schema
    violation — e.g. ``32-15-2025``)."""
    for fmt in OHLCV_DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: '{raw}'")


# ── Phase 3: clock provenance (file-backed reads) ──────────────────────────────
def require_reviewed_clock(path, *, basis: Optional[str] = None):
    """Phase-3 gate — raise `ClockProvenanceError` unless `path` has a reviewed clock record.

    Thin façade over ``data_ingestion.clock_registry`` so every ingestion path can reach all three
    enforcement phases through this one module. The import is function-local because
    ``clock_registry`` imports ``ClockProvenanceError`` from here — a module-level import would
    make that a cycle.

    `basis` — pass the active ``feature_pipeline.session_timestamp_basis`` when the caller resolves
    one, to also run the double-conversion guard.
    """
    from data_ingestion.clock_registry import require_reviewed_clock as _gate
    return _gate(path, basis=basis)


def require_unique_ohlcv_headers(
    fieldnames: Iterable[str], *, source: str = "Historical dataset"
) -> None:
    """Raise ValueError if any header (case-insensitive, after strip) appears
    more than once — e.g. ``timestamp open high low close volume volume``. A
    duplicate column silently shadows the real one under set-based presence
    checks, so it must fail fast."""
    counts = Counter(str(h).strip().lower() for h in fieldnames)
    dupes = sorted(h for h, n in counts.items() if h and n > 1)
    if dupes:
        raise ValueError(
            f"{source} has duplicate column headers: " + ", ".join(dupes)
        )


def resolve_ohlcv_headers(fieldnames: Iterable[str]) -> dict:
    """
    Map each canonical OHLCV field to the actual header present in `fieldnames`
    (case-insensitive, known synonyms allowed). Returns only the fields that
    resolve; the caller enforces presence via
    ``require_ohlcv_columns(resolved.keys())``.
    """
    fieldnames = list(fieldnames)
    require_unique_ohlcv_headers(fieldnames)
    lower_to_actual = {str(h).strip().lower(): h for h in fieldnames}
    resolved: dict = {}
    for canonical, aliases in OHLCV_HEADER_ALIASES.items():
        for alias in aliases:
            if alias in lower_to_actual:
                resolved[canonical] = lower_to_actual[alias]
                break
    return resolved


# ── Phase 1: presence ─────────────────────────────────────────────────────────
def require_ohlcv_columns(
    columns: Iterable[str], *, source: str = "Historical dataset"
) -> None:
    """Raise ValueError if any of the six mandatory columns is absent."""
    missing = REQUIRED_OHLCV_COLUMNS - set(columns)
    if missing:
        raise ValueError(
            f"{source} missing required columns: " + ", ".join(sorted(missing))
        )


# ── Phase 2: value integrity (DataFrame path) ──────────────────────────────────
def validate_ohlcv_frame(df, *, source: str = "Historical dataset") -> None:
    """
    Full value-integrity gate for a DataFrame. Assumes the six columns have
    already been numerically coerced by the caller (``pd.to_numeric(...,
    errors="coerce")``) so that any unparseable cell surfaces as NaN and is
    caught here rather than silently masked.
    """
    require_ohlcv_columns(df.columns, source=source)

    cols = list(_REQUIRED_ORDER)
    if df[cols].isnull().any().any():
        raise ValueError(
            f"{source} contains NaN/empty values in required OHLCV columns"
        )
    if (df["volume"] < 0).any():
        raise ValueError(f"{source} contains negative volume")

    hi, lo, op, cl = df["high"], df["low"], df["open"], df["close"]
    inconsistent = (
        (hi < lo) | (hi < op) | (hi < cl) | (lo > op) | (lo > cl)
    )
    if inconsistent.any():
        raise ValueError(
            f"{source} contains inconsistent candles (high/low vs open/close)"
        )


# ── Phase 2: value integrity (single-row path) ─────────────────────────────────
def validate_ohlcv_row(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    *,
    source: str = "Historical dataset",
    line: Optional[int] = None,
) -> None:
    """
    Value-integrity gate for one already-parsed candle (streaming/CSV loaders).
    Mirrors `validate_ohlcv_frame` for the numeric fields. `timestamp` is
    validated at parse time by the loader (it must exist and be parseable).
    """
    where = f" (line {line})" if line is not None else ""
    for name, val in (("open", open_), ("high", high), ("low", low), ("close", close), ("volume", volume)):
        if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
            raise ValueError(
                f"{source} contains NaN/empty value in required column '{name}'{where}"
            )
    if volume < 0:
        raise ValueError(f"{source} contains negative volume{where}")
    if high < low or high < open_ or high < close or low > open_ or low > close:
        raise ValueError(
            f"{source} contains inconsistent candle (high/low vs open/close){where}"
        )
