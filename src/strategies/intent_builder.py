"""
intent_builder.py
================================================================================
StrategyIntentBuilder — central adapter that converts any StrategyResult into
a StrategyIntent without modifying individual strategy files.

Design:
  - ALL 10 strategies get a StrategyIntent via this builder.
    No strategy is excluded; no strategy is dominant.
  - builder.build() returns None only for NO_TRADE signals.
  - If r.intent_obj is already set (self-explaining strategy), it is returned
    as-is (builder-as-fallback pattern).
  - r.capabilities: frozenset[str] (emitted by the strategy result, not a class
    attribute or registry lookup) determines which evidence path is taken.
    Works offline, in batch replay, and in remote workers.
  - MAX_EVIDENCE = 4 caps both CRT-path and generic evidence lists to prevent
    unbounded allocation (~90 strategies × evidence × every candle).
  - strategy_family reduces replay sparsity — family-level expectancy is learned
    before per-strategy expectancy when samples are thin.

Canonical dict key for transition path: "_transition_path"
  (never "_transition_history")
================================================================================
"""

from __future__ import annotations

import hashlib
from typing import Callable, List, Optional, Tuple

from strategies.strategy_intent import InvalidationRule, StrategyIntent  # type: ignore
from strategies.strategy_result import StrategyResult                    # type: ignore


class StrategyIntentBuilder:
    """Converts any StrategyResult → StrategyIntent.

    Instantiate once (e.g. per _aggregate() call or per orchestrator lifetime).
    Thread-safe: stateless after construction.
    """

    _DEFAULT_TTL: int = 3    # candles; matches soft_conf_max_candles
    MAX_EVIDENCE: int = 4    # max evidence items — prevents unbounded allocation

    # Map strategy_id → family label.  Single source of truth — no per-strategy changes.
    _FAMILY_MAP: dict[str, str] = {
        "S1":  "CRT",
        "S2":  "MOMENTUM",
        "S3":  "BREAKOUT",
        "S4":  "STAT_ARB",
        "S5":  "MOMENTUM",
        "S6":  "MOMENTUM",
        "S7":  "SENTIMENT",
        "S8":  "BITNET",
        "S9":  "PATTERN",
        "S10": "ZONE",
    }

    def build(
        self,
        strategy_result: StrategyResult,
        features: dict,
    ) -> Optional[StrategyIntent]:
        """Convert a StrategyResult to a StrategyIntent.

        Returns None only when signal is NO_TRADE (no hypothesis to form).
        If ``strategy_result.intent_obj`` is already populated (self-explaining
        strategy), it is returned directly — builder acts as fallback only.

        Parameters
        ----------
        strategy_result  Output from a strategy's compute() call.
        features         Feature dict for the current candle (may contain
                         ``"_transition_path"`` injected by live_engine_hook).
        """
        r = strategy_result
        if r.signal == "NO_TRADE":
            return None

        # Builder-as-fallback: respect intent already set by the strategy itself.
        if r.intent_obj is not None:
            return r.intent_obj

        direction = 1 if r.signal == "BUY" else -1
        rr = (
            abs((r.tp - r.entry) / (r.entry - r.sl + 1e-9))
            if r.sl != r.entry
            else 0.0
        )

        invalidation   = self._generic_invalidation(r, features)
        evidence_fn, path_hash = self._build_evidence(r, features)

        return StrategyIntent(
            strategy_id       = r.strategy_id,
            strategy_family   = self._FAMILY_MAP.get(r.strategy_id, "UNKNOWN"),
            direction         = direction,
            confidence        = r.confidence,
            invalidation      = invalidation,
            expected_rr       = round(rr, 3),
            ttl               = self._DEFAULT_TTL,
            source_path_hash  = path_hash,
            _evidence_factory = evidence_fn,   # Callable — materialised on .evidence access
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _generic_invalidation(
        self, r: StrategyResult, features: dict
    ) -> List[InvalidationRule]:
        """Geometry-based invalidation applicable to every strategy."""
        atr = float(features.get("atr", 0.001)) or 0.001
        rules: List[InvalidationRule] = []
        if r.signal == "BUY":
            rules.append(InvalidationRule(
                "close", "<", r.entry - atr,
                "price closed below entry - 1×ATR",
            ))
        else:
            rules.append(InvalidationRule(
                "close", ">", r.entry + atr,
                "price closed above entry + 1×ATR",
            ))
        return rules

    def _build_evidence(
        self, r: StrategyResult, features: dict
    ) -> Tuple[Callable[[], List[str]], str]:
        """Return (evidence_factory: Callable, path_hash: str).

        CRT-enriched path is taken when:
          - ``"transition_path"`` is in r.capabilities   AND
          - ``"_transition_path"`` is present + non-empty in features.
        All other strategies use the generic feature-summary path.

        r.capabilities travels WITH the result (frozenset on StrategyResult) —
        no registry lookup, works in offline replay and remote workers.
        """
        transition_path = features.get("_transition_path", [])

        if "transition_path" in r.capabilities and transition_path:
            # path_hash computed eagerly — cheap, and needed for replay grouping.
            # Includes sweep_type + disp_strength to prevent state-name collisions
            # (RANGE→SWEEP is different for TYPE-A vs TYPE-B sweeps).
            path_str = "→".join(
                f"{t.from_state}:{t.to_state}:{t.sweep_type or ''}:{round(t.disp_strength or 0.0, 1)}"
                for t in transition_path
            )
            path_hash = hashlib.sha256(path_str.encode()).hexdigest()[:16]

            # Capture last MAX_EVIDENCE transitions — prevents unbounded allocation
            # for long paths (recent_transition_path() returns up to 16 items).
            _tp = list(transition_path[-self.MAX_EVIDENCE:])
            evidence_fn: Callable[[], List[str]] = lambda: [
                f"{t.from_state}→{t.to_state}:{t.trigger_reason[:40]}"
                for t in _tp
            ]
        else:
            # Generic evidence — captures r by reference, evaluated lazily.
            _r = r
            evidence_fn = lambda: [
                f"intent:{_r.intent}",
                f"regime:{_r.regime}",
                f"score:{round(_r.score, 3)}",
                f"conf:{round(_r.confidence, 3)}",
            ][:self.MAX_EVIDENCE]
            path_hash = ""

        return evidence_fn, path_hash
