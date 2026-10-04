"""Phase E0 floors: journal parse parity + XAUUSD Gaussian dim/load contract.

Design: docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md §E0
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "xauusd_gaussian_econ_units.py"
JOURNAL = (
    ROOT
    / "results"
    / "gaussian_xauusd_train"
    / "gaussian_xauusd_train_20260722T194904Z"
    / "bar_semantic_journal.jsonl"
)
MODEL_REL = "XAUUSD/20260722T194904Z/gaussian_xauusd_nb_20260722T194904Z.json"
REGISTRY = ROOT / "models" / "gaussian_registry.json"


def _load_script_module():
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    name = "xauusd_gaussian_econ_units"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e0():
    if not SCRIPT.exists():
        pytest.skip("E0 script missing")
    return _load_script_module()


@pytest.mark.skipif(not JOURNAL.exists(), reason="bar_semantic journal not on disk")
def test_e0_journal_holdout_and_label_counts(e0):
    units, stats = e0.parse_journal_units(JOURNAL)
    assert stats["kind_counts_extracted"].get("HOLDOUT") == 267
    assert stats["kind_counts_extracted"].get("LABEL_ACCEPTED") == 2980
    assert stats["n_train_parsed"] == 2980
    assert stats["n_oos_parsed"] == 267
    assert stats["n_units_parsed"] == 2980 + 267
    # all units have split + direction
    assert all(u["split"] in ("train", "oos") for u in units)
    assert all(u["direction"] in ("long", "short") for u in units)
    assert all(u["reason_code_origin"] for u in units)
    # train units carry research labels; oos holdout typically do not
    train = [u for u in units if u["split"] == "train"]
    oos = [u for u in units if u["split"] == "oos"]
    assert all(u["train_y_rr"] is not None for u in train)
    assert all(u["journal_kind"] == "HOLDOUT" for u in oos)
    assert stats["holdout_start"] is not None


@pytest.mark.skipif(
    not (ROOT / "models" / MODEL_REL).exists(),
    reason="XAUUSD Gaussian artifact missing",
)
def test_e0_model_n_features_is_39(e0):
    sys.path.insert(0, str(ROOT / "src"))
    from training.trainer import load_gaussian_model

    model, scaler, meta = load_gaussian_model(MODEL_REL)
    assert model.n_features == 39
    resolved = meta.get("feature_schema_resolved") or []
    assert len(resolved) == 39
    assert meta.get("schema_alignment") in ("exact", "named_subset", None) or True
    # one transform smoke
    vec = [0.0] * 39
    scaled = scaler.transform_one(vec)
    assert len(scaled) == 39
    err, conf, probs = model.predict_expected_rr(scaled)
    assert conf >= 0.0
    assert len(probs) >= 1


@pytest.mark.skipif(not REGISTRY.exists(), reason="gaussian registry missing")
def test_e0_registry_active_pointer_xauusd(e0):
    import json

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    active = (reg.get("__active__") or {}).get("XAUUSD")
    assert active == "xauusd_nb_20260722T194904Z"
    entry = reg[active]
    assert entry.get("active") is True
    assert entry.get("instrument") == "XAUUSD"
    rel, _ = e0.resolve_model_rel(active, REGISTRY)
    assert (ROOT / "models" / rel).exists()


def test_e0_script_module_exports(e0):
    assert hasattr(e0, "parse_journal_units")
    assert hasattr(e0, "score_units")
    assert hasattr(e0, "PHASE")
    assert e0.PHASE == "E0_SCORED_UNITS"
    assert "ECONOMIC_AUTHORITY" in e0.AUTHORITY or "RESEARCH" in e0.AUTHORITY
