"""Thin CLI refuse-without-paper and import smoke."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CLI = _ROOT / "scripts" / "live" / "run_live_rail.py"
_spec = importlib.util.spec_from_file_location("run_live_rail_cli", _CLI)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
main = _mod.main


def test_refuse_without_paper_flag() -> None:
    rc = main(["--config", "configs/experimental/spec/live_rail_tickdb_paper_run.json"])
    assert rc == 2


def test_refuse_missing_config(tmp_path: Path) -> None:
    rc = main(["--paper", "--config", str(tmp_path / "nope.json")])
    assert rc == 2
