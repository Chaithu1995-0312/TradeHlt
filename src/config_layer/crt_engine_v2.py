"""
╔══════════════════════════════════════════════════════════════════╗
║         CANDLE RANGE THEORY (CRT) TRADING ENGINE v2.0           ║
║         Deterministic State Machine + Ultron Risk Gating         ║
║                                                                  ║
║  Patch v2 — Jarvis Audit Fixes:                                  ║
║    [1] Bounded ATR buffer (atr_period × 3)                       ║
║    [2] Sweep age constraint (max_sweep_age_candles)              ║
║    [3] Strengthened expansion guard (close > disp_close + ATR)  ║
║    [4] Event timestamping on every transition                    ║
║    [5] Adaptive retest depth (min of range% and ATR%)           ║
║    [6] Time-decay scoring (exponential decay since retest)       ║
╚══════════════════════════════════════════════════════════════════╝

Architecture: RangeDetector → StateMachine → UltronRiskEngine → ExecutionEngine
All transitions are rule-based. No prediction. No ML.
"""

from __future__ import annotations
from bitnet.bitnet_inference import bitnet_score
import hashlib
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum, auto
from types import MappingProxyType
from typing import Any, List, Mapping, Optional
from features.feature_schema import CANONICAL_FEATURES
from features.schema_validator import validate_features
from config_layer.crt_sweep_taxonomy import classify_sweep as _classify_sweep_geometry
from utils.sweep_trace_logger import SweepTraceLogger
from utils.integrity_events import emit_integrity_event
import statistics as _statistics
import json as _json
from pathlib import Path as _Path

# M2 — enveloped CRT state-transition stream (additive dual-write; mirrors M1 idiom).
# Guarded import keeps crt_engine_v2 importable even if the event fabric is absent.
try:
    from events.event_fabric import make_event_envelope as _make_event_envelope, EventType as _EventType
    _ENVELOPE_OK = True
except Exception:  # noqa: BLE001
    _ENVELOPE_OK = False

_CRT_TRANSITIONS_LOG = _Path("logs/crt_transitions.jsonl")
# ─────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("CRT_ENGINE_V2")


# ─────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────

class CRTState(Enum):
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
    LONG  = "LONG"
    SHORT = "SHORT"
    NONE  = "NONE"


class RejectReason(Enum):
    LOW_SCORE       = "score_below_threshold"
    OUTSIDE_SESSION = "outside_session_window"
    NO_DOUBLE_SWEEP = "no_double_sweep_confirmed"
    NEWS_FILTER     = "news_filter_active"
    HIGH_SPREAD     = "spread_too_high"
    INVALID_STATE   = "invalid_state_for_execution"


# ─────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────

@dataclass
class Candle:
    timestamp: datetime
    open:  float
    high:  float
    low:   float
    close: float
    volume: float = 0.0
    index: int = 0          # [PATCH 4] candle_index for time-based rules

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def wick_size(self) -> float:
        return self.high - self.low

    @property
    def body_ratio(self) -> float:
        return self.body_size / self.wick_size if self.wick_size > 0 else 0.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2


@dataclass
class Range:
    """HTF or session-level price range."""
    h_ref:       float
    l_ref:       float
    equilibrium: float
    formed_at:   datetime
    htf_candle_id: str
    session:     str = "UNKNOWN"

    @property
    def size(self) -> float:
        return self.h_ref - self.l_ref

    def is_inside(self, price: float) -> bool:
        return self.l_ref <= price <= self.h_ref

    def retrace_depth(self, price: float, direction: Direction) -> float:
        if direction == Direction.LONG:
            return (price - self.l_ref) / self.size if self.size > 0 else 0.0
        return (self.h_ref - price) / self.size if self.size > 0 else 0.0


# ─────────────────────────────────────────────────────────────────
# [PATCH 4] — EVENT LOG ENTRY
# Every engine event carries full timestamp + candle index + metadata
# ─────────────────────────────────────────────────────────────────

@dataclass
class EngineEvent:
    """
    Immutable event record.
    Replays exactly when fed back into the engine — supports:
    - audit trails
    - DynamoDB persistence (Nexus GenAI storage)
    - backtesting replay
    """
    event:        str                     # e.g. "STATE_TRANSITION", "SWEEP", "RESET"
    timestamp:    datetime
    candle_index: int
    state_from:   Optional[str] = None
    state_to:     Optional[str] = None
    direction:    Optional[str] = None
    price:        Optional[float] = None
    reason:       Optional[str] = None
    metadata:     dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event":        self.event,
            "timestamp":    self.timestamp.isoformat(),
            "candle_index": self.candle_index,
            "state_from":   self.state_from,
            "state_to":     self.state_to,
            "direction":    self.direction,
            "price":        self.price,
            "reason":       self.reason,
            "metadata":     self.metadata,
        }


@dataclass
class SweepEvent:
    direction:        Direction
    price:            float
    candle:           Candle
    double_confirmed: bool = False
    candle_index:     int  = 0      # [PATCH 2] for age enforcement
    # [HANDOVER v3] Geometric sweep archetype metadata — informational only,
    # never consumed by FusionEngine / EngineRunner / UltronRiskGate.
    # Populated by RangeDetector.detect_sweep via crt_sweep_taxonomy.classify_sweep.
    sweep_type:       Optional[str] = None   # 'TYPE-A' | 'TYPE-B' | 'TYPE-C' | 'TYPE-D' | None
    sweep_label:      Optional[str] = None   # 'PINBAR BEAR' | 'SHOOTING STAR' | 'HAMMER' | 'PINBAR BULL' | None


@dataclass
class RiskScore:
    sweep_score:    float = 0.0
    breakout_score: float = 0.0
    retest_score:   float = 0.0
    time_score:     float = 0.0
    decay_factor:   float = 1.0          # [PATCH 6] applied before final
    score_override: Optional[float] = None  # set by soft-conf fusion to override computed final

    @property
    def final(self) -> float:
        if self.score_override is not None:
            return self.score_override
        raw = (
            0.35 * self.sweep_score +
            0.25 * self.breakout_score +
            0.20 * self.retest_score +
            0.20 * self.time_score
        )
        return raw * self.decay_factor


@dataclass
class Trade:
    id:           str
    direction:    Direction
    entry_price:  float
    sl_price:     float
    tp1_price:    float
    tp2_price:    float
    risk_pct:       float = 0.01      # [PATCH: Proportional sizing slot]
    runner_active:  bool  = True
    opened_at:      Optional[datetime] = None
    closed_at:      Optional[datetime] = None
    pnl:            float = 0.0
    partial_pnl:    float = 0.0    # [P2] PnL from TP1 partial close (50%)
    status:         str   = "PENDING"
    cached_features: Optional[dict] = None   # features copied from state at build time; survives reset
    open_candle_index: int = 0     # [P1] candle index at open, for time-stop tracking

    @property
    def risk_reward_tp1(self) -> float:
        if abs(self.entry_price - self.sl_price) == 0:
            return 0.0
        return abs(self.tp1_price - self.entry_price) / abs(self.entry_price - self.sl_price)


@dataclass
class EngineState:
    current_state:       CRTState  = CRTState.RANGE
    active_range:        Optional[Range] = None
    sweep_event:         Optional[SweepEvent] = None
    risk_score:          Optional[RiskScore] = None
    active_trade:        Optional[Trade] = None
    direction:           Direction = Direction.NONE
    atr:                 float = 0.0
    displacement_candle: Optional[Candle] = None
    retest_candle:       Optional[Candle] = None
    retest_candle_index: int = 0       # [PATCH 6] for decay calculation
    current_candle_index: int = 0      # [PATCH 4] global tick counter
    transition_log:      list = field(default_factory=list)   # legacy compat
    event_log:           list = field(default_factory=list)   # [PATCH 4] typed EngineEvent list
    # Soft confirmation manifold state (replaces binary awaiting_confirmation)
    evaluating_soft_conf: bool  = False
    soft_conf_candles:    int   = 0
    cached_features:      Optional[dict] = None   # [CACHE] scored at RETEST, read at EXECUTE
    # EMA state for momentum smoothing (initialised on first candle)
    ema_fast_val:         float = 0.0
    ema_slow_val:         float = 0.0
    # Phase 0b telemetry context (set from backtest loop; read by reset_to_range)
    htf_remaining_candles: int  = 0
    _displacement_entry_idx: int = 0   # candle_index when DISPLACEMENT state was entered
    # Phase 1 — Shadow displacement memory (survives one HTF reset, expires after TTL)
    pending_displacement_candle:       Optional[Candle]   = None
    pending_displacement_dir:          Direction           = Direction.NONE
    pending_displacement_ttl:          int                 = 0
    pending_displacement_source_htf:   str                 = ""
    pending_displacement_formed_idx:   int                 = 0
    pending_displacement_age_at_reset: int                 = 0
    pending_displacement_reason_created: str               = ""
    # Phase 2b — Persists True from SHADOW_EXPANSION_CONFIRMED until reset, so TRADE_OPENED
    # can read it even though the shadow action fired on an earlier candle.
    _came_from_shadow:                 bool                = False
    # Phase 3a — candle_index when EXPANSION state was entered; used for candidate_age_at_entry.
    _expansion_entry_idx:              int                 = 0
    # Phase 3b — wall-clock timestamp when EXPANSION was entered; enables hour-based TTL check.
    _expansion_entry_ts:               Optional[datetime]  = None
    # Phase 4b — HTF alignment of pending displacement at shadow expansion entry; None for normal.
    # True  = displacement direction still aligned with current HTF range midpoint.
    # False = direction conflict; shadow context is structurally misaligned.
    _shadow_htf_alignment:             Optional[bool]      = None

    def update_emas(self, close: float, fast: int = 2, slow: int = 5) -> None:
        """Standard EMA update. α = 2/(N+1). Seeds from first close."""
        if self.ema_fast_val == 0.0:
            self.ema_fast_val = self.ema_slow_val = close
            return
        alpha_f = 2.0 / (fast + 1)
        alpha_s = 2.0 / (slow + 1)
        self.ema_fast_val = close * alpha_f + self.ema_fast_val * (1.0 - alpha_f)
        self.ema_slow_val = close * alpha_s + self.ema_slow_val * (1.0 - alpha_s)


# ─────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CRTConfig:
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


# ─────────────────────────────────────────────────────────────────
# EVENT LOGGER HELPER
# ─────────────────────────────────────────────────────────────────

class EventLogger:
    """
    [PATCH 4] — Central structured event log.
    Every state change, sweep, reset, and trade action gets an EngineEvent.
    Designed for DynamoDB serialisation via .to_dict().
    """

    def __init__(self, state: EngineState):
        self._state = state
        self.log = logging.getLogger("CRT.EventLog")

    def record(
        self,
        event: str,
        candle: Candle,
        state_from: Optional[str] = None,
        state_to:   Optional[str] = None,
        direction:  Optional[str] = None,
        price:      Optional[float] = None,
        reason:     Optional[str] = None,
        metadata:   Optional[dict] = None,
    ) -> EngineEvent:
        ev = EngineEvent(
            event=event,
            timestamp=candle.timestamp,
            candle_index=candle.index,
            state_from=state_from,
            state_to=state_to,
            direction=direction,
            price=price,
            reason=reason,
            metadata=metadata or {},
        )
        self._state.event_log.append(ev)
        self.log.debug(
            f"EVENT | {ev.event} | idx={ev.candle_index} "
            f"{ev.state_from}→{ev.state_to} | {ev.reason}"
        )
        self._emit_enveloped(ev)
        return ev

    def _emit_enveloped(self, ev: EngineEvent) -> None:
        """M2 dual-write: emit STATE_TRANSITION events as a canonical envelope to
        logs/crt_transitions.jsonl. Read-only projection of the in-memory EngineEvent —
        state.event_log above stays the source of truth and is never altered. The flat
        payload carries candle ts + candle_index, so the stream is replay-comparable.
        Fail-open: any error is swallowed so the state machine is never disrupted."""
        if not _ENVELOPE_OK or ev.event != "STATE_TRANSITION":
            return
        try:
            env = _make_event_envelope(
                event_type = _EventType.STATE_TRANSITION.value,
                instrument = "",
                source     = "CRTEngine",
                payload    = ev.to_dict(),
            )
            _CRT_TRANSITIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(_CRT_TRANSITIONS_LOG, "a", encoding="utf-8") as fh:
                fh.write(_json.dumps(env) + "\n")
        except Exception as e:  # noqa: BLE001
            self.log.debug(f"CRT transition envelope emit failed: {e}")

    def dump(self) -> list[dict]:
        """Serialise full event log to list of dicts (DynamoDB-ready)."""
        return [e.to_dict() for e in self._state.event_log]


# ─────────────────────────────────────────────────────────────────
# PHASE-0 TELEMETRY COLLECTOR
# Passive observability sidecar — zero behavior change.
# Accumulates five event types during a run; flushed once at end.
# ─────────────────────────────────────────────────────────────────

