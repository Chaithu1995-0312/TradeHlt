"""
Gaussian family shadow measurement (H + ML via EngineRunner shadow_ml contract).

Research-only. No fusion wiring, no config promote, no ΔG001 authority.

Measures
--------
1. Agreement rate:  sign(H>=0.5) == sign(ML>=0.5)
2. Disagreement magnitude: |score_ml - score_h|
3. Same metrics conditioned on Market Geometry contexts:
   - CRT state (RANGE / SWEEP / …)
   - rare zone occupancy (zone ∈ RARE_ZONES)
   - rare-zone *entry* bars
   - boundary (lowest margin quintile)
4. Economic performance (honest forward_walk intrabar_fixed + 12 bps) of subsets:
   - H_pass, ML_pass, agree_high, agree_low, disagree
   on a fixed candidate base (default: SWEEP bars + rare-zone entries)

Uses the same dual-score contract as ``EngineRunner`` ``gaussian_impl=shadow_ml``:
  primary H score + shadow ML with delta + agreement.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import pandas as pd

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_engine_v2 import CRTEngine, Candle
from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
from engines.ml_gaussian_engine import MLGaussianEngine
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES
from research.contracts import Signal
from research.costs import DEFAULT_COST_MODEL, CostModel
from research.measurement.forward_walk import forward_walk
from research.zone_mapping.collect_trade_opened_features import _harden_crt_config
from research.zone_mapping.historical_zone_mapper import (
    HistoricalZoneMapper,
    ZoneMapConfig,
)
from research.zone_mapping.rare_zone_detection_eval import RARE_ZONES
from research.zone_mapping.zone_census import _zone_key
from runtime.backtest_v2 import HTFBuilder

SCHEMA_VERSION = "gaussian_family_shadow_eval_v1"
AGREE_THR = 0.5


@dataclass(frozen=True)
class GaussianShadowBar:
    """One bar: CRT × zone × dual Gaussian scores (shadow_ml contract)."""

    timestamp: str
    candle_index: int  # 1-based stream index (matches joint-label collectors)
    bar_pos: int  # 0-based index into candles[] / labels[]
    crt_state: str
    zone_id: str
    cluster_score: float
    margin_best_second: float
    best_zone_score: float
    second_best_score: float
    crt_action: str
    score_h: float
    score_ml: float
    delta: float
    agreement: bool
    ml_reason: str
    h_reason: str
    direction: int  # +1 long, -1 short, 0 unknown
    close: float
    atr_price: float
    is_rare_zone: bool
    is_rare_entry: bool
    is_boundary: bool  # filled after global margin quintile


def _mean(xs: Sequence[float]) -> Optional[float]:
    return float(sum(xs) / len(xs)) if xs else None


def _quantile_edges(values: Sequence[float], n_bins: int = 5) -> list[float]:
    if not values:
        return [0.0, 1.0]
    s = sorted(values)
    n = len(s)
    edges = [s[0]]
    for b in range(1, n_bins):
        idx = min(n - 1, int(round(b * n / n_bins)))
        edges.append(s[idx])
    edges.append(s[-1] + 1e-15)
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + 1e-12
    return edges


def _bin_index(x: float, edges: Sequence[float]) -> int:
    for i in range(len(edges) - 1):
        if edges[i] <= x < edges[i + 1]:
            return i
    return max(0, len(edges) - 2)


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def _direction_from_feat_and_crt(
    feat: Mapping[str, Any],
    crt_direction: Any,
) -> int:
    """Prefer CRT direction; fall back to EMA polarity."""
    if crt_direction is not None:
        try:
            d = int(getattr(crt_direction, "value", crt_direction))
            if d in (-1, 1):
                return d
        except (TypeError, ValueError):
            pass
    ema_f = _safe_float(feat.get("ema_fast"), 0.0)
    ema_s = _safe_float(feat.get("ema_slow"), 0.0)
    if ema_f > ema_s:
        return 1
    if ema_f < ema_s:
        return -1
    mom = _safe_float(feat.get("momentum_score"), 0.0)
    if mom > 0:
        return 1
    if mom < 0:
        return -1
    return 0


def _engine_config(instrument: str) -> dict:
    """Minimal engine_runner-shaped config for dual Gaussian load."""
    return {
        "instrument": instrument,
        "gaussian_impl": "shadow_ml",
    }


def collect_gaussian_shadow_bars(
    csv_path: str,
    *,
    instrument: str = "BNBUSDT",
    warmup_candles: int = 50,
    htf_candles_per_range: int = 96,
    zone_config: Optional[ZoneMapConfig] = None,
    rare_zones: Sequence[str] = RARE_ZONES,
    progress_every: int = 5000,
    max_bars: int = 0,
) -> list[GaussianShadowBar]:
    """
    Stream OHLCV → FeaturePipeline + CRT + ZoneMapper + H/ML (shadow_ml contract).

    Mirrors EngineRunner dual-score attachment:
      delta = ml - h
      agreement = (ml>=0.5) == (h>=0.5)
    """
    raw = pd.read_csv(csv_path)
    raw.columns = [c.strip().lower() for c in raw.columns]
    if "timestamp" not in raw.columns:
        if "date" in raw.columns and "time" in raw.columns:
            raw["timestamp"] = raw["date"].astype(str) + " " + raw["time"].astype(str)
        elif "date" in raw.columns:
            raw["timestamp"] = raw["date"]
        else:
            raise ValueError(f"No timestamp in {csv_path}")

    pipeline = FeaturePipeline(raw)
    enriched, vectors = pipeline.run()
    ts_series = pd.to_datetime(enriched["timestamp"])
    ts_to_idx = {
        ts_series.iloc[i].strftime("%Y-%m-%d %H:%M:%S"): i
        for i in range(len(ts_series))
    }

    candles: list[Candle] = []
    for _, row in raw.iterrows():
        ts = pd.to_datetime(row["timestamp"]).to_pydatetime()
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.replace(tzinfo=None)
        if not isinstance(ts, datetime):
            ts = datetime.fromisoformat(str(ts))
        candles.append(
            Candle(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"])
                if "volume" in row and pd.notna(row["volume"])
                else 0.0,
            )
        )

    cfg = zone_config or ZoneMapConfig.from_prod_engine_runner()
    mapper = HistoricalZoneMapper(cfg)
    crt_cfg = _harden_crt_config(ConfigBuilder.build(instrument))
    engine = CRTEngine(crt_cfg)
    htf = HTFBuilder(htf_candles_per_range, instrument)

    eng_cfg = _engine_config(instrument)
    # Ensure instrument-aware ML registry lookup (same as EngineRunner path).
    os.environ["GAUSSIAN_INSTRUMENT"] = instrument
    h_engine = HeuristicGaussianEngine(eng_cfg)
    ml_engine = MLGaussianEngine(eng_cfg, preload=True)

    rare_set = set(rare_zones)
    rows: list[dict[str, Any]] = []
    initialised = False
    candle_idx = 0
    prev_htf = ""
    htf_remaining = htf_candles_per_range
    n_candles = len(candles)
    prev_zone: Optional[str] = None

    for candle in candles:
        candle_idx += 1
        htf.push(candle)
        if htf.current_htf_id != prev_htf:
            prev_htf = htf.current_htf_id
            htf_remaining = htf_candles_per_range - 1
        else:
            htf_remaining = max(0, htf_remaining - 1)
        engine.state.htf_remaining_candles = htf_remaining

        if candle_idx < warmup_candles:
            continue
        if not initialised:
            seed = htf.seed_candles()
            if seed:
                engine.initialise_range(seed, htf.current_htf_id, "OFF_SESSION")
                initialised = True
            continue

        result = engine.process_candle(candle, htf.current_htf_id)
        action = str(result.get("action", "NONE"))
        state_name = engine.state.current_state.name

        ts_key = candle.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        fv_idx = ts_to_idx.get(ts_key, -1)
        if fv_idx < 0:
            continue

        vec = vectors[fv_idx]
        if hasattr(vec, "tolist"):
            vec = vec.tolist()
        feat = {name: float(vec[j]) for j, name in enumerate(CANONICAL_FEATURES)}
        for col in ("open", "high", "low", "close", "volume"):
            if col in enriched.columns:
                feat[col] = float(enriched.iloc[fv_idx][col])

        zrec = mapper.map_row(
            feat, timestamp=ts_key, bar_index=candle_idx, instrument=instrument
        )
        zone_id = _zone_key(zrec.get("best_zone_id"))
        # Match rare_zone_detection_eval.find_zone_entries: transition into rare.
        is_rare_entry = bool(
            prev_zone is not None
            and zone_id in rare_set
            and zone_id != prev_zone
        )
        prev_zone = zone_id

        direction = _direction_from_feat_and_crt(feat, engine.state.direction)
        feat["direction"] = direction
        feat["signal_dir"] = direction
        _gauss_dir = "short" if direction < 0 else "long"

        h_res = h_engine.compute(feat, direction=_gauss_dir)
        ml_res = ml_engine.compute(feat, direction=_gauss_dir)
        score_h = _safe_float(h_res.get("score"), 0.5)
        score_ml = _safe_float(ml_res.get("score"), 0.5)
        delta = round(score_ml - score_h, 4)
        agreement = bool((score_ml >= AGREE_THR) == (score_h >= AGREE_THR))

        atr_rel = _safe_float(feat.get("atr"), 0.0)
        close = float(candle.close)
        atr_price = atr_rel * close if atr_rel > 0 else 0.0

        rows.append(
            {
                "timestamp": ts_key,
                "candle_index": candle_idx,
                "bar_pos": candle_idx - 1,  # 0-based into candles
                "crt_state": str(state_name),
                "zone_id": zone_id,
                "cluster_score": float(zrec.get("cluster_score", 0.0)),
                "margin_best_second": float(zrec.get("margin_best_second") or 0.0),
                "best_zone_score": float(zrec.get("best_zone_score") or 0.0),
                "second_best_score": float(zrec.get("second_best_score") or 0.0),
                "crt_action": action,
                "score_h": score_h,
                "score_ml": score_ml,
                "delta": delta,
                "agreement": agreement,
                "ml_reason": str(ml_res.get("reason", "")),
                "h_reason": str(h_res.get("reason", "")),
                "direction": direction,
                "close": close,
                "atr_price": atr_price,
                "is_rare_zone": zone_id in rare_set,
                "is_rare_entry": is_rare_entry,
            }
        )
        if progress_every and candle_idx % progress_every == 0:
            print(
                f"  gaussian shadow bars {len(rows)} (candle {candle_idx}/{n_candles})…",
                flush=True,
            )
        if max_bars and len(rows) >= max_bars:
            break

    # Boundary flag: lowest margin quintile (global)
    margins = [r["margin_best_second"] for r in rows]
    edges = _quantile_edges(margins, 5)
    bars: list[GaussianShadowBar] = []
    for r in rows:
        b = _bin_index(float(r["margin_best_second"]), edges)
        is_boundary = b == 0
        bars.append(
            GaussianShadowBar(
                timestamp=r["timestamp"],
                candle_index=r["candle_index"],
                bar_pos=r["bar_pos"],
                crt_state=r["crt_state"],
                zone_id=r["zone_id"],
                cluster_score=r["cluster_score"],
                margin_best_second=r["margin_best_second"],
                best_zone_score=r["best_zone_score"],
                second_best_score=r["second_best_score"],
                crt_action=r["crt_action"],
                score_h=r["score_h"],
                score_ml=r["score_ml"],
                delta=r["delta"],
                agreement=r["agreement"],
                ml_reason=r["ml_reason"],
                h_reason=r["h_reason"],
                direction=r["direction"],
                close=r["close"],
                atr_price=r["atr_price"],
                is_rare_zone=r["is_rare_zone"],
                is_rare_entry=r["is_rare_entry"],
                is_boundary=is_boundary,
            )
        )
    return bars


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx <= 0 or dy <= 0:
        return None
    return float(num / (dx * dy))


def _percentile_value(sorted_vals: Sequence[float], p: float) -> float:
    """p in [0,1]; nearest-rank on pre-sorted list."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    idx = min(len(sorted_vals) - 1, max(0, int(round(p * (len(sorted_vals) - 1)))))
    return float(sorted_vals[idx])


