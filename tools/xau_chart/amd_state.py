"""D1_AMD state machine — ONE implementation shared by the AMD-H1 harness and the chart artifact.

C2 (user calibration, 2026-10-08; v3 kept in amd_state_v3.py) changes three things in the v3 text below:
  reclaim window 2 -> 8 bars (breach bar = bar 1; depth = extreme over the whole probe);
  acceptance = no reclaim by the close of bar 8;
  displacement 0.35 -> 0.75 x D1_ATR, and only if no pool on the OTHER side was breached earlier today.
v3 (user Option c, 2026-10-08) REPLACES the v2 ACCUMULATION exits below (v2 kept in amd_state_v2.py):
  Probe   = first bar that trades past an eligible pool (pool eligible only if P0 starts inside it).
  Reclaim = the probe bar or the next bar CLOSES back inside the pool.
            depth (pool to probe extreme) >= 0.15*D1_ATR and reclaim at/before 12:00 UTC
            -> MANIPULATION (sweep below + reclaim = bullish). Shallow or late reclaim just clears the probe.
  Accept  = probe bar and next bar both close beyond the pool -> DIRECT_EXPANSION that way.
  Displacement > 0.35*D1_ATR from P0 -> DIRECT_EXPANSION, but only while no probe is pending
            (otherwise Oct 6's sweep would be pre-empted before its reclaim).
  No 06:00 lockout (T2_FROM_HOUR = 0). Everything after MANIPULATION is unchanged from v2.

v2 (user decision 2026-10-08, after the rollover-ATR finding):
  Volatility basis = D1_ATR14: mean of the last 14 completed UTC-day true ranges BEFORE this day
  (daily TR = max(H-L, |H-prevC|, |L-prevC|) over UTC days that have a 00:00 P0 bar). Constant
  for the whole day, so the 22:00-01:00 UTC lull cannot shrink the gates. Days without 14 prior
  full days are NO_ATR.
  d        = 0.15 * D1_ATR   (manipulation excursion)
  type2    = 0.35 * D1_ATR   (direct-expansion displacement)
  lockout  = DIRECT_EXPANSION may only be declared at or after 06:00 UTC.

Bullish shown; bearish is the exact mirror.
  ACCUMULATION -> MANIPULATION     P0 - runLow > d AND a pool below swept (PDL; Asia low after 06:00 UTC)
  ACCUMULATION -> DIRECT_EXPANSION hour >= 06:00 UTC AND P0 - runLow > type2 AND no pool ABOVE swept.
                                   Manipulation is checked first on the same bar. runLow is the low
                                   since the open, so a displacement built before 06:00 fires at 06:00.
  MANIPULATION -> DIST_EARLY       close > H_ref (latest k=2 pivot high before L_anchor, confirmed by t)
  DIST_EARLY   -> DIST_CONFIRMED   close > P0
  any MANIP/DIST + low < L_anchor  -> MANIPULATION, L_anchor = this bar
  DIRECT_EXPANSION has no exit rule (none specified); it holds to day end. SETTLEMENT not emitted.
Day = UTC calendar day; P0 = open of the 00:00 UTC bar. PDH/PDL = previous day that has a P0
(never the 2-hour Sunday 22:00-24:00 UTC stub).
"""
from __future__ import annotations

import bisect

import numpy as np
import pandas as pd

ACC, MANIP, EARLY, CONF, DIRECT = "ACCUMULATION", "MANIPULATION", "DIST_EARLY", "DIST_CONFIRMED", "DIRECT_EXPANSION"
D_MULT, T2_MULT, ATR_DAYS = 0.15, 0.75, 14   # C2: displacement gate 0.35 -> 0.75 x D1_ATR
T2_FROM_HOUR = 0            # no 06:00 lockout on acceptance/displacement (sensitivity run sets 6)
MANIP_CUTOFF_MIN = 12 * 60  # a reclaim must happen at or before 12:00 UTC to count as manipulation
PROBE_BARS = 8              # C2: breach bar + next 7 bars to reclaim; none -> acceptance at bar 8
ACCEPT_CLOSES = 2           # acceptance also needs >= 2 consecutive closes beyond (always true without a reclaim)
ASIA_END_HOUR = 6           # Asia pools exist only from 06:00 UTC


