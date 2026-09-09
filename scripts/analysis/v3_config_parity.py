#!/usr/bin/env python
"""v3_config_parity.py — prove v3 is decision-identical to v2, and that emission is neutral.

CH-v3-unified-market-structure-v1. OBSERVATION / VERIFICATION ONLY — writes nothing into the
repository's governed surfaces and never touches `configs/production/ACTIVE_VERSION`.

WHAT IT PROVES
--------------
Two independent claims, each a byte-comparison of a real backtest ledger:

  A. **Requirement 9 (compatibility).** `v2_htfcrt_2026_08` and
     `v3_unified_market_structure_2026_09` produce byte-identical `*_events.jsonl` and
     `*_crt_telemetry.jsonl`, and `*_trades.csv` / `*_summary.json` identical on every field
     EXCEPT `config_version`. v3 differs from v2 only by three new hash-neutral top-level
     sections, so any other divergence means one of them leaked into a decision.

     The `config_version` carve-out is not a loosened gate. The ledger stamps the config it
     ran under on every trade row; two different configs producing the same stamp would be a
     provenance defect. Measured on the XAUUSD corpus, that stamp is the ONLY difference —
     85 of 86 trade columns and every non-volatile summary key match exactly.

  B. **Requirements 4 and 5 (observation only).** v3 with `bar_structure_snapshot.enabled` TRUE
     produces the same artifacts as v3 with it FALSE — here `config_version` must match too,
     since both arms are the same config — while actually emitting a non-empty snapshot
     stream. Both halves matter: identical ledgers alone would also be satisfied by an emitter
     that silently did nothing, so the run is only accepted if the ON arm wrote rows.

WHY IT DOES NOT FLIP `ACTIVE_VERSION`
-------------------------------------
`PROD_VERSION` is resolved ONCE at import (`production_config.py:82`) from
`configs/production/ACTIVE_VERSION`, and that pointer path is RELATIVE to the process working
directory (`production_config.py:57`). Flipping the shared pointer in place would be visible to
every other process running against this repository for the duration of a multi-minute
backtest — and this repository is routinely worked by several concurrent sessions.

So each arm instead runs in its own isolated ROOT: a scratch directory holding a real copy of
`configs/` (2 MB — with its own one-line ACTIVE_VERSION) plus directory JUNCTIONS to the large
shared trees (`data/`, `models/`, `src/`, `scripts/`). The subprocess runs with `cwd` set to
that root, so it reads its own pointer and nothing else on the machine can observe the choice.
Junctions need no elevation on Windows; on POSIX the same structure is built with symlinks.

USAGE
    python scripts/analysis/v3_config_parity.py --instrument XAUUSD
"""

from __future__ import annotations

import argparse
import csv
import filecmp
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V2 = "v2_htfcrt_2026_08"
V3 = "v3_unified_market_structure_2026_09"

#: Shared trees each isolated root links to rather than copies. `configs` is deliberately
#: absent — it is the one tree that must be a real, independently-writable copy.
LINKED_TREES = ("data", "models", "src", "scripts")


def _link_dir(src: Path, dst: Path) -> None:
    """Directory junction (Windows) or symlink (POSIX). Junctions avoid the developer-mode /
    elevation requirement that plain Windows directory symlinks carry."""
    if platform.system() == "Windows":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            check=True, capture_output=True,
        )
    else:
        os.symlink(src, dst, target_is_directory=True)


def build_root(tmp: Path, name: str, version: str, *, emit: bool) -> Path:
    """One isolated run root pinned to `version`, with snapshot emission forced on/off."""
    root = tmp / name
    root.mkdir(parents=True)
    shutil.copytree(REPO / "configs", root / "configs")
    for tree in LINKED_TREES:
        _link_dir(REPO / tree, root / tree)
    (root / "logs").mkdir()
    (root / "results").mkdir()

    (root / "configs" / "production" / "ACTIVE_VERSION").write_text(
        version + "\n", encoding="utf-8"
    )

    # Force the emit flag in THIS root's copy only. The repository's own v3 config keeps its
    # default of false; nothing here can change what the committed config says.
    cfg_path = root / "configs" / "production" / f"{version}.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if "bar_structure_snapshot" in cfg:
        cfg["bar_structure_snapshot"]["enabled"] = bool(emit)
        cfg["bar_structure_snapshot"]["output_dir"] = str(root / "logs" / "bar_structure")
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif emit:
        raise SystemExit(f"{version} has no bar_structure_snapshot section; cannot emit")
    return root


