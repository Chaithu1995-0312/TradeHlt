"""Daily trend filter on H4 trades, both sides (trend_study_declaration.json). One run.
Writes results/h4_long_holdout/trend_study.json."""
import os, sys, json, math, hashlib
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
os.environ["TF"] = "H4"
sys.path.insert(0, _HERE)
import numpy as np
import pandas as pd
import replica as H

DECL = os.path.join(_HERE, "trend_study_declaration.json")
assert hashlib.sha256(open(DECL, "rb").read()).hexdigest() == "b1b4b05889e0ecbaad523af7144149d333858353a4e290b212ceeaef26c92153"
m = H.load(os.path.join(ROOT, "data", "mt5", "XAUUSD_M15.csv")); h4 = H.parents(m); ts = m["timestamp"]; N = len(m)
day = m.groupby(ts.dt.normalize())["close"].last()                  # broker-day closes
sma50 = day.rolling(50).mean(); ret20 = day.shift(20)
day_end = pd.Series(day.index + pd.Timedelta(days=1), index=day.index)  # a broker day is complete at next 00:00

rows = []
for t, p in h4.iterrows():
    if np.isnan(p.atr): continue
    ca = t + pd.Timedelta(hours=4); j = ts.searchsorted(ca)
    if j >= N or ts.iloc[j] > ca + pd.Timedelta(minutes=120): continue
    done = day.index[day_end.to_numpy() <= ca]                       # completed days before the H4 close
    if len(done) < 51: continue
    dlast = done[-1]
    if np.isnan(sma50[dlast]) or np.isnan(ret20[dlast]): continue
    t1 = 1 if day[dlast] > sma50[dlast] else -1
    t2 = 1 if day[dlast] > ret20[dlast] else -1
    for d in (1, -1):
        o = m["open"].iloc[j]; E = o + H.SPREAD + H.SLIP if d == 1 else o - H.SLIP
        SL = p.low - 0.2 * p.atr if d == 1 else p.high + 0.2 * p.atr + H.SPREAD; R = d * (E - SL)
        if R <= 0: continue
        c = dict(signal=t, entry_at=ts.iloc[j], j=int(j), d=d, E=E, SL=SL, R=R, D=R + H.SLIP + H.COMM)
        st, ex, r, _ = H.walk(m, c, 1.5, N)
        if st == "OPEN": continue
        rows.append(dict(signal=t, d=d, r=r, T1_sma50=t1, T2_ret20=t2))
df = pd.DataFrame(rows)
stat = lambda x: dict(n=int(len(x)), mean=float(x.mean()) if len(x) else None, se=float(x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else None,
                      win=float((x > 0).mean()) if len(x) else None)
out = {"first_signal": str(df.signal.min()), "last_signal": str(df.signal.max()), "periods": {}}
for per, (a, b) in {"history_seen": ("2024-05-22", "2025-05-22"), "test": ("2025-05-22", "2026-05-22")}.items():
    x = df[(df.signal >= a) & (df.signal < b)]
    res = {}
    L, S = x[x.d == 1].r, x[x.d == -1].r
    res["all_longs"] = stat(L); res["all_shorts"] = stat(S)
    for T in ("T1_sma50", "T2_ret20"):
        lu = x[(x.d == 1) & (x[T] == 1)].r; ld = x[(x.d == 1) & (x[T] == -1)].r
        sd = x[(x.d == -1) & (x[T] == -1)].r; su = x[(x.d == -1) & (x[T] == 1)].r
        both = pd.concat([lu, sd])
        r_ = dict(longs_up=stat(lu), longs_down=stat(ld), shorts_down=stat(sd), shorts_up=stat(su), trend_both=stat(both),
                  up_share=float((x[x.d == 1][T] == 1).mean()))
        if per == "test":
            c1 = lu.mean() - L.mean() > lu.std(ddof=1) / math.sqrt(len(lu))
            c2 = sd.mean() - S.mean() > sd.std(ddof=1) / math.sqrt(len(sd)) if len(sd) > 1 else False
            c3 = both.mean() > 0 and len(lu) >= 30 and len(sd) >= 30
            r_["checks"] = dict(longs_up_beats_all_longs=bool(c1), shorts_down_beats_all_shorts=bool(c2), trend_both_positive=bool(c3), PASS=bool(c1 and c2 and c3))
        res[T] = r_
    out["periods"][per] = res
json.dump(out, open(os.path.join(ROOT, "results", "h4_long_holdout", "trend_study.json"), "w"), indent=1)
f = lambda s: f"n={s['n']:4} {s['mean']:+.3f}±{s['se']:.3f} win {s['win']:.0%}" if s["n"] > 1 else f"n={s['n']}"
for per, res in out["periods"].items():
    print(f"\n== {per}: all longs {f(res['all_longs'])} | all shorts {f(res['all_shorts'])}")
    for T in ("T1_sma50", "T2_ret20"):
        r_ = res[T]
        print(f"  {T} (uptrend share {r_['up_share']:.0%})")
        for k in ("longs_up", "longs_down", "shorts_down", "shorts_up", "trend_both"): print(f"    {k:12} {f(r_[k])}")
        if "checks" in r_: print("    checks:", r_["checks"])
