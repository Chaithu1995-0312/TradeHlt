"""Unit tests for the governance-invariant gate (scripts/maintenance/check_governance_invariants.py).

Exercises the git-free decision core (requires_run) and pins the named policy constants
(GOVERNED_PREFIXES / GOVERNED_FILES / GREEN_FLOOR) so the gate's policy cannot silently
drift. No git, no real pytest run — pure functions + constant checks only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SRC = Path("scripts/maintenance/check_governance_invariants.py")
_spec = importlib.util.spec_from_file_location("check_governance_invariants", _SRC)
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


def test_requires_run_on_governed_prefixes() -> None:
    assert chk.requires_run(["src/research/regime_conditioning.py"])
    assert chk.requires_run(["docs/governance/EPISTEMIC_INTEGRITY.md"])
    assert chk.requires_run(["tests/governance/test_epistemic_invariants.py"])
    # backslash paths (Windows `git diff` can emit either) are normalized
    assert chk.requires_run(["src\\research\\exit_grid.py"])


def test_requires_run_on_governed_files() -> None:
    assert chk.requires_run(["docs/current-findings.md"])
    assert chk.requires_run(["docs/operations/KNOWN_ILLUSIONS.md"])
    # mixed: one governed file among exempt ones still triggers
    assert chk.requires_run(["README.md", "docs/current-findings.md"])


def test_requires_run_skips_exempt_paths() -> None:
    assert not chk.requires_run([])
    assert not chk.requires_run(["README.md", "docs/reference/architecture.md"])
    # src/ but NOT src/research|features/ — the engine spine stays out of this gate's scope
    assert not chk.requires_run(["src/core/engine_runner.py"])
    # Gate-6: feature-math surfaces ARE in scope now
    assert chk.requires_run(["src/features/candle_math.py"])
    assert chk.requires_run(["configs/formulas/market_ontology.yaml"])
    assert chk.requires_run(["active_models.yaml"])
    # a docs/ file that is not a governed file
    assert not chk.requires_run(["docs/topics/foo.md"])


def test_policy_constants_are_named_and_typed() -> None:
    assert isinstance(chk.GOVERNED_PREFIXES, tuple) and chk.GOVERNED_PREFIXES
    assert isinstance(chk.GOVERNED_FILES, tuple) and chk.GOVERNED_FILES
    assert "src/research/" in chk.GOVERNED_PREFIXES
    assert "tests/governance/" in chk.GOVERNED_PREFIXES
    assert "docs/current-findings.md" in chk.GOVERNED_FILES
    # Gate-6 Construction Contract surfaces (2026-07-08)
    assert "src/features/" in chk.GOVERNED_PREFIXES
    assert "configs/formulas/" in chk.GOVERNED_PREFIXES
    assert "active_models.yaml" in chk.GOVERNED_FILES
    # SITS PR-2 inventory surfaces
    assert "src/governance/script_registry.py" in chk.GOVERNED_FILES
    assert "tests/test_script_registry.py" in chk.GREEN_FLOOR
    assert "tests/test_script_matrix_sync.py" in chk.GREEN_FLOOR
    # SITS PR-3 ephemera prefixes
    assert "scripts/probes/" in chk.GOVERNED_PREFIXES
    assert "scripts/tmp/" in chk.GOVERNED_PREFIXES
    # JSONL Claim Surface PR-1 (CT-008 extension): catalog loader is governed; the PRIMARY YAML
    # rides the existing docs/governance/ prefix. src/governance/ stays OFF the prefix list.
    assert "src/governance/jsonl_claim_catalog.py" in chk.GOVERNED_FILES
    assert "src/governance/" not in chk.GOVERNED_PREFIXES
    assert "tests/test_jsonl_claim_catalog.py" in chk.GREEN_FLOOR
    assert "tests/test_findings_export.py" in chk.GREEN_FLOOR
    assert "tests/test_hypothesis_registry.py" in chk.GREEN_FLOOR
    # PR-2: grounder + its floor
    assert "src/governance/semantic_grounding.py" in chk.GOVERNED_FILES
    assert "tests/test_jsonl_claim_grounding.py" in chk.GREEN_FLOOR
    # PR-3: result-log module + the instances/ prefix. The LOG FILE itself must NOT be a
    # governed file — every append would otherwise re-run the whole floor.
    assert "src/governance/measurement_result_log.py" in chk.GOVERNED_FILES
    assert "configs/research/measurement_contracts/instances/" in chk.GOVERNED_PREFIXES
    assert "configs/research/measurement_result_log.jsonl" not in chk.GOVERNED_FILES
    assert "tests/test_measurement_result_log.py" in chk.GREEN_FLOOR
    assert chk.requires_run(["scripts/probes/foo.py"])
    assert chk.requires_run(["scripts/tmp/scratch.py"])


def test_green_floor_targets_exist() -> None:
    """GREEN_FLOOR is the curated currently-green set — every target must resolve to a
    real test path so the gate never silently runs an empty/typo'd selection."""
    assert isinstance(chk.GREEN_FLOOR, tuple) and chk.GREEN_FLOOR
    for target in chk.GREEN_FLOOR:
        assert Path(target).exists(), f"GREEN_FLOOR target missing: {target}"
