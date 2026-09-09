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

RUN IDENTITY IS NOT INFERRED
----------------------------
`crt_construction` and `bar_structure` are per-bar sidecars of ONE BacktestRunner pass and are
joinable only on `(run_id, bar_index)` WITHIN that pass. Several emits of the same instrument
match the same globs, so binding a family to whichever path sorts first would silently pair two
different runs -- a join that returns 0 rows at exit 0. Pass `--run-dir` to scope every family
to one emit; without it, an ambiguous family is a hard error, never a quiet pick.

USAGE
    venv/Scripts/python.exe scripts/analysis/query_trace.py --list
    venv/Scripts/python.exe scripts/analysis/query_trace.py --run-dir logs/dual_construction_full_gapfix
    venv/Scripts/python.exe scripts/analysis/query_trace.py --family crt_construction
    venv/Scripts/python.exe scripts/analysis/query_trace.py --sql "select count(*) from crt_construction"
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
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
    # NOT a JSONL family: `build_bar_matrix.py` writes this Parquet directly beside a
    # canonical CSV, so it has no `jsonl_to_parquet` FAMILY_DEFAULTS entry and no projection
    # manifest. Its own run manifest records whether the optional writer actually ran --
    # see `_bar_matrix_parquet_ok`. CSV stays canonical there.
    "bar_matrix": (
        "results/research/bar_matrix/**/bar_matrix.parquet",
    ),
}

# Families that are direct Parquet artifacts rather than JSONL projections. They are exempt
# from the projection-manifest verification check and carry their own admissibility rule.
_NON_PROJECTION_FAMILIES = ("bar_matrix",)

# Exclude non-events-population files from the `events` view (GT-3).
# These share the `*_events.parquet` glob but are distinct populations
# (integrity events, secondlow prospective events) — mixing them would
# silently coalesce three schemas into one family.
NON_EVENTS_FAMILY_PREFIXES = ("integrity_events", "secondlow_prospective_events")


def _bar_matrix_parquet_ok(projection: Path) -> "tuple[bool, str]":
    """(admissible, reason) for a `bar_matrix.parquet`.

    `build_bar_matrix.py` treats CSV as canonical and `to_parquet` as optional: a missing
    engine records `parquet_written: false` and keeps going. Reporting such a directory as a
    DuckDB-ready family would present a skipped write as a completed one.
    """
    manifest = projection.parent / "manifest.json"
    if not manifest.exists():
        return False, f"no manifest.json beside {projection.name}"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"unreadable manifest.json: {exc}"
    if data.get("parquet_written") is not True:
        reason = data.get("parquet_skipped_reason", "parquet_written is not true")
        return False, f"CSV is canonical here; parquet not written ({reason})"
    return True, ""


def _projection_verified(projection: Path) -> "tuple[bool, str]":
    """(admissible, reason) for a JSONL-derived projection, read from its manifest.

    A projection whose round-trip FAILED is still fully readable on disk, so refusing it here
    is what keeps a failed check from being indistinguishable from a passed one. Manifests
    written before MANIFEST_VERSION 1.1 carry no `verified` block at all; those are reported
    as unverified rather than assumed good.
    """
    manifest = Path(str(projection) + ".manifest.json")
    if not manifest.exists():
        return False, f"no projection manifest beside {projection.name}"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"unreadable projection manifest: {exc}"
    verified = data.get("verified")
    if verified is None:
        return False, (
            "manifest carries no `verified` block -- rebuild with "
            "`jsonl_to_parquet.py --verify`"
        )
    if not verified.get("ok"):
        return False, (
            f"round-trip FAILED ({verified.get('mismatches')} mismatches) -- "
            "JSONL is the system of record; discard this projection"
        )
    return True, ""


def admissible(fam: str, projection: Path) -> "tuple[bool, str]":
    """Whether *projection* may back a queryable view. Fail closed on anything unproven."""
    if fam in _NON_PROJECTION_FAMILIES:
        return _bar_matrix_parquet_ok(projection)
    return _projection_verified(projection)


def _read_parquet_glob(projection: Path) -> str:
    """DuckDB read_parquet argument for a single-file or partitioned projection."""
    if projection.is_dir():
        # Hive-style partitions: <name>.parquet/<key>=<value>/part-0.parquet
        return (projection / "**" / "*.parquet").as_posix()
    return projection.as_posix()


