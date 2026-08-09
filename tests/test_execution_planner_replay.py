"""
tests/test_execution_planner_replay.py — unit tests for the execution-planner replay experiment.

Covers:
  Group A — RETEST_REPLAY additive telemetry (emission + flush wiring)
  Group B — faithful structure / vanilla SL-TP reconstruction (offline mirror of build_trade)
  Group C — 2x2 attribution decomposition identity
"""

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

import pytest

from config_layer.crt_engine_v2 import TelemetryCollector


# Import the research script as a module (no main() runs on import).
def _load_replay_module():
    path = _ROOT / "scripts" / "research" / "execution_planner_replay.py"
    spec = importlib.util.spec_from_file_location("execution_planner_replay", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


REPLAY = _load_replay_module()


# ── Group A — telemetry emission ───────────────────────────────────────────────

def _emit(tc, **over):
    base = dict(
        candle_index=196, timestamp="2024-05-24T07:30:00", direction=-1, entry=591.1,
        disp_low=590.6, disp_high=595.3, atr=2.5, sl_atr_buffer=0.2, tp1_mult=1.0,
        tp2_mult=2.0, intent="reversal", score=0.51, accepted=False,
        reject_reason="shadow_advisory_only",
    )
    base.update(over)
    tc.on_retest_replay(**base)


def test_retest_replay_appended_and_flushed():
    tc = TelemetryCollector()
    _emit(tc, accepted=True, reject_reason=None)
    _emit(tc, candle_index=200, accepted=False, reject_reason="not_discount_zone")
    out = [r for r in tc.flush() if r.get("kind") == "RETEST_REPLAY"]
    assert len(out) == 2


def test_retest_replay_required_fields_present():
    tc = TelemetryCollector()
    _emit(tc)
    rec = next(r for r in tc.flush() if r.get("kind") == "RETEST_REPLAY")
    for k in ("candle_index", "timestamp", "direction", "entry", "disp_low", "disp_high",
              "atr", "sl_atr_buffer", "tp1_mult", "tp2_mult", "intent", "score",
              "accepted", "reject_reason"):
        assert k in rec, f"missing field {k}"
    assert rec["direction"] in (1, -1)


def test_accepted_record_has_no_reject_reason():
    tc = TelemetryCollector()
    _emit(tc, accepted=True, reject_reason=None)
    rec = next(r for r in tc.flush() if r.get("kind") == "RETEST_REPLAY")
    assert rec["accepted"] is True and rec["reject_reason"] is None


# ── Group B — faithful SL/TP reconstruction (mirror of build_trade) ────────────

def test_structure_levels_long_anchored_to_displacement_low():
    r = dict(direction=1, entry=100.0, disp_low=98.0, disp_high=101.0, atr=1.0,
             sl_atr_buffer=0.2, tp1_mult=1.0, tp2_mult=2.0)
    sl, tp1, tp2 = REPLAY._structure_levels(r)
    assert sl == pytest.approx(98.0 - 0.2 * 1.0)        # disp_low - buffer*atr
    risk = abs(100.0 - sl)
    assert tp1 == pytest.approx(100.0 + 1.0 * risk)     # +1R
    assert tp2 == pytest.approx(100.0 + 2.0 * risk)     # +2R


def test_structure_levels_short_anchored_to_displacement_high():
    r = dict(direction=-1, entry=100.0, disp_low=99.0, disp_high=102.0, atr=2.0,
             sl_atr_buffer=0.2, tp1_mult=1.0, tp2_mult=2.0)
    sl, tp1, tp2 = REPLAY._structure_levels(r)
    assert sl == pytest.approx(102.0 + 0.2 * 2.0)       # disp_high + buffer*atr (above entry)
    assert sl > 100.0 and tp1 < 100.0 and tp2 < tp1     # short: SL above, TP below


def test_vanilla_levels_fixed_1atr_sl_2atr_tp():
    r = dict(direction=1, entry=100.0, atr=2.0)
    sl, tp1, tp2 = REPLAY._vanilla_levels(r)
    assert sl == pytest.approx(98.0)                    # entry - 1*atr
    assert tp1 == tp2 == pytest.approx(104.0)           # entry + 2*atr, single TP


# ── Group C — 2x2 attribution decomposition identity ───────────────────────────

def test_attribution_identity_reconstructs_observed_jump():
    exp = {
        "A_selected_vanilla":   0.286,
        "B_selected_structure": 0.357,
        "C_rejected_vanilla":   0.182,
        "D_rejected_structure": 0.172,
    }
    a = REPLAY.compute_attribution(exp)
    obs = a["observed_C_to_B"]
    # both decomposition paths must reconstruct B - C
    assert a["selection_effect_vanilla"] + a["sltp_effect_on_selected"] == pytest.approx(obs, abs=1e-4)
    assert a["selection_effect_structure"] + a["sltp_effect_on_rejected"] == pytest.approx(obs, abs=1e-4)


def test_attribution_interaction_is_difference_of_sltp_effects():
    exp = {
        "A_selected_vanilla":   0.20,
        "B_selected_structure": 0.40,
        "C_rejected_vanilla":   0.10,
        "D_rejected_structure": 0.15,
    }
    a = REPLAY.compute_attribution(exp)
    assert a["interaction"] == pytest.approx(
        a["sltp_effect_on_selected"] - a["sltp_effect_on_rejected"], abs=1e-4
    )
