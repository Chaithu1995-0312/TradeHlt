from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from retrieval.config import build_default_config
from retrieval.corpus import CorpusDiscoverer


def test_discover_twice_same_order_and_hashes():
    cfg = build_default_config()
    a = CorpusDiscoverer(cfg).discover()
    b = CorpusDiscoverer(cfg).discover()
    assert [d.metadata["filepath"] for d in a] == [d.metadata["filepath"] for d in b]
    assert [d.content_sha for d in a] == [d.content_sha for d in b]
