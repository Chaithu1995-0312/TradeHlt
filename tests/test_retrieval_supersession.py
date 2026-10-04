from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from retrieval.divergence import detect_divergences
from retrieval.truth_tier import classify_status, is_non_live


class _Hit:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_superseded_never_unmarked():
    status = classify_status("**Status:** SUPERSEDED by F-016\n")
    assert is_non_live(status.status)
    hit = _Hit(
        chunk_id="c1",
        truth_class="RECORDED",
        lifecycle_status=status.status,
        status_evidence=status.status_evidence,
        ids="F-001",
        symbols="",
        text="**Status:** SUPERSEDED by F-016\n",
    )
    flags = detect_divergences([hit], repo_root=None)
    kinds = {f.kind for f in flags}
    assert "superseded_hit" in kinds
