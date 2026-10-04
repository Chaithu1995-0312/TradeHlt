"""Commit-linkage guard: a commit that changes governed code must ship a same-day SESSION LOG entry.

This operationalizes the FORWARD half of the CLAUDE.md §6 Persistent Logging Mandate that a
pytest structurally cannot — responses are not durable artifacts, but commits are. The split:

  - tests/test_session_log.py (the timeless floor): every entry that EXISTS is well-formed.
  - THIS check (the forward mandate): an entry must EXIST, dated today, for a governed change.

Together they cover *malformed* + *missing*. It deliberately does NOT (and cannot) check that the
belief recorded is *true* — that residual stays doctrine (CLAUDE.md §6.1).

Trigger scope (per the approved plan + user guardrails):
  - Fires only when the staged diff touches GOVERNED paths: src/** or configs/production/**.
    Pure docs/tests/scripts/config-elsewhere changes are exempt (a belief-line on a README edit
    is noise).
  - Honors a `[nolog]` escape token in the commit message for trivial refactors.

Wired as a `commit-msg` hook (the earliest stage where the message — hence `[nolog]` — exists).
Usage: ``python scripts/maintenance/check_session_log_commit.py <commit-msg-file>``; exits non-zero
with a human-readable reason to abort the commit. The pure helpers are git-free so they unit-test
deterministically (tests/test_session_log_commit_check.py).
"""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

# A change under one of these prefixes is "governed" and requires a logged belief.
_GOVERNED_PREFIXES = ("src/", "configs/production/")

_LOG_PATH = "assistant_project.md"
_NOLOG_RE = re.compile(r"\[nolog\]", re.IGNORECASE)

# Mirror of tests/test_session_log.py (kept self-contained so the hook has no test-dir import).
_MARKER_RE = re.compile(r"^📝 SESSION LOG ENTRY[ \t]*$", re.MULTILINE)
_CORE_FIELDS = ("Date", "Topic", "Decision/Output", "Open Questions", "Next Step")
_DATE_RE = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def _norm(path: str) -> str:
    return path.replace("\\", "/").strip().strip('"')


def requires_log(changed_paths: list[str]) -> bool:
    """True if any staged path is under a governed prefix (src/** or configs/production/**)."""
    return any(_norm(p).startswith(_GOVERNED_PREFIXES) for p in changed_paths)


def has_nolog_escape(commit_message: str) -> bool:
    return bool(_NOLOG_RE.search(commit_message))


def _blocks(log_text: str) -> list[str]:
    starts = [m.start() for m in _MARKER_RE.finditer(log_text)]
    return [log_text[s : (starts[i + 1] if i + 1 < len(starts) else len(log_text))]
            for i, s in enumerate(starts)]


def _entry_is_well_formed(block: str, today_iso: str) -> bool:
    if not all(re.search(rf"^{re.escape(f)}:", block, re.MULTILINE) for f in _CORE_FIELDS):
        return False
    m = _DATE_RE.search(block)
    return bool(m) and m.group(1) == today_iso


def has_valid_today_entry(log_text: str, today_iso: str) -> bool:
    """A well-formed SESSION LOG entry dated today exists somewhere in the log.

    Tolerant of the log's historically-inconsistent ordering: we require that *an* entry for
    today is present and well-formed, not that it is positionally first.
    """
    return any(_entry_is_well_formed(b, today_iso) for b in _blocks(log_text))


def check(
    changed_paths: list[str],
    commit_message: str,
    log_text: str,
    today_iso: str,
) -> tuple[bool, str]:
    """Pure decision. Returns (ok, reason). ok=True means allow the commit."""
    if not requires_log(changed_paths):
        return True, "no governed paths changed — log not required"
    if has_nolog_escape(commit_message):
        return True, "[nolog] escape present — log skipped by author"
    if has_valid_today_entry(log_text, today_iso):
        return True, f"governed change has a well-formed SESSION LOG entry dated {today_iso}"
    return False, (
        "governed change (src/** or configs/production/**) committed without a same-day SESSION "
        f"LOG entry in {_LOG_PATH}.\n"
        f"  Add a well-formed 📝 SESSION LOG ENTRY dated {today_iso} (CLAUDE.md §6/§7.4),\n"
        "  or append [nolog] to the commit message for a trivial refactor."
    )


# ── git wiring (impure) ──────────────────────────────────────────────────────


def _staged_paths() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    ).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def _staged_log_text() -> str:
    """The STAGED content of the session log (what is actually being committed), with fallbacks."""
    blob = subprocess.run(
        ["git", "show", f":{_LOG_PATH}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if blob.returncode == 0 and blob.stdout:
        return blob.stdout
    p = Path(_LOG_PATH)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def main(argv: list[str]) -> int:
    commit_message = ""
    if len(argv) > 1:
        msg_file = Path(argv[1])
        if msg_file.exists():
            commit_message = msg_file.read_text(encoding="utf-8")
    ok, reason = check(
        _staged_paths(), commit_message, _staged_log_text(), _dt.date.today().isoformat()
    )
    if not ok:
        sys.stderr.write("SESSION LOG commit-linkage check FAILED:\n" + reason + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
