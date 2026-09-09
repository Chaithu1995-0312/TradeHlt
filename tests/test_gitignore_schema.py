"""Pin the gitignore schema: occupancy ignored, identity names not.

No src/scripts change. Does not add or untrack MIXED_RESIDUE blobs.
Authority: docs/governance/GITIGNORE_SCHEMA.md (CH-gitignore-schema-v1).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_GITIGNORE = _ROOT / ".gitignore"
_SCHEMA = _ROOT / "docs" / "governance" / "GITIGNORE_SCHEMA.md"

_REQUIRED_HEADERS = (
    "LOCAL_CACHE",
    "LOCAL_SECRET",
    "LOCAL_BLOB",
    "LOCAL_TELEMETRY",
    "LOCAL_RUN",
    "LOCAL_MODEL",
    "LOCAL_IDENTITY",
    "MIXED_RESIDUE",
)

# Pathnames; files need not exist. --no-index applies the rule even if tracked.
_MUST_IGNORE = (
    "data/mt5/XAUUSD_M15.csv",
    "logs/crt_transitions.jsonl",
    "logs/trade_lifecycle.jsonl",
    "results/validation/dummy.json",
    "models/_schema_probe_untracked.json",
    ".env",
    "runtime/exec_telemetry/orders.jsonl",
    "objects/deadbeef",
    "records/L0/deadbeef.jsonl",
    "identity_store/bindings/bindings.jsonl",
    "reports/_schema_probe_untracked.md",
)

_MUST_NOT_IGNORE = (
    "docs/governance/GITIGNORE_SCHEMA.md",
    "docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json",
    "docs/governance/dataset_identity_registry.json",
    "docs/governance/identity_bindings/README.md",
    "docs/research-readiness/sujan_crt/mc_sujan_xauusd_m15_v1/metrics.json",
    "configs/production/ACTIVE_VERSION",
    "configs/research/measurement_result_log.jsonl",
    "src/identity/store.py",
    "data/README.md",
    "logs/README.md",
    "results/README.md",
    "models/README.md",
    "exec_telemetry/report.py",
)


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _ignored_no_index(path: str) -> bool:
    out = _git(["check-ignore", "--no-index", "-q", path])
    return out.returncode == 0


@pytest.fixture(scope="module")
def git_ok() -> None:
    out = _git(["rev-parse", "--is-inside-work-tree"])
    if out.returncode != 0:
        pytest.skip("git index unavailable")


def test_schema_and_gitignore_exist() -> None:
    assert _SCHEMA.is_file(), "docs/governance/GITIGNORE_SCHEMA.md missing"
    assert _GITIGNORE.is_file(), ".gitignore missing"
    text = _SCHEMA.read_text(encoding="utf-8")
    assert "RECOMPUTE != RECOVER" in text
    assert "TRACKED_BINDING" in text
    assert "LOCAL_BLOB" in text
    assert "forbidden this schema" in text


def test_gitignore_declares_schema_classes() -> None:
    text = _GITIGNORE.read_text(encoding="utf-8")
    missing = [h for h in _REQUIRED_HEADERS if h not in text]
    assert not missing, f".gitignore missing schema class headers: {missing}"
    assert "GITIGNORE_SCHEMA.md" in text


def test_local_occupancy_is_ignored(git_ok: None) -> None:
    leaked = [p for p in _MUST_IGNORE if not _ignored_no_index(p)]
    assert not leaked, f"schema LOCAL paths not ignored: {leaked}"


def test_tracked_bindings_are_not_ignored(git_ok: None) -> None:
    blocked = [p for p in _MUST_NOT_IGNORE if _ignored_no_index(p)]
    assert not blocked, f"TRACKED_BINDING/CODE paths ignored: {blocked}"


def test_mixed_residue_models_rule_does_not_imply_untrack(git_ok: None) -> None:
    """32 models/ files remain tracked. Schema forbids silent git rm --cached."""
    listed = _git(["ls-files", "--", "models/"])
    tracked = [ln for ln in listed.stdout.splitlines() if ln.strip()]
    readmes = [p for p in tracked if p.replace("\\", "/").endswith("README.md")]
    occupancy = [p for p in tracked if p not in readmes and not p.endswith(".gitkeep")]
    assert occupancy, "expected MIXED_RESIDUE tracked model files; did someone untrack them?"
    assert _ignored_no_index("models/_schema_probe_untracked.json")


def test_data_logs_results_have_zero_occupancy_in_index(git_ok: None) -> None:
    for tree in ("data/", "logs/", "results/"):
        listed = _git(["ls-files", "--", tree])
        tracked = [ln.replace("\\", "/") for ln in listed.stdout.splitlines() if ln.strip()]
        occupancy = [
            p
            for p in tracked
            if not p.endswith("README.md") and not p.endswith(".gitkeep")
        ]
        assert occupancy == [], f"{tree} has git-tracked occupancy (forbidden): {occupancy[:8]}"
