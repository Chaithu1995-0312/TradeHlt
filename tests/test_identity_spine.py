"""Unit tests for the canonical bar-clock bridge / identity hierarchy (Phase 3).

Pins: the fixed alias vocabularies, the canonical bar_ts normalization across all four
timestamp dialects, frozen-PK resolution from every index dialect, and the id-mint +
allowed/illegal join tables.
"""
import datetime as dt
from pathlib import Path

import pytest

from governance.identity_spine import (
    ALLOW_JOIN_BAR_OPEN_TS,
    BAR_TS_ALIASES,
    DENY_POSITION_JOIN,
    DENY_RAW_INDEX,
    FROZEN_PK_FIELDS,
    ID_MINTS,
    INDEX_ALIASES,
    JOIN_TABLE,
    index_field,
    is_frozen_pk_complete,
    normalize_bar_ts,
    resolve_bar,
)


class TestAliasVocabularies:
    def test_index_aliases_cover_all_four_dialects(self):
        for dialect in ("bar_index", "engine_candle_index", "bar_idx", "_pos",
                        "candle_index", "candle_open"):
            assert dialect in INDEX_ALIASES

    def test_bar_ts_aliases_cover_every_timestamp_name(self):
        for name in ("timestamp", "bar_ts", "opened_at", "first_seen_ts"):
            assert name in BAR_TS_ALIASES

    def test_frozen_pk_fields_are_exact(self):
        assert FROZEN_PK_FIELDS == ("instrument", "timeframe", "bar_open_ts", "corpus_sha256")


class TestNormalizeBarTs:
    def test_datetime_naive(self):
        assert normalize_bar_ts(dt.datetime(2026, 9, 22, 14, 30, 0)) == "2026-09-22 14:30:00"

    def test_iso_space_form(self):
        assert normalize_bar_ts("2026-09-22 14:30:00") == "2026-09-22 14:30:00"

    def test_iso_t_separator(self):
        assert normalize_bar_ts("2026-09-22T14:30:00") == "2026-09-22 14:30:00"

    def test_iso_with_microseconds(self):
        assert normalize_bar_ts("2026-09-22 14:30:00.123456") == "2026-09-22 14:30:00"

    def test_iso_with_z_utc(self):
        assert normalize_bar_ts("2026-09-22T14:30:00Z") == "2026-09-22 14:30:00"

    def test_iso_with_timezone_offset(self):
        # +02:00 aware datetime -> rendered in the machine's local tz wall-clock
        aware = dt.datetime(2026, 9, 22, 14, 30, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        expected = aware.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        assert normalize_bar_ts("2026-09-22T14:30:00+02:00") == expected

    def test_epoch_seconds(self):
        t = dt.datetime(2026, 9, 22, 14, 30, 0, tzinfo=dt.timezone.utc).timestamp()
        assert normalize_bar_ts(t) == "2026-09-22 14:30:00"

    def test_none_raises(self):
        with pytest.raises(ValueError):
            normalize_bar_ts(None)

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            normalize_bar_ts("not-a-timestamp")

    def test_dialects_are_equivalent(self):
        a = normalize_bar_ts(dt.datetime(2026, 9, 22, 9, 0, 0))
        b = normalize_bar_ts("2026-09-22 09:00:00")
        c = normalize_bar_ts("2026-09-22T09:00:00")
        assert a == b == c


class TestResolveBar:
    def test_snapshot_dialect(self):
        rec = {
            "instrument": "XAUUSD", "timeframe": "M15",
            "corpus_sha256": "c0ffee" * 8,
            "bar_index": 41, "engine_candle_index": 7,
            "timestamp": "2026-09-22 09:00:00",
        }
        pk = resolve_bar(rec)
        assert pk == ("XAUUSD", "M15", "2026-09-22 09:00:00", "c0ffee" * 8)
        assert index_field(rec) == "bar_index"
        assert is_frozen_pk_complete(pk)

    def test_layer_trace_dialect(self):
        rec = {"bar_idx": 12, "bar_ts": "2026-09-22 09:15:00", "instrument": "XAUUSD"}
        pk = resolve_bar(rec)
        assert pk[0] == "XAUUSD" and pk[2] == "2026-09-22 09:15:00"
        assert index_field(rec) == "bar_idx"

    def test_trades_csv_dialect(self):
        rec = {"candle_open": 99, "opened_at": "2026-09-22T09:30:00", "instrument": "XAUUSD"}
        pk = resolve_bar(rec)
        assert pk[2] == "2026-09-22 09:30:00"
        assert index_field(rec) == "candle_open"

    def test_telemetry_dialect(self):
        rec = {"candle_index": 4, "bar_ts": "2026-09-22 09:45:00"}
        pk = resolve_bar(rec, instrument="XAUUSD")
        assert pk[0] == "XAUUSD" and pk[2] == "2026-09-22 09:45:00"
        assert index_field(rec) == "candle_index"

    def test_labeler_dialect(self):
        rec = {"_pos": 200, "timestamp": "2026-09-22 10:00:00"}
        pk = resolve_bar(rec, instrument="XAUUSD")
        assert pk[2] == "2026-09-22 10:00:00"
        assert index_field(rec) == "_pos"

    def test_run_scoped_layer_row_is_not_a_bar(self):
        rec = {"bar_idx": -1, "bar_ts": None, "layer": "L0"}
        assert resolve_bar(rec) is None
        assert not is_frozen_pk_complete(None)

    def test_unparseable_bar_ts_fails_loud(self):
        with pytest.raises(ValueError):
            resolve_bar({"timestamp": "not-a-date"})


class TestJoinTable:
    def test_raw_index_joins_are_denied(self):
        denied = [j for j in JOIN_TABLE if j[4] == DENY_RAW_INDEX]
        assert denied, "expected at least one DENY_RAW_INDEX term"

    def test_position_join_is_denied(self):
        assert any(j[4] == DENY_POSITION_JOIN for j in JOIN_TABLE)

    def test_canonical_clock_join_is_allowed(self):
        allowed = [j for j in JOIN_TABLE if j[4] == ALLOW_JOIN_BAR_OPEN_TS]
        assert len(allowed) == 1
        assert allowed[0][1] == "bar_open_ts" and allowed[0][3] == "bar_open_ts"


class TestIdMintTable:
    def test_every_durable_id_is_recorded(self):
        ids = {m["id"] for m in ID_MINTS}
        for required in ("run_id", "trade_id", "execution_intent_id", "candidate_id"):
            assert required in ids

    def test_execution_intent_never_replaces_trade_id(self):
        mint = {m["id"]: m for m in ID_MINTS}["execution_intent_id"]
        assert "derived 1:1" in mint["scope"]
        trade_mint = {m["id"]: m for m in ID_MINTS}["trade_id"]
        assert "stays the journal/CSV trade_id" in trade_mint["scope"]