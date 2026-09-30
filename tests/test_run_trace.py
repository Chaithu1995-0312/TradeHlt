"""Live Run Trace: per-run emitter output (bar_structure_snapshot live switches) + read API.

Covers:
  * defaults unchanged: a SnapshotConfig without the new switches writes the shared per-instrument
    file, no manifest, and no `features` key (today's behaviour);
  * per_run_dir: manifest exists BEFORE the first bar (status running), flips to finished on close;
  * features: LIVE rows carry the 48 names in schema order, WARMUP rows carry null (never 0-filled),
    and a wrong-length vector raises instead of silently mis-labelling;
  * read API: byte cursor returns only new complete lines and never consumes a partial last line;
    a verified Parquet projection is served for a finished run (cursor=auto) while a client that
    pinned cursor=byte keeps tailing the JSONL; run_id cannot escape the root.
"""
from __future__ import annotations

import dataclasses
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle  # noqa: E402
from control_plane import run_trace_api as api  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from runtime.bar_structure_snapshot import (  # noqa: E402
    SNAPSHOT_SCHEMA_VERSION,
    BarStructureEmitter,
    SnapshotConfig,
)

WARMUP = 5
N = 40


class _State:
    atr_abs = 3.0
    active_range = None
    sweep_event = None
    displacement_candle = None
    retest_candle = None
    direction = None
    pending_displacement_ttl = None
    htf_remaining_candles = 5
    evaluating_soft_conf = False
    active_trade = None


def _cfg(tmp: Path, **live) -> SnapshotConfig:
    base = SnapshotConfig(
        enabled=True, schema_version=SNAPSHOT_SCHEMA_VERSION, output_dir=str(tmp),
        filename_suffix="_bar_structure.jsonl", flush_every=7, emit_on_warmup_bars=True,
        families={}, eqh_eql_tolerance_atr=0.1, eqh_eql_max_swings=8, memoize_break_events=True,
    )
    return dataclasses.replace(base, **live)


def _emitter(cfg: SnapshotConfig, run_id: str = "run_t1") -> BarStructureEmitter:
    return BarStructureEmitter(
        cfg, run_id=run_id, instrument="XAUUSD", timeframe="M15",
        corpus_path="data/mt5/XAUUSD_M15.csv", corpus_hash="0" * 64,
        config_version="v5_test", config_hash="deadbeef", swing_window=2, smc_max_window=100,
        timestamp_basis="broker_local", objective_gate_enabled=False,
        objective_gate_mode="allow_exists_only", parent_timeframe="H4", htf_thresholds=None,
        feature_schema_version="6.0", feature_schema_hash="h",
        feature_names=(tuple(CANONICAL_FEATURES) if cfg.include_features else None),
        manifest_extra=({"config": {"backtest": {"sl_anchor": "displacement"}}, "corpus_rows": N}
                        if cfg.per_run_dir else None),
    )


def _candles():
    rng = random.Random(3)
    p, t0, out = 2000.0, datetime(2025, 1, 1), []
    for i in range(N):
        p += rng.gauss(0, 2)
        out.append(Candle(timestamp=t0 + timedelta(minutes=15 * i), open=p, high=p + 1, low=p - 1,
                          close=p + 0.3, volume=10.0, index=i))
    return out


def _drive(em: BarStructureEmitter, *, stop_before_close: bool = False) -> None:
    st = _State()
    for i, c in enumerate(_candles()):
        if i < WARMUP:
            em.emit_warmup(c, i)
        else:
            vec = [float(i) + k / 100 for k in range(len(CANONICAL_FEATURES))]
            em.emit(candle=c, bar_index=i, engine_state=st,
                    result={"action": "NONE", "candle_index": i}, prev_state="RANGE",
                    curr_state="RANGE", htf_candle_id="H1", parent_feed=None,
                    features=vec if em.cfg.include_features else None)
    if not stop_before_close:
        em.close()


# ---- emitter -----------------------------------------------------------------------------

