"""
build_rr_dataset.py
===================
Build and save RR dataset JSON from either:

  (A) Opportunity Scanner JSONL — RECOMMENDED (unbiased, no FeaturePipeline needed)
      py build_rr_dataset.py --opportunities logs/opportunities_EURUSD.jsonl
      py build_rr_dataset.py --opportunities logs/opportunities_*.jsonl

  (B) Trades CSVs — legacy biased source (only CRT-accepted trades)
      py build_rr_dataset.py --csv results/batch/AUDUSD_M15/AUDUSD_M15_trades.csv
      py build_rr_dataset.py --dir results/batch
      py build_rr_dataset.py --glob "results/**/*_trades.csv"

The --opportunities path bypasses FeaturePipeline entirely: features are already
pre-computed in each JSONL record's "features" dict.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time as _time
from pathlib import Path
from typing import List, Dict

# Ensure src/ is on sys.path when run from repo root
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.rr.rr_dataset_builder import (
    build_dataset,
    save_dataset,
    extract_features,
    extract_target,
    validate_dataset_integrity,
    MIN_SAMPLES,
    N_FEATURES,
)


# ── JSONL (opportunity scanner) path ─────────────────────────────────────────

def _read_run_id_from_jsonl(path: str) -> str:
    """Return run_id from the first-line run_header, or empty string."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            rec = json.loads(fh.readline().strip())
        if rec.get("type") == "run_header":
            return rec.get("run_id", "")
    except Exception:
        pass
    return ""


def _load_jsonl(paths: List[str]) -> List[dict]:
    """Load opportunity scanner JSONL files, return list of records.
    Skips run_header lines (type == "run_header") automatically.
    """
    records: List[dict] = []
    for p in paths:
        print("Loading JSONL:", p)
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("type") == "run_header":
                            continue   # skip run_header sentinel
                        records.append(rec)
                    except json.JSONDecodeError:
                        pass   # skip malformed lines silently
        except OSError as exc:
            print(f"  Warning: cannot read {p}: {exc}")
    return records


def _build_from_opportunities(records: List[dict], output: str,
                               version: str | None = None,
                               register: bool = True,
                               instrument: str = "",
                               run_id: str = "") -> None:
    """
    Build RR dataset directly from opportunity JSONL records.

    Each record already has:
      record["features"]    → 35-dim canonical feature dict
      record["rr_achieved"] → float RR label
      record["outcome"]     → "TP_HIT" / "SL_HIT" / "TIMEOUT"

    No FeaturePipeline run needed — features are pre-computed by the scanner.
    Saves a versioned copy and registers in rr_registry.json when register=True.
    """
    X:     List[List[float]] = []
    y_rr:  List[float]       = []
    y_win: List[int]         = []
    skipped = 0

    for rec in records:
        feats_dict = rec.get("features")
        if not isinstance(feats_dict, dict):
            skipped += 1
            continue
        try:
            vec       = extract_features(feats_dict)        # list[float] len=35
            rr, win   = extract_target(rec, feats_dict)     # rr_achieved + outcome
            X.append(vec)
            y_rr.append(rr)
            y_win.append(win)
        except Exception:
            skipped += 1
            continue   # skip bad records; errors surfaced in summary

    if skipped:
        print(f"  Skipped {skipped} records (missing features / bad RR)")

    if len(X) < MIN_SAMPLES:
        raise SystemExit(
            f"Insufficient data: {len(X)} valid records "
            f"(minimum {MIN_SAMPLES}). "
            f"Run the opportunity scanner first to generate JSONL files."
        )

    validate_dataset_integrity(X, y_rr, y_win)

    # ── save canonical output ────────────────────────────────────────────────
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    save_dataset(X, y_rr, y_win, output)
    print(f"Saved RR dataset ({len(X)} samples, {N_FEATURES} features) -> {output}")

    # ── save versioned copy + register ───────────────────────────────────────
    if register:
        _register_dataset(X, y_rr, y_win, output, version,
                          instrument=instrument, run_id=run_id)


def _register_dataset(X, y_rr, y_win, canonical_output: str,
                      version: str | None,
                      instrument: str = "",
                      run_id: str = "") -> None:
    """Save versioned dataset file and register in rr_registry.json (fail-open)."""
    try:
        ver = version or _time.strftime("%Y%m_v1")
        out_path = Path(canonical_output)
        versioned_path = out_path.parent / f"rr_dataset_{ver}.json"
        versioned_path.parent.mkdir(parents=True, exist_ok=True)
        save_dataset(X, y_rr, y_win, str(versioned_path))
        print(f"Saved versioned dataset -> {versioned_path}")

        from core.model_registry import register_rr_dataset, promote_rr, get_active_rr
        register_rr_dataset(ver, str(versioned_path), len(X), N_FEATURES,
                            instrument=instrument or None,
                            run_id=run_id or None)
        print(f"Registered in rr_registry: {ver}")

        # Auto-promote if no active version exists yet
        if get_active_rr() is None:
            ok, reason = promote_rr(ver)
            print(f"Auto-promoted: {reason}")
    except Exception as e:
        print(f"  Warning: rr_registry update failed (non-fatal): {e}")


