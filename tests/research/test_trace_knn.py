"""Trace k-NN similarity graph floor (ERP) — descriptive, deterministic, no edge field.

Validates the k-NN layer built on geometry.npz: exactly k neighbours per trace (no self-loops); the
summary carries the local-outcome-structure stats + the random-baseline comparison; nothing edge/promote;
deterministic on re-run. `slow` + SKIP if the geometry artifact is absent (gitignored).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_GEO = _ROOT / "results" / "research" / "trace_corpus" / "xauusd" / "geometry" / "geometry.npz"

pytestmark = [pytest.mark.research_integrity, pytest.mark.slow]
skip_no_geo = pytest.mark.skipif(not _GEO.exists(), reason="geometry.npz not built")


def _load_knn():
    spec = importlib.util.spec_from_file_location(
        "trace_knn", _ROOT / "scripts" / "research" / "trace_knn.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@skip_no_geo
def test_knn_graph_and_summary_descriptive():
    knn = _load_knn()
    summary, graph = knn.build(k=10, metric="cosine")

    # exactly k neighbours per trace, no self-loops
    assert len(graph) == summary["n_traces"]
    for g in graph[:200]:
        assert len(g["neighbours"]) == 10
        assert all(nb["trade_id"] != g["trade_id"] for nb in g["neighbours"])
    # local-outcome-structure stats + baseline present
    for key in ("neighbourhood_outcome_concordance", "neighbourhood_tp_rate",
                "random_baseline", "cross_cluster_edge_fraction", "local_density_dist_to_k"):
        assert key in summary, key
    assert "same_outcome_concordance" in summary["random_baseline"]
    # DESCRIPTIVE: no edge/verdict/promote key
    blob = json.dumps(summary)
    assert not any(tok in blob for tok in ("\"verdict\"", "\"promote\"", "\"edge\"", "\"profit\""))
    assert "not edges" in summary["banner"].lower()


@skip_no_geo
def test_knn_is_deterministic():
    knn = _load_knn()
    a, _ = knn.build(k=8, metric="cosine")
    b, _ = knn.build(k=8, metric="cosine")
    assert a == b