def _agreement_pack(bars: Sequence[GaussianShadowBar]) -> dict[str, Any]:
    n = len(bars)
    if n == 0:
        return {
            "n": 0,
            "agreement_rate": None,
            "mean_abs_delta": None,
            "mean_delta": None,
            "mean_score_h": None,
            "mean_score_ml": None,
            "ml_fallback_rate": None,
            "h_pass_rate": None,
            "ml_pass_rate": None,
            "agree_high_rate": None,
            "agree_low_rate": None,
            "disagree_rate": None,
            "pearson_h_ml": None,
            "min_score_h": None,
            "min_score_ml": None,
            "p10_score_h": None,
            "p10_score_ml": None,
            "p90_score_h": None,
            "p90_score_ml": None,
            "binary_thr_informative": None,
        }
    n_agree = sum(1 for b in bars if b.agreement)
    abs_deltas = [abs(b.delta) for b in bars]
    deltas = [b.delta for b in bars]
    hs = [b.score_h for b in bars]
    mls = [b.score_ml for b in bars]
    n_fb = sum(1 for b in bars if b.ml_reason == "ml_gaussian_fallback")
    n_h = sum(1 for b in bars if b.score_h >= AGREE_THR)
    n_ml = sum(1 for b in bars if b.score_ml >= AGREE_THR)
    n_ah = sum(1 for b in bars if b.score_h >= AGREE_THR and b.score_ml >= AGREE_THR)
    n_al = sum(1 for b in bars if b.score_h < AGREE_THR and b.score_ml < AGREE_THR)
    n_dis = n - n_agree
    hs_s = sorted(hs)
    mls_s = sorted(mls)
    pearson = _pearson(hs, mls)
    # Binary thr is informative only if both sides of 0.5 appear for at least one model
    thr_info = not (n_h in (0, n) and n_ml in (0, n))
    return {
        "n": n,
        "agreement_rate": round(n_agree / n, 4),
        "mean_abs_delta": round(sum(abs_deltas) / n, 4),
        "mean_delta": round(sum(deltas) / n, 4),
        "mean_score_h": round(sum(hs) / n, 4),
        "mean_score_ml": round(sum(mls) / n, 4),
        "ml_fallback_rate": round(n_fb / n, 4),
        "h_pass_rate": round(n_h / n, 4),
        "ml_pass_rate": round(n_ml / n, 4),
        "agree_high_rate": round(n_ah / n, 4),
        "agree_low_rate": round(n_al / n, 4),
        "disagree_rate": round(n_dis / n, 4),
        "pearson_h_ml": (round(pearson, 4) if pearson is not None else None),
        "min_score_h": round(hs_s[0], 4),
        "min_score_ml": round(mls_s[0], 4),
        "p10_score_h": round(_percentile_value(hs_s, 0.10), 4),
        "p10_score_ml": round(_percentile_value(mls_s, 0.10), 4),
        "p90_score_h": round(_percentile_value(hs_s, 0.90), 4),
        "p90_score_ml": round(_percentile_value(mls_s, 0.90), 4),
        "binary_thr_informative": thr_info,
    }


