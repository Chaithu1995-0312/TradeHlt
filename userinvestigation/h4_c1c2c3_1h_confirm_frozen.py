"""FROZEN 2026-10-06 — H4 C1/C2/C3 with a 1H confirmation close (successor of
h4_c1c2c3_near_level_frozen.py; that rule FAILED out-of-sample and is not edited).

UNVALIDATED proxy of a bridged Sujan reading (drift log Record 8). Not Sujan identity.
Sujan's words used: "Put 1 hr candle close after sweep, not 15 min ... 1 hr confirmation
require" (Record 7) and "... on bullish candle close - entry trigger" (2026-10-06 chat).

Rule (identical to the predecessor except the ENTRY)
  C1/C2      ParentCandleBuilder("H4") (broker grid) + ParentCRTTrack; signal on
             RANGE_C1 -> MANIPULATION_C2. swept low -> long, swept high -> short.
  stop       C2 swept extreme (no buffer).   target = C1 far side.
  1H confirm after C2 closes, scan the broker-hour 1H candles inside C3 (the next H4 period,
             at most 4 hours). The FIRST 1H candle that closes in the trade direction
             (long: close > open; short: close < open) is the trigger. Entry = its close.
             No trade if: the stop is touched before or during the trigger candle; no
             confirming 1H close inside C3; or the trigger close is at/beyond the target.
  walk       M15 bars after the trigger candle until stop or target; stop first on a shared
             bar; a bar opening through the stop fills at its open.
  near level |C2 swept extreme - L| <= 0.5 * ATR14 of the closed H4 bars before C2,
             L in {PDH, PDL (previous broker date), WO (first M15 open of the ISO week)}.
  cost       research.costs.xau_measured_cost_model, nights_held=0 (swap UNMEASURED).
Primary     mean gross R of near-level confirmed trades with C2 start >= --eval-start.
Secondary   all confirmed trades (no level filter).
Control     50 random-entry draws (seed 20261006): same side, risk, planned RR, random H4 close.
Verdict     n < 30 INSUFFICIENT; gross <= 0 FAIL;
            gross > 0 and net > 0 and share of random draws >= real <= 0.10 PASS; else INCONCLUSIVE.
"""
import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config_layer.crt_engine_v2 import Candle  # noqa: E402
from config_layer.parent_crt import ParentCRTTrack  # noqa: E402
from config_layer.state_identity import CRTState, Direction  # noqa: E402
from features.parent_candle import ParentCandleBuilder  # noqa: E402
from research.costs import xau_measured_cost_model  # noqa: E402

