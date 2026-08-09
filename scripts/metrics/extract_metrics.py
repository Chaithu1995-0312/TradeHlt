"""
extract_metrics.py
==================
PROSPECTIVE, READ-ONLY extractor for the optional ``**Metrics**`` self-report block that may
be appended to ``📝 SESSION LOG ENTRY`` blocks in ``assistant_project.md``.

Why
    The Metrics Block (docs/architecture/intelligence-compounding.md → "Metrics Block") is an
    *optional* one-line self-report telemetry convention on the doctrine's operational hook
    (CLAUDE.md §7.4). This tool tabulates those blocks into structured records for trend review.

Epistemic status (binding — CLAUDE.md §6.5 Authority Ladder + E-001)
    The fields are SELF-RATED grades. Tabulating them is honest self-report / compliance
    telemetry ONLY; it does not make them empirical. The output carries ZERO authority and may
    NEVER be used to settle a TruthConflict, decide documentation wording, or gate behavior.

Prospective by design
    Historical log entries predate the convention and contain no ``**Metrics**`` blocks, so this
    tool returns an empty list for them. That is expected, not a bug.

This tool mutates nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LOG = _ROOT / "assistant_project.md"

# Stable field order — the legend in intelligence-compounding.md depends on this.
FIELDS: tuple[str, ...] = ("GP", "Act", "Rec", "Find", "Ent", "NS", "KROI")

# A Metrics block: the literal **Metrics** marker line, then a pipe-separated key:value value
# line (must contain GP:), then an optional Notes: line.
_BLOCK_RE = re.compile(
    r"^\*\*Metrics\*\*[ \t]*\r?\n"          # marker line
    r"(?P<values>[^\r\n]*GP:[^\r\n]*)\r?\n"  # a pipe-delimited line containing GP:...
    r"(?:[ \t]*Notes:[ \t]*(?P<notes>[^\r\n]*)\r?\n?)?",  # optional Notes:
    re.MULTILINE,
)
_DATE_RE = re.compile(r"^Date:[ \t]*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def _parse_values(line: str) -> dict[str, str]:
    """Split a 'GP:1|Act:Redirect|...' value line into an ordered dict (stable FIELDS order)."""
    pairs: dict[str, str] = {}
    for token in line.strip().split("|"):
        if ":" not in token:
            continue
        key, value = token.split(":", 1)
        pairs[key.strip()] = value.strip()
    # Re-key in canonical order; preserve any unexpected keys at the end for visibility.
    ordered = {f: pairs[f] for f in FIELDS if f in pairs}
    ordered.update({k: v for k, v in pairs.items() if k not in FIELDS})
    return ordered


def parse_metrics(text: str) -> list[dict]:
    """
    Pure parser: extract every Metrics block from log text.

    Returns a list of records: {"fields": {...}, "notes": str|None, "date": "YYYY-MM-DD"|None}.
    Each block is tagged with the nearest preceding ``Date:`` line (the enclosing entry). Empty
    or block-free input yields an empty list (prospective-by-design).
    """
    records: list[dict] = []
    for m in _BLOCK_RE.finditer(text):
        preceding = text[: m.start()]
        dates = _DATE_RE.findall(preceding)
        records.append(
            {
                "fields": _parse_values(m.group("values")),
                "notes": (m.group("notes").strip() if m.group("notes") else None),
                "date": (dates[-1] if dates else None),
            }
        )
    return records


def _filter_since(records: list[dict], since: str) -> list[dict]:
    """Keep records whose date >= since (ISO YYYY-MM-DD lexical compare); undated records drop."""
    return [r for r in records if r["date"] and r["date"] >= since]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract optional **Metrics** self-report blocks (read-only, no authority)."
    )
    ap.add_argument("--file", default=str(_DEFAULT_LOG),
                    help="log file to scan (default: repo-root assistant_project.md)")
    ap.add_argument("--since", default=None, metavar="YYYY-MM-DD",
                    help="only records dated on/after this ISO date")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    # Lazy import so the pure parser stays import-light and the test needs no src on path.
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from src.utils.console_safe import safe_print

    path = Path(args.file)
    if not path.exists():
        safe_print(f"extract_metrics: log not found → {path}", file=sys.stderr)
        return 1

    records = parse_metrics(path.read_text(encoding="utf-8"))
    if args.since:
        records = _filter_since(records, args.since)

    if args.json:
        safe_print(json.dumps(records, indent=2, ensure_ascii=False))
        return 0

    if not records:
        safe_print(
            "extract_metrics: 0 Metrics blocks found. "
            "The **Metrics** convention is PROSPECTIVE — historical entries predate it. "
            "Append a block to a future SESSION LOG entry to start tracking."
        )
        return 0

    safe_print(f"extract_metrics: {len(records)} Metrics block(s) in {path.name}")
    for r in records:
        date = r["date"] or "????-??-??"
        fields = " ".join(f"{k}:{v}" for k, v in r["fields"].items())
        safe_print(f"  [{date}] {fields}")
        if r["notes"]:
            safe_print(f"           Notes: {r['notes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
