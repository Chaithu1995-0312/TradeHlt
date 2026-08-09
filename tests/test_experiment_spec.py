"""ExperimentSpec — the reusable execution contract (Research Runtime Step 1c).

Introduced BEFORE generalizing the XAUUSD validation script so Step 2 consumes a
contract instead of becoming driver #195. The guards below encode the specific
failures the spec exists to prevent: a second config system, corpus pins buried in
Python, and research artifacts that read as authoritative.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from research.experiment_spec import (  # noqa: E402
    MODE_ALL,
    MODE_EXPLICIT,
    CorpusSpec,
    ExperimentSpec,
    ExperimentSpecError,
    ModelSelectionSpec,
    OutputSpec,
)

_EXAMPLE = _REPO / "configs" / "research" / "experiments" / "xauusd_implementation_validation.json"


def _spec(**over) -> ExperimentSpec:
    base = dict(
        experiment_id="t",
        kind="benchmark",
        corpus=(CorpusSpec(path="data/x.csv", instrument="XAUUSD", sha256="ab", rows=10),),
        model_selection=ModelSelectionSpec(mode=MODE_ALL),
        output=OutputSpec(out_dir="results/t", artifact_name="t"),
    )
    base.update(over)
    return ExperimentSpec(**base)


# ── fail-closed construction ─────────────────────────────────────────────────
def test_authority_is_frozen_at_none():
    with pytest.raises(ExperimentSpecError):
        _spec(authority="PRODUCTION")


def test_unknown_kind_rejected():
    with pytest.raises(ExperimentSpecError):
        _spec(kind="vibes")


def test_unknown_selection_mode_rejected():
    with pytest.raises(ExperimentSpecError):
        _spec(model_selection=ModelSelectionSpec(mode="whatever"))


def test_explicit_mode_requires_versions():
    with pytest.raises(ExperimentSpecError):
        _spec(model_selection=ModelSelectionSpec(mode=MODE_EXPLICIT))


def test_corpus_is_required():
    with pytest.raises(ExperimentSpecError):
        _spec(corpus=())


def test_experiment_id_must_be_non_empty():
    with pytest.raises(ExperimentSpecError):
        _spec(experiment_id="   ")


# ── deterministic identity ───────────────────────────────────────────────────
def test_sha256_is_stable_across_construction():
    assert _spec().sha256() == _spec().sha256()


def test_sha256_changes_with_the_corpus_pin():
    a = _spec()
    b = _spec(corpus=(CorpusSpec(path="data/x.csv", instrument="XAUUSD", sha256="cd", rows=10),))
    assert a.sha256() != b.sha256()


def test_notes_are_not_part_of_identity():
    """Prose must not change an experiment's provenance hash."""
    assert _spec().sha256() == _spec(notes="a long explanation").sha256()


def test_spec_is_immutable():
    s = _spec()
    with pytest.raises(Exception):
        s.experiment_id = "mutated"  # type: ignore[misc]


# ── references, never redefines ──────────────────────────────────────────────
def test_spec_points_at_configs_rather_than_inlining_params():
    """A spec that carried engine params would become a second config system."""
    canonical = _spec(
        measurement_config="configs/research/research_config.json",
        production_config_ref="v2_multi_2026_04",
    ).canonical()
    blob = json.dumps(canonical)
    for leaked in ("sl_atr_mult", "round_trip_bps", "expansion_atr_min_distance", "warmup"):
        assert leaked not in blob, f"spec inlined a measurement/engine param: {leaked}"
    assert canonical["measurement_config"] == "configs/research/research_config.json"
    assert canonical["production_config_ref"] == "v2_multi_2026_04"


def test_authority_is_carried_into_canonical_form():
    assert _spec().canonical()["authority"] == "NONE"


# ── the example spec ─────────────────────────────────────────────────────────
def test_example_spec_file_loads():
    assert _EXAMPLE.exists(), f"missing example spec {_EXAMPLE}"
    spec = ExperimentSpec.from_file(_EXAMPLE)
    assert spec.kind == "implementation_validation"
    assert spec.sha256()


def test_example_spec_carries_the_corpus_pin_as_data():
    """The pin the old driver hardcoded in Python must now live in the spec."""
    spec = ExperimentSpec.from_file(_EXAMPLE)
    (corpus,) = spec.corpus
    assert corpus.instrument == "XAUUSD"
    assert corpus.sha256 == "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
    assert corpus.rows == 47275


def test_example_spec_keeps_dangling_artifacts_as_results():
    spec = ExperimentSpec.from_file(_EXAMPLE)
    assert spec.model_selection.include_missing_artifacts is True


def test_from_dict_rejects_a_malformed_corpus():
    with pytest.raises(ExperimentSpecError):
        ExperimentSpec.from_dict({"experiment_id": "x", "kind": "benchmark", "corpus": [{}]})


def test_from_dict_requires_output_fields():
    with pytest.raises(ExperimentSpecError):
        ExperimentSpec.from_dict(
            {
                "experiment_id": "x",
                "kind": "benchmark",
                "corpus": [{"path": "a.csv", "instrument": "X"}],
                "output": {"out_dir": "results/x"},
            }
        )
