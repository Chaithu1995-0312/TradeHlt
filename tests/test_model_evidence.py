"""Layer-7 Model Evidence floor — declaration contract, fail-closed build, F-048 semantic.

Mirrors the discipline of tests/test_market_context.py: a malformed-declaration battery (every
one a LOAD error), fail-closed build behaviour, determinism, and a registry-exhaustiveness
ratchet so a newly declared model cannot silently escape the layer.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from features.model_evidence import (  # noqa: E402
    EvidenceSet,
    ModelEvidenceBuilder,
    X_PREFIX,
    load_active_models,
)


@pytest.fixture(scope="module")
def doc() -> dict:
    return load_active_models()


@pytest.fixture()
def builder(doc: dict) -> ModelEvidenceBuilder:
    return ModelEvidenceBuilder(copy.deepcopy(doc))


@pytest.fixture()
def engine_results() -> dict:
    """The shape EngineRunner assembles (values arbitrary — this layer computes nothing)."""
    return {
        "crt": {"score": 0.4123},
        "gaussian": {"score": 0.8825, "reason": "kernel"},
        "zone_gate": {"score": 0.61, "passed": True, "valid": True},
        "rr": {"score": 0.72, "candle_polarity": 0.72, "rr_ratio": 0.72,
               "reason": "candle_polarity:0.72", "semantic": "candle_structure_quality"},
    }


def _model_section(doc: dict, model_id: str) -> dict:
    return doc[model_id]


# ── declaration contract (LOAD errors) ───────────────────────────────────────

@pytest.mark.parametrize("field", ["engine_key", "output_field", "output_semantic", "active"])
def test_missing_binding_field_is_a_load_error(doc: dict, field: str) -> None:
    """Every model must declare its full evidence binding — no defaults."""
    d = copy.deepcopy(doc)
    del _model_section(d, "crt")["runtime"][field]
    with pytest.raises(ValueError, match=field):
        ModelEvidenceBuilder(d)


def test_duplicate_engine_key_is_a_load_error(doc: dict) -> None:
    """One slot, one owner — a second claimant is a registry conflict."""
    d = copy.deepcopy(doc)
    _model_section(d, "gaussian")["runtime"]["engine_key"] = "crt"
    with pytest.raises(ValueError, match="one slot, one owner"):
        ModelEvidenceBuilder(d)


def test_non_string_engine_key_is_a_load_error(doc: dict) -> None:
    d = copy.deepcopy(doc)
    _model_section(d, "crt")["runtime"]["engine_key"] = 7
    with pytest.raises(ValueError, match="non-string"):
        ModelEvidenceBuilder(d)


def test_producer_without_output_field_is_a_load_error(doc: dict) -> None:
    d = copy.deepcopy(doc)
    _model_section(d, "crt")["runtime"]["output_field"] = None
    with pytest.raises(ValueError, match="output_field"):
        ModelEvidenceBuilder(d)


def test_empty_semantic_is_a_load_error(doc: dict) -> None:
    """A value without a declared meaning is what this layer exists to prevent."""
    d = copy.deepcopy(doc)
    _model_section(d, "rr_model")["runtime"]["output_semantic"] = ""
    with pytest.raises(ValueError, match="output_semantic"):
        ModelEvidenceBuilder(d)


def test_orchestration_sections_are_not_models(builder: ModelEvidenceBuilder) -> None:
    """`strategies`/`engine_runner`/`philosophy` carry intent but answer no question."""
    for non_model in ("strategies", "engine_runner", "philosophy", "feature_lineage", "meta"):
        assert non_model not in builder.models


# ── build contract (fail-closed) ─────────────────────────────────────────────

def test_undeclared_producer_raises(builder: ModelEvidenceBuilder, engine_results: dict) -> None:
    engine_results["mystery_engine"] = {"score": 1.0}
    with pytest.raises(KeyError, match="no declaring model"):
        builder.build(engine_results)


def test_absent_declared_producer_raises_listing_all(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    del engine_results["zone_gate"]
    del engine_results["rr"]
    with pytest.raises(KeyError) as exc:
        builder.build(engine_results)
    assert "zone_gate" in str(exc.value) and "rr" in str(exc.value)


def test_declared_output_field_missing_raises(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """rr declares candle_polarity; a producer that stops emitting it is a shape change."""
    del engine_results["rr"]["candle_polarity"]
    with pytest.raises(KeyError, match="changed shape"):
        builder.build(engine_results)


def test_inert_models_are_named_not_dropped(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """F-004 BitNet / F-005 TradeNet / envelope stay visible as declared-absent."""
    es = builder.build(engine_results)
    assert set(es.absent) == {"bitnet", "tradenet", "envelope"}
    assert set(es.evidence) == set(builder.producers)


# ── F-048 contract: the semantic travels with the value ──────────────────────

def test_rr_evidence_declares_polarity_not_economic_rr(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """The whole point of the layer: polarity can never be read as reward:risk."""
    es = builder.build(engine_results)
    rr = es.evidence["rr_model"]
    # Mirrors the engine's own self-declared semantic (rr_engine.py:81), not the legacy alias.
    assert rr.semantic == "candle_structure_quality"
    assert "rr_ratio" not in rr.semantic
    assert rr.engine_key == "rr"
    assert rr.value == pytest.approx(0.72)


def test_producer_semantic_drift_raises(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """If the engine ever relabels its own output, the registry must not silently disagree."""
    engine_results["rr"]["semantic"] = "forward_reward_risk"
    with pytest.raises(ValueError, match="disagree about what the value MEANS"):
        builder.build(engine_results)


def test_rr_engine_self_declared_semantic_matches_the_registry() -> None:
    """Ties the declaration to live source: run the real RREngine and compare."""
    from engines.rr_engine import RREngine
    out = RREngine({}).compute({"high": 101.0, "low": 99.0, "close": 100.8})
    assert out["semantic"] == ModelEvidenceBuilder().spec("rr_model").output_semantic
    # Domain check from source: the two fractions sum to 1, so polarity >= 0.5 when range > 0.
    assert 0.5 <= out["candle_polarity"] <= 1.0


def test_no_model_claims_an_economic_rr_semantic(builder: ModelEvidenceBuilder) -> None:
    """True RR is SL/TP-derived and owned by UltronRiskGate — no engine slot may claim it."""
    for model_id in builder.producers:
        assert builder.spec(model_id).output_semantic not in {
            "true_rr", "reward_risk_ratio", "candle_polarity_as_rr",
        }


def test_semantic_of_slot_is_readable_without_the_spine(
    builder: ModelEvidenceBuilder,
) -> None:
    assert builder.semantic_of("rr") == "candle_structure_quality"
    with pytest.raises(KeyError):
        builder.semantic_of("not_a_slot")


# ── drift markers, determinism, exhaustiveness ───────────────────────────────

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "not_a_number"])
def test_non_numeric_value_becomes_a_marker_not_a_substitute(
    builder: ModelEvidenceBuilder, engine_results: dict, bad: object
) -> None:
    engine_results["crt"]["score"] = bad
    es = builder.build(engine_results)
    assert es.evidence["crt"].rendered.startswith(X_PREFIX)
    assert es.evidence["crt"].value is None
    assert any(m.startswith("crt=") for m in es.x_markers)


def test_boolean_output_is_refused_not_coerced(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """float(True)==1.0 — a gate flag must never be silently accepted as a score."""
    engine_results["zone_gate"]["score"] = True
    with pytest.raises(TypeError, match="a flag is not a score"):
        builder.build(engine_results)


def test_evidence_hash_is_deterministic(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    a = builder.build(copy.deepcopy(engine_results))
    b = builder.build(copy.deepcopy(engine_results))
    assert a.evidence_hash == b.evidence_hash
    assert isinstance(a, EvidenceSet) and len(a.evidence_hash) == 16


def test_evidence_hash_moves_with_the_evidence(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    before = builder.build(copy.deepcopy(engine_results)).evidence_hash
    engine_results["crt"]["score"] = 0.9999
    assert builder.build(engine_results).evidence_hash != before


def test_reason_is_carried_verbatim_and_absence_is_recorded(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    es = builder.build(engine_results)
    assert es.evidence["gaussian"].reason == "kernel"
    assert es.evidence["crt"].reason is None      # recorded, not filled


def test_layer_performs_no_arithmetic(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """Combination is Layer 8's job — values pass through unmodified."""
    es = builder.build(engine_results)
    for model_id, key, field in (
        ("crt", "crt", "score"), ("gaussian", "gaussian", "score"),
        ("zone_gate", "zone_gate", "score"), ("rr_model", "rr", "candle_polarity"),
    ):
        assert es.evidence[model_id].value == pytest.approx(engine_results[key][field])


