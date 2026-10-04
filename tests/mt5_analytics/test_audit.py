"""Phase 6.5 — audit chain (append-only)."""
from __future__ import annotations

from mt5_analytics.analytics_config import load_config
from mt5_analytics.core.audit import append_audit
from utils.jsonl_writer import read_jsonl  # type: ignore


def _cfg(tmp_path):
    cfg = load_config()
    cfg["audit_root"] = str(tmp_path / "audit")
    return cfg


def test_append_audit_writes_line(tmp_path):
    cfg = _cfg(tmp_path)
    line = append_audit("verification_run", {"status": "PASS", "mt5_positions": 0}, cfg=cfg)
    assert line["kind"] == "verification_run" and "timestamp_utc" in line
    f = tmp_path / "audit" / "verification_runs.jsonl"
    recs = read_jsonl(f)
    assert len(recs) == 1 and recs[0]["status"] == "PASS"


def test_append_only(tmp_path):
    cfg = _cfg(tmp_path)
    append_audit("rebuild_run", {"episodes_written": 1}, cfg=cfg)
    append_audit("rebuild_run", {"episodes_written": 2}, cfg=cfg)
    recs = read_jsonl(tmp_path / "audit" / "rebuild_runs.jsonl")
    assert [r["episodes_written"] for r in recs] == [1, 2]   # append-only, ordered
