"""
jsonl_writer.py — the canonical append-only JSONL helper.

Consolidates the identical 3-line append snippets scattered across the repo
(engine_telemetry._append_jsonl, log_index_writer._append_index,
llm_inference_client._append_llm_audit). New code should use this; the existing
callers are left untouched for now (additive-only).

Pattern (matches the existing snippets): mkdir-safe parent, one JSON object per line,
UTF-8. `fail_silent=True` swallows write errors (fire-and-forget telemetry); the
default raises so callers that need durability (a ledger) hear about failures.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

logger = logging.getLogger("jsonl_writer")


def append_jsonl(path: "Path | str", record: dict, *, fail_silent: bool = False) -> None:
    """Append one JSON record as a line to *path* (creating parent dirs)."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:  # noqa: BLE001
        if fail_silent:
            logger.debug("append_jsonl: write failed (non-blocking): %s", exc)
            return
        raise


def read_jsonl(path: "Path | str") -> list[dict]:
    """Read all well-formed JSON lines from *path*. Missing file -> []. Skips blank/corrupt lines."""
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            logger.debug("read_jsonl: skipping corrupt line in %s", p)
    return out


def iter_jsonl(path: "Path | str") -> Iterator[dict]:
    """Stream well-formed JSON lines (memory-friendly for large ledgers)."""
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                logger.debug("iter_jsonl: skipping corrupt line in %s", p)
