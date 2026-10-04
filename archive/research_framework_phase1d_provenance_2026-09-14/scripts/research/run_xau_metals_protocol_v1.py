#!/usr/bin/env python3
"""
run_xau_metals_protocol_v1.py
============================
Execute frozen **xau_metals_protocol_v1** end-to-end (P0–P7).

Reads ONLY configs/research/xau_metals_protocol_v1.json for primary
cost / entry / control / M4 knobs. Do not retune after OOS.

  P0 record protocol_sha256
  P1 stream CRT RETEST enter-edge candidates (+ journal kinds)
  P2 score frozen XAUUSD Gaussian NB (no retrain)
  P3 label net R: primary fixed USD RT + sensitivity diagnostic
  P4 arms + XAU_CTRL_V1 acceptance_test
  P5 E1 tables + kill_criteria
  P6 M4 evaluate_pre_bh / finalize / BH (primary USD cost adapter)
  P7 manifests; economic_authority_granted=false always

Authority: RESEARCH_ONLY. Grants no live wire / no gaussian_impl flip.

Usage:
  python scripts/research/run_xau_metals_protocol_v1.py
  python scripts/research/run_xau_metals_protocol_v1.py --n-permutations 200
"""
from __future__ import annotations

import argparse
import dataclasses
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
AUTHORITY = (
    "RESEARCH_ONLY — xau_metals_protocol_v1 measurement; "
    "not production PromotionManager; not ΔG001; not gaussian_impl flip; "
    "economic_authority_granted=false unless separate human E3"
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True)
class FixedUsdCostAdapter:
    """Duck-types research.costs.CostModel for fixed USD round-trip.

    Primary under xau_metals_protocol_v1. EdgeReport.round_trip_bps is left 0
    (meaningless for USD mode); real cost is recorded in manifests.
    """

    usd_round_trip: float
    round_trip_bps: float = 0.0

    def cost_r(self, entry: float, risk_distance: float) -> float:
        if risk_distance <= 0:
            raise ValueError(
                f"FixedUsdCostAdapter.cost_r: non-positive risk_distance ({risk_distance})"
            )
        return float(self.usd_round_trip) / float(risk_distance)

    def net_rr(self, gross_rr: float, entry: float, risk_distance: float) -> float:
        return float(gross_rr) - self.cost_r(entry, risk_distance)


@dataclass
class Bar:
    index: int
    timestamp: Any
    open: float
    high: float
    low: float
    close: float
    volume: float


