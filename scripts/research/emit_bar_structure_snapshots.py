#!/usr/bin/env python
"""emit_bar_structure_snapshots.py — produce the per-bar BarStructureSnapshot stream.

CH-v3-unified-market-structure-v1. SEM-035. Thin CLI wrapper: all logic lives in
`src/utils/isolated_config_root.py` and `src/runtime/bar_structure_snapshot.py`.

WHAT IT DOES
------------
Runs one backtest under `v3_unified_market_structure_2026_09` with
`bar_structure_snapshot.enabled` forced true, in an ISOLATED config root so the repository's
`ACTIVE_VERSION` is never touched (see `isolated_config_root`'s docstring for why that matters
here). The resulting JSONL stream is copied to a stable destination and, when pyarrow is
available, projected to parquet and VERIFIED.

AUTHORITY MODEL
---------------
JSONL is the system of record; the parquet file is a regenerable PROJECTION and never a second
authority (`CC-PARQUET-PROJECTION`). The projection is only kept if `verify_projection` returns
clean — a parquet file that does not round-trip is deleted rather than left on disk, because a
silently-wrong projection is worse than no projection.

The stream this writes carries no economic claim. It records what the declared vocabulary said
at each bar; whether any of it is worth anything is the separate question
`MC-CTXATTR-XAUUSD-M15-V1` exists to answer.

USAGE
    python scripts/research/emit_bar_structure_snapshots.py --instrument XAUUSD
    python scripts/research/emit_bar_structure_snapshots.py --instrument XAUUSD --out logs/bar_structure
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.isolated_config_root import build_config_root, run_backtest  # noqa: E402

V3 = "v3_unified_market_structure_2026_09"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--config", default=V3, help=f"production config version (default {V3})")
    ap.add_argument("--csv", default=None,
                    help="corpus path RELATIVE to the repo root; default data/mt5/<INSTRUMENT>_M15.csv")
    ap.add_argument("--out", default="logs/bar_structure",
                    help="destination directory for the JSONL stream (relative to repo root)")
    ap.add_argument("--no-parquet", action="store_true",
                    help="skip the parquet projection even when pyarrow is available")
    args = ap.parse_args()

    corpus_rel = args.csv or f"data/mt5/{args.instrument}_M15.csv"
    if not (REPO / corpus_rel).exists():
        raise SystemExit(f"corpus not found: {REPO / corpus_rel}")

    dest_dir = (REPO / args.out).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{args.instrument}_bar_structure.jsonl"
    if dest.exists():
        # Append-mode emission means a stale file would silently double the corpus. Refuse
        # rather than clobber: the previous stream may already be cited by a measurement run.
        raise SystemExit(
            f"{dest} already exists. Move or delete it first -- this script will not overwrite "
            "a stream that an existing measurement result may already cite."
        )

    tmp = Path(tempfile.mkdtemp(prefix="bar_structure_"))
    try:
        stream_dir = tmp / "emit" / "logs" / "bar_structure"

        def _enable(cfg: dict) -> None:
            if "bar_structure_snapshot" not in cfg:
                raise SystemExit(f"{args.config} has no bar_structure_snapshot section")
            cfg["bar_structure_snapshot"]["enabled"] = True
            cfg["bar_structure_snapshot"]["output_dir"] = str(stream_dir)

        print(f"config    : {args.config} (isolated root; ACTIVE_VERSION untouched)")
        print(f"corpus    : {corpus_rel}")
        root = build_config_root(REPO, tmp / "emit", args.config, mutate_config=_enable)
        print("running backtest ...", flush=True)
        result_dir = run_backtest(REPO, root, corpus_rel, args.instrument)
        print(f"  ledger  : {result_dir}")

        produced = stream_dir / f"{args.instrument}_bar_structure.jsonl"
        if not produced.exists():
            raise SystemExit("no snapshot stream was produced (emission did not run)")
        shutil.copy2(produced, dest)
        rows = sum(1 for _ in dest.open(encoding="utf-8"))
        size_mb = dest.stat().st_size / 1048576
        print(f"  stream  : {dest}  ({rows:,} rows, {size_mb:,.1f} MB)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if args.no_parquet:
        print("  parquet : skipped (--no-parquet)")
        return 0

    from utils.parquet_store import compact_jsonl, parquet_available, verify_projection

    if not parquet_available():
        # Not an error: pyarrow is an optional extra (`pyproject.toml` [parquet]) and every
        # read path degrades to JSONL. The record of truth is already written.
        print("  parquet : SKIPPED -- pyarrow not installed (pip install 'pyarrow'); "
              "JSONL is the system of record and is complete")
        return 0

    print("  parquet : projecting ...", flush=True)
    manifest = compact_jsonl(dest, partition_by="crt_state_after", compression="zstd")
    report = verify_projection(dest)
    if not report["ok"]:
        # A projection that does not round-trip is deleted, not shipped. `parquet_store`'s own
        # tests exist because a reordered flatten group scrambles vectors with no error
        # anywhere -- a silently-wrong projection is strictly worse than none.
        proj = Path(manifest["dest"]) if "dest" in manifest else None
        if proj is not None and proj.exists():
            shutil.rmtree(proj, ignore_errors=True) if proj.is_dir() else proj.unlink()
        print(f"  parquet : FAILED verification ({report['mismatches']} mismatches) -- removed")
        print(f"            first: {report.get('first_mismatch')}")
        return 1
    print(f"  parquet : OK, verified {report['rows']:,} rows round-trip clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
