"""forensics.py — Layer-6 root-cause analysis: WHY a behavior loses under intrabar truth.

Single-instrument, single-behavior forensic replay. For each detected signal it forward-walks
the SAME future bars under both the governing `intrabar_fixed` model and the measure-only
`close_only` optimistic bound, then attributes WHERE expectancy is destroyed (loss-mechanism
ranking, intrabar-damage conversion matrix, clustering, concentration cuts).

EXPLANATION ONLY — no optimization, no new hypotheses, no promotion. `close_only` is a
counterfactual instrument; the governing model remains `intrabar_fixed`. Isolated from the
live spine (reuses CandleLoader + research primitives only).
"""

from __future__ import annotations

import dataclasses
import statistics
from collections import Counter, defaultdict

from research.config import ResearchConfig
from research.costs import CostModel
from research.indicators import sma
from research.measurement.forward_walk import forward_walk, horizon_excursion
from research.provenance import provenance_block
from research.registry import get_hypothesis

FORENSICS_VERSION = "1.1"
_EPS = 1e-9
_TREND_FAST, _TREND_SLOW = 10, 30
_FAST_SLOW_CANDLES = 96   # 1 day of M15: sl_hit_fast (<) vs sl_hit_slow (>=)


# ── collection ───────────────────────────────────────────────────────────────
def collect_records(behavior: str, csv_path: str, instrument: str,
                    cfg: ResearchConfig) -> list[dict]:
    """Detect signals and dual-model forward-walk each → ordered per-trade records."""
    from runtime.backtest_v2 import CandleLoader   # proven loader (allowed primitive)

    hyp = get_hypothesis(behavior)
    cost = CostModel(cfg.round_trip_bps)
    candles = list(CandleLoader(csv_path, instrument).stream())
    for i, c in enumerate(candles):
        c.index = i
    n = len(candles)
    records: list[dict] = []

    for i in range(cfg.warmup, n):
        lo = max(0, i - cfg.window_size + 1)
        window = candles[lo:i + 1]
        for s in hyp.detect(window, {}, {"instrument": instrument}):
            if cfg.apply_signal_defaults:
                s = dataclasses.replace(s, sl_atr_mult=cfg.sl_atr_mult, tp_atr_mult=cfg.tp_atr_mult)
            future = candles[i + 1:i + 1 + cfg.max_forward]
            if not future:
                continue
            ib = forward_walk(s, future, max_forward=cfg.max_forward,
                              trail_mult=cfg.trail_mult, exit_model="intrabar_fixed")
            co = forward_walk(s, future, max_forward=cfg.max_forward,
                              trail_mult=cfg.trail_mult, exit_model="close_only")
            exc = horizon_excursion(s, future, max_forward=cfg.max_forward)
            records.append(_record(behavior, instrument, s, ib, co, cost, window, exc))

    _attach_sequence_state(records)
    return records


def _record(behavior, instrument, s, ib, co, cost: CostModel, window, exc: dict) -> dict:
    risk = s.sl_atr_mult * s.atr
    rr_net_ib = cost.net_rr(ib.rr_achieved, s.entry, risk)
    rr_net_co = cost.net_rr(co.rr_achieved, s.entry, risk)
    ts = s.timestamp
    trend = ((sma(window, _TREND_FAST) - sma(window, _TREND_SLOW)) / s.atr) if s.atr else 0.0
    return {
        "trade_id": f"{instrument}-{behavior}-{s.entry_index}",
        "behavior": behavior,
        "timestamp": ts.isoformat(),
        "hour": ts.hour, "dow": ts.weekday(), "month": ts.strftime("%Y-%m"),
        "direction": s.direction, "entry": s.entry, "atr": s.atr,
        "outcome_intrabar": ib.outcome, "outcome_close_only": co.outcome,
        "rr_gross_intrabar": ib.rr_achieved, "rr_net_intrabar": round(rr_net_ib, 6),
        "rr_gross_close_only": co.rr_achieved, "rr_net_close_only": round(rr_net_co, 6),
        "mfe": ib.mfe, "mae": ib.mae, "duration": ib.duration_candles,
        "reached_1r": ib.reached_1r,
        "damage_rr": round(rr_net_ib - rr_net_co, 6),
        "damage_source": _classify(ib, co, rr_net_ib),
        "trend_proxy": round(trend, 4),
        # ── exit-agnostic opportunity (Layer 2) ──
        "max_favorable_excursion_r": exc["mfe_r"], "max_adverse_excursion_r": exc["mae_r"],
        "reached_0_5r": exc["reached_0_5r"], "reached_1r_horizon": exc["reached_1r"],
        "reached_1_5r": exc["reached_1_5r"], "reached_2r": exc["reached_2r"],
        "reached_3r": exc["reached_3r"], "favorable_first": exc["favorable_first"],
        "bars_to_first_1r": exc["bars_to_first_1r"],
    }


