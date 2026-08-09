"""Fusion weights = config-only, fail-fast (no silent runtime default).

Invariant (user doctrine, CLAUDE.md §6.5 "NO silent config defaults"): production fusion
weights are POLICY and must come from configs/production/*.json. A missing
`fusion_engine.weight_*` must RAISE at EngineRunner construction — never fall back to a
code-embedded constant (the `FusionConfig` dataclass defaults `0.30/0.25/0.25/0.20` and the
`ENGINE_RUNNER_DEFAULTS` test fixture are a second authority reachable ONLY by direct
construction in tests, never by the runtime path).

This is a shell/behavioral floor (conventions.md §9): it pins that the runtime reads each
weight through the strict `_cfg_require` accessor and that the active config supplies them —
so the fail-fast cannot silently regress into `.get(key, literal)`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core import engine_runner

_REPO = Path(__file__).resolve().parents[1]
_WEIGHTS = ("weight_crt", "weight_gaussian", "weight_zone_gate", "weight_rr")


def test_cfg_require_raises_on_missing_weight():
    """The strict accessor used by the fusion path fails fast on any absent key."""
    partial = {"weight_crt": 0.4, "weight_gaussian": 0.2, "weight_zone_gate": 0.2}  # no weight_rr
    with pytest.raises(KeyError):
        engine_runner._cfg_require(partial, "weight_rr", "fusion_engine")


def test_runtime_reads_each_weight_via_cfg_require_not_get():
    """Source floor: every fusion weight is read strictly, never via a defaulted .get()."""
    src = (_REPO / "src" / "core" / "engine_runner.py").read_text(encoding="utf-8")
    for w in _WEIGHTS:
        assert re.search(rf'_cfg_require\(\s*_fusion_cfg_dict,\s*"{w}"', src), (
            f"{w} must be read via _cfg_require (fail-fast), not a silent default"
        )
        # And it must NOT be read through a defaulted .get() on the fusion dict.
        assert not re.search(rf'_fusion_cfg_dict\.get\(\s*"{w}"', src), (
            f"{w} must not use _fusion_cfg_dict.get(...) — that reintroduces a silent default"
        )


def test_active_production_config_supplies_all_fusion_weights():
    """Branch-scoped (§4.0): the ACTIVE config must physically carry all four weights."""
    version = (_REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    cfg = json.loads((_REPO / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8"))
    fusion = cfg["fusion_engine"]
    for w in _WEIGHTS:
        assert w in fusion, f"active config {version}: fusion_engine.{w} missing (fail-fast would trip)"
        assert isinstance(fusion[w], (int, float))
