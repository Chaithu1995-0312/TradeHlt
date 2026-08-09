"""
live_path_replay.py — R2: does the backtest edge survive the LIVE ExecutionPlanner + Ultron path?

The +20.59%/PF backtest headline was produced by the backtest spine, which sizes via
CapitalCurve.position_size() and runs NEITHER ExecutionPlannerV1_2 NOR UltronRiskGate (grep: 0 hits
in runtime/backtest_v2.py). Those are LIVE-ONLY (live_engine_hook.py:768-872). So the backtest number
has never been re-derived through the live decision path. This harness closes that gap (F-010 / R2).

WHAT IS MEASURED (faithful decomposition)
  Because CRT is the sole SL/TP authority on BOTH paths, an executed trade's R outcome (pnl_rr_net) is
  SL/TP- and size-independent. Therefore the live path can only change outcomes two ways:
    (1) SELECTION  — ExecutionPlanner.plan() (intent/UNKNOWN reject + GateIntelligence) or UltronRiskGate
                     checks REJECT a trade the backtest took  → changes R-space metrics (PF/WR/avgR).
    (2) SIZING     — UltronRiskGate Check 7 sizes differently than CapitalCurve              → changes
                     $-space metrics ($ return, $ maxDD). R-space PF is size-invariant.
  We reuse each surviving trade's recorded pnl_rr_net (exact), so no exit re-simulation is needed —
  this is strictly MORE faithful than re-deriving exits.

COVERAGE (the live decision path is the single production path: live_engine_hook.py:768-872)
  ExecutionPlannerV1_2.plan(): feature-validation, intent classification, UNKNOWN reject, GateIntelligence
  accept/reject, intent-specific TTL (synchronous plan→evaluate ⇒ TTL never fires, faithfully — same as
  the live hook). UltronRiskGate.evaluate(): Ch0 persisted kill-switch, Ch1 TTL, Ch2 RR-floor+cost tax,
  Ch2.5 per-symbol duplicate, Ch3 daily-trade-limit, Ch4 daily-loss kill-switch (stateful, persisted),
  Ch5 portfolio-exposure + per-trade-risk cap, Ch6/6b SL-distance floor, Ch7 final sizing.
  UltronRiskGateWrapper: regime pre-scaling of risk_percent (regime not recorded in trades.csv — see
  --regime assumption below). Stateful checks (Ch0/2.5/3/4/5) are covered by threading EVOLVING
  portfolio state trade-to-trade with daily resets and kill-switch persistence honored.

ASSUMPTION (explicit, surfaced in the report)
  regime is not persisted per trade in the backtest. --regime sets the wrapper factor used for every
  trade (default "trend" = 1.0× = no fabricated down-scale, isolating the Ultron-core + selection
  effects). Re-run with --regime neutral for a sizing sensitivity.

TRUST GATE (hard)
  Recomputed backtest metrics (from pnl_rr_net) must reproduce the engine's own approved-trade count;
  and the pass-through control (Ultron disabled + no planner filtering) must reproduce backtest PF
  bit-for-bit. Otherwise the harness is UNTRUSTED → exit non-zero, no gap claim.

MEASURE-ONLY: writes ONLY under results/live_path_replay/. No config edit, no promotion, no global
state mutation (kill-switch state file is redirected under the output dir).
"""
from __future__ import annotations

import argparse
import csv as _csv
import glob
import json
import math
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "src")

from config_layer.production_config import (                    # noqa: E402
    PROD_VERSION,
    get_prod_section,
    load_prod_config_from_registry,
)
from config_layer.config_builder import ConfigBuilder           # noqa: E402
from config_layer.execution_planner import ExecutionPlannerV1_2  # noqa: E402
import core.ultron_risk_gate as _urg                            # noqa: E402
from core.ultron_risk_gate import UltronRiskGate                # noqa: E402
from core.ultron_risk_gate_wrapper import UltronRiskGateWrapper  # noqa: E402
from runtime.backtest_v2 import (                               # noqa: E402
    BacktestConfig,
    BacktestRunner,
    CandleLoader,
)

# 13 hard-required planner feature keys (execution_planner._REQUIRED_FEATURE_KEYS).
_FEATURE_KEYS = (
    "close", "high", "low", "atr", "body_ratio", "disp_strength", "sweep_detected",
    "double_sweep", "retest_depth", "candles_since_retest", "ema_fast", "ema_slow",
    "momentum_score",
)
_OPTIONAL_KEYS = ("volume", "swing_high", "swing_low", "higher_high", "lower_low")


# ─────────────────────────────────────────────────────────────────────────────
# Faithful backtest on the ACTIVE prod config (mirrors execution_planner_replay._run_backtest)
# ─────────────────────────────────────────────────────────────────────────────
def _run_backtest(instrument: str, csv: str, out_dir: Path):
    base = load_prod_config_from_registry(PROD_VERSION, instrument)
    crt = ConfigBuilder.from_existing(instrument, base)
    cfg = BacktestConfig.from_prod_config(instrument=instrument, crt_config=crt)
    loader = CandleLoader(csv, instrument)
    runner = BacktestRunner(cfg, csv_path=csv)
    m = runner.run(loader.stream(), loader.count(), str(out_dir))
    trd = sorted(
        glob.glob(str(out_dir / "**" / f"{instrument}*trades.csv"), recursive=True),
        key=os.path.getmtime, reverse=True,
    )
    if not trd:
        raise SystemExit(f"no trades.csv produced under {out_dir}")
    return Path(trd[0]), m