def _filter_context(
    bars: Sequence[GaussianShadowBar],
    context: str,
) -> list[GaussianShadowBar]:
    c = context.upper()
    if c == "ALL":
        return list(bars)
    if c == "RANGE":
        return [b for b in bars if b.crt_state == "RANGE"]
    if c == "SWEEP":
        return [b for b in bars if b.crt_state == "SWEEP"]
    if c == "DISPLACEMENT":
        return [b for b in bars if b.crt_state == "DISPLACEMENT"]
    if c == "RARE_ZONE":
        return [b for b in bars if b.is_rare_zone]
    if c == "RARE_ENTRY":
        return [b for b in bars if b.is_rare_entry]
    if c == "BOUNDARY":
        return [b for b in bars if b.is_boundary]
    if c == "RARE_ENTRY_SWEEP":
        return [b for b in bars if b.is_rare_entry and b.crt_state == "SWEEP"]
    if c == "BOUNDARY_SWEEP":
        return [b for b in bars if b.is_boundary and b.crt_state == "SWEEP"]
    raise ValueError(f"unknown context {context!r}")


def _candidate_bars(
    bars: Sequence[GaussianShadowBar],
    mode: str = "sweep_or_rare_entry",
) -> list[GaussianShadowBar]:
    """Fixed economic candidate base (pre-Gaussian filter)."""
    m = mode.lower()
    out: list[GaussianShadowBar] = []
    for b in bars:
        if b.direction == 0 or b.atr_price <= 0:
            continue
        if m == "all_directional":
            out.append(b)
        elif m == "sweep":
            if b.crt_state == "SWEEP":
                out.append(b)
        elif m == "rare_entry":
            if b.is_rare_entry:
                out.append(b)
        elif m == "trade_opened":
            if "TRADE_OPENED" in (b.crt_action or ""):
                out.append(b)
        else:  # sweep_or_rare_entry
            if b.crt_state == "SWEEP" or b.is_rare_entry:
                out.append(b)
    return out