def _normalize_direction(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    d = str(getattr(raw, "name", raw)).lower()
    if "long" in d or d in ("buy", "bull", "1"):
        return "long"
    if "short" in d or d in ("sell", "bear", "-1"):
        return "short"
    return None


def _resolve_direction(engine: Any) -> Optional[str]:
    st = getattr(engine, "state", None)
    if st is None:
        return None
    for attr in ("direction", "sweep_direction", "trade_direction", "bias"):
        d = _normalize_direction(getattr(st, attr, None))
        if d in ("long", "short"):
            return d
    return None


def _atr_abs(feat: dict, bar: Bar, priority_note: list) -> float:
    atr = float(feat.get("atr", 0.0) or 0.0)
    close = float(bar.close)
    if 0 < atr < 1.0 and close > 1.0:
        atr_abs = atr * close
        priority_note.append("atr_relative_x_close")
    elif atr > 0:
        atr_abs = atr
        priority_note.append("atr_as_absolute")
    else:
        atr_abs = max(bar.high - bar.low, 1e-8)
        priority_note.append("bar_range_fallback")
    return float(atr_abs)


def stream_retest_candidates(
    df: pd.DataFrame,
    enriched: pd.DataFrame,
    feature_order: list[str],
    *,
    holdout_start: pd.Timestamp,
    sl_atr_mult: float,
    tp_atr_mult: float,
    max_forward: int,
    exit_model: str,
    journal_path: Path,
) -> tuple[list[dict], dict]:
    """P1+P3 geometry: RETEST enter-edge → forward_walk gross (no cost yet)."""
    from config_layer.config_builder import ConfigBuilder
    from config_layer.crt_engine_v2 import CRTEngine
    from config_layer.production_config import get_prod_section
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
    from research.contracts import Signal
    from research.measurement.forward_walk import forward_walk
    from runtime.backtest_v2 import CandleLoader, HTFBuilder

    crt_cfg = ConfigBuilder().build(instrument=INSTRUMENT)
    engine = CRTEngine(config=crt_cfg)
    corpus_path = guard_xauusd_csv_path("data/mt5/XAUUSD_M15.csv", INSTRUMENT)
    loader = CandleLoader(str(corpus_path), instrument=INSTRUMENT)
    htf_n = 4
    try:
        htf_n = int(get_prod_section("backtest").get("htf_candles_per_range", 4))
    except Exception:
        pass
    htf = HTFBuilder(candles_per_htf=htf_n, instrument=INSTRUMENT)

    enr = enriched.copy()
    enr["timestamp"] = pd.to_datetime(enr["timestamp"])
    ts_to_enr = {pd.Timestamp(t): i for i, t in enumerate(enr["timestamp"])}

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

    warmup_n = 30
    try:
        warmup_n = int(get_prod_section("backtest").get("warmup_candles", 30))
    except Exception:
        pass

    candidates: list[dict] = []
    skips: Counter = Counter()
    diagnostics: Counter = Counter()
    journal_f = journal_path.open("w", encoding="utf-8")

    def jemit(kind: str, **payload: Any) -> None:
        row = {
            "schema": "xau_metals_protocol_v1_journal",
            "kind": kind,
            **payload,
        }
        journal_f.write(json.dumps(row, default=str) + "\n")

    initialised = False
    n_streamed = 0
    prev_state: Optional[str] = None

    try:
        for candle in loader.stream():
            n_streamed += 1
            htf.push(candle)
            ts_raw = getattr(candle, "timestamp", None)
            if ts_raw is None and isinstance(candle, dict):
                ts_raw = candle.get("timestamp")
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
            except Exception:
                skips["crt_exception"] += 1
                continue

            st = getattr(getattr(engine, "state", None), "current_state", None)
            st_name = getattr(st, "name", str(st) if st is not None else "") or ""

            # Diagnostic SWEEP count only
            if st_name == "SWEEP" and prev_state != "SWEEP":
                diagnostics["SWEEP_enter_edge"] += 1

            is_retest = st_name == "RETEST" and prev_state != "RETEST"
            prev_state = st_name
            if not is_retest:
                continue

            direction = _resolve_direction(engine)
            # also peek process_candle events
            if direction not in ("long", "short") and isinstance(out, dict):
                for e in [out] + list(out.get("events") or []):
                    if not isinstance(e, dict):
                        continue
                    d = e.get("direction") or (e.get("metadata") or {}).get("direction")
                    nd = _normalize_direction(d)
                    if nd in ("long", "short"):
                        direction = nd
                        break

            ts = pd.Timestamp(ts_raw)
            split = "oos" if ts >= holdout_start else "train"
            jemit(
                "RETEST_CANDIDATE",
                timestamp=str(ts),
                bar_index=int(bar_idx_guess),
                direction=direction,
                crt_state=st_name,
                split=split,
            )

            if direction not in ("long", "short"):
                skips["no_direction"] += 1
                jemit(
                    "RETEST_SKIPPED",
                    reason="no_direction",
                    timestamp=str(ts),
                    bar_index=int(bar_idx_guess),
                    crt_state=st_name,
                    split=split,
                )
                continue

            # Resolve raw index
            idx = getattr(candle, "index", None)
            if idx is None or int(idx) <= 0:
                matches = np.where(raw_ts.values == np.datetime64(ts))[0]
                if len(matches) == 0:
                    matches = np.where(raw_ts.astype(str) == str(ts))[0]
                if len(matches) == 0:
                    skips["ts_not_in_raw"] += 1
                    jemit(
                        "RETEST_SKIPPED",
                        reason="ts_not_in_raw",
                        timestamp=str(ts),
                        direction=direction,
                        split=split,
                    )
                    continue
                idx = int(matches[0])
            else:
                idx = int(idx)

            if idx < 0 or idx >= len(bars) - 2:
                skips["idx_oob"] += 1
                jemit(
                    "RETEST_SKIPPED",
                    reason="idx_oob",
                    timestamp=str(ts),
                    direction=direction,
                    bar_index=idx,
                    split=split,
                )
                continue

            enr_i = ts_to_enr.get(ts)
            if enr_i is None:
                enr_i = ts_to_enr.get(pd.Timestamp(str(ts)))
            if enr_i is None:
                skips["no_features"] += 1
                jemit(
                    "RETEST_SKIPPED",
                    reason="no_features",
                    timestamp=str(ts),
                    direction=direction,
                    bar_index=idx,
                    split=split,
                )
                continue

            feat_row = enr.iloc[enr_i]
            try:
                feat = {k: float(feat_row[k]) for k in feature_order if k in feat_row.index}
            except Exception:
                skips["feature_cast"] += 1
                jemit(
                    "RETEST_SKIPPED",
                    reason="feature_cast",
                    timestamp=str(ts),
                    direction=direction,
                    split=split,
                )
                continue

            atr_note: list[str] = []
            atr_abs = _atr_abs(feat, bars[idx], atr_note)
            if atr_abs <= 0:
                skips["atr_nonpos"] += 1
                jemit(
                    "RETEST_SKIPPED",
                    reason="atr_nonpos",
                    timestamp=str(ts),
                    direction=direction,
                    split=split,
                )
                continue

            entry = float(bars[idx].close)
            sig = Signal(
                instrument=INSTRUMENT,
                timestamp=bars[idx].timestamp
                if isinstance(bars[idx].timestamp, datetime)
                else pd.Timestamp(bars[idx].timestamp).to_pydatetime(),
                entry_index=idx,
                direction=direction,
                entry=entry,
                sl_atr_mult=float(sl_atr_mult),
                tp_atr_mult=float(tp_atr_mult),
                atr=float(atr_abs),
                meta={"source": "crt_retest_enter", "state": st_name},
            )
            future = bars[idx + 1 :]
            try:
                outcome = forward_walk(
                    sig, future, max_forward=max_forward, exit_model=exit_model
                )
            except Exception as exc:
                skips["forward_walk_fail"] += 1
                jemit(
                    "RETEST_SKIPPED",
                    reason="forward_walk_fail",
                    timestamp=str(ts),
                    direction=direction,
                    error=type(exc).__name__,
                    split=split,
                )
                continue

            gross = float(getattr(outcome, "rr_achieved", 0.0) or 0.0)
            exit_reason = str(
                getattr(outcome, "outcome", None)
                or getattr(outcome, "exit_reason", "")
                or ""
            )
            duration = int(getattr(outcome, "duration_candles", 0) or 0)
            mfe = float(getattr(outcome, "mfe", 0.0) or 0.0)
            mae = float(getattr(outcome, "mae", 0.0) or 0.0)

            if split == "oos":
                jemit(
                    "HOLDOUT",
                    timestamp=str(ts),
                    direction=direction,
                    bar_index=idx,
                    holdout_start=str(holdout_start),
                )

            unit = {
                "timestamp": str(ts),
                "bar_index": idx,
                "feature_row_index": int(enr_i),
                "direction": direction,
                "split": split,
                "crt_state": st_name,
                "entry": entry,
                "atr_abs": atr_abs,
                "atr_source": atr_note[-1] if atr_note else None,
                "sl_atr_mult": float(sl_atr_mult),
                "tp_atr_mult": float(tp_atr_mult),
                "gross_rr": gross,
                "exit_reason": exit_reason,
                "duration_candles": duration,
                "mfe": mfe,
                "mae": mae,
                "entry_ontology": "XAU_ENTRY_V2_RETEST_EDGE",
                "exit_geometry": "XAU_EXIT_V1_FIXED_1R",
                "feature_vec": [float(feat.get(k, float("nan"))) for k in feature_order],
            }
            candidates.append(unit)
            jemit(
                "RETEST_ACCEPTED",
                timestamp=str(ts),
                direction=direction,
                bar_index=idx,
                split=split,
                gross_rr=gross,
                exit_reason=exit_reason,
                entry=entry,
                atr_abs=atr_abs,
            )
    finally:
        journal_f.close()

    meta = {
        "n_streamed": n_streamed,
        "n_candidates": len(candidates),
        "n_train": sum(1 for c in candidates if c["split"] == "train"),
        "n_oos": sum(1 for c in candidates if c["split"] == "oos"),
        "skips": dict(skips),
        "diagnostics": dict(diagnostics),
        "holdout_start": str(holdout_start),
        "warmup_n": warmup_n,
    }
    return candidates, meta


def score_candidates(
    candidates: list[dict],
    model_rel: str,
    feature_order: list[str],
    dim_required: int,
) -> tuple[list[dict], dict]:
    """P2: name-anchored Gaussian score on frozen model."""
    from features.gaussian_schema_contract import extract_model_feature_vector
    from training.trainer import load_gaussian_model

    model, scaler, meta = load_gaussian_model(model_rel)
    resolved = list(meta.get("feature_schema_resolved") or feature_order)
    n_features = int(model.n_features)
    if n_features != dim_required:
        raise RuntimeError(
            f"model n_features={n_features} != protocol feature_dim_required={dim_required}"
        )

    scored: list[dict] = []
    fails: Counter = Counter()
    for u in candidates:
        feat = {
            k: float(v)
            for k, v in zip(feature_order, u.get("feature_vec") or [])
            if v is not None and not (isinstance(v, float) and math.isnan(v))
        }
        # rebuild full name map when vec incomplete
        if len(feat) < len(feature_order):
            fails["incomplete_feat"] += 1
            # still try with what we have via extract
            pass
        try:
            # Prefer full feature_vec length match
            if len(u.get("feature_vec") or []) == len(feature_order):
                feat = {
                    k: float(u["feature_vec"][i]) for i, k in enumerate(feature_order)
                }
            vec = extract_model_feature_vector(feat, resolved)
            scaled = scaler.transform_one(vec)
            expected_rr, confidence, _probs = model.predict_expected_rr(scaled)
            sc = 1.0 / (1.0 + math.exp(-float(expected_rr)))
            sc = max(0.0, min(1.0, sc))
        except Exception as e:
            fails[f"score:{type(e).__name__}"] += 1
            continue
        out = {
            **{k: v for k, v in u.items() if k != "feature_vec"},
            "score": round(float(sc), 6),
            "expected_rr": round(float(expected_rr), 6),
            "confidence": round(float(confidence), 6),
            "model_n_features": n_features,
            "schema_alignment": meta.get("schema_alignment"),
        }
        scored.append(out)
    runtime = {
        "n_scored": len(scored),
        "n_train": sum(1 for u in scored if u["split"] == "train"),
        "n_oos": sum(1 for u in scored if u["split"] == "oos"),
        "fail_counts": dict(fails),
        "model_n_features": n_features,
        "schema_alignment": meta.get("schema_alignment"),
    }
    return scored, runtime


def apply_costs(units: list[dict], protocol: dict) -> list[dict]:
    """P3: primary USD + sensitivity grid + legacy 12bps diagnostic."""
    from research.xau_metals_protocol import (
        cost_r_fixed_usd,
        cost_r_flat_bps,
        primary_usd,
        sensitivity_usd_grid,
    )

    usd_primary = primary_usd(protocol)
    grid = sensitivity_usd_grid(protocol)
    bps = float(protocol["cost_model"]["legacy_diagnostic"]["round_trip_bps"])
    sl = float(protocol["exit_geometry"]["sl_atr_mult"])

    out = []
    for u in units:
        entry = float(u["entry"])
        atr = float(u["atr_abs"])
        gross = float(u["gross_rr"])
        c_primary = cost_r_fixed_usd(
            entry, atr, sl_atr_mult=sl, usd_round_trip=usd_primary
        )
        row = {
            **u,
            "cost_r_primary": c_primary,
            "net_rr_primary": gross - c_primary,
            "usd_primary": usd_primary,
            "cost_r_legacy_12bps": cost_r_flat_bps(
                entry, atr, sl_atr_mult=sl, round_trip_bps=bps
            ),
            "net_rr_legacy_12bps": gross
            - cost_r_flat_bps(entry, atr, sl_atr_mult=sl, round_trip_bps=bps),
        }
        for usd in grid:
            key = f"usd_{str(usd).replace('.', 'p')}"
            c = cost_r_fixed_usd(entry, atr, sl_atr_mult=sl, usd_round_trip=usd)
            row[f"cost_r_{key}"] = c
            row[f"net_rr_{key}"] = gross - c
        out.append(row)
    return out


def assign_arms(units: list[dict], protocol: dict) -> tuple[dict[str, list[int]], dict]:
    """P4: train-only quantiles + arms + control acceptance."""
    from research.xau_metals_protocol import (
        assert_control_acceptance,
        assign_random_match_control,
        train_quantiles,
    )

    qcfg = protocol["scoring_arms"]["quantiles"]
    train_scores = [
        float(u["score"]) for u in units if u.get("split") == "train"
    ]
    q = train_quantiles(
        train_scores,
        low_pct=float(qcfg["low_pct"]),
        high_pct=float(qcfg["high_pct"]),
    )
    p_low, p_high = q["p_low"], q["p_high"]
    n = len(units)
    all_idx = list(range(n))
    top = [i for i, u in enumerate(units) if float(u["score"]) >= p_high]
    bot = [i for i, u in enumerate(units) if float(u["score"]) <= p_low]
    long_only = [i for i, u in enumerate(units) if u.get("direction") == "long"]
    short_only = [i for i, u in enumerate(units) if u.get("direction") == "short"]

    splits = [str(u["split"]) for u in units]
    in_top = [float(u["score"]) >= p_high for u in units]
    in_random = assign_random_match_control(
        n_units=n, splits=splits, in_top=in_top, protocol=protocol
    )
    assert_control_acceptance(in_top=in_top, in_random=in_random, splits=splits)
    random_idx = [i for i, m in enumerate(in_random) if m]

    arms = {
        "all_units": all_idx,
        "nb_top_decile": top,
        "nb_bottom_decile": bot,
        "random_match_n": random_idx,
        "long_only": long_only,
        "short_only": short_only,
    }
    meta = {
        "quantiles": q,
        "control_acceptance": {
            "passed": True,
            "n_top": len(top),
            "n_random": len(random_idx),
            "n_top_train": sum(1 for i in top if units[i]["split"] == "train"),
            "n_top_oos": sum(1 for i in top if units[i]["split"] == "oos"),
            "n_random_train": sum(
                1 for i in random_idx if units[i]["split"] == "train"
            ),
            "n_random_oos": sum(1 for i in random_idx if units[i]["split"] == "oos"),
        },
    }
    return arms, meta


def arm_metrics(net_rrs: list[float]) -> dict:
    if not net_rrs:
        return {
            "n": 0,
            "mean_net_rr": None,
            "pf": None,
            "win_rate": None,
            "sum_net_rr": 0.0,
        }
    a = np.asarray(net_rrs, dtype=float)
    pos = a[a > 0]
    neg = a[a < 0]
    gw = float(pos.sum()) if pos.size else 0.0
    gl = float(-neg.sum()) if neg.size else 0.0
    pf = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else None)
    return {
        "n": int(a.size),
        "mean_net_rr": float(a.mean()),
        "std_net_rr": float(a.std()),
        "sum_net_rr": float(a.sum()),
        "pf": pf if pf is None or math.isfinite(pf) else None,
        "win_rate": float((a > 0).mean()),
        "n_pos": int((a > 0).sum()),
        "n_neg": int((a < 0).sum()),
    }


