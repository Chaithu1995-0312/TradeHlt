"""Unit tests for the bar-clock bridge emitter (bar_identity.jsonl) — Phase 3.

Pins: the identity block on every row, the canonical bar_open_ts per bar, index pair
capture, buffered flush into the run dir, and the None-config semantics (absent section /
disabled = no emitter, exactly like the sibling observation emitters).
"""
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.bar_clock_bridge import (
    BarClockBridgeEmitter,
    BarClockConfig,
    BRIDGE_SCHEMA_VERSION,
)


def _cfg(tmp_path: Path, enabled: bool = True, flush_every: int = 2) -> BarClockConfig:
    return BarClockConfig(
        enabled=enabled,
        schema_version=BRIDGE_SCHEMA_VERSION,
        output_dir=str(tmp_path),
        filename_suffix="_bar_identity.jsonl",
        flush_every=flush_every,
    )


def _candle(iso_ts: str):
    from datetime import datetime
    return SimpleNamespace(timestamp=datetime.fromisoformat(iso_ts))


class TestEmitter:
    def test_emits_identity_plus_index_pair_and_canonical_clock(self, tmp_path):
        em = BarClockBridgeEmitter(
            _cfg(tmp_path),
            run_id="run_20260922_120000",
            instrument="XAUUSD",
            timeframe="M15",
            corpus_hash="c0ffee" * 8,
        )
        em.emit(candle=_candle("2026-09-22 09:00:00"), bar_index=40, engine_candle_index=6)
        em.close()
        rows = [json.loads(l) for l in Path(em.path).read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(rows) == 1
        r = rows[0]
        assert r["run_id"] == "run_20260922_120000"
        assert r["instrument"] == "XAUUSD"
        assert r["timeframe"] == "M15"
        assert r["corpus_sha256"] == "c0ffee" * 8
        assert r["bar_index"] == 40
        assert r["engine_candle_index"] == 6
        assert r["bar_open_ts"] == "2026-09-22 09:00:00"
        assert r["bar_ts"].startswith("2026-09-22")

    def test_engine_candle_index_can_be_absent(self, tmp_path):
        em = BarClockBridgeEmitter(
            _cfg(tmp_path), run_id="r", instrument="XAUUSD", timeframe="M15", corpus_hash="h" * 64,
        )
        em.emit(candle=_candle("2026-09-22 09:15:00"), bar_index=41)
        em.close()
        r = json.loads(Path(em.path).read_text(encoding="utf-8").splitlines()[0])
        assert r["engine_candle_index"] is None

    def test_flush_every_buffers_then_writes_all_rows(self, tmp_path):
        em = BarClockBridgeEmitter(
            _cfg(tmp_path, flush_every=2), run_id="r", instrument="XAUUSD", timeframe="M15",
            corpus_hash="h" * 64,
        )
        em.emit(candle=_candle("2026-09-22 09:00:00"), bar_index=0)
        assert em.rows_written == 1
        em.emit(candle=_candle("2026-09-22 09:15:00"), bar_index=1)
        assert em.rows_written == 2   # second emit triggers a flush at flush_every
        lines = Path(em.path).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2

    def test_disabled_config_is_a_noop(self, tmp_path):
        em = BarClockBridgeEmitter(
            _cfg(tmp_path, enabled=False), run_id="r", instrument="XAUUSD", timeframe="M15",
            corpus_hash="h" * 64,
        )
        em.emit(candle=_candle("2026-09-22 09:00:00"), bar_index=0)
        em.close()
        assert not Path(em.path).exists()
        assert em.rows_written == 0

    def test_from_prod_config_absent_section_is_none(self, monkeypatch):
        def raiser(*a, **k):
            raise RuntimeError("section absent (every pre-existing config)")
        monkeypatch.setattr("config_layer.production_config.get_prod_section", raiser)
        assert BarClockConfig.from_prod_config() is None

    def test_from_prod_config_enabled_false_is_none(self, monkeypatch):
        monkeypatch.setattr(
            "config_layer.production_config.get_prod_section",
            lambda *a, **k: {"enabled": False},
        )
        assert BarClockConfig.from_prod_config() is None