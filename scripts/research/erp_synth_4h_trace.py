#!/usr/bin/env python
"""erp_synth_4h_trace.py — intentional synthetic 4h M15 OHLCV + intended-vs-produced trace.

DESIGN (not random):
  - Warmup: 32 x M15 bars of a tight range around 100.00 (for ATR / feature windows).
  - Event window: exactly 16 x M15 bars = 4.0 hours of scripted market structure.
  - One designed LONG opportunity after a liquidity sweep + displacement + retest.
  - Future path is constructed so forward_walk(intrabar_fixed) must hit TP (not SL).
  - Engines: design feature contract at entry → real CRT / Gaussian / Zone-soft / RR scores
    (intended closed-form vs produced engine callables must match).

Outputs under data/synthetic/erp_4h_m15/:
  SYNTH_4H_M15.csv
  intended_spec.json
  produced_compare.json
  TRACE_NARRATIVE.md  (written by this script from the live comparison)

Usage:
  PYTHONPATH=src python scripts/research/erp_synth_4h_trace.py
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from data_ingestion.ohlcv_schema import (  # noqa: E402
    require_ohlcv_columns,
    validate_ohlcv_frame,
)
from engines.crt_engine import compute as crt_compute  # noqa: E402
from engines.heuristic_gaussian_engine import HeuristicGaussianEngine  # noqa: E402
from engines.rr_engine import RREngine  # noqa: E402
from engines.scoring_engine import compute_scores  # noqa: E402
from engines.zone_gate_engine import _compute_soft_zone_score  # noqa: E402
from features.candle_math import body_ratio as cm_body_ratio  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from research.contracts import Signal  # noqa: E402
from research.measurement.forward_walk import forward_walk  # noqa: E402

OUT_DIR = _ROOT / "data" / "synthetic" / "erp_4h_m15"
CSV_PATH = OUT_DIR / "SYNTH_4H_M15.csv"
INTENDED_PATH = OUT_DIR / "intended_spec.json"
PRODUCED_PATH = OUT_DIR / "produced_compare.json"
NARRATIVE_PATH = OUT_DIR / "TRACE_NARRATIVE.md"

# ── Geometry constants (all intentional) ─────────────────────────────────────
INSTRUMENT = "SYNTHUSDT"
TIMEFRAME = "M15"
START = datetime(2024, 6, 1, 0, 0, 0)
WARMUP_BARS = 32          # 8h warmup — not part of the 4h story window
EVENT_BARS = 16           # 4.0 hours @ M15
BASE = 100.0
RANGE_HALF = 0.30         # warmup / early range half-width
SWEEP_LOW = 98.50         # intentional liquidity sweep print
DISP_CLOSE_1 = 102.40
DISP_CLOSE_2 = 103.20
EXPANSION_HIGH = 104.20
RETEST_LOW = 101.40
ENTRY_PRICE = 102.00      # long entry after retest reclaim
DESIGN_ATR = 1.00         # used by the designed Signal (not estimated)
SL_ATR_MULT = 1.0         # SL = 101.00
TP_ATR_MULT = 2.0         # TP = 104.00
# Within event window, indices relative to event start (0..15)
REL_SWEEP = 3
REL_DISP1 = 4
REL_DISP2 = 5
REL_EXP1 = 6
REL_EXP2 = 7
REL_RETEST = 8
REL_ENTRY = 9             # signal bar (entry_index absolute = WARMUP + REL_ENTRY)
# After entry: bars REL_ENTRY+1 .. must not touch 101.00, must touch 104.00

# ── Designed engine feature contract (from story — not random scores) ────────
# Weights match PLAN-002 / scoring_engine default HOW tuple.
SCORE_COMPONENT_WEIGHTS = (0.35, 0.25, 0.20, 0.20)
# Retest mid-pocket → s_retest peaks at retest_depth=0.5 in scoring_engine.
DESIGN_RETEST_DEPTH = 0.5
DESIGN_CANDLES_SINCE_RETEST = 1  # entry is next bar after retest phase
# Soft zone (zone_mode=soft path): near/fresh/strong around retest structure.
DESIGN_ZONE_DISTANCE = 0.10
DESIGN_ZONE_FRESHNESS = 0.90
DESIGN_ZONE_STRENGTH = 0.80
# Heuristic gaussian kernel (mu/sigma fixed for pack determinism — not registry).
DESIGN_GAUSS_MU = 0.0
DESIGN_GAUSS_SIGMA = 1.0
DESIGN_EMA_FAST = 102.50   # post-displacement fast mean
DESIGN_EMA_SLOW = 100.50   # lagging mean near old range
DESIGN_MOMENTUM = 0.80     # bullish thrust after displacement


@dataclass
class Bar:
    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    phase: str
    note: str


def _ohlc(o: float, h: float, l: float, c: float) -> tuple[float, float, float, float]:
    """Enforce high/low consistency."""
    hi = max(o, h, l, c)
    lo = min(o, h, l, c)
    return round(o, 4), round(hi, 4), round(lo, 4), round(c, 4)


def build_bars() -> list[Bar]:
    bars: list[Bar] = []
    ts = START
    idx = 0

    # ── Warmup: alternating micro range about 100 ───────────────────────────
    for i in range(WARMUP_BARS):
        # deliberate 2-bar oscillation — not random
        if i % 2 == 0:
            o, c = BASE - 0.05, BASE + 0.05
        else:
            o, c = BASE + 0.05, BASE - 0.05
        o, h, l, c = _ohlc(o, max(o, c) + RANGE_HALF, min(o, c) - RANGE_HALF, c)
        bars.append(Bar(idx, ts, o, h, l, c, 1000.0 + i, "warmup", "tight range for ATR window"))
        ts += timedelta(minutes=15)
        idx += 1

    event_start_ts = ts
    # last close ~100
    prev_c = bars[-1].close

    # Event relative construction
    plan: list[tuple[str, str, float, float, float, float, float]] = []
    # (phase, note, o, h, l, c, vol)

    # 0-2: continue range at top of morning
    plan.append(("event_range", "range hold pre-sweep", prev_c, 100.35, 99.70, 100.10, 1100))
    plan.append(("event_range", "range hold", 100.10, 100.40, 99.75, 100.05, 1050))
    plan.append(("event_range", "range hold", 100.05, 100.30, 99.80, 100.00, 1000))

    # 3: SWEEP — print SWEEP_LOW, close back inside range
    plan.append(("sweep", "liquidity sweep below range, close reclaimed", 100.00, 100.20, SWEEP_LOW, 99.90, 5000))

    # 4-5: DISPLACEMENT up
    plan.append(("displacement", "impulsive bullish displacement bar 1", 99.90, 102.60, 99.85, DISP_CLOSE_1, 4500))
    plan.append(("displacement", "impulsive bullish displacement bar 2", DISP_CLOSE_1, 103.50, 102.20, DISP_CLOSE_2, 4200))

    # 6-7: EXPANSION / hold highs
    plan.append(("expansion", "expansion print toward design TP zone", DISP_CLOSE_2, EXPANSION_HIGH, 103.00, 103.80, 3000))
    plan.append(("expansion", "hold near highs", 103.80, 104.10, 103.40, 103.70, 2800))

    # 8: RETEST — pullback that does not violate design SL (101)
    plan.append(("retest", "retest pullback above design SL=101", 103.70, 103.75, RETEST_LOW, 101.80, 3500))

    # 9: ENTRY bar — reclaim; designed long entry = ENTRY_PRICE
    plan.append(("entry", "reclaim / designed LONG entry bar", 101.80, 102.40, 101.70, 102.15, 3200))

    # 10: mild adverse — low 101.20 > SL 101.00 (must NOT stop out)
    plan.append(("path", "adverse excursion short of SL", 102.15, 102.30, 101.20, 101.90, 2500))

    # 11-12: recovery
    plan.append(("path", "recovery", 101.90, 102.80, 101.85, 102.60, 2200))
    plan.append(("path", "grind higher", 102.60, 103.40, 102.50, 103.20, 2100))

    # 13: TP touch — high >= 104.00, low > 101 (TP_HIT intended)
    plan.append(("path_tp", "designed TP touch high>=104", 103.20, 104.25, 103.10, 104.05, 4000))

    # 14-15: post-TP noise (forward_walk should already have exited at bar 13 path)
    plan.append(("post", "post-outcome residual bar", 104.05, 104.40, 103.80, 104.10, 1800))
    plan.append(("post", "post-outcome residual bar", 104.10, 104.30, 103.90, 104.00, 1700))

    assert len(plan) == EVENT_BARS, f"event plan length {len(plan)} != {EVENT_BARS}"

    for phase, note, o, h, l, c, vol in plan:
        o, h, l, c = _ohlc(o, h, l, c)
        bars.append(Bar(idx, ts, o, h, l, c, float(vol), phase, note))
        ts += timedelta(minutes=15)
        idx += 1

    assert bars[WARMUP_BARS + REL_SWEEP].phase == "sweep"
    assert bars[WARMUP_BARS + REL_ENTRY].phase == "entry"
    assert abs(bars[WARMUP_BARS + REL_SWEEP].low - SWEEP_LOW) < 1e-9
    return bars


def bars_to_df(bars: list[Bar]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [b.timestamp.strftime("%Y-%m-%d %H:%M:%S") for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )


def _design_engine_features(entry_bar: Bar) -> dict[str, Any]:
    """Feature inputs for engines at entry — derived from scripted geometry.

    Not random: each field is justified by the bar story or explicit design constants.
    """
    br = float(cm_body_ratio(entry_bar.open, entry_bar.high, entry_bar.low, entry_bar.close))
    # Displacement magnitude in price units (sweep low → disp2 close); atr-scaled in scoring.
    disp_move = float(round(DISP_CLOSE_2 - SWEEP_LOW, 4))  # 103.2 - 98.5 = 4.7
    return {
        "open": entry_bar.open,
        "high": entry_bar.high,
        "low": entry_bar.low,
        "close": entry_bar.close,
        "body_ratio": br,
        "disp_strength": disp_move,
        "atr": DESIGN_ATR,
        "retest_depth": DESIGN_RETEST_DEPTH,
        "candles_since_retest": DESIGN_CANDLES_SINCE_RETEST,
        "sweep_detected": True,
        "double_sweep": False,
        "ema_fast": DESIGN_EMA_FAST,
        "ema_slow": DESIGN_EMA_SLOW,
        "momentum_score": DESIGN_MOMENTUM,
        "zone_distance": DESIGN_ZONE_DISTANCE,
        "zone_freshness": DESIGN_ZONE_FRESHNESS,
        "zone_strength": DESIGN_ZONE_STRENGTH,
        "direction": 1,  # LONG
        "score_component_weights": list(SCORE_COMPONENT_WEIGHTS),
        "justification": {
            "sweep_detected": "event phase sweep printed SWEEP_LOW then reclaimed",
            "double_sweep": "only one designed sweep bar",
            "body_ratio": "canonical FM body/range on entry OHLC",
            "disp_strength": "DISP_CLOSE_2 - SWEEP_LOW (price units of thrust)",
            "atr": "DESIGN_ATR of the pack signal",
            "retest_depth": "0.5 = mid-pocket (CRT s_retest peak by design)",
            "candles_since_retest": "entry is one bar after retest phase",
            "ema_fast/slow": "bullish stack after displacement (design seed, not live EMA)",
            "momentum_score": "positive thrust seed consistent with long path",
            "zone_*": "soft-zone near retest structure (not zone_registry lookup)",
        },
    }


def _intended_engine_scores(feats: dict[str, Any]) -> dict[str, Any]:
    """Closed-form intended scores using the same formulas engines use."""
    crt_parts = compute_scores(
        body_ratio=float(feats["body_ratio"]),
        move=float(feats["disp_strength"]),
        atr=float(feats["atr"]),
        retest_depth=float(feats["retest_depth"]),
        candles_since_retest=int(feats["candles_since_retest"]),
        sweep_detected=bool(feats["sweep_detected"]),
        double_sweep=bool(feats["double_sweep"]),
        score_weights=tuple(feats["score_component_weights"]),
    )
    # RR polarity (same as RREngine)
    hi, lo, cl = float(feats["high"]), float(feats["low"]), float(feats["close"])
    rng = hi - lo
    if rng <= 1e-9:
        rr_score = 0.0
    else:
        rr_score = round(max((hi - cl) / rng, (cl - lo) / rng), 4)
    # Soft zone
    zone_score = float(
        _compute_soft_zone_score(
            {
                "zone_distance": feats["zone_distance"],
                "zone_freshness": feats["zone_freshness"],
                "zone_strength": feats["zone_strength"],
            }
        )
    )
    # Heuristic gaussian closed form (mu/sigma pack constants)
    ema_diff = (float(feats["ema_fast"]) - float(feats["ema_slow"])) / float(feats["ema_slow"])
    momentum_norm = math.tanh(float(feats["momentum_score"]))
    x = (ema_diff + momentum_norm) / 2.0
    g_score = math.exp(-((x - DESIGN_GAUSS_MU) ** 2) / (2 * DESIGN_GAUSS_SIGMA**2))

    return {
        "crt": {
            "score": crt_parts["final"],
            "components": {
                "sweep": crt_parts["sweep"],
                "breakout": crt_parts["breakout"],
                "retest": crt_parts["retest"],
                "time": crt_parts["time"],
            },
            "weights": list(SCORE_COMPONENT_WEIGHTS),
        },
        "gaussian": {
            "score": round(g_score, 4),
            "mu": DESIGN_GAUSS_MU,
            "sigma": DESIGN_GAUSS_SIGMA,
            "x": round(x, 6),
            "kernel": "heuristic_exp",
        },
        "zone_gate": {
            "score": round(zone_score, 6),
            "mode": "soft_designed",
            "passed": zone_score >= 0.25,  # informational only for pack
            "inputs": {
                "zone_distance": DESIGN_ZONE_DISTANCE,
                "zone_freshness": DESIGN_ZONE_FRESHNESS,
                "zone_strength": DESIGN_ZONE_STRENGTH,
            },
        },
        "rr": {
            "score": rr_score,
            "semantic": "candle_structure_quality",
            "note": "polarity index, not true RR (F-048 class)",
        },
        "EXPECTED_ENGINES": sorted(["crt", "gaussian", "zone_gate", "rr"]),
    }


def intended_spec(bars: list[Bar]) -> dict[str, Any]:
    entry_abs = WARMUP_BARS + REL_ENTRY
    entry_bar = bars[entry_abs]
    sl_price = ENTRY_PRICE - SL_ATR_MULT * DESIGN_ATR
    tp_price = ENTRY_PRICE + TP_ATR_MULT * DESIGN_ATR
    # forward_walk uses 1-based duration: first future bar => time_to_tp=1
    tp_rel = None
    for j, b in enumerate(bars[entry_abs + 1 :]):
        if b.high >= tp_price:
            tp_rel = j + 1
            break

    engine_feats = _design_engine_features(entry_bar)
    engines_intended = _intended_engine_scores(engine_feats)

    return {
        "schema_version": "1.0",
        "instrument": INSTRUMENT,
        "timeframe": TIMEFRAME,
        "design_principle": "deterministic_scripted_geometry_not_random",
        "warmup_bars": WARMUP_BARS,
        "event_bars": EVENT_BARS,
        "event_hours": EVENT_BARS * 0.25,
        "start_timestamp": START.isoformat(sep=" "),
        "event_start_timestamp": bars[WARMUP_BARS].timestamp.isoformat(sep=" "),
        "event_end_timestamp": bars[-1].timestamp.isoformat(sep=" "),
        "price_base": BASE,
        "geometry": {
            "sweep_low": SWEEP_LOW,
            "displacement_closes": [DISP_CLOSE_1, DISP_CLOSE_2],
            "expansion_high": EXPANSION_HIGH,
            "retest_low": RETEST_LOW,
            "entry_price": ENTRY_PRICE,
            "design_atr": DESIGN_ATR,
            "sl_atr_mult": SL_ATR_MULT,
            "tp_atr_mult": TP_ATR_MULT,
            "sl_price": sl_price,
            "tp_price": tp_price,
        },
        "signal_intended": {
            "direction": "long",
            "entry_index": entry_abs,
            "entry_timestamp": entry_bar.timestamp.isoformat(sep=" "),
            "entry": ENTRY_PRICE,
            "atr": DESIGN_ATR,
            "sl_atr_mult": SL_ATR_MULT,
            "tp_atr_mult": TP_ATR_MULT,
            "meta": {
                "story": "sweep→displacement→expansion→retest→entry",
                "rel_indices": {
                    "sweep": REL_SWEEP,
                    "disp1": REL_DISP1,
                    "retest": REL_RETEST,
                    "entry": REL_ENTRY,
                },
            },
        },
        "outcome_intended": {
            "exit_model": "intrabar_fixed",
            "outcome": "TP_HIT",
            "tp_touch_bar_offset": tp_rel,
            "must_not_touch_sl_before_tp": True,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "expected_rr_achieved_min": 2.0 - 1e-6,
        },
        "engines_feature_contract": engine_feats,
        "engines_intended": engines_intended,
        "topic_intended_transforms": _topic_intendeds(
            sl_price, tp_price, entry_abs, tp_rel, engines_intended
        ),
        "bars": [
            {
                "index": b.index,
                "timestamp": b.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "phase": b.phase,
                "note": b.note,
            }
            for b in bars
        ],
    }


def _topic_intendeds(
    sl_price: float,
    tp_price: float,
    entry_abs: int,
    tp_rel: int | None,
    engines_intended: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eng = engines_intended or {}
    return {
        "market_data": {
            "in": "scripted generator constants",
            "out": f"{WARMUP_BARS + EVENT_BARS} OHLCV rows CSV schema timestamp,open,high,low,close,volume",
        },
        "schema_validation": {
            "in": "CSV frame",
            "out": "PASS validate_ohlcv_frame (no NaN, hi/lo consistent, vol>=0)",
        },
        "features_candle_math": {
            "in": "each bar OHLC",
            "out": "body_ratio in [0,1]; entry bar body_ratio computed from open/close/range",
        },
        "events_opportunity_seed": {
            "in": "event geometry phases",
            "out": f"one designed LONG Signal at entry_index={entry_abs} entry={ENTRY_PRICE}",
            "note": "CRT engine not required to emit this seed — seed is design-injected for factory trace",
        },
        "engines_evidence": {
            "in": "engines_feature_contract at entry (geometry-derived + design seeds)",
            "out": {
                "crt": eng.get("crt", {}).get("score"),
                "gaussian": eng.get("gaussian", {}).get("score"),
                "zone_gate": eng.get("zone_gate", {}).get("score"),
                "rr": eng.get("rr", {}).get("score"),
            },
            "note": "scores from real engine formulas; features designed from story, not random",
        },
        "fusion_decision": {
            "in": "N/A",
            "out": "N/A — research lens isolation; no fusion claim",
        },
        "plan_risk": {
            "in": "Signal SL/TP ATR mults",
            "out": f"absolute SL={sl_price} TP={tp_price} from design ATR",
        },
        "execution": {
            "in": "N/A dry path",
            "out": "no broker call in this pack",
        },
        "outcome_forward_walk": {
            "in": "Signal + bars after entry_index",
            "out": f"TP_HIT at offset={tp_rel}, rr_achieved≈2.0, exit_model=intrabar_fixed",
        },
        "test_harness": {
            "in": "this script as producer",
            "out": "intended_spec.json + produced_compare.json for H1/H2/H3 comparison",
        },
    }


class _FWBar:
    __slots__ = ("index", "high", "low", "close")

    def __init__(self, index: int, high: float, low: float, close: float):
        self.index = index
        self.high = high
        self.low = low
        self.close = close


def produce_compare(bars: list[Bar], intended: dict[str, Any]) -> dict[str, Any]:
    df = bars_to_df(bars)
    produced: dict[str, Any] = {
        "run_at": datetime.now().astimezone().isoformat(),
        "csv_path": str(CSV_PATH.relative_to(_ROOT)).replace("\\", "/"),
        "checks": {},
        "topic_produced": {},
        "compare": {},
    }

    # ── schema ──────────────────────────────────────────────────────────────
    try:
        require_ohlcv_columns(df.columns)
        validate_ohlcv_frame(df)
        produced["checks"]["schema"] = {"ok": True, "n_rows": len(df)}
    except Exception as e:
        produced["checks"]["schema"] = {"ok": False, "error": str(e)}

    # ── load counts ─────────────────────────────────────────────────────────
    produced["checks"]["row_count"] = {
        "ok": len(df) == WARMUP_BARS + EVENT_BARS,
        "n": len(df),
        "expected": WARMUP_BARS + EVENT_BARS,
    }
    produced["checks"]["event_hours"] = {
        "ok": True,
        "hours": EVENT_BARS * 0.25,
        "bars": EVENT_BARS,
    }

    # ── candle math on entry bar ────────────────────────────────────────────
    entry_abs = intended["signal_intended"]["entry_index"]
    eb = bars[entry_abs]
    rng = eb.high - eb.low
    body = abs(eb.close - eb.open)
    br_manual = (body / rng) if rng > 0 else 0.0
    br = float(cm_body_ratio(eb.open, eb.high, eb.low, eb.close))
    produced["topic_produced"]["features_candle_math"] = {
        "entry_index": entry_abs,
        "range": rng,
        "body": body,
        "body_ratio_manual_body_over_range": br_manual,
        "body_ratio_module": br,
        "body_ratio_match": math.isclose(br, br_manual, abs_tol=1e-12),
    }

    # ── designed signal + forward_walk ──────────────────────────────────────
    sig = Signal(
        instrument=INSTRUMENT,
        timestamp=bars[entry_abs].timestamp,
        entry_index=entry_abs,
        direction="long",
        entry=float(intended["signal_intended"]["entry"]),
        sl_atr_mult=float(intended["signal_intended"]["sl_atr_mult"]),
        tp_atr_mult=float(intended["signal_intended"]["tp_atr_mult"]),
        atr=float(intended["signal_intended"]["atr"]),
        meta=dict(intended["signal_intended"]["meta"]),
    )
    future = [
        _FWBar(b.index, b.high, b.low, b.close)
        for b in bars
        if b.index > entry_abs
    ]
    outcome = forward_walk(sig, future, max_forward=40, exit_model="intrabar_fixed")
    produced["topic_produced"]["outcome_forward_walk"] = {
        "outcome": outcome.outcome,
        "rr_achieved": outcome.rr_achieved,
        "mfe": outcome.mfe,
        "mae": outcome.mae,
        "duration_candles": outcome.duration_candles,
        "time_to_tp": outcome.time_to_tp,
        "time_to_failure": outcome.time_to_failure,
        "reached_1r": outcome.reached_1r,
    }
    produced["topic_produced"]["plan_risk"] = {
        "sl_price": sig.entry - sig.sl_atr_mult * sig.atr,
        "tp_price": sig.entry + sig.tp_atr_mult * sig.atr,
    }
    produced["topic_produced"]["events_opportunity_seed"] = {
        "signal": {
            "instrument": sig.instrument,
            "entry_index": sig.entry_index,
            "direction": sig.direction,
            "entry": sig.entry,
            "atr": sig.atr,
            "sl_atr_mult": sig.sl_atr_mult,
            "tp_atr_mult": sig.tp_atr_mult,
        }
    }

    # ── geometric guards on path ────────────────────────────────────────────
    sl_p = produced["topic_produced"]["plan_risk"]["sl_price"]
    tp_p = produced["topic_produced"]["plan_risk"]["tp_price"]
    touched_sl_before_tp = False
    tp_offset = None
    for j, b in enumerate(bars[entry_abs + 1 :]):
        hit_sl = b.low <= sl_p
        hit_tp = b.high >= tp_p
        if hit_sl and not hit_tp:
            touched_sl_before_tp = True
            break
        if hit_sl and hit_tp:
            # conservative SL-first in same bar — would be SL_HIT
            touched_sl_before_tp = True
            break
        if hit_tp:
            tp_offset = j
            break

    produced["checks"]["path_geometry"] = {
        "touched_sl_before_tp": touched_sl_before_tp,
        "tp_offset_observed": tp_offset,
        "sweep_low_observed": bars[WARMUP_BARS + REL_SWEEP].low,
        "retest_low_observed": bars[WARMUP_BARS + REL_RETEST].low,
    }

    # ── engines (designed features → real engine callables) ─────────────────
    feats = dict(intended["engines_feature_contract"])
    feats.pop("justification", None)
    weights = list(feats["score_component_weights"])

    crt_out = crt_compute(
        "SYNTH_4H",
        {
            "body_ratio": feats["body_ratio"],
            "disp_strength": feats["disp_strength"],
            "atr": feats["atr"],
            "retest_depth": feats["retest_depth"],
            "candles_since_retest": feats["candles_since_retest"],
            "sweep_detected": feats["sweep_detected"],
            "double_sweep": feats["double_sweep"],
        },
        {"score_component_weights": weights},
    )
    rr_out = RREngine({}).compute(
        {
            "open": feats["open"],
            "high": feats["high"],
            "low": feats["low"],
            "close": feats["close"],
        }
    )
    zone_out_score = float(
        _compute_soft_zone_score(
            {
                "zone_distance": feats["zone_distance"],
                "zone_freshness": feats["zone_freshness"],
                "zone_strength": feats["zone_strength"],
            }
        )
    )
    g_engine = HeuristicGaussianEngine(
        {"mu": DESIGN_GAUSS_MU, "sigma": DESIGN_GAUSS_SIGMA},
        instrument=INSTRUMENT,
        preload_registry=False,
    )
    g_input = {k: 0.0 for k in CANONICAL_FEATURES}
    g_input["ema_fast"] = float(feats["ema_fast"])
    g_input["ema_slow"] = float(feats["ema_slow"])
    g_input["momentum_score"] = float(feats["momentum_score"])
    g_out = g_engine.compute(g_input, direction="long")

    produced["topic_produced"]["engines_evidence"] = {
        "status": "RUN",
        "feature_contract_keys": sorted(
            k for k in intended["engines_feature_contract"] if k != "justification"
        ),
        "crt": {"score": float(crt_out.get("score", 0.0)), "raw": crt_out},
        "gaussian": {
            "score": float(g_out.get("score", 0.0)),
            "reason": g_out.get("reason"),
            "meta": g_out.get("meta", {}),
        },
        "zone_gate": {
            "score": round(zone_out_score, 6),
            "mode": "soft_designed",
            "passed": zone_out_score >= 0.25,
        },
        "rr": {
            "score": float(rr_out.get("score", 0.0)),
            "candle_polarity": rr_out.get("candle_polarity"),
            "semantic": rr_out.get("semantic"),
            "reason": rr_out.get("reason"),
        },
    }

    ei = intended["engines_intended"]
    ep = produced["topic_produced"]["engines_evidence"]
    eng_match = {
        "crt": math.isclose(ep["crt"]["score"], ei["crt"]["score"], abs_tol=1e-4),
        "gaussian": math.isclose(
            ep["gaussian"]["score"], ei["gaussian"]["score"], abs_tol=1e-4
        ),
        "zone_gate": math.isclose(
            ep["zone_gate"]["score"], ei["zone_gate"]["score"], abs_tol=1e-5
        ),
        "rr": math.isclose(ep["rr"]["score"], ei["rr"]["score"], abs_tol=1e-4),
    }

    # ── intended vs produced ────────────────────────────────────────────────
    oi = intended["outcome_intended"]
    op = produced["topic_produced"]["outcome_forward_walk"]
    produced["compare"] = {
        "schema_pass": produced["checks"]["schema"].get("ok"),
        "row_count_match": produced["checks"]["row_count"]["ok"],
        "outcome_match": op["outcome"] == oi["outcome"],
        "outcome_intended": oi["outcome"],
        "outcome_produced": op["outcome"],
        "tp_offset_intended": oi["tp_touch_bar_offset"],
        "tp_offset_produced": op["time_to_tp"],
        "rr_produced": op["rr_achieved"],
        "rr_intended_min": oi["expected_rr_achieved_min"],
        "rr_ok": op["rr_achieved"] + 1e-9 >= oi["expected_rr_achieved_min"],
        "tp_offset_match": op["time_to_tp"] == oi["tp_touch_bar_offset"],
        "sl_not_hit_first": not touched_sl_before_tp,
        "sweep_low_match": math.isclose(
            bars[WARMUP_BARS + REL_SWEEP].low, SWEEP_LOW, abs_tol=1e-9
        ),
        "engines_match": eng_match,
        "engines_all_match": all(eng_match.values()),
        "engines_intended_scores": {
            "crt": ei["crt"]["score"],
            "gaussian": ei["gaussian"]["score"],
            "zone_gate": ei["zone_gate"]["score"],
            "rr": ei["rr"]["score"],
        },
        "engines_produced_scores": {
            "crt": ep["crt"]["score"],
            "gaussian": ep["gaussian"]["score"],
            "zone_gate": ep["zone_gate"]["score"],
            "rr": ep["rr"]["score"],
        },
        "all_critical_pass": False,  # set below
    }
    c = produced["compare"]
    c["all_critical_pass"] = bool(
        c["schema_pass"]
        and c["row_count_match"]
        and c["outcome_match"]
        and c["rr_ok"]
        and c["tp_offset_match"]
        and c["sl_not_hit_first"]
        and c["sweep_low_match"]
        and c["engines_all_match"]
    )

    # topics not executed (honest N/A — do not invent)
    for topic in (
        "fusion_decision",
        "execution_mt5",
        "qualification_m4",
        "promotion",
        "control_plane_ui",
        "binance_live",
        "oi_positioning",
    ):
        produced["topic_produced"][topic] = {
            "status": "NOT_RUN",
            "reason": "out of scope for this pack; no hallucinated outputs",
        }

    return produced


def write_narrative(intended: dict[str, Any], produced: dict[str, Any]) -> str:
    c = produced["compare"]
    lines = [
        "# Synthetic 4h OHLCV — Transformation Trace (Intended vs Produced)",
        "",
        f"> Generated by `scripts/research/erp_synth_4h_trace.py`.  ",
        f"> Instrument `{INSTRUMENT}` · M15 · event window **4.0 hours** ({EVENT_BARS} bars)  ",
        f"> Warmup {WARMUP_BARS} bars (indicator window only).  ",
        f"> Critical compare: **{'PASS' if c.get('all_critical_pass') else 'FAIL'}**",
        "",
        "## Design principle",
        "",
        "This series is **not random**. Every bar phase is scripted so that:",
        "1. A liquidity **sweep** prints a known low.",
        "2. **Displacement / expansion** create upside structure.",
        "3. A **retest** holds above the design SL.",
        "4. A design-injected LONG signal has a path that **hits TP before SL** under `forward_walk(intrabar_fixed)`.",
        "",
        "That lets us compare **intended_spec.json** vs **produced_compare.json** without market noise.",
        "",
        "## Files",
        "",
        f"| File | Role |",
        f"|---|---|",
        f"| `SYNTH_4H_M15.csv` | OHLCV input artifact |",
        f"| `intended_spec.json` | Ground-truth design |",
        f"| `produced_compare.json` | What code actually produced |",
        f"| `TRACE_NARRATIVE.md` | This narration |",
        "",
        "## Bar phases (event window only)",
        "",
        "| Abs idx | Time | Phase | Note |",
        "|---|---|---|---|",
    ]
    for b in intended["bars"]:
        if b["phase"] == "warmup":
            continue
        lines.append(
            f"| {b['index']} | {b['timestamp']} | `{b['phase']}` | {b['note']} |"
        )

    lines += [
        "",
        "## Topic-by-topic transformation",
        "",
    ]

    topics = [
        (
            "1. Market data collect",
            "Generator constants → CSV rows",
            f"n={WARMUP_BARS + EVENT_BARS} rows written",
            f"row_count ok={c.get('row_count_match')}",
        ),
        (
            "2. Schema validation",
            "CSV frame → `validate_ohlcv_frame`",
            "PASS (six columns, monotonic ts, OHLC consistency)",
            f"schema ok={produced['checks'].get('schema', {}).get('ok')}",
        ),
        (
            "3. Features (candle math sample)",
            "Entry bar OHLC → body/range",
            "body_ratio in [0,1] from designed open/close/range",
            json.dumps(produced["topic_produced"].get("features_candle_math", {}), sort_keys=True),
        ),
        (
            "4. Events / opportunity seed",
            "Scripted phases → design Signal (injected; CRT not required)",
            f"LONG entry_index={intended['signal_intended']['entry_index']} entry={ENTRY_PRICE}",
            json.dumps(produced["topic_produced"].get("events_opportunity_seed", {}), sort_keys=True),
        ),
        (
            "5. Engines evidence",
            "Design feature contract → CRT/Gaussian/Zone soft/RR engines",
            json.dumps(produced["compare"].get("engines_intended_scores", {}), sort_keys=True),
            json.dumps(
                {
                    "status": produced["topic_produced"]["engines_evidence"].get("status"),
                    "scores": produced["compare"].get("engines_produced_scores"),
                    "match": produced["compare"].get("engines_match"),
                },
                sort_keys=True,
            ),
        ),
        (
            "6. Fusion / decision",
            "Scores → execute/reject",
            "NOT IN THIS PACK",
            produced["topic_produced"]["fusion_decision"]["status"],
        ),
        (
            "7. Plan + risk levels",
            "ATR mults → absolute SL/TP",
            f"SL={intended['geometry']['sl_price']} TP={intended['geometry']['tp_price']}",
            json.dumps(produced["topic_produced"].get("plan_risk", {}), sort_keys=True),
        ),
        (
            "8. Execution (MT5)",
            "Order intent → ticket",
            "NOT IN THIS PACK",
            produced["topic_produced"]["execution_mt5"]["status"],
        ),
        (
            "9. Outcome factory (`forward_walk`)",
            "Signal + future bars → Outcome",
            f"{intended['outcome_intended']['outcome']} rr≥{intended['outcome_intended']['expected_rr_achieved_min']}",
            json.dumps(produced["topic_produced"].get("outcome_forward_walk", {}), sort_keys=True),
        ),
        (
            "10. Test harness compare",
            "intended_spec vs produced_compare",
            "all_critical_pass=true",
            f"all_critical_pass={c.get('all_critical_pass')}",
        ),
    ]

    for title, tin, tout_i, tout_p in topics:
        lines += [
            f"### {title}",
            "",
            f"| | |",
            f"|---|---|",
            f"| **Transform** | {tin} |",
            f"| **Intended out** | {tout_i} |",
            f"| **Produced out** | `{tout_p}` |",
            "",
        ]

    lines += [
        "## Critical comparison table",
        "",
        "| Check | Intended | Produced | Match |",
        "|---|---|---|---|",
        f"| Schema | PASS | {produced['checks'].get('schema', {}).get('ok')} | {c.get('schema_pass')} |",
        f"| Row count | {WARMUP_BARS + EVENT_BARS} | {produced['checks'].get('row_count', {}).get('n')} | {c.get('row_count_match')} |",
        f"| Sweep low | {SWEEP_LOW} | {produced['checks'].get('path_geometry', {}).get('sweep_low_observed')} | {c.get('sweep_low_match')} |",
        f"| Outcome | {c.get('outcome_intended')} | {c.get('outcome_produced')} | {c.get('outcome_match')} |",
        f"| TP offset (bars after entry) | {c.get('tp_offset_intended')} | {c.get('tp_offset_produced')} | {c.get('tp_offset_intended') == c.get('tp_offset_produced')} |",
        f"| RR ≥ 2 | ≥2 | {c.get('rr_produced')} | {c.get('rr_ok')} |",
        f"| SL not first | true | {c.get('sl_not_hit_first')} | {c.get('sl_not_hit_first')} |",
        f"| Engines all match | true | {c.get('engines_all_match')} | {c.get('engines_all_match')} |",
        f"| CRT score | {c.get('engines_intended_scores', {}).get('crt')} | {c.get('engines_produced_scores', {}).get('crt')} | {c.get('engines_match', {}).get('crt')} |",
        f"| Gaussian score | {c.get('engines_intended_scores', {}).get('gaussian')} | {c.get('engines_produced_scores', {}).get('gaussian')} | {c.get('engines_match', {}).get('gaussian')} |",
        f"| Zone soft score | {c.get('engines_intended_scores', {}).get('zone_gate')} | {c.get('engines_produced_scores', {}).get('zone_gate')} | {c.get('engines_match', {}).get('zone_gate')} |",
        f"| RR polarity | {c.get('engines_intended_scores', {}).get('rr')} | {c.get('engines_produced_scores', {}).get('rr')} | {c.get('engines_match', {}).get('rr')} |",
        "",
        f"**Overall critical: {'PASS' if c.get('all_critical_pass') else 'FAIL'}**",
        "",
        "## Engines design (topic 5)",
        "",
        "Features at entry are **not random scores** — they are a design contract from the story:",
        "",
        "- `sweep_detected=True` (sweep bar exists); `double_sweep=False`",
        "- `body_ratio` from entry OHLC via `candle_math`",
        "- `disp_strength = DISP_CLOSE_2 - SWEEP_LOW` (thrust magnitude)",
        "- `retest_depth=0.5` (CRT retest component peak by design)",
        "- EMA/momentum seeds for bullish heuristic gaussian (fixed mu/sigma for pack)",
        "- Soft zone distance/freshness/strength near retest structure",
        "",
        "Produced via real callables: `crt_engine.compute`, `HeuristicGaussianEngine`,",
        "`_compute_soft_zone_score`, `RREngine.compute` — intended closed-form must match.",
        "",
        "## Narration of the 4-hour path",
        "",
        "1. **Warmup (prior 8h):** price oscillates in a ±0.30 band around 100 so later ATR-style",
        "   windows see a calm regime (features may still use longer windows elsewhere).",
        "2. **Event +0:00–0:45:** three range bars — market still balanced.",
        f"3. **Sweep:** one bar prints low **{SWEEP_LOW}** then closes back up — designed liquidity grab.",
        "4. **Displacement:** two strong up bars into the 102–103 area.",
        "5. **Expansion:** highs probe the **104** region (design TP neighborhood).",
        f"6. **Retest:** pullback low **{RETEST_LOW}** stays **above** design SL **{intended['geometry']['sl_price']}**.",
        f"7. **Entry:** designed long at **{ENTRY_PRICE}** (index {intended['signal_intended']['entry_index']}).",
        "8. **Path:** one mild adverse bar (low 101.20) that **must not** hit SL 101.00,",
        "   then grind higher until a bar high **≥ 104.00** → **TP_HIT** under intrabar_fixed.",
        "9. **Post bars:** residual after outcome (should not change forward_walk result).",
        "",
        "## What this does *not* claim",
        "",
        "- Not a CRT engine detection proof (seed is design-injected).",
        "- Not fusion/live/MT5/Binance proof.",
        "- Not economic edge — only that the **measurement path** matches geometry we built.",
        "- Outputs remain research fixtures; trust token still starts `UNTRUSTED_RAW` until flow review.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "PYTHONPATH=src python scripts/research/erp_synth_4h_trace.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bars = build_bars()
    df = bars_to_df(bars)
    df.to_csv(CSV_PATH, index=False)

    intended = intended_spec(bars)
    INTENDED_PATH.write_text(json.dumps(intended, indent=2), encoding="utf-8")

    produced = produce_compare(bars, intended)
    PRODUCED_PATH.write_text(json.dumps(produced, indent=2), encoding="utf-8")

    narrative = write_narrative(intended, produced)
    NARRATIVE_PATH.write_text(narrative, encoding="utf-8")

    # also mirror narrative into docs for program discoverability
    docs_copy = _ROOT / "docs" / "research-readiness" / "erp-synthetic-4h-trace.md"
    docs_copy.write_text(narrative, encoding="utf-8")

    ok = produced["compare"].get("all_critical_pass")
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {INTENDED_PATH}")
    print(f"Wrote {PRODUCED_PATH}")
    print(f"Wrote {NARRATIVE_PATH}")
    print(f"Wrote {docs_copy}")
    print(f"CRITICAL_COMPARE={'PASS' if ok else 'FAIL'}")
    print(json.dumps(produced["compare"], indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