def discover_projections(
    families: list[str] | None = None,
    *,
    run_dir: "str | Path | None" = None,
) -> dict[str, list[Path]]:
    """Return family -> existing projection paths (files or partitioned dirs).

    *run_dir* restricts every family to projections under that directory, so all views come
    from ONE emit. Without it a family may resolve to several runs; resolving that ambiguity
    is the caller's job (see `select_projections`), never this function's.
    """
    wanted = list(FAMILY_GLOBS) if families is None else list(families)
    scope = None
    if run_dir is not None:
        scope = Path(run_dir)
        if not scope.is_absolute():
            scope = ROOT / scope
        scope = scope.resolve()
        if not scope.is_dir():
            raise SystemExit(f"--run-dir is not a directory: {run_dir}")
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
                if scope is not None and not p.resolve().is_relative_to(scope):
                    continue
                # Exclude non-events-population files from the `events` view (GT-3).
                if p.name.startswith(NON_EVENTS_FAMILY_PREFIXES):
                    continue
                # glob may hit part-0.parquet inside a partitioned dir; keep the
                # projection root (the *.parquet file OR the *.parquet directory).
                if p.is_file() and p.parent.name.endswith(".parquet"):
                    p = p.parent
                if p.name.endswith(".parquet") and p not in paths:
                    paths.append(p)
        if paths:
            found[fam] = sorted(paths)
    return found


class AmbiguousRunError(SystemExit):
    """A family resolved to projections from more than one emit and no --run-dir was given."""


def select_projections(
    discovered: dict[str, list[Path]], *, run_dir_scoped: bool
) -> dict[str, Path]:
    """Resolve each family to exactly ONE admissible projection, or fail closed.

    Two refusals, both deliberate:
      * ambiguity  -- >1 projection and no --run-dir: refuse rather than bind paths[0],
        which would silently pair two different runs across views.
      * unproven   -- a projection whose manifest does not attest a passing round-trip
        (or, for bar_matrix, whose run manifest says the writer was skipped).
    """
    chosen: dict[str, Path] = {}
    for fam, paths in sorted(discovered.items()):
        ok_paths, rejected = [], []
        for p in paths:
            good, why = admissible(fam, p)
            (ok_paths if good else rejected).append((p, why))
        for p, why in rejected:
            print(f"REFUSED {fam}: {p.relative_to(ROOT).as_posix()} -- {why}")
        if not ok_paths:
            continue
        if len(ok_paths) > 1 and not run_dir_scoped:
            listing = "\n".join(
                f"    {p.relative_to(ROOT).as_posix()}" for p, _ in ok_paths
            )
            raise AmbiguousRunError(
                f"family {fam!r} resolves to {len(ok_paths)} projections from different "
                f"emits:\n{listing}\n"
                "  Views from different runs do not join on (run_id, bar_index) -- the join "
                "would return 0 rows without saying so.\n"
                "  Re-run with --run-dir <one emit directory>."
            )
        chosen[fam] = ok_paths[0][0]
    return chosen


class LineageConflictError(SystemExit):
    """Two open views disagree on run identity, or one view spans more than one run."""


def _bar_matrix_lineage(projection: Path) -> dict:
    """corpus_sha256 for a bar_matrix view, read from its sibling run manifest.

    `bar_matrix.parquet` carries no run_id/corpus_sha256 COLUMNS (confirmed: its header
    has neither) -- its lineage lives in `manifest.json` beside it, written by
    `build_bar_matrix.py`. Treated as attributable-by-corpus, not by run: bar_matrix has
    no run_id concept at all, it is a per-corpus artifact.
    """
    manifest = projection.parent / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"run_ids": [], "corpus_shas": [], "attributable": False}
    sha = data.get("corpus_sha256")
    return {
        "run_ids": [],
        "corpus_shas": [sha] if sha else [],
        "attributable": bool(sha),
    }


