"""
test_vector_fixture_freshness.py
═══════════════════════════════════════════════════════════════════════════════
Guards the committed fixture (tests/fixtures/test_vectors.json) against silent
staleness when CANONICAL_FEATURE_ORDER changes.

If any test here fails, regenerate the fixture:
    python scripts/data/generate_vectors.py
═══════════════════════════════════════════════════════════════════════════════
"""

import json
from pathlib import Path

import pytest

from features.feature_schema import CANONICAL_FEATURE_DIM, CANONICAL_FEATURE_ORDER

_FIXTURE = Path(__file__).parent / "fixtures" / "test_vectors.json"


@pytest.fixture(scope="module")
def fixture_data():
    assert _FIXTURE.exists(), (
        f"Fixture missing: {_FIXTURE}\n"
        "Regenerate with: python scripts/data/generate_vectors.py"
    )
    return json.loads(_FIXTURE.read_text())


def test_fixture_exists():
    """Fixture file must be present in the repo."""
    assert _FIXTURE.exists(), (
        f"tests/fixtures/test_vectors.json not found.\n"
        "Run: python scripts/data/generate_vectors.py"
    )


def test_fixture_record_count(fixture_data):
    """Fixture must contain exactly 200 records (generator default n=200)."""
    assert len(fixture_data) == 200, (
        f"Expected 200 records, got {len(fixture_data)}.\n"
        "Regenerate: python scripts/data/generate_vectors.py"
    )


def test_fixture_schema_matches(fixture_data):
    """Every record's keys must exactly match CANONICAL_FEATURE_ORDER.

    Fails if CANONICAL_FEATURE_ORDER was extended, renamed, or trimmed
    without regenerating the fixture.
    """
    expected = set(CANONICAL_FEATURE_ORDER)
    for i, rec in enumerate(fixture_data):
        actual = set(rec.keys())
        missing = expected - actual
        extra   = actual - expected
        assert not missing and not extra, (
            f"Record {i} key mismatch — fixture is stale.\n"
            f"  Missing from fixture : {sorted(missing)}\n"
            f"  Extra in fixture     : {sorted(extra)}\n"
            "Regenerate: python scripts/data/generate_vectors.py"
        )


def test_fixture_dimensions(fixture_data):
    """Each record must have exactly CANONICAL_FEATURE_DIM (35) features."""
    for i, rec in enumerate(fixture_data):
        assert len(rec) == CANONICAL_FEATURE_DIM, (
            f"Record {i}: expected {CANONICAL_FEATURE_DIM} features, got {len(rec)}.\n"
            "Regenerate: python scripts/data/generate_vectors.py"
        )


def test_fixture_value_types(fixture_data):
    """All feature values must be floats within the generator's output range."""
    for i, rec in enumerate(fixture_data):
        for feat, val in rec.items():
            assert isinstance(val, float), (
                f"Record {i}[{feat}]: expected float, got {type(val).__name__}"
            )
            assert val == 0.0 or (-5.0 <= val <= 5.0), (
                f"Record {i}[{feat}]={val}: outside expected range [-5.0, 5.0] or 0.0"
            )


def test_fixture_feature_order_preserved(fixture_data):
    """The key insertion order in every record must match CANONICAL_FEATURE_ORDER.

    Ensures the fixture can be consumed as an ordered vector without re-sorting.
    """
    expected_order = list(CANONICAL_FEATURE_ORDER)
    for i, rec in enumerate(fixture_data):
        actual_order = list(rec.keys())
        assert actual_order == expected_order, (
            f"Record {i}: key order diverges from CANONICAL_FEATURE_ORDER at index "
            f"{next(j for j,(a,b) in enumerate(zip(actual_order,expected_order)) if a!=b)}.\n"
            "Regenerate: python scripts/data/generate_vectors.py"
        )
