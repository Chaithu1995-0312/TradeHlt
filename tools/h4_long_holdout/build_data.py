"""Per-trade and per-day record of the H4 long-only 1.5R holdout (declaration.json, sha256 2c3016a1...).

Same frozen rule and data as the one declared run; this script only records it in detail.
Writes results/h4_long_holdout/holdout.json. Read-only on data/.
"""
import os, sys, json, math, hashlib
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
os.environ["TF"] = "H4"
sys.path.insert(0, _HERE)
import numpy as np
import pandas as pd
import replica as H

DATA = os.path.join(ROOT, "data", "mt5", "XAUUSD_M15_2026-04-20_to_2026-10-06.csv")
SHA = "494e045b700aac88b0a538789549418ebf1014fa7e1f64d6c7cbe420c297c7b6"
DECL = os.path.join(_HERE, "declaration.json")
assert hashlib.sha256(open(DATA, "rb").read()).hexdigest() == SHA
SPANS = [(pd.Timestamp("2026-05-22"), pd.Timestamp("2026-07-06")), (pd.Timestamp("2026-08-08"), pd.Timestamp("2026-10-07"))]
ACCOUNTS = {"A": dict(capital=1_000_000, budget=30_000), "B": dict(capital=100_000, budget=3_000)}

def ist(ts):
    """Broker wall time (mt5_icmarkets_xau: New York wall + 7h) -> IST wall time."""
    return (ts - pd.Timedelta(hours=7)).tz_localize("America/New_York").tz_convert("Asia/Kolkata").tz_localize(None)

def walk(m, c, mult, N):
    """replica.walk with the fill, funding nights and exit kind kept."""
    d, E, SL, D = 1, c["E"], c["SL"], c["D"]
    TP = E + mult * D + H.SLIP + H.COMM
    O, Hh, L, T = m["open"].to_numpy(), m["high"].to_numpy(), m["low"].to_numpy(), m["timestamp"]
    nights = 0; last_day = T.iloc[c["j"]].normalize()
    for k in range(c["j"], N):
        day = T.iloc[k].normalize()
        if day > last_day:
            for dd in pd.date_range(last_day + pd.Timedelta(days=1), day):
                nights += 3 if dd.dayofweek == 3 else 1
            last_day = day
        carry = H.CARRY[1] * nights
        if L[k] <= SL:
            gap = k > c["j"] and O[k] <= SL
            fill = (O[k] if gap else SL) - H.SLIP
            return dict(kind="Stop (gap at open)" if gap else "Stop", exit=T.iloc[k], fill=fill, nights=nights, TP=TP,
                        r=((fill - E) - H.COMM + carry) / D, carry=carry)
        if Hh[k] >= TP:
            fill = TP - H.SLIP
            return dict(kind="Target", exit=T.iloc[k], fill=fill, nights=nights, TP=TP, r=((fill - E) - H.COMM + carry) / D, carry=carry)
    return dict(kind="Open at file end", exit=None, fill=None, nights=nights, TP=TP, r=None, carry=None)

m = H.load(DATA); h4 = H.parents(m); ts = m["timestamp"]; N = len(m)
cands = []
for t, p in h4.iterrows():
    if np.isnan(p.atr) or not any(a <= t < b for a, b in SPANS): continue
    ca = t + pd.Timedelta(hours=4); j = ts.searchsorted(ca)
    if j >= N or ts.iloc[j] > ca + pd.Timedelta(minutes=120): continue
    rng = p.high - p.low
    if rng <= 0: continue
    o = m["open"].iloc[j]; E = o + H.SPREAD + H.SLIP; SL = p.low - 0.2 * p.atr; R = E - SL
    if R <= 0: continue
    c = dict(signal=t, entry_at=ts.iloc[j], j=int(j), E=E, SL=SL, R=R, D=R + H.SLIP + H.COMM, atr=float(p.atr),
             body_ratio=abs(p.close - p.open) / rng, sel=abs(p.close - p.open) / rng >= 0.66,
             sig_ohlc=[float(p.open), float(p.high), float(p.low), float(p.close)])
    c.update(walk(m, c, 1.5, N)); cands.append(c)

def fmt(t): return None if t is None else t.strftime("%Y-%m-%d %H:%M")

