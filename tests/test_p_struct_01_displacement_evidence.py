"""P-STRUCT-01 evidence-table floor.

The node is an evidence table over CRT DISPLACEMENT events. These tests
lock the inventory boundary: UNKNOWN_N stays data, forbidden dimensions
cannot appear, volume stays numeric, RANGE→DISPLACEMENT is illegal
rather than after_range.
"""
from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from scripts.research.p_struct_01_displacement_evidence import (  # noqa: E402
    FORBIDDEN_OUTPUT_KEYS,
    LEGAL_DISP_PREDECESSORS,
    ROW_KEYS,
    UNKNOWN_N,
    IllegalPredecessor,
    extract_rows,
    load_volume_join,
    main,
)


def _ts(i: int) -> str:
    epoch = datetime(2024, 5, 23, 2, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i)
    return epoch.strftime("%Y-%m-%dT%H:%M:%S")


def _transition(i: int, state_from: str, state_to: str) -> dict:
    return {
        "event": "STATE_TRANSITION",
        "timestamp": _ts(i),
        "candle_index": i,
        "state_from": state_from,
        "state_to": state_to,
        "direction": None,
    }


def _sweep_event(i: int, direction: str) -> dict:
    return {
        "event": "SWEEP",
        "timestamp": _ts(i),
        "candle_index": i,
        "direction": direction,
        "state_from": None,
        "state_to": None,
    }


def _legal_sequence(*, direction: str = "LONG", disp_at: int = 3, exp_at: int | None = 6) -> list[dict]:
    events = [
        _transition(0, "RANGE", "SWEEP"),
        _sweep_event(0, direction),
        _transition(disp_at, "SWEEP", "DISPLACEMENT"),
    ]
    if exp_at is not None:
        events.append(_transition(exp_at, "DISPLACEMENT", "EXPANSION"))
    return events


FROZEN_ROW_KEYS = (
    "timestamp",
    "engine_state",
    "direction",
    "direction_source",
    "predecessor_state",
    "after_sweep",
    "age_since_sweep_bars",
    "age_since_sweep_class",
    "continuation_successor",
    "continuation_age_bars",
    "continuation_age_class",
    "volume_ratio",
    "volume_spike",
    "volume_join_status",
    "volume_participation",
    "crt_wire",
    "crt_wire_gate",
)


def test_row_keys_do_not_grow_from_interesting_counts() -> None:
    """Enrichment is join-or-contract only. A histogram is not a column."""
    assert ROW_KEYS == FROZEN_ROW_KEYS


def test_legal_predecessors_are_sweep_only() -> None:
    from config_layer.state_identity import CRTState, VALID_TRANSITIONS

    assert LEGAL_DISP_PREDECESSORS == {"SWEEP"}
    assert CRTState.DISPLACEMENT in VALID_TRANSITIONS[CRTState.SWEEP]
    assert CRTState.DISPLACEMENT not in VALID_TRANSITIONS[CRTState.RANGE]
    assert CRTState.RANGE.name not in LEGAL_DISP_PREDECESSORS


def test_happy_path_unknown_n_and_direction_join() -> None:
    rows, rollup = extract_rows(_legal_sequence(direction="SHORT", disp_at=2, exp_at=5))
    assert len(rows) == 1
    row = rows[0]
    assert row["engine_state"] == "DISPLACEMENT"
    assert row["direction"] == "SHORT"
    assert row["direction_source"] == "SWEEP_EVENT"
    assert row["predecessor_state"] == "SWEEP"
    assert row["after_sweep"] is True
    assert row["age_since_sweep_bars"] == 2
    assert row["age_since_sweep_class"] == UNKNOWN_N
    assert row["continuation_successor"] == "EXPANSION"
    assert row["continuation_age_bars"] == 3
    assert row["continuation_age_class"] == UNKNOWN_N
    assert row["volume_join_status"] == "NOT_JOINED"
    assert row["volume_ratio"] is None
    assert row["volume_participation"] == "UNJOINED"
    assert row["crt_wire"] == "UNJOINED"
    assert row["crt_wire_gate"] == "UNUSED"
    assert set(row) == set(ROW_KEYS)
    assert rollup["claims"] == "none"
    assert rollup["n"] == 1


def test_age_one_is_still_unknown_n_not_immediate() -> None:
    rows, _ = extract_rows(_legal_sequence(disp_at=1, exp_at=2))
    assert rows[0]["age_since_sweep_bars"] == 1
    assert rows[0]["age_since_sweep_class"] == UNKNOWN_N
    assert rows[0]["continuation_age_bars"] == 1
    assert rows[0]["continuation_age_class"] == UNKNOWN_N
    assert "immediate" not in rows[0]


def test_no_expansion_is_absent_not_a_class() -> None:
    rows, _ = extract_rows(_legal_sequence(exp_at=None))
    assert rows[0]["continuation_successor"] == "NONE"
    assert rows[0]["continuation_age_bars"] is None
    assert rows[0]["continuation_age_class"] == "ABSENT"


