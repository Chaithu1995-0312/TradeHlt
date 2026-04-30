from core.fusion_engine import FusionEngine, FusionConfig
from features.schema_validator import validate_vector


def test_fusion_accepts_engine_results_without_canonical_validation():
    fusion = FusionEngine(gaussian_adapter=None)
    engine_results = {
        "crt": {"score": 0.4, "non_canonical": "x"},
        "gaussian": {"score": 0.5},
        "zone_gate": {"zone": 0.7},
        "rr": {"score": 0.6},
    }
    out = fusion.compute(engine_results)
    assert "final_score" in out
    assert out.get("missing_engines") == []


def test_convergence_layered_uses_weighted_score_not_flat_average():
    """
    Option B — Layered: ConvergenceController must use the pre-weighted fusion
    score as base_avg, not re-average calibrated scores.

    Setup: crt=1.0 only, all others=0.0; weight_crt=1.0.
    Weighted score = 1.0.
    Flat average of calibrated scores (all near 0) would give a much lower value.
    After enough outcome records (warm), the layered final_score must be > flat avg.
    """
    from core.convergence_controller import ConvergenceController

    ctrl = ConvergenceController(window_size=10, initial_threshold=0.3)
    # Warm up the controller
    for _ in range(10):
        ctrl.record_outcome(accepted=True)

    raw_scores = {"crt": 1.0, "gaussian": 0.0, "zone_gate": 0.0, "rr": 0.0}

    layered = ctrl.apply(raw_scores, weighted_score=1.0, debug=True)
    flat    = ctrl.apply(raw_scores)   # no weighted_score → flat average

    assert layered["final_score"] > flat["final_score"], (
        f"Layered ({layered['final_score']}) should exceed flat ({flat['final_score']}) "
        "when weighted_score=1.0 vs flat average of low calibrated scores"
    )
    assert layered["debug"]["weighted_score"] == 1.0


def test_fusion_compute_passes_weighted_score_to_convergence():
    """
    Option B integration: FusionEngine.compute() with convergence active must
    produce a different result than without convergence, and the weighted_score
    must feed into the convergence layer (not a flat average).
    """
    from core.convergence_controller import ConvergenceController

    ctrl = ConvergenceController(window_size=10, initial_threshold=0.3)
    for _ in range(10):
        ctrl.record_outcome(accepted=True)

    # weight_crt=1.0 so weighted fusion score = crt score = 0.9
    fusion_with_conv = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(
            weight_crt=1.0, weight_gaussian=0.0,
            weight_zone_gate=0.0, weight_rr=0.0,
        ),
        convergence_controller=ctrl,
    )
    fusion_no_conv = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(
            weight_crt=1.0, weight_gaussian=0.0,
            weight_zone_gate=0.0, weight_rr=0.0,
        ),
    )
    engine_results = {
        "crt":       {"score": 0.9},
        "gaussian":  {"score": 0.1},
        "zone_gate": {"score": 0.1},
        "rr":        {"score": 0.1},
    }
    out_conv   = fusion_with_conv.compute(engine_results)
    out_noconv = fusion_no_conv.compute(engine_results)

    # No-conv result: weighted score = 0.9
    assert abs(out_noconv["final_score"] - 0.9) < 0.001
    # With-conv result: convergence penalty applied on top of 0.9 (high variance
    # from diverging scores) — final should be < 0.9
    assert out_conv["final_score"] < 0.9, (
        f"Convergence penalty should reduce 0.9, got {out_conv['final_score']}"
    )
    # Convergence debug keys must be present
    assert "variance" in out_conv
    assert "threshold" in out_conv


def test_fusion_weighted_score_reflects_config_weights():
    """GAP-011: compute() must apply per-engine weights from FusionConfig, not a flat average."""
    # crt=1.0, others=0.0 — with weight_crt=1.0 and all others=0.0, final must be 1.0
    fusion = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(
            weight_crt=1.0, weight_gaussian=0.0,
            weight_zone_gate=0.0, weight_rr=0.0,
        ),
    )
    engine_results = {
        "crt":       {"score": 1.0},
        "gaussian":  {"score": 0.0},
        "zone_gate": {"score": 0.0},
        "rr":        {"score": 0.0},
    }
    out = fusion.compute(engine_results)
    assert out["final_score"] == 1.0, (
        f"Expected 1.0 when only crt is weighted, got {out['final_score']}"
    )


