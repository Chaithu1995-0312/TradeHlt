"""Candle corpus loading shared by analysis probes."""
from __future__ import annotations

import csv
import json
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

def load_live_rows(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("phase") == "LIVE":
                out.append(rec)
    return out


def join_and_verify(live: list[dict], corpus: list[dict]) -> tuple[list[dict], dict]:
    """Join envelope rows to corpus bars BY TIMESTAMP and verify the OHLC agrees.

    The feature pipeline drops warmup bars and resets its index, so a POSITIONAL join is exactly
    the alignment bug that has bitten this corpus before. Timestamp is the key; the OHLC compare
    is the guard that proves the key was right.
    """
    by_ts = {c["ts"]: c for c in corpus}
    joined, mismatches, unmatched = [], 0, 0
    for rec in live:
        ts = datetime.fromisoformat(rec["timestamp"])
        bar = by_ts.get(ts)
        if bar is None:
            unmatched += 1
            continue
        fv = rec.get("resolver.feature_vector") or {}
        for field in ("open", "high", "low", "close"):
            if field not in fv:
                continue
            # RELATIVE tolerance: the canonical vector stores prices as float32, so at XAUUSD's
            # ~4,000 level it round-trips as 4155.47021484375 vs the CSV's 4155.47 -- ~2e-4 of
            # representation noise. 1e-6 relative (~0.004 here) sits ~20x above that noise and
            # orders of magnitude below any real misalignment, which would differ by whole
            # dollars. An ABSOLUTE 1e-6 flagged all 2,222 rows and was a bug in this guard.
            if abs(float(fv[field]) - bar[field]) > 1e-6 * max(1.0, abs(bar[field])):
                mismatches += 1
                break
        joined.append({"rec": rec, "bar": bar})
    return joined, {"unmatched": unmatched, "ohlc_mismatches": mismatches}