def test_reset_from_displacement_is_range_not_later_expansion() -> None:
    events = [
        _transition(0, "RANGE", "SWEEP"),
        _sweep_event(0, "LONG"),
        _transition(2, "SWEEP", "DISPLACEMENT"),
        {
            "event": "RESET",
            "timestamp": _ts(4),
            "candle_index": 4,
            "state_from": "DISPLACEMENT",
            "state_to": "RANGE",
            "direction": None,
        },
        _transition(10, "RANGE", "SWEEP"),
        _sweep_event(10, "SHORT"),
        _transition(12, "SWEEP", "DISPLACEMENT"),
        _transition(15, "DISPLACEMENT", "EXPANSION"),
    ]
    rows, rollup = extract_rows(events)
    assert len(rows) == 2
    assert rows[0]["continuation_successor"] == "RANGE"
    assert rows[0]["continuation_age_bars"] is None
    assert rows[0]["continuation_age_class"] == "ABSENT"
    assert rows[0]["direction"] == "LONG"
    assert rows[1]["continuation_successor"] == "EXPANSION"
    assert rows[1]["continuation_age_bars"] == 3
    assert rows[1]["direction"] == "SHORT"
    assert rollup["continuation_successor"] == {"RANGE": 1, "EXPANSION": 1}


def test_range_to_displacement_is_illegal_not_after_range() -> None:
    events = [_transition(1, "RANGE", "DISPLACEMENT")]
    with pytest.raises(IllegalPredecessor, match="ILLEGAL_PREDECESSOR"):
        extract_rows(events)


def test_sweep_to_expansion_skip_is_not_a_row() -> None:
    events = [
        _transition(0, "RANGE", "SWEEP"),
        _sweep_event(0, "LONG"),
        _transition(2, "SWEEP", "EXPANSION"),
    ]
    rows, rollup = extract_rows(events)
    assert rows == []
    assert rollup["sweep_to_expansion_skips_excluded"] == 1


def test_unjoined_direction_is_null_not_guessed() -> None:
    events = [
        _transition(0, "RANGE", "SWEEP"),
        _transition(3, "SWEEP", "DISPLACEMENT"),
    ]
    rows, _ = extract_rows(events)
    assert rows[0]["direction"] is None
    assert rows[0]["direction_source"] == "UNJOINED"


def test_volume_join_stays_numeric_never_high_volume(tmp_path: Path) -> None:
    vol_path = tmp_path / "vol.jsonl"
    ts = _ts(3).replace("T", " ")
    vol_path.write_text(
        json.dumps({
            "timestamp": _ts(3),
            "volume_ratio": 1.73,
            "volume_spike": 1,
        })
        + "\n",
        encoding="utf-8",
    )
    volume_by_ts = load_volume_join(vol_path)
    rows, _ = extract_rows(_legal_sequence(disp_at=3, exp_at=None), volume_by_ts=volume_by_ts)
    row = rows[0]
    assert row["volume_join_status"] == "JOINED"
    assert row["volume_ratio"] == 1.73
    assert row["volume_spike"] == 1
    assert row["volume_participation"] == "VolumeSpike"
    assert row["crt_wire"] == "DISPLACEMENT:VolumeSpike:ANNOTATION_ONLY"
    assert row["crt_wire_gate"] == "UNUSED"
    assert "high_volume" not in row
    assert ts.startswith(row["timestamp"][:10])


def test_forbidden_keys_absent_from_every_row() -> None:
    rows, rollup = extract_rows(_legal_sequence())
    for row in rows:
        assert set(row) & FORBIDDEN_OUTPUT_KEYS == set()
    for name in FORBIDDEN_OUTPUT_KEYS:
        assert name not in rollup


def test_extractor_does_not_import_parent_crt_or_smc() -> None:
    src = (
        ROOT / "scripts" / "research" / "p_struct_01_displacement_evidence.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = {
        "config_layer.parent_crt",
        "config_layer.htf_state",
        "features.smc",
        "features.parent_candle",
        "runtime.parent_crt_feed",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in banned
            assert not any(node.module.startswith(p + ".") for p in banned)
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned


def test_official_volume_join_is_feature_pipeline_only() -> None:
    src = (
        ROOT / "scripts" / "research" / "p_struct_01_displacement_evidence.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "official_volume_by_ts"
    )
    imported = []
    for node in ast.walk(fn):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "features.feature_pipeline" in imported
    body_src = ast.get_source_segment(src, fn) or ""
    assert "rolling" not in body_src
    assert "volume_ma" not in body_src


def test_cli_rejects_both_volume_sources(tmp_path: Path) -> None:
    ev = tmp_path / "events.jsonl"
    ev.write_text("{}\n", encoding="utf-8")
    vol = tmp_path / "vol.jsonl"
    vol.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="not both"):
        main([
            "--events", str(ev),
            "--join-official-pipeline",
            "--volume-jsonl", str(vol),
        ])


