"""
P1 2026-07-22 — HeuristicGaussianEngine registry retry-storm cache.

Bug: when GaussianRegistry.load() failed (no active version for instrument),
``_registry`` stayed None and compute() re-called _load_registry() every bar
→ ~47k identical warnings on XAUUSD validation runs.

Fix: ``_registry_resolved`` caches success OR failure; re-attempt only when
RegistryWatcher sees gaussian_registry.json mtime advance.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from features.feature_schema import CANONICAL_FEATURES


def _feats(**overrides) -> dict:
    d = {k: 0.0 for k in CANONICAL_FEATURES}
    d["ema_fast"] = 1.01
    d["ema_slow"] = 1.00
    d["momentum_score"] = 0.1
    d.update(overrides)
    return d


@pytest.fixture
def missing_instrument_registry(tmp_path: Path) -> Path:
    """Registry with active pointers that exclude the test instrument."""
    reg = {
        "__active__": {"ETHUSDT": "v_eth"},
        "v_eth": {
            "version": "v_eth",
            "model_file": "does_not_matter.json",
            "active": True,
            "feature_schema": [],
            "trained_at": "2026-01-01T00:00:00Z",
        },
    }
    path = tmp_path / "gaussian_registry.json"
    path.write_text(json.dumps(reg), encoding="utf-8")
    return path


def test_failed_registry_load_is_cached_not_retried_every_compute(
    missing_instrument_registry: Path, caplog
):
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine

    eng = HeuristicGaussianEngine(
        {"gaussian_registry_path": str(missing_instrument_registry)},
        instrument="XAUUSD",
        preload_registry=False,
    )
    assert eng._registry_resolved is False

    with caplog.at_level(logging.WARNING, logger="engines.heuristic_gaussian_engine"):
        for _ in range(20):
            out = eng.compute(_feats())
            assert "score" in out

    assert eng._registry_resolved is True
    assert eng._registry is None
    assert eng._registry_load_error is not None
    # Exactly one warning for the failed load (not 20).
    fail_logs = [
        r for r in caplog.records
        if "registry load failed" in r.getMessage()
    ]
    assert len(fail_logs) == 1, (
        f"expected 1 registry-load warning, got {len(fail_logs)} — retry storm is back"
    )


def test_preload_failure_also_sets_resolved(missing_instrument_registry: Path):
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine

    eng = HeuristicGaussianEngine(
        {"gaussian_registry_path": str(missing_instrument_registry)},
        instrument="XAUUSD",
        preload_registry=True,
    )
    assert eng._registry_resolved is True
    assert eng._registry is None
    # Subsequent compute must not re-enter load
    calls = {"n": 0}
    original = eng._load_registry

    def _count_load():
        calls["n"] += 1
        return original()

    eng._load_registry = _count_load  # type: ignore[method-assign]
    eng.compute(_feats())
    eng.compute(_feats())
    assert calls["n"] == 0


def test_mtime_advance_allows_single_retry_after_miss(
    missing_instrument_registry: Path, tmp_path: Path
):
    """After a cached miss, promoting an active pointer must be pickable once mtime moves."""
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    import os
    import time

    eng = HeuristicGaussianEngine(
        {"gaussian_registry_path": str(missing_instrument_registry)},
        instrument="XAUUSD",
        preload_registry=True,
    )
    assert eng._registry is None and eng._registry_resolved is True

    # Artifact must exist: GaussianRegistry fail-closes when the active file is missing.
    # Absolute model_file path avoids depending on cwd models/.
    artifact = tmp_path / "xau_gaussian_stub.json"
    artifact.write_text(json.dumps({"stub": True}), encoding="utf-8")

    data = json.loads(missing_instrument_registry.read_text(encoding="utf-8"))
    data["__active__"]["XAUUSD"] = "v_xau"
    data["v_xau"] = {
        "version": "v_xau",
        "model_file": str(artifact),
        "active": True,
        "mu": 0.0,
        "sigma": 1.0,
        "feature_schema": [],
        "trained_at": "2026-07-22T00:00:00Z",
    }
    missing_instrument_registry.write_text(json.dumps(data), encoding="utf-8")
    now = time.time() + 2.0
    os.utime(missing_instrument_registry, (now, now))

    eng.compute(_feats())
    assert eng._registry is not None
    assert eng._loaded_version == "v_xau"
    assert eng._registry_load_error is None


def test_explicit_mu_override_skips_registry_entirely(tmp_path: Path, caplog):
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine

    # Empty/missing registry path would fail if consulted
    eng = HeuristicGaussianEngine(
        {
            "gaussian_registry_path": str(tmp_path / "nope.json"),
            "gaussian_mu": 0.25,
            "gaussian_sigma": 1.5,
        },
        instrument="XAUUSD",
        preload_registry=False,
    )
    with caplog.at_level(logging.WARNING, logger="engines.heuristic_gaussian_engine"):
        out = eng.compute(_feats())
    assert out["score"] is not None
    assert eng.mu == pytest.approx(0.25)
    assert eng.sigma == pytest.approx(1.5)
    assert eng._registry_resolved is False  # never needed
    assert not any("registry load failed" in r.getMessage() for r in caplog.records)


def test_resolving_instrument_still_loads_once():
    """BNB/ETH path: successful load remains one-shot until mtime change."""
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine

    eng = HeuristicGaussianEngine({}, instrument="BNBUSDT", preload_registry=True)
    assert eng._registry_resolved is True
    # May or may not have a registry depending on env; if loaded, stays loaded
    calls = {"n": 0}
    original = eng._load_registry

    def _count():
        calls["n"] += 1
        return original()

    eng._load_registry = _count  # type: ignore[method-assign]
    for _ in range(5):
        eng.compute(_feats())
    assert calls["n"] == 0
