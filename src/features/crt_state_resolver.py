"""
CRT State Resolver — Layer 5 of the semantic pipeline (2026-07-24).

PURPOSE
-------
Resolve the 9 CRT state machine states from DECLARED FEATURE STATES, using a
config-driven predicate system. Given a per-bar feature vector (canonical 39-dim),
determine which CRT state the bar belongs to.

This is a MARKET REALITY layer — it runs alongside the CRT engine, not replacing it.
The CRT engine (crt_engine_v2.py) remains the execution authority for live trading.

DESIGN
------
1. Reads ``configs/formulas/market_crt_states.yaml`` for state definitions,
   feature references, valid transitions, and tunable thresholds.
2. Uses ``FeatureStateEncoder`` (feature_states.py) to convert raw feature values
   into declared semantic states from ``configs/formulas/market_ontology.yaml``.
3. Evaluates state predicates per-bar: a bar matches a CRT state if, for every
   feature in the state's ``when`` block, the feature's current state is in the
   allowed list (AND across features, OR within a state list).
4. First-match precedence: states are evaluated in the order defined in config
   (most specific first). RANGE is the default/ground state.
5. Memory states (SHADOW_PENDING, EXPIRED, RESOLUTION) cannot be resolved from a
   single bar's features — they require the resolver to maintain a state machine
   that tracks the engine's progression across the valid_transitions graph.

USAGE
-----
    resolver = CRTStateResolver()
    state = resolver.resolve(feature_vector, timestamp=ts)  # returns CRT state name
    counts = resolver.counts                  # per-state bar count

LIFECYCLE (HTF / gap RESET → RANGE)
-----------------------------------
Mirrors the engine's narrative termination:

  * **HTF window change** (every ``lifecycle.htf_candles_per_range`` bars, or
    when an explicit ``htf_id`` changes) → force RANGE, **except** when current
    state is EXPANSION/RETEST (engine protects active setups).
  * **Session gap** (timestamp delta > ``lifecycle.gap_reset_minutes``) → always
    force RANGE (including EXPANSION).
  * **HTF reset from DISPLACEMENT** may set ``pending_displacement_active``
    (shadow memory) when ``shadow_on_htf_displacement_reset`` is true.

Optional ``force_reset=True`` applies an unconditional RANGE reset (exact event
replay / external gap signal).

THRESHOLD TUNING
----------------
The ``thresholds`` block in market_crt_states.yaml can be tuned to adjust which
bars match which CRT states. This is how you make the resolver's counts match
real market data:
  - Increase body_ratio_min → fewer DISPLACEMENT matches
  - Increase expansion_atr_min_distance → fewer EXPANSION matches
  - Decrease max_sweep_age_candles → fewer stale SWEEP matches

B1 SWEEP GEOMETRY (BEHAVIOR_CHANGE_AUTHORIZED 2026-08-05)
---------------------------------------------------------
``thresholds.sweep_geometry`` selects the RANGE→SWEEP founding detector:

  * ``htf_range`` (default) — engine ``RangeDetector.detect_sweep`` geometry:
    compare bar high/low/close against a frozen HTF active range
    (h_ref/l_ref = max high / min low of the range seed window). Research-shadow
    only; does not alter the production CRT engine or the 39-dim pipeline vector.
  * ``pipeline_swing`` — legacy: rely on FeaturePipeline ``liquidity_sweep``
    (last-swing refs). Kept for A/B regression against pre-B1 shadow behaviour.

Seed pre-warmup OHLC via ``seed_ohlc`` so the first active range matches the
engine's ``initialise_range(htf.seed_candles())`` path after BacktestRunner warmup.
"""

from __future__ import annotations

import dataclasses
import math
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import yaml

from features.feature_schema import CANONICAL_FEATURES
from features.feature_states import FeatureStateEncoder
from features.registry import load_ontology

logger = logging.getLogger("CRT_STATE_RESOLVER")

# ── Config path (resolved relative to project root) ──────────────
_CRT_STATES_CONFIG = Path("configs/formulas/market_crt_states.yaml")


# ── Exception types ──────────────────────────────────────────────

class CRTStateResolverError(Exception):
    """Base exception for resolver errors."""


class ConfigLoadError(CRTStateResolverError):
    """Failed to load or parse the CRT states config."""


class PredicateValidationError(CRTStateResolverError):
    """A predicate references an unknown feature or state."""


class TransitionError(CRTStateResolverError):
    """An illegal state transition was attempted."""


# ── Data structures ──────────────────────────────────────────────

@dataclass
class CRTStateMemory:
    """Stateful memory carried between bar resolutions.

    This mirrors EngineState from crt_engine_v2.py but uses only the subset
    needed for CRT state resolution — no trade state, no risk scores.
    """
    current_state: str = "RANGE"
    sweep_candle_index: int = -1           # last sweep candle index
    displacement_candle_index: int = -1    # last displacement candle index
    displacement_candle_close: float = 0.0  # displacement close price
    displacement_direction: int = 0        # +1 LONG / -1 SHORT at DISPLACEMENT entry
    retest_candle_index: int = -1          # last retest candle index
    expansion_entry_index: int = -1        # candle index when EXPANSION was entered
    expansion_entry_ts: Optional[Any] = None  # timestamp when EXPANSION was entered
    pending_displacement_active: bool = False  # cross-window shadow memory
    pending_displacement_formed_idx: int = -1
    pending_displacement_dir: str = "NONE"
    pending_displacement_ttl: int = 0      # bars remaining for shadow memory
    pending_displacement_created_idx: int = -1  # skip TTL tick on create bar (engine)
    trade_active: bool = False             # EXECUTION → RESOLUTION tracking
    candle_index: int = 0
    # ── Lifecycle memory (HTF / gap) ────────────────────────────
    active_htf_id: str = ""                # last seen HTF window id
    htf_bars_in_window: int = 0            # bars pushed into current HTF buffer
    last_timestamp: Optional[Any] = None   # prior bar ts for gap detection
    last_reset_reason: str = ""            # most recent RESET reason (debug)
    htf_reset_count: int = 0
    gap_reset_count: int = 0
    forced_reset_count: int = 0
    # ── B1 HTF-range sweep memory (engine active_range + candle_buffer) ──
    # h_ref/l_ref frozen between resets; buffer holds recent OHLC for rebuild.
    range_h_ref: float = 0.0
    range_l_ref: float = 0.0
    range_ready: bool = False
    # Engine: active_range.htf_candle_id — frozen WITH the range, NOT advanced
    # during protected EXPANSION/RETEST. Post-protect, stale range_htf_id forces
    # RESET even if active_htf_id already caught up (ResetLogic.should_reset).
    range_htf_id: str = ""
    ohlc_buffer: list = field(default_factory=list)  # list[tuple[o,h,l,c]]
    # Warmup HTFBuilder-equivalent: non-overlapping completed windows for seed.
    seed_window_buf: list = field(default_factory=list)
    last_completed_seed: list = field(default_factory=list)
    last_completed_seed_htf_id: str = ""


# ── Resolver ─────────────────────────────────────────────────────

