"""Independent replica of Codex's frozen H8 SELECTED_FEATURE rule (HTF-XAUUSD-RR-GRID-V1), run on XAUUSD
M15 history. Read-only on the repo; writes only to the path given as argv[2].

Rule (docs/research/htf-rr-grid-v1/specification.json in the Codex worktree):
  H4 = broker-time 4h bucket with exactly 16 M15 children; H8 = two adjacent complete H4s at 00/08/16.
  ATR = simple mean of 14 TR over trailing complete H8 parents (needs 15).
  LONG if lower_wick_ratio >= 0.2; SHORT if body_ratio <= 0.33; both -> conflict (book skips).
  Entry: first M15 OPEN within 120 min after the H8 close. LONG E = open + spread + slip; SHORT E = open - slip.
  Stop: LONG low - 0.2 ATR (bid); SHORT high + 0.2 ATR + spread (ask).
  D = R + stop_slip + commission; TP = E + d*(m*D + exit_slip + commission). SL first on same bar.
Costs BASE: spread .09, entry slip .09, stop/exit slip .09, commission .08 RT. Funding: LONG -0.5759,
SHORT +0.39793 USD/oz per broker midnight, Wednesday x3.
"""
import sys, json
import numpy as np
import pandas as pd

import os
TF = os.environ.get("TF", "H8")
SPREAD, SLIP, COMM = 0.09, 0.09, 0.08
CARRY = {1: -0.5759, -1: 0.39793}
GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]

def load(path, start=None, end=None):
    m = pd.read_csv(path); m["timestamp"] = pd.to_datetime(m["timestamp"])
    m = m.sort_values("timestamp").reset_index(drop=True)
    return m

def parents(m):
    b4 = m["timestamp"].dt.floor("4h")
    g = m.groupby(b4)
    h4 = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                       "close": g["close"].last(), "n": g.size()})
    h4 = h4[h4["n"] == 16]
    if TF == "H4":
        pc = h4["close"].shift(1)
        tr = np.maximum(h4["high"] - h4["low"], np.maximum((h4["high"] - pc).abs(), (h4["low"] - pc).abs()))
        h4["atr"] = tr.rolling(14).mean()
        return h4
    rows = []
    for t in h4.index:
        if t.hour not in (0, 8, 16): continue
        t2 = t + pd.Timedelta(hours=4)
        if t2 not in h4.index: continue
        a, b = h4.loc[t], h4.loc[t2]
        rows.append(dict(t=t, open=a.open, high=max(a.high, b.high), low=min(a.low, b.low), close=b.close))
    h8 = pd.DataFrame(rows).set_index("t")
    pc = h8["close"].shift(1)
    tr = np.maximum(h8["high"] - h8["low"], np.maximum((h8["high"] - pc).abs(), (h8["low"] - pc).abs()))
    h8["atr"] = tr.rolling(14).mean()          # trailing complete parents incl. this one (TR of 14 parents, 15 needed)
    return h8

def candidates(m, h8, score_from=None, score_to=None):
    ts = m["timestamp"]; idx = pd.Series(np.arange(len(m)), index=ts)
    out = []
    for t, p in h8.iterrows():
        if np.isnan(p.atr): continue
        if score_from is not None and t < score_from: continue
        if score_to is not None and t >= score_to: continue
        close_at = t + pd.Timedelta(hours=8 if TF == "H8" else 4)
        j = ts.searchsorted(close_at)
        if j >= len(m) or ts.iloc[j] > close_at + pd.Timedelta(minutes=120): continue
        rng = p.high - p.low
        if rng <= 0: continue
        body = abs(p.close - p.open); lw = min(p.open, p.close) - p.low
        sides = []
        if TF == "H8":
            if lw / rng >= 0.2: sides.append(1)
            if body / rng <= 0.33: sides.append(-1)
        else:   # H4 frozen cuts: LONG body_ratio >= 0.66; SHORT body_strength = clip(body/ATR, 0, 3) <= 0.5
            if body / rng >= 0.66: sides.append(1)
            if min(max(body / p.atr, 0.0), 3.0) <= 0.5: sides.append(-1)
        for d in sides:
            o = m["open"].iloc[j]
            E = o + SPREAD + SLIP if d == 1 else o - SLIP
            SL = p.low - 0.2 * p.atr if d == 1 else p.high + 0.2 * p.atr + SPREAD
            R = d * (E - SL)
            if R <= 0: continue
            out.append(dict(signal=t, entry_at=ts.iloc[j], j=int(j), d=d, E=E, SL=SL, R=R, D=R + SLIP + COMM,
                            conflict=len(sides) > 1))
    return out

def walk(m, c, m_rr, end_j):
    """Return (status, exit_at, net_R) for one target multiple; SL first on a shared bar."""
    d, E, SL, D = c["d"], c["E"], c["SL"], c["D"]
    TP = E + d * (m_rr * D + SLIP + COMM)
    H, L, T = m["high"].to_numpy(), m["low"].to_numpy(), m["timestamp"]
    nights = 0; last_day = T.iloc[c["j"]].normalize()
    for k in range(c["j"], end_j):
        day = T.iloc[k].normalize()
        if day > last_day:
            for dd in pd.date_range(last_day + pd.Timedelta(days=1), day):
                nights += 3 if dd.dayofweek == 3 else 1      # Wed->Thu rollover counted triple
            last_day = day
        # bid H/L; ask = bid + spread
        stop = (L[k] <= SL) if d == 1 else (H[k] + SPREAD >= SL)
        tgt = (H[k] >= TP) if d == 1 else (L[k] + SPREAD <= TP)
        carry = CARRY[d] * nights
        if stop:
            O = m["open"].iat[k]
            if k > c["j"] and (O <= SL if d == 1 else O + SPREAD >= SL):     # gapped through the stop: fill at the open
                fill = O - SLIP if d == 1 else O + SPREAD + SLIP
            else:
                fill = SL - SLIP if d == 1 else SL + SLIP
            return "SL", T.iloc[k], (d * (fill - E) - COMM + carry) / D, k
        if tgt:
            fill = TP - SLIP if d == 1 else TP + SLIP
            return "TP", T.iloc[k], (d * (fill - E) - COMM + carry) / D, k
    return "OPEN", None, None, end_j