def _tercile_edges(values: Sequence[float]) -> tuple[float, float]:
    s = sorted(values)
    if not s:
        return (0.0, 1.0)
    return (_percentile_value(s, 1.0 / 3.0), _percentile_value(s, 2.0 / 3.0))


def _subset(
    cands: Sequence[GaussianShadowBar],
    name: str,
    *,
    h_edges: Optional[tuple[float, float]] = None,
    ml_edges: Optional[tuple[float, float]] = None,
    abs_delta_edges: Optional[tuple[float, float]] = None,
) -> list[GaussianShadowBar]:
    n = name.lower()
    if n == "base":
        return list(cands)
    if n == "h_only" or n == "h_pass":
        return [b for b in cands if b.score_h >= AGREE_THR]
    if n == "ml_only" or n == "ml_pass":
        return [b for b in cands if b.score_ml >= AGREE_THR]
    if n == "agree_high":
        return [
            b
            for b in cands
            if b.score_h >= AGREE_THR and b.score_ml >= AGREE_THR
        ]
    if n == "agree_low":
        return [
            b for b in cands if b.score_h < AGREE_THR and b.score_ml < AGREE_THR
        ]
    if n == "agree_any":
        return [b for b in cands if b.agreement]
    if n == "disagree":
        return [b for b in cands if not b.agreement]
    # Continuous rank subsets (edges from candidate base)
    if h_edges is not None:
        lo, hi = h_edges
        if n == "h_top_tercile":
            return [b for b in cands if b.score_h >= hi]
        if n == "h_bot_tercile":
            return [b for b in cands if b.score_h <= lo]
    if ml_edges is not None:
        lo, hi = ml_edges
        if n == "ml_top_tercile":
            return [b for b in cands if b.score_ml >= hi]
        if n == "ml_bot_tercile":
            return [b for b in cands if b.score_ml <= lo]
    if abs_delta_edges is not None:
        lo, hi = abs_delta_edges
        if n == "low_abs_delta":  # continuous agreement (scores close)
            return [b for b in cands if abs(b.delta) <= lo]
        if n == "high_abs_delta":  # continuous disagreement (scores far)
            return [b for b in cands if abs(b.delta) >= hi]
    if n in (
        "h_top_tercile",
        "h_bot_tercile",
        "ml_top_tercile",
        "ml_bot_tercile",
        "low_abs_delta",
        "high_abs_delta",
    ):
        return []  # edges missing
    raise ValueError(f"unknown subset {name!r}")


