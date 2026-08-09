"""story_spec.py — frozen value objects for a deterministic market story.

A StorySpec is a *scripted* market scenario (geometry lives in CODE, per D-23). The story_builder
turns it into an intended_spec + produced_compare + narrative, and the ontology binder validates it
at six layers. Nothing here imports engines or config — pure data (research-isolation safe).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PhaseBar:
    """One scripted M15 event bar. `market_state` is a STRUCTURE-layer ontology state id — the
    ordered structure states drive the story's CRT skeleton path."""

    market_state: str    # structure-layer state id (e.g. "range", "sweep", "displacement", ...)
    note: str
    o: float
    h: float
    low: float
    c: float
    volume: float


@dataclass(frozen=True)
class EntrySignal:
    """The designed trade signal. Entry is one of the phase bars (0-based `entry_rel_index`)."""

    direction: str       # "long" | "short"
    entry_rel_index: int  # index into `StorySpec.phases`
    entry_price: float
    atr: float
    sl_atr_mult: float
    tp_atr_mult: float


@dataclass(frozen=True)
class EntryContract:
    """Designed engine feature contract at entry (NOT random scores — justified by the story).

    Mirrors the design contract in scripts/research/erp_synth_4h_trace.py:_design_engine_features.
    `body_ratio` is derived from the entry bar OHLC (not stored here). mu/sigma are pack constants
    passed as explicit gaussian overrides so no model registry is consulted (determinism)."""

    disp_strength: float
    atr: float
    retest_depth: float
    candles_since_retest: int
    sweep_detected: bool
    double_sweep: bool
    ema_fast: float
    ema_slow: float
    momentum_score: float
    zone_distance: float
    zone_freshness: float
    zone_strength: float
    gauss_mu: float = 0.0
    gauss_sigma: float = 1.0
    score_component_weights: tuple = (0.35, 0.25, 0.20, 0.20)


@dataclass(frozen=True)
class StorySpec:
    """A complete deterministic story + its six-layer expectations."""

    id: str
    family: str
    instrument: str
    story: str                    # one-line narrative
    phases: tuple                 # tuple[PhaseBar, ...]
    signal: EntrySignal
    contract: EntryContract
    # ── six-layer expectations ──────────────────────────────────────────────
    expected_market_states: tuple    # semantic states across all 8 layers (ids)
    expected_crt_states: tuple        # CRTState NAMES, in order (the CRT skeleton walk)
    expected_feature_signature: tuple  # canonical feature names the story exercises
    expected_engine_signature: dict    # {crt,gaussian,zone,rr -> band name}
    expected_outcome: str             # TP_HIT | SL_HIT | TIMEOUT
    expected_rr_min: float = 0.0      # required when outcome == TP_HIT
    # ── generator knobs (warmup shared with erp_synth pattern) ──────────────
    timeframe: str = "M15"
    warmup_bars: int = 32
    base_price: float = 100.0
    range_half: float = 0.30
    meta: dict = field(default_factory=dict)