def _classify(ib, co, rr_net_ib: float) -> str:
    """Primary loss mechanism (mutually exclusive, priority order). Winners → 'winner'."""
    if rr_net_ib > 0:
        return "winner"
    if ib.rr_achieved > 0:                                   # gross-positive flipped by cost
        return "cost_drag"
    if co.outcome == "TP_HIT" and ib.outcome == "SL_HIT":    # wick reversed a winner
        # NAMING CAVEAT (2026-07-19, Program 10): despite the name this is NOT the same-bar
        # SL/TP collision population (forward_walk.py:127). It is "intrabar reversed a
        # close_only winner" over an ARBITRARY horizon. Neither set contains the other:
        #   * not sufficient — a bar wicking BOTH levels that closes back inside lands in
        #     `plain_stop_loss` here, because close_only never crosses TP on the close;
        #   * not necessary  — a bar may wick SL while closing high, after which close_only
        #     walks on and closes above TP many bars later (no collision at all).
        # The measured contingency lives in
        # results/research/path/ambiguity_census.json -> overlap_vs_f025_same_bar_conflict.
        # Kept under this name because F-025's registered results reference it (§6.2 rule 4).
        return "same_bar_conflict"
    if ib.outcome == "TIMEOUT":
        return "timeout"
    if ib.outcome == "SL_HIT":
        return "plain_stop_loss"
    return "other"


def _attach_sequence_state(records: list[dict]) -> None:
    prev = None
    win_streak = loss_streak = 0
    for pos, r in enumerate(records):
        r["sequence_position"] = pos
        r["prev_trade_result"] = prev
        r["loss_streak_before"] = loss_streak
        r["win_streak_before"] = win_streak
        if r["rr_net_intrabar"] > 0:
            win_streak += 1; loss_streak = 0; prev = "win"
        else:
            loss_streak += 1; win_streak = 0; prev = "loss"


# ── metric helpers ───────────────────────────────────────────────────────────
def _pf(rrs: list[float]) -> float:
    gw = sum(r for r in rrs if r > 0)
    gl = -sum(r for r in rrs if r < 0)
    if gl > 0:
        return round(gw / gl, 4)
    return float("inf") if gw > 0 else 0.0


def _expectancy_decomposition(records) -> dict:
    net = [r["rr_net_intrabar"] for r in records]
    gross = [r["rr_gross_intrabar"] for r in records]
    n = len(net)
    if n == 0:
        return {"n": 0}
    winners = [r for r in net if r > 0]
    losers = [r for r in net if r <= 0]
    wr = len(winners) / n
    avg_w = statistics.mean(winners) if winners else 0.0
    avg_l = statistics.mean([-r for r in losers]) if losers else 0.0
    e_net = statistics.mean(net)
    e_gross = statistics.mean(gross)
    return {
        "n": n, "win_rate": round(wr, 4),
        "avg_winner_rr": round(avg_w, 4), "avg_loser_rr": round(avg_l, 4),
        "expectancy_net": round(e_net, 6), "expectancy_gross": round(e_gross, 6),
        "cost_drag_rr": round(e_gross - e_net, 6),
        "identity_check": round(wr * avg_w - (1 - wr) * avg_l, 6),   # ≈ expectancy_net
    }


def _intrabar_damage(records) -> dict:
    co = [r["rr_net_close_only"] for r in records]
    ib = [r["rr_net_intrabar"] for r in records]
    matrix = {"winner_to_loser": 0, "winner_to_smaller_winner": 0,
              "unchanged": 0, "loser_to_loser": 0, "other": 0}
    for r in records:
        c, i = r["rr_net_close_only"], r["rr_net_intrabar"]
        if abs(c - i) < _EPS:
            matrix["unchanged"] += 1
        elif c > 0 and i <= 0:
            matrix["winner_to_loser"] += 1
        elif c > 0 and 0 < i < c:
            matrix["winner_to_smaller_winner"] += 1
        elif c <= 0 and i <= 0:
            matrix["loser_to_loser"] += 1
        else:
            matrix["other"] += 1
    worst = sorted(records, key=lambda r: r["damage_rr"])[:50]
    return {
        "conversion_matrix": matrix,
        "pf_close_only": _pf(co), "pf_intrabar": _pf(ib),
        "expectancy_close_only": round(statistics.mean(co), 6) if co else 0.0,
        "expectancy_intrabar": round(statistics.mean(ib), 6) if ib else 0.0,
        "expectancy_delta": round((statistics.mean(ib) - statistics.mean(co)), 6) if ib else 0.0,
        "same_bar_sl_tp_count": sum(
            1 for r in records
            if r["outcome_close_only"] == "TP_HIT" and r["outcome_intrabar"] == "SL_HIT"),
        "worst_50_damage": [
            {"trade_id": r["trade_id"], "timestamp": r["timestamp"],
             "damage_rr": r["damage_rr"], "rr_net_close_only": r["rr_net_close_only"],
             "rr_net_intrabar": r["rr_net_intrabar"], "damage_source": r["damage_source"]}
            for r in worst],
    }


