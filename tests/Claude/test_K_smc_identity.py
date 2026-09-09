"""K. SMC primitives are FEATURES, not STATES (F-076).

Semantic invariant: the 9 SMC primitives added by
CH-htfcrt-parent-candle-smc-v1 (order block, FVG, breaker, mitigation block,
PDH/PDL, EQH/EQL, change-of-character) grew the canonical vector 39 -> 48
(schema v4.0 -> v5.0). They are vector slots with an index. They are not
CRTState members, they do not appear in VALID_TRANSITIONS, and they cannot
open a trade — TRADE_OPENED still requires the M15 execution machine to
reach CRTState.EXECUTION.

Ordinary tests pin the DETECTORS (tests/test_smc_primitives.py walks order-block
formation, FVG fill, no-lookahead, CHoCH bounds). They do not ask whether an SMC
name can be mistaken for a state, which is the F-077-class collision one layer
down from the HTFState / DISTRIBUTION_C3 collision Grok family I already pins.
"""
from __future__ import annotations

import pytest

from config_layer.state_identity import (
    CRTState,
    EXECUTION_TIMEFRAME_STATES,
    VALID_TRANSITIONS,
)
from features.feature_schema import (
    CANONICAL_FEATURES,
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURE_ORDER,
    FEATURE_INDEX_MAP,
    SCHEMA_V4_FEATURE_DIM,
    SCHEMA_VERSION,
)

# The v5.0 tail, in schema order. Written out rather than sliced so that a
# reordering of CANONICAL_FEATURE_ORDER is a test failure, not a silent re-slice.
SMC_PRIMITIVES = (
    "order_block_distance",
    "fvg_distance",
    "breaker_distance",
    "mitigation_block_distance",
    "pdh_distance",
    "pdl_distance",
    "eqh_distance",
    "eql_distance",
    "change_of_character",
)


def test_schema_is_48_dim_v5_with_a_nine_slot_smc_tail():
    """The vector grew by exactly the 9 SMC primitives, appended.

    Source: feature_schema.CANONICAL_FEATURE_DIM (48), SCHEMA_VERSION ("5.0"),
    SCHEMA_V4_FEATURE_DIM (39)
    Failure mode: a tenth primitive is appended without a schema-version bump, so
    every consumer that trusts SCHEMA_VERSION scores a vector it was not trained on.
    """
    assert CANONICAL_FEATURE_DIM == 48
    assert SCHEMA_VERSION == "5.0"
    assert SCHEMA_V4_FEATURE_DIM == 39
    assert CANONICAL_FEATURE_DIM - SCHEMA_V4_FEATURE_DIM == len(SMC_PRIMITIVES)
    assert tuple(CANONICAL_FEATURE_ORDER[SCHEMA_V4_FEATURE_DIM:]) == SMC_PRIMITIVES


@pytest.mark.parametrize("name", SMC_PRIMITIVES)
def test_no_smc_feature_name_is_a_crt_state(name: str):
    """An SMC column name never resolves to a CRTState member.

    Source: features.feature_schema.CANONICAL_FEATURE_ORDER vs
    state_identity.CRTState.__members__
    Failure mode: a report or trace prints 'change_of_character' in a state column
    and a downstream reader treats it as a 13th CRT state.
    """
    assert name.upper() not in CRTState.__members__
    assert name not in {s.name for s in CRTState}


@pytest.mark.parametrize("state", list(CRTState))
def test_no_crt_state_name_is_a_canonical_feature(state: CRTState):
    """The collision is symmetric: no state name is a vector slot either.

    Source: CRTState (12 members) vs CANONICAL_FEATURE_ORDER (48 names)
    Failure mode: a feature named after a state makes 'which axis is this' a guess,
    the same ambiguity F-077 raised for HTFState.DISTRIBUTION vs DISTRIBUTION_C3.
    """
    assert state.name.lower() not in CANONICAL_FEATURE_ORDER
    assert state.name not in CANONICAL_FEATURE_ORDER


@pytest.mark.parametrize("name", SMC_PRIMITIVES)
def test_smc_primitives_occupy_the_declared_tail_index(name: str):
    """Each primitive has a fixed index in 39..47 — position is part of the contract.

    Source: feature_schema.FEATURE_INDEX_MAP
    Failure mode: an SMC slot is inserted mid-vector instead of appended, shifting
    every downstream mu/sigma without changing the dimension count.
    """
    idx = FEATURE_INDEX_MAP[name]
    assert SCHEMA_V4_FEATURE_DIM <= idx < CANONICAL_FEATURE_DIM
    assert CANONICAL_FEATURE_ORDER[idx] == name


def test_smc_names_are_absent_from_the_transition_graph():
    """No SMC primitive is a node in the CRT graph, so none can open a trade.

    Source: state_identity.VALID_TRANSITIONS keys/values are CRTState only;
    EXECUTION_TIMEFRAME_STATES is the trade-opening boundary.
    Failure mode: 'the FVG triggered the entry' is written as a state transition,
    so a feature value is credited with the authority of the execution machine.
    """
    graph_names = {s.name for s in VALID_TRANSITIONS}
    graph_names |= {d.name for dsts in VALID_TRANSITIONS.values() for d in dsts}
    assert graph_names.isdisjoint({n.upper() for n in SMC_PRIMITIVES})
    predecessors = [s for s, dsts in VALID_TRANSITIONS.items() if CRTState.EXECUTION in dsts]
    assert predecessors == [CRTState.RETEST]
    assert CRTState.EXECUTION in EXECUTION_TIMEFRAME_STATES


def test_canonical_features_and_order_are_one_list_not_two():
    """The two exported names are the same 48 slots, so neither can drift alone.

    Source: feature_schema.CANONICAL_FEATURES / CANONICAL_FEATURE_ORDER
    Failure mode: one export gains the SMC tail and the other does not, so the
    dimension assertion passes while consumers read two different schemas.
    """
    assert tuple(CANONICAL_FEATURES) == tuple(CANONICAL_FEATURE_ORDER)
    assert len(set(CANONICAL_FEATURE_ORDER)) == CANONICAL_FEATURE_DIM
