"""
dataset_integrity.py
================================================================================
Layer 2 — whole-dataset SEQUENCE integrity (pre-flight gate).

`ohlcv_schema.py` owns single-ROW correctness (missing columns, NaN, negative
volume, OHLC consistency). This module owns whole-SEQUENCE correctness across an
entire historical file, the checks a streaming row-by-row loader cannot see:

  • path consistency      — file lives under a configured canonical root and its
                            name matches `{symbol}_{timeframe}.csv`
  • duplicate timestamps  — the same bar time must not appear twice
  • timestamp order       — strictly increasing (monotonic)
  • future timestamps     — no bar dated after "now" (+ a 0-minute tolerance)
  • timeframe consistency — the MODAL inter-bar delta must equal the timeframe
                            (mode, not mean — gaps distort the mean)
  • missing candles       — THRESHOLD gate: small gaps are reported (crypto
                            exchanges legitimately go down and the backtest
                            already force-resets on gaps); large corruption
                            (missing > max_missing_pct, a single gap >
                            max_single_gap_candles, or a gap spanning >
                            max_gap_span_minutes) raises DatasetIntegrityError.

`validate_dataset()` is the pre-flight L3 gate the `backtest_v2` entry points run
before `CandleLoader` starts streaming (single-instrument `_preflight_dataset` +
multi-instrument `validate_universe`). It is NOT universal: the other
`CandleLoader.stream()` consumers — the `src/research/` qualification pipeline,
`analytics/sl_tp_comparator`, `governance/portfolio_validation`,
`runtime/exit_model_band`, `runtime/unified_replay_harness`,
`config_layer/config_validator` — stream with only the always-on inline L1/L2
backstop inside `stream()` (no L3 pre-flight). See finding F-039. It writes a
per-file fingerprint report
to `reports/dataset_integrity/{symbol}_{tf}.json` (audit trail + future-L3
substrate) and raises `DatasetIntegrityError` (defined in `ohlcv_schema.py`,
re-exported here) on any HARD violation.

Run report-only over a whole data dir (P0 recon, measure blast radius before
enforcing):
    python -m data_ingestion.dataset_integrity scan data
Validate one file (enforcing):
    python -m data_ingestion.dataset_integrity validate data/BNBUSDT_M15.csv
================================================================================
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional

# Path bootstrap so the module is runnable as `python -m data_ingestion.dataset_integrity`.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _utcnow_naive() -> datetime:
    """Naive UTC 'now' (parsed CSV timestamps are tz-naive, assumed UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from data_ingestion.ohlcv_schema import (
    DatasetIntegrityError,  # re-exported: callers import it from here OR ohlcv_schema
    parse_ohlcv_timestamp,
    require_ohlcv_columns,
    require_unique_ohlcv_headers,
    resolve_ohlcv_headers,
)
from utils.console_safe import safe_print
from utils.logging_config import get_flow_logger

logger = get_flow_logger("DATA_INGESTION")

# Bumped when the meaning of any check changes — recorded in every fingerprint so
# a stored report identifies which validator approved a dataset (replay audit).
VALIDATOR_VERSION = "1.0"
# L3 (cross-file) logic evolves independently from the per-file (L1/L2) validator.
UNIVERSE_VALIDATOR_VERSION = "1.0"

# L1 (row) + L2 (sequence/session) + L3 (cross-file) complete — FROZEN infrastructure.
# No L4. No further validators / anomaly heuristics. Revisit ONLY if a feed or layout
# change invalidates the session-calendar or {symbol}_{tf}.csv naming assumptions.
DATA_VALIDATION_STACK_VERSION = "3.0"

# Timeframe suffix → minutes. Mirrors historical_fetcher._tf_to_seconds.
_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}

_REPORT_DIR = Path("reports") / "dataset_integrity"


class DatasetDecision(Enum):
    """Outcome of a dataset integrity check. Runners consume this rather than
    catching exceptions: APPROVE → run; WARN → run + attach report; REJECT →
    log + skip the instrument (never abort the whole batch)."""
    APPROVE = "APPROVE"
    WARN = "WARN"
    REJECT = "REJECT"


class MarketType(Enum):
    """Trading-calendar class. CRYPTO trades 24x7; WEEKDAY (FX + metals) trades
    the standard Sun-open→Fri-close week. Missing-candle/gap math counts only
    *tradable* slots, so legitimate weekend closes are not flagged as gaps."""
    CRYPTO = "24x7"
    WEEKDAY = "weekday"