class TelemetryCollector:
    """Collects CRT funnel telemetry without altering any state machine logic."""

    def __init__(self) -> None:
        self._transition_counts: dict[str, int] = {}
        self._state_entered_idx: int = 0
        # Per-expansion episode running state
        self._expansion_active: bool = False
        self._expansion_start_idx: int = 0
        self._expansion_max_depth: float = 0.0
        self._expansion_ceiling_at_max: float = 0.0
        self._expansion_time_to_max: int = 0
        # Expansion dwell histogram (candles spent in EXPANSION per episode)
        self._expansion_dwells: list[int] = []
        self._expansion_start_ts: Optional[datetime] = None   # Phase 3a — wall-clock entry time
        # Phase 3b RC1: last candle seen while EXPANSION active — for correct RUN_END closure.
        # Without this, open episodes at flush() collapse to zero duration (start=end).
        self._last_expansion_seen_idx: int = 0
        self._last_expansion_seen_ts: Optional[datetime] = None
        # Phase 3b RC-Closure: track the reason of the first (highest-priority) closure call.
        # Allows on_expansion_ended() to reject duplicate lower-priority late calls.
        self._expansion_ended_reason: str = ""
        # Closure priority: higher number wins when multiple reasons apply simultaneously.
        # Order: RETEST (execution success) > EXPIRED (TTL) > RESET (interrupted) > RUN_END (flush)
        self._CLOSURE_PRIORITY: dict[str, int] = {
            "QUALIFIED": 4,   # Retest fired — structure delivered
            "EXPIRED":   3,   # TTL guard fired
            "RESET":     2,   # HTF or other reset interrupted (any non-QUALIFIED/EXPIRED reason)
            "RUN_END":   1,   # Flush at end of run
        }
        # Accumulated records by type
        self._expansion_records: list[dict] = []
        self._reset_records:     list[dict] = []
        self._candidate_records: list[dict] = []
        self._decision_records:  list[dict] = []
        # Active candidate lifecycle (one at a time)
        self._active_candidate: Optional[dict] = None

    # ── State entry tracking ──────────────────────────────────────

    def on_state_entered(
        self, state_name: str, candle_index: int,
        candle_ts: Optional[datetime] = None,   # Phase 3a — wall-clock timestamp for age_hours_actual
    ) -> None:
        """Called from StateMachine._transition() on every valid state entry."""
        self._transition_counts[state_name] = (
            self._transition_counts.get(state_name, 0) + 1
        )
        self._state_entered_idx = candle_index
        if state_name == "EXPANSION":
            self._expansion_active         = True
            self._expansion_start_idx      = candle_index
            self._expansion_start_ts       = candle_ts     # Phase 3a
            self._last_expansion_seen_idx  = candle_index  # Phase 3b RC1
            self._last_expansion_seen_ts   = candle_ts     # Phase 3b RC1
            self._expansion_ended_reason   = ""            # Phase 3b RC-Closure: reset per episode
            self._expansion_max_depth      = 0.0
            self._expansion_ceiling_at_max = 0.0
            self._expansion_time_to_max    = 0
        # Update active candidate state list (exclude RANGE / RESOLUTION)
        if (self._active_candidate is not None
                and state_name not in ("RANGE", "RESOLUTION")
                and state_name not in self._active_candidate["entered_states"]):
            self._active_candidate["entered_states"].append(state_name)
            self._active_candidate["last_seen_idx"] = candle_index

    # ── Expansion retrace tracking ────────────────────────────────

    def on_expansion_retrace_check(
        self, candle_index: int, depth_abs: float, ceiling: float,
        candle_ts: Optional[datetime] = None,   # Phase 3b RC1 — update last-seen timestamp
    ) -> None:
        """Called once per candle in try_expansion_to_retest(), before filtering."""
        if not self._expansion_active:
            return
        if depth_abs > self._expansion_max_depth:
            self._expansion_max_depth      = depth_abs
            self._expansion_ceiling_at_max = ceiling
            self._expansion_time_to_max    = candle_index - self._expansion_start_idx
        # Phase 3b RC1: keep last-seen position current so RUN_END flush uses real episode end
        self._last_expansion_seen_idx = candle_index
        if candle_ts is not None:
            self._last_expansion_seen_ts = candle_ts

    def on_expansion_ended(
        self, candle_index: int, reason: str,
        end_ts: Optional[datetime] = None,        # Phase 3a — actual candle timestamp at episode end
        shadow_used: bool = False,                # Phase 3a — was this a shadow expansion?
        candidate_age_at_entry: int = 0,          # Phase 3a — candles from displacement → expansion
        age_pct_of_threshold: float = 0.0,        # Phase 3b — age/TTL×100; 0.0 if no TTL active
    ) -> None:
        """Emit per-episode EXPANSION_RETRACE_CHECK record when episode terminates."""
        # Phase 3b RC-Closure: closure priority guard.
        # Map reason to priority bucket. Any reason not in QUALIFIED/EXPIRED/RUN_END → RESET (2).
        _new_prio = self._CLOSURE_PRIORITY.get(
            reason if reason in self._CLOSURE_PRIORITY else "RESET", 0
        )
        if not self._expansion_active:
            # Episode already closed — allow a higher-priority late arrival to patch the record
            _old_prio = self._CLOSURE_PRIORITY.get(
                self._expansion_ended_reason if self._expansion_ended_reason in self._CLOSURE_PRIORITY
                else "RESET", 0
            )
            if _new_prio > _old_prio and self._expansion_records:
                # Patch the most recent record's ended_by and outcome
                _last = self._expansion_records[-1]
                _last["ended_by"] = (
                    "retest"  if reason == "QUALIFIED"
                    else "eof"      if reason == "RUN_END"
                    else "expired"  if reason == "EXPIRED"
                    else "reset"
                )
                _last["outcome"] = (
                    "QUALIFIED"    if reason == "QUALIFIED"
                    else "RUN_END"      if reason == "RUN_END"
                    else "EXPIRED"      if reason == "EXPIRED"
                    else "INTERRUPTED"
                )
                self._expansion_ended_reason = reason
            return
        self._expansion_active = False
        self._expansion_ended_reason = reason  # Phase 3b RC-Closure: record winning reason
        dwell = candle_index - self._expansion_start_idx
        self._expansion_dwells.append(dwell)

        # Phase 3a: ended_by taxonomy (key diagnostic for Case A vs Case B)
        _ended_by = (
            "retest"   if reason == "QUALIFIED"
            else "eof"      if reason == "RUN_END"
            else "expired"  if reason == "EXPIRED"
            else "reset"
        )

        # Phase 3a: dual age_hours — actual from timestamps, estimated from M15 approximation
        _age_estimated: float = round(dwell * 15 / 60, 2)
        _age_actual: Optional[float] = None
        if self._expansion_start_ts is not None and end_ts is not None:
            _age_actual = round(
                (end_ts - self._expansion_start_ts).total_seconds() / 3600.0, 2
            )

        # Phase 3b RC2: emit CLOCK_DRIFT — INFO if >10%, WARNING if >25%.
        # 5% was too aggressive: markets have gaps, DST, and exchange timestamp variance.
        if _age_actual is not None and _age_estimated > 0:
            _drift_pct = abs(_age_actual - _age_estimated) / _age_estimated
            if _drift_pct > 0.10:
                _drift_severity = "WARNING" if _drift_pct > 0.25 else "INFO"
                emit_integrity_event(
                    "CLOCK_DRIFT", _drift_severity, "crt_engine",
                    {
                        "age_hours_actual":    _age_actual,
                        "age_hours_estimated": _age_estimated,
                        "drift_pct":           round(_drift_pct * 100, 1),
                        "candle_index":        candle_index,
                    },
                )

        outcome = (
            "QUALIFIED"    if reason == "QUALIFIED"
            else "RUN_END"      if reason == "RUN_END"
            else "EXPIRED"      if reason == "EXPIRED"
            else "RESET_HTF"    if "HTF" in reason
            else "RESET_RETRACE"    if "retrace" in reason.lower()
            else "RESET_EXTENSION"  if "extension" in reason.lower()
            else "RESET_OTHER"
        )
        self._expansion_records.append({
            "kind":                        "EXPANSION_RETRACE_CHECK",
            "episode_start_idx":           self._expansion_start_idx,
            "episode_end_idx":             candle_index,
            "duration_candles":            dwell,
            "age_hours_actual":            _age_actual,          # Phase 3a — None if timestamps absent
            "age_hours_estimated":         _age_estimated,       # Phase 3a — M15 approximation
            "ended_by":                    _ended_by,            # Phase 3a
            "shadow_used":                 shadow_used,          # Phase 3a
            "candidate_age_at_entry":      candidate_age_at_entry,  # Phase 3a
            "max_retrace_depth_abs":       self._expansion_max_depth,
            "ceiling_at_max":              self._expansion_ceiling_at_max,
            "time_to_max_retrace_candles": self._expansion_time_to_max,
            "age_pct_of_threshold":        age_pct_of_threshold,         # Phase 3b — 0.0 if no TTL active
            "freshness_ratio":             round(age_pct_of_threshold / 100.0, 3),  # Phase 3b RC5
            "qualified":                   outcome == "QUALIFIED",
            "outcome":                     outcome,
        })

    # ── Reset attribution ─────────────────────────────────────────

    def on_reset(
        self, from_state: str, reason: str, candle_index: int,
        displacement_age_candles: int = 0,
        ema_aligned: bool = False,
        remaining_htf_candles: int = 0,
        direction_consistent: bool = False,
        candle_ts: Optional[datetime] = None,       # Phase 3a — for age_hours_actual
        shadow_used: bool = False,                  # Phase 3a — was expansion shadow-sourced?
        candidate_age_at_entry: int = 0,            # Phase 3a — candles from displacement → expansion
    ) -> None:
        """Called from StateMachine.reset_to_range() before state changes."""
        state_age = candle_index - self._state_entered_idx
        self._state_entered_idx = candle_index  # RANGE entry time
        self._transition_counts["RANGE"] = (
            self._transition_counts.get("RANGE", 0) + 1
        )
        # Compute expansion probability score for DISPLACEMENT+HTF resets
        _would_expand_score = 0.0
        if from_state == "DISPLACEMENT" and "HTF" in reason:
            _would_expand_score = (
                min(displacement_age_candles / 3, 1.0) * 0.30
                + (0.30 if ema_aligned else 0.0)
                + (0.25 if direction_consistent else 0.0)
                + min(remaining_htf_candles / 4, 1.0) * 0.15
            )
        self._reset_records.append({
            "kind":                  "RESET_ATTRIBUTED",
            "candle_index":          candle_index,
            "from_state":            from_state,
            "to_state":              "RANGE",
            "reason":                reason,
            "state_age_candles":     state_age,
            "candidate_id":          (
                self._active_candidate["candidate_id"]
                if self._active_candidate else None
            ),
            "htf_window_position":   (
                self._active_candidate.get("disp_htf_pos")
                if self._active_candidate else None
            ),
            "would_expand_score":    round(_would_expand_score, 4),
            "would_expand_threshold": 0.55,
            "would_expand":          _would_expand_score >= 0.55,
        })
        # Close expansion episode if it was active (pass Phase 3a context for rich records)
        if from_state == "EXPANSION":
            self.on_expansion_ended(
                candle_index, reason,
                end_ts=candle_ts,
                shadow_used=shadow_used,
                candidate_age_at_entry=candidate_age_at_entry,
            )
        # Classify and close active candidate
        if self._active_candidate is not None:
            death = (
                "RESET_HTF"        if "HTF" in reason
                else "RESET_RETRACE"   if "retrace" in reason.lower()
                else "RESET_EXTENSION" if "extension" in reason.lower()
                else "SWEEP_EXPIRED"   if "expired" in reason.lower() or "Sweep expired" in reason
                else "SOFT_CONF_TIMEOUT" if ("confirmation" in reason.lower()
                                              or "timeout" in reason.lower())
                else "FILTER_REJECTED" if any(k in reason for k in
                                               ("discount zone", "premium zone", "off_session"))
                else "RESET_OTHER"
            )
            self._close_candidate(death, candle_index)

    # ── Candidate lifecycle ───────────────────────────────────────

    def on_candidate_opened(
        self, candidate_id: str, candle_index: int, ts: str,
        shadow: bool = False,
    ) -> None:
        """Called when a new SWEEP (or shadow sweep) is detected."""
        if self._active_candidate is not None:
            self._close_candidate("RUN_OVERLAP", candle_index)
        self._active_candidate = {
            "candidate_id":     candidate_id,
            "first_seen_idx":   candle_index,
            "first_seen_ts":    ts,
            "last_seen_idx":    candle_index,
            "entered_states":   ["SWEEP"],
            "max_score_seen":   0.0,
            "shadow_used":      shadow,
            "score_at_approval": None,
            "death_reason":     None,
        }

    def on_candidate_score(self, score: float) -> None:
        """Track highest S-score seen across all soft-conf evaluations."""
        if self._active_candidate and score > self._active_candidate["max_score_seen"]:
            self._active_candidate["max_score_seen"] = score

    def on_displacement_htf_position(self, position: int, remaining: int) -> None:
        """Record which HTF-window position (1-4) the displacement was detected on."""
        if self._active_candidate is not None:
            self._active_candidate["disp_htf_pos"]       = position
            self._active_candidate["disp_htf_remaining"] = remaining

    def on_candidate_accepted(
        self,
        candle_index:          int,
        score_at_approval:     float = 0.0,
        shadow_context:        Optional[dict] = None,   # Phase 4b
        shadow_displacement_br: float = 0.0,            # Phase 4b — body_ratio of pending disp candle
    ) -> None:
        """Called when TRADE_OPENED fires — candidate lifecycle ends as ACCEPTED."""
        if self._active_candidate is not None:
            self._active_candidate["score_at_approval"]      = score_at_approval
            self._active_candidate["shadow_context"]         = shadow_context or {}   # Phase 4b
            self._active_candidate["shadow_displacement_br"] = shadow_displacement_br  # Phase 4b
        self._close_candidate("ACCEPTED", candle_index)

    def _close_candidate(self, death_reason: str, candle_index: int) -> None:
        if self._active_candidate is None:
            return
        c = self._active_candidate
        self._candidate_records.append({
            "kind":              "CANDIDATE_LIFECYCLE",
            "candidate_id":      c["candidate_id"],
            "first_seen_idx":    c["first_seen_idx"],
            "first_seen_ts":     c["first_seen_ts"],
            "last_seen_idx":     candle_index,
            "age_candles":       candle_index - c["first_seen_idx"],
            "entered_states":    c["entered_states"],
            "max_score_seen":    c["max_score_seen"],
            "shadow_used":          c.get("shadow_used", False),
            "score_at_approval":    c.get("score_at_approval"),    # None if not accepted
            "shadow_context":       c.get("shadow_context", {}),   # Phase 4b — age/penalty/alignment
            "shadow_displacement_br": c.get("shadow_displacement_br", 0.0),  # Phase 4b
            "death_reason":         death_reason,
        })
        self._active_candidate = None

    # ── Decision distance ─────────────────────────────────────────

    def on_decision_distance(
        self,
        candle_index: int,
        score_actual: float,
        score_threshold: float,
        accepted: bool,
        rejection_reason: str,
        soft_conf_candle_num: int,
    ) -> None:
        """Called after every S-score computation inside the soft-conf window."""
        self._decision_records.append({
            "kind":               "DECISION_DISTANCE",
            "candle_index":       candle_index,
            "candidate_id":       (
                self._active_candidate["candidate_id"]
                if self._active_candidate else None
            ),
            "score_actual":       score_actual,
            "score_threshold":    score_threshold,
            "decision_distance":  abs(score_actual - score_threshold),
            "accepted":           accepted,
            "rejection_reason":   rejection_reason,
            "soft_conf_candle_num": soft_conf_candle_num,
        })

    # ── Flush ─────────────────────────────────────────────────────

    def flush(self) -> list[dict]:
        """Return all telemetry records. Called once at end-of-run."""
        # Phase 3b RC1: use _last_expansion_seen_idx/ts, not _expansion_start_idx.
        # Using start_idx caused open episodes to collapse to zero duration at flush time.
        if self._expansion_active:
            self.on_expansion_ended(
                self._last_expansion_seen_idx, "RUN_END",
                end_ts=self._last_expansion_seen_ts,
            )
        if self._active_candidate is not None:
            self._close_candidate("RUN_END", self._state_entered_idx)

        _dwells = self._expansion_dwells
        _sorted_d = sorted(_dwells) if _dwells else []
        _dwell_stats: dict = {
            "count":   len(_dwells),
            "mean":    round(_statistics.mean(_dwells), 1)    if _dwells else 0,
            "median":  round(_statistics.median(_dwells), 1)  if _dwells else 0,
            "p90":     _sorted_d[int(0.90 * len(_sorted_d))]  if len(_dwells) >= 10 else 0,
            "p99":     _sorted_d[int(0.99 * len(_sorted_d))]  if len(_dwells) >= 10 else 0,  # Phase 3a
            "max":     max(_dwells, default=0),
            # Phase 3a: ended_by_counts — primary Case A/B diagnostic
            "ended_by_counts": {
                "retest":  sum(1 for r in self._expansion_records if r.get("ended_by") == "retest"),
                "reset":   sum(1 for r in self._expansion_records if r.get("ended_by") == "reset"),
                "eof":     sum(1 for r in self._expansion_records if r.get("ended_by") == "eof"),
                "expired": sum(1 for r in self._expansion_records if r.get("ended_by") == "expired"),
            },
        }

        # Phase 3b RC3: UNBOUNDED_STATE — CRITICAL if any episode exceeds max(P95×3, median×25).
        # P99 is self-referential with small N (the anomaly inflates P99, masking itself).
        # P95×3 is stable: normal episodes stay below, the 20k-candle outlier fires reliably.
        if len(_dwells) >= 10:
            _p95    = _sorted_d[int(0.95 * len(_sorted_d))]
            _median = _statistics.median(_dwells)
            _threshold = max(_p95 * 3, _median * 25)
            _unbounded = [d for d in _dwells if d > _threshold]
            if _unbounded:
                emit_integrity_event(
                    "UNBOUNDED_STATE", "CRITICAL", "crt_engine",
                    {
                        "state":     "EXPANSION",
                        "p95":       _p95,
                        "median":    _median,
                        "threshold": _threshold,
                        "offenders": _unbounded,
                    },
                )

        records: list[dict] = [{
            "kind":                  "TRANSITION_COUNTER",
            "state_entry_counts":    dict(self._transition_counts),
            "expansion_dwell_stats": _dwell_stats,
        }]
        records.extend(self._expansion_records)
        records.extend(self._reset_records)
        records.extend(self._candidate_records)
        records.extend(self._decision_records)
        return records