def _loss_mechanisms(records) -> list[dict]:
    losers = [r for r in records if r["rr_net_intrabar"] <= 0]
    n_loss = len(losers)
    total_loss_r = sum(r["rr_net_intrabar"] for r in losers)   # negative
    by = defaultdict(list)
    for r in losers:
        by[r["damage_source"]].append(r["rr_net_intrabar"])
    out = []
    for name, rrs in by.items():
        r_lost = sum(rrs)
        out.append({
            "name": name, "count": len(rrs),
            "count_pct": round(100 * len(rrs) / n_loss, 2) if n_loss else 0.0,
            "r_lost": round(r_lost, 4),
            "r_lost_pct": round(100 * r_lost / total_loss_r, 2) if total_loss_r else 0.0,
            "avg_r_per_trade": round(r_lost / len(rrs), 4),
        })
    out.sort(key=lambda d: d["r_lost_pct"], reverse=True)
    for rank, d in enumerate(out, start=1):
        d["mechanism_rank"] = rank
    return out


def _clusters(records, win: bool) -> dict:
    lengths = Counter()
    run = 0
    longest = 0
    for r in records:
        is_win = r["rr_net_intrabar"] > 0
        if is_win == win:
            run += 1
        else:
            if run:
                lengths["4+" if run >= 4 else str(run)] += 1
            longest = max(longest, run)
            run = 0
    if run:
        lengths["4+" if run >= 4 else str(run)] += 1
        longest = max(longest, run)
    return {"max_consecutive": longest, "cluster_lengths": dict(sorted(lengths.items()))}


def _pctl(xs: list[float], p: float):
    """Nearest-rank percentile (p in [0,100]); None on empty."""
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return round(s[0], 4)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)


def _opp_bundle(records) -> dict:
    """Exit-agnostic opportunity metrics for a subset (the reusable Layer-2 leaf)."""
    n = len(records)
    if n == 0:
        return {"n": 0}
    mfes = [r["max_favorable_excursion_r"] for r in records]
    maes = [r["max_adverse_excursion_r"] for r in records]

    def pct(flag):
        return round(100 * sum(1 for r in records if r[flag]) / n, 2)

    reached_1r = [r for r in records if r["reached_1r_horizon"]]
    caps = [r["rr_net_intrabar"] / r["max_favorable_excursion_r"]
            for r in records if r["max_favorable_excursion_r"] > _EPS]
    btf = [r["bars_to_first_1r"] for r in reached_1r if r["bars_to_first_1r"] is not None]
    return {
        "n": n,
        "pct_reached_0_5r": pct("reached_0_5r"), "pct_reached_1r": pct("reached_1r_horizon"),
        "pct_reached_1_5r": pct("reached_1_5r"), "pct_reached_2r": pct("reached_2r"),
        "pct_reached_3r": pct("reached_3r"),
        "mfe_r_p50": _pctl(mfes, 50), "mfe_r_p90": _pctl(mfes, 90), "mfe_r_p95": _pctl(mfes, 95),
        "mae_r_p50": _pctl(maes, 50),
        "capture_ratio_p50": _pctl(caps, 50), "capture_ratio_p90": _pctl(caps, 90),
        "n_with_opportunity": len(caps),
        "pct_favorable_first": (round(100 * sum(1 for r in reached_1r if r["favorable_first"])
                                      / len(reached_1r), 2) if reached_1r else 0.0),
        "n_reached_1r": len(reached_1r),
        "bars_to_first_1r_p50": _pctl(btf, 50), "bars_to_first_1r_p90": _pctl(btf, 90),
        "bars_to_first_1r_p95": _pctl(btf, 95),
    }


def _opportunity_profile(records) -> dict:
    sl = [r for r in records if r["outcome_intrabar"] == "SL_HIT"]
    return {
        "overall": _opp_bundle(records),
        "by_result": {
            "winner": _opp_bundle([r for r in records if r["rr_net_intrabar"] > 0]),
            "loser": _opp_bundle([r for r in records if r["rr_net_intrabar"] <= 0]),
        },
        "by_exit_reason": {
            "sl_hit": _opp_bundle(sl),
            "tp_hit": _opp_bundle([r for r in records if r["outcome_intrabar"] == "TP_HIT"]),
            "timeout": _opp_bundle([r for r in records if r["outcome_intrabar"] == "TIMEOUT"]),
            "sl_hit_long": _opp_bundle([r for r in sl if r["direction"] == "long"]),
            "sl_hit_short": _opp_bundle([r for r in sl if r["direction"] == "short"]),
            "sl_hit_fast": _opp_bundle([r for r in sl if r["duration"] < _FAST_SLOW_CANDLES]),
            "sl_hit_slow": _opp_bundle([r for r in sl if r["duration"] >= _FAST_SLOW_CANDLES]),
        },
    }


