"""
L3 semantic goldens for the reachability layer — DRIFT DETECTION ONLY.

Authority (docs/research-readiness/README.md Test-Authority Ladder):
    L1 behavioral invariants   (test_config_reachability.test_no_dead_config_keys)  CAN FAIL BUILDS
    L2 generated evidence      (reports/reachability_validation.json)               OBSERVATIONAL
    L3 semantic goldens        (THIS FILE)                                          DRIFT DETECTION
These goldens may DETECT a truth change; they never DEFINE truth. Truth comes from code +
generators + behavioral invariants. When one fails on an INTENTIONAL change, run
    python scripts/analysis/update_reachability_golden.py
and commit the regenerated artifacts — the drift becomes an explicit accepted change, not silent.

Semantic-subset only: we compare verdict_counts / dead_keys / tooling_only_keys / model coverage /
runtime flags — never generated_at, evidence paths, key ordering, or full markdown (those drift for
non-semantic reasons and would raise false alarms).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_CONFIG_REPORT = _REPO / "docs" / "research-readiness" / "config-reachability-report.json"
_REGISTRY_GOLDEN = _REPO / "tests" / "golden" / "registry_summary.json"
_ANALYSIS = _REPO / "scripts" / "analysis"


def _load(mod_path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_config_summary_matches_committed_report():
    """A fresh analyzer run's semantic subset must equal the committed report's — drift means the
    config→code wiring changed since the report was last accepted. Regenerate via the accept script."""
    cr = _load(_ANALYSIS / "config_reachability.py", "config_reachability")
    if not _CONFIG_REPORT.exists():
        pytest.skip("committed config-reachability-report.json absent")
    fresh = cr.build_summary(cr.build_report())
    committed = cr.build_summary(json.loads(_CONFIG_REPORT.read_text(encoding="utf-8")))
    assert fresh == committed, (
        "config reachability drifted from the committed golden report.\n"
        "If intentional: python scripts/analysis/update_reachability_golden.py && commit.\n"
        f"fresh={fresh}\ncommitted={committed}"
    )


def test_registry_summary_matches_golden():
    """active_models.yaml + ACTIVE_VERSION config coverage/flags must equal the committed fixture.

    EXCEPTION NOTE (deliberately confined): active_models.yaml has NO native generator+`--check`
    workflow (unlike findings/config, which regenerate from source), so ONE stored semantic fixture
    is introduced here. Do NOT generalize tests/golden/ into a snapshot framework — that recreates
    the framework-sprawl the reachability doctrine avoids. This is a drift alarm, not a truth source.
    """
    upd = _load(_ANALYSIS / "update_reachability_golden.py", "update_reachability_golden")
    if not _REGISTRY_GOLDEN.exists():
        pytest.skip("registry golden fixture absent — run update_reachability_golden.py")
    derived = upd.build_registry_summary()
    committed = json.loads(_REGISTRY_GOLDEN.read_text(encoding="utf-8"))
    assert derived == committed, (
        "registry summary drifted from the committed golden.\n"
        "If intentional: python scripts/analysis/update_reachability_golden.py && commit.\n"
        f"derived={derived}\ncommitted={committed}"
    )
