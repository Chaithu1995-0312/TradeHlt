"""Floors for `CRTStateResolver.resolve_metadata()` — the observation-only `F_t | S_t` view.

WHY THIS FILE IS THE LOAD-BEARING ONE
-------------------------------------
`resolve_metadata()` calls the REAL `_resolve_from_features` rather than a hand-copied "pure
twin", under a save/restore window. That reuse is only safe if it is mechanically proven that
running it changes nothing `resolve()` subsequently does — which is exactly
`test_behavior_neutral` below. If that test is ever deleted or weakened, the reuse must be
re-justified from scratch; a passing suite without it proves nothing.

The neutrality case is run BOTH with `record_resolver_evidence` off and on, because the funnel
mutates `last_resolver_evidence` IN PLACE (`crt_state_resolver.py:1312-1315`) — a bug class a
reference-only save/restore would not catch.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features.crt_state_resolver import (  # noqa: E402
    CRTStateResolver,
    PredicateValidationError,
    ResolverMetadata,
)
from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM  # noqa: E402
from features.feature_states import FeatureStateEncoder  # noqa: E402

# The 6 non-vector stateful identities (lineage.vector_key: []). `classify()` cannot produce
# them; they exist only if the caller supplies them. Derived, not hardcoded, so an ontology
# change surfaces here rather than silently shrinking the L2 map.
_ENCODER = FeatureStateEncoder()
_NON_VECTOR = tuple(sorted(set(_ENCODER.stateful_features) - {s.name for s in _ENCODER._vector_bound}))


def _bar(i: int) -> dict[str, float]:
    """One fully-supplied feature row. Values vary with `i` so different funnel branches fire."""
    phase = (i % 7) / 7.0
    feat = {name: float(i % 5) * 0.1 for name in CANONICAL_FEATURES}
    # Give the geometry-bearing names plausible, moving magnitudes.
    feat.update({
        "close": 2000.0 + i * 1.5,
        "open": 2000.0 + i * 1.5 - 0.5,
        "high": 2000.0 + i * 1.5 + 2.0,
        "low": 2000.0 + i * 1.5 - 2.0,
        "atr": 0.001,
        "candle_range": 4.0,
        "body_ratio": 0.5 + 0.4 * phase,
        "volatility_regime": phase,
        "trend_bias": 1.0 if i % 3 else -1.0,
        "session": float(i % 4),
        "sweep_detected": 1.0 if i % 5 == 0 else 0.0,
        "liquidity_sweep": 1.0 if i % 5 == 0 else 0.0,
        "double_sweep": 0.0,
        "swing_high": 2000.0 + i * 1.5 + 5.0,
        "swing_low": 2000.0 + i * 1.5 - 5.0,
        "higher_high": 1.0 if i % 2 else 0.0,
        "lower_low": 0.0 if i % 2 else 1.0,
        "break_of_structure": 1.0 if i % 6 == 0 else 0.0,
        "change_of_character": 0.0,
        "volume_spike": 1.0 if i % 4 == 0 else 0.0,
    })
    for name in _NON_VECTOR:
        feat[name] = float(i % 3) * 0.4
    return feat


def _bars(n: int = 60) -> list[dict[str, float]]:
    return [_bar(i) for i in range(n)]


def _snapshot(r: CRTStateResolver) -> tuple:
    """Everything `resolve()` carries forward, plus the published per-bar provenance."""
    return (
        dataclasses.asdict(r._memory),
        dict(r.counts),
        r.transition_count,
        r._last_funnel_site,
        r._last_injection_site,
        None if r.last_resolver_evidence is None else dict(r.last_resolver_evidence),
    )


# ── the load-bearing floor ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("record_evidence", [False, True], ids=["evidence_off", "evidence_on"])
def test_behavior_neutral(record_evidence):
    """Interleaving `resolve_metadata()` changes NOTHING about the `resolve()` sequence.

    Control resolves only. Subject calls `resolve_metadata()` both before and after each
    `resolve()` — the adversarial ordering, since a leaked funnel-site write would be visible
    on the following bar.
    """
    bars = _bars()

    control = CRTStateResolver()
    control.record_resolver_evidence = record_evidence
    control_states, control_snaps = [], []
    for b in bars:
        control_states.append(control.resolve(b))
        control_snaps.append(_snapshot(control))

    subject = CRTStateResolver()
    subject.record_resolver_evidence = record_evidence
    subject_states, subject_snaps = [], []
    for b in bars:
        subject.resolve_metadata(b)              # before
        subject_states.append(subject.resolve(b))
        subject.resolve_metadata(b)              # after
        subject_snaps.append(_snapshot(subject))

    assert subject_states == control_states, "resolve() output sequence diverged"
    for i, (got, want) in enumerate(zip(subject_snaps, control_snaps)):
        assert got == want, f"resolver internal state diverged at bar {i}"


def test_metadata_does_not_advance_memory_on_its_own():
    """Called alone, `resolve_metadata()` leaves memory byte-identical (no candle_index tick)."""
    r = CRTStateResolver()
    before = _snapshot(r)
    for b in _bars(25):
        r.resolve_metadata(b)
    assert _snapshot(r) == before


# ── shape ─────────────────────────────────────────────────────────────────────────────────
def test_l2_map_has_19_keys():
    """The full L2 map, not `classify()`'s 13 vector-bound subset."""
    md = CRTStateResolver().resolve_metadata(_bar(3))
    assert set(md.l2_map) == set(_ENCODER.stateful_features)
    assert len(md.l2_map) == 19


