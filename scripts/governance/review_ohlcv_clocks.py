"""
review_ohlcv_clocks.py — the human review step behind the OHLCV clock-provenance gate.

`data_ingestion.clock_registry.require_reviewed_clock` refuses to read any corpus whose timezone
has not been DECLARED and REVIEWED. This CLI is how a corpus gets reviewed.

WHY A HUMAN STEP AT ALL
-----------------------
`mt5_candle_fetcher.py:186` stamps MT5 broker-server time as UTC, so a corpus's own claim about
its clock is not evidence (F-066). `clock_detector` can gather strong evidence but it is ADVISORY:
it never sets `user_reviewed`. Someone has to look and declare, because a wrong clock silently
mislabels the session filter, `time_score` and hour-of-day features rather than failing loudly.

USAGE
-----
    # 1. bootstrap: the first reference must be a corpus that is UTC by provenance, not by
    #    measurement (Binance klines are UTC epoch by API contract; T3 corroborates 00:00 open)
    python scripts/governance/review_ohlcv_clocks.py --review data/binance/BTCUSDT_M15.csv \\
        --timezone UTC --reviewed-by "<you>" --notes "Binance klines are UTC epoch by API contract"

    # 2. scan everything else, measuring against the declared-UTC reference
    python scripts/governance/review_ohlcv_clocks.py --scan

    # 3. see what still blocks execution
    python scripts/governance/review_ohlcv_clocks.py --list --unreviewed

    # 4. inspect one corpus (prints evidence, writes nothing)
    python scripts/governance/review_ohlcv_clocks.py --review data/mt5/XAUUSD_M15.csv

    # 5. declare it
    python scripts/governance/review_ohlcv_clocks.py --review data/mt5/XAUUSD_M15.csv \\
        --timezone MT5_SERVER_NY_DST --reviewed-by "<you>"

`--review` WITHOUT `--timezone` is a read-only inspection: it prints the detector's evidence and
its suggestion, and exits. Declaring always takes an explicit `--timezone`, so a verdict can never
become a declaration by default.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from data_ingestion.clock_detector import (            # noqa: E402
    detect_clock, load_raw_ohlcv, suggested_timezone,
)
from data_ingestion.clock_registry import (            # noqa: E402
    ClockRecord, TZ_UTC, load_registry, normalize_key, registry_path,
    save_registry, sha256_file, utcnow_iso, validate_timezone_value,
)
from utils.console_safe import safe_print              # noqa: E402

OHLCV_SUFFIXES = (".csv", ".xlsx", ".xlsm", ".xls")


def _iter_corpora(data_dir: Path):
    for p in sorted(data_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in OHLCV_SUFFIXES:
            yield p


def _load_reference(records: dict, explicit: str | None):
    """The reference is a corpus already DECLARED `UTC` by a human — never one merely detected as
    UTC. Bootstrapping off a measured guess would let one unreviewed corpus define the clock for
    every other."""
    if explicit:
        return load_raw_ohlcv(explicit), explicit
    for key, rec in sorted(records.items()):
        if rec.user_reviewed and rec.timezone == TZ_UTC:
            path = _REPO_ROOT / key
            if path.exists():
                return load_raw_ohlcv(path), key
    return None, None


def cmd_scan(args) -> int:
    data_dir = (_REPO_ROOT / args.data_dir).resolve()
    if not data_dir.is_dir():
        safe_print(f"ERROR: no such directory: {data_dir}")
        return 2

    records = load_registry()
    reference, ref_key = _load_reference(records, args.reference)
    if reference is None:
        safe_print(
            "NOTE: no corpus is declared UTC yet, so T1/T2/T4 cannot run and every verdict will\n"
            "      be INCONCLUSIVE. Declare a UTC reference first (see --help), then re-scan.\n"
        )
    else:
        safe_print(f"reference (declared UTC): {ref_key}\n")

    added = skipped = failed = 0
    for path in _iter_corpora(data_dir):
        key = normalize_key(path)
        sha = sha256_file(path)
        existing = records.get(key)
        if existing and existing.sha256 == sha and existing.user_reviewed:
            skipped += 1
            continue
        try:
            detection = detect_clock(path, reference=reference)
        except Exception as exc:                       # unreadable/!OHLCV — record nothing
            safe_print(f"  SKIP {key}: {type(exc).__name__}: {str(exc)[:90]}")
            failed += 1
            continue
        records[key] = ClockRecord(
            path=key, sha256=sha, timezone=(existing.timezone if existing else ""),
            user_reviewed=False, detector=detection,
            notes=(existing.notes if existing else ""),
        )
        added += 1
        safe_print(f"  DRAFT {key}: {detection['verdict']} ({detection['confidence']})")

    save_registry(records)
    safe_print(f"\nscanned {data_dir}")
    safe_print(f"  drafted/updated : {added}")
    safe_print(f"  already reviewed: {skipped}")
    safe_print(f"  unreadable      : {failed}")
    safe_print(f"  registry        : {registry_path()}")
    safe_print("\nNothing above is reviewed. Declare each with --review <path> --timezone <TZ>.")
    return 0


def cmd_list(args) -> int:
    records = load_registry()
    if not records:
        safe_print("registry is empty - run --scan first")
        return 0
    rows = [r for r in records.values() if not (args.unreviewed and r.user_reviewed)]
    for rec in sorted(rows, key=lambda r: r.path):
        mark = "OK " if rec.user_reviewed else "PENDING"
        tz = rec.timezone or "<undeclared>"
        guess = ""
        if not rec.user_reviewed and rec.detector:
            guess = f"  [detector: {rec.detector.get('verdict')} " \
                    f"/{rec.detector.get('confidence')}]"
        safe_print(f"  {mark}  {rec.path}  {tz}{guess}")
    total, reviewed = len(records), sum(1 for r in records.values() if r.user_reviewed)
    safe_print(f"\n{reviewed}/{total} reviewed; {total - reviewed} still block execution")
    return 0


def cmd_review(args) -> int:
    path = (_REPO_ROOT / args.review).resolve() if not Path(args.review).is_absolute() \
        else Path(args.review)
    if not path.exists():
        safe_print(f"ERROR: no such file: {path}")
        return 2

    records = load_registry()
    key = normalize_key(path)
    sha = sha256_file(path)
    existing = records.get(key)

    detection = existing.detector if (existing and existing.detector) else None
    if detection is None or args.redetect:
        reference, ref_key = _load_reference(records, args.reference)
        detection = detect_clock(path, reference=reference)
        if reference is None:
            safe_print("NOTE: no declared-UTC reference available - DST/offset tests cannot run.\n")

    # ── evidence ──
    safe_print(f"corpus     : {key}")
    safe_print(f"sha256     : {sha}")
    safe_print(f"rows       : {detection['rows_inspected']}  "
               f"({detection['first_timestamp']} .. {detection['last_timestamp']})")
    safe_print(f"verdict    : {detection['verdict']}  (confidence {detection['confidence']})")
    safe_print(f"authority  : {detection['authority']}")
    safe_print("evidence   :")
    for line in detection["reasoning"]:
        safe_print(f"    - {line}")
    if args.verbose:
        safe_print(json.dumps(detection["tests"], indent=2, default=str))

    if not args.timezone:
        sugg = suggested_timezone(detection)
        safe_print("")
        safe_print("NOT RECORDED - this was an inspection. To declare the clock, re-run with:")
        safe_print(f"    --timezone {sugg or '<UTC|MT5_SERVER_NY_DST|IANA zone>'} "
                   f"--reviewed-by \"<you>\"")
        if sugg is None:
            safe_print("  (the detector does not point at a named kind here; declare explicitly)")
        return 0

    try:
        validate_timezone_value(args.timezone)
    except ValueError as exc:
        safe_print(f"ERROR: {exc}")
        return 2
    if not args.reviewed_by:
        safe_print("ERROR: --reviewed-by is required to declare a clock. "
                   "An unattributable review is not a review.")
        return 2

    records[key] = ClockRecord(
        path=key, sha256=sha, timezone=args.timezone, user_reviewed=True,
        reviewed_by=args.reviewed_by, reviewed_at=utcnow_iso(),
        detector=detection, notes=args.notes or "",
    )
    save_registry(records)
    safe_print(f"\nRECORDED: {key} declared {args.timezone} by {args.reviewed_by}")
    safe_print(f"  registry: {registry_path()}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Review and declare the timezone of OHLCV corpora (Phase-3 clock provenance).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("USAGE\n-----\n", 1)[-1],
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", action="store_true",
                   help="walk --data-dir, hash + detect, write UNREVIEWED drafts")
    g.add_argument("--list", action="store_true", help="list records")
    g.add_argument("--review", metavar="PATH",
                   help="inspect one corpus; add --timezone to declare it")
    ap.add_argument("--data-dir", default="data", help="scan root (default: data)")
    ap.add_argument("--unreviewed", action="store_true", help="--list: only pending records")
    ap.add_argument("--timezone", help="declare: UTC | MT5_SERVER_NY_DST | an IANA zone")
    ap.add_argument("--reviewed-by", help="declare: who reviewed it (required to declare)")
    ap.add_argument("--notes", help="declare: why you concluded this")
    ap.add_argument("--reference", help="path to a UTC corpus to measure against (bootstrap)")
    ap.add_argument("--redetect", action="store_true", help="--review: re-run the detector")
    ap.add_argument("--verbose", action="store_true", help="--review: dump raw test output")
    args = ap.parse_args(argv)

    if args.scan:
        return cmd_scan(args)
    if args.list:
        return cmd_list(args)
    return cmd_review(args)


if __name__ == "__main__":
    raise SystemExit(main())
