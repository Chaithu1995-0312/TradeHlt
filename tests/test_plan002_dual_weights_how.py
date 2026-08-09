"""
IC-007 PLAN-002 — dual-path score weights → TWO DISTINCT HOW keys.

Design (user-approved 2026-07-11): the legacy tuple 0.35/0.25/0.20/0.20 appeared on TWO
semantically different paths and gets TWO identities — never aliased to each other or to
conf_weights (PROVEN_DIFFERENT_SEMANTIC):

  risk_score_weights      → RiskScore.final (Ultron/CRT spine score; sweep, breakout,
                            retest, time) via CRTConfig, injected at the sole constructor
                            (UltronRiskEngine.compute_score).
  score_component_weights → engines path (engines.scoring_engine.compute_scores), injected
                            by EngineRunner as crt_compute context (previously context={} so
                            the CODE default always won — the dual-path gap).

Guarantees:
  1. Default-parity on BOTH paths (defaults == legacy literals; outputs byte-equal).
  2. Dynamism per path; changing one key does NOT move the other path (no aliasing).
  3. Fail-closed validation (length/type/finite/negative/bool) for both keys.
  4. Production load surfaces both keys; conf_weights untouched.
"""
from __future__ import annotations

import math

import pytest

from config_layer.crt_engine_v2 import CRTConfig, RiskScore, UltronRiskEngine
from config_layer.production_config import get_prod_config, get_prod_section
from engines import crt_engine
from engines.scoring_engine import compute_scores

_LEGACY = (0.35, 0.25, 0.20, 0.20)


# ── 1. defaults are the legacy literals ──────────────────────────────────────

def test_dataclass_defaults_are_legacy():
    cfg = CRTConfig()
    assert tuple(cfg.risk_score_weights) == pytest.approx(_LEGACY)
    assert tuple(cfg.score_component_weights) == pytest.approx(_LEGACY)
    assert tuple(RiskScore().weights) == pytest.approx(_LEGACY)


def test_conf_weights_not_aliased():
    """conf_weights is a DIFFERENT semantic (soft-confirmation) — must stay untouched."""
    assert tuple(CRTConfig().conf_weights) == pytest.approx((0.35, 0.35, 0.15, 0.15))


# ── 2. Ultron path: RiskScore.final ─────────────────────────────────────────

def _legacy_final(s, b, r, t, decay=1.0):
    return (0.35 * s + 0.25 * b + 0.20 * r + 0.20 * t) * decay


@pytest.mark.parametrize("s,b,r,t,decay", [
    (0.0, 0.0, 0.0, 0.0, 1.0),
    (1.0, 1.0, 1.0, 1.0, 1.0),
    (0.7, 0.31, 0.92, 0.14, 0.83),
    (0.05, 0.99, 0.5, 0.6, 0.449),
])
def test_riskscore_final_default_parity(s, b, r, t, decay):
    rs = RiskScore(sweep_score=s, breakout_score=b, retest_score=r,
                   time_score=t, decay_factor=decay)
    assert rs.final == _legacy_final(s, b, r, t, decay)  # exact, not approx (byte parity)


def test_riskscore_dynamism_and_engine_injection():
    # direct: weights change → final changes exactly as specified
    rs = RiskScore(sweep_score=1.0, breakout_score=0.5, retest_score=0.25,
                   time_score=0.0, weights=(1.0, 0.0, 0.0, 0.0))
    assert rs.final == 1.0
    # engine injection: compute_score builds RiskScore with config weights
    cfg = CRTConfig(risk_score_weights=[0.0, 1.0, 0.0, 0.0])
    assert tuple(cfg.risk_score_weights) == (0.0, 1.0, 0.0, 0.0)  # list→tuple coercion
    eng = UltronRiskEngine(cfg)

    class _State:  # minimal duck-typed EngineState for compute_score
        sweep_event = None
        active_range = None
        displacement_candle = None
        retest_candle = None
        current_candle_index = 0
        retest_candle_index = 0
        direction = None
        atr = 1.0

    rs2 = eng.compute_score(_State())
    assert tuple(rs2.weights) == (0.0, 1.0, 0.0, 0.0)


