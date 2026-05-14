"""
gate_intelligence.py — Pure signal gate for ExecutionPlanner.

Responsibilities:
    1. compute_crt_levels() — module-level pure function that mirrors
       crt_engine_v2.py lines 1162-1201 exactly; CRT is sole SL/TP authority.
    2. GateIntelligence — deterministic multi-factor approval gate.
       Scores intent quality, volatility, liquidity, and structure.
       Returns approve/reject with component breakdown.
       No randomness, no external I/O, no mutable state.
"""

from __future__ import annotations

from typing import Any

from utils.logging_config import get_flow_logger

logger = get_flow_logger("GATE_INTELLIGENCE")


# ── CRT-level computation (sole SL/TP authority) ──────────────────────────────

def compute_crt_levels(
    entry: float,
    direction: int,
    low: float,
    high: float,
    atr: float,
    sl_atr_buffer: float = 0.2,
    tp1_mult: float = 1.0,
    tp2_mult: float = 2.0,
) -> dict[str, float]:
    """
    Compute SL, TP1, TP2 using the CRT engine formula.

    Mirrors crt_engine_v2.py lines 1162-1201 exactly.
    LONG:  sl = low  - sl_atr_buffer * atr
    SHORT: sl = high + sl_atr_buffer * atr
    tp1   = entry + direction * tp1_mult * risk_dist
    tp2   = entry + direction * tp2_mult * risk_dist

    Parameters
    ----------
    entry         : float — trade entry price
    direction     : int   — 1 for LONG, -1 for SHORT
    low           : float — current candle low
    high          : float — current candle high
    atr           : float — average true range (must be > 0)
    sl_atr_buffer : float — ATR multiplier for SL offset (default 0.2)
    tp1_mult      : float — TP1 R-multiple (default 1.0); use intent-specific values
    tp2_mult      : float — TP2 R-multiple (default 2.0); use intent-specific values

    Returns
    -------
    dict with keys: sl, tp1, tp2, risk_dist, rr

    Raises
    ------
    ValueError if atr <= 0 or direction not in (1, -1).
    """
    if atr <= 0:
        raise ValueError(f"compute_crt_levels: atr must be > 0, got {atr}")
    if direction not in (1, -1):
        raise ValueError(
            f"compute_crt_levels: direction must be 1 or -1, got {direction}"
        )

    if direction == 1:
        sl = low - sl_atr_buffer * atr
    else:
        sl = high + sl_atr_buffer * atr

    risk_dist = abs(entry - sl)
    tp1 = entry + direction * tp1_mult * risk_dist
    tp2 = entry + direction * tp2_mult * risk_dist

    return {
        "sl":        sl,
        "tp1":       tp1,
        "tp2":       tp2,
        "risk_dist": risk_dist,
        "rr":        tp1_mult,
    }


# ── Gate Intelligence ─────────────────────────────────────────────────────────

