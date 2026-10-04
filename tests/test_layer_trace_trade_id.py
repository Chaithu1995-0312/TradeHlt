"""Unit tests for the L8 named trade_id column on layer_trace rows (Phase 3).

Pins: every emit() path (per-bar and run-scoped) records the trade_id key (None when the
caller does not supply it — uniform column, no missing-key drift), and the L8 row carries
the engine CRT trade_id verbatim.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.layer_trace import LayerTraceConfig, LayerTraceEmitter, TRACE_SCHEMA_VERSION


def _emitter(tmp_path: Path) -> LayerTraceEmitter:
    cfg = LayerTraceConfig(
        enabled=True,
        schema_version=TRACE_SCHEMA_VERSION,
        output_dir=str(tmp_path),
        filename_suffix="_layer_trace.jsonl",
        flush_every=100,
    )
    return LayerTraceEmitter(
        cfg,
        run_id="lt_20260922_120000_XAUUSD",
        instrument="XAUUSD",
        timeframe="M15",
        active_version="v2_htfcrt_2026_08",
        config_hash="c" * 64,
        schema_hash="s" * 64,
        dataset_id="d" * 64,
        corpus_path="data/XAUUSD_M15.csv",
        corpus_rows=10,
        corpus_sha256="c0ffee" * 8,
        code_sha="k" * 40,
        tree_dirty=False,
        rail="backtest",
        preexisting_run_ids={"Runner": "run_20260922_120000"},
    )


class TestTradeIdColumn:
    def test_l8_row_carries_named_trade_id(self, tmp_path):
        em = _emitter(tmp_path)
        em.emit(
            trace_id="lt_x:12", bar_idx=12, bar_ts=__import__("datetime").datetime(2026, 9, 22, 9, 0, 0),
            layer="L8", module="config_layer.crt_engine_v2.Trade", status="PASS",
            output_hash="CRT-0007", trade_id="CRT-0007",
        )
        em.close()
        rows = [json.loads(l) for l in Path(em.path).read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(rows) == 1
        assert rows[0]["trade_id"] == "CRT-0007"
        assert rows[0]["output_hash"] == "CRT-0007"   # same engine id, additive naming

    def test_emit_without_trade_id_records_none_uniformly(self, tmp_path):
        em = _emitter(tmp_path)
        em.emit(
            trace_id="lt_x:0", bar_idx=0, bar_ts=None,
            layer="L0", module="data_ingestion", status="PASS",
        )
        em.emit_not_reached_once(layer="L7", module="core.ultron_risk_gate", note="backtest rail")
        em.close()
        rows = [json.loads(l) for l in Path(em.path).read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(rows) == 2
        for r in rows:
            assert "trade_id" in r and r["trade_id"] is None   # key present on every row path

    def test_all_layer_trace_rows_have_uniform_keys(self, tmp_path):
        em = _emitter(tmp_path)
        em.emit(
            trace_id="a:1", bar_idx=1, bar_ts=__import__("datetime").datetime(2026, 9, 22, 9, 0, 0),
            layer="L3", module="config_layer.crt_engine_v2", status="PASS",
        )
        em.emit(
            trace_id="a:1", bar_idx=1, bar_ts=__import__("datetime").datetime(2026, 9, 22, 9, 0, 0),
            layer="L8", module="config_layer.crt_engine_v2.Trade", status="PASS",
            output_hash="CRT-0001", trade_id="CRT-0001",
        )
        em.close()
        rows = [json.loads(l) for l in Path(em.path).read_text(encoding="utf-8").splitlines() if l.strip()]
        key_sets = {frozenset(r.keys()) for r in rows}
        assert len(key_sets) == 1   # one uniform schema across all rows (L3 + L8)