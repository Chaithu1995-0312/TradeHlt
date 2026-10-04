"""CT-009: existing CRT objects — relations are explicit and mechanically checked.

Loads docs/governance/crt_object_relations.yaml. Every YAML ``check`` must have
a function here; every function listed in the YAML must run. No new liquidity
object (P-CRT-LIQ-01).
"""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest
import yaml

from config_layer.crt_engine_v2 import RangeDetector, ResetLogic
from config_layer.m15_structural_range import M15StructuralLiquidityRange
from config_layer.parent_crt import ParentCRTTrack, ParentRange
from runtime.backtest_v2 import HTFBuilder

_REPO = Path(__file__).resolve().parents[1]
_TABLE = _REPO / "docs" / "governance" / "crt_object_relations.yaml"
_ENGINE = _REPO / "src" / "config_layer" / "crt_engine_v2.py"

_ALLOWED_RELATIONS = frozenset(
    {"is_not", "reads", "does_not_read", "clocks", "joins_only_at", "does_not_found"}
)


def _load() -> dict:
    data = yaml.safe_load(_TABLE.read_text(encoding="utf-8"))
    assert data["schema"] == "crt_object_relations/v1"
    assert data["policy"] == "P-CRT-LIQ-01"
    return data


def _engine_ast() -> ast.Module:
    return ast.parse(_ENGINE.read_text(encoding="utf-8"))


def _fn(tree: ast.Module, qualname: str) -> ast.FunctionDef:
    """Find a function, optionally Class.method."""
    if "." in qualname:
        cls_name, fn_name = qualname.split(".", 1)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == cls_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == fn_name:
                        return item
        raise AssertionError(f"missing {_ENGINE.name}::{qualname}")
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == qualname:
            return node
    raise AssertionError(f"missing {_ENGINE.name}::{qualname}")


def _src(node: ast.AST) -> str:
    return ast.unparse(node)


# ── per-relation checks ─────────────────────────────────────────────────────


def types_m15_slr_is_not_htf_builder() -> None:
    assert M15StructuralLiquidityRange is not HTFBuilder
    assert not issubclass(HTFBuilder, M15StructuralLiquidityRange)
    assert not hasattr(HTFBuilder, "h_ref")


def types_m15_slr_is_not_parent_range() -> None:
    assert M15StructuralLiquidityRange is not ParentRange
    assert type(ParentRange(h_ref=1.0, l_ref=0.0, formed_at_index=0)) is not M15StructuralLiquidityRange


def detect_sweep_reads_active_range_hl() -> None:
    fn = _fn(_engine_ast(), "RangeDetector.detect_sweep")
    text = _src(fn)
    assert "active_range.h_ref" in text
    assert "active_range.l_ref" in text
    args = [a.arg for a in fn.args.args]
    assert "active_range" in args


def crt_engine_has_no_smc_import() -> None:
    text = _ENGINE.read_text(encoding="utf-8")
    assert "features.smc" not in text
    assert "from features.smc" not in text


def detect_sweep_body_omits_parent_range() -> None:
    fn = _fn(_engine_ast(), "RangeDetector.detect_sweep")
    text = _src(fn)
    assert "ParentRange" not in text
    assert "ParentCRTTrack" not in text
    assert "parent_state" not in text


def reset_compares_clock_id() -> None:
    fn = _fn(_engine_ast(), "ResetLogic.should_reset")
    text = _src(fn)
    assert "current_htf_id" in text
    assert "clock_id" in text or "htf_candle_id" in text
    assert "HTF changed" in text


def parent_state_only_at_execution_filter() -> None:
    tree = _engine_ast()
    sweep = _src(_fn(tree, "RangeDetector.detect_sweep"))
    assert "parent_state" not in sweep
    proc = _fn(tree, "CRTEngine.process_candle")
    args = [a.arg for a in proc.args.args]
    assert "parent_state" in args
    text = _src(proc)
    assert "Against parent-timeframe bias" in text
    assert "parent_state" in text
    # Founding path must not consult parent bias.
    range_branch_marker = "detect_sweep"
    bias_marker = "Against parent-timeframe bias"
    assert text.index(range_branch_marker) < text.index(bias_marker)