def classify_market(symbol: Optional[str], cfg: dict) -> MarketType:
    """Classify by symbol: a stablecoin-quoted pair (…USDT/USDC/BUSD) is 24x7
    crypto; everything else (FX, metals like XAUUSD) follows the weekday session."""
    s = (symbol or "").upper()
    sc = cfg.get("session_calendar", {})
    for suf in sc.get("crypto_quote_suffixes", ["USDT", "USDC", "BUSD"]):
        if s.endswith(suf):
            return MarketType.CRYPTO
    return MarketType.WEEKDAY


def _parse_known_gaps(entries, symbol: Optional[str]) -> list:
    """Parse `session_calendar.known_gaps` entries applicable to `symbol` into (lo, hi) naive-UTC
    datetime ranges. Each entry: {symbol?(omit=all), from, to, reason?}. Malformed entries are
    skipped (never a hard failure — the gate must not crash on a bad accept-list row)."""
    out: list = []
    sym = (symbol or "").upper()
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        esym = (e.get("symbol") or "").upper()
        if esym and sym and esym != sym:
            continue
        try:
            lo = datetime.fromisoformat(str(e["from"]))
            hi = datetime.fromisoformat(str(e["to"]))
        except (KeyError, ValueError, TypeError):
            continue
        # Compare against naive-UTC candle timestamps.
        lo = lo.replace(tzinfo=None)
        hi = hi.replace(tzinfo=None)
        if hi > lo:
            out.append((lo, hi))
    return out


def _is_tradable(dt: datetime, market: MarketType, sc: dict) -> bool:
    """Is `dt` inside a tradable session for `market`? CRYPTO → always. WEEKDAY →
    the FX week: open Sun >= open_hour, all of Mon-Thu, Fri < close_hour, Sat never,
    minus a daily rollover break (e.g. 21:00 UTC) every trading day.

    Irregular closures are modelled by an explicit, reviewed `session_calendar.holidays`
    list (`YYYY-MM-DD` dates) that is non-tradable for ANY market. The default is empty
    (⇒ identical behavior to before this list existed); dates are added only by a reviewed
    decision after the strict gate surfaces a genuine market-closed gap. This keeps the
    zero-tolerance fetch gate from false-stopping on legitimate holiday closures while still
    hard-stopping on real mid-session corruption.

    A reviewed, timestamp-RANGE `sc["_known_gaps"]` accept-list (parsed from
    `session_calendar.known_gaps`) marks specific confirmed broker-outage windows non-tradable for
    ANY mode/market — this is how a genuine intraday micro-gap is accepted without whole-day
    holiday marking (keeps the day's other bars). Empty default ⇒ parity.

    If `sc["_weekly_mask"]` is present (autoderive mode — see session_autoderive), tradability is
    the LEARNED provider mask instead of the hardcoded FX hours; this self-calibrates to any
    broker's real session (no Sunday / no daily break / shifted open) so weekend/overnight closures
    aren't false-flagged. Holidays still apply on top."""
    known_gaps = sc.get("_known_gaps")
    if known_gaps:
        for lo, hi in known_gaps:
            if lo <= dt < hi:
                return False   # reviewed broker-outage window → accepted (non-tradable)
    holidays = sc.get("holidays")
    mask = sc.get("_weekly_mask")
    if mask is not None:
        # Autoderive: tradability is the LEARNED mask + holidays (a provider's crypto CFD may
        # itself close on some holidays — that is captured by the data-derived mask + list).
        from data_ingestion.session_autoderive import is_tradable_by_mask
        return is_tradable_by_mask(dt, mask, holidays)
    if market is MarketType.CRYPTO:
        return True   # 24x7 spot crypto trades through TradFi holidays → holidays do NOT apply
    if holidays and dt.date().isoformat() in holidays:
        return False
    open_h = int(sc.get("weekday_open_hour", 22))
    close_h = int(sc.get("weekday_close_hour", 21))
    break_hours = set(sc.get("weekday_daily_break_hours", [21]))
    wd = dt.weekday()  # Mon=0 … Sun=6
    if wd == 5:                     # Saturday — closed
        return False
    if wd == 6:                     # Sunday — opens in the evening
        return dt.hour >= open_h
    if wd == 4 and dt.hour >= close_h:   # Friday — weekly close
        return False
    return dt.hour not in break_hours    # Mon-Fri minus daily rollover break


