"""
hierarchical_meta_fusion.py
============================
6-layer hierarchical meta-fusion for capital allocation quality scoring.

Layers (weighted):
    1. Zone Intelligence     (zone_gate score, passed flag)
    2. Liquidity Intelligence (liquidity_pressure_score, liquidity_distance)
    3. RR Intelligence       (rr engine score + expected_rr)
    4. Replay Intelligence   (historical_winrate, cluster_stability, replay_density)
    5. Market-State Intel    (cluster_confidence, state_persistence, trap_probability)
    6. TradeNet Meta         (capital_quality_score, allocation_confidence)

Penalties applied post-fusion:
    P1: Stale cluster      — replay_density < 0.10 → -0.08
    P2: High trap prob     — trap_prob > 0.60      → -(trap_prob - 0.60) × 0.50 (max 0.20)
    P3: Low replay density — replay_density < 0.05 → -0.05
    P4: Score convergence  — low variance over last 50 bars → up to -0.20
    P5: Low TradeNet conf  — allocation_confidence < 0.20 → -0.05

Output: HMFResult.to_dict() with full breakdown for cognitive telemetry.

Advisory only — this output is NEVER returned by EngineRunner.run().
It is consumed by CognitiveBus and written to logs/cognitive_telemetry.jsonl.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("HIERARCHICAL_META_FUSION")

# Market-state → base opportunity score table (before confidence weighting)
_STATE_SCORES: dict[str, float] = {
    "TREND_EXPANSION":       0.85,
    "BREAKOUT_CONTINUATION": 0.80,
    "LIQUIDITY_COMPRESSION": 0.50,
    "RANGE_TRAP":            0.35,
    "VOLATILE_REVERSAL":     0.40,
    "TRANSITIONAL_CHAOS":    0.25,
}


@dataclass
class HMFResult:
    """Full capital allocation quality result with per-layer breakdown."""
    opportunity_score:       float
    decision:                str    # "ALLOW" | "REDUCE" | "REJECT"
    market_state:            dict   = field(default_factory=dict)
    replay_intelligence:     dict   = field(default_factory=dict)
    liquidity_intelligence:  dict   = field(default_factory=dict)
    rr_intelligence:         dict   = field(default_factory=dict)
    structural_intelligence: dict   = field(default_factory=dict)
    execution_reliability:   dict   = field(default_factory=dict)
    historical_statistics:   dict   = field(default_factory=dict)
    risk_allocation:         dict   = field(default_factory=dict)
    penalties:               dict   = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "opportunity_score":       round(self.opportunity_score, 4),
            "decision":                self.decision,
            "market_state":            self.market_state,
            "replay_intelligence":     self.replay_intelligence,
            "liquidity_intelligence":  self.liquidity_intelligence,
            "rr_intelligence":         self.rr_intelligence,
            "structural_intelligence": self.structural_intelligence,
            "execution_reliability":   self.execution_reliability,
            "historical_statistics":   self.historical_statistics,
            "risk_allocation":         self.risk_allocation,
            "penalties":               self.penalties,
        }


class _ConvergenceTracker:
    """
    Detects score convergence (stuck at same value) over a rolling window.

    Returns penalty ∈ [0, 0.20] when score variance is abnormally low.
    Low variance = system is repeating the same score → possible feedback loop.
    """

    def __init__(self, window: int = 50):
        self._w = window
        self._history: list = []

    def push(self, score: float) -> float:
        """
        Append score and return convergence penalty ∈ [0, 0.20].

        Penalty = max(0, 0.20 - std × 2.0).
        Below 10 samples returns 0.0 (insufficient history).
        """
        self._history.append(score)
        if len(self._history) > self._w:
            self._history.pop(0)
        if len(self._history) < 10:
            return 0.0
        mean = sum(self._history) / len(self._history)
        variance = sum((x - mean) ** 2 for x in self._history) / len(self._history)
        std = math.sqrt(variance)
        return min(0.20, max(0.0, 0.20 - std * 2.0))


class HierarchicalMetaFusion:
    """
    6-layer capital-quality fusion.

    All layer inputs are optional (fail-open). Missing layers use neutral scores.
    Penalties reduce the final score but never below 0.

    Parameters
    ----------
    weights : dict
        Per-layer weights (default: equal 1/6 weighting, normalised internally).
        Keys: "zone", "liquidity", "rr", "replay", "market_state", "tradenet_meta".
    allow_threshold : float
        opportunity_score ≥ this → decision "ALLOW" (default 0.60).
    reduce_threshold : float
        opportunity_score ≥ this → decision "REDUCE" (default 0.45).
    """

    _DEFAULT_WEIGHTS = {
        "zone":          0.20,
        "liquidity":     0.12,
        "rr":            0.18,
        "replay":        0.20,
        "market_state":  0.15,
        "tradenet_meta": 0.15,
    }

    def __init__(
        self,
        weights: Optional[dict] = None,
        allow_threshold: float = 0.60,
        reduce_threshold: float = 0.45,
    ):
        self._weights  = {**self._DEFAULT_WEIGHTS, **(weights or {})}
        self._allow_t  = allow_threshold
        self._reduce_t = reduce_threshold
        self._convergence = _ConvergenceTracker()

    def compute(
        self,
        features: dict,
        zone_result: dict,
        rr_result: dict,
        replay_result: Optional[dict] = None,
        market_state_result: Optional[object] = None,   # MarketStateOutput
        tradenet_meta_result: Optional[dict] = None,
        base_fusion_result: Optional[dict] = None,       # FusionEngine.compute() output (unused, reserved)
    ) -> HMFResult:
        """
        Compute Capital Allocation Quality Score.

        All parameters are optional beyond features/zone_result/rr_result.
        Missing layers default to neutral (0.5) — never raises.
        """
        try:
            return self._compute_inner(
                features, zone_result, rr_result,
                replay_result, market_state_result, tradenet_meta_result,
            )
        except Exception as exc:
            logger.warning("HierarchicalMetaFusion.compute() failed (fail-open): %s", exc)
            return HMFResult(
                opportunity_score=0.5,
                decision="REDUCE",
                risk_allocation={"reason": "hmf_fallback"},
            )

    # ── Private ───────────────────────────────────────────────────────────────

    def _compute_inner(
        self,
        features: dict,
        zone_result: dict,
        rr_result: dict,
        replay_result: Optional[dict],
        market_state_result: Optional[object],
        tradenet_meta_result: Optional[dict],
    ) -> HMFResult:
        replay_r = replay_result or {}
        ms       = market_state_result
        tn       = tradenet_meta_result or {}

        # ── Layer 1: Zone Intelligence ─────────────────────────────────────────
        zone_score = float(zone_result.get("score", 0.5))
        zone_conf  = 1.0 if zone_result.get("passed") else 0.5

        # ── Layer 2: Liquidity Intelligence ───────────────────────────────────
        liq_pressure = float(features.get("liquidity_pressure_score", 0.3))
        liq_dist     = float(features.get("liquidity_distance",       5.0))
        # High pressure = near liquidity = elevated sweep risk → lowers opportunity
        liq_score    = max(0.0, 1.0 - liq_pressure * 0.8)

        # ── Layer 3: RR Intelligence ───────────────────────────────────────────
        rr_score    = float(rr_result.get("score", 0.5))
        rr_expected = float(
            rr_result.get("expected_rr", rr_result.get("rr", 0.0))
        )

        # ── Layer 4: Replay Intelligence ──────────────────────────────────────
        hist_wr     = float(replay_r.get("historical_winrate",  0.5))
        hist_rr     = float(replay_r.get("historical_rr",       0.0))
        cluster_stb = float(replay_r.get("cluster_stability",   0.5))
        replay_dens = float(replay_r.get("replay_density",      0.0))
        # Blend: 60% win rate, 40% normalised RR contribution
        hist_rr_norm = min(1.0, max(0.0, hist_rr / 2.0))
        replay_score = hist_wr * 0.60 + hist_rr_norm * 0.40

        # ── Layer 5: Market-State Intelligence ────────────────────────────────
        if ms is not None:
            ms_conf    = float(getattr(ms, "cluster_confidence", 0.0))
            trap_prob  = float(getattr(ms, "trap_probability",   0.3))
            state_pers = float(getattr(ms, "state_persistence",  0.5))
            ms_state   = str(getattr(ms, "market_state",         "TRANSITIONAL_CHAOS"))
            # Weighted blend: state quality × confidence + neutral × (1 − confidence)
            state_base = _STATE_SCORES.get(ms_state, 0.5)
            ms_score   = state_base * ms_conf + 0.5 * (1.0 - ms_conf)
        else:
            ms_conf, trap_prob, state_pers = 0.0, 0.3, 0.5
            ms_state, ms_score = "UNKNOWN", 0.5

        # ── Layer 6: TradeNet Meta ─────────────────────────────────────────────
        tn_cq   = float(tn.get("capital_quality_score", 0.5))
        tn_conf = float(tn.get("allocation_confidence",  0.0))

        # ── Weighted fusion ────────────────────────────────────────────────────
        w = self._weights
        total_w = sum(w.values()) or 1.0
        raw_score = (
            w.get("zone",          0.0) * zone_score
            + w.get("liquidity",   0.0) * liq_score
            + w.get("rr",          0.0) * rr_score
            + w.get("replay",      0.0) * replay_score
            + w.get("market_state",0.0) * ms_score
            + w.get("tradenet_meta",0.0) * tn_cq
        ) / total_w

        # ── Penalties ──────────────────────────────────────────────────────────
        penalties: dict = {}

        # P1: Stale cluster (low replay density)
        if replay_dens < 0.10:
            p1 = 0.08
            penalties["stale_cluster"] = p1
        else:
            p1 = 0.0

        # P2: High trap probability
        if trap_prob > 0.60:
            p2 = (trap_prob - 0.60) * 0.50    # max 0.20 at trap_prob=1.0
            penalties["high_trap_prob"] = round(p2, 4)
        else:
            p2 = 0.0

        # P3: Very low replay density (separate from P1 — reinforces both)
        if replay_dens < 0.05:
            p3 = 0.05
            penalties["low_replay_density"] = p3
        else:
            p3 = 0.0

        # P4: Score convergence (score stuck at same value)
        p4 = self._convergence.push(raw_score)
        if p4 > 0.01:
            penalties["convergence"] = round(p4, 4)

        # P5: Low TradeNet confidence
        if tn_conf < 0.20:
            p5 = 0.05
            penalties["low_tradenet_confidence"] = p5
        else:
            p5 = 0.0

        total_penalty = p1 + p2 + p3 + p4 + p5
        opportunity_score = max(0.0, min(1.0, raw_score - total_penalty))

        # ── Decision ──────────────────────────────────────────────────────────
        if opportunity_score >= self._allow_t:
            decision = "ALLOW"
        elif opportunity_score >= self._reduce_t:
            decision = "REDUCE"
        else:
            decision = "REJECT"

        return HMFResult(
            opportunity_score = opportunity_score,
            decision          = decision,
            market_state = {
                "state":       ms_state,
                "confidence":  round(ms_conf, 4),
                "persistence": round(state_pers, 4),
                "trap_prob":   round(trap_prob, 4),
            },
            replay_intelligence = {
                "historical_winrate": round(hist_wr, 4),
                "historical_rr":      round(hist_rr, 4),
                "cluster_stability":  round(cluster_stb, 4),
                "replay_density":     round(replay_dens, 4),
            },
            liquidity_intelligence = {
                "pressure_score": round(liq_pressure, 4),
                "distance_atr":   round(liq_dist, 4),
                "liq_score":      round(liq_score, 4),
            },
            rr_intelligence = {
                "score":       round(rr_score, 4),
                "expected_rr": round(rr_expected, 4),
            },
            structural_intelligence = {
                "zone_score": round(zone_score, 4),
                "zone_conf":  round(zone_conf, 4),
            },
            execution_reliability = {
                "tradenet_cq":   round(tn_cq, 4),
                "tradenet_conf": round(tn_conf, 4),
            },
            historical_statistics = {
                "sample_size":   int(replay_r.get("sample_size", 0)),
                "failure_modes": replay_r.get("failure_modes", []),
            },
            risk_allocation = {
                "raw_score":     round(raw_score, 4),
                "total_penalty": round(total_penalty, 4),
                "final_score":   round(opportunity_score, 4),
                "decision":      decision,
            },
            penalties = penalties,
        )
