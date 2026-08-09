"""Kernel <-> research import-direction boundary (Research Runtime Step 0), PLUS
the narrower research -> promotion/validation authority boundary.

Contract 1: research may import the kernel; the kernel must never import research.
Contract 2 (added 2026-07-29, see src/research/__init__.py): research may freely
import kernel ENGINES to observe/score with them (research.model_runners.adapters
deliberately does this — measuring what production actually runs beats measuring
a reimplementation that could silently diverge, the F-037 failure mode) but must
NEVER import the promotion/validation AUTHORITY (governance.promotion_manager /
config_layer.config_validator).

See scripts/governance/scan_runtime_boundary.py for the rationale on both.

These tests are behavioral, not textual: each guard is exercised against synthetic
source so the detector is shown to FAIL on a real violation. A gate that cannot be
demonstrated to fail is not enforcement (E-001).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts" / "governance"))

from scan_runtime_boundary import (  # noqa: E402
    FORBIDDEN_AUTHORITY_MODULES,
    RESEARCH_PACKAGES,
    authority_imports_in_source,
    research_imports_in_source,
    scan,
    scan_authority,
    side_of_file,
)


# ── the invariant ────────────────────────────────────────────────────────────
def test_kernel_does_not_import_research():
    violations = scan()
    assert violations == [], (
        "kernel module(s) import research - this lets a research change alter "
        "production behavior:\n"
        + "\n".join(f"  {v['file']}:{v['line']} -> {v['imports']}" for v in violations)
    )


# ── classification ───────────────────────────────────────────────────────────
def test_research_and_interpreters_are_research_side():
    assert side_of_file("src/research/runner.py") == "research"
    assert side_of_file("src/interpreters/adapter.py") == "research"


def test_kernel_packages_are_kernel_side():
    for rel in (
        "src/core/engine_runner.py",
        "src/engines/rr_engine.py",
        "src/config_layer/model_resolver.py",
        "src/features/feature_pipeline.py",
        "src/runtime/backtest_v2.py",
    ):
        assert side_of_file(rel) == "kernel", rel


def test_interpreters_classified_research_because_only_research_consumes_it():
    """Guard the classification decision itself, so a future kernel consumer is loud."""
    assert "interpreters" in RESEARCH_PACKAGES


# ── the detector must be able to fail ────────────────────────────────────────
def test_detects_module_level_import():
    src = "from research.contracts import Signal\n"
    assert research_imports_in_source(src, "src/core/x.py") == [(1, "research.contracts")]


def test_detects_plain_import():
    src = "import research\n"
    assert research_imports_in_source(src, "src/core/x.py") == [(1, "research")]


def test_detects_function_local_import():
    """Local-scope imports are the common evasion - they must still be caught."""
    src = "def f():\n    from interpreters.contract import Interpreter\n    return Interpreter\n"
    assert research_imports_in_source(src, "src/core/x.py") == [(2, "interpreters.contract")]


def test_ignores_prose_mentioning_research():
    """src/governance/promotion_manager.py:7 says 'from research -> production
    registry' in a docstring. AST detection must not trip on prose."""
    src = '"""Moves a validated config from research -> production registry."""\n'
    assert research_imports_in_source(src, "src/governance/promotion_manager.py") == []


def test_allows_kernel_imports():
    src = "from config_layer.crt_engine_v2 import Candle\nimport json\n"
    assert research_imports_in_source(src, "src/research/runner.py") == []


def test_research_importing_kernel_is_not_a_violation():
    """The allowed direction: research/ files are skipped by scan() entirely."""
    assert all(v["file"].split("/")[1] not in RESEARCH_PACKAGES for v in scan())


# ── contract 2: research -> promotion/validation authority ──────────────────
def test_research_does_not_import_promotion_or_validation_authority():
    violations = scan_authority()
    assert violations == [], (
        "research/interpreters module(s) import the promotion/validation "
        "authority - research must observe/score, never promote or "
        "validate-for-promotion:\n"
        + "\n".join(f"  {v['file']}:{v['line']} -> {v['imports']}" for v in violations)
    )


def test_forbidden_authority_modules_are_exactly_promotion_and_validation():
    """Guard the scope of contract 2 itself: engines (core.*) are NOT forbidden —
    only the promotion/validation authority is. A future accidental widening of
    this set would silently break research.model_runners.adapters' legitimate
    engine imports; a narrowing would silently reopen the authority hole."""
    assert FORBIDDEN_AUTHORITY_MODULES == {
        "governance.promotion_manager",
        "config_layer.config_validator",
    }


def test_authority_detector_catches_module_level_import():
    src = "from governance.promotion_manager import PromotionManager\n"
    assert authority_imports_in_source(src, "src/research/x.py") == [
        (1, "governance.promotion_manager")
    ]


def test_authority_detector_catches_plain_import():
    src = "import config_layer.config_validator\n"
    assert authority_imports_in_source(src, "src/research/x.py") == [
        (1, "config_layer.config_validator")
    ]


def test_authority_detector_catches_function_local_import():
    """Local-scope imports are the common evasion - they must still be caught."""
    src = (
        "def f():\n"
        "    from governance.promotion_manager import PromotionManager\n"
        "    return PromotionManager\n"
    )
    assert authority_imports_in_source(src, "src/research/x.py") == [
        (2, "governance.promotion_manager")
    ]


def test_authority_detector_catches_submodule_import():
    """A forbidden module's own submodules are forbidden too, not just the exact name."""
    src = "from config_layer.config_validator.internal import helper\n"
    assert authority_imports_in_source(src, "src/research/x.py") == [
        (1, "config_layer.config_validator.internal")
    ]


def test_authority_detector_allows_engine_imports():
    """The permitted coupling: research.model_runners.adapters calling live
    engines directly is NOT a violation of contract 2 (only contract 1, the
    kernel<-research direction, which does not apply here since these are
    research-side files)."""
    src = (
        "from core.decision_engine import DecisionEngine\n"
        "from core.engine_runner import detect_regime, breakout_engine, trap_engine\n"
        "from core.gate_intelligence import compute_crt_levels\n"
        "from core.fusion_engine import FusionEngine, FusionConfig, GaussianAdapter\n"
    )
    assert authority_imports_in_source(src, "src/research/model_runners/adapters/x.py") == []


def test_authority_detector_ignores_prose_mentioning_promotion_manager():
    src = '"""This module must never import governance.promotion_manager."""\n'
    assert authority_imports_in_source(src, "src/research/x.py") == []
