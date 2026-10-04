"""rotate_session_log.py — bound the unbounded SESSION LOG (CLAUDE.md §6 / the #3 context-ceiling).

`assistant_project.md` is append-only and ~2,500 lines / 124 entries. Durable conclusions are
already distilled into `docs/current-findings.md` + the memory files, so the old tail is
forensic-replay-only. This keeps the doctrine preamble + the newest `--keep` entries in the hot
file and spills the rest to `docs/analysis/session-log-archive/` (the §6.2-rule-5 history home) —
nothing is deleted, the archive preserves every spilled entry verbatim.

Mirrors `scripts/maintenance/cleanup_logs.py` (argparse, --dry-run, UTF-8 stdout, summary print).
Safety: a marker-count conservation check aborts before any write if parsing would lose an entry.

Usage:
    python scripts/maintenance/rotate_session_log.py [--keep 20] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Force UTF-8 so the 📝 marker + em-dashes print cleanly on Windows (see cleanup_logs.py).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_DEFAULT_LOG = Path("assistant_project.md")
_ARCHIVE_DIR = Path("docs/analysis/session-log-archive")
_MARKER = "📝 SESSION LOG ENTRY"
# Recognise the canonical marker, its emoji-corrupted form (`??`) from older cp1252 round-trips,
# AND the BARE form with no prefix at all. All three are real entries; the first two are repaired
# to `📝` on write (otherwise they hide from the parser and get dumped into the preamble).
#
# 2026-08-26 (CH-measurement-provenance-boundary): the bare form was added after the provenance
# audit measured 90 bare markers in the live log against 78 the parser could see. Running the
# rotator as documented would have swallowed those 90 entries into the doctrine preamble — no
# content deleted, but 90 entries would stop being addressable as entries.
# The `*` also absorbs a doubled prefix — `📝 📝 SESSION LOG ENTRY` really occurs once in the live
# log (an earlier append bug) and was invisible to the parser AND to the old guard. Repaired to a
# single canonical marker on write, the same treatment `??` already gets.
_MARKER_RE = re.compile(r"^(?:(?:📝|\?\?) )*SESSION LOG ENTRY[ \t]*$")

# The conservation guard MUST count with a regex independent of the parser's. Before this change
# both used _MARKER_RE, so the guard compared the parser against itself (78 == 78) and could never
# fire on a marker form the parser did not recognise — a guard structurally blind to the failure it
# existed to catch. This one is deliberately looser: it matches the phrase on its own line whatever
# precedes it.
_LOOSE_MARKER_RE = re.compile(r"^.{0,4}SESSION LOG ENTRY[ \t]*$")
_HR_RE = re.compile(r"^---\s*$")
_DATE_RE = re.compile(
    r"^Date:\s*(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?", re.MULTILINE
)


def _date_key(body: str) -> tuple[int, ...]:
    """(Y, M, D, h, m, s) sort key from the entry's Date line; (0,...) if unparseable."""
    m = _DATE_RE.search(body)
    if not m:
        return (0, 0, 0, 0, 0, 0)
    return tuple(int(g) if g else 0 for g in m.groups())


def _date_str(body: str) -> str:
    k = _date_key(body)
    return f"{k[0]:04d}-{k[1]:02d}-{k[2]:02d}"


def parse_log(text: str) -> tuple[str, list[str]]:
    """Split into (preamble, [entry_body, ...]).

    An entry runs from a standalone `📝 SESSION LOG ENTRY` line to the next `---` (or next marker /
    EOF). Everything else is the doctrine preamble; opening `---` delimiters and trailing blanks are
    stripped so the rebuilt file is clean. The interleaved doctrine block is preserved because the
    terminator is the `---` rule, not the next marker.
    """
    lines = text.splitlines()
    preamble: list[str] = []
    entries: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        if _MARKER_RE.match(lines[i]):
            while preamble and (preamble[-1].strip() == "" or _HR_RE.match(preamble[-1])):
                preamble.pop()  # drop this entry's opening delimiter from the preamble
            body = [_MARKER]  # repair a corrupted `??` marker to the canonical `📝`
            i += 1
            while i < n and not _HR_RE.match(lines[i]) and not _MARKER_RE.match(lines[i]):
                body.append(lines[i])
                i += 1
            if i < n and _HR_RE.match(lines[i]):
                i += 1  # consume the closing delimiter
            entries.append("\n".join(body).rstrip())
        else:
            preamble.append(lines[i])
            i += 1
    while preamble and (preamble[-1].strip() == "" or _HR_RE.match(preamble[-1])):
        preamble.pop()
    return "\n".join(preamble), entries


