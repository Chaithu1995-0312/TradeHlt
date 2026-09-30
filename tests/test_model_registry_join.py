"""Model-registry join floor (Phase 0, 2026-09-23).

Joins the three model-declaring surfaces that previously had no test checking they agree:
  - MODEL_CATALOG (src/research/model_runners/contracts.py) — the hub, bound to code
  - miar_registry.json entries[].semantic_ids — intent-owner back-refs
  - active_models.yaml <section>.semantic_ids — descriptive-mirror back-refs

Before this floor, the same model carried three different ids across the three files
(catalog "rr" / MIAR "candle_commitment" / active_models.yaml "rr_model") with nothing checking they
were the same model. This floor makes that mechanically checkable via one semantic_id.

Design plan: docs/implementation_plan/dont-read-codebase-yet-lovely-clarke.md, "Phase 0 —
DETAILED DESIGN". This is a DATA-ONLY, declarative check — it grants no production authority
(CLAUDE.md §6.5); it only verifies that declared metadata is internally consistent.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from research.model_runners.contracts import MODEL_CATALOG  # noqa: E402

_MIAR_JSON = _REPO / "docs" / "governance" / "miar_registry.json"
_ACTIVE_YAML = _REPO / "active_models.yaml"

_SEMANTIC_ID_RE = re.compile(r"^M[0-9]_[A-Z0-9_]+$")
_VALID_TIERS = {"M0", "M1", "M2", "M3", "M4", "M9"}
_VALID_SCALE_TYPES = {
    "score", "tail_prob", "calibrated_prob", "regression", "gate_bool", "categorical", "composite",
}
_VALID_AUTHORITY = {"NONE", "SHADOW", "FUSION_VOTE", "VETO", "SPINE"}
_SPINE_AUTHORITY = {"FUSION_VOTE", "VETO", "SPINE"}
_OFFSPINE_AUTHORITY = {"NONE", "SHADOW"}
# EXPECTED_ENGINES fusion-completeness votes (core.engine_runner.py:54) — the mechanical basis
# for the FUSION_VOTE derivation rule documented in contracts.py's module docstring.
_EXPECTED_ENGINE_ROWS = {"crt_structure_rule_score", "ema_momentum_kernel", "feature_cluster_similarity", "candle_commitment"}


@pytest.fixture(scope="module")
def miar() -> dict:
    return json.loads(_MIAR_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def active_models() -> dict:
    return yaml.safe_load(_ACTIVE_YAML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog_semantic_ids() -> dict:
    return {m.semantic_id: model_id for model_id, m in MODEL_CATALOG.items()}


# ---------------------------------------------------------------------------
# (a) semantic_id is unique and matches the tier-prefixed regex
# ---------------------------------------------------------------------------

def test_semantic_ids_unique_and_well_formed():
    seen: dict[str, str] = {}
    for model_id, m in MODEL_CATALOG.items():
        assert _SEMANTIC_ID_RE.match(m.semantic_id), (
            f"{model_id}: semantic_id {m.semantic_id!r} does not match ^M[0-9]_[A-Z0-9_]+$"
        )
        assert m.semantic_id not in seen, (
            f"duplicate semantic_id {m.semantic_id!r}: {model_id} and {seen[m.semantic_id]}"
        )
        seen[m.semantic_id] = model_id
        assert m.tier in _VALID_TIERS, f"{model_id}: tier {m.tier!r} not in {_VALID_TIERS}"
        assert m.semantic_id.startswith(m.tier + "_"), (
            f"{model_id}: semantic_id {m.semantic_id!r} does not start with its own tier {m.tier!r}"
        )


def test_scale_type_and_authority_vocabularies():
    for model_id, m in MODEL_CATALOG.items():
        assert m.scale_type in _VALID_SCALE_TYPES, (
            f"{model_id}: scale_type {m.scale_type!r} not in {_VALID_SCALE_TYPES}"
        )
        assert m.authority in _VALID_AUTHORITY, (
            f"{model_id}: authority {m.authority!r} not in {_VALID_AUTHORITY}"
        )


# ---------------------------------------------------------------------------
# (b) every miar_id / active_models_key resolves, or carries a reason
# ---------------------------------------------------------------------------

def test_miar_id_resolves_or_has_reason(miar):
    miar_ids = {e["id"] for e in miar["entries"]}
    for model_id, m in MODEL_CATALOG.items():
        if m.miar_id is None:
            assert m.miar_absent_reason, (
                f"{model_id}: miar_id is None but miar_absent_reason is empty"
            )
        else:
            assert m.miar_id in miar_ids, (
                f"{model_id}: miar_id {m.miar_id!r} not a real miar_registry.json entries[].id"
            )
            assert not m.miar_absent_reason, (
                f"{model_id}: has a real miar_id {m.miar_id!r} but also a miar_absent_reason "
                "(pick one)"
            )


def test_active_models_key_resolves_or_has_reason(active_models):
    def _resolves(dotted: str) -> bool:
        node = active_models
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return True

    for model_id, m in MODEL_CATALOG.items():
        if m.active_models_key is None:
            assert m.active_models_absent_reason, (
                f"{model_id}: active_models_key is None but active_models_absent_reason is empty"
            )
        else:
            assert _resolves(m.active_models_key), (
                f"{model_id}: active_models_key {m.active_models_key!r} does not resolve in "
                "active_models.yaml"
            )
            assert not m.active_models_absent_reason, (
                f"{model_id}: has a real active_models_key {m.active_models_key!r} but also an "
                "active_models_absent_reason (pick one)"
            )


# ---------------------------------------------------------------------------
# (c) back-refs agree with the catalog in both directions
# ---------------------------------------------------------------------------

def test_miar_semantic_ids_backref_agrees_with_catalog(miar, catalog_semantic_ids):
    for e in miar["entries"]:
        for sid in e.get("semantic_ids", []):
            assert sid in catalog_semantic_ids, (
                f"miar entry {e['id']!r} declares semantic_ids includes {sid!r}, "
                "which no MODEL_CATALOG row carries"
            )
            owner = MODEL_CATALOG[catalog_semantic_ids[sid]]
            assert owner.miar_id == e["id"], (
                f"miar entry {e['id']!r} claims {sid!r} but that row's own miar_id is "
                f"{owner.miar_id!r} — the back-ref must be symmetric"
            )
    # And the forward direction: every catalog row with a real miar_id must be listed back.
    by_id = {e["id"]: e for e in miar["entries"]}
    for model_id, m in MODEL_CATALOG.items():
        if m.miar_id is not None:
            assert m.semantic_id in by_id[m.miar_id].get("semantic_ids", []), (
                f"{model_id}: declares miar_id={m.miar_id!r} but that MIAR entry's "
                f"semantic_ids does not list {m.semantic_id!r} back"
            )


def test_active_models_semantic_ids_backref_agrees_with_catalog(active_models, catalog_semantic_ids):
    non_model_keys = {"meta", "philosophy", "feature_lineage"}
    for key, section in active_models.items():
        if key in non_model_keys or not isinstance(section, dict):
            continue
        for sid in section.get("semantic_ids", []):
            assert sid in catalog_semantic_ids, (
                f"active_models.yaml section {key!r} declares semantic_ids includes {sid!r}, "
                "which no MODEL_CATALOG row carries"
            )
    # Forward direction: every catalog row with a real active_models_key must be listed back
    # at that (possibly dotted, possibly shared) key's TOP-LEVEL section.
    for model_id, m in MODEL_CATALOG.items():
        if m.active_models_key is not None:
            top_key = m.active_models_key.split(".")[0]
            section = active_models.get(top_key, {})
            assert m.semantic_id in section.get("semantic_ids", []), (
                f"{model_id}: declares active_models_key={m.active_models_key!r} but "
                f"active_models.yaml[{top_key!r}].semantic_ids does not list "
                f"{m.semantic_id!r} back"
            )


# ---------------------------------------------------------------------------
# (d) authority consistent with spine_active; (e) authority>SHADOW needs a MIAR entry
# ---------------------------------------------------------------------------

def test_authority_consistent_with_spine_active():
    for model_id, m in MODEL_CATALOG.items():
        if m.spine_active:
            assert m.authority in _SPINE_AUTHORITY, (
                f"{model_id}: spine_active=True but authority={m.authority!r} not in "
                f"{_SPINE_AUTHORITY}"
            )
        else:
            assert m.authority in _OFFSPINE_AUTHORITY, (
                f"{model_id}: spine_active=False but authority={m.authority!r} not in "
                f"{_OFFSPINE_AUTHORITY}"
            )


def test_fusion_vote_authority_matches_expected_engines():
    """Mechanical derivation, not a per-row judgment call: FUSION_VOTE iff the row's engine
    is one of core.engine_runner.EXPECTED_ENGINES ({"crt","ema_momentum_kernel","feature_cluster_similarity","candle_commitment"})."""
    fusion_vote_rows = {mid for mid, m in MODEL_CATALOG.items() if m.authority == "FUSION_VOTE"}
    assert fusion_vote_rows == _EXPECTED_ENGINE_ROWS, (
        f"FUSION_VOTE rows {fusion_vote_rows} != EXPECTED_ENGINES-derived set "
        f"{_EXPECTED_ENGINE_ROWS} — either a row's authority drifted or EXPECTED_ENGINES "
        "changed in core/engine_runner.py without this floor being updated"
    )


def test_authority_above_shadow_requires_miar_entry():
    for model_id, m in MODEL_CATALOG.items():
        if m.authority not in ("NONE", "SHADOW"):
            assert m.miar_id is not None, (
                f"{model_id}: authority={m.authority!r} (> SHADOW) but has no miar_id — a "
                "model with real production authority must have a declared intent owner"
            )


# ---------------------------------------------------------------------------
# (f) a trained-on-stale-schema artifact must not claim a fully-trusted audit_status
# ---------------------------------------------------------------------------

_UNTRUSTED_STATUSES_FOR_STALE_ARTIFACT = {
    "DORMANT", "EXPERIMENTAL", "OFF_SPINE", "UNWIRED", "DEPRECATED", "FAILED", "CONDITIONAL",
}


def test_trained_artifact_never_claims_certified_status():
    """A model with a declared trained_on_schema (i.e. it was trained on SOME fixed artifact,
    not a stateless heuristic) must not carry audit_status=CERTIFIED — CERTIFIED is reserved
    for stateless/geometric rows with nothing to go stale. Catches BitNet's exact failure class
    (Gap 1/2 this session) mechanically: a trained artifact silently treated as fully trusted."""
    for model_id, m in MODEL_CATALOG.items():
        if m.trained_on_schema is not None:
            assert m.audit_status in _UNTRUSTED_STATUSES_FOR_STALE_ARTIFACT, (
                f"{model_id}: trained_on_schema={m.trained_on_schema!r} but "
                f"audit_status={m.audit_status!r} claims full trust — a trained artifact must "
                f"carry one of {_UNTRUSTED_STATUSES_FOR_STALE_ARTIFACT}"
            )


# ---------------------------------------------------------------------------
# (g) required_feature_keys is a subset of the live canonical schema
# ---------------------------------------------------------------------------

def test_required_feature_keys_are_canonical():
    from features.feature_schema import CANONICAL_FEATURES

    canonical = set(CANONICAL_FEATURES)
    for model_id, m in MODEL_CATALOG.items():
        unknown = m.required_feature_keys - canonical
        assert not unknown, (
            f"{model_id}: required_feature_keys contains non-canonical names {unknown} — "
            "not in the live 48-dim v6.0 schema"
        )


# ---------------------------------------------------------------------------
# (h) design-only specialist/arbiter ids are disjoint from live catalog ids
# ---------------------------------------------------------------------------

def test_design_only_semantic_ids_disjoint_from_catalog(miar, catalog_semantic_ids):
    design_only_ids = {
        d["semantic_id"] for d in miar["design_only_concepts"] if "semantic_id" in d
    }
    overlap = design_only_ids & set(catalog_semantic_ids)
    assert not overlap, (
        f"design_only_concepts semantic_ids overlap MODEL_CATALOG semantic_ids: {overlap} — "
        "a DESIGN_ONLY row must not claim an id already live in the catalog"
    )
    # And they must themselves be unique and well-formed.
    seen: set[str] = set()
    for d in miar["design_only_concepts"]:
        sid = d.get("semantic_id")
        if sid is None:
            continue
        assert _SEMANTIC_ID_RE.match(sid), f"design_only {d['name']!r}: bad semantic_id {sid!r}"
        assert sid not in seen, f"design_only duplicate semantic_id {sid!r}"
        seen.add(sid)


def test_design_only_count_matches_phase3_plan(miar):
    """Pins the seed count from the approved plan (16 block specialists + 3 state specialists +
    1 temporal tracker + 1 arbiter = 21), plus the pre-existing envelope/RRPatternMiner rows.
    A change here should be a deliberate Phase 3 build-out, not silent drift."""
    with_ids = [d for d in miar["design_only_concepts"] if "semantic_id" in d]
    assert len(with_ids) == 21
    without_ids = [d for d in miar["design_only_concepts"] if "semantic_id" not in d]
    assert len(without_ids) == 2  # RRPatternMiner_historical_evidence_retrieval, envelope_...
