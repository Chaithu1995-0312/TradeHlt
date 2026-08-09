"""contracts.py — frozen interfaces for the Edge Discovery Program.

These dataclasses + the Hypothesis Protocol are the stable contract every research
component agrees on. Behavior-agnostic by construction: a continuation hypothesis and
a mean-reversion hypothesis implement the *identical* interface and flow through the
*identical* measurement / qualification machinery. `family` is a descriptive label
used only for meta-analysis grouping — never branched on for control flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # avoid pulling the heavy crt_engine_v2 import at runtime
    from config_layer.crt_engine_v2 import Candle


# ─────────────────────────────────────────────────────────────────
# HYPOTHESIS PROTOCOL  (behavior-agnostic plugin contract)
# ─────────────────────────────────────────────────────────────────
@runtime_checkable
class Hypothesis(Protocol):
    """A market-behavior hypothesis. Pure: no forward data, no I/O in detect().

    detect() returns zero+ candidate Signals for the bar at the *end* of `window`.
    It may only inspect `window` (past + current bar) — never future bars. The
    direction/entry it returns says nothing about *why* the edge should exist; that
    rationale is declared separately so the M4.7 economic gate can reason about it.
    """

    name: str
    family: str               # descriptive only — e.g. "continuation", "mean_reversion"
    economic_rationale: str    # M4.7: declared mechanism; "" => UNEXPLAINED (held with suspicion)

    def detect(self, window: list["Candle"], features: dict, ctx: dict) -> list["Signal"]:
        ...


# ─────────────────────────────────────────────────────────────────
# VALUE OBJECTS
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Signal:
    """A candidate trade event emitted by a hypothesis.

    SL/TP are expressed in ATR multiples (instrument-agnostic, crypto-safe). The
    forward-walk converts them to absolute prices using `atr`.
    """

    instrument: str
    timestamp: datetime
    entry_index: int           # candle .index; forward-walk may only read bars with index > this
    direction: str             # "long" | "short"
    entry: float
    sl_atr_mult: float
    tp_atr_mult: float
    atr: float
    meta: dict = field(default_factory=dict)   # hypothesis telemetry (geometry, thresholds fired)


@dataclass(frozen=True)
class Outcome:
    """Forward-measured result of a Signal. Produced by measurement.forward_walk."""

    signal: Signal
    outcome: str               # TP_HIT | SL_HIT | TIMEOUT
    rr_achieved: float         # realized R (price move / risk_distance)
    mfe: float                 # max favorable excursion, price units (>= 0)
    mae: float                 # max adverse excursion, price units (<= 0)
    duration_candles: int
    time_to_tp: int | None     # bars to first TP touch (None if never reached)
    time_to_failure: int | None  # bars until SL hit, i.e. survival time (None if not SL_HIT)
    reached_1r: bool           # MFE >= 1R before exit — the continuation-probability primitive


@dataclass(frozen=True)
class MetaProfile:
    """M4.5 — answers *where/when* an edge works, to block accidental (lucky) edges."""

    by_regime: dict = field(default_factory=dict)        # {"trending": {"pf":.., "n":..}, ...}
    by_volatility: dict = field(default_factory=dict)
    by_session: dict = field(default_factory=dict)
    by_symbol_class: dict = field(default_factory=dict)
    concentration: float = 0.0   # share of total PnL from the single best slice (high => accidental)
    robust_slices: int = 0       # # slices with PF>1.1 AND n>=min (breadth of the edge)
    verdict_flag: str = "FRAGILE"  # ROBUST | CONCENTRATED | FRAGILE


@dataclass(frozen=True)
class EdgeReport:
    """Aggregated evidence for one hypothesis over an instrument set.

    M1 fills the measurable fields; M4/M4.5/M4.7 fill OOS, significance, meta, rationale,
    and the final verdict. Defaults keep the dataclass constructible at M1.
    """

    hypothesis: str
    instruments: list[str]
    n: int
    wins: int
    losses: int
    win_rate: float                    # all rate/PF/expectancy fields are NET of costs
    profit_factor: float
    expectancy_rr: float
    mfe_p50: float
    mfe_p90: float
    mae_p50: float
    mae_p90: float
    median_time_to_failure: float
    continuation_prob: float           # P(reached_1r)
    max_drawdown_rr: float
    # filled in later milestones --------------------------------------------------
    round_trip_bps: float = 0.0         # cost provenance (set by EdgeAggregator)
    is_metrics: dict = field(default_factory=dict)
    oos_metrics: dict = field(default_factory=dict)
    oos_retention: float = 0.0
    baseline_delta: float = 0.0        # vs the WINNING control
    baseline_name: str = ""             # which control was the benchmark (e.g. "always_long")
    p_value: float = 1.0
    economic_rationale: str = ""        # M4.7
    meta: MetaProfile | None = None     # M4.5 — required before PROMOTE
    verdict: str = "INSUFFICIENT"       # PROMOTE | REJECT | INSUFFICIENT | HUMAN_REVIEW
    reject_reasons: list[str] = field(default_factory=list)
