"""Floor: Model Intent Authority Register (MIAR) shape + ownership uniqueness."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIAR_JSON = ROOT / "docs" / "governance" / "miar_registry.json"
MIAR_MD = ROOT / "docs" / "governance" / "MODEL_INTENT_AUTHORITY_REGISTER.md"

EXPECTED_IDS = [
    "market_ontology",
    "feature_pipeline",
    "crt",
    "gaussian",
    "zone_gate",
    "tradenet",
    "rr_engine",
    "rr_trained",
    "bitnet",
    "trap",
    "breakout",
    "regime",
    "execution_intent",
    "decision_fusion",
    "qualification_gate",
    "backtest",
    "research_runner",
]


EXPECTED_SIDECAR_IDS = [
    "hierarchical_meta_fusion",
    "tradenet_meta",
    "replay_memory",
    "cognitive_bus",
]


def _load() -> dict:
    assert MIAR_JSON.is_file(), f"missing {MIAR_JSON}"
    return json.loads(MIAR_JSON.read_text(encoding="utf-8"))


def test_miar_charter_exists():
    assert MIAR_MD.is_file()
    text = MIAR_MD.read_text(encoding="utf-8")
    assert "Model Intent Authority Register" in text
    assert "explicit_non_goals" in text or "Explicit non-goals" in text
    assert "Market Ontology" in text


def test_miar_has_exactly_seventeen_entries():
    data = _load()
    entries = data["entries"]
    assert len(entries) == 17
    ids = [e["id"] for e in entries]
    assert ids == EXPECTED_IDS


def test_miar_required_fields_complete():
    data = _load()
    required = data["required_fields"]
    for e in data["entries"]:
        for f in required:
            assert f in e, f"entry {e.get('id')} missing field {f}"
            val = e[f]
            if f == "explicit_non_goals":
                assert isinstance(val, list) and len(val) >= 1
            elif f == "dependencies":
                assert isinstance(val, list)
            elif f == "primary_code":
                assert isinstance(val, list) and len(val) >= 1
            elif f == "stage_order":
                # null = adjunct / measurement (not in 1–10 spine order)
                assert val is None or (isinstance(val, int) and val >= 0)
            else:
                assert val is not None and val != ""


def test_miar_alignment_tokens_valid():
    data = _load()
    allowed = set(data["alignment_tokens"])
    for e in data["entries"]:
        assert e["alignment"] in allowed
        assert e["implementation_status"] in (
            "EXECUTABLE",
            "PARTIAL",
            "DESIGN_ONLY",
        )


def _norm_intent(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def test_miar_intents_unique_among_decision_owners():
    """No two entries may share the same normalized intent string.

    Spans BOTH registers: a sidecar must not restate a spine engine's question.
    """
    data = _load()
    seen: dict[str, str] = {}
    for e in data["entries"] + data.get("sidecar_entries", []):
        key = _norm_intent(e["intent"])
        assert key not in seen, (
            f"duplicate intent between {seen[key]} and {e['id']}: {e['intent']!r}"
        )
        seen[key] = e["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Advisory sidecar register (registered 2026-07-29) — zero spine authority.
# Kept OUT of `entries` so the 17-entry spine register stays fixed (the same
# invariant the envelope DESIGN_ONLY note protects).
# ─────────────────────────────────────────────────────────────────────────────


def test_sidecar_register_shape():
    data = _load()
    entries = data["sidecar_entries"]
    assert [e["id"] for e in entries] == EXPECTED_SIDECAR_IDS
    spine_ids = {e["id"] for e in data["entries"]}
    for e in entries:
        assert e["id"] not in spine_ids, f"{e['id']} is in both registers"


def test_sidecar_required_fields_complete():
    """Sidecars carry the same 16-field contract as spine entries."""
    data = _load()
    required = data["required_fields"]
    stages = set(data["stages"])
    allowed_alignment = set(data["alignment_tokens"])
    for e in data["sidecar_entries"]:
        for f in required:
            assert f in e, f"sidecar {e.get('id')} missing field {f}"
        assert isinstance(e["explicit_non_goals"], list) and len(e["explicit_non_goals"]) >= 1
        assert isinstance(e["primary_code"], list) and len(e["primary_code"]) >= 1
        assert e["stage"] in stages
        assert e["alignment"] in allowed_alignment
        assert e["implementation_status"] in ("EXECUTABLE", "PARTIAL", "DESIGN_ONLY")


def test_sidecar_has_zero_spine_authority():
    """The binding sidecar rule, enforced mechanically rather than by prose.

    Every sidecar must declare NONE authority and must forbid entering
    EXPECTED_ENGINES. This is what stops a decision-SHAPED advisory output from
    quietly acquiring decision authority.
    """
    data = _load()
    for e in data["sidecar_entries"]:
        assert e["authority_boundary"].strip().upper().startswith("NONE"), (
            f"{e['id']} must declare NONE authority, got {e['authority_boundary']!r}"
        )
        non_goals = " ".join(e["explicit_non_goals"]).lower()
        assert "expected_engines" in non_goals, (
            f"{e['id']} must explicitly forbid entering EXPECTED_ENGINES"
        )


def test_sidecar_owns_no_market_question():
    """Sidecars may not own a row in the market-question ownership matrix."""
    data = _load()
    sidecar_ids = {e["id"] for e in data["sidecar_entries"]}
    for row in data["market_question_matrix"]:
        assert row["owner"] not in sidecar_ids, (
            f"sidecar {row['owner']} must not own question {row['question']!r}"
        )


def test_sidecar_authority_rule_recorded():
    data = _load()
    rule = data["sidecar_authority"]
    assert "F-012" in rule["finding"]
    for token in ("EXPECTED_ENGINES", "EngineRunner.run()"):
        assert token in rule["rule"]
    assert rule["promotion_path"]


def test_market_question_matrix_single_owner():
    data = _load()
    entry_ids = {e["id"] for e in data["entries"]}
    owners: dict[str, str] = {}
    for row in data["market_question_matrix"]:
        q = _norm_intent(row["question"])
        owner = row["owner"]
        assert owner in entry_ids, f"owner {owner} not in entries"
        assert q not in owners, f"duplicate owner for question {row['question']!r}"
        owners[q] = owner
        for c in row.get("secondary_consumers") or []:
            assert c in entry_ids or c == "crt", f"unknown consumer {c}"


def test_design_only_rrpatternminer_retrieval_recorded():
    data = _load()
    names = [d["name"] for d in data.get("design_only_concepts", [])]
    assert "RRPatternMiner_historical_evidence_retrieval" in names


def test_stage_fields_and_pipeline_sequence():
    data = _load()
    stages = set(data.get("stages") or [])
    assert "market_understanding" in stages
    assert "opportunity_understanding" in stages
    assert "decision" in stages
    for e in data["entries"]:
        assert e["stage"] in stages
        assert "stage_order" in e
    seq = data["pipeline_sequence"]
    assert seq["stage_1_market_understanding"][0] == "crt"
    assert seq["stage_4_decision"] == ["decision_fusion"]
    assert data["alignment_workflow"]["start_with"] == "crt"


def test_locked_vocabulary_has_score_probability_confidence():
    data = _load()
    vocab = data["locked_vocabulary"]
    assert "probability" in vocab
    assert "score" in vocab
    assert "confidence" in vocab
    assert "commitment" in vocab
    # three-way separation must remain explicit in definitions
    assert "calibrated" in vocab["probability"].lower()
    assert "without probabilistic" in vocab["score"].lower() or "ordinal" in vocab["score"].lower()
    assert "reliability" in vocab["confidence"].lower()
