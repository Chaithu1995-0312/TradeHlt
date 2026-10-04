"""L-003H — Candle replay for trail/exit transition events (standalone).

Measure-only. Does NOT modify src/. Duplicates opportunity_scanner._simulate
(trailing, trail_mult=0.5) and forward_walk(exit_model=intrabar_fixed) with
event hooks for trail activation / joint timing.

Governing exit horizon: MAX_FORWARD=40 (matches anatomy / scanner / forward_walk).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as stats
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]

MAX_FORWARD = 40
TRAIL_MULT = 0.5
VERSION = "L-003H.v1"
L003F_ESC_RATE = 0.315257  # ~31.53% EARLY_STOP_CANDIDATE / JOINT_STATE_SL_TP
L003F_ESC_N = 176471
L003F_N = 559768
L003F_PER_INST = {
    "BNBUSDT": {"n": 139942, "esc": 44791, "rate": 0.3201},
    "BTCUSDT": {"n": 139942, "esc": 43392, "rate": 0.3101},
    "ETHUSDT": {"n": 139942, "esc": 43725, "rate": 0.3125},
    "SOLUSDT": {"n": 139942, "esc": 44563, "rate": 0.3184},
}

_OPP_DEFAULTS = {
    "BNBUSDT": "logs/BNBUSDT/20260530_011521/opportunities.jsonl",
    "BTCUSDT": "logs/BTCUSDT/anatomy_BTCUSDT_20260613/opportunities.jsonl",
    "ETHUSDT": "logs/ETHUSDT/anatomy_ETHUSDT_20260613/opportunities.jsonl",
    "SOLUSDT": "logs/SOLUSDT/anatomy_SOLUSDT_20260613/opportunities.jsonl",
}

INSTRUMENTS = ["BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"]


def _norm_ts(s: str) -> str:
    return s.replace("T", " ").strip()


def load_candles(csv_path: Path):
    """Plain OHLC arrays + ts->index; SimpleNamespace bars for optional debug."""
    highs, lows, closes, opens, ts_list = [], [], [], [], []
    ts_to_idx = {}
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        for i, row in enumerate(rd):
            ts = _norm_ts(row["timestamp"])
            highs.append(float(row["high"]))
            lows.append(float(row["low"]))
            closes.append(float(row["close"]))
            opens.append(float(row["open"]))
            ts_list.append(ts)
            ts_to_idx[ts] = i
    return {
        "high": highs,
        "low": lows,
        "close": closes,
        "open": opens,
        "ts": ts_list,
        "ts_to_idx": ts_to_idx,
        "n": len(highs),
    }


def joint_state_id(scanner: str, oracle: str) -> str:
    if scanner == "TP_HIT" and oracle == "TP_HIT":
        return "BOTH_TP"
    if scanner == "SL_HIT" and oracle == "SL_HIT":
        return "BOTH_SL"
    if scanner == "TIMEOUT" and oracle == "TIMEOUT":
        return "BOTH_TIMEOUT"
    if scanner == "SL_HIT" and oracle == "TP_HIT":
        return "JOINT_STATE_SL_TP"
    if scanner == "TP_HIT" and oracle == "SL_HIT":
        return "FALSE_TP_CANDIDATE"
    if scanner == "TIMEOUT" and oracle == "TP_HIT":
        return "LATE_REALIZATION"
    if scanner == "TIMEOUT" and oracle == "SL_HIT":
        return "LATE_FAILURE"
    if scanner == "TP_HIT" and oracle == "TIMEOUT":
        return "SCANNER_TP_ORACLE_TIMEOUT"
    if scanner == "SL_HIT" and oracle == "TIMEOUT":
        return "SCANNER_SL_ORACLE_TIMEOUT"
    return f"OTHER_{scanner}_{oracle}"


def trailing_walk_events(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    highs,
    lows,
    closes,
    start: int,
    n_bars: int,
    trail_mult: float = TRAIL_MULT,
) -> dict:
    """Duplicate opportunity_scanner._simulate with trail-activation hooks.

    Uses list slices indexed from candle start (exclusive entry bar).
    """
    risk = abs(entry - sl)
    if risk <= 0:
        return {"ok": False, "reason": "zero_risk"}
    trail_dist = trail_mult * risk
    trail_stop = sl
    peak = entry
    trail_activated = False
    bars_to_trail_activation = None
    initial_sl = sl
    end = min(start + n_bars, len(highs))
    duration = 0
    scanner_fill_r = None

    for i in range(start, end):
        high = highs[i]
        low = lows[i]
        duration = i - start + 1

        if direction == "long":
            if high > peak:
                peak = high
            if peak >= entry + trail_dist:
                new_stop = peak - trail_dist
                if new_stop > trail_stop:
                    trail_stop = new_stop
                if not trail_activated:
                    # first ratchet / activation when peak clears trail_dist
                    if trail_stop != initial_sl or peak >= entry + trail_dist:
                        trail_activated = True
                        bars_to_trail_activation = duration
            sl_hit = low <= trail_stop
            tp_hit = high >= tp
        else:
            if low < peak:
                peak = low
            if peak <= entry - trail_dist:
                new_stop = peak + trail_dist
                if new_stop < trail_stop:
                    trail_stop = new_stop
                if not trail_activated:
                    if trail_stop != initial_sl or peak <= entry - trail_dist:
                        trail_activated = True
                        bars_to_trail_activation = duration
            sl_hit = high >= trail_stop
            tp_hit = low <= tp

        if sl_hit:
            trail_past_tp = (
                (direction == "long" and trail_stop >= tp)
                or (direction == "short" and trail_stop <= tp)
            )
            if trail_past_tp:
                rr = (tp - entry) / risk if direction == "long" else (entry - tp) / risk
                return {
                    "ok": True,
                    "trail_activated": trail_activated,
                    "bars_to_trail_activation": bars_to_trail_activation,
                    "trail_exit": False,  # TP honoured despite SL touch after trail past TP
                    "scanner_outcome_replay": "TP_HIT",
                    "scanner_exit_bar": duration,
                    "scanner_fill_r": float(round(rr, 4)),
                }
            rr = (
                (trail_stop - entry) / risk
                if direction == "long"
                else (entry - trail_stop) / risk
            )
            return {
                "ok": True,
                "trail_activated": trail_activated,
                "bars_to_trail_activation": bars_to_trail_activation,
                "trail_exit": bool(trail_activated),
                "scanner_outcome_replay": "SL_HIT",
                "scanner_exit_bar": duration,
                "scanner_fill_r": float(round(rr, 4)),
            }
        if tp_hit:
            rr = (tp - entry) / risk if direction == "long" else (entry - tp) / risk
            return {
                "ok": True,
                "trail_activated": trail_activated,
                "bars_to_trail_activation": bars_to_trail_activation,
                "trail_exit": False,
                "scanner_outcome_replay": "TP_HIT",
                "scanner_exit_bar": duration,
                "scanner_fill_r": float(round(rr, 4)),
            }

    # TIMEOUT
    if duration == 0:
        unrealized = 0.0
    else:
        last_close = closes[end - 1]
        unrealized = (last_close - entry) if direction == "long" else (entry - last_close)
    rr = unrealized / risk if risk > 0 else 0.0
    return {
        "ok": True,
        "trail_activated": trail_activated,
        "bars_to_trail_activation": bars_to_trail_activation,
        "trail_exit": False,
        "scanner_outcome_replay": "TIMEOUT",
        "scanner_exit_bar": duration if duration > 0 else n_bars,
        "scanner_fill_r": float(round(rr, 4)),
    }


def fixed_walk_events(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    highs,
    lows,
    closes,
    start: int,
    n_bars: int,
) -> dict:
    """Duplicate forward_walk exit_model=intrabar_fixed (no ratchet)."""
    risk = abs(entry - sl)
    if risk <= 0:
        return {"ok": False, "reason": "zero_risk"}
    end = min(start + n_bars, len(highs))
    duration = 0
    for i in range(start, end):
        high = highs[i]
        low = lows[i]
        duration = i - start + 1
        if direction == "long":
            sl_hit = low <= sl
            tp_hit = high >= tp
        else:
            sl_hit = high >= sl
            tp_hit = low <= tp

        # Conservative SL-before-TP tie-break (matches forward_walk / CRTEngine)
        if sl_hit:
            rr = -1.0
            return {
                "ok": True,
                "oracle_outcome_replay": "SL_HIT",
                "oracle_exit_bar": duration,
                "oracle_tp_bar": None,
                "oracle_sl_bar": duration,
                "oracle_fill_r": rr,
            }
        if tp_hit:
            rr = abs(tp - entry) / risk
            return {
                "ok": True,
                "oracle_outcome_replay": "TP_HIT",
                "oracle_exit_bar": duration,
                "oracle_tp_bar": duration,
                "oracle_sl_bar": None,
                "oracle_fill_r": float(round(rr, 4)),
            }

    if duration == 0:
        unrealized = 0.0
    else:
        last_close = closes[end - 1]
        unrealized = (last_close - entry) if direction == "long" else (entry - last_close)
    rr = unrealized / risk if risk > 0 else 0.0
    return {
        "ok": True,
        "oracle_outcome_replay": "TIMEOUT",
        "oracle_exit_bar": duration if duration > 0 else n_bars,
        "oracle_tp_bar": None,
        "oracle_sl_bar": None,
        "oracle_fill_r": float(round(rr, 4)),
    }


def _median(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return float(stats.median(xs))


def _pct(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return float(xs[0])
    # nearest-rank
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
    return float(xs[k])


def _rate(num, den):
    return (num / den) if den else None


def process_instrument(inst: str, max_forward: int = MAX_FORWARD, progress_every: int = 25000):
    opp_rel = _OPP_DEFAULTS[inst]
    candles_path = ROOT_DIR / f"data/{inst}_M15.csv"
    opp_path = ROOT_DIR / opp_rel
    print(f"[{inst}] loading candles {candles_path}")
    c = load_candles(candles_path)
    highs, lows, closes = c["high"], c["low"], c["close"]
    ts_to_idx = c["ts_to_idx"]
    print(f"[{inst}] candles={c['n']}  opps={opp_path}")

    rows = []
    skips = Counter()
    t0 = time.time()
    with opp_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            opp = json.loads(line)
            if opp.get("type") == "run_header":
                continue
            ts = _norm_ts(opp["timestamp"])
            idx = ts_to_idx.get(ts)
            if idx is None:
                skips["no_candle"] += 1
                continue
            direction = str(opp["direction"]).lower()
            entry = float(opp["entry"])
            sl = float(opp["sl"])
            tp = float(opp.get("tp", entry))
            risk = abs(entry - sl)
            if risk <= 0:
                skips["zero_risk"] += 1
                continue
            start = idx + 1
            if start >= c["n"]:
                skips["no_future"] += 1
                continue

            tr = trailing_walk_events(
                direction, entry, sl, tp, highs, lows, closes, start, max_forward
            )
            fx = fixed_walk_events(
                direction, entry, sl, tp, highs, lows, closes, start, max_forward
            )
            if not tr["ok"] or not fx["ok"]:
                skips["sim_fail"] += 1
                continue

            art_outcome = opp.get("outcome", "")
            s_out = tr["scanner_outcome_replay"]
            o_out = fx["oracle_outcome_replay"]
            js_replay = joint_state_id(s_out, o_out)
            js_artifact = joint_state_id(art_outcome, o_out) if art_outcome else "OTHER_MISSING_ARTIFACT"

            oracle_tp = fx["oracle_tp_bar"]
            scanner_exit = tr["scanner_exit_bar"]
            oracle_exit = fx["oracle_exit_bar"]
            # Measured operationalization of "stopped earlier on the path"
            scanner_exit_before_oracle_tp = bool(
                o_out == "TP_HIT"
                and oracle_tp is not None
                and scanner_exit is not None
                and scanner_exit < oracle_tp
            )
            # also vs oracle_exit_bar (identical when TP)
            scanner_exit_before_oracle_exit = bool(
                o_out == "TP_HIT"
                and oracle_exit is not None
                and scanner_exit is not None
                and scanner_exit < oracle_exit
            )

            row = {
                "instrument": inst,
                "timestamp": ts,
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "art_outcome": art_outcome,
                "trail_activated": tr["trail_activated"],
                "bars_to_trail_activation": tr["bars_to_trail_activation"],
                "trail_exit": tr["trail_exit"],
                "scanner_outcome_replay": s_out,
                "scanner_exit_bar": scanner_exit,
                "scanner_fill_r": tr["scanner_fill_r"],
                "oracle_outcome_replay": o_out,
                "oracle_exit_bar": oracle_exit,
                "oracle_tp_bar": oracle_tp,
                "oracle_sl_bar": fx["oracle_sl_bar"],
                "oracle_fill_r": fx["oracle_fill_r"],
                "joint_state_replay": js_replay,
                "joint_state_artifact": js_artifact,
                "scanner_label_match_artifact": art_outcome == s_out,
                "scanner_exit_before_oracle_tp": scanner_exit_before_oracle_tp,
                "scanner_exit_before_oracle_exit": scanner_exit_before_oracle_exit,
                "trail_activated_and_joint_sl_tp": bool(
                    tr["trail_activated"] and js_replay == "JOINT_STATE_SL_TP"
                ),
                "exit_bar_delta": (
                    (oracle_exit - scanner_exit)
                    if (oracle_exit is not None and scanner_exit is not None)
                    else None
                ),
            }
            rows.append(row)
            if progress_every and len(rows) % progress_every == 0:
                elapsed = time.time() - t0
                print(f"  [{inst}] {len(rows)} rows  ({elapsed:.1f}s)")

    elapsed = time.time() - t0
    print(f"[{inst}] done n={len(rows)} skips={dict(skips)} elapsed={elapsed:.1f}s")
    return rows, dict(skips), elapsed


def summarize_by_joint(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["joint_state_replay"]].append(r)

    out = {}
    for state, grp in sorted(by.items(), key=lambda kv: -len(kv[1])):
        n = len(grp)
        act = sum(1 for r in grp if r["trail_activated"])
        trail_exit_n = sum(1 for r in grp if r["trail_exit"])
        seb = [r["scanner_exit_before_oracle_tp"] for r in grp]
        # rate among rows where oracle is TP (denominator for early-stop op)
        oracle_tp_rows = [r for r in grp if r["oracle_outcome_replay"] == "TP_HIT"]
        seb_among_otp = sum(1 for r in oracle_tp_rows if r["scanner_exit_before_oracle_tp"])
        act_bars = [r["bars_to_trail_activation"] for r in grp if r["bars_to_trail_activation"] is not None]
        s_ex = [r["scanner_exit_bar"] for r in grp if r["scanner_exit_bar"] is not None]
        o_ex = [r["oracle_exit_bar"] for r in grp if r["oracle_exit_bar"] is not None]
        deltas = [r["exit_bar_delta"] for r in grp if r["exit_bar_delta"] is not None]
        out[state] = {
            "n": n,
            "rate": n / len(rows) if rows else None,
            "trail_activated_n": act,
            "trail_activated_rate": _rate(act, n),
            "trail_exit_n": trail_exit_n,
            "trail_exit_rate": _rate(trail_exit_n, n),
            "median_bars_to_trail_activation": _median(act_bars),
            "scanner_exit_before_oracle_tp_n": sum(1 for x in seb if x),
            "scanner_exit_before_oracle_tp_rate": _rate(sum(1 for x in seb if x), n),
            "scanner_exit_before_oracle_tp_among_oracle_tp": {
                "n_oracle_tp": len(oracle_tp_rows),
                "n_true": seb_among_otp,
                "rate": _rate(seb_among_otp, len(oracle_tp_rows)),
            },
            "scanner_exit_bar": {
                "median": _median(s_ex),
                "p25": _pct(s_ex, 25),
                "p75": _pct(s_ex, 75),
                "mean": (sum(s_ex) / len(s_ex)) if s_ex else None,
            },
            "oracle_exit_bar": {
                "median": _median(o_ex),
                "p25": _pct(o_ex, 25),
                "p75": _pct(o_ex, 75),
                "mean": (sum(o_ex) / len(o_ex)) if o_ex else None,
            },
            "exit_bar_delta_oracle_minus_scanner": {
                "median": _median(deltas),
                "p25": _pct(deltas, 25),
                "p75": _pct(deltas, 75),
                "mean": (sum(deltas) / len(deltas)) if deltas else None,
                "frac_positive": _rate(sum(1 for d in deltas if d > 0), len(deltas)),
            },
        }
    return out


def loio_trail_activated_in_joint_sl_tp(per_inst_summaries):
    """Leave-one-instrument-out stability of trail_activated rate within JOINT_STATE_SL_TP."""
    insts = list(per_inst_summaries.keys())
    # gather per-instrument (n_act, n) for JOINT_STATE_SL_TP
    parts = {}
    for inst, summ in per_inst_summaries.items():
        js = summ.get("by_joint_state_replay", {}).get("JOINT_STATE_SL_TP", {})
        parts[inst] = {
            "n": js.get("n", 0) or 0,
            "act": js.get("trail_activated_n", 0) or 0,
            "rate": js.get("trail_activated_rate"),
        }
    loio = {}
    for hold in insts:
        n = sum(parts[i]["n"] for i in insts if i != hold)
        act = sum(parts[i]["act"] for i in insts if i != hold)
        loio[f"holdout_{hold}"] = {
            "n_joint_sl_tp": n,
            "trail_activated_n": act,
            "trail_activated_rate": _rate(act, n),
        }
    rates = [v["trail_activated_rate"] for v in loio.values() if v["trail_activated_rate"] is not None]
    return {
        "per_instrument": parts,
        "loio": loio,
        "loio_rate_mean": (sum(rates) / len(rates)) if rates else None,
        "loio_rate_std": (stats.pstdev(rates) if len(rates) > 1 else 0.0) if rates else None,
        "loio_rate_range": [min(rates), max(rates)] if rates else None,
    }


def falsification_lean(agg_by_joint: dict) -> dict:
    j = agg_by_joint.get("JOINT_STATE_SL_TP", {})
    both_sl = agg_by_joint.get("BOTH_SL", {})
    both_tp = agg_by_joint.get("BOTH_TP", {})
    ta_j = j.get("trail_activated_rate")
    ta_sl = both_sl.get("trail_activated_rate")
    ta_tp = both_tp.get("trail_activated_rate")
    te_j = j.get("trail_exit_rate")
    te_sl = both_sl.get("trail_exit_rate")
    te_tp = both_tp.get("trail_exit_rate")
    seb_j = j.get("scanner_exit_before_oracle_tp_rate")
    seb_otp = (j.get("scanner_exit_before_oracle_tp_among_oracle_tp") or {}).get("rate")
    seb_tp_otp = (both_tp.get("scanner_exit_before_oracle_tp_among_oracle_tp") or {}).get("rate")

    enrichment_vs_both_sl = (ta_j - ta_sl) if (ta_j is not None and ta_sl is not None) else None
    enrichment_vs_both_tp = (ta_j - ta_tp) if (ta_j is not None and ta_tp is not None) else None

    weakens_trail_involvement = (
        enrichment_vs_both_sl is not None and abs(enrichment_vs_both_sl) < 0.05
    )
    weakens_stopped_earlier = seb_otp is not None and seb_otp < 0.90
    supports_trail_activated_vs_both_tp = (
        enrichment_vs_both_tp is not None and enrichment_vs_both_tp > 0.10
    )
    differentiates_vs_both_tp_via_seb = (
        seb_otp is not None
        and seb_tp_otp is not None
        and (seb_otp - (seb_tp_otp or 0.0)) > 0.50
    )
    differentiates_vs_both_tp_via_trail_exit = (
        te_j is not None and te_tp is not None and (te_j - te_tp) > 0.50
    )

    leans = []
    if weakens_trail_involvement:
        leans.append(
            "WEAKENS_TRAIL_INVOLVEMENT: JOINT_STATE_SL_TP trail_activated_rate approx BOTH_SL (no enrichment)"
        )
    else:
        leans.append(
            "SUPPORTS_TRAIL_INVOLVEMENT_VS_BOTH_SL: material trail_activated enrichment vs BOTH_SL"
        )
    if weakens_stopped_earlier:
        leans.append(
            "WEAKENS_STOPPED_EARLIER: scanner_exit_before_oracle_tp not near-certain in JOINT_STATE_SL_TP"
        )
    else:
        leans.append(
            "SUPPORTS_STOPPED_EARLIER_OPERATIONALIZATION: scanner_exit_before_oracle_tp near-certain in JOINT_STATE_SL_TP (still not trail-causality proof)"
        )
    if supports_trail_activated_vs_both_tp:
        leans.append(
            "SUPPORTS_TRAIL_INVOLVEMENT_CANDIDATE_VS_BOTH_TP: large trail_activated enrichment vs BOTH_TP"
        )
    else:
        leans.append(
            "NO_TRAIL_ACTIVATED_ENRICHMENT_VS_BOTH_TP: trail_activated alone does not separate JOINT from BOTH_TP"
        )
    if differentiates_vs_both_tp_via_seb:
        leans.append(
            "DIFFERENTIATES_VS_BOTH_TP_VIA_EXIT_TIMING: scanner_exit_before_oracle_tp gap vs BOTH_TP"
        )
    if differentiates_vs_both_tp_via_trail_exit:
        leans.append(
            "DIFFERENTIATES_VS_BOTH_TP_VIA_TRAIL_EXIT: trail_exit_rate gap vs BOTH_TP"
        )

    if (
        (not weakens_trail_involvement)
        and (not weakens_stopped_earlier)
        and (differentiates_vs_both_tp_via_seb or differentiates_vs_both_tp_via_trail_exit)
    ):
        overall = "LEAN_SUPPORTS_TRAIL_EARLY_EXIT_PATTERN_IN_JOINT_STATE_SL_TP"
    elif weakens_trail_involvement and weakens_stopped_earlier:
        overall = "LEAN_FALSIFIES_SIMPLE_TRAIL_EARLY_STOP_STORY"
    elif weakens_trail_involvement and (not weakens_stopped_earlier):
        overall = "LEAN_EARLY_EXIT_WITHOUT_TRAIL_ENRICHMENT_VS_BOTH_SL"
    elif (not weakens_trail_involvement) and weakens_stopped_earlier:
        overall = "LEAN_TRAIL_ENRICHED_BUT_EXIT_TIMING_NOT_NEAR_CERTAIN"
    else:
        overall = "MIXED"

    return {
        "trail_activated_rate_JOINT_STATE_SL_TP": ta_j,
        "trail_activated_rate_BOTH_SL": ta_sl,
        "trail_activated_rate_BOTH_TP": ta_tp,
        "trail_exit_rate_JOINT_STATE_SL_TP": te_j,
        "trail_exit_rate_BOTH_SL": te_sl,
        "trail_exit_rate_BOTH_TP": te_tp,
        "enrichment_vs_BOTH_SL": enrichment_vs_both_sl,
        "enrichment_vs_BOTH_TP": enrichment_vs_both_tp,
        "scanner_exit_before_oracle_tp_rate_JOINT_STATE_SL_TP": seb_j,
        "scanner_exit_before_oracle_tp_among_oracle_tp_JOINT_STATE_SL_TP": seb_otp,
        "scanner_exit_before_oracle_tp_among_oracle_tp_BOTH_TP": seb_tp_otp,
        "thresholds": {
            "trail_enrichment_vs_BOTH_SL_abs_lt": 0.05,
            "seb_near_certain_lt": 0.90,
            "trail_enrichment_vs_BOTH_TP_gt": 0.10,
            "seb_or_trail_exit_gap_vs_BOTH_TP_gt": 0.50,
        },
        "criterion_flags": {
            "weakens_trail_involvement_vs_BOTH_SL": weakens_trail_involvement,
            "weakens_stopped_earlier": weakens_stopped_earlier,
            "supports_trail_activated_enrichment_vs_BOTH_TP": supports_trail_activated_vs_both_tp,
            "differentiates_vs_BOTH_TP_via_scanner_exit_before_oracle_tp": differentiates_vs_both_tp_via_seb,
            "differentiates_vs_BOTH_TP_via_trail_exit": differentiates_vs_both_tp_via_trail_exit,
        },
        "leans": leans,
        "overall_lean": overall,
        "caveats": [
            "scanner_exit_before_oracle_tp is a measured path-timing operationalization; not proof of trail causality alone",
            "detector stopped early remains INFERENCE unless exit timestamps prove scanner_exit_bar earlier than oracle_tp_bar",
            "trail_activated enrichment vs BOTH_SL supports trail-involvement candidate; JOINT and BOTH_TP may both be fully activated so activation alone may not separate them - exit timing / trail_exit can",
            "trail_activated enrichment is not causation of label mismatch alone",
        ],
    }


def write_bnb_events_csv(rows, path: Path):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def render_md(payload: dict) -> str:
    run_id = payload["run_id"]
    agg = payload["aggregate"]
    lean = payload["falsification_lean"]
    recon = payload["reconcile_vs_l003f"]
    by = agg["by_joint_state_replay"]
    j = by.get("JOINT_STATE_SL_TP", {})
    both_sl = by.get("BOTH_SL", {})
    both_tp = by.get("BOTH_TP", {})

    def pct(x):
        return "n/a" if x is None else f"{100.0 * x:.2f}%"

    lines = []
    lines.append("# L-003H — Trail / exit transition events (candle replay)")
    lines.append("")
    lines.append("**Status:** MEASURED (falsification-oriented observation)")
    lines.append("**L-003 remains NOT frozen** — attribution remains blocked (IDENTITY + OUTCOME_SEMANTICS)")
    lines.append(f"**Date (UTC):** {payload['generated_at_utc']}")
    lines.append(f"**Branch pin:** `{payload['branch']}` @ `{payload['git_commit_sha']}`")
    lines.append(f"**run_id:** `{run_id}`")
    lines.append(f"**version / doctrine:** `{VERSION}`")
    lines.append("")
    lines.append(f"Machine-readable: `docs/governance/analytics_trail_exit_transitions_l003h-2026-09-07.json`.")
    lines.append("")
    lines.append("## Banner / discipline")
    lines.append("")
    lines.append("**Observation → Measurement → Evidence → Promotion.**")
    lines.append("")
    lines.append("- **Question:** Does `JOINT_STATE_SL_TP` show measured trail/exit transition patterns that `BOTH_SL` / `BOTH_TP` do not?")
    lines.append("- **Method:** candle replay of trailing walk (scanner process, `trail_mult=0.5`) and fixed walk (`intrabar_fixed` oracle) with event hooks — **not** inferred from T_MAE alone.")
    lines.append("- **NOT answered:** trail *causes* label mismatch; which Y should replace the other; promotion.")
    lines.append("")
    lines.append("## Terminology (L-003-TERM.v1 compliant)")
    lines.append("")
    lines.append("| Term | Meaning | Claim class |")
    lines.append("|---|---|---|")
    lines.append("| `scanner_outcome_replay` | re-simulated `opportunity_scanner._simulate` trailing walk | measured |")
    lines.append("| `art_outcome` | opportunities.jsonl scanner label (artifact) | measured (identity xref) |")
    lines.append("| `oracle_outcome_replay` | re-simulated `forward_walk(exit_model=intrabar_fixed)` | measured |")
    lines.append("| `JOINT_STATE_SL_TP` | scanner=SL_HIT × oracle=TP_HIT | joint state_id (canonical) |")
    lines.append("| `EARLY_STOP_CANDIDATE` | SAFE_ALIAS for `JOINT_STATE_SL_TP` only | research alias — NOT observation that detector stopped early |")
    lines.append("| `trail_activated` | stop first ratchets from initial SL on trailing walk | measured event |")
    lines.append("| `scanner_exit_before_oracle_tp` | oracle TP and `scanner_exit_bar < oracle_tp_bar` | measured path-timing operationalization of \"stopped earlier\"; **not** trail-causality proof |")
    lines.append("| \"detector stopped early\" | interpretive claim | **INFERENCE** unless exit timestamps prove inequality (rate measured here) |")
    lines.append("")
    lines.append("## Horizon / defaults")
    lines.append("")
    lines.append(f"- `MAX_FORWARD={MAX_FORWARD}` for **both** trailing and fixed exit outcomes (matches anatomy governing layer / scanner `max_forward_candles=40`).")
    lines.append(f"- `trail_mult={TRAIL_MULT}` (scanner default).")
    lines.append("- PEAK_HORIZON=96 is **not** used here (peak timing is out of scope for exit-transition events).")
    lines.append("- Standalone script: `scripts/research/l003h_trail_exit_transition_replay.py` (no `src/` edits).")
    lines.append("")
    lines.append("## Falsification criteria (stated upfront)")
    lines.append("")
    lines.append("1. If `JOINT_STATE_SL_TP` has `trail_activated` rate ≈ `BOTH_SL` (no enrichment) → weakens trail-involvement hypothesis.")
    lines.append("2. If `scanner_exit_before_oracle_tp` is not near-certain in `JOINT_STATE_SL_TP` → weakens \"stopped earlier\" inference.")
    lines.append("3. If `trail_activated` enrichment is large in `JOINT_STATE_SL_TP` vs `BOTH_TP` → supports trail-involvement candidate (still not causation of label mismatch alone).")
    lines.append("")
    lines.append("## A. Population census (replay joint states)")
    lines.append("")
    lines.append(f"n = **{agg['n']:,}** (BNB+BTC+ETH+SOL).")
    lines.append("")
    lines.append("| state_id | n | rate |")
    lines.append("|---|---:|---:|")
    for state, s in sorted(by.items(), key=lambda kv: -kv[1]["n"]):
        lines.append(f"| `{state}` | {s['n']:,} | {pct(s['rate'])} |")
    lines.append("")
    lines.append("### Reconcile vs L-003F (~31.53% JOINT_STATE_SL_TP / EARLY_STOP_CANDIDATE)")
    lines.append("")
    lines.append(f"- Replay `JOINT_STATE_SL_TP` n/rate: **{recon['replay_joint_sl_tp_n']:,}** / {pct(recon['replay_joint_sl_tp_rate'])}")
    lines.append(f"- Artifact×oracle-replay `JOINT_STATE_SL_TP` n/rate: **{recon['artifact_joint_sl_tp_n']:,}** / {pct(recon['artifact_joint_sl_tp_rate'])}")
    lines.append(f"- L-003F expected ESC n/rate: **{L003F_ESC_N:,}** / {pct(L003F_ESC_RATE)}")
    lines.append(f"- Artifact joint vs L-003F rate delta: {recon['artifact_vs_l003f_rate_delta']}")
    lines.append(f"- Scanner label match (art_outcome == scanner_outcome_replay): {pct(recon['scanner_label_match_rate'])}")
    lines.append(f"- Notes: {recon['notes']}")
    lines.append("")
    lines.append("## B. Trail / exit transitions by joint state")
    lines.append("")
    lines.append("| Metric | JOINT_STATE_SL_TP | BOTH_SL | BOTH_TP |")
    lines.append("|---|---:|---:|---:|")
    lines.append(f"| n | {j.get('n', 0):,} | {both_sl.get('n', 0):,} | {both_tp.get('n', 0):,} |")
    lines.append(f"| trail_activated_rate | {pct(j.get('trail_activated_rate'))} | {pct(both_sl.get('trail_activated_rate'))} | {pct(both_tp.get('trail_activated_rate'))} |")
    lines.append(f"| median bars_to_trail_activation | {j.get('median_bars_to_trail_activation')} | {both_sl.get('median_bars_to_trail_activation')} | {both_tp.get('median_bars_to_trail_activation')} |")
    lines.append(f"| trail_exit_rate | {pct(j.get('trail_exit_rate'))} | {pct(both_sl.get('trail_exit_rate'))} | {pct(both_tp.get('trail_exit_rate'))} |")
    lines.append(f"| scanner_exit_before_oracle_tp_rate | {pct(j.get('scanner_exit_before_oracle_tp_rate'))} | {pct(both_sl.get('scanner_exit_before_oracle_tp_rate'))} | {pct(both_tp.get('scanner_exit_before_oracle_tp_rate'))} |")
    seb_otp = (j.get("scanner_exit_before_oracle_tp_among_oracle_tp") or {})
    lines.append(f"| scanner_exit_before_oracle_tp among oracle TP | {pct(seb_otp.get('rate'))} (n_otp={seb_otp.get('n_oracle_tp')}) | — | — |")
    lines.append(f"| median scanner_exit_bar | { (j.get('scanner_exit_bar') or {}).get('median') } | { (both_sl.get('scanner_exit_bar') or {}).get('median') } | { (both_tp.get('scanner_exit_bar') or {}).get('median') } |")
    lines.append(f"| median oracle_exit_bar | { (j.get('oracle_exit_bar') or {}).get('median') } | { (both_sl.get('oracle_exit_bar') or {}).get('median') } | { (both_tp.get('oracle_exit_bar') or {}).get('median') } |")
    lines.append("")
    lines.append("### Exit-bar delta (oracle_exit_bar − scanner_exit_bar) in JOINT_STATE_SL_TP")
    lines.append("")
    d = j.get("exit_bar_delta_oracle_minus_scanner") or {}
    lines.append(f"- median={d.get('median')}, p25={d.get('p25')}, p75={d.get('p75')}, mean={d.get('mean')}")
    lines.append(f"- frac(delta>0)={pct(d.get('frac_positive'))} (positive ⇒ scanner exited earlier than oracle)")
    lines.append("")
    lines.append("## C. Falsification lean")
    lines.append("")
    lines.append(f"**Overall lean:** `{lean['overall_lean']}`")
    lines.append("")
    for item in lean["leans"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Caveats:")
    for c in lean["caveats"]:
        lines.append(f"- {c}")
    lines.append("")
    lines.append("## D. LOIO stability (trail_activated within JOINT_STATE_SL_TP)")
    lines.append("")
    loio = payload["loio_stability"]
    lines.append("| holdout | n_JOINT_STATE_SL_TP | trail_activated_rate |")
    lines.append("|---|---:|---:|")
    for k, v in loio["loio"].items():
        lines.append(f"| {k} | {v['n_joint_sl_tp']:,} | {pct(v['trail_activated_rate'])} |")
    lines.append("")
    lines.append(f"LOIO rate mean={pct(loio.get('loio_rate_mean'))}, std={loio.get('loio_rate_std')}, range={loio.get('loio_rate_range')}.")
    lines.append("")
    lines.append("## E. Per-instrument snapshot")
    lines.append("")
    for inst, pi in payload["per_instrument"].items():
        js = pi["by_joint_state_replay"].get("JOINT_STATE_SL_TP", {})
        lines.append(
            f"- **{inst}** n={pi['n']:,}; JOINT_STATE_SL_TP n={js.get('n', 0):,} ({pct(js.get('rate'))}); "
            f"trail_activated={pct(js.get('trail_activated_rate'))}; "
            f"seb_otp={pct((js.get('scanner_exit_before_oracle_tp_among_oracle_tp') or {}).get('rate'))}"
        )
    lines.append("")
    lines.append("## Flags")
    lines.append("")
    for k, v in payload["flags"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("## Reproducibility")
    lines.append("")
    lines.append(f"- Script: `{payload['reproducibility']['script']}`")
    lines.append(f"- Commit: `{payload['git_commit_sha']}`")
    lines.append(f"- Events (BNB CSV): `{payload['reproducibility'].get('bnb_events_csv')}`")
    lines.append(f"- Runtime_s aggregate: {payload.get('runtime_s')}")
    lines.append("")
    lines.append("## Parent links")
    lines.append("")
    lines.append("- L-003F: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md`")
    lines.append("- L-003G: `docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md`")
    lines.append("")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="L-003H trail/exit transition candle replay")
    ap.add_argument("--instruments", default=",".join(INSTRUMENTS))
    ap.add_argument("--max-forward", type=int, default=MAX_FORWARD)
    ap.add_argument("--progress-every", type=int, default=25000)
    ap.add_argument("--write-bnb-events", action="store_true", default=True)
    ap.add_argument("--no-write-bnb-events", action="store_true")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    generated_at = datetime.now(timezone.utc)
    run_id = args.run_id or f"l003h_trail_exit_transitions_{generated_at.strftime('%Y%m%d_%H%M%S')}"
    # pin commit
    import subprocess

    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT_DIR), text=True).strip()
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=str(ROOT_DIR), text=True
        ).strip()
    except Exception:
        branch = "unknown"

    instruments = [x.strip() for x in args.instruments.split(",") if x.strip()]
    all_rows = []
    per_inst = {}
    skips_all = {}
    runtime = {}
    t_all = time.time()

    for inst in instruments:
        rows, skips, elapsed = process_instrument(
            inst, max_forward=args.max_forward, progress_every=args.progress_every
        )
        all_rows.extend(rows)
        runtime[inst] = elapsed
        skips_all[inst] = skips
        by = summarize_by_joint(rows)
        # artifact joint census
        art_c = Counter(r["joint_state_artifact"] for r in rows)
        label_match = sum(1 for r in rows if r["scanner_label_match_artifact"])
        per_inst[inst] = {
            "n": len(rows),
            "skips": skips,
            "runtime_s": elapsed,
            "by_joint_state_replay": by,
            "joint_state_artifact_counts": dict(art_c),
            "scanner_label_match_rate": _rate(label_match, len(rows)),
            "JOINT_STATE_SL_TP_replay_rate": (by.get("JOINT_STATE_SL_TP") or {}).get("rate"),
        }

    agg_by = summarize_by_joint(all_rows)
    art_c_all = Counter(r["joint_state_artifact"] for r in all_rows)
    label_match_all = sum(1 for r in all_rows if r["scanner_label_match_artifact"])
    j_n = (agg_by.get("JOINT_STATE_SL_TP") or {}).get("n", 0) or 0
    art_j_n = art_c_all.get("JOINT_STATE_SL_TP", 0)
    n_all = len(all_rows)

    reconcile = {
        "l003f_expected_n": L003F_N,
        "l003f_expected_esc_n": L003F_ESC_N,
        "l003f_expected_esc_rate": L003F_ESC_RATE,
        "replay_n": n_all,
        "replay_joint_sl_tp_n": j_n,
        "replay_joint_sl_tp_rate": _rate(j_n, n_all),
        "artifact_joint_sl_tp_n": art_j_n,
        "artifact_joint_sl_tp_rate": _rate(art_j_n, n_all),
        "artifact_vs_l003f_n_delta": art_j_n - L003F_ESC_N,
        "artifact_vs_l003f_rate_delta": (_rate(art_j_n, n_all) or 0) - L003F_ESC_RATE,
        "replay_vs_l003f_rate_delta": (_rate(j_n, n_all) or 0) - L003F_ESC_RATE,
        "scanner_label_match_rate": _rate(label_match_all, n_all),
        "notes": (
            "L-003F used anatomy art_outcome × anatomy oracle outcome; "
            "this pass reconciles artifact scanner labels × re-simulated oracle, "
            "and separately reports fully re-simulated joint states."
        ),
    }

    lean = falsification_lean(agg_by)
    loio = loio_trail_activated_in_joint_sl_tp(
        {inst: {"by_joint_state_replay": per_inst[inst]["by_joint_state_replay"]} for inst in per_inst}
    )

    out_events_dir = ROOT_DIR / "results/research/l003h_trail_exit_transitions"
    out_events_dir.mkdir(parents=True, exist_ok=True)
    bnb_csv = None
    if not args.no_write_bnb_events:
        bnb_rows = [r for r in all_rows if r["instrument"] == "BNBUSDT"]
        bnb_csv = str(out_events_dir / f"{run_id}_BNBUSDT_events.csv")
        write_bnb_events_csv(bnb_rows, Path(bnb_csv))
        print(f"wrote BNB events {bnb_csv} n={len(bnb_rows)}")

    # compact summary JSON (not full 560k)
    summary_path = out_events_dir / f"{run_id}_summary.json"

    payload = {
        "finding_id": "L-003H",
        "version": VERSION,
        "run_id": run_id,
        "generated_at_utc": generated_at.isoformat().replace("+00:00", "Z"),
        "git_commit_sha": sha,
        "branch": branch,
        "status": "MEASURED",
        "doctrine": "Observation → Measurement → Evidence → Promotion",
        "questions_answered": [
            "Does JOINT_STATE_SL_TP show measured trail/exit transition patterns that BOTH_SL / BOTH_TP do not?",
            "What is scanner_exit_before_oracle_tp rate within JOINT_STATE_SL_TP?",
        ],
        "questions_NOT_answered": [
            "Does trail cause label mismatch?",
            "Should scanner be replaced by oracle?",
            "Is EARLY_STOP_CANDIDATE a true early-stop (remains INFERENCE)",
        ],
        "horizon": {
            "max_forward_exit_outcomes": args.max_forward,
            "trail_mult": TRAIL_MULT,
            "peak_horizon_not_used": 96,
            "note": "Exit outcomes use MAX_FORWARD=40 to match governing anatomy/scanner layer; trail uses the same horizon.",
        },
        "flags": {
            "promotion": False,
            "l003_frozen": False,
            "attribution_unblocked": False,
            "economic_claims": False,
            "registry_edits": False,
        },
        "terminology": {
            "JOINT_STATE_SL_TP": "scanner_outcome==SL_HIT & oracle_outcome==TP_HIT",
            "EARLY_STOP_CANDIDATE": "SAFE_ALIAS only for JOINT_STATE_SL_TP",
            "scanner_exit_before_oracle_tp": "measured path-timing operationalization; not trail-causality proof",
            "detector_stopped_early": "INFERENCE unless exit timestamps prove scanner_exit_bar < oracle_tp_bar",
        },
        "aggregate": {
            "n": n_all,
            "by_joint_state_replay": agg_by,
            "joint_state_artifact_counts": dict(art_c_all),
            "scanner_label_match_rate": _rate(label_match_all, n_all),
        },
        "per_instrument": per_inst,
        "reconcile_vs_l003f": reconcile,
        "falsification_lean": lean,
        "loio_stability": loio,
        "skips": skips_all,
        "runtime_s": {"per_instrument": runtime, "total": time.time() - t_all},
        "reproducibility": {
            "script": "scripts/research/l003h_trail_exit_transition_replay.py",
            "bnb_events_csv": bnb_csv,
            "summary_json": str(summary_path.relative_to(ROOT_DIR)).replace("\\", "/"),
            "subsample": None,
        },
        "parent_links": {
            "L-003F": "docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md",
            "L-003G": "docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md",
        },
    }

    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    gov_json = ROOT_DIR / "docs/governance/analytics_trail_exit_transitions_l003h-2026-09-07.json"
    gov_md = ROOT_DIR / "docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md"
    gov_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    gov_md.write_text(render_md(payload), encoding="utf-8")

    # optional impact pointer
    impact = {
        "finding_id": "L-003H",
        "run_id": run_id,
        "version": VERSION,
        "git_commit_sha": sha,
        "pointers": {
            "md": "docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md",
            "json": "docs/governance/analytics_trail_exit_transitions_l003h-2026-09-07.json",
            "script": "scripts/research/l003h_trail_exit_transition_replay.py",
            "parent_L003F": "docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md",
            "parent_L003G": "docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md",
        },
        "headline": {
            "trail_activated_rate_by_joint": {
                "JOINT_STATE_SL_TP": (agg_by.get("JOINT_STATE_SL_TP") or {}).get("trail_activated_rate"),
                "BOTH_SL": (agg_by.get("BOTH_SL") or {}).get("trail_activated_rate"),
                "BOTH_TP": (agg_by.get("BOTH_TP") or {}).get("trail_activated_rate"),
            },
            "scanner_exit_before_oracle_tp_among_oracle_tp_JOINT_STATE_SL_TP": (
                (agg_by.get("JOINT_STATE_SL_TP") or {}).get("scanner_exit_before_oracle_tp_among_oracle_tp") or {}
            ).get("rate"),
            "overall_lean": lean["overall_lean"],
            "reconcile_artifact_joint_sl_tp_rate": reconcile["artifact_joint_sl_tp_rate"],
        },
        "flags": payload["flags"],
    }
    impact_path = ROOT_DIR / "docs/governance/analytics_trail_exit_transitions_l003h_impact-2026-09-07.json"
    impact_path.write_text(json.dumps(impact, indent=2, default=str), encoding="utf-8")

    # append pointer notes into L-003F/G md if not already present
    pointer_line = (
        f"\n## Child measurement (L-003H)\n\n"
        f"- Trail/exit transition candle replay: `docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md` "
        f"(run_id `{run_id}`).\n"
    )
    for parent in [
        ROOT_DIR / "docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md",
        ROOT_DIR / "docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md",
    ]:
        if parent.exists():
            txt = parent.read_text(encoding="utf-8")
            if "ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H" not in txt:
                parent.write_text(txt.rstrip() + "\n" + pointer_line, encoding="utf-8")
                print(f"appended L-003H pointer to {parent.name}")

    print("=" * 60)
    print("run_id", run_id)
    print("n", n_all)
    print("JOINT_STATE_SL_TP trail_activated", (agg_by.get("JOINT_STATE_SL_TP") or {}).get("trail_activated_rate"))
    print("BOTH_SL trail_activated", (agg_by.get("BOTH_SL") or {}).get("trail_activated_rate"))
    print("BOTH_TP trail_activated", (agg_by.get("BOTH_TP") or {}).get("trail_activated_rate"))
    print(
        "seb_otp JOINT_STATE_SL_TP",
        ((agg_by.get("JOINT_STATE_SL_TP") or {}).get("scanner_exit_before_oracle_tp_among_oracle_tp") or {}).get("rate"),
    )
    print("lean", lean["overall_lean"])
    print("wrote", gov_md)
    print("wrote", gov_json)
    print("wrote", impact_path)
    print("total_s", time.time() - t_all)


if __name__ == "__main__":
    main()