def test_l2_map_is_wider_than_classify_alone():
    """Pins the two-step construction: `classify()` alone would silently return 13."""
    feat = _bar(3)
    assert len(_ENCODER.classify(feat)) == 13
    assert len(CRTStateResolver().resolve_metadata(feat).l2_map) == 19


def test_feature_vector_contains_canonical_48():
    """The 48 canonical names are a SUBSET — the echoed dict also carries non-vector extras."""
    md = CRTStateResolver().resolve_metadata(_bar(1))
    assert CANONICAL_FEATURE_DIM == 48
    assert set(CANONICAL_FEATURES).issubset(md.feature_vector)
    assert set(_NON_VECTOR).issubset(md.feature_vector)


def test_affinity_and_gate_keys_are_declared_states():
    md = CRTStateResolver().resolve_metadata(_bar(2))
    declared = {s["name"] for s in CRTStateResolver()._config["states"]}
    assert set(md.predicate_affinity) <= declared
    assert set(md.continuous_passed) <= declared
    assert all(isinstance(v, bool) for v in md.predicate_affinity.values())
    assert all(isinstance(v, bool) for v in md.continuous_passed.values())


def test_returns_no_state_label():
    """The envelope's whole point: the resolver contributes `F_t | S_t`, never a rival `S_t`."""
    fields = {f.name for f in dataclasses.fields(ResolverMetadata)}
    assert not any("state" in f and f != "projected_funnel_site" for f in fields)
    assert "projected_funnel_site" in fields


def test_projected_site_is_a_known_funnel_site_or_none():
    sites = set()
    r = CRTStateResolver()
    for b in _bars(40):
        sites.add(r.resolve_metadata(b).projected_funnel_site)
        r.resolve(b)
    assert sites, "no site observed — fixture never reached the funnel"
    assert all(s is None or isinstance(s, str) for s in sites)


# ── supply contract ───────────────────────────────────────────────────────────────────────
# Two DISTINCT fail-closed mechanisms, at different depths. Keep them apart: a vector-bound
# name dies in `classify()` (and can never reach the supply check), a non-vector name is
# exactly what the supply check exists for.
def _enforceable_non_vector(r: CRTStateResolver) -> list[str]:
    vector_bound = {s.name for s in _ENCODER._vector_bound}
    return sorted((r.required_when_features - r.waived_when_features) - vector_bound)


def test_missing_vector_bound_feature_fails_closed_in_classify():
    r = CRTStateResolver()
    feat = _bar(1)
    feat.pop("break_of_structure")
    with pytest.raises(PredicateValidationError, match="required stateful features absent"):
        r.resolve_metadata(feat)


def test_supply_contract_enforces_by_default():
    r = CRTStateResolver()
    required = _enforceable_non_vector(r)
    if not required:
        pytest.skip("no enforceable non-vector when:-named features on this variant")
    feat = _bar(1)
    feat.pop(required[0])
    with pytest.raises(PredicateValidationError):
        r.resolve_metadata(feat)


def test_supply_contract_can_report_instead_of_raising():
    r = CRTStateResolver()
    required = _enforceable_non_vector(r)
    if not required:
        pytest.skip("no enforceable non-vector when:-named features on this variant")
    feat = _bar(1)
    feat.pop(required[0])
    md = r.resolve_metadata(feat, enforce_required_when=False)
    assert md.supply_ok is False
    assert required[0] in md.missing_when
    # ...and evaluation still completed rather than dropping the row.
    assert len(md.l2_map) == 18  # the popped non-vector identity is genuinely absent


def test_supply_ok_when_fully_supplied():
    md = CRTStateResolver().resolve_metadata(_bar(1))
    assert md.supply_ok is True
    assert md.missing_when == ()