def _load_trades(path: Path) -> list[dict]:
    rows = list(_csv.DictReader(open(path, encoding="utf-8")))
    rows.sort(key=lambda r: str(r.get("opened_at", "")))
    return rows


def _f(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _direction(row: dict) -> int:
    return 1 if str(row.get("direction", "")).upper() in ("LONG", "BUY", "1") else -1


def _pref(row: dict, runtime_key: str, batch_key: str) -> float:
    """Prefer the RUNTIME value the engine actually consumed (cached_/live_ columns) over the
    post-hoc FeaturePipeline batch column. The live gate sees the runtime vector, so this is the
    faithful source. backtest_v2.py:264 documents live_atr as 'raw price-unit ATR used for SL/TP'."""
    if runtime_key in row and str(row.get(runtime_key, "")).strip() != "":
        v = _f(row, runtime_key)
        if v != 0.0:
            return v
    return _f(row, batch_key)


def _features_from_row(row: dict) -> dict:
    feats = {k: _f(row, k) for k in _FEATURE_KEYS}
    # ── Use the RUNTIME values the engine/gate actually consumed (cached_/live_), not the
    #    post-hoc batch columns. Critically, the plain "atr" column is FeaturePipeline's NORMALISED
    #    atr (~0.001); the gate/CRT use price-unit atr = live_atr (~1.0). Wrong scale → vol_score=0. ──
    feats["atr"] = _pref(row, "live_atr", "atr")
    feats["ema_fast"] = _pref(row, "live_ema_fast", "ema_fast")
    feats["ema_slow"] = _pref(row, "live_ema_slow", "ema_slow")
    feats["retest_depth"] = _pref(row, "cached_retest_depth", "retest_depth")
    feats["body_ratio"] = _pref(row, "cached_body_ratio", "body_ratio")
    feats["disp_strength"] = _pref(row, "cached_disp_strength", "disp_strength")
    # sweep flags are stored as float 0.0/1.0 → planner casts via bool(); preserve truthiness.
    feats["sweep_detected"] = bool(_f(row, "sweep_detected"))
    feats["double_sweep"] = bool(_pref(row, "cached_double_sweep", "double_sweep"))
    feats["candles_since_retest"] = int(_f(row, "candles_since_retest", 99))
    for k in _OPTIONAL_KEYS:
        if k in row:
            feats[k] = _f(row, k)
    # GateIntelligence._liquidity_score needs volume_ma20 for its volume sub-score.
    # trades.csv stores volume_ratio (= volume / volume_ma20, FeaturePipeline:225) but not
    # volume_ma20 itself — reconstruct it so vol_score is faithful (not collapsed to 0).
    vr = _f(row, "volume_ratio")
    if vr > 0:
        feats["volume_ma20"] = _f(row, "volume") / vr
    # NOTE: lowest_low_20/5 + highest_high_20/5 are NOT produced by FeaturePipeline (and are not
    # canonical), so the sweep sub-component of _liquidity_score is 0 on BOTH the live path and
    # here — faithful. This is the only residual gate caveat; it can only make live MORE permissive
    # than this replay (i.e. our reject count is an upper bound).
    return feats


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────
def _r_metrics(rr: list[float]) -> dict:
    n = len(rr)
    if n == 0:
        return {"trades": 0, "win_rate": 0.0, "pf": 0.0, "avg_r": 0.0, "max_dd_r": 0.0}
    wins = [x for x in rr if x > 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(x for x in rr if x < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    # R-space max drawdown on the cumulative-R curve.
    eq, peak, max_dd = 0.0, 0.0, 0.0
    for x in rr:
        eq += x
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    return {
        "trades": n,
        "win_rate": round(len(wins) / n, 4),
        "pf": round(pf, 4) if math.isfinite(pf) else None,
        "avg_r": round(sum(rr) / n, 4),
        "max_dd_r": round(max_dd, 4),
    }


def _dollar_metrics(equity: list[float], initial: float) -> dict:
    if not equity:
        return {"total_return_pct": 0.0, "max_dd_pct": 0.0, "final_balance": round(initial, 2)}
    peak, max_dd_pct = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            max_dd_pct = max(max_dd_pct, (peak - v) / peak * 100.0)
    return {
        "total_return_pct": round((equity[-1] / initial - 1.0) * 100.0, 4),
        "max_dd_pct": round(max_dd_pct, 4),
        "final_balance": round(equity[-1], 2),
    }


def _size_dist(sizes: list[float]) -> dict:
    if not sizes:
        return {"min": 0.0, "median": 0.0, "mean": 0.0, "max": 0.0}
    return {
        "min": round(min(sizes), 4),
        "median": round(statistics.median(sizes), 4),
        "mean": round(statistics.mean(sizes), 4),
        "max": round(max(sizes), 4),
    }


# ── Planner rejection attribution (measure-only) ─────────────────────────────
def _bucket_stats(rr: list[float]) -> dict:
    """Per-population R stats: expectancy + lottery-ticket detectors + profit density."""
    n = len(rr)
    if n == 0:
        return {"count": 0, "mean_r": 0.0, "pct_positive": 0.0, "median_r": 0.0,
                "max_r": 0.0, "min_r": 0.0, "sum_r": 0.0, "sum_positive": 0.0,
                "sum_negative": 0.0, "avg_positive": 0.0, "avg_negative": 0.0}
    pos = [x for x in rr if x > 0]
    neg = [x for x in rr if x < 0]
    return {
        "count": n,
        "mean_r": round(sum(rr) / n, 4),
        "pct_positive": round(len(pos) / n, 4),
        "median_r": round(statistics.median(rr), 4),
        "max_r": round(max(rr), 4),
        "min_r": round(min(rr), 4),
        "sum_r": round(sum(rr), 4),
        "sum_positive": round(sum(pos), 4),                             # alpha forgone (if rejected)
        "sum_negative": round(sum(neg), 4),                             # losses avoided (if rejected)
        "avg_positive": round(sum(pos) / len(pos), 4) if pos else 0.0,   # profit density (winners)
        "avg_negative": round(sum(neg) / len(neg), 4) if neg else 0.0,   # profit density (losers)
    }


def _verdict(s: dict) -> str:
    """Hardened thresholds: Mean AND Median must agree (an outlier-inflated mean ≠ forgone alpha)."""
    if s["count"] == 0:
        return "n/a"
    if s["mean_r"] < 0 and s["median_r"] < 0:
        return "Good (removes garbage)"
    if s["mean_r"] > 0 and s["median_r"] > 0 and s["pct_positive"] > 0.5:
        return "HARMFUL (forgoes alpha)"
    return "Mixed"


# human label per raw reason key
_REASON_LABEL = {
    "accepted": "ACCEPTED",
    "planner_reject_unknown_intent": "UNKNOWN_INTENT",
    "planner_reject_gate": "GATE_REJECT",
    "ultron_rr_too_low_after_costs": "ULTRON_RR",
}


def _attribution(rr_by_reason: dict) -> dict:
    """Build the per-bucket attribution + opportunity-cost ranking from raw reason→rr lists."""
    buckets = {}
    for key, lst in rr_by_reason.items():
        s = _bucket_stats(lst)
        # ACCEPTED is the reference population, not a filter — no Good/Harmful verdict.
        v = "(accepted reference)" if key == "accepted" else _verdict(s)
        buckets[_REASON_LABEL.get(key, key)] = {**s, "verdict": v, "raw_reason": key}
    # opportunity-cost ranking over REJECT buckets only (exclude ACCEPTED), by total forgone R desc
    ranking = sorted(
        ((lbl, b) for lbl, b in buckets.items() if b["raw_reason"] != "accepted"),
        key=lambda kv: kv[1]["sum_r"], reverse=True,
    )
    opp = [{"bucket": lbl, "count": b["count"], "mean_r": b["mean_r"], "sum_r": b["sum_r"],
            "alpha_forgone": b["sum_positive"], "losses_avoided": b["sum_negative"],
            "verdict": b["verdict"]} for lbl, b in ranking]
    return {"buckets": buckets, "opportunity_cost_ranking": opp}


# ── UNKNOWN_INTENT root-cause attribution (measure-only) ─────────────────────
def _mirror_intent(feats: dict, direction: int) -> str:
    """Faithful mirror of ExecutionPlannerV1_2._derive_intent (execution_planner.py:353-371)."""
    sweep = bool(feats.get("sweep_detected", False))
    dsweep = bool(feats.get("double_sweep", False))
    depth = float(feats.get("retest_depth", 0.0))
    csr = int(feats.get("candles_since_retest", 99))
    mom = float(feats.get("momentum_score", 0.0))
    body = float(feats.get("body_ratio", 0.0))
    disp = float(feats.get("disp_strength", 0.0))
    ef = float(feats.get("ema_fast", 0.0))
    es = float(feats.get("ema_slow", 0.0))
    if sweep or dsweep:
        return "LIQ_SWEEP"
    if 0.3 <= depth <= 0.7 and csr <= 5 and mom > 0:
        return "PULLBACK"
    if body > 0.6 and disp > 1.5:
        return "BREAKOUT"
    if (ef > es and direction == -1) or (ef < es and direction == 1):
        return "REVERSAL"
    return "UNKNOWN"


def _unknown_diag(u: dict) -> dict:
    """Classify WHY one trade is UNKNOWN: nearest rule + failing margins + cause bucket."""
    f = u["feats"]
    d = int(u["direction"])
    body = float(f.get("body_ratio", 0.0)); disp = float(f.get("disp_strength", 0.0))
    depth = float(f.get("retest_depth", 0.0)); csr = int(f.get("candles_since_retest", 99))
    mom = float(f.get("momentum_score", 0.0)); atr = float(f.get("atr", 0.0))
    ef = float(f.get("ema_fast", 0.0)); es = float(f.get("ema_slow", 0.0))
    ema_dir = "fast>slow" if ef > es else ("fast<slow" if ef < es else "flat")

    mirrored = _mirror_intent(f, d)
    # BREAKOUT near-miss: BOTH features within relaxed bands (body≥0.5 vs 0.6; disp≥1.2 vs 1.5) but
    # NOT both strictly passing — i.e. one condition passes and the other marginally fails (or both
    # marginally fail). A feature far below its relaxed floor → NOT a near-miss (taxonomy).
    bo_near = (body >= 0.5 and disp >= 1.2) and not (body > 0.6 and disp > 1.5)
    # PULLBACK near-miss: within 0.1 of the depth band, recent-ish, momentum not strongly negative.
    pb_pass = (0.3 <= depth <= 0.7 and csr <= 5 and mom > 0)
    pb_near = (not pb_pass) and (0.2 <= depth <= 0.8) and csr <= 8 and mom > -0.1

    if mirrored != "UNKNOWN":
        cause, nearest = "CLASSIFIER_BUG", mirrored
    elif body == 0.0 or disp == 0.0 or atr == 0.0 or depth == 0.0:
        cause, nearest = "MISSING_FEATURE", "-"
    elif bo_near or pb_near:
        cause, nearest = "THRESHOLDING", ("BREAKOUT" if bo_near else "PULLBACK")
    else:
        cause = "TAXONOMY_GAP"
        d_bo = max(0.0, 0.6 - body) / 0.6 + max(0.0, 1.5 - disp) / 1.5
        d_pb = ((0.0 if 0.3 <= depth <= 0.7 else min(abs(depth - 0.3), abs(depth - 0.7)) / 0.3)
                + max(0, csr - 5) / 5.0 + (0.0 if mom > 0 else min(1.0, abs(mom))))
        d_rev = 0.0 if ((ef > es and d == -1) or (ef < es and d == 1)) else 1.0
        nearest = min([("BREAKOUT", d_bo), ("PULLBACK", d_pb), ("REVERSAL", d_rev)],
                      key=lambda x: x[1])[0]
    return {
        "ts": u["ts"][:16], "rr": round(float(u["rr"]), 3), "nearest": nearest, "cause": cause,
        "body": round(body, 2), "disp": round(disp, 2), "depth": round(depth, 2),
        "csr": csr, "mom": round(mom, 2), "ema": ema_dir, "dir": d,
    }


def _unknown_attribution(unknown_rows: list) -> dict:
    diags = [_unknown_diag(u) for u in unknown_rows]
    agg: dict[str, dict] = {}
    for r in diags:
        a = agg.setdefault(r["cause"], {"count": 0, "sum_r": 0.0})
        a["count"] += 1
        a["sum_r"] = round(a["sum_r"] + r["rr"], 4)
    return {"per_trade": diags, "by_cause": agg}


# ── disp_strength sensitivity sweep (measure-only, in-process monkeypatch) ────
def _make_derive_intent(disp_thresh: float):
    """Faithful copy of ExecutionPlannerV1_2._derive_intent (execution_planner.py:339-371) with the
    BREAKOUT `disp_strength > X` bound parameterized. Everything else identical."""
    def _di(self, features, engine_result):
        direction = int(engine_result.get("direction", engine_result.get("selected_direction", 0)))
        if bool(features.get("sweep_detected", False)) or bool(features.get("double_sweep", False)):
            return "LIQ_SWEEP", "sweep detected"
        depth = float(features.get("retest_depth", 0.0))
        csr = int(features.get("candles_since_retest", 99))
        mom = float(features.get("momentum_score", 0.0))
        if 0.3 <= depth <= 0.7 and csr <= 5 and mom > 0:
            return "PULLBACK", "retest depth within 0.3-0.7, recent, positive momentum"
        body = float(features.get("body_ratio", 0.0))
        disp = float(features.get("disp_strength", 0.0))
        if body > 0.6 and disp > disp_thresh:
            return "BREAKOUT", "strong body and displacement"
        ef = float(features.get("ema_fast", 0.0)); es = float(features.get("ema_slow", 0.0))
        if (ef > es and direction == -1) or (ef < es and direction == 1):
            return "REVERSAL", "counter-trend signal (EMA vs direction)"
        return "UNKNOWN", "no clear pattern"
    return _di


def _disp_sweep(rows, planner_cfg, ultron_cfg, crt_cfg, regime, initial_balance,
                thresholds=(1.5, 1.4, 1.3, 1.2, 1.1)) -> dict:
    """Per disp threshold X, monkeypatch the gate's intent classifier and re-run the full live replay.
    Measures gate-admission economics (CRT SL/TP/R held fixed). Restores the original method."""
    ts_rr = {str(r.get("opened_at", "")): _f(r, "pnl_rr_net") for r in rows}
    orig = ExecutionPlannerV1_2._derive_intent
    rows_out, admitted_by_x = [], {}
    try:
        for x in thresholds:
            ExecutionPlannerV1_2._derive_intent = _make_derive_intent(x)
            live_x = _replay(rows, planner_cfg, ultron_cfg, crt_cfg, regime, initial_balance, control=False)
            admitted_by_x[x] = set(live_x.get("survivor_ts", []))
            rows_out.append({
                "disp_thresh": x,
                "trades": live_x["trades"], "pf": live_x["pf"], "avg_r": live_x["avg_r"],
                "return_pct": live_x["total_return_pct"], "max_dd_pct": live_x["max_dd_pct"],
                "unknown_rejects": live_x["rejects"].get("planner_reject_unknown_intent", 0),
            })
    finally:
        ExecutionPlannerV1_2._derive_intent = orig   # always restore

    base = admitted_by_x.get(thresholds[0], set())
    for r in rows_out:
        new = admitted_by_x[r["disp_thresh"]] - base
        r["new_admitted"] = len(new)
        r["sum_r_new"] = round(sum(ts_rr.get(t, 0.0) for t in new), 4)
        r["r_per_added"] = round(r["sum_r_new"] / r["new_admitted"], 4) if r["new_admitted"] else 0.0
    return {"thresholds": list(thresholds), "rows": rows_out}


# ── FULL-BACKTEST disp sweep: re-run the real backtest per threshold (captures TP1-mult→exit) ──
def _make_crt_intent(disp_thresh: float):
    """Faithful copy of ExecutionEngine._derive_trade_intent (crt_engine_v2.py:1873-1886): lowercase
    intents, fallback 'reversal' (NOT 'unknown'), breakout `disp_strength > X` parameterized."""
    def _di(features, disp_threshold=1.5):  # accept the new 2nd arg; closure `disp_thresh` wins
        if features.get("sweep_detected") or features.get("double_sweep"):
            return "liq_sweep"
        rd = float(features.get("retest_depth", 0.0))
        csr = int(features.get("candles_since_retest", 99))
        mom = float(features.get("momentum_score", 0.0))
        if 0.3 <= rd <= 0.7 and csr <= 5 and mom > 0:
            return "pullback"
        body = float(features.get("body_ratio", 0.0))
        disp = float(features.get("disp_strength", 0.0))
        if body > 0.6 and disp > disp_thresh:
            return "breakout"
        return "reversal"
    return _di


def _backtest_book(trades_csv: Path, initial_balance: float) -> dict:
    """Full backtest-book metrics from a fresh trades.csv (the 35-trade spine, not the live subset)."""
    import collections
    rows = _load_trades(trades_csv)
    rr = [_f(r, "pnl_rr_net") for r in rows]
    eq = [_f(r, "capital_after") for r in rows]
    ib = _f(rows[0], "capital_before", initial_balance) if rows else initial_balance
    exits = dict(collections.Counter(str(r.get("exit_reason", "?")) for r in rows))
    return {**_r_metrics(rr), **_dollar_metrics(eq, ib), "exit_dist": exits, "_rows": rows, "_ib": ib}


def _disp_sweep_full(instrument, csv, out, planner_cfg, ultron_cfg, crt_cfg, regime, initial_balance,
                     thresholds=(1.5, 1.4, 1.3, 1.2, 1.1)) -> dict:
    """Per X: monkeypatch BOTH intent classifiers to breakout disp>X, re-run a FRESH backtest (rebuilds
    TP1 mults/exits), then live-gate it. Captures the TP1-mult→exit blast radius the replay reused away.
    Restores both methods via try/finally."""
    from config_layer.crt_engine_v2 import ExecutionEngine
    orig_crt = ExecutionEngine._derive_trade_intent
    orig_plan = ExecutionPlannerV1_2._derive_intent
    rows_out = []
    try:
        for x in thresholds:
            ExecutionEngine._derive_trade_intent = staticmethod(_make_crt_intent(x))
            ExecutionPlannerV1_2._derive_intent = _make_derive_intent(x)
            tcsv, _m = _run_backtest(instrument, csv, out / "_sweep_full" / f"x{x:.2f}")
            book = _backtest_book(tcsv, initial_balance)
            brows, ib = book.pop("_rows"), book.pop("_ib")
            live_x = _replay(brows, planner_cfg, ultron_cfg, crt_cfg, regime, ib, control=False)
            rows_out.append({
                "disp_thresh": x,
                "backtest": {k: book[k] for k in ("trades", "pf", "avg_r", "total_return_pct",
                                                  "max_dd_pct", "exit_dist")},
                "live": {"trades": live_x["trades"], "pf": live_x["pf"],
                         "return_pct": live_x["total_return_pct"], "max_dd_pct": live_x["max_dd_pct"],
                         "avg_r": live_x["avg_r"]},
            })
    finally:
        ExecutionEngine._derive_trade_intent = orig_crt
        ExecutionPlannerV1_2._derive_intent = orig_plan
    return {"thresholds": list(thresholds), "rows": rows_out}


# ─────────────────────────────────────────────────────────────────────────────
# Live-path replay
# ─────────────────────────────────────────────────────────────────────────────
def _planned_rr(intent: str, crt_cfg: dict, planner_cfg: dict) -> float:
    """Blended planned RR handed to Ultron — mirrors live_engine_hook.py:799 fix exactly:
    partial scale-out → ptf*tp1_mult + (1-ptf)*tp2_mult ; else full TP2 target."""
    i = str(intent or "UNKNOWN").lower()
    tp1m = float(crt_cfg.get(f"tp1_atr_multiplier_{i}", crt_cfg.get("tp1_atr_multiplier", 1.0)))
    tp2m = float(crt_cfg.get("tp2_atr_multiplier", 2.0))
    ptf = float(planner_cfg.get("partial_tp_fraction", 0.5))
    partial_on = bool(planner_cfg.get("partial_tp_breakeven_enabled", False))
    return (ptf * tp1m + (1.0 - ptf) * tp2m) if partial_on else tp2m


def _replay(rows, planner_cfg, ultron_cfg, crt_cfg, regime, initial_balance, *, control=False):
    """Run every backtest trade through the real plan()+evaluate() path, threading portfolio state.

    control=True → pass-through (Ultron disabled, planner filtering ignored): used by the trust gate
    to confirm survivors == all backtest trades and PF == backtest PF.
    """
    gate = UltronRiskGate({**ultron_cfg, "disabled": True} if control else ultron_cfg)
    gate.reset_kill_switch()  # clean run (state file already redirected under output dir)
    wrapper = UltronRiskGateWrapper(gate, regime_factors=ultron_cfg.get("regime_factors"))
    planner = ExecutionPlannerV1_2(planner_cfg)
    risk_percent = float(planner_cfg.get("risk_percent", 0.5))

    balance = initial_balance
    equity = []
    survivor_rr, sizes, survivor_ts = [], [], []
    rejects: dict[str, int] = {}
    rr_by_reason: dict[str, list[float]] = {}   # reason -> realized pnl_rr_net (planner attribution)
    unknown_rows: list[dict] = []               # UNKNOWN_INTENT trades for root-cause attribution
    cur_day, trades_today, day_start_balance, day_loss = None, 0, balance, 0.0

    def bump(reason: str, rr: float):
        rejects[reason] = rejects.get(reason, 0) + 1
        rr_by_reason.setdefault(reason, []).append(rr)

    for row in rows:
        day = str(row.get("opened_at", ""))[:10]
        if day != cur_day:                       # daily reset (mirrors _daily_reset_tracker)
            cur_day, trades_today, day_start_balance, day_loss = day, 0, balance, 0.0

        feats = _features_from_row(row)
        direction = _direction(row)
        engine_result = {
            "decision": "execute",
            "direction": direction,
            "confidence": _f(row, "risk_score"),
            "regime": regime,
        }
        context = {
            "symbol": str(row.get("instrument", "UNKNOWN")),
            "signal": direction,
            "score": _f(row, "risk_score"),
            "account_balance": balance,
        }

        if not control:
            plan = planner.plan(engine_result, feats, context)
            if plan.get("decision") != "execute":
                bump("planner_" + str(plan.get("decision")), _f(row, "pnl_rr_net"))
                if plan.get("decision") == "reject_unknown_intent":
                    unknown_rows.append({"ts": str(row.get("opened_at", "")),
                                         "rr": _f(row, "pnl_rr_net"),
                                         "feats": feats, "direction": direction})
                continue
        else:
            plan = {"decision": "execute", "execution_id": row.get("trade_id", "X"),
                    "trade_intent": "UNKNOWN", "direction": direction,
                    "entry_price": _f(row, "entry_fill"), "symbol": context["symbol"]}

        entry = _f(row, "entry_fill")
        sl = _f(row, "sl")
        risk_dist = abs(entry - sl)
        plan["entry_price"] = entry
        plan["stop_loss"] = sl
        plan["take_profit_1"] = _f(row, "tp1")
        plan["take_profit_2"] = _f(row, "tp2")
        plan["rr_ratio"] = _planned_rr(plan.get("trade_intent"), crt_cfg, planner_cfg)  # mirrors live hook :799
        plan["risk_percent"] = risk_percent
        plan["symbol"] = context["symbol"]
        plan["position_size_hint"] = (
            (balance * risk_percent / 100.0) / risk_dist if risk_dist > 0 else None
        )

        portfolio_state = {
            "account_balance": balance,
            "total_open_risk_pct": 0.0,           # backtest is sequential → flat at each entry
            "trades_today": trades_today,
            "daily_loss_pct": day_loss,
            "open_positions": 0,
            "positions": {},
        }
        res = wrapper.evaluate(plan, portfolio_state, regime=regime)
        if res.get("decision") != "approve":
            bump("ultron_" + str(res.get("risk_reason")), _f(row, "pnl_rr_net"))
            continue

        # survivor — reuse the recorded (exact) R outcome; size via Ultron.
        rr = _f(row, "pnl_rr_net")
        allowed = float(res.get("allowed_risk_pct", risk_percent))
        risk_usd = balance * (allowed / 100.0)
        pnl = rr * risk_usd
        balance += pnl
        trades_today += 1
        if pnl < 0 and day_start_balance > 0:
            day_loss += (-pnl / day_start_balance) * 100.0
        survivor_rr.append(rr)
        rr_by_reason.setdefault("accepted", []).append(rr)
        sizes.append(float(res.get("final_position_size", 0.0)))
        survivor_ts.append(str(row.get("opened_at", "")))
        equity.append(balance)

    gate.reset_kill_switch()
    out = {**_r_metrics(survivor_rr), **_dollar_metrics(equity, initial_balance),
           "position_size_dist": _size_dist(sizes), "rejects": rejects,
           "rr_by_reason": rr_by_reason, "unknown_rows": unknown_rows,
           "survivor_ts": survivor_ts}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None, help="default data/<INSTR>_M15.csv")
    ap.add_argument("--output-dir", default="results/live_path_replay")
    ap.add_argument("--regime", default="trend",
                    choices=["trend", "range", "neutral", "uncertain"],
                    help="wrapper regime factor (regime not recorded per trade) — see ASSUMPTION")
    ap.add_argument("--disp-sweep", action="store_true",
                    help="run the BREAKOUT disp_strength sensitivity sweep (gate-admission, CRT reused)")
    ap.add_argument("--disp-sweep-full", action="store_true",
                    help="full-backtest disp sweep: re-run backtest per threshold (captures TP1->exit)")
    args = ap.parse_args(argv)

    instrument = args.instrument
    csv = args.csv or f"data/{instrument}_M15.csv"
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    # Redirect kill-switch persistence under the output dir (measure-only side-effect isolation).
    _urg._KS_STATE_PATH = out / "_ks_state.json"

    planner_cfg = {**get_prod_section("execution_planner")}
    try:
        planner_cfg.update(get_prod_section("gate_intelligence"))  # live hook merges these (:752)
    except (RuntimeError, KeyError):
        pass
    ultron_cfg = dict(get_prod_section("ultron_risk_gate"))
    crt_cfg = dict(get_prod_section("crt_engine"))  # tp1/tp2 multipliers for the planned-RR mirror

    # 1) faithful backtest on ACTIVE config
    trades_csv, metrics = _run_backtest(instrument, csv, out / "_run")
    rows = _load_trades(trades_csv)
    if not rows:
        raise SystemExit("no executed trades in backtest — cannot measure live path")

    initial_balance = _f(rows[0], "capital_before", 100000.0)
    bt_rr = [_f(r, "pnl_rr_net") for r in rows]
    bt_equity = [_f(r, "capital_after") for r in rows]
    backtest = {**_r_metrics(bt_rr), **_dollar_metrics(bt_equity, initial_balance),
                "position_size_dist": _size_dist([_f(r, "position_size") for r in rows])}

    # 2) TRUST GATE
    approved = int(getattr(metrics, "approved_trades", len(rows)))
    control = _replay(rows, planner_cfg, ultron_cfg, crt_cfg, args.regime, initial_balance, control=True)
    count_ok = (backtest["trades"] == approved == len(rows))
    pf_ok = (control["pf"] == backtest["pf"] and control["trades"] == backtest["trades"])
    trust_ok = count_ok and pf_ok

    # 3) LIVE PATH
    live = _replay(rows, planner_cfg, ultron_cfg, crt_cfg, args.regime, initial_balance, control=False)

    # 4) PLANNER REJECTION ATTRIBUTION (measure-only) — accepted vs rejected expectancy by reason
    attribution = _attribution(live.get("rr_by_reason", {}))
    # 5) UNKNOWN_INTENT ROOT-CAUSE ATTRIBUTION (measure-only) — why each UNKNOWN trade fell through
    unknown_attr = _unknown_attribution(live.get("unknown_rows", []))
    # 6) disp_strength SENSITIVITY SWEEP (measure-only) — only when requested
    disp_sweep = _disp_sweep(rows, planner_cfg, ultron_cfg, crt_cfg, args.regime,
                             initial_balance) if args.disp_sweep else None
    # 7) FULL-BACKTEST disp sweep (measure-only) — re-runs the real backtest per threshold
    disp_sweep_full = _disp_sweep_full(instrument, csv, out, planner_cfg, ultron_cfg, crt_cfg,
                                       args.regime, initial_balance) if args.disp_sweep_full else None

    rejected_total = sum(live["rejects"].values())
    payload = {
        "prod_version": PROD_VERSION,
        "instrument": instrument,
        "regime_assumption": args.regime,
        "initial_balance": initial_balance,
        "trust_gate": {
            "backtest_trades_eq_engine_approved": count_ok,
            "control_pf_reproduces_backtest": pf_ok,
            "trustworthy": trust_ok,
        },
        "backtest": backtest,
        "live_path": live,
        "planner_attribution": attribution,
        "unknown_intent_attribution": unknown_attr,
        "disp_sweep": disp_sweep,
        "disp_sweep_full": disp_sweep_full,
        "gap": {
            "trades_delta": live["trades"] - backtest["trades"],
            "rejected_by_live_path": rejected_total,
            "pf_backtest": backtest["pf"],
            "pf_live_path": live["pf"],
            "return_pct_backtest": backtest["total_return_pct"],
            "return_pct_live_path": live["total_return_pct"],
            "max_dd_pct_backtest": backtest["max_dd_pct"],
            "max_dd_pct_live_path": live["max_dd_pct"],
        },
    }
    (out / f"{instrument.lower()}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ── Acceptance-Contract table ────────────────────────────────────────────
    def g(d, k):
        return d.get(k)
    print(f"=== Live-Path Replay — {instrument} ({PROD_VERSION}) — regime={args.regime} ===")
    print(f"  TRUST GATE: count_ok={count_ok} pf_ok={pf_ok} -> {'OK' if trust_ok else 'FAIL'}")
    print(f"  {'Metric':<26}{'Backtest':>14}{'Live Replay':>14}")
    rsel = live["rejects"]
    def rc(*keys):
        return sum(rsel.get(k, 0) for k in keys)
    rows_out = [
        ("Trades", backtest["trades"], live["trades"]),
        ("Win Rate", backtest["win_rate"], live["win_rate"]),
        ("PF", backtest["pf"], live["pf"]),
        ("Avg R", backtest["avg_r"], live["avg_r"]),
        ("Max DD (R)", backtest["max_dd_r"], live["max_dd_r"]),
        ("Total Return %", backtest["total_return_pct"], live["total_return_pct"]),
        ("Max DD %", backtest["max_dd_pct"], live["max_dd_pct"]),
        ("Pos Size (median)", backtest["position_size_dist"]["median"], live["position_size_dist"]["median"]),
        ("Planner Rejects", 0, sum(v for k, v in rsel.items() if k.startswith("planner_"))),
        ("Ultron Rejects", 0, sum(v for k, v in rsel.items() if k.startswith("ultron_"))),
        ("TTL Expiry Count", 0, rc("ultron_expired_signal", "ultron_malformed_expires_at")),
        ("Daily Limit Rejects", 0, rc("ultron_daily_limit")),
        ("Exposure Cap Rejects", 0, rc("ultron_over_exposure")),
        ("Kill-switch Rejects", 0, rc("ultron_kill_switch", "ultron_kill_switch_active")),
        ("RR-floor Rejects", 0, rc("ultron_rr_too_low_after_costs")),
    ]
    for name, b, l in rows_out:
        print(f"  {name:<26}{str(b):>14}{str(l):>14}")
    if rsel:
        print(f"  reject breakdown: {json.dumps(rsel)}")

    # ── Planner Rejection Attribution ────────────────────────────────────────
    print("\n  --- PLANNER REJECTION ATTRIBUTION (realized backtest R per decision) ---")
    print(f"  {'Bucket':<16}{'N':>4}{'MeanR':>8}{'MedR':>8}{'%Pos':>7}{'MaxR':>8}{'SumR':>8}"
          f"{'avg+':>7}{'avg-':>7}  Verdict")
    order = ["ACCEPTED", "UNKNOWN_INTENT", "GATE_REJECT", "ULTRON_RR"]
    bks = attribution["buckets"]
    for lbl in order + [k for k in bks if k not in order]:
        if lbl not in bks:
            continue
        b = bks[lbl]
        print(f"  {lbl:<16}{b['count']:>4}{b['mean_r']:>8.3f}{b['median_r']:>8.3f}"
              f"{b['pct_positive']*100:>6.0f}%{b['max_r']:>8.3f}{b['sum_r']:>8.3f}"
              f"{b['avg_positive']:>7.2f}{b['avg_negative']:>7.2f}  {b['verdict']}")
    print("  opportunity-cost ranking (reject buckets, by total forgone R):")
    for o in attribution["opportunity_cost_ranking"]:
        print(f"    {o['bucket']:<16} N={o['count']:<3} sumR={o['sum_r']:+.3f} "
              f"(alpha_forgone={o['alpha_forgone']:+.3f} / losses_avoided={o['losses_avoided']:+.3f})"
              f" -> {o['verdict']}")
    print("  SAMPLE-SIZE CAVEAT: 35 trades total -> buckets are tiny; single-digit verdicts are "
          "DIRECTIONAL, not conclusive.")

    # ── UNKNOWN_INTENT root-cause attribution ────────────────────────────────
    print("\n  --- UNKNOWN_INTENT ROOT-CAUSE ATTRIBUTION (why each fell through _derive_intent) ---")
    print(f"  {'ts':<17}{'R':>7}{'nearest':>11}{'body':>6}{'disp':>6}{'depth':>7}{'csr':>5}"
          f"{'mom':>7}{'ema':>10}{'dir':>4}  cause")
    for r in unknown_attr["per_trade"]:
        print(f"  {r['ts']:<17}{r['rr']:>7.3f}{r['nearest']:>11}{r['body']:>6.2f}{r['disp']:>6.2f}"
              f"{r['depth']:>7.2f}{r['csr']:>5}{r['mom']:>7.2f}{r['ema']:>10}{r['dir']:>4}  {r['cause']}")
    print("  by cause (rank by Sum R, not count):")
    for cause, a in sorted(unknown_attr["by_cause"].items(), key=lambda kv: kv[1]["sum_r"], reverse=True):
        print(f"    {cause:<16} count={a['count']:<3} sumR={a['sum_r']:+.3f}")

    # ── disp_strength sensitivity sweep ──────────────────────────────────────
    if disp_sweep is not None:
        print("\n  --- disp_strength SENSITIVITY SWEEP (gate-admission; CRT SL/TP/R held fixed) ---")
        print(f"  {'disp>':>6}{'trades':>8}{'new':>5}{'sumR_new':>10}{'R/added':>9}"
              f"{'unk_rej':>9}{'PF':>7}{'ret%':>8}{'maxDD%':>8}{'avgR':>7}")
        for r in disp_sweep["rows"]:
            print(f"  {r['disp_thresh']:>6.2f}{r['trades']:>8}{r['new_admitted']:>5}"
                  f"{r['sum_r_new']:>+10.3f}{r['r_per_added']:>+9.3f}{r['unknown_rejects']:>9}"
                  f"{(r['pf'] if r['pf'] is not None else 0):>7.3f}{r['return_pct']:>8.3f}"
                  f"{r['max_dd_pct']:>8.3f}{r['avg_r']:>7.3f}")
        print("  NOTE: gate-admission scope (CRT levels reused); disp is the REJECTING feature - flat "
              "R/added across X => acting as a gate, not a predictive signal. N=13, directional.")

    # ── full-backtest disp sweep (CRT intent -> TP1 mult -> exits rebuilt) ────
    if disp_sweep_full is not None:
        print("\n  --- FULL-BACKTEST disp_strength SWEEP (CRT intent->TP1->exits rebuilt per X) ---")
        print(f"  {'disp>':>6} | BACKTEST: {'tr':>3}{'PF':>7}{'ret%':>8}{'DD%':>7}{'avgR':>7}  exits"
              f"   || LIVE: {'tr':>3}{'PF':>7}{'ret%':>8}{'DD%':>7}")
        for r in disp_sweep_full["rows"]:
            b, l = r["backtest"], r["live"]
            bpf = b["pf"] if b["pf"] is not None else 0.0
            lpf = l["pf"] if l["pf"] is not None else 0.0
            print(f"  {r['disp_thresh']:>6.2f} | {b['trades']:>13}{bpf:>7.3f}{b['total_return_pct']:>8.3f}"
                  f"{b['max_dd_pct']:>7.3f}{b['avg_r']:>7.3f}  {b['exit_dist']}"
                  f"   || {l['trades']:>9}{lpf:>7.3f}{l['return_pct']:>8.3f}{l['max_dd_pct']:>7.3f}")
        print("  Self-consistency: X=1.5 BACKTEST should be 35/+20.59/PF2.54; LIVE should be 12/+4.87/PF3.35.")
    print(f"  wrote {out / (instrument.lower() + '.json')}")
    return 0 if trust_ok else 2


if __name__ == "__main__":
    sys.exit(main())
