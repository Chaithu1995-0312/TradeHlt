from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from retrieval.config import build_default_config
from retrieval.corpus import CorpusDiscoverer


def test_no_derived_in_discover():
    cfg = build_default_config()
    docs = CorpusDiscoverer(cfg).discover()
    for doc in docs:
        rel = doc.metadata["filepath"].replace("\\", "/")
        assert not rel.startswith("context/"), rel
        assert not rel.endswith(".generated.md"), rel
        assert doc.truth_class != "DERIVED"
