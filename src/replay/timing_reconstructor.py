"""
timing_reconstructor.py
=======================
Deterministic forward-walk that augments the opportunity/trade outcome
simulation with first-crossing TIMING for favorable R-levels.

This is the canonical, pure core for the Pattern Timing Library (measure-first,
no new model). It is shared by two callers so they cannot drift apart:

  - scripts/research/opportunity_scanner.py  (emits timing on every new scan)
  - offline backfill of existing logs/**/opportunities.jsonl (no re-scan needed)

Design contract (matches CLAUDE.md invariants):
  - No lookahead: we only ever read candles AT or AFTER entry; the favorable
    crossing for a level is the FIRST forward bar whose favorable excursion
    reaches that level, observed only up to the trade's own exit bar.
  - Conservative same-bar tie-break: a bar that triggers a pure stop-loss does
    NOT also get credited a favorable crossing (SL wins ties) — identical to
    the existing scanner convention (opportunity_scanner._simulate :68,106).
  - Outcome / rr_achieved / duration_candles / mfe / mae are computed
    byte-identically to the legacy _simulate so existing pipelines are
    unaffected; time_to_* are purely ADDITIVE keys (telemetry-additive).
  - Pure / deterministic: no RNG, no I/O in the core; same inputs -> same dict.

time_to_* are 1-indexed candle counts from entry (entry bar = idx; first
forward bar = step 1). ×15min gives minutes on M15. None == not reached
within the trade's life inside the forward horizon.
"""
from __future__ import annotations

import csv as _csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Strict OHLCV schema gate (pure-stdlib; no pandas pulled in).
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_ingestion.ohlcv_schema import (
    require_ohlcv_columns, require_reviewed_clock, resolve_ohlcv_headers,
)
from utils.parquet_store import iter_records

# Favorable R-levels we time (matches the falsification-gate experiment).
R_LEVELS: Tuple[float, ...] = (0.25, 0.5, 1.0)

# A forward bar is (high, low, close).
Bar = Tuple[float, float, float]


def _result(outcome: str, rr: float, duration: int, mfe: float, mae: float,
            time_to: Dict[float, Optional[int]],
            r_levels: Sequence[float]) -> dict:
    out = {
        "outcome": outcome,
        "rr_achieved": float(round(rr, 4)),
        "duration_candles": duration,
        "mfe": float(round(mfe, 6)),
        "mae": float(round(mae, 6)),
        # ── ADDITIVE timing fields ───────────────────────────────────────
        "time_to_025R": time_to.get(0.25),
        "time_to_05R":  time_to.get(0.5),
        "time_to_1R":   time_to.get(1.0),
        # time_to_tp / time_to_sl: the exit candle when that exit fired, else None
        "time_to_tp": duration if outcome == "TP_HIT" else None,
        "time_to_sl": duration if outcome == "SL_HIT" else None,
    }
    return out


def simulate_with_timing(direction: str, entry: float, sl: float, tp: float,
                         bars: Sequence[Bar], risk_distance: float,
                         trail_mult: float = 0.5,
                         r_levels: Sequence[float] = R_LEVELS) -> dict:
    """Forward-walk a single trade with a trailing stop, returning the legacy
    outcome dict PLUS first-crossing timing for each favorable R-level.

    Mirrors scripts/research/opportunity_scanner.py:_simulate exactly for the
    legacy keys; adds time_to_* on top.

    Parameters
    ----------
    direction : "long" | "short"
    entry, sl, tp : float          entry / stop / take-profit prices
    bars : sequence of (high, low, close) for forward candles (entry+1, ...)
    risk_distance : float          |entry - sl| in price units (the 1R unit)
    trail_mult : float             trailing distance as a multiple of risk_distance
    """
    trail_dist = trail_mult * risk_distance
    trail_stop = sl          # starts at original SL price
    peak = entry             # most favorable price seen
    mfe = 0.0
    mae = 0.0
    duration = 0
    time_to: Dict[float, Optional[int]] = {lvl: None for lvl in r_levels}

    for i, bar in enumerate(bars):
        high = float(bar[0])
        low = float(bar[1])
        step = i + 1

        if direction == "long":
            peak = max(peak, high)
            if peak >= entry + trail_dist:                 # trail activated
                trail_stop = max(trail_stop, peak - trail_dist)
            unrealized_hi = high - entry
            unrealized_lo = low - entry
            sl_hit = low <= trail_stop
            tp_hit = high >= tp
            fav_r = (high - entry) / risk_distance if risk_distance > 0 else 0.0
        else:                                              # short
            peak = min(peak, low)
            if peak <= entry - trail_dist:                 # trail activated
                trail_stop = min(trail_stop, peak + trail_dist)
            unrealized_hi = entry - low
            unrealized_lo = entry - high
            sl_hit = high >= trail_stop
            tp_hit = low <= tp
            fav_r = (entry - low) / risk_distance if risk_distance > 0 else 0.0

        if unrealized_hi > mfe:
            mfe = unrealized_hi
        if unrealized_lo < mae:
            mae = unrealized_lo
        duration = step

        # Conservative same-bar tie-break for TIMING credit. We only suppress a
        # favorable level crossing when this bar exits via a stop that is still
        # at a LOSS/breakeven (trail not yet in profit) — there the intra-bar
        # order is genuinely ambiguous, so "stop first" wins (no favorable
        # credit). If the trail has moved into profit, the favorable run
        # demonstrably already happened, so the crossing is credited.
        tp_via_trail = sl_hit and (
            (direction == "long" and trail_stop >= tp) or
            (direction == "short" and trail_stop <= tp)
        )
        losing_stop_exit = sl_hit and not tp_via_trail and (
            (direction == "long" and trail_stop <= entry) or
            (direction == "short" and trail_stop >= entry)
        )
        if not losing_stop_exit:
            for lvl in r_levels:
                if time_to[lvl] is None and fav_r >= lvl:
                    time_to[lvl] = step

        if sl_hit:
            if tp_via_trail:
                rr = ((tp - entry) / risk_distance if direction == "long"
                      else (entry - tp) / risk_distance)
                return _result("TP_HIT", rr, duration, mfe, mae, time_to, r_levels)
            rr = ((trail_stop - entry) / risk_distance if direction == "long"
                  else (entry - trail_stop) / risk_distance)
            return _result("SL_HIT", rr, duration, mfe, mae, time_to, r_levels)
        if tp_hit:
            rr = ((tp - entry) / risk_distance if direction == "long"
                  else (entry - tp) / risk_distance)
            return _result("TP_HIT", rr, duration, mfe, mae, time_to, r_levels)

    # Forward window exhausted without TP/SL — TIMEOUT, mark-to-last-close.
    if not bars:
        unrealized = 0.0
    else:
        last_close = float(bars[-1][2])
        unrealized = ((last_close - entry) if direction == "long"
                      else (entry - last_close))
    rr = unrealized / risk_distance if risk_distance > 0 else 0.0
    return _result("TIMEOUT", rr, duration, mfe, mae, time_to, r_levels)


