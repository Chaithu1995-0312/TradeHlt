"""Independent re-derivations used by the feature-audit scripts.

These deliberately do NOT import the repo's feature code (features.*, structure.*): the audit compares
the pipeline against a separate implementation of the REGISTERED formula. Plain loops, float64.
"""
from __future__ import annotations

import numpy as np


def ema_first(x, span):
    """EMA seeded with the first value (pandas ewm(adjust=False))."""
    x = np.asarray(x, float); n = len(x); a = 2 / (span + 1)
    out = np.full(n, np.nan); idx = np.where(~np.isnan(x))[0]; s = idx[0]; out[s] = x[s]
    for i in range(s + 1, n):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def sma(x, w):
    x = np.asarray(x, float); n = len(x); out = np.full(n, np.nan)
    for i in range(w - 1, n):
        seg = x[i - w + 1:i + 1]
        if not np.isnan(seg).any():
            out[i] = seg.sum() / w
    return out


def true_range(h, l, c):
    n = len(c); tr = np.empty(n); tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    return tr


def pivots(x, kind, k, strict=False):
    """Centered pivot at t over t-k..t+k (full window). Registered rule: equal to the extreme (ties count).
    strict=True: the textbook fractal, strictly beyond every neighbour."""
    x = np.asarray(x, float); n = len(x); out = np.zeros(n, dtype=int)
    for t in range(k, n - k):
        seg = x[t - k:t + k + 1]; others = np.delete(seg, k)
        if kind == "high":
            out[t] = int(x[t] > others.max()) if strict else int(x[t] == seg.max())
        else:
            out[t] = int(x[t] < others.min()) if strict else int(x[t] == seg.min())
    return out


def publish(piv, x, k):
    """FC1-A causal publication: flag at i = pivot at i-k; last swing price at i = latest pivot price at or before i-k."""
    n = len(x); flag = np.zeros(n, dtype=int); last = np.full(n, np.nan); lastc = np.full(n, np.nan); cur = np.nan
    for t in range(n):
        if piv[t] == 1:
            cur = x[t]
        lastc[t] = cur
    for i in range(k, n):
        flag[i] = piv[i - k]; last[i] = lastc[i - k]
    return flag, last


def lifecycle(h, l, c, sh, sl, k):
    """MKT-E01 level book. A level is added at publication (bar i, price at i-k) and tested from bar i on.
    UPPER: swept if high > L and close < L, else broken if close > L. LOWER mirrored. A level ends either way.
    Returns (up, down, up_levels, down_levels): per-bar event flags and the swept prices on that bar."""
    n = len(c); active = []
    up = np.zeros(n, dtype=int); down = np.zeros(n, dtype=int)
    up_lv = [[] for _ in range(n)]; dn_lv = [[] for _ in range(n)]
    for i in range(n):
        if i - k >= 0 and sh[i] == 1:
            active.append((h[i - k], "U"))
        if i - k >= 0 and sl[i] == 1:
            active.append((l[i - k], "L"))
        keep = []
        for price, side in active:
            if side == "U":
                if h[i] > price and c[i] < price:
                    up[i] = 1; up_lv[i].append(price)
                elif c[i] > price:
                    pass
                else:
                    keep.append((price, side))
            else:
                if l[i] < price and c[i] > price:
                    down[i] = 1; dn_lv[i].append(price)
                elif c[i] < price:
                    pass
                else:
                    keep.append((price, side))
        active = keep
    return up, down, up_lv, dn_lv


def active_levels_before_bar(h, l, c, sh, sl, k):
    """Same MKT-E01 book as `lifecycle`, but returns, for each bar i, the prices of the levels still
    ACTIVE at the open of bar i (after bar i-1 was processed; levels published on bar i are not yet known)."""
    n = len(c); active = []; snap = [[] for _ in range(n)]
    for i in range(n):
        snap[i] = [p for p, _ in active]
        if i - k >= 0 and sh[i] == 1:
            active.append((h[i - k], "U"))
        if i - k >= 0 and sl[i] == 1:
            active.append((l[i - k], "L"))
        keep = []
        for price, side in active:
            if side == "U":
                if (h[i] > price and c[i] < price) or c[i] > price:
                    continue
            else:
                if (l[i] < price and c[i] > price) or c[i] < price:
                    continue
            keep.append((price, side))
        active = keep
    return snap


def roll_any(ev, w):
    ev = np.asarray(ev); n = len(ev); out = np.zeros(n, int)
    for i in range(n):
        out[i] = int(ev[max(0, i - w + 1):i + 1].any())
    return out
