"""Floor for src/utils/run_linkage.py — registry addressability.

The dual-construction source id has no results/run_*_XAUUSD directory (scratch
ledger deleted). A registry row that resolve_artifacts never consults is the
declared-but-unexecuted class (F-083). This floor pins: explicit run_id →
method=registry even when RESULTS_DIR is empty; latest-run (run_id=None) is
not rewritten to a registry id.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils import run_linkage as rl


def test_registry_path_is_tracked_binding_not_logs_occupancy():
    rel = rl.REGISTRY_PATH.resolve().relative_to(rl.REPO_ROOT).as_posix()
    assert rel == "docs/governance/run_linkage_registry.json"
    assert rl.REGISTRY_PATH.is_file()


def test_source_run_resolves_via_registry():
    out = rl.resolve_artifacts("XAUUSD", "run_20260906_013609")
    assert out["run_id"] == "run_20260906_013609"
    assert out["method"] == "registry"
    assert out["resolved_run"] is None
    assert out["logs"]["dir"]
    assert out["parquet"]
    dirs = [p["dir"].replace("\\", "/") for p in out["parquet"]]
    assert any("dual_construction_full_gapfix" in d and "crt_construction" in d for d in dirs)
    assert any("dual_construction_full_gapfix" in d and "bar_structure" in d for d in dirs)


def test_fourarm_run_resolves_via_registry_to_source_parquet():
    out = rl.resolve_artifacts("XAUUSD", "run_20260909_190546")
    assert out["method"] == "registry"
    assert out["source_run_id"] == "run_20260906_013609"
    assert out["scoreboard_dir"]
    assert "run_20260909_190546" in out["scoreboard_dir"].replace("\\", "/")


def test_schema_bridge_is_keyed_by_run_id():
    """Envelope run_id has the corpus/dataset/CAD pointers the files already carry."""
    out = rl.resolve_artifacts("XAUUSD", "run_20260909_202201")
    assert out["method"] == "registry"
    assert out["run_id"] == "run_20260909_202201"
    assert out["source_run_id"] == "run_20260906_013609"
    bridge = out["schema_bridge"]
    assert bridge["run_id"] == "run_20260909_202201"
    has = bridge["has"]
    assert has["source_run_id"] == "run_20260906_013609"
    assert has["logical_corpus_id"] == "XAUUSD_M15"
    assert has["decision_id"] == "CAD-XAUUSD_M15-PHASE1-FROZEN"
    assert has["dataset_id"] == "XAUUSD_MT5_PHASE1_20260521"
    assert has["canonical_artifact"]["sha256"].startswith("4d73f5ce")
    assert has["parent_timeframe_source"] == "derived_h4"
    assert has["approved_physical_path"] is None
    assert has["economic_claims_allowed"] is False
    assert has["coding_llm_context_pack"] == "docs/research/phase1_run_20260909_202201_coding_llm_context.yaml"
    # Omitted-ID rule (pack must stay projection of schema_bridge.has, no extras).
    assert "contract_id" not in has
    assert "mt00" not in has
    assert "finding_id" not in has
    assert "mx_id" not in has
    # Surfaces pin: pack<->registry anti-drift. Four-arm/lifecycle VALID.
    # CREATE session/hour/HTF/H20 were rebuilt on event-timestamp->CSV (2026-09-10) but the
    # rebuild alone did not resolve their admissibility: the 2026-09-10 surfaces_ruling
    # (forbidden_inferences outranks trust_table -- see run_linkage_registry.json's
    # surfaces_ruling block and CH-f069-epoch-scope) marks these three INVALIDATED. This pin
    # previously asserted VALID, which encoded the ruling's absence from the machine-readable
    # side rather than catching it (tests/test_run_linkage_traces.py now refuses a claim
    # citing any of the three).
    surfaces = bridge["surfaces"]
    assert surfaces["four_arm_economics"] == "VALID"
    assert surfaces["four_arm_H20"] == "VALID"
    assert surfaces["create_lifecycle_counts"] == "VALID"
    assert surfaces["create_session_hour_tables"] == "INVALIDATED"
    assert surfaces["create_htf_parent_context_tables"] == "INVALIDATED"
    assert surfaces["create_H20_context_economics"] == "INVALIDATED"
    assert surfaces["rebuild_completed"] is True
    src = rl.resolve_artifacts("XAUUSD", "run_20260906_013609")
    assert src["schema_bridge"]["run_id"] == "run_20260906_013609"
    assert src["schema_bridge"]["has"]["dataset_id"] == has["dataset_id"]


def test_unknown_run_id_stays_none():
    out = rl.resolve_artifacts("XAUUSD", "run_00000000_000000")
    assert out["method"] == "none"
    assert out["parquet"] == []


def test_registry_fires_when_results_dir_empty(tmp_path, monkeypatch):
    """The early-return bug: no results/run_* dir must not skip the registry."""
    results = tmp_path / "results"
    results.mkdir()
    logs = tmp_path / "dual"
    logs.mkdir()
    (logs / "XAUUSD_crt_construction.parquet").mkdir()
    reg = tmp_path / "reg.json"
    reg.write_text(
        json.dumps(
            {
                "XAUUSD": {
                    "run_20260906_013609": {
                        "logs_dir": str(logs),
                        "parquet_globs": [str(logs / "XAUUSD_crt_construction.parquet")],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rl, "RESULTS_DIR", results)
    monkeypatch.setattr(rl, "REGISTRY_PATH", reg)
    out = rl.resolve_artifacts("XAUUSD", "run_20260906_013609")
    assert out["method"] == "registry"
    assert out["resolved_run"] is None
    assert out["parquet"]


def test_latest_run_is_not_rewritten_to_registry_id():
    """run_id=None still means latest results/ backtest, not the observation emit."""
    out = rl.resolve_artifacts("XAUUSD", None)
    if out["resolved_run"] is None:
        pytest.skip("no results/run_*_XAUUSD ledger on this clone")
    assert out["run_id"] != "run_20260906_013609"
    assert out["run_id"] != "run_20260909_190546"
    assert out["run_id"] != "run_20260909_202201"
    assert str(out["run_id"]).endswith("_XAUUSD")
