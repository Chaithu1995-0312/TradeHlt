"""Contract split A/B/C/D — polarity vs true RR vs rr_fusion shadow.

A — RREngine candle polarity (fusion score)
B — trained rr_fusion (must stay non-mutating when disabled)
C — DecisionEngine owns NO economic RR gate (F-048 RESOLVED — semantic approval only)
D — Ultron true RR from SL/TP geometry (the sole economic-RR owner)

Authority: architecture/hygiene; documents the F-048 ownership resolution.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.decision_engine import DecisionEngine
from core.gate_intelligence import compute_crt_levels


_DE_CFG = {
    "score_threshold": 0.45,
    "p_win_threshold": 0.4,
    # rr_threshold intentionally ABSENT — DecisionEngine must construct without it (F-048).
    "weak_link_weight": 0.5,
    "weak_component_threshold": 0.4,
    "threshold_percentile": 85,
    "threshold_min": 0.45,
    "threshold_max": 0.65,
}


def _de_ready() -> DecisionEngine:
    de = DecisionEngine(config=_DE_CFG)
    # Fill history so dynamic threshold is low enough for score=0.8 to pass.
    for _ in range(100):
        de._dynamic_threshold.update(0.01)
    return de


# ── Contract C — DecisionEngine is semantic-only, owns no economic RR ─────────

def test_decision_engine_constructs_without_rr_threshold():
    """F-048 ownership guard: DecisionEngine neither requires nor holds an RR knob."""
    de = DecisionEngine(config=_DE_CFG)
    assert not hasattr(de, "rr_threshold")


def test_decision_engine_ignores_polarity_rr():
    """A polarity value in fusion is not a gate — it yields execute, not low_rr."""
    de = _de_ready()
    result = de.evaluate(
        score=0.8,
        p_win=0.6,
        zone_gate={"valid": True},
        fusion={"normalized_score": 0.8, "candle_polarity": 0.9, "weak_component": 0.1},
        config=_DE_CFG,
    )
    assert result["decision"] == "execute", result


def test_decision_engine_does_not_gate_on_economic_rr():
    """A low true_rr must NOT reject here — economics is UltronRiskGate's job (contract D)."""
    de = _de_ready()
    result = de.evaluate(
        score=0.8,
        p_win=0.6,
        zone_gate={"valid": True},
        fusion={"normalized_score": 0.8, "true_rr": 1.0, "weak_component": 0.1},
        config=_DE_CFG,
    )
    assert result["decision"] == "execute", result
    assert result["reason"] != "low_rr"


def test_low_rr_reason_is_never_emitted_by_decision_engine():
    """The DecisionEngine 'low_rr' reject reason no longer exists on any path."""
    de = _de_ready()
    # Even a value that would have tripped the old 1.5 threshold passes now.
    for fusion in (
        {"normalized_score": 0.8, "rr": 0.5, "weak_component": 0.1},
        {"normalized_score": 0.8, "true_rr": 0.1, "weak_component": 0.1},
    ):
        r = de.evaluate(score=0.8, p_win=0.6, zone_gate={"valid": True},
                        fusion=fusion, config=_DE_CFG)
        assert r["reason"] != "low_rr", r


def test_ultron_risk_gate_owns_economic_rr():
    """Contract D: the economic RR floor lives in UltronRiskGate, cost-taxed."""
    from core.ultron_risk_gate import UltronRiskGate
    gate = UltronRiskGate({"min_rr_ratio": 1.5, "pip_size": 0.0001})
    trade = {
        "execution_id": "T1", "symbol": "XAUUSD",
        "entry_price": 100.0, "stop_loss": 99.0, "take_profit": 101.0,
        "rr_ratio": 1.0,   # below the 1.5 floor
    }
    result = gate.evaluate(trade, {})
    assert result.get("decision") == "reject"
    assert "rr_too_low_after_costs" in str(result.get("risk_reason", ""))


def test_true_rr_from_sl_tp_geometry_matches_tp1_mult():
    """Contract D: rr_ratio = |tp1-entry|/|entry-sl| equals tp1_mult by CRT construction."""
    entry, low, high, atr = 100.0, 99.0, 101.0, 1.0
    for direction, tp1_mult in ((1, 1.5), (-1, 2.0), (1, 1.0)):
        levels = compute_crt_levels(
            entry=entry,
            direction=direction,
            low=low,
            high=high,
            atr=atr,
            sl_atr_buffer=0.2,
            tp1_mult=tp1_mult,
            tp2_mult=2.0,
        )
        risk = abs(entry - levels["sl"])
        rr_tp1 = abs(levels["tp1"] - entry) / risk
        rr_tp2 = abs(levels["tp2"] - entry) / risk
        assert rr_tp1 == pytest.approx(tp1_mult, rel=1e-9)
        assert rr_tp2 == pytest.approx(2.0, rel=1e-9)
        assert levels["rr"] == pytest.approx(tp1_mult, rel=1e-9)


def test_active_config_rr_fusion_remains_disabled():
    """B stays shadow/inert on active production config."""
    root = Path(__file__).resolve().parents[1]
    active = (root / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    # ACTIVE_VERSION may be bare name or with suffix; load matching json
    cfg_path = root / "configs" / "production" / f"{active}.json"
    if not cfg_path.exists():
        cfg_path = root / "configs" / "production" / "v2_multi_2026_04.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    rr_fusion = (cfg.get("engine_runner") or {}).get("rr_fusion") or {}
    assert rr_fusion.get("enabled") is False, (
        f"rr_fusion must stay disabled (shadow-only); got {rr_fusion!r} from {cfg_path}"
    )
