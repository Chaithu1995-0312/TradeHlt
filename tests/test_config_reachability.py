"""
Advisory guard for the config-reachability analyzer (research-readiness audit 2026-06-12).

Keeps the analyzer importable + runnable and asserts the active config carries NO `DEAD`
keys (every tunable can at least be consumed). Inert/hardcoded/shadow keys are reported but
NOT failed here — those are tracked as findings, not regressions. Run the full report with:
    python scripts/analysis/config_reachability.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "analysis" / "config_reachability.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("config_reachability", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report():
    if not _TOOL.exists():
        pytest.skip("config_reachability.py not present")
    return _load_tool().build_report()


def test_report_has_expected_shape(report):
    assert report["active_version"]
    assert report["summary"]
    assert report["keys"]
    for k in report["keys"]:
        assert k["verdict"] in {
            "READ_AND_USED", "READ_BUT_INERT", "SHADOW_ONLY",
            "DOC_ONLY", "DEAD", "HARDCODED_OVERRIDE", "METADATA",
        }


def test_no_dead_config_keys(report):
    """Every key in the active config must be consumable (no DEAD). Inert/shadow/
    hardcoded are findings, tracked in docs/research-readiness, not failures here."""
    dead = [f"{k['section']}.{k['key']}" for k in report["keys"]
            if k["verdict"] == "DEAD"]
    assert not dead, f"DEAD config keys (present but cannot be consumed): {dead}"