def render(preamble: str, entries: list[str]) -> str:
    """Rebuild the canonical file: preamble, then each entry wrapped in `---` delimiters."""
    out = [preamble, ""]
    for e in entries:
        out.append("---")
        out.append(e)
    out.append("---")
    return "\n".join(out) + "\n"


def render_archive(entries: list[str], source_name: str = "assistant_project.md") -> str:
    span = f"{_date_str(entries[-1])} … {_date_str(entries[0])}" if entries else "—"
    header = (
        f"# SESSION LOG archive (spilled from {source_name})\n\n"
        f"> Range: {span} · {len(entries)} entries · newest-first.\n"
        "> Spilled by `scripts/maintenance/rotate_session_log.py` to keep the live log bounded\n"
        "> (CLAUDE.md §6 / §6.2 rule 5). Nothing deleted — this is the forensic-replay record.\n"
    )
    return render(header.rstrip(), entries)


def rotate(keep: int, dry_run: bool, *, log_path: Path = _DEFAULT_LOG,
           archive_dir: Path = _ARCHIVE_DIR, prefix: str = "session-log") -> int:
    text = log_path.read_text(encoding="utf-8")
    # Counted with the LOOSE regex, not the parser's — a guard that shares the parser's blind spot
    # cannot detect the parser's blind spot.
    marker_count = sum(1 for ln in text.splitlines() if _LOOSE_MARKER_RE.match(ln))
    preamble, entries = parse_log(text)

    # Conservation guard — abort before any write if parsing dropped/duplicated an entry.
    if len(entries) != marker_count:
        print(f"[ABORT] parsed {len(entries)} entries but a loose scan found {marker_count} "
              "markers — refusing to rewrite (entries the parser cannot see would be swallowed "
              "into the preamble).")
        return 1
    for e in entries:
        if _date_key(e) == (0, 0, 0, 0, 0, 0):
            print(f"[WARN] entry with unparseable Date will sort oldest:\n  {e.splitlines()[:2]}")

    entries.sort(key=_date_key, reverse=True)  # newest-first; normalizes inconsistent order
    kept, spilled = entries[:keep], entries[keep:]

    print(f"Entries: {len(entries)}  |  keep newest: {len(kept)}  |  spill: {len(spilled)}")
    if not spilled:
        print("Nothing to rotate (already within --keep). No-op.")
        return 0

    archive_name = f"{prefix}-{_date_str(spilled[-1])}_to_{_date_str(spilled[0])}.md"
    archive_path = archive_dir / archive_name
    print(f"Archive → {archive_path}")

    if dry_run:
        print("[DRY-RUN] no files written. Re-run without --dry-run to apply.")
        return 0

    assert len(kept) + len(spilled) == len(entries), "conservation check failed"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(render_archive(spilled, source_name=log_path.name), encoding="utf-8")
    log_path.write_text(render(preamble, kept), encoding="utf-8")
    print(f"Done. Live log now {len(kept)} entries; {len(spilled)} archived to {archive_path}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Bound a SESSION LOG file by archiving old entries.")
    ap.add_argument("--keep", type=int, default=20, help="Newest N entries to retain (default 20)")
    ap.add_argument("--dry-run", action="store_true", help="Print the split; write nothing")
    ap.add_argument("--file", default="assistant_project.md",
                    help="Log file to rotate (default assistant_project.md; e.g. llm_project_assistant.md)")
    args = ap.parse_args()
    log_path = Path(args.file)
    if not log_path.exists():
        print(f"[ERROR] {log_path} not found")
        return 1
    # Default codebase log keeps its historical archive dir + prefix; other logs get their own.
    if log_path == _DEFAULT_LOG:
        archive_dir, prefix = _ARCHIVE_DIR, "session-log"
    else:
        archive_dir = Path("docs/analysis") / f"{log_path.stem}-archive"
        prefix = log_path.stem
    return rotate(keep=args.keep, dry_run=args.dry_run, log_path=log_path,
                  archive_dir=archive_dir, prefix=prefix)


if __name__ == "__main__":
    raise SystemExit(main())