def mfe(m, c, end_j):
    d, E, SL, R = c["d"], c["E"], c["SL"], c["R"]
    H, L = m["high"].to_numpy(), m["low"].to_numpy(); best = 0.0
    for k in range(c["j"], end_j):
        if (L[k] <= SL) if d == 1 else (H[k] + SPREAD >= SL): break
        fav = (H[k] - E) if d == 1 else (E - (L[k] + SPREAD))
        best = max(best, fav / c["D"])
    return best

def book(cands, results, m_rr):
    """One position at a time, conflict signals skipped (Codex book rule). Net in ordinary R."""
    busy = None; trades = []; skipped = 0; conflicts = 0
    by_at = {}
    for c in cands: by_at.setdefault(c["entry_at"], []).append(c)
    for at in sorted(by_at):
        if busy is not None and at <= busy: skipped += 1; continue
        items = by_at[at]
        if len(items) > 1: conflicts += 1; continue
        c = items[0]; st, ex, r, _ = results[(c["signal"], c["d"], m_rr)]
        if st == "OPEN": trades.append(dict(c=c, st=st, r=None)); break
        trades.append(dict(c=c, st=st, r=r, exit=ex)); busy = ex
    return trades, skipped, conflicts

if __name__ == "__main__":
    path = sys.argv[1]; out_path = sys.argv[2]
    sf = pd.Timestamp(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    st_ = pd.Timestamp(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    m = load(path); h8 = parents(m)
    cands = candidates(m, h8, sf, st_)
    end_j = len(m)
    res = {}
    for c in cands:
        c["mfe"] = mfe(m, c, end_j)
        for g in GRID: res[(c["signal"], c["d"], g)] = walk(m, c, g, end_j)
    summary = {"corpus": path, "rows": len(m), "first": str(m.timestamp.iloc[0]), "last": str(m.timestamp.iloc[-1]),
               "h8_parents": int(h8["atr"].notna().sum()), "candidates": len(cands), "grid": {}}
    for g in GRID:
        rs = [res[(c["signal"], c["d"], g)] for c in cands]
        settled = [x for x in rs if x[0] != "OPEN"]
        nr = np.array([x[2] for x in settled])
        tr, sk, cf = book(cands, res, g)
        br = np.array([t["r"] for t in tr if t["r"] is not None])
        by_side = {}
        for d in (1, -1):
            s = np.array([res[(c["signal"], c["d"], g)][2] for c in cands if c["d"] == d and res[(c["signal"], c["d"], g)][0] != "OPEN"])
            by_side["LONG" if d == 1 else "SHORT"] = dict(n=len(s), win=float((s > 0).mean()) if len(s) else None, mean_r=float(s.mean()) if len(s) else None)
        summary["grid"][g] = dict(candidates_settled=len(settled), open=len(rs) - len(settled), win_rate=float((nr > 0).mean()),
                                  mean_r=float(nr.mean()), sum_r=float(nr.sum()), by_side=by_side,
                                  book_trades=len(br), book_wins=int((br > 0).sum()), book_sum_r=float(br.sum()),
                                  book_mean_r=float(br.mean()) if len(br) else None, book_skipped_busy=sk, book_conflicts=cf,
                                  book_open_at_end=any(t["r"] is None for t in tr))
    mf = np.array([c["mfe"] for c in cands])
    summary["mfe"] = {"median": float(np.median(mf)), "p75": float(np.percentile(mf, 75)), "p90": float(np.percentile(mf, 90)),
                      "share_reaching": {str(g): float((mf >= g).mean()) for g in GRID}}
    by_year = {}
    for g in (1.5, 3.0, 5.0):
        for c in cands:
            x = res[(c["signal"], c["d"], g)]
            if x[0] == "OPEN": continue
            k = (str(c["signal"].year) + ("H1" if c["signal"].month <= 6 else "H2"), g)
            by_year.setdefault(k, []).append(x[2])
    summary["by_half_year"] = {f"{k[0]} {k[1]}R": dict(n=len(v), mean_r=float(np.mean(v)), sum_r=float(np.sum(v))) for k, v in sorted(by_year.items())}
    summary["trades_1_5_3_5"] = [dict(signal=str(c["signal"]), side="LONG" if c["d"] == 1 else "SHORT", entry_at=str(c["entry_at"]),
                                      E=round(c["E"], 2), SL=round(c["SL"], 2), mfe=round(c["mfe"], 2), conflict=c["conflict"],
                                      **{f"r{g}": (None if res[(c["signal"], c["d"], g)][2] is None else round(res[(c["signal"], c["d"], g)][2], 3)) for g in (1.5, 3.0, 5.0)})
                                 for c in cands]
    json.dump(summary, open(out_path, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("trades_1_5_3_5", "by_half_year")}, indent=1, default=str))
