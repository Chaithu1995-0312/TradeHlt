"""GD-004 / GD-005 disp_strength identity closure — byte-identical parity floor.

The 2026-07-11 micro-phase (FU-SCORING-DISP) retired the last two `disp_strength` grandfather
pins by routing their math through the Formula Registry, with ZERO behavior change:

  GD-004  scoring_engine.compute_scores:  local `disp_strength = move/atr` → FM-029
          derived_math.disp_strength_atr_rescale (a THIRD identity: caller crt_engine.py:23
          passes the FM-020 feature as `move`; ≠ FM-020, ≠ FM-028 — probe
          docs/governance/gd004_disp_rescale_probe-2026-07-11.json).
  GD-005  crt_engine_v2 [PATCH 7]:  `wick_size / atr` → FM-028
          derived_math.displacement_atr_ratio (wick_size ≡ candle_range per F-046).

These tests freeze (a) scalar parity of the routed impls against the exact pre-closure inline
math, (b) compute_scores() output identity against values produced by the OLD formula, and
(c) registry dispatch + ontology registration of FM-029.
"""
from __future__ import annotations

import math

import pytest

from features import derived_math
from features.registry import load_ontology
from features.registry.derived_registry import compute_derived
from engines.scoring_engine import compute_scores

# Grid spans the observed FM-020 range [0, 3], the probe's as-wired magnitudes (~10^2-10^3 via
# close-relative atr ~0.001-0.03), and the guard edges (atr <= 0).
_MOVE_GRID = [0.0, 0.001, 0.25, 0.518, 1.0, 2.0, 3.0]
_ATR_GRID = [0.00085, 0.0042, 0.034, 0.5, 1.0, 2.7]
_ATR_GUARD = [0.0, -1.0, -0.0042]


# ── GD-004: FM-029 scalar parity vs the pre-closure inline formula ──────────────────────────

@pytest.mark.parametrize("move", _MOVE_GRID)
@pytest.mark.parametrize("atr", _ATR_GRID + _ATR_GUARD)
def test_fm029_scalar_parity_vs_old_inline(move, atr):
    old = move / atr if atr > 0 else 0.0          # scoring_engine.py:31 pre-closure, verbatim
    assert derived_math.disp_strength_atr_rescale(move, atr) == old


def test_fm029_negative_move_passthrough():
    # The old inline math had no clamp on move; the routed impl must not add one.
    assert derived_math.disp_strength_atr_rescale(-0.5, 2.0) == -0.25


# ── GD-004: compute_scores output identity (expected values from the OLD formula) ───────────

@pytest.mark.parametrize("move", _MOVE_GRID)
@pytest.mark.parametrize("atr", _ATR_GRID + _ATR_GUARD)
@pytest.mark.parametrize("sweep_detected,double_sweep", [(False, False), (True, False), (True, True)])
def test_compute_scores_byte_identical(move, atr, sweep_detected, double_sweep):
    body_ratio, retest_depth, csr, lam = 0.62, 0.41, 3, 0.05
    weights = (0.35, 0.25, 0.20, 0.20)

    # OLD formula, transcribed verbatim from pre-closure scoring_engine.compute_scores.
    disp = move / atr if atr > 0 else 0.0
    s_sweep = 0.0 if not sweep_detected else (1.0 if double_sweep else 0.7)
    s_breakout = 0.5 * min(body_ratio, 1.0) + 0.5 * min(disp / 2.0, 1.0)
    s_retest = math.exp(-((retest_depth - 0.5) ** 2) / 0.04)
    s_time = math.exp(-lam * max(0, csr))
    s_final = (weights[0] * s_sweep + weights[1] * s_breakout
               + weights[2] * s_retest + weights[3] * s_time)
    expected = {"sweep": round(s_sweep, 4), "breakout": round(s_breakout, 4),
                "retest": round(s_retest, 4), "time": round(s_time, 4),
                "final": round(s_final, 4), "score": round(s_final, 4)}

    got = compute_scores(
        body_ratio=body_ratio, move=move, atr=atr, retest_depth=retest_depth,
        candles_since_retest=csr, sweep_detected=sweep_detected, double_sweep=double_sweep,
        lambda_decay=lam, score_weights=weights,
    )
    assert got == expected


# ── GD-005: FM-028 route parity vs the pre-closure inline formula ────────────────────────────

@pytest.mark.parametrize("wick_size", [0.0, 0.37, 1.9, 84.2, 512.0])
@pytest.mark.parametrize("atr", [0.31, 2.7, 55.0])
def test_gd005_route_parity_vs_old_inline(wick_size, atr):
    # [PATCH 7] pre-closure: `_disp_strength = wick_size / atr`, only reached when atr > 0.
    assert derived_math.displacement_atr_ratio(wick_size, atr) == wick_size / atr


def test_gd005_guard_convention_consistent():
    # The site only computes when atr > 0; the impl's atr<=0 -> 0.0 branch is never reached
    # there, so routing cannot change guard behavior. Freeze the impl convention anyway.
    assert derived_math.displacement_atr_ratio(1.5, 0.0) == 0.0
    assert derived_math.displacement_atr_ratio(1.5, -1.0) == 0.0


# ── FM-029 registration: ontology entry + registry dispatch ─────────────────────────────────

def test_fm029_registered_in_ontology():
    ont = load_ontology()
    entry = ont["derived_metrics"]["disp_strength_atr_rescale"]
    assert entry["id"] == "FM-029"
    assert entry["impl"] == "derived_math.disp_strength_atr_rescale"
    assert entry["depends_on"] == ["disp_strength", "atr"]
    assert entry["active"] is True


def test_fm029_registry_dispatch():
    val = compute_derived("disp_strength_atr_rescale", disp_strength=0.518, atr=0.0042)
    assert val == pytest.approx(0.518 / 0.0042)
    assert compute_derived("disp_strength_atr_rescale", disp_strength=0.518, atr=0.0) == 0.0


def test_fm029_distinct_from_fm020_and_fm028():
    # Identity separation on a representative bar (probe medians): the three quantities differ.
    body_size, candle_range, atr_rel, close = 1.2, 2.9, 0.0042, 580.0
    fm020 = derived_math.disp_strength(body_size, atr_rel, close)
    fm028 = derived_math.displacement_atr_ratio(candle_range, atr_rel * close)
    fm029 = derived_math.disp_strength_atr_rescale(fm020, atr_rel)
    assert fm029 != pytest.approx(fm020)
    assert fm029 != pytest.approx(fm028)
