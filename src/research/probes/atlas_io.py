"""Decision-atlas IO helpers extracted from build_decision_atlas.py."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def load_bar_structure(path: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("phase") != "WARMUP":
                out[int(rec["bar_index"])] = rec
    return out

