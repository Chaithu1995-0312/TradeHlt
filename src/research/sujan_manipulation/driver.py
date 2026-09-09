"""SUJAN_MANIPULATION_RESEARCH_PHASE_1 run driver (SEM-033). Research only.

Loads a corpus, resolves EXTERNALLY-SUPPLIED parent bulk candles, streams bars through
the Phase-1 state machine, and writes the alert stream plus a manifest recording exactly
what was measured and what was not.

NOT IN THIS FILE, BY SPECIFICATION
----------------------------------
No entry, no stop, no target, no ``forward_walk``, no cost model, no controls, no split,
no expectancy, no measurement contract. Phase 1 emits an alert and stops. The alert COUNT
is an observation, never a result: nothing here derives a rate, a quality, or an economic
reading from it.

``runtime.backtest_v2`` is deliberately not used for loading — the CSV parse is local,
matching the isolation idiom every ``src/research/`` program uses.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from data_ingestion.dataset_integrity import validate_dataset

from research.sujan_manipulation.bulk_proxy import (
    FROZEN_TOP_N,
    PROXY_ID,
    PROXY_STATUS,
    RankedCandidate,
    build_selectors,
    overlap_indices,
)
from research.sujan_manipulation.geometry import ALERT_KIND, ManipulationEvent
from research.sujan_manipulation.label_page import (
    confirmed_parents_template,
    render as render_label_page,
)
from research.sujan_manipulation.parquet_check import (
    DEFAULT_CLEAN_LABELS,
    ParquetCheckUnavailable,
    cross_check,
)
from research.sujan_manipulation.parent import (
    BULK_CANDLE_EVIDENCE,
    BULK_CANDLE_SELECTOR,
    Bar,
    ExplicitTimestampSelector,
    ParentBulkCandle,
    load_parent_timestamps,
)
from research.sujan_manipulation.state import ManipulationRunner, StateTransition

OBJECT_ID = "SUJAN_MANIPULATION_RESEARCH_PHASE_1"
SEM_ID = "SEM-033"
CORPUS = Path("data/mt5/XAUUSD_M15.csv")
BAR_MINUTES = 15


def _parse_ts(raw: str) -> datetime:
    s = str(raw).strip().replace("T", " ")
    return datetime.fromisoformat(s[:19])


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_bars(path: Path) -> list[Bar]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    return [
        Bar(
            timestamp=_parse_ts(row["timestamp"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume") or 0.0),
            index=i,
        )
        for i, row in enumerate(rows)
    ]


def _alert_record(event: ManipulationEvent) -> dict[str, Any]:
    return {
        "event": ALERT_KIND,
        # ── the three fields the Phase-1 specification requires ──────────
        "parent_timestamp": event.parent_timestamp.isoformat(sep=" "),
        "manipulation_timestamp": event.manipulation_timestamp.isoformat(sep=" "),
        "side": event.side.value,
        # ── provenance ───────────────────────────────────────────────────
        "object": OBJECT_ID,
        "sem_id": SEM_ID,
        "parent_index": event.parent_index,
        "manipulation_index": event.manipulation_index,
        "range_high": event.range_high,
        "range_low": event.range_low,
        "bar_high": event.bar_high,
        "bar_low": event.bar_low,
        "bar_close": event.bar_close,
        "economic_claims_allowed": False,
    }


def _transition_record(t: StateTransition) -> dict[str, Any]:
    return {
        "parent_timestamp": t.parent_timestamp.isoformat(sep=" "),
        "from": t.from_state.value,
        "to": t.to_state.value,
        "bar_index": t.bar_index,
        "bar_timestamp": None if t.bar_timestamp is None else t.bar_timestamp.isoformat(sep=" "),
    }


def run(
    corpus: Path,
    parents_path: Path,
    *,
    instrument: str | None = None,
    preflight: bool = True,
) -> dict[str, Any]:
    """Execute one Phase-1 detection run and return the report."""
    corpus = Path(corpus)
    parents_path = Path(parents_path)
    if preflight:
        validate_dataset(
            str(corpus), instrument=instrument, bar_minutes=BAR_MINUTES, write_report=False
        )

    bars = load_bars(corpus)
    if not bars:
        raise ValueError(f"{corpus}: no bars loaded")

    timestamps = load_parent_timestamps(parents_path)
    selector = ExplicitTimestampSelector(
        timestamps, source=f"externally supplied: {parents_path.as_posix()}"
    )
    parents: Sequence[ParentBulkCandle] = selector.select(bars)

    runner = ManipulationRunner.from_parents(parents)
    events = runner.run(bars)

    return {
        "object": OBJECT_ID,
        "sem_id": SEM_ID,
        "phase": 1,
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {
            "path": corpus.as_posix(),
            "sha256": _sha256(corpus),
            "n_bars": len(bars),
            "first_timestamp": bars[0].timestamp.isoformat(sep=" "),
            "last_timestamp": bars[-1].timestamp.isoformat(sep=" "),
        },
        "parents": {
            "path": parents_path.as_posix(),
            "sha256": _sha256(parents_path),
            "n_supplied": len(parents),
            "source": selector.source,
            "timestamps": [p.timestamp.isoformat(sep=" ") for p in parents],
        },
        "bulk_candle_selector": {
            "status": BULK_CANDLE_SELECTOR,
            "evidence": list(BULK_CANDLE_EVIDENCE),
            "note": (
                "No selector ships in this package. Parent bulk candles are supplied "
                "externally by the human bridge. Resolving this requires a recorded freeze."
            ),
        },
        "predicate": {
            "purge": "SP-001 structure.predicates.swept_high / swept_low (strict both sides)",
            "closes_back_inside": "range_low < close < range_high (literal reading, bridge Record 5)",
            "alternative_reading_preserved": (
                "SP-001-only (closed back past the purged side) is re-derivable from every "
                "alert's bar_close / range_high / range_low fields without a re-run."
            ),
            "same_candle": "purge and close-back-inside are properties of ONE later candle",
        },
        "alerts": [_alert_record(e) for e in events],
        "state_trace": [_transition_record(t) for t in runner.trace],
        "n_alerts": len(events),
        "economic_claims_allowed": False,
        "authority": (
            "Detection only. The alert count is an observation, not a result. No entry, "
            "no outcome, no expectancy, no G001, no production authority."
        ),
    }


def write_report(report: dict[str, Any], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "alerts.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in report["alerts"]),
        encoding="utf-8",
    )
    (out_dir / "state_trace.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in report["state_trace"]),
        encoding="utf-8",
    )
    manifest = {k: v for k, v in report.items() if k not in ("alerts", "state_trace")}
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


# ─────────────────────────────────────────────────────────────────────────
# SEM-034 candidate shortlist (the proxy path)
#
# Separate from `run()` above on purpose. `run()` DETECTS against parents that already
# exist; this SHORTLISTS candles for the human bridge to confirm into parents. A candidate
# is not a parent, and this function never feeds one to the detector.
# ─────────────────────────────────────────────────────────────────────────

def _candidate_record(c: RankedCandidate) -> dict[str, Any]:
    return {
        "timestamp": c.parent.timestamp.isoformat(sep=" "),
        "bar_index": c.parent.index,
        "rank": c.rank,
        "ranking": c.ranking,
        "magnitude": c.magnitude,
        "high": c.parent.high,
        "low": c.parent.low,
        "proxy_id": PROXY_ID,
        "proxy_status": PROXY_STATUS,
        "confirmed": False,
        "economic_claims_allowed": False,
    }


def _temporal_coverage(
    bars: Sequence[Bar], ranked: dict[str, Sequence[RankedCandidate]]
) -> dict[str, Any]:
    """Where the shortlist actually falls in time.

    Recorded because "top-N over the whole corpus" has a known and unavoidable property:
    it concentrates on the most volatile stretches, so quiet months can contribute NOTHING.
    That is the rule behaving as specified, not a defect — but a reader must not mistake a
    shortlist for a survey of the corpus. Measured here so the artifact says it out loud.
    """
    corpus_months = sorted({bar.timestamp.strftime("%Y-%m") for bar in bars})
    out: dict[str, Any] = {
        "corpus_months": len(corpus_months),
        "note": (
            "Top-N over the whole corpus concentrates on high-volatility periods by "
            "construction. Months with zero candidates are NOT evidence that they contain "
            "no bulk candles."
        ),
    }
    for ranking, cands in ranked.items():
        hit: dict[str, int] = {}
        for c in cands:
            key = c.parent.timestamp.strftime("%Y-%m")
            hit[key] = hit.get(key, 0) + 1
        out[ranking] = {
            "months_represented": len(hit),
            "months_empty": len(corpus_months) - len(hit),
            "by_month": dict(sorted(hit.items())),
        }
    return out


def run_candidates(
    corpus: Path,
    *,
    top_n: int,
    instrument: str | None = None,
    preflight: bool = True,
    verify_parquet: bool = False,
    parquet_source: Path | str = DEFAULT_CLEAN_LABELS,
) -> dict[str, Any]:
    """Shortlist bulk-candle candidates under the SEM-034 proxy. Detection does not run."""
    corpus = Path(corpus)
    if preflight:
        validate_dataset(
            str(corpus), instrument=instrument, bar_minutes=BAR_MINUTES, write_report=False
        )

    bars = load_bars(corpus)
    if not bars:
        raise ValueError(f"{corpus}: no bars loaded")

    range_sel, body_sel = build_selectors(top_n)
    ranked = {
        range_sel.ranking: range_sel.rank(bars),
        body_sel.ranking: body_sel.rank(bars),
    }
    overlap = overlap_indices(ranked[range_sel.ranking], ranked[body_sel.ranking])

    cross: dict[str, Any]
    if verify_parquet:
        try:
            cross = cross_check(bars, source=parquet_source).as_dict()
        except ParquetCheckUnavailable as exc:
            # Fail closed and SAY SO. A skipped check must never read as a passed one.
            cross = {"status": "UNAVAILABLE", "reason": str(exc)}
    else:
        cross = {"status": "SKIPPED", "reason": "--verify-parquet not requested"}

    return {
        "object": OBJECT_ID,
        "sem_id": SEM_ID,
        "mode": "candidates",
        "phase": 1,
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {
            "path": corpus.as_posix(),
            "sha256": _sha256(corpus),
            "n_bars": len(bars),
            "first_timestamp": bars[0].timestamp.isoformat(sep=" "),
            "last_timestamp": bars[-1].timestamp.isoformat(sep=" "),
        },
        "proxy": {
            "id": PROXY_ID,
            "status": PROXY_STATUS,
            "rule": "top-N over the whole corpus, per ranking, ties broken by ascending bar index",
            "top_n": top_n,
            "frozen_top_n": FROZEN_TOP_N,
            "rankings": list(ranked),
            "magnitude_source": "features.candle_math FM-002 candle_range / FM-001 body_size",
            "note": (
                "Bridge-approved mechanical proxy for a VISUAL concept (drift log Record 6). "
                "UNVALIDATED: never agreement-checked against a hand-labelled set. UNK-007 "
                "stays OPEN. A candidate is not a parent until the bridge confirms it."
            ),
        },
        "overlap": {
            "bar_indices": list(overlap),
            "count": len(overlap),
            "note": (
                "Reported, never merged. The two rankings measure DIFFERENT quantities "
                "(often large-bodied vs may be wick-dominant); where they disagree is "
                "information about how under-determined the concept is."
            ),
        },
        "temporal_coverage": _temporal_coverage(bars, ranked),
        "parquet_cross_check": cross,
        "candidates": {
            ranking: [_candidate_record(c) for c in cands] for ranking, cands in ranked.items()
        },
        "economic_claims_allowed": False,
        "authority": (
            "Shortlist only. No detection ran. The candidate count is an observation, not a "
            "result, and says nothing about the market or about what Sujan means."
        ),
        "_bars": bars,
        "_ranked": ranked,
        "_overlap": overlap,
    }


def write_candidates(report: dict[str, Any], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for ranking, rows in report["candidates"].items():
        (out_dir / f"candidates_{ranking}.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8"
        )

    (out_dir / "candidates.html").write_text(
        render_label_page(
            report["_bars"],
            report["_ranked"],
            corpus_path=report["corpus"]["path"],
            overlap=report["_overlap"],
        ),
        encoding="utf-8",
    )

    manifest = {
        k: v for k, v in report.items() if k not in ("candidates", "_bars", "_ranked", "_overlap")
    }
    manifest["candidate_counts"] = {k: len(v) for k, v in report["candidates"].items()}
    (out_dir / "candidates_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "confirmed_parents.template.json").write_text(
        confirmed_parents_template(), encoding="utf-8"
    )