# ─────────────────────────────────────────────────────────────────
# MODULE 1 — RANGE DETECTOR
# ─────────────────────────────────────────────────────────────────

class RangeDetector:

    def __init__(self, config: CRTConfig):
        self.config = config
        self.log = logging.getLogger("CRT.RangeDetector")

    def detect_htf_range(
        self, candles: list[Candle], htf_candle_id: str, session: str = "UNKNOWN"
    ) -> Range:
        h_ref = max(c.high for c in candles)
        l_ref = min(c.low  for c in candles)
        equilibrium = (h_ref + l_ref) / 2
        r = Range(
            h_ref=h_ref, l_ref=l_ref, equilibrium=equilibrium,
            formed_at=candles[-1].timestamp,
            htf_candle_id=htf_candle_id, session=session,
        )
        self.log.info(
            f"Range | H={h_ref:.5f} L={l_ref:.5f} EQ={equilibrium:.5f} "
            f"Session={session} HTF={htf_candle_id}"
        )
        return r

    def compute_atr(self, candles: list[Candle], period: int = 14) -> float:
        if len(candles) < 2:
            return 0.0
        trs = []
        for i in range(1, len(candles)):
            prev_close = candles[i - 1].close
            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - prev_close),
                abs(candles[i].low  - prev_close),
            )
            trs.append(tr)
        window = trs[-period:] if len(trs) >= period else trs
        return sum(window) / len(window)

    def detect_sweep(
        self,
        candle: Candle,
        active_range: Range,
        prev_sweep: Optional[SweepEvent],
        current_index: int,
    ) -> Optional[SweepEvent]:
        swept_high = candle.high > active_range.h_ref and candle.close < active_range.h_ref
        swept_low  = candle.low  < active_range.l_ref and candle.close > active_range.l_ref

        if not swept_high and not swept_low:
            return None

        direction = Direction.SHORT if swept_high else Direction.LONG
        price = candle.high if swept_high else candle.low

        double_confirmed = (
            prev_sweep is not None and
            prev_sweep.direction != direction
        )

        # [HANDOVER v3] Annotate the SweepEvent with its geometric archetype
        # (TYPE-A/B/C/D) per Section 5.3 of Jarvis_CRT_Handover.docx. This is
        # diagnostic metadata only — sweep detection above (range-boundary rule)
        # is the production decision; downstream scoring ignores these fields.
        full_range = max(candle.high - candle.low, 0.001)
        upper_wick = (candle.high - max(candle.open, candle.close)) / full_range
        lower_wick = (min(candle.open, candle.close) - candle.low) / full_range
        sweep_type, sweep_label = _classify_sweep_geometry(
            upper_wick=upper_wick,
            lower_wick=lower_wick,
            body_ratio=candle.body_ratio,
            bearish=(candle.close < candle.open),
        )

        event = SweepEvent(
            direction=direction,
            price=price,
            candle=candle,
            double_confirmed=double_confirmed,
            candle_index=current_index,   # [PATCH 2]
            sweep_type=sweep_type,        # [HANDOVER v3]
            sweep_label=sweep_label,      # [HANDOVER v3]
        )
        self.log.info(
            f"Sweep | Dir={direction.value} Price={price:.5f} "
            f"Double={double_confirmed} idx={current_index} "
            f"Type={sweep_type or '-'} Label={sweep_label or '-'}"
        )
        return event


# ─────────────────────────────────────────────────────────────────
# MODULE 2 — STATE MACHINE
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


