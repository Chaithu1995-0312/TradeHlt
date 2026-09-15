"""chart_api.py — read-only payload builder for the dashboard's Trade Chart tab.

Pure orchestration: every decision lives in the already-governed libraries this module
composes (`charts.chart_series`, `charts.crt_overlay`, `charts.resolver_overlay`,
`data_ingestion.dataset_integrity`, `control_plane.dashboard_api._resolve_run`). No new
authority is created here — CLAUDE.md §6.5: descriptive/UI only, no economic claim, no G001.

Every failure mode fails CLOSED and VISIBLY (the F-079/F-083/F-085 silent-gap class): a
missing run, an unbound corpus, a corpus/run mismatch, or a missing resolver cache all
return an explicit status string next to the data rather than an empty/successful-looking
payload.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from charts import chart_series as cs
from charts import crt_overlay as co

log = logging.getLogger("charts.chart_api")

# `control_plane.dashboard_api` is imported LAZILY (inside `chart_payload`, not here), same
# discipline `crt_overlay.py` uses for `config_layer.production_config` / `runtime.backtest_v2`:
# `src/control_plane/__init__.py` eagerly imports `server`, and `server` imports THIS module
# at top level -- a module-level import here would close a circular-import loop
# (control_plane -> server -> chart_api -> control_plane) the moment this module loads.

MAX_LIMIT = 5000
DEFAULT_LIMIT = 1500

# One corpus resident per (path, mtime, size) — a 47k-row XAUUSD load is not cheap enough
# to repeat per request. Bounded: dashboards touch a handful of instruments in a session.
_CANDLE_CACHE: dict[tuple, list] = {}
_INTEGRITY_CACHE: dict[tuple, dict] = {}
_CACHE_MAX_ENTRIES = 8

_STATE_EVENT_KINDS = ("SWEEP", "DISPLACEMENT", "RETEST", "EXECUTION", "RESET")


def _corpus_path(instrument: str) -> Path:
    return Path("data") / "mt5" / f"{instrument}_M15.csv"


def _cache_key(path: Path) -> Optional[tuple]:
    try:
        st = path.stat()
    except OSError:
        return None
    return (str(path), st.st_mtime_ns, st.st_size)


def _load_base_cached(path: Path, instrument: str) -> tuple[list, Optional[str]]:
    """Load the base M15 corpus once per (path, mtime, size). Returns (bars, error)."""
    key = _cache_key(path)
    if key is None:
        return [], f"corpus not found: {path}"
    if key in _CANDLE_CACHE:
        return _CANDLE_CACHE[key], None
    try:
        bars = cs.load_base_candles(path, instrument)
    except Exception as exc:                                       # noqa: BLE001
        return [], f"corpus load failed ({type(exc).__name__}: {exc})"
    if len(_CANDLE_CACHE) >= _CACHE_MAX_ENTRIES:
        _CANDLE_CACHE.pop(next(iter(_CANDLE_CACHE)))
    _CANDLE_CACHE[key] = bars
    return bars, None


def _integrity_cached(path: Path, instrument: str) -> dict:
    key = _cache_key(path)
    if key is None:
        return {"decision": "REJECT", "hard_failures": [f"corpus not found: {path}"],
                "warnings": [], "missing_pct": None}
    if key in _INTEGRITY_CACHE:
        return _INTEGRITY_CACHE[key]
    try:
        from data_ingestion.dataset_integrity import validate_dataset
        report = validate_dataset(
            str(path), instrument=instrument, write_report=False, raise_on_fail=False,
        )
    except Exception as exc:                                       # noqa: BLE001
        report = {"decision": "WARN", "hard_failures": [],
                  "warnings": [f"integrity check failed to run ({type(exc).__name__}: {exc})"],
                  "missing_pct": None}
    if len(_INTEGRITY_CACHE) >= _CACHE_MAX_ENTRIES:
        _INTEGRITY_CACHE.pop(next(iter(_INTEGRITY_CACHE)))
    _INTEGRITY_CACHE[key] = report
    return report


def _find_gap_bands(bars: list, bar_minutes: float = 15.0, factor: float = 2.5) -> list[dict]:
    """Consecutive-bar gaps wider than `factor`x the base cadence — a description for the
    chart to shade, not a re-implementation of the dataset_integrity gap classifier (which
    reports counts/pct, not windows)."""
    out: list[dict] = []
    if len(bars) < 2:
        return out
    threshold = bar_minutes * factor * 60.0
    for i in range(1, len(bars)):
        delta = (bars[i].timestamp - bars[i - 1].timestamp).total_seconds()
        if delta > threshold:
            out.append({
                "from": bars[i - 1].timestamp.isoformat(),
                "to": bars[i].timestamp.isoformat(),
                "span_minutes": round(delta / 60.0, 1),
            })
    return out


def _parse_iso(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _read_trades(trades_path: Path, instrument: str,
                  start: Optional[datetime], end: Optional[datetime]) -> list[dict]:
    if not trades_path.exists():
        return []
    out: list[dict] = []
    with open(trades_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            opened = _parse_iso(row.get("opened_at"))
            if opened is None:
                continue
            if start is not None and opened < start:
                continue
            if end is not None and opened > end:
                continue
            out.append({
                "trade_id":    row.get("trade_id"),
                "direction":   row.get("direction"),
                "opened_at":   row.get("opened_at"),
                "closed_at":   row.get("closed_at"),
                "entry_fill":  _safe_float(row.get("entry_fill")),
                "sl":          _safe_float(row.get("sl")),
                "tp1":         _safe_float(row.get("tp1")),
                "tp2":         _safe_float(row.get("tp2")),
                "exit_fill":   _safe_float(row.get("exit_fill")),
                "exit_reason": row.get("exit_reason"),
                "pnl_rr_net":  _safe_float(row.get("pnl_rr_net")),
            })
    return out


def _safe_float(v: Any) -> Optional[float]:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _read_event_pins(events_path: Path,
                      start: Optional[datetime], end: Optional[datetime]) -> list[dict]:
    if not events_path.exists():
        return []
    out: list[dict] = []
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or not any(k in line for k in _STATE_EVENT_KINDS):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") not in _STATE_EVENT_KINDS:
                continue
            ts = _parse_iso(rec.get("timestamp"))
            if ts is None:
                continue
            if start is not None and ts < start:
                continue
            if end is not None and ts > end:
                continue
            out.append({
                "event":     rec.get("event"),
                "timestamp": rec.get("timestamp"),
                "direction": rec.get("direction"),
                "price":     rec.get("price"),
                "reason":    rec.get("reason"),
            })
    return out


RESOLVER_UNAVAILABLE_FALLBACK = "UNAVAILABLE"


def _resolver_states_full(instrument: str, corpus_sha: Optional[str],
                           base_ts: list) -> tuple[list[str], str, int]:
    """Per-base-bar resolver states (aligned to `base_ts`) plus source + transition count.

    Serves a precomputed cache ONLY if it matches this exact corpus sha256 — never computed
    in-request (a multi-minute FeaturePipeline + resolver pass). Degrades to an all-
    UNAVAILABLE track on any miss, matching `charts.crt_overlay`'s discipline.
    """
    try:
        from charts.resolver_overlay import load_cached_track
    except Exception as exc:                                       # noqa: BLE001
        return ([RESOLVER_UNAVAILABLE_FALLBACK] * len(base_ts),
                f"UNAVAILABLE:resolver_overlay import failed ({exc})", 0)

    result = load_cached_track(instrument, corpus_sha, base_ts)
    return (result.states, result.source, result.transitions)


def chart_payload(
    instrument: str,
    run_id: Optional[str],
    timeframe: str = "M15",
    limit: int = DEFAULT_LIMIT,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> dict:
    instrument = (instrument or "").upper()
    timeframe = (timeframe or "M15").upper()
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))

    if timeframe not in cs.TIMEFRAMES:
        return {"ok": False, "instrument": instrument, "run_id": run_id,
                "error": f"unsupported timeframe {timeframe!r} (expected {list(cs.TIMEFRAMES)})"}

    from control_plane import dashboard_api as dash
    run = dash._resolve_run(instrument, run_id)
    if run is None:
        return {"ok": False, "instrument": instrument, "run_id": run_id,
                "error": "no backtest run found for this instrument/run_id"}

    corpus_path = _corpus_path(instrument)
    integrity = _integrity_cached(corpus_path, instrument)

    base_bars, load_err = _load_base_cached(corpus_path, instrument)
    if load_err:
        return {"ok": False, "instrument": instrument, "run_id": run.run_id,
                "error": load_err, "integrity": integrity}

    base_ts = [c.timestamp for c in base_bars]
    # G4 (2026-09-10): pull THIS run's own recorded config provenance from its
    # summary.json so the legend can't imply the CURRENT active config governs states
    # an archived run actually produced under a different one.
    run_summary = dash._read_json(run.summary_path) if run.summary_path.exists() else {}
    config_pin = cs.build_config_pin(
        instrument, corpus_path,
        run_config_version=run_summary.get("config_version"),
        run_htf_clock_basis=run_summary.get("htf_clock_basis"),
        run_htf_candles_per_range=run_summary.get("htf_candles_per_range"),
    )
    corpus_sha = config_pin.get("corpus_sha256")

    start_dt = _parse_iso(start)
    end_dt = _parse_iso(end)

    # Engine (spine) CRT track from THIS run's own events.jsonl — never a fresh spine run.
    engine_track = co.track_from_events(run.events_path, base_ts, run.run_id) \
        if run.events_path.exists() else co.unavailable("no events.jsonl for this run", len(base_ts))

    resolver_states_full, resolver_source, resolver_transitions = _resolver_states_full(
        instrument, corpus_sha, base_ts,
    )

    htf_bars = cs.to_timeframe(base_bars, timeframe)
    engine_htf_states = cs.downsample_states(base_bars, engine_track.states, htf_bars, timeframe)
    resolver_htf_states = cs.downsample_states(base_bars, resolver_states_full, htf_bars, timeframe)

    # Window: default the tail `limit` bars; start/end override. One shared index list keeps
    # bars / engine states / resolver states aligned regardless of which branch is taken.
    if start_dt is not None or end_dt is not None:
        windowed_bars, idx = cs.slice_window(htf_bars, start_dt, end_dt)
    else:
        idx = list(range(len(htf_bars)))[-limit:]
        windowed_bars = [htf_bars[i] for i in idx]
    windowed_engine_states = [engine_htf_states[i] for i in idx]
    windowed_resolver_states = [resolver_htf_states[i] for i in idx]

    win_start = windowed_bars[0].timestamp if windowed_bars else None
    win_end = windowed_bars[-1].timestamp if windowed_bars else None

    # `crt_aliasing` compares base-bar density to CRT dwell WITHIN the rendered window —
    # scoping `base_bars`/`base_transitions` to the full corpus here (instead of the base
    # bars this window actually spans) inflates bars-per-bucket by corpus_len/window_len and
    # falsely flags even M15 (window == base cadence) as ALIASED.
    base_window_bars, base_window_idx = cs.slice_window(base_bars, win_start, win_end)
    base_window_transitions = sum(
        1 for i in range(1, len(base_window_idx))
        if engine_track.states[base_window_idx[i]] != engine_track.states[base_window_idx[i] - 1]
    )

    series = cs.ChartSeries(
        instrument=instrument, timeframe=timeframe, bars=windowed_bars,
        crt_state=windowed_engine_states, crt_state_source=engine_track.source,
        config_pin=config_pin,
        base_bars=len(base_window_bars), base_transitions=base_window_transitions,
    )

    bars_payload = [{
        "time": c.timestamp.isoformat(), "open": c.open, "high": c.high,
        "low": c.low, "close": c.close, "volume": c.volume,
    } for c in windowed_bars]

    return {
        "ok": True,
        "instrument": instrument,
        "run_id": run.run_id,
        "timeframe": timeframe,
        "bars": bars_payload,
        "crt_state": {
            "engine": {
                "states": windowed_engine_states,
                "source": engine_track.source,
                "transitions": engine_track.transitions,
            },
            "resolver": {
                "states": windowed_resolver_states,
                "source": resolver_source,
                "transitions": resolver_transitions,
            },
        },
        "trades": _read_trades(run.trades_path, instrument, win_start, win_end),
        "event_pins": _read_event_pins(run.events_path, win_start, win_end),
        "gap_bands": _find_gap_bands(windowed_bars),
        "integrity": {
            "decision": integrity.get("decision"),
            "missing_pct": integrity.get("missing_pct"),
            "hard_failures": integrity.get("hard_failures", []),
            "warnings": integrity.get("warnings", []),
        },
        "legend": cs.build_legend(series),
        "config_pin": config_pin,
    }