def test_defaults_are_todays_behaviour(tmp_path):
    em = _emitter(_cfg(tmp_path))
    _drive(em)
    assert em.path == tmp_path / "XAUUSD_bar_structure.jsonl"      # shared file, not per-run
    assert not list(tmp_path.glob("*/manifest.json"))
    rows = [json.loads(line) for line in em.path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == N and all("features" not in r for r in rows)


def test_manifest_exists_before_first_bar_and_finishes(tmp_path):
    em = _emitter(_cfg(tmp_path, per_run_dir=True))
    m = json.loads((tmp_path / "run_t1" / "manifest.json").read_text(encoding="utf-8"))
    assert m["status"] == "running" and m["rows"] == 0 and m["corpus_rows"] == N
    assert m["identity"]["config_version"] == "v5_test"
    _drive(em)
    m = json.loads((tmp_path / "run_t1" / "manifest.json").read_text(encoding="utf-8"))
    assert m["status"] == "finished" and m["rows"] == N and m["finished_at"]


def test_features_in_schema_order_live_and_null_on_warmup(tmp_path):
    em = _emitter(_cfg(tmp_path, per_run_dir=True, include_features=True))
    _drive(em)
    rows = [json.loads(line) for line in em.path.read_text(encoding="utf-8").splitlines()]
    warm = [r for r in rows if r["phase"] == "WARMUP"]
    live = [r for r in rows if r["phase"] == "LIVE"]
    assert len(warm) == WARMUP and all(r["features"] is None for r in warm)
    assert all(list(r["features"]) == list(CANONICAL_FEATURES) for r in live)
    assert live[0]["features"][CANONICAL_FEATURES[1]] == pytest.approx(WARMUP + 0.01)
    assert list(live[0])[-1] == "features"  # trailing: earlier key order untouched


def test_manifest_write_survives_a_locked_destination(tmp_path, monkeypatch):
    """RUNTIME bug (2026-09-28, full-corpus run): Path.replace onto a manifest.json a
    concurrent reader has open raises PermissionError ([WinError 5]) on Windows. That must
    never propagate out of flush()/close() -- it nearly took down a real backtest."""
    em = _emitter(_cfg(tmp_path, per_run_dir=True))
    calls = {"n": 0}
    real_replace = Path.replace

    def flaky_replace(self, target):
        if self.name == "manifest.json.tmp" and calls["n"] < 2:
            calls["n"] += 1
            raise PermissionError(5, "Access is denied")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    em.emit_warmup(_candles()[0], 0)  # triggers _write_manifest via __init__ already ran;
    _drive(em)                        # this call exercises flush()'s manifest write path
    m = json.loads((tmp_path / "run_t1" / "manifest.json").read_text(encoding="utf-8"))
    assert m["status"] == "finished" and calls["n"] == 2  # survived 2 failures, then succeeded


def test_wrong_length_vector_raises(tmp_path):
    em = _emitter(_cfg(tmp_path, per_run_dir=True, include_features=True))
    c = _candles()[0]
    with pytest.raises(ValueError, match="feature vector"):
        em.emit(candle=c, bar_index=0, engine_state=_State(), result={}, prev_state="RANGE",
                curr_state="RANGE", htf_candle_id=None, parent_feed=None, features=[1.0, 2.0])


# ---- read API ----------------------------------------------------------------------------

def test_byte_cursor_returns_only_new_complete_lines(tmp_path):
    em = _emitter(_cfg(tmp_path, per_run_dir=True, include_features=True))
    _drive(em, stop_before_close=True)       # flush_every=7 -> most rows flushed, run "running"
    first = api.bars("run_t1", 0, 1000, root=tmp_path, cursor="byte")
    assert first["status"] == "running" and first["source"] == "jsonl"
    n1 = len(first["rows"])
    assert n1 == (N // 7) * 7
    # A half-written append must not be consumed.
    with em.path.open("ab") as fh:
        fh.write(b'{"bar_index": 999, "partial"')
    again = api.bars("run_t1", first["next_offset"], 1000, root=tmp_path, cursor="byte")
    assert again["rows"] == [] and again["next_offset"] == first["next_offset"]


def test_finished_run_serves_verified_parquet_but_pinned_byte_cursor_stays_jsonl(tmp_path):
    pytest.importorskip("pyarrow")
    em = _emitter(_cfg(tmp_path, per_run_dir=True, include_features=True, write_parquet=True))
    _drive(em)
    m = api.run_meta("run_t1", root=tmp_path)
    assert m["parquet"]["verified"]["ok"] is True
    auto = api.bars("run_t1", 0, 5000, root=tmp_path)
    assert auto["source"].startswith("parquet") and auto["cursor"] == "row"
    assert len(auto["rows"]) == N
    live = [r for r in auto["rows"] if r["phase"] == "LIVE"]
    assert list(live[0]["features"]) == list(CANONICAL_FEATURES)
    pinned = api.bars("run_t1", 0, 5000, root=tmp_path, cursor="byte")
    assert pinned["source"] == "jsonl" and len(pinned["rows"]) == N


def test_list_runs_and_run_id_cannot_escape_root(tmp_path):
    _drive(_emitter(_cfg(tmp_path, per_run_dir=True)))
    runs = api.list_runs(root=tmp_path)["runs"]
    assert [r["run_id"] for r in runs] == ["run_t1"] and runs[0]["status"] == "finished"
    for bad in ("../x", "..", "a/b", ""):
        with pytest.raises(KeyError):
            api.run_meta(bad, root=tmp_path)
