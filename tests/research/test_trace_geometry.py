"""Trace Geometry floor (ERP) — descriptive clustering, deterministic, no edge field.

Validates the descriptive cluster layer over the trace corpus: a k is chosen by silhouette; cluster
sizes account for every kept trace; the cluster library has the required descriptive fields and carries
NO edge/promote/verdict key; and labels are deterministic (fixed seed → identical on re-run). `slow` +
SKIP-if-corpus-absent (the corpus is a gitignored artifact).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "results" / "research" / "trace_corpus" / "xauusd" / "trace_corpus.jsonl"

pytestmark = [pytest.mark.research_integrity, pytest.mark.slow]
skip_no_corpus = pytest.mark.skipif(not _CORPUS.exists(), reason="trace corpus artifact not built")


def _load_geo():
    spec = importlib.util.spec_from_file_location(
        "trace_geometry", _ROOT / "scripts" / "research" / "trace_geometry.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@skip_no_corpus
def test_geometry_clusters_and_descriptive_only():
    geo = _load_geo()
    df = geo._load()
    rep = geo.build(df, geo.MORPHOLOGY_FEATURES, "morphology")

    assert rep["k_selected"] in geo.K_SWEEP
    assert {s["k"] for s in rep["k_sweep"]} <= set(geo.K_SWEEP)
    # every kept trace belongs to exactly one cluster
    assert sum(c["size"] for c in rep["clusters"].values()) == rep["n_kept"]
    # descriptive fields present; morphology excludes absolute price-level features
    a_cluster = next(iter(rep["clusters"].values()))
    for k in ("size", "family_composition", "outcome_distribution", "feature_signature",
              "representative_trade_ids", "centroid_original_units"):
        assert k in a_cluster, k
    assert set(rep["level_features_excluded"]) and "close" in rep["level_features_excluded"]
    # DESCRIPTIVE: no edge/verdict/promote key anywhere in the library
    import json
    blob = json.dumps({k: v for k, v in rep.items() if not k.startswith("_")})
    assert not any(tok in blob for tok in ("\"verdict\"", "\"promote\"", "\"edge\"", "\"profit\""))
    assert "not edges" in rep["banner"].lower()


@skip_no_corpus
def test_geometry_labels_are_deterministic():
    geo = _load_geo()
    df = geo._load()
    a = geo.build(df, geo.MORPHOLOGY_FEATURES, "morphology")["_labels"]
    b = geo.build(df, geo.MORPHOLOGY_FEATURES, "morphology")["_labels"]
    assert np.array_equal(a, b)
