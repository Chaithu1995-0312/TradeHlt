"""Governance-invariant gate: run the curated green floor when governed paths change.

This is the CONTINUOUS analogue of the E-001 behavioral invariant (Program E-001,
docs/governance/EPISTEMIC_INTEGRITY.md). The behavioral red->green proof in
tests/governance/test_epistemic_invariants.py is real but only runs when someone runs
pytest by hand; this gate makes it run on every governed commit (pre-commit hook) and on
every push/PR (CI) — turning the lesson into infrastructure.

Two entry modes, ONE code path (so the hook and CI cannot drift):
  - default (pre-commit): read the staged diff; run GREEN_FLOOR only if a GOVERNED path
    changed (else exit 0 — a docs/README edit must not trigger a multi-second pytest run,
    or fast-hook discipline erodes into --no-verify habit).
  - ``--all`` (CI): skip the path gate and run GREEN_FLOOR unconditionally.

DESIGN CONSTRAINT (an E-001 lesson applied to itself — do NOT broaden GREEN_FLOOR to the
whole suite): the full suite carries ~66 known reds (config split-brain / branch-TP3 / LLM-env,
F-018). A gate that is permanently red enforces nothing — it is itself decorative wiring
(E-001F). GREEN_FLOOR is the curated currently-green set; it grows MONOTONICALLY as F-018
reds are resolved, and is never replaced by ``pytest`` whole.

Path lists are policy and deserve names — GOVERNED_PREFIXES / GOVERNED_FILES / GREEN_FLOOR
are module constants pinned by tests/test_governance_invariant_check.py so policy can't drift.

Native ``git commit --no-verify`` remains the human escape hatch; no custom token needed.
The pure helper (``requires_run``) is git-free so it unit-tests deterministically.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ── policy (named constants — pinned by tests/test_governance_invariant_check.py) ──

# A staged change under one of these prefixes pulls in the governance gate.
GOVERNED_PREFIXES: tuple[str, ...] = (
    "src/research/",
    "docs/governance/",
    "tests/governance/",
    # Gate-6 Construction Contract (2026-07-08): feature-math / ontology surfaces are governed —
    # changes here must run the extended floor (REPOSITORY_CONSTRUCTION_PROTOCOL.md).
    "src/features/",
    "configs/formulas/",
    "scripts/analysis/",
    # SITS PR-3: new ephemera homes pull GREEN_FLOOR (inventory coverage + ratchet)
    "scripts/probes/",
    "scripts/tmp/",
)

# Exact files (not under a governed prefix) that also pull in the gate.
GOVERNED_FILES: tuple[str, ...] = (
    "docs/current-findings.md",
    "docs/operations/KNOWN_ILLUSIONS.md",
    "active_models.yaml",  # Gate-6: model-registry truth is a governed surface
    "src/config_layer/model_paths.py",  # ModelPaths layout authority
    "src/config_layer/model_resolver.py",
    "docs/governance/model_paths_literal_debt.json",  # models/ literal freeze ratchet
    # SITS (Script & Implementation Traceability) — inventory authority only:
    "src/governance/script_registry.py",
    "scripts/governance/seed_script_registry.py",
    "scripts/governance/query_scripts.py",
    "tests/test_script_registry.py",
    "tests/test_script_matrix_sync.py",
    "docs/reference/script-matrix.md",
)

# The curated, currently-green pytest target list — the SINGLE source of truth shared by
# the pre-commit hook and CI. Grows monotonically; never replaced by the whole suite.
GREEN_FLOOR: tuple[str, ...] = (
    "tests/governance/",
    "tests/test_governance_invariant_check.py",  # the gate guards its own policy
    "tests/test_regime_conditioning.py",
    "tests/test_current_findings.py",
    "tests/test_doc_citations.py",
    "tests/test_session_log.py",
    "tests/replay/test_timing_reconstructor.py",
    # Gate-6 Construction Contract additions (all verified green 2026-07-08; monotonic growth):
    "tests/test_formula_registry.py",
    "tests/test_candle_math.py",
    "tests/test_derived_math.py",
    "tests/test_feature_math_lint.py",
    "tests/test_feature_lineage.py",
    "tests/test_geometry_census.py",      # incl. the census FRESHNESS keystone (B1)
    "tests/test_gate2b_closure.py",
    "tests/test_active_models_registry.py",
    "tests/test_construction_protocol.py",
    # ModelPaths Phase 0+: ban new unauthorized models/ path literals (debt ratchet)
    "tests/test_model_paths_literals.py",
    # SITS PR-2: coverage + matrix sync (atomic with enabling 100% path registration)
    "tests/test_script_registry.py",
    "tests/test_script_matrix_sync.py",
)


def _norm(path: str) -> str:
    return path.replace("\\", "/").strip().strip('"')


def requires_run(changed_paths: list[str]) -> bool:
    """True if any staged path is governed (under a prefix, or an exact governed file)."""
    for raw in changed_paths:
        p = _norm(raw)
        if p.startswith(GOVERNED_PREFIXES) or p in GOVERNED_FILES:
            return True
    return False


# ── git + pytest wiring (impure) ──────────────────────────────────────────────


def _staged_paths() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    ).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def _run_green_floor() -> int:
    """Run the curated floor; return pytest's exit code."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *GREEN_FLOOR],
        check=False,
    ).returncode


def main(argv: list[str]) -> int:
    run_all = "--all" in argv[1:]

    if not run_all and not requires_run(_staged_paths()):
        return 0  # no governed paths staged — gate not applicable

    rc = _run_green_floor()
    if rc != 0:
        sys.stderr.write(
            "\nGovernance-invariant gate FAILED (Program E-001).\n"
            "  The curated green floor must stay green for governed changes.\n"
            "  Fix the failing test, or bypass a trivial change with: git commit --no-verify\n"
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