def test_score_override_still_wins():
    rs = RiskScore(sweep_score=1.0, weights=(1.0, 0.0, 0.0, 0.0), score_override=0.123)
    assert rs.final == 0.123


# ── 3. engines path: compute_scores / crt_compute context ───────────────────

def test_engines_path_default_parity():
    base = dict(body_ratio=0.62, move=0.5, atr=0.004, retest_depth=0.41,
                candles_since_retest=3, sweep_detected=True, double_sweep=False)
    default = compute_scores(**base)
    explicit = compute_scores(**base, score_weights=_LEGACY)
    assert default == explicit


def test_engines_path_dynamism_via_context():
    features = {"body_ratio": 0.62, "disp_strength": 0.5, "atr": 0.004,
                "retest_depth": 0.41, "candles_since_retest": 3,
                "sweep_detected": True, "double_sweep": False}
    # legacy reference: compute_scores with default weights (CODE-level default)
    from engines.scoring_engine import compute_scores
    legacy_score = compute_scores(
        body_ratio=0.62, move=0.5, atr=0.004, retest_depth=0.41,
        candles_since_retest=3, sweep_detected=True, double_sweep=False
    )["final"]
    # explicit legacy weights via crt_engine.compute must match
    legacy = crt_engine.compute("t", dict(features),
                                {"score_component_weights": list(_LEGACY)})
    assert legacy.get("score") == legacy_score, "explicit legacy must match compute_scores default"
    # moved weights produce different score
    moved = crt_engine.compute("t", dict(features),
                               {"score_component_weights": [1.0, 0.0, 0.0, 0.0]})
    assert legacy.get("score") != moved.get("score"), "context weights must reach compute_scores"
    # empty context must fail closed (PLAN-002 closure) — compute catches the
    # KeyError and returns score=0.0 with a reason string, never silently using
    # CODE literals.
    fail_result = crt_engine.compute("t", dict(features), {})
    assert fail_result.get("score") == 0.0, "missing weights must produce score 0.0"
    assert "score_component_weights" in str(fail_result.get("reason", "")), \
        "reason must mention the missing key"


# ── 4. NO aliasing between the two identities ────────────────────────────────

def test_no_aliasing_between_paths():
    cfg = CRTConfig(risk_score_weights=[0.9, 0.1, 0.0, 0.0])
    # Ultron path moved…
    rs = RiskScore(sweep_score=1.0, breakout_score=1.0, retest_score=1.0, time_score=1.0,
                   weights=tuple(cfg.risk_score_weights))
    assert rs.final == 1.0  # 0.9+0.1
    # …engines-path key is untouched by construction
    assert tuple(cfg.score_component_weights) == pytest.approx(_LEGACY)
    # and vice versa
    cfg2 = CRTConfig(score_component_weights=[0.0, 0.0, 0.0, 1.0])
    assert tuple(cfg2.risk_score_weights) == pytest.approx(_LEGACY)


# ── 5. fail-closed validation ────────────────────────────────────────────────

@pytest.mark.parametrize("key", ["risk_score_weights", "score_component_weights"])
@pytest.mark.parametrize("bad", [
    [0.35, 0.25, 0.20],                    # wrong length
    [0.35, 0.25, 0.20, 0.20, 0.0],         # wrong length
    [0.35, 0.25, 0.20, float("nan")],      # non-finite
    [0.35, 0.25, 0.20, float("inf")],      # non-finite
    [0.35, 0.25, 0.20, -0.1],              # negative
    [0.35, 0.25, 0.20, True],              # bool
    [0.35, 0.25, 0.20, "0.2"],             # non-numeric
    0.35,                                   # not a sequence
])
def test_fail_closed(key, bad):
    with pytest.raises(ValueError):
        CRTConfig(**{key: bad})


# ── 6. production load exposes both keys (HOW ownership) ────────────────────

def test_production_load_exposes_both_keys():
    cfg = get_prod_config("BNBUSDT")
    assert tuple(cfg.risk_score_weights) == pytest.approx(_LEGACY)
    assert tuple(cfg.score_component_weights) == pytest.approx(_LEGACY)
    sec = get_prod_section("crt_engine")
    assert "risk_score_weights" in sec and "score_component_weights" in sec