def assert_view_lineage(con, selected: dict[str, Path]) -> dict:
    """Read run_id / corpus_sha256 straight OUT OF the opened views and refuse to proceed
    if they disagree. This is what makes lineage a CHECKED invariant rather than a
    convention `--run-dir` merely encourages: it does not trust the directory name or the
    caller's scoping -- it reads the columns every view actually carries.

    Two views can each be internally consistent (one run_id, one corpus_sha256) and still
    have been opened from DIFFERENT emits if `--run-dir` was not scoped tightly enough, or
    if a family's glob ever matches a directory holding more than one run (something
    `select_projections`'s path-level ambiguity check cannot see, because it operates on
    paths, not on the data inside them). This function is the check that operates on the
    data.

    Returns a lineage report `{fam: {"run_ids": [...], "corpus_shas": [...],
    "attributable": bool}}`. Raises `LineageConflictError` (refuses to proceed) when:
      * any single view spans MORE THAN ONE run_id or corpus_sha256 (a directory that
        turned out to hold two runs);
      * two ATTRIBUTABLE views disagree on run_id or corpus_sha256.
    A view carrying neither column (`events`, `crt_telemetry` today) is UNATTRIBUTABLE --
    reported by name, never silently treated as compatible with the attributable views.
    """
    report: dict[str, dict] = {}
    for fam, path in selected.items():
        if fam == "bar_matrix":
            report[fam] = _bar_matrix_lineage(path)
            continue
        cols = {r[0] for r in con.execute(f"describe {fam}").fetchall()}
        run_ids: list[str] = []
        shas: list[str] = []
        if "run_id" in cols:
            run_ids = [
                r[0] for r in con.execute(
                    f"select distinct run_id from {fam} where run_id is not null"
                ).fetchall()
            ]
        if "corpus_sha256" in cols:
            shas = [
                r[0] for r in con.execute(
                    f"select distinct corpus_sha256 from {fam} where corpus_sha256 is not null"
                ).fetchall()
            ]
        report[fam] = {
            "run_ids": run_ids,
            "corpus_shas": shas,
            "attributable": bool(run_ids or shas),
        }

    # 1. a single view spanning more than one run_id or corpus_sha256.
    internally_split = {
        fam: r for fam, r in report.items()
        if len(r["run_ids"]) > 1 or len(r["corpus_shas"]) > 1
    }
    if internally_split:
        lines = [
            f"    {fam}: run_ids={r['run_ids']} corpus_shas={r['corpus_shas']}"
            for fam, r in internally_split.items()
        ]
        raise LineageConflictError(
            "view(s) span MORE THAN ONE run -- a family's projection directory holds "
            "records from different emits:\n" + "\n".join(lines) +
            "\n  --run-dir alone cannot catch this; it scopes by PATH, not by the "
            "run_id/corpus_sha256 actually inside the files."
        )

    # 2. two attributable views disagreeing on run_id or corpus_sha256.
    attributable = {fam: r for fam, r in report.items() if r["attributable"]}
    run_id_sets = {fam: frozenset(r["run_ids"]) for fam, r in attributable.items() if r["run_ids"]}
    sha_sets = {fam: frozenset(r["corpus_shas"]) for fam, r in attributable.items() if r["corpus_shas"]}
    if len(set(run_id_sets.values())) > 1:
        raise LineageConflictError(
            "attributable views disagree on run_id:\n" +
            "\n".join(f"    {fam}: {sorted(v)}" for fam, v in run_id_sets.items()) +
            "\n  Views from different runs do not join on (run_id, bar_index) -- the "
            "join would return rows silently pairing the wrong bars, or zero rows, "
            "either way without saying so."
        )
    if len(set(sha_sets.values())) > 1:
        raise LineageConflictError(
            "attributable views disagree on corpus_sha256:\n" +
            "\n".join(f"    {fam}: {sorted(v)}" for fam, v in sha_sets.items())
        )

    unattributable = sorted(fam for fam, r in report.items() if not r["attributable"])
    run_id = next(iter(next(iter(run_id_sets.values()), frozenset())), None)
    corpus = next(iter(next(iter(sha_sets.values()), frozenset())), None)
    print(
        f"lineage: run_id={run_id or 'n/a'}  corpus={((corpus or '')[:12] + '...') if corpus else 'n/a'}"
        f"  views={','.join(sorted(attributable))}"
    )
    print(f"         UNATTRIBUTABLE (no run identity in-record): {','.join(unattributable) or '(none)'}")
    return report


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
    ap.add_argument(
        "--run-dir",
        help="Scope every family to projections under this directory (ONE emit). "
             "Required whenever a family matches projections from more than one run.",
    )
    args = ap.parse_args(argv)

    discovered = discover_projections(args.families, run_dir=args.run_dir)
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

    # One view per family, chosen fail-closed: ambiguity across emits and unverified
    # projections are refusals, not notes. Multi-file UNION stays out of scope here.
    selected = select_projections(discovered, run_dir_scoped=args.run_dir is not None)
    if not selected:
        print("no admissible projections — see REFUSED lines above")
        return 1
    for fam, path in selected.items():
        print(f"view {fam}: {path.relative_to(ROOT).as_posix()}")
    table_globs = {fam: _read_parquet_glob(p) for fam, p in selected.items()}

    con = open_views(table_globs, read_only=True)
    assert_view_lineage(con, selected)

    if args.sql:
        con.execute(args.sql).df().to_string(sys.stdout)
        print()
        return 0

    _default_report(con, list(table_globs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
