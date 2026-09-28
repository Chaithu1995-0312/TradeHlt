"""
signal_belief_tracker.py
================================================================================
Temporal belief accumulator that gates DecisionEngine calls.

Problem: A strategy winning a single candle can trigger execution (noise).
Fix:     Accumulate post-fusion conviction over consecutive candles before
         allowing DecisionEngine to proceed.

Gate location (strict):
    CRT → Features → StrategyOrchestrator → Fusion → [BeliefTracker] → Decision
                                                        ↑
                                             accumulates post-fusion score

Formula:
    belief[t] = DECAY × belief[t-1] + (1 - DECAY) × fusion_signal
    fusion_signal = fusion_score × strategy_consensus_direction  (signed)

Gate passes when:
    abs(belief) >= HIGH_CONVICTION   →  "HIGH_CONVICTION"
    OR confirm_count >= MIN_CONFIRMS →  "CONFIRMED"

Ownership:
    RuntimeContext (created by BacktestRunner / LiveRunner) owns BeliefRegistry.
    EngineRunner reads context["belief_registry"] — it never creates trackers.
    No module-global state: parallel pytest runs and multi-coin backtests are safe.
================================================================================
"""

from __future__ import annotations

from dataclasses import dataclass

from config_layer.strict_config import require_all, require_section


# ─────────────────────────────────────────────────────────────────
# BeliefState — read-only output of SignalBeliefTracker.update()
# ─────────────────────────────────────────────────────────────────

@dataclass
class BeliefState:
    """Snapshot of one tracker's state after a single candle update.

    Fields
    ------
    belief        Signed exponential average in [-1, 1].
                  Positive = BUY conviction, negative = SELL conviction.
    direction     1=BUY, -1=SELL, 0=NEUTRAL (matches the input direction).
    confirm_count Consecutive candles that passed the fusion gate same direction.
    approved      True → DecisionEngine may proceed.
    reason        "HIGH_CONVICTION" | "CONFIRMED" | "INSUFFICIENT"
    """
    belief:        float
    direction:     int
    confirm_count: int
    approved:      bool
    reason:        str


# ─────────────────────────────────────────────────────────────────
# SignalBeliefTracker — per-symbol belief accumulator
# ─────────────────────────────────────────────────────────────────

class SignalBeliefTracker:
    """Exponential belief accumulator over post-fusion conviction scores.

    Instantiated by BeliefRegistry — never directly by EngineRunner.
    One tracker per (instrument, timeframe) pair.

    Parameters
    ----------
    config  Optional config dict read from engine_runner.signal_belief in the
            production JSON.  Falls back to class-level defaults when absent.
    """

    # EPIC-84 STORY-84.2: the class-level _DEFAULT_DECAY / _DEFAULT_HIGH_CONVICTION /
    # _DEFAULT_MIN_CONFIRMS literals are gone; every knob is a required
    # engine_runner.signal_belief key (values live in the production JSON only).
    _REQUIRED_KEYS = ("decay", "high_conviction_threshold", "min_confirmations")

    @classmethod
    def from_prod_config(cls, base_config: dict | None = None) -> "SignalBeliefTracker":
        """Production constructor — fail-fast. Strict-reads every knob from
        ``engine_runner.signal_belief`` (nested, not top-level); a missing section or key raises.

        Reached only when the gate is enabled: EngineRunner checks ``_belief_enabled`` before
        asking the registry for a tracker (engine_runner.py), and BeliefRegistry creates trackers
        lazily — so this never raises for the 20 production configs that omit the section while
        leaving the gate off.
        """
        from config_layer.production_config import get_prod_section
        section = require_section(
            get_prod_section("engine_runner"), "signal_belief", consumer="SignalBeliefTracker",
        )
        merged = dict(base_config or {})
        merged.update(require_all(
            section, cls._REQUIRED_KEYS,
            section_name="engine_runner.signal_belief", consumer="SignalBeliefTracker",
        ))
        return cls(merged)

    def __init__(self, config: dict) -> None:
        # EPIC-84 STORY-84.2: one require_all, then index — no .get() literal fallbacks.
        cfg = require_all(
            config, self._REQUIRED_KEYS,
            section_name="engine_runner.signal_belief", consumer="SignalBeliefTracker",
        )
        self._decay           = float(cfg["decay"])
        self._high_conviction = float(cfg["high_conviction_threshold"])
        self._min_confirms    = int(cfg["min_confirmations"])

        self._belief:        float = 0.0   # signed, range [-1, 1]
        self._last_direction: int  = 0
        self._confirm_count:  int  = 0

    def update(self, fusion_score: float, direction: int) -> BeliefState:
        """Update belief with one candle's post-fusion score.

        Parameters
        ----------
        fusion_score  Final fusion output in [0, 1].
        direction     Consensus direction: 1=BUY, -1=SELL, 0=NEUTRAL.
                      Derived from strategy_consensus_direction in context.

        Returns
        -------
        BeliefState with approved=True when the gate passes.
        """
        if direction == 0:
            # Neutral candle: decay belief toward zero, reset streak.
            self._belief = self._belief * self._decay
            self._confirm_count = 0
            self._last_direction = 0
            return BeliefState(
                belief        = self._belief,
                direction     = 0,
                confirm_count = 0,
                approved      = False,
                reason        = "INSUFFICIENT",
            )

        # Signed fusion signal: positive for BUY, negative for SELL.
        fusion_signal = float(fusion_score) * direction
        self._belief = self._decay * self._belief + (1.0 - self._decay) * fusion_signal

        # Track consecutive-candle confirmation streak.
        if direction == self._last_direction:
            self._confirm_count += 1
        else:
            # Direction flip: reset streak, start at 1.
            self._confirm_count = 1
        self._last_direction = direction

        # Gate decision.
        high_conviction = abs(self._belief) >= self._high_conviction
        confirmed       = self._confirm_count >= self._min_confirms

        if high_conviction:
            reason = "HIGH_CONVICTION"
        elif confirmed:
            reason = "CONFIRMED"
        else:
            reason = "INSUFFICIENT"

        return BeliefState(
            belief        = self._belief,
            direction     = direction,
            confirm_count = self._confirm_count,
            approved      = high_conviction or confirmed,
            reason        = reason,
        )

    def reset(self) -> None:
        """Reset belief state (useful for testing or explicit lifecycle management)."""
        self._belief        = 0.0
        self._last_direction = 0
        self._confirm_count  = 0


