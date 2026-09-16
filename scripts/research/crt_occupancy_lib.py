"""REM-CRT-02 shared CRT occupancy feeder helpers (research-only).

Used by:
  - scripts/research/crt_occupancy_feeder_smoke.py
  - scripts/live/run_live_rail.py --crt-occupancy-sidecar (paper only)

Does not change ACTIVE_VERSION, tokens.py, or Ultron live orders.
CRT occupancy is ADDITIVE chart/alert dual-write — never a broker shortcut.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION_DEFAULT = "v2_htfcrt_2026_08"
INSTRUMENT_DEFAULT = "XAUUSD"
CSV_DEFAULT = "data/mt5/XAUUSD_M15.csv"
REMEDIATION = "REM-CRT-02"

logger = logging.getLogger("crt_occupancy_lib")


def limited_stream(loader, limit: int):
    """Thin wrapper: stop after N candles; same Candle objects as full stream."""
    return itertools.islice(loader.stream(), limit)


def promote_events(scratch: Path, out_dir: Path, instrument: str) -> Path:
    hits = sorted(scratch.rglob(f"{instrument}_events.jsonl"), key=lambda p: p.stat().st_mtime)
    if not hits:
        raise FileNotFoundError(f"no {instrument}_events.jsonl under {scratch}")
    dest = out_dir / f"{instrument}_events.jsonl"
    shutil.copy2(hits[-1], dest)
    return dest


def verify_chart_parseable(events_path: Path, sample_n: int = 64) -> dict[str, Any]:
    """Import crt_overlay parsers; optionally track_from_events on event timestamps."""
    from charts import crt_overlay as co

    parsed = co._parse_state_events(events_path)
    state_names = sorted({st for _ci, st, _ts in parsed})
    event_counts: Counter = Counter()
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_counts[str(rec.get("event", "?"))] += 1

    track_ok = False
    track_err = None
    track_source = None
    if parsed:
        # base_ts must cover EVERY state-event timestamp.
        _ = sample_n  # noqa: F841 — kept for signature stability
        seen = []
        seen_set = set()
        for _ci, _st, ts in parsed:
            if ts not in seen_set:
                seen_set.add(ts)
                seen.append(ts)
        base_ts = sorted(seen)
        try:
            track = co.track_from_events(events_path, base_ts, VERSION_DEFAULT)
            track_ok = not str(getattr(track, "source", "")).startswith("UNAVAILABLE")
            track_source = getattr(track, "source", None)
            if not track_ok:
                track_err = track_source
        except Exception as exc:  # noqa: BLE001
            track_err = f"{type(exc).__name__}: {exc}"

    return {
        "n_events_total": sum(event_counts.values()),
        "n_stateish": event_counts.get("STATE_TRANSITION", 0)
        + event_counts.get("RESET", 0),
        "event_counts": dict(event_counts),
        "n_parsed_state_events": len(parsed),
        "sample_state_names": state_names[:20],
        "chart_overlay_parseable": len(parsed) > 0,
        "track_from_events_ok": track_ok,
        "track_from_events_source": track_source,
        "track_from_events_error": track_err,
    }


def run_crt_occupancy_feeder(
    *,
    out_dir: Path | str,
    limit: int = 3000,
    csv: str = CSV_DEFAULT,
    instrument: str = INSTRUMENT_DEFAULT,
    version: str = VERSION_DEFAULT,
    skip_features: bool = True,
    source: str = "dual_write_smoke",
    verify: bool = True,
) -> dict[str, Any]:
    """Drive BacktestRunner over a limited CandleLoader stream; write events + meta.

    Sets BACKTEST_ENGINE_GATE=0 for this call only (restored in finally).
    Pins PROD_VERSION in-process only — never writes ACTIVE_VERSION.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = out_dir / "_runner_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    gate_prev = os.environ.get("BACKTEST_ENGINE_GATE")
    os.environ["BACKTEST_ENGINE_GATE"] = "0"

    import config_layer.production_config as _pc
    import runtime.backtest_v2 as _bt
    from config_layer.production_config import load_prod_config_from_registry
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader

    _pc_prev, _bt_prev = _pc.PROD_VERSION, _bt.PROD_VERSION
    _pc.PROD_VERSION = version
    _bt.PROD_VERSION = version
    n = 0
    total_available = 0
    try:
        crt_cfg = load_prod_config_from_registry(version, instrument)
        pip = _bt.MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.01)
        cfg = BacktestConfig.from_prod_config(
            instrument=instrument,
            pip_size=pip,
            crt_config=crt_cfg,
        )
        cfg.instrument = instrument
        cfg.pip_size = pip

        loader = CandleLoader(csv, instrument)
        total_available = loader.count()
        n = min(int(limit), total_available)
        logger.info(
            "REM-CRT-02 feeder | ver=%s | limit=%d (csv=%d) | skip_features=%s | gate=%s | out=%s",
            version,
            n,
            total_available,
            skip_features,
            os.environ.get("BACKTEST_ENGINE_GATE"),
            out_dir,
        )

        runner = BacktestRunner(
            cfg,
            csv_path=csv if not skip_features else None,
            skip_features=skip_features,
            overrides={
                "_research_feeder": REMEDIATION,
                "_authority": "RESEARCH_ONLY",
            },
        )
        runner.run(limited_stream(loader, n), n, str(scratch))
    finally:
        _pc.PROD_VERSION = _pc_prev
        _bt.PROD_VERSION = _bt_prev
        if gate_prev is None:
            os.environ.pop("BACKTEST_ENGINE_GATE", None)
        else:
            os.environ["BACKTEST_ENGINE_GATE"] = gate_prev

    events_path = promote_events(scratch, out_dir, instrument)
    n_lines = sum(1 for _ in open(events_path, encoding="utf-8") if _.strip())
    if n_lines <= 0:
        raise RuntimeError(f"events file empty: {events_path}")

    meta = {
        "constructor_id": "engine",
        "remediation": REMEDIATION,
        "authority": "RESEARCH_ONLY",
        "source": source,
        "parent_schema": "live_chart_bind_v1",
        "alert_schema": "live_alert_v1",
        "version": version,
        "instrument": instrument,
        "csv": csv,
        "limit": n,
        "candles_available": total_available,
        "skip_features": skip_features,
        "backtest_engine_gate": "0",
        "events_path": str(events_path).replace("\\", "/"),
        "n_events": n_lines,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "notes": (
            "BacktestRunner + CandleLoader islice; BACKTEST_ENGINE_GATE=0 during feeder only; "
            "no Ultron live submit; ACTIVE_VERSION file not modified; "
            "no CRT→broker shortcut."
        ),
    }
    meta_path = out_dir / "FEEDER_META.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    result: dict[str, Any] = {
        "ok": True,
        "out_dir": str(out_dir).replace("\\", "/"),
        "events_path": str(events_path).replace("\\", "/"),
        "meta_path": str(meta_path).replace("\\", "/"),
        "n_events": n_lines,
        "limit": n,
        "instrument": instrument,
        "version": version,
        "meta": meta,
    }

    if verify:
        verify_payload = verify_chart_parseable(events_path)
        verify_payload.update(
            {
                "events_path": str(events_path).replace("\\", "/"),
                "events_nonempty": n_lines > 0,
                "remediation": REMEDIATION,
                "verified_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        verify_path = out_dir / "FEEDER_VERIFY.json"
        verify_path.write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")
        result["verify_path"] = str(verify_path).replace("\\", "/")
        result["verify"] = verify_payload

    return result


def write_sidecar_meta(
    *,
    paper_run_dir: Path | str,
    crt_occupancy_dir: Path | str,
    events_path: Path | str,
    feeder_result: dict[str, Any] | None = None,
    arm: str | None = None,
    corpus: str | None = None,
    limit: int | None = None,
) -> Path:
    """Link paper rail report-dir to CRT occupancy dual-write artifacts."""
    paper_run_dir = Path(paper_run_dir)
    crt_occupancy_dir = Path(crt_occupancy_dir)
    events_path = Path(events_path)
    n_events = None
    if feeder_result is not None:
        n_events = feeder_result.get("n_events")
    if n_events is None and events_path.is_file():
        n_events = sum(1 for _ in open(events_path, encoding="utf-8") if _.strip())

    payload = {
        "remediation": REMEDIATION,
        "authority": "RESEARCH_ONLY",
        "role": "crt_occupancy_sidecar",
        "parent_schema": "live_chart_bind_v1",
        "alert_schema": "live_alert_v1",
        "paper_run_dir": str(paper_run_dir).replace("\\", "/"),
        "crt_occupancy_dir": str(crt_occupancy_dir).replace("\\", "/"),
        "events_path": str(events_path).replace("\\", "/"),
        "n_events": n_events,
        "arm": arm,
        "corpus": corpus,
        "limit": limit,
        "design": (
            "ADDITIVE dual-write beside paper live rail; "
            "orders still via EngineRunner/HookedLiveEngine; "
            "CRT feeder never submits to broker."
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    if feeder_result and isinstance(feeder_result.get("meta"), dict):
        payload["feeder_meta"] = feeder_result["meta"]
    dest = paper_run_dir / "SIDECAR_META.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest
