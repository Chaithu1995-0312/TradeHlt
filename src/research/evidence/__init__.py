"""Queryable evidence layer over the XAUUSD parquet projections.

Not a training dataset. Highest-value output is a defensible measurement.
"""
from research.evidence.catalog import (
    LEGAL_JOINS,
    SURFACES,
    IllegalJoinError,
    assert_join,
)
from research.evidence.atlases import (
    asymmetry_atlas,
    leakage_atlas,
    state_value_surface,
)
from research.evidence.queries import answer_question, rows_to_cols
from research.evidence.records import EvidenceRecord

__all__ = [
    "SURFACES",
    "LEGAL_JOINS",
    "IllegalJoinError",
    "assert_join",
    "EvidenceRecord",
    "answer_question",
    "rows_to_cols",
    "leakage_atlas",
    "state_value_surface",
    "asymmetry_atlas",
]
