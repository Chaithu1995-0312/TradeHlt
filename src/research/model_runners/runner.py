"""Orchestrate substrate × adapter → artifacts (OBSERVATION_ONLY)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from research.model_runners.adapters import build_adapter
from research.model_runners.contracts import get_contract
from research.model_runners.envelope import (
    RECORD_SCHEMA,
    MANIFEST_SCHEMA,
    RunManifest,
    RunRecord,
    collect_code_provenance,
    make_run_id,
    parse_formats,
    utc_now_iso,
    write_csv_from_records,
    write_json,
    write_jsonl,
)
from research.model_runners.require_config import (
    load_production_json,
    require_key,
    require_section,
    sha256_file,
)
from research.model_runners.stats import array_stats
from research.model_runners.substrate import (
    build_feature_substrate,
    iter_bar_contexts,
    select_window,
)


@dataclass(frozen=True)
class RunRequest:
    model_id: str
    csv_path: Path
    instrument: str
    out_dir: Path
    repo_root: Path
    config_path: Path | None
    start: str | None
    end: str | None
    limit: int | None
    formats: str | None
    artifact: Path | None = None
    emit: str | None = None


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    manifest_path: Path
    n_ok: int
    n_error: int


def run_model(req: RunRequest) -> RunResult:
    contract = get_contract(req.model_id)
    if not req.instrument:
        raise ValueError("--instrument is required and must be non-empty")

    prod_config, config_path = load_production_json(
        repo_root=req.repo_root, config_path=req.config_path
    )
    config_sha = sha256_file(config_path)

    # A7: error-rate gate. Strict read — model_runners.max_error_rate must exist.
    mr_cfg = require_section(prod_config, "model_runners")
    max_error_rate = float(require_key(mr_cfg, "max_error_rate", path="model_runners"))
    if not 0.0 <= max_error_rate <= 1.0:
        raise ValueError(
            f"model_runners.max_error_rate must be in [0,1], got {max_error_rate}"
        )

    csv_path = (
        req.csv_path
        if req.csv_path.is_absolute()
        else (req.repo_root / req.csv_path)
    )
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    substrate = build_feature_substrate(csv_path)

    start_ts = pd.Timestamp(req.start) if req.start is not None else None
    end_ts = pd.Timestamp(req.end) if req.end is not None else None
    if (req.start is None) ^ (req.end is None):
        # Allow either bound alone; both optional. No hidden window.
        pass
    window_df = select_window(
        substrate.enriched,
        start=start_ts,
        end=end_ts,
        limit=req.limit,
    )
    if len(window_df) == 0:
        raise RuntimeError(
            "selected window has 0 bars after FeaturePipeline warmup/filter"
        )

    art = req.artifact
    if art is not None and not art.is_absolute():
        art = req.repo_root / art
    adapter = build_adapter(
        req.model_id,
        prod_config=prod_config,
        instrument=req.instrument,
        repo_root=req.repo_root,
        artifact=art,
        emit=req.emit,
        ohlcv_csv=csv_path,
    )

    records: list[RunRecord] = []
    score_values: list[float] = []
    n_ok = 0
    n_error = 0

    for bar in iter_bar_contexts(window_df):
        try:
            native = adapter.score_bar(bar)
            rec = RunRecord(
                schema=RECORD_SCHEMA,
                model_id=req.model_id,
                instrument=req.instrument,
                bar_index=bar.bar_index,
                timestamp=bar.timestamp,
                status="ok",
                native=native,
                error=None,
            )
            n_ok += 1
            if "score" in native and isinstance(native["score"], (int, float)):
                score_values.append(float(native["score"]))
        except Exception as exc:
            rec = RunRecord(
                schema=RECORD_SCHEMA,
                model_id=req.model_id,
                instrument=req.instrument,
                bar_index=bar.bar_index,
                timestamp=bar.timestamp,
                status="error",
                native={},
                error=f"{type(exc).__name__}: {exc}",
            )
            n_error += 1
        records.append(rec)

    formats = parse_formats(req.formats)
    run_id = make_run_id()
    run_dir = (
        Path(req.out_dir)
        / req.model_id
        / req.instrument
        / run_id
    )
    if not run_dir.is_absolute():
        run_dir = req.repo_root / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "n_ok": n_ok,
        "n_error": n_error,
        "n_bars": len(records),
        "score_stats": array_stats(score_values) if score_values else {"n": 0},
    }

    manifest = RunManifest(
        schema=MANIFEST_SCHEMA,
        authority="research_only",
        PRODUCTION_BEHAVIOR_CHANGED=False,
        model_id=req.model_id,
        instrument=req.instrument,
        config_path=str(config_path),
        config_sha256=config_sha,
        csv_path=str(substrate.csv_path),
        csv_sha256=substrate.csv_sha256,
        window={
            "start": req.start,
            "end": req.end,
            "limit": req.limit,
            "n_loaded_rows": substrate.n_loaded_rows,
            "n_enriched_rows": substrate.n_enriched_rows,
            "n_bars_scored": len(records),
        },
        feature_schema=substrate.feature_schema,
        artifact=adapter.artifact_info,
        config_sections_read=list(adapter.config_sections_read),
        config_keys_read=list(adapter.config_keys_read),
        entry_point=contract.entry_point,
        spine_active=contract.spine_active,
        created_at=utc_now_iso(),
        summary_stats=summary,
        n_ok=n_ok,
        n_error=n_error,
        run_id=run_id,
        out_dir=str(run_dir),
        code_provenance=collect_code_provenance(req.repo_root),
    )

    if "jsonl" in formats:
        write_jsonl(run_dir / "scores.jsonl", records)
    if "csv" in formats:
        write_csv_from_records(run_dir / "scores.csv", records)
    if "summary" in formats:
        write_json(run_dir / "summary.json", summary)
    if "manifest" in formats:
        write_json(run_dir / "manifest.json", manifest.to_dict())

    latest_path = run_dir.parent / "LATEST.json"
    write_json(
        latest_path,
        {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "model_id": req.model_id,
            "instrument": req.instrument,
            "created_at": manifest.created_at,
        },
    )

    # A7: fail loudly on a run whose artifacts would otherwise look legitimate.
    # Artifacts are written FIRST so the failure is diagnosable, then the run is
    # rejected — a manifest at n_ok=0 must never be mistaken for a clean run.
    n_bars = len(records)
    error_rate = (n_error / n_bars) if n_bars else 0.0
    if error_rate > max_error_rate:
        sample = next(
            (r.error for r in records if r.status == "error" and r.error), "n/a"
        )
        raise RuntimeError(
            f"model_runners error-rate gate FAILED for model_id={req.model_id!r}: "
            f"{n_error}/{n_bars} bars errored (rate={error_rate:.4f}) exceeds "
            f"model_runners.max_error_rate={max_error_rate}. "
            f"Artifacts written to {run_dir} for diagnosis. First error: {sample}"
        )

    return RunResult(
        run_id=run_id,
        run_dir=run_dir,
        manifest_path=run_dir / "manifest.json",
        n_ok=n_ok,
        n_error=n_error,
    )
