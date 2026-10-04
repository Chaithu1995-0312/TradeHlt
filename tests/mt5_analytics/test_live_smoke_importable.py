"""
Anti-bitrot guard for the manual live-smoke harness (Phase 5.5).

Imports `tests/manual/live_smoke.py` by path and asserts its check functions exist. The
module must NOT connect to MT5 at import time (connection happens only when `main()`/the
checks run), so this stays deterministic with no terminal — it catches syntax/wiring drift
without running live.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SMOKE = Path(__file__).resolve().parents[1] / "manual" / "live_smoke.py"


def _load():
    spec = importlib.util.spec_from_file_location("live_smoke", _SMOKE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # must not connect to MT5
    return module


def test_live_smoke_imports_without_terminal():
    assert _SMOKE.exists(), f"missing {_SMOKE}"
    mod = _load()
    assert callable(mod.main)
    assert callable(mod.check_execution_unreachable)
    assert callable(mod._run_live)
    # the execution-unreachable check is structural and must run with no terminal.
    mod._results.clear()
    mod.check_execution_unreachable()
    name, status, _ = mod._results[0]
    assert name == "execution_unreachable" and status == "PASS"
