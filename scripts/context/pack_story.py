"""
pack_story.py — emit one upload-ready context pack for a story (Portable Mind + that story's files).

Usage:
  python scripts/context/pack_story.py --story STORY-1.1
  python scripts/context/pack_story.py --story STORY-1.1 --add src/foo.py --budget 16000
  python scripts/context/pack_story.py --story STORY-1.1 --check   # print, write nothing
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
try:  # preserve non-ASCII (em-dashes etc.) without crashing a cp1252 console
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from multi_llm.context_pack import build_pack  # noqa: E402
from multi_llm.tokens import DEFAULT_BUDGET  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--story", required=True, help="STORY-x.y id (from multi_llm/build_queue.jsonl)")
    ap.add_argument("--add", action="append", default=[], help="extra file path to include (repeatable)")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="approx token budget")
    ap.add_argument("--check", action="store_true", help="print to stdout, write nothing")
    args = ap.parse_args()

    content = build_pack(args.story, extra_paths=tuple(args.add), budget=args.budget)
    if args.check:
        print(content)
        return
    out = _REPO_ROOT / "context" / "packs" / f"{args.story}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"wrote {out.relative_to(_REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
