"""
state_identity.py
═════════════════════════════════════════════════════════════════════════════════
CRT State Machine Identity — Enums, Baseline Transitions, and Configuration Schema.

Single source of truth for:
  - CRTState enum (9 members: RANGE, SWEEP, DISPLACEMENT, EXPANSION, RETEST, EXECUTION, RESOLUTION, SHADOW_PENDING, EXPIRED)
  - Direction enum (LONG, SHORT, NONE)
  - RejectReason enum (LOW_SCORE, OUTSIDE_SESSION, NO_DOUBLE_SWEEP, NEWS_FILTER, HIGH_SPREAD, INVALID_STATE)
  - VALID_TRANSITIONS module seed (legal state edges)
  - CRTConfig dataclass (frozen, validation in __post_init__)

Zero imports from: crt_engine_v2, state_contract_loader, state_topology.
Imported by: all three (and tests, strategies, engines, etc.).

This module breaks the circular dependency:
  OLD: crt_engine_v2 ↔ state_contract_loader/state_topology (both import CRTState from engine)
  NEW: state_identity ← state_contract_loader / state_topology / crt_engine_v2 (all import from identity)
═════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import time
from enum import Enum, auto
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────
# STATE MACHINE ENUMS
# ─────────────────────────────────────────────────────────────────

class CRTState(Enum):
    """Legal states in the CRT state machine (9 members)."""
    RANGE          = auto()
    SHADOW_PENDING = auto()   # Cross-window displacement memory active; awaiting sweep confirmation
    SWEEP          = auto()
    DISPLACEMENT   = auto()
    EXPANSION      = auto()
    EXPIRED        = auto()   # Phase 3b — soft archive: TTL exceeded, one-candle pause before RANGE reset
    RETEST         = auto()
    EXECUTION      = auto()
    RESOLUTION     = auto()


class Direction(Enum):
    """Trade direction."""
    LONG  = "LONG"
    SHORT = "SHORT"
    NONE  = "NONE"


class RejectReason(Enum):
    """Reasons for rejecting a trade signal."""
    LOW_SCORE       = "score_below_threshold"
    OUTSIDE_SESSION = "outside_session_window"
    NO_DOUBLE_SWEEP = "no_double_sweep_confirmed"
    NEWS_FILTER     = "news_filter_active"
    HIGH_SPREAD     = "spread_too_high"
    INVALID_STATE   = "invalid_state_for_execution"


# ─────────────────────────────────────────────────────────────────
# VALID TRANSITIONS SEED
# ─────────────────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[CRTState, list[CRTState]] = {
    CRTState.RANGE:          [CRTState.SWEEP, CRTState.SHADOW_PENDING],
    CRTState.SHADOW_PENDING: [CRTState.SWEEP, CRTState.RANGE],
    CRTState.SWEEP:          [CRTState.DISPLACEMENT, CRTState.EXPANSION, CRTState.RANGE],
    CRTState.DISPLACEMENT:   [CRTState.EXPANSION, CRTState.RANGE],
    CRTState.EXPANSION:      [CRTState.RETEST, CRTState.EXPIRED, CRTState.RANGE],  # Phase 3b: EXPIRED added
    CRTState.EXPIRED:        [CRTState.RANGE],   # Phase 3b — one-candle soft archive then RANGE
    CRTState.RETEST:         [CRTState.EXECUTION, CRTState.RANGE],
    CRTState.EXECUTION:      [CRTState.RESOLUTION],
    CRTState.RESOLUTION:     [CRTState.RANGE],
}


# ─────────────────────────────────────────────────────────────────
# CONFIGURATION SCHEMA
# ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CRTConfig:
    """Frozen configuration for CRT engine — fail-fast validation in __post_init__."""
    # State machine thresholds
    body_ratio_min:        float = 0.70
    atr_multiplier_min:    float = 1.50
    retest_depth_max:      float = 0.25    # [PATCH 5] now used as ceiling only

    # [PATCH 1] Bounded ATR buffer
    atr_period:            int   = 14
    atr_buffer_multiplier: int   = 3       # buffer = atr_period * this

    # [PATCH 2] Sweep age constraint
    max_sweep_age_candles: int   = 20      # sweep invalidated after N candles

    # [PATCH 3] Expansion quality
    expansion_atr_min_distance: float = 0.20   # close must be > disp_close + 0.2 * ATR

    # [PATCH 5] Adaptive retest depth
    retest_atr_depth_fraction: float = 0.50   # adaptive ceiling = 0.5 * ATR
    # [IC-007 / PLAN-001] Minimum retest depth floor as a fraction of ATR.
    # Legacy CODE literal was `min_depth = 0.1 * atr` in try_expansion_to_retest.
    # Default 0.1 preserves prior behavior; HOW owns the value via production merge.
    # Domain: finite and >= 0 (no invented upper bound — formula is ATR-relative floor).
    retest_min_depth_atr_fraction: float = 0.10

    # [IC-007 / PLAN-002] TWO DISTINCT weight identities (same legacy numbers, DIFFERENT
    # semantics — never alias each other or conf_weights):
    #   risk_score_weights      — RiskScore.final (Ultron/CRT spine score):
    #                             (sweep, breakout, retest, time). Legacy literals 0.35/0.25/0.20/0.20.
    #   score_component_weights — engines path (engines.scoring_engine.compute_scores via
    #                             engines.crt_engine.compute context; EngineRunner injects).
    # Defaults preserve prior behavior on both paths; HOW owns the values via production merge.
    # Domain each: length-4, real, finite, >= 0 (no sum constraint — dynamism is the point).
    risk_score_weights: tuple = (0.35, 0.25, 0.20, 0.20)
    score_component_weights: tuple = (0.35, 0.25, 0.20, 0.20)

    # [PATCH 7] Displacement strength ceiling
    # Displacement is measured as wick_size / ATR at the displacement candle.
    # High values (>2.0) indicate an overextended impulse move — the market has
    # already exhausted momentum, so a subsequent retest is unlikely to have
    # enough fuel to continue.  Empirical finding from EURUSD M15 backtest:
    # winners had cached_disp ≤ 1.95, losers ranged 1.33–6.10.
    max_displacement_strength: float = 2.0

    # [PATCH 6] Time-decay scoring
    score_decay_lambda:    float = 0.05    # decay rate per candle since retest

    # Ultron risk thresholds
    score_threshold:       float = 0.45
    max_spread_pct:        float = 0.05
    # ── DATA-DRIVEN CONSTANTS (AUTO-DERIVED) ──
    atr_min_displacement: float = 1.2     # displacement >= 1.2 * ATR
    confirmation_body_min: float = 0.6    # strong candle
    sl_atr_buffer: float = 0.2           # SL buffer
    tp1_atr_multiplier: float = 1.0
    tp2_atr_multiplier: float = 2.0
    # [trust-layer F2, 2026-06-10] Exit-trigger model (GOVERNED). "intrabar_touch"
    # (default) fires SL/TP on a high/low wick touch with conservative SL-before-TP
    # same-bar ordering (see CRTEngine._intrabar_trigger_price); "close_only" is the
    # legacy optimistic bound (close-crossing only). Adopting intrabar makes backtest
    # metrics realistic for an SL-based strategy. See
    # docs/analysis/exit-model-adoption-2026-06-10.md.
    exit_model: str = "intrabar_touch"
    # BREAKOUT-vs-REVERSAL intent boundary (displacement strength). Per-symbol
    # overrides resolve via production_config.resolve_breakout_disp_threshold.
    breakout_disp_threshold: float = 1.5
    # Per-intent TP1 multipliers (override tp1_atr_multiplier when intent is known)
    tp1_atr_multiplier_breakout:  float = 1.5
    tp1_atr_multiplier_pullback:  float = 0.8
    tp1_atr_multiplier_liq_sweep: float = 1.2
    tp1_atr_multiplier_reversal:  float = 1.0
    bitnet_main_threshold: float = 0.55
    use_bitnet: bool = False

    # Session windows (UTC)
    session_windows: dict = field(default_factory=lambda: {
        "LONDON":  (time(7,  0), time(10, 0)),
        "NEWYORK": (time(13, 0), time(16, 0)),
        "ASIA":    (time(0,  0), time(3,  0)),
    })

    # Sessions in which trade signals are allowed to fire.
    # Mirrors engine_runner.allowed_sessions; populated from JSON via config_builder.
    # UPPERCASE to match session_windows keys.
    allowed_sessions: tuple = ("LONDON", "NEWYORK", "OVERLAP")

    # Reset triggers
    retrace_reset_pct:   float = 0.50
    extension_reset_fib: float = 1.618

    # News blackout (minutes before/after)
    news_blackout_minutes: int = 15

    # ── Soft Confirmation Manifold (replaces binary 5-candle gate) ──
    conf_alpha:         float = 0.70   # structural (Gaussian) weight in fusion
    conf_beta:          float = 0.30   # confirmation weight in fusion
    conf_weights:       tuple = (0.35, 0.35, 0.15, 0.15)  # body, mom, dist, disp
    conf_floor:         float = 0.20   # C is clamped to [floor, 1.0]
    weak_link_weight:   float = 0.30   # penalty for weakest of body/mom
    ema_fast:           int   = 2      # EMA period for fast momentum
    ema_slow:           int   = 5      # EMA period for slow momentum

    # ── Tiered execution thresholds ──────────────────────────────
    tier_1_threshold:   float = 0.75   # full risk
    tier_2_threshold:   float = 0.30   # half risk
    soft_conf_max_candles: int = 3     # evaluation window (was 5-candle binary gate)

    # ── Shadow displacement protection (Phase 1) ──────────────────
    # Candles a pending_displacement memory survives after an HTF reset.
    # TTL = 4 = one HTF window (4 × M15 = 1 h).  Set to 0 to disable.
    pending_displacement_ttl_candles: int = 4

    # ── Expansion TTL guard (Phase 3b) ────────────────────────────
    # Expire if EITHER candle OR hour limit is exceeded. Set 0 to disable either.
    # Derived from Phase 3a: min(P99_non_outlier=495 candles, 7d=672 candles) = 495 candles.
    # 495 M15 candles = 123.75 hours → max_expansion_age_hours = 124 (ceiling).
    # P95 (342 candles) used as TEMPORAL_STALE_WIN warn threshold.
    max_expansion_age_candles: int   = 495   # expire after this many candles (≈5.2 days)
    max_expansion_age_hours:   int   = 124   # expire after this many hours (timestamp-based)
    expansion_age_warn_candles: int  = 342   # TEMPORAL_STALE_WIN warning if trade opened above P95

    # ── Shadow age-decay gate (Phase 4b) ─────────────────────────
    # Exponential decay applied to the S-score of shadow candidates at soft-conf approval.
    # effective_score = final_S × exp(−λ × candidate_age_at_entry)
    # 0.0 = OFF (no decay, Phase 3b behavior).  Experiment levels: 0.00 | 0.10 | 0.20 | 0.35
    # At shadow age=4 (invariant): λ=0.10 → ×0.670 | λ=0.20 → ×0.449 | λ=0.35 → ×0.247
    shadow_age_penalty_lambda: float = 0.0

    # Normalisation denominator for the shadow age-decay (Phase 4b Variant B).
    # 0 = Variant A (raw): exp(-λ × age)        — λ not interpretable when age is constant.
    # N = Variant B (normalised): exp(-λ × age/N) — λ=1.0 means "at max age (N), score → 1/e".
    # Recommended for Variant B: set to pending_displacement_ttl_candles (= 4).
    # A/B parity check: Variant A λ=0.20 ≡ Variant B λ=0.80, norm=4 (same penalty at age=4).
    shadow_age_norm_candles: int = 0

    # Advisory-only shadow: if True, shadow expansions never produce trades.
    # Shadow still tracks telemetry through EXPANSION→RETEST; EXECUTION is blocked.
    # Fallback when no λ satisfies the composite shadow governance gate.
    shadow_advisory_only: bool = False

    # ── Proportional sizing bands (score → risk_pct) ─────────────
    sizing_bands: list = field(default_factory=lambda: [
        (0.75, 0.010),   # Tier 1 → 1.0%
        (0.55, 0.005),   # Tier 2 → 0.5%
    ])

    def __post_init__(self) -> None:
        """Fail-closed validation for IC-007 PLAN-001/PLAN-002 HOW keys (and future strict knobs)."""
        v = self.retest_min_depth_atr_fraction
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(
                f"retest_min_depth_atr_fraction must be a real number, got {type(v).__name__}"
            )
        fv = float(v)
        if not math.isfinite(fv):
            raise ValueError(
                f"retest_min_depth_atr_fraction must be finite, got {v!r}"
            )
        if fv < 0.0:
            raise ValueError(
                f"retest_min_depth_atr_fraction must be >= 0 (ATR-relative floor), got {fv}"
            )

        # [PLAN-002] weight vectors: coerce list→tuple (JSON arrays), then fail-closed.
        for key in ("risk_score_weights", "score_component_weights"):
            w = getattr(self, key)
            if not isinstance(w, (list, tuple)):
                raise ValueError(f"{key} must be a 4-element list/tuple, got {type(w).__name__}")
            if len(w) != 4:
                raise ValueError(f"{key} must have exactly 4 components, got {len(w)}")
            coerced = []
            for i, c in enumerate(w):
                if isinstance(c, bool) or not isinstance(c, (int, float)):
                    raise ValueError(f"{key}[{i}] must be a real number, got {type(c).__name__}")
                fc = float(c)
                if not math.isfinite(fc):
                    raise ValueError(f"{key}[{i}] must be finite, got {c!r}")
                if fc < 0.0:
                    raise ValueError(f"{key}[{i}] must be >= 0, got {fc}")
                coerced.append(fc)
            # frozen dataclass — coercion via object.__setattr__ (standard __post_init__ pattern)
            object.__setattr__(self, key, tuple(coerced))
