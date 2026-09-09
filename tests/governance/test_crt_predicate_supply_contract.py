"""CRT resolver predicate supply contract -- behavioral floor.

Two things had no test at all before this file:

  1. ``_validate_predicates`` -- the construction-time allow-list enforcing
     `when:` names subset of `feature_states:` subset of ontology stateful
     features. Real enforcement, zero coverage.

  2. The SUPPLY contract. ``FeatureStateEncoder.classify`` already fails closed
     for every VECTOR-BOUND stateful feature, and its docstring names
     rsi_state / displacement_flag / retest_flag as deliberately excluded
     ("this method never invents them from their inputs"). But nothing enforced
     that callers then supply them: absent, ``_predicates_match`` returned False
     silently -- indistinguishable from "present but did not match". Ten of the
     thirteen `when:`-named features were strict; three were not. This closes
     that asymmetry.

The ratchet below is deliberately NOT the naive invariant
``set(resolver_vocab) == set(features_with_vector_key)``, which is false in both
directions: volatility_regime and volume_spike are declared-but-never-named, and
change_of_character (FM-083) is vector-bound but legitimately unnamed.

Authority: research/governance only. Grants nothing.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.crt_state_resolver import (  # noqa: E402
    ConfigLoadError,
    CRTStateResolver,
    PredicateValidationError,
)
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

STATES_YAML = ROOT / "configs" / "formulas" / "market_crt_states.yaml"

# Features named by a `when:` block that are NOT vector-bound. Each entry states
# the FM id, the producing call site, and who must inject it. SHRINK-ONLY: an
# entry that becomes vector-bound is stale and must be deleted, and a NEW
# non-vector `when:` name must be adjudicated here rather than defaulting.
_NON_VECTOR_SUPPLY_CONTRACT: dict[str, str] = {
    "retest_flag": (
        "FM-061, lineage.vector_key: []. Emitted by FeaturePipeline as a "
        "non-canonical column (feature_pipeline.py:1030). Named by "
        "EXECUTION/RETEST/RANGE. Every resolve() caller must inject it."
    ),
    "displacement_flag": (
        "FM-069, lineage.vector_key: []. Emitted by FeaturePipeline as a "
        "non-canonical column (feature_pipeline.py:1009-1013). Named by "
        "EXPANSION/DISPLACEMENT/SWEEP/RANGE. Every resolve() caller must inject it."
    ),
    "rsi_state": (
        "FM-068, lineage.vector_key: []. Emitted by FeaturePipeline as a "
        "non-canonical column (feature_pipeline.py:596-599). Named by EXECUTION "
        "only. classify() deliberately never derives it from rsi_14 -- that "
        "would be re-derivation."
    ),
}


def _states_cfg():
    return yaml.safe_load(STATES_YAML.read_text(encoding="utf-8"))


def _write(tmp_path, cfg, name="states.yaml"):
    out = tmp_path / name
    out.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return out


def _state(cfg, name):
    for s in cfg["states"]:
        if s["name"] == name:
            return s
    raise KeyError(name)


def _full_features(**overrides):
    """A complete, honest input: canonical vector PLUS the three non-vector
    `when:`-named features a real pipeline frame carries."""
    fv = {n: 0.0 for n in CANONICAL_FEATURES}
    fv.update({"retest_flag": 0.0, "displacement_flag": 0.0, "rsi_state": 0.0})
    fv.update({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
               "atr": 0.001, "body_ratio": 0.5, "candle_range": 2.0})
    fv.update(overrides)
    return fv


# == 1. _validate_predicates: the four negative branches =======================
def test_shipped_config_constructs_clean():
    """Positive control: the negative tests below must be failing for their
    stated reason, not because construction is broken generally."""
    assert CRTStateResolver() is not None


def test_feature_states_naming_a_non_stateful_feature_raises(tmp_path):
    cfg = _states_cfg()
    cfg["feature_states"]["close"] = ["Whatever"]     # continuous, not stateful
    with pytest.raises(PredicateValidationError, match="not a declared stateful feature"):
        CRTStateResolver(config_path=_write(tmp_path, cfg))


def test_feature_states_naming_an_unknown_ontology_state_raises(tmp_path):
    cfg = _states_cfg()
    cfg["feature_states"]["retest_flag"] = ["NoRetest", "NotAnOntologyState"]
    with pytest.raises(PredicateValidationError, match="not found in ontology"):
        CRTStateResolver(config_path=_write(tmp_path, cfg))


def test_when_naming_a_feature_outside_the_vocabulary_raises(tmp_path):
    cfg = _states_cfg()
    _state(cfg, "RANGE")["when"]["change_of_character"] = ["NoCHoCH"]
    with pytest.raises(PredicateValidationError, match="not in feature_states block"):
        CRTStateResolver(config_path=_write(tmp_path, cfg))


def test_when_naming_an_invalid_state_for_that_feature_raises(tmp_path):
    cfg = _states_cfg()
    _state(cfg, "RANGE")["when"]["retest_flag"] = ["RetestActive", "Bogus"]
    with pytest.raises(PredicateValidationError, match="not valid for feature"):
        CRTStateResolver(config_path=_write(tmp_path, cfg))


# == 2. Supply-contract ratchet (two-sided, shrink-only) =======================
def _non_vector_when_features(r: CRTStateResolver) -> set[str]:
    return set(r.required_when_features) - set(r._encoder.vector_bound_features)


def test_every_non_vector_when_feature_is_adjudicated():
    """A NEW non-vector `when:` name must be declared here, not defaulted."""
    undeclared = sorted(
        _non_vector_when_features(CRTStateResolver()) - set(_NON_VECTOR_SUPPLY_CONTRACT)
    )
    assert not undeclared, (
        f"`when:`-named features with no vector slot and no declared supply "
        f"contract: {undeclared}. Every resolve() caller must inject these -- "
        "record who, and why, before shipping the predicate."
    )


def test_no_stale_supply_contract_entries():
    """An entry that became vector-bound is dead weight -- shrink-only."""
    stale = sorted(set(_NON_VECTOR_SUPPLY_CONTRACT) - _non_vector_when_features(CRTStateResolver()))
    assert not stale, (
        f"_NON_VECTOR_SUPPLY_CONTRACT names {stale}, which are no longer "
        "non-vector `when:` features. Delete the entry."
    )


@pytest.mark.parametrize("name", sorted(_NON_VECTOR_SUPPLY_CONTRACT))
def test_every_contract_entry_carries_a_substantive_reason(name):
    reason = _NON_VECTOR_SUPPLY_CONTRACT[name]
    assert len(reason.strip()) > 60, f"{name}: reason must name FM id, producer, and requiring states"
    assert "FM-0" in reason, f"{name}: reason must cite the ontology identity"


def test_the_naive_invariant_is_false_in_both_directions():
    """Pins WHY the obvious `resolver_vocab == vector_keys` test is not written:
    it would fail on legitimate cases in both directions. If this ever stops
    being true, the simpler invariant becomes available and should replace the
    ratchet above."""
    r = CRTStateResolver()
    vocab = set(r._config["feature_states"])
    vector_bound = set(r._encoder.vector_bound_features)
    # Declared in the vocabulary, named by no predicate (dead permission).
    assert {"volatility_regime", "volume_spike"} <= vocab - set(r.required_when_features)
    # Vector-bound and stateful, but legitimately absent from the vocabulary.
    assert "change_of_character" in vector_bound - vocab


# == 3. The strict supply check ================================================
def test_vector_only_caller_now_raises_naming_all_three():
    """The defect this closes: a CANONICAL_FEATURES-only dict silently produced
    a degraded run. It must now fail on bar 0."""
    r = CRTStateResolver()
    with pytest.raises(PredicateValidationError) as ei:
        r.resolve({n: 0.0 for n in CANONICAL_FEATURES})
    msg = str(ei.value)
    for name in ("retest_flag", "displacement_flag", "rsi_state"):
        assert name in msg, f"{name} missing from the error"


def test_error_names_the_requiring_states_and_the_producer():
    r = CRTStateResolver()
    feats = _full_features()
    del feats["rsi_state"]
    with pytest.raises(PredicateValidationError) as ei:
        r.resolve(feats)
    msg = str(ei.value)
    assert "rsi_state" in msg
    assert "EXECUTION" in msg, "must say WHICH state requires it"
    assert "feature_pipeline.py:598" in msg, "must say WHO produces it"
    assert "retest_flag" not in msg, "must report only what is actually missing"


def test_complete_input_resolves_normally():
    """The green half: the check must not fire on an honest caller."""
    r = CRTStateResolver()
    assert r.resolve(_full_features()) in set(r._config["feature_states"]) | {
        s["name"] for s in r._config["states"]
    }


def test_out_of_domain_value_is_a_value_failure_not_a_supply_failure():
    """A garbage VALUE must not be reported as a missing feature. classify_value
    returns an X_UNMAPPED marker, which fails the predicate normally -- the two
    failure modes must stay distinguishable."""
    r = CRTStateResolver()
    state = r.resolve(_full_features(rsi_state=0.5))   # 0.5 maps to no state
    assert isinstance(state, str) and state


# == 4. Escape hatch ===========================================================
def test_waiver_restores_the_previous_tolerance():
    r = CRTStateResolver(allow_missing_when_features=["rsi_state"])
    feats = _full_features()
    del feats["rsi_state"]
    assert isinstance(r.resolve(feats), str)          # no raise
    assert r.waived_when_features == frozenset({"rsi_state"})


def test_waiver_is_narrow_not_a_blanket():
    """Waiving one feature must not tolerate the others going missing."""
    r = CRTStateResolver(allow_missing_when_features=["rsi_state"])
    feats = _full_features()
    del feats["rsi_state"]
    del feats["retest_flag"]
    with pytest.raises(PredicateValidationError, match="retest_flag"):
        r.resolve(feats)


def test_stale_waiver_raises_at_construction():
    """The anti-parking-lot ratchet: waiving something that is not `when:`-named
    is refused, so a waiver cannot outlive the predicate it was written for."""
    with pytest.raises(ConfigLoadError, match="not `when:`-named"):
        CRTStateResolver(allow_missing_when_features=["change_of_character"])


def test_waived_feature_still_fails_its_predicate_rather_than_defaulting():
    """A waiver restores the OLD behaviour for that name and nothing more: the
    feature does not acquire a default value, and its predicate still fails."""
    r = CRTStateResolver(allow_missing_when_features=["rsi_state"])
    assert r._predicates_match({"rsi_state": ["NeutralMomentum"]}, {}) is False


def test_no_waiver_is_the_default():
    assert CRTStateResolver().waived_when_features == frozenset()


# == 5. Red/green proof ========================================================
def test_red_green_guard_proof():
    """Emulate REMOVING the supply check and prove the silent degradation
    returns -- i.e. the guard is load-bearing, not decorative.

    Unguarded, a vector-only caller produces a state with no error at all; the
    RANGE `when:` block simply never matches on its retest_flag/
    displacement_flag clauses and the run looks clean.
    """
    r = CRTStateResolver()
    vector_only = {n: 0.0 for n in CANONICAL_FEATURES}

    # Guarded: raises.
    with pytest.raises(PredicateValidationError):
        r.resolve(dict(vector_only))

    # Unguarded equivalent: waive exactly what the check would have caught.
    lax = CRTStateResolver(
        allow_missing_when_features=["retest_flag", "displacement_flag", "rsi_state"]
    )
    silent = lax.resolve(dict(vector_only))
    assert isinstance(silent, str) and silent, (
        "without the guard a vector-only caller resolves silently -- this is the "
        "degradation the check exists to make visible"
    )
