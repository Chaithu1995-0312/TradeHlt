"""CRT variant comparison surface -- behavioral floor for the pure transforms.

Exercises scripts/research/crt_variant_surface.py without a corpus run: the
alignment, the engine-anchored per-state/per-cause attribution, and the
variant-vs-variant stream-identity check are all pure and drivable with
synthetic inputs (E-001: a test that cannot fail is not enforcement).

The load-bearing assertions here are:
  * a variant with no rationale is REFUSED at construction (duplicate-vs-variant
    made mechanical, not a review convention);
  * "same agreement rate, DIFFERENT bars" is distinguishable from "same rate,
    same bars" -- the distinction the whole surface exists to expose;
  * pairwise variant comparison carries NO cause attribution (cause is defined
    only against the engine anchor).

Authority: research/governance only. Grants nothing.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, _REPO / "scripts" / "research" / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def surf():
    return _load("crt_variant_surface")


@pytest.fixture(scope="module")
def cpc():
    return _load("crt_parity_classifier")


def _stream(surf, vid, engine, states, bars=None):
    bars = tuple(range(len(states))) if bars is None else tuple(bars)
    return surf.VariantStream(
        variant_id=vid,
        bar_indices=bars,
        states=tuple(states),
        engine_states=tuple(engine),
        agreement=sum(1 for e, r in zip(engine, states) if e == r),
        total=len(states),
    )


# -- Declaration discipline ---------------------------------------------------
def test_variant_without_rationale_is_refused(surf):
    """A variant that cannot say what the comparison tests is a duplicate."""
    with pytest.raises(ValueError, match="rationale"):
        surf.VariantInput(variant_id="v1", rationale="")
    with pytest.raises(ValueError, match="rationale"):
        surf.VariantInput(variant_id="v1", rationale="   ")


def test_variant_without_id_is_refused(surf):
    with pytest.raises(ValueError, match="variant_id"):
        surf.VariantInput(variant_id="  ", rationale="tests something real")


def test_valid_variant_constructs(surf):
    v = surf.VariantInput(variant_id="base", rationale="baseline, no links enabled")
    assert v.links == frozenset()
    assert v.config_path is None


# -- Alignment ----------------------------------------------------------------
def test_align_drops_out_of_range_source_indices(surf):
    """Mirrors build_confusion: only bars present on BOTH sides survive."""
    engine = ["RANGE", "SWEEP", "RANGE"]
    resolver = ["RANGE", "RANGE", "SWEEP", "RANGE"]
    source = [0, 1, 2, 99]           # 99 is past the engine timeline
    idx, eng, res = surf.align(engine, resolver, source)
    assert idx == [0, 1, 2]
    assert eng == ["RANGE", "SWEEP", "RANGE"]
    assert res == ["RANGE", "RANGE", "SWEEP"]


def test_align_handles_negative_index(surf):
    idx, eng, res = surf.align(["RANGE"], ["RANGE", "SWEEP"], [-1, 0])
    assert idx == [0] and eng == ["RANGE"] and res == ["SWEEP"]


# -- Stream identity: the inert-link criterion --------------------------------
def test_identical_streams_are_reported_identical(surf):
    engine = ["RANGE", "RANGE", "SWEEP", "SWEEP"]
    a = _stream(surf, "a", engine, ["RANGE", "RANGE", "SWEEP", "RANGE"])
    b = _stream(surf, "b", engine, ["RANGE", "RANGE", "SWEEP", "RANGE"])
    out = surf.pairwise_stream_identity([a, b])[("a", "b")]
    assert out["identical"] is True
    assert out["n_differing_bars"] == 0


def test_same_rate_different_bars_is_not_identical(surf):
    """THE distinction the surface exists for: equal agreement counts must not
    be mistaken for equal streams. Two genuinely different models can tie."""
    engine = ["RANGE", "RANGE", "SWEEP", "SWEEP"]
    a = _stream(surf, "a", engine, ["RANGE", "RANGE", "SWEEP", "RANGE"])   # 3/4
    b = _stream(surf, "b", engine, ["RANGE", "RANGE", "RANGE", "SWEEP"])   # 3/4
    out = surf.pairwise_stream_identity([a, b])[("a", "b")]
    assert a.agreement == b.agreement == 3
    assert out["same_agreement_rate"] is True
    assert out["identical"] is False, "equal rate must not imply equal stream"
    assert out["n_differing_bars"] == 2


def test_incomparable_bar_sets_are_flagged_not_silently_zipped(surf):
    engine = ["RANGE", "RANGE"]
    a = _stream(surf, "a", engine, ["RANGE", "SWEEP"], bars=[0, 1])
    b = _stream(surf, "b", engine, ["RANGE", "SWEEP"], bars=[0, 5])
    out = surf.pairwise_stream_identity([a, b])[("a", "b")]
    assert out["comparable"] is False
    assert out["identical"] is False


def test_pairwise_carries_no_cause_attribution(surf):
    """Cause is defined ONLY against the engine anchor. A pairwise entry that
    grew a cause field would be asserting something it cannot know."""
    engine = ["RANGE", "SWEEP"]
    a = _stream(surf, "a", engine, ["RANGE", "RANGE"])
    b = _stream(surf, "b", engine, ["SWEEP", "SWEEP"])
    out = surf.pairwise_stream_identity([a, b])[("a", "b")]
    forbidden = {"cause", "code", "category", "per_state_per_cause", "cell_causes"}
    assert not (set(out) & forbidden), f"pairwise leaked cause attribution: {out}"


# -- Engine-anchored cause attribution ----------------------------------------
def test_causes_are_attributed_per_cell_and_engine_anchored(surf, cpc):
    engine = ["EXECUTION", "EXECUTION", "RANGE"]
    s = _stream(surf, "a", engine, ["RANGE", "RANGE", "RANGE"])
    causes = surf.attribute_causes(s, cpc.MismatchContext())
    # Only the mismatching cell is classified; the agreeing bar is not.
    assert set(causes) == {("EXECUTION", "RANGE")}
    assert causes[("EXECUTION", "RANGE")].code == "B-UNREACHABLE-STATE"


def test_per_state_per_cause_is_a_breakdown_not_a_scalar(surf, cpc):
    engine = ["EXECUTION", "EXECUTION", "RANGE", "RANGE"]
    s = _stream(surf, "a", engine, ["RANGE", "RANGE", "RANGE", "SWEEP"])
    causes = surf.attribute_causes(s, cpc.MismatchContext())
    breakdown = surf.per_state_per_cause(s, causes)
    assert breakdown["EXECUTION"]["B-UNREACHABLE-STATE"] == 2
    assert sum(breakdown["RANGE"].values()) == 1
    assert "EXECUTION" in breakdown and "RANGE" in breakdown


def test_agreeing_bars_contribute_no_cause(surf, cpc):
    engine = ["RANGE", "RANGE"]
    s = _stream(surf, "a", engine, ["RANGE", "RANGE"])
    causes = surf.attribute_causes(s, cpc.MismatchContext())
    assert causes == {}
    assert surf.per_state_per_cause(s, causes) == {}


# -- Surface assembly ---------------------------------------------------------
def test_duplicate_variant_ids_are_refused(surf):
    v = surf.VariantInput(variant_id="dup", rationale="r")
    with pytest.raises(ValueError, match="duplicate variant_id"):
        surf.build_surface(object(), [v, v])
