"""Smoke: Phase-1 models on a tiny synthetic OHLCV CSV (OBSERVATION_ONLY)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.model_runners.runner import RunRequest, run_model


REPO = Path(__file__).resolve().parents[2]


def _write_synth_csv(path: Path, n: int = 250) -> None:
    """Enough bars for FeaturePipeline warmup; simple random walk OHLCV."""
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.2, size=n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    volume = rng.uniform(100, 1000, size=n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


@pytest.fixture(scope="module")
def synth_csv(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("ohlcv") / "SYNTH_M15.csv"
    _write_synth_csv(p, n=250)
    return p


@pytest.mark.parametrize("model_id", ["rr", "gaussian", "crt_score"])
def test_phase1_smoke_no_zone(model_id: str, synth_csv: Path, tmp_path: Path):
    """rr / gaussian / crt_score do not need zone registry artifact."""
    out = tmp_path / "out"
    req = RunRequest(
        model_id=model_id,
        csv_path=synth_csv,
        instrument="SYNTH",
        out_dir=out,
        repo_root=REPO,
        config_path=REPO / "configs" / "production" / "v2_multi_2026_04.json",
        start=None,
        end=None,
        limit=30,
        formats="jsonl,manifest,summary",
        artifact=None,
        emit=None,
    )
    result = run_model(req)
    assert result.n_ok > 0
    assert result.manifest_path.is_file()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["authority"] == "research_only"
    assert manifest["PRODUCTION_BEHAVIOR_CHANGED"] is False
    assert manifest["model_id"] == model_id
    assert manifest["config_keys_read"] is not None
    scores = (result.run_dir / "scores.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(scores) == result.n_ok + result.n_error
    first = json.loads(scores[0])
    assert first["schema"] == "model_runner_v1"
    assert first["status"] in ("ok", "error")


def test_zone_gate_smoke_if_artifact_present(synth_csv: Path, tmp_path: Path):
    cfg_path = REPO / "configs" / "production" / "v2_multi_2026_04.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    er = cfg["engine_runner"]
    art = REPO / er["zone_registry_path"]
    if not art.is_file():
        pytest.skip(f"zone artifact absent: {art}")

    out = tmp_path / "out"
    req = RunRequest(
        model_id="zone_gate",
        csv_path=synth_csv,
        instrument="SYNTH",
        out_dir=out,
        repo_root=REPO,
        config_path=cfg_path,
        start=None,
        end=None,
        limit=20,
        formats="jsonl,manifest,summary",
        artifact=None,
        emit=None,
    )
    result = run_model(req)
    assert result.n_ok > 0
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact"] is not None
    assert "engine_runner.zone_registry_path" in manifest["config_keys_read"]


def test_cli_requires_flags():
    import importlib.util

    cli_path = REPO / "scripts" / "research" / "run_model_offline.py"
    spec = importlib.util.spec_from_file_location("run_model_offline_cli", cli_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(SystemExit):
        mod.main([])
