"""Contract registry + soft-default ban for research.model_runners."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.model_runners.contracts import MODEL_CATALOG, get_contract, list_models
from research.model_runners.envelope import ALLOWED_FORMATS, DEFAULT_FORMATS, parse_formats
from research.model_runners.require_config import require_key, require_section


PKG = Path(__file__).resolve().parents[2] / "src" / "research" / "model_runners"


def test_catalog_has_live_four_and_blocked():
    ids = set(MODEL_CATALOG)
    for need in ("rr", "gaussian", "zone_gate", "crt_score", "llm_gate", "strategies"):
        assert need in ids
    runnable = {m.model_id for m in list_models() if m.runnable}
    assert {"rr", "gaussian", "zone_gate", "crt_score"} <= runnable
    for m in list_models():
        assert m.entry_point
        assert m.model_id in MODEL_CATALOG


def test_get_contract_unknown():
    with pytest.raises(KeyError, match="unknown model_id"):
        get_contract("not_a_model")


def test_require_key_missing():
    with pytest.raises(KeyError, match="missing production config: a.b"):
        require_key({}, "b", path="a")


def test_require_section():
    cfg = {"engine_runner": {"zone_registry_path": "x"}}
    sec = require_section(cfg, "engine_runner")
    assert sec["zone_registry_path"] == "x"
    with pytest.raises(KeyError, match="missing production config"):
        require_section(cfg, "nope")


def test_parse_formats_default_is_fixed_contract():
    assert parse_formats(None) == DEFAULT_FORMATS
    assert "jsonl" in DEFAULT_FORMATS
    assert "manifest" in DEFAULT_FORMATS


def test_parse_formats_rejects_unknown():
    with pytest.raises(ValueError, match="unknown format"):
        parse_formats("jsonl,banana")
    assert ALLOWED_FORMATS >= set(DEFAULT_FORMATS)


class _SoftDefaultVisitor(ast.NodeVisitor):
    """Fail on dict.get(key, literal) and `x or <Constant>` substitutes in package."""

    def __init__(self, path: Path):
        self.path = path
        self.hits: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        # mapping.get("k", default)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if len(node.args) >= 2:
                self.hits.append(
                    f"{self.path.name}:{node.lineno}: .get(..., default)"
                )
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # flag `a or "literal"` / `a or 0` style substitutes
        if isinstance(node.op, ast.Or):
            for v in node.values[1:]:
                if isinstance(v, ast.Constant) and v.value is not None and v.value is not False:
                    # allow `x or y` only if no constant substitute — constant RHS is fallback
                    self.hits.append(
                        f"{self.path.name}:{node.lineno}: `or` constant fallback {v.value!r}"
                    )
        self.generic_visit(node)


def test_no_soft_defaults_in_model_runners_package():
    hits: list[str] = []
    for path in PKG.rglob("*.py"):
        if path.name == "__init__.py" and path.parent == PKG:
            # package docstring only — still scan
            pass
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        v = _SoftDefaultVisitor(path)
        v.visit(tree)
        hits.extend(v.hits)
    assert hits == [], "soft-default patterns found:\n" + "\n".join(hits)