def _pivots(hi, lo):
    n = len(hi)
    rmax = pd.Series(hi).rolling(5, center=True).max().to_numpy()
    rmin = pd.Series(lo).rolling(5, center=True).min().to_numpy()
    return ([i for i in range(2, n - 2) if hi[i] == rmax[i]], [i for i in range(2, n - 2) if lo[i] == rmin[i]])


def _ref(pivots, arr, anchor, t):
    k = bisect.bisect_left(pivots, min(anchor, t - 1)) - 1
    while k >= 0:
        p = pivots[k]
        if p < anchor and p + 2 <= t:
            return arr[p]
        k -= 1
    return None


def run(df: pd.DataFrame) -> tuple[list, list, list]:
    """df needs open/high/low/close and `utc` (naive UTC). Positional index.

    Returns (state_per_bar, first_trigger_per_day, day_info). first_trigger kinds:
    A | B | UNRESOLVED | AMBIGUOUS | NO_P0 | NO_ATR.
    """
    hi, lo, op, cl = (df[c].to_numpy() for c in ("high", "low", "open", "close"))
    uday = df["utc"].dt.date.to_numpy()
    uhour = df["utc"].dt.hour.to_numpy()
    umin = df["utc"].dt.minute.to_numpy()
    piv_hi, piv_lo = _pivots(hi, lo)
    states = [None] * len(df)
    triggers, info = [], []
    groups = pd.Series(range(len(df))).groupby(uday).apply(list)
    full = []          # completed full days: (idx, high, low, close)
    trs = []           # their true ranges (first one has no prev close -> H-L)
    for day, idx in groups.items():
        if not (uhour[idx[0]] == 0 and umin[idx[0]] == 0):
            triggers.append({"day": str(day), "kind": "NO_P0", "t": None, "dir": 0})
            continue
        dh, dl, dc = hi[idx].max(), lo[idx].min(), cl[idx[-1]]
        if full:
            pc = full[-1][3]
            tr_today = max(dh - dl, abs(dh - pc), abs(dl - pc))
        else:
            tr_today = dh - dl
        if len(trs) < ATR_DAYS:
            triggers.append({"day": str(day), "kind": "NO_ATR", "t": None, "dir": 0})
            full.append((idx, dh, dl, dc)); trs.append(tr_today)
            continue
        D1 = float(np.mean(trs[-ATR_DAYS:]))
        PDH, PDL = full[-1][1], full[-1][2]
        full.append((idx, dh, dl, dc)); trs.append(tr_today)
        d, t2 = D_MULT * D1, T2_MULT * D1
        P0 = op[idx[0]]
        asia = [i for i in idx if uhour[i] < 6]
        AH, AL = (hi[asia].max(), lo[asia].min()) if asia else (None, None)
        st, dr, anchor = ACC, 0, None
        runL = runH = None
        first = None
        events = []
        # pools: side +1 = above (PDH/AsiaH), -1 = below (PDL/AsiaL). Eligible only if P0 starts inside.
        pools = [{"name": "PDH", "side": 1, "lvl": PDH, "from": 0}, {"name": "PDL", "side": -1, "lvl": PDL, "from": 0}]
        if AH is not None:
            pools += [{"name": "AsiaH", "side": 1, "lvl": AH, "from": ASIA_END_HOUR},
                      {"name": "AsiaL", "side": -1, "lvl": AL, "from": ASIA_END_HOUR}]
        pools = [p for p in pools if (P0 < p["lvl"] if p["side"] == 1 else P0 > p["lvl"])]
        for p in pools:
            p["probe"] = None   # {"k", "ext": most extreme price, "n": bars in probe, "run"/"maxrun": closes beyond}
        swept = {1: False, -1: False}   # any eligible pool on that side breached today
        for t in idx:
            runL = lo[t] if runL is None else min(runL, lo[t])
            runH = hi[t] if runH is None else max(runH, hi[t])
            if st == ACC:
                mins = uhour[t] * 60 + umin[t]
                manip_ok = mins <= MANIP_CUTOFF_MIN
                manip, accept = [], []
                for p in pools:
                    if uhour[t] < p["from"]:
                        continue
                    breached = lo[t] < p["lvl"] if p["side"] == -1 else hi[t] > p["lvl"]
                    if breached:
                        swept[p["side"]] = True
                    if p["probe"] is None and breached:
                        p["probe"] = {"k": t, "ext": lo[t] if p["side"] == -1 else hi[t], "n": 0, "run": 0, "maxrun": 0}
                    pr = p["probe"]
                    if pr is None:
                        continue
                    pr["n"] += 1
                    pr["ext"] = min(pr["ext"], lo[t]) if p["side"] == -1 else max(pr["ext"], hi[t])
                    inside = cl[t] > p["lvl"] if p["side"] == -1 else cl[t] < p["lvl"]
                    if inside:
                        depth = abs(p["lvl"] - pr["ext"])
                        if depth >= d and manip_ok:
                            manip.append(-p["side"])          # sweep below + reclaim -> bullish
                        p["probe"] = None                      # shallow / late reclaim just clears it
                    else:
                        pr["run"] += 1
                        pr["maxrun"] = max(pr["maxrun"], pr["run"])
                        if pr["n"] >= PROBE_BARS and pr["maxrun"] >= ACCEPT_CLOSES:
                            accept.append(p["side"])          # no reclaim within the window -> acceptance
                            p["probe"] = None
                if len(set(manip)) > 1 or (manip and accept and set(manip) != set(accept)):
                    first = first or {"day": str(day), "kind": "AMBIGUOUS", "t": t, "dir": 0}
                    states[t] = st
                    break
                pending = any(p["probe"] is not None for p in pools)
                if manip:
                    st, dr = MANIP, manip[0]
                    seg = idx[: idx.index(t) + 1]
                    anchor = int(seg[int(np.argmin(lo[seg]))]) if dr == 1 else int(seg[int(np.argmax(hi[seg]))])
                    events.append(("MANIP", t, dr))
                elif uhour[t] >= T2_FROM_HOUR and accept:
                    st, dr = DIRECT, accept[0]; why = "acceptance"
                elif uhour[t] >= T2_FROM_HOUR and not pending and P0 - runL >= t2 and not swept[1]:
                    st, dr = DIRECT, -1; why = "displacement"                      # macro displacement down, no pool above swept
                elif uhour[t] >= T2_FROM_HOUR and not pending and runH - P0 >= t2 and not swept[-1]:
                    st, dr = DIRECT, 1; why = "displacement"
                if st == DIRECT:
                    first = first or {"day": str(day), "kind": "B", "t": t, "dir": dr, "why": why}
                    events.append(("TYPE2", t, dr))
                states[t] = st
                continue
            if st == DIRECT:
                states[t] = st
                continue
            if dr == 1:
                if lo[t] < lo[anchor]:
                    if st != MANIP:
                        events.append(("RESET", t, dr))
                    st, anchor = MANIP, t
                ref = _ref(piv_hi, hi, anchor, t)
                if st == MANIP and ref is not None and cl[t] > ref:
                    st = EARLY; events.append(("EARLY", t, dr))
                if st == EARLY and cl[t] > P0:
                    st = CONF; events.append(("CONF", t, dr))
                    first = first or {"day": str(day), "kind": "A", "t": t, "dir": dr}
            else:
                if hi[t] > hi[anchor]:
                    if st != MANIP:
                        events.append(("RESET", t, dr))
                    st, anchor = MANIP, t
                ref = _ref(piv_lo, lo, anchor, t)
                if st == MANIP and ref is not None and cl[t] < ref:
                    st = EARLY; events.append(("EARLY", t, dr))
                if st == EARLY and cl[t] < P0:
                    st = CONF; events.append(("CONF", t, dr))
                    first = first or {"day": str(day), "kind": "A", "t": t, "dir": dr}
            states[t] = st
        triggers.append(first or {"day": str(day), "kind": "UNRESOLVED", "t": None, "dir": 0})
        info.append({"day": str(day), "start": idx[0], "end": idx[-1], "P0": P0, "PDH": PDH, "PDL": PDL,
                     "D1_ATR": D1, "d": d, "t2": t2,
                     "asia_end": asia[-1] if asia else None, "AH": AH, "AL": AL, "events": events,
                     "anchor": anchor})
    return states, triggers, info
