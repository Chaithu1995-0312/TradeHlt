#!/usr/bin/env python
"""query_trace.py — DuckDB query surface over Trace / research Parquet projections.

READ-ONLY. DESCRIPTIVE ONLY. No p-value/verdict/economic claim.

Opens ephemeral DuckDB views over Parquet sidecars produced by
`scripts/maintenance/jsonl_to_parquet.py` (backed by `src/utils/parquet_store.py`).
JSONL remains the system of record; projections are regenerable. This script does
NOT migrate `query_decision_atlas.py` onto the shared helper — that atlas stays on
its own path.

Family vocabulary matches `jsonl_to_parquet.FAMILY_DEFAULTS` suffixes
(crt_construction, crt_telemetry, events, opportunities, clean_labels, bar_structure).
Globs cover both `logs/` and `results/` layouts measured in-repo.

USAGE
    venv/Scripts/python.exe scripts/analysis/query_trace.py --list
    venv/Scripts/python.exe scripts/analysis/query_trace.py --family crt_construction
    venv/Scripts/python.exe scripts/analysis/query_trace.py --sql "select count(*) from crt_construction"
"""
from __future__ import annotations

import argparse
import glob as _glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from utils.duckdb_query import duckdb_available, open_views  # noqa: E402

# Family key -> glob(s) that locate Parquet projections under logs/ and results/.
# Keys align with FAMILY_DEFAULTS vocabulary (suffix without leading underscore /
# .jsonl). Partitioned projections are directories named `*.parquet` containing
# `key=value/part-0.parquet`; single-file projections are plain `*.parquet` files.
FAMILY_GLOBS: dict[str, tuple[str, ...]] = {
    "crt_construction": (
        "logs/**/*_crt_construction.parquet",
        "results/**/*_crt_construction.parquet",
    ),
    "crt_telemetry": (
        "results/**/*_crt_telemetry.parquet",
        "logs/**/*_crt_telemetry.parquet",
    ),
    "events": (
        "results/**/*_events.parquet",
        "logs/**/*_events.parquet",
    ),
    "opportunities": (
        "logs/**/opportunities.parquet",
        "results/**/opportunities.parquet",
    ),
    "clean_labels": (
        "results/**/clean_labels.parquet",
        "logs/**/clean_labels.parquet",
    ),
    "bar_structure": (
        "logs/**/*_bar_structure.parquet",
        "results/**/*_bar_structure.parquet",
    ),
}


def _read_parquet_glob(projection: Path) -> str:
    """DuckDB read_parquet argument for a single-file or partitioned projection."""
    if projection.is_dir():
        # Hive-style partitions: <name>.parquet/<key>=<value>/part-0.parquet
        return (projection / "**" / "*.parquet").as_posix()
    return projection.as_posix()


def discover_projections(families: list[str] | None = None) -> dict[str, list[Path]]:
    """Return family -> existing projection paths (files or partitioned dirs)."""
    wanted = list(FAMILY_GLOBS) if families is None else list(families)
    found: dict[str, list[Path]] = {}
    for fam in wanted:
        if fam not in FAMILY_GLOBS:
            raise SystemExit(
                f"unknown family {fam!r}; choose from: {', '.join(FAMILY_GLOBS)}"
            )
        paths: list[Path] = []
        for pattern in FAMILY_GLOBS[fam]:
            for hit in _glob.glob(str(ROOT / pattern), recursive=True):
                p = Path(hit)
                # glob may hit part-0.parquet inside a partitioned dir; keep the
                # projection root (the *.parquet file OR the *.parquet directory).
                if p.is_file() and p.parent.name.endswith(".parquet"):
                    p = p.parent
                if p.name.endswith(".parquet") and p not in paths:
                    paths.append(p)
        if paths:
            found[fam] = sorted(paths)
    return found


def _default_report(con, families: list[str]) -> None:
    print("=== projection presence (row counts) ===")
    for fam in families:
        try:
            n = con.execute(f"select count(*) as n from {fam}").fetchone()[0]
            cols = [r[0] for r in con.execute(f"describe {fam}").fetchall()]
            print(f"  {fam}: rows={n:,}  cols={len(cols)}")
        except Exception as exc:  # noqa: BLE001 - descriptive surface, keep going
            print(f"  {fam}: ERROR — {exc}")

    if "crt_construction" in families:
        print("\n=== crt_construction by engine_state_after (stratum) ===")
        print(
            con.execute(
                """
                select engine_state_after, phase, count(*) as n
                from crt_construction
                group by 1, 2
                order by n desc
                """
            )
            .df()
            .to_string(index=False)
        )

    if "bar_structure" in families:
        print("\n=== bar_structure by crt_state_after (stratum) ===")
        try:
            print(
                con.execute(
                    """
                    select crt_state_after, count(*) as n
                    from bar_structure
                    group by 1
                    order by n desc
                    """
                )
                .df()
                .to_string(index=False)
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  (skipped: {exc})")

    print("\nDESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--family",
        action="append",
        dest="families",
        choices=sorted(FAMILY_GLOBS),
        help="Family to open (repeatable). Default: all with an existing projection.",
    )
    ap.add_argument("--list", action="store_true", help="List families and projection paths.")
    ap.add_argument("--sql", help="Run one ad-hoc SQL query against the open views and exit.")
    args = ap.parse_args(argv)

    discovered = discover_projections(args.families)
    if args.list:
        if not discovered:
            print("no projections found for the requested families")
            print("build with: python scripts/maintenance/jsonl_to_parquet.py --glob ...")
            return 1
        for fam, paths in discovered.items():
            print(f"{fam}:")
            for p in paths:
                kind = "dir" if p.is_dir() else "file"
                print(f"  [{kind}] {p.relative_to(ROOT).as_posix()}")
        return 0

    if not discovered:
        print("no projections found — run jsonl_to_parquet.py first, or pass --list")
        return 1

    if not duckdb_available():
        print("duckdb is not installed — install it with `pip install tradelatest[parquet]`.")
        return 2

    # One view per family: if multiple projections match, prefer the first (sorted)
    # and print a note. Multi-file UNION is out of scope for this thin surface.
    table_globs: dict[str, str] = {}
    for fam, paths in discovered.items():
        if len(paths) > 1:
            print(
                f"note: {fam} has {len(paths)} projections; using {paths[0].relative_to(ROOT)}"
            )
        table_globs[fam] = _read_parquet_glob(paths[0])

    con = open_views(table_globs, read_only=True)

    if args.sql:
        con.execute(args.sql).df().to_string(sys.stdout)
        print()
        return 0

    _default_report(con, list(table_globs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
