"""run_trace_api.py — read-only API behind the Live Run Trace page (ui_kits/run_trace).

Reads the per-run output of `runtime.bar_structure_snapshot` when a run enables
`per_run_dir` (+ optionally `families.features` / `write_parquet`):

    <root>/<run_id>/manifest.json            identity, feature schema, resolved config, status
    <root>/<run_id>/<INSTR>_bar_structure.jsonl   one row per bar, appended during the run
    <root>/<run_id>/<INSTR>_bar_structure.parquet (+ .manifest.json)  after close(), optional

Live runs are read from the JSONL by BYTE CURSOR so a poll returns only new rows. A trailing
line with no newline is a partial write in progress and is left for the next poll, never
half-parsed. Finished runs read through `utils.parquet_store.iter_records`, which uses the
Parquet projection only when it is FRESH and verified against its source, else the JSONL.

Read-only, no authority (CLAUDE.md §6.5): nothing here writes, and nothing a decision path reads.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "logs" / "bar_structure"

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
MAX_LIMIT = 5000


def _root(root: Optional[Path]) -> Path:
    return Path(root) if root is not None else DEFAULT_ROOT


def _run_dir(run_id: str, root: Optional[Path] = None) -> Path:
    # run_id comes from a query string: refuse anything that could escape the root.
    if not run_id or not _RUN_ID_RE.match(run_id):
        raise KeyError(f"invalid run_id {run_id!r}")
    d = _root(root) / run_id
    if not (d / "manifest.json").is_file():
        raise KeyError(f"no run-trace manifest for {run_id!r}")
    return d


def _load_manifest(d: Path) -> dict:
    return json.loads((d / "manifest.json").read_text(encoding="utf-8"))


def list_runs(root: Optional[Path] = None) -> dict:
    """Every run with a manifest, newest first, without the (large) config block."""
    runs = []
    base = _root(root)
    if base.is_dir():
        for mp in base.glob("*/manifest.json"):
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue  # a manifest mid-replace is skipped this poll, not reported broken
            ident = m.get("identity", {})
            runs.append({
                "run_id": mp.parent.name,
                "status": m.get("status"),
                "instrument": ident.get("instrument"),
                "config_version": ident.get("config_version"),
                "rows": m.get("rows"),
                "corpus_rows": m.get("corpus_rows"),
                "started_at": m.get("started_at"),
                "finished_at": m.get("finished_at"),
                "features_in_rows": m.get("features_in_rows"),
                "parquet": bool((m.get("parquet") or {}).get("verified")),
            })
    runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return {"root": str(base), "runs": runs}


def run_meta(run_id: str, root: Optional[Path] = None) -> dict:
    d = _run_dir(run_id, root)
    m = _load_manifest(d)
    m["run_id"] = run_id
    return m


def read_jsonl_from(path: Path, offset: int, limit: int) -> tuple[list[dict], int]:
    """Complete lines from `offset`, at most `limit`. Returns (rows, next_offset).

    Binary read so offsets are true byte positions. A final line without '\\n' is an append in
    progress: it is not consumed, and next_offset stops before it.
    """
    rows: list[dict] = []
    if not path.is_file():
        return rows, offset
    size = path.stat().st_size
    if offset > size:  # file was replaced/truncated -> restart
        offset = 0
    with path.open("rb") as fh:
        fh.seek(offset)
        pos = offset
        while len(rows) < limit:
            line = fh.readline()
            if not line or not line.endswith(b"\n"):
                break
            pos += len(line)
            s = line.strip()
            if not s:
                continue
            try:
                rows.append(json.loads(s))
            except json.JSONDecodeError:
                continue
    return rows, pos


def bars(run_id: str, offset: int = 0, limit: int = 1000, root: Optional[Path] = None,
         cursor: str = "auto") -> dict:
    """`cursor`: "byte" (JSONL tail), "row" (Parquet row index), or "auto" (row when the run is
    finished with a verified projection, else byte). A client that started tailing a live run
    keeps sending "byte", so the run finishing mid-session never changes the cursor's unit."""
    d = _run_dir(run_id, root)
    m = _load_manifest(d)
    limit = max(1, min(int(limit), MAX_LIMIT))
    jsonl = d / m.get("jsonl", "")
    use_row = cursor == "row" or (
        cursor == "auto" and m.get("status") == "finished"
        and bool((m.get("parquet") or {}).get("verified"))
    )
    if use_row:
        # Finished + verified projection: `offset` is a ROW index here, and iter_records falls
        # back to JSONL by itself if the projection turns out stale.
        from itertools import islice
        from utils.parquet_store import iter_records, projection_status

        start = max(0, int(offset))
        rows = list(islice(iter_records(jsonl), start, start + limit))
        return {"run_id": run_id, "source": f"parquet:{projection_status(jsonl)}",
                "cursor": "row", "rows": rows, "next_offset": start + len(rows),
                "status": m.get("status"), "total_rows": m.get("rows")}
    rows, nxt = read_jsonl_from(jsonl, int(offset), limit)
    return {"run_id": run_id, "source": "jsonl", "cursor": "byte", "rows": rows,
            "next_offset": nxt, "status": m.get("status"), "total_rows": m.get("rows")}
