"""
CRT closure report pin — Phase 8.

Ensures the durable closure verdict file exists and cannot silently claim CLOSED
while F-050 remains the documented blocking collision.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_REPORT = _ROOT / "docs" / "governance" / "crt_closure_report.md"


def test_closure_report_exists():
    assert _REPORT.is_file(), f"missing {_REPORT}"


def test_closure_status_is_closed_after_ch002():
    """Post CH-002 F-050 emission rename: CRT boundary identity is CLOSED."""
    text = _REPORT.read_text(encoding="utf-8")
    assert "CRT_CLOSURE_STATUS = CLOSED" in text
    assert "F-050" in text
    # Residual history may mention BLOCKED; active verdict must be CLOSED
    assert "CH-002" in text or "REMEDIATED" in text or "emission rename" in text.lower()


def test_closure_report_lists_phase_artifacts():
    text = _REPORT.read_text(encoding="utf-8")
    for name in (
        "crt_executable_surface",
        "crt_formula_contract",
        "crt_executable_state_graph",
        "crt_diversion_registry",
        "crt_config_reachability",
        "crt_13_candidate_provenance",
        "crt_adversarial_validation",
    ):
        assert name in text, f"report missing reference to {name}"
