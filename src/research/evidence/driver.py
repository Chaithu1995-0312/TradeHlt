"""Load the four projections and emit an evidence report.

JSONL is the system of record. When the parquet sidecar is FRESH we read it for
column pruning; otherwise `iter_records` falls back to JSONL.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research.evidence.catalog import SURFACES, Surface, assert_join
from research.evidence.queries import (
    answer_question,
    join_cols,
    rows_to_cols,
    run_named,
)
from research.evidence.records import EvidenceRecord
from utils.parquet_store import FRESH, iter_records, parquet_available, projection_status

_REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUT = _REPO / "results/research/parquet_evidence_layer"


@dataclass
class DriverConfig:
    out_dir: Path = DEFAULT_OUT
    question: str | None = None
    atlas: str | None = None
    max_rows: int | None = None


def _read_parquet_cols(parquet_path: Path, max_rows: int | None) -> dict[str, list]:
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq

    if parquet_path.is_dir():
        table = ds.dataset(str(parquet_path), format="parquet").to_table()
    else:
        table = pq.read_table(parquet_path)
    if max_rows is not None:
        table = table.slice(0, max_rows)
    return {name: table.column(name).to_pylist() for name in table.column_names}


def _load_surface(surf: Surface, max_rows: int | None) -> list[dict]:
    src = surf.jsonl
    if not src.exists():
        return []
    rows: list[dict] = []
    for rec in iter_records(src):
        if rec.get("type") == "run_header" or rec.get("kind") == "run_header":
            continue
        rows.append(rec)
        if max_rows is not None and len(rows) >= max_rows:
            break
    return rows


def _load_cols(surf: Surface, max_rows: int | None) -> dict[str, list]:
    src = surf.jsonl
    pq_path = src.with_suffix(".parquet")
    if projection_status(src) == FRESH and parquet_available() and pq_path.exists():
        return _read_parquet_cols(pq_path, max_rows)
    rows = _load_surface(surf, max_rows)
    return rows_to_cols(rows) if rows else {}


def _n(cols: dict[str, list]) -> int:
    if not cols:
        return 0
    return len(next(iter(cols.values())))


def _grain_check(opp: dict[str, list], lab: dict[str, list]) -> dict[str, Any]:
    ots = [str(x) for x in (opp.get("timestamp") or [])]
    lts = [str(x) for x in (lab.get("decision_ts") or lab.get("timestamp") or [])]
    unique_ts = len(set(ots))
    n_opp, n_lab = len(ots), len(lts)
    return {
        "opportunities_n": n_opp,
        "clean_labels_n": n_lab,
        "unique_timestamps": unique_ts,
        "bar_x_direction_matches": bool(
            unique_ts and n_opp == unique_ts * 2 and n_lab == n_opp
        ),
        "timestamp_overlap": len(set(ots) & set(lts)),
        "join": "legal",
    }


def run(cfg: DriverConfig | None = None) -> dict[str, Any]:
    cfg = cfg or DriverConfig()
    assert_join("opportunities", "clean_labels")
    assert_join("events", "telemetry")

    status = {sid: projection_status(s.jsonl) for sid, s in SURFACES.items()}
    loaded_cols = {sid: _load_cols(surf, cfg.max_rows) for sid, surf in SURFACES.items()}
    loaded_n = {k: _n(v) for k, v in loaded_cols.items()}

    lab_cols = loaded_cols["clean_labels"]
    opp_cols = loaded_cols["opportunities"]
    grain = _grain_check(opp_cols, lab_cols)
    if lab_cols and opp_cols:
        lab_cols = join_cols(opp_cols, lab_cols)
        grain["joined_n"] = _n(lab_cols)
    tel_cols = loaded_cols["telemetry"] or None
    ev_cols = loaded_cols["events"] or None

    if cfg.atlas:
        recs = run_named(cfg.atlas, lab=lab_cols or None, tel=tel_cols, ev=ev_cols)
        route = cfg.atlas
    elif cfg.question:
        recs = answer_question(cfg.question, lab=lab_cols or None, tel=tel_cols, ev=ev_cols)
        route = recs[0].extra.get("route") if recs else None
    else:
        recs = []
        if lab_cols:
            for name in (
                "census", "regimes", "quality", "exits", "ontology", "graph",
                "leakage", "state_value", "asymmetry",
            ):
                recs.extend(run_named(name, lab=lab_cols, tel=tel_cols, ev=ev_cols))
        if tel_cols:
            recs.extend(run_named("lifecycle", lab=lab_cols, tel=tel_cols, ev=ev_cols))
        route = "all"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "change_id": "CH-evidence-atlases",
        "authority": "RESEARCH_ONLY",
        "parquet_available": parquet_available(),
        "projection_status": status,
        "fresh": {k: v == FRESH for k, v in status.items()},
        "loaded_n": loaded_n,
        "grain": grain,
        "question": cfg.question,
        "route": route,
        "n_records": len(recs),
        "records": [r.to_dict() if isinstance(r, EvidenceRecord) else r for r in recs],
        "not": [
            "training dataset",
            "XGBoost feature store",
            "production authority",
            "one shared lifecycle across all four files",
        ],
    }
    return report


def write_report(report: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    # compact candidate-finding index
    idx = [
        {
            "question": r["question"],
            "n": r["n"],
            "effect_name": r["effect_name"],
            "effect_size": r["effect_size"],
            "confidence": r["confidence"],
            "candidate_finding": r["candidate_finding"],
        }
        for r in report["records"]
        if r.get("effect_name") not in {"features_enumerated", "no_redetection",
                                        "coincidence_not_certification", "not_joined_to_94k"}
        or "quality" in r.get("question", "")
    ]
    (out_dir / "candidate_findings.json").write_text(
        json.dumps(idx, indent=2, default=str), encoding="utf-8"
    )
    atlas = {
        "leakage": [r for r in report["records"] if "leak" in r.get("question", "")],
        "state_value": [r for r in report["records"] if r.get("question", "").startswith("state value")],
        "asymmetry": [r for r in report["records"] if "asymmetry" in r.get("question", "")],
    }
    (out_dir / "atlases.json").write_text(
        json.dumps(atlas, indent=2, default=str), encoding="utf-8"
    )
    return path
