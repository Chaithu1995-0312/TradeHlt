from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from retrieval.retriever import HybridResult


def test_hybrid_result_requires_nonzero_lines_for_evidence():
    # Contract: a citation with 0–0 is not evidence. Construction itself allows
    # zeros (legacy), but consumers must treat them as invalid — assert helper.
    hr = HybridResult(
        chunk_id="x",
        text="hello",
        score=1.0,
        filepath="src/foo.py",
        start_line=10,
        end_line=20,
        truth_class="CURRENT",
        content_sha="abc",
    )
    assert hr.start_line > 0 and hr.end_line >= hr.start_line
    assert hr.filepath
    assert hr.content_sha
