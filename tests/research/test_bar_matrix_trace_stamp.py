"""CH-oracle-join-spine: the fail-closed identity join in `build_bar_matrix.py` (C/C2).

Exercises the join primitives directly (`_load_l3_map` / `_join_trace_identity` /
`_engine_state_name`) against small synthetic layer-trace files and DataFrames, rather
than the full `build_bar_matrix()` pipeline (feature pipeline + admission + resolver —
out of scope here; covered end-to-end by the real-corpus verification run). Every miss
case here must be a declared status or a refusal, never a silent skip (F-056/F-079/
F-083/F-085) — that discipline is what this file protects.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_SCRIPTS_RESEARCH = _ROOT / "scripts" / "research"
if str(_SCRIPTS_RESEARCH) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_RESEARCH))

from governance.identity_spine import ALLOW_JOIN_BAR_OPEN_TS, JOIN_TABLE  # noqa: E402
from build_bar_matrix import (  # noqa: E402
    DuplicateTraceBar,
    FrozenPkMismatch,
    LtIdNotFound,
    TraceMatrixCoverageMismatch,
    UnjoinedMatrixBars,
    _engine_state_name,
    _join_trace_identity,
    _load_l3_map,
)

INSTRUMENT, TIMEFRAME, CORPUS = "XAUUSD", "M15", "c" * 64
LT_A, LT_B = "lt_20260922_044800_XAUUSD", "lt_20260921_172325_XAUUSD"


def _l3_row(run_id, bar_ts, output_hash="CRTState.RANGE", **overrides):
    row = {
        "run_id": run_id, "instrument": INSTRUMENT, "timeframe": TIMEFRAME,
        "corpus_sha256": CORPUS, "layer": "L3", "bar_ts": bar_ts,
        "trace_id": f"{run_id}:{INSTRUMENT}:{bar_ts.replace(' ', 'T')}",
        "output_hash": output_hash,
    }
    row.update(overrides)
    return row


def _write_trace(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "XAUUSD_layer_trace.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return p


def _three_bars(run_id=LT_A):
    return [
        _l3_row(run_id, "2024-05-22 20:00:00", output_hash="CRTState.RANGE"),
        _l3_row(run_id, "2024-05-22 20:15:00", output_hash="CRTState.SWEEP"),
        _l3_row(run_id, "2024-05-22 20:30:00", output_hash="CRTState.EXPANSION"),
    ]


def _matrix_3():
    return pd.DataFrame({
        "timestamp": pd.to_datetime([
            "2024-05-22 20:00:00", "2024-05-22 20:15:00", "2024-05-22 20:30:00",
        ]),
        "_pos": [0, 1, 2],
    })


# ─────────────────────────────────────────────────────────────────────────────
# _engine_state_name
# ─────────────────────────────────────────────────────────────────────────────
def test_engine_state_name_strips_crtstate_prefix():
    assert _engine_state_name("CRTState.RANGE") == "RANGE"
    assert _engine_state_name("CRTState.SHADOW_PENDING") == "SHADOW_PENDING"


def test_engine_state_name_passes_through_unprefixed_and_none():
    assert _engine_state_name("RANGE") == "RANGE"      # already bare -- no double-strip
    assert _engine_state_name(None) is None


# ─────────────────────────────────────────────────────────────────────────────
# _load_l3_map
# ─────────────────────────────────────────────────────────────────────────────
def test_l3_map_filters_by_lt_id_and_layer(tmp_path):
    rows = _three_bars(LT_A) + _three_bars(LT_B) + [
        dict(_l3_row(LT_A, "2024-05-22 20:00:00"), layer="L4"),   # not L3 -- excluded
    ]
    trace_path = _write_trace(tmp_path, rows)
    m, stats = _load_l3_map(trace_path, LT_A, instrument=INSTRUMENT, timeframe=TIMEFRAME,
                            corpus_sha256=CORPUS)
    assert stats["l3_rows_this_lt"] == 3
    assert set(m) == {"2024-05-22 20:00:00", "2024-05-22 20:15:00", "2024-05-22 20:30:00"}
    assert m["2024-05-22 20:15:00"] == (f"{LT_A}:{INSTRUMENT}:2024-05-22T20:15:00", "SWEEP")


def test_l3_map_ignores_run_scoped_rows_but_counts_them(tmp_path):
    # A hypothetical run-scoped L3 row (bar_ts=None, no timestamp alias present at all) --
    # `resolve_bar` returns None for it, so it must be counted, never silently dropped nor
    # mistaken for a real bar. L3 never actually emits this way today (only L7's
    # `emit_not_reached_once` does); this exercises the defensive branch directly.
    run_scoped = {
        "run_id": LT_A, "instrument": INSTRUMENT, "timeframe": TIMEFRAME,
        "corpus_sha256": CORPUS, "layer": "L3", "bar_ts": None,
        "trace_id": f"{LT_A}:RUN_SCOPED", "output_hash": None,
    }
    rows = _three_bars(LT_A) + [run_scoped]
    trace_path = _write_trace(tmp_path, rows)
    _, stats = _load_l3_map(trace_path, LT_A, instrument=INSTRUMENT, timeframe=TIMEFRAME,
                            corpus_sha256=CORPUS)
    assert stats["run_scoped_rows_ignored"] == 1
    assert stats["l3_rows_this_lt"] == 3


def test_absent_lt_id_raises_and_lists_available_ids(tmp_path):
    trace_path = _write_trace(tmp_path, _three_bars(LT_A))
    with pytest.raises(LtIdNotFound) as exc:
        _load_l3_map(trace_path, "lt_does_not_exist", instrument=INSTRUMENT,
                    timeframe=TIMEFRAME, corpus_sha256=CORPUS)
    assert LT_A in str(exc.value)


def test_duplicate_bar_open_ts_within_one_lt_id_raises(tmp_path):
    rows = _three_bars(LT_A) + [_l3_row(LT_A, "2024-05-22 20:00:00")]  # same bar, twice
    trace_path = _write_trace(tmp_path, rows)
    with pytest.raises(DuplicateTraceBar):
        _load_l3_map(trace_path, LT_A, instrument=INSTRUMENT, timeframe=TIMEFRAME,
                    corpus_sha256=CORPUS)


def test_frozen_pk_mismatch_raises(tmp_path):
    rows = [_l3_row(LT_A, "2024-05-22 20:00:00", instrument="EURUSD")]
    trace_path = _write_trace(tmp_path, rows)
    with pytest.raises(FrozenPkMismatch):
        _load_l3_map(trace_path, LT_A, instrument=INSTRUMENT, timeframe=TIMEFRAME,
                    corpus_sha256=CORPUS)


# ─────────────────────────────────────────────────────────────────────────────
# _join_trace_identity
# ─────────────────────────────────────────────────────────────────────────────
def test_lt_id_and_trace_id_are_inherited_from_l3_not_minted(tmp_path):
    trace_path = _write_trace(tmp_path, _three_bars(LT_A))
    enriched = _matrix_3()
    manifest = _join_trace_identity(
        enriched, lt_id=LT_A, layer_trace_path=trace_path,
        instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
        no_trace_join=False, allow_unjoined_bars=False, allow_trace_only_bars=False,
    )
    assert manifest["trace_join_status"] == "COMPLETE"
    assert list(enriched["lt_id"].unique()) == [LT_A]
    assert enriched["trace_id"].tolist() == [
        f"{LT_A}:{INSTRUMENT}:2024-05-22T20:00:00",
        f"{LT_A}:{INSTRUMENT}:2024-05-22T20:15:00",
        f"{LT_A}:{INSTRUMENT}:2024-05-22T20:30:00",
    ]
    assert (enriched["trace_join_status"] == "JOINED").all()


def test_engine_state_after_is_copied_from_l3_output_hash_stripped(tmp_path):
    trace_path = _write_trace(tmp_path, _three_bars(LT_A))
    enriched = _matrix_3()
    _join_trace_identity(
        enriched, lt_id=LT_A, layer_trace_path=trace_path,
        instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
        no_trace_join=False, allow_unjoined_bars=False, allow_trace_only_bars=False,
    )
    assert enriched["engine_state_after"].tolist() == ["RANGE", "SWEEP", "EXPANSION"]


def test_bar_idx_is_not_written_as_a_column(tmp_path):
    trace_path = _write_trace(tmp_path, _three_bars(LT_A))
    enriched = _matrix_3()
    _join_trace_identity(
        enriched, lt_id=LT_A, layer_trace_path=trace_path,
        instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
        no_trace_join=False, allow_unjoined_bars=False, allow_trace_only_bars=False,
    )
    assert "bar_idx" not in enriched.columns


def test_matrix_bar_with_no_l3_row_raises_by_default(tmp_path):
    trace_path = _write_trace(tmp_path, _three_bars(LT_A)[:2])   # only 2 of 3 bars
    enriched = _matrix_3()
    with pytest.raises(UnjoinedMatrixBars):
        _join_trace_identity(
            enriched, lt_id=LT_A, layer_trace_path=trace_path,
            instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
            no_trace_join=False, allow_unjoined_bars=False, allow_trace_only_bars=False,
        )


def test_allow_unjoined_bars_writes_no_l3_row_never_a_blank(tmp_path):
    trace_path = _write_trace(tmp_path, _three_bars(LT_A)[:2])
    enriched = _matrix_3()
    manifest = _join_trace_identity(
        enriched, lt_id=LT_A, layer_trace_path=trace_path,
        instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
        no_trace_join=False, allow_unjoined_bars=True, allow_trace_only_bars=False,
    )
    assert manifest["trace_join_status"] == "PARTIAL"
    assert manifest["rows_without_trace_id"] == 1
    last = enriched.iloc[2]
    assert last["trace_join_status"] == "NO_L3_ROW"
    assert last["trace_id"] == "NOT_JOINED"          # never blank, never NaN
    assert last["engine_state_after"] == "NOT_JOINED"


def test_trace_only_bars_raise_by_default_and_allow_flag_accepts(tmp_path):
    rows = _three_bars(LT_A) + [_l3_row(LT_A, "2024-05-22 21:00:00")]  # extra L3 bar
    trace_path = _write_trace(tmp_path, rows)
    enriched = _matrix_3()
    with pytest.raises(TraceMatrixCoverageMismatch):
        _join_trace_identity(
            enriched, lt_id=LT_A, layer_trace_path=trace_path,
            instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
            no_trace_join=False, allow_unjoined_bars=False, allow_trace_only_bars=False,
        )
    manifest = _join_trace_identity(
        enriched.copy(), lt_id=LT_A, layer_trace_path=trace_path,
        instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
        no_trace_join=False, allow_unjoined_bars=False, allow_trace_only_bars=True,
    )
    assert manifest["trace_bar_ts_absent_from_matrix"] == 1


def test_no_trace_join_writes_declined_on_every_row_and_in_the_manifest():
    enriched = _matrix_3()
    manifest = _join_trace_identity(
        enriched, lt_id=None, layer_trace_path=None,
        instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
        no_trace_join=True, allow_unjoined_bars=False, allow_trace_only_bars=False,
    )
    assert manifest["trace_join_status"] == "DECLINED"
    assert (enriched["trace_join_status"] == "DECLINED").all()
    assert (enriched["trace_id"] == "NOT_JOINED").all()
    assert (enriched["engine_state_after"] == "NOT_JOINED").all()


def test_instrument_timeframe_corpus_sha_stamped_per_row(tmp_path):
    trace_path = _write_trace(tmp_path, _three_bars(LT_A))
    enriched = _matrix_3()
    _join_trace_identity(
        enriched, lt_id=LT_A, layer_trace_path=trace_path,
        instrument=INSTRUMENT, timeframe=TIMEFRAME, corpus_sha256=CORPUS,
        no_trace_join=False, allow_unjoined_bars=False, allow_trace_only_bars=False,
    )
    assert (enriched["instrument"] == INSTRUMENT).all()
    assert (enriched["timeframe"] == TIMEFRAME).all()
    assert (enriched["corpus_sha256"] == CORPUS).all()


# ─────────────────────────────────────────────────────────────────────────────
# Join legality (identity_spine.JOIN_TABLE)
# ─────────────────────────────────────────────────────────────────────────────
def test_join_key_is_the_allow_join_bar_open_ts_row_of_join_table():
    """The join implemented above keys on bar_open_ts. Assert that literal row of the
    table exists and is the ALLOW verdict — legality is mechanical, not asserted in prose."""
    row = next(r for r in JOIN_TABLE if r[1] == "bar_open_ts" and r[3] == "bar_open_ts")
    assert row[4] == ALLOW_JOIN_BAR_OPEN_TS
