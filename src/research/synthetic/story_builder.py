"""story_builder.py — turn a StorySpec into an intended-vs-produced golden trace + six-layer binding.

Generalizes scripts/research/erp_synth_4h_trace.py: the warmup pattern, geometry consistency,
designed engine feature contract, closed-form intended scores, and the REAL engine callables are
reused verbatim. Nothing is written to disk here — `build_story()` returns in-memory artifacts;
the driver (scripts/research/story_library_build.py) is the sole writer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from data_ingestion.ohlcv_schema import require_ohlcv_columns, validate_ohlcv_frame
from engines.crt_engine import compute as crt_compute
from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
from engines.rr_engine import RREngine
from engines.scoring_engine import compute_scores
from engines.zone_gate_engine import _compute_soft_zone_score
from features.candle_math import body_ratio as cm_body_ratio
from features.feature_schema import CANONICAL_FEATURES
from research.contracts import Signal
from research.measurement.forward_walk import forward_walk
from research.synthetic.ontology import StoryOntology
from research.synthetic.story_spec import StorySpec

_START = datetime(2024, 6, 1, 0, 0, 0)
_EPS = 1e-9


@dataclass
class _Bar:
    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    phase: str
    note: str


class _FWBar:
    __slots__ = ("index", "high", "low", "close")

    def __init__(self, index: int, high: float, low: float, close: float):
        self.index, self.high, self.low, self.close = index, high, low, close


def _ohlc(o: float, h: float, l: float, c: float) -> tuple[float, float, float, float]:
    hi, lo = max(o, h, l, c), min(o, h, l, c)
    return round(o, 4), round(hi, 4), round(lo, 4), round(c, 4)


def build_bars(spec: StorySpec) -> list[_Bar]:
    """Warmup (deterministic oscillation about base_price — same pattern as erp_synth) + event bars."""
    bars: list[_Bar] = []
    ts = _START
    for i in range(spec.warmup_bars):
        if i % 2 == 0:
            o, c = spec.base_price - 0.05, spec.base_price + 0.05
        else:
            o, c = spec.base_price + 0.05, spec.base_price - 0.05
        o, h, l, c = _ohlc(o, max(o, c) + spec.range_half, min(o, c) - spec.range_half, c)
        bars.append(_Bar(i, ts, o, h, l, c, 1000.0 + i, "warmup", "indicator window"))
        ts += timedelta(minutes=15)
    for j, ph in enumerate(spec.phases):
        o, h, l, c = _ohlc(ph.o, ph.h, ph.low, ph.c)
        bars.append(_Bar(spec.warmup_bars + j, ts, o, h, l, c, float(ph.volume),
                         ph.market_state, ph.note))
        ts += timedelta(minutes=15)
    return bars


def bars_to_df(bars: list[_Bar]) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [b.timestamp.strftime("%Y-%m-%d %H:%M:%S") for b in bars],
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    })


def _design_features(spec: StorySpec, entry_bar: _Bar) -> dict[str, Any]:
    c = spec.contract
    return {
        "open": entry_bar.open, "high": entry_bar.high, "low": entry_bar.low, "close": entry_bar.close,
        "body_ratio": float(cm_body_ratio(entry_bar.open, entry_bar.high, entry_bar.low, entry_bar.close)),
        "disp_strength": float(c.disp_strength), "atr": float(c.atr),
        "retest_depth": float(c.retest_depth), "candles_since_retest": int(c.candles_since_retest),
        "sweep_detected": bool(c.sweep_detected), "double_sweep": bool(c.double_sweep),
        "ema_fast": float(c.ema_fast), "ema_slow": float(c.ema_slow),
        "momentum_score": float(c.momentum_score),
        "zone_distance": float(c.zone_distance), "zone_freshness": float(c.zone_freshness),
        "zone_strength": float(c.zone_strength),
        "score_component_weights": list(c.score_component_weights),
    }


def _intended_scores(spec: StorySpec, feats: dict[str, Any]) -> dict[str, float]:
    c = spec.contract
    crt_parts = compute_scores(
        body_ratio=float(feats["body_ratio"]), move=float(feats["disp_strength"]),
        atr=float(feats["atr"]), retest_depth=float(feats["retest_depth"]),
        candles_since_retest=int(feats["candles_since_retest"]),
        sweep_detected=bool(feats["sweep_detected"]), double_sweep=bool(feats["double_sweep"]),
        score_weights=tuple(feats["score_component_weights"]),
    )
    hi, lo, cl = float(feats["high"]), float(feats["low"]), float(feats["close"])
    rng = hi - lo
    rr = 0.0 if rng <= _EPS else round(max((hi - cl) / rng, (cl - lo) / rng), 4)
    zone = float(_compute_soft_zone_score(
        {"zone_distance": feats["zone_distance"], "zone_freshness": feats["zone_freshness"],
         "zone_strength": feats["zone_strength"]}))
    ema_diff = (float(feats["ema_fast"]) - float(feats["ema_slow"])) / float(feats["ema_slow"])
    x = (ema_diff + math.tanh(float(feats["momentum_score"]))) / 2.0
    g = math.exp(-((x - c.gauss_mu) ** 2) / (2 * c.gauss_sigma ** 2))
    return {"crt": round(float(crt_parts["final"]), 4), "gaussian": round(g, 4),
            "zone": round(zone, 6), "rr": rr}


def _produced_scores(spec: StorySpec, feats: dict[str, Any], entry_bar: _Bar) -> dict[str, float]:
    c = spec.contract
    crt_out = crt_compute(spec.id, {
        "body_ratio": feats["body_ratio"], "disp_strength": feats["disp_strength"],
        "atr": feats["atr"], "retest_depth": feats["retest_depth"],
        "candles_since_retest": feats["candles_since_retest"],
        "sweep_detected": feats["sweep_detected"], "double_sweep": feats["double_sweep"],
    }, {"score_component_weights": list(c.score_component_weights)})
    rr_out = RREngine({}).compute(
        {"open": entry_bar.open, "high": entry_bar.high, "low": entry_bar.low, "close": entry_bar.close})
    zone = float(_compute_soft_zone_score(
        {"zone_distance": feats["zone_distance"], "zone_freshness": feats["zone_freshness"],
         "zone_strength": feats["zone_strength"]}))
    g_engine = HeuristicGaussianEngine(
        {"gaussian_mu": c.gauss_mu, "gaussian_sigma": c.gauss_sigma}, instrument=spec.instrument,
        preload_registry=False)
    g_input = {k: 0.0 for k in CANONICAL_FEATURES}
    g_input["ema_fast"], g_input["ema_slow"] = float(c.ema_fast), float(c.ema_slow)
    g_input["momentum_score"] = float(c.momentum_score)
    g_out = g_engine.compute(g_input, direction=spec.signal.direction)
    return {"crt": round(float(crt_out.get("score", 0.0)), 4),
            "gaussian": round(float(g_out.get("score", 0.0)), 4),
            "zone": round(zone, 6), "rr": round(float(rr_out.get("score", 0.0)), 4)}


def build_story(spec: StorySpec, ontology: StoryOntology | None = None) -> dict[str, Any]:
    """Build the full intended-vs-produced trace + six-layer ontology binding for one story."""
    onto = ontology or StoryOntology()
    bars = build_bars(spec)
    df = bars_to_df(bars)
    entry_abs = spec.warmup_bars + spec.signal.entry_rel_index
    entry_bar = bars[entry_abs]

    feats = _design_features(spec, entry_bar)
    intended = _intended_scores(spec, feats)
    produced = _produced_scores(spec, feats, entry_bar)

    # schema
    try:
        require_ohlcv_columns(df.columns)
        validate_ohlcv_frame(df)
        schema_pass = True
    except Exception:  # noqa: BLE001 — schema failure is a critical check, recorded not raised
        schema_pass = False

    # outcome via the governing forward_walk kernel
    sig = Signal(instrument=spec.instrument, timestamp=entry_bar.timestamp, entry_index=entry_abs,
                 direction=spec.signal.direction, entry=float(spec.signal.entry_price),
                 sl_atr_mult=float(spec.signal.sl_atr_mult), tp_atr_mult=float(spec.signal.tp_atr_mult),
                 atr=float(spec.signal.atr), meta={"story": spec.id})
    future = [_FWBar(b.index, b.high, b.low, b.close) for b in bars if b.index > entry_abs]
    outcome = forward_walk(sig, future, max_forward=40, exit_model="intrabar_fixed")

    engines_match = {e: math.isclose(produced[e], intended[e], abs_tol=1e-4 if e != "zone" else 1e-5)
                     for e in ("crt", "gaussian", "zone", "rr")}
    row_count_match = len(df) == spec.warmup_bars + len(spec.phases)
    outcome_match = outcome.outcome == spec.expected_outcome
    rr_ok = spec.expected_outcome != "TP_HIT" or (outcome.rr_achieved + _EPS >= spec.expected_rr_min)
    all_critical_pass = bool(schema_pass and row_count_match and outcome_match and rr_ok
                             and all(engines_match.values()))

    binding = onto.bind(spec, produced, outcome.outcome, outcome.rr_achieved)

    sl_price = spec.signal.entry_price + (
        -1 if spec.signal.direction == "long" else 1) * spec.signal.sl_atr_mult * spec.signal.atr
    tp_price = spec.signal.entry_price + (
        1 if spec.signal.direction == "long" else -1) * spec.signal.tp_atr_mult * spec.signal.atr

    return {
        "id": spec.id, "family": spec.family, "instrument": spec.instrument,
        "story": spec.story, "timeframe": spec.timeframe,
        "warmup_bars": spec.warmup_bars, "event_bars": len(spec.phases),
        "entry_index": entry_abs, "direction": spec.signal.direction,
        "geometry": {"entry": spec.signal.entry_price, "atr": spec.signal.atr,
                     "sl_price": round(sl_price, 4), "tp_price": round(tp_price, 4),
                     "sl_atr_mult": spec.signal.sl_atr_mult, "tp_atr_mult": spec.signal.tp_atr_mult},
        "engines_intended": intended,
        "engines_produced": produced,
        "engines_match": engines_match,
        "outcome": {"outcome": outcome.outcome, "rr_achieved": outcome.rr_achieved,
                    "time_to_tp": outcome.time_to_tp, "time_to_failure": outcome.time_to_failure,
                    "duration_candles": outcome.duration_candles,
                    "mfe": outcome.mfe, "mae": outcome.mae},
        "checks": {"schema_pass": schema_pass, "row_count_match": row_count_match,
                   "outcome_match": outcome_match, "rr_ok": rr_ok},
        "all_critical_pass": all_critical_pass,
        "ontology_binding": binding,
        "df": df,
        "bars": [{"index": b.index, "timestamp": b.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                  "open": b.open, "high": b.high, "low": b.low, "close": b.close,
                  "volume": b.volume, "phase": b.phase, "note": b.note} for b in bars],
    }
