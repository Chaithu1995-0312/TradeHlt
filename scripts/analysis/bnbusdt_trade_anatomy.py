"""bnbusdt_trade_anatomy.py — MEASURE-ONLY trade-anatomy substrate for BNBUSDT.

Sits UNDERNEATH F-019/020/021 and Phase D: it explains *behavior*, it does not optimize it.
No tuning, no edge-search. Recovered-first discipline — everything that already exists in logs is
reused as-is; only the horizon/time fields that NO artifact stores are derived from candle history.

PRIMARY output : results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv  (canonical
                 substrate for survival / clustering / time-decay / MFE-capture / future ML).
SECONDARY      : results/research/bnbusdt_trade_anatomy/anatomy_summary.json  (aggregates → report).

RECOVERED (Priority 1) : timestamp, direction, entry/sl/tp, outcome, rr_achieved, duration_candles,
                         mfe, mae, 38-dim feature vector   ← opportunities.jsonl
                         bitnet_score, pnl_rr_net, costs    ← governed-spine BNBUSDT_trades.csv
DERIVED   (Priority 2) : return_15/30/45/60/90m, time_to_peak, time_to_bottom, horizon-excursion R
                         metrics (reuse research.measurement.horizon_excursion), capture_ratio, giveback.

Cost basis: gross + net, headline NET 12 bps round-trip (0.0012). Net always shrinks toward zero.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import math
import statistics as stats
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config_layer.crt_engine_v2 import Candle               # noqa: E402
from research.contracts import Signal                        # noqa: E402
from research.measurement.forward_walk import forward_walk, horizon_excursion  # noqa: E402

# ── constants ──────────────────────────────────────────────────────────────────
COST_RT = 0.0012                       # 12 bps round-trip, fraction of notional
HORIZON_BARS = {15: 1, 30: 2, 45: 3, 60: 4, 90: 6}   # M15: minutes → bars forward
MAX_FORWARD = 40                       # GOVERNING realized-exit / horizon-excursion cap (held fixed — realized layer byte-stable)
PEAK_HORIZON = 96                      # exit-agnostic peak-timing window (24 h) — de-censors bars_to_peak_path
SURVIVAL_K = [1, 2, 3, 4, 6, 8, 12, 24]
THE_38 = [  # canonical feature order present in opportunities.jsonl features{}
    "open", "high", "low", "close", "volume", "volume_ratio", "double_sweep",
    "ema_fast", "ema_slow", "ema_spread", "trend_bias", "trend_strength", "momentum_score",
    "atr", "volatility_ratio", "rsi_14", "macd_line", "macd_signal", "macd_hist",
    "sweep_detected", "liquidity_sweep", "break_of_structure", "swing_high", "swing_low",
    "higher_high", "lower_low", "body_size", "wick_size", "body_ratio", "volatility_regime",
    "session", "hour_of_day", "disp_strength", "retest_depth", "candles_since_retest",
    "liquidity_distance", "liquidity_pressure_score", "volume_spike",
]
CLUSTER_FEATS = ["ema_spread", "volume_ratio", "volatility_ratio", "body_ratio",
                 "momentum_score", "trend_strength", "disp_strength", "retest_depth", "atr"]


# ── helpers ────────────────────────────────────────────────────────────────────
def _norm_ts(s: str) -> str:
    return s.replace("T", " ").strip()


def _session_from_hour(h: float) -> str:
    """DERIVED session proxy from UTC hour (clearly not the spine's resolver)."""
    h = int(h) % 24
    if h < 7:
        return "ASIA"
    if h < 13:
        return "LONDON"
    if h < 21:
        return "NEWYORK"
    return "OFF"


def _pct(vals, p):
    if not vals:
        return None
    return round(float(stats.quantiles(vals, n=100)[p - 1]) if len(vals) > 1 else vals[0], 6)


def _safe_div(a, b):
    return a / b if b else float("nan")


def load_candles(csv_path: Path):
    """Return (candles list with .index, ts→index dict, close-by-index list)."""
    candles, ts_to_idx, closes = [], {}, []
    with csv_path.open(encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for i, row in enumerate(rd):
            ts = _norm_ts(row["timestamp"])
            c = Candle(
                timestamp=datetime.fromisoformat(ts.replace(" ", "T")),
                open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row.get("volume", 0) or 0), index=i,
            )
            candles.append(c)
            ts_to_idx[ts] = i
            closes.append(c.close)
    return candles, ts_to_idx, closes


def load_spine(run_csv: Path):
    """Governed-spine trades keyed by normalized opened_at (low-N, illustrative-only join)."""
    spine = {}
    cfg = ""
    if not run_csv or not run_csv.exists():
        return spine, cfg
    with run_csv.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cfg = r.get("config_version", cfg)
            spine[_norm_ts(r["opened_at"])] = {
                "bitnet_score": _f(r.get("bitnet_score_at_entry")),
                "pnl_rr_net": _f(r.get("pnl_rr_net")),
                "cost_pips": (_f(r.get("slippage_pips")) or 0) + (_f(r.get("spread_pips")) or 0),
                "exit_reason": r.get("exit_reason", ""),
            }
    return spine, cfg


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pick_spine_run(explicit: str | None, inst: str = "BNBUSDT") -> Path | None:
    if explicit:
        return Path(explicit)
    pats = [f"results/research/{inst.lower()}_authoritative/run_*_{inst}/{inst}_trades.csv",
            f"results/_s0_baseline/_run/run_*_{inst}/{inst}_trades.csv",
            f"results/{inst}/run_*_{inst}/{inst}_trades.csv"]
    for pat in pats:
        hits = sorted(glob.glob(str(ROOT_DIR / pat)))
        if hits:
            return Path(hits[-1])
    return None


# ── core per-opportunity derivation ──────────────────────────────────────────────
def derive_row(opp, candles, ts_to_idx, closes, spine, inst="BNBUSDT"):
    ts = _norm_ts(opp["timestamp"])
    idx = ts_to_idx.get(ts)
    if idx is None:
        return None, "no_candle"
    direction = opp["direction"].lower()
    entry = float(opp["entry"])
    sl = float(opp["sl"])
    tp = float(opp.get("tp", entry))
    risk = abs(entry - sl)
    if risk <= 0:
        return None, "zero_risk"
    feats = opp.get("features", {})

    # RECOVERED artifact fields (UNRELIABLE: outcome/rr internally inconsistent — kept for x-ref only)
    art_rr = _f(opp.get("rr_achieved")) or 0.0
    art_mfe = _f(opp.get("mfe")) or 0.0
    art_mae = _f(opp.get("mae")) or 0.0
    art_outcome = opp.get("outcome", "")
    art_dur = int(opp.get("duration_candles") or 0)
    # consistency flag: an SL_HIT must have adverse excursion reaching the stop (mae <= -risk)
    art_consistent = not (art_outcome == "SL_HIT" and art_mae > -risk)

    # DERIVED — fixed-horizon close returns (price-fraction), gross + net
    rets = {}
    rets_R = {}
    n = len(closes)
    for mins, k in HORIZON_BARS.items():
        j = idx + k
        if j < n:
            cf = closes[j]
            move = (cf - entry) if direction == "long" else (entry - cf)
            rets[mins] = (move / entry, move / entry - COST_RT)      # (gross, net) fraction
            rets_R[mins] = (move / risk, move / risk - COST_RT * entry / risk)  # R gross/net
        else:
            rets[mins] = (float("nan"), float("nan"))
            rets_R[mins] = (float("nan"), float("nan"))

    # DERIVED — GOVERNING realized exit (REUSE forward_walk, intrabar_fixed) — the trusted layer.
    # One 96-bar slice feeds everything; forward_walk/horizon_excursion internally cap at MAX_FORWARD
    # (=40), so the realized layer stays byte-identical while peak-timing observes the full 96 bars.
    future = candles[idx + 1: idx + 1 + PEAK_HORIZON]
    sig = Signal(instrument=inst, timestamp=candles[idx].timestamp, entry_index=idx,
                 direction=direction, entry=entry, sl_atr_mult=1.0,
                 tp_atr_mult=abs(tp - entry) / risk, atr=risk)
    if not future:
        return None, "no_future"
    fw = forward_walk(sig, future, max_forward=MAX_FORWARD, exit_model="intrabar_fixed")
    rr = fw.rr_achieved            # governing realized R
    mfe = fw.mfe                   # governing max favorable excursion (price units)
    mae = fw.mae
    outcome = fw.outcome           # TP_HIT | SL_HIT | TIMEOUT (consistent with geometry)
    dur = fw.duration_candles
    # DERIVED — exit-agnostic R excursion (REUSE primitive, 40-bar cap, unchanged)
    hx = horizon_excursion(sig, future, max_forward=MAX_FORWARD)
    # DERIVED — TWO distinct, never-mixed peak fields (per user):
    #   bars_to_peak_path        = favorable peak over the full PEAK_HORIZON (exit-agnostic; de-censored)
    #   bars_to_peak_within_trade = favorable peak bounded by the realized exit (≤ dur)
    t_peak_path, t_bottom_path, best_fav, worst_adv = None, None, 0.0, 0.0
    t_peak_within, best_fav_within = None, 0.0
    for i, b in enumerate(future):
        fav = (b.high - entry) if direction == "long" else (entry - b.low)
        adv = (b.low - entry) if direction == "long" else (entry - b.high)
        if fav > best_fav:
            best_fav, t_peak_path = fav, i + 1
        if adv < worst_adv:
            worst_adv, t_bottom_path = adv, i + 1
        if i < dur and fav > best_fav_within:        # within the realized trade life only
            best_fav_within, t_peak_within = fav, i + 1

    # DERIVED combine — capture / giveback (governing realized vs governing MFE)
    realized_px = rr * risk
    capture = _safe_div(realized_px, mfe) if mfe > 0 else float("nan")
    giveback = _safe_div(mfe - realized_px, mfe) if mfe > 0 else float("nan")

    dt = candles[idx].timestamp
    row = {
        "timestamp": ts, "entry_index": idx, "direction": direction,
        "entry": entry, "sl": sl, "tp": tp, "risk_distance": risk,
        "outcome": outcome, "win": int(rr > 0), "rr_achieved": rr, "duration_candles": dur,
        "mfe": mfe, "mae": mae,
        "art_outcome": art_outcome, "art_rr": art_rr, "art_mfe": art_mfe, "art_mae": art_mae,
        "art_consistent": int(art_consistent),
        "mfe_r": hx.get("mfe_r"), "mae_r": hx.get("mae_r"),
        "reached_0_5r": int(bool(hx.get("reached_0_5r"))),
        "reached_1r": int(bool(hx.get("reached_1r"))),
        "reached_2r": int(bool(hx.get("reached_2r"))),
        "favorable_first": int(bool(hx.get("favorable_first"))),
        "bars_to_first_1r": hx.get("bars_to_first_1r"),
        "bars_to_peak_path": t_peak_path, "bars_to_peak_within_trade": t_peak_within,
        "time_to_bottom_path": t_bottom_path,
        "capture_ratio": capture, "giveback": giveback,
        "year": dt.year, "month": dt.month, "weekday": dt.weekday(),
        "hour": int(feats.get("hour_of_day", dt.hour)),
        "session_derived": _session_from_hour(feats.get("hour_of_day", dt.hour)),
        "session_code": feats.get("session"),
        "volatility_regime": feats.get("volatility_regime"),
        "trend_bias": feats.get("trend_bias"),
    }
    for mins in HORIZON_BARS:
        row[f"return_{mins}m_gross"] = rets[mins][0]
        row[f"return_{mins}m_net"] = rets[mins][1]
    for f in THE_38:
        row[f"f_{f}"] = feats.get(f)
    # internal-only R returns for hold-time expectancy aggregation
    row["_r"] = {m: rets_R[m] for m in HORIZON_BARS}

    sp = spine.get(ts)
    row["bitnet_score"] = sp["bitnet_score"] if sp else None
    row["spine_pnl_rr_net"] = sp["pnl_rr_net"] if sp else None
    row["spine_cost_pips"] = sp["cost_pips"] if sp else None
    return row, "ok"


# ── aggregation ──────────────────────────────────────────────────────────────────
def aggregate(rows, spine, spine_cfg, spine_run):
    n = len(rows)
    wins = [r for r in rows if r["win"]]
    losers = [r for r in rows if not r["win"]]
    ts_sorted = sorted(r["timestamp"] for r in rows)
    d0 = datetime.fromisoformat(ts_sorted[0].replace(" ", "T"))
    d1 = datetime.fromisoformat(ts_sorted[-1].replace(" ", "T"))
    span_days = max((d1 - d0).days, 1)

    def dist(key):
        out = {}
        for r in rows:
            out[str(r[key])] = out.get(str(r[key]), 0) + 1
        return dict(sorted(out.items()))

    # time decay: P(return>0) gross & net
    decay = {}
    for mins in HORIZON_BARS:
        g = [r[f"return_{mins}m_gross"] for r in rows if not math.isnan(r[f"return_{mins}m_gross"])]
        net = [r[f"return_{mins}m_net"] for r in rows if not math.isnan(r[f"return_{mins}m_net"])]
        decay[mins] = {
            "p_positive_gross": round(sum(x > 0 for x in g) / len(g), 4) if g else None,
            "p_positive_net": round(sum(x > 0 for x in net) / len(net), 4) if net else None,
            "n": len(g),
        }

    # hold-time fixed-exit expectancy (mean R) gross & net
    hold = {}
    for mins in HORIZON_BARS:
        gr = [r["_r"][mins][0] for r in rows if not math.isnan(r["_r"][mins][0])]
        nr = [r["_r"][mins][1] for r in rows if not math.isnan(r["_r"][mins][1])]
        hold[mins] = {
            "mean_R_gross": round(stats.fmean(gr), 4) if gr else None,
            "mean_R_net": round(stats.fmean(nr), 4) if nr else None,
            "n": len(gr),
        }
    best_net = max((m for m in hold if hold[m]["mean_R_net"] is not None),
                   key=lambda m: hold[m]["mean_R_net"], default=None)

    # survival: P(not stopped by bar k)  (stopped = SL_HIT with duration <= k)
    survival = {}
    for k in SURVIVAL_K:
        stopped = sum(1 for r in rows if r["outcome"] == "SL_HIT" and 0 < r["duration_candles"] <= k)
        survival[k] = round(1 - stopped / n, 4)

    # peak-timing distribution — TWO never-mixed fields × winners/losers/all, full percentiles.
    def _peak_pcts(subset, key):
        vals = [r[key] for r in subset if r[key] is not None]
        if not vals:
            return {"n": 0}
        return {"n": len(vals), "p10": _pct(vals, 10), "p25": _pct(vals, 25),
                "p50": round(stats.median(vals), 2), "p75": _pct(vals, 75),
                "p90": _pct(vals, 90), "mean": round(stats.fmean(vals), 2)}
    peak_timing = {}
    for key in ("bars_to_peak_path", "bars_to_peak_within_trade"):
        peak_timing[key] = {"winners": _peak_pcts(wins, key),
                            "losers": _peak_pcts(losers, key),
                            "all": _peak_pcts(rows, key)}
    peak_timing["peak_window_bars"] = PEAK_HORIZON
    peak_timing["censoring_note"] = (
        "bars_to_peak_path observed over PEAK_HORIZON bars (exit-agnostic); "
        "bars_to_peak_within_trade is bounded by the realized exit (≤ duration_candles).")

    # duration vs expectancy buckets (minutes)
    def bucket(durc):
        m = durc * 15
        if m <= 30:
            return "0-30m"
        if m <= 60:
            return "30-60m"
        if m <= 90:
            return "60-90m"
        if m <= 180:
            return "90-180m"
        return "180m+"
    dur_exp = {}
    for b in ["0-30m", "30-60m", "60-90m", "90-180m", "180m+"]:
        sub = [r["rr_achieved"] for r in rows if bucket(r["duration_candles"]) == b]
        dur_exp[b] = {"n": len(sub), "mean_R": round(stats.fmean(sub), 4) if sub else None}

    # capture / giveback
    cap = [r["capture_ratio"] for r in rows if not math.isnan(r["capture_ratio"])]
    gb = [r["giveback"] for r in rows if not math.isnan(r["giveback"])]
    cap_w = [r["capture_ratio"] for r in wins if not math.isnan(r["capture_ratio"])]

    mfe_px = [r["mfe"] for r in rows]
    mae_px = [r["mae"] for r in rows]
    mfe_r = [r["mfe_r"] for r in rows if r["mfe_r"] is not None]
    mae_r = [r["mae_r"] for r in rows if r["mae_r"] is not None]

    summary = {
        "grain": "opportunity (unfiltered detection — NOT tradeable count)",
        "n_opportunities": n,
        "date_range": [ts_sorted[0], ts_sorted[-1]],
        "frequency": {
            "total": n, "span_days": span_days,
            "per_day": round(n / span_days, 3),
            "per_week": round(n / span_days * 7, 2),
            "per_month": round(n / span_days * 30.44, 1),
            "per_year": round(n / span_days * 365.25, 1),
        },
        "splits": {
            "by_year": dist("year"), "by_month": dist("month"),
            "by_weekday": dist("weekday"), "by_hour": dist("hour"),
            "by_session_derived": dist("session_derived"),
            "by_volatility_regime": dist("volatility_regime"),
        },
        "outcome_distribution_governing": dist("outcome"),
        "outcome_distribution_artifact": dist("art_outcome"),
        "artifact_consistency_rate": round(sum(r["art_consistent"] for r in rows) / n, 4),
        "artifact_truth_conflict": (
            "opportunities.jsonl outcome/rr is INTERNALLY INCONSISTENT (SL_HIT rows whose adverse "
            "excursion never reaches the stop). Realized layer is therefore DERIVED via governing "
            "forward_walk(intrabar_fixed); artifact outcome/rr kept only as flagged cross-reference."),
        "win_rate": round(len(wins) / n, 4),
        "mfe_mae": {
            "mfe_price_mean": round(stats.fmean(mfe_px), 5),
            "mae_price_mean": round(stats.fmean(mae_px), 5),
            "mfe_r_median": round(stats.median(mfe_r), 4) if mfe_r else None,
            "mfe_r_p90": _pct(mfe_r, 90), "mae_r_median": round(stats.median(mae_r), 4) if mae_r else None,
        },
        "time_decay_P_positive": decay,
        "survival_P_not_stopped": survival,
        "peak_timing": peak_timing,
        "hold_time_fixed_exit_expectancy_R": hold,
        "best_net_hold_minutes": best_net,
        "duration_vs_expectancy": dur_exp,
        "mfe_capture": {
            "capture_ratio_median_all": round(stats.median(cap), 4) if cap else None,
            "capture_ratio_median_winners": round(stats.median(cap_w), 4) if cap_w else None,
            "giveback_median": round(stats.median(gb), 4) if gb else None,
        },
        "spine_grain": {
            "run": str(spine_run) if spine_run else None,
            "config_version": spine_cfg,
            "n_trades": len(spine),
            "note": "illustrative-only (N too small for clustering)",
        },
    }
    summary["morphology_clusters"] = cluster_morphology(rows)
    return summary


def cluster_morphology(rows):
    """DESCRIPTIVE KMeans (k=4) on standardized features — trade *morphology*, NOT predictive edge."""
    try:
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except Exception as e:  # graceful degrade
        return {"status": f"skipped ({type(e).__name__})"}
    X, keep = [], []
    for r in rows:
        vals = [r.get(f"f_{f}") for f in CLUSTER_FEATS]
        if all(v is not None for v in vals):
            X.append([float(v) for v in vals])
            keep.append(r)
    if len(X) < 100:
        return {"status": "insufficient"}
    Xs = StandardScaler().fit_transform(np.asarray(X))
    km = KMeans(n_clusters=4, random_state=0, n_init=10).fit(Xs)
    out = {"status": "ok", "feats": CLUSTER_FEATS, "k": 4,
           "note": "descriptive morphology only — clusters are NOT edges", "clusters": {}}
    for c in range(4):
        members = [keep[i] for i in range(len(keep)) if km.labels_[i] == c]
        if not members:
            continue
        tp = [m["bars_to_peak_path"] for m in members if m["bars_to_peak_path"]]
        out["clusters"][str(c)] = {
            "n": len(members),
            "win_rate": round(sum(m["win"] for m in members) / len(members), 4),
            "mean_R": round(stats.fmean([m["rr_achieved"] for m in members]), 4),
            "median_bars_to_peak_path": round(stats.median(tp), 2) if tp else None,
            "median_duration": round(stats.median([m["duration_candles"] for m in members]), 1),
            "mean_mfe_r": round(stats.fmean([m["mfe_r"] for m in members if m["mfe_r"] is not None]), 4),
        }
    return out


def write_csv(rows, out_csv: Path):
    cols = [k for k in rows[0] if k != "_r"]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in cols})
    # optional parquet
    try:
        import pandas as pd
        pd.DataFrame([{k: r[k] for k in cols} for r in rows]).to_parquet(
            out_csv.with_suffix(".parquet"))
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="Trade-anatomy substrate (measure-only, any instrument).")
    ap.add_argument("--instrument", default="BNBUSDT", help="e.g. BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT")
    ap.add_argument("--opportunities", default=None, help="default derived from --instrument")
    ap.add_argument("--candles", default=None, help="default data/{INSTRUMENT}_M15.csv")
    ap.add_argument("--spine-run", default=None)
    ap.add_argument("--out-dir", default=None, help="default results/research/{instrument-lower}_trade_anatomy")
    args = ap.parse_args()

    inst = args.instrument
    # BNB keeps its frozen Phase-1 source for byte-identical reproduction; others use the regen run.
    _OPP_DEFAULTS = {"BNBUSDT": "logs/BNBUSDT/20260530_011521/opportunities.jsonl"}
    opp_path = args.opportunities or _OPP_DEFAULTS.get(
        inst, f"logs/{inst}/anatomy_{inst}_20260613/opportunities.jsonl")
    candles_path = args.candles or f"data/{inst}_M15.csv"
    out_dir_rel = args.out_dir or f"results/research/{inst.lower()}_trade_anatomy"

    candles, ts_to_idx, closes = load_candles(ROOT_DIR / candles_path)
    spine_run = pick_spine_run(args.spine_run, inst)
    spine, spine_cfg = load_spine(spine_run)
    print(f"instrument={inst}  candles={len(candles)}  opp={opp_path}  spine_run={spine_run}  spine_trades={len(spine)} cfg={spine_cfg}")

    rows, skips = [], {}
    with (ROOT_DIR / opp_path).open(encoding="utf-8") as fh:
        for ln, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            opp = json.loads(line)
            if opp.get("type") == "run_header":
                continue
            row, status = derive_row(opp, candles, ts_to_idx, closes, spine, inst)
            if row is None:
                skips[status] = skips.get(status, 0) + 1
                continue
            rows.append(row)
            if len(rows) % 20000 == 0:
                print(f"  ... {len(rows)} rows")
    print(f"derived rows={len(rows)}  skips={skips}")

    out_dir = ROOT_DIR / out_dir_rel
    out_csv = out_dir / f"trade_dataset_{inst}.csv"
    had_parquet = write_csv(rows, out_csv)
    summary = aggregate(rows, spine, spine_cfg, spine_run)
    summary["skips"] = skips
    summary["parquet_written"] = had_parquet
    # Canonical-substrate freeze: pin the CSV content hash (deterministic across runs).
    sha = hashlib.sha256(out_csv.read_bytes()).hexdigest()
    summary["dataset_sha256"] = sha
    summary["dataset_rows"] = len(rows)
    (out_dir / "anatomy_summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                                  encoding="utf-8")
    print(f"wrote {out_csv}  (parquet={had_parquet})  sha256={sha}")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
