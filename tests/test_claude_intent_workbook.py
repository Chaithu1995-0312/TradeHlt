"""Floor for docs/analysis/claude_test_intent.xlsx (Claude auditor, nodeid grain).

Sibling of tests/test_grok_intent_workbook.py. Collects via
collect_nodeids("Claude") (subprocess contract), never ambient session.items.
Generate-to-tmp so CI does not depend on an untracked xlsx.
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

_SUITE = "Claude"
_SHEET = gen._SUITES[_SUITE].sheet


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


def _generate(tmp_path: Path) -> tuple[list[str], list[dict[str, object]]]:
    nodeids = gen.collect_nodeids(_SUITE)
    rows = gen.build_intent_rows(_SUITE, nodeids)
    out = tmp_path / "claude_test_intent.xlsx"
    gen.write_intent_excel(rows, out, _SUITE)
    return nodeids, _sheet_rows(out, _SHEET)


def test_tmp_row_count_matches_subprocess_collect(tmp_path: Path):
    nodeids, data = _generate(tmp_path)
    assert len(data) == len(nodeids)
    assert len(data) == len(gen.collect_nodeids(_SUITE))


def test_every_claude_test_module_appears(tmp_path: Path):
    _nodeids, data = _generate(tmp_path)
    files = {r["File"] for r in data}
    disk = {
        str(p.relative_to(_REPO)).replace("\\", "/")
        for p in (_REPO / "tests" / _SUITE).glob("test_*.py")
    }
    assert disk <= files


def test_every_row_is_a_mapped_claude_family(tmp_path: Path):
    """J-M are declared in _FAMILY_LAYER, so no Claude row may be UNMAPPED."""
    _nodeids, data = _generate(tmp_path)
    assert {r["Family"] for r in data} == {"J", "K", "L", "M"}
    assert {r["Added by"] for r in data} == {"Claude"}
    assert not [r for r in data if r["Topic layer"] == "UNMAPPED"]


def test_house_style_holds_for_every_claude_case(tmp_path: Path):
    """Every Claude test carries both Source: and Failure mode: in its docstring."""
    _nodeids, data = _generate(tmp_path)
    degraded = [
        (r["Method"], r["Intent quality"])
        for r in data
        if r["Intent quality"] != "FROM_DOCSTRING"
    ]
    assert degraded == []
    assert all(r["Source contract"] and r["Failure mode"] for r in data)


def test_extractor_goldens(tmp_path: Path):
    """Byte-reproducible extractor output for one row per family."""
    _nodeids, data = _generate(tmp_path)

    def _find(method: str, case: str | None = None) -> dict:
        hits = [
            r
            for r in data
            if r["Method"] == method and (case is None or r["Case id"] == case)
        ]
        assert hits, f"missing {method} case={case}"
        return hits[0]

    j1 = _find("test_sweep_to_displacement_edge_is_legal_but_geometry_still_refuses")
    assert j1["Family"] == "J"
    assert j1["Topic layer"] == "3 Directional displacement F-074"
    assert j1["Case id"] == "-"
    assert j1["Intent"] == (
        "The graph permits the hop that try_sweep_to_displacement then denies."
    )
    assert j1["Trying to do"] == j1["Intent"]
    assert j1["Source contract"] == (
        "state_identity.VALID_TRANSITIONS vs StateMachine.try_sweep_to_displacement"
    )
    assert j1["Failure mode"].startswith("an auditor reads the edge out of VALID_TRANSITIONS")
    assert j1["Why ordinary tests miss it"].startswith("the graph floors and the shape floors")
    assert j1["Intent quality"] == "FROM_DOCSTRING"
    assert j1["Added by"] == "Claude"

    j2 = _find("test_wrong_sign_is_rejected_before_the_energy_gate", "Direction.LONG")
    assert j2["Intent"] == (
        "Sign is checked first: overwhelming energy cannot buy a wrong-signed hop."
    )
    assert j2["Parametrize arity"] == 2
    # `Numbers:` is a recognized label, so it is classified out of Intent, not into it.
    assert "Numbers" not in j2["Intent"]
    assert "989" not in j2["Intent"]

    k1 = _find("test_no_smc_feature_name_is_a_crt_state", "order_block_distance")
    assert k1["Family"] == "K"
    assert k1["Topic layer"] == "6 SMC primitives F-076"
    assert k1["Parametrize arity"] == 9
    assert k1["Intent"] == "An SMC column name never resolves to a CRTState member."

    l1 = _find("test_a_stale_registry_cannot_produce_a_pass")
    assert l1["Family"] == "L"
    assert l1["Topic layer"] == "1 Ontology / feature vector"
    assert l1["Intent"] == (
        "Through the live entry point the stale artifact BLOCKS, it does not score."
    )
    assert l1["Source contract"].startswith("run_zone_gate_engine step 3")

    m1 = _find("test_crt_closure_surface_is_still_open")
    assert m1["Family"] == "M"
    assert m1["Topic layer"] == "4 Parent 3-candle 12-state"
    assert m1["Intent"] == "Wiring the parent graph did not re-certify the state machine."
    assert m1["Source contract"] == 'docs/governance/closure_authority_index.json, surface_id "CRT"'


def test_collect_failed_stub_overwrites(tmp_path: Path):
    out = tmp_path / "claude_test_intent.xlsx"
    gen.write_intent_excel(
        [
            {
                "Family": "J",
                "Topic layer": "3 Directional displacement F-074",
                "File": "tests/Claude/test_J_directional_displacement.py",
                "Method": "test_dummy",
                "Nodeid": "tests/Claude/test_J_directional_displacement.py::test_dummy",
                "Case id": "-",
                "Intent": "old row",
                "Trying to do": "old row",
                "Source contract": "",
                "Failure mode": "",
                "Why ordinary tests miss it": "",
                "Intent quality": "INTENT_INFERRED",
                "Parametrize arity": 1,
                "Added by": "Claude",
                "Referred files": "",
            }
        ],
        out,
        _SUITE,
    )
    gen.write_collect_failed_stub(out, "boom", _SUITE)
    data = _sheet_rows(out, _SHEET)
    assert len(data) == 1
    assert data[0]["Intent"] == "COLLECT_FAILED"
    assert data[0]["Added by"] == "Claude"


def test_the_two_suites_do_not_share_a_family_letter():
    """Grok owns A-I and Claude owns J-M, so a merged view is unambiguous."""
    grok_families = {
        gen.family_from_filename(p.name)
        for p in (_REPO / "tests" / "Grok").glob("test_*.py")
    }
    claude_families = {
        gen.family_from_filename(p.name)
        for p in (_REPO / "tests" / "Claude").glob("test_*.py")
    }
    assert grok_families and claude_families
    assert grok_families.isdisjoint(claude_families)
    assert (grok_families | claude_families) <= set(gen._FAMILY_LAYER)


def test_on_disk_sibling_matches_collect_if_present():
    path = _REPO / "docs" / "analysis" / "claude_test_intent.xlsx"
    if not path.is_file():
        pytest.skip("sibling xlsx absent")
    data = _sheet_rows(path, _SHEET)
    if data and data[0].get("Intent") == "COLLECT_FAILED":
        pytest.skip("sibling is COLLECT_FAILED stub")
    assert len(data) == len(gen.collect_nodeids(_SUITE))
