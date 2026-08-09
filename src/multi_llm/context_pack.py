"""
context_pack.py — bounded, upload-ready context for ONE task (never the whole codebase).

Realizes the compression hierarchy's last hop:
  Portable Mind (context/01..06) + only the STORY's files (from build_queue.jsonl) -> one pack.

Token-budgeted: files are added until the budget is reached, then TRUNCATED with an explicit flag
(the full file always remains on disk — no silent loss). Bare-basename file refs from the queue are
resolved under src/tests/scripts (same approach as tests/test_doc_citations.py).
"""
from __future__ import annotations

from pathlib import Path

from multi_llm.tokens import estimate_tokens, DEFAULT_BUDGET
from utils.jsonl_writer import read_jsonl

_REPO_ROOT = Path(__file__).resolve().parents[2]
_QUEUE = _REPO_ROOT / "multi_llm" / "build_queue.jsonl"
_CONTEXT_DIR = _REPO_ROOT / "context"
_SEARCH_ROOTS = ("src", "tests", "scripts", "configs", "docs")


def get_story(story_id: str) -> dict | None:
    for r in read_jsonl(_QUEUE):
        if r.get("id") == story_id:
            return r
    return None


def _resolve(path_str: str) -> Path | None:
    if "/" in path_str or "\\" in path_str:
        p = (_REPO_ROOT / path_str)
        return p if p.exists() else None
    hits: list[Path] = []
    for root in _SEARCH_ROOTS:
        hits.extend((_REPO_ROOT / root).rglob(path_str))
    hits = sorted(set(hits))
    return hits[0] if len(hits) == 1 else (None if not hits else hits[0])


def _portable_mind() -> list[tuple[str, str]]:
    out = []
    if _CONTEXT_DIR.exists():
        for p in sorted(_CONTEXT_DIR.glob("0*.md")):
            out.append((p.name, p.read_text(encoding="utf-8")))
    return out


def build_pack(story_id: str, *, extra_paths: tuple[str, ...] = (), budget: int = DEFAULT_BUDGET) -> str:
    story = get_story(story_id)
    parts: list[str] = []
    manifest: list[str] = []
    truncations: list[str] = []

    title = story.get("title", "") if story else "(unknown story)"
    parts.append(f"# CONTEXT PACK — {story_id}: {title}\n")
    parts.append(f"> Bounded context for one task. Budget ~{budget} tokens. "
                 "Portable Mind + only this story's files. Truncations are flagged, never silent.\n")

    used = 0
    pm = _portable_mind()
    if pm:
        block = "\n\n".join(f"<!-- {name} -->\n{text}" for name, text in pm)
        used += estimate_tokens(block)
        parts.append("## Portable Mind (context/01..06)\n\n" + block)
        manifest.append(f"Portable Mind ({len(pm)} files, ~{estimate_tokens(block)} tok)")
    else:
        parts.append("## Portable Mind\n\n_[run `python scripts/context/build_context.py` first]_")

    file_refs = list(story.get("files", []) if story else []) + list(extra_paths)
    parts.append("\n## Story files")
    if not file_refs:
        parts.append("_[no files listed for this story]_")
    for ref in file_refs:
        resolved = _resolve(ref)
        if resolved is None:
            parts.append(f"\n### {ref}\n_[file not found]_")
            truncations.append(f"{ref}: not found")
            continue
        rel = resolved.relative_to(_REPO_ROOT).as_posix()
        content = resolved.read_text(encoding="utf-8", errors="replace")
        est = estimate_tokens(content)
        remaining = budget - used
        if est <= remaining:
            used += est
            parts.append(f"\n### `{rel}`\n```\n{content}\n```")
            manifest.append(f"{rel} (~{est} tok)")
        else:
            allowed_chars = max(0, remaining * 4)
            clipped = content[:allowed_chars]
            used = budget
            flag = f"[TRUNCATED at ~{remaining} tok — full file on disk: {rel}]"
            parts.append(f"\n### `{rel}`\n```\n{clipped}\n# ...{flag}\n```")
            truncations.append(flag)
            manifest.append(f"{rel} (TRUNCATED)")

    head = ["\n## Manifest"]
    head += [f"- {m}" for m in manifest] or ["- (empty)"]
    head.append(f"\n_estimated total: ~{used} tok (budget {budget})_")
    if truncations:
        head.append("\n**Truncations (full content on disk):**")
        head += [f"- {t}" for t in truncations]
    parts.append("\n".join(head))
    return "\n".join(parts).rstrip() + "\n"
