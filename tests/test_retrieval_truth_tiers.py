"""Every configured corpus path classifies to exactly one truth_class."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from retrieval.config import build_default_config
from retrieval.corpus import CorpusDiscoverer
from retrieval.truth_tier import TRUTH_CLASSES, classify_path, UNCLASSIFIED


def test_classify_path_known_examples():
    assert classify_path("src/runtime/backtest_v2.py").truth_class == "CURRENT"
    assert classify_path("configs/formulas/market_ontology.yaml").truth_class == "INTENDED"
    assert classify_path("docs/current-findings.md").truth_class == "RECORDED"
    assert classify_path("docs/reference/cli-matrix.md").truth_class == "REFERENCE"
    assert classify_path("docs/implementation_plan/foo.md").truth_class == "HISTORICAL"
    assert classify_path("context/05_HANDOFF.md").truth_class == "DERIVED"
    assert classify_path("context/05_HANDOFF.md").indexable is False


def test_corpus_paths_all_classified():
    cfg = build_default_config()
    docs = CorpusDiscoverer(cfg).discover()
    assert docs, "corpus discover returned empty — check include/exclude"
    bad = []
    for doc in docs:
        assert doc.truth_class in TRUTH_CLASSES
        assert doc.truth_class != "DERIVED"
        # unclassified sentinel would have indexable False and rule unclassified
        a = classify_path(doc.metadata["filepath"])
        if a.rule == "unclassified":
            bad.append(doc.metadata["filepath"])
    assert not bad, f"unclassified paths: {bad[:20]}"
