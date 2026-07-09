"""
CRT adversarial closure suite — Phase 7 CRT Closure.

These tests fail when the CRT contract is broken (formula drift, illegal
transitions, graph/code skew, incomplete reset, missing candidate path,
dead config silent return, F-050 emission identity).

Compliant controls prove legitimate behavior still passes.

Artifacts consumed (read-only):
  docs/governance/crt_executable_surface.json
  docs/governance/crt_formula_contract.json
  docs/governance/crt_executable_state_graph.json
  docs/governance/crt_diversion_registry.jsonl
  docs/governance/crt_config_reachability.json
  docs/governance/crt_13_candidate_provenance.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from config_layer.crt_engine_v2 import (
    CRTConfig,
    CRTState,
    Candle,
    Direction,
    EngineState,
    Range,
    StateMachine,
    SweepEvent,
    VALID_TRANSITIONS,
)
from features import candle_math as cm
from features import derived_math as dm

_ROOT = Path(__file__).resolve().parents[1]
_GOV = _ROOT / "docs" / "governance"


def _load_json(name: str) -> dict:
    p = _GOV / name
    assert p.is_file(), f"missing governance artifact: {p}"
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _candle(
    o: float = 100.0,
    h: float = 110.0,
    l: float = 95.0,
    c: float = 108.0,
    idx: int = 1,
) -> Candle:
    return Candle(
        timestamp=datetime(2024, 6, 1, 12, 0, 0),
        open=o, high=h, low=l, close=c, volume=1.0, index=idx,
    )


# ── 1. Formula: governed candle math still owns CRT Candle properties ─────

def test_control_body_ratio_matches_candle_math_fm010():
    """CONTROL: CRT Candle.body_ratio == FM-010 candle_math (F-046)."""
    c = _candle(100, 110, 90, 106)
    assert c.body_ratio == pytest.approx(cm.body_ratio(100, 110, 90, 106))
    assert c.body_size == pytest.approx(cm.body_size(100, 106))
    assert c.wick_size == pytest.approx(cm.candle_range(110, 90))


def test_adversarial_body_ratio_not_body_over_total_wick():
    """FAIL if CRT body_ratio silently becomes body/total_wick (dead variant)."""
    c = _candle(100, 120, 80, 110)  # body=10, range=40, total_wick=30
    canonical = cm.body_ratio(100, 120, 80, 110)  # 10/40 = 0.25
    wick_based = cm.body_size(100, 110) / cm.total_wick(100, 120, 80, 110)  # 10/30
    assert c.body_ratio == pytest.approx(canonical)
    assert abs(c.body_ratio - wick_based) > 1e-9  # still distinct from wick-based


# ── 2. F-050: CRT emission math is FM-027/028, not FM-021/020 names ───────

def test_control_displacement_retrace_is_fm027_not_fm021():
    """CONTROL: CRT retest_depth emission math == displacement_retrace (FM-027)."""
    # displacement bullish: open 100 close 110; retest close 105
    fm027 = dm.displacement_retrace(retest_close=105.0, disp_open=100.0, disp_close=110.0)
    # FM-021 needs ema — different formula entirely
    fm021 = dm.retest_depth(close=105.0, ema_fast=100.0, atr=0.01)  # large vs atr*close
    assert fm027 == pytest.approx(0.5)  # |105-100|/|110-100|
    assert fm027 != pytest.approx(fm021)


def test_control_displacement_atr_ratio_is_fm028_not_fm020():
    """CONTROL: CRT disp_strength emission math == displacement_atr_ratio (FM-028)."""
    # range=20, atr=10 → FM-028 = 2.0; FM-020 body/(atr*close) different
    fm028 = dm.displacement_atr_ratio(candle_range=20.0, atr=10.0)
    fm020 = dm.disp_strength(body_size=10.0, atr=0.1, close=100.0)  # body/(atr*close)=1.0 clipped
    assert fm028 == pytest.approx(2.0)
    assert fm028 != pytest.approx(fm020)


def test_adversarial_f050_emission_keys_are_fm027_fm028():
    """CH-002: CRT emission keys must be governed identities, not colliding pipeline names."""
    d = _load_json("crt_formula_contract.json")
    b = d["f050_boundary"]
    assert b["status"] == "REMEDIATED_CH002"
    assert b["displacement_retrace"]["crt_emission_key"] == "displacement_retrace"
    assert b["displacement_retrace"]["true_registry_id"] == "FM-027"
    assert b["displacement_atr_ratio"]["crt_emission_key"] == "displacement_atr_ratio"
    assert b["displacement_atr_ratio"]["true_registry_id"] == "FM-028"
    # Must not re-emit under pipeline collision names as primary keys
    assert b["displacement_retrace"]["crt_emission_key"] != "retest_depth"
    assert b["displacement_atr_ratio"]["crt_emission_key"] != "disp_strength"


def test_adversarial_crt_cache_emission_uses_derived_math_keys():
    """Live cache keys on a synthetic retest stamp must be FM-027/028 names."""
    from config_layer.crt_engine_v2 import CRTConfig, EngineState, StateMachine, Range, Direction, Candle
    from datetime import datetime

    cfg = CRTConfig(
        retest_depth_max=1.0,
        retest_atr_depth_fraction=1.0,
        max_displacement_strength=10.0,
    )
    sm = StateMachine(cfg)
    st = EngineState()
    st.current_state = CRTState.EXPANSION
    st.atr = 2.0
    st.direction = Direction.LONG
    st.active_range = Range(
        h_ref=120.0, l_ref=100.0, equilibrium=110.0,
        formed_at=datetime(2024, 1, 1), htf_candle_id="T", session="LONDON",
    )
    # displacement: open 100 close 110 → body 10
    st.displacement_candle = Candle(
        timestamp=datetime(2024, 1, 1, 12, 0), open=100, high=112, low=99, close=110, volume=1, index=5,
    )
    st.sweep_event = SweepEvent(
        direction=Direction.LONG, price=99.0, candle=st.displacement_candle,
        double_confirmed=False, candle_index=5,
    )
    st.current_candle_index = 10
    # retest close near range low → depth_abs = close - l_ref small enough
    retest = Candle(
        timestamp=datetime(2024, 1, 1, 13, 0), open=102, high=103, low=100.5, close=101.0, volume=1, index=10,
    )
    ok = sm.try_expansion_to_retest(st, retest, atr=2.0)
    assert ok is True, "control retest should accept under loose ceilings"
    cf = st.cached_features
    assert cf is not None
    assert "displacement_retrace" in cf
    assert "displacement_atr_ratio" in cf
    assert "body_ratio" in cf
    assert "retest_depth" not in cf
    assert "disp_strength" not in cf
    assert "disp_str" not in cf
    # math parity with derived_math
    assert cf["displacement_retrace"] == pytest.approx(
        dm.displacement_retrace(101.0, 100.0, 110.0)
    )
    assert cf["displacement_atr_ratio"] == pytest.approx(
        dm.displacement_atr_ratio(st.displacement_candle.wick_size, 2.0)
    )


# ── 3. State graph ↔ code parity (adversarial: extra/missing edge) ───────

def test_adversarial_graph_cannot_add_illegal_transition_without_code():
    """Graph may not claim a transition code forbids."""
    g = _load_json("crt_executable_state_graph.json")
    code = {s.name: {t.name for t in ts} for s, ts in VALID_TRANSITIONS.items()}
    for edge in g["governed_transitions"]:
        if edge.get("via") == "force_reset":
            continue  # force-reset intentionally outside VALID_TRANSITIONS
        src, dst = edge["from"], edge["to"]
        # only enforce for pure _transition edges
        if edge.get("via") == "_transition":
            assert dst in code[src], f"graph claims illegal {src}->{dst}"


def test_control_valid_transitions_cover_exactly_nine_states():
    assert len(CRTState) == 9
    assert set(VALID_TRANSITIONS.keys()) == set(CRTState)


# ── 4. Illegal mutation / transition bypass ──────────────────────────────

def test_adversarial_illegal_transition_does_not_mutate_state():
    sm = StateMachine(CRTConfig())
    st = EngineState()
    st.current_state = CRTState.RANGE
    ok = sm._transition(st, CRTState.EXECUTION, "adversarial skip")
    assert ok is False
    assert st.current_state is CRTState.RANGE


def test_control_legal_range_to_sweep_mutates():
    sm = StateMachine(CRTConfig())
    st = EngineState()
    c = _candle()
    sw = SweepEvent(
        direction=Direction.LONG, price=c.low, candle=c,
        double_confirmed=False, candle_index=1,
    )
    assert sm.try_range_to_sweep(st, sw) is True
    assert st.current_state is CRTState.SWEEP


def test_adversarial_direct_state_assign_not_via_public_transition_api_is_documentable():
    """
    Force-reset assigns RANGE without _transition — must remain documented
    as bypass in graph artifact (not silently become 'legal transition only').
    """
    g = _load_json("crt_executable_state_graph.json")
    fr = g["force_reset_semantics"]
    assert fr["bypasses_valid_transitions"] is True


# ── 5. Reset cleanup completeness ────────────────────────────────────────

def test_adversarial_reset_must_clear_cached_features_and_soft_conf():
    sm = StateMachine(CRTConfig())
    st = EngineState()
    st.current_state = CRTState.RETEST
    st.cached_features = {"retest_depth": 0.9, "body_ratio": 0.8, "disp_strength": 1.2}
    st.evaluating_soft_conf = True
    st.soft_conf_candles = 2
    st.direction = Direction.LONG
    st._came_from_shadow = True
    c = _candle()
    sm.reset_to_range(st, "adversarial cleanup check", c)
    assert st.current_state is CRTState.RANGE
    assert st.cached_features is None
    assert st.evaluating_soft_conf is False
    assert st.soft_conf_candles == 0
    assert st.direction is Direction.NONE
    assert st._came_from_shadow is False


# ── 6. Candidate emission path requirements (Phase 6 artifact) ───────────

def test_adversarial_all_13_candidates_have_required_state_sequence():
    d = _load_json("crt_13_candidate_provenance.json")
    assert d["candidate_count"] == 13
    assert d["summary"]["complete"] == 13
    required_tail = ["EXPANSION", "RETEST", "EXECUTION"]
    for c in d["candidates"]:
        seq = c["state_sequence"]
        assert seq[0] == "RANGE", c["trade_id"]
        for s in required_tail:
            assert s in seq, f"{c['trade_id']} missing {s} in {seq}"
        assert c["crt_action"] == "TRADE_OPENED"
        # no TRADE_OPENED without soft conf score
        assert c["score_gate_results"]["S_score"] is not None
        assert c["score_gate_results"]["S_score"] >= 0.30  # tier_2 floor on prod


def test_adversarial_candidate_cannot_skip_retest():
    """No candidate path may jump to EXECUTION without RETEST."""
    d = _load_json("crt_13_candidate_provenance.json")
    for c in d["candidates"]:
        seq = c["state_sequence"]
        i_exec = seq.index("EXECUTION")
        assert "RETEST" in seq[:i_exec], c["trade_id"]


def test_control_golden_and_shadow_paths_only():
    d = _load_json("crt_13_candidate_provenance.json")
    allowed = {"GOLDEN", "SHADOW"}
    for c in d["candidates"]:
        assert c["path_class"] in allowed


# ── 7. Config loaded-but-ignored / hardcoded shadows ─────────────────────

def test_adversarial_dead_and_legacy_config_remain_flagged():
    d = _load_json("crt_config_reachability.json")
    by = {r["key"]: r for r in d["matrix"]}
    assert by["news_blackout_minutes"]["consumption_status"] == "DEAD_LOADED"
    assert by["score_threshold"]["consumption_status"] == "LEGACY_ONLY"


def test_adversarial_hardcoded_g_weights_and_min_depth_remain_registered():
    d = _load_json("crt_config_reachability.json")
    ids = {h["id"] for h in d["hardcoded_shadows"]}
    assert "HC-G-WEIGHTS" in ids
    assert "HC-RETEST-MIN-DEPTH" in ids


def test_control_reachable_fields_still_majority():
    d = _load_json("crt_config_reachability.json")
    hist = d["status_histogram"]
    assert hist.get("REACHABLE", 0) >= 40


# ── 8. Diversion registry exhaustiveness floor ───────────────────────────

def test_adversarial_diversion_registry_min_coverage():
    path = _GOV / "crt_diversion_registry.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) >= 30
    ids = {r["diversion_id"] for r in rows}
    # must keep critical diversions registered
    for must in (
        "DIV-SESSION-FILTER",
        "DIV-SOFT-CONF-SCORE",
        "DIV-INVERTED-SL",
        "DIV-EXPANSION-TTL",
        "DIV-RESET-HTF",
        "DIV-ILLEGAL-TRANSITION",
    ):
        assert must in ids


# ── 9. Authority freeze (Phase 1) ────────────────────────────────────────

def test_adversarial_active_authority_remains_unique():
    d = _load_json("crt_executable_surface.json")
    assert d["authority_verdict"] == "UNIQUE"
    assert d["crt_active_authority"]["class"] == "CRTEngine"
    assert d["crt_active_authority"]["module"].endswith("crt_engine_v2.py")


# ── 10. Displacement gate uses FM-010 body_ratio threshold ───────────────

def test_adversarial_displacement_rejects_low_body_ratio():
    """Control+adversarial: body_ratio_min gate rejects weak body candles."""
    cfg = CRTConfig(body_ratio_min=0.70, atr_min_displacement=0.0, atr_multiplier_min=0.0)
    sm = StateMachine(cfg)
    st = EngineState()
    st.current_state = CRTState.SWEEP
    st.atr = 1.0
    # weak body: open 100 close 101, range 100 points → body_ratio ~0.01
    weak = _candle(100, 200, 100, 101, idx=2)
    st.sweep_event = SweepEvent(
        direction=Direction.LONG, price=100, candle=weak,
        double_confirmed=False, candle_index=1,
    )
    assert weak.body_ratio < cfg.body_ratio_min
    assert sm.try_sweep_to_displacement(st, weak) is False
    assert st.current_state is CRTState.SWEEP


def test_control_displacement_accepts_strong_body_with_move():
    cfg = CRTConfig(body_ratio_min=0.50, atr_min_displacement=0.5, atr_multiplier_min=0.5)
    sm = StateMachine(cfg)
    st = EngineState()
    st.current_state = CRTState.SWEEP
    st.atr = 1.0
    # strong body candle
    strong = _candle(100, 110, 99, 109, idx=2)  # body=9, range=11, ratio~0.82
    st.sweep_event = SweepEvent(
        direction=Direction.LONG, price=99, candle=strong,
        double_confirmed=False, candle_index=1,
    )
    assert strong.body_ratio >= cfg.body_ratio_min
    assert sm.try_sweep_to_displacement(st, strong) is True
    assert st.current_state is CRTState.DISPLACEMENT