NEAR_ATR = 0.5
SEED = 20261006
DRAWS = 50
MIN_N = 30
PASS_SHARE = 0.10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--eval-start", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.csv, parse_dates=["timestamp"])
    print(f"corpus {args.csv} rows={len(df)} {df.timestamp.iloc[0]} -> {df.timestamp.iloc[-1]}")
    ts = df.timestamp
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    hour_key = ts.dt.floor("h").values
    h4_key = ts.dt.floor("4h").values
    bars = [Candle(timestamp=t.to_pydatetime(), open=o[i], high=h[i], low=l[i], close=c[i],
                   volume=float(df.volume.iloc[i]), index=i) for i, t in enumerate(ts)]

    day = df.groupby(ts.dt.date).agg(high=("high", "max"), low=("low", "min"))
    prev_day = day.shift(1)
    iso = ts.dt.isocalendar()
    wk = iso.year.astype(str) + "-" + iso.week.astype(str)
    week_open = df.groupby(wk.values).open.first()
    h4 = df.set_index("timestamp").resample("4h", origin="epoch").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([h4.high - h4.low, (h4.high - h4.close.shift()).abs(),
                    (h4.low - h4.close.shift()).abs()], axis=1).max(axis=1)
    atr_prev = tr.rolling(14).mean().shift(1)

    def walk(i, entry, stop, target, d):
        for j in range(i, len(bars)):
            if d == 1:
                if o[j] <= stop: return j, o[j], "SL_HIT"
                if l[j] <= stop: return j, stop, "SL_HIT"
                if h[j] >= target: return j, target, "TP_HIT"
            else:
                if o[j] >= stop: return j, o[j], "SL_HIT"
                if h[j] >= stop: return j, stop, "SL_HIT"
                if l[j] <= target: return j, target, "TP_HIT"
        return None, None, "OPEN"

    def confirm(i, stop, d):
        """First 1H close in direction d inside C3 (the H4 period that starts at bar i).
        Returns (trigger_last_bar_index, entry) or (None, reason)."""
        if i >= len(bars):
            return None, "no_data"
        c3 = h4_key[i]
        j = i
        while j < len(bars) and h4_key[j] == c3:
            hk = hour_key[j]
            hopen, k = o[j], j
            while k < len(bars) and hour_key[k] == hk:
                if (d == 1 and l[k] <= stop) or (d == -1 and h[k] >= stop):
                    return None, "stop_before_confirm"
                k += 1
            hclose = c[k - 1]
            if (d == 1 and hclose > hopen) or (d == -1 and hclose < hopen):
                return k - 1, hclose
            j = k
        return None, "no_confirm_in_c3"

    cost = xau_measured_cost_model()
    builder, track = ParentCandleBuilder("H4", keep=3), ParentCRTTrack()
    eval_start = pd.Timestamp(args.eval_start)
    rows, skipped = [], {}
    for i, b in enumerate(bars):
        if not builder.push(b):
            continue
        parent = builder.parent_candle
        prev = track.state
        if not (track.on_parent_close(parent) == CRTState.MANIPULATION_C2 and prev == CRTState.RANGE_C1):
            continue
        sw, rng = track.sweep, track.range
        d = 1 if sw.direction == Direction.LONG else -1
        stop = sw.price
        target = rng.h_ref if d == 1 else rng.l_ref
        c2_ts = pd.Timestamp(parent.timestamp)
        in_eval = bool(c2_ts >= eval_start)
        trig, entry = confirm(i, stop, d)
        if trig is None:
            key = (in_eval, entry)
            skipped[f"{'eval' if in_eval else 'warmup'}:{entry}"] = skipped.get(f"{'eval' if in_eval else 'warmup'}:{entry}", 0) + 1
            continue
        risk, reward = (entry - stop) * d, (target - entry) * d
        if risk <= 0 or reward <= 0:
            k = f"{'eval' if in_eval else 'warmup'}:{'nonpositive_risk' if risk <= 0 else 'entry_beyond_target'}"
            skipped[k] = skipped.get(k, 0) + 1
            continue
        pdh, pdl = prev_day.loc[c2_ts.date()]
        ic = c2_ts.isocalendar()
        wo = week_open.get(f"{ic[0]}-{ic[1]}")
        atr = atr_prev.get(c2_ts, np.nan)
        near = {name: bool(not pd.isna(L) and not pd.isna(atr) and abs(sw.price - L) <= NEAR_ATR * atr)
                for name, L in (("PDH", pdh), ("PDL", pdl), ("WO", wo))}
        j, px, kind = walk(trig + 1, entry, stop, target, d)
        row = dict(c2_ts=str(c2_ts), trigger_ts=str(ts.iloc[trig]), in_eval=in_eval,
                   direction="long" if d == 1 else "short", entry=entry, stop=stop,
                   target=target, risk=risk, planned_rr=reward / risk, c2_close=parent.close,
                   c1_high=rng.h_ref, c1_low=rng.l_ref, pdh=pdh, pdl=pdl, wo=wo, atr_h4_prev=atr,
                   near_PDH=near["PDH"], near_PDL=near["PDL"], near_WO=near["WO"],
                   near_any=any(near.values()), exit_kind=kind)
        if kind != "OPEN":
            g = (px - entry) * d / risk
            cr = cost.cost_r(entry, risk, exit_kind=kind, direction=row["direction"], nights_held=0)
            row.update(exit_ts=str(bars[j].timestamp), exit_price=px, bars_held=j - trig,
                       gross_r=g, cost_r=cr, net_r=g - cr)
        rows.append(row)

    out = Path(args.out)
    out.with_suffix(".jsonl").write_text("\n".join(json.dumps(r, default=float) for r in rows) + "\n",
                                         encoding="utf-8")
    a = pd.DataFrame(rows)
    ev = a[a.in_eval]

    k4 = ts.dt.floor("D").astype("int64") // 10**9 + (ts.dt.hour // 4)
    starts = np.flatnonzero(k4.values[1:] != k4.values[:-1]) + 1
    starts = starts[ts.values[starts] >= np.datetime64(eval_start)]

    def control(sub):
        rng_ = random.Random(SEED)
        means = []
        for _ in range(DRAWS):
            vals = []
            for r in sub.itertuples():
                d = 1 if r.direction == "long" else -1
                k = int(rng_.choice(starts))
                e = c[k - 1]
                _, px, kind = walk(k, e, e - d * r.risk, e + d * r.risk * r.planned_rr, d)
                if kind != "OPEN":
                    vals.append((px - e) * d / r.risk)
            means.append(np.mean(vals))
        m = np.array(means)
        return dict(random_mean=round(float(m.mean()), 4),
                    share_of_draws_beating_real=round(float((m >= sub.gross_r.mean()).mean()), 3))

    def stats(sub, ctrl=False):
        sub = sub[sub.exit_kind != "OPEN"]
        n = len(sub)
        if n == 0:
            return {"n": 0}
        se = sub.gross_r.std(ddof=1) / n ** 0.5 if n > 1 else float("nan")
        s = dict(n=n, long_n=int((sub.direction == "long").sum()),
                 win_rate=round((sub.exit_kind == "TP_HIT").mean(), 4),
                 breakeven_win_rate=round((1 / (1 + sub.planned_rr)).mean(), 4),
                 gross_r_mean=round(sub.gross_r.mean(), 4),
                 gross_r_ci95=[round(sub.gross_r.mean() - 1.96 * se, 4), round(sub.gross_r.mean() + 1.96 * se, 4)],
                 net_r_mean=round(sub.net_r.mean(), 4),
                 long_gross_r=round(sub[sub.direction == "long"].gross_r.mean(), 4) if (sub.direction == "long").any() else None,
                 short_gross_r=round(sub[sub.direction == "short"].gross_r.mean(), 4) if (sub.direction == "short").any() else None,
                 worst_r=round(sub.gross_r.min(), 4))
        if ctrl and n >= 2:
            s["random_control"] = control(sub)
        return s

    def verdict(p):
        if p["n"] < MIN_N:
            return "INSUFFICIENT"
        if p["gross_r_mean"] <= 0:
            return "FAIL"
        if p["net_r_mean"] > 0 and p["random_control"]["share_of_draws_beating_real"] <= PASS_SHARE:
            return "PASS"
        return "INCONCLUSIVE"

    p = stats(ev[ev.near_any], ctrl=True)
    s2 = stats(ev, ctrl=True)
    summary = dict(rule=out.name, csv=args.csv, eval_start=args.eval_start, rows=len(df),
                   first=str(ts.iloc[0]), last=str(ts.iloc[-1]), skipped=skipped,
                   primary_near_any_confirmed=p, verdict=verdict(p),
                   secondary_all_confirmed=s2, secondary_verdict=verdict(s2),
                   eval_not_near=stats(ev[~ev.near_any]),
                   open_in_eval=int((ev.exit_kind == "OPEN").sum()),
                   economic_claims_allowed=False)
    out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    print(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
