"""EPIC-84 L-C (src/features): dataset_validator's MIN_RECORDS_TO_TRAIN /
MIN_RECORDS_RECOMMEND module constants no longer fall back to code literals
(200 / 500) on ANY exception loading the "training" config section (missing
file, wrong version, JSON error, or a genuinely absent section) — they are
now required, and the active config already declares both (10 / 10).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))


def test_module_reads_declared_active_config_values():
    import features.dataset_validator as m
    importlib.reload(m)
    assert m.MIN_RECORDS_TO_TRAIN == 10
    assert m.MIN_RECORDS_RECOMMEND == 10


def test_module_import_raises_when_training_section_absent(monkeypatch):
    import config_layer.production_config as prod_config

    def _boom(section, version=None):
        raise RuntimeError("Section 'training' not found in production config")

    monkeypatch.setattr(prod_config, "get_prod_section", _boom)
    import features.dataset_validator as m
    with pytest.raises(RuntimeError, match="training"):
        importlib.reload(m)
    # restore real config state so any test running after this one in-process
    # (module-level reload mutates shared global state) sees the real values.
    monkeypatch.undo()
    importlib.reload(m)
