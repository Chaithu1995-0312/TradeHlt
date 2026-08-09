"""Engine-parity floor for the shadow CRTStateResolver's remaining transition gates.

Companion to test_crt_state_resolver_displacement_gate.py (which pins the D1 gate-4 fix). These
tests pin the funnel legality + continuous gates the resolver ports from crt_engine_v2, so an
upstream rename / threshold drift (the D1 failure class) can't silently loosen the shadow again.

Authority citations (crt_engine_v2.StateMachine):
  * SWEEP funnel                 try_range_to_sweep            (only from RANGE / shadow collapse)
  * DISPLACEMENT gates 1-3       try_sweep_to_displacement:1099 (move≥atr_min_displacement·atr),
                                   :1131 (sweep age), :1166 (body_ratio≥min); only from SWEEP
  * DISPLACEMENT→EXPANSION        try_displacement_to_expansion:1296 (directional close vs open),
                                   :1334 (close beyond disp_close), :1380 (abs Δ ≥
                                   expansion_atr_min_distance·atr_abs)
  * RETEST / EXECUTION            resolver-grade gates keyed to CRTConfig thresholds
                                   (retest_depth_max, score_threshold=0.45). Engine retest GEOMETRY
                                   differs by design (header: pipeline retest_flag is looser); what
                                   is parity-tested is the FUNNEL + the engine-grade
                                   fail-closed-without-score rule for EXECUTION.

Numeric fixtures use close=2000, atr(relative)=0.001 → atr_abs = atr·close = 2.0, so:
  displacement move_min = 1.2·2.0 = 2.4 ; wick_min = 1.5·2.0 = 3.0 ; expansion min_dist = 0.2·atr_abs.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features.crt_state_resolver import CRTStateResolver  # noqa: E402


def _resolver(state: str = "RANGE") -> CRTStateResolver:
    r = CRTStateResolver()
    r._memory.current_state = state
    r._memory.candle_index = 10
    return r


# ── SWEEP funnel (try_range_to_sweep): only from RANGE / SWEEP / SHADOW_PENDING ───────────────
def test_sweep_allowed_from_range_sweep_shadow():
    for src in ("RANGE", "SWEEP", "SHADOW_PENDING"):
        assert _resolver(src)._sweep_entry_allowed({}) is True, src


def test_sweep_rejected_mid_funnel():
    for src in ("DISPLACEMENT", "EXPANSION", "EXECUTION"):
        assert _resolver(src)._sweep_entry_allowed({}) is False, src


# ── DISPLACEMENT gates 1-3 (try_sweep_to_displacement): only from SWEEP + move/body/age ────────
def _disp_resolver() -> CRTStateResolver:
    r = _resolver("SWEEP")
    r._memory.sweep_candle_index = 10  # age 0 → fresh
    return r


def _disp_raw(*, move: float = 2.5, body_ratio: float = 0.8, candle_range: float = 3.5,
             close: float = 2000.0, atr_rel: float = 0.001) -> dict:
    return {"open": close - move, "close": close, "atr": atr_rel,
            "body_ratio": body_ratio, "candle_range": candle_range}


def test_displacement_rejected_when_not_from_sweep():
    # Engine: DISPLACEMENT is reachable only from SWEEP.
    r = _resolver("RANGE")
    assert r._displacement_entry_allowed(_disp_raw()) is False


def test_displacement_rejected_small_body_move():
    # Gate 1: move < atr_min_displacement·atr_abs (2.4).
    assert _disp_resolver()._displacement_entry_allowed(_disp_raw(move=1.0)) is False


def test_displacement_rejected_low_body_ratio():
    # Gate 3: body_ratio < body_ratio_min (0.70).
    assert _disp_resolver()._displacement_entry_allowed(_disp_raw(body_ratio=0.5)) is False


def test_displacement_rejected_stale_sweep():
    # Gate 2: sweep age > max_sweep_age_candles (20).
    r = _disp_resolver()
    r._memory.candle_index = 40
    r._memory.sweep_candle_index = 10  # age 30 > 20
    assert r._displacement_entry_allowed(_disp_raw()) is False


def test_displacement_admitted_when_all_gates_pass():
    assert _disp_resolver()._displacement_entry_allowed(_disp_raw()) is True


# ── DISPLACEMENT→EXPANSION (try_displacement_to_expansion) ────────────────────────────────────
def _exp_resolver(direction: int = 1, disp_close: float = 2000.0) -> CRTStateResolver:
    r = _resolver("DISPLACEMENT")
    r._memory.displacement_candle_close = disp_close
    r._memory.displacement_direction = direction
    return r


def test_expansion_admitted_on_directional_extension():
    # LONG: bullish bar, close beyond disp_close, distance ≥ 0.2·atr_abs.
    r = _exp_resolver()
    assert r._expansion_entry_allowed({"open": 2004.0, "close": 2005.0, "atr": 0.001}) is True


def test_expansion_rejected_when_close_not_beyond_disp():
    # close ≤ disp_close for a LONG → engine :1334 reject.
    r = _exp_resolver()
    assert r._expansion_entry_allowed({"open": 1998.0, "close": 1999.5, "atr": 0.001}) is False


def test_expansion_rejected_when_distance_below_atr_floor():
    # abs(close-disp_close)=0.1 < expansion_atr_min_distance·atr_abs (0.2·2.0=0.4) → engine :1380.
    r = _exp_resolver()
    assert r._expansion_entry_allowed({"open": 2000.05, "close": 2000.1, "atr": 0.001}) is False


def test_expansion_never_entered_cold_from_range():
    # Engine never enters EXPANSION from RANGE.
    r = _resolver("RANGE")
    assert r._expansion_entry_allowed({"open": 2004.0, "close": 2005.0, "atr": 0.001}) is False


def test_expansion_shadow_resume_from_sweep_with_pending():
    # SHADOW/SWEEP + pending displacement → shadow resume (engine skips strength check).
    r = _resolver("SWEEP")
    r._memory.pending_displacement_active = True
    assert r._expansion_entry_allowed({"open": 2000.0, "close": 2000.0, "atr": 0.001}) is True


# ── RETEST gate (funnel + retest_depth_max) ───────────────────────────────────────────────────
def test_retest_admitted_from_expansion_within_depth():
    r = _resolver("EXPANSION")
    assert r._continuous_gates_pass("RETEST", {"retest_depth": 0.05}) is True


def test_retest_rejected_when_depth_exceeds_max():
    # retest_depth_max = 0.08.
    r = _resolver("EXPANSION")
    assert r._continuous_gates_pass("RETEST", {"retest_depth": 0.2}) is False


def test_retest_rejected_cold_from_range():
    r = _resolver("RANGE")
    assert r._continuous_gates_pass("RETEST", {"retest_depth": 0.01}) is False


# ── EXECUTION gate (funnel + engine-grade fail-closed score) ──────────────────────────────────
def test_execution_fail_closed_without_score():
    # The engine requires risk score ≥ score_threshold; the resolver must NOT fire EXECUTION on
    # retest_flag alone. No score feature ⇒ reject.
    r = _resolver("RETEST")
    assert r._continuous_gates_pass("EXECUTION", {"retest_depth": 0.01}) is False


def test_execution_rejected_below_score_threshold():
    r = _resolver("RETEST")
    assert r._continuous_gates_pass("EXECUTION", {"retest_depth": 0.01, "score": 0.4}) is False


def test_execution_admitted_when_score_clears_threshold():
    # score_threshold = 0.45.
    r = _resolver("RETEST")
    assert r._continuous_gates_pass("EXECUTION", {"retest_depth": 0.01, "score": 0.5}) is True


def test_execution_rejected_cold_from_range_even_with_score():
    r = _resolver("RANGE")
    assert r._continuous_gates_pass("EXECUTION", {"retest_depth": 0.01, "score": 0.9}) is False