class StateMachine:

    def __init__(self, config: CRTConfig, telemetry: Optional["TelemetryCollector"] = None):
        self.config = config
        self.telemetry = telemetry
        self.log = logging.getLogger("CRT.StateMachine")

    def _transition(
        self, state: EngineState, target: CRTState,
        reason: str, candle: Optional[Candle] = None,
        ev_logger: Optional[EventLogger] = None,
    ) -> bool:
        allowed = VALID_TRANSITIONS.get(state.current_state, [])
        if target not in allowed:
            self.log.warning(
                f"ILLEGAL {state.current_state.name} → {target.name} | {reason}"
            )
            return False

        self.log.info(f"STATE: {state.current_state.name} → {target.name} | {reason}")

        # [PATCH 4] Record in both legacy log and typed event log
        entry = {"from": state.current_state.name, "to": target.name, "reason": reason}
        state.transition_log.append(entry)

        if ev_logger and candle:
            ev_logger.record(
                "STATE_TRANSITION", candle,
                state_from=state.current_state.name,
                state_to=target.name,
                reason=reason,
                # Enrich metadata so recent_transition_path() can reconstruct WHY each
                # transition happened without any duplicate storage on EngineState.
                # dict() copy of cached_features prevents reference aliasing —
                # if the caller later mutates state.cached_features this snapshot stays stable.
                metadata={
                    "sweep_type":    state.sweep_event.sweep_type if state.sweep_event else None,
                    "disp_strength": state.cached_features.get("disp_strength") if state.cached_features else None,
                    "atr":           state.atr,
                    "features":      dict(state.cached_features) if state.cached_features else {},
                },
            )

        state.current_state = target
        if target == CRTState.DISPLACEMENT and candle:
            state._displacement_entry_idx = candle.index
        if target == CRTState.EXPANSION and candle:          # Phase 3a/3b
            state._expansion_entry_idx = candle.index
            state._expansion_entry_ts  = candle.timestamp   # Phase 3b — for hour-based TTL
        if self.telemetry and candle:
            self.telemetry.on_state_entered(target.name, candle.index, candle_ts=candle.timestamp)
            if target == CRTState.RETEST and self.telemetry._expansion_active:
                self.telemetry.on_expansion_ended(
                    candle.index, "QUALIFIED",
                    end_ts=candle.timestamp,                                       # Phase 3a
                    shadow_used=state._came_from_shadow,                           # Phase 3a
                    candidate_age_at_entry=(                                       # Phase 3a
                        state._expansion_entry_idx - state._displacement_entry_idx
                    ),
                )
        return True

    # ── Transition guards ─────────────────────────────────────

    def try_range_to_sweep(
        self, state: EngineState, sweep: SweepEvent,
        ev_logger: Optional[EventLogger] = None
    ) -> bool:
        state.sweep_event = sweep
        state.direction   = sweep.direction
        return self._transition(
            state, CRTState.SWEEP,
            f"Sweep @ {sweep.price:.5f} idx={sweep.candle_index}",
            sweep.candle, ev_logger,
        )

    def try_range_to_shadow_pending(
        self, state: EngineState, sweep: "SweepEvent",
        ev_logger: Optional[EventLogger] = None
    ) -> bool:
        """Transition RANGE→SHADOW_PENDING when a confirming sweep fires while pending memory is active."""
        state.sweep_event = sweep
        state.direction   = sweep.direction
        return self._transition(
            state, CRTState.SHADOW_PENDING,
            f"Shadow resume: confirming sweep @ {sweep.price:.5f} dir={sweep.direction.value}",
            sweep.candle, ev_logger,
        )

    def try_shadow_pending_to_expansion(
        self, state: EngineState, candle: Candle,
        ev_logger: Optional[EventLogger] = None
    ) -> bool:
        """Restore prior-window displacement context and collapse SHADOW_PENDING→SWEEP→EXPANSION.

        Bypasses the body_ratio / ATR displacement strength check because displacement
        was already validated in the previous HTF window.  The confirming sweep in the
        new window is sufficient evidence that the move is continuing.
        """
        state.displacement_candle = state.pending_displacement_candle
        state.direction           = state.pending_displacement_dir
        # Two-step transition for full audit trail
        ok_sweep = self._transition(
            state, CRTState.SWEEP,
            f"Shadow: prior-window displacement restored from idx={state.pending_displacement_formed_idx}",
            candle, ev_logger,
        )
        if not ok_sweep:
            return False
        return self._transition(
            state, CRTState.EXPANSION,
            "Shadow resume: displacement carried from prior HTF window — strength check skipped",
            candle, ev_logger,
        )

    def try_sweep_to_displacement(
        self, state: EngineState, candle: Candle,
        ev_logger: Optional[EventLogger] = None
    ) -> bool:
        """
        [PATCH 2] Sweep age check — invalidate if sweep is too old.
        [PATCH 3] Displacement requires body_ratio AND ATR size.
        """
        move = abs(candle.close - candle.open)

        if move < self.config.atr_min_displacement * state.atr:
            self.log.debug(f"Displacement REJECTED: move={move:.5f} < threshold")
            return False
        # [PATCH 2] Stale sweep guard
        if state.sweep_event is not None:
            age = state.current_candle_index - state.sweep_event.candle_index
            if age > self.config.max_sweep_age_candles:
                self.log.info(
                    f"Sweep invalidated: age={age} > max={self.config.max_sweep_age_candles}. "
                    f"Resetting to RANGE."
                )
                if ev_logger:
                    ev_logger.record(
                        "SWEEP_EXPIRED", candle,
                        reason=f"age={age} exceeded max_sweep_age_candles={self.config.max_sweep_age_candles}",
                    )
                return False

        if candle.body_ratio < self.config.body_ratio_min:
            self.log.debug(
                f"Displacement REJECTED: body_ratio={candle.body_ratio:.3f} "
                f"< {self.config.body_ratio_min}"
            )
            return False

        if state.atr > 0 and candle.wick_size < self.config.atr_multiplier_min * state.atr:
            self.log.debug(
                f"Displacement REJECTED: wick={candle.wick_size:.5f} "
                f"< {self.config.atr_multiplier_min}×ATR"
            )
            return False

        state.displacement_candle = candle
        return self._transition(
            state, CRTState.DISPLACEMENT,
            f"Displacement | body_ratio={candle.body_ratio:.3f} wick={candle.wick_size:.5f}",
            candle, ev_logger,
        )

    def try_displacement_to_expansion(
        self, state: EngineState, candle: Candle,
        ev_logger: Optional[EventLogger] = None
    ) -> bool:
        """
        [PATCH 3] Strengthened expansion guard.
        Requires: close > displacement_close AND close_distance ≥ 0.2 × ATR
        (in addition to directional close > open check).
        """
        if state.displacement_candle is None:
            return False

        disp_close = state.displacement_candle.close
        is_long  = state.direction == Direction.LONG
        is_short = state.direction == Direction.SHORT

        # Basic directional check
        if is_long and not (candle.close > candle.open):
            return False
        if is_short and not (candle.close < candle.open):
            return False

        # [PATCH 3] close must extend beyond displacement close
        if is_long and candle.close <= disp_close:
            self.log.debug(
                f"Expansion REJECTED: close={candle.close:.5f} ≤ disp_close={disp_close:.5f}"
            )
            return False
        if is_short and candle.close >= disp_close:
            self.log.debug(
                f"Expansion REJECTED: close={candle.close:.5f} ≥ disp_close={disp_close:.5f}"
            )
            return False

        # [PATCH 3] ATR-distance guard
        if state.atr > 0:
            distance = abs(candle.close - disp_close)
            min_distance = self.config.expansion_atr_min_distance * state.atr
            if distance < min_distance:
                self.log.debug(
                    f"Expansion REJECTED: distance={distance:.5f} "
                    f"< {self.config.expansion_atr_min_distance}×ATR={min_distance:.5f}"
                )
                return False

        label = "Bullish" if is_long else "Bearish"
        return self._transition(
            state, CRTState.EXPANSION,
            f"{label} expansion | close={candle.close:.5f} disp_close={disp_close:.5f}",
            candle, ev_logger,
        )

    def try_expansion_to_retest(
        self, state: EngineState, candle: Candle, atr: float,
        ev_logger: Optional[EventLogger] = None
    ) -> bool:
        """
        [PATCH 5] Adaptive retest depth.
        Ceiling = max(range-based, ATR-based)
        This prevents over-filtering in low-vol and under-filtering in high-vol.
        """
        if state.active_range is None:
            return False

        rng = state.active_range

        # [PATCH 5] Adaptive ceiling
        static_ceiling  = self.config.retest_depth_max * rng.size
        atr_ceiling      = self.config.retest_atr_depth_fraction * atr if atr > 0 else static_ceiling
        adaptive_ceiling = max(static_ceiling, atr_ceiling)

        # Distance from boundary
        if state.direction == Direction.LONG:
            depth_abs = candle.close - rng.l_ref
        else:
            depth_abs = rng.h_ref - candle.close
        
        min_depth = 0.1 * atr if atr > 0 else 0.0
        # [TELEMETRY] Track every retrace attempt regardless of outcome (RC1: pass candle_ts)
        if self.telemetry:
            self.telemetry.on_expansion_retrace_check(
                state.current_candle_index, depth_abs, adaptive_ceiling,
                candle_ts=candle.timestamp,
            )
        if depth_abs < min_depth:
            return False

        # Existing ceiling check
        if depth_abs > adaptive_ceiling:
            self.log.debug(
                f"Retest REJECTED: depth_abs={depth_abs:.5f} > "
                f"adaptive_ceiling={adaptive_ceiling:.5f} "
                f"(static={static_ceiling:.5f} atr={atr_ceiling:.5f})"
            )
            return False

        # ── [PATCH 7] Displacement strength ceiling ───────────────────────────
        # Check BEFORE committing retest state (cheap early exit).
        # disp.wick_size / ATR > max_displacement_strength → overextended move.
        # Cache the value so it's available even if the guard fires.
        _disp_check = state.displacement_candle
        _atr_check  = state.atr
        if _disp_check is not None and _atr_check > 0:
            _disp_strength = _disp_check.wick_size / _atr_check
            if _disp_strength > self.config.max_displacement_strength:
                self.log.debug(
                    f"Retest REJECTED [PATCH 7]: disp_strength={_disp_strength:.3f} > "
                    f"max_displacement_strength={self.config.max_displacement_strength:.3f} "
                    f"— overextended impulse, retest unlikely to sustain"
                )
                return False

        state.retest_candle       = candle
        state.retest_candle_index = state.current_candle_index  # [PATCH 6]

        # ── [CACHE] Compute and store features at the moment retest is confirmed.
        # Uses displacement-retrace definition (retest.close vs disp.close / disp_move)
        # to match the empirical calibration in CRTGaussianScorer.
        disp = state.displacement_candle
        _atr = state.atr
        state.cached_features = {
            "retest_depth": 0.0,
            "body_ratio": 0.0,
            "disp_str": 0.0,
        }
        if disp is not None and _atr > 0 and abs(disp.close - disp.open) > 0:
            _disp_move = abs(disp.close - disp.open)
            # retrace = how far candle.close moved back toward disp.open from disp.close
            _retrace   = abs(candle.close - disp.open) / _disp_move
            # [Phase-6] session + double_confirmed stamped here so
            # Phase5ExecutionGate.evaluate() can apply regime-based risk tiers
            # without needing live engine state at fill time.
            state.cached_features = {
                "retest_depth":     _retrace,
                "body_ratio":       disp.body_ratio,
                "disp_strength":    disp.wick_size / _atr,
                "retest_index":     state.current_candle_index,
                "session":          state.active_range.session if state.active_range else "UNKNOWN",
                "double_sweep":     state.sweep_event.double_confirmed if state.sweep_event else False,
            }
            # Hard assertion — production behavior
            assert "disp_strength" in state.cached_features, "Missing canonical: disp_strength"
            assert "body_ratio" in state.cached_features, "Missing canonical: body_ratio"
            try:
                validate_features(
                    {
                        "body_ratio": float(state.cached_features.get("body_ratio", 0.0)),
                        "atr": float(_atr),
                        "displacement": float(state.cached_features.get("disp_str", 0.0)),
                        "retest_depth": float(state.cached_features.get("retest_depth", 0.0)),
                        "session": str(state.cached_features.get("session", "UNKNOWN")),
                        "spread": 0.0,
                    },
                    context="crt_engine_v2.cached_features",
                )
            except Exception as _schema_err:
                self.log.debug(f"[FSUL] cached feature schema check skipped: {_schema_err}")
            print(
                    f"[CRT DEBUG] disp_open={disp.open:.5f} "
                    f"disp_close={disp.close:.5f} "
                    f"retest={candle.close:.5f} "
                    f"r={_retrace:.3f}"
                )

        return self._transition(
            state, CRTState.RETEST,
            f"Retest | depth_abs={depth_abs:.5f} ceiling={adaptive_ceiling:.5f}",
            candle, ev_logger,
        )

    def try_retest_to_execution(
        self, state: EngineState, candle: Optional[Candle] = None,
        ev_logger: Optional[EventLogger] = None
    ) -> bool:
        return self._transition(
            state, CRTState.EXECUTION,
            "Risk approved → entering execution",
            candle, ev_logger,
        )

    def try_execution_to_resolution(
        self, state: EngineState, reason: str,
        candle: Optional[Candle] = None,
        ev_logger: Optional[EventLogger] = None,
    ) -> bool:
        return self._transition(state, CRTState.RESOLUTION, reason, candle, ev_logger)

    def reset_to_range(
        self, state: EngineState, reason: str,
        candle: Optional[Candle] = None,
        ev_logger: Optional[EventLogger] = None,
    ) -> None:
        self.log.info(f"RESET → RANGE | {reason}")
        state.transition_log.append({"from": state.current_state.name, "to": "RANGE", "reason": reason})

        # [TELEMETRY] Reset attribution + expansion/candidate closure
        if self.telemetry and candle:
            _disp_age = (
                candle.index - state._displacement_entry_idx
                if state.current_state == CRTState.DISPLACEMENT
                else 0
            )
            _ema_aligned = (
                (state.ema_fast_val > state.ema_slow_val) == (state.direction.value == "LONG")
                if state.direction.value in ("LONG", "SHORT") else False
            )
            _dir_con = (
                (candle.close > candle.open) == (state.direction.value == "LONG")
                if state.direction.value in ("LONG", "SHORT") else False
            )
            self.telemetry.on_reset(
                state.current_state.name, reason, candle.index,
                displacement_age_candles=_disp_age,
                ema_aligned=_ema_aligned,
                remaining_htf_candles=state.htf_remaining_candles,
                direction_consistent=_dir_con,
                candle_ts=candle.timestamp,                              # Phase 3a
                shadow_used=state._came_from_shadow,                     # Phase 3a
                candidate_age_at_entry=(                                 # Phase 3a
                    state._expansion_entry_idx - state._displacement_entry_idx
                    if state.current_state == CRTState.EXPANSION else 0
                ),
            )

        if ev_logger and candle:
            ev_logger.record(
                "RESET", candle,
                state_from=state.current_state.name,
                state_to="RANGE",
                reason=reason,
            )

        # [Phase 1] Create pending displacement memory before clearing, if appropriate
        _create_shadow = (
            state.current_state == CRTState.DISPLACEMENT
            and state.displacement_candle is not None
            and "HTF" in reason
        )
        if _create_shadow:
            state.pending_displacement_candle        = state.displacement_candle
            state.pending_displacement_dir           = state.direction
            state.pending_displacement_ttl           = self.config.pending_displacement_ttl_candles
            state.pending_displacement_source_htf    = (
                state.active_range.htf_candle_id if state.active_range else ""
            )
            state.pending_displacement_formed_idx    = state._displacement_entry_idx
            state.pending_displacement_age_at_reset  = (
                candle.index - state._displacement_entry_idx if candle else 0
            )
            state.pending_displacement_reason_created = reason
        elif state.pending_displacement_ttl > 0 and not _create_shadow:
            # Non-HTF reset (retrace, extension, session) expires any existing shadow memory
            state.pending_displacement_candle  = None
            state.pending_displacement_ttl     = 0
            state.pending_displacement_dir     = Direction.NONE

        state.current_state        = CRTState.RANGE
        state.sweep_event          = None
        state.displacement_candle  = None
        state.retest_candle        = None
        state.retest_candle_index  = 0
        state.risk_score           = None
        state.direction            = Direction.NONE
        state.cached_features      = None   # [CACHE] invalidate on reset
        state.evaluating_soft_conf = False  # clear soft conf window on every reset
        state.soft_conf_candles    = 0
        state._came_from_shadow      = False  # [Phase 2b] clear shadow flag on reset
        state._expansion_entry_idx   = 0      # [Phase 3a] clear expansion entry tracker
        state._expansion_entry_ts    = None   # [Phase 3b] clear hour-based TTL anchor
        state._shadow_htf_alignment  = None   # [Phase 4b] clear HTF alignment signal


# ─────────────────────────────────────────────────────────────────
# MODULE 3 — ULTRON RISK ENGINE
# ─────────────────────────────────────────────────────────────────

