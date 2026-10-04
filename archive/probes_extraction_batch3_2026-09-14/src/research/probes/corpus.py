"""Candle corpus loading shared by analysis probes."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


def load_corpus(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            rows.append({
                "index": i,
                "ts": datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S"),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
            })
    return rows
