"""GATE-0 dual feasibility probe: TradeNet (TN) + EnvelopeNet (ENV).

READ-ONLY. No training, no spine wire, no registry/config mutation.

Answers TN G0-Q1…Q9 and ENV-0 pilot questions on BNBUSDT opportunities + M15 candles
via forward_walk(intrabar_fixed) + horizon_excursion (clean path labels; F-022 stream is
diagnostic only).

Usage:
  python scripts/research/gate0_tn_env_feasibility.py
  python scripts/research/gate0_tn_env_feasibility.py --pilot-n 150 --max-scan 20000
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as stats
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from research.contracts import Signal  # noqa: E402
from research.measurement.forward_walk import forward_walk, horizon_excursion  # noqa: E402
from research.zone_label_audit import honest_outcome, MAX_FORWARD  # noqa: E402
from bnbusdt_trade_anatomy import load_candles  # noqa: E402

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
TP1_STREAM = frozenset({"TP1", "TP2", "TP1_HIT", "TP2_HIT", "TP_HIT"})
TP2_STREAM = frozenset({"TP2", "TP2_HIT"})


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    if len(xs) == 1:
        return round(float(xs[0]), 6)
    xs = sorted(xs)
    k = (len(xs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(float(xs[int(k)]), 6)
    return round(float(xs[f] * (c - k) + xs[c] * (k - f)), 6)


def _finite(x) -> bool:
    try:
        v = float(x)
        return math.isfinite(v)
    except (TypeError, ValueError):
        return False


def _load_units(path: Path, max_scan: int) -> list[dict]:
    units: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= max_scan:
                break
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            # skip header / non-opportunity lines
            if "entry" not in rec or "timestamp" not in rec:
                continue
            units.append(rec)
    return units


def _feature_complete(rec: dict) -> bool:
    feats = rec.get("features")
    if not isinstance(feats, dict):
        return False
    for name in CANONICAL_FEATURES:
        if name not in feats or not _finite(feats[name]):
            return False
    return True


def _geometry_ok(rec: dict) -> bool:
    if not all(k in rec for k in ("entry", "sl", "direction", "timestamp")):
        return False
    if not _finite(rec["entry"]) or not _finite(rec["sl"]):
        return False
    if abs(float(rec["entry"]) - float(rec["sl"])) <= 0:
        return False
    d = str(rec.get("direction", "")).lower()
    if d not in ("long", "short"):
        return False
    # single TP field is acceptable for two-head / pilot TP1
    tp = rec.get("tp", rec.get("tp1"))
    return _finite(tp)


def _has_tp2(rec: dict) -> bool:
    return _finite(rec.get("tp2"))


def _stream_y(rec: dict) -> dict:
    outcome = str(rec.get("outcome", "")).upper()
    risk = abs(float(rec["entry"]) - float(rec["sl"]))
    mfe = rec.get("mfe")
    survives = None
    if _finite(mfe) and risk > 0:
        survives = 1.0 if float(mfe) >= risk else 0.0
    return {
        "y_tp1": 1.0 if outcome in TP1_STREAM else 0.0,
        "y_tp2": 1.0 if outcome in TP2_STREAM else 0.0,
        "y_survives_be": survives,
        "outcome": outcome,
        "mfe": float(mfe) if _finite(mfe) else None,
        "mae": float(rec["mae"]) if _finite(rec.get("mae")) else None,
    }


def _bars_to_mfe(direction: str, entry: float, future, mfe_price: float) -> int | None:
    """1-based bar index when MFE is first attained (exit-agnostic over provided future)."""
    if mfe_price <= 0:
        return None
    for i, bar in enumerate(future):
        high, low = float(bar.high), float(bar.low)
        fav = (high - entry) if direction == "long" else (entry - low)
        if fav + 1e-12 >= mfe_price:
            return i + 1
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--opportunities",
        default="logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl",
    )
    ap.add_argument("--candles", default="data/BNBUSDT_M15.csv")
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--pilot-n", type=int, default=150, help="geometry-complete pilot size [50,200]")
    ap.add_argument("--max-scan", type=int, default=25000)
    ap.add_argument("--max-forward", type=int, default=MAX_FORWARD)
    ap.add_argument(
        "--out-dir",
        default=None,
        help="default results/tradenet/gate0_feasibility/<run_id> + results/envelope/gate0_feasibility/<run_id>",
    )
    args = ap.parse_args(argv)

    pilot_n = max(50, min(200, int(args.pilot_n)))
    opp_path = ROOT / args.opportunities
    candle_path = ROOT / args.candles
    if not opp_path.is_file():
        print(f"ERROR: opportunities not found: {opp_path}")
        return 2
    if not candle_path.is_file():
        print(f"ERROR: candles not found: {candle_path}")
        return 2

    print(f"[gate0] loading opportunities scan_cap={args.max_scan} from {opp_path}")
    raw = _load_units(opp_path, args.max_scan)
    n_raw = len(raw)

    # ── census ────────────────────────────────────────────────────────────
    n_geom = 0
    n_tp2 = 0
    n_feat = 0
    n_closed_stream = 0
    outcome_ctr: Counter = Counter()
    for rec in raw:
        if _geometry_ok(rec):
            n_geom += 1
            if _has_tp2(rec):
                n_tp2 += 1
        if _feature_complete(rec):
            n_feat += 1
        oc = str(rec.get("outcome", "")).upper()
        if oc and oc not in ("", "UNKNOWN", "NONE"):
            n_closed_stream += 1
            outcome_ctr[oc] += 1

    print(f"[gate0] n_raw={n_raw} n_geometry={n_geom} n_feat38={n_feat} n_stream_outcome={n_closed_stream}")

    print(f"[gate0] loading candles {candle_path}")
    candles, ts_to_idx, _ = load_candles(candle_path)
    n_candles = len(candles)

    # OHLCV coverage among geometry-complete
    n_ts_hit = 0
    n_future_ok = 0
    geom_units = [r for r in raw if _geometry_ok(r)]
    for rec in geom_units:
        ts = str(rec["timestamp"]).replace("T", " ").strip()
        idx = ts_to_idx.get(ts)
        if idx is None:
            continue
        n_ts_hit += 1
        if idx + 1 < n_candles and (n_candles - (idx + 1)) >= 1:
            # at least 1 future bar; full horizon preferred
            if (n_candles - (idx + 1)) >= args.max_forward:
                n_future_ok += 1
            else:
                n_future_ok += 1  # partial future still walkable; count separately below

    # refine future: full max_forward
    n_future_full = 0
    for rec in geom_units:
        ts = str(rec["timestamp"]).replace("T", " ").strip()
        idx = ts_to_idx.get(ts)
        if idx is None:
            continue
        if (n_candles - (idx + 1)) >= args.max_forward:
            n_future_full += 1

    # ── pilot walk ────────────────────────────────────────────────────────
    pilot: list[dict] = []
    skips = Counter()
    exceptions: list[str] = []

    for rec in geom_units:
        if len(pilot) >= pilot_n:
            break
        if not _feature_complete(rec):
            skips["no_features"] += 1
            # still allow walk for geometry feasibility; features tracked separately
        ts = str(rec["timestamp"]).replace("T", " ").strip()
        idx = ts_to_idx.get(ts)
        if idx is None:
            skips["no_candle_ts"] += 1
            continue
        try:
            oc = honest_outcome(rec, candles, ts_to_idx)
        except Exception as e:  # noqa: BLE001 — catalogue, don't crash pilot
            exceptions.append(f"honest_outcome: {type(e).__name__}: {e}")
            skips["walk_exception"] += 1
            continue
        if oc is None:
            skips["honest_none"] += 1
            continue

        direction = str(rec["direction"]).lower()
        entry = float(rec["entry"])
        sl = float(rec["sl"])
        risk = abs(entry - sl)
        future = candles[idx + 1 : idx + 1 + args.max_forward]
        try:
            # exit-agnostic envelope substrate
            sig_env = Signal(
                instrument=args.instrument,
                timestamp=candles[idx].timestamp,
                entry_index=idx,
                direction=direction,
                entry=entry,
                sl_atr_mult=1.0,
                tp_atr_mult=1.0,
                atr=risk,
            )
            hexc = horizon_excursion(sig_env, future, max_forward=args.max_forward)
        except Exception as e:  # noqa: BLE001
            exceptions.append(f"horizon_excursion: {type(e).__name__}: {e}")
            skips["hexc_exception"] += 1
            continue

        stream = _stream_y(rec)
        # TradeNet clean heads
        y_tp1 = 1.0 if oc.outcome == "TP_HIT" else 0.0
        # TP2: geometric MFE>=2R before/at exit path — use horizon reached_2r as pilot surrogate
        # when unit has no tp2 field (documented in report)
        y_tp2 = 1.0 if hexc.get("reached_2r") else 0.0
        y_survives = 1.0 if oc.reached_1r else 0.0

        mfe_r = (oc.mfe / risk) if risk > 0 else None
        mae_r_heat = (abs(oc.mae) / risk) if risk > 0 else None
        # exit-agnostic (envelope primary)
        env_mfe_r = hexc["mfe_r"]
        env_mae_r = abs(hexc["mae_r"]) if hexc["mae_r"] is not None else None
        ttm = _bars_to_mfe(direction, entry, future, oc.mfe if oc.mfe > 0 else env_mfe_r * risk)

        pilot.append(
            {
                "timestamp": ts,
                "direction": direction,
                "risk": risk,
                "feature_complete": _feature_complete(rec),
                "has_tp2_field": _has_tp2(rec),
                "stream": stream,
                "clean": {
                    "outcome": oc.outcome,
                    "y_tp1": y_tp1,
                    "y_tp2_surrogate_reached_2r": y_tp2,
                    "y_survives_be": y_survives,
                    "rr_achieved": oc.rr_achieved,
                    "mfe_r_path": mfe_r,
                    "mae_r_heat_path": mae_r_heat,
                    "holding_bars": oc.duration_candles,
                    "time_to_tp": oc.time_to_tp,
                    "time_to_failure": oc.time_to_failure,
                },
                "envelope": {
                    "mfe_r": env_mfe_r,
                    "mae_r_heat": env_mae_r,
                    "reached_1r": hexc["reached_1r"],
                    "reached_2r": hexc["reached_2r"],
                    "bars_to_first_1r": hexc["bars_to_first_1r"],
                    "time_to_mfe_est": ttm,
                    "holding_under_walk": oc.duration_candles,
                    "expired_timeout": 1.0 if oc.outcome == "TIMEOUT" else 0.0,
                },
            }
        )

    n_pilot = len(pilot)
    print(f"[gate0] pilot_ok={n_pilot} skips={dict(skips)} exceptions={len(exceptions)}")

    # ── agreement (TN) ────────────────────────────────────────────────────
    agree_tp1 = agree_surv = n_surv_both = 0
    stream_mfe_vs_path = []
    for p in pilot:
        if p["stream"]["y_tp1"] == p["clean"]["y_tp1"]:
            agree_tp1 += 1
        if p["stream"]["y_survives_be"] is not None:
            n_surv_both += 1
            if p["stream"]["y_survives_be"] == p["clean"]["y_survives_be"]:
                agree_surv += 1
        if p["stream"]["mfe"] is not None and p["clean"]["mfe_r_path"] is not None:
            stream_mfe_r = p["stream"]["mfe"] / p["risk"] if p["risk"] else None
            if stream_mfe_r is not None:
                stream_mfe_vs_path.append(abs(stream_mfe_r - p["clean"]["mfe_r_path"]))

    agree_tp1_rate = agree_tp1 / n_pilot if n_pilot else None
    agree_surv_rate = agree_surv / n_surv_both if n_surv_both else None

    # ── base rates & envelope quantiles ───────────────────────────────────
    y_tp1_rate = sum(p["clean"]["y_tp1"] for p in pilot) / n_pilot if n_pilot else None
    y_surv_rate = sum(p["clean"]["y_survives_be"] for p in pilot) / n_pilot if n_pilot else None
    y_tp2_rate = sum(p["clean"]["y_tp2_surrogate_reached_2r"] for p in pilot) / n_pilot if n_pilot else None
    timeout_rate = sum(p["envelope"]["expired_timeout"] for p in pilot) / n_pilot if n_pilot else None

    env_mfe = [p["envelope"]["mfe_r"] for p in pilot if p["envelope"]["mfe_r"] is not None]
    env_mae = [p["envelope"]["mae_r_heat"] for p in pilot if p["envelope"]["mae_r_heat"] is not None]
    hold = [float(p["clean"]["holding_bars"]) for p in pilot]
    ttm_vals = [float(p["envelope"]["time_to_mfe_est"]) for p in pilot if p["envelope"]["time_to_mfe_est"]]

    # correlation-ish: path survives_be vs env mfe_r (point-biserial via means)
    mfe_surv = [p["envelope"]["mfe_r"] for p in pilot if p["clean"]["y_survives_be"] == 1.0]
    mfe_die = [p["envelope"]["mfe_r"] for p in pilot if p["clean"]["y_survives_be"] == 0.0]

    feat_ok_pilot = sum(1 for p in pilot if p["feature_complete"])
    tp2_field_pilot = sum(1 for p in pilot if p["has_tp2_field"])

    # ── power extrapolation ───────────────────────────────────────────────
    # pass rate among scanned geometry units that also have candle + walk
    geom_with_ts = n_ts_hit
    walk_pass = n_pilot / max(1, min(len(geom_units), pilot_n + sum(skips.values())))
    # better: among first K geometry units attempted until pilot filled
    attempted = n_pilot + skips["no_candle_ts"] + skips["honest_none"] + skips["walk_exception"] + skips["hexc_exception"]
    pass_rate = n_pilot / attempted if attempted else 0.0
    # full file estimate: file is huge; use stream closed count from scan + pass_rate
    # Prefer: fraction of scan that is geometry * future * features
    frac_geom = n_geom / n_raw if n_raw else 0.0
    frac_feat = n_feat / n_raw if n_raw else 0.0
    frac_future = n_future_full / n_geom if n_geom else 0.0
    # rough expected clean units on scanned window
    expected_clean_scan = int(n_raw * frac_geom * frac_future * min(1.0, frac_feat / max(frac_geom, 1e-9)) * pass_rate)
    # full file size estimate via line count sample
    file_bytes = opp_path.stat().st_size
    avg_line = file_bytes / max(1, n_raw) if n_raw < args.max_scan else file_bytes / args.max_scan
    # if we hit max_scan, estimate total lines
    if n_raw >= args.max_scan:
        est_total_lines = int(file_bytes / max(avg_line, 1))
        # header lines negligible
        scale = est_total_lines / n_raw
        expected_clean_full = int(expected_clean_scan * scale)
    else:
        est_total_lines = n_raw
        expected_clean_full = expected_clean_scan

    # ── Q answers ─────────────────────────────────────────────────────────
    q = {}
    q["G0-Q1"] = {
        "question": "trade_decision population keys exist?",
        "practical": n_raw > 0 and n_geom > 0,
        "evidence": {
            "source": str(args.opportunities),
            "n_raw_scanned": n_raw,
            "unit_keys_present": ["timestamp", "direction", "entry", "sl", "tp", "features", "outcome", "mfe", "mae"],
            "note": "Population is opportunity/detection stream (F-022 class) — units are entry+geometry rows, not verified trade ledger. Usable as trade_decision candidates for clean re-label.",
        },
    }
    q["G0-Q2"] = {
        "question": "entry/SL/TP1 reconstructable?",
        "practical": (n_geom / n_raw if n_raw else 0) >= 0.80,
        "evidence": {
            "n_geometry_ok": n_geom,
            "pct_geometry": round(100 * n_geom / n_raw, 2) if n_raw else None,
            "n_with_tp2_field": n_tp2,
            "pct_tp2_field": round(100 * n_tp2 / n_geom, 2) if n_geom else 0.0,
            "tp2_note": "tp2 field almost/never present → three-head needs surrogate (MFE>=2R) or two-head protocol freeze at GATE-L",
            "pilot_tp2_field": tp2_field_pilot,
        },
    }
    q["G0-Q3"] = {
        "question": "OHLCV for forward_walk after entry?",
        "practical": (n_future_full / n_geom if n_geom else 0) >= 0.90 or (n_ts_hit / n_geom if n_geom else 0) >= 0.90,
        "evidence": {
            "candle_path": str(args.candles),
            "n_candles": n_candles,
            "n_geometry": n_geom,
            "n_timestamp_matched": n_ts_hit,
            "pct_ts_match": round(100 * n_ts_hit / n_geom, 2) if n_geom else None,
            "n_future_full_horizon": n_future_full,
            "pct_future_full": round(100 * n_future_full / n_geom, 2) if n_geom else None,
            "max_forward": args.max_forward,
        },
    }
    q["G0-Q4"] = {
        "question": "38-dim features@decision attachable?",
        "practical": (n_feat / n_raw if n_raw else 0) >= 0.80 or feat_ok_pilot / max(n_pilot, 1) >= 0.80,
        "evidence": {
            "n_feature_complete_scan": n_feat,
            "pct_feature_complete_scan": round(100 * n_feat / n_raw, 2) if n_raw else None,
            "pilot_feature_complete": feat_ok_pilot,
            "pilot_feature_pct": round(100 * feat_ok_pilot / n_pilot, 2) if n_pilot else None,
            "pit_note": "Stored opportunity features are pre-computed; F-051 centered-swing era may apply to historical JSONL — GATE-L must stamp pit_status.",
        },
    }
    q["G0-Q5"] = {
        "question": "pilot clean re-derive works end-to-end?",
        "practical": n_pilot >= 50 and len(exceptions) == 0,
        "evidence": {
            "n_pilot": n_pilot,
            "target_pilot_n": pilot_n,
            "skips": dict(skips),
            "exception_count": len(exceptions),
            "exception_samples": exceptions[:5],
            "clean_base_rates": {
                "y_tp1": y_tp1_rate,
                "y_tp2_surrogate": y_tp2_rate,
                "y_survives_be": y_surv_rate,
                "timeout_rate": timeout_rate,
            },
        },
    }
    q["G0-Q6"] = {
        "question": "contamination/agreement vs stream (diagnostic)?",
        "practical": True,  # always informative
        "evidence": {
            "agree_tp1_rate": agree_tp1_rate,
            "agree_survives_be_rate": agree_surv_rate,
            "n_survives_comparable": n_surv_both,
            "mean_abs_stream_mfe_r_minus_path_mfe_r": (
                round(sum(stream_mfe_vs_path) / len(stream_mfe_vs_path), 4) if stream_mfe_vs_path else None
            ),
            "note": "Low agreement strengthens need for clean y (F-022); does not fail feasibility.",
        },
    }
    q["G0-Q7"] = {
        "question": "powered train n plausible after filters?",
        "practical": expected_clean_full >= 500 or expected_clean_scan >= 500,
        "evidence": {
            "est_total_opportunity_lines": est_total_lines,
            "expected_clean_on_scan": expected_clean_scan,
            "expected_clean_full_file": expected_clean_full,
            "gate_l_floor_default": 500,
            "pass_rate_pilot_attempt": round(pass_rate, 4),
            "frac_geometry": round(frac_geom, 4),
            "frac_future_full": round(frac_future, 4),
            "frac_features": round(frac_feat, 4),
        },
    }
    q["G0-Q8"] = {
        "question": "engineering cost of full GATE-L builder?",
        "practical": True,
        "evidence": {
            "reuse": [
                "research.zone_label_audit.honest_outcome",
                "research.measurement.forward_walk",
                "research.measurement.horizon_excursion",
                "features.dataset_builder.extract_feature_vector",
                "scripts/analysis/bnbusdt_trade_anatomy.load_candles",
            ],
            "new_work": [
                "versioned clean JSONL/parquet writer + protocol_hash sidecar",
                "multi-instrument driver",
                "tp2 policy freeze (surrogate vs two-head)",
                "pit_status stamping / optional re-emit",
            ],
            "est_effort": "1–3 engineering days for TN GATE-L builder; +0.5–1 day for ENV labels sharing same walk",
            "risks": ["F-051 PIT on stored features", "tp2 geometry absent", "F-022 stream must stay diagnostic-only"],
        },
    }
    q["G0-Q9"] = {
        "question": "worth it now?",
        "practical": True,
        "evidence": {
            "rationale": (
                "User explicitly chartered TN GATE-0 + ENV-0 together after accepting ENV_ARCH_V1. "
                "F-005 TradeNet unwired + F-045/F-059 label contamination block any KEEP/RETIRE without clean y. "
                "Envelope design accepted; without clean MFE/MAE/holding labels ENV cannot leave design freeze. "
                "F-001 still binds (governance/throughput > intelligence) but measuring honesty of existing "
                "predictive surfaces is high knowledge-ROI and unblocks both ladders without spine wire."
            ),
            "worth_now": True,
            "authority_if_go": "GATE-L / ENV-L research builders only — no train promote, no neural_fn, no planner attach",
        },
    }

    # ENV-specific summary
    env_summary = {
        "n_pilot": n_pilot,
        "quantiles": {
            "mfe_r": {"q50": _pct(env_mfe, 50), "q80": _pct(env_mfe, 80), "q20": _pct(env_mfe, 20)},
            "mae_r_heat": {"q50": _pct(env_mae, 50), "q80": _pct(env_mae, 80), "q20": _pct(env_mae, 20)},
            "holding_bars_walk": {"q50": _pct(hold, 50), "q80": _pct(hold, 80)},
            "time_to_mfe_est": {"q50": _pct(ttm_vals, 50), "q80": _pct(ttm_vals, 80), "n": len(ttm_vals)},
        },
        "timeout_rate": timeout_rate,
        "mean_mfe_r_when_survives_be": round(sum(mfe_surv) / len(mfe_surv), 4) if mfe_surv else None,
        "mean_mfe_r_when_not": round(sum(mfe_die) / len(mfe_die), 4) if mfe_die else None,
        "label_defs": {
            "y_mfe_r": "horizon_excursion mfe_r (exit-agnostic, primary envelope)",
            "y_mae_r_heat": "abs(horizon_excursion mae_r)",
            "y_holding_bars": "forward_walk duration_candles under intrabar_fixed + unit SL/TP",
            "y_time_to_mfe": "bars until path MFE first attained",
            "y_survives_be_link": "forward_walk.reached_1r (TradeNet head; correlated with envelope mfe)",
        },
        "non_constant": bool(env_mfe) and (max(env_mfe) - min(env_mfe) > 1e-6),
        "feasible_labels": n_pilot >= 50 and bool(env_mfe) and (max(env_mfe) > min(env_mfe)),
    }

    # Verdicts
    q1_5_ok = all(q[k]["practical"] for k in ("G0-Q1", "G0-Q2", "G0-Q3", "G0-Q4", "G0-Q5"))
    q7_ok = q["G0-Q7"]["practical"]
    q8_ok = q["G0-Q8"]["practical"]
    q9_worth = bool(q["G0-Q9"]["evidence"]["worth_now"])

    if not q1_5_ok:
        tn_verdict = "INFEASIBLE_STOP"
    elif not q7_ok:
        tn_verdict = "INFEASIBLE_STOP"  # or plan multi-window — if scan expects <500 but full file large, check
    elif q9_worth:
        tn_verdict = "FEASIBLE_GO"
    else:
        tn_verdict = "FEASIBLE_DEFER"

    # Soften Q7: if full-file expected >= 500 even if scan window small
    if tn_verdict == "INFEASIBLE_STOP" and expected_clean_full >= 500 and q1_5_ok:
        tn_verdict = "FEASIBLE_GO" if q9_worth else "FEASIBLE_DEFER"
        q["G0-Q7"]["practical"] = True
        q["G0-Q7"]["evidence"]["note"] = "Re-evaluated practical via full-file extrapolation"

    if env_summary["feasible_labels"] and q1_5_ok and expected_clean_full >= 500:
        env_verdict = "FEASIBLE_GO" if q9_worth else "FEASIBLE_DEFER"
    elif env_summary["feasible_labels"] and q1_5_ok:
        env_verdict = "FEASIBLE_GO" if (q9_worth and expected_clean_full >= 200) else "FEASIBLE_DEFER"
    else:
        env_verdict = "INFEASIBLE_STOP"

    summary = {
        "run_id": RUN_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "opportunities": str(args.opportunities),
        "candles": str(args.candles),
        "exit_model": "intrabar_fixed",
        "max_forward": args.max_forward,
        "cost_note": "12 bps not applied to pilot heads (label geometry only)",
        "authority": "NONE — GATE-0 / ENV-0 feasibility only; no train/wire/promote",
        "census": {
            "n_raw_scanned": n_raw,
            "n_geometry": n_geom,
            "n_feature_complete": n_feat,
            "n_stream_outcome": n_closed_stream,
            "outcome_top": outcome_ctr.most_common(8),
            "n_candles": n_candles,
            "n_ts_match": n_ts_hit,
            "n_future_full": n_future_full,
            "est_total_lines": est_total_lines,
            "expected_clean_full": expected_clean_full,
        },
        "pilot": {
            "n": n_pilot,
            "skips": dict(skips),
            "exception_count": len(exceptions),
        },
        "tn_questions": q,
        "tn_verdict": tn_verdict,
        "env_summary": env_summary,
        "env_verdict": env_verdict,
        "shared_notes": {
            "population_class": "opportunities detection stream (F-022) — clean y via forward_walk only",
            "tp2_policy": "no tp2 field; pilot used horizon reached_2r surrogate",
            "envelope_shares_walk": True,
        },
    }

    # ── write artifacts ───────────────────────────────────────────────────
    tn_dir = ROOT / "results" / "tradenet" / "gate0_feasibility" / RUN_ID
    env_dir = ROOT / "results" / "envelope" / "gate0_feasibility" / RUN_ID
    if args.out_dir:
        base = ROOT / args.out_dir
        tn_dir = base / "tradenet"
        env_dir = base / "envelope"
    tn_dir.mkdir(parents=True, exist_ok=True)
    env_dir.mkdir(parents=True, exist_ok=True)

    pilot_path = tn_dir / "pilot_summary.json"
    pilot_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (env_dir / "pilot_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    tn_report = _render_tn_report(summary)
    env_report = _render_env_report(summary)
    (tn_dir / "report.md").write_text(tn_report, encoding="utf-8")
    (env_dir / "report.md").write_text(env_report, encoding="utf-8")
    # also copy to docs/governance for durable pointer
    gov_tn = ROOT / "docs" / "governance" / f"tradenet_gate0_feasibility-{RUN_ID}.md"
    gov_env = ROOT / "docs" / "governance" / f"envelope_gate0_feasibility-{RUN_ID}.md"
    gov_tn.write_text(tn_report, encoding="utf-8")
    gov_env.write_text(env_report, encoding="utf-8")
    # latest pointers
    (ROOT / "docs" / "governance" / "tradenet_gate0_feasibility.LATEST.md").write_text(
        tn_report, encoding="utf-8"
    )
    (ROOT / "docs" / "governance" / "envelope_gate0_feasibility.LATEST.md").write_text(
        env_report, encoding="utf-8"
    )

    print(f"[gate0] TN_VERDICT={tn_verdict}  ENV_VERDICT={env_verdict}")
    print(f"[gate0] wrote {tn_dir}")
    print(f"[gate0] wrote {env_dir}")
    print(f"[gate0] docs {gov_tn.name} / {gov_env.name}")
    return 0


def _render_tn_report(s: dict) -> str:
    q = s["tn_questions"]
    lines = [
        f"# TradeNet GATE-0 Feasibility Report",
        "",
        f"| Field | Value |",
        f"|-------|--------|",
        f"| run_id | `{s['run_id']}` |",
        f"| created_utc | {s['created_utc']} |",
        f"| instrument | {s['instrument']} |",
        f"| opportunities | `{s['opportunities']}` |",
        f"| candles | `{s['candles']}` |",
        f"| exit_model | `{s['exit_model']}` max_forward={s['max_forward']} |",
        f"| **verdict** | **{s['tn_verdict']}** |",
        f"| authority | {s['authority']} |",
        "",
        "## Census",
        "",
        "```json",
        json.dumps(s["census"], indent=2),
        "```",
        "",
        "## G0-Q1 … G0-Q9",
        "",
    ]
    for k in [f"G0-Q{i}" for i in range(1, 10)]:
        cell = q[k]
        lines += [
            f"### {k} — {cell['question']}",
            "",
            f"- **practical:** `{cell['practical']}`",
            f"- **evidence:**",
            "",
            "```json",
            json.dumps(cell["evidence"], indent=2, default=str),
            "```",
            "",
        ]
    lines += [
        "## Verdict rule application",
        "",
        f"- Q1–Q5 practical: `{all(q[f'G0-Q{i}']['practical'] for i in range(1,6))}`",
        f"- Q7 power plan: `{q['G0-Q7']['practical']}` (expected_clean_full={s['census']['expected_clean_full']})",
        f"- Q8 cost bounded: `{q['G0-Q8']['practical']}`",
        f"- Q9 worth now: `{q['G0-Q9']['evidence']['worth_now']}`",
        "",
        f"**GATE-0 verdict: {s['tn_verdict']}**",
        "",
        "### Effect",
        "",
    ]
    if s["tn_verdict"] == "FEASIBLE_GO":
        lines += [
            "- `TRADENET_GATE_0_STATUS = PASS`",
            "- GATE-L engineering **may** start (research builder only)",
            "- Still **forbidden**: train promote, KEEP/RETIRE authority, neural_fn wire, GATE-P",
            "",
        ]
    elif s["tn_verdict"] == "FEASIBLE_DEFER":
        lines += [
            "- Assessment complete; GATE-L **BLOCKED_DEFER** until User reopens",
            "",
        ]
    else:
        lines += [
            "- Clean-label program stop or remediate hard-fail questions",
            "",
        ]
    lines += [
        "## Dual-track note",
        "",
        f"Envelope ENV-0 ran on the same pilot (`env_verdict={s['env_verdict']}`). "
        "Shared substrate: `honest_outcome` + `horizon_excursion`. "
        "See `docs/governance/envelope_gate0_feasibility.LATEST.md`.",
        "",
    ]
    return "\n".join(lines)


def _render_env_report(s: dict) -> str:
    e = s["env_summary"]
    lines = [
        f"# EnvelopeNet ENV-0 Feasibility Report",
        "",
        f"| Field | Value |",
        f"|-------|--------|",
        f"| run_id | `{s['run_id']}` |",
        f"| design | `ENV_ARCH_V1` (accepted) |",
        f"| created_utc | {s['created_utc']} |",
        f"| instrument | {s['instrument']} |",
        f"| **verdict** | **{s['env_verdict']}** |",
        f"| authority | {s['authority']} |",
        "",
        "## Purpose",
        "",
        "Is a clean-label path for EnvelopeNet operating-boundary targets **practical** and **worth implementing**?",
        "Labels: MFE/MAE (R), holding bars, time-to-MFE — via `horizon_excursion` + `forward_walk`, never stream MFE alone.",
        "",
        "## Pilot quantiles (exit-agnostic envelope)",
        "",
        "```json",
        json.dumps(e, indent=2, default=str),
        "```",
        "",
        "## Shared logistics (with TradeNet GATE-0)",
        "",
        "```json",
        json.dumps(
            {
                "census": s["census"],
                "pilot": s["pilot"],
                "G0-Q1_geometry": s["tn_questions"]["G0-Q1"]["practical"],
                "G0-Q3_ohlcv": s["tn_questions"]["G0-Q3"]["practical"],
                "G0-Q4_features": s["tn_questions"]["G0-Q4"]["practical"],
                "G0-Q5_walk": s["tn_questions"]["G0-Q5"]["practical"],
                "agreement_stream_vs_clean_tp1": s["tn_questions"]["G0-Q6"]["evidence"]["agree_tp1_rate"],
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        f"**ENV-0 verdict: {s['env_verdict']}**",
        "",
        "### Effect",
        "",
    ]
    if s["env_verdict"] == "FEASIBLE_GO":
        lines += [
            "- ENV-L clean-label builder **may** start (research only), preferably **shared** with TN GATE-L walk",
            "- Still **forbidden**: spine attach, planner TTL rewrite, fusion coherence channel, train promote",
            "",
        ]
    else:
        lines += [
            f"- Verdict `{s['env_verdict']}` — do not implement ENV-L until remediated or User reopens",
            "",
        ]
    lines += [
        "## Distinction check (non-duplication)",
        "",
        "- TradeNet pilot heads: Bernoulli y_tp1 / y_survives_be (and tp2 surrogate)",
        "- Envelope pilot heads: continuous mfe_r / mae_r_heat / holding_bars / time_to_mfe",
        "- Related horizon, different information kind — design non-duplication rule held in pilot schema",
        "",
        f"TN GATE-0 verdict on same run: **{s['tn_verdict']}** "
        f"(`docs/governance/tradenet_gate0_feasibility.LATEST.md`).",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
