"""One-month XAUUSD projector parity (Program 12 Slice 1).

Loads a parent M15 CSV by explicit path (no R3 admission), projects H1/H4 with
``research.resample.resample``, and compares to a native HTF series on the same
dates. Method: F-080 (exact OHLC on overlap; daily-open slot classified; do not
widen tolerance). Certifies the projector. Not the ladder population.

Do not import CandleLoader or admit_csv_path. A CandleLoader XAUUSD-M15 request
rewrites ``data/XAUUSD_M15.csv`` to the 2-year Phase-1 artifact.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable

from config_layer.crt_engine_v2 import Candle
from data_ingestion.ohlcv_schema import parse_ohlcv_timestamp
from research.resample import resample

DECLARED_PARENT_PATH = "data/XAUUSD_M15.csv"
DECLARED_PARENT_N = 2116
DECLARED_PARENT_START = datetime(2026, 7, 7, 1, 0, 0)
DECLARED_PARENT_END = datetime(2026, 8, 6, 23, 45, 0)

VOL_REL_TOL = 1e-8
SUPPORTED_RULES = ("H1", "H4")


def load_ohlcv_csv(path: str | Path) -> list[Candle]:
    """Read canonical OHLCV CSV into Candle objects. No corpus admission."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"load_ohlcv_csv: missing file {path}")
    out: list[Candle] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"load_ohlcv_csv: empty header in {path}")
        cols = {h.strip().lower(): h for h in reader.fieldnames}
        for key in ("timestamp", "open", "high", "low", "close"):
            if key not in cols:
                raise ValueError(
                    f"load_ohlcv_csv: {path} missing column {key!r}; "
                    f"have {list(reader.fieldnames)}"
                )
        vol_key = cols.get("volume")
        prev_ts: datetime | None = None
        for i, row in enumerate(reader):
            ts = parse_ohlcv_timestamp(row[cols["timestamp"]])
            if prev_ts is not None and ts <= prev_ts:
                raise ValueError(
                    f"load_ohlcv_csv: non-increasing timestamp at row {i}: "
                    f"{prev_ts} -> {ts}"
                )
            prev_ts = ts
            vol = float(row[vol_key]) if vol_key and row.get(vol_key) not in (None, "") else 0.0
            out.append(
                Candle(
                    timestamp=ts,
                    open=float(row[cols["open"]]),
                    high=float(row[cols["high"]]),
                    low=float(row[cols["low"]]),
                    close=float(row[cols["close"]]),
                    volume=vol,
                    index=i,
                )
            )
    return out


def parent_window_report(candles: Iterable[Candle]) -> dict:
    """Echo n / first / last against the declared one-month window."""
    rows = list(candles)
    first = rows[0].timestamp if rows else None
    last = rows[-1].timestamp if rows else None
    return {
        "n": len(rows),
        "first": first.isoformat(sep=" ") if first else None,
        "last": last.isoformat(sep=" ") if last else None,
        "declared_n": DECLARED_PARENT_N,
        "declared_first": DECLARED_PARENT_START.isoformat(sep=" "),
        "declared_last": DECLARED_PARENT_END.isoformat(sep=" "),
        "matches_declared_window": (
            len(rows) == DECLARED_PARENT_N
            and first == DECLARED_PARENT_START
            and last == DECLARED_PARENT_END
        ),
    }


def project(parent: list[Candle], rule: str) -> list[Candle]:
    """Calendar resample of the parent series. Drops the trailing partial bucket."""
    if rule not in SUPPORTED_RULES:
        raise ValueError(f"project: rule must be one of {SUPPORTED_RULES}, got {rule!r}")
    return resample(parent, rule)


def is_daily_open_slot(ts: datetime, rule: str) -> bool:
    """F-080 daily-open slot: broker 00:00 on H4 (and the H1 00:00 hour)."""
    if ts.minute != 0 or ts.second != 0:
        return False
    if rule == "H4":
        return ts.hour == 0
    if rule == "H1":
        return ts.hour == 0
    return False


