"""Phase 2B typed episode propositions — research shadow (no spine)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.episode_propositions import (
    CLAIM_KINDS,
    EXIT_CLAIM_KINDS,
    POLICY_O12,
    RELATION_VOCAB,
    Proposition,
    attach_propositions,
    build_chapter_vs_structure_score,
    build_direction_alignment,
    build_propositions,
    dir_sign_crt,
    dir_sign_shape,
    dir_sign_trend,
    proposition_by_claim,
    relation_to_census_class,
)

_REPO = Path(__file__).resolve().parents[1]
_MOD = _REPO / "src" / "research" / "episode_propositions.py"


def _ep(**overrides):
    base = {
        "episode_id": "TEST_EP",
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
                    "question": "Is the market structure valid?",
                    "status": "active",
                },
                "gaussian": {
                    "value": 0.88,
                    "semantic": "ema_momentum_kernel_score",
                    "question": "profitable?",
                },
                "rr_model": {
                    "value": 0.7,
                    "semantic": "candle_structure_quality",
                    "question": "rr?",
                },
            },
            "absent": ["bitnet", "tradenet", "envelope"],
        },
    }
    base.update(overrides)
    return base


def test_relation_and_claim_vocab_closed():
    assert "SAME_EVENT" in RELATION_VOCAB
    assert "ORTHOGONAL" in RELATION_VOCAB
    assert "CONFLICT" in RELATION_VOCAB
    assert set(EXIT_CLAIM_KINDS) <= CLAIM_KINDS


def test_dir_sign_helpers():
    assert dir_sign_crt("LONG") == 1
    assert dir_sign_crt("SHORT") == -1
    assert dir_sign_crt("NONE") == 0
    assert dir_sign_trend("Bullish") == 1
    assert dir_sign_trend("Bearish") == -1
    assert dir_sign_shape("BearishBreakoutExpansion") == -1
    assert dir_sign_shape("BullishStructuralBreak") == 1


def test_o11_same_event_when_dirs_align():
    p = build_direction_alignment(_ep())
    assert p.claim_kind == "DIRECTION_ALIGNMENT"
    assert p.relation == "SAME_EVENT"
    assert p.observation_id == "O11"
    assert relation_to_census_class(p.relation, observation="O11_crt_dir_vs_context_shape") == "COVERED"


def test_o11_conflict_long_vs_bearish_shape():
    p = build_direction_alignment(
        _ep(
            crt={"state": "RETEST", "event": {"direction": "LONG"}},
            feature_states={"trend_bias": "Bearish"},
            market_shape={"name": "BearishStructuralBreak", "matched": True},
        )
    )
    assert p.relation == "CONFLICT"
    assert relation_to_census_class(p.relation, observation="O11_crt_dir_vs_context_shape") == (
        "CONTRADICTORY"
    )


def test_o11_insufficient_without_crt_direction():
    p = build_direction_alignment(
        _ep(crt={"state": "EXPANSION", "event": None})
    )
    assert p.relation == "INSUFFICIENT"


def test_o12_orthogonal_even_when_score_is_zero():
    """POL-O12-SCORE-NOT-CHAPTER: low structure score ≠ chapter conflict."""
    p = build_chapter_vs_structure_score(_ep())
    assert p.claim_kind == "CHAPTER_VS_STRUCTURE_SCORE"
    assert p.relation == "ORTHOGONAL"
    assert p.resolution is not None
    assert p.resolution["policy_id"] == POLICY_O12["policy_id"]
    assert p.surfaces["testimony"]["semantic"] == "structure_rule_score"
    assert p.surfaces["testimony"]["value"] == 0.0
    assert relation_to_census_class(
        p.relation, observation="O12_crt_story_vs_structure_score"
    ) == "COVERED"


def test_o12_pins_structure_rule_score_semantic():
    p = build_chapter_vs_structure_score(
        _ep(
            model_evidence={
                "values": {
                    "crt": {
                        "value": 0.9,
                        "semantic": "something_else",
                        "question": "?",
                    }
                }
            }
        )
    )
    assert p.relation == "INSUFFICIENT"


def test_build_propositions_emits_exit_claims():
    props = build_propositions(_ep())
    kinds = {p.claim_kind for p in props}
    for k in EXIT_CLAIM_KINDS:
        assert k in kinds
    assert "QUALITY_VS_DIRECTION" in kinds
    assert "MAGNITUDE_SUBSTRATE" in kinds
    # no Agreement product
    assert all(p.claim_kind != "AGREEMENT" for p in props)


def test_quality_vs_direction_is_orthogonal():
    p = proposition_by_claim(build_propositions(_ep()), "QUALITY_VS_DIRECTION")
    assert isinstance(p, Proposition)
    assert p.relation == "ORTHOGONAL"


def test_magnitude_substrate_orthogonal_when_present():
    p = proposition_by_claim(build_propositions(_ep()), "MAGNITUDE_SUBSTRATE")
    assert isinstance(p, Proposition)
    assert p.relation == "ORTHOGONAL"


def test_attach_propositions_jsonable():
    out = attach_propositions(_ep())
    assert isinstance(out["propositions"], list)
    assert len(out["propositions"]) == 4
    assert all("relation" in p for p in out["propositions"])


def test_invalid_relation_rejected():
    with pytest.raises(ValueError):
        Proposition(
            proposition_id="x",
            episode_id="e",
            claim_kind="DIRECTION_ALIGNMENT",
            relation="MAYBE",
        )


def test_module_does_not_import_spine_or_promotion():
    """Research shadow: no core.engine_runner / promotion_manager imports."""
    tree = ast.parse(_MOD.read_text(encoding="utf-8"))
    forbidden = {
        "core.engine_runner",
        "core.decision_engine",
        "governance.promotion_manager",
        "config_layer.config_validator",
        "engines.crt_engine",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden
                assert not any(alias.name.startswith(f + ".") for f in forbidden)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in forbidden
            assert not any(node.module.startswith(f + ".") for f in forbidden)


def test_deterministic_rebuild():
    ep = _ep()
    a = [p.to_dict() for p in build_propositions(ep)]
    b = [p.to_dict() for p in build_propositions(ep)]
    assert a == b