class CRTStateResolver:
    """Config-driven CRT state resolver.

    Evaluates per-bar feature states against CRC state definitions and
    maintains a lightweight state machine for memory-dependent states.

    Thread-safe after construction if used with external locking (the
    internal ``_memory`` is mutated on each call to ``resolve``).
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        ontology: dict | None = None,
    ):
        self._config_path = Path(config_path) if config_path else _CRT_STATES_CONFIG
        self._config = self._load_config()
        self._encoder = FeatureStateEncoder(ontology or load_ontology())
        self._validate_predicates()
        self._memory = CRTStateMemory()
        self._counts: dict[str, int] = {}
        self._transition_count: int = 0
        self._lifecycle = self._load_lifecycle()
        # B1: SWEEP detector geometry (research shadow only — not production engine)
        thr0 = self._config.get("thresholds", {})
        geom = str(thr0.get("sweep_geometry", "htf_range")).strip().lower()
        if geom not in ("htf_range", "pipeline_swing"):
            raise ConfigLoadError(
                f"thresholds.sweep_geometry must be 'htf_range' or 'pipeline_swing', got {geom!r}"
            )
        self._sweep_geometry = geom
        # Engine CRTConfig.atr_period — used to rebuild active_range on HTF/gap reset
        # (crt_engine_v2.process_candle:2656-2658 uses candle_buffer[-atr_period:]).
        self._range_atr_period = int(thr0.get("range_atr_period", 14))
        if self._range_atr_period < 1:
            raise ConfigLoadError("thresholds.range_atr_period must be >= 1")
        # Cap OHLC buffer (engine uses atr_period * atr_buffer_multiplier; 14*3=42)
        self._ohlc_buffer_cap = max(self._range_atr_period * 3, 48)

    # ── public API ───────────────────────────────────────────────

    @property
    def counts(self) -> dict[str, int]:
        """Per-state bar count (cumulative since construction or last reset)."""
        return dict(self._counts)

    @property
    def memory(self) -> CRTStateMemory:
        """Current state memory (read-only snapshot)."""
        return CRTStateMemory(**{f.name: getattr(self._memory, f.name)
                                 for f in dataclasses.fields(CRTStateMemory)})

    @property
    def transition_count(self) -> int:
        """Number of state transitions observed."""
        return self._transition_count

    @property
    def lifecycle_stats(self) -> dict[str, int]:
        """HTF / gap / forced reset counters since construction or last memory reset."""
        return {
            "htf_reset_count": self._memory.htf_reset_count,
            "gap_reset_count": self._memory.gap_reset_count,
            "forced_reset_count": self._memory.forced_reset_count,
            "last_reset_reason": self._memory.last_reset_reason,
        }

    def reset_counts(self) -> None:
        """Reset per-state counts without clearing memory."""
        self._counts = {}

    def reset_memory(self) -> None:
        """Reset state memory to initial (RANGE, no pending)."""
        self._memory = CRTStateMemory()
        self._transition_count = 0

    def seed_ohlc(
        self,
        open_: float,
        high: float,
        low: float,
        close: float,
        *,
        htf_id: Optional[str] = None,
    ) -> None:
        """Push one pre-resolution OHLC bar into HTF-range memory (no state emit).

        Mirrors BacktestRunner warmup: HTFBuilder accumulates candles before
        ``initialise_range``. Call for every raw bar *before* the first
        ``resolve`` so ``active_range`` matches the engine's seed window.

        B1b: during warmup the engine does **not** rebuild active_range on HTF
        change — only ``initialise_range(seed_candles)`` after warmup. We mirror
        HTFBuilder non-overlapping windows and freeze only in
        ``finalize_seed_range``.

        Research-shadow only. No-op for ``sweep_geometry=pipeline_swing``.
        """
        if self._sweep_geometry != "htf_range":
            return
        o, h, l, c = float(open_), float(high), float(low), float(close)
        self._push_bar_ohlc(o, h, l, c)
        # HTFBuilder.push equivalent (non-overlapping completed windows)
        cph = int(self._lifecycle["htf_candles_per_range"])
        if cph < 1:
            cph = 1
        self._memory.seed_window_buf.append((o, h, l, c))
        if htf_id is not None:
            self._memory.active_htf_id = str(htf_id)
        if len(self._memory.seed_window_buf) >= cph:
            self._memory.last_completed_seed = self._memory.seed_window_buf[:cph]
            self._memory.last_completed_seed_htf_id = (
                str(htf_id) if htf_id is not None else self._memory.active_htf_id
            )
            # Drop completed window (HTFBuilder clears buffer on complete)
            self._memory.seed_window_buf = self._memory.seed_window_buf[cph:]

    def finalize_seed_range(self) -> None:
        """After ``seed_ohlc`` stream, set active_range like engine ``initialise_range``.

        Uses the last **completed** HTFBuilder window (``seed_candles``), NOT
        ``buffer[-htf_candles:]`` of the continuous stream (those can include an
        incomplete open window — a pre-B1b seed bug that desynced h_ref/l_ref).
        """
        if self._sweep_geometry != "htf_range":
            return
        window = self._memory.last_completed_seed
        if not window:
            # Fallback: incomplete stream — last cph of continuous buffer
            cph = int(self._lifecycle["htf_candles_per_range"])
            self._rebuild_active_range(
                cph if cph > 0 else self._range_atr_period,
                htf_id=self._memory.active_htf_id or "",
            )
            return
        highs = [b[1] for b in window]
        lows = [b[2] for b in window]
        self._memory.range_h_ref = max(highs)
        self._memory.range_l_ref = min(lows)
        self._memory.range_ready = self._memory.range_h_ref > self._memory.range_l_ref
        self._memory.range_htf_id = self._memory.last_completed_seed_htf_id or (
            self._memory.active_htf_id or ""
        )

    def resolve(
        self,
        features: Mapping[str, float] | Sequence[float],
        timestamp: Optional[Any] = None,
        *,
        htf_id: Optional[str] = None,
        force_reset: bool = False,
        reset_reason: Optional[str] = None,
        engine_reset: bool = False,
        engine_state_to: Optional[str] = None,
    ) -> str:
        """Resolve the CRT state for one bar.

        Args:
            features: Either a canonical 39-dim feature vector OR a dict of
                      feature_name → value.
            timestamp: Optional bar timestamp (EXPIRED TTL + gap detection).
            htf_id: Optional external HTF window id. When omitted, the resolver
                    advances an internal HTF counter every
                    ``lifecycle.htf_candles_per_range`` bars (engine HTFBuilder).
            force_reset: Unconditional RESET → RANGE (external gap / event replay).
            reset_reason: Optional reason string recorded on force_reset.
            engine_reset: Research-shadow only. When True, treat this bar as an
                engine ``RESET`` event: force RANGE and rebuild active_range from
                ``ohlc_buffer[-range_atr_period:]`` unless the reason is a
                session-gap (backtest gap path does not rebuild range). Use when
                replaying ``events.jsonl`` so freeze bars match the engine.
            engine_state_to: Research-shadow only. Engine ``STATE_TRANSITION``
                ``state_to`` on this bar (timestamp-joined). Used to:
                  * promote into EXPANSION when engine does (DISP/SHADOW path)
                  * exit EXPANSION when engine leaves (cuts FP over-hold)

        Returns:
            CRT state name (one of the states defined in config).

        Raises:
            PredicateValidationError: If features are missing or invalid.
        """
        # Normalize to dict
        feat_dict = self._normalize_features(features)

        # B1: append OHLC before lifecycle (engine appends to candle_buffer first,
        # then rebuilds active_range on HTF reset from buffer including this bar).
        if self._sweep_geometry == "htf_range":
            self._push_bar_ohlc_from_features(feat_dict)
            if not self._memory.range_ready and len(self._memory.ohlc_buffer) >= int(
                self._lifecycle["htf_candles_per_range"]
            ):
                # Late seed if caller skipped seed_ohlc/finalize_seed_range
                self.finalize_seed_range()

        # Get feature states
        feature_states: dict[str, str] = {}
        try:
            feature_states = self._encoder.classify(feat_dict)
        except KeyError as e:
            raise PredicateValidationError(
                f"Missing required features for state resolution: {e}"
            ) from e

        # Also classify non-vector stateful features that the predicates reference
        non_vector_features = {}
        for fname in feat_dict:
            try:
                non_vector_features[fname] = self._encoder.classify_value(fname, feat_dict[fname])
            except KeyError:
                pass  # not a stateful feature — skip

        feature_states.update(non_vector_features)

        # Update memory candle index
        self._memory.candle_index += 1

        # Always advance current HTF id (even if gap/force fires this bar)
        self._advance_htf(htf_id)

        # ── Lifecycle: gap / HTF / forced / engine-event RESET ───────────
        # Engine order: gap check → process_candle (which may HTF-reset).
        # HTF reset uses range_htf_id (frozen with active_range), NOT merely
        # "id advanced this bar" — so protected EXPANSION leaves a stale
        # range_htf_id that fires RESET on the first unprotected bar after.
        #
        # engine_reset: optional research replay of events.jsonl RESET bars so
        # range freezes share the engine's candle_buffer[-atr_period:] sequence.
        if engine_reset:
            # B1d: Engine ResetLogic suppresses HTF reset while EXPANSION/RETEST
            # (and active trade). Never force-kill protected narrative from a
            # mis-ordered injection — only non-HTF resets (retrace/gap/extension)
            # may interrupt EXPANSION.
            rsn = (reset_reason or "").lower()
            is_htf = "htf" in rsn
            protect = set(self._lifecycle["htf_protect_states"])
            if self._lifecycle["htf_protect_execution"]:
                protect.add("EXECUTION")
            if is_htf and self._memory.current_state in protect:
                engine_reset = False
            else:
                force_reset = True
                if reset_reason is None:
                    reset_reason = "engine_reset_event"

        did_reset, reason, reset_kind = self._apply_lifecycle_resets(
            timestamp=timestamp,
            force_reset=force_reset,
            reset_reason=reset_reason,
        )
        if did_reset:
            if self._sweep_geometry == "htf_range":
                # Engine process_candle rebuilds range on should_reset
                # (HTF / retrace / extension). Session-gap in backtest_v2 only
                # calls reset_to_range (no rebuild). Forced engine-event replay:
                # rebuild unless reason looks like a session gap.
                do_rebuild = False
                if reset_kind == "htf":
                    do_rebuild = True
                elif reset_kind == "forced":
                    rsn = (reason or "").lower()
                    do_rebuild = not (
                        "session gap" in rsn or "gap detected" in rsn
                    )
                # gap kind: no rebuild
                if do_rebuild:
                    self._rebuild_active_range(
                        self._range_atr_period,
                        htf_id=self._memory.active_htf_id,
                    )
            else:
                resolved = "RANGE"
                self._memory.last_timestamp = timestamp
                self._counts[resolved] = self._counts.get(resolved, 0) + 1
                return resolved

        # Tick pending-displacement TTL (shadow memory)
        self._tick_shadow_ttl()

        # Resolve state through predicate evaluation (+ continuous thresholds)
        resolved = self._resolve_from_features(feature_states, timestamp, feat_dict)

        # Apply transition validity from memory
        resolved = self._apply_transition_validity(resolved)

        # B1e/B1g/B1h research: honour engine STATE_TRANSITION for EXP + SHADOW
        # entry/exit. engine_state_to may be "FROM>TO" (B1g) or bare "TO" (legacy).
        if engine_state_to:
            raw_to = str(engine_state_to)
            if ">" in raw_to:
                eng_from, eng_to = raw_to.split(">", 1)
            else:
                eng_from, eng_to = "", raw_to
            cur_pre = self._memory.current_state
            # B1h: engine RANGE→SHADOW_PENDING founding bar. Continuous path often
            # takes plain SWEEP (pending/dir not yet aligned); force SHADOW so the
            # next bar's SWEEP>EXPANSION collapse can fire (43/60 engine EXP).
            if eng_to == "SHADOW_PENDING" and cur_pre in (
                "RANGE", "SWEEP", "SHADOW_PENDING"
            ):
                resolved = "SHADOW_PENDING"
            elif eng_to == "EXPANSION":
                # Only promote along engine-legal edges.
                # Engine shadow collapse is logged as SWEEP>EXPANSION while the
                # resolver (after B1h SHADOW inject) sits in SHADOW_PENDING —
                # allow that pair (not only cur==SWEEP).
                if eng_from:
                    if eng_from in ("DISPLACEMENT", "SHADOW_PENDING", "SWEEP") and cur_pre in (
                        "DISPLACEMENT", "SHADOW_PENDING", "SWEEP"
                    ):
                        if eng_from == "SWEEP" and cur_pre in ("SWEEP", "SHADOW_PENDING"):
                            resolved = "EXPANSION"
                        elif eng_from in ("DISPLACEMENT", "SHADOW_PENDING"):
                            resolved = "EXPANSION"
                elif cur_pre in ("DISPLACEMENT", "SHADOW_PENDING"):
                    # legacy bare TO: never from SWEEP (B1g FP guard)
                    resolved = "EXPANSION"
            elif cur_pre == "EXPANSION" and eng_to in (
                "RETEST", "EXPIRED", "RANGE", "RESOLUTION", "SWEEP"
            ):
                if eng_to in ("RESOLUTION", "SWEEP"):
                    resolved = "RANGE"
                else:
                    resolved = eng_to
            # B1h: engine leaves DISPLACEMENT→RANGE (HTF reset) without EXP —
            # if continuous path still produced EXP, leave inject is handled by
            # engine_reset; here honour direct DISP→RANGE / SWEEP→RANGE leaves.
            elif cur_pre in ("DISPLACEMENT", "SWEEP", "SHADOW_PENDING") and eng_to == "RANGE":
                if eng_from in ("", cur_pre) or eng_from == cur_pre:
                    resolved = "RANGE"

        # Update memory based on resolved state
        self._update_memory(resolved, feat_dict, timestamp)
        self._memory.last_timestamp = timestamp

        # Count
        self._counts[resolved] = self._counts.get(resolved, 0) + 1

        return resolved

    def resolve_batch(
        self,
        feature_vectors: list[Sequence[float] | Mapping[str, float]],
        timestamps: Optional[list[Any]] = None,
        *,
        htf_ids: Optional[list[Optional[str]]] = None,
        force_resets: Optional[list[bool]] = None,
    ) -> list[str]:
        """Resolve CRT states for a batch of bars.

        Maintains state memory across the batch (sequential resolution).
        """
        states: list[str] = []
        for i, fv in enumerate(feature_vectors):
            ts = timestamps[i] if timestamps else None
            hid = htf_ids[i] if htf_ids else None
            fr = force_resets[i] if force_resets else False
            states.append(self.resolve(fv, ts, htf_id=hid, force_reset=fr))
        return states

    # ── lifecycle (HTF / gap) ─────────────────────────────────────

    def _load_lifecycle(self) -> dict[str, Any]:
        """Load lifecycle block from thresholds (defaults match active backtest)."""
        thr = self._config.get("thresholds", {})
        life = thr.get("lifecycle") or {}
        return {
            "htf_reset_enabled": bool(life.get("htf_reset_enabled", True)),
            "htf_candles_per_range": int(life.get("htf_candles_per_range", 4)),
            "htf_protect_states": set(
                life.get("htf_protect_states") or ["EXPANSION", "RETEST"]
            ),
            "htf_protect_execution": bool(life.get("htf_protect_execution", True)),
            "gap_reset_enabled": bool(life.get("gap_reset_enabled", True)),
            "gap_reset_minutes": float(life.get("gap_reset_minutes", 120)),
            "shadow_on_htf_displacement_reset": bool(
                life.get("shadow_on_htf_displacement_reset", True)
            ),
            "pending_displacement_ttl_candles": int(
                life.get("pending_displacement_ttl_candles", 4)
            ),
        }

    def _apply_lifecycle_resets(
        self,
        *,
        timestamp: Optional[Any],
        force_reset: bool,
        reset_reason: Optional[str],
    ) -> tuple[bool, str, str]:
        """Apply forced / gap / HTF resets. Returns (did_reset, reason, kind).

        Priority (engine-aligned): force_reset ≥ gap ≥ HTF.

        HTF reset uses engine ResetLogic rule:
          current_htf_id != active_range.htf_candle_id  (``range_htf_id`` here)
        not "HTF id advanced on this bar only". Protected states suppress the
        reset but leave ``range_htf_id`` stale so the first unprotected bar
        still rebuilds (engine process_candle path).
        """
        # 1) Explicit force (event replay / external signal)
        if force_reset:
            reason = reset_reason or "force_reset"
            # Engine HTF resets create shadow from DISPLACEMENT; research
            # engine_reset injection must use kind=htf when reason says HTF so
            # pending_displacement_dir is set (B1d — 42/60 EXP entries are shadow).
            kind = "htf" if "HTF" in (reason or "") or "htf" in (reason or "").lower() else "forced"
            # Gap reasons stay non-htf even if forced
            if "gap" in (reason or "").lower() or "session gap" in (reason or "").lower():
                kind = "gap"
            self._force_range_reset(reason, kind=kind)
            return True, reason, kind

        # 2) Session gap (always terminates narrative, including EXPANSION)
        # Backtest gap path: reset_to_range WITHOUT active_range rebuild.
        if self._lifecycle["gap_reset_enabled"] and timestamp is not None:
            gap_hit, gap_reason = self._check_session_gap(timestamp)
            if gap_hit:
                self._force_range_reset(gap_reason, kind="gap")
                return True, gap_reason, "gap"

        # 3) HTF id vs frozen range id (engine should_reset HTF branch)
        if self._lifecycle["htf_reset_enabled"] and self._memory.range_ready:
            cur_htf = self._memory.active_htf_id
            rng_htf = self._memory.range_htf_id
            if cur_htf and rng_htf and cur_htf != rng_htf:
                cur = self._memory.current_state
                protect = set(self._lifecycle["htf_protect_states"])
                if self._lifecycle["htf_protect_execution"]:
                    protect.add("EXECUTION")
                if cur in protect:
                    # Engine: DO NOT INTERRUPT ACTIVE SETUP — range_htf_id stays
                    logger.debug(
                        "HTF change suppressed (protected state=%s): range=%s current=%s",
                        cur, rng_htf, cur_htf,
                    )
                    return False, "", ""
                reason = f"HTF changed: {rng_htf} → {cur_htf}"
                self._force_range_reset(reason, kind="htf")
                return True, reason, "htf"

        return False, "", ""

    def _check_session_gap(self, timestamp: Any) -> tuple[bool, str]:
        """GapDetector-equivalent: gap_mins > gap_reset_minutes → reset."""
        last = self._memory.last_timestamp
        if last is None:
            return False, ""
        try:
            delta = timestamp - last
            gap_mins = delta.total_seconds() / 60.0
        except (TypeError, AttributeError):
            return False, ""
        thr = self._lifecycle["gap_reset_minutes"]
        if gap_mins > thr:
            return True, (
                f"Session gap detected: {gap_mins:.0f}min > {thr:.0f}min"
            )
        return False, ""

    def _advance_htf(self, htf_id: Optional[str]) -> str:
        """Advance current HTF id (``active_htf_id``). Returns the new id.

        Does **not** decide RESET — that compares ``active_htf_id`` to frozen
        ``range_htf_id`` in ``_apply_lifecycle_resets`` (engine
        ``active_range.htf_candle_id`` semantics).

        Internal mode mirrors HTFBuilder: after every ``htf_candles_per_range``
        bars the window id advances (``HTF-{n:06d}``).
        """
        if htf_id is not None:
            new_id = str(htf_id)
            self._memory.active_htf_id = new_id
            return new_id

        if not self._lifecycle["htf_reset_enabled"]:
            return self._memory.active_htf_id

        n = self._lifecycle["htf_candles_per_range"]
        if n <= 0:
            return self._memory.active_htf_id
        self._memory.htf_bars_in_window += 1
        if self._memory.htf_bars_in_window < n:
            if not self._memory.active_htf_id:
                self._memory.active_htf_id = "HTF-INIT"
            return self._memory.active_htf_id
        completed = max(1, self._memory.candle_index // n)
        new_id = f"HTF-{completed:06d}"
        self._memory.htf_bars_in_window = 0
        self._memory.active_htf_id = new_id
        return new_id

    def _force_range_reset(self, reason: str, *, kind: str) -> None:
        """RESET → RANGE, clearing sticky narrative memory (engine reset_to_range)."""
        prev = self._memory.current_state
        # Shadow memory: HTF reset from DISPLACEMENT creates pending displacement
        if (
            kind == "htf"
            and prev == "DISPLACEMENT"
            and self._lifecycle["shadow_on_htf_displacement_reset"]
        ):
            self._memory.pending_displacement_active = True
            self._memory.pending_displacement_formed_idx = (
                self._memory.displacement_candle_index
            )
            self._memory.pending_displacement_ttl = int(
                self._lifecycle["pending_displacement_ttl_candles"]
            )
            # Engine: pending_displacement_dir = state.direction at HTF reset
            d = self._memory.displacement_direction
            self._memory.pending_displacement_dir = (
                "LONG" if d > 0 else ("SHORT" if d < 0 else "NONE")
            )
            # Engine skips TTL countdown on the creating bar (fall-through same candle)
            self._memory.pending_displacement_created_idx = self._memory.candle_index
        elif kind in ("gap", "forced"):
            # Non-HTF reset expires shadow (engine behaviour)
            self._memory.pending_displacement_active = False
            self._memory.pending_displacement_ttl = 0
            self._memory.pending_displacement_formed_idx = -1
            self._memory.pending_displacement_dir = "NONE"
            self._memory.pending_displacement_created_idx = -1

        if prev != "RANGE":
            self._transition_count += 1

        self._memory.current_state = "RANGE"
        self._memory.sweep_candle_index = -1
        self._memory.displacement_candle_index = -1
        self._memory.displacement_candle_close = 0.0
        self._memory.displacement_direction = 0
        self._memory.retest_candle_index = -1
        self._memory.expansion_entry_index = -1
        self._memory.expansion_entry_ts = None
        self._memory.trade_active = False
        self._memory.last_reset_reason = reason

        if kind == "htf":
            self._memory.htf_reset_count += 1
        elif kind == "gap":
            self._memory.gap_reset_count += 1
        else:
            self._memory.forced_reset_count += 1

        logger.debug("RESET → RANGE | %s (was %s)", reason, prev)

    def _tick_shadow_ttl(self) -> None:
        """Decrement pending-displacement TTL; expire when exhausted.

        Engine skips the creating bar (pending_displacement_created_idx) so a
        configured TTL of N yields N usable bars after HTF fall-through.
        """
        if not self._memory.pending_displacement_active:
            return
        if self._memory.candle_index == self._memory.pending_displacement_created_idx:
            return
        if self._memory.pending_displacement_ttl > 0:
            self._memory.pending_displacement_ttl -= 1
            if self._memory.pending_displacement_ttl <= 0:
                self._memory.pending_displacement_active = False
                self._memory.pending_displacement_formed_idx = -1
                self._memory.pending_displacement_dir = "NONE"
                self._memory.pending_displacement_created_idx = -1

    # ── config loading ───────────────────────────────────────────

    def _load_config(self) -> dict:
        """Load and validate the CRT states config YAML."""
        path = self._config_path
        if not path.exists():
            raise ConfigLoadError(f"CRT states config not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh)
        except Exception as e:
            raise ConfigLoadError(f"Failed to parse {path}: {e}") from e

        required_keys = ["version", "states", "valid_transitions", "thresholds"]
        for key in required_keys:
            if key not in cfg:
                raise ConfigLoadError(f"Config {path} missing required key: {key}")

        if not isinstance(cfg["states"], list) or len(cfg["states"]) == 0:
            raise ConfigLoadError(f"Config {path}: 'states' must be a non-empty list")

        return cfg

    def _validate_predicates(self) -> None:
        """Validate that all predicate references match known feature states.

        Raises PredicateValidationError on first mismatch.
        """
        stateful = set(self._encoder.stateful_features)
        declared: dict[str, set[str]] = {}
        for fname, snames in self._config.get("feature_states", {}).items():
            declared[fname] = set(snames)
            if fname not in stateful:
                raise PredicateValidationError(
                    f"feature_states '{fname}' is not a declared stateful feature "
                    "in market_ontology.yaml"
                )
            # Validate each state name against the ontology's declared states
            sf = self._encoder.spec(fname)
            actual_states = set(sf.value_to_state.values())
            for sn in snames:
                if sn not in actual_states:
                    # Check if it's a valid state (might be a state name that exists)
                    raise PredicateValidationError(
                        f"State '{sn}' for feature '{fname}' not found in ontology. "
                        f"Valid states: {sorted(actual_states)}"
                    )

        # Validate each state's predicates
        for state_def in self._config["states"]:
            name = state_def["name"]
            when = state_def.get("when", {})
            for fname, allowed_states in when.items():
                if fname not in declared:
                    raise PredicateValidationError(
                        f"CRT state '{name}': feature '{fname}' not in feature_states block "
                        f"(valid: {sorted(declared)})"
                    )
                for sname in allowed_states:
                    if sname not in declared[fname]:
                        actual = declared.get(fname, set())
                        raise PredicateValidationError(
                            f"CRT state '{name}': state '{sname}' not valid for feature "
                            f"'{fname}' (valid: {sorted(actual)})"
                        )

    # ── resolution logic ─────────────────────────────────────────

    def _normalize_features(
        self, features: Mapping[str, float] | Sequence[float]
    ) -> dict[str, float]:
        """Normalize features to a name→value dict."""
        if isinstance(features, Mapping):
            return dict(features)
        # Sequence — assume canonical 39-dim
        if len(features) != len(CANONICAL_FEATURES):
            raise PredicateValidationError(
                f"Expected {len(CANONICAL_FEATURES)}-dim canonical vector, got {len(features)}"
            )
        return dict(zip(CANONICAL_FEATURES, features))

    def _resolve_from_features(
        self,
        feature_states: dict[str, str],
        timestamp: Optional[Any] = None,
        raw_features: Optional[Mapping[str, float]] = None,
    ) -> str:
        """Evaluate feature states against CRT state predicates.

        First-match order: most specific states evaluated first.
        Memory-only states (EXPIRED, RESOLUTION) are resolved from current
        memory when their conditions are met.
        Continuous thresholds (body_ratio, retest_depth) further gate
        DISPLACEMENT / RETEST / EXECUTION when raw values are present.
        """
        raw = dict(raw_features or {})

        # Check memory-only states first (these check current memory, not features)
        if self._memory.current_state == "EXPANSION":
            if self._check_expired(timestamp):
                return "EXPIRED"
            # B1f: continuous mid-dwell hold. Engine stays in EXPANSION until
            # try_expansion_to_retest (strict geometry) or TTL/RESET — NOT until
            # pipeline retest_flag (fires on a large fraction of bars and was
            # promoting EXP→RETEST→RANGE mid-episode, opening ~2k FN holes).
            # Research RETEST/RANGE exits still apply via engine_state_to inject
            # after this return path is overridden in resolve().
            return "EXPANSION"

        if self._memory.current_state == "EXECUTION":
            if self._check_resolution(feature_states):
                return "RESOLUTION"
            # Cap EXECUTION dwell at soft_conf_max_candles (trade lifecycle
            # is not fully modelled; avoid multi-thousand-bar EXECUTION).
            if self._sticky_age_expired("EXECUTION"):
                return "RESOLUTION"

        # SWEEP age expiry → RANGE (engine: max_sweep_age during SWEEP handling)
        if self._memory.current_state == "SWEEP" and self._sticky_age_expired("SWEEP"):
            return "RANGE"

        # ── B1d: shadow + HTF-range SWEEP founding (engine RANGE/SHADOW branches)
        #
        # Engine:
        #   RANGE + pending + matching sweep → SHADOW_PENDING (same bar)
        #   next bar SHADOW_PENDING → try_shadow_pending_to_expansion (→ EXP)
        # Do NOT auto-SHADOW on pending alone (pre-B1d bug), and do NOT re-found
        # SWEEP from SHADOW_PENDING (that stole ~42/60 engine EXP entries).
        cur = self._memory.current_state
        sweep_sig = (
            self._detect_htf_range_sweep(raw)
            if self._sweep_geometry == "htf_range"
            else 0
        )

        if cur == "SHADOW_PENDING":
            if self._memory.pending_displacement_active:
                # Engine SHADOW branch: collapse to EXPANSION (strength skipped)
                return "EXPANSION"
            # SHADOW_LEAK equivalent
            return "RANGE"

        if (
            self._sweep_geometry == "htf_range"
            and cur == "RANGE"
            and sweep_sig != 0
            and self._sweep_entry_allowed(raw)
        ):
            if self._memory.pending_displacement_active and self._shadow_dir_matches(
                sweep_sig
            ):
                return "SHADOW_PENDING"
            return "SWEEP"

        # ── B1c/B1g/B1h: continuous-only funnel (engine StateMachine, not pipeline flags)
        # B1g: do NOT promote SWEEP→EXPANSION on pending alone. Engine shadow
        # collapse is SHADOW_PENDING→EXP only; SWEEP+stale-pending was creating
        # ~400-bar FP EXP over-holds while engine was still SWEEP/RANGE.
        # B1h: continuous DISPLACEMENT→EXPANSION is OFF by default
        # (thresholds.continuous_disp_to_expansion=false). Residual 128 FP were
        # all 1-bar DISP dwells that met ATR-extension but engine RESET→RANGE
        # without ever taking EXP; research EXP entry is inject-owned
        # (DISPLACEMENT>EXPANSION / SWEEP>EXPANSION) + SHADOW collapse above.
        if cur == "SWEEP":
            if self._displacement_entry_allowed(raw):
                return "DISPLACEMENT"
        thr = self._config.get("thresholds", {})
        if (
            cur == "DISPLACEMENT"
            and bool(thr.get("continuous_disp_to_expansion", False))
            and self._expansion_entry_allowed(raw)
        ):
            return "EXPANSION"

        # Evaluate config-defined states in order (with funnel-entry override)
        matched: list[str] = []
        for state_def in self._config["states"]:
            name = state_def["name"]
            when = state_def.get("when", {})
            requires_memory = state_def.get("requires_memory", False)

            # Skip memory-only states if we're evaluating from features alone
            # (they require the _apply_transition_validity pass)
            if requires_memory and not when:
                continue

            # B1/B1c: under htf_range, founding SWEEP + funnel promotions are
            # continuous-gate owned above. Skip pipeline when-block re-entry for
            # SWEEP/DISPLACEMENT/EXPANSION when not already dwelling there
            # (sticky dwell uses the sticky-hold path below).
            if self._sweep_geometry == "htf_range":
                if name == "SWEEP" and cur != "SWEEP":
                    continue
                if name == "DISPLACEMENT" and cur != "DISPLACEMENT":
                    continue
                if name == "EXPANSION" and cur != "EXPANSION":
                    continue

            # Check discrete predicates
            if not self._predicates_match(when, feature_states):
                continue

            # Continuous threshold gates (engine-grade filters)
            if not self._continuous_gates_pass(name, raw):
                continue

            matched.append(name)

        if matched:
            # Funnel-entry rule: from RANGE, a bar that matches both SWEEP and
            # DISPLACEMENT must enter SWEEP first (engine: sweep event then
            # subsequent-bar displacement). Config first-match would otherwise
            # skip SWEEP because DISPLACEMENT is listed earlier.
            if (
                self._memory.current_state in ("RANGE", "SHADOW_PENDING")
                and "SWEEP" in matched
            ):
                return "SWEEP"
            # Passive RANGE predicate match must NOT kill sticky dwell mid-window.
            # Narrative termination is owned by lifecycle RESET (HTF/gap) and
            # sticky age expiry — not by the ground-state when-block.
            if (
                matched[0] == "RANGE"
                and self._memory.current_state in self._STICKY_STATES
                and not self._sticky_age_expired(self._memory.current_state)
            ):
                return self._memory.current_state
            return matched[0]

        # Sticky hold: if no new predicate matched, keep dwelling in the
        # current sticky state so multi-bar engine dwell is approximated.
        # Age expiry is enforced in _apply_transition_validity (entry indices
        # set only on transition — see _update_memory).
        if self._memory.current_state in self._STICKY_STATES:
            return self._memory.current_state

        return "RANGE"

    def _continuous_gates_pass(self, state_name: str, raw: Mapping[str, float]) -> bool:
        """Apply continuous thresholds from config for selected states.

        Discrete feature states alone over-fire RETEST/EXECUTION because the
        pipeline ``retest_flag`` is a rolling-lookback OR of any recent sweep
        near EMA — far looser than the CRT engine's EXPANSION→RETEST gate.
        When raw continuous values are present, apply the declared thresholds.
        Missing values → pass (fail-open for synthetic / partial vectors).
        """
        thr = self._config.get("thresholds", {})

        if state_name == "SWEEP":
            return self._sweep_entry_allowed(raw)

        if state_name == "DISPLACEMENT":
            return self._displacement_entry_allowed(raw)

        if state_name == "EXPANSION":
            return self._expansion_entry_allowed(raw)

        if state_name in ("RETEST", "EXECUTION"):
            depth_max = float(thr.get("retest_depth_max", 0.25))
            depth = raw.get("retest_depth")
            if depth is not None and depth > depth_max:
                return False
            # Must arrive via the funnel (not cold-start from RANGE)
            if state_name == "RETEST" and self._memory.current_state not in (
                "EXPANSION", "RETEST"
            ):
                return False
            if state_name == "EXECUTION" and self._memory.current_state not in (
                "RETEST", "EXECUTION"
            ):
                return False
            # EXECUTION also requires risk score when present (engine score_threshold).
            # Without a score feature the gate fails closed — EXECUTION is the
            # rarest state and must not fire on retest_flag alone.
            if state_name == "EXECUTION":
                score = raw.get("score", raw.get("risk_score", raw.get("crt_score")))
                score_thr = float(thr.get("score_threshold", 0.45))
                if score is None:
                    return False  # fail closed: no score ⇒ no EXECUTION
                if score < score_thr:
                    return False

        return True

    def _sweep_entry_allowed(self, raw: Mapping[str, float]) -> bool:
        """Engine-grade SWEEP entry funnel (try_range_to_sweep).

        * Already in SWEEP → allow (sticky re-eval; age expiry handled earlier)
        * From RANGE → allow (founding event; detector is sweep_geometry)
        * From SHADOW_PENDING → allow (shadow collapse step to SWEEP)
        * Else → reject (cannot jump into SWEEP mid-funnel)

        Detector geometry (B1): ``htf_range`` uses engine HTF active-range
        cross-and-close-back; ``pipeline_swing`` uses FeaturePipeline
        liquidity_sweep when-block (legacy).
        """
        cur = self._memory.current_state
        if cur in ("SWEEP", "RANGE", "SHADOW_PENDING"):
            return True
        return False

    # ── B1 HTF-range sweep helpers ───────────────────────────────

    def _push_bar_ohlc(self, open_: float, high: float, low: float, close: float) -> None:
        buf = self._memory.ohlc_buffer
        buf.append((float(open_), float(high), float(low), float(close)))
        if len(buf) > self._ohlc_buffer_cap:
            del buf[: len(buf) - self._ohlc_buffer_cap]

    def _push_bar_ohlc_from_features(self, raw: Mapping[str, float]) -> None:
        o = raw.get("open")
        h = raw.get("high")
        l = raw.get("low")
        c = raw.get("close")
        if o is None or h is None or l is None or c is None:
            return
        self._push_bar_ohlc(float(o), float(h), float(l), float(c))

    def _rebuild_active_range(
        self, period: int, *, htf_id: Optional[str] = None
    ) -> None:
        """Freeze h_ref/l_ref from the last ``period`` OHLC bars (engine detect_htf_range).

        Also stamps ``range_htf_id`` (engine ``Range.htf_candle_id``) so subsequent
        HTF advances compare against the freeze, not the pre-rebuild current id.
        """
        buf = self._memory.ohlc_buffer
        if not buf or period < 1:
            self._memory.range_ready = False
            return
        window = buf[-period:] if len(buf) >= period else buf[:]
        highs = [b[1] for b in window]
        lows = [b[2] for b in window]
        self._memory.range_h_ref = max(highs)
        self._memory.range_l_ref = min(lows)
        self._memory.range_ready = self._memory.range_h_ref > self._memory.range_l_ref
        if htf_id is not None:
            self._memory.range_htf_id = str(htf_id)
        elif self._memory.active_htf_id:
            self._memory.range_htf_id = self._memory.active_htf_id

    def _detect_htf_range_sweep(self, raw: Mapping[str, float]) -> int:
        """Engine RangeDetector.detect_sweep geometry.

        Returns +1 (sell-side / high sweep → SHORT), -1 (buy-side / low → LONG),
        or 0. Engine uses strict close inequalities: close < h_ref / close > l_ref.
        """
        if not self._memory.range_ready:
            return 0
        h = raw.get("high")
        l = raw.get("low")
        c = raw.get("close")
        if h is None or l is None or c is None:
            return 0
        h_ref = self._memory.range_h_ref
        l_ref = self._memory.range_l_ref
        swept_high = float(h) > h_ref and float(c) < h_ref
        swept_low = float(l) < l_ref and float(c) > l_ref
        if not swept_high and not swept_low:
            return 0
        # Engine: if both (rare), direction = SHORT if swept_high else LONG
        if swept_high:
            return 1
        return -1

    def _shadow_dir_matches(self, sweep_sig: int) -> bool:
        """Engine: confirming sweep.direction == pending_displacement_dir."""
        pending = self._memory.pending_displacement_dir
        if pending in ("", "NONE") or sweep_sig == 0:
            # Unknown pending dir: allow resume (fail-open on incomplete memory)
            return True
        # sweep_sig +1 = sell-side = SHORT; -1 = buy-side = LONG
        want = "SHORT" if sweep_sig > 0 else "LONG"
        return pending == want

    def _displacement_entry_allowed(self, raw: Mapping[str, float]) -> bool:
        """Engine-grade DISPLACEMENT entry (try_sweep_to_displacement).

        ONLY from SWEEP. Gates (all must pass):
          1. sweep age <= max_sweep_age_candles
          2. abs(close-open) >= atr_min_displacement * atr_abs
          3. body_ratio >= body_ratio_min
          4. candle_range (v4.0; ≡ engine wick_size) >= atr_multiplier_min * atr_abs
        """
        thr = self._config.get("thresholds", {})
        cur = self._memory.current_state

        if cur == "DISPLACEMENT":
            return True  # sticky dwell

        if cur != "SWEEP":
            return False

        # Stale sweep — do not promote (engine expires sweep → RANGE path)
        if self._sticky_age_expired("SWEEP"):
            return False

        close = raw.get("close")
        open_ = raw.get("open")
        if close is None or open_ is None:
            return False

        atr_abs = self._atr_abs(raw)
        if atr_abs is None or atr_abs <= 0:
            return False

        # (2) min body move in price units
        move = abs(float(close) - float(open_))
        min_move = float(thr.get("atr_min_displacement", 1.2)) * atr_abs
        if move < min_move:
            return False

        # (3) body_ratio
        body = raw.get("body_ratio")
        body_min = float(thr.get("body_ratio_min", 0.70))
        if body is not None and float(body) < body_min:
            return False

        # (4) candle_range vs ATR — engine try_sweep_to_displacement gate 4
        # (crt_engine_v2.py:1198 → candle.wick_size < atr_multiplier_min * atr_abs, where the
        # engine's Candle.wick_size ≡ FM-002 candle_range = high - low).
        # SCHEMA v4.0 renamed the canonical column `wick_size` → `candle_range`
        # (feature_schema.py:89): the canonical vector no longer carries `wick_size`, so the prior
        # `raw.get("wick_size")` was always None and this gate silently no-op'd on every real
        # vector — the shadow was looser than the engine here. feature_pipeline emits candle_range
        # ABSOLUTE (high - low, un-normalized), the same units as atr_abs, so the comparison is
        # direct (no relative/absolute guess). `wick_size` is kept only as a read-side fallback for
        # pre-v4 / synthetic dicts. Present on the canonical path ⇒ fail-closed like the engine;
        # genuinely absent (partial synthetic vector) ⇒ skip.
        candle_range = raw.get("candle_range", raw.get("wick_size"))
        if candle_range is not None:
            wick_min = float(thr.get("atr_multiplier_min", 1.5)) * atr_abs
            if float(candle_range) < wick_min:
                return False

        return True

    def _expansion_entry_allowed(self, raw: Mapping[str, float]) -> bool:
        """Engine-grade EXPANSION entry (try_displacement_to_expansion + shadow).

        Funnel (hard):
          * already in EXPANSION → allow (sticky re-evaluation / dwell)
          * from DISPLACEMENT → require ATR-distance extension past disp_close
          * from SWEEP / SHADOW_PENDING with pending_displacement_active →
            shadow resume (engine skips strength check)
          * otherwise → reject (engine never enters EXPANSION from RANGE)

        Continuous (DISPLACEMENT path only):
          * directional extension of close beyond displacement_candle_close
          * abs(close - disp_close) >= expansion_atr_min_distance * atr_abs
        """
        thr = self._config.get("thresholds", {})
        cur = self._memory.current_state

        if cur == "EXPANSION":
            return True  # dwell; lifecycle/TTL owns exit

        # Shadow resume: SHADOW_PENDING→SWEEP→EXPANSION collapse (43/60 engine entries)
        if cur in ("SWEEP", "SHADOW_PENDING") and self._memory.pending_displacement_active:
            return True

        if cur != "DISPLACEMENT":
            return False

        # ── DISPLACEMENT → EXPANSION continuous gates ─────────────
        disp_close = self._memory.displacement_candle_close
        close = raw.get("close")
        if close is None or disp_close <= 0:
            # No displacement memory / price → fail closed (cannot prove extension)
            return False

        direction = self._memory.displacement_direction
        if direction == 0:
            # Infer from this bar's body if memory lacks direction
            o = raw.get("open")
            if o is not None and close != o:
                direction = 1 if close > o else -1
            else:
                return False

        # Directional bar (engine: LONG requires bullish close, SHORT bearish)
        o = raw.get("open")
        if o is not None:
            if direction > 0 and not (close > o):
                return False
            if direction < 0 and not (close < o):
                return False

        # close must extend beyond displacement close
        if direction > 0 and close <= disp_close:
            return False
        if direction < 0 and close >= disp_close:
            return False

        # ATR-distance guard
        atr_abs = self._atr_abs(raw)
        if atr_abs is None or atr_abs <= 0:
            return False
        min_dist = float(thr.get("expansion_atr_min_distance", 0.20)) * atr_abs
        if abs(close - disp_close) < min_dist:
            return False

        return True

    def _atr_abs(self, raw: Mapping[str, float]) -> Optional[float]:
        """Resolve absolute ATR from the feature vector.

        Canonical ``atr`` is typically relative (atr/close). Engine gates use
        atr_abs in price units. When ``expansion_atr_is_relative`` is true
        (default), multiply by close.
        """
        atr = raw.get("atr")
        if atr is None:
            return None
        thr = self._config.get("thresholds", {})
        relative = bool(thr.get("expansion_atr_is_relative", True))
        close = raw.get("close")
        if relative and close is not None and close > 0:
            return float(atr) * float(close)
        return float(atr)

    def _predicates_match(
        self,
        when: dict[str, list[str]],
        feature_states: dict[str, str],
    ) -> bool:
        """Check if all predicates in ``when`` match.

        AND across features: EVERY feature's state must be in its allowed list.
        OR within a feature: ANY of the listed states satisfies.
        """
        if not when:
            return True  # empty predicates always match
        for fname, allowed_states in when.items():
            actual = feature_states.get(fname)
            if actual is None:
                return False  # feature not available — predicate fails
            if actual not in allowed_states:
                return False
        return True

    def _apply_transition_validity(self, target: str) -> str:
        """Ensure the resolved state is a valid transition from current memory.

        Sticky dwell (engine-equivalent):
          - SWEEP / DISPLACEMENT / EXPANSION / RETEST persist across bars that
            no longer fire their entry predicates, until a *forward* transition
            or an age-based invalidate (thresholds.max_sweep_age_candles /
            expansion TTL). RANGE is NOT auto-reached on every non-match —
            that was collapsing multi-bar engine dwell into single-bar spikes.
          - RANGE remains reachable from sticky states only when the age window
            has expired (invalidate) or the target is an explicit valid edge.
        """
        current = self._memory.current_state
        if current == target:
            # Same-state hold: still check sticky age expiry
            if current in self._STICKY_STATES and self._sticky_age_expired(current):
                self._transition_count += 1
                return "RANGE"
            return target

        valid_targets = self._config["valid_transitions"].get(current, [])

        # Forward / lateral transitions declared in the graph.
        # RANGE from a sticky state is only taken on age expiry (or lifecycle
        # RESET, which bypasses this method via _force_range_reset). This keeps
        # multi-bar SWEEP/EXPANSION dwell intact inside an HTF window.
        if target in valid_targets:
            if (
                target == "RANGE"
                and current in self._STICKY_STATES
                and not self._sticky_age_expired(current)
            ):
                return current
            self._transition_count += 1
            return target

        # Not a declared edge: hold sticky state while age remains, else RANGE
        if current in self._STICKY_STATES:
            if self._sticky_age_expired(current):
                self._transition_count += 1
                return "RANGE"
            return current

        # Non-sticky (RANGE / SHADOW_PENDING / EXPIRED / RESOLUTION):
        # RANGE is always a valid soft reset from these
        if target == "RANGE":
            self._transition_count += 1
            return target

        return current

    # States that dwell across bars (engine state machine, not single-bar flags)
    _STICKY_STATES = frozenset({"SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION"})

    def _sticky_age_expired(self, state: str) -> bool:
        """Return True if the sticky state's age window has been exceeded."""
        thr = self._config.get("thresholds", {})
        idx = self._memory.candle_index

        if state == "SWEEP":
            # Engine: age > max_sweep_age_candles (strict greater-than)
            max_age = int(thr.get("max_sweep_age_candles", 20))
            if self._memory.sweep_candle_index < 0:
                return True
            return (idx - self._memory.sweep_candle_index) > max_age

        if state == "DISPLACEMENT":
            # B1e: engine has NO sticky age kill on DISPLACEMENT — only HTF reset
            # or successful →EXPANSION. A short max_displacement_age was forcing
            # RANGE before expansion gates could pass (7 fully-missed eng EXP eps).
            return False

        if state == "EXPANSION":
            return self._check_expired(self._memory.expansion_entry_ts)

        if state == "RETEST":
            # Soft-confirm window: soft_conf_max_candles (default 3)
            max_age = int(thr.get("soft_conf_max_candles", 3))
            if self._memory.retest_candle_index < 0:
                return True
            return (idx - self._memory.retest_candle_index) >= max_age

        if state == "EXECUTION":
            # Without full trade lifecycle, cap EXECUTION at soft-confirm window
            max_age = int(thr.get("soft_conf_max_candles", 3))
            # Use retest index as proxy entry if no dedicated execution index
            entry = self._memory.retest_candle_index
            if entry < 0:
                return True
            return (idx - entry) >= max_age

        return True

    def _update_memory(
        self,
        resolved: str,
        features: dict[str, float],
        timestamp: Optional[Any] = None,
    ) -> None:
        """Update state memory after resolution.

        Entry indices are set only on *transition into* a state (not on every
        dwell bar) so sticky age windows actually expire.
        """
        prev = self._memory.current_state
        entered = prev != resolved
        self._memory.current_state = resolved

        if resolved == "SWEEP" and entered:
            self._memory.sweep_candle_index = self._memory.candle_index
            # Engine: SellSideSweep (high) → SHORT (−1), BuySide → LONG (+1)
            if self._sweep_geometry == "htf_range":
                sig = self._detect_htf_range_sweep(features)
                if sig != 0:
                    # sig +1 = sell-side = SHORT; −1 = buy-side = LONG
                    self._memory.displacement_direction = -1 if sig > 0 else 1

        if resolved == "DISPLACEMENT" and entered:
            self._memory.displacement_candle_index = self._memory.candle_index
            self._memory.displacement_candle_close = float(features.get("close", 0.0) or 0.0)
            # Direction from candle body (engine Direction.LONG/SHORT); keep
            # sweep-direction fallback already stored at SWEEP entry.
            o = features.get("open")
            c = features.get("close")
            if o is not None and c is not None and c != o:
                self._memory.displacement_direction = 1 if c > o else -1
            elif self._memory.displacement_direction == 0:
                tb = features.get("trend_bias", 0.0)
                self._memory.displacement_direction = (
                    1 if tb > 0 else (-1 if tb < 0 else 0)
                )

        if resolved == "EXPANSION" and entered:
            self._memory.expansion_entry_index = self._memory.candle_index
            self._memory.expansion_entry_ts = timestamp
            # Shadow resume consumes pending displacement (engine clears on confirm)
            if self._memory.pending_displacement_active:
                self._memory.pending_displacement_active = False
                self._memory.pending_displacement_ttl = 0
                self._memory.pending_displacement_formed_idx = -1
                self._memory.pending_displacement_dir = "NONE"

        if resolved == "RETEST" and entered:
            self._memory.retest_candle_index = self._memory.candle_index

        if resolved == "EXECUTION" and entered:
            self._memory.trade_active = True

        if resolved == "RESOLUTION":
            self._memory.trade_active = False

        if resolved == "RANGE" and prev == "SHADOW_PENDING":
            # Shadow expired — clear pending memory
            self._memory.pending_displacement_active = False

        if resolved == "SHADOW_PENDING" and entered:
            self._memory.pending_displacement_active = True

    def _check_expired(self, timestamp: Optional[Any] = None) -> bool:
        """Check if the EXPANSION TTL has been exceeded.

        Returns True if the expansion has been active for too many candles
        or too many hours.
        """
        thresholds = self._config.get("thresholds", {})
        max_candles = thresholds.get("max_expansion_age_candles", 495)
        max_hours = thresholds.get("max_expansion_age_hours", 124)

        # Check candle-based TTL
        if max_candles > 0:
            age = self._memory.candle_index - self._memory.expansion_entry_index
            if age >= max_candles:
                return True

        # Check hour-based TTL (if timestamp available)
        if max_hours > 0 and timestamp is not None and self._memory.expansion_entry_ts is not None:
            try:
                delta = timestamp - self._memory.expansion_entry_ts
                hours = delta.total_seconds() / 3600
                if hours >= max_hours:
                    return True
            except (TypeError, AttributeError):
                pass  # cannot compute — skip hour check

        return False

    def _check_resolution(self, feature_states: dict[str, str]) -> bool:
        """Check if a trade should resolve.

        For feature-only resolution, we consider the trade resolved when
        the engine would reset to RANGE (no sweep, no displacement, etc.).
        This is a heuristic — actual resolution requires trade PnL tracking.
        """
        # If the bar is in RANGE and we had a trade active → resolved
        range_conditions = self._find_state_def("RANGE").get("when", {})
        return self._predicates_match(range_conditions, feature_states)

    def _find_state_def(self, name: str) -> dict:
        """Find a state definition by name."""
        for sd in self._config["states"]:
            if sd["name"] == name:
                return sd
        return {}