def evaluate_e1(units: list[dict], arms: dict[str, list[int]], protocol: dict) -> dict:
    """P5: E1 tables + kill criteria (primary net only)."""
    report = {}
    for arm, idxs in arms.items():
        overall = [float(units[i]["net_rr_primary"]) for i in idxs]
        is_rr = [
            float(units[i]["net_rr_primary"])
            for i in idxs
            if units[i].get("split") == "train"
        ]
        oos_rr = [
            float(units[i]["net_rr_primary"])
            for i in idxs
            if units[i].get("split") == "oos"
        ]
        report[arm] = {
            "n_members": len(idxs),
            "overall": arm_metrics(overall),
            "is": arm_metrics(is_rr),
            "oos": arm_metrics(oos_rr),
        }

    # kill criteria from protocol
    top = (report.get("nb_top_decile") or {}).get("oos") or {}
    allu = (report.get("all_units") or {}).get("oos") or {}
    rand = (report.get("random_match_n") or {}).get("oos") or {}
    e_top = top.get("mean_net_rr")
    e_all = allu.get("mean_net_rr")
    e_rand = rand.get("mean_net_rr")

    kills = []
    if e_top is None or e_all is None or e_rand is None:
        relative = {
            "verdict": "INSUFFICIENT",
            "reason": "missing OOS mean for top/all/random",
        }
    else:
        beats_all = e_top > e_all
        beats_rand = e_top > e_rand
        if (not beats_all) and (not beats_rand):
            relative = {
                "verdict": "NO_RELATIVE_SKILL",
                "reason": protocol["kill_criteria"]["E1_relative"],
                "beats_all_units_oos": False,
                "beats_random_oos": False,
            }
            kills.append("NO_RELATIVE_SKILL")
        else:
            relative = {
                "verdict": "RELATIVE_SIGNAL_RESEARCH_ONLY",
                "reason": "OOS top beats at least one of all/random",
                "beats_all_units_oos": beats_all,
                "beats_random_oos": beats_rand,
            }

    if e_top is not None and e_top < 0:
        absolute = {
            "verdict": "NO_ABSOLUTE_EDGE",
            "reason": protocol["kill_criteria"]["E1_absolute"],
            "e_top_oos": e_top,
        }
        kills.append("NO_ABSOLUTE_EDGE")
    elif e_top is None:
        absolute = {"verdict": "INSUFFICIENT", "e_top_oos": None}
    else:
        absolute = {
            "verdict": "ABSOLUTE_E_NONNEG_RESEARCH_ONLY",
            "e_top_oos": e_top,
        }

    return {
        "arms": report,
        "kill": {
            "E1_relative": relative,
            "E1_absolute": absolute,
            "kills_fired": kills,
            "e_top_oos": e_top,
            "e_all_oos": e_all,
            "e_random_oos": e_rand,
        },
        "sensitivity_oos_top_decile": _sensitivity_top(
            units, arms.get("nb_top_decile") or [], protocol
        ),
    }


