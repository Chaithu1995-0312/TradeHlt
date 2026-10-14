"""Research Navigator Phase-1 reconciler.

Synthetic workbooks only. Proves column bindings, exact-path joins, and that
legend sheets stay in the coverage denominator.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import openpyxl

_TOOL = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "nav_reconcile.py"


def _load():
    spec = importlib.util.spec_from_file_location("nav_reconcile", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _wb(path: Path, sheets: dict[str, list[list]]) -> None:
    book = openpyxl.Workbook()
    first = True
    for name, rows in sheets.items():
        ws = book.active if first else book.create_sheet(name)
        if first:
            ws.title = name
            first = False
        for row in rows:
            ws.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)
    book.close()


def test_business_summary_and_basename_are_not_defaulted(tmp_path: Path) -> None:
    nav = _load()
    _wb(tmp_path / "scripts_business_functionality.xlsx", {
        "Scripts Analysis": [
            ["File Name", "Summary of functionality", "Referred files"],
            ["__init__.py", "Package marker.", "(none / stdlib-only)"],
            ["scripts/governance/nav_reconcile.py", None, "src/features/feature_schema.py"],
        ],
        "Counts": [["Metric", "Value"], ["rows", 2]],
    })
    _wb(tmp_path / "DOC_TRACKING_INDEX.xlsx", {
        "Master_Index": [["Rel_Path", "Topic", "Freshness"], ["docs/a.md", "Alpha", "current"]],
        "Legend": [["Token", "Meaning"], ["X", "example"]],
        "Hot_Recent_30d": [["Rel_Path", "Topic"], ["docs/a.md", "Alpha again"]],
    })
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "RESEARCH_SCRIPTS_INTENT_TRACKER.csv").write_text(
        "script_path,intent,status_hints\n"
        "scripts/governance/nav_reconcile.py,Reconcile inventories,\n",
        encoding="utf-8",
    )
    _wb(tmp_path / "Infrastructure Inventory.xlsx", {
        "Assets": [["ID", "Name", "Location", "Purpose"],
                   ["INV-001", "Runtime Harnesses (Backtest)", "src/runtime/", "Run backtests"]],
        "Relationships": [["Source", "Relationship", "Target", "Evidence"],
                          ["OHLCV CSV (data/)", "streamed into", "Runtime Harnesses (Backtest)", "signal-flow"]],
        "Confidence": [["Asset", "Confidence", "Reason"],
                       ["INV-001 Runtime Harnesses (Backtest)", "HIGH", "on disk"],
                       ["INV-999 Missing", "LOW", "no such asset"]],
        "CRT Constructors": [["Path", "Role"], ["src/config_layer/crt_engine_v2.py", "Primary constructor"]],
    })

    rec = nav.build_index(tmp_path, tmp_path / "out", None)
    arts = (tmp_path / "out" / "artifacts.jsonl").read_text(encoding="utf-8")
    rels = (tmp_path / "out" / "relationships.jsonl").read_text(encoding="utf-8")

    bare = next(a for a in rec["inferred_identity_candidates"] if a["raw_file_name"] == "__init__.py")
    assert bare["confidence"] == "inferred_candidate"
    assert rec["verified_identity_matches"][0]["key"] == "scripts/governance/nav_reconcile.py"

    assert "Package marker." in arts
    assert '"intent_confidence": "intent_unstated"' in arts
    biz_unstated = [
        line for line in arts.splitlines()
        if "NAV-BIZ:scripts/__init__.py" in line or "NAV-BIZ:scripts/governance/nav_reconcile.py" in line
    ]
    assert any('"intent_confidence": "declared"' in line and "Package marker." in line for line in biz_unstated)
    assert any("nav_reconcile.py" in line and '"intent_confidence": "intent_unstated"' in line for line in biz_unstated)

    assert '"relationship_type": "streamed into"' in rels
    assert "depends_on" not in rels
    assert '"target_raw": "Runtime Harnesses (Backtest)"' in rels
    assert '"target_resolution": "exact_name"' in rels
    assert '"source_resolution": "unresolved"' in rels
    assert '"endpoint_resolution": "unresolved"' in rels

    assert '"confidence_sheet": "HIGH"' in arts
    assert "INV-999 Missing" in arts
    assert "src/config_layer/crt_engine_v2.py" in arts
    assert "docs/a.md" in arts
    # Hot recent and master stay two records.
    assert arts.count("docs/a.md") >= 2

    inv = rec["coverage"]["inventory"]
    assert inv["explicitly_excluded_rows"] >= 2  # Legend + Counts
    assert inv["discovered_data_rows"] > inv["accounted_for"]
    assert inv["ratio"] < 1
    dispositions = {(c["workbook"], c["sheet"]): c["disposition"] for c in rec["sheet_census"]}
    assert dispositions[("DOC_TRACKING_INDEX.xlsx", "Legend")] == "excluded"
    assert dispositions[("DOC_TRACKING_INDEX.xlsx", "Hot_Recent_30d")] == "row_preserved"
    assert rec["coverage"]["lifecycle"]["with_explicit_disposition"] == 0

    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Derived index. Not an authority registry." in html
    assert "not a verified join" in html
    assert "This page does not record decisions." in html
    assert "__NAV_PAYLOAD__" not in html
    assert "ROW_CAP = 150" in html
    assert "intent_unstated" in html
    assert "Package marker." in html
    assert "__init__.py" in html
    assert "inferred_candidate" in html
    assert "Legend" in html
    assert '"disposition":"excluded"' in html
    assert html.lower().count("</script>") == 1
    assert not any(m.get("key") == "__init__.py" for m in rec["verified_identity_matches"])


def test_html_payload_cannot_close_the_script(tmp_path: Path) -> None:
    nav = _load()
    art = {
        "artifact_id": "NAV-X",
        "declared_intent": "</script><script>alert(1)</script>",
        "intent_confidence": "intent_unstated",
    }
    rec = {
        "authority": "derived_index_not_authority",
        "inferred_identity_candidates": [{
            "confidence": "inferred_candidate",
            "raw_file_name": "__init__.py",
            "reason": "not a verified join",
        }],
        "sheet_census": [{"workbook": "DOC", "sheet": "Legend", "rows": 1, "disposition": "excluded"}],
        "exclusions": [{"item": "Legend", "reason": "excluded"}],
        "coverage": {}, "missing_sources": [], "conflicts": {}, "counts": {},
    }
    nav.write_html(tmp_path, [art], [], rec)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert html.lower().count("</script>") == 1
    assert "<script>alert" not in html.lower()
    assert "\\u003c/script\\u003e" in html
    assert "Derived index. Not an authority registry." in html
    assert "intent_unstated" in html