# ─────────────────────────────────────────────────────────────────────────
# Offline backfill helpers — recompute timing for EXISTING opportunity records
# without re-running the scanner. Reads the same M15 CSV the scan used.
# ─────────────────────────────────────────────────────────────────────────

def load_candles(csv_path: "str | Path") -> Tuple[List[str], List[float],
                                                   List[float], List[float]]:
    """Load an M15 OHLCV CSV the same way the scanner does (lowercased headers,
    timestamp derived from date[/time] if absent). Returns
    (timestamps, highs, lows, closes) as parallel lists, in file order.
    Pure stdlib — no pandas dependency in src/."""
    p = Path(csv_path)
    ts: List[str] = []
    highs: List[float] = []
    lows: List[float] = []
    closes: List[float] = []
    require_reviewed_clock(p)   # Phase 3: declared + reviewed clock (ohlcv_schema)
    with p.open(newline="", encoding="utf-8") as f:
        reader = _csv.reader(f)
        header = [h.strip().lower() for h in next(reader)]
        col = {name: i for i, name in enumerate(header)}
        # Enforce the full six-column dataset contract (this reader consumes only
        # timestamp + high/low/close, but the source must be a complete dataset).
        resolved = resolve_ohlcv_headers(header)
        require_ohlcv_columns(resolved.keys(), source=f"Historical dataset {p}")
        # Prefer an explicit split date+time pair; else the resolved single
        # timestamp column. Never derived from the row index.
        split_dt = "date" in col and "time" in col
        ts_idx = col[resolved["timestamp"]]
        for row in reader:
            if not row:
                continue
            if split_dt:
                t = f"{row[col['date']]} {row[col['time']]}"
            else:
                t = row[ts_idx]
            ts.append(str(t))
            highs.append(float(row[col["high"]]))
            lows.append(float(row[col["low"]]))
            closes.append(float(row[col["close"]]))
    return ts, highs, lows, closes


def reconstruct_record(record: dict,
                       highs: Sequence[float], lows: Sequence[float],
                       closes: Sequence[float], ts_index: Dict[str, int],
                       *, max_forward_candles: int = 40,
                       trail_mult: float = 0.5,
                       r_levels: Sequence[float] = R_LEVELS) -> Optional[dict]:
    """Recompute the outcome+timing dict for one stored opportunity record by
    re-walking the candle arrays forward from its entry timestamp.

    Returns the simulate_with_timing dict, or None if the record's timestamp
    is not found in the candle series (skip). risk_distance is derived from the
    record exactly as the scanner sized it: |entry - sl|.
    """
    t = str(record.get("timestamp", ""))
    i = ts_index.get(t)
    if i is None:
        return None
    entry = float(record["entry"])
    sl = float(record["sl"])
    tp = float(record["tp"])
    direction = record["direction"]
    risk_distance = abs(entry - sl)
    if risk_distance <= 0:
        return None
    end = min(i + 1 + int(max_forward_candles), len(highs))
    bars: List[Bar] = [(highs[k], lows[k], closes[k]) for k in range(i + 1, end)]
    return simulate_with_timing(direction, entry, sl, tp, bars, risk_distance,
                                trail_mult=trail_mult, r_levels=r_levels)


def iter_jsonl(path: "str | Path"):
    """Yield parsed records from an opportunities.jsonl, skipping the
    run_header line. Fail-soft on malformed lines (skipped).

    Reads through a Parquet projection when a fresh one exists, else straight from the
    JSONL source. The name is kept for its callers; the records are identical either way.
    """
    for rec in iter_records(path):
        if rec.get("type") == "run_header":
            continue
        yield rec
