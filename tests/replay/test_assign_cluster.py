"""
tests/replay/test_assign_cluster.py
===================================
Regression tests for ReplayMemoryEngine._assign_cluster (RME forensic-audit
precondition #2 — the "cluster-0 collapse" repair).

Background
----------
The producer (scripts/research/discover_zones.py) writes zone ``center`` values
in *weighted* feature space (each feature multiplied by ``feature_weights``
before K-Means). The consumer previously (a) read the wrong key ``centroid`` and
(b) built an *unweighted* query vector — so every record collapsed to cluster 0.
These tests pin the fixed behaviour:

    1. Non-collapse: a record near zone B assigns to B (not 0).
    2. Non-collapse over a batch: both clusters get used.
    3. Weighting is consumed: weights change the winning zone.
    4. Legacy ``centroid`` key still works (back-compat).
    5. Empty / missing registry → 0 (unchanged contract).
    6. Determinism: same inputs twice → identical assignment.
    7. Registry guard: the generated zone_v1 replay registry validates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from replay.replay_memory_engine import ReplayMemoryEngine


def _engine_with_registry(registry: dict | None) -> ReplayMemoryEngine:
    """Construct an engine and inject a zone registry directly (bypass load)."""
    eng = ReplayMemoryEngine(opportunities_dir="logs")
    eng._zone_registry = registry
    return eng


# ── 1. Non-collapse: record near zone B → cluster B, not 0 ───────────────────

def test_assign_picks_nearest_nonzero_zone():
    reg = {
        "feature_order":   ["a", "b"],
        "feature_weights": [1.0, 1.0],
        "zones": [
            {"zone_id": 0, "center": [0.0, 0.0]},
            {"zone_id": 1, "center": [10.0, 10.0]},
        ],
    }
    eng = _engine_with_registry(reg)
    assert eng._assign_cluster({"a": 9.5, "b": 10.2}) == 1
    assert eng._assign_cluster({"a": 0.1, "b": -0.1}) == 0


# ── 2. Non-collapse over a batch: both clusters used ─────────────────────────

def test_assign_does_not_collapse_to_zero():
    reg = {
        "feature_order":   ["a", "b"],
        "feature_weights": [1.0, 1.0],
        "zones": [
            {"zone_id": 0, "center": [0.0, 0.0]},
            {"zone_id": 1, "center": [10.0, 10.0]},
        ],
    }
    eng = _engine_with_registry(reg)
    near0 = [{"a": 0.0 + i * 0.01, "b": 0.0} for i in range(20)]
    near1 = [{"a": 10.0 - i * 0.01, "b": 10.0} for i in range(20)]
    assigned = {eng._assign_cluster(f) for f in (near0 + near1)}
    assert assigned == {0, 1}, f"collapse signature — got {assigned}"


# ── 3. Weighting is consumed (the real driver of the collapse) ───────────────

def test_weighting_changes_winning_zone():
    """Centers live in weighted space. A raw record that is nearest zone 0 in
    *raw* space must map to zone 1 once registry weights are applied — proving
    feature_weights are honoured (without them, raw OHLCV scale dominates)."""
    reg = {
        "feature_order":   ["price", "geo"],
        "feature_weights": [0.01, 10.0],   # down-weight price, up-weight geometry
        "zones": [
            # center for zone 0 matches the RAW vector [50, 0.5]
            {"zone_id": 0, "center": [50.0, 0.5]},
            # center for zone 1 matches the WEIGHTED vector [0.5, 5.0]
            {"zone_id": 1, "center": [0.5, 5.0]},
        ],
    }
    eng = _engine_with_registry(reg)
    rec = {"price": 50.0, "geo": 0.5}      # weighted → [0.5, 5.0] → zone 1
    assert eng._assign_cluster(rec) == 1


# ── 4. Legacy "centroid" key back-compat ─────────────────────────────────────

def test_legacy_centroid_key_supported():
    reg = {
        "feature_order":   ["a", "b"],
        "feature_weights": [1.0, 1.0],
        "zones": [
            {"zone_id": 0, "centroid": [0.0, 0.0]},
            {"zone_id": 1, "centroid": [10.0, 10.0]},
        ],
    }
    eng = _engine_with_registry(reg)
    assert eng._assign_cluster({"a": 9.0, "b": 11.0}) == 1


# ── 5. Empty / missing registry → 0 (unchanged contract) ─────────────────────

def test_no_registry_returns_zero():
    assert _engine_with_registry(None)._assign_cluster({"a": 1.0}) == 0


def test_empty_zones_returns_zero():
    reg = {"feature_order": ["a"], "feature_weights": [1.0], "zones": []}
    assert _engine_with_registry(reg)._assign_cluster({"a": 1.0}) == 0


def test_missing_feature_weights_defaults_to_unweighted():
    """No feature_weights → behave as equal-weight (never crash)."""
    reg = {
        "feature_order": ["a", "b"],
        "zones": [
            {"zone_id": 0, "center": [0.0, 0.0]},
            {"zone_id": 1, "center": [5.0, 5.0]},
        ],
    }
    eng = _engine_with_registry(reg)
    assert eng._assign_cluster({"a": 4.9, "b": 5.1}) == 1


# ── 6. Determinism ───────────────────────────────────────────────────────────

def test_assign_is_deterministic():
    reg = {
        "feature_order":   ["a", "b"],
        "feature_weights": [1.0, 1.0],
        "zones": [
            {"zone_id": 0, "center": [0.0, 0.0]},
            {"zone_id": 1, "center": [10.0, 10.0]},
        ],
    }
    eng = _engine_with_registry(reg)
    f = {"a": 6.0, "b": 7.0}
    assert eng._assign_cluster(f) == eng._assign_cluster(f)


# ── 7. Generated replay registries validate as zone_v1 (all instruments) ─────

_REPLAY_DIR = Path(__file__).parents[2] / "models" / "replay"
_REPLAY_REGISTRIES = sorted(_REPLAY_DIR.glob("zone_registry_*.json"))


@pytest.mark.parametrize(
    "path",
    _REPLAY_REGISTRIES or [pytest.param(None, marks=pytest.mark.skip(
        reason="no replay registries generated yet (run discover_zones --normalize)"))],
    ids=[p.stem for p in _REPLAY_REGISTRIES] or ["none"],
)
def test_generated_replay_registry_is_valid_zone_v1(path):
    from features.feature_schema import CANONICAL_FEATURE_ORDER

    reg = json.loads(path.read_text(encoding="utf-8"))
    assert reg.get("schema_version") == "zone_v1"
    assert len(reg.get("feature_weights", [])) == len(CANONICAL_FEATURE_ORDER)
    assert reg.get("feature_order") == list(CANONICAL_FEATURE_ORDER)
    zones = reg.get("zones", [])
    assert zones, "registry has no zones"
    for z in zones:
        assert "center" in z, "zone missing 'center' key"
        assert len(z["center"]) == len(CANONICAL_FEATURE_ORDER)

    # The repaired engine must assign across >1 cluster on these real centers.
    eng = _engine_with_registry(reg)
    feats = {name: 0.0 for name in CANONICAL_FEATURE_ORDER}
    # Probe each zone's own center → should map back to that zone (sanity).
    seen = set()
    for z in zones:
        probe = {name: z["center"][i] / (reg["feature_weights"][i] or 1.0)
                 for i, name in enumerate(CANONICAL_FEATURE_ORDER)}
        seen.add(eng._assign_cluster(probe))
    assert len(seen) > 1, f"registry collapses to a single cluster: {seen}"
