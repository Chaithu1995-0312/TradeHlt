"""
unified_data_builder.py
═══════════════════════════════════════════════════════════════════
CRT Engine — Unified Batch Data Ingestion Pipeline
Replaces: build_m15_unified.py, run_hisotircal_data_*.py, convert_binance_m1_to_m15.py

WHAT IT DOES
  - Single entry point for all instruments (forex + crypto)
  - Auto-detects source format (histdata / binance / standard)
  - Resolves glob patterns per instrument
  - Routes each file to the correct parser (from prepare_data.py)
  - Outputs clean M15 CSV per instrument to data/
  - Validates output before declaring success
  - Full debug logging: files loaded, rows parsed, rows dropped, candle count

USAGE
  python unified_data_builder.py                     # build all instruments in INSTRUMENT_CONFIG
  python unified_data_builder.py GBPUSD BTCUSDT      # build specific instruments only
  python unified_data_builder.py --validate-only     # validate existing M15 files
  python unified_data_builder.py --dry-run           # show what would be built, no output

ASSUMPTIONS
  - Input M1 files live in data/ directory (configurable via --data-dir)
  - Output M15 CSVs are written to data/ (configurable via --output-dir)
  - backtest_v2.py expects columns: timestamp,open,high,low,close,volume
  - backtest_v2.py file naming: {INSTRUMENT}_M15.csv  (or _M15_real.csv)

EDGE CASES HANDLED
  - Empty files -> skipped with structured warning, pipeline continues
  - Mixed format files per instrument -> auto-detection per file
  - No files found for instrument -> structured error, continue to next
  - Invalid schema -> file skipped, warning logged, count tracked
  - Duplicate timestamps -> deduplicated, count reported
  - Out-of-order rows -> sorted before resampling
  - Partial M15 buckets -> included (prepare_data.py behaviour preserved)
  - Friday->Monday gaps -> not flagged as errors in validation
  - Zero-range candles filtered by resample_m15 OHLC integrity check

FAILURE MODES
  - prepare_data.py not in same directory -> clear ImportError message
  - All files missing for an instrument -> error logged, others continue
  - Output directory not writable -> exception propagated with path info

TEST CASES (manual)
  Forex:  python unified_data_builder.py GBPUSD EURCAD XAUUSD
  Crypto: python unified_data_builder.py BTCUSDT
  Mixed:  python unified_data_builder.py GBPUSD BTCUSDT
  All:    python unified_data_builder.py
  Dryrun: python unified_data_builder.py --dry-run

INTEGRATION (backtest_v2 compatibility)
  backtest_v2.py loads data/{INSTRUMENT}_M15.csv or {INSTRUMENT}_M15_real.csv
  This builder writes to --output-dir/{INSTRUMENT}_M15_real.csv by default.
  If your backtest_v2 expects _M15.csv (no _real suffix), set:
    OUTPUT_SUFFIX = "_M15.csv"  in the config block below.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# DEPENDENCY CHECK — prepare_data.py must be importable from same directory
# ──────────────────────────────────────────────────────────────────────────────
try:
    from prepare_data import (
        parse_histdata,
        parse_binance,
        parse_standard,
        resample_m15,
        validate,
        write_csv,
    )
except ImportError as e:
    print(
        "\n  IMPORT ERROR: Cannot import from prepare_data.py\n"
        "    Ensure prepare_data.py is in the same directory as this script.\n"
        f"    Details: {e}\n"
    )
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# INSTRUMENT CONFIG — edit here to add/remove instruments
# ──────────────────────────────────────────────────────────────────────────────

INSTRUMENT_CONFIG: dict[str, dict] = {
    "GBPUSD": {
        "source":  "auto",          # auto-detect per file
        "pattern": "data/DAT_ASCII_GBPUSD_M1_*.csv",
        "note":    "histdata.com ASCII M1",
    },
    "EURCAD": {
        "source":  "auto",
        "pattern": "data/DAT_ASCII_EURCAD_M1_*.csv",
        "note":    "histdata.com ASCII M1",
    },
    "XAUUSD": {
        "source":  "auto",
        "pattern": "data/DAT_ASCII_XAUUSD_M1_*.csv",
        "note":    "histdata.com ASCII M1",
    },
    "BTCUSDT": {
        "source":  "auto",
        "pattern": "data/BTCUSDT-1m-*.csv",
        "note":    "Binance klines — Unix ms timestamps",
    },
    "EURUSD": {
        "source": "auto",
        "pattern": "data/DAT_ASCII_EURUSD_M1_*.csv",
    },
    "USDJPY": {
        "source": "auto",
        "pattern": "data/DAT_ASCII_USDJPY_M1_*.csv",
    },
    "AUDUSD": {
        "source": "auto",
        "pattern": "data/DAT_ASCII_AUDUSD_M1_*.csv",
    },
    "ETHUSDT": {
        "source": "auto",
        "pattern": "data/ETHUSDT-1m-*.csv",
    }
}

# Output filename suffix — set to "_M15.csv" if backtest_v2 expects no _real suffix
OUTPUT_SUFFIX = "_M15.csv"


# ──────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ──────────────────────────────────────────────────────────────────────────────

def setup_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )
    return logging.getLogger("unified_builder")


# ──────────────────────────────────────────────────────────────────────────────
# AUTO SOURCE DETECTION
# ──────────────────────────────────────────────────────────────────────────────

def detect_source(filepath: str) -> str:
    """
    Sniff first non-empty line to determine data source format.

    Rules:
      binance  -> first field is a 13-digit integer (Unix ms timestamp > 1e12)
      histdata -> first field matches YYYYMMDD HHMMSS pattern (8-digit date block)
      standard -> fallback (has named headers like 'timestamp','open',...)

    Returns: "histdata" | "binance" | "standard"
    """
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                sep = ";" if ";" in line else ","
                parts = line.split(sep)
                first = parts[0].strip()

                # Binance unix ms: exactly 13-digit integer
                if first.isdigit() and len(first) == 13:
                    return "binance"

                # histdata: "YYYYMMDD HHMMSS" — first 8 chars are digits, space at pos 8
                if len(first) >= 8 and first[:8].isdigit():
                    return "histdata"

                # Standard: alphabetic header
                return "standard"
    except (OSError, UnicodeDecodeError):
        pass

    return "standard"  # safe fallback


# ──────────────────────────────────────────────────────────────────────────────
# PARSERS MAP
# ──────────────────────────────────────────────────────────────────────────────

PARSERS = {
    "histdata": parse_histdata,
    "binance":  parse_binance,
    "standard": parse_standard,
}


# ──────────────────────────────────────────────────────────────────────────────
# SINGLE INSTRUMENT BUILDER
# ──────────────────────────────────────────────────────────────────────────────

def build_instrument(
    instrument: str,
    config:     dict,
    data_dir:   str  = "data",
    output_dir: str  = "data",
    dry_run:    bool = False,
    log:        Optional[logging.Logger] = None,
) -> dict:
    """
    Build M15 CSV for a single instrument.

    Returns result dict with keys:
      instrument, status, files_found, files_loaded, files_skipped,
      m1_rows_parsed, m1_rows_dropped, m15_candles,
      output_path, validation, errors, elapsed_s
    """
    if log is None:
        log = logging.getLogger("unified_builder")

    result: dict = {
        "instrument":      instrument,
        "status":          "ERROR",
        "files_found":     0,
        "files_loaded":    0,
        "files_skipped":   0,
        "m1_rows_parsed":  0,
        "m1_rows_dropped": 0,
        "m15_candles":     0,
        "output_path":     None,
        "validation":      None,
        "errors":          [],
    }

    t0 = time.perf_counter()

    # ── 1. Resolve glob pattern ──────────────────────────────────────────────
    raw_pattern = config.get("pattern", "")
    matched = sorted(glob.glob(raw_pattern))
    if not matched:
        # Try relative to data_dir
        matched = sorted(glob.glob(str(Path(data_dir) / Path(raw_pattern).name)))

    result["files_found"] = len(matched)

    if not matched:
        msg = f"No files found for pattern: {raw_pattern}"
        log.error("%-10s  NO FILES   %s", instrument, msg)
        result["errors"].append(msg)
        result["status"] = "ERROR"
        result["elapsed_s"] = round(time.perf_counter() - t0, 2)
        return result

    log.info("%-10s  Found %d file(s)", instrument, len(matched))
    for f in matched:
        log.debug("           -> %s", f)

    if dry_run:
        log.info("%-10s  DRY RUN — would process %d file(s)", instrument, len(matched))
        result["status"] = "SKIP"
        result["elapsed_s"] = round(time.perf_counter() - t0, 2)
        return result

    # ── 2. Load and parse each file ──────────────────────────────────────────
    all_rows: list[tuple] = []
    config_source = config.get("source", "auto")

    for filepath in matched:
        if config_source == "auto":
            source = detect_source(filepath)
            log.debug("           auto-detected source=%s for %s", source, Path(filepath).name)
        else:
            source = config_source

        parser = PARSERS.get(source)
        if parser is None:
            msg = f"Unknown source '{source}' for {filepath}"
            log.warning("%-10s  SKIP       %s", instrument, msg)
            result["files_skipped"] += 1
            result["errors"].append(msg)
            continue

        try:
            rows = parser(filepath)
        except Exception as exc:
            msg = f"Parse error in {Path(filepath).name}: {exc}"
            log.warning("%-10s  SKIP       %s", instrument, msg)
            result["files_skipped"] += 1
            result["errors"].append(msg)
            continue

        if not rows:
            log.warning("%-10s  SKIP       Empty file (0 rows): %s", instrument, Path(filepath).name)
            result["files_skipped"] += 1
            continue

        log.info(
            "%-10s  Loaded     %s  [%s]  ->  %d M1 bars",
            instrument, Path(filepath).name, source, len(rows)
        )
        all_rows.extend(rows)
        result["files_loaded"] += 1
        result["m1_rows_parsed"] += len(rows)

    if not all_rows:
        msg = "All files were empty or failed to parse"
        log.error("%-10s  ERROR      %s", instrument, msg)
        result["errors"].append(msg)
        result["elapsed_s"] = round(time.perf_counter() - t0, 2)
        return result

    # ── 3. Sort + deduplicate ────────────────────────────────────────────────
    before_dedup = len(all_rows)
    all_rows.sort(key=lambda x: x[0])
    seen: set = set()
    deduped: list[tuple] = []
    for row in all_rows:
        if row[0] not in seen:
            seen.add(row[0])
            deduped.append(row)

    dropped = before_dedup - len(deduped)
    result["m1_rows_dropped"] = dropped
    if dropped:
        log.info("%-10s  Dedup      Removed %d duplicate timestamps", instrument, dropped)

    all_rows = deduped

    log.info(
        "%-10s  M1 Total   %d bars  |  %s -> %s",
        instrument,
        len(all_rows),
        all_rows[0][0].strftime("%Y-%m-%d"),
        all_rows[-1][0].strftime("%Y-%m-%d"),
    )

    # ── 4. Schema sanity check (spot-check 10 rows) ──────────────────────────
    sample = all_rows[:10]
    bad_schema = sum(1 for row in sample if len(row) != 6)
    if bad_schema:
        msg = f"Schema warning: {bad_schema}/10 sample rows have unexpected column count"
        log.warning("%-10s  SCHEMA     %s", instrument, msg)
        result["errors"].append(msg)

    # ── 5. Resample M1 -> M15 ────────────────────────────────────────────────
    log.info("%-10s  Resample   M1 -> M15 ...", instrument)
    m15_rows = resample_m15(all_rows)
    result["m15_candles"] = len(m15_rows)

    log.info(
        "%-10s  M15 Total  %d candles  (expected ~%d)",
        instrument, len(m15_rows), len(all_rows) // 15
    )

    if not m15_rows:
        msg = "Resampling produced 0 M15 candles — check M1 data integrity"
        log.error("%-10s  ERROR      %s", instrument, msg)
        result["errors"].append(msg)
        result["elapsed_s"] = round(time.perf_counter() - t0, 2)
        return result

    # ── 6. Validate M15 output ───────────────────────────────────────────────
    stats = validate(m15_rows, instrument)
    result["validation"] = stats

    if stats["status"] == "OK":
        log.info(
            "%-10s  Validate   OK  |  bars=%d  |  %s -> %s",
            instrument, stats["total_bars"],
            stats["date_from"][:10], stats["date_to"][:10],
        )
    else:
        log.warning("%-10s  Validate   %s", instrument, stats["status"])
        for issue in stats.get("issues", []):
            log.warning("%-10s             * %s", instrument, issue)

    # ── 7. Write output CSV ──────────────────────────────────────────────────
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = str(Path(output_dir) / f"{instrument}{OUTPUT_SUFFIX}")
    try:
        write_csv(m15_rows, out_path)
        result["output_path"] = out_path
        log.info("%-10s  Written    %s", instrument, out_path)
    except Exception as exc:
        msg = f"Write failed to {out_path}: {exc}"
        log.error("%-10s  ERROR      %s", instrument, msg)
        result["errors"].append(msg)
        result["elapsed_s"] = round(time.perf_counter() - t0, 2)
        return result

    result["status"] = stats["status"]   # "OK" or "WARNING"
    result["elapsed_s"] = round(time.perf_counter() - t0, 2)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATE EXISTING M15 FILES
# ──────────────────────────────────────────────────────────────────────────────

def validate_existing(data_dir: str = "data", log: Optional[logging.Logger] = None) -> None:
    """Scan data dir for *_M15*.csv files and print a validation report."""
    if log is None:
        log = logging.getLogger("unified_builder")

    files = sorted(Path(data_dir).glob("*_M15*.csv"))
    if not files:
        log.warning("No *_M15*.csv files found in %s/", data_dir)
        return

    print(f"\n{'='*65}")
    print(f"  EXISTING M15 DATASET VALIDATION REPORT")
    print(f"{'='*65}")

    for f in files:
        try:
            rows = parse_standard(str(f))
        except Exception as exc:
            print(f"\n  ERROR  {f.name}  ->  {exc}")
            continue
        instr = f.stem.replace("_M15_real", "").replace("_M15", "").replace("_real", "")
        stats = validate(rows, instr)
        flag = "OK " if stats["status"] == "OK" else "WRN"
        print(f"\n  [{flag}] {instr}  ({f.name})")
        print(f"    Bars:          {stats['total_bars']:>8,}")
        print(f"    Date range:    {stats['date_from'][:10]} -> {stats['date_to'][:10]}")
        print(f"    Calendar days: {stats['calendar_days']:>8,}")
        if stats["issues"]:
            for issue in stats["issues"]:
                print(f"    WARN  {issue}")
        else:
            print(f"    Issues:        None")

    print(f"\n{'='*65}\n")


# ──────────────────────────────────────────────────────────────────────────────
# BATCH RUNNER
# ──────────────────────────────────────────────────────────────────────────────

def run_batch(
    instruments: list[str],
    data_dir:    str  = "data",
    output_dir:  str  = "data",
    dry_run:     bool = False,
    log:         Optional[logging.Logger] = None,
) -> list[dict]:
    """Run the full pipeline for the given list of instruments."""
    if log is None:
        log = logging.getLogger("unified_builder")

    results: list[dict] = []

    print(f"\n{'='*65}")
    print(f"  UNIFIED DATA BUILDER  {'[DRY RUN]' if dry_run else ''}")
    print(f"  Instruments: {', '.join(instruments)}")
    print(f"  Output dir:  {output_dir}/")
    print(f"{'='*65}\n")

    for instrument in instruments:
        config = INSTRUMENT_CONFIG.get(instrument)
        if config is None:
            log.error("%-10s  Not found in INSTRUMENT_CONFIG — skipping", instrument)
            results.append({
                "instrument": instrument, "status": "ERROR",
                "m1_rows_parsed": 0, "m15_candles": 0,
                "output_path": None,
                "errors": ["Not in INSTRUMENT_CONFIG"],
                "elapsed_s": 0,
            })
            continue

        print(f"  -- {instrument}  ({config.get('note','')})")
        result = build_instrument(
            instrument=instrument,
            config=config,
            data_dir=data_dir,
            output_dir=output_dir,
            dry_run=dry_run,
            log=log,
        )
        results.append(result)
        print()

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"{'='*65}")
    print(f"  BUILD SUMMARY")
    print(f"{'='*65}")
    header = f"  {'Instrument':<12} {'Status':<10} {'M1 Bars':>10} {'M15 Bars':>10} {'Secs':>6}  Output"
    print(header)
    print(f"  {'-'*61}")

    ok_count  = 0
    err_count = 0

    for r in results:
        instr  = r["instrument"]
        status = r["status"]
        m1     = r.get("m1_rows_parsed", 0)
        m15    = r.get("m15_candles", 0)
        secs   = r.get("elapsed_s", 0)
        out    = Path(r["output_path"]).name if r.get("output_path") else "—"
        flag   = "OK " if status == "OK" else ("WRN" if status == "WARNING" else "ERR")

        print(f"  [{flag}] {instr:<10} {status:<10} {m1:>10,} {m15:>10,} {secs:>5.1f}s  {out}")

        if status in ("OK", "WARNING"):
            ok_count += 1
        else:
            err_count += 1

        for e in r.get("errors", []):
            print(f"         -> {e}")

    print(f"  {'-'*61}")
    print(f"  Built: {ok_count}   Errors: {err_count}   Total: {len(results)}")
    print(f"{'='*65}\n")

    return results


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="CRT Engine — Unified Batch M1->M15 Data Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python unified_data_builder.py                      # build all configured instruments
  python unified_data_builder.py GBPUSD BTCUSDT       # build specific instruments
  python unified_data_builder.py --validate-only      # validate existing M15 files
  python unified_data_builder.py --dry-run            # preview without writing
  python unified_data_builder.py BTCUSDT -v           # verbose (debug) logging

Configured instruments:
"""
        + "\n".join(
            f"  {k:<12} {v.get('source','auto'):<10} {v.get('pattern','')}"
            for k, v in INSTRUMENT_CONFIG.items()
        )
    )

    ap.add_argument(
        "instruments", nargs="*",
        help="Instruments to build (default: all in INSTRUMENT_CONFIG)",
    )
    ap.add_argument(
        "--data-dir", default="data",
        help="Directory where raw M1 CSVs live (default: data/)",
    )
    ap.add_argument(
        "--output-dir", default="data",
        help="Directory to write M15 CSVs (default: data/)",
    )
    ap.add_argument(
        "--validate-only", action="store_true",
        help="Only validate existing *_M15*.csv files, no building",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Resolve patterns and report counts, do not write output",
    )
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable DEBUG-level logging",
    )

    args = ap.parse_args()
    log  = setup_logging(verbose=args.verbose)

    if args.validate_only:
        validate_existing(args.data_dir, log=log)
        return

    instruments = args.instruments if args.instruments else list(INSTRUMENT_CONFIG.keys())

    unknown = [i for i in instruments if i not in INSTRUMENT_CONFIG]
    if unknown:
        log.warning("Unknown instruments (not in INSTRUMENT_CONFIG): %s — skipping", unknown)
        instruments = [i for i in instruments if i in INSTRUMENT_CONFIG]

    if not instruments:
        log.error("No valid instruments to process. Exiting.")
        sys.exit(1)

    results = run_batch(
        instruments=instruments,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        log=log,
    )

    # Non-zero exit if any instrument errored
    errors = [r for r in results if r["status"] == "ERROR"]
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
