"""List design cards. No LLM."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "design_cards"

def main() -> None:
    rows = []
    for status in ("draft", "final"):
        d = ROOT / status
        if not d.exists():
            continue
        for f in sorted(d.glob("DC-*.md")):
            rows.append(f"{status:5}  {f.name}")
    print("\n".join(rows) if rows else "(no cards)")

if __name__ == "__main__":
    main()
