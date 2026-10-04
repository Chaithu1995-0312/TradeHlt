"""Floor for the ERP Information-Class Boundary registry (md <-> json twin).

Asserts only STABLE invariants (deliberately loose so the actively-maintained registry can evolve):
the twin exists and agrees, the measured boundary + E-001 correction are recorded, and every open
information class has an id + status and is referenced in the human twin. Governance-doc floor —
no market data, fast.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_JSON = _ROOT / "docs" / "research-readiness" / "erp-information-class-boundary.json"
_MD = _ROOT / "docs" / "research-readiness" / "erp-information-class-boundary.md"

pytestmark = pytest.mark.research_integrity


def test_registry_twin_exists():
    assert _JSON.exists() and _MD.exists()


def test_measured_boundary_and_correction_recorded():
    d = json.loads(_JSON.read_text(encoding="utf-8"))
    mb = d["measured_boundary"]
    assert mb.get("statement"), "measured boundary statement missing"
    # E-001 correction must be recorded with the mandatory phrase
    corr = d["correction_note"]
    assert "Caught me overclaiming" in corr["phrase"]
    assert corr.get("corrected_to")
    md = _MD.read_text(encoding="utf-8")
    assert "Caught me overclaiming" in md
    # the boundary must stay scoped (no unqualified "at any resolution" universal claim)
    assert "OHLCV" in mb["statement"]


def test_open_information_classes_wellformed_and_in_md():
    d = json.loads(_JSON.read_text(encoding="utf-8"))
    classes = d["open_information_classes"]
    assert isinstance(classes, list) and classes
    md = _MD.read_text(encoding="utf-8")
    for c in classes:
        assert c.get("id"), c
        assert c.get("status"), c
        assert "caveat" in c  # "not measured != likely to work" discipline
        assert c["id"] in md, f"{c['id']} not referenced in the human twin"
    # the six information-class questions the boundary opened must all be present
    ids = {c["id"] for c in classes}
    assert {"RC-005", "RC-006", "RC-007", "RC-008", "RC-009", "RC-010"} <= ids