def _ohlc_equal(a: Candle, b: Candle) -> bool:
    for field in ("open", "high", "low", "close"):
        if float(getattr(a, field)) != float(getattr(b, field)):
            return False
    va, vb = float(a.volume), float(b.volume)
    denom = max(abs(va), abs(vb), 1e-12)
    return abs(va - vb) / denom <= VOL_REL_TOL


def compare_projected_vs_native(
    projected: list[Candle],
    native: list[Candle],
    *,
    rule: str,
    drop_native_trailing: bool = True,
) -> dict:
    """F-080-style overlap compare. Exact OHLC; daily-open mismatches classified.

    Native trailing bar is dropped by default (resampler never emits the
    in-progress bucket — same rule as ``verify_m5_resample_parity``).
    """
    if rule not in SUPPORTED_RULES:
        raise ValueError(f"compare_projected_vs_native: unsupported rule {rule!r}")
    ref = list(native[:-1] if drop_native_trailing and native else native)
    if not projected or not ref:
        return {
            "status": "FAIL",
            "rule": rule,
            "reason": "empty series",
            "n_projected": len(projected),
            "n_native": len(ref),
        }
    lo = max(projected[0].timestamp, ref[0].timestamp)
    hi = min(projected[-1].timestamp, ref[-1].timestamp)
    if lo > hi:
        return {
            "status": "FAIL",
            "rule": rule,
            "reason": f"no coverage overlap ({lo} > {hi})",
            "n_projected": len(projected),
            "n_native": len(ref),
        }
    proj = [c for c in projected if lo <= c.timestamp <= hi]
    nat = [c for c in ref if lo <= c.timestamp <= hi]
    by_ts = {c.timestamp: c for c in nat}
    mismatches: list[dict] = []
    n_daily_open = 0
    n_other = 0
    n_missing_native = 0
    n_agree = 0
    for a in proj:
        b = by_ts.get(a.timestamp)
        slot = is_daily_open_slot(a.timestamp, rule)
        if b is None:
            n_missing_native += 1
            mismatches.append(
                {
                    "timestamp": a.timestamp.isoformat(sep=" "),
                    "class": "daily_open_slot" if slot else "missing_in_native",
                    "field": None,
                }
            )
            if slot:
                n_daily_open += 1
            else:
                n_other += 1
            continue
        if _ohlc_equal(a, b):
            n_agree += 1
            continue
        field = None
        for name in ("open", "high", "low", "close", "volume"):
            va, vb = float(getattr(a, name)), float(getattr(b, name))
            if name == "volume":
                denom = max(abs(va), abs(vb), 1e-12)
                if abs(va - vb) / denom > VOL_REL_TOL:
                    field = name
                    break
            elif va != vb:
                field = name
                break
        klass = "daily_open_slot" if slot else "other"
        if slot:
            n_daily_open += 1
        else:
            n_other += 1
        mismatches.append(
            {
                "timestamp": a.timestamp.isoformat(sep=" "),
                "class": klass,
                "field": field,
            }
        )
    proj_ts = {c.timestamp for c in proj}
    n_missing_projected = sum(1 for c in nat if c.timestamp not in proj_ts)
    if n_other == 0 and n_missing_projected == 0:
        status = "PASS" if n_daily_open == 0 else "PASS_DAILY_OPEN_ONLY"
    else:
        status = "FAIL"
    return {
        "status": status,
        "rule": rule,
        "overlap_start": lo.isoformat(sep=" "),
        "overlap_end": hi.isoformat(sep=" "),
        "n_projected": len(proj),
        "n_native": len(nat),
        "n_agree": n_agree,
        "n_mismatch": len(mismatches),
        "n_daily_open_slot": n_daily_open,
        "n_other": n_other,
        "n_missing_in_native": n_missing_native,
        "n_missing_in_projected": n_missing_projected,
        "mismatches": mismatches[:50],
    }
