"""Second-low algorithm (userinvestigation/second_low_monitor.jsonl, turns 1-22).

Research tool, no order is ever sent. Results carry economic_claims_allowed = false.

Steps (turn 22, user accepted the recommendation in turn 23):
  1 level    second_low_20d = second-smallest daily low of the previous 20 trading days
             (research.secondlow_v1.detector.compute_trading_day_second_low).
  2 trigger  bar low < level; one trigger per approach (re-armed after a close >= level),
             triggers >= 120 min apart (detector._detect_raw_purge_mask / _independent_indices).
  3 order    long. entry = trigger bar close (decision 1a). sl/tp1/tp2 =
             core.gate_intelligence.compute_crt_levels(entry, 1, low, high, atr_abs, 0.2, 1.0, 2.0),
             atr_abs = FeaturePipeline atr * close (F-072 price units).
  4 pnl      research.oracle.multi_tp_walk defaults (partial 0.5, half-way trail, production
             tie-break), max_forward = every bar left (no 40-bar cap).
  5 row      level, order prices, 48-feature schema on the trigger bar, rr_gross, exit_kind.
  6 path     full-position mark at each later open/close until exit; first -0.25R, then
             +0.25R, then -0.25R anchors.
  7 timeframe M15 / H1 / H4 bars (research.resample.resample); the level is daily, so equal.
  8 learn    PRE-DECLARED before any result was read:
               a. timeframe = highest mean rr_gross among timeframes with n >= 20 (tie -> lower TF)
               b. on that timeframe, six candidate conditions on the three named slots:
                    fvg_distance != 0 | fvg_distance == 0
                    pdl_distance < 0  | pdl_distance >= 0
                    liquidity_sweep == -1 | liquidity_sweep != -1
                  pick the highest mean rr_gross with n >= 10, only if it beats the timeframe's
                  all-trade mean; otherwise no filter.
  9 live     `live` subcommand: MT5 history -> same steps -> candidate rows for triggers on or
             after --forward-start, with the frozen timeframe + filter, walked on bars so far.
             Real-time (2026-10-07): the live path also emits the trailing HTF bar when it is
             already closed (`_closed_tail`), so a bar that just closed is evaluated at once, not
             one bar later. `backtest` is unchanged (include_closed_tail=False).

Usage
  python second_low_algo.py backtest --csv A.csv [--csv B.csv] --out-dir DIR
  python second_low_algo.py live --rule DIR/rule_frozen.json --forward-start 2026-10-07 --out-dir DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from config_layer.crt_engine_v2 import Candle  # noqa: E402
from config_layer.production_config import get_prod_section  # noqa: E402
from core.gate_intelligence import compute_crt_levels  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURE_ORDER  # noqa: E402
from research.oracle.multi_tp_walk import multi_tp_walk  # noqa: E402
from research.resample import bucket_floor, resample  # noqa: E402
from research.secondlow_v1.detector import (  # noqa: E402
    _detect_raw_purge_mask,
    _independent_indices,
    compute_trading_day_second_low,
)

TIMEFRAMES = ("M15", "H1", "H4")
SL_BUFFER, TP1_MULT, TP2_MULT = 0.2, 1.0, 2.0   # active-config compute_crt_levels base
MARK = 0.25
MIN_N_TF, MIN_N_COND = 20, 10
CONDITIONS = {
    "fvg_active": lambda r: r["fvg_distance"] != 0,
    "fvg_none": lambda r: r["fvg_distance"] == 0,
    "below_pdl": lambda r: r["pdl_distance"] < 0,
    "at_or_above_pdl": lambda r: r["pdl_distance"] >= 0,
    "sellside_sweep": lambda r: r["liquidity_sweep"] == -1,
    "no_sellside_sweep": lambda r: r["liquidity_sweep"] != -1,
}


def load_csvs(paths: list[str]) -> pd.DataFrame:
    frames = [pd.read_csv(p, parse_dates=["timestamp"]) for p in paths]
    df = frames[0]
    for f in frames[1:]:
        df = pd.concat([df, f[f.timestamp > df.timestamp.iloc[-1]]], ignore_index=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def to_candles(df: pd.DataFrame) -> list[Candle]:
    return [Candle(timestamp=t.to_pydatetime(), open=float(o), high=float(h), low=float(l),
                   close=float(c), volume=float(v), index=i)
            for i, (t, o, h, l, c, v) in enumerate(df[["timestamp", "open", "high", "low", "close", "volume"]]
                                                    .itertuples(index=False))]


def _closed_tail(candles: list[Candle], tf: str) -> list[Candle]:
    """The trailing HTF bucket, if it is already fully closed (live path only).

    `resample` drops the trailing bucket until a child of the NEXT bucket arrives, and the live
    fetch drops the forming M15 bar -- so 10 min after an H4 close the just-closed H4 bar is
    withheld and live reads one bar (4h) stale. A trailing bucket is closed exactly when the next
    M15 slot would floor into a different bucket; then the canonical `resample` is reused (via a
    sentinel child of the next bucket) so the aggregation is not re-implemented. A bucket cut
    short by a weekend/holiday never meets this test and stays withheld, as in `resample`."""
    last = candles[-1]
    start = bucket_floor(last.timestamp, tf)
    nxt = last.timestamp + timedelta(minutes=15)
    if bucket_floor(nxt, tf) == start:
        return []   # bucket still open: more M15 children are expected
    tail = []
    for c in reversed(candles):
        if bucket_floor(c.timestamp, tf) != start:
            break
        tail.append(c)
    tail.reverse()
    sentinel = Candle(timestamp=nxt, open=last.close, high=last.close, low=last.close,
                      close=last.close, volume=0.0, index=last.index + 1)
    return resample(tail + [sentinel], tf)


def tf_frame(m15: pd.DataFrame, tf: str, include_closed_tail: bool = False) -> pd.DataFrame:
    if tf == "M15":
        return m15.copy()
    candles = to_candles(m15)
    bars = resample(candles, tf)
    if include_closed_tail:
        bars = bars + _closed_tail(candles, tf)
    return pd.DataFrame({"timestamp": [pd.Timestamp(b.timestamp) for b in bars],
                         "open": [b.open for b in bars], "high": [b.high for b in bars],
                         "low": [b.low for b in bars], "close": [b.close for b in bars],
                         "volume": [float(b.volume) for b in bars]})


def path_anchors(future: list[Candle], entry: float, risk: float, n: int) -> dict:
    """Step 6: first -0.25R, then +0.25R, then -0.25R on full-position open/close marks."""
    want, got, names = [-MARK, MARK, -MARK], [], ["first_neg", "then_pos", "then_neg"]
    for b in future[:n]:
        for px in (b.open, b.close):
            m = (px - entry) / risk
            if len(got) < 3:
                t = want[len(got)]
                if (t < 0 and m <= t) or (t > 0 and m >= t):
                    got.append(str(pd.Timestamp(b.timestamp)))
    return {names[i]: (got[i] if i < len(got) else None) for i in range(3)}


def build_rows(m15: pd.DataFrame, tf: str, eval_start: pd.Timestamp | None = None,
               include_closed_tail: bool = False) -> list[dict]:
    raw = tf_frame(m15, tf, include_closed_tail)
    feat, _ = FeaturePipeline(raw.copy(), cfg=get_prod_section("feature_pipeline")).run()
    feat = feat.set_index("timestamp")
    work = raw.set_index("timestamp")
    work["second_low_20d"] = compute_trading_day_second_low(work)
    mask = _detect_raw_purge_mask(work)
    bars = to_candles(raw)
    rows = []
    for pos in _independent_indices(work.index, mask):
        ts = work.index[pos]
        if eval_start is not None and ts < eval_start:
            continue
        if ts not in feat.index:
            continue   # inside the pipeline warmup
        f = feat.loc[ts]
        b = bars[pos]
        atr_abs = float(f["atr"]) * float(f["close"])
        if not np.isfinite(atr_abs) or atr_abs <= 0:
            continue
        lv = compute_crt_levels(b.close, 1, b.low, b.high, atr_abs, SL_BUFFER, TP1_MULT, TP2_MULT)
        future = bars[pos + 1:]
        row = dict(tf=tf, trigger_ts=str(ts), level=float(work["second_low_20d"].iloc[pos]),
                   bar_open=b.open, bar_low=b.low, bar_close=b.close, entry=b.close,
                   sl=lv["sl"], tp1=lv["tp1"], tp2=lv["tp2"], risk=lv["risk_dist"], atr_abs=atr_abs,
                   schema={k: float(f[k]) for k in CANONICAL_FEATURE_ORDER})
        for k in ("fvg_distance", "pdl_distance", "pdh_distance", "liquidity_sweep"):
            row[k] = float(f[k])
        if not future:
            row.update(status="OPEN", bars_available=0)
            rows.append(row)
            continue
        out = multi_tp_walk(b.close, "long", lv["sl"], lv["tp1"], lv["tp2"], future,
                            max_forward=len(future), entry_index=b.index)
        done = out.outcome != "TIMEOUT"
        row.update(status="CLOSED" if done else "OPEN", outcome=out.outcome,
                   exit_kind=out.exit_kind, rr_gross=out.rr_gross if done else None,
                   mark_r_now=out.rr_gross if not done else None,
                   duration_candles=out.duration_candles, reached_tp1=out.reached_tp1,
                   mfe_r=out.mfe / lv["risk_dist"], mae_r=out.mae / lv["risk_dist"],
                   gapped_stop=out.gapped_stop, ambiguous=out.ambiguous,
                   **path_anchors(future, b.close, lv["risk_dist"], out.duration_candles))
        rows.append(row)
    return rows


def stats(rows: list[dict]) -> dict:
    r = [x["rr_gross"] for x in rows if x.get("status") == "CLOSED"]
    if not r:
        return {"n": 0}
    a = np.array(r)
    se = a.std(ddof=1) / len(a) ** 0.5 if len(a) > 1 else float("nan")
    return dict(n=len(a), mean_rr_gross=round(float(a.mean()), 4),
                ci95=[round(float(a.mean() - 1.96 * se), 4), round(float(a.mean() + 1.96 * se), 4)],
                win_share=round(float((a > 0).mean()), 4), median=round(float(np.median(a)), 4),
                worst=round(float(a.min()), 4), best=round(float(a.max()), 4))


def cmd_backtest(args) -> None:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    m15 = load_csvs(args.csv)
    print(f"corpus {args.csv} rows={len(m15)} {m15.timestamp.iloc[0]} -> {m15.timestamp.iloc[-1]}")
    per_tf = {}
    for tf in TIMEFRAMES:
        rows = build_rows(m15, tf)
        (out / f"backtest_{tf}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        per_tf[tf] = rows
        print(tf, stats(rows))
    # step 8a
    tf_stats = {tf: stats(rows) for tf, rows in per_tf.items()}
    eligible = [tf for tf in TIMEFRAMES if tf_stats[tf]["n"] >= MIN_N_TF]
    chosen_tf = max(eligible, key=lambda tf: (tf_stats[tf]["mean_rr_gross"], -TIMEFRAMES.index(tf))) if eligible else None
    # step 8b
    cond_stats, chosen_cond = {}, None
    if chosen_tf:
        rows = per_tf[chosen_tf]
        base = tf_stats[chosen_tf]["mean_rr_gross"]
        for name, fn in CONDITIONS.items():
            cond_stats[name] = stats([r for r in rows if fn(r)])
        ok = [n for n, s in cond_stats.items() if s["n"] >= MIN_N_COND and s["mean_rr_gross"] > base]
        chosen_cond = max(ok, key=lambda n: cond_stats[n]["mean_rr_gross"]) if ok else None
    sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summary = dict(corpus=args.csv, rows=len(m15), first=str(m15.timestamp.iloc[0]),
                   last=str(m15.timestamp.iloc[-1]), per_timeframe=tf_stats,
                   chosen_timeframe=chosen_tf, condition_stats_on_chosen_tf=cond_stats,
                   chosen_condition=chosen_cond, economic_claims_allowed=False)
    (out / "backtest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    rule = dict(frozen_at=datetime.now().isoformat(timespec="seconds"), tool=str(Path(__file__).name),
                tool_sha256=sha, timeframe=chosen_tf, condition=chosen_cond,
                learned_on=f"{summary['first']} .. {summary['last']}",
                note="forward paper test only; in-sample learning is not evidence of an edge",
                economic_claims_allowed=False)
    (out / "rule_frozen.json").write_text(json.dumps(rule, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("per_timeframe", "chosen_timeframe", "chosen_condition")}, indent=1))
    print("condition stats", json.dumps(cond_stats, indent=1))


def fetch_mt5(days: int) -> pd.DataFrame:
    import MetaTrader5 as mt5
    from datetime import timedelta, timezone
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        mt5.symbol_select("XAUUSD", True)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        r = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M15, end - timedelta(days=days + 1), end)
    finally:
        mt5.shutdown()
    if r is None or len(r) == 0:
        raise RuntimeError("MT5 returned no bars")
    d = pd.DataFrame(r)
    d["timestamp"] = pd.to_datetime(d.time, unit="s")
    d = d.rename(columns={"tick_volume": "volume"})[["timestamp", "open", "high", "low", "close", "volume"]]
    return d.iloc[:-1].reset_index(drop=True)   # drop the forming bar


def cmd_live(args) -> None:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rule = json.loads(Path(args.rule).read_text(encoding="utf-8"))
    sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if sha != rule["tool_sha256"]:
        raise SystemExit(f"tool changed since freeze: {sha} != {rule['tool_sha256']}")
    m15 = load_csvs(args.csv) if args.csv else fetch_mt5(args.days)
    tf, cond = rule["timeframe"], rule["condition"]
    rows = build_rows(m15, tf, eval_start=pd.Timestamp(args.forward_start), include_closed_tail=True)
    for r in rows:
        r["passes_filter"] = True if cond is None else bool(CONDITIONS[cond](r))
        r["candidate_order"] = (dict(side="long", entry=r["entry"], sl=r["sl"], tp1=r["tp1"], tp2=r["tp2"])
                                if r["passes_filter"] else None)
    (out / "live_candidates.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""),
                                               encoding="utf-8")
    taken = [r for r in rows if r["passes_filter"]]
    run = dict(run_at=datetime.now().isoformat(timespec="seconds"), data_last_bar=str(m15.timestamp.iloc[-1]),
               rows=len(m15), timeframe=tf, condition=cond, forward_start=args.forward_start,
               triggers=len(rows), candidates=len(taken),
               open=sum(r["status"] == "OPEN" for r in taken), closed=stats(taken),
               economic_claims_allowed=False)
    with (out / "live_runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(run) + "\n")
    print(json.dumps(run, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backtest")
    b.add_argument("--csv", action="append", required=True)
    b.add_argument("--out-dir", required=True)
    lv = sub.add_parser("live")
    lv.add_argument("--rule", required=True)
    lv.add_argument("--forward-start", required=True)
    lv.add_argument("--out-dir", required=True)
    lv.add_argument("--days", type=int, default=60)
    lv.add_argument("--csv", action="append", help="replay from CSV instead of MT5")
    args = ap.parse_args()
    {"backtest": cmd_backtest, "live": cmd_live}[args.cmd](args)


if __name__ == "__main__":
    main()