def _econ_stats(
    bars: Sequence[GaussianShadowBar],
    candles: Sequence[Candle],
    *,
    instrument: str,
    sl_atr_mult: float = 1.0,
    tp_atr_mult: float = 2.0,
    max_forward: int = 40,
    cost_model: CostModel = DEFAULT_COST_MODEL,
    stride: int = 1,
) -> dict[str, Any]:
    """Honest forward_walk net expectancy for a bar subset."""
    if stride < 1:
        stride = 1
    rrs: list[float] = []
    n_skip = 0
    for i, b in enumerate(bars):
        if stride > 1 and (i % stride) != 0:
            continue
        idx = b.bar_pos
        if idx < 0 or idx >= len(candles) - 1:
            n_skip += 1
            continue
        if b.atr_price <= 0 or b.direction == 0:
            n_skip += 1
            continue
        direction = "long" if b.direction > 0 else "short"
        # Attach .index for forward_walk no-lookahead assert
        entry_c = candles[idx]
        # Candle may not have .index — use synthetic bar list with index attrs
        future = []
        for j in range(idx + 1, min(len(candles), idx + 1 + max_forward)):
            c = candles[j]
            # duck-typed bar
            future.append(_BarView(j, c.high, c.low, c.close))
        sig = Signal(
            instrument=instrument,
            timestamp=entry_c.timestamp
            if isinstance(entry_c.timestamp, datetime)
            else datetime.fromisoformat(str(entry_c.timestamp)),
            entry_index=idx,
            direction=direction,
            entry=float(b.close),
            sl_atr_mult=float(sl_atr_mult),
            tp_atr_mult=float(tp_atr_mult),
            atr=float(b.atr_price),
            meta={
                "score_h": b.score_h,
                "score_ml": b.score_ml,
                "crt_state": b.crt_state,
                "zone_id": b.zone_id,
            },
        )
        try:
            out = forward_walk(
                sig, future, max_forward=max_forward, exit_model="intrabar_fixed"
            )
        except ValueError:
            n_skip += 1
            continue
        risk = sl_atr_mult * b.atr_price
        net = cost_model.net_rr(out.rr_achieved, b.close, risk)
        rrs.append(net)

    n = len(rrs)
    if n == 0:
        return {
            "n": 0,
            "n_skipped": n_skip,
            "expectancy_rr_net": None,
            "win_rate": None,
            "profit_factor": None,
            "sum_rr_net": None,
        }
    wins = [r for r in rrs if r > 0]
    losses = [r for r in rrs if r < 0]
    gw = sum(wins)
    gl = abs(sum(losses))
    pf = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0.0)
    return {
        "n": n,
        "n_skipped": n_skip,
        "expectancy_rr_net": round(sum(rrs) / n, 4),
        "win_rate": round(len(wins) / n, 4),
        "profit_factor": (round(pf, 4) if pf != float("inf") else "inf"),
        "sum_rr_net": round(sum(rrs), 4),
    }


