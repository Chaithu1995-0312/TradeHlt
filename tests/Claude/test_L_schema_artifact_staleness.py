"""L. Schema vs model artifact — which failure is open and which is closed (F-076).

Semantic invariant: ZoneGate is the only LIVE hard gate (F-041), and every model
family is now trained on a <=39-dim schema against a 48-dim vector (F-076). The
resolution is fail-CLOSED at the vector: silent truncation was removed
2026-07-22, the registry's own `feature_order` is authoritative BY NAME, and a
name it asks for that the schema no longer emits raises rather than being
quietly aliased away. Registry-schema errors, by contrast, deliberately fail
OPEN to a neutral 0.5 — the same gate carries two opposite failure policies, and
that asymmetry is the contract, not an accident.

Ordinary tests pin zone scoring and registry migration in isolation. They do not
put a deliberately stale feature_order through the live entry point to prove a
one-generation-old artifact cannot produce a PASS, and they do not assert the
two failure policies against each other.
"""
from __future__ import annotations

import pytest

from engines.zone_gate_engine import CANONICAL_KEYS, _extract_vector, run_zone_gate_engine
from features.feature_schema import (
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURE_ORDER,
    SCHEMA_V2_FEATURE_DIM,
    SCHEMA_V3_ALIASES,
    SCHEMA_V3_FEATURE_DIM,
    SCHEMA_V4_FEATURE_DIM,
)


def _canonical_features() -> dict:
    """A complete, well-formed 48-key feature dict. Values are irrelevant here."""
    return {k: 1.0 for k in CANONICAL_KEYS}


def _stale_order(retired_name: str) -> list:
    """A trained feature_order from before the rename that retired `retired_name`."""
    return [retired_name] + list(CANONICAL_FEATURE_ORDER[: SCHEMA_V4_FEATURE_DIM - 1])


def _always_confident(vector: list) -> float:
    """A model that would clear any threshold — so a PASS can only come from the gate."""
    return 0.99


@pytest.mark.parametrize("retired", sorted(SCHEMA_V3_ALIASES))
def test_retired_schema_name_in_a_trained_order_raises(retired: str):
    """A feature_order naming a column the schema no longer emits is an error.

    Source: zone_gate_engine._extract_vector — KeyError on a name absent from the
    feature dict is re-raised as ValueError, demanding remap or retrain.
    Failure mode: the missing column is defaulted to 0.0 and the stale model scores
    a vector whose mu/sigma no longer line up with any of its inputs.
    """
    assert retired not in CANONICAL_FEATURE_ORDER
    with pytest.raises(ValueError, match=retired):
        _extract_vector(_canonical_features(), _stale_order(retired))


def test_a_stale_registry_cannot_produce_a_pass():
    """Through the live entry point the stale artifact BLOCKS, it does not score.

    Source: run_zone_gate_engine step 3 converts the _extract_vector ValueError to
    passed=False / valid=False (fail-closed), never to a pass.
    Failure mode: the one live hard gate returns passed=True off a mis-shaped
    vector, so F-076's "all six model families are stale" becomes a silent
    permissive gate instead of a visible block.
    """
    result = run_zone_gate_engine(
        _canonical_features(),
        _always_confident,
        threshold=0.5,
        feature_order=_stale_order("macd_hist"),
    )
    assert result["passed"] is False
    assert result["valid"] is False
    assert result["score"] == 0.0
    assert result["vector"] == []


@pytest.mark.parametrize("retired", sorted(SCHEMA_V3_ALIASES))
def test_v3_aliases_are_migration_vocabulary_not_a_scoring_fallback(retired: str):
    """The alias map exists and is deliberately NOT consulted while scoring.

    Source: feature_schema.SCHEMA_V3_ALIASES (wick_size to candle_range, macd_hist
    to macd_hist_z) vs _extract_vector, which resolves names against the feature
    dict only.
    Failure mode: the gate auto-substitutes the renamed column, silently feeding a
    trained model a different quantity under its old name — exactly the
    one-name-two-values defect the v4.0 macd split was created to end.
    Why ordinary tests miss it: the migrator is tested where it is used, so nothing
    asserts that the scoring path declines to use it.
    """
    successor = SCHEMA_V3_ALIASES[retired]
    assert successor in CANONICAL_FEATURE_ORDER
    features = _canonical_features()
    assert successor in features and retired not in features
    with pytest.raises(ValueError):
        _extract_vector(features, [retired])


