"""Output envelope schemas for model_runners (single serialization authority)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RECORD_SCHEMA = "model_runner_v1"
MANIFEST_SCHEMA = "model_runner_manifest_v1"
# Fixed output set when --format is omitted (defined once here — not invented per call).
DEFAULT_FORMATS: tuple[str, ...] = ("jsonl", "manifest", "summary")
ALLOWED_FORMATS: frozenset[str] = frozenset(
    {"jsonl", "csv", "manifest", "summary"}
)


@dataclass
class RunRecord:
    schema: str
    model_id: str
    instrument: str
    bar_index: int
    timestamp: str
    status: str  # "ok" | "error"
    native: dict[str, Any]
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunManifest:
    schema: str
    authority: str
    PRODUCTION_BEHAVIOR_CHANGED: bool
    model_id: str
    instrument: str
    config_path: str
    config_sha256: str
    csv_path: str
    csv_sha256: str
    window: dict[str, Any]
    feature_schema: dict[str, Any]
    artifact: dict[str, Any] | None
    config_sections_read: list[str]
    config_keys_read: list[str]
    entry_point: str
    spine_active: bool
    created_at: str
    summary_stats: dict[str, Any]
    n_ok: int
    n_error: int
    run_id: str
    out_dir: str
    # A6: CODE provenance. Config and data were already hashed; without this a
    # run cannot be pinned to a source state at all.
    code_provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def collect_code_provenance(repo_root: Path) -> dict[str, Any]:
    """Best-effort git provenance for the manifest (A6).

    Never raises: provenance is metadata about the run, so a git failure must
    not abort a scoring run. Failure is RECORDED (``available: false`` plus the
    error) rather than silently omitted — an absent field and a failed lookup
    must not look identical.
    """
    import subprocess

    def _git(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(str(exc)) from exc
        if out.returncode != 0:
            return None
        return out.stdout.strip()

    try:
        sha = _git("rev-parse", "HEAD")
        branch = _git("rev-parse", "--abbrev-ref", "HEAD")
        porcelain = _git("status", "--porcelain")
        if sha is None:
            return {
                "available": False,
                "error": "git rev-parse HEAD failed (not a repo?)",
            }
        if porcelain is None:
            return {
                "available": False,
                "error": "git status --porcelain failed",
                "git_sha": sha,
            }
        lines = [l for l in porcelain.splitlines() if l.strip()]
        untracked = [l for l in lines if l.startswith("??")]
        tracked_dirty = [l for l in lines if not l.startswith("??")]
        return {
            "available": True,
            "git_sha": sha,
            "branch": branch,
            "dirty": bool(tracked_dirty),
            "tracked_modified_count": len(tracked_dirty),
            "untracked_count": len(untracked),
            "note": (
                "dirty/untracked>0 means this run is NOT reproducible from git_sha "
                "alone — the working tree differs from the commit"
            ),
        }
    except Exception as exc:  # provenance must never abort a run
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_formats(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_FORMATS
    parts = tuple(p.strip() for p in raw.split(",") if p.strip())
    if not parts:
        raise ValueError("--format was empty after parse")
    unknown = [p for p in parts if p not in ALLOWED_FORMATS]
    if unknown:
        raise ValueError(
            f"unknown format(s) {unknown}; allowed={sorted(ALLOWED_FORMATS)}"
        )
    return parts


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: Sequence[RunRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec.to_dict(), sort_keys=True, default=str))
            fh.write("\n")


def write_csv_from_records(path: Path, records: Sequence[RunRecord]) -> None:
    """Flatten envelope + native fields; native keys prefixed native_."""
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        path.write_text("", encoding="utf-8")
        return

    native_keys: list[str] = []
    seen: set[str] = set()
    for rec in records:
        for k in rec.native:
            if k not in seen:
                seen.add(k)
                native_keys.append(k)

    fieldnames = [
        "schema",
        "model_id",
        "instrument",
        "bar_index",
        "timestamp",
        "status",
        "error",
        *[f"native_{k}" for k in native_keys],
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for rec in records:
            row: dict[str, Any] = {
                "schema": rec.schema,
                "model_id": rec.model_id,
                "instrument": rec.instrument,
                "bar_index": rec.bar_index,
                "timestamp": rec.timestamp,
                "status": rec.status,
                "error": rec.error if rec.error is not None else "",
            }
            for k in native_keys:
                val = rec.native[k] if k in rec.native else ""
                row[f"native_{k}"] = val
            w.writerow(row)
