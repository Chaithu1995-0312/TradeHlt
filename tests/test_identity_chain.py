"""Golden-fixture + per-invariant negative tests for the 9-invariant chain checker (Phase 3).

The golden fixture is a tiny, self-consistent run dir: 2 accepted trades wired through
trades.csv, crt_telemetry.jsonl, layer_trace L8 rows, labels.csv, and bar_identity.jsonl on
the SAME bar clock. Every negative fixture mutates exactly one stream so exactly one
invariant FAILs — the mechanical proof that each invariant is fail-loud and independent.
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

from governance.identity_chain import FAIL, PASS, SKIP, check_run

CORPUS = "5" * 64
RUN_ID = "run_20260922_120000"
INSTRUMENT = "XAUUSD"
TIMEFRAME = "M15"


def _telemetry_rows(overrides=None):
    """Two ACCEPTED lifecycles (CRT-0001 @ 09:00, CRT-0002 @ 10:00) + soft-conf decisions."""
    rows = [
        {
            "kind": "CANDIDATE_LIFECYCLE", "candidate_id": "CAND-7",
            "first_seen_idx": 7, "first_seen_ts": "2026-09-22 09:00:00",
            "last_seen_idx": 9, "age_candles": 2,
            "entered_states": ["SWEEP", "EXPANSION"], "max_score_seen": 0.9,
            "shadow_used": False, "score_at_approval": 0.8,
            "shadow_context": {}, "shadow_displacement_br": 0.0,
            "trade_id": "CRT-0001", "bar_ts": "2026-09-22 09:00:00",
            "death_reason": "ACCEPTED",
        },
        {
            "kind": "CANDIDATE_LIFECYCLE", "candidate_id": "CAND-9",
            "first_seen_idx": 40, "first_seen_ts": "2026-09-22 10:00:00",
            "last_seen_idx": 42, "age_candles": 2,
            "entered_states": ["SWEEP", "EXPANSION", "RETEST"], "max_score_seen": 0.95,
            "shadow_used": False, "score_at_approval": 0.9,
            "shadow_context": {}, "shadow_displacement_br": 0.0,
            "trade_id": "CRT-0002", "bar_ts": "2026-09-22 10:00:00",
            "death_reason": "ACCEPTED",
        },
        {
            "kind": "DECISION_DISTANCE", "candle_index": 8, "candidate_id": "CAND-7",
            "bar_ts": "2026-09-22 09:15:00", "score_actual": 0.72, "score_threshold": 0.6,
            "decision_distance": 0.12, "accepted": True, "rejection_reason": "APPROVED",
            "soft_conf_candle_num": 2,
        },
        {
            "kind": "DECISION_DISTANCE", "candle_index": 41, "candidate_id": "CAND-9",
            "bar_ts": "2026-09-22 10:15:00", "score_actual": 0.9, "score_threshold": 0.6,
            "decision_distance": 0.3, "accepted": True, "rejection_reason": "APPROVED",
            "soft_conf_candle_num": 1,
        },
    ]
    for r in rows:
        r.setdefault("run_id", RUN_ID)
        r.setdefault("instrument", INSTRUMENT)
        r.setdefault("timeframe", TIMEFRAME)
        r.setdefault("corpus_sha256", CORPUS)
    if overrides:
        for idx, key, value in overrides:
            rows[idx][key] = value
    return rows


def _trades_rows():
    # [CH-measurement-basis-declaration] the 5-axis basis I9 verifies. Values match
    # what backtest_v2.py actually stamps (walk_kernel=backtest_ledger,
    # reference_level=displacement_extreme, fill_model_id=engine_intrabar).
    basis = {
        "walk_kernel": "backtest_ledger", "cost_model_id": "backtest_g1g2_v2",
        "fill_model_id": "engine_intrabar", "tie_break": "production",
        "reference_level": "displacement_extreme", "sl_refloored": "0",
    }
    return [
        {"trade_id": "CRT-0001", "candidate_id": "CAND-7", "instrument": INSTRUMENT,
         "opened_at": "2026-09-22 09:00:00", "candle_open": 12, "direction": "LONG",
         "entry_raw": "1.0", "pnl_rr_net": "0.5", **basis},
        {"trade_id": "CRT-0002", "candidate_id": "CAND-9", "instrument": INSTRUMENT,
         "opened_at": "2026-09-22 10:00:00", "candle_open": 52, "direction": "SHORT",
         "entry_raw": "1.0", "pnl_rr_net": "-0.2", **basis},
    ]


def _layer_rows():
    return [
        {"bar_idx": 12, "bar_ts": "2026-09-22 09:00:00", "layer": "L8",
         "status": "PASS", "module": "config_layer.crt_engine_v2.Trade",
         "trade_id": "CRT-0001", "output_hash": "CRT-0001",
         "run_id": RUN_ID, "instrument": INSTRUMENT, "timeframe": TIMEFRAME,
         "corpus_sha256": CORPUS},
        {"bar_idx": 52, "bar_ts": "2026-09-22 10:00:00", "layer": "L8",
         "status": "PASS", "module": "config_layer.crt_engine_v2.Trade",
         "trade_id": "CRT-0002", "output_hash": "CRT-0002",
         "run_id": RUN_ID, "instrument": INSTRUMENT, "timeframe": TIMEFRAME,
         "corpus_sha256": CORPUS},
        {"bar_idx": -1, "bar_ts": None, "layer": "L0", "status": "PASS",
         "module": "data_ingestion", "trade_id": None,
         "run_id": RUN_ID, "instrument": INSTRUMENT, "timeframe": TIMEFRAME,
         "corpus_sha256": CORPUS},
        # L3 rows for I8 (label_trace_resolution) — one per golden-fixture label bar
        # (_pos 0 -> 09:00:00, _pos 1 -> 09:15:00), plus a spare bar so the join has
        # more than a 1:1 coincidence to prove.
        {"bar_idx": 0, "bar_ts": "2026-09-22 09:00:00", "layer": "L3",
         "status": "PASS", "module": "config_layer.crt_engine_v2",
         "trade_id": None, "output_hash": "CRTState.RANGE",
         "run_id": RUN_ID, "instrument": INSTRUMENT, "timeframe": TIMEFRAME,
         "corpus_sha256": CORPUS},
        {"bar_idx": 1, "bar_ts": "2026-09-22 09:15:00", "layer": "L3",
         "status": "PASS", "module": "config_layer.crt_engine_v2",
         "trade_id": None, "output_hash": "CRTState.SWEEP",
         "run_id": RUN_ID, "instrument": INSTRUMENT, "timeframe": TIMEFRAME,
         "corpus_sha256": CORPUS},
    ]


def _bar_identity_rows():
    return [
        {"bar_index": i, "engine_candle_index": i - 12, "bar_ts": ts,
         "bar_open_ts": ts, "run_id": RUN_ID, "instrument": INSTRUMENT,
         "timeframe": TIMEFRAME, "corpus_sha256": CORPUS}
        for i, ts in enumerate((
            "2026-09-22 09:00:00", "2026-09-22 09:15:00", "2026-09-22 09:30:00",
            "2026-09-22 09:45:00", "2026-09-22 10:00:00",
        ))
    ]


def _label_rows():
    # [CH-measurement-basis-declaration] the 5-axis basis I9 verifies. Values match
    # what labeler.py's PRIMARY arm actually stamps (sl_geom=disp_bar maps to
    # reference_level=signal_bar_extreme; see labeler.py's own C2 comment).
    basis = {
        "sl_geom": "disp_bar", "tie_break": "production",
        "walk_kernel": "multi_tp_walk", "cost_model_id": "sem015_component_xauusd",
        "fill_model_id": "sem016_adverse", "reference_level": "signal_bar_extreme",
    }
    return [
        {"_pos": 0, "timestamp": "2026-09-22 09:00:00", "dataset_hash": CORPUS,
         "label_run_id": "LABEL_tag_20260922_120000", "label_generated_utc": "2026-09-22T12:00:00",
         "direction": "LONG", "outcome": "WIN",
         "lt_id": RUN_ID, "bar_open_ts": "2026-09-22 09:00:00",
         "trace_id": f"{RUN_ID}:{INSTRUMENT}:2026-09-22T09:00:00", **basis},
        {"_pos": 1, "timestamp": "2026-09-22 09:15:00", "dataset_hash": CORPUS,
         "label_run_id": "LABEL_tag_20260922_120000", "label_generated_utc": "2026-09-22T12:00:00",
         "direction": "SHORT", "outcome": "LOSS",
         "lt_id": RUN_ID, "bar_open_ts": "2026-09-22 09:15:00",
         "trace_id": f"{RUN_ID}:{INSTRUMENT}:2026-09-22T09:15:00", **basis},
    ]
# SEAM-1


def _write_fixture(tmp_path: Path, *, tel_overrides=None, trades=None, layer=None,
                   labels=None, bar_identity=None):
    tel = tmp_path / "crt_telemetry.jsonl"
    with tel.open("w", encoding="utf-8") as fh:
        for r in _telemetry_rows(tel_overrides):
            fh.write(json.dumps(r) + "\n")
    tr = tmp_path / "trades.csv"
    with tr.open("w", encoding="utf-8", newline="") as fh:
        rows = trades if trades is not None else _trades_rows()
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    lt = tmp_path / "layer_trace.jsonl"
    with lt.open("w", encoding="utf-8") as fh:
        for r in (layer if layer is not None else _layer_rows()):
            fh.write(json.dumps(r) + "\n")
    bi = tmp_path / "bar_identity.jsonl"
    with bi.open("w", encoding="utf-8") as fh:
        for r in (bar_identity if bar_identity is not None else _bar_identity_rows()):
            fh.write(json.dumps(r) + "\n")
    lb = tmp_path / "labels.csv"
    lbls = labels if labels is not None else _label_rows()
    with lb.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=lbls[0].keys())
        w.writeheader()
        w.writerows(lbls)
    return {
        "telemetry": tel, "trades": tr, "layer_trace": lt, "labels": lb,
        "bar_identity": bi,
    }


def _run(tmp_path, *, require_all=False, **paths):
    return check_run(
        telemetry_path=paths.get("telemetry") or tmp_path / "crt_telemetry.jsonl",
        trades_path=paths.get("trades") or tmp_path / "trades.csv",
        layer_trace_path=paths.get("layer_trace") or tmp_path / "layer_trace.jsonl",
        labels_path=paths.get("labels") or tmp_path / "labels.csv",
        bar_identity_path=paths.get("bar_identity") or tmp_path / "bar_identity.jsonl",
        corpus_sha256=CORPUS,
        require_all=require_all,
    )


def _status_for(outcomes, inv):
    return next(o.status for o in outcomes if o.invariant == inv)
# SEAM-2


class TestGoldenFixture:
    def test_all_nine_invariants_pass(self, tmp_path):
        _write_fixture(tmp_path)
        ok, outcomes = _run(tmp_path)
        assert ok, [o.detail for o in outcomes if o.status == FAIL]
        for inv in ("I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9"):
            assert _status_for(outcomes, inv) == PASS, inv

    def test_partial_inputs_gracefully_skip(self, tmp_path):
        _write_fixture(tmp_path)
        ok, outcomes = check_run(telemetry_path=tmp_path / "crt_telemetry.jsonl",
                                 trades_path=tmp_path / "trades.csv")
        assert ok
        assert _status_for(outcomes, "I5") == SKIP      # no layer-trace input
        assert _status_for(outcomes, "I7") == SKIP      # no labels input
        assert _status_for(outcomes, "I1") == PASS

    def test_require_all_passes_only_when_every_invariant_is_verified(self, tmp_path):
        _write_fixture(tmp_path)
        ok, outcomes = _run(tmp_path, require_all=True)
        assert ok, [(o.invariant, o.status, o.detail) for o in outcomes if o.status != PASS]
        for inv in ("I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9"):
            assert _status_for(outcomes, inv) == PASS, inv

    def test_require_all_fails_a_partial_run_that_default_mode_passes(self, tmp_path):
        _write_fixture(tmp_path)
        # Same telemetry+trades-only inputs as test_partial_inputs_gracefully_skip: default
        # mode is ok=True there. require_all must flip that same input set to ok=False.
        lenient_ok, _ = check_run(telemetry_path=tmp_path / "crt_telemetry.jsonl",
                                  trades_path=tmp_path / "trades.csv")
        strict_ok, outcomes = check_run(telemetry_path=tmp_path / "crt_telemetry.jsonl",
                                        trades_path=tmp_path / "trades.csv",
                                        require_all=True)
        assert lenient_ok and not strict_ok
        assert _status_for(outcomes, "I5") == SKIP      # outcomes are unchanged by the mode
        assert _status_for(outcomes, "I7") == SKIP


class TestNegativeFixtures:
    def test_i1_envelope_non_uniform(self, tmp_path):
        _write_fixture(tmp_path, tel_overrides=[(0, "instrument", "")])
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I1") == FAIL

    def test_i2_accepted_missing_trade_id(self, tmp_path):
        _write_fixture(tmp_path, tel_overrides=[(1, "trade_id", None)])
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I2") == FAIL

    def test_i3_backwards_bar_clock(self, tmp_path):
        _write_fixture(tmp_path, tel_overrides=[(3, "bar_ts", "2026-09-22 09:00:00")])
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I3") == FAIL

    def test_i4_candidate_not_in_lifecycle(self, tmp_path):
        trades = _trades_rows()
        trades[0]["candidate_id"] = "CAND-404"
        _write_fixture(tmp_path, trades=trades)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I4") == FAIL

    def test_i4_duplicate_candidate_in_trades(self, tmp_path):
        trades = _trades_rows()
        trades = [dict(trades[0]), trades[0]]
        _write_fixture(tmp_path, trades=trades)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I4") == FAIL

    def test_i5_l8_bar_ts_mismatch(self, tmp_path):
        layer = _layer_rows()
        layer[0]["bar_ts"] = "2026-09-22 09:15:00"
        _write_fixture(tmp_path, layer=layer)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I5") == FAIL

    def test_i6_stray_l8_trade(self, tmp_path):
        layer = _layer_rows() + [dict(_layer_rows()[0], trade_id="CRT-9999",
                                      bar_ts="2026-09-22 11:00:00")]
        _write_fixture(tmp_path, layer=layer)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I6") == FAIL

    def _vetoed_fixture(self):
        """CRT-0002 committed (ACCEPTED lifecycle) then vetoed post-commit: no trades.csv row,
        no L8 row — the shape of k23 lt_20260924_194133 CRT-0024."""
        trades = [t for t in _trades_rows() if t["trade_id"] != "CRT-0002"]
        layer = [r for r in _layer_rows() if r.get("trade_id") != "CRT-0002"]
        return trades, layer

    def test_i5_i6_post_commit_veto_with_l5_evidence_passes(self, tmp_path):
        trades, layer = self._vetoed_fixture()
        layer.append(dict(layer[0], layer="L5", status="REJECT", trade_id="CRT-0002",
                          bar_idx=52, bar_ts="2026-09-22 10:00:00",
                          module="core.engine_runner.EngineRunner"))
        _write_fixture(tmp_path, trades=trades, layer=layer)
        ok, outcomes = _run(tmp_path)
        assert _status_for(outcomes, "I5") == PASS
        assert _status_for(outcomes, "I6") == PASS

    def test_i5_i6_post_commit_veto_without_evidence_fails(self, tmp_path):
        trades, layer = self._vetoed_fixture()
        _write_fixture(tmp_path, trades=trades, layer=layer)
        ok, outcomes = _run(tmp_path)
        assert not ok
        assert _status_for(outcomes, "I5") == FAIL
        assert _status_for(outcomes, "I6") == FAIL

    def test_i6_vetoed_trade_leaking_into_l8_fails(self, tmp_path):
        layer = _layer_rows() + [dict(_layer_rows()[1], layer="L5", status="REJECT",
                                      module="core.engine_runner.EngineRunner")]
        _write_fixture(tmp_path, layer=layer)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I6") == FAIL

    def test_i5_i6_ignore_foreign_run_l8_rows_without_manifest(self, tmp_path):
        """The layer-trace file may be shared across many runs (no per-run rotation yet,
        `docs/memory/identity-chain-memory.md` backlog item A). `trade_id` is minted
        per-run, not globally unique — a DIFFERENT run reusing the SAME trade_id at the
        SAME bar must not be mistaken for a duplicate of THIS run's trade. No run_manifest
        supplied, so I5/I6 fall back to telemetry's own run_id to scope the L8 lookup."""
        foreign = [dict(r, run_id="run_FOREIGN_20260101_000000") for r in _layer_rows()
                   if r["layer"] == "L8"]
        layer = _layer_rows() + foreign
        _write_fixture(tmp_path, layer=layer)
        ok, outcomes = _run(tmp_path)
        assert ok, [(o.invariant, o.detail) for o in outcomes if o.status == FAIL]
        assert _status_for(outcomes, "I5") == PASS
        assert _status_for(outcomes, "I6") == PASS

    def test_i5_i6_use_run_manifest_layer_trace_id_when_telemetry_run_id_differs(self, tmp_path):
        """F-101: the telemetry envelope's run_id (canonical/ReportWriter id) and the
        layer-trace subsystem's own run_id are two DIFFERENT strings for the same physical
        run. Without the manifest's layer_trace_id pointer, telemetry's run_id doesn't match
        the layer rows' run_id at all, and I5/I6 correctly refuse (0 L8 rows resolve) rather
        than silently matching the wrong run. With the manifest, they resolve correctly."""
        layer = [dict(r, run_id="lt_20260922_999999_XAUUSD") if r["layer"] == "L8" else r
                 for r in _layer_rows()]
        _write_fixture(tmp_path, layer=layer)

        ok, outcomes = check_run(
            telemetry_path=tmp_path / "crt_telemetry.jsonl",
            trades_path=tmp_path / "trades.csv",
            layer_trace_path=tmp_path / "layer_trace.jsonl",
            labels_path=tmp_path / "labels.csv",
            bar_identity_path=tmp_path / "bar_identity.jsonl",
            corpus_sha256=CORPUS,
        )
        assert not ok
        assert _status_for(outcomes, "I5") == FAIL
        assert _status_for(outcomes, "I6") == FAIL

        manifest_path = tmp_path / "run_manifest.json"
        manifest_path.write_text(
            json.dumps({"layer_trace_id": "lt_20260922_999999_XAUUSD"}), encoding="utf-8"
        )
        ok, outcomes = check_run(
            telemetry_path=tmp_path / "crt_telemetry.jsonl",
            trades_path=tmp_path / "trades.csv",
            layer_trace_path=tmp_path / "layer_trace.jsonl",
            labels_path=tmp_path / "labels.csv",
            bar_identity_path=tmp_path / "bar_identity.jsonl",
            corpus_sha256=CORPUS,
            run_manifest_path=manifest_path,
        )
        assert ok, [(o.invariant, o.detail) for o in outcomes if o.status == FAIL]
        assert _status_for(outcomes, "I5") == PASS
        assert _status_for(outcomes, "I6") == PASS

    def test_i7_labels_missing_lineage_column(self, tmp_path):
        labels = [{k: v for k, v in r.items() if k != "dataset_hash"}
                  for r in _label_rows()]
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I7") == FAIL

    def test_i8_label_with_no_l3_row_fails(self, tmp_path):
        labels = _label_rows()
        labels[0]["bar_open_ts"] = "2026-09-22 23:45:00"    # no L3 row at this bar_open_ts
        labels[0]["trace_id"] = f"{RUN_ID}:{INSTRUMENT}:2026-09-22T23:45:00"
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I8") == FAIL

    def test_i8_trace_id_timestamp_disagrees_with_bar_open_ts_fails(self, tmp_path):
        """The two identity columns were copied from different bars — must FAIL, not
        silently join on whichever one happens to resolve."""
        labels = _label_rows()
        labels[0]["trace_id"] = f"{RUN_ID}:{INSTRUMENT}:2026-09-22T09:15:00"  # bar 1's ts
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I8") == FAIL

    def test_i8_two_lt_ids_in_one_label_file_fails(self, tmp_path):
        labels = _label_rows()
        labels[1]["lt_id"] = "run_20260921_000000"
        labels[1]["trace_id"] = f"run_20260921_000000:{INSTRUMENT}:2026-09-22T09:15:00"
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I8") == FAIL

    def test_i8_blank_lt_id_fails(self, tmp_path):
        labels = _label_rows()
        labels[0]["lt_id"] = ""
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I8") == FAIL

    def test_i8_missing_join_columns_fails(self, tmp_path):
        labels = [{k: v for k, v in r.items() if k not in ("lt_id", "trace_id")}
                  for r in _label_rows()]
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I8") == FAIL

    def test_i8_skips_without_layer_trace(self, tmp_path):
        _write_fixture(tmp_path)
        ok, outcomes = check_run(
            telemetry_path=tmp_path / "crt_telemetry.jsonl",
            trades_path=tmp_path / "trades.csv",
            labels_path=tmp_path / "labels.csv",
            corpus_sha256=CORPUS,
        )
        assert ok
        assert _status_for(outcomes, "I8") == SKIP

    def test_i8_skip_under_require_all_is_a_violation(self, tmp_path):
        _write_fixture(tmp_path)
        ok, outcomes = check_run(
            telemetry_path=tmp_path / "crt_telemetry.jsonl",
            trades_path=tmp_path / "trades.csv",
            labels_path=tmp_path / "labels.csv",
            corpus_sha256=CORPUS,
            require_all=True,
        )
        assert not ok
        assert _status_for(outcomes, "I8") == SKIP

    # ── I9 (CH-measurement-basis-declaration) ───────────────────────────────
    def test_i9_blank_axis_on_label_fails(self, tmp_path):
        labels = _label_rows()
        labels[0]["tie_break"] = ""
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I9") == FAIL

    def test_i9_unrecognised_axis_value_on_trades_fails(self, tmp_path):
        trades = _trades_rows()
        trades[0]["cost_model_id"] = "some_made_up_model_id"
        _write_fixture(tmp_path, trades=trades)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I9") == FAIL

    def test_i9_explicit_unstamped_axis_fails(self, tmp_path):
        """UNSTAMPED is a legal VALUE for can_compare to refuse on, but a row that
        declares it explicitly has not actually declared its basis — I9 must FAIL,
        not silently accept it as a valid declaration."""
        labels = _label_rows()
        labels[0]["reference_level"] = "UNSTAMPED"
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I9") == FAIL

    def test_i9_missing_axis_column_entirely_fails(self, tmp_path):
        labels = [{k: v for k, v in r.items() if k != "walk_kernel"} for r in _label_rows()]
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert not ok and _status_for(outcomes, "I9") == FAIL

    def test_i9_distinct_bases_in_one_file_does_not_itself_fail(self, tmp_path):
        """Two rows correctly declaring DIFFERENT bases is not an I9 violation — that
        is exactly what can_compare exists to name (DENY_*), not a declaration defect.
        I9 only fails on a bad/absent declaration, never on a real mismatch."""
        labels = _label_rows()
        labels[1]["tie_break"] = "optimistic"   # a second, legitimately different arm
        _write_fixture(tmp_path, labels=labels)
        ok, outcomes = _run(tmp_path)
        assert ok and _status_for(outcomes, "I9") == PASS

    def test_i9_skips_without_labels_or_trades(self, tmp_path):
        _write_fixture(tmp_path)
        ok, outcomes = check_run(telemetry_path=tmp_path / "crt_telemetry.jsonl")
        assert ok
        assert _status_for(outcomes, "I9") == SKIP

    def test_i9_skip_under_require_all_is_a_violation(self, tmp_path):
        _write_fixture(tmp_path)
        ok, outcomes = check_run(
            telemetry_path=tmp_path / "crt_telemetry.jsonl", require_all=True,
        )
        assert not ok
        assert _status_for(outcomes, "I9") == SKIP

    def test_i9_golden_fixture_trades_only_passes(self, tmp_path):
        """trades_path alone (no labels_path) is enough to activate I9 — it does not
        require both streams, only at least one outcome-bearing stream to check."""
        _write_fixture(tmp_path)
        ok, outcomes = check_run(
            telemetry_path=tmp_path / "crt_telemetry.jsonl",
            trades_path=tmp_path / "trades.csv",
        )
        assert ok
        assert _status_for(outcomes, "I9") == PASS
