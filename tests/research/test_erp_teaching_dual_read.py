"""Regression: Dual-Read Bar 78 teaching pair stays consistent (ERP IC-001).

Docs: docs/research-readiness/erp-teaching-dual-read-bar78.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXEMPLARS = ROOT / "results" / "research" / "trace_corpus" / "xauusd" / "representative_exemplars.jsonl"
CLOSURE = ROOT / "docs" / "research-readiness" / "ic-001-xauusd-static-entry-closure.md"
TEACHING = ROOT / "docs" / "research-readiness" / "erp-teaching-dual-read-bar78.md"
BOUNDARY_JSON = ROOT / "docs" / "research-readiness" / "erp-information-class-boundary.json"

ID_TP = "expansion_breakout_000007"
ID_SL = "mean_reversion_000012"
ENGINES = (
    "engine_crt_score",
    "engine_gaussian_score",
    "engine_zone_score",
    "engine_rr_score",
    "fusion_composite",
)


def _load_exemplars() -> dict[str, dict]:
    if not EXEMPLARS.exists():
        pytest.skip(f"exemplars artifact missing (gitignored results?): {EXEMPLARS}")
    out: dict[str, dict] = {}
    with open(EXEMPLARS, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r["trade_id"]] = r
    return out


def test_ic001_closure_and_teaching_docs_exist():
    assert CLOSURE.is_file(), "IC-001 closure chapter missing"
    assert TEACHING.is_file(), "Dual-read teaching card missing"
    text = CLOSURE.read_text(encoding="utf-8")
    assert "IC-001" in text
    assert "static entry-time OHLCV-derived information" in text
    assert TEACHING.read_text(encoding="utf-8").count("2387.55") >= 1


def test_boundary_json_ic001_complete():
    data = json.loads(BOUNDARY_JSON.read_text(encoding="utf-8"))
    mb = data["measured_boundary"]
    assert mb.get("ic_id") == "IC-001"
    assert mb.get("status") == "COMPLETE"
    assert data["ic_alias_map"]["IC-002"] == "RC-005"
    assert "Do not create new engines" in data.get("hard_guardrail", "")
    # After IC-002 first measure, discipline.next advances to IC-003
    assert data["discipline"]["next"] in ("RC-005", "IC-003")
    assert data["measured_boundary"]["status"] == "COMPLETE"


def test_dual_read_bar78_pair():
    rows = _load_exemplars()
    assert ID_TP in rows and ID_SL in rows
    a, b = rows[ID_TP], rows[ID_SL]

    assert a["entry_index"] == b["entry_index"] == 78
    assert a.get("entry_timestamp") == b.get("entry_timestamp")
    assert float(a.get("entry", a.get("feature_close", 0))) == pytest.approx(
        float(b.get("entry", b.get("feature_close", 0))), rel=0, abs=1e-6
    )

    assert a["direction"] != b["direction"]
    assert a["outcome"] == "TP_HIT"
    assert b["outcome"] == "SL_HIT"

    for k in ENGINES:
        assert a.get(k) is not None and b.get(k) is not None
        assert abs(float(a[k]) - float(b[k])) < 1e-6, f"{k} mismatch"

    tags_a = a.get("tags") or []
    tags_b = b.get("tags") or []
    assert "dual_read_bar_78" in tags_a or "dual_read_bar_78" in tags_b
    assert b.get("category") == "dual_read" or "dual_read" in str(b.get("category", ""))
