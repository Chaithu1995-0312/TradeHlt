"""
Soft-confirmation double-EMA-update floor.

Behavioral tests for the OBSERVATION_ONLY probe at
scripts/analysis/soft_conf_ema_double_update_probe.py, per the "measure first, fix after"
decision on the CRT soft-conf EMA defect (crt_engine_v2.py:2617 + :2976 both fire
update_emas on the same candle close during the RETEST/soft-confirmation window).

These tests exercise the REAL `EngineState.update_emas` / `UltronRiskEngine.
compute_soft_confirmation` (unpatched — imported straight from src) to prove the
mechanism (double-application == effective alpha = 2a - a**2, compresses spread in a
monotone trend), and cross-check the probe's pure reimplementation of the confirmation
arithmetic against the real function for exact (byte-for-byte) agreement — a test that
CAN fail if the probe's formula transcription ever drifts from crt_engine_v2.py:1900-1939.

Per E-001 (a test that cannot fail is not enforcement): test 2 and test 3 below assert
concrete numeric values / exact equality, not just "no exception raised".
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from config_layer.crt_engine_v2 import (
    Candle, CRTConfig, Direction, EngineState, Range, UltronRiskEngine,
)

_REPO = Path(__file__).resolve().parents[1]
_PROBE = _REPO / "scripts" / "analysis" / "soft_conf_ema_double_update_probe.py"
_ARTIFACT = _REPO / "results" / "analysis" / "soft_conf_ema_double_update.LATEST.json"


def _load_probe():
    spec = importlib.util.spec_from_file_location("soft_conf_ema_double_update_probe", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["soft_conf_ema_double_update_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    if not _PROBE.exists():
        pytest.skip("soft_conf_ema_double_update_probe.py not present")
    return _load_probe()


def _ts(i: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc).replace(minute=(i * 15) % 60, hour=(i // 4) % 24)


# ─────────────────────────────────────────────────────────────────────────────
# 1. The closed-form mechanism, independent of the probe: applying
#    EngineState.update_emas (the REAL src function) twice on the same close
#    is equivalent to one update at effective alpha = 2a - a**2.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fast,slow", [(2, 5), (3, 8), (5, 20)])
def test_double_update_equals_closed_form_alpha(fast, slow):
    a_f = 2.0 / (fast + 1)
    a_s = 2.0 / (slow + 1)
    alpha_eff_f = 2 * a_f - a_f ** 2
    alpha_eff_s = 2 * a_s - a_s ** 2

    state = EngineState()
    state.current_candle_index = 1
    state.update_emas(100.0, fast=fast, slow=slow)  # seed
    state.current_candle_index = 2
    close = 105.0
    state.update_emas(close, fast=fast, slow=slow)  # 1st application this candle
    state.update_emas(close, fast=fast, slow=slow)  # 2nd application, SAME candle/close

    expected_fast = close * alpha_eff_f + 100.0 * (1.0 - alpha_eff_f)
    expected_slow = close * alpha_eff_s + 100.0 * (1.0 - alpha_eff_s)

    assert state.ema_fast_val == pytest.approx(expected_fast, abs=1e-12)
    assert state.ema_slow_val == pytest.approx(expected_slow, abs=1e-12)


def test_alpha_eff_888_and_555_for_production_ema_periods():
    """The production config's ema_fast=2/ema_slow=5 (configs/production/v2_multi_2026_04.json)
    gives the specific effective spans cited in the finding: fast span 2 -> 1.25, slow span
    5 -> 2.6 under double-application."""
    a_f, a_s = 2.0 / 3, 2.0 / 6
    alpha_eff_f = 2 * a_f - a_f ** 2
    alpha_eff_s = 2 * a_s - a_s ** 2
    assert alpha_eff_f == pytest.approx(8.0 / 9, abs=1e-12)
    assert alpha_eff_s == pytest.approx(5.0 / 9, abs=1e-12)
    span_f = 2.0 / alpha_eff_f - 1.0
    span_s = 2.0 / alpha_eff_s - 1.0
    assert span_f == pytest.approx(1.25, abs=1e-9)
    assert span_s == pytest.approx(2.6, abs=1e-9)


def test_double_update_compresses_spread_in_monotone_trend():
    """A strictly monotone-increasing close series: the double-update spread must be
    SMALLER in magnitude than the single-update spread (compression, not the
    'overly sensitive' inflation the received bug-trace claimed)."""
    fast, slow = 2, 5
    closes = [100.0 + 0.5 * i for i in range(30)]

    single = EngineState()
    double = EngineState()
    for i, c in enumerate(closes):
        single.current_candle_index = i
        double.current_candle_index = i
        single.update_emas(c, fast=fast, slow=slow)
        double.update_emas(c, fast=fast, slow=slow)
        double.update_emas(c, fast=fast, slow=slow)  # second application, same close

    spread_single = single.ema_fast_val - single.ema_slow_val
    spread_double = double.ema_fast_val - double.ema_slow_val

    assert spread_single > 0  # sanity: series is trending up, fast should lead slow
    assert spread_double > 0
    assert spread_double < spread_single  # COMPRESSION, not inflation
    ratio = spread_double / spread_single
    # Empirically observed on the XAUUSD corpus (n=10 trend evals): 0.4673.
    # Analytic asymptote for this alpha pair on a linear ramp is close to but not
    # identical to the corpus figure (finite-window transient) — assert a band.
    assert 0.35 < ratio < 0.60


# ─────────────────────────────────────────────────────────────────────────────
# 2. Self-consistency: the probe's pure reimplementation of the confirmation
#    arithmetic (mirroring crt_engine_v2.py:1900-1939) must reproduce the REAL
#    UltronRiskEngine.compute_soft_confirmation exactly, given identical EMA inputs.
# ─────────────────────────────────────────────────────────────────────────────

def _make_fixture(direction=Direction.LONG, atr=2.0, ema_fast=101.0, ema_slow=100.0):
    cfg = CRTConfig()
    risk = UltronRiskEngine(cfg)

    rng = Range(
        h_ref=110.0, l_ref=90.0, equilibrium=100.0,
        formed_at=_ts(0), htf_candle_id="HTF-1", session="LONDON",
    )
    disp = Candle(timestamp=_ts(1), open=100.0, high=106.0, low=99.0, close=105.0)
    conf_candle = Candle(timestamp=_ts(2), open=103.0, high=104.0, low=101.5, close=102.5)

    state = EngineState()
    state.direction = direction
    state.active_range = rng
    state.displacement_candle = disp
    state.atr_abs = atr
    state.ema_fast_val = ema_fast
    state.ema_slow_val = ema_slow
    return risk, conf_candle, state


@pytest.mark.parametrize("direction,atr,ema_fast,ema_slow", [
    (Direction.LONG, 2.0, 101.0, 100.0),
    (Direction.SHORT, 2.0, 101.0, 100.0),
    (Direction.LONG, 0.5, 99.7, 100.4),
    (Direction.SHORT, 5.0, 100.0, 100.0),  # zero spread edge case
    (Direction.LONG, 3.3, 103.2, 98.9),
])
def test_probe_recompute_matches_real_function_exactly(probe, direction, atr, ema_fast, ema_slow):
    risk, conf_candle, state = _make_fixture(direction, atr, ema_fast, ema_slow)

    C_real = risk.compute_soft_confirmation(conf_candle, state)
    check = probe._recompute_C(risk, conf_candle, state, state.ema_fast_val, state.ema_slow_val)

    assert check["C"] == C_real  # exact, not approx — byte-parity self-consistency


def test_tier_bucket_matches_approve_with_soft_conf_semantics(probe):
    """Mirrors the >=, >= (not >) boundary semantics at crt_engine_v2.py:2018-2026."""
    t1, t2 = 0.75, 0.30
    assert probe._tier_bucket(0.75, t1, t2) == "TIER1"
    assert probe._tier_bucket(0.7499999999, t1, t2) == "TIER2"
    assert probe._tier_bucket(0.30, t1, t2) == "TIER2"
    assert probe._tier_bucket(0.2999999999, t1, t2) == "REJECT"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Artifact schema — only runs against a real generated artifact; skipped if absent.
# ─────────────────────────────────────────────────────────────────────────────

def test_artifact_schema_and_self_consistency():
    if not _ARTIFACT.exists():
        pytest.skip("probe artifact not yet generated")
    import json
    with open(_ARTIFACT, "r", encoding="utf-8") as f:
        art = json.load(f)

    for key in ("artifact", "instrument", "csv_path", "csv_sha256", "config_version",
                "provenance", "summary", "records", "exactness_boundary"):
        assert key in art

    s = art["summary"]
    for key in ("n_evaluations", "n_flipped", "n_post_divergence", "first_divergence_idx",
                "max_c_self_consistency_err", "n_compute_soft_confirmation_calls"):
        assert key in s

    assert s["n_evaluations"] == len(art["records"])
    assert s["n_flipped"] == sum(1 for r in art["records"] if r["flipped"])
    # The artifact's own runtime self-check (see probe's patched_compute_soft_confirmation)
    # must show the reimplementation tracked the real function within float noise.
    assert s["max_c_self_consistency_err"] < 1e-9

    fdi = s["first_divergence_idx"]
    for r in art["records"]:
        assert "post_divergence" in r
        if fdi is None:
            assert r["post_divergence"] is False
        else:
            assert r["post_divergence"] == (r["candle_index"] > fdi)
