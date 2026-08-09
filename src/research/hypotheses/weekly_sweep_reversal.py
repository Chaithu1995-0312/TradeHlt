"""weekly_sweep_reversal.py — Program 8 economic consumer of the weekly liquidity-sweep ontology.

The ICT/CRT weekly liquidity theory: Monday+Tuesday form an accumulation range; Wed-Fri is a
sweep of that range (a stop-hunt) followed by the real directional move in the OPPOSITE
direction of the sweep (the classic "judas swing" / stop-hunt-then-reverse reading — matching
`config_layer.crt_engine_v2.RangeDetector.detect_sweep`'s own `short-on-high-sweep /
long-on-low-sweep` convention). This is the ONLY consumer built in Program 8's first pass; a
continuation variant is explicitly out of scope (see the pre-registration doc).

Flows through the IDENTICAL frozen machinery (forward_walk intrabar_fixed + CostModel +
the M4 QualificationGate) as every other Edge Discovery hypothesis. Per the Authority Ladder
(CLAUDE.md §6.5) it earns NO authority unless the gate PROMOTEs it. Pure, no-lookahead:
detect() reads only `window`.

Exit geometry is RANGE-WIDTH-DERIVED (target the opposite boundary of the swept weekly
range), not a flat ATR multiple — this is the one place Program 8's research config diverges
from the FX toy-family pattern (`apply_signal_defaults: false`, see the config's `_doc`).

The Direction x Volatility 3x3 diagnostic (see the driver script) uses a SPLIT-AXIS encoding
deliberately different from `CandleStateEncoder`'s own bundled `.vol` field: `.vol` classifies
from a single bar's true range against a short (14-bar) trailing ATR — local/noisy, not a
macro-liquidity baseline. The volatility axis here instead uses `RegimeLabeler`
(`interpreters.regime_observer`) constructed with a WIDENED `tercile_window` (config-driven,
not RegimeLabeler's own 480-bar default) to capture genuine macro regime state. Direction
still comes from `CandleStateEncoder` (its 5-state direction axis has no such short-window
problem — it is a per-bar body-ratio classification, not a volatility memory).
"""

from __future__ import annotations

from typing import Sequence

from interpreters.regime_observer import RegimeLabeler
from research.candle_state.encoder import CandleStateEncoder
from research.contracts import Signal
from research.indicators import atr
from research.registry import register_hypothesis
from research.weekly_sweep.weekly_range import (
    _first_sweep_this_week,
    current_week_range,
    detect_weekly_sweep,
    is_week_structurally_valid,
)

SWEEP_WEEKDAYS = (2, 3, 4)   # Wednesday, Thursday, Friday


@register_hypothesis
class WeeklySweepReversal:
    name = "weekly_sweep_reversal"
    family = "structural"
    economic_rationale = (
        "ICT/CRT weekly liquidity theory: Monday+Tuesday accumulation forms a range; a "
        "Wed-Fri sweep of that range's high/low is a stop-hunt, and the real directional "
        "move follows in the OPPOSITE direction of the sweep. Program 8 first-pass reversal "
        "consumer of the weekly-sweep ontology."
    )

    def __init__(
        self,
        min_accumulation_bars: int = 40,
        sl_range_frac: float = 0.25,
        atr_period: int = 14,
        max_intraweek_gap_minutes: float = 30.0,
        regime_tercile_window: int = 2000,
        check_week_validity: bool = False,
        weekly_mask=None,
        holidays=None,
        encoder: CandleStateEncoder | None = None,
        regime_labeler: RegimeLabeler | None = None,
    ):
        # Defaults mirror configs/research/research_config_weekly_sweep.json's `weekly_sweep`
        # block, purely so @register_hypothesis's zero-arg registry instantiation succeeds
        # (matching every other hypothesis's pattern, e.g. CompressionBreakout). The driver
        # script constructs its OWN config-sourced (and per-instrument weekly_mask) instances
        # directly for the actual measurement run — this registered instance is never used
        # for scoring, only for Protocol registration/introspection.
        self.min_accumulation_bars = min_accumulation_bars
        self.sl_range_frac = sl_range_frac
        self.atr_period = atr_period
        self.max_intraweek_gap_minutes = max_intraweek_gap_minutes
        self.check_week_validity = check_week_validity
        self.weekly_mask = weekly_mask
        self.holidays = holidays or set()
        self.encoder = encoder or CandleStateEncoder(atr_period=atr_period)
        self.regime_labeler = regime_labeler or RegimeLabeler(
            atr_period=atr_period, tercile_window=regime_tercile_window
        )

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        bars = list(window)
        if not bars:
            return []
        bar = bars[-1]
        if bar.timestamp.weekday() not in SWEEP_WEEKDAYS:
            return []

        wr = current_week_range(
            bars,
            min_accumulation_bars=self.min_accumulation_bars,
            max_intraweek_gap_minutes=self.max_intraweek_gap_minutes,
        )
        if wr is None:
            return []

        if self.check_week_validity and self.weekly_mask is not None:
            if not is_week_structurally_valid(bars, self.weekly_mask, self.holidays):
                return []

        ev = detect_weekly_sweep(bars, wr)
        if ev is None:
            return []

        if not _first_sweep_this_week(bars, wr, ev.boundary):
            return []

        a = atr(bars, self.atr_period)
        if a <= 0:
            return []

        range_width = wr.h_ref - wr.l_ref
        if range_width <= 0:
            return []

        tp_atr_mult = range_width / a
        sl_atr_mult = self.sl_range_frac * range_width / a
        if sl_atr_mult <= 0:
            return []

        state = self.encoder.encode(bars)
        vol_label = self.regime_labeler.label_at(bars, len(bars) - 1)
        direction_vol_cell = f"{state.direction}/{vol_label}"

        return [Signal(
            instrument=ctx.get("instrument", "UNKNOWN"),
            timestamp=bar.timestamp,
            entry_index=bar.index,
            direction=ev.direction,
            entry=float(bar.close),
            sl_atr_mult=sl_atr_mult,
            tp_atr_mult=tp_atr_mult,
            atr=a,
            meta={
                "boundary": ev.boundary,
                "h_ref": round(wr.h_ref, 6),
                "l_ref": round(wr.l_ref, 6),
                "iso_year": wr.iso_year,
                "iso_week": wr.iso_week,
                "direction_vol_cell": direction_vol_cell,
            },
        )]
