"""
build_context.py  —  the Context Compiler ("Compile" trigger)
=============================================================
Regenerate the **Portable Mind**: a small set of derived context files under context/ that you
paste into any external model (DeepSeek / Gemini / ChatGPT / Claude) so they share one reality.

WHY (MULTI_LLM_PROTOCOL.md §5 rule 1): context/*.md are a DERIVED VIEW, never a source of truth.
The truth lives in CLAUDE.md, docs/current-findings.md, configs/production/ACTIVE_VERSION, and the
queue. This script reads those canonical sources and renders the views. It does not duplicate or
fork them — edit the source, then re-Compile. context/*.md is gitignored (a disposable export).

Mirrors scripts/analysis/gen_citation_map.py: stdlib only, deterministic (no timestamps; same
inputs -> byte-identical output), GENERATED header stamped on every file, `--check` mode.

Outputs (context/):
  01_GLOBAL_CONTEXT.md       <- docs/architecture/goal.md + CLAUDE.md Project Summary + doctrine map
  02_CURRENT_STATE.md        <- ACTIVE_VERSION + branch + latest SESSION LOG + NEXT_10 from the queue
  03_FINDINGS.md             <- docs/current-findings.md (non-terminal) + Repository Truths Index
  04_DEPENDENCY_AND_INTENT.md<- docs/intent/* titles + pointers to the generated maps
  05_HANDOFF.md              <- protocol summary + role one-liners + HANDOFF.md live state

Usage:
  python scripts/context/build_context.py            # write context/*.md
  python scripts/context/build_context.py --check     # print all files to stdout, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUT_DIR = _REPO_ROOT / "context"

# Optional: the multi-LLM discussion digest (context/06). Guarded so the compiler still runs
# even if src/ is unavailable (e.g. the script copied elsewhere) — falls back to a placeholder.
sys.path.insert(0, str(_REPO_ROOT / "src"))
try:
    from multi_llm.discussion import render_digest_from_ledger as _discussion_digest
except Exception:  # noqa: BLE001
    _discussion_digest = None

_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_GOAL = _REPO_ROOT / "docs" / "architecture" / "goal.md"
_FINDINGS = _REPO_ROOT / "docs" / "current-findings.md"
_ACTIVE_VERSION = _REPO_ROOT / "configs" / "production" / "ACTIVE_VERSION"
_SESSION_LOG = _REPO_ROOT / "assistant_project.md"
_QUEUE = _REPO_ROOT / "multi_llm" / "build_queue.jsonl"
_HANDOFF = _REPO_ROOT / "HANDOFF.md"
_INTENT_DIR = _REPO_ROOT / "docs" / "intent"
_ROLES_DIR = _REPO_ROOT / "multi_llm" / "roles"
_LEDGER = _REPO_ROOT / "multi_llm" / "turn_ledger.jsonl"

_SESSION_ENTRIES = 5      # how many recent SESSION LOG entries to surface
_NEXT_STEPS = 10          # NEXT_10_STEPS


# --------------------------------------------------------------------------- helpers
def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _between(text: str, start_contains: str, stop_prefixes: tuple[str, ...]) -> str:
    """Lines from the one containing `start_contains` up to (excluding) the next line that
    startswith any of `stop_prefixes`. Empty string if the start marker is absent."""
    lines = text.splitlines()
    out: list[str] = []
    capturing = False
    for ln in lines:
        if not capturing:
            if start_contains in ln:
                capturing = True
                out.append(ln)
            continue
        if any(ln.startswith(p) for p in stop_prefixes):
            break
        out.append(ln)
    return "\n".join(out).strip()


def _git_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _header(title: str, sources: list[Path]) -> str:
    src = ", ".join(p.relative_to(_REPO_ROOT).as_posix() for p in sources)
    return (
        f"# {title}\n\n"
        "> **GENERATED — do not edit by hand.** Regenerate with "
        "`python scripts/context/build_context.py` (the `Compile` trigger).\n"
        ">\n"
        "> A *derived view*, not a source of truth (MULTI_LLM_PROTOCOL.md §2: Shared Context is "
        "never authoritative on conflict). Edit the source, then re-Compile.\n"
        f">\n> **Sources:** {src}\n"
    )


def _recent_session_entries(n: int) -> list[dict]:
    text = _read(_SESSION_LOG)
    if not text:
        return []
    blocks = [b for b in re.split(r"^---\s*$", text, flags=re.MULTILINE)
              if "SESSION LOG ENTRY" in b]
    out: list[dict] = []
    for b in blocks[-n:]:
        def _field(label: str) -> str:
            m = re.search(rf"^{label}:\s*(.+)$", b, flags=re.MULTILINE)
            return m.group(1).strip() if m else ""
        out.append({"date": _field("Date"), "topic": _field("Topic"),
                    "next": _field("Next Step")})
    return out


def _queue_pending(n: int) -> list[dict]:
    text = _read(_QUEUE)
    if not text:
        return []
    rows = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    pending = [r for r in rows if r.get("status") == "pending"]
    return pending[:n]


def _first_heading(text: str) -> str:
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            return s.lstrip("# ").strip()
    return ""


# --------------------------------------------------------------------------- renderers
def _render_global() -> str:
    goal = _between(_read(_GOAL), "## 1. The goal in one paragraph",
                    ("## 2.", "## 1.1", "---")) or "[goal.md §1 not found]"
    summary = _between(_read(_CLAUDE_MD), "## 1. Project Summary",
                       ("## 2.", "---")) or "[CLAUDE.md §1 not found]"
    parts = [_header("01 · Global Context", [_GOAL, _CLAUDE_MD])]
    parts.append("## Goal (plain language)\n\n" + goal)
    parts.append("## What the system is\n\n" + summary)
    parts.append(
        "## Operating doctrines (full text in CLAUDE.md — read there, do not re-derive)\n\n"
        "- §4.0 ORIENT_RUNTIME + Runtime Truth Precedence (branch-scoped, file-driven)\n"
        "- §6.1 Intelligence Compounding (zero intelligence loss; goal-first ROI)\n"
        "- §6.2 Repository Truth Maintenance (zero silent truth divergence)\n"
        "- §6.5 Config-First + Authority Ladder (evidence > doctrine; authority is earned)\n"
        "- §12 Trigger Vocabulary · §13 Multi-LLM Layer\n"
    )
    return "\n\n".join(parts).rstrip() + "\n"


def _render_current_state() -> str:
    active = _read(_ACTIVE_VERSION).strip() or "[ACTIVE_VERSION not found]"
    branch = _git_branch()
    parts = [_header("02 · Current State", [_ACTIVE_VERSION, _SESSION_LOG, _QUEUE])]
    parts.append(
        "## Runtime truth (Tier 0)\n\n"
        f"- **ACTIVE_VERSION:** `{active}`  (branch-scoped — see CLAUDE.md §4.0)\n"
        f"- **git branch:** `{branch}`\n"
    )

    entries = _recent_session_entries(_SESSION_ENTRIES)
    if entries:
        lines = [f"## Recent SESSION LOG (last {len(entries)})", ""]
        for e in entries:
            lines.append(f"- **{e['date']}** — {e['topic']}")
            if e["next"]:
                lines.append(f"  - next: {e['next']}")
        parts.append("\n".join(lines))
    else:
        parts.append("## Recent SESSION LOG\n\n[assistant_project.md not found]")

    pending = _queue_pending(_NEXT_STEPS)
    if pending:
        lines = [f"## NEXT_10_STEPS (from multi_llm/build_queue.jsonl)", ""]
        for r in pending:
            conf = f" · conf {r['confidence']}%" if r.get("confidence") is not None else ""
            lines.append(f"- `{r['id']}` (Epic {r.get('epic')}) {r.get('title','')}{conf}")
        parts.append("\n".join(lines))
    else:
        parts.append("## NEXT_10_STEPS\n\n[build_queue.jsonl empty — run "
                     "`python scripts/context/seed_build_queue.py`]")
    return "\n\n".join(parts).rstrip() + "\n"


def _render_findings() -> str:
    findings = _between(_read(_FINDINGS), "## Findings (non-terminal)",
                        ("## Terminal", "## Funding", "## Schema")) \
        or "[current-findings.md non-terminal section not found]"
    truths = _between(_read(_CLAUDE_MD), "Repository Truths Index",
                      ("## 6.3", "---\n\n## 6.3", "## 6.3")) \
        or "[CLAUDE.md Repository Truths Index not found]"
    parts = [_header("03 · Findings & Evidence", [_FINDINGS, _CLAUDE_MD])]
    parts.append("## Repository Truths Index (thin)\n\n" + truths)
    parts.append("## Findings — full record (non-terminal)\n\n" + findings)
    return "\n\n".join(parts).rstrip() + "\n"


def _render_dependency_intent() -> str:
    parts = [_header("04 · Dependency & Intent", [_INTENT_DIR])]
    intents = sorted(_INTENT_DIR.glob("*.md")) if _INTENT_DIR.exists() else []
    if intents:
        lines = ["## Intent contracts (docs/intent/)", ""]
        for p in intents:
            lines.append(f"- `{p.name}` — {_first_heading(_read(p)) or '(no heading)'}")
        parts.append("\n".join(lines))
    else:
        parts.append("## Intent contracts\n\n[docs/intent/ not found]")
    parts.append(
        "## Dependency & flow maps (authoritative — load on demand, not inlined)\n\n"
        "- `docs/architecture/code-map.generated.md` — module dependency map\n"
        "- `docs/architecture/signal-flow.md` — candle→order end-to-end flow\n"
        "- `docs/architecture/service-boundary-map.md` — service contracts\n"
        "- `docs/architecture/citation-map.generated.md` — symbol → citing docs\n"
    )
    return "\n\n".join(parts).rstrip() + "\n"


def _render_handoff() -> str:
    parts = [_header("05 · Handoff & Protocol", [_ROLES_DIR, _HANDOFF])]
    roles = sorted(_ROLES_DIR.glob("ROLE_*.md")) if _ROLES_DIR.exists() else []
    if roles:
        lines = ["## Roles (frozen — multi_llm/roles/)", ""]
        for p in roles:
            lines.append(f"- `{p.name}` — {_first_heading(_read(p)) or '(no heading)'}")
        parts.append("\n".join(lines))
    parts.append(
        "## Mandatory response block (every model, every turn)\n\n"
        "```\nCURRENT_TASK:\nNEXT_10_STEPS:\nCONTEXT_DELTA:\nFOR_NEXT_MODEL:\n"
        "PROMPT_FOR_NEXT_MODEL:\nCONFIRMATION:\n```\n\n"
        "Flow: DeepSeek→Gemini→ChatGPT→Claude→Tests/Findings→Gemini. "
        "Full mandate: `multi_llm/MULTI_LLM_PROTOCOL.md`."
    )
    handoff = _read(_HANDOFF).strip()
    parts.append("## Live handoff state (HANDOFF.md)\n\n"
                 + (handoff if handoff else "[HANDOFF.md not found]"))
    return "\n\n".join(parts).rstrip() + "\n"


def _render_discussion() -> str:
    parts = [_header("06 · Multi-LLM Discussion (so far)", [_LEDGER])]
    if _discussion_digest is None:
        parts.append("_[discussion module unavailable]_")
    else:
        parts.append("## Discussion so far (rewind with "
                     "`python scripts/context/discussion.py --full`)\n\n" + _discussion_digest())
    return "\n\n".join(parts).rstrip() + "\n"


def build() -> dict[str, str]:
    """Pure: source files -> {filename: content}. No writes, no timestamps (deterministic)."""
    return {
        "01_GLOBAL_CONTEXT.md": _render_global(),
        "02_CURRENT_STATE.md": _render_current_state(),
        "03_FINDINGS.md": _render_findings(),
        "04_DEPENDENCY_AND_INTENT.md": _render_dependency_intent(),
        "05_HANDOFF.md": _render_handoff(),
        "06_DISCUSSION.md": _render_discussion(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="print to stdout, write nothing")
    args = ap.parse_args()

    files = build()
    if args.check:
        for name, content in files.items():
            print(f"\n===== context/{name} =====\n")
            print(content)
        return
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (_OUT_DIR / name).write_text(content, encoding="utf-8")
    print(f"wrote {len(files)} files -> {_OUT_DIR.relative_to(_REPO_ROOT).as_posix()}/")


if __name__ == "__main__":
    main()