def _count_tradable_slots(
    start: datetime, end: datetime, bar_minutes: int, market: MarketType, sc: dict,
    *, exclusive: bool = False,
) -> int:
    """Count grid points (step = bar_minutes) in [start, end] that are tradable.
    `exclusive=True` counts strictly between start and end (for gap interiors)."""
    step = timedelta(minutes=bar_minutes)
    t = start + step if exclusive else start
    stop = end if exclusive else end + step
    count = 0
    while t < stop:
        if _is_tradable(t, market, sc):
            count += 1
        t += step
    return count


# ── Config (lazy, fail-fast on first use) ──────────────────────────────────────
# Loaded lazily rather than at import so that importing this module (e.g. from
# backtest_v2 for the pre-flight wiring) never couples to the config section's
# presence — the fail-fast still fires the first time the gate actually runs.
@lru_cache(maxsize=1)
def _cfg() -> dict:
    from config_layer.production_config import get_prod_section

    cfg = get_prod_section("dataset_integrity")
    if not cfg:
        raise RuntimeError(
            "dataset_integrity section missing from the active production config. "
            "Add it to configs/production/<ACTIVE_VERSION>.json."
        )
    return cfg


def _require(cfg: dict, key: str) -> object:
    if key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from dataset_integrity section. "
            f"Add it to the active production config JSON."
        )
    return cfg[key]


# ── Public report shape ────────────────────────────────────────────────────────
def _empty_report(filepath: str, instrument: Optional[str]) -> dict:
    return {
        "decision":       "APPROVE",
        "severity":       "INFO",
        "filepath":       str(filepath),
        "instrument":     instrument,
        "validator_version": VALIDATOR_VERSION,
        "evaluated_at":   _utcnow_naive().isoformat() + "Z",
        "hard_failures":  [],
        "warnings":       [],
    }


