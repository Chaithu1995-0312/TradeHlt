#!/usr/bin/env python3
"""
train_gaussian_xauusd.py
========================
Train a GaussianNB model on the Phase-1 frozen XAUUSD corpus, then evaluate on
the trailing 2-month window (same window as prior observation runs).

Feature schema
--------------
Live production canonical order (CANONICAL_FEATURE_ORDER / GAUSSIAN_SCHEMA).
NOTE: live dim is **39** (schema v4.0). Pre-v4 docs/artifacts said "38"; this
trainer uses the **current** production feature schema, not a reconstructed v3
38-vector. Manifest records both numbers explicitly.

Label generation (production-aligned)
-------------------------------------
Spine TRADE_OPENED on XAUUSD is N≈1 (starved) — insufficient for
MIN_GAUSSIAN_SAMPLES=20. Training units are therefore CRT **SWEEP detections**
on the frozen corpus (direction-bearing structure events), labeled with the
**governing exit model**:

  forward_walk(exit_model='intrabar_fixed', max_forward=40)
  + cost_bps=12  (clean_labels / M4 production research standard)

y_rr = outcome.rr_achieved net of cost  (compatible with extract_target priority:
rr_achieved → pnl_rr_net). Classes via features.dataset_builder.rr_to_class.

Temporal discipline
-------------------
Train only on bars with timestamp < eval_window_start (trailing 2 calendar
months held out). Eval scores every bar in the 2m window (no label required).

Outputs
-------
  models/XAUUSD/<run_id>/gaussian_<version>.json     — model artifact
  models/XAUUSD/<run_id>/train_dataset.jsonl         — training rows (features+y)
  results/gaussian_xauusd_train/<run_id>/...         — train+eval manifests
  results/gaussian_xauusd_train/.../eval_scores_2m.csv
  results/gaussian_xauusd_train/.../bar_semantic_journal.jsonl
      — bar-level semantic journal (schema bar_semantic.v1) for progress +
        later LLM explanations (reason_code is authoritative; narrative is render)

Authority: OBSERVATION / research artifact only.
  - Does NOT promote into gaussian_registry active map
  - Does NOT change engine_runner.gaussian_impl
  - No economic claim / no live wiring
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INSTRUMENT = "XAUUSD"
COST_BPS = 12.0
MAX_FORWARD = 40
EXIT_MODEL = "intrabar_fixed"
# Production crt_engine knobs (used for Signal SL/TP geometry)
DEFAULT_SL_ATR_MULT = 1.0   # risk distance in ATR units at sweep entry
DEFAULT_TP_ATR_MULT = 1.0   # crt_engine.tp1_atr_multiplier
# Semantic journal heartbeats (stdout + PROGRESS events)
HEARTBEAT_EVERY = 500


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stats(arr) -> dict:
    a = np.asarray(arr, dtype=np.float64)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return {"n": int(a.size), "n_finite": 0, "n_nan": int(a.size)}
    return {
        "n": int(a.size),
        "n_finite": int(finite.size),
        "n_nan": int(a.size - finite.size),
        "mean": float(finite.mean()),
        "std": float(finite.std()),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "p01": float(np.percentile(finite, 1)),
        "p50": float(np.percentile(finite, 50)),
        "p99": float(np.percentile(finite, 99)),
        "n_unique_6dp": int(np.unique(np.round(finite, 6)).size),
        "is_constant": bool(finite.std() < 1e-12),
    }


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
    sy = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    return cov / (sx * sy) if sx > 0 and sy > 0 else 0.0


@dataclass
class Bar:
    index: int
    timestamp: Any
    open: float
    high: float
    low: float
    close: float
    volume: float


def _cost_rr(rr_gross: float, entry: float, atr: float, sl_atr_mult: float) -> float:
    """Convert gross RR to net RR after round-trip cost_bps on notional.

    Approximates cost in R-units: cost_frac * entry / risk_distance.
    """
    risk = max(sl_atr_mult * atr, 1e-12)
    cost_price = entry * (COST_BPS / 10_000.0)
    cost_r = cost_price / risk
    return float(rr_gross) - cost_r


def build_training_units(
    df: pd.DataFrame,
    enriched: pd.DataFrame,
    feature_order: list[str],
    *,
    train_end_ts: pd.Timestamp,
    sl_atr_mult: float,
    tp_atr_mult: float,
    tracker: Any = None,
) -> tuple[list[dict], dict]:
    """CRT SWEEP → forward_walk labels with canonical features at entry bar.

    When ``tracker`` is a BarSemanticTracker, every interesting bar decision is
    journaled with a stable reason_code + LLM narrative seed.
    """
    from config_layer.crt_engine_v2 import CRTEngine
    from config_layer.config_builder import ConfigBuilder
    from config_layer.production_config import get_prod_section
    from runtime.backtest_v2 import HTFBuilder, CandleLoader
    from research.contracts import Signal
    from research.measurement.forward_walk import forward_walk
    from training.bar_semantic_tracker import ReasonCode

    crt_cfg = ConfigBuilder().build(instrument=INSTRUMENT)
    engine = CRTEngine(config=crt_cfg)

    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

    corpus_path = guard_xauusd_csv_path("data/mt5/XAUUSD_M15.csv", INSTRUMENT)
    loader = CandleLoader(str(corpus_path), instrument=INSTRUMENT)
    htf_n = 4
    try:
        htf_n = int(get_prod_section("backtest").get("htf_candles_per_range", 4))
    except Exception:
        pass
    htf = HTFBuilder(candles_per_htf=htf_n, instrument=INSTRUMENT)

    # Map timestamp → enriched feature row index (after pipeline drop)
    enr = enriched.copy()
    enr["timestamp"] = pd.to_datetime(enr["timestamp"])
    ts_to_enr = {pd.Timestamp(t): i for i, t in enumerate(enr["timestamp"])}

    # Pre-build bar list for forward_walk future slices
    raw_ts = pd.to_datetime(df["timestamp"])
    bars: list[Bar] = []
    for i in range(len(df)):
        bars.append(
            Bar(
                index=i,
                timestamp=raw_ts.iloc[i].to_pydatetime()
                if hasattr(raw_ts.iloc[i], "to_pydatetime")
                else raw_ts.iloc[i],
                open=float(df.iloc[i]["open"]),
                high=float(df.iloc[i]["high"]),
                low=float(df.iloc[i]["low"]),
                close=float(df.iloc[i]["close"]),
                volume=float(df.iloc[i].get("volume", 0.0) or 0.0),
            )
        )

    units: list[dict] = []
    skips: Counter = Counter()
    event_counts: Counter = Counter()

    # Warmup / init CRT via HTF seeds when available
    initialised = False
    warmup_n = 30
    try:
        bc = get_prod_section("backtest")
        warmup_n = int(bc.get("warmup_candles", 30))
    except Exception:
        pass

    if tracker is not None:
        tracker.set_phase("label_build_crt_sweep")
        tracker.total_bars = len(df)

    n_streamed = 0
    prev_state = None
    for candle in loader.stream():
        n_streamed += 1
        htf.push(candle)

        ts_raw = getattr(candle, "timestamp", None)
        if ts_raw is None and isinstance(candle, dict):
            ts_raw = candle.get("timestamp")
        # Stream ordinal is the reliable progress index; candle.index is often unset/0.
        bar_idx_guess = n_streamed - 1
        _ci = getattr(candle, "index", None)
        if _ci is not None:
            try:
                _ci_i = int(_ci)
                if _ci_i > 0:
                    bar_idx_guess = _ci_i
            except (TypeError, ValueError):
                pass

        if n_streamed < warmup_n:
            if tracker is not None:
                tracker.on_streamed_bar(
                    bar_index=int(bar_idx_guess),
                    timestamp=ts_raw,
                    crt_state=None,
                    crt_event=None,
                    is_warmup=True,
                    warmup_n=warmup_n,
                )
            continue
        if not initialised:
            seeds = htf.seed_candles()
            if seeds:
                try:
                    engine.initialise_range(seeds, htf.current_htf_id, "UNKNOWN")
                except Exception:
                    pass
                initialised = True
            else:
                continue

        try:
            out = engine.process_candle(candle, htf.current_htf_id)
        except Exception as exc:
            skips["crt_exception"] += 1
            if tracker is not None:
                tracker.on_crt_exception(
                    bar_index=int(bar_idx_guess),
                    timestamp=ts_raw,
                    error=exc,
                )
            continue

        st = getattr(getattr(engine, "state", None), "current_state", None)
        st_name = getattr(st, "name", str(st) if st is not None else "")
        if st_name:
            event_counts[f"ST:{st_name}"] += 1

        # Prefer explicit SWEEP events from process_candle / nested events
        events = []
        crt_event_name = None
        if isinstance(out, dict):
            ev = out.get("event") or out.get("event_type") or out.get("status")
            crt_event_name = str(ev) if ev is not None else None
            if ev:
                events.append(out)
            for e in out.get("events") or []:
                if isinstance(e, dict):
                    events.append(e)
            if ev:
                event_counts[f"EV:{ev}"] = event_counts.get(f"EV:{ev}", 0) + 1

        if tracker is not None:
            tracker.on_streamed_bar(
                bar_index=int(bar_idx_guess),
                timestamp=ts_raw,
                crt_state=st_name or None,
                crt_event=crt_event_name,
                is_warmup=False,
                warmup_n=warmup_n,
            )

        is_sweep = False
        direction = None
        for e in events:
            ename = str(e.get("event") or e.get("event_type") or e.get("status") or "").upper()
            if "SWEEP" in ename:
                is_sweep = True
                d = e.get("direction") or (e.get("metadata") or {}).get("direction")
                if d is not None:
                    direction = str(d).lower()

        # State edge: first bar entering SWEEP
        if not is_sweep and st_name == "SWEEP" and prev_state != "SWEEP":
            is_sweep = True
        prev_state = st_name

        if is_sweep and direction is None:
            d = getattr(getattr(engine, "state", None), "direction", None)
            if d is not None:
                direction = str(getattr(d, "name", d)).lower()
            for attr in ("sweep_direction", "trade_direction", "bias"):
                if direction in ("long", "short"):
                    break
                v = getattr(getattr(engine, "state", None), attr, None)
                if v is not None:
                    direction = str(getattr(v, "name", v)).lower()

        if direction is not None:
            if "long" in direction or direction in ("buy", "bull", "1"):
                direction = "long"
            elif "short" in direction or direction in ("sell", "bear", "-1"):
                direction = "short"

        if not is_sweep:
            continue

        # From here: SWEEP candidate path (always journal)
        ts = pd.Timestamp(ts_raw)
        if tracker is not None:
            tracker.on_sweep_candidate(
                bar_index=int(bar_idx_guess),
                timestamp=ts,
                crt_state=st_name or None,
                direction=direction if direction in ("long", "short") else None,
            )

        if direction not in ("long", "short"):
            skips["no_direction"] += 1
            if tracker is not None:
                tracker.on_label_skip(
                    ReasonCode.NO_DIRECTION,
                    bar_index=int(bar_idx_guess),
                    timestamp=ts,
                    crt_state=st_name or None,
                )
            continue

        if ts >= train_end_ts:
            skips["in_holdout_window"] += 1
            if tracker is not None:
                tracker.on_label_skip(
                    ReasonCode.IN_HOLDOUT_WINDOW,
                    bar_index=int(bar_idx_guess),
                    timestamp=ts,
                    crt_state=st_name or None,
                    direction=direction,
                    extra={"holdout_start": str(train_end_ts)},
                )
            continue

        idx = getattr(candle, "index", None)
        if idx is None:
            matches = np.where(raw_ts.values == np.datetime64(ts))[0]
            if len(matches) == 0:
                matches = np.where(raw_ts.astype(str) == str(ts))[0]
            if len(matches) == 0:
                skips["ts_not_in_raw"] += 1
                if tracker is not None:
                    tracker.on_label_skip(
                        ReasonCode.TS_NOT_IN_RAW,
                        bar_index=int(bar_idx_guess),
                        timestamp=ts,
                        direction=direction,
                    )
                continue
            idx = int(matches[0])
        else:
            idx = int(idx)

        if idx < 0 or idx >= len(bars) - 2:
            skips["idx_oob"] += 1
            if tracker is not None:
                tracker.on_label_skip(
                    ReasonCode.IDX_OOB,
                    bar_index=idx,
                    timestamp=ts,
                    direction=direction,
                )
            continue

        enr_i = ts_to_enr.get(ts)
        if enr_i is None:
            enr_i = ts_to_enr.get(pd.Timestamp(str(ts)))
        if enr_i is None:
            skips["no_features"] += 1
            if tracker is not None:
                tracker.on_label_skip(
                    ReasonCode.NO_FEATURES,
                    bar_index=idx,
                    timestamp=ts,
                    direction=direction,
                )
            continue
        feat_row = enr.iloc[enr_i]
        try:
            feat = {k: float(feat_row[k]) for k in feature_order}
        except Exception:
            skips["feature_cast"] += 1
            if tracker is not None:
                tracker.on_label_skip(
                    ReasonCode.FEATURE_CAST_FAIL,
                    bar_index=idx,
                    timestamp=ts,
                    direction=direction,
                )
            continue

        atr = float(feat.get("atr", 0.0) or 0.0)
        close = float(bars[idx].close)
        atr_abs = atr * close if 0 < atr < 1.0 and close > 1.0 else atr
        if atr_abs <= 0:
            atr_abs = max(bars[idx].high - bars[idx].low, 1e-8)

        entry = close
        sig = Signal(
            instrument=INSTRUMENT,
            timestamp=bars[idx].timestamp,
            entry_index=idx,
            direction=direction,
            entry=entry,
            sl_atr_mult=float(sl_atr_mult),
            tp_atr_mult=float(tp_atr_mult),
            atr=float(atr_abs),
            meta={"source": "crt_sweep", "state": st_name},
        )
        future = bars[idx + 1 :]
        try:
            outcome = forward_walk(
                sig, future, max_forward=MAX_FORWARD, exit_model=EXIT_MODEL
            )
        except Exception as exc:
            skips["forward_walk_fail"] += 1
            if tracker is not None:
                tracker.on_label_skip(
                    ReasonCode.FORWARD_WALK_FAIL,
                    bar_index=idx,
                    timestamp=ts,
                    direction=direction,
                    extra={
                        "exit_model": EXIT_MODEL,
                        "error_type": type(exc).__name__,
                        "error_msg": str(exc)[:200],
                    },
                )
            continue

        rr_gross = float(
            getattr(outcome, "rr_achieved", None)
            or getattr(outcome, "rr", 0.0)
            or 0.0
        )
        rr_net = _cost_rr(rr_gross, entry, atr_abs, sl_atr_mult)
        vec = [float(feat[k]) for k in feature_order]
        exit_reason = str(
            getattr(outcome, "exit_reason", None)
            or getattr(outcome, "reason", "")
            or getattr(outcome, "outcome", "")
        )

        units.append(
            {
                "timestamp": str(ts),
                "bar_index": idx,
                "direction": direction,
                "entry": entry,
                "atr_abs": atr_abs,
                "sl_atr_mult": sl_atr_mult,
                "tp_atr_mult": tp_atr_mult,
                "rr_gross": rr_gross,
                "rr_net": rr_net,
                "y_rr": rr_net,
                "exit_reason": exit_reason,
                "feature_vec": vec,
            }
        )
        if tracker is not None:
            tracker.on_label_accepted(
                bar_index=idx,
                timestamp=ts,
                crt_state=st_name or None,
                direction=direction,
                y_rr=rr_net,
                rr_gross=rr_gross,
                exit_reason=exit_reason,
                entry=entry,
                atr_abs=atr_abs,
                sl_atr_mult=sl_atr_mult,
                tp_atr_mult=tp_atr_mult,
            )

    meta = {
        "n_streamed": n_streamed,
        "n_units": len(units),
        "skips": dict(skips),
        "event_counts_sample": dict(event_counts.most_common(30)),
        "entry_definition": "CRT SWEEP detection (direction-bearing)",
        "label_definition": (
            f"forward_walk(exit_model={EXIT_MODEL!r}, max_forward={MAX_FORWARD}) "
            f"then net cost_bps={COST_BPS} → y_rr"
        ),
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "train_end_ts": str(train_end_ts),
        "bar_semantic": tracker.summary() if tracker is not None else None,
    }
    return units, meta


def main() -> int:
    from data_ingestion.xauusd_phase1_candidate import (
        PHASE1_SHA256,
        PHASE1_STATUS,
        guard_xauusd_csv_path,
    )
    from features.feature_pipeline import FeaturePipeline
    from features.feature_schema import (
        CANONICAL_FEATURE_DIM,
        CANONICAL_FEATURE_ORDER,
        FEATURE_ORDER_HASH,
        GAUSSIAN_SCHEMA,
        SCHEMA_HASH,
        SCHEMA_V3_FEATURE_DIM,
    )
    from features.dataset_builder import rr_to_class
    from training.trainer import (
        train_gaussian,
        cross_val_gaussian,
        save_gaussian_model,
        MIN_GAUSSIAN_SAMPLES,
        load_gaussian_model,
    )
    from features.gaussian_schema_contract import extract_model_feature_vector
    from training.bar_semantic_tracker import (
        SCHEMA_VERSION as BAR_SEM_SCHEMA,
        BarSemanticTracker,
        Kind,
        ReasonCode,
    )

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    version = f"xauusd_nb_{run_ts}"
    run_id = f"gaussian_xauusd_train_{run_ts}"

    model_dir = ROOT / "models" / "XAUUSD" / run_ts
    out_dir = ROOT / "results" / "gaussian_xauusd_train" / run_id
    model_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    journal_path = out_dir / "bar_semantic_journal.jsonl"
    tracker = BarSemanticTracker(
        run_id=run_id,
        instrument=INSTRUMENT,
        path=journal_path,
        total_bars=0,  # set after corpus load
        every_bar=False,  # interesting bars + heartbeats (LLM-dense, not 47k noise)
        heartbeat_every=HEARTBEAT_EVERY,
        phase="init",
    ).open()

    # ── corpus ──────────────────────────────────────────────────────────
    corpus = Path(guard_xauusd_csv_path("data/mt5/XAUUSD_M15.csv", INSTRUMENT))
    df = pd.read_csv(corpus)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    corpus_sha = _sha256_file(corpus)
    tracker.total_bars = len(df)
    print(f"corpus rows={len(df)} {df.timestamp.iloc[0]} .. {df.timestamp.iloc[-1]}")
    print(f"sha={corpus_sha[:16]}... status={PHASE1_STATUS}")
    print(f"bar_semantic journal → {journal_path} (schema {BAR_SEM_SCHEMA})")

    end = df["timestamp"].max()
    eval_start = end - pd.DateOffset(months=2)
    print(f"eval window start (holdout)={eval_start} end={end}")

    # ── features ────────────────────────────────────────────────────────
    tracker.set_phase("feature_pipeline")
    print("FeaturePipeline on full corpus...")
    pipe = FeaturePipeline(df)
    enriched, vectors = pipe.run()
    print(f"enriched={len(enriched)} vectors={vectors.shape}")
    tracker.emit(
        Kind.NOTE,
        ReasonCode.OPERATOR_NOTE,
        bar_index=-1,
        timestamp=None,
        extra={
            "note": (
                f"FeaturePipeline complete: enriched={len(enriched)} "
                f"vectors={list(vectors.shape)} dim={CANONICAL_FEATURE_DIM}."
            ),
        },
        force=True,
    )

    feature_order = list(CANONICAL_FEATURE_ORDER)
    assert len(feature_order) == CANONICAL_FEATURE_DIM

    # Production SL/TP mults
    sl_mult = DEFAULT_SL_ATR_MULT
    tp_mult = DEFAULT_TP_ATR_MULT
    try:
        from config_layer.production_config import get_prod_section

        crt = get_prod_section("crt_engine")
        tp_mult = float(crt.get("tp1_atr_multiplier", tp_mult))
        # atr_min_displacement is displacement threshold not SL; prefer 1.0 SL
        sl_mult = 1.0
        print(f"tp1_atr_multiplier={tp_mult} sl_atr_mult={sl_mult}")
    except Exception as e:
        print(f"config soft-fail: {e}")

    # ── build labeled units (train period only) ─────────────────────────
    print("Building CRT-SWEEP + forward_walk labels (train period)...")
    print(
        f"[BAR_SEM] heartbeats every {HEARTBEAT_EVERY} bars; "
        "interesting events (state change / sweep / label / skip) always logged"
    )
    try:
        units, unit_meta = build_training_units(
            df,
            enriched,
            feature_order,
            train_end_ts=eval_start,
            sl_atr_mult=sl_mult,
            tp_atr_mult=tp_mult,
            tracker=tracker,
        )
    except Exception:
        tracker.close()
        raise
    print(f"units={len(units)} meta_skips={unit_meta.get('skips')}")

    if len(units) < MIN_GAUSSIAN_SAMPLES:
        print(
            f"WARNING: only {len(units)} units < MIN_GAUSSIAN_SAMPLES={MIN_GAUSSIAN_SAMPLES}"
        )
        tracker.emit(
            Kind.NOTE,
            ReasonCode.OPERATOR_NOTE,
            bar_index=-1,
            timestamp=None,
            extra={
                "note": (
                    f"Insufficient training units: {len(units)} < "
                    f"{MIN_GAUSSIAN_SAMPLES}; skips={unit_meta.get('skips')}"
                ),
            },
            force=True,
        )
        tracker.close()
        raise SystemExit(
            f"Insufficient training units: {len(units)} < {MIN_GAUSSIAN_SAMPLES}. "
            f"skips={unit_meta.get('skips')}"
        )

    # Sort temporal
    units.sort(key=lambda u: u["timestamp"])
    X = [u["feature_vec"] for u in units]
    y_rr = [float(u["y_rr"]) for u in units]
    y_cls = [rr_to_class(r) for r in y_rr]
    class_counts = Counter(y_cls)

    # Persist dataset
    ds_path = model_dir / "train_dataset.jsonl"
    with ds_path.open("w", encoding="utf-8") as f:
        for u in units:
            row = {k: v for k, v in u.items() if k != "feature_vec"}
            row["feature_vec"] = u["feature_vec"]
            f.write(json.dumps(row) + "\n")

    # ── train ───────────────────────────────────────────────────────────
    tracker.set_phase("train_gaussian_nb")
    print(f"train_gaussian n={len(X)} class_counts={dict(class_counts)}")
    model, scaler, train_metrics = train_gaussian(X, y_rr, train_ratio=0.70)
    cv_result = cross_val_gaussian(X, y_rr)
    print(f"train_metrics={train_metrics}")
    print(f"cv={ {k: cv_result.get(k) for k in ('stable','corr_mean','corr_std','n_folds') if k in cv_result or True} }")

    # ── save artifact ───────────────────────────────────────────────────
    model_name = f"XAUUSD/{run_ts}/gaussian_{version}.json"
    model_path = save_gaussian_model(
        model,
        scaler,
        {
            **train_metrics,
            "cv_stable": cv_result.get("stable"),
            "cv_corr_mean": cv_result.get("corr_mean"),
            "cv_corr_std": cv_result.get("corr_std"),
            "instrument": INSTRUMENT,
            "entry_definition": unit_meta["entry_definition"],
            "label_definition": unit_meta["label_definition"],
            "n_units_total": len(units),
            "class_counts": dict(class_counts),
            "cost_bps": COST_BPS,
            "exit_model": EXIT_MODEL,
            "max_forward": MAX_FORWARD,
            "sl_atr_mult": sl_mult,
            "tp_atr_mult": tp_mult,
            "holdout_eval_start": str(eval_start),
            "canonical_note": (
                f"Trained on live CANONICAL dim={CANONICAL_FEATURE_DIM} (v4). "
                f"Pre-v4 '38' = SCHEMA_V3_FEATURE_DIM={SCHEMA_V3_FEATURE_DIM}."
            ),
        },
        name=model_name,
        feature_schema=list(feature_order),
    )
    # Ensure feature_schema_resolved path works on load (name-anchored)
    print(f"saved model → {model_path}")

    # Register under gaussian_registry WITHOUT promote (append inactive entry)
    registry_note = None
    try:
        from core.model_registry import register_gaussian

        register_gaussian(
            version=version,
            model_file=str(model_path).replace("\\", "/"),
            feature_schema=list(feature_order),
            metrics={
                **train_metrics,
                "instrument": INSTRUMENT,
                "n_units": len(units),
            },
            instrument=INSTRUMENT,
        )
        # Force active=false if register sets active
        reg_path = ROOT / "models" / "gaussian_registry.json"
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        if version in reg and isinstance(reg[version], dict):
            reg[version]["active"] = False
            reg[version]["instrument"] = INSTRUMENT
            reg[version]["note"] = (
                "XAUUSD research train; NOT promoted; gaussian_impl stays heuristic"
            )
            reg_path.write_text(json.dumps(reg, indent=2), encoding="utf-8")
        registry_note = f"registered inactive version={version}"
    except Exception as e:
        registry_note = f"registry soft-fail: {type(e).__name__}: {e}"
        print(registry_note)

    # ── evaluate on 2m window (every bar) ───────────────────────────────
    tracker.set_phase("eval_2m_scores")
    print("Evaluating on trailing 2m window (every bar)...")
    # reload to exercise load path (save_gaussian_model may return a relative path
    # already under models/ — never assume absolute for Path.relative_to).
    mp = Path(model_path)
    if mp.is_absolute():
        try:
            rel = str(mp.resolve().relative_to((ROOT / "models").resolve())).replace(
                "\\", "/"
            )
        except ValueError:
            # Fall back: strip a leading models/ segment if present
            s = str(mp).replace("\\", "/")
            rel = s.split("/models/", 1)[-1] if "/models/" in s else s
    else:
        rel = str(mp).replace("\\", "/")
        if rel.startswith("models/"):
            rel = rel[len("models/") :]
    model2, scaler2, meta2 = load_gaussian_model(rel)
    resolved = list(meta2.get("feature_schema_resolved") or feature_order)

    enr_ts = pd.to_datetime(enriched["timestamp"])
    enr_mask = (enr_ts >= eval_start) & (enr_ts <= end)
    window_df = enriched.loc[enr_mask].reset_index(drop=True)
    print(f"eval bars={len(window_df)} {window_df.timestamp.iloc[0]} .. {window_df.timestamp.iloc[-1]}")

    cols = [c for c in feature_order if c in window_df.columns]
    records = window_df[cols].to_dict(orient="records")
    timestamps = [str(t) for t in window_df["timestamp"].tolist()]

    scores = np.full(len(records), np.nan)
    expected_rrs = np.full(len(records), np.nan)
    confs = np.full(len(records), np.nan)
    exceptions = 0
    first_err = None
    # Progress heartbeats during eval (reuse tracker heartbeat cadence)
    eval_hb = max(HEARTBEAT_EVERY // 2, 100)
    for i, feat in enumerate(records):
        try:
            vec = extract_model_feature_vector(feat, resolved)
            if len(vec) != model2.n_features:
                exceptions += 1
                continue
            scaled = scaler2.transform_one(vec)
            err, conf, _probs = model2.predict_expected_rr(scaled)
            sc = 1.0 / (1.0 + math.exp(-float(err)))
            scores[i] = max(0.0, min(1.0, sc))
            expected_rrs[i] = float(err)
            confs[i] = float(conf)
        except Exception as e:
            exceptions += 1
            if first_err is None:
                first_err = f"{type(e).__name__}: {e}"
            tracker.emit(
                Kind.EVAL_SCORE,
                ReasonCode.SCORE_FAIL,
                bar_index=i,
                timestamp=timestamps[i] if i < len(timestamps) else None,
                extra={"error_type": type(e).__name__, "error_msg": str(e)[:200]},
            )
        if (i + 1) % eval_hb == 0 or (i + 1) == len(records):
            tracker.emit(
                Kind.PROGRESS,
                ReasonCode.HEARTBEAT,
                bar_index=i,
                timestamp=timestamps[i] if i < len(timestamps) else None,
                extra={
                    "note": f"eval progress {i+1}/{len(records)}",
                    "n_streamed": i + 1,
                    "total_bars": len(records),
                },
                force=True,
            )

    scores_csv = out_dir / f"eval_scores_2m_{run_ts}.csv"
    pd.DataFrame(
        {
            "timestamp": timestamps,
            f"score_{version}": [
                None if not np.isfinite(x) else round(float(x), 6) for x in scores
            ],
            f"expected_rr_{version}": [
                None if not np.isfinite(x) else round(float(x), 6) for x in expected_rrs
            ],
            f"confidence_{version}": [
                None if not np.isfinite(x) else round(float(x), 6) for x in confs
            ],
        }
    ).to_csv(scores_csv, index=False)

    # ── manifests ───────────────────────────────────────────────────────
    train_manifest = {
        "run_id": run_id,
        "timestamp_utc": run_ts,
        "version": version,
        "task": "Train GaussianNB on frozen XAUUSD + eval trailing 2m",
        "authority": (
            "RESEARCH ARTIFACT ONLY — not promoted; gaussian_impl stays heuristic; "
            "no economic claim"
        ),
        "instrument": INSTRUMENT,
        "corpus": {
            "path": str(corpus).replace("\\", "/"),
            "sha256": corpus_sha,
            "phase1_pin": PHASE1_SHA256,
            "phase1_status": PHASE1_STATUS,
            "rows": int(len(df)),
            "range": [str(df.timestamp.iloc[0]), str(df.timestamp.iloc[-1])],
        },
        "feature_schema": {
            "live_canonical_dim": CANONICAL_FEATURE_DIM,
            "schema_v3_dim_historical_38": SCHEMA_V3_FEATURE_DIM,
            "used_dim": len(feature_order),
            "feature_order": feature_order,
            "feature_order_hash": FEATURE_ORDER_HASH,
            "schema_hash": SCHEMA_HASH,
            "gaussian_schema_n_features": GAUSSIAN_SCHEMA.n_features,
            "gaussian_schema_version": GAUSSIAN_SCHEMA.version,
            "note": (
                "User wording 'canonical 38' maps to pre-v4 docs; this train uses "
                "current production canonical order (39-dim v4)."
            ),
        },
        "labels": unit_meta,
        "bar_semantic_journal": {
            "schema_version": BAR_SEM_SCHEMA,
            "path": str(journal_path).replace("\\", "/"),
            "purpose": (
                "Per-bar semantic journal for operator progress + later LLM explanations. "
                "reason_code is authoritative; narrative is a deterministic template render."
            ),
            "every_bar": False,
            "heartbeat_every": HEARTBEAT_EVERY,
            "llm_contract": (
                "Explainer must ground claims in reason_code + payload; "
                "must not invent causes not present in the journal."
            ),
        },
        "dataset": {
            "n_units": len(units),
            "class_counts": dict(class_counts),
            "y_rr_stats": _stats(y_rr),
            "dataset_path": str(ds_path).replace("\\", "/"),
            "temporal_holdout_start": str(eval_start),
        },
        "training": {
            "metrics": train_metrics,
            "cv": {
                "stable": cv_result.get("stable"),
                "corr_mean": cv_result.get("corr_mean"),
                "corr_std": cv_result.get("corr_std"),
                "n_folds": cv_result.get("n_folds"),
                "fold_corrs": cv_result.get("fold_corrs"),
            },
            "min_gaussian_samples": MIN_GAUSSIAN_SAMPLES,
        },
        "artifact": {
            "model_path": str(model_path).replace("\\", "/"),
            "model_sha256": _sha256_file(Path(model_path)),
            "n_features": model.n_features,
            "registry_note": registry_note,
            "promoted": False,
            "active": False,
        },
        "evaluation_2m": {
            "window_start": str(eval_start),
            "window_end": str(end),
            "n_bars": len(records),
            "ts_first": timestamps[0] if timestamps else None,
            "ts_last": timestamps[-1] if timestamps else None,
            "exceptions": exceptions,
            "first_error": first_err,
            "score_stats": _stats(scores),
            "expected_rr_stats": _stats(expected_rrs),
            "confidence_stats": _stats(confs),
            "scores_csv": str(scores_csv).replace("\\", "/"),
            "named_export_file": (
                "data/XAUUSD_W2026-03-23-to-2026-05-21.csv  # same 2m window family"
            ),
        },
        "paired_with": [
            "results/gaussian_xauusd_2m/gaussian_xauusd_2m_LATEST.json",
            "results/zonegate_xauusd_2m/zonegate_xauusd_2m_LATEST.json",
            "results/rr_xauusd_2m/rr_xauusd_2m_LATEST.json",
        ],
        "interpretation_guardrails": [
            "Not promoted; live gaussian_impl remains heuristic (F-060 path).",
            "Entry universe = CRT SWEEP (spine TRADE_OPENED starved on XAUUSD).",
            "Labels = forward_walk(intrabar_fixed)+12bps — governing research exit, "
            "not F-022 stream rr_achieved.",
            "No economic authority; descriptive train/eval only.",
            f"Feature dim = {CANONICAL_FEATURE_DIM} (live v4), not historical 38.",
            "Bar semantic journal is observational; LLM explainers must not invent "
            "causes beyond reason_code + payload.",
        ],
    }

    journal_summary = tracker.close()
    train_manifest["bar_semantic_journal"]["summary"] = journal_summary

    man_path = out_dir / f"train_eval_manifest_{run_ts}.json"
    latest = ROOT / "results" / "gaussian_xauusd_train" / "LATEST.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    for p in (man_path, latest):
        p.write_text(json.dumps(train_manifest, indent=2, default=str), encoding="utf-8")

    print("--- DONE ---")
    print(f"model:    {model_path}")
    print(f"dataset:  {ds_path}")
    print(f"manifest: {man_path}")
    print(f"scores:   {scores_csv}")
    print(f"journal:  {journal_path}")
    print(f"latest:   {latest}")
    print(
        json.dumps(
            {
                "n_train_units": len(units),
                "class_counts": dict(class_counts),
                "train_metrics": train_metrics,
                "eval_score_stats": _stats(scores),
                "eval_exceptions": exceptions,
                "model_path": str(model_path),
                "bar_semantic_events": journal_summary.get("n_events"),
                "bar_semantic_rate": journal_summary.get("rate_bars_per_s"),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