def _bucket_stats(records, key_fn) -> dict:
    groups = defaultdict(list)
    for r in records:
        groups[key_fn(r)].append(r["rr_net_intrabar"])
    return {str(k): {"n": len(v), "expectancy": round(statistics.mean(v), 6), "pf": _pf(v)}
            for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}


def _damage_by(records, key_fn) -> dict:
    groups = defaultdict(list)
    for r in records:
        groups[key_fn(r)].append(r["damage_rr"])
    return {str(k): round(statistics.mean(v), 6)
            for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}


def _atr_quartile_key(records):
    atrs = sorted(r["atr"] for r in records)
    if not atrs:
        return lambda r: "NA"
    q = [atrs[int(len(atrs) * f)] for f in (0.25, 0.5, 0.75)]
    def key(r):
        a = r["atr"]
        return "Q1" if a <= q[0] else "Q2" if a <= q[1] else "Q3" if a <= q[2] else "Q4"
    return key


def aggregate(behavior: str, records: list[dict], cfg: ResearchConfig) -> dict:
    """Build the forensic report for one behavior from its per-trade records."""
    n = len(records)
    net = [r["rr_net_intrabar"] for r in records]
    atr_key = _atr_quartile_key(records)
    return {
        "behavior": behavior,
        # ── PRIMARY (causal) ──
        "expectancy_decomposition": _expectancy_decomposition(records),
        "intrabar_damage": _intrabar_damage(records),
        "loss_mechanisms": _loss_mechanisms(records),
        "opportunity_profile": _opportunity_profile(records),
        "consecutive_loss_clusters": _clusters(records, win=False),
        "consecutive_win_clusters": _clusters(records, win=True),
        "exit_reason_distribution": dict(Counter(r["outcome_intrabar"] for r in records)),
        "trade_stats": {
            "n": n,
            "win_rate": round(sum(1 for r in net if r > 0) / n, 4) if n else 0.0,
            "avg_rr": round(statistics.mean(net), 6) if n else 0.0,
            "median_rr": round(statistics.median(net), 6) if n else 0.0,
            "avg_duration": round(statistics.mean([r["duration"] for r in records]), 2) if n else 0.0,
            "largest_win": round(max(net), 4) if n else 0.0,
            "largest_loss": round(min(net), 4) if n else 0.0,
        },
        "signal_stats": {
            "n": n,
            "long": sum(1 for r in records if r["direction"] == "long"),
            "short": sum(1 for r in records if r["direction"] == "short"),
            "by_month": dict(Counter(r["month"] for r in records)),
            "by_hour": dict(Counter(r["hour"] for r in records)),
            "by_dow": dict(Counter(r["dow"] for r in records)),
        },
        # ── SECONDARY (concentration cuts) ──
        "hour_stats": _bucket_stats(records, lambda r: r["hour"]),
        "day_of_week_stats": _bucket_stats(records, lambda r: r["dow"]),
        "month_stats": _bucket_stats(records, lambda r: r["month"]),
        "duration_stats": _bucket_stats(records, lambda r: r["duration"]),
        "regime_stats": {
            "atr_quartile": _bucket_stats(records, atr_key),
            "trend_proxy": _bucket_stats(
                records, lambda r: "up" if r["trend_proxy"] > 0.1
                else "down" if r["trend_proxy"] < -0.1 else "flat"),
        },
        "damage_by_hour": _damage_by(records, lambda r: r["hour"]),
        "damage_by_day_of_week": _damage_by(records, lambda r: r["dow"]),
        "damage_by_month": _damage_by(records, lambda r: r["month"]),
        "damage_by_atr_percentile": _damage_by(records, atr_key),
    }


def build_report(behaviors: dict[str, list[dict]], cfg: ResearchConfig) -> dict:
    """Top-level forensic report across behaviors, with provenance."""
    rep = {
        "forensics_version": FORENSICS_VERSION,
        "note": "close_only rows are the optimistic MEASURE-ONLY bound; intrabar_fixed governs.",
        **provenance_block(cfg.exit_model, cfg.round_trip_bps),
        "config_sha256": cfg.sha256(),
        "behaviors": {b: aggregate(b, recs, cfg) for b, recs in behaviors.items()},
    }
    return rep
