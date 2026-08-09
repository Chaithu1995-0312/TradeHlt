"""`scale_free_v1` mask must zero every price-unit dim across BOTH schema generations.

The mask is name-based. v3 called the candle-range dim `wick_size`; the v4
ALIGNMENT_REMAP renamed it `candle_range` (numerically inert at the time, because the
dim was already zero-weighted). If the converter lists only the v3 name, a retrain on a
v4+ schema silently re-admits a price-unit dim to the Gaussian score — making zone
similarity depend on raw instrument scale, the defect class `scale_free_v1` exists to
prevent (cf. F-061 dimensional-mix).

Both names are therefore listed. These tests pin that, and pin that the converter still
reproduces the live v3 artifact exactly (its provenance claim).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "scripts" / "research"))

from features.feature_schema import CANONICAL_FEATURE_ORDER  # noqa: E402


def _load_cz():
    spec = importlib.util.spec_from_file_location(
        "convert_zones_v1_to_gaussian",
        _REPO / "scripts" / "research" / "convert_zones_v1_to_gaussian.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cz = _load_cz()

_V3 = _REPO / "models" / "zone_registry.json"
_V4 = _REPO / "models" / "zone_registry_v4_2026_07.json"


def _zone0(doc: dict) -> dict:
    zones = doc["zones"]
    return zones[0] if isinstance(zones, list) else list(zones.values())[0]


# ── provenance: the converter must still reproduce v3 exactly ────────────────
def test_v3_weights_are_reproduced_exactly():
    v3 = json.loads(_V3.read_text(encoding="utf-8"))
    weights, _ = cz.scale_free_weights(v3["feature_order"])
    assert weights == _zone0(v3)["weights"]


def test_v3_has_25_active_dims():
    v3 = json.loads(_V3.read_text(encoding="utf-8"))
    weights, _ = cz.scale_free_weights(v3["feature_order"])
    assert sum(1 for w in weights if w > 0) == 25


# ── both schema generations zero the candle-range dim ────────────────────────
def test_both_names_for_the_candle_range_dim_are_masked():
    assert "wick_size" in cz.ABSOLUTE_SCALE_FEATURES
    assert "candle_range" in cz.ABSOLUTE_SCALE_FEATURES


def test_v4_schema_zeroes_candle_range():
    v4 = json.loads(_V4.read_text(encoding="utf-8"))
    order = v4["feature_order"]
    weights, zero_idx = cz.scale_free_weights(order)
    assert order.index("candle_range") in zero_idx
    assert weights[order.index("candle_range")] == 0.0


def test_no_price_unit_dim_survives_on_the_live_schema():
    """Regression guard: every absolute-scale name present in the live canonical
    order must land on weight 0.0."""
    order = [n for n in CANONICAL_FEATURE_ORDER if n != "macd_hist_raw"]
    weights, _ = cz.scale_free_weights(order)
    for name in cz.ABSOLUTE_SCALE_FEATURES:
        if name in order:
            assert weights[order.index(name)] == 0.0, name


# ── the v5 retrain shape ─────────────────────────────────────────────────────
def test_v5_subset_shape():
    """38-name subset -> 13 zeroed, 25 active at 0.04 (same active count as v3)."""
    order = [n for n in CANONICAL_FEATURE_ORDER if n != "macd_hist_raw"]
    assert len(order) == 38
    weights, zero_idx = cz.scale_free_weights(order)
    assert len(zero_idx) == 13
    active = [w for w in weights if w > 0]
    assert len(active) == 25
    assert all(abs(w - 0.04) < 1e-9 for w in active)


def test_macd_hist_raw_is_not_silently_admitted():
    """It is a price-unit dim and is NOT in the mask - so it must be excluded from
    training, not trained with a nonzero weight. If it is ever added to the trained
    vector, this test should be updated together with the mask."""
    assert "macd_hist_raw" not in cz.ABSOLUTE_SCALE_FEATURES
    full = list(CANONICAL_FEATURE_ORDER)
    weights, _ = cz.scale_free_weights(full)
    assert weights[full.index("macd_hist_raw")] > 0, (
        "macd_hist_raw would be scored if trained - it must stay excluded via "
        "discover_zones --exclude-feature, or be added to ABSOLUTE_SCALE_FEATURES"
    )
