"""Floor for docs/analysis/grok_test_intent.xlsx (Grok auditor, nodeid grain).

Collects via collect_grok_nodeids() (subprocess contract), never ambient
session.items. Generate-to-tmp so CI does not depend on an untracked xlsx.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts" / "analysis"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import test_functionality_excel as gen  # noqa: E402

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

pytestmark = pytest.mark.skipif(openpyxl is None, reason="openpyxl not installed")

_HEADERS = gen._GROK_INTENT_HEADERS


def _sheet_rows(path: Path, sheet: str) -> list[dict[str, object]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h) if h is not None else "" for h in next(rows_iter)]
    out = []
    for raw in rows_iter:
        rec = {headers[i]: raw[i] for i in range(len(headers))}
        out.append(rec)
    wb.close()
    return out


def test_tmp_row_count_matches_subprocess_collect(tmp_path: Path):
    nodeids = gen.collect_grok_nodeids()
    rows = gen.build_grok_intent_rows(nodeids)
    out = tmp_path / "grok_test_intent.xlsx"
    gen.write_grok_intent_excel(rows, out)
    data = _sheet_rows(out, "Grok Method Intent")
    assert len(data) == len(nodeids)
    assert len(data) == len(gen.collect_grok_nodeids())


def test_every_grok_test_module_appears(tmp_path: Path):
    nodeids = gen.collect_grok_nodeids()
    rows = gen.build_grok_intent_rows(nodeids)
    out = tmp_path / "grok_test_intent.xlsx"
    gen.write_grok_intent_excel(rows, out)
    data = _sheet_rows(out, "Grok Method Intent")
    files = {r["File"] for r in data}
    disk = {
        str(p.relative_to(_REPO)).replace("\\", "/")
        for p in (_REPO / "tests" / "Grok").glob("test_*.py")
    }
    assert disk <= files


def test_section9_goldens(tmp_path: Path):
    """Byte-reproducible extractor goldens from the design §9 table."""
    nodeids = gen.collect_grok_nodeids()
    rows = gen.build_grok_intent_rows(nodeids)
    by_node = {r["Nodeid"]: r for r in rows}

    def _find(method: str, case: str | None = None) -> dict:
        hits = [
            r
            for r in rows
            if r["Method"] == method
            and (case is None or r["Case id"] == case)
        ]
        assert hits, f"missing {method} case={case}"
        return hits[0]

    a1 = _find("test_impossible_direct_range_to_execution_is_rejected")
    assert a1["Family"] == "A"
    assert a1["Intent"] == "RANGE → EXECUTION is not a legal hop."
    assert a1["Trying to do"] == a1["Intent"]
    assert a1["Source contract"] == "StateMachine._transition + VALID_TRANSITIONS"
    assert a1["Failure mode"] == (
        "skipped causal events (sweep/disp/retest) still open a trade path."
    )
    assert a1["Intent quality"] == "FROM_DOCSTRING"
    assert a1["Added by"] == "Grok"
    assert a1["Case id"] == "-"

    a2 = _find(
        "test_missing_intermediate_hops_are_illegal",
        "CRTState.SHADOW_PENDING-CRTState.EXPANSION",
    )
    assert a2["Intent"] == "Skipped causal events must not be a single legal transition."
    assert a2["Trying to do"] == a2["Intent"]
    assert a2["Source contract"] == "VALID_TRANSITIONS"
    assert "SHADOW_PENDING→EXPANSION" in a2["Failure mode"]
    assert a2["Intent quality"] == "FROM_DOCSTRING"

    i1 = _find("test_m15_cannot_hop_into_parent_states", "CRTState.RANGE-CRTState.RANGE_C1")
    assert i1["Family"] == "I"
    assert i1["Intent"].startswith("No M15 execution state may become C1/C2/C3")
    assert i1["Source contract"].startswith("VALID_TRANSITIONS disjoint-split comment")
    assert i1["Intent quality"] == "FROM_DOCSTRING"

    i2 = _find(
        "test_parent_cannot_hop_into_m15_states",
        "CRTState.DISTRIBUTION_C3-CRTState.EXECUTION",
    )
    assert i2["Intent"].startswith("C3 is not EXECUTION")
    assert i2["Source contract"] == ""
    assert "DISTRIBUTION_C3 → EXECUTION" in i2["Failure mode"]
    assert i2["Intent quality"] == "INTENT_PARTIAL"

    i3 = _find("test_htf_distribution_is_not_crt_distribution_c3")
    assert i3["Intent"].startswith("F-077 name collision")
    assert i3["Source contract"] == "htf_state.py module doc + HTFState enum"
    assert i3["Intent quality"] == "FROM_DOCSTRING"
    assert by_node[i3["Nodeid"]]["Trying to do"] == i3["Intent"]


def test_collect_failed_stub_overwrites(tmp_path: Path):
    out = tmp_path / "grok_test_intent.xlsx"
    gen.write_grok_intent_excel(
        [
            {
                "Family": "A",
                "Topic layer": "2 CRT 9-state M15 spine",
                "File": "tests/Grok/test_A_crt_journeys.py",
                "Method": "test_dummy",
                "Nodeid": "tests/Grok/test_A_crt_journeys.py::test_dummy",
                "Case id": "-",
                "Intent": "old row",
                "Trying to do": "old row",
                "Source contract": "",
                "Failure mode": "",
                "Why ordinary tests miss it": "",
                "Intent quality": "INTENT_INFERRED",
                "Parametrize arity": 1,
                "Added by": "Grok",
                "Referred files": "",
            }
        ],
        out,
    )
    gen.write_grok_collect_failed_stub(out, "boom")
    data = _sheet_rows(out, "Grok Method Intent")
    assert len(data) == 1
    assert data[0]["Intent"] == "COLLECT_FAILED"


def test_on_disk_sibling_matches_collect_if_present():
    path = _REPO / "docs" / "analysis" / "grok_test_intent.xlsx"
    if not path.is_file():
        pytest.skip("sibling xlsx absent")
    data = _sheet_rows(path, "Grok Method Intent")
    if data and data[0].get("Intent") == "COLLECT_FAILED":
        pytest.skip("sibling is COLLECT_FAILED stub")
    assert len(data) == len(gen.collect_grok_nodeids())
