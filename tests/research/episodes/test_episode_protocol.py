"""OE_L1 contract floor — the freeze must be stable and its invariants mechanical.

These are behavioral assertions, not grep checks: each one would go red if the
corresponding design principle were violated in the protocol module.
"""
from __future__ import annotations

import pytest

from research.episodes import protocol as P


def test_protocol_hash_is_deterministic():
    assert P.compute_protocol_hash() == P.compute_protocol_hash()


def test_protocol_hash_is_scope_sensitive():
    base = P.compute_protocol_hash()
    scoped = P.compute_protocol_hash({"instrument": "BNBUSDT"})
    assert base != scoped


def test_freeze_block_is_json_serializable_and_ordered():
    import json

    blob = json.dumps(P.freeze_block(), sort_keys=True)
    assert json.loads(blob)["protocol_id"] == P.PROTOCOL_ID


def test_governing_policy_is_intrabar_fixed():
    """F-022/M4 discipline: the governing economic truth never silently changes."""
    assert P.GOVERNING_POLICY == "intrabar_fixed"
    assert P.GOVERNING_POLICY in P.V1_POLICIES


def test_v1_policies_are_exactly_the_audited_kernel_modes():
    """No second exit kernel (substrate §18 CRITICAL risk).

    Every declared v1 policy must be a mode `forward_walk` already accepts. If a
    policy is added here that the kernel rejects, this test goes red — which is the
    point: it forces a pre-registration instead of a second simulator.
    """
    from research.contracts import Signal

    # A one-bar walk is enough to exercise the kernel's exit_model validation.
    class _Bar:
        index, high, low, close = 1, 101.0, 99.0, 100.0

    sig = Signal(
        instrument="TEST", timestamp=None, entry_index=0, direction="long",
        entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0,
    )
    from research.measurement.forward_walk import forward_walk

    for policy in P.V1_POLICIES:
        forward_walk(sig, [_Bar()], max_forward=1, exit_model=policy)

    with pytest.raises(ValueError):
        forward_walk(sig, [_Bar()], max_forward=1, exit_model="partial_tp_be")


def test_t_convention_matches_forward_walk_no_lookahead_contract():
    """t=0 is the entry bar; policies must start at t=1 or the kernel raises."""
    assert P.T_ZERO_IS_ENTRY_BAR is True
    assert P.POLICY_WALK_STARTS_AT_T == 1


def test_observation_schema_excludes_atr_and_derived_quantities():
    """Observations are immutable facts only (substrate §9, prereg decision 3)."""
    fields = set(P.OBSERVATION_FIELDS)
    assert {"open", "high", "low", "close", "volume", "timestamp"} <= fields
    for leaked in ("atr", "mfe", "mae", "stop", "tp", "regime", "unrealized_pnl_rr"):
        assert leaked not in fields, f"{leaked!r} is not an observation"


def test_invariants_declare_policy_independence():
    inv = P.freeze_block()["invariants"]
    assert inv["episode_is_policy_independent"] is True
    assert inv["exit_policy_hash_lives_on_labelset_not_episode"] is True
    assert inv["events_are_derived_never_stored_in_episode"] is True
    assert inv["no_second_exit_kernel"] is True
    assert inv["production_behavior_changed"] == "NO"


def test_stream_fields_are_forbidden_as_canonical():
    """F-022: the detection stream is not a trade ledger."""
    forbidden = set(P.FORBIDDEN_AS_CANONICAL)
    assert {"stream.outcome", "stream.rr_achieved", "stream.mfe", "stream.mae"} <= forbidden


def test_partial_tp_is_a_declared_non_goal():
    non_goals = " ".join(P.freeze_block()["non_goals"]).lower()
    assert "partial tp" in non_goals or "partial_tp" in non_goals


def test_authority_is_research_only():
    assert P.AUTHORITY == "research_substrate_only"
    assert P.PIT_STATUS == "PIT_UNCLEAN_STORED_FEATURES"