class UltronRiskEngine:
    """
    Scores a setup before execution.
    FINAL = (0.35·sweep + 0.25·breakout + 0.20·retest + 0.20·time) × decay_factor
    """

    def __init__(self, config: CRTConfig):
        self.config = config
        self.log = logging.getLogger("CRT.UltronRisk")
        self._news_active      = False
        self._current_spread_pct = 0.0

    def set_news_flag(self, active: bool) -> None:
        self._news_active = active
        self.log.info(f"News filter: {'ACTIVE' if active else 'CLEAR'}")

    def set_spread(self, bid: float, ask: float) -> None:
        mid = (bid + ask) / 2
        self._current_spread_pct = (ask - bid) / mid if mid > 0 else 0.0

    # ── Scoring components ────────────────────────────────────

    def score_sweep(self, sweep: SweepEvent, active_range: Range) -> float:
        base = 0.6
        double_bonus = 0.4 if sweep.double_confirmed else 0.0
        ref = active_range.h_ref if sweep.direction == Direction.SHORT else active_range.l_ref
        overshoot = abs(sweep.price - ref)
        proximity_penalty = min(overshoot / active_range.size, 0.2) if active_range.size > 0 else 0.2
        return min(max(0.0, base + double_bonus - proximity_penalty), 1.0)

    def score_breakout(self, displacement_candle: Candle, atr: float) -> float:
        body_component = min(displacement_candle.body_ratio, 1.0)
        atr_multiple   = displacement_candle.wick_size / atr if atr > 0 else 0.0
        atr_component  = min(atr_multiple / 3.0, 1.0)
        return 0.5 * body_component + 0.5 * atr_component

    def score_retest(self, retest_candle: Candle, active_range: Range, direction: Direction, atr: float) -> float:
        """
        [PATCH 5] Adaptive depth ceiling used in scoring too.
        Depth from boundary → lower = better.
        """
        if direction == Direction.LONG:
            depth_abs = retest_candle.close - active_range.l_ref
        else:
            depth_abs = active_range.h_ref - retest_candle.close

        static_ceiling  = self.config.retest_depth_max * active_range.size
        atr_ceiling      = self.config.retest_atr_depth_fraction * atr if atr > 0 else static_ceiling
        adaptive_ceiling = max(static_ceiling, atr_ceiling)

        score = max(0.0, 1.0 - depth_abs / adaptive_ceiling) if adaptive_ceiling > 0 else 0.0
        return score

    def score_time(self, timestamp: datetime) -> float:
        t = timestamp.time()
        matches = sum(1 for start, end in self.config.session_windows.values() if start <= t <= end)
        if matches >= 2:
            return 1.0
        if matches == 1:
            return 0.8
        return 0.0

    def compute_decay_factor(self, state: EngineState) -> float:
        """
        [PATCH 6] Exponential decay based on candles elapsed since retest confirmation.
        decay = exp(-lambda * candles_since_retest)
        At 0 candles: factor=1.0. At 10 candles (λ=0.10): factor≈0.37.
        """
        candles_elapsed = state.current_candle_index - state.retest_candle_index
        if candles_elapsed <= 0:
            return 1.0
        factor = math.exp(-self.config.score_decay_lambda * candles_elapsed)
        self.log.debug(
            f"DecayFactor | elapsed={candles_elapsed} λ={self.config.score_decay_lambda} "
            f"factor={factor:.4f}"
        )
        return factor

    def compute_score(self, state: EngineState) -> RiskScore:
        rs = RiskScore()
        if state.sweep_event and state.active_range:
            rs.sweep_score = self.score_sweep(state.sweep_event, state.active_range)
        if state.displacement_candle:
            rs.breakout_score = self.score_breakout(state.displacement_candle, state.atr)
        if state.retest_candle and state.active_range:
            rs.retest_score = self.score_retest(
                state.retest_candle, state.active_range, state.direction, state.atr
            )
        ref_candle = state.retest_candle or state.displacement_candle
        if ref_candle:
            rs.time_score = self.score_time(ref_candle.timestamp)

        rs.decay_factor = self.compute_decay_factor(state)   # [PATCH 6]

        self.log.info(
            f"RiskScore | sweep={rs.sweep_score:.3f} breakout={rs.breakout_score:.3f} "
            f"retest={rs.retest_score:.3f} time={rs.time_score:.3f} "
            f"decay={rs.decay_factor:.3f} FINAL={rs.final:.3f}"
        )
        return rs

    def resolve_risk_pct(self, final_score: float) -> float:
        """
        [PATCH: Proportional sizing] Map score to position risk %.
        Plugs directly into Ultron capital governance.
        """
        for threshold, pct in sorted(self.config.sizing_bands, reverse=True):
            if final_score >= threshold:
                return pct
        return 0.0

    # ── Soft Confirmation Manifold ────────────────────────────

    def compute_soft_confirmation(
        self, candle: Candle, state: EngineState
    ) -> float:
        """
        Continuous confirmation score C ∈ [conf_floor, 1.0].

        Components:
          f_body — body ratio vs target (rewards conviction, caps exhaustion)
          f_mom  — EMA-spread momentum (smoothed directional velocity)
          f_dist — Gaussian distance decay from retest boundary
          f_disp — structural inheritance from displacement candle

        C = 0.7 × linear_blend + 0.3 × min(f_body, f_mom)  [Weak-Link Penalty]
        """
        w_body, w_mom, w_dist, w_disp = self.config.conf_weights

        # 1. Body ratio — normalised to confirmation_body_min target
        f_body = min(1.0, candle.body_ratio / self.config.confirmation_body_min)

        # 2. Smoothed momentum — EMA fast/slow spread normalised by ATR
        dir_mult = 1.0 if state.direction == Direction.LONG else -1.0
        mom_delta = (state.ema_fast_val - state.ema_slow_val) * dir_mult
        f_mom = max(0.0, min(1.0, mom_delta / state.atr)) if state.atr > 0 else 0.0

        # 3. Non-linear distance decay — Gaussian penalty for late entries
        rng = state.active_range
        static_ceiling  = self.config.retest_depth_max * rng.size
        atr_ceiling     = self.config.retest_atr_depth_fraction * state.atr if state.atr > 0 else static_ceiling
        adaptive_ceiling = max(static_ceiling, atr_ceiling)
        if state.direction == Direction.LONG:
            depth = abs(candle.close - rng.l_ref)
        else:
            depth = abs(rng.h_ref - candle.close)
        f_dist = math.exp(-((depth / adaptive_ceiling) ** 2)) if adaptive_ceiling > 0 else 0.0

        # 4. Displacement strength — structural inheritance
        disp      = state.displacement_candle
        disp_move = abs(disp.close - disp.open) if disp else 0.0
        f_disp    = min(1.0, disp_move / (1.5 * state.atr)) if state.atr > 0 else 0.0

        # Linear blend
        C_linear = (w_body * f_body) + (w_mom * f_mom) + (w_dist * f_dist) + (w_disp * f_disp)

        # Weak-link penalty: min(body, mom) drags down a hiding bad signal
        weak_link = min(f_body, f_mom)
        C = (1.0 - self.config.weak_link_weight) * C_linear + self.config.weak_link_weight * weak_link

        C = max(self.config.conf_floor, C)

        self.log.debug(
            f"SoftConf | C={C:.3f} body={f_body:.2f} mom={f_mom:.2f} "
            f"dist={f_dist:.2f} disp={f_disp:.2f}"
        )
        return C

    def approve_with_soft_conf(
        self,
        state: EngineState,
        conf_candle: Candle,
    ) -> tuple[bool, Optional[RejectReason], float]:
        """
        Replaces the binary approve() during the soft-confirmation window.
        Returns (approved, reason, final_S).

        S = G^α × C^β   (geometric fusion, strictly bounded [0,1])
        Tier 1: S ≥ tier_1_threshold → full risk
        Tier 2: S ≥ tier_2_threshold → half risk
        """
        # Hard gates (unchanged)
        if self._news_active:
            return False, RejectReason.NEWS_FILTER, 0.0
        if self._current_spread_pct > self.config.max_spread_pct:
            return False, RejectReason.HIGH_SPREAD, 0.0

        # Structural score G (Ultron base)
        #rs = self.compute_score(state)

        rs = self.compute_score(state)
        state.risk_score = rs

        # -----------------------------
        # BitNet Validation Layer
        # -----------------------------
        required = ["body_ratio", "retest_depth", "disp_strength"]

        if state.cached_features and all(k in state.cached_features for k in required):
            features = state.cached_features.copy()
            features["atr"] = state.atr
            features["candles_since_retest"] = (
                state.current_candle_index - state.retest_candle_index
            )

            if self.config.use_bitnet:
                bn_score = bitnet_score(features)
                self.log.info(f"BitNetMain Score: {bn_score:.4f}")
                if bn_score < 0.55:
                    self.log.warning(f"REJECTED BY BITNET MAIN (score={bn_score:.3f})")
                    return False, RejectReason.LOW_SCORE, 0.0
# else: BitNet is disabled – no check
        state.risk_score = rs
        G = rs.final

        # Confirmation score C
        C = self.compute_soft_confirmation(conf_candle, state)

        # Geometric fusion
        S = (G ** self.config.conf_alpha) * (C ** self.config.conf_beta)

        self.log.info(
            f"FusionScore | S={S:.3f} = G={G:.3f}^{self.config.conf_alpha} "
            f"× C={C:.3f}^{self.config.conf_beta}"
        )

        if S >= self.config.tier_1_threshold:
            self.log.info(f"APPROVED TIER 1 | S={S:.3f}")
            return True, None, S
        elif S >= self.config.tier_2_threshold:
            self.log.info(f"APPROVED TIER 2 | S={S:.3f}")
            return True, None, S
        else:
            self.log.warning(f"REJECTED | S={S:.3f} < tier_2={self.config.tier_2_threshold}")
            return False, RejectReason.LOW_SCORE, S

    # ── Gate ─────────────────────────────────────────────────

    def approve(self, state: EngineState) -> tuple[bool, Optional[RejectReason]]:

        # HARD GATES
        if self._news_active:
            self.log.warning(f"REJECTED: {RejectReason.NEWS_FILTER.value}")
            return False, RejectReason.NEWS_FILTER

        if self._current_spread_pct > self.config.max_spread_pct:
            self.log.warning(
                f"REJECTED: {RejectReason.HIGH_SPREAD.value} "
                f"(spread={self._current_spread_pct:.4f})"
            )
            return False, RejectReason.HIGH_SPREAD

        # BASE SCORE
        #rs = self.compute_score(state)
        

        rs = self.compute_score(state)
        state.risk_score = rs

        # -----------------------------
        # BitNet Validation Layer
        # -----------------------------
        required = ["body_ratio", "retest_depth", "disp_strength"]

        if state.cached_features and all(k in state.cached_features for k in required):
            features = state.cached_features.copy()
            features["atr"] = state.atr
            features["candles_since_retest"] = (
                state.current_candle_index - state.retest_candle_index
            )

            if not hasattr(state, "bitnet_main_score"):
                state.bitnet_main_score = bitnet_score(features)

            bitnet_main_score = state.bitnet_main_score

            self.log.info(f"BitNetMain Score: {bitnet_main_score:.4f}")

            if bitnet_main_score < 0.55:
                self.log.warning(f"REJECTED BY BITNET MAIN (score={bitnet_main_score:.3f})")
                return False, RejectReason.LOW_SCORE, 0.0
        state.risk_score = rs

        penalty = 0.0
        bonus = 0.0

        # SESSION PENALTY (SOFT)
        ref_candle = state.retest_candle or state.displacement_candle
        if ref_candle and self.score_time(ref_candle.timestamp) == 0.0:
            penalty += 0.10   # reduced

        # DOUBLE SWEEP
        if state.sweep_event:
            if state.sweep_event.double_confirmed:
                bonus += 0.10
            

        adjusted_score = rs.final - penalty + bonus

        if adjusted_score < self.config.score_threshold:
            self.log.warning(
                f"REJECTED: {RejectReason.LOW_SCORE.value} "
                f"(raw={rs.final:.3f} adjusted={adjusted_score:.3f} "
                f"penalty={penalty:.3f} bonus={bonus:.3f})"
            )
            return False, RejectReason.LOW_SCORE

        self.log.info(
            f"APPROVED | raw={rs.final:.3f} adjusted={adjusted_score:.3f} "
            f"penalty={penalty:.3f} bonus={bonus:.3f} "
            f"risk_pct={self.resolve_risk_pct(adjusted_score):.3f}"
        )

        return True, None


# ─────────────────────────────────────────────────────────────────
# MODULE 4 — EXECUTION ENGINE
# ─────────────────────────────────────────────────────────────────

