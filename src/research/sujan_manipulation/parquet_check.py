"""Cross-check the proxy's CSV-derived magnitudes against the Parquet projection.

WHY THIS EXISTS
---------------
The bulk-candle proxy ranks over `data/mt5/XAUUSD_M15.csv` — the tracked, complete,
label-free corpus. The Parquet layer independently carries the SAME two quantities as
precomputed columns (`features.candle_range` = FM-002, `features.body_size` = FM-001,
both recorded MATCH_EXACT against `candle_math`). Comparing them turns "the two agree"
from an assumption into a measurement.

Parquet is the CHECK, not the source. Three reasons it is not the source:

  1. `data/mt5/XAUUSD_M15.csv` has NO Parquet twin — nothing exists under `data/` at all.
     The XAUUSD projections live under `logs/` and `results/`, both gitignored, and the
     Sujan measurement contract forbids citing evidence inside a gitignored tree.
  2. Grain differs: one row per (bar x direction), 47,166 timestamps x 2 sides, which is
     ~109 bars SHORT of the CSV's 47,275 (78-bar feature warmup plus edge trim).
  3. `clean_labels` carries `y_R_net` / `y_tp1` / `y_mfe_r` in the same table. Selecting
     the founding from a label-bearing ledger puts forward outcomes in the read path.

FAIL CLOSED
-----------
`parquet_store.iter_records` silently degrades to reading the JSONL source when pyarrow is
missing — and pyarrow is installed only in the project venvs, not the bare `python` on
PATH. A silent degrade here would make a SKIPPED check indistinguishable from a PASSED one:
the F-079 / F-083 / F-085 failure class. So this module refuses to run without pyarrow
rather than quietly reading a 299 MB JSONL and reporting success.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from utils.parquet_store import iter_records, parquet_available, projection_status

from research.sujan_manipulation.bulk_proxy import RANKING_BODY, RANKING_RANGE
from research.sujan_manipulation.parent import Bar

#: The JSONL system of record; `iter_records` selects the Parquet projection itself.
DEFAULT_CLEAN_LABELS = Path("results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.jsonl")

#: Top-level keys only — the projection stores `features.*` as flattened columns but
#: `iter_records` reconstructs the nested dict shape.
_COLUMNS = ("decision_ts", "side", "features")

#: One side is enough: the ledger duplicates each bar across long/short.
_KEEP_SIDE = "long"

#: Float equality tolerance. These are the same arithmetic on the same inputs, so the only
#: expected difference is float32 storage in the projection.
_TOL = 1e-6


class ParquetCheckUnavailable(RuntimeError):
    """pyarrow is absent, or the projection is not FRESH. Fail closed, never degrade."""


@dataclass(frozen=True)
class CrossCheckResult:
    status: str                    # AGREES | DISAGREES
    source_path: str
    projection_status: str
    csv_bars: int
    parquet_rows_read: int
    compared: int
    csv_only: int                  # bars in the CSV with no projection row (expected ~109)
    parquet_only: int
    mismatches: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_path": self.source_path,
            "projection_status": self.projection_status,
            "csv_bars": self.csv_bars,
            "parquet_rows_read": self.parquet_rows_read,
            "compared": self.compared,
            "csv_only": self.csv_only,
            "parquet_only": self.parquet_only,
            "mismatch_count": len(self.mismatches),
            "mismatches": list(self.mismatches[:20]),
            "tolerance": _TOL,
            "note": (
                "Parquet is a CHECK, not the source. csv_only is EXPECTED (~109: 78-bar "
                "feature warmup plus edge trim) and is not a failure."
            ),
        }


def _parse_ts(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if not raw:
        return None
    s = str(raw).strip().replace("T", " ")
    try:
        return datetime.fromisoformat(s[:19])
    except ValueError:
        return None


def _projection_rows(path: Path) -> Iterable[dict[str, Any]]:
    for rec in iter_records(path, columns=list(_COLUMNS), strict=True):
        if rec.get("side") != _KEEP_SIDE:
            continue
        feats = rec.get("features")
        if not isinstance(feats, dict):
            raise ParquetCheckUnavailable(
                f"{path}: row has no nested 'features' dict — the column projection returned "
                f"{type(feats).__name__}. Refusing to report a check that compared nothing."
            )
        ts = _parse_ts(rec.get("decision_ts"))
        if ts is None:
            continue
        yield {
            "timestamp": ts,
            RANKING_RANGE: feats.get("candle_range"),
            RANKING_BODY: feats.get("body_size"),
        }


def cross_check(
    bars: Sequence[Bar],
    *,
    source: Path | str = DEFAULT_CLEAN_LABELS,
) -> CrossCheckResult:
    """Compare CSV-derived candle_range / body_size against the Parquet projection.

    Raises `ParquetCheckUnavailable` rather than returning a passing result it did not earn.
    """
    from features.candle_math import body_size, candle_range

    source = Path(source)
    if not parquet_available():
        raise ParquetCheckUnavailable(
            "pyarrow is not importable, so iter_records would silently read the JSONL source "
            "instead of the projection and this check would prove nothing. Run with a venv "
            "interpreter (venv/Scripts/python.exe) or omit the cross-check."
        )
    if not source.exists():
        raise ParquetCheckUnavailable(f"projection source not found: {source}")

    status = projection_status(source)
    if status != "FRESH":
        raise ParquetCheckUnavailable(
            f"{source}: projection status is {status}, not FRESH. A stale or absent projection "
            "cannot corroborate anything."
        )

    csv_by_ts = {
        bar.timestamp: (
            candle_range(bar.high, bar.low),
            body_size(bar.open, bar.close),
        )
        for bar in bars
    }

    rows_read = 0
    compared = 0
    seen: set[datetime] = set()
    mismatches: list[dict[str, Any]] = []

    for row in _projection_rows(source):
        rows_read += 1
        ts = row["timestamp"]
        seen.add(ts)
        expected = csv_by_ts.get(ts)
        if expected is None:
            continue
        compared += 1
        for i, ranking in enumerate((RANKING_RANGE, RANKING_BODY)):
            got = row[ranking]
            if got is None:
                mismatches.append(
                    {"timestamp": ts.isoformat(sep=" "), "ranking": ranking,
                     "csv": expected[i], "parquet": None, "reason": "column absent"}
                )
                continue
            if abs(float(got) - expected[i]) > _TOL:
                mismatches.append(
                    {"timestamp": ts.isoformat(sep=" "), "ranking": ranking,
                     "csv": expected[i], "parquet": float(got),
                     "delta": float(got) - expected[i]}
                )

    if compared == 0:
        raise ParquetCheckUnavailable(
            f"{source}: zero rows joined to the CSV corpus. Refusing to report AGREES on an "
            "empty comparison."
        )

    return CrossCheckResult(
        status="AGREES" if not mismatches else "DISAGREES",
        source_path=source.as_posix(),
        projection_status=status,
        csv_bars=len(csv_by_ts),
        parquet_rows_read=rows_read,
        compared=compared,
        csv_only=len(set(csv_by_ts) - seen),
        parquet_only=len(seen - set(csv_by_ts)),
        mismatches=tuple(mismatches),
    )