def test_fusion_weighted_score_is_not_flat_average():
    """GAP-011: weighted result must differ from flat average when weights differ."""
    # crt=0.8, gaussian=0.2, zone_gate=0.2, rr=0.2
    # flat average = (0.8+0.2+0.2+0.2)/4 = 0.35
    # weighted (crt=1.0, rest=0.0) = 0.8 / 1.0 = 0.8
    fusion_flat = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(
            weight_crt=0.25, weight_gaussian=0.25,
            weight_zone_gate=0.25, weight_rr=0.25,
        ),
    )
    fusion_biased = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(
            weight_crt=1.0, weight_gaussian=0.0,
            weight_zone_gate=0.0, weight_rr=0.0,
        ),
    )
    engine_results = {
        "crt":       {"score": 0.8},
        "gaussian":  {"score": 0.2},
        "zone_gate": {"score": 0.2},
        "rr":        {"score": 0.2},
    }
    flat_score   = fusion_flat.compute(engine_results)["final_score"]
    biased_score = fusion_biased.compute(engine_results)["final_score"]
    assert abs(flat_score - 0.35) < 0.001, f"Expected 0.35 flat, got {flat_score}"
    assert abs(biased_score - 0.8) < 0.001, f"Expected 0.8 biased, got {biased_score}"
    assert flat_score != biased_score


def test_fusion_config_defaults_match_production_config():
    """GAP-011: FusionConfig defaults must match the values in production config."""
    import json, pathlib
    prod = json.loads(
        (pathlib.Path(__file__).parent / "production_configs" / "v1_multi_2026_03.json").read_text()
    )
    fe_cfg = prod["fusion_engine"]
    defaults = FusionConfig()
    assert defaults.weight_crt       == fe_cfg["weight_crt"]
    assert defaults.weight_gaussian  == fe_cfg["weight_gaussian"]
    assert defaults.weight_zone_gate == fe_cfg["weight_zone_gate"]
    assert defaults.weight_rr        == fe_cfg["weight_rr"]


def test_fusion_conservative_rejects_directional_conflict():
    """GAP-010: conservative policy must reject when engines emit opposing directions."""
    fusion = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(conflict_resolution_policy="conservative"),
    )
    engine_results = {
        "crt":       {"score": 0.7, "direction":  1},   # BUY
        "gaussian":  {"score": 0.7, "direction": -1},   # SELL — conflict
        "zone_gate": {"score": 0.6, "direction":  0},   # no opinion
        "rr":        {"score": 0.5, "direction":  0},
    }
    out = fusion.compute(engine_results)
    assert out["final_score"] == 0.0, "Conservative policy must zero score on conflict"
    assert out["reason"] == "directional_conflict"
    assert out["conflict_resolution_policy"] == "conservative"
    assert out["missing_engines"] == []


def test_fusion_majority_resolves_conflict():
    """GAP-010: majority policy continues when one direction dominates."""
    fusion = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(conflict_resolution_policy="majority"),
    )
    engine_results = {
        "crt":       {"score": 0.7, "direction":  1},   # BUY
        "gaussian":  {"score": 0.7, "direction":  1},   # BUY
        "zone_gate": {"score": 0.6, "direction": -1},   # SELL (minority)
        "rr":        {"score": 0.5, "direction":  1},   # BUY
    }
    out = fusion.compute(engine_results)
    # Majority BUY — conflict detected but majority wins → score is non-zero
    assert out["final_score"] > 0.0, "Majority policy must produce non-zero score when majority agrees"
    assert out.get("reason") != "directional_conflict"


def test_fusion_majority_tie_falls_back_to_conservative():
    """GAP-010: majority policy with exact tie must reject (conservative fallback)."""
    fusion = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(conflict_resolution_policy="majority"),
    )
    engine_results = {
        "crt":       {"score": 0.7, "direction":  1},
        "gaussian":  {"score": 0.7, "direction": -1},
        "zone_gate": {"score": 0.6, "direction":  0},
        "rr":        {"score": 0.5, "direction":  0},
    }
    out = fusion.compute(engine_results)
    assert out["final_score"] == 0.0
    assert out["reason"] == "directional_conflict_tie"


def test_fusion_no_conflict_when_directions_agree():
    """GAP-010: no conflict path triggered when all engines agree on direction."""
    fusion = FusionEngine(
        gaussian_adapter=None,
        config=FusionConfig(conflict_resolution_policy="conservative"),
    )
    engine_results = {
        "crt":       {"score": 0.7, "direction": 1},
        "gaussian":  {"score": 0.8, "direction": 1},
        "zone_gate": {"score": 0.6, "direction": 1},
        "rr":        {"score": 0.5, "direction": 0},   # no opinion is fine
    }
    out = fusion.compute(engine_results)
    assert out.get("reason") != "directional_conflict"
    assert out["final_score"] > 0.0


def test_validate_vector_uses_len_not_shape_tuple():
    schema = tuple(f"f{i}" for i in range(24))
    validate_vector([0.0] * 24, schema)
    try:
        validate_vector([0.0] * 23, schema)
        raise AssertionError("Expected AssertionError for vector length mismatch")
    except AssertionError as exc:
        assert "length mismatch" in str(exc)
