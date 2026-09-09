"""Phase 4 floor: certify the live decision rail against deterministic historical replay.

This is an INTEGRATION certification, not an economic one. It proves a historical bar
can travel raw OHLCV -> canonical features -> FeatureStore -> HookedLiveEngine.process
-> a recorded decision, deterministically, with no orders. It makes no claim about
whether those decisions are profitable. F-073 stays OPEN (no production loop) and
F-010 stays OPEN (no exit loop).

Guards the defect these tests were written for: `_feature_store` was assigned without
a `global` declaration, so the canonical ingestion boundary never ran and every live
bar died inside ZoneGate with 29 of 48 canonical keys missing.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from config_layer.crt_engine_v2 import Candle
from inout.live_rail.bar_builder import BarBuilder
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.ohlcv_replay_port import (
    OhlcvTickReplayPort,
    assert_round_trip,
    bar_to_ticks,
    load_corpus_bars,
    read_corpus_rows,
)
from inout.live_rail.types import ClockBasis, VenueName
from runtime.live_rail_orchestrator import LiveRailOrchestrator, summarize_audit

_CORPUS = Path("data/mt5/XAUUSD_M15.csv")
_RUN_CFG = Path("configs/experimental/spec/live_rail_tickdb_paper_run.json")
# 78 warmup rows are dropped by FeaturePipeline.finalize, so this leaves 22 decided bars.
_LIMIT = 100

requires_corpus = pytest.mark.skipif(
    not _CORPUS.is_file(),
    reason=f"historical corpus {_CORPUS} not present (gitignored data tree)",
)


def _cfg() -> LiveRailConfig:
    section = json.loads(_RUN_CFG.read_text(encoding="utf-8"))["live_rail"]
    return LiveRailConfig.from_prod_config(section)


def _run_arm_a(tmp_path: Path, limit: int = _LIMIT) -> tuple[LiveRailOrchestrator, Path]:
    os.environ["LIVE_ENGINE_ENABLED"] = "1"
    cfg = _cfg()
    report = tmp_path / "audit.jsonl"
    orch = LiveRailOrchestrator.from_config(cfg, report_path=report)
    bars = load_corpus_bars(_CORPUS, cfg, limit=limit)
    asyncio.run(orch.run_bars(bars))
    return orch, report


def _records(report: Path) -> list[dict]:
    return [json.loads(l) for l in report.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── corpus reader ────────────────────────────────────────────────────────────────

def test_corpus_reader_rejects_missing_columns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("timestamp,open,high,low\n2024-01-01 00:00:00,1,2,0.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        read_corpus_rows(bad)


def test_corpus_reader_rejects_non_monotonic_timestamps(tmp_path: Path) -> None:
    bad = tmp_path / "rev.csv"
    bad.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2024-01-01 01:00:00,1,2,0.5,1.5,10\n"
        "2024-01-01 00:45:00,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-monotonic"):
        read_corpus_rows(bad)


# ── Arm B round trip: the assertion that keeps the arm honest ────────────────────

def _synthetic_rows(n: int) -> list[dict]:
    base = datetime(2024, 5, 22, 1, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        o = 2400.0 + i
        rows.append({
            "timestamp": base + timedelta(minutes=15 * i),
            "open": o, "high": o + 3.0, "low": o - 2.0, "close": o + 1.0,
            "volume": 100.0 + i,
        })
    return rows


def test_bar_to_ticks_round_trips_through_bar_builder() -> None:
    """O/H/L/C expansion must rebuild the source bar exactly, or Arm B is a fiction."""
    cfg = _cfg()
    rows = _synthetic_rows(5)
    builder = BarBuilder(cfg)
    produced = []
    seq = 1
    for row in rows:
        for tick in bar_to_ticks(
            row, symbol=cfg.symbol, clock_basis=cfg.clock_basis,
            venue=cfg.data_venue, seq_start=seq,
        ):
            closed = builder.on_tick(tick)
            if closed is not None:
                produced.append(closed)
        seq += 4
    # BarBuilder closes on the NEXT period's first tick, so the last row never emits.
    assert len(produced) == len(rows) - 1
    assert_round_trip(rows[:-1], produced)


def test_round_trip_assertion_actually_fails_on_a_mismatch() -> None:
    """A guard that cannot fail is not a guard (E-001)."""
    cfg = _cfg()
    rows = _synthetic_rows(3)
    builder = BarBuilder(cfg)
    produced = []
    seq = 1
    for row in rows:
        for tick in bar_to_ticks(
            row, symbol=cfg.symbol, clock_basis=cfg.clock_basis,
            venue=cfg.data_venue, seq_start=seq,
        ):
            closed = builder.on_tick(tick)
            if closed is not None:
                produced.append(closed)
        seq += 4
    corrupted = [dict(r) for r in rows[:-1]]
    corrupted[0]["high"] = corrupted[0]["high"] + 1.0
    with pytest.raises(AssertionError, match="round-trip"):
        assert_round_trip(corrupted, produced)


# ── Phase 4 certification criteria ───────────────────────────────────────────────

@requires_corpus
def test_every_attempt_returns_a_decision(tmp_path: Path) -> None:
    """The regression guard for the missing `global`.

    Before the fix this was attempts=N, calls=0, every record an engine error raised
    inside ZoneGate because FeatureStore had never been constructed.
    """
    orch, report = _run_arm_a(tmp_path)
    assert orch.process_calls > 0, "no bar reached HookedLiveEngine.process"
    assert orch.process_attempts == orch.process_calls, (
        f"{orch.process_attempts - orch.process_calls} attempts raised inside process()"
    )
    counts = summarize_audit(report)
    assert counts.get("ENGINE_ERROR", 0) == 0, f"engine errors: {counts}"
    assert counts.get("FEEDER_REJECT", 0) == 0, f"feeder rejects: {counts}"


@requires_corpus
def test_one_terminal_record_per_decided_bar(tmp_path: Path) -> None:
    orch, report = _run_arm_a(tmp_path)
    recs = _records(report)
    terminal = {"NO_ORDER", "FILL", "PREFLIGHT_REJECT", "HUMAN_GATE"}
    assert len(recs) == orch.process_calls
    assert all(r["kind"] in terminal for r in recs), {r["kind"] for r in recs}


@requires_corpus
def test_replay_is_deterministic(tmp_path: Path) -> None:
    """Same corpus slice twice -> identical records once wall-clock ts is excluded."""
    def _norm(report: Path) -> list[str]:
        out = []
        for rec in _records(report):
            rec.pop("ts", None)
            out.append(json.dumps(rec, sort_keys=True))
        return out

    _, r1 = _run_arm_a(tmp_path / "a")
    _, r2 = _run_arm_a(tmp_path / "b")
    assert _norm(r1) == _norm(r2)


@requires_corpus
def test_certification_run_places_no_orders(tmp_path: Path) -> None:
    orch, report = _run_arm_a(tmp_path)
    assert orch._ctx.cfg.dry_run is True
    assert orch._ctx.cfg.hook_submit_orders is False
    assert summarize_audit(report).get("FILL", 0) == 0


@requires_corpus
def test_arm_b_ticks_reach_decisions(tmp_path: Path) -> None:
    os.environ["LIVE_ENGINE_ENABLED"] = "1"
    cfg = _cfg()
    report = tmp_path / "audit.jsonl"
    port = OhlcvTickReplayPort(cfg, _CORPUS, limit=_LIMIT)
    orch = LiveRailOrchestrator.from_config(cfg, report_path=report, port=port)
    asyncio.run(orch.run_until_exhausted())
    # One fewer than Arm A: the final corpus row never closes.
    assert orch.closed_bars_seen == _LIMIT - 1
    assert orch.process_calls > 0
    assert orch.process_attempts == orch.process_calls
    assert summarize_audit(report).get("ENGINE_ERROR", 0) == 0


# ── the seams this program closed, pinned so they cannot silently reopen ─────────

def test_feature_store_singleton_is_declared_global() -> None:
    """The defect itself: assignment without `global` silently discarded the store."""
    import inspect

    from runtime import live_engine_hook

    src = inspect.getsource(live_engine_hook._load_engine_config)
    assert "_feature_store" in src.split("global", 1)[1].split("\n", 1)[0], (
        "_load_engine_config assigns _feature_store but does not declare it global -- "
        "the assignment binds a local and the canonical ingestion boundary never runs"
    )


def test_auxiliary_carries_exactly_the_canonical_surface() -> None:
    """FeatureStore validates an exact set: no missing v5 keys, no non-canonical extras."""
    from features.feature_schema import CANONICAL_FEATURES
    from runtime.live_engine_hook import _build_ohlcv_and_auxiliary

    trade_data = {
        "symbol": "XAUUSD", "timeframe": "M15",
        "timestamp": datetime(2024, 5, 22, 1, 0, tzinfo=timezone.utc),
        "open": 2400.0, "high": 2403.0, "low": 2398.0, "close": 2401.0, "volume": 100.0,
        "session": 4, "hour_of_day": 3,
    }
    for name in CANONICAL_FEATURES:
        trade_data.setdefault(name, 0.0)
    trade_data["macd_hist"] = 0.0
    ohlcv, auxiliary = _build_ohlcv_and_auxiliary(trade_data)
    produced = set(ohlcv) | set(auxiliary)
    canonical = set(CANONICAL_FEATURES)
    assert not (canonical - produced), f"missing canonical keys: {sorted(canonical - produced)}"
    assert not (produced - canonical - {"double_sweep"}), (
        f"non-canonical extras reach FeatureStore: {sorted(produced - canonical)}"
    )


def test_session_closed_ordinal_is_recognised() -> None:
    """SessionOrdinal.CLOSED=4 is 20% of a real XAUUSD sample; it must classify, not raise."""
    from features.session_classifier import SessionOrdinal
    from runtime.live_engine_hook import _normalize_session

    assert _normalize_session(int(SessionOrdinal.CLOSED)) == "closed"
    assert _normalize_session(4.0) == "closed"
    with pytest.raises(ValueError, match="Unrecognised session"):
        _normalize_session(99)