@dataclass
class _BarView:
    index: int
    high: float
    low: float
    close: float


def _load_candles(csv_path: str) -> list[Candle]:
    raw = pd.read_csv(csv_path)
    raw.columns = [c.strip().lower() for c in raw.columns]
    if "timestamp" not in raw.columns:
        if "date" in raw.columns and "time" in raw.columns:
            raw["timestamp"] = raw["date"].astype(str) + " " + raw["time"].astype(str)
        elif "date" in raw.columns:
            raw["timestamp"] = raw["date"]
    candles: list[Candle] = []
    for _, row in raw.iterrows():
        ts = pd.to_datetime(row["timestamp"]).to_pydatetime()
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.replace(tzinfo=None)
        candles.append(
            Candle(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"])
                if "volume" in row and pd.notna(row["volume"])
                else 0.0,
            )
        )
    return candles


CONTEXTS = (
    "ALL",
    "RANGE",
    "SWEEP",
    "DISPLACEMENT",
    "RARE_ZONE",
    "RARE_ENTRY",
    "BOUNDARY",
    "RARE_ENTRY_SWEEP",
    "BOUNDARY_SWEEP",
)

ECON_SUBSETS = (
    "base",
    "h_pass",
    "ml_pass",
    "agree_high",
    "agree_low",
    "agree_any",
    "disagree",
    # Continuous rank / magnitude (informative when binary thr saturates)
    "h_top_tercile",
    "h_bot_tercile",
    "ml_top_tercile",
    "ml_bot_tercile",
    "low_abs_delta",
    "high_abs_delta",
)


