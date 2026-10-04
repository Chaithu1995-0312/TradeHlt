"""Floor for SemanticIndex.answer — closed question slugs, fail-closed aliases."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from governance.semantic_query import (  # noqa: E402
    AMBIGUOUS,
    QUESTION_REGISTRY,
    UNANSWERABLE,
    SemanticIndex,
)


@pytest.fixture(scope="module")
def idx() -> SemanticIndex:
    return SemanticIndex.load()


def test_question_registry_is_closed():
    assert set(QUESTION_REGISTRY) == {
        "guarantees",
        "owner",
        "writers",
        "disproved",
        "authoritative",
    }


def test_unknown_question_raises(idx: SemanticIndex):
    with pytest.raises(KeyError, match="unknown question"):
        idx.answer("vibes", "CN-001")


def test_authoritative_on_live_concept(idx: SemanticIndex):
    answer = idx.answer("authoritative", "CN-001")
    assert answer.verdict != UNANSWERABLE
    assert answer.rows


def test_missing_target_is_unanswerable_or_ambiguous(idx: SemanticIndex):
    answer = idx.answer("authoritative", "CN-404")
    assert answer.verdict in {UNANSWERABLE, AMBIGUOUS}
