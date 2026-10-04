"""run_id_last_ran.py — persist last-ran time per recorded run_id.

Companion to cross-family run identity (docs/implementation_plan/cross-family-run-join.md).

Stores:
  logs/index/run_id_last_ran.json   — upsert map keyed by run_id (fast lookup)
  logs/index/run_id_last_ran.jsonl  — append-only history (one line per record call)

Fail-open on write (never take down a producer). Read returns None if missing.
Does NOT mint run_ids and does NOT equate ids by clock (F-101).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_INDEX_DIR = Path("logs/index")
_MAP_PATH = _INDEX_DIR / "run_id_last_ran.json"
_HIST_PATH = _INDEX_DIR / "run_id_last_ran.jsonl"
_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_run_last_ran(
    run_id: str,
    *,
    when: Optional[str] = None,
    source: str = "",
    instrument: str = "",
    artifact_path: str = "",
    started_at: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Upsert last_ran_at for run_id. Returns the updated record, or None on failure."""
    rid = (run_id or "").strip()
    if not rid:
        return None
    ts = (when or _utc_now_iso()).strip()
    rec = {
        "run_id": rid,
        "last_ran_at": ts,
        "source": (source or "").strip() or None,
        "instrument": (instrument or "").strip() or None,
        "artifact_path": (artifact_path or "").strip() or None,
        "started_at": (started_at or "").strip() or None,
    }
    try:
        _INDEX_DIR.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            data: dict[str, Any] = {}
            if _MAP_PATH.exists():
                try:
                    loaded = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        data = loaded
                except Exception:  # noqa: BLE001
                    data = {}
            prev = data.get(rid) if isinstance(data.get(rid), dict) else None
            if prev and prev.get("first_ran_at"):
                rec["first_ran_at"] = prev["first_ran_at"]
            else:
                rec["first_ran_at"] = (started_at or ts)
            rec["ran_count"] = int((prev or {}).get("ran_count") or 0) + 1
            # keep earliest started_at if previously recorded
            if prev and prev.get("started_at") and not rec["started_at"]:
                rec["started_at"] = prev["started_at"]
            data[rid] = rec
            _MAP_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with _HIST_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec
    except Exception:  # noqa: BLE001 — fail-open
        return None


def get_run_last_ran(run_id: str) -> Optional[dict[str, Any]]:
    """Return the saved last-ran record for run_id, or None."""
    rid = (run_id or "").strip()
    if not rid or not _MAP_PATH.exists():
        return None
    try:
        data = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
        rec = data.get(rid)
        return rec if isinstance(rec, dict) else None
    except Exception:  # noqa: BLE001
        return None
