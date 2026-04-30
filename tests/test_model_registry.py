"""
test_model_registry.py
======================
GAP-008: Atomicity and GOV-3 invariant tests for ModelRegistry and
GaussianModelRegistry.

Covers:
  - promote() leaves exactly one active model (no dual-active)
  - _assert_single_active raises on dual-active in-memory state
  - _save_atomic produces valid JSON even if caller crashes mid-write
  - get_active() falls back to registry scan when active.txt is stale
  - GaussianModelRegistry promote_gaussian GOV-3 invariant
  - Concurrent promote() calls leave exactly one active model
"""

import json
import os
import threading
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.model_registry import (
    ModelRegistry,
    GaussianModelRegistry,
    _assert_single_active,
    _save_atomic,
    PROMOTION_MARGIN,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_eval(score: float):
    ev = MagicMock()
    ev.composite_score = score
    ev.accuracy  = score
    ev.precision = score
    ev.recall    = score
    ev.bucket_stats = {}
    ev.n_samples = 100
    return ev


def _registry(tmp_path: Path) -> ModelRegistry:
    return ModelRegistry(models_dir=tmp_path)


def _gaussian_registry(tmp_path: Path) -> GaussianModelRegistry:
    return GaussianModelRegistry(models_dir=tmp_path)


def _gaussian_metrics(corr: float = 0.5) -> dict:
    return {"corr_expected_rr": corr, "calibration_error": 0.1,
            "n_train": 100, "n_val": 50}


# ---------------------------------------------------------------------------
# _assert_single_active
# ---------------------------------------------------------------------------

def test_assert_single_active_passes_with_zero():
    reg = {"a": {"promoted": False}, "b": {"promoted": False}}
    _assert_single_active(reg, "promoted")  # must not raise


def test_assert_single_active_passes_with_one():
    reg = {"a": {"promoted": True}, "b": {"promoted": False}}
    _assert_single_active(reg, "promoted")  # must not raise


def test_assert_single_active_raises_with_two():
    reg = {"a": {"promoted": True}, "b": {"promoted": True}}
    with pytest.raises(RuntimeError, match="GOV-3 violation"):
        _assert_single_active(reg, "promoted")


# ---------------------------------------------------------------------------
# _save_atomic
# ---------------------------------------------------------------------------

def test_save_atomic_produces_valid_json(tmp_path):
    path = tmp_path / "test.json"
    data = {"key": "value", "n": 42}
    _save_atomic(path, data)
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded == data


def test_save_atomic_no_tmp_left_behind(tmp_path):
    path = tmp_path / "test.json"
    _save_atomic(path, {"x": 1})
    tmp = path.with_suffix(".tmp")
    assert not tmp.exists(), ".tmp file should be cleaned up by os.replace()"


def test_save_atomic_overwrites_existing(tmp_path):
    path = tmp_path / "reg.json"
    _save_atomic(path, {"v": 1})
    _save_atomic(path, {"v": 2})
    assert json.loads(path.read_text())["v"] == 2


# ---------------------------------------------------------------------------
# ModelRegistry.try_promote — GOV-3 invariant
# ---------------------------------------------------------------------------

def test_try_promote_single_active_after_first_promotion(tmp_path):
    reg = _registry(tmp_path)
    reg.register("model_a", _make_eval(0.80))
    promoted, _ = reg.try_promote("model_a")
    assert promoted

    raw = json.loads((tmp_path / "registry.json").read_text())
    active = [k for k, v in raw.items() if v.get("promoted", False)]
    assert len(active) == 1, f"Expected 1 active, got {active}"
    assert active[0] == "model_a"


def test_try_promote_demotes_old_before_promoting_new(tmp_path):
    reg = _registry(tmp_path)
    reg.register("model_a", _make_eval(0.70))
    reg.try_promote("model_a")

    reg.register("model_b", _make_eval(0.70 + PROMOTION_MARGIN + 0.01))
    promoted, _ = reg.try_promote("model_b")
    assert promoted

    raw = json.loads((tmp_path / "registry.json").read_text())
    active = [k for k, v in raw.items() if v.get("promoted", False)]
    assert active == ["model_b"], f"Only model_b should be active, got {active}"
    assert not raw["model_a"]["promoted"]


def test_try_promote_no_dual_active_below_margin(tmp_path):
    reg = _registry(tmp_path)
    reg.register("model_a", _make_eval(0.80))
    reg.try_promote("model_a")

    # model_b just barely below margin — should NOT be promoted
    reg.register("model_b", _make_eval(0.80 + PROMOTION_MARGIN - 0.001))
    promoted, _ = reg.try_promote("model_b")
    assert not promoted

    raw = json.loads((tmp_path / "registry.json").read_text())
    active = [k for k, v in raw.items() if v.get("promoted", False)]
    assert len(active) == 1
    assert active[0] == "model_a"


# ---------------------------------------------------------------------------
# ModelRegistry.get_active — fallback to registry scan
# ---------------------------------------------------------------------------

def test_get_active_fallback_when_active_txt_stale(tmp_path):
    reg = _registry(tmp_path)
    reg.register("model_a", _make_eval(0.80))
    reg.try_promote("model_a")

    # Corrupt active.txt to point at a non-existent model
    (tmp_path / "active.txt").write_text("ghost_model")

    # get_active() must fall back to registry promoted=True scan
    active = reg.get_active()
    assert active == "model_a", (
        f"get_active() should fall back to registry scan, got '{active}'"
    )


def test_get_active_fallback_when_active_txt_missing(tmp_path):
    reg = _registry(tmp_path)
    reg.register("model_a", _make_eval(0.80))
    reg.try_promote("model_a")
    (tmp_path / "active.txt").unlink()

    active = reg.get_active()
    assert active == "model_a"


# ---------------------------------------------------------------------------
# Concurrent promote() — no dual-active under threading
# ---------------------------------------------------------------------------

def test_concurrent_promote_no_dual_active(tmp_path):
    """
    GAP-008: two threads promoting different models simultaneously must result
    in exactly one active model.
    """
    reg = _registry(tmp_path)
    reg.register("model_a", _make_eval(0.70))
    reg.register("model_b", _make_eval(0.70 + PROMOTION_MARGIN + 0.05))
    reg.register("model_c", _make_eval(0.70 + PROMOTION_MARGIN + 0.10))

    errors = []

    def promote(name):
        try:
            reg.try_promote(name)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=promote, args=("model_b",))
    t2 = threading.Thread(target=promote, args=("model_c",))
    t1.start(); t2.start()
    t1.join();  t2.join()

    assert not errors, f"Threads raised: {errors}"

    raw = json.loads((tmp_path / "registry.json").read_text())
    active = [k for k, v in raw.items() if v.get("promoted", False)]
    assert len(active) == 1, f"Expected exactly 1 active after concurrent promote, got {active}"


