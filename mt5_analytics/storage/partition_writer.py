"""
partition_writer — idempotent, date-partitioned JSONL writer.

Layout: ``<root>/<kind>/YYYY/MM/DD/<kind>.jsonl`` with a sibling ``manifest.json``.
Records are partitioned by their close date and **deduped on `episode_id`** before
append, so a crash-and-restart or a re-run never produces duplicates (idempotency
pillar). After appending, the partition's manifest is rebuilt over the *full* current
record set so its sha256 always reflects what is on disk.

Reuses the canonical `append_jsonl` / `read_jsonl` from `src/utils/jsonl_writer.py`.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from utils.jsonl_writer import append_jsonl, read_jsonl  # type: ignore

from .manifest_builder import build_manifest, write_manifest

_DEDUP_KEY = "episode_id"


class PartitionWriter:
    """Writes deduped, date-partitioned JSONL artifacts with provenance manifests."""

    def __init__(self, root: "Path | str", kind: str) -> None:
        self._root = Path(root)
        self._kind = kind

    def _partition_dir(self, date_iso: str) -> Path:
        # date_iso like "2026-06-19T01:23:45Z" -> YYYY/MM/DD
        date_part = date_iso[:10]
        y, m, d = date_part.split("-")
        return self._root / self._kind / y / m / d

    def write(
        self,
        records: Iterable[dict],
        *,
        date_key: str = "exit_time",
        schema_version: str = "1.0",
        source_history_window: "dict | None" = None,
        rebuild_id: str = "",
        generated_by: str = "",
    ) -> dict:
        """Append new records (deduped by `episode_id`), rebuild affected manifests.

        Returns a summary: ``{written, skipped_duplicates, partitions}``.
        """
        by_part: dict[Path, list[dict]] = defaultdict(list)
        for rec in records:
            date_iso = str(rec[date_key])
            by_part[self._partition_dir(date_iso)].append(rec)

        written = 0
        skipped = 0
        touched: list[str] = []

        for part_dir, new_recs in by_part.items():
            data_file = part_dir / f"{self._kind}.jsonl"
            existing = read_jsonl(data_file)
            existing_ids = {str(r.get(_DEDUP_KEY)) for r in existing}

            for rec in new_recs:
                rid = str(rec.get(_DEDUP_KEY))
                if rid in existing_ids:
                    skipped += 1
                    continue
                append_jsonl(data_file, rec)
                existing.append(rec)
                existing_ids.add(rid)
                written += 1

            manifest = build_manifest(
                existing,
                schema_version=schema_version,
                source_history_window=source_history_window,
                rebuild_id=rebuild_id,
                generated_by=generated_by,
            )
            write_manifest(manifest, part_dir)
            touched.append(str(part_dir))

        return {
            "written": written,
            "skipped_duplicates": skipped,
            "partitions": sorted(touched),
        }
