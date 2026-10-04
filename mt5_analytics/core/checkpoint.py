"""
checkpoint — idempotency cursor persisted to `state/checkpoint.json`.

Tracks the last processed deal ticket / time and the last seen M15 bar so the daemon
queries `history_deals_get(last_processed_time, now)` → **O(new deals)**, never O(all).
Pure file I/O; carries no financial truth (MT5 owns that).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Checkpoint:
    last_processed_ticket: int = 0
    last_processed_time: int = 0          # epoch seconds (MT5 deal.time units)
    last_m15_bar_time: int = 0            # epoch seconds of last seen M15 bar

    def to_dict(self) -> dict:
        return asdict(self)


def load_checkpoint(path: "Path | str") -> Checkpoint:
    """Load the cursor; a missing/corrupt file yields a zeroed (genesis) checkpoint."""
    p = Path(path)
    if not p.exists():
        return Checkpoint()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Checkpoint()
    return Checkpoint(
        last_processed_ticket=int(data.get("last_processed_ticket", 0)),
        last_processed_time=int(data.get("last_processed_time", 0)),
        last_m15_bar_time=int(data.get("last_m15_bar_time", 0)),
    )


def save_checkpoint(cp: Checkpoint, path: "Path | str") -> Path:
    """Atomically persist the cursor (write-temp-then-replace)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(cp.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)
    return p
