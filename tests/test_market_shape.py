"""Floor for the Market Shape layer (src/features/market_shape.py + configs/formulas/market_shapes.yaml).

Proves shape identity is content-addressed over the PROJECTED context (invariant to
out-of-projection dimensions), naming is strict first-match over declared states only,
the spec loader rejects every malformed form at load, and X_ drift can never wear a shape name.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from features.feature_states import FeatureStateEncoder, X_PREFIX
from features.market_context import MarketContextBuilder
from features.market_shape import MarketShapeClassifier, SHAPE_ID_PREFIX


@pytest.fixture(scope="module")
def enc() -> FeatureStateEncoder:
    return FeatureStateEncoder()


@pytest.fixture(scope="module")
def builder() -> MarketContextBuilder:
    return MarketContextBuilder()


@pytest.fixture(scope="module")
def clf(builder) -> MarketShapeClassifier:
    return MarketShapeClassifier(builder)


def _states(enc, **overrides: str) -> dict[str, str]:
    """All-zeros legal state mapping with named overrides."""
    base = {n: enc.spec(n).value_to_state[0] for n in enc.vector_bound_features}
    for k, v in overrides.items():
        assert k in base, f"override {k} is not vector-bound"
        base[k] = v
    return base


def _shape(clf, builder, enc, **overrides):
    return clf.classify_context(builder.build(_states(enc, **overrides)))


# ── spec loading ─────────────────────────────────────────────────────────────

def test_real_spec_loads_with_expected_shapes(clf):
    names = [s.name for s in clf.shapes]
    assert names[0] == "DoubleSweepTrap"  # precedence head
    for expected in ("BuySideLiquidityGrab", "Compression", "BullishBreakoutExpansion"):
        assert expected in names
    assert clf.projection == ("Trend", "Volatility", "Liquidity", "MarketStructure")


def test_unsatisfiable_trend_continuation_stays_blocked(clf):
    """Layer-6 discovery (2026-07-24): {HigherHigh, NoSweep, NoBreak} is a logical contradiction —
    all three states compare against the same reference, so HigherHigh forces Break-or-Sweep
    exhaustively. The shape was removed to blocked_shapes; declaring it again as a single-bar
    predicate would reintroduce a predicate that can never fire (and its floor test could only
    pass on hand-built impossible inputs, which is how v1 slipped through)."""
    assert not any("TrendContinuation" in s.name for s in clf.shapes)


@pytest.mark.parametrize("bad_yaml, err_fragment", [
    # unknown feature in a predicate
    ("projection: [Liquidity]\nshapes:\n  - name: A\n    when:\n      not_a_feature: [NoSweep]\n",
     "not a vector-bound stateful feature"),
    # undeclared state name (typo) — must be a LOAD error
    ("projection: [Liquidity]\nshapes:\n  - name: A\n    when:\n      liquidity_sweep: [BuySweep]\n",
     "no declared state"),
    # predicate feature outside the projection
    ("projection: [Liquidity]\nshapes:\n  - name: A\n    when:\n      trend_bias: [Bullish]\n",
     "inside the projection"),
    # unknown projection dimension
    ("projection: [Sentiment]\nshapes:\n  - name: A\n    when:\n      liquidity_sweep: [NoSweep]\n",
     "unknown/unpopulated"),
    # duplicate shape name
    ("projection: [Liquidity]\nshapes:\n  - name: A\n    when: {liquidity_sweep: [NoSweep]}\n"
     "  - name: A\n    when: {liquidity_sweep: [NoSweep]}\n",
     "duplicate"),
    # empty when
    ("projection: [Liquidity]\nshapes:\n  - name: A\n    when: {}\n", "empty `when`"),
    # no shapes at all
    ("projection: [Liquidity]\nshapes: []\n", "no shapes"),
])
def test_malformed_specs_raise_at_load(tmp_path, builder, bad_yaml, err_fragment):
    p = tmp_path / "shapes.yaml"
    p.write_text(bad_yaml, encoding="utf-8")
    with pytest.raises(ValueError) as e:
        MarketShapeClassifier(builder, spec_path=p)
    assert err_fragment in str(e.value)


# ── content-addressed identity + projection invariance ───────────────────────

def test_shape_id_deterministic_and_prefixed(clf, builder, enc):
    a = _shape(clf, builder, enc)
    b = _shape(clf, builder, enc)
    assert a.shape_id == b.shape_id
    assert a.shape_id.startswith(SHAPE_ID_PREFIX)


def test_out_of_projection_changes_do_not_move_shape_id(clf, builder, enc):
    """Session (Time) and volume_spike (Volume) are conditioning variables, NOT structure —
    flipping them must leave the shape identity untouched."""
    base = _shape(clf, builder, enc)
    sess = _shape(clf, builder, enc, session="OVERLAP")
    vol = _shape(clf, builder, enc, volume_spike="VolumeSpike")
    assert base.shape_id == sess.shape_id == vol.shape_id


def test_projected_changes_move_shape_id(clf, builder, enc):
    base = _shape(clf, builder, enc)
    trend = _shape(clf, builder, enc, trend_bias="Bullish")
    sweep = _shape(clf, builder, enc, liquidity_sweep="BuySideSweep")
    assert trend.shape_id != base.shape_id
    assert sweep.shape_id != base.shape_id != trend.shape_id


# ── naming semantics ─────────────────────────────────────────────────────────

def test_named_shapes_match_their_definitions(clf, builder, enc):
    cases = {
        "BuySideLiquidityGrab": dict(liquidity_sweep="BuySideSweep",
                                     sweep_detected="SweepDetected"),
        "SellSideLiquidityGrab": dict(liquidity_sweep="SellSideSweep",
                                      sweep_detected="SweepDetected"),
        "DoubleSweepTrap": dict(double_sweep="DoubleSweep"),
        "BullishStructuralBreak": dict(break_of_structure="BullishBreak",
                                       higher_high="HigherHigh"),
        "BullishBreakoutExpansion": dict(break_of_structure="BullishBreak",
                                         volatility_regime="HighVolatility"),
        "Compression": dict(volatility_regime="LowVolatility"),
    }
    for expected, overrides in cases.items():
        shape = _shape(clf, builder, enc, **overrides)
        assert shape.name == expected, f"{overrides} -> {shape.name}, wanted {expected}"
        assert shape.matched and shape.label == expected


def test_precedence_first_match_wins(clf, builder, enc):
    # Matches BOTH DoubleSweepTrap and BuySideLiquidityGrab — declared order decides.
    shape = _shape(clf, builder, enc,
                   double_sweep="DoubleSweep", liquidity_sweep="BuySideSweep",
                   sweep_detected="SweepDetected")
    assert shape.name == "DoubleSweepTrap"
    # Expansion outranks the bare StructuralBreak for the same break state.
    shape2 = _shape(clf, builder, enc,
                    break_of_structure="BullishBreak", volatility_regime="HighVolatility")
    assert shape2.name == "BullishBreakoutExpansion"


def test_unmatched_context_is_explicit_unnamed(clf, builder, enc):
    # NormalVolatility + no events matches nothing (Compression requires LowVolatility).
    shape = _shape(clf, builder, enc, volatility_regime="NormalVolatility")
    assert shape.name is None and shape.family is None and not shape.matched
    assert shape.label == f"UNNAMED({shape.shape_id})"


def test_families_group_directional_variants(clf):
    fams = {s.name: s.family for s in clf.shapes}
    assert fams["BuySideLiquidityGrab"] == fams["SellSideLiquidityGrab"] == "LiquidityGrab"
    assert fams["BullishStructuralBreak"] == fams["BearishStructuralBreak"] == "StructuralBreak"


# ── X_ drift can never wear a name ───────────────────────────────────────────

def test_drifted_state_yields_unnamed_with_markers(clf, builder, enc):
    states = _states(enc, liquidity_sweep="BuySideSweep", sweep_detected="SweepDetected")
    states["trend_bias"] = f"{X_PREFIX}UNMAPPED(0.5)"
    shape = clf.classify_context(builder.build(states))
    # trend_bias drift is inside the projection: identity still assigned, name possible only if
    # no predicate touches the drifted feature — BuySideLiquidityGrab doesn't, so it may match;
    # but a predicate ON the drifted feature can never match:
    assert shape.x_markers == (f"trend_bias={X_PREFIX}UNMAPPED(0.5)",)
    states2 = _states(enc)
    states2["liquidity_sweep"] = f"{X_PREFIX}UNMAPPED(9.0)"
    states2["double_sweep"] = "DoubleSweep"
    shape2 = clf.classify_context(builder.build(states2))
    assert shape2.name == "DoubleSweepTrap"  # predicate untouched by the drifted feature
    states3 = _states(enc)
    states3["liquidity_sweep"] = f"{X_PREFIX}UNMAPPED(9.0)"
    shape3 = clf.classify_context(builder.build(states3))
    assert shape3.name is None  # grab predicates need liquidity_sweep, which is drifted


# ── pipeline-truth survey ────────────────────────────────────────────────────

def _synthetic(n: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    body_top = np.maximum(open_, close)
    body_bot = np.minimum(open_, close)
    high = body_top + rng.uniform(0.05, 0.8, n)
    low = body_bot - rng.uniform(0.05, 0.8, n)
    volume = rng.uniform(100, 1000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": volume})


def test_survey_on_a_real_pipeline_run(clf):
    from features.feature_pipeline import FeaturePipeline

    _df, vectors = FeaturePipeline(_synthetic()).run()
    report = clf.survey(vectors)
    assert sum(report["by_label"].values()) == len(vectors)  # total function: every bar shaped
    assert len(report["by_shape_id"]) < len(vectors)          # shapes RECUR
    named = sum(n for lbl, n in report["by_label"].items() if not lbl.startswith("UNNAMED"))
    assert named > 0, "no named shape occurred on a 400-bar random walk — predicates dead?"
    for shape_vecs in vectors[:: max(1, len(vectors) // 20)]:
        assert not clf.classify_vector(shape_vecs).x_markers
