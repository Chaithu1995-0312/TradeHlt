"""Candle-arithmetic profit ranges for H4 longs (range_study_declaration.json). One run.
Writes results/h4_long_holdout/range_study.json."""
import os, sys, json, math, hashlib
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
os.environ["TF"] = "H4"
sys.path.insert(0, _HERE)
import numpy as np
import pandas as pd
import replica as H

DECL = os.path.join(_HERE, "range_study_declaration.json")
assert hashlib.sha256(open(DECL, "rb").read()).hexdigest() == "02d11c014e2a9b3d63640d7ea0b1aa74e04c6b06767fdd0b86f1c91ea63bca73"
m = H.load(os.path.join(ROOT, "data", "mt5", "XAUUSD_M15.csv")); h4 = H.parents(m); ts = m["timestamp"]; N = len(m)
h4["prev_close"] = h4["close"].shift(1); h4["close_6"] = h4["close"].shift(6)
rows = []
for t, p in h4.iterrows():
    if np.isnan(p.atr) or np.isnan(p.close_6): continue
    ca = t + pd.Timedelta(hours=4); j = ts.searchsorted(ca)
    if j >= N or ts.iloc[j] > ca + pd.Timedelta(minutes=120): continue
    rng = p.high - p.low
    if rng <= 0: continue
    o = m["open"].iloc[j]; E = o + H.SPREAD + H.SLIP; SL = p.low - 0.2 * p.atr; R = E - SL
    if R <= 0: continue
    c = dict(signal=t, j=int(j), d=1, E=E, SL=SL, R=R, D=R + H.SLIP + H.COMM)
    st, ex, r, _ = H.walk(m, c, 1.5, N)
    if st == "OPEN": continue
    rows.append(dict(signal=t, r=r,
                     body_ratio=abs(p.close - p.open) / rng, upper_wick_ratio=(p.high - max(p.open, p.close)) / rng,
                     lower_wick_ratio=(min(p.open, p.close) - p.low) / rng, close_location=(p.close - p.low) / rng,
                     range_atr=rng / p.atr, body_atr_signed=(p.close - p.open) / p.atr,
                     momentum_atr=(p.close - p.prev_close) / p.atr, trend_6_atr=(p.close - p.close_6) / p.atr, hour=t.hour))
df = pd.DataFrame(rows)
FEATS = ["body_ratio", "upper_wick_ratio", "lower_wick_ratio", "close_location", "range_atr", "body_atr_signed", "momentum_atr", "trend_6_atr", "hour"]
tr = df[df.signal < "2025-05-22"].reset_index(drop=True); te = df[df.signal >= "2025-05-22"].reset_index(drop=True)
rng_ = np.random.default_rng(20261014)

def bins_for(f):
    if f == "hour":
        vals = sorted(tr[f].unique()); return [("=", v) for v in vals]
    q = np.quantile(tr[f], [0, .2, .4, .6, .8, 1.0]); q[0], q[-1] = -np.inf, np.inf
    return [(q[i], q[i + 1]) for i in range(5)]

def assign(x, f, bins):
    if f == "hour": return np.array([[b[1] for b in bins].index(v) if v in [b[1] for b in bins] else -1 for v in x])
    return np.searchsorted([b[1] for b in bins][:-1], x, side="right")

def best_range(b_idx, r, nb):
    best = None
    for w in (1, 2, 3):
        for s in range(nb - w + 1):
            mask = (b_idx >= s) & (b_idx < s + w)
            if mask.mean() < 0.20: continue
            v = r[mask].mean()
            if best is None or v > best[0]: best = (v, s, w, mask)
    return best

out = dict(train=dict(n=len(tr), mean=float(tr.r.mean()), first=str(tr.signal.min()), last=str(tr.signal.max())),
           test=dict(n=len(te), mean=float(te.r.mean()), se=float(te.r.std(ddof=1) / math.sqrt(len(te))), first=str(te.signal.min()), last=str(te.signal.max())),
           features={})
for f in FEATS:
    bins = bins_for(f); nb = len(bins)
    bi = assign(tr[f].to_numpy(), f, bins); r = tr.r.to_numpy()
    prof = [dict(bin=i, lo=None if f == "hour" else float(bins[i][0]), hi=None if f == "hour" else float(bins[i][1]),
                 value=bins[i][1] if f == "hour" else None, n=int((bi == i).sum()), mean_r=float(r[bi == i].mean()), win=float((r[bi == i] > 0).mean()))
            for i in range(nb)]
    v, s, w, mask = best_range(bi, r, nb); gain = v - r.mean()
    null = []
    for _ in range(200):
        rp = rng_.permutation(r); vv, *_ = best_range(bi, rp, nb); null.append(vv - rp.mean())
    p95 = float(np.quantile(null, .95)); passes_noise = gain > p95
    lo = None if f == "hour" else bins[s][0]; hi = None if f == "hour" else bins[s + w - 1][1]
    hours = [bins[i][1] for i in range(s, s + w)] if f == "hour" else None
    rec = dict(train_bins=prof, range=dict(lo=lo, hi=hi, hours=hours, bins=[s, s + w - 1]), train_in=dict(n=int(mask.sum()), mean_r=float(v), win=float((r[mask] > 0).mean())),
               train_gain=float(gain), shuffle_p95=p95, passes_noise=bool(passes_noise))
    if passes_noise:
        ti = assign(te[f].to_numpy(), f, bins); tm = (ti >= s) & (ti < s + w); x = te.r.to_numpy()[tm]
        se = x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else float("nan")
        rec["test_in"] = dict(n=int(tm.sum()), mean_r=float(x.mean()), se=float(se), win=float((x > 0).mean()))
        rec["test_pass"] = bool(len(x) >= 30 and x.mean() > 0 and x.mean() - out["test"]["mean"] > se)
    out["features"][f] = rec
json.dump(out, open(os.path.join(ROOT, "results", "h4_long_holdout", "range_study.json"), "w"), indent=1, default=float)
print(f"train n={len(tr)} mean {tr.r.mean():+.3f}R | test n={len(te)} mean {te.r.mean():+.3f}R ± {out['test']['se']:.3f}")
for f, rec in out["features"].items():
    rg = rec["range"]; desc = f"hours {rg['hours']}" if f == "hour" else f"[{rg['lo']:.3g}, {rg['hi']:.3g})"
    line = f"{f:17} range {desc:26} train in n={rec['train_in']['n']:4} {rec['train_in']['mean_r']:+.3f}R gain {rec['train_gain']:+.3f} vs shuffle95 {rec['shuffle_p95']:+.3f} -> {'PASS' if rec['passes_noise'] else 'noise'}"
    if "test_in" in rec: line += f" | TEST n={rec['test_in']['n']} {rec['test_in']['mean_r']:+.3f}±{rec['test_in']['se']:.3f} -> {'PASS' if rec['test_pass'] else 'FAIL'}"
    print(line)
