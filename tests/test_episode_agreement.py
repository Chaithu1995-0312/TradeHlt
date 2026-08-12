"""Phase 2C typed Agreement fold (O14) — research shadow."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.episode_agreement import (
    POLICY_VERSION,
    VERDICT_VOCAB,
    Agreement,
    attach_agreement,
    build_agreement,
    verdict_to_layer_status,
)
from research.episode_propositions import build_propositions, propositions_to_jsonable

_REPO = Path(__file__).resolve().parents[1]
_MOD = _REPO / "src" / "research" / "episode_agreement.py"


def _ep_aligned(**overrides):
    base = {
        "episode_id": "EP_ALIGN",
        "crt": {
            "state": "RETEST",
            "event": {"direction": "SHORT", "action": "RETEST_CONFIRMED"},
        },
        "feature_states": {"trend_bias": "Bearish"},
        "market_shape": {
            "name": "BearishBreakoutExpansion",
            "family": "BreakoutExpansion",
            "matched": True,
        },
        "magnitude_states": {
            "body_commitment": "MediumCommitment",
            "atr_magnitude": "HighAtrMagnitude",
            "momentum_magnitude": "MediumMomentumMagnitude",
        },
        "model_evidence": {
            "values": {
                "crt": {
                    "value": 0.0,
                    "semantic": "structure_rule_score",
                    "question": "structure valid?",
                },
                "gaussian": {"value": 0.88, "semantic": "ema_momentum_kernel_score"},
                "rr_model": {"value": 0.7, "semantic": "candle_structure_quality"},
            },
            "absent": ["bitnet"],
        },
    }
    base.update(overrides)
    base["propositions"] = propositions_to_jsonable(build_propositions(base))
    return base


def _ep_conflict():
    return _ep_aligned(
        episode_id="EP_CONFLICT",
        crt={"state": "RETEST", "event": {"direction": "LONG"}},
        feature_states={"trend_bias": "Bearish"},
        market_shape={"name": "BearishStructuralBreak", "matched": True},
    )


def test_verdict_vocab():
    assert VERDICT_VOCAB == {"COHERENT", "PARTIAL", "BREAK"}


def test_coherent_when_o11_same_event_and_o12_orthogonal():
    agr = build_agreement(_ep_aligned())
    assert agr.policy_version == POLICY_VERSION
    assert agr.verdict == "COHERENT"
    assert agr.exit_claims_present is True
    assert agr.unresolved_conflicts == []
    assert any("ORTHOGONAL" in a for a in agr.aligned)
    # O12 low score does not create tension (POL-O12)
    assert not any("structure_rule_score=0" in t and "CONFLICT" in t for t in agr.tension)


def test_break_preserves_o11_conflict():
    agr = build_agreement(_ep_conflict())
    assert agr.verdict == "BREAK"
    assert len(agr.unresolved_conflicts) >= 1
    assert any(c.get("claim_kind") == "DIRECTION_ALIGNMENT" for c in agr.unresolved_conflicts)
    assert agr.tension  # CONFLICT must appear in tension
    assert "Unresolved conflicts" in agr.episode_interpretation
    assert "false-agreed" in agr.episode_interpretation or "preserved" in agr.episode_interpretation


def test_partial_when_o11_insufficient():
    ep = _ep_aligned(
        episode_id="EP_PARTIAL",
        crt={"state": "EXPANSION", "event": None},
    )
    # rebuild props after override
    ep["propositions"] = propositions_to_jsonable(build_propositions(ep))
    agr = build_agreement(ep)
    assert agr.verdict == "PARTIAL"
    assert agr.unresolved_conflicts == []


def test_o12_orthogonal_not_conflict_with_zero_score():
    """POL-O12 non-regression: score 0 + RETEST is ORTHOGONAL, not Agreement BREAK from O12."""
    ep = _ep_aligned()
    props = ep["propositions"]
    o12 = next(p for p in props if p["claim_kind"] == "CHAPTER_VS_STRUCTURE_SCORE")
    assert o12["relation"] == "ORTHOGONAL"
    assert o12["surfaces"]["testimony"]["value"] == 0.0
    agr = build_agreement(ep)
    # aligned path remains COHERENT; O12 not in unresolved_conflicts
    assert agr.verdict == "COHERENT"
    assert not any(
        c.get("claim_kind") == "CHAPTER_VS_STRUCTURE_SCORE" for c in agr.unresolved_conflicts
    )


def test_break_if_exit_propositions_missing():
    ep = _ep_aligned()
    ep["propositions"] = []  # empty
    # build_agreement with empty list → missing exit → BREAK
    agr = build_agreement(ep, propositions=[])
    assert agr.verdict == "BREAK"
    assert agr.exit_claims_present is False


def test_by_relation_preserves_all_props():
    ep = _ep_conflict()
    agr = build_agreement(ep)
    total = sum(agr.relation_counts.values())
    assert total == len(ep["propositions"])
    # every prop id appears in some bucket
    ids = {p["proposition_id"] for p in ep["propositions"]}
    bucket_ids = {
        p["proposition_id"] for rel_list in agr.by_relation.values() for p in rel_list
    }
    assert ids == bucket_ids


def test_attach_agreement_writes_object_and_legacy_view():
    out = attach_agreement(_ep_conflict(), ensure_propositions=True)
    assert "agreement_object" in out
    assert out["agreement_object"]["verdict"] == "BREAK"
    assert out["agreement"]["verdict"] == "BREAK"
    assert out["agreement"]["tension"]
    assert out["agreement"]["policy_version"] == POLICY_VERSION


def test_verdict_to_layer_status():
    assert verdict_to_layer_status("COHERENT") == "OK"
    assert verdict_to_layer_status("PARTIAL") == "PARTIAL"
    assert verdict_to_layer_status("BREAK") == "BREAK"


def test_invalid_verdict_rejected():
    with pytest.raises(ValueError):
        Agreement(
            episode_id="x",
            policy_version=POLICY_VERSION,
            authority="research_shadow",
            verdict="TRUE",
            surfaces_participating={},
            by_relation={},
            aligned=[],
            tension=[],
            silent=[],
            insufficient=[],
            unresolved_conflicts=[],
            episode_interpretation="",
            exit_claims_present=True,
            relation_counts={},
        )


def test_deterministic():
    ep = _ep_conflict()
    a = build_agreement(ep).to_dict()
    b = build_agreement(ep).to_dict()
    assert a == b


def test_no_spine_imports():
    tree = ast.parse(_MOD.read_text(encoding="utf-8"))
    forbidden_prefixes = (
        "core.engine_runner",
        "governance.promotion_manager",
        "config_layer.config_validator",
        "engines.",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(alias.name.startswith(p) for p in forbidden_prefixes)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not any(node.module.startswith(p) for p in forbidden_prefixes)
