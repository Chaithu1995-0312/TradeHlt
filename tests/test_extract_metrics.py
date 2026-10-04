"""
Tests for scripts/metrics/extract_metrics.py — the optional **Metrics** self-report extractor.

Mirrors tests/test_behavior_census.py (load-a-script-and-assert). Pins the parser SHELL
(structure, stable field order, prospective-empty behavior). The *meaning* of the self-rated
fields stays doctrine and is intentionally NOT asserted — these grades carry no authority
(CLAUDE.md §6.5 / E-001).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "metrics" / "extract_metrics.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("extract_metrics", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    if not _TOOL.exists():
        pytest.skip("extract_metrics.py not present")
    return _load_tool()


_SAMPLE = """\
---
📝 SESSION LOG ENTRY
Date: 2026-06-21 01:18 IST
Topic: example
Decision/Output: did a thing

**Metrics**
GP:1|Act:Redirect|Rec:0|Find:Y|Ent:M|NS:Direct|KROI:H
Notes: clearer goal anchoring today.
---
"""


def test_parses_one_block(tool):
    records = tool.parse_metrics(_SAMPLE)
    assert len(records) == 1
    rec = records[0]
    assert rec["fields"] == {
        "GP": "1", "Act": "Redirect", "Rec": "0",
        "Find": "Y", "Ent": "M", "NS": "Direct", "KROI": "H",
    }
    assert rec["notes"] == "clearer goal anchoring today."
    assert rec["date"] == "2026-06-21"


def test_stable_field_order(tool):
    # Even when the source line is shuffled, output keys follow the canonical FIELDS order.
    shuffled = "**Metrics**\nKROI:H|GP:1|NS:None|Act:Continue|Find:N|Ent:L|Rec:2\n"
    rec = tool.parse_metrics(shuffled)[0]
    assert list(rec["fields"].keys()) == list(tool.FIELDS)


def test_empty_input_is_empty(tool):
    # Prospective-by-design: free-text without a Metrics block yields nothing.
    assert tool.parse_metrics("") == []
    assert tool.parse_metrics("Date: 2026-06-20\nno metrics here\n") == []


def test_notes_optional(tool):
    rec = tool.parse_metrics("**Metrics**\nGP:0|Act:Continue|Rec:1|Find:Y|Ent:H|NS:Para|KROI:M\n")[0]
    assert rec["notes"] is None
    assert rec["fields"]["KROI"] == "M"


def test_since_filter(tool):
    two = _SAMPLE + (
        "Date: 2026-05-01 00:00 IST\n\n"
        "**Metrics**\nGP:0|Act:Continue|Rec:0|Find:N|Ent:L|NS:None|KROI:L\n"
    )
    recs = tool.parse_metrics(two)
    assert len(recs) == 2
    kept = tool._filter_since(recs, "2026-06-01")
    assert len(kept) == 1
    assert kept[0]["date"] == "2026-06-21"
