"""Read-only model enumeration (Research Runtime Step 1).

`resolve_model` answers "which version does production run?"; these APIs answer
"which versions exist?" so research can benchmark the selected model against its
alternatives.

The load-bearing invariant is SELECTION PARITY: the `selected` label must equal what
`resolve_model` would actually load. If those diverge, every benchmark that says
"the selected model ranks Nth" is lying about which model is selected.

Nothing here grants authority to run a non-selected model in the spine (CLAUDE.md §6.5).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from config_layer.model_resolver import (  # noqa: E402
    ModelResolveError,
    RegistryEntry,
    enumerate_all,
    enumerate_versions,
    list_model_families,
    resolve_model,
    resolve_version,
)


# ── discovery surface ────────────────────────────────────────────────────────
def test_families_are_the_known_set():
    assert list_model_families() == [
        "bitnet",
        "gaussian",
        "rr",
        "rr_fusion",
        "tradenet",
        "zone_gate",
    ]


def test_enumerate_finds_more_versions_than_are_selected():
    """The whole point: the alternatives must be visible, not just the active one."""
    all_rows = enumerate_all()
    total = sum(len(rows) for rows in all_rows.values())
    selected = sum(1 for rows in all_rows.values() for r in rows if r.selected)
    assert total > selected, "enumeration exposes no alternatives to benchmark against"
    assert total >= 20, f"expected a substantial registry surface, got {total}"


def test_enumeration_is_deterministic():
    a = [r.version for r in enumerate_versions("rr")]
    b = [r.version for r in enumerate_versions("rr")]
    assert a == b == sorted(a)


def test_rows_are_registry_entries():
    for row in enumerate_versions("zone_gate"):
        assert isinstance(row, RegistryEntry)
        assert row.family == "zone_gate"
        assert row.version


# ── the load-bearing invariant ───────────────────────────────────────────────
@pytest.mark.parametrize("family", list_model_families())
def test_selected_label_agrees_with_resolve_model(family):
    """`selected` must mirror the trading path's own resolution, never a re-derivation."""
    resolved = resolve_model(family, require_identity_parity=False)
    labelled = [r.version for r in enumerate_versions(family) if r.selected]
    if resolved.version is None:
        assert labelled == [], f"{family}: no active version, but {labelled} labelled selected"
    else:
        assert labelled == [resolved.version], (
            f"{family}: selected label {labelled} != resolve_model {resolved.version!r}"
        )


def test_at_most_one_selected_per_family():
    for family, rows in enumerate_all().items():
        assert sum(1 for r in rows if r.selected) <= 1, family


# ── meta keys must not masquerade as versions ────────────────────────────────
def test_registry_meta_keys_are_not_enumerated_as_models():
    versions = {r.version for rows in enumerate_all().values() for r in rows}
    for junk in ("__active__", "_schema_v4_note", "canonical_schema_version_at_stamp"):
        assert junk not in versions


# ── failures are recorded, not raised ────────────────────────────────────────
def test_missing_artifacts_are_reported_not_raised():
    """An unloadable checkpoint is an implementation-validation RESULT."""
    rows = [r for rows in enumerate_all().values() for r in rows]
    assert rows, "no registry rows at all"
    for r in rows:
        assert isinstance(r.artifact_exists, bool)
    # The corpus is known to contain registry entries whose file is gone; that must
    # enumerate cleanly rather than blow up.
    assert any(not r.artifact_exists for r in rows), (
        "expected at least one dangling registry entry to prove non-fatal handling"
    )


def test_unknown_family_raises():
    with pytest.raises(ModelResolveError):
        enumerate_versions("no_such_family")


def test_unknown_version_raises_and_lists_known():
    with pytest.raises(ModelResolveError) as exc:
        resolve_version("rr", "definitely_not_a_version")
    assert "not found" in str(exc.value)


# ── explicit-version resolution ──────────────────────────────────────────────
def test_can_resolve_a_non_selected_version():
    rows = enumerate_versions("rr")
    non_selected = [r for r in rows if not r.selected]
    assert non_selected, "need a non-selected version to prove the capability"
    target = non_selected[0]
    got = resolve_version("rr", target.version)
    assert got.version == target.version
    assert got.family == "rr"


def test_resolved_version_is_marked_non_authoritative():
    rows = enumerate_versions("zone_gate")
    got = resolve_version("zone_gate", rows[0].version)
    assert got.meta["authority"] == "NONE"
    assert got.meta["explicit_version"] is True


def test_identity_parity_is_observed_not_enforced():
    """A non-selected version does not match identity - that is data, not an error."""
    rows = enumerate_versions("rr")
    non_selected = [r for r in rows if not r.selected]
    got = resolve_version("rr", non_selected[0].version)
    assert got.identity_parity is False   # observed, and it did not raise


def test_declared_feature_dim_surfaces_schema_drift():
    """Legacy 35-dim artifacts vs the 38-dim canonical schema must be visible."""
    dims = {
        r.declared_feature_dim
        for rows in enumerate_all().values()
        for r in rows
        if r.declared_feature_dim is not None
    }
    assert len(dims) > 1, f"expected mixed declared dims across legacy artifacts, got {dims}"


# ── read-only ────────────────────────────────────────────────────────────────
def test_enumeration_never_mutates_registries():
    reg_dir = _REPO / "models"
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(reg_dir.glob("*registry*.json"))
    }
    enumerate_all()
    for rows in enumerate_all().values():
        for r in rows:
            resolve_version(r.family, r.version)
    after = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(reg_dir.glob("*registry*.json"))
    }
    assert before == after, "enumeration mutated a registry - it must be read-only"