def _sensitivity_top(
    units: list[dict], top_idxs: list[int], protocol: dict
) -> dict:
    from research.xau_metals_protocol import sensitivity_usd_grid

    grid = sensitivity_usd_grid(protocol)
    out = {}
    oos_top = [i for i in top_idxs if units[i].get("split") == "oos"]
    for usd in grid:
        key = f"usd_{str(usd).replace('.', 'p')}"
        rrs = [float(units[i][f"net_rr_{key}"]) for i in oos_top]
        out[key] = arm_metrics(rrs)
    # legacy
    rrs_leg = [float(units[i]["net_rr_legacy_12bps"]) for i in oos_top]
    out["legacy_12bps"] = arm_metrics(rrs_leg)
    return out


def build_outcomes(
    units: list[dict], idxs: list[int]
) -> list:
    """Gross Outcome list for M4; cost applied via FixedUsdCostAdapter."""
    from research.contracts import Outcome, Signal

    outs = []
    for i in idxs:
        u = units[i]
        ts = u["timestamp"]
        try:
            ts_dt = datetime.fromisoformat(str(ts).replace(" ", "T"))
        except Exception:
            ts_dt = datetime(1970, 1, 1)
        sig = Signal(
            instrument=INSTRUMENT,
            timestamp=ts_dt,
            entry_index=int(u.get("bar_index") or 0),
            direction=str(u["direction"]),
            entry=float(u["entry"]),
            sl_atr_mult=float(u.get("sl_atr_mult") or 1.0),
            tp_atr_mult=float(u.get("tp_atr_mult") or 1.0),
            atr=float(u["atr_abs"]),
            meta={"score": u.get("score"), "split": u.get("split")},
        )
        gross = float(u["gross_rr"])
        outs.append(
            Outcome(
                signal=sig,
                outcome=str(u.get("exit_reason") or "UNKNOWN"),
                rr_achieved=gross,
                mfe=float(u.get("mfe") or max(gross, 0.0) * float(u["atr_abs"])),
                mae=float(u.get("mae") or min(gross, 0.0) * float(u["atr_abs"])),
                duration_candles=int(u.get("duration_candles") or 0),
                time_to_tp=None,
                time_to_failure=None,
                reached_1r=bool(gross >= 1.0),
            )
        )
    outs.sort(key=lambda o: (o.signal.timestamp, o.signal.direction))
    return outs