def book(pool, acct):
    cap0 = ACCOUNTS[acct]["capital"]; budget = ACCOUNTS[acct]["budget"]
    busy = None; cap = cap0; trades = []; skipped = []; open_pos = None
    for c in sorted(pool, key=lambda c: c["entry_at"]):
        if busy is not None and c["entry_at"] <= busy:
            skipped.append(dict(signal=fmt(c["signal"]), reason="position already open")); continue
        lots = min(math.floor(budget / (c["D"] * 8400) / 0.01 + 1e-9) * 0.01, 10)
        if lots < 0.01:
            skipped.append(dict(signal=fmt(c["signal"]), reason="below 0.01 lot")); continue
        base = dict(id=f"{acct}-{len(trades) + 1:02d}", signal=fmt(c["signal"]), signal_ist=fmt(ist(c["signal"])),
                    entry_at=fmt(c["entry_at"]), entry_ist=fmt(ist(c["entry_at"])), entry=round(c["E"], 2), stop=round(c["SL"], 2),
                    target=round(c["TP"], 2), risk_usd=round(c["R"], 2), body_ratio=round(c["body_ratio"], 3), atr=round(c["atr"], 2),
                    signal_ohlc=c["sig_ohlc"], lots=round(lots, 2))
        if c["r"] is None:
            open_pos = dict(base, kind=c["kind"]); break
        inr = c["r"] * c["D"] * lots * 8400; cap += inr
        trades.append(dict(base, kind=c["kind"], exit_at=fmt(c["exit"]), exit_ist=fmt(ist(c["exit"])), exit_fill=round(c["fill"], 2),
                           hold_h=round((c["exit"] - c["entry_at"]).total_seconds() / 3600, 2), nights=c["nights"],
                           funding_inr=round(c["carry"] * lots * 100 * 84, 2), r=round(c["r"], 3), inr=round(inr, 2), equity=round(cap, 2)))
        busy = c["exit"]
    # per day: every trading day of the M15 file inside the spans, plus any exit day after a span
    days = sorted(set(ts[(ts >= SPANS[0][0]) & (ts < SPANS[0][1]) | (ts >= SPANS[1][0])].dt.strftime("%Y-%m-%d"))
                  | {t["exit_at"][:10] for t in trades})
    eq = cap0; peak = cap0; rows = []
    for d in days:
        opened = [t["id"] for t in trades if t["entry_at"][:10] == d] + ([open_pos["id"]] if open_pos and open_pos["entry_at"][:10] == d else [])
        closed = [t for t in trades if t["exit_at"][:10] == d]
        pnl = sum(t["inr"] for t in closed); eq += pnl; peak = max(peak, eq)
        holding = any(t["entry_at"][:10] <= d <= t["exit_at"][:10] for t in trades) or bool(open_pos and open_pos["entry_at"][:10] <= d)
        span = "1" if d < "2026-07-06" else ("2" if d >= "2026-08-08" else "between")
        rows.append(dict(date=d, weekday=pd.Timestamp(d).strftime("%a"), span=span, opened=opened, closed=[t["id"] for t in closed],
                         wins=sum(t["inr"] > 0 for t in closed), losses=sum(t["inr"] <= 0 for t in closed), pnl=round(pnl, 2),
                         equity=round(eq, 2), drawdown=round((peak - eq) / peak, 4), in_position=holding))
    v = np.array([t["inr"] for t in trades]); r = np.array([t["r"] for t in trades])
    peak = cap0; dd = 0
    for t in trades: peak = max(peak, t["equity"]); dd = max(dd, (peak - t["equity"]) / peak)
    return dict(capital=cap0, budget=budget, trades=trades, open=open_pos, skipped=skipped, days=rows,
                summary=dict(trades=len(trades), wins=int((v > 0).sum()), net=round(float(v.sum()), 2), mean_r=round(float(r.mean()), 3),
                             max_dd=round(dd, 4), end=round(cap0 + float(v.sum()), 2), best=round(float(v.max()), 2), worst=round(float(v.min()), 2),
                             funding=round(sum(t["funding_inr"] for t in trades), 2),
                             days_traded=sum(1 for d in rows if d["closed"]), green_days=sum(1 for d in rows if d["pnl"] > 0),
                             red_days=sum(1 for d in rows if d["pnl"] < 0)))

rule = [c for c in cands if c["sel"]]
out = dict(declaration=json.load(open(DECL, encoding="utf-8")), declaration_sha256=hashlib.sha256(open(DECL, "rb").read()).hexdigest(),
           data=dict(path="data/mt5/XAUUSD_M15_2026-04-20_to_2026-10-06.csv", sha256=SHA, rows=N, first=fmt(ts.iloc[0]), last=fmt(ts.iloc[-1])),
           gold=dict(start=float(m[ts >= SPANS[0][0]].close.iloc[0]), end=float(m.close.iloc[-1]),
                     span1=[float(m[(ts >= SPANS[0][0])].close.iloc[0]), float(m[ts < SPANS[0][1]].close.iloc[-1])],
                     span2=[float(m[ts >= SPANS[1][0]].close.iloc[0]), float(m.close.iloc[-1])]),
           signals=len(rule), candidates=len(cands),
           accounts={a: book(rule, a) for a in ACCOUNTS},
           control={a: book(cands, a)["summary"] for a in ACCOUNTS})
os.makedirs(os.path.join(ROOT, "results", "h4_long_holdout"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "results", "h4_long_holdout", "holdout.json"), "w", encoding="utf-8"), indent=1, default=str)
for a in ACCOUNTS:
    print(a, out["accounts"][a]["summary"], "open:", out["accounts"][a]["open"] and out["accounts"][a]["open"]["entry_at"])
print("control", out["control"])