def test_feature_order_is_name_authoritative_not_positional():
    """Reordering the trained order reorders the vector — alignment is by name.

    Source: _extract_vector docstring — when supplied, feature_order is
    AUTHORITATIVE and the vector is assembled by NAME, so a schema that reorders or
    extends CANONICAL_FEATURE_ORDER cannot silently misalign the model's mu/sigma.
    Failure mode: the vector is built in ambient canonical order regardless of the
    registry, so a model trained on a different ordering is scored transposed.
    """
    positional = {name: float(i) for i, name in enumerate(CANONICAL_KEYS)}
    ambient = _extract_vector(positional)
    by_name = _extract_vector(positional, list(reversed(CANONICAL_KEYS)))
    assert ambient == [float(i) for i in range(CANONICAL_FEATURE_DIM)]
    assert by_name == list(reversed(ambient))


def test_a_shorter_trained_order_is_aligned_by_name_not_truncated():
    """A 39-dim artifact reads its own 39 names out of the 48-key dict, correctly.

    Source: _extract_vector builds keys from feature_order, so the vector length is
    the ARTIFACT's dimension and the length guard compares against that.
    Failure mode: "stale artifact" is confused with "broken artifact" and a
    correctly-aligned older model is blocked, or a 48-key dict is trimmed to its
    first 39 positions — the truncation branch removed in 2026-07-22.
    Why ordinary tests miss it: this is the case that must NOT raise, so it is
    invisible to any suite that only exercises the error paths.
    """
    older = list(CANONICAL_FEATURE_ORDER[:SCHEMA_V4_FEATURE_DIM])
    positional = {name: float(i) for i, name in enumerate(CANONICAL_KEYS)}
    vector = _extract_vector(positional, older)
    assert len(vector) == SCHEMA_V4_FEATURE_DIM
    assert vector == [float(i) for i in range(SCHEMA_V4_FEATURE_DIM)]


def test_registry_errors_fail_open_while_vector_errors_fail_closed():
    """One gate, two opposite policies — asserted side by side so neither drifts.

    Source: zone_gate_engine module docstring (strict schema validation but
    fail-open on registry errors); step 2 returns neutral 0.5 with passed=True,
    step 3 returns 0.0 with passed=False.
    Failure mode: the fail-open branch is widened to cover extraction errors too, so
    a mis-shaped vector reaches production as a neutral PASS.
    """
    features = _canonical_features()
    open_path = run_zone_gate_engine(
        features, _always_confident, zone_registry={"not": "a registry"}
    )
    closed_path = run_zone_gate_engine(
        features, _always_confident, feature_order=_stale_order("wick_size")
    )
    assert (open_path["passed"], open_path["score"], open_path["valid"]) == (True, 0.5, True)
    assert (closed_path["passed"], closed_path["score"], closed_path["valid"]) == (False, 0.0, False)


@pytest.mark.parametrize(
    "label,dim",
    [
        ("v2.0", SCHEMA_V2_FEATURE_DIM),
        ("v3.0", SCHEMA_V3_FEATURE_DIM),
        ("v4.0", SCHEMA_V4_FEATURE_DIM),
    ],
)
def test_every_historical_schema_dim_is_distinct_from_the_live_one(label: str, dim: int):
    """35 / 38 / 39 are all strictly below the live 48 — no generation aliases another.

    Source: feature_schema.SCHEMA_V2/V3/V4_FEATURE_DIM vs CANONICAL_FEATURE_DIM
    Failure mode: a dimension check that only tests inequality against one past
    generation lets an artifact from another generation through.
    """
    assert dim < CANONICAL_FEATURE_DIM
    assert dim != CANONICAL_FEATURE_DIM