class ExecutionEngine:

    def __init__(self, config: CRTConfig):
        self.config = config
        self.log = logging.getLogger("CRT.Execution")
        self._trade_counter = 0

    def _next_id(self) -> str:
        """Fallback sequential ID — used internally before entry price is known."""
        self._trade_counter += 1
        return f"CRT-{self._trade_counter:04d}"

    @staticmethod
    def generate_trade_id(instrument: str, opened_at, direction: str, entry: float) -> str:
        """
        Content-addressed trade ID. Unique across instruments, runs, and machines.
        Tier-1.1 hardening vs original:
          • 16 hex chars (was 12) — collision prob 2.7e-12 at 10k trades
          • Timestamp normalised to second precision — strips tz + microseconds
          • Entry rounded to 5dp with explicit .5f format — kills float repr drift
          • UTF-8 encoding — no locale dependency
        """
        from datetime import datetime as _dt
        if isinstance(opened_at, _dt):
            ts_norm = opened_at.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            ts_norm = str(opened_at)[:19]   # "YYYY-MM-DDTHH:MM:SS"
        raw = f"{instrument}|{ts_norm}|{direction}|{round(entry, 5):.5f}"
        return "CRT-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _derive_trade_intent(features: dict) -> str:
        """Classify trade intent from cached features for TP multiplier selection."""
        if features.get("sweep_detected") or features.get("double_sweep"):
            return "liq_sweep"
        rd  = float(features.get("retest_depth",         0.0))
        csr = int(  features.get("candles_since_retest", 99))
        mom = float(features.get("momentum_score",       0.0))
        if 0.3 <= rd <= 0.7 and csr <= 5 and mom > 0:
            return "pullback"
        body = float(features.get("body_ratio",    0.0))
        disp = float(features.get("disp_strength", 0.0))
        if body > 0.6 and disp > 1.5:
            return "breakout"
        return "reversal"

    def build_trade(
        self, state: EngineState, risk_engine: Optional[UltronRiskEngine] = None
    ) -> Optional[Trade]:
        if state.active_range is None or state.sweep_event is None:
            self.log.error("Cannot build trade: missing range or sweep.")
            return None

        rng       = state.active_range
        direction = state.direction

        atr = state.atr
        entry = state.retest_candle.close

        # ── SL anchored to displacement candle extreme ────────────────────────
        # The displacement candle is the structural event that created the move.
        # It doesn't drift with HTF range refreshes (unlike sweep_event.price or
        # active_range boundaries which update every 16 candles).
        # CRT doctrine: SL beyond the displacement candle = trade is structurally invalid.
        if state.displacement_candle is None:
            self.log.error("Cannot build trade: no displacement candle.")
            return None

        if direction == Direction.LONG:
            # Swept LOW → displaced UP → SL below displacement candle low
            sl  = state.displacement_candle.low  - self.config.sl_atr_buffer * atr
            # [Phase-2] TP levels anchored to actual risk distance (1R and 2R)
            # This guarantees TP1=+1R and TP2=+2R regardless of ATR scaling.
            # Risk distance is computed AFTER sl is set so it's always consistent.

        elif direction == Direction.SHORT:
            # Swept HIGH → displaced DOWN → SL above displacement candle high
            sl  = state.displacement_candle.high + self.config.sl_atr_buffer * atr
        else:
            self.log.error("Cannot build trade: direction NONE.")
            return None

        # ── Inverted SL guard ──────────────────────────────────────────────
        # Rejects when SL lands on the wrong side of entry — happens when the
        # sweep is extremely close to the range boundary, making risk_distance
        # near-zero and position_size overflow to catastrophic levels.
        if direction == Direction.LONG and sl >= entry:
            self.log.warning(
                f"Trade REJECTED: inverted SL on LONG "
                f"(entry={entry:.5f} sl={sl:.5f} sweep={state.sweep_event.price:.5f})"
            )
            return None
        if direction == Direction.SHORT and sl <= entry:
            self.log.warning(
                f"Trade REJECTED: inverted SL on SHORT "
                f"(entry={entry:.5f} sl={sl:.5f} sweep={state.sweep_event.price:.5f})"
            )
            return None

        # [Phase-2] Anchor TP1 and TP2 to actual risk distance (R-multiples)
        # TP1 uses per-intent multiplier; TP2 uses tp2_atr_multiplier (default 2R).
        risk_dist  = abs(entry - sl)
        _intent    = self._derive_trade_intent(state.cached_features or {})
        _tp1_key   = f"tp1_atr_multiplier_{_intent}"
        _tp1_mult  = getattr(self.config, _tp1_key, self.config.tp1_atr_multiplier)
        _tp2_mult  = self.config.tp2_atr_multiplier
        if direction == Direction.LONG:
            tp1 = entry + _tp1_mult * risk_dist
            tp2 = entry + _tp2_mult * risk_dist
        else:
            tp1 = entry - _tp1_mult * risk_dist
            tp2 = entry - _tp2_mult * risk_dist

        # [PATCH: Proportional sizing — priority order]
        # 1. Gaussian scorer already wrote risk_pct onto the Trade object via runner
        #    (runner calls engine.state.active_trade.risk_pct = ... before journaling)
        # 2. Ultron RiskScore is available → use band table
        # 3. Fallback: minimum viable risk (0.5% — never 0)
        if state.risk_score and risk_engine:
            risk_pct = risk_engine.resolve_risk_pct(state.risk_score.final)
            if risk_pct == 0.0:
                risk_pct = 0.005   # floor — score below all bands still gets minimum
        elif state.risk_score:
            # No Ultron engine passed but score exists — map linearly
            raw = state.risk_score.final
            risk_pct = max(0.005, min(0.015, raw * 0.015))
        else:
            risk_pct = 0.005   # warmup / no-score default

        trade = Trade(
            id=self._next_id(),
            direction=direction,
            entry_price=entry,
            sl_price=sl,
            tp1_price=tp1,
            tp2_price=tp2,
            risk_pct=risk_pct,
            runner_active=True,
            cached_features=state.cached_features,   # persists through state reset
        )
        self.log.info(
            f"Trade built | {trade.id} | Dir={direction.value} "
            f"Entry={entry:.5f} SL={sl:.5f} TP1={tp1:.5f} TP2={tp2:.5f} "
            f"RR={trade.risk_reward_tp1:.2f} risk_pct={risk_pct:.3f}"
        )
        return trade

    def open_trade(self, trade: Trade, timestamp: datetime) -> None:
        trade.opened_at = timestamp
        trade.status = "OPEN"
        self.log.info(f"Trade OPENED | {trade.id} @ {timestamp}")

    def update_trade(self, trade: Trade, current_price: float) -> str:
        """
        [P2] Partial close + break-even shift logic.
        TP1: close 50% of position, lock remaining at breakeven.
        TP2: close remaining 50% runner.
        SL after TP1: runner stopped at entry (breakeven) — no further loss.
        """
        if trade.status not in ("OPEN", "TP1"):
            return "UNCHANGED"

        is_long       = trade.direction == Direction.LONG
        pnl_direction = 1 if is_long else -1

        hit_sl  = current_price <= trade.sl_price  if is_long else current_price >= trade.sl_price
        hit_tp1 = current_price >= trade.tp1_price if is_long else current_price <= trade.tp1_price
        hit_tp2 = current_price >= trade.tp2_price if is_long else current_price <= trade.tp2_price

        # ── Priority order: TP2 > SL > TP1 (all on same candle, TP2 wins) ──

        if hit_tp2 and trade.status == "TP1":
            # Runner (50%) reaches full target
            runner_pnl   = 0.5 * pnl_direction * (trade.tp2_price - trade.entry_price)
            trade.pnl    = trade.partial_pnl + runner_pnl
            trade.status = "TP2"
            self.log.info(
                f"Trade TP2 HIT | {trade.id} | "
                f"partial={trade.partial_pnl:.5f} runner={runner_pnl:.5f} total={trade.pnl:.5f}"
            )
            return "TP2"

        if hit_sl:
            if trade.status == "TP1":
                # [P2] Runner stopped at breakeven — SL was moved to entry after TP1
                # No additional loss on the runner; only partial_pnl counts
                trade.pnl    = trade.partial_pnl   # 0 on the runner (BE hit)
                trade.status = "STOPPED"
                self.log.info(
                    f"Trade BE HIT | {trade.id} | "
                    f"runner stopped at entry, partial locked: {trade.partial_pnl:.5f}"
                )
            else:
                # Full loss before TP1
                trade.pnl    = pnl_direction * (trade.sl_price - trade.entry_price)
                trade.status = "STOPPED"
                self.log.info(f"Trade STOPPED | {trade.id} | PnL={trade.pnl:.5f}")
            return "STOPPED"

        if hit_tp1 and trade.status == "OPEN":
            # [P2] Partial close: book 50% of the TP1 move
            trade.partial_pnl = 0.5 * pnl_direction * (trade.tp1_price - trade.entry_price)
            trade.pnl         = trade.partial_pnl
            # [Phase-A.2] Half-way trail-SL on the runner: locks in 0.5R minimum
            # instead of plain breakeven. SL = entry + 0.5 * (TP1 − entry).
            trade.sl_price    = trade.entry_price + 0.5 * (trade.tp1_price - trade.entry_price)
            trade.status      = "TP1"
            self.log.info(
                f"Trade TP1 HIT | {trade.id} | "
                f"partial_pnl={trade.partial_pnl:.5f} SL→trail={trade.sl_price:.5f}"
            )
            return "TP1"

        return "UNCHANGED"


# ─────────────────────────────────────────────────────────────────
# MODULE 5 — RESET LOGIC
# ─────────────────────────────────────────────────────────────────

class ResetLogic:

    def __init__(self, config: CRTConfig):
        self.config = config
        self.log = logging.getLogger("CRT.Reset")

    def should_reset(
        self,
        state: EngineState,
        current_candle: Candle,
        current_htf_id: str,
    ) -> tuple[bool, str]:
        if state.active_range is None:
            return False, ""

        # [Phase-A.3] Protect active trades from reset — let SL/TP/TTL decide
        # the exit. Without this, retrace / HTF-flip / extension kills trades
        # 1 candle after open, before TP1 or SL can fire.
        if state.active_trade and state.active_trade.status in ("OPEN", "TP1"):
            return False, ""

        if current_htf_id != state.active_range.htf_candle_id:
            if state.current_state in [CRTState.EXPANSION, CRTState.RETEST]:
                return False, ""  # DO NOT INTERRUPT ACTIVE SETUP
            return True, f"HTF changed: {state.active_range.htf_candle_id} → {current_htf_id}"

        price = current_candle.close

        if state.displacement_candle is not None:
            disp = state.displacement_candle
            move = abs(disp.close - disp.open)
            retrace = abs(price - disp.close) / move if move > 0 else 0.0
            if retrace >= self.config.retrace_reset_pct:
                return True, f"50% retrace hit (retrace={retrace:.3f})"

        if state.sweep_event is not None and state.displacement_candle is not None:
            sweep_level    = state.sweep_event.price
            disp_close     = state.displacement_candle.close
            extension_size = abs(disp_close - sweep_level) * self.config.extension_reset_fib
            if state.direction == Direction.LONG:
                ext_level = sweep_level + extension_size
                if price >= ext_level:
                    return True, f"1.618 extension hit @ {ext_level:.5f}"
            else:
                ext_level = sweep_level - extension_size
                if price <= ext_level:
                    return True, f"1.618 extension hit @ {ext_level:.5f}"

        return False, ""


# ─────────────────────────────────────────────────────────────────
# ORCHESTRATOR — CRT ENGINE v2
# ─────────────────────────────────────────────────────────────────

