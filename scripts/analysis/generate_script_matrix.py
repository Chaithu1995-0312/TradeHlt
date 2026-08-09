"""Generate docs/reference/script-matrix.md from the Script Registry (SITS).

Prefer seeded ``data/script_registry.jsonl``; fall back to stubs PRIMARY if data/ absent.

    python scripts/analysis/generate_script_matrix.py
    python scripts/analysis/generate_script_matrix.py --out docs/reference/script-matrix.md

Sync floor: tests/test_script_matrix_sync.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.script_registry import ScriptRegistry  # noqa: E402
from utils.jsonl_writer import read_jsonl  # noqa: E402

DEFAULT_DATA = _ROOT / "data" / "script_registry.jsonl"
DEFAULT_STUBS = _ROOT / "docs" / "governance" / "script_registry_stubs.jsonl"
DEFAULT_OUT = _ROOT / "docs" / "reference" / "script-matrix.md"


def _load_records() -> list[dict]:
    if DEFAULT_DATA.exists() and DEFAULT_DATA.stat().st_size > 0:
        return read_jsonl(DEFAULT_DATA)
    if DEFAULT_STUBS.exists():
        return read_jsonl(DEFAULT_STUBS)
    return []


def render_matrix(records: list[dict]) -> str:
    ordered = sorted(records, key=lambda r: r.get("id", ""))
    lines: list[str] = [
        "# Script Matrix (Generated — SITS)",
        "",
        "Generated from the Script Registry (stubs + overlays).",
        "",
        "Regenerate:",
        "",
        "```text",
        "python scripts/governance/seed_script_registry.py",
        "python scripts/analysis/generate_script_matrix.py",
        "```",
        "",
        "Authority: **inventory only** (no promote power). Thin-wrapper purity is **not**",
        "CI-enforced in v1 — rows track `logic_in_script` / `implementation_status` only.",
        "",
        f"**Records:** {len(ordered)}",
        "",
        "| ID | Category | Lifecycle | Impl status | Path | Purpose |",
        "|---|---|---|---|---|---|",
    ]
    for r in ordered:
        purpose = (r.get("purpose") or "").replace("|", "\\|")
        if len(purpose) > 80:
            purpose = purpose[:77] + "..."
        path = (r.get("path") or "").replace("|", "\\|")
        lines.append(
            f"| `{r.get('id', '')}` | {r.get('category', '')} | {r.get('lifecycle', '')} | "
            f"{r.get('implementation_status', '')} | `{path}` | {purpose} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Generator: `scripts/analysis/generate_script_matrix.py` · "
        f"schema: `docs/reference/schemas.md` §9.8 · "
        f"authority={ScriptRegistry.validate_record and 'inventory'}*"
    )
    # fix silly authority line - just pin inventory
    lines[-1] = (
        "*Generator: `scripts/analysis/generate_script_matrix.py` · "
        "schema: `docs/reference/schemas.md` §9.8 · authority=`inventory`*"
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate script-matrix.md from SITS registry")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    records = _load_records()
    # Validate when non-empty so broken stubs fail generation early
    for rec in records:
        ScriptRegistry.validate_record(rec)

    text = render_matrix(records)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {len(records)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
