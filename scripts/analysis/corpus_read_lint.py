"""corpus_read_lint.py — shrink-only ratchet over direct (ungated) corpus reads.

Enforcement half of the census in `corpus_read_census.py` (this module imports and reuses
its scan/classification functions directly — never forks the logic). The census answers
"how many direct corpus reads exist"; this answers "did that number just grow."

RATCHET, NOT A ZERO-TOLERANCE GATE (yet)
-----------------------------------------
`docs/governance/corpus_read_allowlist.json` is a frozen snapshot of every `CORPUS`/`UNKNOWN`
finding that existed when the ratchet was armed (2026-09-10). Matched by `durable_key`
(file + enclosing qualname + call name + argument-AST dump — NOT a line number, so an
unrelated edit shifting lines never spuriously fails or passes this check; same precedent as
`feature_math_lint.py`'s own ratchet).

  * A live `CORPUS`/`UNKNOWN` finding whose `durable_key` is NOT in the allowlist -> FAIL.
    This is the only way the check fails: a genuinely NEW ungated read.
  * An allowlist entry whose `durable_key` no longer appears live -> reported as SHRUNK
    (informational only, never a failure) — the site was migrated to `corpus_store.read()`
    or reclassified `GATED`/`DERIVED` with evidence. The allowlist itself must then be
    regenerated to drop it (this script does not auto-rewrite the pin; see --regenerate).
  * `GATED`/`DERIVED` findings are never checked against the allowlist — they are always
    permitted, ratchet or not.

Usage:
    venv/Scripts/python.exe scripts/analysis/corpus_read_lint.py            # check (CI/pre-commit)
    venv/Scripts/python.exe scripts/analysis/corpus_read_lint.py --regenerate  # re-snapshot
        the allowlist to the CURRENT live CORPUS/UNKNOWN set (only ever shrinks it in normal
        use; use --regenerate ONLY immediately after a genuine migration/reclassification —
        never to silently launder a new violation past the check).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.analysis.corpus_read_census import (  # noqa: E402
    CLASS_CORPUS,
    CLASS_UNKNOWN,
    _iter_py_files,
    scan_file,
)

ALLOWLIST_PATH = _ROOT / "docs" / "governance" / "corpus_read_allowlist.json"
SOURCE_CENSUS_TEMPLATE = (
    "docs/governance/build_manifests/corpus_read_census_{date}.json"
)


def _display_path(p: Path) -> str:
    """`p` relative to `_ROOT` when possible, else the absolute path. Display-only formatting
    must never be able to raise -- `relative_to` throws ValueError when `p` isn't under
    `_ROOT` (e.g. a test monkeypatches `_ROOT` to an unrelated tmp dir), and a crash inside a
    print statement is a worse failure mode than an ugly absolute path."""
    try:
        return p.relative_to(_ROOT).as_posix()
    except ValueError:
        return str(p)


def _load_allowlist() -> dict:
    if not ALLOWLIST_PATH.is_file():
        raise SystemExit(
            f"corpus_read_lint: {ALLOWLIST_PATH} does not exist. The ratchet has never been "
            "armed for this checkout -- run with --regenerate once to create it (only after "
            "confirming the current CORPUS/UNKNOWN set is the intended starting point)."
        )
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def _live_findings() -> list[dict]:
    findings: list[dict] = []
    for f in _iter_py_files():
        findings.extend(scan_file(f))
    return [r for r in findings if r["class"] in (CLASS_CORPUS, CLASS_UNKNOWN)]


def check() -> int:
    allowlist = _load_allowlist()
    pinned = {e["durable_key"]: e for e in allowlist["entries"]}
    live = _live_findings()
    live_by_key = {r["durable_key"]: r for r in live}

    new_violations = [r for r in live if r["durable_key"] not in pinned]
    shrunk = [e for e in allowlist["entries"] if e["durable_key"] not in live_by_key]

    if shrunk:
        print(f"INFO: {len(shrunk)} pinned site(s) no longer read a corpus directly "
              "(migrated or reclassified) -- allowlist can be shrunk:")
        for e in shrunk[:20]:
            print(f"  [SHRUNK ] {e['file']}:{e['line']} {e['qualname']} {e['call']}()")
        if len(shrunk) > 20:
            print(f"  ... and {len(shrunk) - 20} more")
        print(f"  Run with --regenerate to re-snapshot the allowlist to the current set.\n")

    if new_violations:
        print(f"FAIL: {len(new_violations)} NEW direct corpus read(s) not in "
              f"{_display_path(ALLOWLIST_PATH)}:")
        for r in new_violations:
            print(f"  [{r['class']:8s}] {r['file']}:{r['line']} {r['qualname']} "
                  f"{r['call']}()  -- {r['evidence']}")
        print(
            "\nEvery corpus read must resolve through "
            "data_ingestion.corpus_store.read()/corpus_gate.admit_corpus() (or one of the "
            "two annotated exceptions: corpus_store.build itself, and "
            "data_ingestion.clock_detector.py, which must inspect raw bytes to establish "
            "clock provenance before any gate that requires it can run). If this site is "
            "provably already gated or is not actually a corpus read, reclassify it with "
            "evidence rather than adding it here — growing this list is never legitimate."
        )
        return 1

    print(f"PASS: 0 new direct corpus reads (allowlist: {len(pinned)} pinned, "
          f"{len(shrunk)} shrinkable, {len(live)} live).")
    return 0


def regenerate() -> int:
    from datetime import datetime, timezone

    live = _live_findings()
    entries = [
        {"durable_key": r["durable_key"], "file": r["file"], "line": r["line"],
         "qualname": r["qualname"], "call": r["call"], "class": r["class"]}
        for r in live
    ]
    entries.sort(key=lambda e: (e["file"], e["line"]))
    dupes = len(entries) - len({e["durable_key"] for e in entries})
    if dupes:
        raise SystemExit(f"corpus_read_lint --regenerate: {dupes} duplicate durable_key "
                          "collision(s) in the live scan -- census bug, not a data problem.")

    old = _load_allowlist() if ALLOWLIST_PATH.is_file() else None
    old_count = old["entry_count"] if old else 0
    # Carry forward any per-entry `note` (a deliberate-exception rationale, e.g.
    # "independent oracle, do not migrate") for a durable_key that survives the
    # re-snapshot. --regenerate rebuilds every OTHER field from the live scan; a note is
    # documentation about a DECISION already made, not derived data, and must not be
    # silently erased just because the site's line number moved.
    old_notes = {e["durable_key"]: e["note"] for e in (old or {}).get("entries", []) if "note" in e}
    for e in entries:
        if e["durable_key"] in old_notes:
            e["note"] = old_notes[e["durable_key"]]
    frozen_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = {
        "version": 2,
        "description": (old or {}).get("description", (
            "Shrink-only ratchet allowlist for scripts/analysis/corpus_read_lint.py. "
            "Matched by durable_key (file + enclosing qualname + call name + "
            "argument-expression AST dump, with a stable -occN suffix disambiguating "
            "textually-identical duplicate calls in one function). The lint fails on "
            "any CORPUS/UNKNOWN finding whose durable_key is not listed here -- growing "
            "this list is never legitimate; shrinking it (migrate to "
            "corpus_store.read(), or reclassify to GATED/DERIVED with evidence in the "
            "same commit) is the only permitted edit. GATED and DERIVED sites are never "
            "listed -- they are always permitted regardless of this file."
        )),
        "frozen_at": frozen_at,
        "source_census": SOURCE_CENSUS_TEMPLATE.format(date=date_stamp),
        "match_key": "durable_key",
        "entry_count": len(entries),
        "entries": entries,
    }
    ALLOWLIST_PATH.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Regenerated {_display_path(ALLOWLIST_PATH)}: "
          f"{old_count} -> {len(entries)} entries "
          f"({'shrunk' if len(entries) < old_count else 'grew' if len(entries) > old_count else 'unchanged'} "
          f"by {abs(len(entries) - old_count)}).")
    if len(entries) > old_count:
        print("WARNING: the allowlist GREW. --regenerate is meant to record a shrink after "
              "a real migration/reclassification -- confirm this growth is legitimate "
              "(new files added to the repo, not a laundered violation) before committing it.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regenerate", action="store_true",
                     help="re-snapshot the allowlist to the current live CORPUS/UNKNOWN set")
    args = ap.parse_args(argv)
    return regenerate() if args.regenerate else check()


if __name__ == "__main__":
    sys.exit(main())