def test_joined_rollup_has_numeric_volume_not_high_volume() -> None:
    events = _legal_sequence(disp_at=3, exp_at=None)
    volume_by_ts = {
        _ts(3).replace("T", " "): {"volume_ratio": 1.73, "volume_spike": 1},
    }
    _rows, rollup = extract_rows(events, volume_by_ts=volume_by_ts)
    assert "high_volume" not in rollup
    assert rollup["volume_ratio_numeric"]["n"] == 1
    assert rollup["volume_ratio_numeric"]["min"] == 1.73
    assert rollup["volume_spike_raw_counts"] == {"1": 1}
    assert rollup["volume_participation"] == {"VolumeSpike": 1}


def test_volume_participation_is_fm063_identity_not_a_new_cut() -> None:
    events = _legal_sequence(disp_at=3, exp_at=None)
    volume_by_ts = {
        _ts(3).replace("T", " "): {"volume_ratio": 0.9, "volume_spike": 0},
    }
    rows, _ = extract_rows(events, volume_by_ts=volume_by_ts)
    assert rows[0]["volume_participation"] == "NoSpike"
    assert rows[0]["volume_spike"] == 0
    assert rows[0]["crt_wire"] == "DISPLACEMENT:NoSpike:ANNOTATION_ONLY"
    assert rows[0]["crt_wire_gate"] == "UNUSED"


def test_pstruct_06_annotation_is_not_a_displacement_when_predicate() -> None:
    import yaml

    crt_states = yaml.safe_load(
        (ROOT / "configs" / "formulas" / "market_crt_states.yaml").read_text(
            encoding="utf-8"
        )
    )
    disp = next(s for s in crt_states["states"] if s["name"] == "DISPLACEMENT")
    assert "volume_spike" not in (disp.get("when") or {})
    assert "volume_participation" not in (disp.get("when") or {})
    from config_layer.state_identity import VALID_TRANSITIONS, CRTState
    assert CRTState.DISPLACEMENT in VALID_TRANSITIONS
    # annotation did not add a transition
    assert CRTState.DISPLACEMENT not in VALID_TRANSITIONS[CRTState.DISPLACEMENT]


def test_ch_pstruct_05_coincidence_is_counts_not_classes() -> None:
    events = [
        *_legal_sequence(direction="LONG", disp_at=3, exp_at=6),
        _transition(10, "RANGE", "SWEEP"),
        _sweep_event(10, "SHORT"),
        _transition(12, "SWEEP", "DISPLACEMENT"),
    ]
    volume_by_ts = {
        _ts(3).replace("T", " "): {"volume_ratio": 1.1, "volume_spike": 1},
        _ts(12).replace("T", " "): {"volume_ratio": 0.8, "volume_spike": 0},
    }
    rows, rollup = extract_rows(events, volume_by_ts=volume_by_ts)
    coin = rollup["coincidence_declared_columns"]
    assert coin["authority"] == "CH-PSTRUCT-05"
    assert coin["economic_claims_allowed"] is False
    assert coin["classes_minted"] is False
    assert coin["direction_x_volume_participation"]["LONG|VolumeSpike"] == 1
    assert coin["direction_x_volume_participation"]["SHORT|NoSpike"] == 1
    assert sum(coin["direction_x_volume_participation"].values()) == len(rows)
    assert "high_volume" not in json.dumps(coin)
    assert "immediate" not in json.dumps(coin)
    assert all(r["age_since_sweep_class"] == UNKNOWN_N for r in rows)


def test_sem_013_is_identity_of_fm063_not_a_crt_state() -> None:
    from config_layer.state_identity import CRTState
    from features.registry import load_ontology

    ont = load_ontology()
    node = ont["execution_behaviours"]["crt_displacement_volume_participation"]
    assert node["id"] == "SEM-013"
    assert node["version"] == 3
    assert "FM-063" in node["dependencies"]
    assert node["transitions"] == []
    assert "crt_wire" in node["produced_outputs"]
    assert "DO_NOT_CONSUME" in node["notes"]
    assert any("07A CLOSED" in inv for inv in node["epistemic"]["known_invariants"])
    assert any("not a CRTState" in r for r in node["validation_rules"])
    assert "high_volume" in " ".join(node["validation_rules"])
    assert CRTState.DISPLACEMENT.name != node["canonical_name"]
    assert "volume_participation" not in {s.name for s in CRTState}


def test_extractor_source_has_no_threshold_cut() -> None:
    src = (
        ROOT / "scripts" / "research" / "p_struct_01_displacement_evidence.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
        if isinstance(node, ast.FunctionDef):
            assert not target_looks_like_cut(node.name)
    assert "high_volume" not in assigned
    assert "after_range" not in assigned
    assert "against_ema" not in assigned


def target_looks_like_cut(name: str) -> bool:
    lowered = name.lower()
    return any(
        token in lowered
        for token in ("high_volume", "after_range", "against_ema", "fingerprint")
    )