# Map YAML check names → callables. Adding a YAML check without an entry fails the suite.
_CHECKS = {
    "types_m15_slr_is_not_htf_builder": types_m15_slr_is_not_htf_builder,
    "types_m15_slr_is_not_parent_range": types_m15_slr_is_not_parent_range,
    "detect_sweep_reads_active_range_hl": detect_sweep_reads_active_range_hl,
    "crt_engine_has_no_smc_import": crt_engine_has_no_smc_import,
    "detect_sweep_body_omits_parent_range": detect_sweep_body_omits_parent_range,
    "reset_compares_clock_id": reset_compares_clock_id,
    "parent_state_only_at_execution_filter": parent_state_only_at_execution_filter,
}


def test_relation_table_is_closed_and_complete():
    data = _load()
    objects = data["objects"]
    for name, spec in objects.items():
        path = _REPO / spec["path"]
        assert path.is_file(), f"{name}: missing {spec['path']}"
    names = set(objects)
    checks_used: set[str] = set()
    rel_ids: set[str] = set()
    for rel in data["relations"]:
        assert rel["id"] not in rel_ids
        rel_ids.add(rel["id"])
        assert rel["relation"] in _ALLOWED_RELATIONS, rel
        assert rel["source"] in names, rel
        assert rel["dest"] in names, rel
        check = rel["check"]
        assert check in _CHECKS, f"YAML check {check!r} has no function"
        checks_used.add(check)
    unused = set(_CHECKS) - checks_used
    assert not unused, f"check functions not referenced by YAML: {unused}"


@pytest.mark.parametrize("check_name", sorted(_CHECKS))
def test_each_relation_check(check_name: str):
    _CHECKS[check_name]()


def test_parent_track_type_is_not_the_m15_envelope():
    assert ParentCRTTrack is not M15StructuralLiquidityRange
    assert inspect.isclass(ResetLogic)
    assert inspect.isfunction(RangeDetector.detect_sweep)


def test_relations_closed_does_not_close_crt_or_economics():
    """CT-009 CLOSED ≠ CRT CLOSED ≠ economically validated."""
    data = _load()
    assert data["closure_status"] == "CLOSED"
    assert data["closure_token"] == "CRT_OBJECT_RELATIONS_STATUS = CLOSED"
    assert "CRT" in data["does_not_close"]
    assert "G001" in data["does_not_close"]
    assert "SEM-011_domain_meaning" in data["does_not_close"]

    closure = (_REPO / "docs/governance/crt_object_relations_closure.md").read_text(
        encoding="utf-8"
    )
    assert "CRT_OBJECT_RELATIONS_STATUS = CLOSED" in closure
    assert "CRT_CLOSURE_STATUS = REOPENED" in closure
    assert "economically_validated: false" in closure
    assert "SEM-011" in closure and "CHARACTERIZED" in closure
    # Next-work lanes exist and are not implied closed by this surface
    for lane in (
        "semantic certification",
        "measurement / evidence",
        "economic qualification",
    ):
        assert lane in closure.lower() or lane.replace(" / ", "/") in closure.lower()
    assert "three lanes only" in closure.lower()

    crt_report = (_REPO / "docs/governance/crt_closure_report.md").read_text(encoding="utf-8")
    assert "CRT_CLOSURE_STATUS = REOPENED" in crt_report

    index = json.loads(
        (_REPO / "docs/governance/closure_authority_index.json").read_text(encoding="utf-8")
    )
    by_id = {s["surface_id"]: s for s in index["surfaces"]}
    rel = by_id["CRT_OBJECT_RELATIONS"]
    assert rel["status"] == "CLOSED"
    assert rel["economically_validated"] is False
    assert by_id["CRT"]["status"] == "OPEN"
    assert by_id["CRT"]["economically_validated"] is False
    assert "CRT" in rel["downstream_not_implied_closed"]

    ont = (_REPO / "configs/formulas/market_ontology.yaml").read_text(encoding="utf-8")
    assert "id:                     SEM-011" in ont
    sem011 = ont.split("id:                     SEM-011", 1)[1][:600]
    assert "knowledge_status:       CHARACTERIZED" in sem011
