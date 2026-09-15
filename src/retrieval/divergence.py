"""
retrieval/divergence.py — Mechanical divergence checks over retrieval hits.

Never adjudicates. Emits TruthConflict-shaped flags for the caller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from retrieval.truth_tier import is_non_live

_PATH_LINE_RE = re.compile(
    r"(?P<path>(?:src|tests|scripts|docs|configs)/[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)"
    r":(?P<line>\d+)"
)


@dataclass
class DivergenceFlag:
    kind: str  # co_retrieval_divergence | superseded_hit | stale_citation | confidence_carry
    symbol_or_id: str = ""
    truth_classes: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    detail: str = ""
    # TruthConflict-shaped payload (6.2 rule 3) — never picks a winner
    conflict: dict[str, Any] | None = None


def _symbols_of(hit: Any) -> set[str]:
    out: set[str] = set()
    ids = getattr(hit, "ids", "") or ""
    for part in str(ids).split(","):
        part = part.strip()
        if part:
            out.add(part)
    symbols = getattr(hit, "symbols", "") or ""
    for part in str(symbols).split(","):
        part = part.strip()
        if part:
            out.add(part)
    # also pull F-/FM- etc from text lightly via ids already populated
    return out


def detect_divergences(
    hits: Sequence[Any],
    *,
    repo_root: Path | None = None,
) -> list[DivergenceFlag]:
    """Run the four mechanical checks over top-K hits."""
    flags: list[DivergenceFlag] = []

    # 1. co_retrieval_divergence
    by_symbol: dict[str, dict[str, list[str]]] = {}
    for hit in hits:
        tc = getattr(hit, "truth_class", None) or getattr(hit, "domain", "") or ""
        cid = getattr(hit, "chunk_id", "")
        for sym in _symbols_of(hit):
            by_symbol.setdefault(sym, {}).setdefault(tc, []).append(cid)
    for sym, class_map in by_symbol.items():
        if len(class_map) >= 2:
            classes = sorted(class_map)
            cids = [c for lst in class_map.values() for c in lst]
            flags.append(
                DivergenceFlag(
                    kind="co_retrieval_divergence",
                    symbol_or_id=sym,
                    truth_classes=classes,
                    chunk_ids=cids,
                    detail=f"{sym} appears in truth classes {classes}",
                    conflict={
                        "type": "TruthConflict",
                        "symbol": sym,
                        "classes": {
                            tc: class_map[tc] for tc in classes
                        },
                        "resolution": None,
                        "note": "retriever does not pick a winner",
                    },
                )
            )

    # 2. superseded_hit
    for hit in hits:
        status = str(getattr(hit, "lifecycle_status", "LIVE") or "LIVE")
        if is_non_live(status):
            flags.append(
                DivergenceFlag(
                    kind="superseded_hit",
                    symbol_or_id=getattr(hit, "chunk_id", ""),
                    truth_classes=[getattr(hit, "truth_class", "")],
                    chunk_ids=[getattr(hit, "chunk_id", "")],
                    detail=(
                        f"{status}: {getattr(hit, 'status_evidence', '')}".strip(": ")
                    ),
                )
            )

    # 3. stale_citation — path:line that no longer resolves (±30 window check)
    if repo_root is not None:
        for hit in hits:
            text = getattr(hit, "text", "") or ""
            for m in _PATH_LINE_RE.finditer(text):
                rel = m.group("path")
                line_no = int(m.group("line"))
                target = repo_root / rel
                if not target.is_file():
                    flags.append(
                        DivergenceFlag(
                            kind="stale_citation",
                            symbol_or_id=f"{rel}:{line_no}",
                            chunk_ids=[getattr(hit, "chunk_id", "")],
                            detail=f"cited path missing: {rel}",
                        )
                    )
                    continue
                try:
                    n_lines = sum(1 for _ in target.open(encoding="utf-8", errors="replace"))
                except OSError:
                    flags.append(
                        DivergenceFlag(
                            kind="stale_citation",
                            symbol_or_id=f"{rel}:{line_no}",
                            chunk_ids=[getattr(hit, "chunk_id", "")],
                            detail=f"cited path unreadable: {rel}",
                        )
                    )
                    continue
                # ±30 window must still land inside the file
                if line_no < 1 or line_no > n_lines:
                    flags.append(
                        DivergenceFlag(
                            kind="stale_citation",
                            symbol_or_id=f"{rel}:{line_no}",
                            chunk_ids=[getattr(hit, "chunk_id", "")],
                            detail=(
                                f"line {line_no} outside file ({n_lines} lines)"
                            ),
                        )
                    )

    # 4. confidence_carry
    for hit in hits:
        conf = getattr(hit, "confidence", "") or ""
        validated = getattr(hit, "validated", "") or ""
        revalidate = getattr(hit, "revalidate_by", "") or ""
        if conf or validated or revalidate:
            flags.append(
                DivergenceFlag(
                    kind="confidence_carry",
                    symbol_or_id=getattr(hit, "chunk_id", ""),
                    truth_classes=[getattr(hit, "truth_class", "")],
                    chunk_ids=[getattr(hit, "chunk_id", "")],
                    detail=(
                        f"Confidence={conf!r}; Validated={validated!r}; "
                        f"Revalidate-by={revalidate!r}"
                    ),
                )
            )

    return flags
