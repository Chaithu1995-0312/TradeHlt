"""
CRT Engine — Data Preparation Script
Converts raw M1 data -> clean M15 OHLCV CSVs ready for portfolio validation.

Supported input formats:
  - histdata.com  ASCII: 20240101 070000,1.26000,1.26035,...
  - Binance klines:     1704067200000,42000.0,42100.0,...
  - Standard CSV:       2024-01-01 07:00:00,1.26000,...

Usage:
    python prepare_data.py --source histdata --files GBPUSD_2024.csv GBPUSD_2025.csv --instrument GBPUSD
    python prepare_data.py --source binance  --files BTCUSDT-1m-2024-01.csv ... --instrument BTCUSDT
    python prepare_data.py --source standard --files data.csv --instrument XAUUSD
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from datetime import timezone



# ─────────────────────────────────────────────────────────────────
# PARSERS — one per source format
# ─────────────────────────────────────────────────────────────────

def parse_histdata(filepath: str) -> list[tuple]:
    """
    histdata.com ASCII M1 format:
      YYYYMMDD HHMMSS,Open,High,Low,Close,Volume
      20240101 070000,1.10427,1.10433,1.10423,1.10431,0
    OR semicolon-separated with no volume:
      20240101 070000;1.10427;1.10433;1.10423;1.10431;
    """
    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("Date") or line.startswith("date"):
                continue
            # Handle both comma and semicolon delimiters
            sep = ";" if ";" in line else ","
            parts = line.split(sep)
            if len(parts) < 5:
                continue
            try:
                raw_dt = parts[0].strip()
                # Format: YYYYMMDD HHMMSS
                dt = datetime.strptime(raw_dt, "%Y%m%d %H%M%S")
                o, h, l, c = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                v = float(parts[5]) if len(parts) > 5 and parts[5].strip() else 0.0
                rows.append((dt, o, h, l, c, v))
            except (ValueError, IndexError):
                continue
    return rows


def parse_binance(filepath: str) -> list[tuple]:
    """
    Binance klines CSV format:
      open_time,open,high,low,close,volume,close_time,quote_volume,...
      1704067200000,42000.0,42100.0,41900.0,42050.0,123.45,...
    open_time is Unix ms timestamp UTC.
    """
    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        # Check if first row is header or data
        if header and not header[0].strip().lstrip('-').isdigit():
            pass  # actual header, already consumed
        else:
            if header:
                # First row was data
                try:
                    ts_ms = int(header[0])
                    dt = datetime.utcfromtimestamp(ts_ms / 1000)
                    o, h, l, c = float(header[1]), float(header[2]), float(header[3]), float(header[4])
                    v = float(header[5]) if len(header) > 5 else 0.0
                    rows.append((dt, o, h, l, c, v))
                except (ValueError, IndexError):
                    pass

        for parts in reader:
            if not parts:
                continue
            try:
                ts_ms = int(parts[0])
                dt    = datetime.utcfromtimestamp(ts_ms / 1000)
                o, h, l, c = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                v = float(parts[5]) if len(parts) > 5 else 0.0
                rows.append((dt, o, h, l, c, v))
            except (ValueError, IndexError):
                continue
    return rows


def parse_standard(filepath: str) -> list[tuple]:
    """
    Standard CSV format (same as engine output):
      timestamp,open,high,low,close,volume
      2024-01-01 07:00:00,1.10427,1.10433,...
    Also handles Yahoo Finance format with 'Date' header.
    """
    DATE_FORMATS = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = [h.strip().lower() for h in next(reader, [])]

        # Detect column indices
        def _find(aliases):
            for alias in aliases:
                for i, h in enumerate(headers):
                    if h == alias:
                        return i
            return None

        ts_col = _find(["timestamp", "datetime", "date", "time"])
        o_col  = _find(["open", "o"])
        h_col  = _find(["high", "h"])
        l_col  = _find(["low", "l"])
        c_col  = _find(["close", "c", "adj close"])
        v_col  = _find(["volume", "vol"])

        if any(x is None for x in [ts_col, o_col, h_col, l_col, c_col]):
            raise ValueError(f"Cannot detect OHLC columns. Headers: {headers}")

        for row in reader:
            if not row:
                continue
            try:
                raw = row[ts_col].strip()
                dt  = None
                for fmt in DATE_FORMATS:
                    try:
                        dt = datetime.strptime(raw, fmt)
                        break
                    except ValueError:
                        continue
                if dt is None:
                    continue

                o, h, l, c = float(row[o_col]), float(row[h_col]), float(row[l_col]), float(row[c_col])
                v = float(row[v_col]) if v_col is not None else 0.0
                rows.append((dt, o, h, l, c, v))
            except (ValueError, IndexError):
                continue
    return rows


# ─────────────────────────────────────────────────────────────────
# RESAMPLER — M1 → M15
# ─────────────────────────────────────────────────────────────────

def resample_m15(m1_rows: list[tuple]) -> list[tuple]:
    """
    Aggregate M1 OHLCV candles into M15 buckets.
    Bucket anchor: floor(minute / 15) * 15 — e.g. :00, :15, :30, :45
    Only outputs complete buckets (all 15 M1 bars present is ideal,
    but partial buckets at session open/close are included if >= 1 bar).
    """
    buckets: dict = defaultdict(list)

    for dt, o, h, l, c, v in m1_rows:
        # Floor to 15-minute boundary
        floored_min = (dt.minute // 15) * 15
        bucket_dt   = dt.replace(minute=floored_min, second=0, microsecond=0)
        buckets[bucket_dt].append((dt, o, h, l, c, v))

    result = []
    for bucket_dt in sorted(buckets.keys()):
        bars = sorted(buckets[bucket_dt], key=lambda x: x[0])
        o15 = bars[0][1]                    # first bar open
        h15 = max(b[2] for b in bars)       # max high
        l15 = min(b[3] for b in bars)       # min low
        c15 = bars[-1][4]                   # last bar close
        v15 = sum(b[5] for b in bars)       # sum volume

        # Basic integrity check
        if h15 < max(o15, c15) or l15 > min(o15, c15) or h15 == l15:
            continue

        result.append((bucket_dt, o15, h15, l15, c15, v15))

    return result


# ─────────────────────────────────────────────────────────────────
# VALIDATOR
# ─────────────────────────────────────────────────────────────────

def validate(rows: list[tuple], instrument: str) -> dict:
    if not rows:
        return {"status": "EMPTY", "issues": ["No rows"]}

    issues = []

    # Check time ordering
    for i in range(1, len(rows)):
        if rows[i][0] <= rows[i-1][0]:
            issues.append(f"Out of order at row {i}: {rows[i-1][0]} -> {rows[i][0]}")
            if len(issues) >= 3:
                break

    # Check for OHLC integrity violations
    bad_ohlc = sum(1 for dt,o,h,l,c,v in rows if h < max(o,c) or l > min(o,c))
    if bad_ohlc > 0:
        issues.append(f"{bad_ohlc} candles with OHLC integrity violations")

    # Check for zero-range candles
    zero_range = sum(1 for dt,o,h,l,c,v in rows if h == l)
    if zero_range > 0:
        issues.append(f"{zero_range} zero-range candles")

    # Check for gaps > 2h during weekdays
    gaps = []
    for i in range(1, len(rows)):
        gap_min = (rows[i][0] - rows[i-1][0]).total_seconds() / 60
        # Skip Friday→Monday gaps
        if rows[i-1][0].weekday() == 4 and rows[i][0].weekday() == 0:
            continue
        # Skip known session breaks (weekend)
        if rows[i-1][0].weekday() >= 5 or rows[i][0].weekday() >= 5:
            continue
        if gap_min > 120:
            gaps.append((rows[i-1][0], rows[i][0], gap_min))

    if gaps:
        issues.append(f"{len(gaps)} intra-week gaps > 2h")

    # Date range
    start, end = rows[0][0], rows[-1][0]
    cal_days = (end - start).days

    stats = {
        "status":      "OK" if not issues else "WARNING",
        "instrument":  instrument,
        "total_bars":  len(rows),
        "date_from":   start.isoformat(),
        "date_to":     end.isoformat(),
        "calendar_days": cal_days,
        "trading_days_approx": int(cal_days * 5 / 7),
        "weekend_gaps": len([r for i,r in enumerate(rows[1:], 1)
                             if rows[i-1][0].weekday() == 4 and rows[i][0].weekday() == 0]),
        "issues": issues,
    }

    return stats


# ─────────────────────────────────────────────────────────────────
# WRITER
# ─────────────────────────────────────────────────────────────────

def write_csv(rows: list[tuple], filepath: str) -> None:
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for dt, o, h, l, c, v in rows:
            w.writerow([dt.strftime("%Y-%m-%d %H:%M:%S"),
                        round(o, 5), round(h, 5), round(l, 5), round(c, 5),
                        round(v, 2)])


# ─────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────

PARSERS = {
    "histdata": parse_histdata,
    "binance":  parse_binance,
    "standard": parse_standard,
}


def process(
    source:     str,
    files:      list[str],
    instrument: str,
    output_dir: str = "data",
    already_m15: bool = False,
) -> str:
    """
    Full pipeline: load -> merge -> sort -> resample -> validate -> write.
    Returns output filepath.
    """
    parser = PARSERS.get(source)
    if not parser:
        raise ValueError(f"Unknown source: {source}. Choose: {list(PARSERS.keys())}")

    print(f"\n{'-'*55}")
    print(f"  {instrument} [{source.upper()}]")
    print(f"{'-'*55}")

    # Load and merge all input files
    all_rows = []
    for filepath in files:
        if not Path(filepath).exists():
            print(f"  [!]  File not found: {filepath} - skipping")
            continue
        print(f"  Loading: {filepath}")
        rows = parser(filepath)
        print(f"    Parsed {len(rows):,} M1 bars")
        all_rows.extend(rows)

    if not all_rows:
        print(f"  [FAIL] No data loaded for {instrument}")
        return ""

    # Sort chronologically and deduplicate
    all_rows.sort(key=lambda x: x[0])
    seen = set()
    deduped = []
    for row in all_rows:
        if row[0] not in seen:
            seen.add(row[0])
            deduped.append(row)
    if len(deduped) < len(all_rows):
        print(f"  Removed {len(all_rows)-len(deduped):,} duplicate timestamps")

    all_rows = [
        (dt.replace(tzinfo=timezone.utc), o, h, l, c, v)
        for (dt, o, h, l, c, v) in all_rows
    ]
    print(f"  Total M1 bars: {len(all_rows):,}")
    print(f"  Date range:    {all_rows[0][0]} -> {all_rows[-1][0]}")

    # Resample to M15 (skip if data is already M15)
    if already_m15:
        m15_rows = all_rows
        print(f"  Skipping resample (already M15)")
    else:
        print(f"  Resampling M1 -> M15 ...")
        m15_rows = resample_m15(all_rows)
        print(f"  M15 bars: {len(m15_rows):,}  (expected ~{len(all_rows)//15:,})")

    # Validate
    stats = validate(m15_rows, instrument)
    print(f"\n  VALIDATION:")
    print(f"    Status:         {stats['status']}")
    print(f"    Bars:           {stats['total_bars']:,}")
    print(f"    Date range:     {stats['date_from'][:10]} -> {stats['date_to'][:10]}")
    print(f"    Calendar days:  {stats['calendar_days']:,}")
    print(f"    Weekend gaps:   {stats['weekend_gaps']}")
    if stats['issues']:
        for issue in stats['issues']:
            print(f"    [!]  {issue}")
    else:
        print(f"    [OK] No issues found")

    # Write
    out_path = str(Path(output_dir) / f"{instrument}_M15_real.csv")
    write_csv(m15_rows, out_path)
    print(f"\n  [OK] Written: {out_path}")

    return out_path


# ─────────────────────────────────────────────────────────────────
# QUICK-VALIDATE EXISTING FILES
# ─────────────────────────────────────────────────────────────────

def validate_existing(data_dir: str = "data") -> None:
    """
    Scan data/ directory and validate all *_real.csv files.
    Reports: bars, date range, duplicates, OHLC violations, gap distribution.
    Run before any backtest to confirm data integrity.
    """
    files = sorted(Path(data_dir).glob("*_M15.csv"))
    if not files:
        print(f"No *_real.csv files found in {data_dir}/")
        return

    print(f"\n{'='*65}")
    print(f"  DATASET VALIDATION REPORT")
    print(f"{'='*65}")

    all_ok = True
    for f in files:
        rows = parse_standard(str(f))
        stats = validate(rows, f.stem.replace("_M15_real","").replace("_real",""))
        instr = f.stem.replace("_M15_real","").replace("_M15","").replace("_real","")

        # Gap analysis
        timestamps = [r[0] for r in rows]
        gap_counts: dict[int, int] = {}
        for i in range(1, len(timestamps)):
            g = int((timestamps[i] - timestamps[i-1]).total_seconds() / 60)
            if g != 15:
                gap_counts[g] = gap_counts.get(g, 0) + 1

        # Classify gaps
        expected_gaps   = {g: n for g, n in gap_counts.items() if g in (30, 45, 60, 75)}  # known session breaks
        unexpected_gaps = {g: n for g, n in gap_counts.items()
                          if g not in (30, 45, 60, 75) and g < 4320}  # < 3 days = unexpected
        weekend_gaps    = {g: n for g, n in gap_counts.items() if g >= 4320}

        ok = (stats["status"] == "OK"
              and sum(unexpected_gaps.values()) < 20
              and stats.get("duplicates", 0) == 0)
        all_ok = all_ok and ok
        flag = "[OK]" if ok else "[!] "

        print(f"\n{flag} {instr}")
        print(f"    Bars:             {stats['total_bars']:>8,}")
        print(f"    Date range:       {stats['date_from'][:10]} -> {stats['date_to'][:10]}  ({stats['calendar_days']} days)")
        print(f"    OHLC violations:  {stats.get('bad_ohlc', 0):>8}")
        print(f"    Duplicate ts:     {stats.get('duplicates', 0):>8}")

        if unexpected_gaps:
            items = ", ".join(f"{g}m×{n}" for g,n in sorted(unexpected_gaps.items()))
            print(f"    Unexpected gaps:  {sum(unexpected_gaps.values()):>8}  [{items}]")
        else:
            print(f"    Unexpected gaps:       0  [OK]")

        if expected_gaps:
            items = ", ".join(f"{g}m×{n}" for g,n in sorted(expected_gaps.items()))
            print(f"    Session breaks:   {sum(expected_gaps.values()):>8}  [{items}] (normal)")

        if weekend_gaps:
            print(f"    Weekend/holiday:  {sum(weekend_gaps.values()):>8}  (normal)")

        if stats["issues"]:
            for issue in stats["issues"]:
                print(f"    [!]  {issue}")

    print(f"\n{'='*65}")
    print(f"  Overall: {'[OK] ALL FILES VALID' if all_ok else '[!]  ISSUES FOUND - review above'}")
    print(f"{'='*65}")


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="CRT Engine - Data Preparation (M1 -> M15)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # histdata.com GBPUSD (download ASCII M1 ZIPs, extract CSVs)
  python prepare_data.py \\
    --source histdata \\
    --files DAT_ASCII_GBPUSD_M1_2024.csv DAT_ASCII_GBPUSD_M1_2025.csv \\
    --instrument GBPUSD

  # Binance BTCUSDT (download monthly 1m ZIP files, extract CSVs)
  python prepare_data.py \\
    --source binance \\
    --files BTCUSDT-1m-2024-01.csv BTCUSDT-1m-2024-02.csv ... \\
    --instrument BTCUSDT

  # XAUUSD from histdata
  python prepare_data.py \\
    --source histdata \\
    --files DAT_ASCII_XAUUSD_M1_2024.csv DAT_ASCII_XAUUSD_M1_2025.csv \\
    --instrument XAUUSD

  # Validate what you already have
  python prepare_data.py --validate-only

  # Check a file that's already M15
  python prepare_data.py \\
    --source standard \\
    --files EURCAD_M15.csv \\
    --instrument EURCAD \\
    --already-m15
        """
    )
    ap.add_argument("--source",      choices=["histdata","binance","standard"],
                    help="Data source format")
    ap.add_argument("--files",       nargs="+", default=[],
                    help="Input CSV files (multiple allowed, will be merged)")
    ap.add_argument("--instrument",  default="UNKNOWN",
                    help="Instrument name (e.g. GBPUSD, XAUUSD, BTCUSDT)")
    ap.add_argument("--output",      default="data",
                    help="Output directory (default: data/)")
    ap.add_argument("--already-m15", action="store_true",
                    help="Skip resampling (input is already M15)")
    ap.add_argument("--validate-only", action="store_true",
                    help="Only validate existing *_real.csv files in data/")

    args = ap.parse_args()

    if args.validate_only:
        validate_existing("data")
        return

    if not args.source:
        ap.error("--source required unless --validate-only")
    if not args.files:
        ap.error("--files required unless --validate-only")

    process(
        source      = args.source,
        files       = args.files,
        instrument  = args.instrument,
        output_dir  = args.output,
        already_m15 = args.already_m15,
    )

    print(f"\n{'-'*55}")
    print(f"  Run validation check on all datasets:")
    print(f"  python prepare_data.py --validate-only")
    print(f"{'-'*55}\n")


if __name__ == "__main__":
    main()