# SEAM-3


class TestCli:
    def test_cli_exit_codes(self, tmp_path):
        _write_fixture(tmp_path)
        base = [sys.executable, "scripts/governance/identity_chain_check.py",
                "--telemetry", str(tmp_path / "crt_telemetry.jsonl"),
                "--trades", str(tmp_path / "trades.csv"),
                "--layer-trace", str(tmp_path / "layer_trace.jsonl"),
                "--labels", str(tmp_path / "labels.csv"),
                "--bar-identity", str(tmp_path / "bar_identity.jsonl"),
                "--corpus-sha256", CORPUS]
        r = subprocess.run(base, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stdout + r.stderr
        _write_fixture(tmp_path, tel_overrides=[(0, "instrument", "")])
        r = subprocess.run(base, capture_output=True, text=True, timeout=180)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "I1" in r.stdout and "VIOLATED" in r.stdout

    def test_partial_run_exits_zero_but_discloses_partiality(self, tmp_path):
        _write_fixture(tmp_path)
        r = subprocess.run(
            [sys.executable, "scripts/governance/identity_chain_check.py",
             "--telemetry", str(tmp_path / "crt_telemetry.jsonl"),
             "--trades", str(tmp_path / "trades.csv")],
            capture_output=True, text=True, timeout=180,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "CLOSED" in r.stdout
        assert "PARTIAL" in r.stdout   # the exit code alone must not read as "fully verified"

    def test_require_all_rejects_the_same_partial_run(self, tmp_path):
        _write_fixture(tmp_path)
        base = [sys.executable, "scripts/governance/identity_chain_check.py",
                "--telemetry", str(tmp_path / "crt_telemetry.jsonl"),
                "--trades", str(tmp_path / "trades.csv")]
        r = subprocess.run(base + ["--require-all"], capture_output=True, text=True, timeout=180)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "VIOLATED" in r.stdout

    def test_require_all_accepts_the_golden_fixture(self, tmp_path):
        _write_fixture(tmp_path)
        r = subprocess.run(
            [sys.executable, "scripts/governance/identity_chain_check.py",
             "--telemetry", str(tmp_path / "crt_telemetry.jsonl"),
             "--trades", str(tmp_path / "trades.csv"),
             "--layer-trace", str(tmp_path / "layer_trace.jsonl"),
             "--labels", str(tmp_path / "labels.csv"),
             "--bar-identity", str(tmp_path / "bar_identity.jsonl"),
             "--corpus-sha256", CORPUS, "--require-all"],
            capture_output=True, text=True, timeout=180,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "CLOSED" in r.stdout
        assert "PARTIAL" not in r.stdout