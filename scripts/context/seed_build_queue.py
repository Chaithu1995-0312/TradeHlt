"""
seed_build_queue.py
===================
Parse docs/implementation_plan/FULL_BUILD_SPECIFICATION.md into the single machine-readable
story backlog: multi_llm/build_queue.jsonl (one JSON object per line, append-only convention,
same discipline as configs/promotion_log.jsonl).

WHY: the multi-LLM layer needs ONE queue (MULTI_LLM_PROTOCOL.md §5 rule 2) so every model reads
the same NEXT_10_STEPS instead of inventing its own. This is the bridge from Track 3 (the
coordination layer) to Track 1 (the 44-story domain-first refactor).

Stdlib only (`re`, `json`, `pathlib`), deterministic output (doc order preserved) — byte-identical
across runs on the same spec, safe to commit. Located in multi_llm/ (NOT data/, which is gitignored)
so the queue is tracked.

Each line:
  {"id","epic","epic_title","title","status","confidence","files","depends_on"}

Usage:
  python scripts/context/seed_build_queue.py            # write the queue
  python scripts/context/seed_build_queue.py --check     # print to stdout, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Repo root = two levels up from scripts/context/seed_build_queue.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = _REPO_ROOT / "docs" / "implementation_plan" / "FULL_BUILD_SPECIFICATION.md"
_OUT = _REPO_ROOT / "multi_llm" / "build_queue.jsonl"

_EPIC_RE = re.compile(r"^#\s+\d+\.\s+Epic\s+(\d+):\s+(.+?)\s*$")
_STORY_RE = re.compile(r"^##\s+Story\s+(\d+\.\d+):\s+(.+?)\s*$")
_CONF_RE = re.compile(r"\*\*Confidence:\*\*\s*(\d+)\s*%")
# Providence (Jira-convention author) + population class, optional (defaults to Claude / omitted).
_CREATOR_RE = re.compile(r"\*\*Creator:\*\*\s*(\S+)")
_KIND_RE = re.compile(r"\*\*Kind:\*\*\s*(\S+)")
# File-like tokens cited in a story body (python modules, json configs).
_FILE_RE = re.compile(r"`?([\w./-]+\.(?:py|json|jsonl|md))`?")


def parse() -> list[dict]:
    """Parse the spec into ordered story records. Returns [] gracefully if the spec is absent."""
    if not _SPEC.exists():
        return []
    lines = _SPEC.read_text(encoding="utf-8").splitlines()

    # First pass: locate epic + story header line numbers in document order.
    epic_at: dict[int, tuple[str, str]] = {}      # lineno -> (epic_num, epic_title)
    story_at: list[tuple[int, str, str]] = []      # (lineno, story_id, title)
    for i, text in enumerate(lines):
        em = _EPIC_RE.match(text)
        if em:
            epic_at[i] = (em.group(1), em.group(2))
            continue
        sm = _STORY_RE.match(text)
        if sm:
            story_at.append((i, sm.group(1), sm.group(2)))

    def _epic_for(lineno: int) -> tuple[str, str]:
        best = ("", "")
        for e_ln in sorted(epic_at):
            if e_ln < lineno:
                best = epic_at[e_ln]
            else:
                break
        return best

    records: list[dict] = []
    prev_id: str | None = None
    for idx, (ln, story_id, title) in enumerate(story_at):
        body_end = story_at[idx + 1][0] if idx + 1 < len(story_at) else len(lines)
        body = "\n".join(lines[ln:body_end])

        conf_m = _CONF_RE.search(body)
        confidence = int(conf_m.group(1)) if conf_m else None

        cre_m = _CREATOR_RE.search(body)
        kind_m = _KIND_RE.search(body)

        files = sorted({m.group(1) for m in _FILE_RE.finditer(body)
                        if not m.group(1).endswith(".md") or "/" in m.group(1)})

        epic_num, epic_title = _epic_for(ln)
        rec = {
            "id": f"STORY-{story_id}",
            "epic": int(epic_num) if epic_num else None,
            "epic_title": epic_title,
            "title": title,
            "status": "pending",
            "confidence": confidence,
            "files": files,
            "depends_on": [prev_id] if prev_id else [],
            # Jira-convention author; defaults to Claude when the spec omits it.
            "creator": cre_m.group(1) if cre_m else "Claude",
        }
        # Population class (implementation / governance / artifact) — omitted when unclassified.
        if kind_m:
            rec["kind"] = kind_m.group(1)
        records.append(rec)
        prev_id = f"STORY-{story_id}"
    return records


def _render(records: list[dict]) -> str:
    # Compact, stable JSON line per record (keys sorted for byte-identical output).
    return "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records) + (
        "\n" if records else "")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="print to stdout, write nothing")
    args = ap.parse_args()

    records = parse()
    content = _render(records)
    if args.check:
        print(content)
        print(f"# {len(records)} stories parsed from {_SPEC.relative_to(_REPO_ROOT).as_posix()}")
        return
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(content, encoding="utf-8")
    print(f"wrote {len(records)} stories -> {_OUT.relative_to(_REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
