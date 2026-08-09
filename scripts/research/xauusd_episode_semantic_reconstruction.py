#!/usr/bin/env python3
"""
Source-first semantic market reconstruction of meaningful XAUUSD M15 episodes.

Reuses ONLY existing surfaces:
  - FeaturePipeline (39-dim CANONICAL_FEATURES)
  - FeatureStateEncoder / MarketContextBuilder / MarketShapeClassifier
  - CRT runtime (crt_engine_v2 + HTFBuilder htf=4)
  - ModelEvidenceBuilder over engine_results (crt/gaussian/zone_gate/rr)

No new indicators. No CPR. Observe-only.

Usage:
  PYTHONPATH=src python scripts/research/xauusd_episode_semantic_reconstruction.py \\
      --csv data/mt5/XAUUSD_M15.csv \\
      --out results/research/xauusd_episode_semantic_reconstruction
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from config_layer.crt_engine_v2 import CRTEngine, Candle  # noqa: E402
from config_layer.production_config import get_active_version, load_prod_config_from_registry  # noqa: E402
from engines.crt_engine import compute as crt_compute  # noqa: E402
from engines.heuristic_gaussian_engine import HeuristicGaussianEngine  # noqa: E402
from engines.rr_engine import RREngine  # noqa: E402
from engines.zone_cluster_score import score_zone_cluster  # noqa: E402
from engines.live_engine import get_zone_gate  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from features.feature_states import FeatureStateEncoder  # noqa: E402
from features.market_context import MarketContextBuilder  # noqa: E402
from features.market_shape import MarketShapeClassifier  # noqa: E402
from features.model_evidence import ModelEvidenceBuilder  # noqa: E402
from runtime.backtest_v2 import HTFBuilder  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)


def _pipeline_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, dict[str, int]]:
    pipe = FeaturePipeline(
        df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    )
    enriched, vectors = pipe.run()
    arr = np.asarray(vectors, dtype=np.float64)
    enriched = enriched.copy()
    enriched["timestamp"] = pd.to_datetime(enriched["timestamp"])
    key_to_i = {
        ts.strftime("%Y-%m-%d %H:%M:%S"): i
        for i, ts in enumerate(enriched["timestamp"])
    }
    return enriched, arr, key_to_i


def _feat_map_at(df: pd.DataFrame, arr: np.ndarray, key_to_i: dict[str, int], row_i: int) -> dict[str, float] | None:
    key = pd.Timestamp(df.loc[row_i, "timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    j = key_to_i.get(key)
    if j is None or j >= len(arr):
        return None
    feat = {CANONICAL_FEATURES[k]: float(arr[j, k]) for k in range(min(len(CANONICAL_FEATURES), arr.shape[1]))}
    # OHLCV always present from raw
    for c in ("open", "high", "low", "close", "volume"):
        feat[c] = float(df.loc[row_i, c])
    return feat


def _run_crt(df: pd.DataFrame) -> tuple[list[dict], list[str], dict[int, dict]]:
    """Return (events, state_path per bar index raw, event_by_idx)."""
    cfg = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    engine = CRTEngine(cfg)
    htf = HTFBuilder(4, "XAUUSD")
    init = False
    state_by_idx: dict[int, str] = {}
    events: list[dict] = []
    action_by_idx: dict[int, dict] = {}

    for i, row in df.iterrows():
        candle = Candle(
            timestamp=row["timestamp"].to_pydatetime()
            if hasattr(row["timestamp"], "to_pydatetime")
            else row["timestamp"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"] or 0),
            index=int(i),
        )
        completed = htf.push(candle)
        if not init:
            if completed:
                engine.initialise_range(htf.seed_candles(), htf.current_htf_id, "UNKNOWN")
                init = True
            else:
                state_by_idx[int(i)] = "WARMUP"
                continue
        before = engine.state.current_state.name
        action = engine.process_candle(candle, htf.current_htf_id)
        after = engine.state.current_state.name
        state_by_idx[int(i)] = after
        act = action.get("action") if isinstance(action, dict) else str(action)
        rec = {
            "idx": int(i),
            "ts": str(row["timestamp"]),
            "action": act,
            "state_before": before,
            "state_after": after,
            "direction": engine.state.direction.name if engine.state.direction else None,
            "close": float(row["close"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "open": float(row["open"]),
            "atr": float(engine.state.atr_abs or 0),
            "reason": action.get("reason") if isinstance(action, dict) else None,
        }
        if act not in ("NONE", None) or before != after:
            events.append(rec)
            action_by_idx[int(i)] = rec
    return events, state_by_idx, action_by_idx


def _engine_results(feat: dict[str, float], direction: int, zone_gate, eng_cfg: dict) -> dict:
    """Build declared engine_results slots for ModelEvidenceBuilder (no fusion)."""
    # CRT score — PLAN-002 requires explicit tuple weights
    weights = eng_cfg.get("score_component_weights")
    if isinstance(weights, dict):
        weights = [
            float(weights.get("structure", 0.35)),
            float(weights.get("momentum", 0.25)),
            float(weights.get("zone", 0.20)),
            float(weights.get("volatility", 0.20)),
        ]
    if not weights:
        weights = [0.35, 0.25, 0.20, 0.20]
    # Map pipeline keys CRT score expects
    feat_crt = dict(feat)
    if "disp_strength" not in feat_crt and "displacement_atr_ratio" in feat_crt:
        feat_crt["disp_strength"] = feat_crt["displacement_atr_ratio"]
    crt = crt_compute("ep", feat_crt, {"score_component_weights": weights})
    # Gaussian
    g_eng = HeuristicGaussianEngine(eng_cfg if "gaussian_impl" in eng_cfg else {"gaussian_impl": "heuristic"})
    try:
        gauss = g_eng.compute(feat, direction="short" if direction < 0 else "long")
    except Exception as exc:
        gauss = {"score": 0.0, "reason": f"gaussian_error:{exc}"}
    # RR
    try:
        rr = RREngine(eng_cfg).compute(feat)
    except Exception as exc:
        rr = {"score": 0.0, "candle_polarity": 0.5, "reason": f"rr_error:{exc}", "semantic": "candle_structure_quality"}
    if "candle_polarity" not in rr and "score" in rr:
        rr = {**rr, "candle_polarity": rr["score"], "semantic": "candle_structure_quality"}
    if "semantic" not in rr:
        rr = {**rr, "semantic": "candle_structure_quality"}
    # Zone
    try:
        zg = score_zone_cluster(
            feat,
            zone_gate,
            zone_cluster_threshold=float(eng_cfg.get("zone_cluster_threshold", 0.25)),
            cluster_min_n=int((eng_cfg.get("zone_gate") or {}).get("cluster_min_n", 1)),
            cluster_spread_max=float((eng_cfg.get("zone_gate") or {}).get("cluster_spread_max", 1.0)),
            execution_mode=str(eng_cfg.get("zone_gate_execution_mode", "normal")),
        )
        zone = {
            "score": float(zg.get("score", 0.0)),
            "passed": bool(zg.get("passed", False)),
            "reason": "zone_scored",
        }
    except Exception as exc:
        zone = {"score": 0.0, "passed": False, "reason": f"zone_error:{exc}"}

    # Normalize crt score field
    if "score" not in crt and isinstance(crt, dict):
        crt = {**crt, "score": float(crt.get("score", 0.0) or 0.0)}
    return {
        "crt": crt if isinstance(crt, dict) else {"score": 0.0, "reason": "crt_bad"},
        "gaussian": gauss if isinstance(gauss, dict) else {"score": 0.0},
        "zone_gate": zone,
        "rr": rr if isinstance(rr, dict) else {"score": 0.0, "candle_polarity": 0.5, "semantic": "candle_structure_quality"},
    }


def _select_episodes(
    df: pd.DataFrame,
    events: list[dict],
    state_by_idx: dict[int, str],
    arr: np.ndarray,
    key_to_i: dict[str, int],
) -> list[dict]:
    """Pick meaningful episodes from CRT + price structure (existing surfaces only)."""
    n = len(df)
    atr14 = pd.Series(df["close"]).diff().abs().rolling(14).mean().to_numpy()  # rough for ranking only
    # better: use pipeline atr if available
    body = (df["close"] - df["open"]).abs().to_numpy()
    rng = (df["high"] - df["low"]).to_numpy() + 1e-12
    body_atr = np.full(n, np.nan)
    for i in range(n):
        key = pd.Timestamp(df.loc[i, "timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        j = key_to_i.get(key)
        if j is not None and j < len(arr):
            # atr in vector is relative; use candle range / body for episode ranking
            body_atr[i] = body[i] / max(rng[i], 1e-9)

    candidates: list[dict] = []

    # 1) Largest body expansions (top 5 unique days)
    order = np.argsort(-np.nan_to_num(body / (pd.Series(rng).rolling(14, min_periods=1).median().to_numpy() + 1e-9)))
    seen_days = set()
    for i in order[:200]:
        day = str(df.loc[int(i), "timestamp"])[:10]
        if day in seen_days:
            continue
        seen_days.add(day)
        candidates.append({
            "id": f"EXPANSION_BAR_{day}",
            "kind": "large_body_expansion",
            "anchor_idx": int(i),
            "why": "largest body/range among remaining days — structural expansion candle",
        })
        if len([c for c in candidates if c["kind"] == "large_body_expansion"]) >= 3:
            break

    # 2) CRT terminal events
    for ev in events:
        if ev["action"] in ("TRADE_OPENED", "FILTER_REJECTED", "RETEST_CONFIRMED", "EXPANSION_CONFIRMED"):
            candidates.append({
                "id": f"CRT_{ev['action']}_{ev['ts'].replace(':','').replace(' ','_')}",
                "kind": f"crt_{ev['action'].lower()}",
                "anchor_idx": ev["idx"],
                "why": f"CRT runtime event {ev['action']} dir={ev.get('direction')}",
                "crt_event": ev,
            })

    # 3) Long EXPANSION dwells: contiguous EXPANSION runs length >= 20
    run_start = None
    for i in range(n):
        st = state_by_idx.get(i, "WARMUP")
        if st == "EXPANSION":
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and i - run_start >= 20:
                mid = (run_start + i - 1) // 2
                candidates.append({
                    "id": f"EXPANSION_DWELL_{run_start}_{i-1}",
                    "kind": "expansion_dwell",
                    "anchor_idx": mid,
                    "why": f"contiguous CRT EXPANSION dwell bars {run_start}..{i-1} (len={i-run_start})",
                    "dwell": [run_start, i - 1],
                })
            run_start = None
    if run_start is not None and n - run_start >= 20:
        mid = (run_start + n - 1) // 2
        candidates.append({
            "id": f"EXPANSION_DWELL_{run_start}_{n-1}",
            "kind": "expansion_dwell",
            "anchor_idx": mid,
            "why": f"contiguous CRT EXPANSION dwell to EOF len={n-run_start}",
            "dwell": [run_start, n - 1],
        })

    # Dedup by anchor proximity (keep first of each 8-bar cluster per kind family)
    candidates.sort(key=lambda c: (c["anchor_idx"], c["kind"]))
    kept: list[dict] = []
    last_idx = -999
    for c in candidates:
        if abs(c["anchor_idx"] - last_idx) < 8 and c["kind"] == (kept[-1]["kind"] if kept else None):
            continue
        # limit total
        if len(kept) >= 12:
            break
        kept.append(c)
        last_idx = c["anchor_idx"]

    # Prefer diversity: ensure we have at least one of key kinds if present
    return kept[:10]


def _continuous_snapshot(feat: dict[str, float]) -> dict[str, float]:
    keys = [
        "body_ratio", "candle_range", "atr", "rsi_14", "ema_spread", "momentum_score",
        "trend_strength", "disp_strength", "retest_depth", "volume_ratio",
        "macd_hist_raw", "liquidity_distance",
    ]
    out = {}
    for k in keys:
        if k in feat:
            out[k] = float(feat[k])
    return out


def _reconstruct_one(
    ep: dict,
    df: pd.DataFrame,
    arr: np.ndarray,
    key_to_i: dict[str, int],
    state_by_idx: dict[int, str],
    action_by_idx: dict[int, dict],
    encoder: FeatureStateEncoder,
    ctx_builder: MarketContextBuilder,
    shape_clf: MarketShapeClassifier,
    evidence_builder: ModelEvidenceBuilder,
    zone_gate,
    eng_cfg: dict,
) -> dict[str, Any]:
    i = ep["anchor_idx"]
    row = df.loc[i]
    window = df.loc[max(0, i - 8): min(len(df) - 1, i + 8)]
    feat = _feat_map_at(df, arr, key_to_i, i)

    market = {
        "anchor_ts": str(row["timestamp"]),
        "ohlc": {
            "o": float(row["open"]),
            "h": float(row["high"]),
            "l": float(row["low"]),
            "c": float(row["close"]),
            "v": float(row["volume"] or 0),
        },
        "local_path": {
            "close_start": float(window.iloc[0]["close"]),
            "close_end": float(window.iloc[-1]["close"]),
            "range_high": float(window["high"].max()),
            "range_low": float(window["low"].min()),
            "net_move": float(window.iloc[-1]["close"] - window.iloc[0]["close"]),
            "bars": int(len(window)),
        },
        "narrative_seed": (
            f"Bar {i} @ {row['timestamp']}: O={row['open']:.2f} H={row['high']:.2f} "
            f"L={row['low']:.2f} C={row['close']:.2f}; "
            f"±8-bar net={window.iloc[-1]['close']-window.iloc[0]['close']:.2f} "
            f"path high/low={window['high'].max():.2f}/{window['low'].min():.2f}"
        ),
    }

    out: dict[str, Any] = {
        "episode_id": ep["id"],
        "kind": ep["kind"],
        "why_selected": ep["why"],
        "market": market,
        "crt": {
            "state": state_by_idx.get(i, "UNKNOWN"),
            "event": action_by_idx.get(i),
            "nearby_events": [
                action_by_idx[k]
                for k in range(max(0, i - 5), min(len(df), i + 6))
                if k in action_by_idx
            ],
        },
        "canonical_features": None,
        "feature_states": None,
        "market_context": None,
        "market_shape": None,
        "model_evidence": None,
        "agreement": None,
        "unexplained": [],
        "errors": [],
    }

    if feat is None:
        out["errors"].append("no_feature_vector_for_anchor (warmup/finalize drop)")
        out["unexplained"].append(
            "Anchor bar has no 39-dim vector — finalize warmup or timestamp mismatch; "
            "market OHLC exists but canonical representation is absent."
        )
        return out

    out["canonical_features"] = {
        "continuous_snapshot": _continuous_snapshot(feat),
        "stateful_raw": {k: feat.get(k) for k in encoder.vector_bound_features if k in feat},
    }

    # Feature states + context + shape
    try:
        states = encoder.classify(feat)
        out["feature_states"] = states
        # attach non-vector if present in enriched — only if keys exist
        ctx = ctx_builder.build(states)
        out["market_context"] = {
            "signature": ctx.signature,
            "context_hash": ctx.context_hash,
            "describe": ctx.describe(),
            "dimensions": ctx.dimensions,
            "x_markers": list(ctx.x_markers),
        }
        shape = shape_clf.classify_context(ctx)
        out["market_shape"] = {
            "shape_id": shape.shape_id,
            "name": shape.name,
            "family": shape.family,
            "label": shape.label,
            "matched": shape.matched,
            "projected_signature": shape.projected_signature,
            "x_markers": list(shape.x_markers),
        }
    except Exception as exc:
        out["errors"].append(f"semantic_layers:{exc}")

    # Model evidence
    direction = 1
    if out["crt"].get("event") and out["crt"]["event"].get("direction") == "SHORT":
        direction = -1
    elif out["crt"].get("event") and out["crt"]["event"].get("direction") == "LONG":
        direction = 1
    try:
        er = _engine_results(feat, direction, zone_gate, eng_cfg)
        # ensure rr has required fields
        if "candle_polarity" not in er["rr"]:
            er["rr"]["candle_polarity"] = float(er["rr"].get("score", 0.5))
        if "semantic" not in er["rr"]:
            er["rr"]["semantic"] = "candle_structure_quality"
        # crt must expose score
        if "score" not in er["crt"]:
            er["crt"]["score"] = float(er["crt"].get("final", er["crt"].get("structure", 0.0)) or 0.0)
        evset = evidence_builder.build(er)
        out["model_evidence"] = {
            "signature": evset.signature,
            "evidence_hash": evset.evidence_hash,
            "describe": evset.describe(),
            "absent": list(evset.absent),
            "x_markers": list(evset.x_markers),
            "values": {
                mid: {
                    "value": ev.value,
                    "semantic": ev.semantic,
                    "question": ev.question,
                    "reason": ev.reason,
                    "status": ev.status,
                }
                for mid, ev in evset.evidence.items()
            },
            "raw_engine_results": {
                k: {kk: vv for kk, vv in v.items() if kk in ("score", "candle_polarity", "reason", "semantic", "passed")}
                for k, v in er.items()
            },
        }
    except Exception as exc:
        out["errors"].append(f"model_evidence:{exc}")

    # Agreement / disagreement (semantic, not arithmetic fusion)
    agree = {"aligned": [], "tension": [], "silent": []}
    me = out.get("model_evidence") or {}
    vals = (me.get("values") or {})
    crt_s = out["crt"]["state"]
    # CRT expansion/retest vs gaussian/rr polarity
    if vals:
        g = vals.get("gaussian", {}).get("value")
        rr = vals.get("rr_model", {}).get("value")
        crt_sc = vals.get("crt", {}).get("value")
        zg = vals.get("zone_gate", {}).get("value")
        if g is not None and rr is not None:
            # rr polarity >0.5 bullishish structure quality not direction — note semantic carefully
            agree["aligned"].append(
                f"gaussian={g:.3f} ({vals['gaussian']['semantic']}); "
                f"rr={rr:.3f} ({vals['rr_model']['semantic']}) — both are quality scores not directional capital"
            )
        if crt_s in ("EXPANSION", "RETEST", "DISPLACEMENT") and crt_sc is not None and crt_sc < 0.3:
            agree["tension"].append(
                f"CRT state={crt_s} (story advanced) but crt structure_rule_score={crt_sc:.3f} low"
            )
        if crt_s == "RANGE" and body_atr_like(feat) > 0.7:
            agree["tension"].append(
                "Large body/range bar while CRT state=RANGE — expansion morphology without CRT expansion state"
            )
        for mid in me.get("absent") or []:
            agree["silent"].append(f"{mid} declared absent (no engine slot)")
    out["agreement"] = agree

    # Unexplained dimensions (from continuous remainder + X_ markers + CRT gaps)
    unex = []
    cont = encoder.continuous_features
    unex.append(
        f"CONTINUOUS_UNINTERPRETED: {len(cont)} canonical features have no declared states "
        f"(measured not interpreted), e.g. {list(cont)[:12]}…"
    )
    if out.get("market_context") and out["market_context"].get("x_markers"):
        unex.append(f"X_MARKERS in context: {out['market_context']['x_markers']}")
    if out.get("market_shape") and not out["market_shape"].get("matched"):
        unex.append(
            f"SHAPE_UNNAMED: fine id {out['market_shape'].get('shape_id')} matched no coarse predicate "
            f"(recurring structure without human family name)"
        )
    if out["crt"]["state"] == "RANGE" and ep["kind"] == "large_body_expansion":
        unex.append(
            "CRT_RANGE_VS_EXPANSION_CANDLE: market printed expansion-scale body but CRT remained RANGE "
            "(state machine did not enter DISPLACEMENT/EXPANSION)"
        )
    if feat.get("volume_spike", 0) == 0 and ep["kind"] == "large_body_expansion":
        unex.append(
            "EXPANSION_WITHOUT_VOLUME_SPIKE: large body event without volume_spike=1 — "
            "participation channel not semantically tied to expansion event"
        )
    # wick geometry not in 39-dim (mature audit known gap)
    unex.append(
        "WICK_GEOMETRY_NON_VECTOR: upper_wick/lower_wick/price_position may be pipeline-computed "
        "but are not first-class 39-dim semantic states (known representational gap)"
    )
    # session vs move
    sess = (out.get("feature_states") or {}).get("session")
    if sess is not None:
        unex.append(
            f"SESSION_STATE={sess}: session is labeled but not linked to episode causality "
            f"(why this move now remains unexplained by session alone)"
        )
    out["unexplained"] = unex

    # Human market narrative synthesis from existing layers only
    out["reconstruction"] = _compose_narrative(out)
    return out


def body_atr_like(feat: dict[str, float]) -> float:
    br = float(feat.get("body_ratio") or 0)
    return br


def _compose_narrative(out: dict) -> dict[str, str]:
    m = out["market"]["narrative_seed"]
    crt = out["crt"]["state"]
    shape = (out.get("market_shape") or {}).get("label")
    ctx = (out.get("market_context") or {}).get("describe") or ""
    me = (out.get("model_evidence") or {}).get("describe") or ""
    return {
        "market_what_happened": m,
        "canonical_representation": (
            f"States: {out.get('feature_states')}; continuous snapshot: "
            f"{(out.get('canonical_features') or {}).get('continuous_snapshot')}"
        ),
        "crt_recognition": f"state={crt}; event={out['crt'].get('event')}; nearby={len(out['crt'].get('nearby_events') or [])}",
        "market_shape": f"{shape}",
        "market_context": ctx,
        "model_testimony": me,
        "agreement_summary": json.dumps(out.get("agreement"), default=str),
        "unexplained_summary": " | ".join(out.get("unexplained") or []),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=ROOT / "data" / "mt5" / "XAUUSD_M15.csv")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "research" / "xauusd_episode_semantic_reconstruction",
    )
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print("Loading corpus…", args.csv)
    df = _load_csv(args.csv)
    print(f"  bars={len(df)} {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")

    print("FeaturePipeline…")
    enriched, arr, key_to_i = _pipeline_frame(df)
    print(f"  feature rows={len(arr)}")

    print("CRT runtime…")
    events, state_by_idx, action_by_idx = _run_crt(df)
    print(f"  interesting events={len(events)}")

    print("Semantic layers…")
    encoder = FeatureStateEncoder()
    ctx_builder = MarketContextBuilder(encoder)
    shape_clf = MarketShapeClassifier(ctx_builder)
    evidence_builder = ModelEvidenceBuilder()

    # production-ish engine config for model testimony (read-only)
    from config_layer.production_config import get_prod_metadata

    meta = get_prod_metadata()
    eng_cfg = dict(meta.get("engine_runner") or {})
    eng_cfg.update(meta.get("decision_engine") or {})
    if "zone_gate" not in eng_cfg:
        eng_cfg["zone_gate"] = meta.get("engine_runner", {}).get("zone_gate") or {
            "cluster_min_n": 1,
            "cluster_spread_max": 1.0,
        }
    try:
        zone_gate = get_zone_gate()
    except Exception:
        zone_gate = None

    episodes = _select_episodes(df, events, state_by_idx, arr, key_to_i)
    print(f"Selected episodes={len(episodes)}")

    reconstructions = []
    for ep in episodes:
        print(" ", ep["id"], ep["kind"], ep["anchor_idx"])
        rec = _reconstruct_one(
            ep, df, arr, key_to_i, state_by_idx, action_by_idx,
            encoder, ctx_builder, shape_clf, evidence_builder, zone_gate, eng_cfg,
        )
        reconstructions.append(rec)

    # Cross-episode synthesis of missing dimensions
    missing = _synthesize_missing_dimensions(reconstructions, encoder)

    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus": {
            "path": str(args.csv.as_posix()),
            "sha256": _sha256(args.csv),
            "n_bars": len(df),
            "start": str(df["timestamp"].iloc[0]),
            "end": str(df["timestamp"].iloc[-1]),
        },
        "active_version": get_active_version(),
        "surfaces_used": [
            "FeaturePipeline/CANONICAL_FEATURES",
            "FeatureStateEncoder",
            "MarketContextBuilder",
            "MarketShapeClassifier",
            "CRTEngine+HTFBuilder(htf=4)",
            "ModelEvidenceBuilder(crt,gaussian,zone_gate,rr)",
        ],
        "explicitly_not_used": ["CPR", "new_indicators", "fusion_weights", "risk_tables"],
        "episodes": reconstructions,
        "missing_semantic_dimensions": missing,
        "production_behavior_changed": False,
    }

    json_path = args.out / "episodes.json"
    md_path = args.out / "reconstruction.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_render_md(payload), encoding="utf-8")
    print("Wrote", json_path)
    print("Wrote", md_path)
    return 0


def _synthesize_missing_dimensions(recs: list[dict], encoder: FeatureStateEncoder) -> list[dict]:
    """Genuine gaps from episode evidence — not new indicators."""
    gaps: list[dict] = []
    n_unnamed = sum(1 for r in recs if (r.get("market_shape") or {}).get("matched") is False)
    n_range_vs_exp = sum(
        1 for r in recs
        if r.get("kind") == "large_body_expansion" and (r.get("crt") or {}).get("state") == "RANGE"
    )
    n_err = sum(1 for r in recs if r.get("errors"))
    n_x = sum(1 for r in recs if (r.get("market_context") or {}).get("x_markers"))

    gaps.append({
        "dimension": "CONTINUOUS_FEATURE_SEMANTICS",
        "evidence": f"{len(encoder.continuous_features)}/39 canonical features have no declared states",
        "examples": list(encoder.continuous_features)[:15],
        "why_missing": "Features measure magnitude but Layer-2 states do not interpret them — "
                       "episodes show expansion/momentum only as raw numbers, not semantic bands.",
        "not_a_new_indicator": True,
    })
    if n_unnamed:
        gaps.append({
            "dimension": "NAMED_SHAPE_COVERAGE",
            "evidence": f"{n_unnamed}/{len(recs)} episodes had UNNAMED fine shape ids",
            "why_missing": "Fine context hashes recur but coarse predicates in market_shapes.yaml "
                           "do not name these episodes — structure without vocabulary.",
            "not_a_new_indicator": True,
        })
    if n_range_vs_exp:
        gaps.append({
            "dimension": "CRT_STATE_VS_PRICE_EXPANSION",
            "evidence": f"{n_range_vs_exp} large-body episodes with CRT state still RANGE",
            "why_missing": "Price printed expansion morphology; CRT story stayed in RANGE. "
                           "Missing semantic link: 'expansion event' as market fact independent of state machine.",
            "not_a_new_indicator": True,
        })
    gaps.append({
        "dimension": "WICK_AND_PRICE_POSITION_SEMANTICS",
        "evidence": "Pipeline may compute upper/lower wick; 39-dim + states do not treat them as first-class states",
        "why_missing": "Rejection/absorption (wick) vs commitment (body) is visible on OHLC but not a Layer-2 dimension.",
        "not_a_new_indicator": True,
    })
    gaps.append({
        "dimension": "PARTICIPATION_VS_EXPANSION",
        "evidence": "volume_spike often 0 on large-body bars; volume is continuous/uninterpreted",
        "why_missing": "Who participated (intensity) is not bound to expansion episodes in the semantic stack.",
        "not_a_new_indicator": True,
    })
    gaps.append({
        "dimension": "MODEL_TESTIMONY_VS_STORY_ALIGNMENT",
        "evidence": "Scores are quality semantics (structure/neighbourhood/polarity) not 'this CRT chapter is valid'",
        "why_missing": "No declared cross-layer link between CRT state chapter and model evidence questions.",
        "not_a_new_indicator": True,
    })
    gaps.append({
        "dimension": "TEMPORAL_CAUSALITY_OF_EPISODES",
        "evidence": "session/hour labeled but episode selection does not get a 'why now' semantic object",
        "why_missing": "Time is a feature state, not an episode-level causal context (schedule/regime chapter).",
        "not_a_new_indicator": True,
    })
    if n_x:
        gaps.append({
            "dimension": "STATE_DOMAIN_DRIFT",
            "evidence": f"{n_x} episodes carried X_ markers",
            "why_missing": "Declared state domains disagree with realized feature values — semantics incomplete or mis-scaled.",
            "not_a_new_indicator": True,
        })
    if n_err:
        gaps.append({
            "dimension": "LAYER_COVERAGE_FAILURES",
            "evidence": f"{n_err} episodes had layer errors (features/evidence)",
            "why_missing": "Some meaningful bars never receive full semantic stack (warmup, registry gaps).",
            "not_a_new_indicator": True,
        })
    return gaps


def _render_md(payload: dict) -> str:
    lines = [
        "# XAUUSD episode semantic reconstruction",
        "",
        f"**Generated:** {payload['generated_utc']}",
        f"**Corpus:** `{payload['corpus']['path']}` ({payload['corpus']['n_bars']} bars)",
        f"**Window:** {payload['corpus']['start']} → {payload['corpus']['end']}",
        f"**ACTIVE_VERSION:** `{payload['active_version']}`",
        "",
        "Surfaces: " + ", ".join(f"`{s}`" for s in payload["surfaces_used"]),
        "",
        "Explicitly excluded: " + ", ".join(f"`{s}`" for s in payload["explicitly_not_used"]),
        "",
        "---",
        "",
        "## Missing semantic dimensions (cross-episode)",
        "",
    ]
    for g in payload["missing_semantic_dimensions"]:
        lines += [
            f"### {g['dimension']}",
            "",
            f"- **Evidence:** {g['evidence']}",
            f"- **Why missing:** {g['why_missing']}",
            f"- **New indicator?** {not g.get('not_a_new_indicator', True)} (must stay dimension/ontology, not a formula hunt)",
            "",
        ]
    lines += ["---", "", "## Episodes", ""]
    for ep in payload["episodes"]:
        lines += [
            f"### {ep['episode_id']} ({ep['kind']})",
            "",
            f"**Why selected:** {ep['why_selected']}",
            "",
            f"**Market:** {ep['market']['narrative_seed']}",
            "",
            f"**CRT:** state=`{(ep.get('crt') or {}).get('state')}` event=`{(ep.get('crt') or {}).get('event')}`",
            "",
        ]
        if ep.get("market_shape"):
            lines.append(f"**Shape:** `{ep['market_shape'].get('label')}` family=`{ep['market_shape'].get('family')}`")
            lines.append("")
        if ep.get("market_context"):
            lines.append("**Context:**")
            lines.append("```")
            lines.append(ep["market_context"].get("describe") or "")
            lines.append("```")
            lines.append("")
        if ep.get("model_evidence"):
            lines.append("**Model testimony:**")
            lines.append("```")
            lines.append(ep["model_evidence"].get("describe") or "")
            lines.append("```")
            lines.append("")
        if ep.get("agreement"):
            lines.append(f"**Agreement:** {json.dumps(ep['agreement'], default=str)}")
            lines.append("")
        if ep.get("unexplained"):
            lines.append("**Unexplained (episode-local):**")
            for u in ep["unexplained"]:
                lines.append(f"- {u}")
            lines.append("")
        if ep.get("errors"):
            lines.append(f"**Errors:** {ep['errors']}")
            lines.append("")
        lines.append("---")
        lines.append("")
    lines += [
        "## Method notes",
        "",
        "- Episode selection uses CRT events + large body/range days + long EXPANSION dwells — all from existing runtime.",
        "- Continuous features are reported as measured values; only ontology-declared states enter Layer-2/4/5.",
        "- Model evidence is testimony with declared semantics; no fusion arithmetic.",
        "- CPR intentionally not used.",
        "",
        "`PRODUCTION_BEHAVIOR_CHANGED=NO`",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
