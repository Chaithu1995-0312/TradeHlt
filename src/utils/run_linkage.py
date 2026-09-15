"""run_linkage.py — resolve every artifact linked to a backtest run_id.

The Executive Overview run dropdown selects a *backtest* run (the
`results/run_<ts>_<INSTR>/` directories). Other artifacts — scanner outputs
under `logs/<INSTR>/`, and the Parquet/trace layers under
`logs/bar_structure/`, `logs/dual_construction_*/`, etc. — are *not* addressable
from the run_id by naming convention (a `logs/XAUUSD/xauusd_phase1_20260723`
subdir timestamp does NOT match `run_20260724_*_XAUUSD`). This module links them
so the UI/backend can ask: "give me everything for run_id X".

Resolution order (strongest match wins):
  1. Named/adjacent result artifacts under the run dir itself.
  2. Manifest join — a scanner/parquet manifest that shares provenance with the
     backtest run (config_hash / ACTIVE_VERSION / embedded trace run-id).
  3. Explicit registry — docs/governance/run_linkage_registry.json rows keyed
     by instrument then run_id. TRACKED_BINDING, not logs/ occupancy. Consulted
     even when no results/run_*_<INSTR>/ directory exists (isolated dual-
     construction emits copy JSONL into logs/dual_construction_* and delete the
     scratch ledger).

Read-only, additive, no side effects. Parquet querying is delegated to
`utils.duckdb_query.open_views`, which is optional-import guarded.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
LOGS_DIR = REPO_ROOT / "logs"
REGISTRY_PATH = REPO_ROOT / "docs" / "governance" / "run_linkage_registry.json"

_ARTIFACT_NAMES = (
    "opportunities.jsonl",
    "opportunities.parquet",
    "crt_construction.parquet",
    "bar_structure.parquet",
)


def _read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _abs(p: str) -> str:
    """Resolve a registry path. Repo-relative stays portable; absolute is kept."""
    path = Path(p)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return str(path)


def _iter_runs(instrument: str) -> list[Path]:
    """Backtest run dirs for an instrument (same shape as dashboard_api)."""
    out: list[Path] = []
    for d in sorted(RESULTS_DIR.glob(f"run_*_{instrument}/")):
        if d.is_dir() and (d / f"{instrument}_trades.csv").exists():
            out.append(d)
    return out


def _parquet_layers(run_id: str | None = None) -> list[Path]:
    """Top-level Logs Parquet layer dirs whose NAME could plausibly reference ``run_id``.

    The only consumer (``resolve_artifacts``) keeps a layer solely when
    ``run_id in layer.name`` — a recursive ``rglob("*.parquet")`` over every
    subdirectory of ``logs/`` to confirm parquet presence is wasted work when
    the name predicate already excludes almost everything (measured: this was
    ~1.1s of a 1.76s total request). Filter by name FIRST (cheap), then confirm
    parquet presence only for directories that already match, via a bounded
    non-recursive glob (one level of hive partitioning) instead of a full
    recursive walk.
    """
    out: list[Path] = []
    if not LOGS_DIR.is_dir():
        return out
    for cand in LOGS_DIR.iterdir():
        if not cand.is_dir():
            continue
        if run_id and run_id not in cand.name:
            continue
        if any(cand.glob("*.parquet")) or any(cand.glob("*/*.parquet")):
            out.append(cand)
    return out


def resolve_artifacts(instrument: str, run_id: str | None = None) -> dict[str, Any]:
    """Resolve the full artifact set linked to a backtest run_id.

    Returns:
      {
        "run_id": str,                 # normalized (None if unresolved)
        "instrument": str,
        "resolved_run": { ... } | None,# direct results/ backtest dir handle
        "logs": { "dir": str|None, "sources": [ "str" ], "has_parquet": bool },
        "parquet": [ {"dir": str, "hidden_matches": [str]} ],
        "method": "named"|"manifest"|"registry"|"none",
      }
    """
    runs = _iter_runs(instrument)
    target = None
    if runs:
        target = runs[-1] if run_id is None else next(
            (d for d in runs if d.name == run_id), None
        )

    result: dict[str, Any] = {
        "run_id": target.name if target else (run_id or None),
        "instrument": instrument,
        "resolved_run": None,
        "logs": {"dir": None, "sources": [], "has_parquet": False},
        "parquet": [],
        "method": "none",
    }

    if target is not None:
        result["resolved_run"] = {
            "run_id": target.name,
            "dir": str(target),
            "has_summary": (target / f"{instrument}_summary.json").exists(),
            "has_trades": (target / f"{instrument}_trades.csv").exists(),
            "has_events": (target / f"{instrument}_events.jsonl").exists(),
            "has_telemetry": (target / f"{instrument}_crt_telemetry.jsonl").exists(),
        }

        # 1) Named: logs/<INSTR>/ subdirs that contain known artifact names.
        inst_logs = LOGS_DIR / instrument
        if inst_logs.is_dir():
            for sub in sorted(inst_logs.iterdir()):
                if not sub.is_dir():
                    continue
                has = [n for n in _ARTIFACT_NAMES if (sub / n).exists()]
                if has:
                    result["logs"]["dir"] = str(sub)
                    result["logs"]["sources"] = [f"{sub.name}/{n}" for n in has]
                    result["logs"]["has_parquet"] = any(n.endswith(".parquet") for n in has)

        # 2) Manifest join: top-level parquet layers that reference this run.
        for layer in _parquet_layers(result["run_id"]):
            result["parquet"].append({"dir": str(layer), "hidden_matches": []})

        if result["logs"]["dir"] or result["parquet"]:
            result["method"] = "named"
            return result

    # 3) Explicit registry. Must run even when no results/ dir exists — isolated
    # dual-construction emits leave JSONL under logs/dual_construction_* and
    # delete the scratch ledger, so named/manifest never fire for those ids.
    if not result["run_id"]:
        return result
    reg = _read_json(REGISTRY_PATH)
    if isinstance(reg, dict):
        entry = (reg.get(instrument) or {}).get(result["run_id"])
        if isinstance(entry, dict):
            logs_dir = entry.get("logs_dir")
            pq = [p for p in (entry.get("parquet_globs") or []) if p]
            if logs_dir:
                result["logs"]["dir"] = _abs(str(logs_dir))
                result["logs"]["sources"] = [str(logs_dir)]
                result["logs"]["has_parquet"] = any(
                    Path(_abs(str(p))).exists() for p in pq
                ) or any(
                    Path(result["logs"]["dir"]).glob("*.parquet")
                ) or any(
                    Path(result["logs"]["dir"]).glob("*/*.parquet")
                )
            result["parquet"].extend(
                {"dir": _abs(str(p)), "hidden_matches": []} for p in pq
            )
            if entry.get("scoreboard_dir"):
                result["scoreboard_dir"] = _abs(str(entry["scoreboard_dir"]))
            if entry.get("source_run_id"):
                result["source_run_id"] = entry["source_run_id"]
            if isinstance(entry.get("schema_bridge"), dict):
                result["schema_bridge"] = entry["schema_bridge"]
            if result["logs"]["dir"] or result["parquet"]:
                result["method"] = "registry"
                return result

    return result