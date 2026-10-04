"""Fixture-based tests for cross-family run_id / (instrument, bar_ts) joins.

Draft for docs/implementation_plan/cross-family-run-join.md.
These tests exercise pure helpers with synthetic records shaped like the three
families AFTER the interpreter schema addition (run_id + instrument on readings).
They do NOT require InterpreterReading wiring to be landed yet.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from research.cross_family_join import (
    interpreter_bar_key,
    join_families,
    join_on_instrument_bar,
    join_on_run_id,
    layer_trace_bar_key,
    normalize_run_id,
    opportunity_bar_key,
)


TS = datetime(2024, 5, 22, 14, 30, 0, tzinfo=timezone.utc)
TS2 = datetime(2024, 5, 22, 14, 45, 0, tzinfo=timezone.utc)

LT_RUN = "lt_20240522_143000_XAUUSD"
CANON_RUN = "run_20240522_143000"
SCAN_RUN = "20240522_143015"


@pytest.fixture
def layer_rows():
    return [
        {
            "run_id": LT_RUN,
            "trace_id": f"{LT_RUN}:XAUUSD:{TS.isoformat()}",
            "instrument": "XAUUSD",
            "bar_ts": TS.isoformat(),
            "layer": "L3",
            "preexisting_run_ids": {
                "utils.logging_config.RUN_ID": "20240522_100000",
                "runtime.ReportWriter.run_id": CANON_RUN,
            },
        },
        {
            "run_id": LT_RUN,
            "trace_id": f"{LT_RUN}:XAUUSD:{TS2.isoformat()}",
            "instrument": "XAUUSD",
            "bar_ts": TS2.isoformat(),
            "layer": "L3",
            "preexisting_run_ids": {
                "runtime.ReportWriter.run_id": CANON_RUN,
            },
        },
    ]


@pytest.fixture
def interpreter_rows():
    # Shape AFTER draft schema addition (not yet on InterpreterReading in production).
    return [
        {
            "run_id": LT_RUN,
            "instrument": "XAUUSD",
            "observation_time": TS,
            "trace_id": "PNF-v1-20240522-143000",
            "confidence": 0.7,
        },
        {
            "run_id": LT_RUN,
            "instrument": "XAUUSD",
            "observation_time": TS2,
            "trace_id": "PNF-v1-20240522-144500",
            "confidence": 0.4,
        },
    ]


@pytest.fixture
def opportunity_rows():
    # Today: scan-pass run_id. Draft join uses alias_map to link SCAN_RUN -> LT_RUN
    # until CH-cost-model stamps _canonical_run_id / shared run_id on opportunity rows.
    return [
        {
            "run_id": SCAN_RUN,
            "trace_id": "TR-TEST-CAMPAIGN",
            "analysis_id": "AN-TEST-ANALYSIS",
            "instrument": "XAUUSD",
            "timestamp": TS.isoformat(),
            "direction": "long",
        },
        {
            "run_id": SCAN_RUN,
            "trace_id": "TR-TEST-CAMPAIGN",
            "analysis_id": "AN-TEST-ANALYSIS",
            "instrument": "XAUUSD",
            "timestamp": TS2.isoformat(),
            "direction": "short",
        },
    ]


def test_primary_join_layer_trace_to_interpreter(layer_rows, interpreter_rows):
    pairs = join_on_run_id(layer_rows, interpreter_rows)
    # 2 bars x 2 layers-rows sharing run × matching interpreters at same run
    # each LT row joins both interpreter rows with same run_id (2*2=4)
    assert len(pairs) == 4
    assert all(l["run_id"] == r["run_id"] == LT_RUN for l, r in pairs)


def test_primary_join_interpreter_to_opportunity_requires_alias(
    interpreter_rows, opportunity_rows
):
    # Without alias: scan run_id != lt run_id → no primary pairs (documents the gap)
    assert join_on_run_id(interpreter_rows, opportunity_rows) == []

    alias = {SCAN_RUN: LT_RUN, LT_RUN: LT_RUN}
    pairs = join_on_run_id(interpreter_rows, opportunity_rows, alias_map=alias)
    assert len(pairs) == 4
    for left, right in pairs:
        assert normalize_run_id(left["run_id"], alias) == normalize_run_id(
            right["run_id"], alias
        )


def test_secondary_join_instrument_bar_when_run_ids_differ(
    layer_rows, opportunity_rows
):
    pairs = join_on_instrument_bar(
        layer_rows,
        opportunity_rows,
        left_key_fn=layer_trace_bar_key,
        right_key_fn=opportunity_bar_key,
    )
    assert len(pairs) == 2  # one opp per bar
    for l, r in pairs:
        assert l["instrument"] == r["instrument"] == "XAUUSD"
        assert layer_trace_bar_key(l)[1] == opportunity_bar_key(r)[1]


def test_secondary_join_interpreter_observation_time(layer_rows, interpreter_rows):
    pairs = join_on_instrument_bar(
        layer_rows,
        interpreter_rows,
        left_key_fn=layer_trace_bar_key,
        right_key_fn=interpreter_bar_key,
    )
    assert len(pairs) == 2
    for l, r in pairs:
        assert layer_trace_bar_key(l) == interpreter_bar_key(r)


def test_join_families_bundle(layer_rows, interpreter_rows, opportunity_rows):
    alias = {SCAN_RUN: LT_RUN, LT_RUN: LT_RUN}
    bundle = join_families(
        layer_trace=layer_rows,
        interpreters=interpreter_rows,
        opportunities=opportunity_rows,
        alias_map=alias,
    )
    assert set(bundle) == {
        "layer_trace_to_interpreter",
        "layer_trace_to_opportunity",
        "interpreter_to_opportunity",
    }
    assert len(bundle["layer_trace_to_interpreter"]) == 4
    assert len(bundle["layer_trace_to_opportunity"]) == 4
    assert len(bundle["interpreter_to_opportunity"]) == 4


def test_f101_no_implicit_clock_equality():
    """Two different run_id strings that look time-related must NOT join without alias."""
    left = [{"run_id": "run_20240522_143000", "instrument": "XAUUSD"}]
    right = [{"run_id": "lt_20240522_143000_XAUUSD", "instrument": "XAUUSD"}]
    assert join_on_run_id(left, right) == []


def test_normalize_run_id_alias_and_passthrough():
    alias = {SCAN_RUN: LT_RUN}
    assert normalize_run_id(SCAN_RUN, alias) == LT_RUN
    assert normalize_run_id(LT_RUN, alias) == LT_RUN
    assert normalize_run_id("", alias) == ""


def test_draft_schema_fields_required_for_interpreter_fixture(interpreter_rows):
    """Documents the draft contract: interpreter rows used for joins must carry both keys."""
    for row in interpreter_rows:
        assert row["run_id"], "draft: run_id required on interpreter join records"
        assert row["instrument"] and row["instrument"] != "UNKNOWN"
        assert row["observation_time"] is not None
