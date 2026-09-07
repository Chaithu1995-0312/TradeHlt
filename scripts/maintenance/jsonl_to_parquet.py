"""
jsonl_to_parquet.py — build Parquet projections over JSONL research corpora.

Thin CLI wrapper. All logic lives in `src/utils/parquet_store.py` (conventions: scripts
never define business logic). The JSONL source is never modified or deleted — a projection
is an additive sidecar that any reader may ignore.

Family defaults encode what was MEASURED about each corpus, so callers do not have to
rediscover it:

  crt_telemetry     17 of 28 columns sparse across disjoint `kind` values -> partition by kind
  events            polymorphic `metadata` blob                           -> partition by event
  opportunities     a leading `run_header` row with a different shape     -> skipped
  clean_labels      35 dense columns incl. a per-row feature vector       -> no partitioning
  bar_structure     engine CRT state stratum                              -> partition by crt_state_after
  crt_construction  observation sidecar (schemas.md §9.17); measured
                    columns TBD — no production enabled:true run yet      -> partition by engine_state_after

Usage:
    python scripts/maintenance/jsonl_to_parquet.py <path> [--verify]
    python scripts/maintenance/jsonl_to_parquet.py --glob "results/**/*_crt_telemetry.jsonl" --verify
    python scripts/maintenance/jsonl_to_parquet.py <path> --dry-run
"""
from __future__ import annotations

import argparse
import glob as _glob
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from utils.console_safe import safe_print as print  # noqa: E402, A001 - cp1252 guard
from utils.parquet_store import (  # noqa: E402
    compact_jsonl,
    parquet_available,
    projection_path,
    projection_status,
)

# Family -> (partition_by, skip_predicate). Matched against the file name.
FAMILY_DEFAULTS: dict[str, tuple] = {
    "_crt_telemetry.jsonl": ("kind", None),
    "_events.jsonl": ("event", None),
    "opportunities.jsonl": (None, lambda rec: rec.get("type") == "run_header"),
    "clean_labels.jsonl": (None, None),
    # CH-v3-unified-market-structure-v1. Partitioned on the ENGINE CRT state because the
    # attribution program (SEM-036) reads strictly per-stratum: its primary metric is an
    # overlay delta computed INSIDE each CRT state, so partition pruning matches the access
    # pattern exactly. Warmup rows carry crt_state_after=null and land in their own partition,
    # which is the honest placement -- they have no engine state, rather than a RANGE one.
    "_bar_structure.jsonl": ("crt_state_after", None),
    # Partition by engine_state_after like `_bar_structure.jsonl` (research per CRT-state
    # stratum). Measured columns TBD — no production enabled:true run yet (schemas.md §9.17).
    "_crt_construction.jsonl": ("engine_state_after", None),
}

# Foreign `*_events` look-alikes (analytics schema registry §2.3). They share the
# `_events.jsonl` suffix but are NOT the runtime-events population: different
# owner / population / cardinality / measurement meaning / decision rights
# (GT-3). Never let them project into the `events` family.
EVENTS_FAMILY_EXCLUDE = {
    "integrity_events.jsonl",                # {event,payload,severity,source,ts}
    "secondlow_prospective_events.jsonl",    # {collected_at,hypothesis_id,detector,...}
}


def resolve_family(path: Path) -> tuple:
    """(partition_by, skip_predicate) for *path*, from its family suffix."""
    name = path.name
    if name in EVENTS_FAMILY_EXCLUDE:
        # Foreign *_events look-alike — unpartitioned, unlabelled; NOT the events family.
        return (None, None)
    for suffix, opts in FAMILY_DEFAULTS.items():
        if name.endswith(suffix):
            return opts
    return (None, None)


def _fmt(n: int) -> str:
    return f"{n / 1048576:,.1f} MB"


def convert_one(path: Path, args: argparse.Namespace) -> dict:
    partition_by, skip_predicate = resolve_family(path)
    if args.partition_by is not None:
        partition_by = args.partition_by or None
    manifest = compact_jsonl(
        path,
        partition_by=partition_by,
        skip_predicate=skip_predicate,
        compression=args.compression,
        verify=args.verify,
    )
    ratio = manifest["bytes_in"] / max(manifest["bytes_out"], 1)
    print(
        f"  {path.name}: {manifest['rows']:,} rows  "
        f"{_fmt(manifest['bytes_in'])} -> {_fmt(manifest['bytes_out'])}  ({ratio:.1f}x)"
        + (f"  partitions={len(manifest['partitions'])}" if partition_by else "")
    )
    if args.verify:
        v = manifest["verified"]
        status = "VERIFIED" if v["ok"] else "MISMATCH"
        print(f"    round-trip: {status}  rows={v['rows']:,}  mismatches={v['mismatches']}")
        if not v["ok"]:
            print(f"    first mismatch: {v['first_mismatch']}")
    return manifest


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="Build Parquet projections over JSONL corpora.")
    ap.add_argument("paths", nargs="*", help="JSONL file(s) to project")
    ap.add_argument("--glob", help="glob pattern selecting a whole family (recursive)")
    ap.add_argument("--verify", action="store_true", help="round-trip check every record")
    ap.add_argument("--dry-run", action="store_true", help="list targets and current status only")
    ap.add_argument("--partition-by", help="override the family default ('' disables)")
    ap.add_argument("--compression", default="zstd")
    args = ap.parse_args(argv)

    targets = [Path(p) for p in args.paths]
    if args.glob:
        targets += [Path(p) for p in _glob.glob(args.glob, recursive=True)]
    targets = [p for p in dict.fromkeys(targets) if p.suffix == ".jsonl"]
    if not targets:
        ap.error("no .jsonl targets (pass paths and/or --glob)")

    if not parquet_available() and not args.dry_run:
        print("pyarrow is not installed — install it with `pip install tradelatest[parquet]`.")
        return 2

    if args.dry_run:
        print(f"{len(targets)} target(s):")
        for p in targets:
            size = p.stat().st_size if p.exists() else 0
            partition_by, skip = resolve_family(p)
            print(
                f"  {p}  {_fmt(size)}  status={projection_status(p)}  "
                f"partition_by={partition_by or '-'}  skip_header={'yes' if skip else 'no'}"
                f"  -> {projection_path(p).name}"
            )
        return 0

    total_in = total_out = 0
    failures = 0
    print(f"converting {len(targets)} file(s)")
    for p in targets:
        if not p.exists():
            print(f"  {p}: MISSING — skipped")
            failures += 1
            continue
        try:
            m = convert_one(p, args)
        except Exception as exc:  # noqa: BLE001 - report and continue the batch
            print(f"  {p}: FAILED — {exc}")
            failures += 1
            continue
        total_in += m["bytes_in"]
        total_out += m["bytes_out"]
        if args.verify and not m["verified"]["ok"]:
            failures += 1

    if total_in:
        print(
            f"total: {_fmt(total_in)} -> {_fmt(total_out)}  "
            f"({total_in / max(total_out, 1):.1f}x, saved {_fmt(total_in - total_out)})"
        )
    if failures:
        print(f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