class CRTEngine:
    """
    Top-level orchestrator.
    Feed candles one at a time via `process_candle()`.
    All patches wired through here.
    """

    def __init__(self, config: Optional[CRTConfig] = None,
                 sweep_tracer: Optional[SweepTraceLogger] = None):
        # Config MUST be provided via ConfigBuilder.build(instrument).
        # Direct CRTConfig() fallback is forbidden — it bypasses the market router.
        if config is None:
            raise ValueError(
                "CRTEngine requires an explicit CRTConfig. "
                "Use ConfigBuilder.build(instrument) to create one."
            )
        self.config    = config
        self.detector  = RangeDetector(self.config)
        self.telemetry = TelemetryCollector()
        self.sm        = StateMachine(self.config, self.telemetry)
        self.risk      = UltronRiskEngine(self.config)
        self.executor = ExecutionEngine(self.config)
        self.reset_lg = ResetLogic(self.config)
        self.state    = EngineState()
        self.ev_log   = EventLogger(self.state)    # [PATCH 4]
        self.candle_buffer: list[Candle] = []
        self._sweep_tracer = sweep_tracer           # Layer 0 sweep trace (optional)
        self.log = logging.getLogger("CRT.Orchestrator")

    # ── Public API ────────────────────────────────────────────

    def initialise_range(
        self, candles: list[Candle], htf_candle_id: str, session: str = "UNKNOWN"
    ) -> None:
        # [PATCH 4] Stamp candle indices if missing
        for i, c in enumerate(candles):
            if c.index == 0:
                c.index = i
        self.state.active_range = self.detector.detect_htf_range(candles, htf_candle_id, session)
        self.state.atr = self.detector.compute_atr(candles, self.config.atr_period)
        # [PATCH 1] Bounded buffer
        cap = self.config.atr_period * self.config.atr_buffer_multiplier
        self.candle_buffer = candles[-cap:]
        self.state.current_candle_index = len(candles) - 1

    def set_news(self, active: bool) -> None:
        self.risk.set_news_flag(active)

    def set_spread(self, bid: float, ask: float) -> None:
        self.risk.set_spread(bid, ask)

    def dump_event_log(self) -> list[dict]:
        """Return full typed event log as list of dicts (DynamoDB-ready)."""
        return self.ev_log.dump()

    def dump_telemetry(self) -> list[dict]:
        """Return all Phase-0 telemetry records. Call once at end-of-run."""
        return self.telemetry.flush()

    def process_candle(self, candle: Candle, htf_candle_id: str) -> dict:
        # [PATCH 4] Auto-assign candle index
        self.state.current_candle_index += 1
        candle.index = self.state.current_candle_index

        # [PATCH 1] Bounded ATR buffer
        cap = self.config.atr_period * self.config.atr_buffer_multiplier
        self.candle_buffer.append(candle)
        if len(self.candle_buffer) > cap:
            self.candle_buffer = self.candle_buffer[-cap:]

        self.state.atr = self.detector.compute_atr(self.candle_buffer, self.config.atr_period)

        # Keep EMA state warm every candle — ready when confirmation window opens
        self.state.update_emas(
            candle.close,
            fast=self.config.ema_fast,
            slow=self.config.ema_slow,
        )

        action = {
            "candle":       candle.timestamp,
            "candle_index": candle.index,
            "state":        self.state.current_state.name,
            "action":       "NONE",
        }

        # ── Reset check ───────────────────────────────────────
        should_reset, reset_reason = self.reset_lg.should_reset(self.state, candle, htf_candle_id)
        if should_reset:
            if self.state.active_trade and self.state.active_trade.status == "OPEN":
                self.log.warning("Active trade aborted on reset.")
                self.state.active_trade.status = "STOPPED"
                self.ev_log.record("TRADE_ABORTED", candle, reason="reset forced close")
            self.state.active_range = self.detector.detect_htf_range(
                self.candle_buffer[-self.config.atr_period:], htf_candle_id
            )
            self.sm.reset_to_range(self.state, reset_reason, candle, self.ev_log)
            action["action"] = "RESET"
            action["reason"] = reset_reason
            # ── [DEADLOCK FIX] Fall through to state machine so a sweep on the
            # freshly-seeded range can fire on THIS same candle. Without this,
            # every reset creates a 1-candle blind spot where valid sweeps are missed.
            # Do NOT return early — let the RANGE branch below run.

        # ── Active trade management ───────────────────────────
        if self.state.active_trade and self.state.active_trade.status in ("OPEN", "TP1"):
            result = self.executor.update_trade(self.state.active_trade, candle.close)
            if result in ("STOPPED", "TP2", "TP1"):
                self.ev_log.record(
                    f"TRADE_{result}", candle,
                    reason=f"Trade {self.state.active_trade.id} closed: {result}",
                    metadata={"pnl": self.state.active_trade.pnl},
                )
                self.sm.try_execution_to_resolution(
                    self.state, f"Trade closed: {result}", candle, self.ev_log
                )
                self.sm.reset_to_range(self.state, "Post-resolution reset", candle, self.ev_log)
                action["action"] = f"TRADE_{result}"
                action["state_after"] = self.state.current_state.name
                return action

        # ── State machine processing ──────────────────────────
        s = self.state.current_state

        if s == CRTState.RANGE:
            # ── Pending displacement TTL countdown ─────────────────────
            if self.state.pending_displacement_ttl > 0:
                self.state.pending_displacement_ttl -= 1
                if self.state.pending_displacement_ttl == 0:
                    self.log.debug(
                        f"Shadow memory expired (TTL exhausted) at idx={candle.index}"
                    )
                    self.state.pending_displacement_candle = None
                    self.state.pending_displacement_dir    = Direction.NONE

            sweep = self.detector.detect_sweep(
                candle, self.state.active_range,
                self.state.sweep_event, self.state.current_candle_index,  # [PATCH 2]
            )
            if sweep:
                # ── Shadow resume path: sweep matches pending displacement ──
                if (self.state.pending_displacement_candle is not None
                        and sweep.direction == self.state.pending_displacement_dir):
                    self.sm.try_range_to_shadow_pending(self.state, sweep, self.ev_log)
                    action["action"] = "SHADOW_SWEEP_DETECTED"
                    self.telemetry.on_candidate_opened(
                        f"CAND-{candle.index}", candle.index, candle.timestamp.isoformat(),
                        shadow=True,
                    )
                else:
                    # ── Normal sweep path ──────────────────────────────────
                    self.ev_log.record(
                        "SWEEP", candle,
                        direction=sweep.direction.value, price=sweep.price,
                        metadata={"double_confirmed": sweep.double_confirmed},
                    )
                    self.sm.try_range_to_sweep(self.state, sweep, self.ev_log)
                    action["action"] = "SWEEP_DETECTED"
                    # [TELEMETRY] Open candidate lifecycle record
                    self.telemetry.on_candidate_opened(
                        f"CAND-{candle.index}", candle.index, candle.timestamp.isoformat()
                    )
                    # ── Layer 0: Sweep Trace Packet ────────────────────────
                    if self._sweep_tracer is not None and self.state.active_range is not None:
                        rng = self.state.active_range
                        _cross_high = candle.high > rng.h_ref and candle.close < rng.h_ref
                        _cross_low  = candle.low  < rng.l_ref and candle.close > rng.l_ref
                        _ref        = rng.h_ref if _cross_high else rng.l_ref
                        _pen_pts    = abs(sweep.price - _ref)
                        _pen_atr    = _pen_pts / self.state.atr if self.state.atr > 0 else 0.0
                        self._sweep_tracer.emit(
                            candle_index      = candle.index,
                            range_high        = rng.h_ref,
                            range_low         = rng.l_ref,
                            candle_open       = candle.open,
                            candle_high       = candle.high,
                            candle_low        = candle.low,
                            candle_close      = candle.close,
                            cross_high        = _cross_high,
                            cross_low         = _cross_low,
                            penetration_points = _pen_pts,
                            penetration_atr   = _pen_atr,
                            decision          = "SWEEP_HIGH" if _cross_high else "SWEEP_LOW",
                            state_before      = "RANGE",
                            state_after       = "SWEEP",
                            expired           = False,
                        )

        elif s == CRTState.SHADOW_PENDING:
            # ── SHADOW_LEAK integrity check ────────────────────────────────
            _stored_sweep = self.state.sweep_event
            _shadow_ok = (
                _stored_sweep is not None
                and _stored_sweep.direction == self.state.pending_displacement_dir
            )
            if not _shadow_ok:
                emit_integrity_event(
                    "SHADOW_LEAK", "ERROR", "crt_engine",
                    {
                        "candidate_id": f"CAND-{candle.index}",
                        "pending_dir":  self.state.pending_displacement_dir.value
                                        if self.state.pending_displacement_dir else "NONE",
                        "sweep_dir":    _stored_sweep.direction.value
                                        if _stored_sweep else "NONE",
                        "candle_index": candle.index,
                    },
                )
                self.state.pending_displacement_ttl    = 0
                self.state.pending_displacement_candle = None
                self.state.pending_displacement_dir    = Direction.NONE
                self.sm.reset_to_range(
                    self.state, "SHADOW_LEAK: sweep invalid or direction mismatch",
                    candle, self.ev_log,
                )
                action["action"] = "SHADOW_LEAK"
            else:
                # Valid resume: collapse SHADOW_PENDING → SWEEP → EXPANSION
                _pending_formed = self.state.pending_displacement_formed_idx
                _pending_src    = self.state.pending_displacement_source_htf
                if self.sm.try_shadow_pending_to_expansion(self.state, candle, self.ev_log):
                    action["action"] = "SHADOW_EXPANSION_CONFIRMED"
                    action["shadow_source_htf"]      = _pending_src
                    action["shadow_formed_idx"]      = _pending_formed
                    self.state._came_from_shadow     = True  # persists until reset
                    # Phase 4b: compute HTF alignment BEFORE clearing pending_displacement_dir
                    # True = pending direction still aligned with HTF range midpoint (discount/premium ok)
                    # False = direction conflict; None = no range data available
                    _rng = self.state.active_range
                    _pdir = self.state.pending_displacement_dir
                    if _rng is not None and _pdir != Direction.NONE:
                        _htf_mid = (_rng.h_ref + _rng.l_ref) / 2.0
                        self.state._shadow_htf_alignment = (
                            (_pdir == Direction.LONG  and candle.close < _htf_mid)
                            or (_pdir == Direction.SHORT and candle.close > _htf_mid)
                        )
                    else:
                        self.state._shadow_htf_alignment = None
                    # Clear pending memory now that it has been consumed
                    self.state.pending_displacement_ttl            = 0
                    self.state.pending_displacement_candle         = None
                    self.state.pending_displacement_dir            = Direction.NONE
                    self.state.pending_displacement_source_htf     = ""
                    self.state.pending_displacement_formed_idx     = 0
                    self.state.pending_displacement_age_at_reset   = 0
                    self.state.pending_displacement_reason_created = ""

        elif s == CRTState.SWEEP:
            # [PATCH 2] Age check happens inside try_sweep_to_displacement
            if self.sm.try_sweep_to_displacement(self.state, candle, self.ev_log):
                action["action"] = "DISPLACEMENT_CONFIRMED"
            elif (
                self.state.sweep_event and
                (self.state.current_candle_index - self.state.sweep_event.candle_index)
                > self.config.max_sweep_age_candles
            ):
                # ── Layer 0: Sweep Trace Packet (expired) — capture BEFORE reset ──
                if self._sweep_tracer is not None and self.state.active_range is not None:
                    rng = self.state.active_range
                    _cross_high = candle.high > rng.h_ref and candle.close < rng.h_ref
                    _cross_low  = candle.low  < rng.l_ref and candle.close > rng.l_ref
                    _ref        = rng.h_ref if _cross_high else rng.l_ref
                    _pen_pts    = abs(candle.high - _ref) if _cross_high else abs(candle.low - _ref)
                    _pen_atr    = _pen_pts / self.state.atr if self.state.atr > 0 else 0.0
                    self._sweep_tracer.emit(
                        candle_index      = candle.index,
                        range_high        = rng.h_ref,
                        range_low         = rng.l_ref,
                        candle_open       = candle.open,
                        candle_high       = candle.high,
                        candle_low        = candle.low,
                        candle_close      = candle.close,
                        cross_high        = _cross_high,
                        cross_low         = _cross_low,
                        penetration_points = _pen_pts,
                        penetration_atr   = _pen_atr,
                        decision          = "NONE",
                        state_before      = "SWEEP",
                        state_after       = "RANGE",
                        expired           = True,
                    )
                self.sm.reset_to_range(self.state, "Sweep expired", candle, self.ev_log)
                action["action"] = "SWEEP_EXPIRED"

        elif s == CRTState.DISPLACEMENT:
            if self.sm.try_displacement_to_expansion(self.state, candle, self.ev_log):
                action["action"] = "EXPANSION_CONFIRMED"
        

        elif s == CRTState.EXPANSION:
            self.log.debug(f"EXPANSION STATE ACTIVE | idx={candle.index}")

            # ── RC-Closure: RETEST has priority=4 > EXPIRED priority=3.
            # Try retest FIRST so a qualifying retest always wins over TTL expiry
            # on the same candle. If retest fires, we return before the TTL check runs.
            if self.sm.try_expansion_to_retest(self.state, candle, self.state.atr, self.ev_log):
                action["action"] = "RETEST_CONFIRMED"
                # Begin soft confirmation window (replaces binary 5-candle gate)
                self.state.evaluating_soft_conf = True
                self.state.soft_conf_candles    = 0
                self.ev_log.record(
                    "BEGIN_SOFT_CONF", candle,
                    reason="Retest locked — evaluating soft confirmation manifold"
                )

            else:
                # ── Phase 3b: Expansion TTL guard ─────────────────────────────────
                # Runs only when retest did NOT fire on this candle (RC-Closure).
                _max_c = self.config.max_expansion_age_candles
                _max_h = self.config.max_expansion_age_hours
                _exp_age_c = candle.index - self.state._expansion_entry_idx

                # Hour-based age: prefer actual timestamp delta; fall back to M15 approximation
                if self.state._expansion_entry_ts is not None:
                    _age_h = (candle.timestamp - self.state._expansion_entry_ts).total_seconds() / 3600.0
                else:
                    _age_h = _exp_age_c * 15.0 / 60.0   # M15 approximation

                _ttl_exceeded = (
                    (_max_c > 0 and _exp_age_c > _max_c)
                    or (_max_h > 0 and _age_h > _max_h)
                )

                if _ttl_exceeded:
                    # ── would_trade_if_alive: structural quality check on displacement candle ──
                    _dc = self.state.displacement_candle
                    _would_trade = False
                    _body_ratio  = 0.0
                    if _dc is not None:
                        _rng2 = _dc.high - _dc.low
                        _body_ratio  = abs(_dc.close - _dc.open) / _rng2 if _rng2 > 0 else 0.0
                        _would_trade = _body_ratio >= self.config.body_ratio_min

                    # freshness_ratio = age/ttl (0.20=fresh, 0.80=aging, >1.0=stale)
                    _freshness_ratio = round(_exp_age_c / _max_c, 3) if _max_c > 0 else 0.0
                    _age_pct         = round(_freshness_ratio * 100.0, 1)  # % form for on_expansion_ended

                    # retest_distance: how far was price from triggering a retest at expiry?
                    # depth proxy = max retrace seen during this episode (from telemetry tracker)
                    _current_depth_abs   = self.telemetry._expansion_max_depth
                    _retest_ceiling      = self.config.retest_depth_max   # config fraction ceiling
                    _retest_distance_abs = max(0.0, _retest_ceiling - _current_depth_abs)
                    _retest_depth_pct    = (
                        round(_current_depth_abs / _retest_ceiling, 3)
                        if _retest_ceiling > 0 else 0.0
                    )

                    emit_integrity_event("EXPANSION_EXPIRED", "WARNING", "crt_engine", {
                        "candidate_id":          f"CAND-{self.state._expansion_entry_idx}",
                        "expansion_age_candles": _exp_age_c,
                        "expansion_age_hours":   round(_age_h, 1),
                        "source":                "shadow" if self.state._came_from_shadow else "normal",
                        "shadow_used":           self.state._came_from_shadow,
                        "would_trade_if_alive":  _would_trade,
                        "freshness_ratio":       _freshness_ratio,     # RC5: 0.20=fresh, 1.20=stale
                        "age_pct_of_threshold":  _age_pct,             # e.g. 400/500 → 80.0%
                        "retest_distance_abs":   round(_retest_distance_abs, 6),  # RC5
                        "retest_depth_pct":      _retest_depth_pct,    # RC5: 0-1+, >1 = would have triggered
                        "score":                 round(_body_ratio, 4),
                        "candle_index":          candle.index,
                    })
                    self.telemetry.on_expansion_ended(
                        candle.index, "EXPIRED",
                        end_ts=candle.timestamp,
                        shadow_used=self.state._came_from_shadow,
                        candidate_age_at_entry=(
                            self.state._expansion_entry_idx - self.state._displacement_entry_idx
                        ),
                        age_pct_of_threshold=_age_pct,
                    )
                    self.sm._transition(
                        self.state, CRTState.EXPIRED, "expansion_ttl_exceeded", candle, self.ev_log
                    )
                    action["action"] = "EXPANSION_EXPIRED"

        # ── Phase 3b: EXPIRED branch ──────────────────────────────────────────
        # One-candle soft archive state: the episode label is committed, now reset to RANGE.
        elif s == CRTState.EXPIRED:
            self.sm.reset_to_range(self.state, "expansion_ttl_exceeded", candle, self.ev_log)
            action["action"] = "EXPANSION_TTL_RESET"

        # ── SOFT CONFIRMATION MANIFOLD (replaces binary awaiting_confirmation) ──
        elif self.state.evaluating_soft_conf:

            self.state.soft_conf_candles += 1
            # Update EMA state every candle (used by compute_soft_confirmation)
            self.state.update_emas(
                candle.close,
                fast=self.config.ema_fast,
                slow=self.config.ema_slow,
            )

            # ── Evaluate geometric fusion score on this candle ──
            approved, reason, final_S = self.risk.approve_with_soft_conf(
                self.state, candle
            )

            # ── Phase 4b: Shadow age-decay gate ──────────────────────────────
            # Applies only to shadow candidates (state._came_from_shadow == True).
            # effective_S = final_S × exp(−λ × candidate_age_at_entry)
            # If effective_S < tier_2_threshold, override approval to rejected.
            _effective_S        = final_S
            _freshness_mult     = 1.0
            _shadow_ctx: dict   = {}
            _shadow_disp_br     = 0.0
            if self.state._came_from_shadow:
                _cand_age = (
                    self.state._expansion_entry_idx - self.state._displacement_entry_idx
                )
                _lambda = self.config.shadow_age_penalty_lambda
                _norm   = self.config.shadow_age_norm_candles  # Phase 4b Variant B
                if _lambda > 0.0:
                    # Variant B (normalised) when norm > 0; Variant A (raw) when norm == 0.
                    # Normalised: λ=1.0 means "at max shadow age (norm candles), score → 1/e".
                    _age_input      = (_cand_age / _norm) if _norm > 0 else _cand_age
                    _freshness_mult = math.exp(-_lambda * _age_input)
                    _effective_S    = final_S * _freshness_mult
                    # Override: if decay pushed score below threshold, un-approve
                    if approved and _effective_S < self.config.tier_2_threshold:
                        approved = False
                        reason   = RejectReason.LOW_SCORE
                _shadow_ctx = {
                    "age":                  _cand_age,
                    "age_normalised":       round(_cand_age / _norm, 3) if _norm > 0 else None,
                    "htf_alignment":        self.state._shadow_htf_alignment,
                    "freshness_multiplier": round(_freshness_mult, 4),
                    "score_before":         round(final_S, 4),
                    "score_after":          round(_effective_S, 4),
                    "lambda":               _lambda,
                    "norm_candles":         _norm,
                    "variant":              "B_normalised" if _norm > 0 else "A_raw",
                }
                # Pending displacement body_ratio (stored at expansion entry for Phase 5 label)
                _pdc = self.state.pending_displacement_candle   # already cleared; use cached value
                # Note: pending_displacement_candle is None here (cleared at SHADOW_EXPANSION_CONFIRMED).
                # shadow_displacement_br must be computed at expansion entry if needed for Phase 5.
                # For Phase 4b, we log 0.0; Phase 5 can add a _shadow_displacement_br field to EngineState.
                _shadow_disp_br = 0.0
            # ─────────────────────────────────────────────────────────────────

            # [TELEMETRY] Track S-score and decision gap every soft-conf evaluation
            self.telemetry.on_candidate_score(_effective_S)
            self.telemetry.on_decision_distance(
                candle_index=candle.index,
                score_actual=_effective_S,
                score_threshold=self.config.tier_2_threshold,
                accepted=approved,
                rejection_reason=(
                    reason.value if reason else ("APPROVED" if approved else "UNKNOWN")
                ),
                soft_conf_candle_num=self.state.soft_conf_candles,
            )

            if approved:
                self.state.evaluating_soft_conf = False

                # ── Range position filter (kept from binary gate) ──
                rng = self.state.active_range
                entry_price = self.state.retest_candle.close
                mid = (rng.h_ref + rng.l_ref) / 2
                if self.state.direction == Direction.LONG and entry_price > mid:
                    self.ev_log.record("FILTER_REJECTED", candle, reason="Not in discount zone")
                    self.sm.reset_to_range(self.state, "Not in discount zone", candle, self.ev_log)
                    action["action"] = "FILTER_REJECTED"

                elif self.state.direction == Direction.SHORT and entry_price < mid:
                    self.ev_log.record("FILTER_REJECTED", candle, reason="Not in premium zone")
                    self.sm.reset_to_range(self.state, "Not in premium zone", candle, self.ev_log)
                    action["action"] = "FILTER_REJECTED"

                else:
                    # ── Override final score with fusion S for downstream sizing ──
                    if self.state.risk_score:
                        self.state.risk_score.score_override = final_S

                    # ── Session filter (mirrors engine_runner.allowed_sessions) ──
                    # Skip trade open if candle's session is not in the allowed set.
                    # Live mode would reject anyway via adapter_engine; doing it here
                    # avoids burning a CRT setup on a session that won't trade.
                    _ts_time = candle.timestamp.time()
                    _sess_name = "OFF_SESSION"
                    for _name, (_start, _end) in self.config.session_windows.items():
                        if _start <= _ts_time <= _end:
                            _sess_name = _name
                            break
                    if _sess_name not in self.config.allowed_sessions:
                        self.ev_log.record(
                            "FILTER_REJECTED", candle,
                            reason=f"off_session:{_sess_name}",
                            metadata={"session_name": _sess_name},
                        )
                        self.sm.reset_to_range(
                            self.state, "off_session_filter",
                            candle, self.ev_log,
                        )
                        action["action"] = "FILTER_REJECTED"
                        action["state_after"] = self.state.current_state.name
                        return action

                    # ── Phase 4b: shadow_advisory_only hard block ─────────────
                    # Shadow still tracks telemetry; EXECUTION is suppressed.
                    if self.config.shadow_advisory_only and self.state._came_from_shadow:
                        emit_integrity_event("SHADOW_ADVISORY_BLOCK", "INFO", "crt_engine", {
                            "candidate_id":         f"CAND-{self.state._expansion_entry_idx}",
                            "score_before":         round(final_S, 4),
                            "score_after":          round(_effective_S, 4),
                            "freshness_multiplier": round(_freshness_mult, 4),
                            "htf_alignment":        self.state._shadow_htf_alignment,
                            "candle_index":         candle.index,
                        })
                        self.sm.reset_to_range(
                            self.state, "shadow_advisory_only", candle, self.ev_log
                        )
                        action["action"] = "SHADOW_ADVISORY_BLOCK"
                        return action
                    # ─────────────────────────────────────────────────────────

                    self.sm.try_retest_to_execution(self.state, candle, self.ev_log)
                    trade = self.executor.build_trade(self.state, self.risk)

                    if trade:
                        self.executor.open_trade(trade, candle.timestamp)
                        self.state.active_trade = trade
                        self.ev_log.record(
                            "TRADE_OPENED", candle,
                            direction=trade.direction.value,
                            price=trade.entry_price,
                            metadata={
                                "id": trade.id,
                                "session_name": _sess_name,
                                "S_score": _effective_S,   # Phase 4b: log penalised score
                                "sl": trade.sl_price,
                                "tp1": trade.tp1_price,
                                "tp2": trade.tp2_price,
                                "risk_pct": trade.risk_pct,
                            },
                        )
                        action["action"]       = "TRADE_OPENED"
                        action["trade_id"]     = trade.id
                        action["risk_pct"]     = trade.risk_pct
                        # Embed live engine state so the backtest never needs to
                        # reach back into a static batch array for audit columns.
                        action["live_metrics"] = self.get_live_metrics()
                        # [TELEMETRY] Close candidate as ACCEPTED — Phase 4b: include shadow_context
                        self.telemetry.on_candidate_accepted(
                            candle.index,
                            score_at_approval=_effective_S,
                            shadow_context=_shadow_ctx if self.state._came_from_shadow else {},
                            shadow_displacement_br=_shadow_disp_br,
                        )

                        # ── Phase 3b: Temporal integrity events ───────────────────
                        _struct_age = candle.index - self.state._expansion_entry_idx

                        # TEMPORAL_PARADOX (CRITICAL): last-resort guard — trade opened
                        # after TTL should have expired. If this fires, the TTL check
                        # has a gap (e.g. RETEST priority override let a stale trade through).
                        if (self.config.max_expansion_age_candles > 0
                                and _struct_age > self.config.max_expansion_age_candles):
                            emit_integrity_event(
                                "TEMPORAL_PARADOX", "CRITICAL", "crt_engine",
                                {
                                    "candidate_id":  f"CAND-{self.state._expansion_entry_idx}",
                                    "structure_age": _struct_age,
                                    "max_allowed":   self.config.max_expansion_age_candles,
                                    "shadow_used":   self.state._came_from_shadow,
                                    "candle_index":  candle.index,
                                },
                            )
                            # Note: trade is NOT cancelled here — RETEST > EXPIRED by design.
                            # TEMPORAL_PARADOX is informational: it shows TTL was overridden
                            # by a valid retest. Investigate if count > 0 after production run.

                        # TEMPORAL_STALE_WIN (WARNING): trade opened from expansion older than
                        # P95 (342 candles). Trade still executes — this labels it for training.
                        _warn_age = self.config.expansion_age_warn_candles
                        if _warn_age > 0 and _struct_age > _warn_age:
                            emit_integrity_event(
                                "TEMPORAL_STALE_WIN", "WARNING", "crt_engine",
                                {
                                    "candidate_id":   f"CAND-{self.state._expansion_entry_idx}",
                                    "structure_age":  _struct_age,
                                    "warn_threshold": _warn_age,
                                    "shadow_used":    self.state._came_from_shadow,
                                    "candle_index":   candle.index,
                                },
                            )

            elif self.state.soft_conf_candles >= self.config.soft_conf_max_candles:
                # Evaluation window expired — no qualifying manifold found
                self.state.evaluating_soft_conf = False
                self.ev_log.record(
                    "CONFIRMATION_FAILED", candle,
                    reason=f"Soft confirmation not met within {self.config.soft_conf_max_candles} candles"
                )
                self.sm.reset_to_range(
                    self.state, "Soft confirmation timeout", candle, self.ev_log
                )
                action["action"] = "CONFIRMATION_FAILED"

            else:
                # Still within window — continue evaluating
                action["action"] = "EVALUATING_SOFT_CONF"
            

        action["state_after"] = self.state.current_state.name
        return action

    # ── Live metrics API ──────────────────────────────────────────

    def get_live_metrics(self) -> dict:
        """
        Return the engine's current live indicator state for execution auditing.

        These values are DISTINCT from Universe-A (FeaturePipeline) canonical
        features and serve a different purpose:

          live_atr        – raw price-unit ATR used to size SL/TP at entry.
                            Cross-checking this against sl_price and tp1_price
                            in the CSV immediately verifies position sizing.
          live_ema_fast/slow – EMA-2 / EMA-5 from the soft-confirmation manifold.
                            These are the *actual momentum signals* that drove the
                            RETEST → EXECUTION approval, not the EMA-9/EMA-21
                            reported in the canonical feature vector.
          cached_*        – geometry features computed by StateMachine at RETEST.
                            These are the exact feature values that passed
                            UltronRiskEngine.approve_with_soft_conf() — i.e. the
                            decision inputs for the trade that was just opened.

        Called immediately after TRADE_OPENED so state reflects entry-candle values.
        Safe to call at any time; returns zeroed/empty values if state is pre-init.
        """
        cf: dict = self.state.cached_features or {}
        return {
            # ── Universe-B raw execution indicators ──────────────────────────
            "live_atr":              self.state.atr,
            "live_ema_fast":         self.state.ema_fast_val,
            "live_ema_slow":         self.state.ema_slow_val,
            # ── Decision features (computed at RETEST, not at TRADE_OPENED) ──
            "cached_retest_depth":   float(cf.get("retest_depth",  0.0)),
            "cached_body_ratio":     float(cf.get("body_ratio",    0.0)),
            "cached_disp_strength":  float(cf.get("disp_strength", 0.0)),
            "cached_session":        str(cf.get("session",         "")),
            "cached_double_sweep":   bool(cf.get("double_sweep",   False)),
        }


