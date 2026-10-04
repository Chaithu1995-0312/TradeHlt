"""check_consolidation_due.py — advisory growth monitor for the always-loaded substrate.

The volume analogue of the time-based freshness gate (tests/test_current_findings.py::
test_nonterminal_findings_are_fresh). Rotation bounds the session log; this nudges when the OTHER
substrate grows past a soft threshold: the findings ledger, the memory index, and archive shards.

ADVISORY by default (exit 0) — findings/memory legitimately grow, so this never blocks. `--strict`
exits 1 if any signal is DUE (opt-in CI gate). Wired non-blocking into hooks/commit-msg so every
commit prints any nudge without aborting.

Mirrors scripts/maintenance/cleanup_logs.py / rotate_session_log.py (argparse, UTF-8 stdout). The
pure `evaluate()` is git/IO-free for deterministic unit tests; `main()` gathers repo counts.

Usage:
    python scripts/maintenance/check_consolidation_due.py [--strict] [--findings-max N] ...
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_LOG = Path("assistant_project.md")
_CLAUDE_MD = Path("CLAUDE.md")
_ARCHIVE_GLOB = "docs/analysis/session-log-archive/session-log-*.md"

_MARKER_RE = re.compile(r"^📝 SESSION LOG ENTRY[ \t]*$", re.MULTILINE)
_INDEX_ROW_RE = re.compile(r"^\|\s*F-\d{3}\s*\|", re.MULTILINE)

# name -> (default threshold, remedy)
_SIGNALS = {
    "session_log": (25, "python scripts/maintenance/rotate_session_log.py"),
    "findings":    (30, "review docs/current-findings.md — retire/supersede settled findings, "
                        "move point-in-time detail to docs/analysis/"),
    "memory":      (45, "run the consolidate-memory skill over ~/.claude/.../memory"),
    "archive":     (12, "merge the oldest docs/analysis/session-log-archive/ shards"),
}


class Signal(NamedTuple):
    name: str
    count: int | None        # None → not measurable here (e.g. memory dir absent)
    threshold: int
    due: bool
    remedy: str


def evaluate(counts: dict[str, int | None], thresholds: dict[str, int]) -> list[Signal]:
    """Pure: a Signal per known metric. DUE iff a measured count strictly exceeds its threshold."""
    out: list[Signal] = []
    for name, (default_thr, remedy) in _SIGNALS.items():
        thr = thresholds.get(name, default_thr)
        count = counts.get(name)
        due = count is not None and count > thr
        out.append(Signal(name, count, thr, due, remedy))
    return out


def _default_memory_dir() -> Path:
    # Mirror the harness slug: "D:\Tradelatest" -> "D--Tradelatest".
    slug = str(Path.cwd().resolve()).replace(":", "-").replace("\\", "-").replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory"


def _gather(memory_dir: Path | None) -> dict[str, int | None]:
    log_n = len(_MARKER_RE.findall(_LOG.read_text(encoding="utf-8"))) if _LOG.exists() else 0
    find_n = len(_INDEX_ROW_RE.findall(_CLAUDE_MD.read_text(encoding="utf-8"))) if _CLAUDE_MD.exists() else 0
    arch_n = len(list(Path().glob(_ARCHIVE_GLOB)))
    mem_n: int | None = None
    md = memory_dir or _default_memory_dir()
    if md.is_dir():
        mem_n = sum(1 for p in md.glob("*.md") if p.name != "MEMORY.md")
    return {"session_log": log_n, "findings": find_n, "memory": mem_n, "archive": arch_n}


def _report(signals: list[Signal]) -> int:
    due = [s for s in signals if s.due]
    print("Consolidation check (advisory):")
    for s in signals:
        shown = "n/a" if s.count is None else f"{s.count}/{s.threshold}"
        tag = "DUE " if s.due else ("--- " if s.count is None else "OK  ")
        line = f"  {tag}{s.name:<12} {shown}"
        if s.due:
            line += f"  → {s.remedy}"
        print(line)
    print(f"\n{len(due)} signal(s) due." if due else "\nNothing due — substrate is lean.")
    return len(due)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Advisory: is the loaded substrate due for consolidation?")
    for name, (thr, _) in _SIGNALS.items():
        ap.add_argument(f"--{name.replace('_', '-')}-max", type=int, default=thr,
                        dest=f"{name}_max", help=f"{name} threshold (default {thr})")
    ap.add_argument("--memory-dir", type=Path, default=None, help="override memory dir location")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any signal is DUE (CI gate)")
    args = ap.parse_args(argv)

    thresholds = {name: getattr(args, f"{name}_max") for name in _SIGNALS}
    signals = evaluate(_gather(args.memory_dir), thresholds)
    n_due = _report(signals)
    return 1 if (args.strict and n_due) else 0


if __name__ == "__main__":
    raise SystemExit(main())