def test_declared_slots_match_expected_engines(builder: ModelEvidenceBuilder) -> None:
    """Registry-exhaustiveness ratchet: the declared producers ARE the runtime's engine set.

    Imports EXPECTED_ENGINES here (never in the module) so the layer stays spine-free while the
    invariant is still enforced mechanically.
    """
    from core.engine_runner import EXPECTED_ENGINES
    assert set(builder.engine_keys) == set(EXPECTED_ENGINES)


def test_module_does_not_import_the_spine() -> None:
    """Shadow-only: Layer 7 must not pull core/ or engines/ into its import graph."""
    source = (_ROOT / "src" / "features" / "model_evidence.py").read_text(encoding="utf-8")
    for forbidden in ("from core", "import core", "from engines", "import engines"):
        assert forbidden not in source


# ── L7 structured testimony contract ────────────────────────────────────────

def test_every_producer_has_explicit_question_and_score_semantics(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    es = builder.build(engine_results)
    for mid in builder.producers:
        ev = es.evidence[mid]
        assert ev.question  # non-empty producer question
        assert ev.score_semantics == ev.semantic
        assert ev.producer == mid
        assert ev.availability == "PRESENT"
        assert "active_models.yaml" in ev.provenance


def test_absent_producer_is_structured_absent(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    es = builder.build(engine_results)
    for mid in ("bitnet", "tradenet", "envelope"):
        assert mid in es.absent
        rec = es.absent_records[mid]
        assert rec["availability"] == "ABSENT"
        assert rec["value"] is None
        assert rec["direction"] == "UNKNOWN"
        assert rec["relationship_to_story"] == "NOT_APPLICABLE"
        assert "active_models.yaml" in rec["provenance"]


def test_quality_score_never_becomes_direction(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """Gaussian 0.88 is quality testimony — direction stays UNKNOWN."""
    engine_results["gaussian"]["score"] = 0.88
    es = builder.build(engine_results)
    g = es.evidence["gaussian"]
    assert g.value == pytest.approx(0.88)
    assert g.direction == "UNKNOWN"
    assert g.relationship_to_story == "UNKNOWN"
    assert "profitable" in g.question.lower() or "probability" in g.question.lower()


def test_crt_story_and_crt_testimony_remain_separate(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """CRT state=RETEST + structure_rule_score=0.0 must not collapse into 'CRT invalid'."""
    engine_results["crt"]["score"] = 0.0
    story = {
        "crt_state": "RETEST",
        "crt_direction": "SHORT",
        "context_direction": "Bearish",
        "shape_name": "BearishBreakoutExpansion",
    }
    es = builder.build(engine_results, story=story)
    crt = es.evidence["crt"]
    assert crt.value == pytest.approx(0.0)
    assert crt.semantic == "structure_rule_score"
    assert crt.relationship_to_story == "NOT_APPLICABLE"
    assert crt.direction == "UNKNOWN"  # score is not direction
    assert es.crt_story is not None
    assert es.crt_story["state"] == "RETEST"
    assert es.crt_story["direction"] == "SHORT"
    assert es.crt_testimony is not None
    assert es.crt_testimony["value"] == pytest.approx(0.0)
    assert es.crt_testimony["surface"] == "CRT_TESTIMONY"
    # story surface remains distinct from testimony surface
    assert es.crt_story["surface"] == "CRT_STORY"


def test_high_gaussian_with_crt_story_stays_unknown_relationship(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    engine_results["gaussian"]["score"] = 0.99
    engine_results["crt"]["score"] = 0.0
    es = builder.build(
        engine_results,
        story={"crt_state": "RETEST", "crt_direction": "SHORT"},
    )
    assert es.evidence["gaussian"].relationship_to_story == "UNKNOWN"
    assert es.evidence["crt"].relationship_to_story == "NOT_APPLICABLE"


def test_testimony_does_not_become_market_state(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """Evidence records are scores+questions — no trend/volatility/CRT chapter fields."""
    es = builder.build(engine_results)
    for ev in es.evidence.values():
        d = ev.to_dict()
        assert "crt_state" not in d or d.get("story_refs") is not None
        assert d["score_semantics"]  # meaning travels with value
        # no fabricated market-state label
        assert d["direction"] in ("UNKNOWN", "LONG", "SHORT")


def test_testimony_deterministic_with_story(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    story = {"crt_state": "EXPANSION", "crt_direction": "LONG"}
    a = builder.build(copy.deepcopy(engine_results), story=story)
    b = builder.build(copy.deepcopy(engine_results), story=story)
    assert a.evidence_hash == b.evidence_hash
    assert a.signature == b.signature
    for mid in a.evidence:
        assert a.evidence[mid].relationship_to_story == b.evidence[mid].relationship_to_story


def test_active_models_remains_authoritative_for_producers(
    builder: ModelEvidenceBuilder,
) -> None:
    doc = load_active_models()
    declared_questions = {
        k: v["intent"]["question"]
        for k, v in doc.items()
        if isinstance(v, dict)
        and isinstance(v.get("intent"), dict)
        and v["intent"].get("question")
        and isinstance(v.get("runtime"), dict)
        and v.get("status") is not None
    }
    assert set(builder.models) == set(declared_questions)
    for mid in builder.models:
        assert builder.spec(mid).question == declared_questions[mid]


def test_producer_declared_direction_can_support_or_contradict(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """Only explicit direction fields may SUPPORT/CONTRADICT — never score magnitude."""
    # Inject an explicit direction on gaussian (hypothetical producer extension)
    engine_results["gaussian"]["direction"] = "LONG"
    es_support = builder.build(
        engine_results,
        story={"crt_state": "RETEST", "crt_direction": "LONG", "context_direction": "Bullish"},
    )
    assert es_support.evidence["gaussian"].direction == "LONG"
    assert es_support.evidence["gaussian"].relationship_to_story == "SUPPORTS"

    engine_results["gaussian"]["direction"] = "SHORT"
    es_contra = builder.build(
        engine_results,
        story={"crt_state": "RETEST", "crt_direction": "LONG", "context_direction": "Bullish"},
    )
    assert es_contra.evidence["gaussian"].relationship_to_story == "CONTRADICTS"


def test_no_agreement_field_on_evidence_set(
    builder: ModelEvidenceBuilder, engine_results: dict
) -> None:
    """Testimony must not collapse into agreement."""
    es = builder.build(engine_results)
    d = es.to_dict()
    assert "agreement" not in d
    assert "verdict" not in d
    assert "models_agree" not in d


# ── Cross-layer relationship honesty cases ───────────────────────────────────

@pytest.mark.parametrize(
    "crt_dir,trend,shape,expect_crt_rel",
    [
        ("LONG", "Bullish", "BullishBreakoutExpansion", "NOT_APPLICABLE"),
        ("SHORT", "Bearish", "BearishBreakoutExpansion", "NOT_APPLICABLE"),
        ("LONG", "Bearish", "BearishBreakoutExpansion", "NOT_APPLICABLE"),
        ("SHORT", "Bullish", "BullishBreakoutExpansion", "NOT_APPLICABLE"),
    ],
)
def test_cross_layer_crt_score_relationship_not_direction_proxy(
    builder: ModelEvidenceBuilder,
    engine_results: dict,
    crt_dir: str,
    trend: str,
    shape: str,
    expect_crt_rel: str,
) -> None:
    engine_results["crt"]["score"] = 0.0 if crt_dir == "SHORT" else 0.9
    es = builder.build(
        engine_results,
        story={
            "crt_state": "RETEST",
            "crt_direction": crt_dir,
            "context_direction": trend,
            "shape_name": shape,
        },
    )
    assert es.evidence["crt"].relationship_to_story == expect_crt_rel
    assert es.evidence["gaussian"].relationship_to_story == "UNKNOWN"
    assert es.evidence["rr_model"].direction == "UNKNOWN"
    assert es.crt_story["direction"] == crt_dir
    assert es.crt_testimony["semantic"] == "structure_rule_score"