def evaluate_gaussian_family_shadow(
    bars: Sequence[GaussianShadowBar],
    candles: Sequence[Candle],
    *,
    instrument: str,
    candidate_mode: str = "sweep_or_rare_entry",
    sl_atr_mult: float = 1.0,
    tp_atr_mult: float = 2.0,
    max_forward: int = 40,
    econ_stride: int = 1,
    rare_zones: Sequence[str] = RARE_ZONES,
) -> dict[str, Any]:
    """Full report: agreement global + contexts + economic subsets."""
    overall = _agreement_pack(bars)
    by_context: dict[str, Any] = {}
    for ctx in CONTEXTS:
        subset = _filter_context(bars, ctx)
        by_context[ctx] = _agreement_pack(subset)

    # CRT state distribution
    state_counts = Counter(b.crt_state for b in bars)

    cands = _candidate_bars(bars, mode=candidate_mode)
    cand_agree = _agreement_pack(cands)
    h_edges = _tercile_edges([b.score_h for b in cands])
    ml_edges = _tercile_edges([b.score_ml for b in cands])
    abs_delta_edges = _tercile_edges([abs(b.delta) for b in cands])
    economic: dict[str, Any] = {
        "candidate_mode": candidate_mode,
        "candidate_agreement": cand_agree,
        "exit_model": "intrabar_fixed",
        "cost_round_trip_bps": DEFAULT_COST_MODEL.round_trip_bps,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "max_forward": max_forward,
        "econ_stride": econ_stride,
        "tercile_edges": {
            "score_h": {"p33": h_edges[0], "p66": h_edges[1]},
            "score_ml": {"p33": ml_edges[0], "p66": ml_edges[1]},
            "abs_delta": {"p33": abs_delta_edges[0], "p66": abs_delta_edges[1]},
        },
        "subsets": {},
    }
    for name in ECON_SUBSETS:
        sub = _subset(
            cands,
            name,
            h_edges=h_edges,
            ml_edges=ml_edges,
            abs_delta_edges=abs_delta_edges,
        )
        economic["subsets"][name] = _econ_stats(
            sub,
            candles,
            instrument=instrument,
            sl_atr_mult=sl_atr_mult,
            tp_atr_mult=tp_atr_mult,
            max_forward=max_forward,
            stride=econ_stride,
        )

    # Economic × geometry — continuous subsets when binary thr saturates
    geo_econ: dict[str, Any] = {}
    for geo in ("SWEEP", "RANGE", "RARE_ENTRY", "BOUNDARY"):
        geo_bars = _filter_context(bars, geo)
        geo_cands = _candidate_bars(geo_bars, mode="all_directional")
        g_h = _tercile_edges([b.score_h for b in geo_cands])
        g_ml = _tercile_edges([b.score_ml for b in geo_cands])
        g_ad = _tercile_edges([abs(b.delta) for b in geo_cands])
        pack: dict[str, Any] = {
            "n_context_bars": len(geo_bars),
            "agreement": _agreement_pack(geo_cands),
            "tercile_edges": {
                "score_h": {"p33": g_h[0], "p66": g_h[1]},
                "score_ml": {"p33": g_ml[0], "p66": g_ml[1]},
                "abs_delta": {"p33": g_ad[0], "p66": g_ad[1]},
            },
            "subsets": {},
        }
        for name in (
            "base",
            "h_pass",
            "ml_pass",
            "agree_high",
            "disagree",
            "h_top_tercile",
            "h_bot_tercile",
            "ml_top_tercile",
            "ml_bot_tercile",
            "low_abs_delta",
            "high_abs_delta",
        ):
            sub = _subset(
                geo_cands,
                name,
                h_edges=g_h,
                ml_edges=g_ml,
                abs_delta_edges=g_ad,
            )
            pack["subsets"][name] = _econ_stats(
                sub,
                candles,
                instrument=instrument,
                sl_atr_mult=sl_atr_mult,
                tp_atr_mult=tp_atr_mult,
                max_forward=max_forward,
                stride=max(econ_stride, 1),
            )
        geo_econ[geo] = pack

    ml_reasons = Counter(b.ml_reason for b in bars)
    return {
        "schema_version": SCHEMA_VERSION,
        "instrument": instrument,
        "authority": "research_only",
        "production_behavior_changed": False,
        "gaussian_impl_contract": "shadow_ml",
        "agree_threshold": AGREE_THR,
        "rare_zones": list(rare_zones),
        "n_bars": len(bars),
        "crt_state_counts": dict(state_counts),
        "ml_reason_counts": dict(ml_reasons),
        "overall": overall,
        "by_geometry_context": by_context,
        "economic": economic,
        "economic_by_geometry": geo_econ,
        "notes": [
            "Agreement uses EngineRunner shadow_ml contract: (H>=0.5)==(ML>=0.5).",
            "If binary_thr_informative=false, both models never cross 0.5 — use pearson + terciles + |delta| strata.",
            "Economic outcomes are forward_walk(intrabar_fixed) net of 12 bps — not spine ledger.",
            "Candidate base default = SWEEP bars ∪ rare-zone entry bars with direction+ATR.",
            "No fusion authority; do not promote from this report alone.",
            "MLGaussianEngine registers FeatureSchemaRegistry under version id (not only model file path).",
        ],
    }


