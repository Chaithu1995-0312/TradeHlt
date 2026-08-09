"""Governance floor: unauthorized models/ path literals outside ModelPaths.

Enforces the Phase-0 architectural boundary without requiring immediate loader
migrations. Grandfathered debt lives in docs/governance/model_paths_literal_debt.json
and may only shrink (ratchet). New unauthorized literals FAIL CI.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCANNER = _REPO / "scripts" / "governance" / "scan_model_paths_literals.py"
_DEBT = _REPO / "docs" / "governance" / "model_paths_literal_debt.json"


def _load_scanner():
    spec = importlib.util.spec_from_file_location("scan_model_paths_literals", _SCANNER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def scan():
    return _load_scanner()


def test_debt_file_exists_and_schema(scan) -> None:
    assert _DEBT.exists(), "missing model_paths_literal_debt.json — run scanner --write-debt"
    doc = json.loads(_DEBT.read_text(encoding="utf-8"))
    assert doc.get("version") == 1
    assert isinstance(doc.get("debt"), list)
    assert doc["debt"], "debt list empty — unexpected; regenerate or check scanner"
    for entry in doc["debt"]:
        assert "file" in entry and "literal" in entry
        assert "models/" in entry["literal"].replace("\\", "/"), (
            f"debt token must retain models/ window: {entry['file']}"
        )


def test_approved_modules_include_model_paths(scan) -> None:
    assert scan.is_approved_module("src/config_layer/model_paths.py")
    assert scan.is_approved_module("src/config_layer/model_resolver.py")
    assert scan.is_approved_module("src/utils/zone_schema_migrator.py")
    assert scan.is_approved_module("tests/test_model_paths_literals.py")
    assert scan.is_approved_module("scripts/research/convert_zones_v1_to_gaussian.py")
    assert not scan.is_approved_module("src/core/engine_runner.py")
    assert not scan.is_approved_module("src/engines/live_engine.py")


def test_model_paths_may_contain_models_root_constant(scan) -> None:
    """model_paths.py is approved — scanner must not report it as unauthorized."""
    hits = scan.scan_roots([_REPO / "src"], repo=_REPO)
    assert not any(h["file"].endswith("model_paths.py") for h in hits)


def test_no_new_unauthorized_models_path_literals(scan) -> None:
    """Ratchet: actual unauthorized (file, literal) ⊆ debt; no NEW pairs."""
    hits = scan.scan_roots([_REPO / "src"], repo=_REPO)
    debt_doc = scan.load_debt(_DEBT)
    new_msgs, _stale = scan.evaluate(hits, debt_doc)
    assert not new_msgs, (
        "New unauthorized models/ path literals outside ModelPaths.\n"
        "Import ModelPaths / ModelResolver instead, or (with review) extend "
        f"{_DEBT.name} debt entries.\n" + "\n".join(new_msgs)
    )


def test_debt_is_exact_match_ratchet(scan) -> None:
    """Debt must match actual set exactly — forces removal of fixed sites (shrink-only)."""
    hits = scan.scan_roots([_REPO / "src"], repo=_REPO)
    debt_doc = scan.load_debt(_DEBT)
    new_msgs, stale_msgs = scan.evaluate(hits, debt_doc)
    assert not new_msgs, "new violations:\n" + "\n".join(new_msgs)
    assert not stale_msgs, (
        "Stale debt entries (literals already gone) — remove them from "
        f"{_DEBT.name} to keep the ratchet honest:\n" + "\n".join(stale_msgs)
    )


def test_scanner_cli_exits_zero(scan) -> None:
    assert scan.main([]) == 0
