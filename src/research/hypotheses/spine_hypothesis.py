"""spine_hypothesis.py — the production spine, wrapped as a research Hypothesis.

This is the "backconstruction": instead of a toy detector, the hypothesis IS the full
8-layer production decision spine. Its `detect()` is a PURE lookup against entries the
`SpineSignalSource` committed in a single deterministic backtest pass — so the stateful
spine runs exactly once (not re-run per 64-bar window), and detect() satisfies the
research purity/no-lookahead contract.

It plugs into the UNCHANGED research machinery (HypothesisRunner forward-walk, EdgeAggregator,
the 7-gate QualificationGate, and forensics.py): every one of those already speaks `Signal`,
so the spine is now measured under the identical brutal truth standard the toy hypotheses
faced — intrabar_fixed exits, 12 bps cost, beats-control, OOS retention, permutation + BH.

GEOMETRY: the spine plans absolute prices, not ATR multiples. We compute the research ATR
over the window (the same `indicators.atr` the toy hypotheses use) and express the spine's
SL/TP as multiples of it — `risk_distance = sl_atr_mult * atr` round-trips byte-exact while
the multiple is comparable across hypotheses (and keeps forensics' ATR-normalized trend
proxy meaningful). Requires `apply_signal_defaults=false` in the spine config so the runner
does not overwrite these multiples.
"""

from __future__ import annotations

from typing import Sequence

from research.contracts import Signal
from research.indicators import atr
from research.registry import register_hypothesis


@register_hypothesis
class SpineHypothesis:
    name = "spine"
    family = "composite"   # non-control candidate; descriptive only (never branched on)
    economic_rationale = (
        "production_spine_composite: the live CRT/Gaussian/ZoneGate/RR → Fusion → "
        "RegimeGovernor → Decision → ExecutionPlanner → UltronRiskGate stack. Measured "
        "here under the research truth standard to test whether the composite system "
        "produces a qualified edge, or dies under honest exits + cost + controls."
    )

    def __init__(self, source=None, atr_period: int = 14):
        # `source` is injectable for tests (a canned SpineSignalSource); in production it is
        # the lazily-built ProductionSpineSource (runs the real backtest on first use).
        self._source = source
        self.atr_period = atr_period

    def _ensure_source(self):
        if self._source is None:
            from research.adapters.spine_signal_source import ProductionSpineSource
            self._source = ProductionSpineSource()
        return self._source

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        if not window:
            return []
        bar = window[-1]
        idx = getattr(bar, "index", None)
        if idx is None:
            return []

        instrument = ctx.get("instrument", "UNKNOWN")
        entries = self._ensure_source().entries(instrument)
        e = entries.get(idx)
        if e is None:
            return []

        # Alignment cross-check: catch any INDEX-CONTRACT (off-by-one) regression early.
        if e.timestamp and str(bar.timestamp) != e.timestamp:
            ts = getattr(bar, "timestamp", None)
            if ts is not None and ts.isoformat() != e.timestamp:
                raise ValueError(
                    f"spine entry index/timestamp mismatch at idx={idx}: "
                    f"window={getattr(bar, 'timestamp', None)} entry={e.timestamp}")

        a = atr(window, self.atr_period)
        if a > 0:
            sl_mult = e.risk_distance / a
            tp_mult = e.reward_distance / a
        else:
            # Degenerate window (no range): fall back to absolute distances (atr unit = 1.0).
            a = 1.0
            sl_mult = e.risk_distance
            tp_mult = e.reward_distance

        return [Signal(
            instrument=instrument, timestamp=bar.timestamp, entry_index=idx,
            direction=e.direction, entry=e.entry,
            sl_atr_mult=sl_mult, tp_atr_mult=tp_mult, atr=a,
            meta={
                "spine_sl": e.meta.get("sl"), "spine_tp1": e.meta.get("tp1"),
                "spine_risk_distance": round(e.risk_distance, 8),
                "spine_reward_distance": round(e.reward_distance, 8),
                "backtest_exit_reason": e.meta.get("backtest_exit_reason"),
                "risk_score": e.meta.get("risk_score"),
            },
        )]