def state_risk_score(state: EngineState) -> Optional[float]:
    return state.risk_score.final if state.risk_score else None


# ─────────────────────────────────────────────────────────────────
# PHASE A — CRT TRANSITION PATH VIEW LAYER
# View type + function that reads existing event_log (no new storage on EngineState).
# Architecture invariant: CRT never knows strategy outcome.
#                         StrategyOrchestrator never mutates CRT state.
# ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CRTTransitionEvent:
    """Typed, immutable VIEW of a single CRT state transition.

    Constructed on demand from event_log — never stored on EngineState.
    `feature_snapshot` is a MappingProxyType (copy-then-freeze) — downstream
    code that tries to write to it gets a TypeError, enforcing the invariant
    that StrategyOrchestrator MUST NEVER mutate CRT state.
    """
    candle_idx:       int
    timestamp:        datetime
    from_state:       str                 # e.g. "SWEEP"
    to_state:         str                 # e.g. "DISPLACEMENT"
    trigger_reason:   str                 # copied from EngineEvent.reason
    sweep_type:       Optional[str]       # from metadata["sweep_type"]
    disp_strength:    Optional[float]     # from metadata["disp_strength"]
    atr:              float               # from metadata["atr"]
    feature_snapshot: Mapping[str, Any]   # READ-ONLY — MappingProxyType at construction


def recent_transition_path(
    state: EngineState,
    n: int = 16,
) -> List[CRTTransitionEvent]:
    """Build a typed, windowed view of the last *n* state transitions.

    Reads from state.event_log (canonical truth) — no duplicate storage.
    Returns up to *n* `CRTTransitionEvent` items (fewer if the run has not
    yet produced that many transitions).

    Usage:
        path = recent_transition_path(engine.state)
        # Inject into features before orchestrator call:
        features["_transition_path"] = path

    The key ``"_transition_path"`` is the canonical dict key everywhere —
    never use ``"_transition_history"``.
    """
    transitions = [
        ev for ev in state.event_log
        if ev.event == "STATE_TRANSITION"
    ][-n:]

    result: List[CRTTransitionEvent] = []
    for ev in transitions:
        meta = ev.metadata or {}
        result.append(CRTTransitionEvent(
            candle_idx      = ev.candle_index,
            timestamp       = ev.timestamp,
            from_state      = ev.state_from or "",
            to_state        = ev.state_to or "",
            trigger_reason  = ev.reason or "",
            sweep_type      = meta.get("sweep_type"),
            disp_strength   = meta.get("disp_strength"),
            atr             = float(meta.get("atr", state.atr)),
            # dict() copy THEN MappingProxyType:
            # - dict() prevents ev.metadata["features"]["x"]=y from silently
            #   reflecting through the proxy after construction.
            # - MappingProxyType raises TypeError on any write attempt.
            feature_snapshot = MappingProxyType(dict(meta.get("features", {}))),
        ))
    return result
