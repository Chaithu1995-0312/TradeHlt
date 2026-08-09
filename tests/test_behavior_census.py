"""
Test gate for the config-first behavior census (docs/research-readiness/config-first-doctrine.md).

Keeps the analyzer importable + runnable and pins the Batch-A migrated modules so behavior
cannot silently drift back into code:
  - dynamic_threshold.py must carry ZERO behavioral module/class constants (fully removed);
  - regime_governor / convergence_controller / acceptance_controller must stay config-wired
    (expose from_prod_config / read a config section).
Behavioral constants elsewhere are reported as "future config opportunities", not failed here.
Run the full report with:  python scripts/analysis/behavior_census.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "analysis" / "behavior_census.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("behavior_census", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    if not _TOOL.exists():
        pytest.skip("behavior_census.py not present")
    return _load_tool()


@pytest.fixture(scope="module")
def report(tool):
    return tool.build_report()


def test_report_has_expected_shape(report):
    assert report["generated_at"]
    assert set(report["summary"]) == {"STRUCTURAL", "BEHAVIORAL", "GOAL_SEEKING", "UNCLASSIFIED"}
    assert set(report["maturity_summary"]) == {"CONFIG_DRIVEN", "CONFIG_WIRED", "HARD_CODED"}
    assert isinstance(report["future_config_opportunities"], list)
    assert isinstance(report["modules"], dict)
    for b in report["modules"].values():
        assert b["maturity"] in {"CONFIG_DRIVEN", "CONFIG_WIRED", "HARD_CODED"}


def test_migrated_module_maturities(report):
    """The owner's maturity model: dynamic_threshold fully CONFIG_DRIVEN; controllers CONFIG_WIRED."""
    mods = report["modules"]
    dt = mods.get("core/dynamic_threshold.py")
    if dt is not None:
        assert dt["maturity"] == "CONFIG_DRIVEN"
    for rel in (
        "core/regime_governor.py",
        "core/convergence_controller.py",
        "core/acceptance_controller.py",
    ):
        b = mods.get(rel)
        if b is not None:
            assert b["maturity"] in {"CONFIG_WIRED", "CONFIG_DRIVEN"}


def test_external_injection_not_overreported(report):
    """WI-1: FusionConfig is built from the fusion_engine section by engine_runner, so
    fusion_engine.py must NOT be mislabeled HARD_CODED (external-injection blind spot fixed)."""
    fe = report["modules"].get("core/fusion_engine.py")
    if fe is not None:
        assert fe["maturity"] != "HARD_CODED", (
            f"fusion_engine.py over-reported as HARD_CODED; externally_wired="
            f"{fe.get('externally_wired')} hardcoded={fe.get('hardcoded')}"
        )
        assert fe["externally_wired"], "fusion_engine FusionConfig fields should be externally-wired"


def test_crt_engine_no_genuine_hardcoded(report):
    """Batch C: CRTConfig fields are externally-wired (config-built) and the 3 runtime-state
    placeholders (decay_factor/risk_pct/soft_conf_candles) are STRUCTURAL — so crt_engine_v2.py
    carries ZERO genuine HARD_CODED debt."""
    ce = report["modules"].get("config_layer/crt_engine_v2.py")
    if ce is not None:
        assert not ce["hardcoded"], f"crt_engine_v2 genuine HARD_CODED should be empty: {ce['hardcoded']}"


def test_dynamic_threshold_has_no_behavioral_constants(report):
    """A1: the percentile + clamp bounds were removed from dynamic_threshold.py (now config)."""
    b = report["modules"].get("core/dynamic_threshold.py", {})
    assert not b.get("behavioral"), (
        f"dynamic_threshold.py must carry zero behavioral constants, found: {b.get('behavioral')}"
    )


def test_migrated_controllers_are_config_wired(report):
    """A2-A4: governor / convergence / acceptance route behavior through config (from_prod_config)."""
    for rel in (
        "core/regime_governor.py",
        "core/convergence_controller.py",
        "core/acceptance_controller.py",
    ):
        b = report["modules"].get(rel)
        if b is None:
            continue  # no module-level constants at all is acceptable
        assert b["config_wired"], f"{rel} must remain config-wired (from_prod_config present)"


def test_check_migrated_is_clean(tool, report):
    """The --check gate must pass for the Batch-A migrated modules."""
    assert tool.check_migrated(report) == []