def run_m4(
    units: list[dict],
    arms: dict[str, list[int]],
    protocol: dict,
    *,
    n_permutations: Optional[int] = None,
) -> dict:
    """P6: M4 with primary fixed USD cost adapter."""
    from research.measurement.metrics import EdgeAggregator
    from research.qualification import (
        BH_METHOD_VERSION,
        PERMUTATION_METHOD_VERSION,
        QUALIFICATION_VERSION,
        QualConfig,
        benjamini_hochberg,
        evaluate_pre_bh,
        finalize,
        _net_rrs,
    )

    m4 = protocol["m4"]
    base_qcfg = QualConfig(
        min_samples=int(m4["min_samples"]),
        expectancy_min=float(m4["expectancy_min"]),
        pf_min=float(m4["pf_min"]),
        oos_split=0.3,  # overridden per arm
        oos_retention_min=float(m4["oos_retention_min"]),
        n_permutations=int(
            n_permutations if n_permutations is not None else m4["n_permutations"]
        ),
        significance_alpha=float(m4["significance_alpha"]),
    )
    usd = float(protocol["cost_model"]["primary"]["usd_round_trip"])
    cost = FixedUsdCostAdapter(usd_round_trip=usd)
    agg = EdgeAggregator()

    control_name = m4["control"]
    hyp_names = list(m4["hypotheses"])

    ctrl_idxs = arms[control_name]
    ctrl_outs = build_outcomes(units, ctrl_idxs)
    n_ctrl_oos = sum(1 for i in ctrl_idxs if units[i]["split"] == "oos")
    n_ctrl = len(ctrl_outs)
    oos_frac_ctrl = (n_ctrl_oos / n_ctrl) if n_ctrl else 0.3
    oos_frac_ctrl = min(max(oos_frac_ctrl, 1e-6), 1.0 - 1e-6)
    ctrl_report = agg.aggregate(control_name, [INSTRUMENT], ctrl_outs, cost_model=cost)
    ctrl_rrs = _net_rrs(ctrl_outs, cost)
    ctrl_exp = ctrl_report.expectancy_rr

    pre_states = {}
    for hyp in hyp_names:
        idxs = arms.get(hyp) or []
        outs = build_outcomes(units, idxs)
        if not outs:
            continue
        n_oos = sum(1 for i in idxs if units[i]["split"] == "oos")
        oos_frac = n_oos / len(outs) if outs else 0.3
        oos_frac = min(max(oos_frac, 1e-6), 1.0 - 1e-6)
        qcfg = dataclasses.replace(base_qcfg, oos_split=oos_frac)
        report = agg.aggregate(hyp, [INSTRUMENT], outs, cost_model=cost)
        per_inst = {INSTRUMENT: outs}
        state = evaluate_pre_bh(
            report,
            per_inst,
            control_name,
            ctrl_rrs,
            ctrl_exp,
            qcfg,
            cost,
        )
        pre_states[hyp] = (state, qcfg, oos_frac, n_oos, report)

    pvalues = {
        name: st.p_value
        for name, (st, *_rest) in pre_states.items()
        if not st.insufficient
    }
    survivors = benjamini_hochberg(pvalues, base_qcfg.significance_alpha)

    results = {}
    for name, (st, qcfg, oos_frac, n_oos, report) in pre_states.items():
        final = finalize(st, survivors, qcfg)
        pf = final.profit_factor
        results[name] = {
            "verdict": final.verdict,
            "reject_reasons": list(final.reject_reasons),
            "n": final.n,
            "expectancy_rr": final.expectancy_rr,
            "profit_factor": None if pf == float("inf") else pf,
            "win_rate": final.win_rate,
            "oos_split_used": oos_frac,
            "n_oos_members": n_oos,
            "passed_gates_1_to_6": st.passed_1_to_6,
            "p_value": st.p_value,
            "bh_survivor": name in survivors,
            "is_expectancy": st.is_report.expectancy_rr,
            "oos_expectancy": st.oos_report.expectancy_rr,
        }

    verdicts = Counter(r["verdict"] for r in results.values())
    primary = protocol["scoring_arms"]["primary_hypothesis_for_M4"]
    primary_verdict = (results.get(primary) or {}).get("verdict")
    any_promote = any(r["verdict"] == "PROMOTE" for r in results.values())

    return {
        "qualification_versions": {
            "QUALIFICATION_VERSION": QUALIFICATION_VERSION,
            "PERMUTATION_METHOD_VERSION": PERMUTATION_METHOD_VERSION,
            "BH_METHOD_VERSION": BH_METHOD_VERSION,
        },
        "qual_config": {
            "min_samples": base_qcfg.min_samples,
            "expectancy_min": base_qcfg.expectancy_min,
            "pf_min": base_qcfg.pf_min,
            "oos_retention_min": base_qcfg.oos_retention_min,
            "n_permutations": base_qcfg.n_permutations,
            "significance_alpha": base_qcfg.significance_alpha,
            "primary_cost": {
                "mode": "fixed_usd_round_trip",
                "usd_round_trip": usd,
            },
        },
        "control": {
            "arm": control_name,
            "n": ctrl_report.n,
            "expectancy_rr": ctrl_report.expectancy_rr,
            "profit_factor": (
                None
                if ctrl_report.profit_factor == float("inf")
                else ctrl_report.profit_factor
            ),
            "win_rate": ctrl_report.win_rate,
            "n_oos": n_ctrl_oos,
            "oos_frac": oos_frac_ctrl,
        },
        "hypotheses": hyp_names,
        "primary_hypothesis": primary,
        "primary_verdict": primary_verdict,
        "results": results,
        "cohort": {
            "verdict_counts": dict(verdicts),
            "any_promote": any_promote,
            "bh_survivors": sorted(survivors),
            "economic_authority_granted": False,
            "e3_allowed": primary_verdict == "PROMOTE",
            "note": (
                "Even PROMOTE is research M4 only — production authority "
                "requires separate human E3 + live-path ΔG001."
            ),
        },
    }


