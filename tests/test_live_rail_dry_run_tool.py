"""PR-4d: live_hook.dry_run rewrites to feeder + HookedLiveEngine.process."""
from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

from agent.modes.pipeline_mode import _live_dry_run
from features.feature_pipeline import required_warmup_rows
from runtime.live_engine_hook import HookedLiveEngine

_MODE = Path(__file__).resolve().parents[1] / "src" / "agent" / "modes" / "pipeline_mode.py"


def _write_bars(path: Path, n: int) -> None:
    rng = np.random.default_rng(7)
    close = 2000.0
    lines = []
    for i in range(n):
        close = close + float(rng.normal(0.0, 0.4))
        high = close + abs(float(rng.normal(0.0, 0.2)))
        low = close - abs(float(rng.normal(0.0, 0.2)))
        open_ = close - float(rng.normal(0.0, 0.1))
        ts = datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i)
        lines.append(json.dumps({
            "ts": ts.isoformat(),
            "open": max(open_, low),
            "high": max(high, open_, close),
            "low": min(low, open_, close),
            "close": close,
            "volume": 100.0 + i,
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_source_has_no_live_engine_hook_or_simulate_one() -> None:
    src = _MODE.read_text(encoding="utf-8")
    assert "LiveEngineHook" not in src
    assert "simulate_one" not in src
    assert "dry_run_ok" not in src
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_live_dry_run"
    )
    names = [
        alias.name
        for node in ast.walk(fn)
        if isinstance(node, ast.ImportFrom) and node.module == "runtime.live_engine_hook"
        for alias in node.names
    ]
    assert names == ["HookedLiveEngine"]


def test_missing_history_refuses() -> None:
    out = _live_dry_run("XAUUSD")
    assert out["status"] == "error"
    assert out["error"] == "feeder_not_ready"


def test_short_history_refuses_without_process(tmp_path: Path) -> None:
    bars = tmp_path / "bars.jsonl"
    _write_bars(bars, 3)
    with patch.object(HookedLiveEngine, "process") as proc:
        out = _live_dry_run("XAUUSD", bars_jsonl=str(bars))
    assert out["status"] == "error"
    assert out["error"] == "feeder_not_ready"
    assert out["need"] == required_warmup_rows() + 1
    proc.assert_not_called()


def test_warm_history_calls_process_with_xor_off(tmp_path: Path) -> None:
    bars = tmp_path / "bars.jsonl"
    _write_bars(bars, required_warmup_rows() + 1)
    with patch.object(
        HookedLiveEngine, "process", return_value={"ultron": {"decision": "reject"}}
    ) as proc:
        out = _live_dry_run("XAUUSD", bars_jsonl=str(bars))
    assert out["status"] == "ok"
    assert out["hook_submit_orders"] is False
    proc.assert_called_once()
    args, kwargs = proc.call_args
    assert args[0]["symbol"] == "XAUUSD"
    assert "atr" in args[0]
    assert kwargs.get("gaussian_model") is None


def test_process_failure_is_error_not_ok(tmp_path: Path) -> None:
    bars = tmp_path / "bars.jsonl"
    _write_bars(bars, required_warmup_rows() + 1)
    with patch.object(HookedLiveEngine, "process", side_effect=KeyError("canonical")):
        out = _live_dry_run("XAUUSD", bars_jsonl=str(bars))
    assert out["status"] == "error"
    assert "canonical" in out["error"]
    assert out.get("status") != "dry_run_ok"
