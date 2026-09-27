"""Unit tests for the engine telemetry closure (Phase 3) — the first invariant test.

Pins: CANDIDATE_LIFECYCLE ACCEPTED rows carry trade_id + bar_ts (additive), the runner can
recover the closed candidate_id from on_candidate_accepted, DECISION_DISTANCE rows carry
bar_ts, and the uniform identity envelope (invariant I1) is stamped on every record.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config_layer.crt_engine_v2 import TelemetryCollector
from governance.identity_spine import normalize_bar_ts, stamp_telemetry_envelope


def _collector():
    c = TelemetryCollector()
    c.on_candidate_opened("CAND-7", 7, "2026-09-22 09:00:00")
    return c


class TestAcceptedLifecycleClosure:
    def test_accepted_row_returns_candidate_id_and_lands_fields(self):
        c = _collector()
        cid = c.on_candidate_accepted(
            9,
            score_at_approval=0.8,
            candle_ts=dt.datetime(2026, 9, 22, 9, 0, 0),
            trade_id="CRT-0001",
        )
        assert cid == "CAND-7"
        records = c.flush()
        accepted = [r for r in records if r.get("kind") == "CANDIDATE_LIFECYCLE"
                    and r.get("death_reason") == "ACCEPTED"]
        assert len(accepted) == 1
        row = accepted[0]
        assert row["candidate_id"] == "CAND-7"
        assert row["trade_id"] == "CRT-0001"
        assert row["bar_ts"].startswith("2026-09-22")

    def test_accepted_without_active_candidate_returns_none(self):
        c = TelemetryCollector()
        assert c.on_candidate_accepted(3, trade_id="CRT-9999") is None

    def test_decision_distance_carries_bar_ts(self):
        c = TelemetryCollector()
        c.on_candidate_opened("CAND-1", 1, "2026-09-22 09:00:00")
        c.on_decision_distance(
            2, score_actual=0.5, score_threshold=0.6, accepted=False,
            rejection_reason="LOW_SCORE", soft_conf_candle_num=1,
            candle_ts=dt.datetime(2026, 9, 22, 9, 15, 0),
        )
        rows = c.flush()
        dd = [r for r in rows if r.get("kind") == "DECISION_DISTANCE"]
        assert len(dd) == 1
        assert normalize_bar_ts(dd[0]["bar_ts"]) == "2026-09-22 09:15:00"
        assert dd[0]["candle_index"] == 2

    def test_non_accepted_lifecycle_has_null_trade_fields(self):
        c = _collector()
        c.on_candidate_opened("CAND-8", 8, "2026-09-22 09:00:00")
        # soft-conf expiry closes the candidate without an acceptance
        c._close_candidate("SOFT_CONF_TIMEOUT", 20)
        rows = c.flush()
        closed = [r for r in rows if r.get("kind") == "CANDIDATE_LIFECYCLE"
                  and r.get("candidate_id") == "CAND-8"]
        assert len(closed) == 1
        assert closed[0]["trade_id"] is None and closed[0]["bar_ts"] is None


class TestTelemetryEnvelope:
    def test_envelope_stamped_on_every_record_without_mutation(self):
        raw = [
            {"kind": "CANDIDATE_LIFECYCLE", "candidate_id": "CAND-1"},
            {"kind": "DECISION_DISTANCE", "candle_index": 2},
        ]
        stamped = stamp_telemetry_envelope(
            raw,
            run_id="run_20260922_120000",
            instrument="XAUUSD",
            timeframe="M15",
            corpus_sha256="c0ffee" * 8,
        )
        for r in stamped:
            assert r["run_id"] == "run_20260922_120000"
            assert r["instrument"] == "XAUUSD"
            assert r["timeframe"] == "M15"
            assert r["corpus_sha256"] == "c0ffee" * 8
        # inputs untouched (no in-place mutation)
        assert "run_id" not in raw[0]

    def test_first_invariant_holds_on_real_collector_output(self):
        c = _collector()
        c.on_candidate_accepted(9, candle_ts=dt.datetime(2026, 9, 22, 9, 0, 0), trade_id="CRT-0001")
        stamped = stamp_telemetry_envelope(
            c.flush(), run_id="r", instrument="XAUUSD", timeframe="M15",
            corpus_sha256="h" * 64,
        )
        assert stamped, "collector should have produced records"
        for r in stamped:
            for key in ("run_id", "instrument", "timeframe", "corpus_sha256"):
                assert str(r.get(key) or "").strip(), f"{key} missing on {r.get('kind')}"