class GateIntelligence:
    """
    Deterministic multi-factor signal gate.

    Combines four component scores into a weighted final_score and compares
    against a configurable approval threshold.

    All arithmetic is deterministic: no randomness, no external state,
    no mutable instance variables after __init__.

    Component scores
    ----------------
    intent_score    — price action alignment with declared trade intent
    vol_score       — ATR quality (bar range vs ATR ratio)
    liquidity_score — structural liquidity sweep evidence + volume spike
    structure_score — EMA alignment + displacement strength

    Config keys (with defaults)
    ---------------------------
    gate_weight_intent       : 0.35
    gate_weight_vol          : 0.20
    gate_weight_liquidity    : 0.20
    gate_weight_structure    : 0.25
    gate_approval_threshold  : 0.55
    """

    _CONFIG_DEFAULTS: dict[str, float] = {
        "gate_weight_intent":      0.35,
        "gate_weight_vol":         0.20,
        "gate_weight_liquidity":   0.20,
        "gate_weight_structure":   0.25,
        "gate_approval_threshold": 0.55,
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        m: dict[str, Any] = {**self._CONFIG_DEFAULTS}
        if isinstance(config, dict):
            m.update(config)
        self._w_intent    = float(m["gate_weight_intent"])
        self._w_vol       = float(m["gate_weight_vol"])
        self._w_liquidity = float(m["gate_weight_liquidity"])
        self._w_structure = float(m["gate_weight_structure"])
        self._threshold   = float(m["gate_approval_threshold"])

    # ── Public entry point ────────────────────────────────────────────────────

    def decide(
        self,
        features: dict[str, Any],
        intent: str,
        direction: int,
    ) -> dict[str, Any]:
        """
        Evaluate the signal and return approve/reject with component breakdown.

        Parameters
        ----------
        features  : canonical feature dict (same dict passed to ExecutionPlannerV1_2)
        intent    : one of BREAKOUT / PULLBACK / LIQ_SWEEP / REVERSAL / UNKNOWN
        direction : 1 (long) or -1 (short)

        Returns
        -------
        {
          "approved":    bool,
          "final_score": float,          # weighted sum in [0.0, 1.0]
          "components": {
              "intent_score":    float,
              "vol_score":       float,
              "liquidity_score": float,
              "structure_score": float,
          },
          "reason": str,
        }
        """
        s_i = self._intent_score(features, intent)
        s_v = self._vol_score(features)
        s_l = self._liquidity_score(features, direction)
        s_s = self._structure_score(features, direction)

        final = min(1.0, max(0.0,
            self._w_intent    * s_i
            + self._w_vol       * s_v
            + self._w_liquidity * s_l
            + self._w_structure * s_s
        ))

        approved = final >= self._threshold

        if approved:
            reason = (
                f"approved: score={final:.4f} >= threshold={self._threshold}"
            )
        else:
            reason = (
                f"rejected: score={final:.4f} < threshold={self._threshold} "
                f"[intent={s_i:.3f} vol={s_v:.3f} "
                f"liq={s_l:.3f} struct={s_s:.3f}]"
            )

        return {
            "approved":    approved,
            "final_score": round(final, 6),
            "components": {
                "intent_score":    round(s_i, 6),
                "vol_score":       round(s_v, 6),
                "liquidity_score": round(s_l, 6),
                "structure_score": round(s_s, 6),
            },
            "reason": reason,
        }

    # ── Component scorers ─────────────────────────────────────────────────────

    def _intent_score(self, features: dict[str, Any], intent: str) -> float:
        """
        How strongly do features confirm the declared intent?

        BREAKOUT  : body_ratio (candle conviction) + disp_strength (momentum)
        PULLBACK  : retest_depth centred on 0.5 (triangular) × recency decay
        LIQ_SWEEP : sweep_detected (0.5) + double_sweep bonus (0.5)
        REVERSAL  : low momentum score (counter-trend, so invert |momentum|)
        UNKNOWN   : always 0.0
        """
        body   = float(features.get("body_ratio",          0.0))
        disp   = float(features.get("disp_strength",        0.0))
        depth  = float(features.get("retest_depth",         0.0))
        csr    = int(  features.get("candles_since_retest", 99))
        mom    = float(features.get("momentum_score",       0.0))
        sweep  = bool( features.get("sweep_detected",       False))
        dsweep = bool( features.get("double_sweep",         False))

        if intent == "BREAKOUT":
            disp_component = min(1.0, max(0.0, disp / 3.0))
            score = 0.5 * min(1.0, max(0.0, body)) + 0.5 * disp_component
            return min(1.0, max(0.0, score))

        if intent == "PULLBACK":
            # Triangular peak at depth=0.5, zero at 0 or 1
            depth_score = min(1.0, max(0.0, 1.0 - abs(depth - 0.5) * 2.0))
            recency     = min(1.0, max(0.0, 1.0 - csr / 10.0))
            return min(1.0, max(0.0, 0.6 * depth_score + 0.4 * recency))

        if intent == "LIQ_SWEEP":
            return min(1.0, max(0.0, 0.5 * float(sweep) + 0.5 * float(dsweep)))

        if intent == "REVERSAL":
            # Strong reversal = low or opposite momentum
            return min(1.0, max(0.0, 1.0 - min(1.0, abs(mom))))

        return 0.0  # UNKNOWN or unrecognised

    def _vol_score(self, features: dict[str, Any]) -> float:
        """
        Bar range vs ATR quality.

        Tent function peaking at ratio=1.0 (bar range == ATR):
            ratio <= 1.0 : score = ratio          (ramps 0→1)
            ratio >  1.0 : score = 1 - (r-1)/2   (decays 1→0 at ratio=3)
        Zero if atr <= 0 or bar range <= 0.
        """
        atr = float(features.get("atr", 0.0))
        if atr <= 0:
            return 0.0
        bar_range = float(features.get("high", 0.0)) - float(features.get("low", 0.0))
        if bar_range <= 0:
            return 0.0
        r = bar_range / atr
        score = r if r <= 1.0 else 1.0 - (r - 1.0) / 2.0
        return min(1.0, max(0.0, score))

    def _liquidity_score(self, features: dict[str, Any], direction: int) -> float:
        """
        Structural liquidity sweep evidence + volume spike.

        Sweep extent (50%):
            LONG  : (lowest_low_20 - lowest_low_5) / atr  — positive = sweep below 20-bar low
            SHORT : (highest_high_5 - highest_high_20) / atr — positive = sweep above 20-bar high
        Volume spike (50%):
            vol / vol_ma20 / 2.0 → saturates at 1.0 when volume = 2× average
        """
        atr  = float(features.get("atr",            1.0))
        vol  = float(features.get("volume",          0.0))
        vm20 = float(features.get("volume_ma20",     0.0))
        ll20 = float(features.get("lowest_low_20",   0.0))
        ll5  = float(features.get("lowest_low_5",    0.0))
        hh20 = float(features.get("highest_high_20", 0.0))
        hh5  = float(features.get("highest_high_5",  0.0))

        vol_score = min(1.0, max(0.0, (vol / vm20) / 2.0)) if vm20 > 0 else 0.0

        if atr <= 0:
            return vol_score * 0.5

        extent = ((ll20 - ll5) if direction == 1 else (hh5 - hh20)) / atr
        sweep_score = min(1.0, max(0.0, extent))

        return min(1.0, max(0.0, 0.5 * sweep_score + 0.5 * vol_score))

    def _structure_score(self, features: dict[str, Any], direction: int) -> float:
        """
        EMA alignment + displacement quality.

        EMA alignment (60%):
            LONG  : ema_fast > ema_slow → 1.0, else 0.0
            SHORT : ema_fast < ema_slow → 1.0, else 0.0
        Displacement quality (40%):
            min(1.0, disp_strength / 3.0)
        """
        ef   = float(features.get("ema_fast",      0.0))
        es   = float(features.get("ema_slow",      0.0))
        disp = float(features.get("disp_strength", 0.0))

        aligned = (
            1.0 if (direction == 1 and ef > es) or (direction == -1 and ef < es)
            else 0.0
        )
        disp_quality = min(1.0, max(0.0, disp / 3.0))

        return min(1.0, max(0.0, 0.6 * aligned + 0.4 * disp_quality))
