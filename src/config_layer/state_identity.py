"""
state_identity.py
═════════════════════════════════════════════════════════════════════════════════
CRT State Machine Identity — Enums, Baseline Transitions, and Configuration Schema.

Single source of truth for:
  - CRTState enum (12 members: the original 9 execution-timeframe states — RANGE, SWEEP,
    DISPLACEMENT, EXPANSION, RETEST, EXECUTION, RESOLUTION, SHADOW_PENDING, EXPIRED — plus 3
    parent-timeframe (calendar-true H4/D1/W1/MN1) states added by CH-htfcrt-parent-candle-smc-v1
    (2026-08-15, user-authorized): RANGE_C1, MANIPULATION_C2, DISTRIBUTION_C3. The 3 new states
    form a DISJOINT sub-graph from the original 9 (see VALID_TRANSITIONS below) — they classify
    the parent-timeframe 3-candle CRT construct (config_layer.parent_crt.ParentCRTTrack), never
    the M15 execution machine directly. See docs/governance/crt_closure_report.md (reopened by
    F-074, scope widened again by this program) and docs/governance/semantic_os/concepts.yaml
    CN-004 (invariant text updated 9->12 states, same turn).
  - Direction enum (LONG, SHORT, NONE)
  - RejectReason enum (LOW_SCORE, OUTSIDE_SESSION, NO_DOUBLE_SWEEP, NEWS_FILTER, HIGH_SPREAD, INVALID_STATE)
  - VALID_TRANSITIONS module seed (legal state edges)
  - CRTConfig dataclass (frozen, validation in __post_init__)

CRTState, VALID_TRANSITIONS, PARENT_TIMEFRAME_STATES and EXECUTION_TIMEFRAME_STATES are
GENERATED from active_models.yaml (crt.runtime) by
scripts/maintenance/gen_crt_state_identity.py into _crt_state_generated.py, and re-exported
here (CH-crt-state-generation-v1, 2026-08-31) -- so the ontology is the single authored source
for state IDENTITY. This module remains the import site for every consumer and keeps the
governance rationale. Direction, RejectReason, _VALID_KILL_PRECEDENCE and CRTConfig stay
hand-authored here: none is declared in the ontology.

Zero imports from: crt_engine_v2, state_contract_loader, state_topology.
(The one new import, config_layer._crt_state_generated, imports only `enum` -- no cycle.)
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

# ── CRTState: GENERATED from active_models.yaml ──────────────────────────────
# The 12 members (9 execution-timeframe + 3 parent-timeframe, added
# CH-htfcrt-parent-candle-smc-v1 2026-08-15) are emitted by
# scripts/maintenance/gen_crt_state_identity.py into _crt_state_generated.py and
# re-exported here, so the ontology is the single authored source for state identity
# (CH-crt-state-generation-v1, 2026-08-31). The rationale below is retained here
# rather than moved to YAML -- see the generator's docstring for why.
#
# Per-member semantics (previously inline comments on the enum, preserved verbatim):
#   SHADOW_PENDING  Cross-window displacement memory active; awaiting sweep confirmation
#   EXPIRED         Phase 3b -- soft archive: TTL exceeded, one-candle pause before RANGE reset
#   RANGE_C1        C1: the reference parent candle -- its H/L become h_ref/l_ref
#   MANIPULATION_C2 C2: sweeps C1's boundary and closes back inside (parent-scale sweep)
#   DISTRIBUTION_C3 C3: directional impulse away from the swept side (F-074 contract)
#
# The 3 parent-timeframe states classify 3 consecutive CALENDAR-TRUE parent candles
# (H4/D1/W1/MN1, built by features.parent_candle.ParentCandleBuilder) via
# config_layer.parent_crt.ParentCRTTrack. They never appear as a transition
# target/source for any of the 9 execution states.
from config_layer._crt_state_generated import (  # noqa: E402
    CRTState,
    VALID_TRANSITIONS,
    PARENT_TIMEFRAME_STATES,
    EXECUTION_TIMEFRAME_STATES,
)


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

# VALID_TRANSITIONS, PARENT_TIMEFRAME_STATES and EXECUTION_TIMEFRAME_STATES are
# GENERATED and imported above. Their governance rationale, retained verbatim:
#
# Parent-timeframe 3-candle CRT sub-graph (CH-htfcrt-parent-candle-smc-v1, 2026-08-15):
#   DISJOINT from the 9 execution states -- no edge crosses between the two sub-graphs (no
#   execution state ever transitions into RANGE_C1/MANIPULATION_C2/DISTRIBUTION_C3, and none
#   of these three ever transitions into RANGE/SWEEP/.../RESOLUTION). Deliberate -- these
#   classify a PARENT-timeframe 3-candle window (config_layer.parent_crt.ParentCRTTrack), a
#   different timeframe than the M15 execution machine; interleaving the two graphs would
#   conflate timeframes and change every existing consumer's transition-count invariants. The
#   parent track feeds the M15 engine only through the defaulted `parent_state` keyword on
#   `process_candle` (a bias/objective gate), never through a shared CRTState transition.
#
#   EXPANSION -> EXPIRED is the Phase 3b soft archive; RESOLUTION -> RANGE is a cycle-reset,
#   NOT a dead-end (terminality is expressed in lifecycle.resolution).
#
# State-set partition (CH-htfcrt-parent-candle-smc-v1, 2026-08-15):
#   Single source of truth for the disjoint split, so no consumer (tests, census artifacts,
#   docs generation) hand-duplicates the 3-name list. `PARENT_TIMEFRAME_STATES` is the
#   parent-timeframe 3-candle CRT sub-graph; `EXECUTION_TIMEFRAME_STATES` is the original
#   9-state M15 execution machine (config_layer.crt_engine_v2.CRTEngine) -- the scope of e.g.
#   docs/governance/crt_executable_state_graph.json, which is a crt_engine_v2.py-only census
#   and does not (and should not) grow to cover a different module's states.




# ─────────────────────────────────────────────────────────────────
# CONFIGURATION SCHEMA
# ─────────────────────────────────────────────────────────────────

# [SEM-021] Legal values for CRTConfig.displacement_origin_kill_precedence. The two arms are
# measured separately and never pooled; "absolute" is a declared measurement weakness.
_VALID_KILL_PRECEDENCE = frozenset({"after_resting_fills", "absolute"})


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
    # Fraction of the displacement body. Fires only when close moves AGAINST
    # state.direction (LONG: below disp.close; SHORT: above). Continuation is not a retrace.
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
    # Independent of backtest.htf_candles_per_range (do not auto-scale with HTF size).
    # Set to 0 to disable.
    pending_displacement_ttl_candles: int = 4

    # ── SEM-021 Displacement-Origin Invalidation (CH-DISP-ORIGIN-KILL, 2026-08-21) ──
    # A CLOSE-triggered structural-failure exit: when a candle CLOSES beyond the ORIGIN
    # (open) of the displacement candle that founded the setup, the premise that justified
    # the entry is void, so the trade is closed at that close rather than carried to the
    # geometric stop. Distinct from stop PLACEMENT (SEM-017) and from the stop-POLICY class
    # (SEM-019) — it moves nothing, it terminates.
    #
    # Rankable from M15 OHLC precisely BECAUSE it reads the close and not a running extreme:
    # F-087 measured the extreme-following arms at a 0.261R same-bar ambiguity band, 12–15x
    # the 0.0198–0.0212R policy spread, versus ~0.0005R for close/elapsed-time arms.
    #
    # DEFAULT OFF. Enabled only on a non-promoted shadow config; the active config and its
    # params hash are untouched. Grants no authority (§6.5) — measurable ≠ valuable.
    displacement_origin_kill_enabled: bool = False
    # "after_resting_fills" (default): TP2 → SL → TP1 partial → THEN the kill at the close.
    #   Resting orders fill intrabar and are mechanically prior; the kill still strictly
    #   preempts the SEM-017 half-way trail, so a bar that reaches TP1 and closes through the
    #   origin books the partial and exits the runner instead of arming the trail.
    # "absolute": the kill is evaluated before TP2/SL/TP1. Literal "fires first", but it can
    #   cancel a resting order that would already have filled earlier in the same bar — a form
    #   of lookahead. A DECLARED MEASUREMENT WEAKNESS, not a neutral alternative.
    displacement_origin_kill_precedence: str = "after_resting_fills"

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
        # [SEM-021] Fail closed on an unrecognised precedence rather than silently defaulting.
        # A typo that quietly fell back to "after_resting_fills" would produce a run labelled
        # as the other arm — the two are NOT equivalent, and a mislabelled arm is worse than
        # a crash because it looks like evidence.
        _prec = self.displacement_origin_kill_precedence
        if _prec not in _VALID_KILL_PRECEDENCE:
            raise ValueError(
                f"displacement_origin_kill_precedence must be one of "
                f"{sorted(_VALID_KILL_PRECEDENCE)}, got {_prec!r}"
            )
        if not isinstance(self.displacement_origin_kill_enabled, bool):
            raise ValueError(
                "displacement_origin_kill_enabled must be a bool, got "
                f"{type(self.displacement_origin_kill_enabled).__name__}"
            )

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