# ── HTF phase-lock helper ────────────────────────────────────────

def build_htf_id_timeline(
    n_bars: int,
    *,
    candles_per_htf: int = 4,
    instrument: str = "UNKNOWN",
) -> list[str]:
    """Build per-bar HTF window ids using the engine's HTFBuilder semantics.

    Byte-equivalent to ``runtime.backtest_v2.HTFBuilder``:
      - buffer candles until ``candles_per_htf`` is reached
      - on complete: ``{instrument}-HTF-{idx:06d}`` (1-based idx)
      - until first complete: id remains ``HTF-INIT``

    Used to **phase-lock** the resolver's HTF RESET clock to the engine so
    SWEEP↔RANGE off-diagonal cells are not inflated by warmup/index phase
    drift (FeaturePipeline drops ~78 warmup bars; internal counters would
    otherwise restart at 0 on the enriched slice).

    Args:
        n_bars: Length of the *raw* OHLCV stream (pre-warmup-drop).
        candles_per_htf: ``backtest.htf_candles_per_range`` (prod default 4).
        instrument: Prefix for HTF ids (e.g. ``XAUUSD``).

    Returns:
        List of length ``n_bars``; entry *i* is the HTF id *after* pushing
        candle *i* (0-based), matching ``htf.current_htf_id`` at the end of
        that bar's backtest iteration.
    """
    if n_bars < 0:
        raise ValueError(f"n_bars must be >= 0, got {n_bars}")
    if candles_per_htf <= 0:
        raise ValueError(f"candles_per_htf must be > 0, got {candles_per_htf}")

    ids: list[str] = []
    buffer_len = 0
    htf_idx = 0
    current_id = "HTF-INIT"
    for _ in range(n_bars):
        buffer_len += 1
        if buffer_len >= candles_per_htf:
            htf_idx += 1
            current_id = f"{instrument}-HTF-{htf_idx:06d}"
            buffer_len = 0
        ids.append(current_id)
    return ids


# ── Convenience function ─────────────────────────────────────────

def create_resolver(
    config_path: Optional[Path | str] = None,
    ontology_path: Optional[Path | str] = None,
) -> CRTStateResolver:
    """Create a configured CRTStateResolver with optional overrides."""
    ontology = None
    if ontology_path:
        import yaml as _yaml
        with open(ontology_path, "r", encoding="utf-8") as fh:
            ontology = _yaml.safe_load(fh)
    return CRTStateResolver(config_path=config_path, ontology=ontology)