def run_from_csv(
    csv_path: str,
    *,
    instrument: str = "BNBUSDT",
    candidate_mode: str = "sweep_or_rare_entry",
    econ_stride: int = 1,
    max_bars: int = 0,
    progress_every: int = 5000,
) -> dict[str, Any]:
    bars = collect_gaussian_shadow_bars(
        csv_path,
        instrument=instrument,
        progress_every=progress_every,
        max_bars=max_bars,
    )
    candles = _load_candles(csv_path)
    rep = evaluate_gaussian_family_shadow(
        bars,
        candles,
        instrument=instrument,
        candidate_mode=candidate_mode,
        econ_stride=econ_stride,
    )
    rep["csv_path"] = str(csv_path)
    return rep


def report_to_markdown(rep: Mapping[str, Any], *, title: str = "") -> str:
    inst = rep.get("instrument", "?")
    title = title or f"Gaussian family shadow — {inst}"
    lines = [
        f"# {title}",
        "",
        f"**Schema:** `{rep.get('schema_version')}`  ·  **Authority:** research only",
        f"**Contract:** `{rep.get('gaussian_impl_contract')}`  ·  thr={rep.get('agree_threshold')}",
        f"**Bars:** {rep.get('n_bars')}  ·  **CSV:** `{rep.get('csv_path', '')}`",
        "",
        "## Overall agreement",
        "",
    ]
    o = rep.get("overall") or {}
    lines.append("| metric | value |")
    lines.append("|---|---|")
    for k in (
        "n",
        "agreement_rate",
        "binary_thr_informative",
        "pearson_h_ml",
        "mean_abs_delta",
        "mean_delta",
        "mean_score_h",
        "mean_score_ml",
        "min_score_h",
        "min_score_ml",
        "p10_score_h",
        "p10_score_ml",
        "p90_score_h",
        "p90_score_ml",
        "ml_fallback_rate",
        "h_pass_rate",
        "ml_pass_rate",
        "agree_high_rate",
        "agree_low_rate",
        "disagree_rate",
    ):
        lines.append(f"| {k} | {o.get(k)} |")

    lines.extend(["", "## Agreement by geometry context", ""])
    lines.append(
        "| context | n | agree_rate | pearson | mean_abs_delta | mean_H | mean_ML |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for ctx, pack in (rep.get("by_geometry_context") or {}).items():
        lines.append(
            f"| {ctx} | {pack.get('n')} | {pack.get('agreement_rate')} | "
            f"{pack.get('pearson_h_ml')} | {pack.get('mean_abs_delta')} | "
            f"{pack.get('mean_score_h')} | {pack.get('mean_score_ml')} |"
        )

    econ = rep.get("economic") or {}
    lines.extend(
        [
            "",
            f"## Economic subsets (candidate={econ.get('candidate_mode')})",
            "",
            f"exit=`{econ.get('exit_model')}` · cost={econ.get('cost_round_trip_bps')} bps · "
            f"SL/TP={econ.get('sl_atr_mult')}/{econ.get('tp_atr_mult')}R · "
            f"horizon={econ.get('max_forward')} · stride={econ.get('econ_stride')}",
            "",
            "| subset | n | E[R]_net | win_rate | PF | sum_R |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, s in (econ.get("subsets") or {}).items():
        lines.append(
            f"| {name} | {s.get('n')} | {s.get('expectancy_rr_net')} | "
            f"{s.get('win_rate')} | {s.get('profit_factor')} | {s.get('sum_rr_net')} |"
        )

    lines.extend(["", "## Economic by geometry context (all directional bars in context)", ""])
    for geo, pack in (rep.get("economic_by_geometry") or {}).items():
        lines.append(f"### {geo} (n_context_bars={pack.get('n_context_bars')})")
        lines.append("")
        lines.append("| subset | n | E[R]_net | win_rate | PF |")
        lines.append("|---|---:|---:|---:|---:|")
        for name, s in (pack.get("subsets") or {}).items():
            lines.append(
                f"| {name} | {s.get('n')} | {s.get('expectancy_rr_net')} | "
                f"{s.get('win_rate')} | {s.get('profit_factor')} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
        ]
    )
    for n in rep.get("notes") or []:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)