# ─────────────────────────────────────────────────────────────────
# BeliefRegistry — per-RuntimeContext registry (NOT module-global)
# ─────────────────────────────────────────────────────────────────

class BeliefRegistry:
    """Registry of SignalBeliefTracker instances, keyed by instrument:timeframe.

    Lifecycle: created with RuntimeContext, destroyed when the runner exits.
    No explicit reset methods needed — lifecycle IS the reset.
    NOT module-global: parallel pytest runs and concurrent BacktestRunners
    each receive an isolated registry.
    """

    def __init__(self, config: dict | None) -> None:
        # The engine_runner.signal_belief section. Validated lazily in get() (see docstring):
        # BacktestRunner wraps registry CONSTRUCTION in a try/except that degrades to a fail-open.
        self._config:   dict | None                  = config
        self._trackers: dict[str, SignalBeliefTracker] = {}

    def get(self, instrument: str, timeframe: str) -> SignalBeliefTracker:
        """Return (or lazily create) the tracker for this instrument+timeframe pair.

        Fail-fast (EPIC-84 STORY-84.2): creating a tracker requires ``enabled`` plus every
        behavioral knob in the section — a missing key raises ``ConfigKeyMissingError`` naming
        it (no ``.get("enabled", False)`` literal, no class defaults). Validating here rather
        than in ``__init__`` is deliberate — BacktestRunner wraps registry CONSTRUCTION in a
        try/except that degrades to "belief gate DISABLED", so a constructor raise would be
        swallowed into a fail-open. EngineRunner calls this only when its own
        ``signal_belief.enabled`` is true, outside that guard, so the error is fatal.
        """
        key = f"{instrument}:{timeframe}"
        if key not in self._trackers:
            cfg = require_all(
                self._config, ("enabled",) + SignalBeliefTracker._REQUIRED_KEYS,
                section_name="engine_runner.signal_belief", consumer="BeliefRegistry",
            )
            self._trackers[key] = SignalBeliefTracker(cfg)
        return self._trackers[key]

    def __len__(self) -> int:
        return len(self._trackers)


# ─────────────────────────────────────────────────────────────────
# RuntimeContext — owned by BacktestRunner / LiveRunner
# ─────────────────────────────────────────────────────────────────

@dataclass
class RuntimeContext:
    """Lifecycle container for all per-run runtime state.

    Owned by BacktestRunner / LiveRunner.  Passed into EngineRunner via
    context["belief_registry"] each candle.

    EngineRunner reads from RuntimeContext — it never creates or owns state.

    Future extension point: add regime_tracker, drift_state, etc. here
    rather than as module-global singletons.
    """
    belief_registry: BeliefRegistry
