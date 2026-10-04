"""MKT-P01 projection: stages, dwell, longest terminal match, position track."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantics.identity import InstanceKey, SemanticIdentity
from semantics.market.episodes import UnterminatedEpisode, project_events, project_events_file
from semantics.registry import UnmatchedTerminalReason, match_terminal
from semantics.types import TerminalAuthority, TerminalClass

_ROWS = [
    {"event": "STATE_TRANSITION", "candle_index": 0, "state_to": "RANGE", "run_id": "r"},
    {"event": "STATE_TRANSITION", "candle_index": 5, "state_to": "SWEEP", "run_id": "r"},
    {"event": "STATE_TRANSITION", "candle_index": 8, "state_to": "DISPLACEMENT", "run_id": "r"},
    {"event": "STATE_TRANSITION", "candle_index": 9, "state_to": "EXPANSION", "run_id": "r"},
    {"event": "STATE_TRANSITION", "candle_index": 14, "state_to": "EXECUTION", "run_id": "r"},
    {"event": "RESET", "candle_index": 20, "reason": "50% retrace hit (retrace=0.510)", "run_id": "r"},
]


def test_synthetic_episode_stages_dwell_and_position_track():
    projection = project_events(_ROWS, founding="m15_structural_range")
    assert len(projection.episodes) == 1
    episode = projection.episodes[0]
    assert [(stage.stage, stage.dwell) for stage in episode.stages] == [
        ("AWAITING_SWEEP", 5),
        ("SWEPT", 3),
        ("DISPLACED", 1),
        ("EXTENDED", 11),
    ]
    assert episode.instance_bar == 5
    assert episode.termination is not None
    assert episode.termination.authority is TerminalAuthority.MARKET
    assert episode.termination.terminal_class is TerminalClass.FAILED
    assert episode.termination.reason_code == "RETRACE_BREACH"
    assert episode.termination.legacy_reason.startswith("50% retrace hit")
    assert all(stage.concept_id != "EXECUTION" for stage in episode.stages)
    assert len(projection.position_track) == 1
    mark = projection.position_track[0]
    assert mark.concept_id is None
    assert mark.engine_state == "EXECUTION"
    assert mark.available_at == 14
    assert projection.policy_shaped is False
    assert projection.observation_shaped is False
    assert projection.producer_shaped is False
    assert projection.unmatched_reasons == 0


def test_return_to_range_without_reset_raises():
    # Every termination carries an authority (spec §8). Leaving AWAITING and coming back to
    # RANGE with no RESET row has none, so the projection refuses instead of emitting None.
    rows = _ROWS[:3] + [
        {"event": "STATE_TRANSITION", "candle_index": 12, "state_to": "RANGE", "run_id": "r"},
    ]
    with pytest.raises(UnterminatedEpisode, match="bar 12"):
        project_events(rows, founding="m15_structural_range")


def test_instance_key_is_anchor_bar_and_run_without_producer():
    episode = project_events(_ROWS, founding="m15_structural_range").episodes[0]
    assert episode.instance_key == InstanceKey(anchor="5", side=None, parent="r")
    semantic = SemanticIdentity("MKT-P01", "EPISODE", "MKT-L01 founding", "per_founding",
                                "per_founding", "stage entry bar")
    same = project_events(_ROWS, founding="m15_structural_range").episodes[0]
    other_founding = project_events(_ROWS, founding="swing_pivot").episodes[0]
    assert episode.instance_id(semantic) == same.instance_id(semantic)
    assert episode.instance_id(semantic) != other_founding.instance_id(semantic)
    with pytest.raises(ValueError):
        episode.instance_id(SemanticIdentity("MKT-E01", "EVENT", "x", "bar", "bar_close", "bar_close"))


def test_decision_termination_sets_policy_shaped():
    rows = _ROWS + [
        {"event": "STATE_TRANSITION", "candle_index": 30, "state_to": "SWEEP", "run_id": "r"},
        {"event": "RESET", "candle_index": 40, "reason": "off_session_filter", "run_id": "r"},
    ]
    projection = project_events(rows, founding="m15_structural_range")
    assert len(projection.episodes) == 2
    assert projection.policy_shaped is True
    assert projection.observation_shaped is False
    assert projection.producer_shaped is False
    assert projection.episodes[1].termination.authority is TerminalAuthority.DECISION
    assert projection.episodes[1].instance_bar == 30


def test_unknown_reason_raises():
    rows = [{"event": "RESET", "candle_index": 1, "reason": "not a real reason", "run_id": "r"}]
    with pytest.raises(UnmatchedTerminalReason):
        project_events(rows, founding="m15_structural_range")


def test_longest_match_wins_and_exact_wins_a_tie():
    longer = [
        {"match": "prefix", "reason": "Soft", "authority": "DECISION",
         "class": "FILTERED", "code": "SHORT"},
        {"match": "prefix", "reason": "Soft confirmation not met within", "authority": "DECISION",
         "class": "FILTERED", "code": "LONG"},
    ]
    assert match_terminal("Soft confirmation not met within 3 bars", longer)["code"] == "LONG"
    tied = [
        {"match": "prefix", "reason": "Soft confirmation timeout", "authority": "DECISION",
         "class": "FILTERED", "code": "PREFIX"},
        {"match": "exact", "reason": "Soft confirmation timeout", "authority": "DECISION",
         "class": "FILTERED", "code": "EXACT"},
    ]
    assert match_terminal("Soft confirmation timeout", tied)["code"] == "EXACT"


@pytest.mark.measurement
def test_xau_full_trace_reset_classes():
    root = Path(__file__).resolve().parents[2] / "results" / "xau_full_trace"
    hits = sorted(root.glob("run_20260930_163142*/XAUUSD_events.jsonl"))
    assert len(hits) == 1, hits
    projection = project_events_file(hits[0], founding="m15_structural_range")
    assert projection.unmatched_reasons == 0
    counts = projection.termination_counts
    assert counts[("MARKET", "EXPIRED")] == 2467
    assert counts[("MARKET", "FAILED")] == 166
    assert counts[("MARKET", "SPENT")] == 109
    assert sum(n for (auth, _cls), n in counts.items() if auth == "OBSERVATION") == 121
    assert sum(n for (auth, _cls), n in counts.items() if auth == "DECISION") == 20
    assert sum(n for (auth, _cls), n in counts.items() if auth == "EXECUTION") == 4
    assert sum(counts.values()) == 2887
