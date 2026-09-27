"""Create a design card from template. Plug-in / plug-out — no LLM required."""
from __future__ import annotations
import argparse, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "design_cards"
TEMPLATE = ROOT / "_templates" / "CARD.md"

def main() -> None:
    p = argparse.ArgumentParser(description="New design card")
    p.add_argument("--id", required=True, help="e.g. DC-003")
    p.add_argument("--title", required=True)
    p.add_argument("--final", action="store_true", help="write under final/ instead of draft/")
    args = p.parse_args()
    if not re.fullmatch(r"DC-\d{3,4}", args.id):
        raise SystemExit("id must look like DC-001")
    dest_dir = ROOT / ("final" if args.final else "draft")
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")[:60]
    dest = dest_dir / f"{args.id}-{slug}.md"
    if dest.exists():
        raise SystemExit(f"exists: {dest}")
    text = TEMPLATE.read_text(encoding="utf-8")
    text = text.replace("DC-XXXX", args.id).replace("{{title}}", args.title)
    if args.final:
        text = text.replace("**Status** | draft", "**Status** | final").replace("**Frozen** | no", "**Frozen** | yes")
    dest.write_text(text, encoding="utf-8")
    print(dest)

if __name__ == "__main__":
    main()
