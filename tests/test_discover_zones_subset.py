"""`discover_zones --exclude-feature` — training a documented subset of the live schema.

Added for the ZoneGate v5 causal retrain: the live schema is 39-dim, but the zone model
scores a 38-name subset (`macd_hist_raw` is a price-unit dim that `scale_free_v1`
zero-weights anyway, so training it would add an inert dimension). Excluding it means
centroids and sigma are estimated on exactly the names the model scores.

The load-bearing guarantee is BACKWARD PARITY: with no `--exclude-feature`, behavior is
byte-identical to every prior zone_v1 run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from features.feature_schema import CANONICAL_FEATURE_ORDER  # noqa: E402


def _load_dz():
    """discover_zones.py is a script, not a package module - load it by path."""
    spec = importlib.util.spec_from_file_location(
        "discover_zones", _REPO / "scripts" / "research" / "discover_zones.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dz = _load_dz()


# ── backward parity (the acceptance criterion) ───────────────────────────────
def test_default_is_the_full_canonical_order():
    assert dz.active_feature_order() == list(CANONICAL_FEATURE_ORDER)
    assert dz.active_feature_order(()) == list(CANONICAL_FEATURE_ORDER)


def test_default_vector_extraction_unchanged():
    rec = {"features": {n: float(i) for i, n in enumerate(CANONICAL_FEATURE_ORDER)}}
    weights = [1.0] * len(CANONICAL_FEATURE_ORDER)
    assert dz._vector_from_record(rec, weights) == [
        float(i) for i in range(len(CANONICAL_FEATURE_ORDER))
    ]


# ── subset behavior ──────────────────────────────────────────────────────────
def test_exclusion_drops_exactly_the_named_dim_and_preserves_order():
    sub = dz.active_feature_order(["macd_hist_raw"])
    assert "macd_hist_raw" not in sub
    assert len(sub) == len(CANONICAL_FEATURE_ORDER) - 1
    assert sub == [n for n in CANONICAL_FEATURE_ORDER if n != "macd_hist_raw"]


def test_vector_subset_equals_full_minus_excluded_index():
    sub = dz.active_feature_order(["macd_hist_raw"])
    rec = {"features": {n: float(i) for i, n in enumerate(CANONICAL_FEATURE_ORDER)}}
    full = dz._vector_from_record(rec, [1.0] * len(CANONICAL_FEATURE_ORDER))
    part = dz._vector_from_record(rec, [1.0] * len(sub), sub)
    idx = list(CANONICAL_FEATURE_ORDER).index("macd_hist_raw")
    assert part == [v for j, v in enumerate(full) if j != idx]


def test_multiple_exclusions():
    sub = dz.active_feature_order(["macd_hist_raw", "session"])
    assert len(sub) == len(CANONICAL_FEATURE_ORDER) - 2
    assert "session" not in sub and "macd_hist_raw" not in sub


# ── fail-closed ──────────────────────────────────────────────────────────────
def test_unknown_feature_name_raises():
    """A typo must not silently exclude nothing and mislabel the trained model."""
    with pytest.raises(ValueError) as exc:
        dz.active_feature_order(["macd_hist_rawww"])
    assert "macd_hist_rawww" in str(exc.value)


def test_weights_length_must_match_active_order(tmp_path):
    with pytest.raises(ValueError) as exc:
        dz.discover(
            [tmp_path / "nonexistent.jsonl"],
            n_clusters=8,
            min_samples=15,
            feature_weights=[1.0] * len(CANONICAL_FEATURE_ORDER),  # 39 vs 38 active
            exclude_features=["macd_hist_raw"],
        )
    assert "feature_weights length" in str(exc.value)


# ── provenance ───────────────────────────────────────────────────────────────
def test_record_missing_an_active_feature_is_skipped():
    sub = dz.active_feature_order(["macd_hist_raw"])
    feats = {n: 1.0 for n in CANONICAL_FEATURE_ORDER}
    del feats[sub[0]]
    assert dz._vector_from_record({"features": feats}, [1.0] * len(sub), sub) is None


def test_record_missing_only_the_excluded_feature_still_usable():
    """A corpus without macd_hist_raw must remain trainable for the subset."""
    sub = dz.active_feature_order(["macd_hist_raw"])
    feats = {n: 1.0 for n in CANONICAL_FEATURE_ORDER if n != "macd_hist_raw"}
    assert dz._vector_from_record({"features": feats}, [1.0] * len(sub), sub) is not None