def run_arm(root: Path, corpus_rel: str, instrument: str) -> Path:
    """Run one backtest inside `root` and return its result directory.

    `corpus_rel` is deliberately a path RELATIVE to the root (resolving through the junctioned
    `data/` tree to the same bytes for every arm). It is not a convenience: `dataset_integrity`
    enforces that a corpus lives under a canonical `data/` root and is named
    `{symbol}_{timeframe}.csv` with a reviewed clock record (F-039's L3 gate, F-066's clock
    provenance). A scratch copy elsewhere is REJECTED — correctly — which is also why this
    harness has no corpus-truncation option: there is no way to shorten the corpus that the
    integrity layer would accept, and bypassing that layer to make a parity run faster would
    trade away the very guarantee the run exists to establish.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "runtime.backtest_v2",
         "--csv", corpus_rel, "--instrument", instrument, "--output", str(root / "results")],
        cwd=str(root), env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:] + "\n" + proc.stderr[-4000:] + "\n")
        raise SystemExit(f"backtest failed in {root.name} (exit {proc.returncode})")
    runs = sorted((root / "results").glob(f"*_{instrument}"))
    if not runs:
        raise SystemExit(f"no result directory produced in {root.name}")
    return runs[-1]


#: Keys that legitimately differ between two sequential runs of the SAME decision logic.
VOLATILE_SUMMARY_KEYS = (
    "run_id", "timestamp", "generated_at", "started_at", "finished_at", "duration_sec",
)

#: The ledger stamps the config version it ran under, on every trade row and in the summary.
#: Across the v2-vs-v3 arm this column MUST differ — a ledger recording the same version for
#: two different configs would be a provenance defect, not a parity success. So it is excluded
#: there and REQUIRED to match everywhere else, which is why `expect_version_stamp_differs` is
#: an explicit per-arm argument rather than a blanket skip.
VERSION_STAMP_COLUMN = "config_version"


def _compare_trades(pa: Path, pb: Path, *, ignore: tuple) -> tuple:
    """Column-wise trade comparison -> (identical_ignoring, differing_columns)."""
    with pa.open(encoding="utf-8", newline="") as fa, pb.open(encoding="utf-8", newline="") as fb:
        ra, rb = list(csv.DictReader(fa)), list(csv.DictReader(fb))
    if len(ra) != len(rb):
        return False, [f"<row count {len(ra)} vs {len(rb)}>"]
    if not ra:
        return True, []
    cols = set(ra[0]) | set(rb[0])
    differing = sorted(c for c in cols if any(x.get(c) != y.get(c) for x, y in zip(ra, rb)))
    return all(c in ignore for c in differing), differing


def compare(a: Path, b: Path, instrument: str, label: str,
            *, expect_version_stamp_differs: bool) -> bool:
    """Compare the decision-bearing artifacts of two arms.

    `events.jsonl` and `crt_telemetry.jsonl` are compared BYTE-for-byte: they carry no version
    stamp, so any difference at all is a decision difference. `trades.csv` and `summary.json`
    both embed `config_version`, so they are compared field-wise with that one stamp handled
    explicitly per arm (see VERSION_STAMP_COLUMN). Volatile wall-clock keys are stripped —
    treating a differing timestamp as a decision difference would make the gate meaningless.
    """
    ok = True
    ignore = (VERSION_STAMP_COLUMN,) if expect_version_stamp_differs else ()
    print(f"\n  {label}")

    for artifact in ("events.jsonl", "crt_telemetry.jsonl"):
        pa, pb = a / f"{instrument}_{artifact}", b / f"{instrument}_{artifact}"
        if not pa.exists() and not pb.exists():
            print(f"    - {artifact:<20} both absent -> OK")
            continue
        if pa.exists() != pb.exists():
            print(f"    X {artifact:<20} present in only one arm")
            ok = False
            continue
        same = filecmp.cmp(pa, pb, shallow=False)
        print(f"    {'OK' if same else 'X '} {artifact:<20} "
              f"{'byte-identical' if same else 'DIVERGED'} ({pa.stat().st_size:,} bytes)")
        ok = ok and same

    pa, pb = a / f"{instrument}_trades.csv", b / f"{instrument}_trades.csv"
    if not pa.exists() and not pb.exists():
        print(f"    - {'trades.csv':<20} both absent (no trades) -> OK")
    elif pa.exists() != pb.exists():
        print(f"    X {'trades.csv':<20} present in only one arm")
        ok = False
    else:
        same, differing = _compare_trades(pa, pb, ignore=ignore)
        extra = [c for c in differing if c not in ignore]
        note = "all columns identical" if not differing else (
            f"identical except {differing}" if same else f"DIVERGED on {extra}")
        print(f"    {'OK' if same else 'X '} {'trades.csv':<20} {note}")
        ok = ok and same

    sa = json.loads((a / f"{instrument}_summary.json").read_text(encoding="utf-8"))
    sb = json.loads((b / f"{instrument}_summary.json").read_text(encoding="utf-8"))
    for key in VOLATILE_SUMMARY_KEYS + ignore:
        sa.pop(key, None)
        sb.pop(key, None)
    same = sa == sb
    print(f"    {'OK' if same else 'X '} {'summary.json':<20} {'identical' if same else 'DIVERGED'}")
    if not same:
        for k in sorted(set(sa) | set(sb)):
            if sa.get(k) != sb.get(k):
                print(f"        {k}: {sa.get(k)!r} != {sb.get(k)!r}")
    return ok and same


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--csv", default=None,
                    help="corpus path RELATIVE to the repo root; default data/mt5/<INSTRUMENT>_M15.csv")
    ap.add_argument("--keep", action="store_true", help="keep the scratch roots for inspection")
    args = ap.parse_args()

    corpus_rel = args.csv or f"data/mt5/{args.instrument}_M15.csv"
    if not (REPO / corpus_rel).exists():
        raise SystemExit(f"corpus not found: {REPO / corpus_rel}")

    tmp = Path(tempfile.mkdtemp(prefix="v3_parity_"))
    print(f"scratch roots: {tmp}")
    print(f"corpus       : {corpus_rel} (via junctioned data/)")
    try:
        arms = {
            "v2_baseline": build_root(tmp, "v2_baseline", V2, emit=False),
            "v3_emit_off": build_root(tmp, "v3_emit_off", V3, emit=False),
            "v3_emit_on": build_root(tmp, "v3_emit_on", V3, emit=True),
        }
        out = {}
        for name, root in arms.items():
            print(f"\nrunning {name} ...", flush=True)
            out[name] = run_arm(root, corpus_rel, args.instrument)
            print(f"  -> {out[name]}")

        a_ok = compare(out["v2_baseline"], out["v3_emit_off"], args.instrument,
                       "A. v2_htfcrt_2026_08  vs  v3 (emit OFF)   [requirement 9]",
                       expect_version_stamp_differs=True)
        b_ok = compare(out["v3_emit_off"], out["v3_emit_on"], args.instrument,
                       "B. v3 emit OFF  vs  v3 emit ON            [requirements 4 and 5]",
                       expect_version_stamp_differs=False)

        # Non-vacuity: an emitter that wrote nothing would pass B trivially.
        stream = arms["v3_emit_on"] / "logs" / "bar_structure" / f"{args.instrument}_bar_structure.jsonl"
        rows = sum(1 for _ in stream.open(encoding="utf-8")) if stream.exists() else 0
        print(f"\n  Non-vacuity: snapshot stream rows = {rows:,}")
        if rows == 0:
            print("    X emission produced no rows -- claim B is vacuous")
        nv_ok = rows > 0

        print("\n" + "=" * 68)
        verdict = "PASS" if (a_ok and b_ok and nv_ok) else "FAIL"
        print(f"  v3 CONFIG PARITY: {verdict}")
        print(f"    compatibility with v2 (req 9)     : {'PASS' if a_ok else 'FAIL'}")
        print(f"    decision neutrality (req 4, 5)    : {'PASS' if b_ok else 'FAIL'}")
        print(f"    emission non-vacuity              : {'PASS' if nv_ok else 'FAIL'}")
        print("=" * 68)
        return 0 if verdict == "PASS" else 1
    finally:
        if args.keep:
            print(f"\nscratch roots kept at {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
