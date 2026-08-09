"""market_shape_hypothesis.py — the semantic Market-Shape layer as a research Hypothesis (P11/B1).

Tests, on a CLEAN substrate, whether the directionally-named Market Shapes carry a directional edge
net of cost through the UNCHANGED M4 gate — the fresh re-derivation of F-023/F-041B (never their
premise). `detect()` is a PURE index lookup against `ShapeSignalSource` (one FeaturePipeline +
classification pass), so it inspects only past+current bars and never re-runs the pipeline per
window (same purity idiom as spine_hypothesis).

CONTAMINATION GUARDS (frozen by the pre-registration):
  * F-022: labels come only from the research forward_walk; `detect()` reads NO stream outcome
    field and FAIL-FASTS if any is injected into `features`/`ctx`.
  * F-051: shape features derive from causal (post-FC1-A) swings; PIT is proven by prefix-invariance
    in tests/test_shape_hypothesis_pit.py.
  * SL/TP geometry is config-authoritative (apply_signal_defaults=true) — the hypothesis SELECTS
    entries+direction only; the shape must earn its keep by SELECTION, not by a bespoke exit.
"""
from __future__ import annotations

from typing import Sequence

from research.contracts import Signal
from research.indicators import atr
from research.registry import register_hypothesis

# Stream-outcome keys that must NEVER reach a pure detector (F-022 leak tripwire).
_FORBIDDEN = ("outcome", "rr_achieved", "mfe", "mae", "rr")


@register_hypothesis
class MarketShapeHypothesis:
    name = "market_shape"
    family = "structural"        # descriptive only — never branched on
    economic_rationale = (
        "semantic_shape_selection: the directionally-named Market Shapes (breakout/structural-"
        "break/liquidity-grab), entered in their declared non-fitted direction, tested for net "
        "expectancy through the M4 gate on clean XAUUSD labels. A clean re-derivation of "
        "F-023/F-041B on a different instrument + a non-KMeans, content-addressed shape method."
    )

    def __init__(self, source=None, atr_period: int = 14):
        self._source = source        # injectable for tests; else lazily the ShapeSignalSource
        self.atr_period = atr_period

    def _ensure_source(self):
        if self._source is None:
            from research.adapters.shape_signal_source import ShapeSignalSource
            self._source = ShapeSignalSource()
        return self._source

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        for k in _FORBIDDEN:                       # F-022 tripwire
            if (features and k in features) or (ctx and k in ctx):
                raise ValueError(
                    f"market_shape_hypothesis: forbidden stream field {k!r} in detect() inputs "
                    "— outcomes must come only from forward_walk (F-022)")
        if not window:
            return []
        bar = window[-1]
        idx = getattr(bar, "index", None)
        if idx is None:
            return []
        instrument = ctx.get("instrument", "UNKNOWN")
        direction = self._ensure_source().signals(instrument).get(idx)
        if direction is None:
            return []

        a = atr(window, self.atr_period)
        if a <= 0:
            a = 1.0
        # sl/tp multiples are placeholders — the runner overwrites them from the config
        # (apply_signal_defaults=true), so geometry is identical across all hypotheses/controls.
        return [Signal(
            instrument=instrument, timestamp=bar.timestamp, entry_index=idx,
            direction=direction, entry=bar.close,
            sl_atr_mult=1.0, tp_atr_mult=2.0, atr=a,
            meta={"shape_direction": direction},
        )]