def tag_units_with_arms(units: list[dict], arms: dict[str, list[int]]) -> list[dict]:
    inv: dict[int, list[str]] = {i: [] for i in range(len(units))}
    for arm, idxs in arms.items():
        for i in idxs:
            inv[i].append(arm)
    out = []
    for i, u in enumerate(units):
        row = {**u, "arms": sorted(inv[i])}
        out.append(row)
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Execute xau_metals_protocol_v1")
    ap.add_argument(
        "--protocol",
        default=str(ROOT / "configs/research/xau_metals_protocol_v1.json"),
        help="Path to protocol JSON (must be protocol_id=xau_metals_protocol_v1)",
    )
    ap.add_argument(
        "--n-permutations",
        type=int,
        default=0,
        help="Override M4 n_permutations (0 = use protocol value, default 2000)",
    )
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke: 50 permutations only (not a formal result)",
    )
    args = ap.parse_args(argv)

    from research.xau_metals_protocol import load_protocol, protocol_sha256
    from data_ingestion.xauusd_phase1_candidate import (
        PHASE1_SHA256,
        PHASE1_STATUS,
        guard_xauusd_csv_path,
    )
    from features.feature_pipeline import FeaturePipeline
    from features.feature_schema import (
        CANONICAL_FEATURE_DIM,
        CANONICAL_FEATURE_ORDER,
    )

    proto_path = Path(args.protocol)
    if not proto_path.is_absolute():
        proto_path = ROOT / proto_path
    protocol = load_protocol(str(proto_path))
    if protocol["protocol_id"] != "xau_metals_protocol_v1":
        print(
            f"ERROR: refusing non-v1 protocol_id={protocol['protocol_id']!r}",
            file=sys.stderr,
        )
        return 2
    psha = protocol_sha256(str(proto_path))
    run_ts = _utc()

    out_dir = ROOT / protocol["outputs"]["dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "protocol_sha256.txt").write_text(psha + "\n", encoding="utf-8")

    print(f"[P0] protocol_id={protocol['protocol_id']}")
    print(f"[P0] protocol_sha256={psha}")
    print(f"[P0] authority={AUTHORITY}")
    print(f"[P0] out_dir={out_dir}")

    # ── corpus ──────────────────────────────────────────────────────────
    corpus_rel = protocol["corpus"]["path"]
    corpus = Path(guard_xauusd_csv_path(str(ROOT / corpus_rel), INSTRUMENT))
    corpus_sha = _sha256_file(corpus)
    pin = protocol["corpus"]["phase1_pin_sha256"]
    if corpus_sha != pin:
        print(
            f"ERROR: corpus sha {corpus_sha} != phase1 pin {pin}",
            file=sys.stderr,
        )
        return 3
    df = pd.read_csv(corpus)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    end = df["timestamp"].max()
    months = int(protocol["corpus"]["holdout"]["months"])
    holdout_start = end - pd.DateOffset(months=months)
    print(
        f"[P0] corpus n={len(df)} sha={corpus_sha[:16]}... "
        f"status={PHASE1_STATUS} holdout_start={holdout_start}"
    )

    # ── features ────────────────────────────────────────────────────────
    print("[P1] FeaturePipeline...")
    pipe = FeaturePipeline(df)
    enriched, vectors = pipe.run()
    feature_order = list(CANONICAL_FEATURE_ORDER)
    if CANONICAL_FEATURE_DIM != int(protocol["model"]["feature_dim_required"]):
        print(
            f"ERROR: dim {CANONICAL_FEATURE_DIM} != required "
            f"{protocol['model']['feature_dim_required']}",
            file=sys.stderr,
        )
        return 4
    print(f"[P1] enriched={len(enriched)} vectors={vectors.shape}")

    exit_g = protocol["exit_geometry"]
    journal_path = out_dir / f"journal_{run_ts}.jsonl"
    print("[P1] streaming CRT RETEST enter edges + forward_walk...")
    candidates, cand_meta = stream_retest_candidates(
        df,
        enriched,
        feature_order,
        holdout_start=holdout_start,
        sl_atr_mult=float(exit_g["sl_atr_mult"]),
        tp_atr_mult=float(exit_g["tp_atr_mult"]),
        max_forward=int(exit_g["max_forward"]),
        exit_model=str(exit_g["exit_model"]),
        journal_path=journal_path,
    )
    print(
        f"[P1] candidates={cand_meta['n_candidates']} "
        f"train={cand_meta['n_train']} oos={cand_meta['n_oos']} "
        f"skips={cand_meta['skips']} diag={cand_meta['diagnostics']}"
    )
    if cand_meta["n_candidates"] == 0:
        print("ERROR: zero RETEST candidates", file=sys.stderr)
        return 5

    # candidates.jsonl (without feature_vec for size — full unit later)
    cand_out = out_dir / "candidates.jsonl"
    with cand_out.open("w", encoding="utf-8") as f:
        for c in candidates:
            slim = {k: v for k, v in c.items() if k != "feature_vec"}
            f.write(json.dumps(slim, default=str) + "\n")

    # ── P2 score ────────────────────────────────────────────────────────
    model_path = protocol["model"]["path"]
    model_rel = model_path
    if model_rel.startswith("models/"):
        model_rel = model_rel[len("models/") :]
    model_abs = ROOT / "models" / model_rel
    if not model_abs.exists():
        print(f"ERROR: model missing: {model_abs}", file=sys.stderr)
        return 6
    if protocol["model"].get("retrain_under_this_protocol"):
        print("ERROR: protocol forbids retrain; refusing", file=sys.stderr)
        return 6

    print(f"[P2] scoring frozen model {protocol['model']['version']}...")
    scored, score_meta = score_candidates(
        candidates,
        model_rel,
        feature_order,
        int(protocol["model"]["feature_dim_required"]),
    )
    print(
        f"[P2] scored={score_meta['n_scored']} "
        f"train={score_meta['n_train']} oos={score_meta['n_oos']} "
        f"fails={score_meta['fail_counts']}"
    )
    if score_meta["n_scored"] == 0:
        print("ERROR: zero scored units", file=sys.stderr)
        return 7
    scored.sort(key=lambda u: (u["timestamp"], u["direction"]))

    # ── P3 costs ────────────────────────────────────────────────────────
    print("[P3] applying primary fixed USD cost + sensitivity...")
    units = apply_costs(scored, protocol)

    # ── P4 arms ─────────────────────────────────────────────────────────
    print("[P4] arms + control acceptance...")
    arms, arm_meta = assign_arms(units, protocol)
    print(f"[P4] control_acceptance={arm_meta['control_acceptance']}")
    units = tag_units_with_arms(units, arms)

    units_path = out_dir / "units_scored.jsonl"
    with units_path.open("w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(u, default=str) + "\n")

    ledger_path = out_dir / "ledger.jsonl"
    with ledger_path.open("w", encoding="utf-8") as f:
        for u in units:
            f.write(
                json.dumps(
                    {
                        "timestamp": u["timestamp"],
                        "direction": u["direction"],
                        "split": u["split"],
                        "score": u["score"],
                        "bar_index": u["bar_index"],
                        "entry": u["entry"],
                        "atr_abs": u["atr_abs"],
                        "gross_rr": u["gross_rr"],
                        "exit_reason": u["exit_reason"],
                        "cost_r_primary": u["cost_r_primary"],
                        "net_rr_primary": u["net_rr_primary"],
                        "net_rr_legacy_12bps": u["net_rr_legacy_12bps"],
                        "arms": u["arms"],
                    },
                    default=str,
                )
                + "\n"
            )

    # ── P5 E1 ───────────────────────────────────────────────────────────
    print("[P5] E1 tables + kill criteria...")
    e1 = evaluate_e1(units, arms, protocol)
    for arm, rep in e1["arms"].items():
        o = rep["oos"]
        print(
            f"  {arm:18s} n={rep['n_members']:5d} "
            f"OOS n={o.get('n')} E={o.get('mean_net_rr')} "
            f"PF={o.get('pf')} WR={o.get('win_rate')}"
        )
    print(f"[P5] kill={e1['kill']}")

    e1_manifest = {
        "phase": "E1",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": psha,
        "run_id": f"xau_metals_v1_e1_{run_ts}",
        "timestamp_utc": run_ts,
        "authority": AUTHORITY,
        "entry_ontology": protocol["entry_ontology"]["id"],
        "cost_primary": protocol["cost_model"]["primary"],
        "candidate_meta": cand_meta,
        "score_meta": score_meta,
        "arm_meta": arm_meta,
        "arms": e1["arms"],
        "kill": e1["kill"],
        "sensitivity_oos_top_decile": e1["sensitivity_oos_top_decile"],
        "economic_authority_granted": False,
    }
    e1_path = out_dir / "e1_manifest.json"
    e1_path.write_text(json.dumps(e1_manifest, indent=2, default=str), encoding="utf-8")
    (out_dir / f"e1_manifest_{run_ts}.json").write_text(
        e1_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    # ── P6 M4 ───────────────────────────────────────────────────────────
    n_perm = None
    if args.smoke:
        n_perm = 50
        print("[P6] SMOKE mode n_permutations=50")
    elif args.n_permutations > 0:
        n_perm = int(args.n_permutations)
    print(f"[P6] M4 qualification n_perm={n_perm or protocol['m4']['n_permutations']}...")
    m4 = run_m4(units, arms, protocol, n_permutations=n_perm)
    for name, r in m4["results"].items():
        print(
            f"  {name:18s} {r['verdict']:14s} E={r.get('expectancy_rr')} "
            f"PF={r.get('profit_factor')} reasons={r.get('reject_reasons')[:1]}"
        )
    print(
        f"[P6] primary={m4['primary_hypothesis']} "
        f"verdict={m4['primary_verdict']} any_PROMOTE={m4['cohort']['any_promote']}"
    )

    # ── P7 manifests ────────────────────────────────────────────────────
    e2_manifest = {
        "phase": "E2_M4",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": psha,
        "run_id": f"xau_metals_v1_m4_{run_ts}",
        "timestamp_utc": run_ts,
        "authority": AUTHORITY,
        "smoke": bool(args.smoke),
        **m4,
        "inputs": {
            "units_scored": str(units_path).replace("\\", "/"),
            "units_sha256": _sha256_file(units_path),
            "ledger": str(ledger_path).replace("\\", "/"),
            "ledger_sha256": _sha256_file(ledger_path),
            "candidates": str(cand_out).replace("\\", "/"),
            "journal": str(journal_path).replace("\\", "/"),
            "model": protocol["model"]["path"],
            "model_version": protocol["model"]["version"],
            "corpus_sha256": corpus_sha,
            "phase1_pin": PHASE1_SHA256,
        },
        "e1_kill_context": e1["kill"],
        "economic_authority_granted": False,
    }
    e2_path = out_dir / "e2_m4_manifest.json"
    e2_path.write_text(json.dumps(e2_manifest, indent=2, default=str), encoding="utf-8")
    (out_dir / f"e2_m4_manifest_{run_ts}.json").write_text(
        e2_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    # Master execution record
    exec_record = {
        "status": "EXECUTED",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": psha,
        "run_ts": run_ts,
        "authority": AUTHORITY,
        "economic_authority_granted": False,
        "e3_allowed": m4["cohort"].get("e3_allowed", False),
        "primary_verdict": m4["primary_verdict"],
        "any_promote": m4["cohort"]["any_promote"],
        "n_candidates": cand_meta["n_candidates"],
        "n_scored": score_meta["n_scored"],
        "n_train": score_meta["n_train"],
        "n_oos": score_meta["n_oos"],
        "control_acceptance": arm_meta["control_acceptance"],
        "e1_kills": e1["kill"]["kills_fired"],
        "m4_verdict_counts": m4["cohort"]["verdict_counts"],
        "outputs": {
            "candidates": str(cand_out).replace("\\", "/"),
            "units_scored": str(units_path).replace("\\", "/"),
            "ledger": str(ledger_path).replace("\\", "/"),
            "e1_manifest": str(e1_path).replace("\\", "/"),
            "e2_m4_manifest": str(e2_path).replace("\\", "/"),
            "protocol_sha256": str(out_dir / "protocol_sha256.txt").replace("\\", "/"),
            "journal": str(journal_path).replace("\\", "/"),
        },
        "smoke": bool(args.smoke),
    }
    exec_path = out_dir / "EXECUTION_RECORD.json"
    exec_path.write_text(json.dumps(exec_record, indent=2, default=str), encoding="utf-8")

    # Replace PRE_REGISTERED marker
    marker = out_dir / "PRE_REGISTERED_NOT_EXECUTED.txt"
    if marker.exists():
        marker.unlink()
    (out_dir / "EXECUTED.txt").write_text(
        f"EXECUTED {run_ts}\nprotocol_sha256={psha}\n"
        f"primary_verdict={m4['primary_verdict']}\n"
        f"economic_authority_granted=false\n",
        encoding="utf-8",
    )

    # Human summary
    md = out_dir / "PROTOCOL_V1_RESULT.md"
    kill = e1["kill"]
    lines = [
        f"# xau_metals_protocol_v1 — execution result",
        f"",
        f"**Run:** {run_ts}",
        f"**protocol_sha256:** `{psha}`",
        f"**Authority:** RESEARCH_ONLY · `economic_authority_granted=false`",
        f"",
        f"## Population",
        f"",
        f"- RETEST candidates scored: **{score_meta['n_scored']}** "
        f"(train {score_meta['n_train']} / oos {score_meta['n_oos']})",
        f"- Control acceptance: **PASS** "
        f"(top={arm_meta['control_acceptance']['n_top']} "
        f"random={arm_meta['control_acceptance']['n_random']})",
        f"- Diagnostic SWEEP enter edges (not primary): "
        f"{cand_meta.get('diagnostics', {}).get('SWEEP_enter_edge', 0)}",
        f"",
        f"## E1 (primary cost = fixed USD RT 0.40)",
        f"",
        f"| Arm | n | OOS n | OOS E[R] | OOS PF | OOS WR |",
        f"|---|---:|---:|---:|---:|---:|",
    ]
    for arm, rep in e1["arms"].items():
        o = rep["oos"]
        lines.append(
            f"| {arm} | {rep['n_members']} | {o.get('n')} | "
            f"{o.get('mean_net_rr')} | {o.get('pf')} | {o.get('win_rate')} |"
        )
    lines += [
        f"",
        f"**Kills fired:** {kill.get('kills_fired')}",
        f"- relative: {kill['E1_relative'].get('verdict')}",
        f"- absolute: {kill['E1_absolute'].get('verdict')}",
        f"",
        f"## M4",
        f"",
        f"| Hypothesis | Verdict | E[R] | PF | reject |",
        f"|---|---|---:|---:|---|",
    ]
    for name, r in m4["results"].items():
        reasons = r.get("reject_reasons") or []
        lines.append(
            f"| {name} | {r['verdict']} | {r.get('expectancy_rr')} | "
            f"{r.get('profit_factor')} | {reasons[:1]} |"
        )
    lines += [
        f"",
        f"**Primary (`nb_top_decile`):** `{m4['primary_verdict']}`",
        f"**any_PROMOTE:** {m4['cohort']['any_promote']}",
        f"**E3 allowed:** {m4['cohort'].get('e3_allowed')}",
        f"",
        f"## Read correctly",
        f"",
        f"1. Entry = CRT RETEST enter edge (not SWEEP).",
        f"2. Cost = fixed $0.40 RT (not 12 bps).",
        f"3. Control = per-split size-match; acceptance passed.",
        f"4. No economic authority; no live wire.",
        f"",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")

    print("--- PROTOCOL V1 DONE ---")
    print(f"primary_verdict={m4['primary_verdict']}")
    print(f"economic_authority_granted=false")
    print(f"record: {exec_path}")
    print(f"summary: {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
