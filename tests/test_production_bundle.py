"""ProductionBundle — Selected != Enabled (Research Runtime Step 1b).

`resolve_model` says which version production would LOAD. The bundle says which
checkpoint actually reaches a DECISION. On the active patch those differ for most
families, so a benchmark that compares against "the selected model" would be comparing
against something production does not execute.

The bundle reconciles three existing authorities (registry / identity / production
config) and introduces none. Conflicts are reported, never silently resolved (§6.2 r3).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from config_layer.production_bundle import (  # noqa: E402
    STATUS_ABSENT,
    STATUS_ENABLED_WITHOUT_CHECKPOINT,
    STATUS_SELECTED_AND_ENABLED,
    STATUS_SELECTED_NOT_ENABLED,
    BundleMember,
    ProductionBundle,
    derive_execution_status,
    load_production_bundle,
)
from config_layer.model_resolver import list_model_families, resolve_model  # noqa: E402


@pytest.fixture(scope="module")
def bundle() -> ProductionBundle:
    return load_production_bundle()


# ── status algebra ───────────────────────────────────────────────────────────
def test_status_algebra_covers_all_four_quadrants():
    assert derive_execution_status(selected=True, enabled=True) == STATUS_SELECTED_AND_ENABLED
    assert derive_execution_status(selected=True, enabled=False) == STATUS_SELECTED_NOT_ENABLED
    assert derive_execution_status(selected=False, enabled=True) == STATUS_ENABLED_WITHOUT_CHECKPOINT
    assert derive_execution_status(selected=False, enabled=False) == STATUS_ABSENT


# ── shape ────────────────────────────────────────────────────────────────────
def test_bundle_covers_every_family(bundle):
    assert sorted(bundle.members) == list_model_families()
    for m in bundle.members.values():
        assert isinstance(m, BundleMember)


def test_bundle_reports_the_active_version(bundle):
    assert bundle.active_version
    expected = (_REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    assert bundle.active_version == expected


# ── the invariant this object exists for ─────────────────────────────────────
def test_selected_is_not_the_same_question_as_executing(bundle):
    """The whole reason the bundle exists: on the active patch these differ."""
    selected = {f for f, m in bundle.members.items() if m.selected_version}
    executing = set(bundle.executing_families())
    assert executing < selected, (
        "expected strictly fewer executing checkpoints than selected versions; "
        f"selected={sorted(selected)} executing={sorted(executing)}"
    )


def test_selected_version_mirrors_resolve_model(bundle):
    """The bundle must not re-derive selection - it mirrors the trading path."""
    for family, member in bundle.members.items():
        resolved = resolve_model(family, require_identity_parity=False)
        assert member.selected_version == resolved.version, family


def test_disabled_families_do_not_execute(bundle):
    """rr_fusion is enabled:false on the active config (F-038); tradenet is unwired (F-005)."""
    for family in ("rr_fusion", "tradenet"):
        member = bundle.members[family]
        assert not member.executes_checkpoint, f"{family} must not count as executing"


def test_rr_fusion_disable_is_sourced_from_config(bundle):
    """The enable decision must cite the config key that made it - no magic."""
    member = bundle.members["rr_fusion"]
    assert member.config_enable_key == "engine_runner.rr_fusion.enabled"
    assert member.config_enabled is False


# ── conflicts are surfaced, never auto-resolved ──────────────────────────────
def test_contested_status_withholds_the_execution_claim(bundle):
    """Gaussian loads a selected artifact but no entry carries mu/sigma (F-060), so
    identity declares enabled_without_checkpoint while a registry+config derivation
    concludes selected_and_enabled. Unresolvable mechanically => claim withheld."""
    member = bundle.members["gaussian"]
    if member.contested:
        assert not member.executes_checkpoint
        assert any("CONTESTED" in d for d in member.divergences)


def test_every_contested_member_is_reported(bundle):
    for family, member in bundle.members.items():
        if member.contested:
            assert member.divergences, f"{family} contested but no divergence recorded"
            assert any(family in d for d in bundle.divergences), family


def test_feature_dim_divergence_is_recorded_not_reconciled(bundle):
    """zone_gate identity claims 39 dims; the v4 artifact's feature_order lists 38."""
    for family, member in bundle.members.items():
        if (
            member.registry_feature_dim is not None
            and member.identity_feature_dim is not None
            and member.registry_feature_dim != member.identity_feature_dim
        ):
            assert any("feature dim" in d for d in member.divergences), family


def test_bundle_grants_no_authority(bundle):
    assert bundle.meta["authority"] == "NONE"
