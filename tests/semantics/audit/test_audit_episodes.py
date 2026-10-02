# Phase 1 audit test. Authority: terminal_reason_map.yaml, representation_registry/crt_engine.yaml,
# concept_contracts.yaml MKT-P01 and the slice-1 spec section 8.
from __future__ import annotations
import pytest
from semantics.market.episodes import project_events
from semantics.registry import UnmatchedTerminalReason
from semantics.types import TerminalAuthority, TerminalClass
_STAGES = [("RANGE", "AWAITING_SWEEP"), ("SWEEP", "SWEPT"), ("SHADOW_PENDING", "SHADOW_PENDING"),
           ("DISPLACEMENT", "DISPLACED"), ("EXPANSION", "EXTENDED"), ("RETEST", "RETESTING")]
def _rows(*spec, run="r"):
    return [{"event": "STATE_TRANSITION", "candle_index": b, "state_to": s, "run_id": run} for b, s in spec]
def _ep(rows):
    return project_events(rows, founding="m15_structural_range").episodes
def test_engine_state_aliases_map_to_the_declared_stages():
    for engine_state, stage_alias in _STAGES:
        names = [s.stage for s in _ep(_rows((0, "RANGE"), (3, engine_state)))[0].stages]
        assert names[0] == "AWAITING_SWEEP"
        assert stage_alias in names
def test_dwell_is_the_bar_count_of_each_closed_stage():
    stages = _ep(_rows((0, "RANGE"), (5, "SWEEP"), (8, "EXPANSION"), (12, "RETEST")))[0].stages
    dwell = {s.stage: s.dwell for s in stages}
    assert dwell["AWAITING_SWEEP"] == 5 and dwell["SWEPT"] == 3 and dwell["EXTENDED"] == 4
    assert dwell["RETESTING"] is None
def test_a_reset_closes_the_open_stage_and_gives_it_a_dwell():
    rows = _rows((0, "RANGE"), (5, "SWEEP"), (8, "EXPANSION")) + [
        {"event": "RESET", "candle_index": 20, "reason": "1.618 extension hit z", "run_id": "r"}]
    stages = _ep(rows)[0].stages
    assert {s.stage: s.dwell for s in stages}["EXTENDED"] == 12
    assert all(s.dwell is not None for s in stages)
_CASES = [
    ("Sweep expired", TerminalAuthority.PRODUCER, TerminalClass.EXPIRED, "SWEEP_TTL"),
    ("HTF changed: x", TerminalAuthority.MARKET, TerminalClass.EXPIRED, "HTF_ROLLOVER"),
    ("Session gap detected: y", TerminalAuthority.OBSERVATION, TerminalClass.AVAILABILITY_LAPSE, "DATA_GAP"),
    ("off_session_filter", TerminalAuthority.DECISION, TerminalClass.FILTERED, "OFF_SESSION"),
    ("Post-resolution reset", TerminalAuthority.EXECUTION, TerminalClass.POSITION_CLOSED, "POST_RESOLUTION"),
    ("resolver_founding", TerminalAuthority.PRODUCER, TerminalClass.CONSTRUCTION, "RESOLVER_RESEED"),
]

def test_termination_authority_and_class_come_from_the_map():
    rows = _rows((0, "RANGE"), (3, "SWEEP")) + [
        {"event": "RESET", "candle_index": 20, "reason": "50% retrace hit (0.51)", "run_id": "r"}]
    term = _ep(rows)[0].termination
    assert term.authority is TerminalAuthority.MARKET
    assert term.terminal_class is TerminalClass.FAILED
    assert term.reason_code == "RETRACE_BREACH"
    assert term.legacy_reason.startswith("50% retrace hit")

def test_each_authority_terminates_with_its_declared_class():
    for reason, authority, tclass, code in _CASES:
        rows = _rows((0, 'RANGE'), (3, 'SWEEP')) + [
            {'event': 'RESET', 'candle_index': 10, 'reason': reason, 'run_id': 'r'}]
        term = _ep(rows)[0].termination
        assert term.authority is authority
        assert term.terminal_class is tclass
        assert term.reason_code == code


def test_longest_match_beats_the_shorter_prefix():
    rows = _rows((0, 'RANGE'), (3, 'SWEEP')) + [
        {'event': 'RESET', 'candle_index': 10, 'reason': 'resolver_founding_inputs_missing', 'run_id': 'r'}]
    assert _ep(rows)[0].termination.reason_code == 'RESOLVER_INPUTS_MISSING'


def test_unknown_reason_raises():
    with pytest.raises(UnmatchedTerminalReason):
        project_events([{'event': 'RESET', 'candle_index': 1, 'reason': 'utterly unknown', 'run_id': 'r'}], founding='m15_structural_range')


def test_execution_states_go_to_the_position_track_not_market_stages():
    rows = _rows((0, 'RANGE'), (3, 'SWEEP')) + [
        {'event': 'STATE_TRANSITION', 'candle_index': 6, 'state_to': 'EXECUTION', 'run_id': 'r'},
        {'event': 'STATE_TRANSITION', 'candle_index': 7, 'state_to': 'RESOLUTION', 'run_id': 'r'}]
    proj = project_events(rows, founding='m15_structural_range')
    assert all('EXECUTION' not in s.concept_id and 'RESOLUTION' not in s.concept_id for s in proj.episodes[0].stages)
    assert [m.engine_state for m in proj.position_track] == ['EXECUTION', 'RESOLUTION']
    assert all(m.concept_id is None for m in proj.position_track)


def _shaped(reason):
    rows = _rows((0, 'SWEEP')) + [
        {'event': 'RESET', 'candle_index': 4, 'reason': reason, 'run_id': 'r'}]
    return project_events(rows, founding='m15_structural_range')


def test_series_shaping_flags_follow_the_terminating_authority():
    decision = _shaped('off_session_filter')
    assert decision.policy_shaped and not decision.observation_shaped and not decision.producer_shaped
    observation = _shaped('Session gap detected: 3 bars')
    assert observation.observation_shaped and not observation.policy_shaped
    producer = _shaped('Sweep expired')
    assert producer.producer_shaped and not producer.policy_shaped