# ── Trades-CSV (legacy) path ──────────────────────────────────────────────────

def _collect_csv_paths(args) -> List[str]:
    if args.csv:
        return [args.csv]
    if args.dir:
        return glob.glob(os.path.join(args.dir, "**", "*_trades.csv"), recursive=True)
    if args.glob:
        return glob.glob(args.glob, recursive=True)
    # fallback: newest trades csv under results/
    paths = glob.glob("results/**/*_trades.csv", recursive=True)
    paths = sorted(paths, key=lambda p: os.path.getmtime(p), reverse=True)
    return paths[:1]


def _load_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Build RR dataset from opportunity JSONL (recommended) or trades CSVs (legacy). "
            "Use --opportunities for unbiased training data from the opportunity scanner."
        )
    )
    # Unbiased source (recommended)
    ap.add_argument(
        "--opportunities", nargs="+", metavar="JSONL",
        help="One or more opportunities_*.jsonl files from Opportunity Scanner "
             "(unbiased — bypasses FeaturePipeline)",
    )
    # Legacy biased source
    ap.add_argument("--csv",  help="Path to a single *_trades.csv (legacy)")
    ap.add_argument("--dir",  help="Directory to scan for *_trades.csv (legacy, recursive)")
    ap.add_argument("--glob", help="Glob pattern for trades CSVs (legacy)")
    # Output
    ap.add_argument(
        "--output", default=None,
        help="Canonical output dataset path. When omitted and --instrument is provided, "
             "auto-derives from JSONL run_header: "
             "models/{instrument}/{run_id}/rr_dataset.json",
    )
    # Versioning
    ap.add_argument(
        "--version", default=None,
        help="Version key for rr_registry.json (auto-generates YYYYMM_v1 if omitted)",
    )
    ap.add_argument(
        "--no-register", dest="register", action="store_false", default=True,
        help="Skip saving versioned copy and updating rr_registry.json",
    )
    ap.add_argument(
        "--instrument", default="",
        help="Instrument label (e.g. EURUSD). When provided, output is run-scoped: "
             "models/{instrument}/{run_id}/rr_dataset.json",
    )
    ap.add_argument(
        "--run-id", "--run", dest="run_id", default=None,
        help="Run ID for path scoping (e.g. 20260519_113806). "
             "When given with --instrument and no --opportunities, "
             "auto-resolves logs/{instrument}/{run_id}/opportunities.jsonl.",
    )
    args = ap.parse_args()

    # ── Auto-resolve --opportunities from --instrument + --run-id ────────────
    if not args.opportunities and not args.csv and not args.dir and not args.glob:
        if args.instrument and args.run_id:
            auto_path = Path("logs") / args.instrument / args.run_id / "opportunities.jsonl"
            if not auto_path.exists():
                raise SystemExit(
                    f"Auto-resolved opportunities path not found: {auto_path}\n"
                    f"Run the scanner first or pass --opportunities explicitly."
                )
            args.opportunities = [str(auto_path)]
            print(f"Auto-resolved opportunities: {auto_path}")

    # ── JSONL path (unbiased — preferred) ────────────────────────────────────
    if args.opportunities:
        # Resolve run_id from JSONL run_header
        _run_id = args.run_id or ""
        if not _run_id:
            _run_id = _read_run_id_from_jsonl(args.opportunities[0])
        if not _run_id:
            _run_id = _time.strftime("%Y%m%d_%H%M%S")

        # Resolve output path — run-scoped when instrument is given
        if args.output is None:
            if args.instrument and _run_id:
                output = str(Path("models") / args.instrument / _run_id / "rr_dataset.json")
            elif args.instrument:
                output = str(Path("models") / f"rr_dataset_{args.instrument}.json")
            else:
                output = "models/rr_dataset.json"
        else:
            output = args.output

        records = _load_jsonl(args.opportunities)
        print(f"Total opportunity records loaded: {len(records)}")
        _build_from_opportunities(records, output,
                                  version=args.version, register=args.register,
                                  instrument=args.instrument,
                                  run_id=_run_id)
        return

    # ── CSV path (legacy biased) ──────────────────────────────────────────────
    paths = _collect_csv_paths(args)
    if not paths:
        raise SystemExit(
            "No trades CSV found. Use --opportunities (recommended) or --csv / --dir."
        )

    trades: List[Dict[str, str]] = []
    for p in paths:
        print("Loading:", p)
        trades.extend(_load_csv(p))

    csv_output = args.output or "models/rr_dataset.json"
    print(f"Total trades loaded: {len(trades)}")
    X, y_rr, y_win = build_dataset(trades)
    Path(csv_output).parent.mkdir(parents=True, exist_ok=True)
    save_dataset(X, y_rr, y_win, csv_output)
    print(f"Saved RR dataset -> {csv_output}")
    if args.register:
        _register_dataset(X, y_rr, y_win, csv_output, args.version)


if __name__ == "__main__":
    main()
