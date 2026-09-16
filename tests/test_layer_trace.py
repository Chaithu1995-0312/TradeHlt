"""LayerTraceEmitter (runtime.layer_trace): record shape, identity, and emit-contract floors.

Unit-level floors on the emitter in isolation, mirroring `tests/test_bar_structure_snapshot.py`'s
structure. This is NOT the full-corpus decision-neutrality proof (that requires running
`BacktestRunner` twice — tracing ON vs OFF — against a real corpus and diffing the trade ledger;
see the module's own docstring for why that is a separate, not-yet-built artifact). What this file
DOES pin, at the unit level, backs the decision-neutrality CLAIM without yet being the full proof:

  - `emit()` / `emit_not_reached_once()` never raise on a well-formed call and return None;
  - a disabled emitter (`enabled=False`) writes nothing, so explicit opt-out stays a
    complete no-op;
  - every record carries the identity block (`run_id`/`trace_id`/`span_id`) required to join rows
    across layers, which is this module's entire reason to exist (plan §5 item 1);
  - `layer`/`status`/`plane` are drawn from fixed vocabularies, not free strings, so a caller typo
    fails loudly at `emit()` time rather than writing a silently-uncomparable row.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from runtime.layer_trace import (  # noqa: E402
    LAYER_PLANE,
    LAYERS,
    PLANES,
    STATUSES,
    TRACE_SCHEMA_VERSION,
    LayerTraceConfig,
    LayerTraceEmitter,
    make_trace_id,
    mint_run_id,
)


def _cfg(tmp: Path, *, enabled: bool = True) -> LayerTraceConfig:
    return LayerTraceConfig(
        enabled=enabled,
        schema_version=TRACE_SCHEMA_VERSION,
        output_dir=str(tmp),
        filename_suffix="_layer_trace.jsonl",
        flush_every=50,
    )


def _emitter(tmp: Path, *, enabled: bool = True, run_id: str = "test_run") -> LayerTraceEmitter:
    return LayerTraceEmitter(
        _cfg(tmp, enabled=enabled),
        run_id=run_id,
        instrument="XAUUSD",
        timeframe="M15",
        active_version="v2_htfcrt_2026_08",
        config_hash="7de09f62",
        schema_hash="f52bf5d3",
        dataset_id="",
        corpus_path="data/mt5/XAUUSD_M15.csv",
        corpus_rows=47275,
        corpus_sha256="0" * 64,
        code_sha="deadbeef",
        tree_dirty=True,
        rail="backtest",
        preexisting_run_ids={
            "utils.logging_config.RUN_ID": "20260101_000000",
            "runtime.ReportWriter.run_id": "run_20260101_000000",
        },
    )


def _bar_ts(i: int):
    return datetime(2025, 1, 1, tzinfo=timezone.utc).replace(minute=(i * 15) % 60)


# ---- identity / minting -----------------------------------------------------------------

def test_mint_run_id_is_utc_and_distinguishable_from_preexisting_ids():
    rid = mint_run_id("XAUUSD", datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    assert rid == "lt_20260101_120000_XAUUSD"


def test_make_trace_id_is_deterministic_for_the_same_bar():
    ts = _bar_ts(5)
    a = make_trace_id("lt_run", "XAUUSD", ts)
    b = make_trace_id("lt_run", "XAUUSD", ts)
    assert a == b
    assert a == f"lt_run:XAUUSD:{ts.isoformat()}"


# ---- vocabularies -------------------------------------------------------------------------

def test_layer_plane_covers_every_declared_layer():
    assert set(LAYER_PLANE.keys()) == LAYERS
    assert set(LAYER_PLANE.values()) <= PLANES


def test_emit_rejects_unknown_layer(tmp_path):
    em = _emitter(tmp_path)
    with pytest.raises(ValueError):
        em.emit(trace_id="t", bar_idx=0, bar_ts=_bar_ts(0), layer="L99", module="x", status="PASS")


def test_emit_rejects_unknown_status(tmp_path):
    em = _emitter(tmp_path)
    with pytest.raises(ValueError):
        em.emit(trace_id="t", bar_idx=0, bar_ts=_bar_ts(0), layer="L3", module="x", status="MAYBE")


# ---- emit contract ------------------------------------------------------------------------

def test_emit_returns_none_and_writes_one_row(tmp_path):
    em = _emitter(tmp_path)
    result = em.emit(
        trace_id="lt_run:XAUUSD:t0", bar_idx=0, bar_ts=_bar_ts(0),
        layer="L3", module="config_layer.crt_engine_v2", status="PASS",
    )
    assert result is None
    manifest = em.close()
    assert manifest["rows"] == 1


def test_disabled_emitter_writes_nothing(tmp_path):
    em = _emitter(tmp_path, enabled=False)
    em.emit(trace_id="t", bar_idx=0, bar_ts=_bar_ts(0), layer="L3", module="x", status="PASS")
    em.emit_not_reached_once(layer="L7", module="x", note="n/a")
    manifest = em.close()
    assert manifest["rows"] == 0
    assert not Path(manifest["path"]).exists()


def test_emit_not_reached_once_is_run_scoped_not_bar_scoped(tmp_path):
    em = _emitter(tmp_path)
    em.emit_not_reached_once(layer="L7", module="x", note="unreachable on this rail")
    manifest = em.close()
    rows = [json.loads(l) for l in Path(manifest["path"]).read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["bar_idx"] == -1
    assert rows[0]["status"] == "NOT_REACHED"
    assert rows[0]["plane"] == "execution"


# ---- identity on every record --------------------------------------------------------------

def test_every_record_carries_the_full_identity_block(tmp_path):
    em = _emitter(tmp_path, run_id="lt_20260101_000000_XAUUSD")
    tid = make_trace_id(em.run_id, "XAUUSD", _bar_ts(1))
    em.emit(trace_id=tid, bar_idx=1, bar_ts=_bar_ts(1), layer="L5", module="core.engine_runner", status="PASS")
    manifest = em.close()
    rows = [json.loads(l) for l in Path(manifest["path"]).read_text(encoding="utf-8").splitlines()]
    row = rows[0]
    for key in ("run_id", "trace_id", "span_id", "instrument", "active_version",
                "config_hash", "schema_hash", "corpus_sha256", "code_sha", "tree_dirty",
                "preexisting_run_ids"):
        assert key in row, f"missing identity field {key!r}"
    assert row["run_id"] == "lt_20260101_000000_XAUUSD"
    assert row["trace_id"] == tid
    assert row["span_id"] == f"{tid}:L5"
    # H1 evidence: the pre-existing ids are captured, never silently collapsed to this module's own.
    assert row["preexisting_run_ids"]["utils.logging_config.RUN_ID"] == "20260101_000000"
    assert row["run_id"] != row["preexisting_run_ids"]["utils.logging_config.RUN_ID"]


def test_from_prod_config_defaults_on_when_section_absent(monkeypatch):
    """Absent `layer_trace` section → default ON with module DEFAULT_* (2026-09-16)."""
    import config_layer.production_config as prod_cfg
    from runtime.layer_trace import (
        DEFAULT_FILENAME_SUFFIX,
        DEFAULT_FLUSH_EVERY,
        DEFAULT_OUTPUT_DIR,
        TRACE_SCHEMA_VERSION,
    )

    def _raise(*a, **k):
        raise KeyError("layer_trace")

    monkeypatch.setattr(prod_cfg, "get_prod_section", _raise)
    cfg = LayerTraceConfig.from_prod_config()
    assert cfg is not None
    assert cfg.enabled is True
    assert cfg.schema_version == TRACE_SCHEMA_VERSION
    assert cfg.output_dir == DEFAULT_OUTPUT_DIR
    assert cfg.filename_suffix == DEFAULT_FILENAME_SUFFIX
    assert cfg.flush_every == DEFAULT_FLUSH_EVERY


def test_from_prod_config_returns_none_when_explicitly_disabled(monkeypatch):
    """Present section with enabled:false remains the opt-out."""
    import config_layer.production_config as prod_cfg

    monkeypatch.setattr(
        prod_cfg,
        "get_prod_section",
        lambda *a, **k: {
            "enabled": False,
            "schema_version": "1.0.0",
            "output_dir": "results/layer_trace",
            "filename_suffix": "_layer_trace.jsonl",
            "flush_every": 200,
        },
    )
    assert LayerTraceConfig.from_prod_config() is None