def validate_dataset(
    filepath: str,
    *,
    instrument: Optional[str] = None,
    bar_minutes: Optional[int] = None,
    now: Optional[datetime] = None,
    write_report: bool = True,
    raise_on_fail: bool = True,
    cfg_override: Optional[dict] = None,
) -> dict:
    """
    Pre-flight whole-sequence integrity gate for one historical OHLCV file.

    Streams the file's timestamps in a single O(n) pass (fail-early on the first
    structural violation), then runs modal-delta + gap analysis. Writes a
    fingerprint report and — unless `raise_on_fail=False` (P0 recon mode) —
    raises `DatasetIntegrityError` on any HARD violation.

    `cfg_override` (default None ⇒ byte-identical to the loaded config) shallow-merges over
    the `dataset_integrity` section — used by the STRICT fetch gate to pass the
    zero-tolerance `strict_fetch` thresholds without touching the production defaults the
    backtest path relies on.

    Returns the report dict either way.
    """
    cfg = _cfg()
    if cfg_override:
        cfg = {**cfg, **cfg_override}
    path = Path(filepath)
    now = now or _utcnow_naive()

    report = _empty_report(filepath, instrument)
    hard: list[str] = []      # structural → severity FATAL
    threshold: list[str] = [] # missing-candle threshold breach → severity ERROR
    warnings: list[str] = []

    # ── resolve symbol / timeframe / bar size / market class ───────────────────
    symbol, tf = _parse_symbol_tf(path)
    if bar_minutes is None:
        bar_minutes = _TF_MINUTES.get((tf or "").upper()) or int(
            _require(cfg, "default_bar_minutes")
        )
    sc = cfg.get("session_calendar", {})
    # Normalize the (reviewed) holiday list to a set once → O(1) membership across the
    # whole-grid tradable-slot count (parity: empty list ⇒ empty set ⇒ no behavior change).
    sc = {**sc, "holidays": set(sc.get("holidays", [])),
          "_known_gaps": _parse_known_gaps(sc.get("known_gaps", []), symbol)}
    market = classify_market(symbol, cfg)
    report["timeframe"] = tf
    report["market_type"] = market.value
    report["modal_delta_minutes"] = None

    # ── 1. path consistency ────────────────────────────────────────────────────
    if bool(_require(cfg, "enforce_path_consistency")):
        roots = [str(r) for r in _require(cfg, "canonical_data_roots")]
        pattern = str(_require(cfg, "path_pattern"))
        hard.extend(_check_path_consistency(path, symbol, tf, instrument, roots, pattern))

    # ── 2-4. single streaming pass (dup / order / future) ──────────────────────
    n = 0
    first_ts: Optional[datetime] = None
    last_ts: Optional[datetime] = None
    duplicates = 0
    deltas: list[int] = []
    gap_intervals: list[tuple[datetime, datetime]] = []
    fut_tol = int(_require(cfg, "future_ts_tolerance_minutes"))
    fut_cutoff = now + timedelta(minutes=fut_tol)
    seen: set = set()
    prev: Optional[datetime] = None
    early_break = False
    volumes: list[float] = []
    ranges_pct: list[float] = []
    closes: list[float] = []
    all_ts: list[datetime] = []   # for autoderive weekly-mask (tradability_mode=autoderive)

    try:
        for line_num, ts, o, h, l, c, v in _stream_candles(path):
            n += 1
            if first_ts is None:
                first_ts = ts
            volumes.append(v)
            closes.append(c)
            ranges_pct.append((h - l) / c if c else 0.0)
            all_ts.append(ts)
            if ts in seen:
                duplicates += 1
                hard.append(f"duplicate timestamp {ts.isoformat()} at line {line_num}")
                early_break = True
                break
            if prev is not None and ts < prev:
                hard.append(
                    f"out-of-order timestamp {ts.isoformat()} < {prev.isoformat()} "
                    f"at line {line_num}"
                )
                early_break = True
                break
            if ts > fut_cutoff:
                hard.append(
                    f"future timestamp {ts.isoformat()} > now {now.isoformat()} "
                    f"at line {line_num}"
                )
                early_break = True
                break
            if prev is not None:
                delta = int((ts - prev).total_seconds() // 60)
                deltas.append(delta)
                if delta > bar_minutes:
                    gap_intervals.append((prev, ts))
            seen.add(ts)
            prev = ts
            last_ts = ts
    except (ValueError, OSError) as exc:
        # Unparseable timestamp / header / IO — structural failure.
        hard.append(f"read error: {exc}")
        early_break = True

    report["rows"] = n
    report["first_timestamp"] = first_ts.isoformat() if first_ts else None
    report["last_timestamp"] = last_ts.isoformat() if last_ts else None
    report["duplicates"] = duplicates

    # ── 5. timeframe consistency (modal delta) ─────────────────────────────────
    if deltas and not early_break:
        modal = statistics.mode(deltas)
        report["modal_delta_minutes"] = modal
        if modal != bar_minutes:
            hard.append(
                f"timeframe mismatch: modal inter-bar delta {modal} min "
                f"!= expected {bar_minutes} min ({tf})"
            )

    # ── autoderive: learn the provider's tradable weekly mask from the data itself ─
    if cfg.get("tradability_mode") == "autoderive" and all_ts and not early_break:
        from data_ingestion.session_autoderive import derive_weekly_mask
        mask = derive_weekly_mask(
            all_ts, presence_min=float(cfg.get("autoderive_presence_min", 0.5)))
        sc = {**sc, "_weekly_mask": mask}
        report["tradability_mode"] = "autoderive"
        report["autoderive_mask_slots"] = len(mask)

    # ── 6. missing candles (session-aware THRESHOLD gate) ──────────────────────
    if first_ts and last_ts and not early_break and bar_minutes > 0:
        miss = _analyze_gaps(
            first_ts, last_ts, n, gap_intervals, bar_minutes, market, sc, cfg
        )
        report["missing_pct"] = miss["missing_pct"]
        report["largest_gap_candles"] = miss["largest_gap_candles"]
        report["largest_gap_span_minutes"] = miss["largest_gap_span_minutes"]
        threshold.extend(miss["hard"])
        warnings.extend(miss["warnings"])
    else:
        report["missing_pct"] = 0.0
        report["largest_gap_candles"] = 0
        report["largest_gap_span_minutes"] = 0

    # ── stats baseline (observability only — no check reads these this pass) ───
    report["stats"] = _build_stats(
        volumes, ranges_pct, closes, report.get("modal_delta_minutes")
    )

    # ── decision / severity ────────────────────────────────────────────────────
    all_hard = hard + threshold
    report["hard_failures"] = all_hard
    report["warnings"] = warnings
    if all_hard:
        report["decision"] = DatasetDecision.REJECT.value
    elif warnings:
        report["decision"] = DatasetDecision.WARN.value
    else:
        report["decision"] = DatasetDecision.APPROVE.value
    if hard:
        report["severity"] = "FATAL"
    elif threshold:
        report["severity"] = "ERROR"
    elif warnings:
        report["severity"] = "WARN"
    else:
        report["severity"] = "INFO"

    # ── reproducibility hashes + fingerprint write ─────────────────────────────
    report["file_hash"] = _sha256_file(path)
    report["config_hash"] = _active_config_hash()
    report["schema_hash"] = _schema_hash()
    if write_report and bool(cfg.get("write_fingerprint_report", True)):
        _write_fingerprint(report, symbol, tf)

    if all_hard:
        logger.warning("Dataset integrity REJECT for %s: %s", filepath, "; ".join(all_hard))
        if raise_on_fail:
            raise DatasetIntegrityError(f"{filepath}: " + "; ".join(all_hard))
    elif warnings:
        logger.info("Dataset integrity APPROVE (with warnings) for %s: %s",
                    filepath, "; ".join(warnings))

    return report


# ── Private helpers ────────────────────────────────────────────────────────────
def _parse_symbol_tf(path: Path) -> tuple[Optional[str], Optional[str]]:
    """`BTCUSDT_M15.csv` → ("BTCUSDT", "M15"). Last underscore splits symbol/tf.

    THE single filename parser — L2 and L3 both call this; no other code path may
    re-derive a symbol/timeframe from a filename (per the L3 single-parser rule)."""
    stem = path.stem
    if "_" in stem:
        symbol, tf = stem.rsplit("_", 1)
        return symbol or None, tf or None
    return stem or None, None


def _build_stats(
    volumes: list[float],
    ranges_pct: list[float],
    closes: list[float],
    modal_delta_minutes: Optional[int],
) -> dict:
    """Dataset statistics baseline — recorded in the fingerprint for future
    observability (feed-change / scaling / volatility anomaly detection). NOT a
    check this pass. `mean_spread` is intentionally absent: OHLCV carries no
    bid/ask, so the high-low range is the documented proxy (median_range_pct,
    largest_candle_pct)."""
    def _median(xs: list[float]) -> Optional[float]:
        return round(statistics.median(xs), 8) if xs else None

    return {
        "median_volume":      _median(volumes),
        "zero_volume_pct":    round(sum(1 for v in volumes if v == 0) / len(volumes), 6)
                              if volumes else None,
        "median_range_pct":   _median(ranges_pct),
        "largest_candle_pct": round(max(ranges_pct), 8) if ranges_pct else None,
        "median_close":       _median(closes),
        "min_close":          round(min(closes), 8) if closes else None,
        "max_close":          round(max(closes), 8) if closes else None,
        "modal_delta_minutes": modal_delta_minutes,
    }


def _check_path_consistency(
    path: Path,
    symbol: Optional[str],
    tf: Optional[str],
    instrument: Optional[str],
    roots: list[str],
    pattern: str,
) -> list[str]:
    """File must live under a canonical root, match the filename pattern, and (if
    `instrument` is given) carry a matching symbol. Returns hard-failure strings."""
    failures: list[str] = []
    parts = {p.lower() for p in path.parts}
    if not any(r.lower() in parts for r in roots):
        failures.append(
            f"path outside canonical data roots {roots}: {path} "
            f"(prevents data2/ backup/ final_final/ sprawl)"
        )
    if symbol is None or tf is None:
        failures.append(
            f"filename '{path.name}' does not match pattern '{pattern}' "
            f"({{symbol}}_{{timeframe}}.csv)"
        )
    if instrument and symbol and instrument.upper() != symbol.upper():
        failures.append(
            f"symbol in filename '{symbol}' disagrees with instrument '{instrument}'"
        )
    return failures


def _stream_candles(
    path: Path,
) -> Iterator[tuple[int, datetime, float, float, float, float, float]]:
    """Yield (line, ts, open, high, low, close, volume) for each data row. Resolves
    the timestamp column (single header or split date+time) and the OHLCV columns
    via the shared schema helpers. Raises ValueError on a missing/unparseable
    timestamp or a missing OHLCV column (L1 presence)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            headers = [h.strip() for h in next(reader)]
        except StopIteration:
            return
        require_unique_ohlcv_headers(headers, source=f"Historical dataset {path}")
        lower = [h.lower() for h in headers]
        resolved = resolve_ohlcv_headers(headers)
        ts_name = resolved.get("timestamp")
        ts_idx = lower.index(ts_name.lower()) if ts_name else None
        date_idx = lower.index("date") if "date" in lower else None
        time_idx = lower.index("time") if "time" in lower else None
        use_split = ts_idx is None and date_idx is not None and time_idx is not None
        if ts_idx is None and not use_split:
            # Presence is the schema layer's job; surface a clear message here.
            require_ohlcv_columns(set(resolved), source=f"Historical dataset {path}")
            raise ValueError(f"no timestamp column resolved in {path}")
        require_ohlcv_columns(set(resolved), source=f"Historical dataset {path}")

        def _col(canonical: str) -> int:
            return lower.index(resolved[canonical].lower())

        o_i, h_i, l_i, c_i, v_i = (
            _col("open"), _col("high"), _col("low"), _col("close"), _col("volume")
        )
        for line_num, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            raw = (row[date_idx].strip() + " " + row[time_idx].strip()
                   if use_split else row[ts_idx].strip())
            yield (
                line_num, parse_ohlcv_timestamp(raw),
                float(row[o_i]), float(row[h_i]), float(row[l_i]),
                float(row[c_i]), float(row[v_i]),
            )


def _analyze_gaps(
    first_ts: datetime,
    last_ts: datetime,
    rows: int,
    gap_intervals: list[tuple[datetime, datetime]],
    bar_minutes: int,
    market: MarketType,
    sc: dict,
    cfg: dict,
) -> dict:
    """Session-aware threshold gate over missing candles. Expected candles count
    only TRADABLE grid slots, so legitimate weekend/overnight closes for FX/metals
    are not flagged. Per-gap "missing" and "span" are likewise tradable-only — a
    Fri→Mon weekend gap has ~0 tradable interior. For CRYPTO (24x7) every slot is
    tradable, so this reduces to elapsed-time / timeframe. Small gaps → warnings;
    large corruption → hard failures."""
    expected = _count_tradable_slots(first_ts, last_ts, bar_minutes, market, sc)
    missing = max(expected - rows, 0)
    missing_pct = (missing / expected) if expected > 0 else 0.0

    largest_gap_candles = 0
    largest_gap_span = 0   # tradable minutes missing in the worst single gap
    effective_gaps = 0
    for prev, ts in gap_intervals:
        tradable_missing = _count_tradable_slots(
            prev, ts, bar_minutes, market, sc, exclusive=True
        )
        if tradable_missing > 0:
            effective_gaps += 1
            largest_gap_candles = max(largest_gap_candles, tradable_missing)
            largest_gap_span = max(largest_gap_span, tradable_missing * bar_minutes)

    max_missing_pct = float(_require(cfg, "max_missing_pct"))
    max_single_gap = int(_require(cfg, "max_single_gap_candles"))
    max_gap_span = int(_require(cfg, "max_gap_span_minutes"))

    hard: list[str] = []
    warnings: list[str] = []
    if missing_pct > max_missing_pct:
        hard.append(
            f"missing {missing_pct:.2%} of expected tradable candles "
            f"({missing}/{expected}) exceeds {max_missing_pct:.2%}"
        )
    if largest_gap_candles > max_single_gap:
        hard.append(
            f"single gap of {largest_gap_candles} tradable candles exceeds {max_single_gap}"
        )
    if largest_gap_span > max_gap_span:
        hard.append(
            f"largest tradable gap span {largest_gap_span} min exceeds {max_gap_span} min"
        )
    if not hard and effective_gaps:
        warnings.append(
            f"{effective_gaps} intra-session gap(s); {missing} missing candle(s) "
            f"({missing_pct:.2%}), largest {largest_gap_candles} candle(s) -- "
            f"within thresholds, reported only"
        )
    return {
        "missing_pct": round(missing_pct, 6),
        "largest_gap_candles": largest_gap_candles,
        "largest_gap_span_minutes": largest_gap_span,
        "hard": hard,
        "warnings": warnings,
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return "sha256:" + h.hexdigest()


def _active_config_hash() -> Optional[str]:
    """The params SHA the governance layer already stores for the active config."""
    try:
        from config_layer.production_config import get_prod_metadata

        return get_prod_metadata().get("config_hash")
    except Exception:
        return None


def _schema_hash() -> Optional[str]:
    try:
        from features.feature_schema import SCHEMA_HASH

        return SCHEMA_HASH
    except Exception:
        return None


def _write_fingerprint(report: dict, symbol: Optional[str], tf: Optional[str]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{symbol or 'UNKNOWN'}_{tf or 'NA'}.json"
    out = _REPORT_DIR / name
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)
    except OSError as exc:
        logger.warning("Could not write fingerprint report %s: %s", out, exc)


# ── L3: cross-file (universe) intelligence ──────────────────────────────────────
_DECISION_RANK = {"APPROVE": 0, "WARN": 1, "REJECT": 2}
_RANK_DECISION = {v: k for k, v in _DECISION_RANK.items()}


def _max_decision(a: str, b: str) -> str:
    """Return the more-severe of two decisions (REJECT > WARN > APPROVE)."""
    return _RANK_DECISION[max(_DECISION_RANK.get(a, 0), _DECISION_RANK.get(b, 0))]


def validate_universe(data_dir: str, *, write_report: bool = True) -> dict:
    """Cross-file (L3) intelligence over a data directory. Runs the per-file
    validator (L1/L2) for each CSV, then computes cross-file findings:

      • exact-duplicate SHA-256 groups → HARD REJECT every member (acts on the
        hash FACT only — no winner selection, no filename interpretation). Governed
        by `duplicate_resolution_mode` (only `reject_all` implemented).
      • same-instrument overlapping date ranges → WARN (ambiguous: could be an
        intended shard/extension or an accidental copy — never blocks).

    Returns {"report": <universe dict>, "decisions": {filepath: decision}}. The
    effective per-file decision is the most-severe of its L1/L2 result and any L3
    finding. Never raises (advisory by design, except the exact-dup REJECT)."""
    cfg = _cfg()
    mode = str(cfg.get("duplicate_resolution_mode", "reject_all"))
    if mode != "reject_all":
        logger.warning(
            "duplicate_resolution_mode '%s' not implemented — using 'reject_all'.", mode
        )
        mode = "reject_all"

    files = sorted(Path(data_dir).glob("*.csv"))
    per_file: list[dict] = []
    decisions: dict[str, str] = {}
    by_hash: dict[str, list[str]] = {}
    by_symbol: dict[str, list[tuple[str, Optional[str], Optional[str]]]] = {}

    for fp in files:
        rep = validate_dataset(str(fp), write_report=write_report, raise_on_fail=False)
        symbol, _tf = _parse_symbol_tf(fp)        # single filename parser
        decisions[str(fp)] = rep.get("decision", DatasetDecision.APPROVE.value)
        per_file.append({
            "name": fp.name, "symbol": symbol, "file_hash": rep.get("file_hash"),
            "first_timestamp": rep.get("first_timestamp"),
            "last_timestamp": rep.get("last_timestamp"),
            "rows": rep.get("rows", 0), "decision": rep.get("decision"),
            "stats": rep.get("stats"),
        })
        fh = rep.get("file_hash")
        if fh:
            by_hash.setdefault(fh, []).append(str(fp))
        if symbol:
            by_symbol.setdefault(symbol, []).append(
                (str(fp), rep.get("first_timestamp"), rep.get("last_timestamp"))
            )

    # ── exact-duplicate groups (HARD REJECT all) ───────────────────────────────
    exact_duplicates: list[dict] = []
    warnings: list[str] = []
    for fh, group in by_hash.items():
        if len(group) > 1:
            names = [Path(g).name for g in group]
            exact_duplicates.append({
                "file_hash": fh, "files": names, "severity": "FATAL",
                "resolution": "manual resolution required",
            })
            for g in group:
                decisions[g] = _max_decision(decisions[g], DatasetDecision.REJECT.value)
            msg = f"identical SHA-256 across {names} — REJECT all ({mode})"
            warnings.append(msg)
            logger.error("[universe] %s", msg)

    # ── same-instrument overlapping periods (WARN) ─────────────────────────────
    overlaps: list[dict] = []
    for sym, items in by_symbol.items():
        dated = [(f, datetime.fromisoformat(a), datetime.fromisoformat(b))
                 for f, a, b in items if a and b]
        for i in range(len(dated)):
            for j in range(i + 1, len(dated)):
                f1, a1, b1 = dated[i]
                f2, a2, b2 = dated[j]
                lo, hi = max(a1, a2), min(b1, b2)
                if lo <= hi:
                    overlaps.append({
                        "symbol": sym,
                        "files": [Path(f1).name, Path(f2).name],
                        "overlap_window": [lo.isoformat(), hi.isoformat()],
                        "severity": "WARN",
                    })
                    for f in (f1, f2):
                        decisions[f] = _max_decision(decisions[f], DatasetDecision.WARN.value)
                    warnings.append(
                        f"{sym}: {Path(f1).name} and {Path(f2).name} overlap "
                        f"{lo.isoformat()}..{hi.isoformat()}"
                    )

    vals = list(decisions.values())
    summary = {
        "n_files": len(files),
        "n_approve": sum(1 for v in vals if v == "APPROVE"),
        "n_warn": sum(1 for v in vals if v == "WARN"),
        "n_reject": sum(1 for v in vals if v == "REJECT"),
        "n_duplicate_groups": len(exact_duplicates),
        "n_overlaps": len(overlaps),
    }
    report = {
        "files": per_file,
        "exact_duplicates": exact_duplicates,
        "overlaps": overlaps,
        "warnings": warnings,
        "duplicate_resolution_mode": mode,
        "summary": summary,
        "universe_validator_version": UNIVERSE_VALIDATOR_VERSION,
        "evaluated_at": _utcnow_naive().isoformat() + "Z",
    }
    if write_report:
        _write_universe(report)
    return {"report": report, "decisions": decisions}


def _write_universe(report: dict) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = _REPORT_DIR / "universe.json"
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)
    except OSError as exc:
        logger.warning("Could not write universe report %s: %s", out, exc)


# ── CLI ────────────────────────────────────────────────────────────────────────
def _scan(data_dir: str) -> int:
    """Report-only sweep (P0 recon). Never raises; prints a per-file summary and
    returns the number of files with HARD violations."""
    root = Path(data_dir)
    files = sorted(root.glob("*.csv"))
    if not files:
        print(f"No *.csv files under {root}")
        return 0
    violations = 0
    for fp in files:
        rep = validate_dataset(str(fp), write_report=False, raise_on_fail=False)
        sev = rep["severity"]
        if rep["decision"] == "REJECT":
            violations += 1
        safe_print(f"  [{sev:<5}] {fp.name:<28} {rep['decision']:<8} "
                   f"rows={rep.get('rows', 0)} "
                   f"miss={rep.get('missing_pct', 0):.2%} "
                   + ("| " + "; ".join(rep["hard_failures"]) if rep["hard_failures"] else "")
                   + ("  (warn: " + "; ".join(rep["warnings"]) + ")" if rep["warnings"] else ""))
    safe_print(f"\n{len(files)} file(s) scanned, {violations} with HARD violations.")
    return violations


def _universe_cli(data_dir: str) -> int:
    """Cross-file (L3) report. Prints duplicate/overlap summary; returns the number
    of exact-duplicate groups (→ exit 1 if any)."""
    res = validate_universe(data_dir)
    rep = res["report"]
    s = rep["summary"]
    safe_print(f"  files={s['n_files']} approve={s['n_approve']} warn={s['n_warn']} "
               f"reject={s['n_reject']} dup_groups={s['n_duplicate_groups']} "
               f"overlaps={s['n_overlaps']}")
    for d in rep["exact_duplicates"]:
        safe_print(f"  [FATAL] exact duplicate {d['files']} -- {d['resolution']}")
    for o in rep["overlaps"]:
        safe_print(f"  [WARN ] overlap {o['symbol']} {o['files']} {o['overlap_window']}")
    safe_print(f"\n  universe report -> {_REPORT_DIR / 'universe.json'}")
    return s["n_duplicate_groups"]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: dataset_integrity.py "
              "[scan <data_dir> | validate <file.csv> | universe <data_dir>]")
        sys.exit(2)
    cmd = args[0]
    if cmd == "scan":
        sys.exit(1 if _scan(args[1] if len(args) > 1 else "data") > 0 else 0)
    elif cmd == "validate":
        rep = validate_dataset(args[1], raise_on_fail=False)
        print(json.dumps(rep, indent=2, sort_keys=True))
        sys.exit(1 if rep["decision"] == DatasetDecision.REJECT.value else 0)
    elif cmd == "universe":
        sys.exit(1 if _universe_cli(args[1] if len(args) > 1 else "data") > 0 else 0)
    else:
        print(f"unknown command: {cmd}")
        sys.exit(2)
