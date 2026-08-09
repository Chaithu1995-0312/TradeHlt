"""Golden floor for the ERP market-story library — six-layer binding + determinism + parity anchor.

Satisfies P1.1 "wire synth pack as golden test": every registered story must pass its full six-layer
ontology binding AND the intended-vs-produced critical compare, deterministically, and the anchor
story must reproduce the on-disk erp_4h_m15 engine scores.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.synthetic.ontology import StoryOntology
from research.synthetic.story_builder import build_story
from research.synthetic.story_registry import all_stories, stories_by_id

_ROOT = Path(__file__).resolve().parents[2]
_ONTO = StoryOntology()
_STORIES = all_stories()
_IDS = [s.id for s in _STORIES]


def test_library_nontrivial():
    # 4 active families, ~12 stories in Phase A.
    assert len(_STORIES) >= 12
    assert len({s.family for s in _STORIES}) == 4


@pytest.mark.parametrize("spec", _STORIES, ids=_IDS)
def test_story_passes_all_six_layers_and_critical(spec):
    r = build_story(spec, _ONTO)
    assert r["all_critical_pass"] is True, r["checks"]
    binding = r["ontology_binding"]
    failed = {k: v for k, v in binding["layers"].items() if not v["pass"]}
    assert binding["all_pass"] is True, failed


@pytest.mark.parametrize("spec", _STORIES, ids=_IDS)
def test_story_is_deterministic(spec):
    a = build_story(spec, _ONTO)
    b = build_story(spec, _ONTO)
    assert a["engines_produced"] == b["engines_produced"]
    assert a["engines_intended"] == b["engines_intended"]
    assert a["bars"] == b["bars"]
    assert a["outcome"] == b["outcome"]


def test_outcome_coverage_includes_losers():
    # A golden suite must prove it catches SL_HIT / TIMEOUT, not only TP_HIT.
    outcomes = {build_story(s, _ONTO)["outcome"]["outcome"] for s in _STORIES}
    assert {"TP_HIT", "SL_HIT", "TIMEOUT"} <= outcomes


def test_parity_anchor_reproduces_erp_4h_pack():
    """The anchor story must reproduce the existing data/synthetic/erp_4h_m15 engine scores."""
    pack = _ROOT / "data" / "synthetic" / "erp_4h_m15" / "produced_compare.json"
    if not pack.exists():
        pytest.skip("erp_4h_m15 pack not present")
    erp = json.loads(pack.read_text(encoding="utf-8"))["compare"]["engines_produced_scores"]
    r = build_story(stories_by_id()["liq_sweep_reversal_long"], _ONTO)
    prod = r["engines_produced"]
    # erp uses key "zone_gate"; the library uses "zone" (same soft-zone callable).
    assert prod["crt"] == pytest.approx(erp["crt"], abs=1e-4)
    assert prod["gaussian"] == pytest.approx(erp["gaussian"], abs=1e-4)
    assert prod["zone"] == pytest.approx(erp["zone_gate"], abs=1e-5)
    assert prod["rr"] == pytest.approx(erp["rr"], abs=1e-4)
    # and the geometry: sweep prints 98.50, outcome TP_HIT with R>=2.
    sweep_lows = [bar["low"] for bar in r["bars"] if bar["phase"] == "sweep"]
    assert min(sweep_lows) == pytest.approx(98.50, abs=1e-9)
    assert r["outcome"]["outcome"] == "TP_HIT"
    assert r["outcome"]["rr_achieved"] >= 2.0