# ---------------------------------------------------------------------------
# GaussianModelRegistry.promote_gaussian — GOV-3 invariant
# ---------------------------------------------------------------------------

def test_gaussian_promote_single_active(tmp_path):
    greg = _gaussian_registry(tmp_path)

    with patch("core.model_registry.SCHEMA_VERSION", "v1"):
        greg.register_gaussian("v1", "m1.json", [], _gaussian_metrics(0.5))
        greg.register_gaussian("v2", "m2.json", [], _gaussian_metrics(0.6))

        promoted, _ = greg.promote_gaussian("v1", force=True)
        assert promoted

        promoted2, _ = greg.promote_gaussian("v2", force=True)
        assert promoted2

        raw = json.loads((tmp_path / "gaussian_registry.json").read_text())
        active = [k for k, v in raw.items() if v.get("active", False)]
        assert len(active) == 1, f"Expected 1 active Gaussian, got {active}"
        assert active[0] == "v2"
        assert not raw["v1"]["active"]


def test_gaussian_promote_blocks_regression(tmp_path):
    greg = _gaussian_registry(tmp_path)

    with patch("core.model_registry.SCHEMA_VERSION", "v1"):
        greg.register_gaussian("v1", "m1.json", [], _gaussian_metrics(0.5))
        greg.promote_gaussian("v1", force=True)

        greg.register_gaussian("v2", "m2.json", [], _gaussian_metrics(0.48))
        promoted, reason = greg.promote_gaussian("v2")  # max_regression=0.01 default
        assert not promoted
        assert "BLOCKED" in reason
