"""Profitable-zone event study (observation only; tools/xau_chart).

A bar is a LONG WIN if a long entered at its close reaches +TGT x ATR before -STOP x ATR within
H bars (a bar that touches both counts as a loss); SHORT WIN mirrors it. ATR is the pipeline's
close-relative atr x close (dollars). A PROFITABLE ZONE is a run of >= MIN_RUN consecutive win bars
on one side: a stretch of time where entering on any bar worked.

For every zone we read each feature at fixed offsets around it (before the start, at the start,
at the end, after the end). "Traceable" asks one question per feature: is its value at the zone's
first bar (known at that bar's close, i.e. at entry) different from its value on bars that are NOT
inside a zone of that side? Measured as AUC (0.5 = no difference), and checked for the same sign
in the first and second half of the period. Hindsight labels; descriptive only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STOP, TGT, H, MIN_RUN = 1.0, 2.0, 16, 3
PRE = (-8, -4, -1)          # offsets from the zone's first bar
POST = (4, 8)               # offsets from the zone's last bar
COST = 0.26                 # $/oz round trip (F-082 measured, TP exit)


def win_labels(o, h, l, c, atr_abs):
    n = len(c)
    lw = np.full(n, np.nan)
    sw = np.full(n, np.nan)
    for i in range(n):
        a = atr_abs[i]
        if not (a > 0) or i + H >= n:
            continue
        e = c[i]
        lres = sres = 0.0
        ldone = sdone = False
        for j in range(i + 1, i + H + 1):
            if not ldone:
                if l[j] <= e - STOP * a:
                    ldone = True
                elif h[j] >= e + TGT * a:
                    lres, ldone = (1.0 if TGT * a > COST else 0.0), True
            if not sdone:
                if h[j] >= e + STOP * a:
                    sdone = True
                elif l[j] <= e - TGT * a:
                    sres, sdone = (1.0 if TGT * a > COST else 0.0), True
            if ldone and sdone:
                break
        lw[i], sw[i] = lres, sres
    return lw, sw


def runs(win):
    out, s = [], None
    for i, v in enumerate(win):
        if v == 1.0 and s is None:
            s = i
        if v != 1.0 and s is not None:
            if i - s >= MIN_RUN:
                out.append((s, i - 1))
            s = None
    if s is not None and len(win) - s >= MIN_RUN:
        out.append((s, len(win) - 1))
    return out


def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    pos, neg = pos[~np.isnan(pos)], neg[~np.isnan(neg)]
    if len(pos) < 3 or len(neg) < 3:
        return None
    r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def study(df: pd.DataFrame, feats: list[str]) -> dict:
    """df: timestamp, open, high, low, close, atr (close-relative) + feature columns, chronological."""
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    atr_abs = df["atr"].to_numpy(float) * c
    lw, sw = win_labels(o, h, l, c, atr_abs)
    n = len(df)
    half = n // 2
    res = {"params": {"stop_atr": STOP, "target_atr": TGT, "horizon_bars": H, "min_run": MIN_RUN, "cost": COST},
           "bars": n, "labelled": int((~np.isnan(lw)).sum()),
           "win_rate": {"long": float(np.nanmean(lw)), "short": float(np.nanmean(sw))}}
    for side, win in (("long", lw), ("short", sw)):
        zs = runs(win)
        inzone = np.zeros(n, bool)
        for s, e in zs:
            inzone[s:e + 1] = True
        base = np.where(~inzone & ~np.isnan(win))[0]
        starts = np.array([s for s, _ in zs], int)
        prof = []
        for f in feats:
            v = df[f].to_numpy(float)
            row = {"feature": f}
            for k in PRE + (0,):
                idx = starts + k
                idx = idx[(idx >= 0) & (idx < n)]
                row[f"s{k:+d}"] = float(np.nanmedian(v[idx])) if len(idx) else None
            ends = np.array([e for _, e in zs], int)
            row["end"] = float(np.nanmedian(v[ends])) if len(ends) else None
            for k in POST:
                idx = ends + k
                idx = idx[idx < n]
                row[f"e+{k}"] = float(np.nanmedian(v[idx])) if len(idx) else None
            row["base"] = float(np.nanmedian(v[base])) if len(base) else None
            row["auc"] = auc(v[starts], v[base])
            row["auc_h1"] = auc(v[starts[starts < half]], v[base[base < half]])
            row["auc_h2"] = auc(v[starts[starts >= half]], v[base[base >= half]])
            a1, a2 = row["auc_h1"], row["auc_h2"]
            row["same_sign"] = (a1 is not None and a2 is not None and (a1 - .5) * (a2 - .5) > 0
                                and abs(a1 - .5) >= .05 and abs(a2 - .5) >= .05)
            prof.append(row)
        prof.sort(key=lambda r: -abs((r["auc"] if r["auc"] is not None else .5) - .5))
        res[side] = {"zones": [[int(s), int(e)] for s, e in zs], "n_zones": len(zs),
                     "zone_bars": int(inzone.sum()), "base_bars": int(len(base)),
                     "starts_h1": int((starts < half).sum()), "starts_h2": int((starts >= half).sum()),
                     "profile": prof}
    res["labels"] = {"long": [None if np.isnan(x) else int(x) for x in lw],
                     "short": [None if np.isnan(x) else int(x) for x in sw]}
    return res
